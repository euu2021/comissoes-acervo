# -*- coding: utf-8 -*-
"""
Histórico do acervo em intervalos de validade.

Cada linha de historico.csv é um estado de uma matéria numa comissão, válido de
`desde` até `ate` (datas de coleta, inclusive). `ate` vazio = estado ainda vigente
na última coleta. Logo, o acervo de uma comissão em qualquer data coletada d é:

    desde <= d  e  (ate vazio  ou  d <= ate)

A cada coleta só mudam as linhas cujo estado mudou: a linha antiga ganha `ate`
(a data da coleta anterior, último dia em que foi vista) e uma linha nova é aberta.
Linhas sem mudança não são tocadas, o que mantém pequenos os diffs diários no git.
"""
from __future__ import annotations

from collections import defaultdict

from coletor.esquema import CAMPOS_ESTADO, num


def _chave(linha: dict) -> tuple[str, str]:
    return linha["comissao"], linha["materia_id"]


def _estado(linha: dict) -> tuple:
    return tuple(linha[c] for c in CAMPOS_ESTADO)


def _ordem(linha: dict) -> tuple:
    return num(linha["materia_id"]), linha["desde"], linha["comissao"]


def desfazer(historico: list[dict], data: str, anterior: str | None) -> list[dict]:
    """Desfaz o efeito da coleta de `data`, para que o mesmo dia possa ser recoletado.

    A coleta de `data` abriu as linhas com desde == data e fechou as que ganharam
    ate == anterior (nenhuma outra coleta produz esse valor de `ate`)."""
    resultado = []
    for h in historico:
        if h["desde"] == data:
            continue
        if anterior is not None and h["ate"] == anterior:
            h = {**h, "ate": ""}
        resultado.append(h)
    return resultado


def atualizar(historico: list[dict], data: str, retrato: list[dict],
              anterior: str | None) -> tuple[list[dict], dict]:
    """Aplica o retrato da coleta de `data` ao histórico.

    `anterior` é a data da coleta imediatamente anterior (None se for a primeira).
    Devolve o histórico novo e, por comissão, quantas matérias entraram, saíram ou
    mudaram de estado."""
    abertos: dict[tuple, dict] = {}
    for h in historico:
        if not h["ate"]:
            if _chave(h) in abertos:
                raise ValueError(f"dois intervalos abertos para {_chave(h)}")
            abertos[_chave(h)] = h
    if abertos and anterior is None:
        raise ValueError("há intervalos abertos mas nenhuma coleta anterior")
    if anterior is not None and anterior >= data:
        raise ValueError(f"coleta anterior ({anterior}) não precede {data}")

    atual = {_chave(r): r for r in retrato}
    if len(atual) != len(retrato):
        raise ValueError("retrato com comissão × matéria repetida")

    resumo: dict[str, dict] = defaultdict(lambda: {"entradas": 0, "saidas": 0, "mudancas": 0})
    resultado = []
    for h in historico:
        if not h["ate"]:
            r = atual.get(_chave(h))
            if r is None:
                resumo[h["comissao"]]["saidas"] += 1
                h = {**h, "ate": anterior}
            elif _estado(r) != _estado(h):
                resumo[h["comissao"]]["mudancas"] += 1
                h = {**h, "ate": anterior}
        resultado.append(h)

    for k, r in atual.items():
        h = abertos.get(k)
        if h is None:
            resumo[r["comissao"]]["entradas"] += 1
        if h is None or _estado(h) != _estado(r):
            resultado.append({"comissao": r["comissao"], "materia_id": r["materia_id"],
                              "desde": data, "ate": "",
                              **{c: r[c] for c in CAMPOS_ESTADO}})

    resultado.sort(key=_ordem)
    return resultado, dict(resumo)
