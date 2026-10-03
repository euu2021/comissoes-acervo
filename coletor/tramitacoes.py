# -*- coding: utf-8 -*-
"""
Tramitações das matérias nas comissões, tiradas do feed diário de eventos do SPLEGIS (o
mesmo da reconstrução).

O retrato diário mostra que uma matéria saiu do acervo de uma comissão, mas não para onde
foi nem por quê, e só guarda o último passo interno de cada coleta. Estes registros
guardam o que acontece entre uma coleta e outra:

  tramitacoes.csv      envios de e para as comissões (e envios desfeitos), com o motivo:
                       data, rotulo, tipo (envio | excl_envio), de, para, motivo
  passos_internos.csv  passos da tramitação interna nas comissões (e passos excluídos):
                       data, rotulo, tipo (interna | excl_interna), comissao, area, passo,
                       comentario

Só acrescentam: cada execução baixa o feed do dia de referência e do anterior (o dia
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
from coletor.esquema import CAMPOS_PASSOS_FEED, CAMPOS_TRAMITACOES
from coletor.util import gravar_csv, ler_csv, log
from reconstrucao import fontes
from reconstrucao.eventos import COMISSOES, TIPOS_DO_RELATORIO, interpretar


def extrair(itens: list[dict]) -> tuple[list[dict], list[dict]]:
    """(envios que tocam alguma comissão, passos internos nas comissões) das matérias do
    relatório."""
    envios, passos = [], []
    for item in itens:
        if item["Sigla"] not in TIPOS_DO_RELATORIO:
            continue
        rotulo = f"{item['Sigla']} {item['Numero']}/{item['Ano']}"
        for e in item.get("Eventos") or []:
            ev = interpretar(e["Descricao"])
            data = e["Data"][:19]
            if ev["tipo"] in ("envio", "excl_envio") and (ev["de"] in COMISSOES or ev["para"] in COMISSOES):
                envios.append({"data": data, "rotulo": rotulo, "tipo": ev["tipo"], "de": ev["de"],
                               "para": ev["para"], "motivo": ev.get("motivo", "")})
            elif ev["tipo"] in ("interna", "excl_interna") and ev["comissao"] in COMISSOES:
                passos.append({"data": data, "rotulo": rotulo, "tipo": ev["tipo"], "comissao": ev["comissao"],
                               "area": ev["area"], "passo": ev["passo"], "comentario": ev["comentario"]})
    return envios, passos


def juntar(existentes: list[dict], novas: list[dict], campos: list[str]) -> list[dict]:
    chave = lambda l: tuple(l[c] for c in campos)  # noqa: E731
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
    envios, passos = [], []
    d = inicio
    while d <= fim:
        e, p = extrair(fontes.eventos_do_dia(d))
        log(f"{d}: {len(e)} envios e {len(p)} passos internos nas comissões")
        envios += e
        passos += p
        d += timedelta(days=1)

    for arquivo, campos, novas in ((C.ARQ_TRAMITACOES, CAMPOS_TRAMITACOES, envios),
                                   (C.ARQ_PASSOS_FEED, CAMPOS_PASSOS_FEED, passos)):
        existentes = ler_csv(arquivo)
        linhas = juntar(existentes, novas, campos)
        gravar_csv(arquivo, campos, linhas)
        log(f"{arquivo.name}: {len(linhas) - len(existentes)} linhas novas, {len(linhas)} no total")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
