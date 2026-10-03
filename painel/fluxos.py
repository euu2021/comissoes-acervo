# -*- coding: utf-8 -*-
"""
Passagens das matérias pelas comissões, para os gráficos de fluxo do painel (entradas
e saídas, permanência e rotas).

Uma passagem vai do envio da matéria à comissão (a matéria entra no acervo mesmo antes
de ser recebida) até o envio para outra área, e guarda a origem e o destino. Até a
primeira coleta, as passagens vêm da reconstrução (dados/reconstrucao/presencas.csv);
dali em diante, dos retratos diários (dados/historico.csv). O retrato mostra quando a
matéria sumiu do acervo; a hora e o destino da saída vêm das tramitações do feed
(dados/tramitacoes.csv) e, na falta delas, da comissão onde a matéria apareceu.

O arquivo do painel (fluxos.json) traz as passagens em colunas, com as datas em dias
desde o início do feed e as áreas como índices de uma lista.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from painel import composicao
from reconstrucao.serie import PROJETOS

ORDEM = ["CCJ", "FIN", "URB", "ADM", "ECON", "EDUC", "SAUDE"]
TIPOS = ["PL", "PDL", "PR", "PLO", "DOCREC", "Outros"]
INICIO_FEED = date(2018, 10, 26)  # dia 0
DESCONHECIDO = "?"


def estadas(historico: list[dict], dias: list[str]) -> list[dict]:
    """Junta os intervalos do histórico em estadas: a mesma matéria na mesma comissão em
    coletas seguidas, levada até lá pelo mesmo envio.

    `ultimo` é o último dia de coleta em que a matéria estava lá ("" = continua no
    acervo). Se um envio novo aparece sem a matéria sumir de uma coleta para a outra,
    ela saiu e voltou entre as duas: a estada termina em `volta` e outra começa."""
    seguinte = dict(zip(dias, dias[1:]))
    grupos: dict[tuple, list[dict]] = defaultdict(list)
    for h in historico:
        grupos[(h["comissao"], h["rotulo"])].append(h)
    saida = []
    for (comissao, rotulo), lista in grupos.items():
        lista.sort(key=lambda h: h["desde"])
        atual = None
        for h in lista:
            seguida = atual is not None and atual["ultimo"] and seguinte.get(atual["ultimo"]) == h["desde"]
            if seguida and h["enviado_em"] == atual["enviado_em"]:
                atual["ultimo"] = h["ate"]
                atual["recebido_em"] = atual["recebido_em"] or h["recebido_em"]
                continue
            if seguida:
                atual["volta"] = h["enviado_em"]
            if atual is not None:
                saida.append(atual)
            atual = {"comissao": comissao, "rotulo": rotulo, "primeiro": h["desde"], "ultimo": h["ate"],
                     "enviado_por": h["enviado_por"], "enviado_em": h["enviado_em"],
                     "recebido_em": h["recebido_em"], "volta": ""}
        saida.append(atual)
    return saida


def _saida(e: dict, instantes: dict[str, str], seguinte: dict[str, str],
           tramitacoes: dict[str, list[dict]], chegadas: dict[tuple, str]) -> tuple[str, str, str]:
    """Quando, para onde e com que motivo a estada `e` (já encerrada) saiu da comissão."""
    proximo = seguinte[e["ultimo"]] if not e["volta"] else ""
    limite = e["volta"] or instantes[proximo]
    for t in reversed(tramitacoes.get(e["rotulo"], [])):
        if t["data"] > limite or t["data"][:10] < e["ultimo"]:
            continue
        if t["tipo"] == "envio" and t["de"] == e["comissao"]:
            return t["data"], t["para"], t.get("motivo", "")
        if t["tipo"] == "excl_envio" and t["para"] == e["comissao"]:
            return t["data"], t["de"], ""  # envio desfeito: a matéria volta a quem a enviou
    if e["volta"]:
        return e["volta"], DESCONHECIDO, ""
    outra = chegadas.get((e["rotulo"], proximo), DESCONHECIDO)
    return proximo, outra, ""


def passagens(reconstruidas: list[dict], historico: list[dict], coletas: list[dict],
              tramitacoes: list[dict]) -> list[dict]:
    """Passagens da reconstrução completadas com os retratos diários.

    Cada passagem: comissao, rotulo, desde, recebido e ate (data e hora ISO; None =
    desconhecido, não recebida ou, em ate, ainda no acervo), origem e destino (área; "" =
    ainda no acervo) e o motivo da saída, como o feed o registra."""
    instantes = {c["data"]: c["coletado_em"][:19] for c in coletas}
    dias = sorted(instantes)
    seguinte = dict(zip(dias, dias[1:]))
    anterior = dict(zip(dias[1:], dias))
    primeiro_dia = dias[0]
    por_materia: dict[str, list[dict]] = defaultdict(list)
    for t in sorted(tramitacoes, key=lambda t: t["data"]):
        por_materia[t["rotulo"]].append(t)

    lista = estadas(historico, dias)
    chegadas = {(e["rotulo"], e["primeiro"]): e["comissao"] for e in lista}
    abertas = {(e["comissao"], e["rotulo"]): e for e in lista if e["primeiro"] == primeiro_dia}

    def valor(v: str) -> str | None:
        return None if v in ("", DESCONHECIDO) else v

    saida = []
    usadas = set()
    for p in reconstruidas:
        nova = {"comissao": p["comissao"], "rotulo": p["rotulo"], "desde": valor(p["desde"]),
                "recebido": valor(p["recebido_em"]), "ate": valor(p["ate"]), "origem": p["enviado_por"] or "",
                "destino": p["destino"], "motivo": p.get("motivo_saida", "")}
        if not p["ate"]:  # estava no acervo na primeira coleta: o retrato diz como continua
            e = abertas.get((p["comissao"], p["rotulo"]))
            if e is None:  # a reconstrução diverge do retrato (raro): sai na primeira coleta
                nova["ate"], nova["destino"] = primeiro_dia, DESCONHECIDO
            else:
                usadas.add(id(e))
                nova["recebido"] = nova["recebido"] or valor(e["recebido_em"])
                if e["ultimo"]:
                    nova["ate"], nova["destino"], nova["motivo"] = _saida(e, instantes, seguinte, por_materia,
                                                                          chegadas)
        saida.append(nova)

    for e in lista:
        if id(e) in usadas:
            continue
        if e["primeiro"] == primeiro_dia or (e["enviado_em"] and e["enviado_em"][:10] >= anterior[e["primeiro"]]):
            desde = e["enviado_em"] or e["primeiro"]
        else:  # envio antigo: a matéria voltou porque um envio posterior foi desfeito
            desde = e["primeiro"]
        nova = {"comissao": e["comissao"], "rotulo": e["rotulo"], "desde": desde,
                "recebido": valor(e["recebido_em"]), "ate": None, "origem": e["enviado_por"],
                "destino": "", "motivo": ""}
        if e["ultimo"]:
            nova["ate"], nova["destino"], nova["motivo"] = _saida(e, instantes, seguinte, por_materia, chegadas)
        saida.append(nova)
    return saida


def fim_de_legislatura(motivo: str) -> bool:
    """Arquivamento de fim de legislatura, como o feed o registra: "Motivo: Encerrado-TERMINO
    DE LEGISLATURA (ART. 275 REG. INT.)"."""
    return "TERMINO DE LEGISLATURA" in (motivo or "").upper()


