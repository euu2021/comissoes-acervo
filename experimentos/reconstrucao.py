# -*- coding: utf-8 -*-
"""
TESTE de reconstrução retroativa do acervo das Comissões a partir dos eventos do SPLEGIS.

O webservice MateriasEventosJSON devolve, por dia, todas as tramitações registradas
(envios, recebimentos, exclusões e tramitações internas). Partindo do retrato real
mais recente (dados/acervo.csv), dá para saber em qual comissão cada matéria estava,
e em que passo da tramitação interna, ao fim de cada dia de uma janela.

Validações:
  A. estado final: os eventos, aplicados em ordem, devem levar cada matéria à
     comissão e ao passo interno que o retrato real mostra;
  B. coerência: toda tramitação interna numa comissão deve acontecer enquanto a
     reconstrução diz que a matéria está naquela comissão;
  C. presença diária: numa amostra, compara dia a dia a reconstrução com o histórico
     de movimentações da própria matéria (Pesquisa/HistoricoMovimentacoes), uma fonte
     independente do feed de eventos.

Uso (da raiz):  python -m experimentos.reconstrucao --inicio 2026-08-01 --fim 2026-10-02
"""
from __future__ import annotations

import argparse
import html
import json
import random
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path

from coletor import config as C
from coletor.util import gravar_csv, ler_csv, log

DIR = Path(__file__).resolve().parent
CACHE = DIR / "cache"
SAIDA = DIR / "saida"

COMISSOES = set(C.COMISSOES)
PROJETOS = {"PL", "PDL", "PR", "PLO"}
EXTERNOS = ("envio", "receb", "excl_envio", "excl_receb")

URL_EVENTOS = ("https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx/"
               "MateriasEventosJSON?dataPesquisa={}")
URL_DETALHE = ("https://splegisconsulta.saopaulo.sp.leg.br/Pesquisa/"
               "DetailsMateriaTramitacaoLegislativa?tipo={}&numero={}&ano={}")
URL_HISTORICO = ("https://splegisconsulta.saopaulo.sp.leg.br/Pesquisa/"
                 "HistoricoMovimentacoes?id={}")


