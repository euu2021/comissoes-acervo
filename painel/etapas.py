# -*- coding: utf-8 -*-
"""
Votações por mês e tempo de cada etapa, a partir dos passos internos de cada passagem
das matérias pelas comissões.

Os passos vêm da reconstrução até a primeira coleta (dados/reconstrucao/passos_internos.csv)
e, dali em diante, do feed capturado a cada coleta (dados/passos_internos.csv). As
passagens são as de fluxos.py.

- Votação: o primeiro passo de etapa "votada" na passagem (deliberado, certidão de votação,
  parecer a publicar). Matérias aprovadas em reunião conjunta de comissões não ganham esse
  passo; contam pela saída cujo motivo cita a reunião conjunta.
- Calendário: passos internos lançados e votações em cada dia.
- Etapas: da chegada (recebimento) ao primeiro passo de trabalho com relator (estudo,
  diligência, pauta ou votação); daí ao primeiro passo de pauta (ou votação); e da pauta à
  votação. Cada tempo entra no ano em que a etapa terminou; etapas que não terminaram (a
  matéria saiu antes, ou ainda está nela) ficam de fora.
"""
from __future__ import annotations

import unicodedata
from bisect import bisect_left
from collections import defaultdict
from datetime import date, datetime
from statistics import quantiles

from reconstrucao.serie import PROJETOS, TODAS, etapa

FONTES = {"feed", "historico", "retrato"}  # passos registrados (os demais são marcações da reconstrução)
TRABALHO = {"etapa_estudo", "etapa_diligencia", "etapa_pauta", "etapa_votado"}
ESTAGIOS = ["relator", "estudo", "pauta"]
PRIMEIRO_ANO = 2020  # antes, as etapas longas que começaram antes do feed (out/2018) ficariam de fora


def _texto(t: str) -> str:
    return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower()


def conjunta(motivo: str) -> bool:
    """Saída de matéria aprovada em reunião conjunta de comissões ("Aprovado em Reunião
    Conjunta", "Passou em reunião conjunta"...), mas não a que vai para uma ("Para reunião
    conjunta"), que ainda será votada."""
    texto = _texto(motivo or "")
    return "conjunt" in texto and "para reuniao conjunta" not in texto


def passos_por_materia(reconstruidos: list[dict], capturados: list[dict], ancora: str) -> dict:
    """{(comissao, rotulo): [(data, etapa)]} em ordem, com os passos da reconstrução até o
    instante da primeira coleta e os do feed capturado depois dele."""
    por: dict[tuple, list] = defaultdict(list)
    for r in reconstruidos:
        if r["fonte"] in FONTES and r["data"] <= ancora:
            por[(r["comissao"], r["rotulo"])].append((r["data"], r["area"], r["passo"]))
    for r in sorted(capturados, key=lambda r: r["data"]):
        if r["data"] <= ancora:
            continue
        lista = por[(r["comissao"], r["rotulo"])]
        if r["tipo"] == "interna":
            lista.append((r["data"], r["area"], r["passo"]))
        else:  # passo excluído: sai o mais recente igual a ele
            k = next((i for i in range(len(lista) - 1, -1, -1) if lista[i][1:] == (r["area"], r["passo"])), None)
            if k is not None:
                del lista[k]
    return {k: [(d, etapa(a, p)) for d, a, p in sorted(v)] for k, v in por.items()}


def _dias(a: str, b: str) -> float:
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 86400


INICIO = date(2018, 11, 1)  # primeiro mês da série


def _esparso(por_dia: dict[int, int]) -> list[int]:
    """{dia: n} -> [Δdia, n, Δdia, n, ...], com os dias contados desde INICIO."""
    saida, anterior = [], 0
    for dia in sorted(por_dia):
        saida += [dia - anterior, por_dia[dia]]
        anterior = dia
    return saida


