# -*- coding: utf-8 -*-
"""
Série diária do acervo por comissão, calculada a partir das presenças e passos internos.

Cada dia é avaliado às 23:59:59. A idade conta períodos completos de 24 horas desde o
recebimento, como faz o SPLEGIS; matérias ainda não recebidas entram em `pendentes`.
A agregação (`agregar`) é a mesma usada para os retratos reais no painel.
"""
from __future__ import annotations

import re
import unicodedata
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
# Etapas da tramitação na comissão, na ordem do processo (ver `etapa`). Matérias com passo
# desconhecido não entram em nenhuma: estão em passo_desconhecido.
ETAPAS = ["etapa_sem_relator", "etapa_estudo", "etapa_diligencia", "etapa_pauta", "etapa_votado",
          "etapa_outra"]
# Matérias recebidas pelo tempo sem movimentação interna: dias desde o último passo interno
# (ou desde o recebimento, se ainda não houve passo). As não recebidas ficam em `pendentes`.
FAIXAS_PARADO = [(30, "parado_ate30"), (90, "parado_31a90"), (180, "parado_91a180"),
                 (365, "parado_181a365"), (None, "parado_mais365")]
CAMPOS = (["data", "comissao", "grupo", "materias", "pendentes"]
          + [f for _, f in FAIXAS] + ["idade_desconhecida", "mediana_dias"] + CATEGORIAS + ETAPAS
          + [f for _, f in FAIXAS_PARADO] + ["parado_desconhecido"])

# Uma matéria num dia: (comissão, é projeto?, faixa de idade, dias ou None, categoria do
# passo interno, etapa ou None, sem relator? ou None quando não se sabe, faixa do tempo sem
# movimentação ou None para as não recebidas).
Item = tuple[str, bool, str, "int | None", str, "str | None", "bool | None", "str | None"]


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


def _texto(t: str) -> str:
    return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower()


_DILIGENCIA = re.compile(r"informac|oficio|audiencia|taquigraf|resposta do executivo|cientificado")
_VOTADO = re.compile(r"deliberado|certidao de votacao|publicar parecer|publicacao do parecer")
_PAUTA = re.compile(r"pauta|relatado|adiado|\bvistas?\b|pendente de votacao")
_ESTUDO = ("Relator", "Procuradoria", "Consultoria", "CTEO", "SGP.5")  # relator e assessoria técnica


def etapa(area: str, passo: str) -> str | None:
    """Etapa da matéria na comissão pelo passo interno vigente (as grafias variam).

    "etapa_sem_relator" estima as matérias sem relator, que nenhuma fonte registra antes
    da coleta diária: as que ainda não tiveram passo interno e as que esperam a
    designação (ou redesignação) do relator. No retrato de 02/10/2026, a estimativa dá
    1.170 matérias, e o relatório aponta 1.156 sem relator."""
    if area == DESCONHECIDO:
        return None
    if not area:
        return "etapa_sem_relator"
    texto = _texto(f"{area} {passo}")
    if "designar relator" in texto or "designacao de relator" in texto:
        return "etapa_sem_relator"
    if _DILIGENCIA.search(texto):
        return "etapa_diligencia"
    if _VOTADO.search(texto):
        return "etapa_votado"
    if _PAUTA.search(texto):
        return "etapa_pauta"
    if area.startswith(_ESTUDO):
        return "etapa_estudo"
    return "etapa_outra"


def parado(referencias: list[datetime | None], instante: datetime) -> str:
    """Faixa do tempo sem movimentação: desde a mais recente das referências (último passo
    interno, recebimento) até o instante."""
    conhecidas = [r for r in referencias if r is not None]
    if not conhecidas:
        return "parado_desconhecido"
    dias = max(0, int((instante - max(conhecidas)).total_seconds() // 86400))
    for limite, campo in FAIXAS_PARADO:
        if limite is None or dias <= limite:
            return campo
    raise AssertionError("inalcançável")


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
    for comissao, projeto, faixa, dias, passo, fase, sem_relator, sem_mexer in itens:
        for chave in ((comissao, "todas"), (TODAS, "todas"), (comissao, "projetos"),
                      (TODAS, "projetos"))[: 4 if projeto else 2]:
            c = cont[chave]
            c["materias"] += 1
            c[faixa] += 1
            c[passo] += 1
            if fase:
                c[fase] += 1
            if sem_mexer:
                c[sem_mexer] += 1
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
            vigente = p.passos[k] if k >= 0 else None
            passo = categoria(vigente.area) if vigente else "passo_desconhecido"
            fase = etapa(vigente.area, vigente.passo) if vigente else None
            sem_mexer = None
            if faixa != "pendentes":
                movimento = (datetime.fromisoformat(vigente.data) if vigente and vigente.area not in ("", DESCONHECIDO)
                             and vigente.fonte not in ("chegada", "desconhecido") else None)
                sem_mexer = parado([movimento, recebimentos[i]], instante)
            itens.append((p.comissao, projetos[i], faixa, dias, passo, fase, None, sem_mexer))
        linhas += agregar(str(d), itens, comissoes)
        d += timedelta(days=1)
    return linhas