# ----------------------------------------------------------------------------- HTTP com cache
def _baixar(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": C.USER_AGENT})
    for tentativa in range(1, C.TENTATIVAS + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                texto = r.read().decode("utf-8")
            time.sleep(0.2)  # cortesia com o servidor
            return texto
        except OSError as e:
            if tentativa == C.TENTATIVAS:
                raise
            log(f"  falha ({e}); nova tentativa em {10 * tentativa} s")
            time.sleep(10 * tentativa)
    raise AssertionError("inalcançável")


def _com_cache(caminho: Path, url: str, gravar: bool = True) -> str:
    if caminho.exists():
        return caminho.read_text(encoding="utf-8")
    texto = _baixar(url)
    if gravar:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto, encoding="utf-8")
    return texto


# ----------------------------------------------------------------------------- eventos
@dataclass
class Evento:
    t: str
    ordem: int
    rotulo: str
    tipo: str               # envio | receb | excl_envio | excl_receb | interna | excl_interna | outro
    de: str = ""
    para: str = ""
    comissao: str = ""      # tramitação interna: comissão onde ocorreu
    area: str = ""
    passo: str = ""
    comentario: str = ""
    texto: str = ""


_RX_PREFIXO = re.compile(r"^Matéria [^:]*: ?")
_RX_RECEB = re.compile(r"^recebida na área (.+) \(enviada da área (.+)\)\.?$", re.S)
_RX_EXCL_RECEB = re.compile(r"^excluído recebimento na área (.+?)\.?$", re.S)
_RX_EXCL_ENVIO = re.compile(r"^excluída tramitação da área (.+?) para a área (.+?)\.?$", re.S)
_RX_ENVIO = re.compile(r"^tramitada da área (.+?) para a área (.+?)\.?$", re.S)
_INTERNA = "tramitação interna - "


def interpretar(texto: str) -> dict:
    corpo = _RX_PREFIXO.sub("", texto, count=1).strip()
    if corpo.startswith(_INTERNA):
        partes = corpo[len(_INTERNA):].split("/", 2)
        if len(partes) == 3:
            # "Passo - comentário"; com comentário vazio, o texto termina em " -".
            passo, *comentario = re.split(r"\s+-(?:\s+|$)", partes[2], maxsplit=1)
            return {"tipo": "interna", "comissao": partes[0].strip(), "area": partes[1].strip(),
                    "passo": passo.strip(), "comentario": "".join(comentario).strip()}
    if corpo.startswith("excluída tramitação interna"):
        return {"tipo": "excl_interna"}
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


def carregar_eventos(inicio: date, fim: date) -> tuple[list[Evento], dict[str, tuple]]:
    """Eventos da janela em ordem cronológica e o (tipo, número, ano) de cada rótulo."""
    hoje = datetime.now(C.FUSO).date()
    eventos: list[Evento] = []
    chaves: dict[str, tuple] = {}
    d = inicio
    while d <= fim:
        # O dia corrente ainda vai ganhar eventos: não entra no cache.
        texto = _com_cache(CACHE / "eventos" / f"{d}.json", URL_EVENTOS.format(d), gravar=d < hoje)
        for item in json.loads(texto):
            rotulo = f"{item['Sigla']} {item['Numero']}/{item['Ano']}"
            chaves[rotulo] = (item["Tipo"], item["Numero"], item["Ano"])
            for e in item["Eventos"]:
                eventos.append(Evento(t=e["Data"][:19], ordem=len(eventos), rotulo=rotulo,
                                      texto=e["Descricao"], **interpretar(e["Descricao"])))
        d += timedelta(days=1)
    eventos.sort(key=lambda e: (e.t, e.ordem))
    return eventos, chaves


# ----------------------------------------------------------------------------- linha do tempo
@dataclass
class Trecho:
    """Situação externa de uma matéria a partir de `inicio` (None = desde antes da janela).

    `estada` é quando a matéria foi enviada a `loc` (None = antes da janela). Campos
    None são desconhecidos; recebido_em "" significa envio pendente de recebimento."""
    inicio: str | None
    loc: str | None
    estada: str | None
    enviado_por: str | None = None
    enviado_em: str | None = None
    recebido_em: str | None = None
    fim_estada: str | None = None


def linha_do_tempo(externos: list[Evento], ancora: dict | None) -> tuple[list[Trecho], list[str]]:
    """Trechos de localização de uma matéria na janela, e as incoerências encontradas.

    Sem eventos externos, a matéria ficou parada: vale o retrato (`ancora`). Com eventos,
    a situação anterior ao primeiro deles é deduzida do próprio evento."""
    if not externos:
        if ancora is None:
            return [Trecho(None, None, None)], []
        return [Trecho(None, ancora["comissao"], None, ancora["enviado_por"],
                       ancora["enviado_em"], ancora["recebido_em"])], []

    anomalias: list[str] = []
    e0 = externos[0]
    if e0.tipo == "envio":
        atual = Trecho(None, e0.de, None)
    elif e0.tipo == "receb":
        atual = Trecho(None, e0.para, None, e0.de, None, "")
    else:  # exclusões: antes delas a matéria estava no destino
        atual = Trecho(None, e0.para, None, e0.de or None)
    trechos = [atual]

    for e in externos:
        if e.tipo == "envio":
            if atual.loc != e.de:
                anomalias.append(f"{e.t} enviada de {e.de} estando em {atual.loc}")
            atual = Trecho(e.t, e.para, e.t, e.de, e.t, "")
        elif e.tipo == "receb":
            if atual.loc != e.para:
                anomalias.append(f"{e.t} recebida em {e.para} estando em {atual.loc}")
                atual = Trecho(e.t, e.para, e.t, e.de, None, e.t)
            else:
                atual = replace(atual, inicio=e.t, recebido_em=e.t)
        elif e.tipo == "excl_receb":
            if atual.loc != e.para:
                anomalias.append(f"{e.t} recebimento excluído em {e.para} estando em {atual.loc}")
            atual = replace(atual, inicio=e.t, loc=e.para, recebido_em="")
        else:  # excl_envio: a matéria volta à estada anterior em `de`
            if atual.loc != e.para:
                anomalias.append(f"{e.t} envio para {e.para} excluído estando em {atual.loc}")
            anterior = next((t for t in reversed(trechos)
                             if t.loc == e.de and (t.loc, t.estada) != (atual.loc, atual.estada)),
                            None)
            atual = replace(anterior, inicio=e.t) if anterior else Trecho(e.t, e.de, None)
        trechos.append(atual)

    for i, tr in enumerate(trechos):
        tr.fim_estada = next((t.inicio for t in trechos[i + 1:]
                              if (t.loc, t.estada) != (tr.loc, tr.estada)), None)
    return trechos, anomalias


def trecho_em(t: str, trechos: list[Trecho]) -> Trecho:
    vigente = trechos[0]
    for tr in trechos[1:]:
        if tr.inicio <= t:
            vigente = tr
        else:
            break
    return vigente


def interna_em(t: str, tr: Trecho, internas: list[Evento],
               ancora: dict | None) -> tuple[tuple | None, str]:
    """Tramitação interna vigente em t: ((data, área, passo, comentário), fonte).
    Valor None = desconhecido (anterior à janela)."""
    da_estada = [e for e in internas if e.comissao == tr.loc
                 and (tr.estada is None or e.t >= tr.estada)
                 and (tr.fim_estada is None or e.t < tr.fim_estada)]
    vistos = [e for e in da_estada if e.t <= t]
    if vistos:
        e = vistos[-1]
        return (e.t, e.area, e.passo, e.comentario), "evento"
    if tr.estada is not None:  # chegou durante a janela e ainda não teve tramitação interna
        return ("", "", "", ""), "chegada"
    if (not da_estada and tr.fim_estada is None and ancora is not None
            and ancora["comissao"] == tr.loc and ancora["interna_data"] <= t):
        return (ancora["interna_data"], ancora["interna_area"], ancora["interna_tipo"],
                ancora["interna_comentario"]), "retrato"
    return None, "desconhecida"


@dataclass
class Materia:
    rotulo: str
    trechos: list[Trecho]
    internas: list[Evento]
    anomalias: list[str]
    ancora: dict | None

    @property
    def movimentada(self) -> bool:
        return len(self.trechos) > 1


def reconstruir(eventos: list[Evento], acervo: list[dict]) -> dict[str, Materia]:
    por_rotulo: dict[str, list[Evento]] = defaultdict(list)
    for e in eventos:
        por_rotulo[e.rotulo].append(e)
    ancoras = {r["rotulo"]: r for r in acervo}
    materias = {}
    for rotulo in sorted(set(por_rotulo) | set(ancoras)):
        evs = por_rotulo.get(rotulo, [])
        trechos, anomalias = linha_do_tempo([e for e in evs if e.tipo in EXTERNOS],
                                            ancoras.get(rotulo))
        materias[rotulo] = Materia(rotulo, trechos, [e for e in evs if e.tipo == "interna"],
                                   anomalias, ancoras.get(rotulo))
    return materias


def serie_diaria(materias: dict[str, Materia], dias: list[date]) -> list[dict]:
    linhas = []
    for d in dias:
        t = f"{d}T23:59:59"
        cont: dict[str, Counter] = defaultdict(Counter)
        for m in materias.values():
            tr = trecho_em(t, m.trechos)
            if tr.loc not in COMISSOES:
                continue
            c = cont[tr.loc]
            c["materias"] += 1
            c["projetos"] += m.rotulo.split()[0] in PROJETOS
            c["recebimento_conhecido"] += tr.recebido_em is not None
            c["interna_conhecida"] += interna_em(t, tr, m.internas, m.ancora)[0] is not None
        for sigla in sorted(COMISSOES):
            linhas.append({"data": str(d), "comissao": sigla,
                           **{k: str(cont[sigla][k]) for k in
                              ("materias", "projetos", "recebimento_conhecido", "interna_conhecida")}})
    return linhas


# ----------------------------------------------------------------------------- validações
def validar_estado_final(materias: dict[str, Materia], t_retrato: str) -> dict:
    """A. Onde os eventos dizem que cada matéria movimentada terminou × retrato real."""
    loc, receb, interna = Counter(), Counter(), Counter()
    exemplos: dict[str, list] = defaultdict(list)
    for m in materias.values():
        tr = trecho_em(t_retrato, m.trechos)
        real = m.ancora["comissao"] if m.ancora else None
        if m.movimentada:
            previsto = tr.loc if tr.loc in COMISSOES else None
            if previsto == real:
                loc["acertos"] += 1
            else:
                loc["erros"] += 1
                exemplos["local"].append((m.rotulo, previsto, real, m.anomalias[-3:]))
            if previsto == real and real and tr.recebido_em is not None:
                if tr.recebido_em == m.ancora["recebido_em"]:
                    receb["acertos"] += 1
                else:
                    receb["erros"] += 1
                    exemplos["recebimento"].append((m.rotulo, tr.recebido_em, m.ancora["recebido_em"]))
        if m.ancora and tr.loc == real:
            valor, fonte = interna_em(t_retrato, tr, m.internas, m.ancora)
            if fonte in ("evento", "chegada"):
                real_int = (m.ancora["interna_data"], m.ancora["interna_area"],
                            m.ancora["interna_tipo"], m.ancora["interna_comentario"])
                if valor[:3] == real_int[:3]:
                    interna["acertos"] += 1
                    interna["comentario difere"] += valor[3] != real_int[3]
                else:
                    interna["erros"] += 1
                    exemplos["interna"].append((m.rotulo, valor, real_int))
    return {"local": loc, "recebimento": receb, "interna": interna, "exemplos": exemplos}


def validar_coerencia(materias: dict[str, Materia]) -> dict:
    """B. Toda tramitação interna em comissão deve ocorrer com a matéria naquela comissão."""
    cont, exemplos = Counter(), []
    for m in materias.values():
        for e in m.internas:
            if e.comissao not in COMISSOES:
                continue
            loc = trecho_em(e.t, m.trechos).loc
            if loc == e.comissao:
                cont["coerentes"] += 1
            else:
                cont["incoerentes"] += 1
                exemplos.append((m.rotulo, e.t, e.comissao, loc))
    return {"cont": cont, "exemplos": exemplos}


_RX_H_ENVIO = re.compile(r"^([^/]+)/Encaminhado para (.+)$")
_RX_ID = re.compile(r"GerarArquivoProcessoPorID/(\d+)|id: '(\d+)'")


def historico_da_materia(materia_id: str) -> list[tuple[str, str, str]]:
    """Linhas (data, área/ação, observação) do histórico, em ordem cronológica."""
    texto = _com_cache(CACHE / "historico" / f"{materia_id}.json", URL_HISTORICO.format(materia_id))
    linhas = []
    for row in reversed(json.loads(texto)["data"]):  # a fonte vem do mais novo ao mais antigo
        cel = [html.unescape(re.sub(r"<[^>]+>", "", html.unescape(c))).strip()
               if isinstance(c, str) else "" for c in row]
        linhas.append((cel[0][:19], cel[1], cel[3]))
    linhas.sort(key=lambda l: l[0])
    return linhas


def estado_por_historico(linhas: list[tuple[str, str, str]], t: str) -> tuple[str | None, tuple]:
    """(local, (área, passo) da tramitação interna) em t, segundo o histórico."""
    loc, interna = None, ("", "")
    for ti, acao, _obs in linhas:
        if ti > t:
            break
        if m := _RX_H_ENVIO.match(acao):
            loc, interna = m[2].strip(), ("", "")
        elif acao.count("/") >= 2:
            c, area, passo = acao.split("/", 2)
            if c == loc:
                interna = (area, passo)
        else:  # recebimento ("URB/Recebido" ou só "URB") ou registro inicial
            novo = acao.removesuffix("/Recebido")
            if novo != loc:
                loc, interna = novo, ("", "")
    return loc, interna


def _recebimento_no_historico(linhas: list[tuple[str, str, str]], area: str, t: str) -> bool:
    alvo = datetime.fromisoformat(t)
    return any(acao in (area, f"{area}/Recebido")
               and abs(datetime.fromisoformat(ti) - alvo) <= timedelta(days=1)
               for ti, acao, _ in linhas)


def buscar_ids(rotulos: list[str], catalogo: dict[str, str], chaves: dict[str, tuple]) -> dict[str, str]:
    arq = CACHE / "ids.json"
    ids = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    ids.update({r: catalogo[r] for r in rotulos if r in catalogo})
    for r in rotulos:
        if r not in ids and r in chaves:
            m = _RX_ID.search(_baixar(URL_DETALHE.format(*chaves[r])))
            if m:
                ids[r] = m[1] or m[2]
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(ids, ensure_ascii=False, indent=0), encoding="utf-8")
    return ids


