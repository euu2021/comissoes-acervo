# -*- coding: utf-8 -*-
"""
Coleta diária do acervo das Comissões Permanentes da CMSP.

Baixa do SPLEGIS as matérias em análise em cada uma das 7 Comissões e atualiza dados/:
  acervo.csv     retrato do dia, uma linha por comissão × matéria;
  historico.csv  os mesmos estados em intervalos de validade (ver historico.py);
  materias.csv   catálogo cumulativo (rótulo, ementa) de toda matéria já vista;
  autorias.csv   autores de cada matéria;
  coletas.csv    data, hora e tamanho do acervo de cada comissão em cada coleta.

Idempotente: coletar de novo no mesmo dia substitui a coleta daquele dia.
Se qualquer comissão falhar, nada é gravado.

Uso:
  python -m coletor.coletar              coleta e grava
  python -m coletor.coletar --se-faltar  só coleta se o dia ainda não tiver coleta
  python -m coletor.coletar --forcar     ignora a trava contra queda brusca do acervo
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime

from coletor import config as C
from coletor import historico as H
from coletor import splegis
from coletor.esquema import (CAMPOS_ACERVO, CAMPOS_AUTORIAS, CAMPOS_COLETAS,
                             CAMPOS_HISTORICO, CAMPOS_MATERIAS, num)
from coletor.util import gravar_csv, ler_csv, log


def _queda_brusca(contagem: dict[str, int], coletas: list[dict]) -> str | None:
    """Compara com a coleta mais recente; devolve a mensagem de erro, se houver."""
    if not coletas:
        return None
    ultima = max(c["data"] for c in coletas)
    antes = {c["comissao"]: int(c["materias"]) for c in coletas if c["data"] == ultima}
    for sigla, n in contagem.items():
        n0 = antes.get(sigla, 0)
        if n0 >= C.QUEDA_PISO and n < n0 * (1 - C.QUEDA_MAXIMA):
            return (f"o acervo da {sigla} caiu de {n0} ({ultima}) para {n}. Nada foi "
                    f"gravado; se a queda for real, rode de novo com --forcar.")
    return None


def _resumo_markdown(data: str, contagem: dict[str, int], resumo: dict) -> str:
    linhas = [f"### Coleta de {data}", "",
              "| Comissão | Matérias | Entradas | Saídas | Mudanças de estado |",
              "|---|---:|---:|---:|---:|"]
    for sigla, n in contagem.items():
        r = resumo.get(sigla, {})
        linhas.append(f"| {sigla} | {n} | {r.get('entradas', 0)} | {r.get('saidas', 0)} "
                      f"| {r.get('mudancas', 0)} |")
    linhas.append(f"| **Total** | **{sum(contagem.values())}** | | | |")
    return "\n".join(linhas) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Coleta diária do acervo das Comissões da CMSP.")
    ap.add_argument("--se-faltar", action="store_true",
                    help="só coleta se a data de hoje ainda não tiver coleta")
    ap.add_argument("--forcar", action="store_true",
                    help="grava mesmo que o acervo de alguma comissão tenha caído bruscamente")
    args = ap.parse_args(argv)

    agora = datetime.now(C.FUSO).replace(microsecond=0)
    data = agora.date().isoformat()
    coletas = ler_csv(C.ARQ_COLETAS)
    datas = sorted({c["data"] for c in coletas})

    if args.se_faltar and data in datas:
        log(f"{data} já tem coleta; nada a fazer.")
        return 0
    if datas and data < datas[-1]:
        log(f"ERRO: {data} é anterior à última coleta registrada ({datas[-1]}).")
        return 1
    anterior = max((d for d in datas if d < data), default=None)

    # 1. Baixar tudo antes de gravar qualquer coisa.
    retrato: list[dict] = []
    materias: dict[str, dict] = {}
    autorias: dict[str, list[dict]] = {}
    contagem: dict[str, int] = {}
    for sigla, cod in C.COMISSOES.items():
        t0 = time.monotonic()
        registros = splegis.baixar_comissao(cod)
        for reg in registros:
            linha, materia, auts = splegis.normalizar(reg, sigla)
            retrato.append(linha)
            materias[materia["materia_id"]] = materia
            autorias[materia["materia_id"]] = auts
        contagem[sigla] = len(registros)
        log(f"{sigla}: {len(registros)} matérias ({time.monotonic() - t0:.0f} s)")

    if not args.forcar:
        erro = _queda_brusca(contagem, coletas)
        if erro:
            log(f"ERRO: {erro}")
            return 1

    # 2. Histórico em intervalos.
    historico = ler_csv(C.ARQ_HISTORICO)
    if data in datas:
        log(f"{data} já tinha coleta: substituindo.")
        historico = H.desfazer(historico, data, anterior)
    historico, resumo = H.atualizar(historico, data, retrato, anterior)

    # 3. Catálogos cumulativos: matérias que saíram das comissões continuam lá.
    catalogo = {m["materia_id"]: m for m in ler_csv(C.ARQ_MATERIAS)}
    catalogo.update(materias)
    todas_autorias: dict[str, list[dict]] = {}
    for a in ler_csv(C.ARQ_AUTORIAS):
        todas_autorias.setdefault(a["materia_id"], []).append(a)
    todas_autorias.update(autorias)

    # 4. Gravar; coletas.csv por último, como marca de coleta concluída.
    gravar_csv(C.ARQ_ACERVO, CAMPOS_ACERVO,
               sorted(retrato, key=lambda r: (r["comissao"], num(r["materia_id"]))))
    gravar_csv(C.ARQ_HISTORICO, CAMPOS_HISTORICO, historico)
    gravar_csv(C.ARQ_MATERIAS, CAMPOS_MATERIAS,
               sorted(catalogo.values(), key=lambda m: num(m["materia_id"])))
    gravar_csv(C.ARQ_AUTORIAS, CAMPOS_AUTORIAS,
               [a for mid in sorted(todas_autorias, key=num) for a in todas_autorias[mid]])
    coletas = [c for c in coletas if c["data"] != data] + [
        {"data": data, "coletado_em": agora.isoformat(), "comissao": sigla, "materias": str(n)}
        for sigla, n in contagem.items()]
    gravar_csv(C.ARQ_COLETAS, CAMPOS_COLETAS,
               sorted(coletas, key=lambda c: (c["data"], c["comissao"])))

    md = _resumo_markdown(data, contagem, resumo)
    print(md, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(md)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