def montar(lista: list[dict], fim: str, inicio_coleta: str, atualizado_em: str,
           autorias: dict[str, str] | None = None, nomes_areas: dict[str, str] | None = None) -> dict:
    """As passagens em colunas, para o painel. `autorias` dá a categoria de autoria de cada
    rótulo (ver composicao.py)."""
    autorias = autorias or {}
    areas = sorted(({p["origem"] for p in lista} | {p["destino"] for p in lista}) - {"", DESCONHECIDO})
    indice = {a: i for i, a in enumerate(areas)}

    def dia(v: str | None) -> int | None:
        return None if v is None else (date.fromisoformat(v[:10]) - INICIO_FEED).days

    lista = sorted(lista, key=lambda p: (p["desde"] or "", p["comissao"], p["rotulo"]))
    return {
        "inicio": INICIO_FEED.isoformat(),
        "fim": fim,
        "inicio_coleta": inicio_coleta,
        "atualizado_em": atualizado_em,
        "comissoes": ORDEM,
        "areas": areas,
        "nomes_areas": {a: (nomes_areas or {}).get(a, "") for a in areas},
        "comissao": [ORDEM.index(p["comissao"]) for p in lista],
        "projeto": [int(p["rotulo"].split()[0] in PROJETOS) for p in lista],
        "desde": [dia(p["desde"]) for p in lista],
        "ate": [dia(p["ate"]) for p in lista],
        # null: origem desconhecida (ou registro feito já na comissão); destino desconhecido
        # ou, se `ate` também for null, matéria ainda no acervo.
        "origem": [indice.get(p["origem"]) for p in lista],
        "destino": [indice.get(p["destino"]) for p in lista],
        # 1: saída pelo arquivamento de fim de legislatura (art. 275 do Regimento Interno)
        "fim_legislatura": [int(fim_de_legislatura(p.get("motivo", ""))) for p in lista],
        # Composição: ano de apresentação, tipo e autoria de cada matéria.
        "ano": [int(p["rotulo"].rsplit("/", 1)[1]) for p in lista],
        "tipos": TIPOS,
        "tipo": [TIPOS.index(t) if (t := p["rotulo"].split()[0]) in TIPOS else len(TIPOS) - 1 for p in lista],
        "autorias": composicao.AUTORIAS,
        "autoria": [composicao.AUTORIAS.index(composicao.categoria(p["rotulo"], autorias)) for p in lista],
    }
