# -*- coding: utf-8 -*-
"""
Tramitações externas das matérias que entram nas comissões ou saem delas, tiradas do
feed diário de eventos do SPLEGIS (o mesmo da reconstrução).

O retrato diário mostra que uma matéria saiu do acervo de uma comissão, mas não para
onde foi. Este registro guarda os envios (e os envios desfeitos) de cada dia, para o
painel saber o destino de cada saída: outra comissão, a Secretaria Geral Parlamentar,
o arquivo etc.

  tramitacoes.csv  data, rotulo, tipo (envio | excl_envio), de, para

Só acrescenta: cada execução baixa o feed do dia de referência e do anterior (o dia
corrente ainda vai ganhar eventos) e junta ao que já estava, sem repetir linhas.

Uso:
  python -m coletor.tramitacoes                                 dia de referência e o anterior
  python -m coletor.tramitacoes --desde 2026-10-01 [--ate ...]  período, para preencher lacunas
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta

from coletor import config as C
from coletor.coletar import dia_de_referencia
from coletor.esquema import CAMPOS_TRAMITACOES
from coletor.util import gravar_csv, ler_csv, log
from reconstrucao import fontes
from reconstrucao.eventos import COMISSOES, TIPOS_DO_RELATORIO, interpretar


def extrair(itens: list[dict]) -> list[dict]:
    """Envios e envios desfeitos que tocam alguma comissão, das matérias do relatório."""
    linhas = []
    for item in itens:
        if item["Sigla"] not in TIPOS_DO_RELATORIO:
            continue
        rotulo = f"{item['Sigla']} {item['Numero']}/{item['Ano']}"
        for e in item.get("Eventos") or []:
            ev = interpretar(e["Descricao"])
            if ev["tipo"] in ("envio", "excl_envio") and (ev["de"] in COMISSOES or ev["para"] in COMISSOES):
                linhas.append({"data": e["Data"][:19], "rotulo": rotulo, "tipo": ev["tipo"],
                               "de": ev["de"], "para": ev["para"]})
    return linhas


def juntar(existentes: list[dict], novas: list[dict]) -> list[dict]:
    chave = lambda l: tuple(l[c] for c in CAMPOS_TRAMITACOES)  # noqa: E731
    unicas = {chave(l): l for l in existentes}
    unicas.update((chave(l), l) for l in novas)
    return [unicas[k] for k in sorted(unicas)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Tramitações das comissões no feed do SPLEGIS.")
    ap.add_argument("--desde", type=date.fromisoformat, help="primeiro dia (AAAA-MM-DD)")
    ap.add_argument("--ate", type=date.fromisoformat, help="último dia (AAAA-MM-DD)")
    args = ap.parse_args(argv)

    referencia = date.fromisoformat(dia_de_referencia(datetime.now(C.FUSO)))
    fim = args.ate or referencia
    inicio = args.desde or fim - timedelta(days=1)
    novas = []
    d = inicio
    while d <= fim:
        dia = extrair(fontes.eventos_do_dia(d))
        log(f"{d}: {len(dia)} tramitações de comissões")
        novas += dia
        d += timedelta(days=1)

    existentes = ler_csv(C.ARQ_TRAMITACOES)
    linhas = juntar(existentes, novas)
    gravar_csv(C.ARQ_TRAMITACOES, CAMPOS_TRAMITACOES, linhas)
    log(f"{C.ARQ_TRAMITACOES.name}: {len(linhas) - len(existentes)} linhas novas, {len(linhas)} no total")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