def descartar_recebimentos_trocados(eventos: list[Evento], acervo: list[dict],
                                    catalogo: dict[str, str],
                                    chaves: dict[str, tuple]) -> tuple[list[Evento], Counter, list]:
    """O feed às vezes traz um recebimento com dia e mês trocados (o de 09/04 aparece em
    04/09), o que faz a matéria "voltar" a uma comissão de onde já saiu.

    Todo recebimento órfão (sem envio para a mesma área antes dele, na janela) que envolva
    comissão é conferido no histórico da matéria. Se o histórico não tiver recebimento
    naquela área com até um dia de diferença, o evento é descartado, junto com a
    tramitação interna automática do mesmo instante ("Designar Relator")."""
    por_rotulo: dict[str, list[Evento]] = defaultdict(list)
    for e in eventos:
        por_rotulo[e.rotulo].append(e)
    no_retrato = {r["rotulo"] for r in acervo}
    orfaos = []
    for rotulo, evs in por_rotulo.items():
        pendente = None
        for e in evs:
            if e.tipo == "envio":
                pendente = e.para
            elif e.tipo == "receb":
                if pendente != e.para and (e.para in COMISSOES or rotulo in no_retrato):
                    orfaos.append(e)
                pendente = None
            elif e.tipo == "excl_receb":
                pendente = e.para
            elif e.tipo == "excl_envio":
                pendente = None

    ids = buscar_ids(sorted({e.rotulo for e in orfaos}), catalogo, chaves)
    cont: Counter = Counter()
    descartados: set[tuple] = set()
    for e in orfaos:
        if e.rotulo not in ids:
            cont["sem id"] += 1
            continue
        linhas = historico_da_materia(ids[e.rotulo])
        if not linhas:
            cont["sem histórico"] += 1
            continue
        if _recebimento_no_historico(linhas, e.para, e.t):
            cont["confirmados"] += 1
        else:
            cont["descartados"] += 1
            descartados.add((e.rotulo, e.t, e.para))
    filtrados = [e for e in eventos
                 if (e.rotulo, e.t, e.para) not in descartados          # o recebimento
                 and (e.rotulo, e.t, e.comissao) not in descartados]    # a interna automática
    return filtrados, cont, sorted(descartados)


