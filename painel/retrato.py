# -*- coding: utf-8 -*-
"""
Retrato do dia para o painel (site/dados/retrato.json): cada matéria em análise, com
relator, autoria, idade na comissão e passo interno. Alimenta as visões por relator, por
passo e por autoria e a lista de matérias.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime

from reconstrucao import serie as S

_MINUSCULAS = {"a", "as", "com", "da", "das", "de", "do", "dos", "e", "em", "na", "nas", "no", "nos",
               "o", "os", "para", "pela", "pelo", "por"}
_RX_VEREADOR = re.compile(r"^Ver\. (.+) \(([^)]+)\)$")
_RX_DATA_BR = re.compile(r"^(\d{2})/(\d{2})/(\d{4})")


def nome_proprio(texto: str) -> str:
    """'SILVIA DA BANCADA FEMINISTA' -> 'Silvia da Bancada Feminista'."""
    palavras = []
    for i, palavra in enumerate(texto.lower().split()):
        if i and palavra in _MINUSCULAS:
            palavras.append(palavra)
        else:
            palavras.append("-".join(p[:1].upper() + p[1:] for p in palavra.split("-")))
    return " ".join(palavras)


def pessoa(texto: str) -> tuple[str, str]:
    """(nome, grupo) de um autor ou relator. O grupo é o partido, para vereadores;
    os prefeitos se juntam em "Executivo" e as composições da Mesa em "Mesa Diretora"."""
    if m := _RX_VEREADOR.match(texto):
        return nome_proprio(m[1]), m[2]
    if texto.startswith("Executivo"):
        return "Executivo", "Executivo"
    if texto.upper().startswith("MESA DA C"):
        return "Mesa Diretora", "Mesa Diretora"
    return nome_proprio(texto), "Outros"


def _dias(inicio: str, instante: datetime) -> int | None:
    if not inicio:
        return None
    return S.idade(datetime.fromisoformat(inicio), instante)[1]


def montar(acervo: list[dict], materias: list[dict], autorias: list[dict], coleta: dict) -> dict:
    instante = datetime.fromisoformat(coleta["coletado_em"]).replace(tzinfo=None)
    ementas = {m["materia_id"]: m["ementa"] for m in materias}
    autores_por_materia: dict[str, list[str]] = defaultdict(list)
    for a in sorted(autorias, key=lambda a: (a["materia_id"], int(a["ordem"] or 0))):
        autores_por_materia[a["materia_id"]].append(a["autor"])

    pessoas: list[tuple[str, str]] = []
    indice: dict[tuple[str, str], int] = {}

    def ref(texto: str) -> int:
        chave = pessoa(texto)
        if chave not in indice:
            indice[chave] = len(pessoas)
            pessoas.append(chave)
        return indice[chave]

    saida = []
    for r in sorted(acervo, key=lambda r: (r["comissao"], int(r["materia_id"]))):
        # Sem tramitação interna em aberto, o SPLEGIS só mostra o resumo da última,
        # com a data no começo ("02/09/2026 03:08 - ..."): basta para contar os dias.
        data_passo = r["interna_data"]
        if not data_passo and (m := _RX_DATA_BR.match(r["ultima_interna"])):
            data_passo = f"{m[3]}-{m[2]}-{m[1]}T00:00:00"
        autores = list(dict.fromkeys(ref(a) for a in autores_por_materia[r["materia_id"]]))
        saida.append({
            "c": r["comissao"],
            "id": r["materia_id"],
            "r": r["rotulo"],
            "p": int(r["rotulo"].split()[0] in S.PROJETOS),
            "e": ementas.get(r["materia_id"], ""),
            "rel": ref(r["relator"]) if r["relator"] else None,
            "rec": r["recebido_em"][:10],
            "dc": _dias(r["recebido_em"], instante),
            "pt": r["interna_tipo"],
            "pa": r["interna_area"],
            "dp": _dias(data_passo, instante),
            "a": autores,
        })
    return {"data": coleta["data"], "coletado_em": coleta["coletado_em"],
            "pessoas": [list(p) for p in pessoas], "materias": saida}
