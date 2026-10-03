# -*- coding: utf-8 -*-
"""
Série diária do acervo por comissão, calculada a partir das presenças e passos internos.

Cada dia é avaliado às 23:59:59. A idade conta períodos completos de 24 horas desde o
recebimento, como faz o SPLEGIS; matérias ainda não recebidas entram em `pendentes`.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import median

from reconstrucao.linha_do_tempo import DESCONHECIDO, Presenca

PROJETOS = {"PL", "PDL", "PR", "PLO"}
FAIXAS = [(30, "idade_ate30"), (90, "idade_31a90"), (180, "idade_91a180"),
          (365, "idade_181a365"), (None, "idade_mais365")]
CATEGORIAS = ["passo_relator", "passo_presidente", "passo_secretaria", "passo_procuradoria",
              "passo_consultoria", "passo_outro", "passo_nenhum", "passo_desconhecido"]
CAMPOS = (["data", "comissao", "grupo", "materias", "pendentes"]
          + [f for _, f in FAIXAS] + ["idade_desconhecida", "mediana_dias"] + CATEGORIAS)


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


def _faixa(dias: int) -> str:
    for limite, campo in FAIXAS:
        if limite is None or dias <= limite:
            return campo
    raise AssertionError("inalcançável")


def calcular(presencas: list[Presenca], inicio: date, fim: date) -> list[dict]:
    """Uma linha por dia × comissão × grupo ("todas" e "projetos")."""
    ordem = sorted(presencas, key=lambda p: p.desde if p.desde not in (None, DESCONHECIDO) else "")
    datas_passos = [[x.data for x in p.passos] for p in ordem]
    recebimentos = [datetime.fromisoformat(p.recebido_em)
                    if p.recebido_em not in ("", DESCONHECIDO) else None for p in ordem]
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

        cont: dict[tuple, dict] = defaultdict(lambda: defaultdict(int))
        idades: dict[tuple, list] = defaultdict(list)
        for i in ativas:
            p = ordem[i]
            grupos = ["todas", "projetos"] if p.rotulo.split()[0] in PROJETOS else ["todas"]
            r = recebimentos[i]
            if p.recebido_em == DESCONHECIDO:
                faixa = "idade_desconhecida"
            elif r is None or r > instante:
                faixa = "pendentes"
            else:
                dias = int((instante - r).total_seconds() // 86400)
                faixa = _faixa(dias)
            k = bisect_right(datas_passos[i], fim_dia) - 1
            cat = categoria(p.passos[k].area) if k >= 0 else "passo_desconhecido"
            for g in grupos:
                c = cont[(p.comissao, g)]
                c["materias"] += 1
                c[faixa] += 1
                c[cat] += 1
                if faixa.startswith("idade_") and faixa != "idade_desconhecida":
                    idades[(p.comissao, g)].append(dias)

        for comissao in comissoes:
            for grupo in ("todas", "projetos"):
                c = cont[(comissao, grupo)]
                linha = {campo: str(c.get(campo, 0)) for campo in CAMPOS[3:]}
                amostra = idades[(comissao, grupo)]
                linha["mediana_dias"] = str(int(median(amostra))) if amostra else ""
                linhas.append({"data": str(d), "comissao": comissao, "grupo": grupo, **linha})
        d += timedelta(days=1)
    return linhas