def descartar_exclusoes_contraditas(eventos: list[Evento]) -> tuple[list[Evento], list]:
    """Exclusão de recebimento seguida de tramitação interna na mesma comissão, sem novo
    recebimento no meio, foi correção (o recebimento foi relançado com a data antiga):
    matéria não recebida não tramita internamente. A exclusão é desconsiderada."""
    por_rotulo: dict[str, list[Evento]] = defaultdict(list)
    for e in eventos:
        por_rotulo[e.rotulo].append(e)
    contraditas = set()
    for evs in por_rotulo.values():
        for i, e in enumerate(evs):
            if e.tipo != "excl_receb" or e.para not in COMISSOES:
                continue
            for s in evs[i + 1:]:
                if s.tipo in EXTERNOS:
                    break
                if s.tipo == "interna" and s.comissao == e.para:
                    contraditas.add(id(e))
                    break
    return ([e for e in eventos if id(e) not in contraditas],
            [(e.rotulo, e.t, e.para) for e in eventos if id(e) in contraditas])


def validar_com_historicos(materias: dict[str, Materia], dias: list[date], amostra: list[str],
                           ids: dict[str, str]) -> dict:
    """C. Presença diária (e passo interno) × histórico de movimentações de cada matéria."""
    loc, interna = Counter(), Counter()
    exemplos: dict[str, list] = defaultdict(list)
    for i, rotulo in enumerate(amostra, 1):
        if rotulo not in ids:
            loc["sem id"] += 1
            continue
        if i % 50 == 0:
            log(f"  históricos: {i}/{len(amostra)}")
        linhas = historico_da_materia(ids[rotulo])
        if not linhas:  # DOCRECs antigos vêm sem histórico nesse endpoint
            loc["sem histórico"] += 1
            continue
        m = materias[rotulo]
        for d in dias:
            t = f"{d}T23:59:59"
            tr = trecho_em(t, m.trechos)
            rec = tr.loc if tr.loc in COMISSOES else None
            h_loc, h_int = estado_por_historico(linhas, t)
            h_loc = h_loc if h_loc in COMISSOES else None
            if rec == h_loc:
                loc["dias iguais"] += 1
            else:
                loc["dias diferentes"] += 1
                exemplos["local"].append((rotulo, str(d), rec, h_loc))
            if rec and rec == h_loc:
                valor, _fonte = interna_em(t, tr, m.internas, m.ancora)
                if valor is None:
                    interna["desconhecida na reconstrução"] += 1
                elif (valor[1], valor[2]) == h_int:
                    interna["iguais"] += 1
                else:
                    interna["diferentes"] += 1
                    exemplos["interna"].append((rotulo, str(d), valor[1:3], h_int))
    return {"local": loc, "interna": interna, "exemplos": exemplos}


