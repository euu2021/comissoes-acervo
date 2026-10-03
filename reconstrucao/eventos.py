# -*- coding: utf-8 -*-
"""
Eventos do feed diário do SPLEGIS: interpretação e correções.

O feed registra cada tramitação como texto:
  "tramitada da área X para a área Y.  Motivo: …  Obs: …"   envio
  "recebida na área Y (enviada da área X)."                   recebimento
  "excluída tramitação da área X para a área Y."              envio desfeito
  "excluído recebimento na área Y."                           recebimento desfeito
  "tramitação interna - C/Área/Passo - comentário"            passo interno na comissão C
  "excluída tramitação interna - C/Área/Passo"                passo interno desfeito (até 2021)

Duas falhas da fonte são corrigidas antes da reconstrução (ver `corrigir`).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from reconstrucao import fontes

COMISSOES = {"ADM", "CCJ", "ECON", "EDUC", "FIN", "SAUDE", "URB"}
# Tipos que o relatório "Projetos em Análise nas Comissões" lista (RDS, por exemplo, não).
TIPOS_DO_RELATORIO = {"ANU", "DOCREC", "MOC", "PDL", "PL", "PLO", "PR", "RDP", "REC", "RPP", "RSC"}
EXTERNOS = ("envio", "receb", "excl_envio", "excl_receb")


@dataclass(slots=True)
class Evento:
    t: str                  # data e hora (ISO, horário de Brasília)
    ordem: int              # posição no feed, para desempate
    rotulo: str             # "PL 502/2026"
    tipo: str               # envio | receb | excl_envio | excl_receb | interna | excl_interna | outro
    de: str = ""
    para: str = ""
    comissao: str = ""      # tramitação interna: comissão onde ocorreu
    area: str = ""
    passo: str = ""
    comentario: str = ""


_RX_PREFIXO = re.compile(r"^Matéria [^:]*: ?")
_RX_RECEB = re.compile(r"^recebida na área (.+) \(enviada da área (.+)\)\.?$", re.S)
_RX_EXCL_RECEB = re.compile(r"^excluído recebimento na área (.+?)\.?$", re.S)
_RX_EXCL_ENVIO = re.compile(r"^excluída tramitação da área (.+?) para a área (.+?)\.?$", re.S)
_RX_ENVIO = re.compile(r"^tramitada da área (.+?) para a área (.+?)\.?$", re.S)
_INTERNA = "tramitação interna - "
_EXCL_INTERNA = "excluída tramitação interna - "


def _passo_interno(resto: str, tipo: str) -> dict | None:
    """"C/Área/Passo - comentário" -> campos; com comentário vazio, o texto termina em " -"."""
    partes = resto.split("/", 2)
    if len(partes) != 3:
        return None
    passo, *comentario = re.split(r"\s+-(?:\s+|$)", partes[2], maxsplit=1)
    return {"tipo": tipo, "comissao": partes[0].strip(), "area": partes[1].strip(),
            "passo": passo.strip(), "comentario": "".join(comentario).strip()}


def _linhas(texto: str) -> str:
    return texto.replace("\r\n", "\n").replace("\r", "\n").strip()


def interpretar(texto: str) -> dict:
    corpo = _RX_PREFIXO.sub("", _linhas(texto), count=1).strip()
    if corpo.startswith(_INTERNA):
        if campos := _passo_interno(corpo[len(_INTERNA):], "interna"):
            return campos
    if corpo.startswith(_EXCL_INTERNA):
        if campos := _passo_interno(corpo[len(_EXCL_INTERNA):], "excl_interna"):
            return campos
    if m := _RX_RECEB.match(corpo):
        return {"tipo": "receb", "para": m[1].strip(), "de": m[2].strip()}
    if m := _RX_EXCL_RECEB.match(corpo):
        return {"tipo": "excl_receb", "para": m[1].strip()}
    if m := _RX_EXCL_ENVIO.match(corpo):
        return {"tipo": "excl_envio", "de": m[1].strip(), "para": m[2].strip()}
    # "Motivo:" e "Obs:" vêm depois de dois espaços; nomes de área podem ter ponto ("LIDER. PT").
    if m := _RX_ENVIO.match(corpo.split("  ")[0].strip()):
        return {"tipo": "envio", "de": m[1].strip(), "para": m[2].strip()}
    return {"tipo": "outro"}


@dataclass(slots=True)
class FichaFeed:
    """O que o feed informa sobre cada matéria (a versão mais recente vista)."""
    tipo_cod: int
    sigla: str
    numero: int
    ano: int
    ementa: str
    autores: list


def carregar(inicio: date, fim: date, ate: str) -> tuple[list[Evento], dict[str, FichaFeed]]:
    """Eventos de `inicio` a `fim` com data até `ate`, em ordem cronológica."""
    eventos: list[Evento] = []
    fichas: dict[str, FichaFeed] = {}
    d = inicio
    while d <= fim:
        for item in fontes.eventos_do_dia(d):
            rotulo = f"{item['Sigla']} {item['Numero']}/{item['Ano']}"
            fichas[rotulo] = FichaFeed(item["Tipo"], item["Sigla"], item["Numero"], item["Ano"],
                                       _linhas(item.get("Ementa") or ""), item.get("Autores") or [])
            for e in item["Eventos"]:
                t = e["Data"][:19]
                if t <= ate:
                    eventos.append(Evento(t=t, ordem=len(eventos), rotulo=rotulo,
                                          **interpretar(e["Descricao"])))
        d += timedelta(days=1)
    eventos.sort(key=lambda e: (e.t, e.ordem))
    return eventos, fichas


def por_materia(eventos: list[Evento]) -> dict[str, list[Evento]]:
    grupos: dict[str, list[Evento]] = defaultdict(list)
    for e in eventos:
        grupos[e.rotulo].append(e)
    return grupos


# ----------------------------------------------------------------------------- correções
def _trocar_dia_mes(t: str) -> str | None:
    d = datetime.fromisoformat(t)
    try:
        return d.replace(month=d.day, day=d.month).isoformat()
    except ValueError:
        return None


def recebimentos_suspeitos(eventos: list[Evento]) -> list[Evento]:
    """Recebimentos que envolvem comissão e estão fora de lugar na sequência da matéria:
    sem envio pendente para a mesma área (inclusive o primeiro evento da matéria), ou
    depois de passos internos na área quando a data com dia e mês trocados cairia dentro
    da estada. Desde 2020 é comum haver passo interno antes do recebimento formal, então
    só isso não basta para suspeitar."""
    suspeitos = []
    for evs in por_materia(eventos).values():
        loc, entrada, pendente, internas = None, None, False, False
        for e in evs:
            if e.tipo == "envio":
                loc, entrada, pendente, internas = e.para, e.t, True, False
            elif e.tipo == "receb":
                if e.para in COMISSOES or loc in COMISSOES:
                    trocada = _trocar_dia_mes(e.t)
                    if loc != e.para or not pendente:
                        suspeitos.append(e)
                    elif internas and trocada and entrada and entrada <= trocada < e.t:
                        suspeitos.append(e)
                loc, pendente = e.para, False
            elif e.tipo == "excl_receb":
                pendente = True
            elif e.tipo == "excl_envio":
                loc, entrada, pendente, internas = e.de, None, False, False
            elif e.tipo == "interna" and e.comissao == loc:
                internas = True
    return suspeitos


def _recebimentos_no_historico(linhas: list[tuple[str, str, str]], area: str) -> list[str]:
    return [ti for ti, acao, _ in linhas if acao in (area, f"{area}/Recebido")]


def _perto(a: str, b: str) -> bool:
    return abs(datetime.fromisoformat(a) - datetime.fromisoformat(b)) <= timedelta(days=1)


def corrigir(eventos: list[Evento], fichas: dict[str, FichaFeed], ids_conhecidos: dict[str, str],
             inicio: str) -> tuple[list[Evento], Counter, list]:
    """Corrige duas falhas do feed:

    1. Recebimento com dia e mês trocados (o de 09/04 aparece em 04/09), o que faz a
       matéria voltar a uma comissão de onde já saiu. Cada recebimento suspeito é
       conferido no histórico oficial da matéria: se lá o recebimento está na data com
       dia e mês trocados, o evento é movido para ela, junto com a tramitação interna
       automática do mesmo instante ("Designar Relator"). Se a data certa for anterior ao
       início do feed (`inicio`), o evento sai: o estado inicial já o reflete.
    2. Exclusão de recebimento ou de envio seguida de tramitação interna na comissão
       afetada, sem nova tramitação externa no meio: foi correção (o lançamento foi
       refeito com a data antiga), pois matéria fora da comissão não tramita nela.
       A exclusão é desconsiderada.

    Devolve os eventos corrigidos, a contagem por desfecho e a lista das correções."""
    cont: Counter = Counter()
    correcoes: list[tuple] = []

    suspeitos = recebimentos_suspeitos(eventos)
    chaves = {e.rotulo: (fichas[e.rotulo].tipo_cod, fichas[e.rotulo].numero, fichas[e.rotulo].ano)
              for e in suspeitos if e.rotulo not in ids_conhecidos}
    ids = {**fontes.buscar_ids(chaves), **ids_conhecidos}
    fontes.baixar_historicos([ids[e.rotulo] for e in suspeitos if e.rotulo in ids])

    mover: dict[tuple, str] = {}  # (rótulo, instante, área) -> instante certo
    for e in suspeitos:
        if e.rotulo not in ids:
            cont["recebimento suspeito sem id"] += 1
            continue
        linhas = fontes.historico(ids[e.rotulo])
        if not linhas:
            cont["recebimento suspeito sem histórico"] += 1
            continue
        oficiais = _recebimentos_no_historico(linhas, e.para)
        trocado = _trocar_dia_mes(e.t)
        if any(_perto(o, e.t) for o in oficiais):
            cont["recebimento suspeito confirmado"] += 1
        elif trocado and (certo := next((o for o in oficiais if _perto(o, trocado)), None)):
            cont["recebimento com dia/mês trocados (movido)"] += 1
            mover[(e.rotulo, e.t, e.para)] = certo
            correcoes.append(("data trocada", e.rotulo, e.para, e.t, certo))
        else:
            cont["recebimento suspeito não resolvido (mantido)"] += 1

    for e in eventos:
        alvo = mover.get((e.rotulo, e.t, e.para if e.tipo == "receb" else e.comissao))
        if alvo and e.tipo in ("receb", "interna"):
            e.t = alvo

    descartar = set()
    for evs in por_materia(eventos).values():
        evs.sort(key=lambda e: (e.t, e.ordem))
        for i, e in enumerate(evs):
            if e.tipo == "excl_receb":
                area = e.para
            elif e.tipo == "excl_envio":
                area = e.para
            else:
                continue
            if area not in COMISSOES:
                continue
            for s in evs[i + 1:]:
                if s.tipo in EXTERNOS:
                    break
                if s.tipo == "interna" and s.comissao == area:
                    descartar.add(id(e))
                    cont[f"{e.tipo} desconsiderada"] += 1
                    correcoes.append(("exclusão contradita", e.rotulo, area, e.t, ""))
                    break

    corrigidos = [e for e in eventos if id(e) not in descartar and e.t >= inicio]
    corrigidos.sort(key=lambda e: (e.t, e.ordem))
    return corrigidos, cont, correcoes
