# -*- coding: utf-8 -*-
"""
Autoria de cada matéria, para a composição do acervo no painel: quem é o primeiro autor
dos projetos (vereadores, Executivo, Mesa Diretora ou outros). Matérias que não são
projetos (documentos recebidos, requerimentos etc.) ficam numa categoria própria.

Os autores vêm do feed, na reconstrução (dados/reconstrucao/autorias.csv), e do relatório,
na coleta (dados/autorias.csv). O feed não diz quando o autor é o prefeito: os prefeitos
são reconhecidos pelo código de autor, que é outro quando a mesma pessoa também foi
vereadora (Ricardo Nunes é 1990 como vereador e 2229 como prefeito). O relatório marca o
Executivo ("Executivo - NOME"), o que inclui os códigos de prefeitos futuros.
"""
from __future__ import annotations

import re

from reconstrucao.serie import PROJETOS

# Códigos de autor dos prefeitos desde 2006, conferidos pelos anos dos projetos.
EXECUTIVO = {"1387": "Gilberto Kassab", "1931": "Fernando Haddad", "2163": "João Doria",
             "2169": "Bruno Covas", "2229": "Ricardo Nunes"}
AUTORIAS = ["Vereadores", "Executivo", "Mesa Diretora", "Outros ou desconhecido", "Documentos e outros tipos"]
_INSTITUICAO = re.compile(r"^(COMISS|EXTRA\.|TRIBUNAL|CORREGEDORIA|PREFEITURA|SECRETARIA|MINIST|CAIXA|"
                          r"INSTITUTO|CONSELHO|DEFENSORIA|GOVERNO|ASSOCIA|SINDICATO|FUNDA)", re.I)


def classe(nome: str, codigo: str, executivo: set[str]) -> str:
    if codigo in executivo or nome.startswith("Executivo"):
        return "Executivo"
    if nome.upper().startswith("MESA DA C"):
        return "Mesa Diretora"
    if _INSTITUICAO.match(nome):
        return "Outros ou desconhecido"
    return "Vereadores"


def autorias(reconstruidas: list[dict], coletadas: list[dict], materias: list[dict]) -> dict[str, str]:
    """{rótulo: categoria de autoria} das matérias com autor conhecido."""
    rotulos = {m["materia_id"]: m["rotulo"] for m in materias}
    executivo = set(EXECUTIVO) | {a["autor_codigo"] for a in coletadas if a["autor"].startswith("Executivo")}
    primeiro: dict[str, tuple[str, str]] = {}
    for a in sorted(reconstruidas, key=lambda a: int(a["ordem"] or 0)):
        primeiro.setdefault(a["rotulo"], (a["autor"], a["autor_codigo"]))
    do_relatorio: dict[str, tuple[str, str]] = {}
    for a in sorted(coletadas, key=lambda a: int(a["ordem"] or 0)):
        if rotulo := rotulos.get(a["materia_id"]):
            do_relatorio.setdefault(rotulo, (a["autor"], a["autor_codigo"]))
    primeiro.update(do_relatorio)  # o relatório é a fonte mais recente
    return {rotulo: classe(nome, codigo, executivo) for rotulo, (nome, codigo) in primeiro.items()}


def categoria(rotulo: str, por_rotulo: dict[str, str]) -> str:
    if rotulo.split()[0] not in PROJETOS:
        return "Documentos e outros tipos"
    return por_rotulo.get(rotulo, "Outros ou desconhecido")