# ----------------------------------------------------------------------------- relatório
def _pct(c: Counter, bom: str, ruim: str) -> str:
    total = c[bom] + c[ruim]
    return f"{c[bom]}/{total} ({100 * c[bom] / total:.1f}%)" if total else "—"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--inicio", type=date.fromisoformat, required=True)
    ap.add_argument("--fim", type=date.fromisoformat, required=True)
    ap.add_argument("--amostra", type=int, default=300,
                    help="matérias movimentadas a validar contra o histórico de cada uma")
    ap.add_argument("--paradas", type=int, default=100,
                    help="matérias sem movimentação externa a validar do mesmo jeito")
    ap.add_argument("--semente", type=int, default=2026)
    args = ap.parse_args(argv)

    acervo = ler_csv(C.ARQ_ACERVO)
    coletas = ler_csv(C.ARQ_COLETAS)
    t_retrato = max(c["coletado_em"] for c in coletas)[:19]
    if args.fim.isoformat() != t_retrato[:10]:
        log(f"ERRO: a janela precisa terminar no dia do retrato ({t_retrato[:10]}).")
        return 1
    catalogo = {m["rotulo"]: m["materia_id"] for m in ler_csv(C.ARQ_MATERIAS)}

    log(f"Eventos de {args.inicio} a {args.fim}...")
    eventos, chaves = carregar_eventos(args.inicio, args.fim)
    eventos = [e for e in eventos if e.t <= t_retrato]
    tipos = Counter(e.tipo for e in eventos)
    log(f"{len(eventos)} eventos: {dict(tipos)}")
    log("Conferindo recebimentos órfãos no histórico das matérias...")
    eventos, orfaos, descartados = descartar_recebimentos_trocados(eventos, acervo, catalogo, chaves)
    log(f"Recebimentos órfãos: {dict(orfaos)}")
    eventos, contraditas = descartar_exclusoes_contraditas(eventos)

    materias = reconstruir(eventos, acervo)
    dias = [args.inicio + timedelta(days=i) for i in range((args.fim - args.inicio).days + 1)]
    serie = serie_diaria(materias, dias)
    SAIDA.mkdir(parents=True, exist_ok=True)
    gravar_csv(SAIDA / "serie_reconstruida.csv", list(serie[0]), serie)

    final = validar_estado_final(materias, t_retrato)
    coerencia = validar_coerencia(materias)

    rnd = random.Random(args.semente)
    movimentadas = sorted(r for r, m in materias.items()
                          if m.movimentada and any(t.loc in COMISSOES for t in m.trechos))
    paradas = sorted(r for r, m in materias.items() if not m.movimentada and m.ancora)
    amostra = (rnd.sample(movimentadas, min(args.amostra, len(movimentadas)))
               + rnd.sample(paradas, min(args.paradas, len(paradas))))
    log(f"Validando {len(amostra)} matérias contra o histórico de cada uma...")
    ids = buscar_ids(amostra, catalogo, chaves)
    hist = validar_com_historicos(materias, dias, amostra, ids)

    anomalias = Counter(a.split(" ", 1)[1].split(" estando")[0].split(" ")[0]
                        for m in materias.values() for a in m.anomalias)
    total_inicio = sum(int(l["materias"]) for l in serie if l["data"] == str(dias[0]))
    total_fim = sum(int(l["materias"]) for l in serie if l["data"] == str(dias[-1]))
    relatorio = [
        f"# Teste de reconstrução: {args.inicio} a {args.fim}", "",
        f"- Eventos lidos: {len(eventos)} ({', '.join(f'{k} {v}' for k, v in tipos.most_common())})",
        f"- Matérias no universo: {len(materias)}; movimentadas entre comissões na janela: {len(movimentadas)}",
        f"- Acervo reconstruído: {total_inicio} matérias em {dias[0]} → {total_fim} em {dias[-1]}"
        f" (retrato real: {len(acervo)})",
        f"- Incoerências na sequência de eventos: {sum(anomalias.values())} ({dict(anomalias)})",
        f"- Recebimentos órfãos conferidos no histórico: {dict(orfaos)};"
        f" descartados por data trocada: {descartados}",
        f"- Exclusões de recebimento desconsideradas (houve tramitação interna depois): {contraditas}", "",
        "## A. Estado final previsto pelos eventos × retrato real", "",
        f"- Comissão onde a matéria está: {_pct(final['local'], 'acertos', 'erros')}",
        f"- Data de recebimento: {_pct(final['recebimento'], 'acertos', 'erros')}",
        f"- Tramitação interna (data, área, passo): {_pct(final['interna'], 'acertos', 'erros')};"
        f" comentário diferente em {final['interna']['comentario difere']}", "",
        "## B. Coerência: tramitação interna acontece onde a matéria está", "",
        f"- {_pct(coerencia['cont'], 'coerentes', 'incoerentes')}", "",
        f"## C. Dia a dia × histórico de cada matéria ({len(amostra)} matérias, {len(dias)} dias)", "",
        f"- Comissão onde a matéria está: {_pct(hist['local'], 'dias iguais', 'dias diferentes')};"
        f" sem histórico no SPLEGIS (fora da conta): {hist['local']['sem histórico']} matérias",
        f"- Passo da tramitação interna: {_pct(hist['interna'], 'iguais', 'diferentes')};"
        f" desconhecido na reconstrução em {hist['interna']['desconhecida na reconstrução']} matéria-dias", "",
        "## Exemplos de divergência", "",
    ]
    for nome, lista in [("A/local", final["exemplos"]["local"]),
                        ("A/recebimento", final["exemplos"]["recebimento"]),
                        ("A/interna", final["exemplos"]["interna"]),
                        ("B", coerencia["exemplos"]),
                        ("C/local", hist["exemplos"]["local"]),
                        ("C/interna", hist["exemplos"]["interna"])]:
        for ex in lista[:8]:
            relatorio.append(f"- {nome}: {ex}")
    texto = "\n".join(relatorio) + "\n"
    (SAIDA / "relatorio.md").write_text(texto, encoding="utf-8")
    print(texto, flush=True)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
