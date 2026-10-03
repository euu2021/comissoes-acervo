# -*- coding: utf-8 -*-
"""
Série diária do acervo por comissão, calculada a partir das presenças e passos internos.

Cada dia é avaliado às 23:59:59. A idade conta períodos completos de 24 horas desde o
recebimento, como faz o SPLEGIS; matérias ainda não recebidas entram em `pendentes`.
A agregação (`agregar`) é a mesma usada para os retratos reais no painel.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from statistics import median

from reconstrucao.linha_do_tempo import DESCONHECIDO, Presenca

TODAS = "TODAS"  # as 7 comissões juntas
PROJETOS = {"PL", "PDL", "PR", "PLO"}
FAIXAS = [(30, "idade_ate30"), (90, "idade_31a90"), (180, "idade_91a180"),
          (365, "idade_181a365"), (None, "idade_mais365")]
CATEGORIAS = ["passo_relator", "passo_presidente", "passo_secretaria", "passo_procuradoria",
              "passo_consultoria", "passo_outro", "passo_nenhum", "passo_desconhecido"]
CAMPOS = (["data", "comissao", "grupo", "materias", "pendentes"]
          + [f for _, f in FAIXAS] + ["idade_desconhecida", "mediana_dias"] + CATEGORIAS)

# Uma matéria num dia: (comissão, é projeto?, faixa de idade, dias ou None, categoria do
# passo interno, sem relator? ou None quando não se sabe).
Item = tuple[str, bool, str, "int | None", str, "bool | None"]


def categoria(area: str) -> str:
    """Agrupa a área da tramitação interna (as grafias variam: "Secretaria (SGP.12)")."""
    if area == DESCONHECIDO:
        return "passo_desconhecido"
    if not area:
        return "passo_nenhum"
    for prefixo, cat in (("Relator", "passo_relator"), ("Presidente da Comiss", "passo_presidente"),
                         ("Secretaria", "passo_secretaria"), ("Procuradoria", "passo_procuradoria"),
                         ("Consultoria", "passo_consultoria")):
        if area.startswith(prefixo):
            return cat
    return "passo_outro"


def idade(recebido: datetime | None, instante: datetime) -> tuple[str, int | None]:
    """(faixa, dias) de uma matéria recebida em `recebido` (None = ainda não recebida)."""
    if recebido is None or recebido > instante:
        return "pendentes", None
    dias = int((instante - recebido).total_seconds() // 86400)
    for limite, campo in FAIXAS:
        if limite is None or dias <= limite:
            return campo, dias
    raise AssertionError("inalcançável")


def agregar(data: str, itens: Iterable[Item], comissoes: list[str],
            com_relator: bool = False) -> list[dict]:
    """Uma linha por comissão (mais TODAS) × grupo ("todas" e "projetos")."""
    cont: dict[tuple, dict] = defaultdict(lambda: defaultdict(int))
    idades: dict[tuple, list] = defaultdict(list)
    for comissao, projeto, faixa, dias, passo, sem_relator in itens:
        for chave in ((comissao, "todas"), (TODAS, "todas"), (comissao, "projetos"),
                      (TODAS, "projetos"))[: 4 if projeto else 2]:
            c = cont[chave]
            c["materias"] += 1
            c[faixa] += 1
            c[passo] += 1
            c["sem_relator"] += bool(sem_relator)
            if dias is not None:
                idades[chave].append(dias)

    linhas = []
    for comissao in [*comissoes, TODAS]:
        for grupo in ("todas", "projetos"):
            c = cont[(comissao, grupo)]
            linha = {"data": data, "comissao": comissao, "grupo": grupo,
                     **{campo: str(c.get(campo, 0)) for campo in CAMPOS[3:]}}
            amostra = idades[(comissao, grupo)]
            linha["mediana_dias"] = str(int(median(amostra))) if amostra else ""
            if com_relator:
                linha["sem_relator"] = str(c.get("sem_relator", 0))
            linhas.append(linha)
    return linhas


def calcular(presencas: list[Presenca], inicio: date, fim: date) -> list[dict]:
    """Série da reconstrução: uma linha por dia × comissão (mais TODAS) × grupo."""
    ordem = sorted(presencas, key=lambda p: p.desde if p.desde not in (None, DESCONHECIDO) else "")
    datas_passos = [[x.data for x in p.passos] for p in ordem]
    recebimentos = [datetime.fromisoformat(p.recebido_em)
                    if p.recebido_em not in ("", DESCONHECIDO) else None for p in ordem]
    projetos = [p.rotulo.split()[0] in PROJETOS for p in ordem]
    comissoes = sorted({p.comissao for p in presencas})
    linhas = []
    proxima, ativas = 0, []
    d = inicio
    while d <= fim:
        fim_dia = f"{d}T23:59:59"
        instante = datetime.fromisoformat(fim_dia)
        while proxima < len(ordem) and (ordem[proxima].desde in (None, DESCONHECIDO)
                                        or ordem[proxima].desde <= fim_dia):
            ativas.append(proxima)
            proxima += 1
        ativas = [i for i in ativas if ordem[i].ate is None or ordem[i].ate > fim_dia]

        itens = []
        for i in ativas:
            p = ordem[i]
            if p.recebido_em == DESCONHECIDO:
                faixa, dias = "idade_desconhecida", None
            else:
                faixa, dias = idade(recebimentos[i], instante)
            k = bisect_right(datas_passos[i], fim_dia) - 1
            passo = categoria(p.passos[k].area) if k >= 0 else "passo_desconhecido"
            itens.append((p.comissao, projetos[i], faixa, dias, passo, None))
        linhas += agregar(str(d), itens, comissoes)
        d += timedelta(days=1)
    return linhas
