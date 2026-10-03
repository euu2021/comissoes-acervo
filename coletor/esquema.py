# -*- coding: utf-8 -*-
"""Colunas dos arquivos de dados/ (o dicionário de dados está no README)."""

# Estado de uma matéria numa comissão. Qualquer mudança em um destes campos abre
# um novo intervalo no histórico. Contagens de dias ficam de fora de propósito:
# mudam todo dia em toda linha, e são deriváveis das datas + hora da coleta.
CAMPOS_ESTADO = [
    "rotulo",
    "relator_codigo",
    "relator",
    "enviado_por",
    "enviado_em",
    "recebido_em",
    "interna_data",
    "interna_area",
    "interna_tipo",
    "interna_comentario",
    "ultima_interna",
]

CAMPOS_ACERVO = ["comissao", "materia_id", *CAMPOS_ESTADO]
CAMPOS_HISTORICO = ["comissao", "materia_id", "desde", "ate", *CAMPOS_ESTADO]
CAMPOS_MATERIAS = ["materia_id", "rotulo", "tipo", "numero", "ano", "ementa"]
CAMPOS_AUTORIAS = ["materia_id", "ordem", "autor_codigo", "autor", "classe"]
CAMPOS_COLETAS = ["data", "coletado_em", "comissao", "materias"]
CAMPOS_TRAMITACOES = ["data", "rotulo", "tipo", "de", "para", "motivo"]
CAMPOS_PASSOS_FEED = ["data", "rotulo", "tipo", "comissao", "area", "passo", "comentario"]


def num(valor: str) -> int:
    """Chave de ordenação numérica para ids guardados como texto."""
    return int(valor) if valor.isdigit() else -1
