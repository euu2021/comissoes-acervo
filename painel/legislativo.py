# -*- coding: utf-8 -*-
"""
Pareceres, relatores e desfecho dos projetos para o painel (site/dados/legislativo.json), a
partir do que coletor/legislativo.py guarda do webservice do SPLEGIS:

- pareceres: quantos pareceres cada comissão deu por mês, pela conclusão (favorável, pela
  legalidade, pela ilegalidade, contrário, outros);
- relatores: quantos pareceres cada relator deu em cada comissão, por mês. O partido é o que
  o SPLEGIS registra hoje para o vereador, não necessariamente o da época;
- desfechos: como terminaram os projetos apresentados em cada ano (lei, veto, rejeição,
  retirada, apensamento, arquivamento no fim da legislatura) e quantos seguem em tramitação.
"""
from __future__ import annotations

import unicodedata
from collections import defaultdict
from datetime import date

from reconstrucao.serie import TODAS

CONCLUSOES = ["favoravel", "legalidade", "ilegalidade", "contrario", "outros"]
DESFECHOS = ["lei", "vetado", "rejeitado", "retirado", "apensado", "legislatura", "outros"]
PRIMEIRO_ANO = 2013


def _texto(t: str) -> str:
    return unicodedata.normalize("NFD", t or "").encode("ascii", "ignore").decode().upper()


def conclusao(texto: str) -> str:
    t = _texto(texto)
    if t.startswith("CONTRAR"):
        return "contrario"
    if "ILEGAL" in t or t.startswith("INCONSTITUC"):
        return "ilegalidade"
    if t.startswith(("FAVOR", "LEG. E FAV", "LEGALIDADE E FAVOR")):
        return "favoravel"
    if t.startswith(("LEGALIDADE", "CONSTITUCIONALIDADE")):
        return "legalidade"
    return "outros"


def desfecho(motivo: str) -> str:
    t = _texto(motivo)
    if "PROMULGADO" in t or "VETO PARCIAL" in t:
        return "lei"
    if "VETO TOTAL" in t:
        return "vetado"
    if "ILEGALIDADE" in t or "REJEITADO" in t or "CONTRARIO" in t:
        return "rejeitado"
    if "RETIRADO" in t:
        return "retirado"
    if "APENSADO" in t:
        return "apensado"
    if "TERMINO DE LEGISLATURA" in t:
        return "legislatura"
    return "outros"


def montar(relatorias: list[dict], encerrados: list[dict], contagem: list[dict], fim: str) -> dict:
    meses = []
    m = date(2018, 11, 1)
    while m.isoformat()[:7] <= fim[:7]:
        meses.append(m.isoformat()[:7])
        m = date(m.year + m.month // 12, m.month % 12 + 1, 1)
    pos = {mes: i for i, mes in enumerate(meses)}

    comissoes = sorted({r["comissao"] for r in relatorias})
    pareceres = {c: {k: [0] * len(meses) for k in CONCLUSOES} for c in [*comissoes, TODAS]}
    relatores: dict[tuple, int] = {}
    por_relator: dict[str, dict[tuple, int]] = defaultdict(lambda: defaultdict(int))
    for r in relatorias:
        if not r["parecer_em"] or r["parecer_em"][:7] not in pos:
            continue
        i = pos[r["parecer_em"][:7]]
        k = conclusao(r["conclusao"])
        for c in (r["comissao"], TODAS):
            pareceres[c][k][i] += 1
        if r["relator"]:
            idx = relatores.setdefault((r["relator"], r["partido"]), len(relatores))
            por_relator[r["comissao"]][(i, idx)] += 1

    anos = list(range(PRIMEIRO_ANO, int(fim[:4]) + 1))
    apresentados = defaultdict(int)
    for c in contagem:
        apresentados[int(c["ano"])] += int(c["projetos"])
    desfechos = {k: [0] * len(anos) for k in DESFECHOS}
    for e in encerrados:
        ano = int(e["ano"])
        if ano in anos:
            desfechos[desfecho(e["motivo"])][anos.index(ano)] += 1
    encerrados_ano = [sum(desfechos[k][i] for k in DESFECHOS) for i in range(len(anos))]
    return {
        "meses": meses,
        "pareceres": pareceres,
        "relatores": [list(r) for r in relatores],
        # por comissão: [mês, relator, pareceres, mês, relator, pareceres, ...]
        "pareceres_por_relator": {c: [v for (i, idx), n in sorted(d.items()) for v in (i, idx, n)]
                                  for c, d in por_relator.items()},
        "anos": anos,
        "apresentados": [apresentados.get(a) for a in anos],
        "desfechos": desfechos,
        "em_tramitacao": [None if apresentados.get(a) is None else max(0, apresentados[a] - encerrados_ano[i])
                          for i, a in enumerate(anos)],
    }