def calcular(passagens: list[dict], passos: dict, fim: str) -> dict:
    """Votações por mês e tempos das etapas por ano, por grupo × comissão (e TODAS)."""
    meses = []
    m = date(2018, 11, 1)
    while m.isoformat()[:7] <= fim[:7]:
        meses.append(m.isoformat()[:7])
        m = date(m.year + m.month // 12, m.month % 12 + 1, 1)
    anos = list(range(PRIMEIRO_ANO, int(fim[:4]) + 1))
    pos_mes = {mes: i for i, mes in enumerate(meses)}
    contagem = defaultdict(lambda: {"votadas": [0] * len(meses), "conjunta": [0] * len(meses)})
    duracoes = defaultdict(list)  # (grupo, comissao, estagio, ano) -> dias
    calendario = defaultdict(lambda: {"passos": defaultdict(int), "votos": defaultdict(int)})

    def dia(t: str) -> int:
        return (date.fromisoformat(t[:10]) - INICIO).days

    for p in passagens:
        grupos = ("todas", "projetos") if p["rotulo"].split()[0] in PROJETOS else ("todas",)
        chaves = [(g, c) for g in grupos for c in (p["comissao"], TODAS)]
        lista = passos.get((p["comissao"], p["rotulo"]), [])
        inicio = bisect_left(lista, (p["desde"],)) if p["desde"] else 0
        fim_p = bisect_left(lista, (p["ate"],)) if p["ate"] else len(lista)
        dentro = [x for x in lista[inicio:fim_p] if x[1]]

        for d, _ in dentro:
            if d >= "2018-11-01":
                for k in chaves:
                    calendario[k]["passos"][dia(d)] += 1
        voto = next((d for d, e in dentro if e == "etapa_votado"), None)
        if voto and voto[:7] in pos_mes:
            for k in chaves:
                contagem[k]["votadas"][pos_mes[voto[:7]]] += 1
                calendario[k]["votos"][dia(voto)] += 1
        elif not voto and p["ate"] and conjunta(p.get("motivo", "")) and p["ate"][:7] in pos_mes:
            for k in chaves:
                contagem[k]["conjunta"][pos_mes[p["ate"][:7]]] += 1
                calendario[k]["votos"][dia(p["ate"])] += 1

        if not p["desde"] or p["desde"] < "2018-11-01":
            continue
        t0 = p["recebido"] if p.get("recebido") and p["recebido"] >= p["desde"] else p["desde"]
        t1 = next(((d, e) for d, e in dentro if d >= t0 and e in TRABALHO), None)
        if not t1:
            continue
        marcos = [("relator", t0, t1[0])]
        t2 = next(((d, e) for d, e in dentro if d >= t1[0] and e in ("etapa_pauta", "etapa_votado")), None)
        if t2:
            marcos.append(("estudo", t1[0], t2[0]))
            if t2[1] == "etapa_pauta":
                t3 = next((d for d, e in dentro if d >= t2[0] and e == "etapa_votado"), None)
                if t3:
                    marcos.append(("pauta", t2[0], t3))
        for estagio, a, b in marcos:
            ano = int(b[:4])
            if ano >= PRIMEIRO_ANO:
                for g, c in chaves:
                    duracoes[(g, c, estagio, ano)].append(_dias(a, b))

    producao, tempos, dias = {}, {}, {}
    comissoes = sorted({p["comissao"] for p in passagens}) + [TODAS]
    for g in ("projetos", "todas"):
        producao[g] = {c: contagem[(g, c)] for c in comissoes}
        dias[g] = {c: {m: _esparso(calendario[(g, c)][m]) for m in ("passos", "votos")} for c in comissoes}
        tempos[g] = {}
        for c in comissoes:
            tempos[g][c] = {}
            for estagio in ESTAGIOS:
                serie = {"mediana": [], "p25": [], "p75": [], "n": []}
                for ano in anos:
                    v = duracoes.get((g, c, estagio, ano), [])
                    q = quantiles(v, n=4, method="inclusive") if len(v) >= 2 else [None, None, None]
                    if len(v) == 1:
                        q = [v[0]] * 3
                    serie["p25"].append(None if q[0] is None else round(q[0]))
                    serie["mediana"].append(None if q[1] is None else round(q[1]))
                    serie["p75"].append(None if q[2] is None else round(q[2]))
                    serie["n"].append(len(v))
                tempos[g][c][estagio] = serie
    return {"meses": meses, "anos": anos, "producao": producao, "tempos": tempos,
            "calendario": {"inicio": INICIO.isoformat(), **dias}}
