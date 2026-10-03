# -*- coding: utf-8 -*-
"""
Dados do processo legislativo que o relatório das comissões não traz, tirados do
webservice do SPLEGIS (https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx):

  areas.csv            nome de cada área de tramitação (SGP21 = Equipe de Apoio ao Plenário...)
  relatorias.csv       relator de cada projeto em cada comissão, com o parecer e a conclusão,
                       por despacho (ProjetosReunioesDeComissao)
  encerrados.csv       como terminou cada projeto encerrado: lei, veto, arquivamento...
                       (ProjetosEncerrados)
  projetos_por_ano.csv quantos projetos de cada tipo foram apresentados por ano (ProjetosPorAno)

Cada execução refaz os anos pedidos (pelo ano do projeto) e mantém os demais.

Uso:
  python -m coletor.legislativo                     os últimos 8 anos (contagem: os 2 últimos)
  python -m coletor.legislativo --desde 2013        do ano dado até o atual, contagem inclusive
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime

from coletor import config as C
from coletor.util import gravar_csv, ler_csv, log
from reconstrucao import fontes

URL = "https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx/"
TIPOS = ["PL", "PDL", "PR", "PLO"]
CAMPOS_AREAS = ["sigla", "nome"]
CAMPOS_RELATORIAS = ["rotulo", "comissao", "despacho", "despachado_em", "relator", "partido", "parecer",
                     "parecer_em", "conclusao"]
CAMPOS_ENCERRADOS = ["rotulo", "tipo", "ano", "leitura", "encerramento", "motivo"]
CAMPOS_CONTAGEM = ["ano", "tipo", "projetos"]
_RX_PARTIDO = re.compile(r"\(([^()]+)\)\s*$")


def _json(operacao: str) -> list:
    return json.loads(fontes.baixar_json(URL + operacao))


def _data(v) -> str:
    return (v or "")[:19]


def relatorias(itens: list[dict]) -> list[dict]:
    """Uma linha por projeto × despacho × comissão permanente."""
    linhas = []
    for p in itens:
        rotulo = f"{p['tipo']} {p['numero']}/{p['ano']}"
        for e in p.get("encaminhamentos") or []:
            for c in e.get("comissoes") or []:
                if c.get("nome") not in C.COMISSOES:
                    continue
                relatorio = c.get("relatorio") or {}
                m = _RX_PARTIDO.search(c.get("relator") or "")
                linhas.append({
                    "rotulo": rotulo, "comissao": c["nome"], "despacho": str(e.get("sequencia", "")),
                    "despachado_em": _data(e.get("data")), "relator": (c.get("nomePolitico") or "").strip(),
                    "partido": m[1].strip() if m else "",
                    "parecer": f"{relatorio['numero']}/{relatorio['ano']}" if relatorio.get("numero") else "",
                    "parecer_em": _data(c.get("dataParecer")), "conclusao": (c.get("conclusao") or "").strip(),
                })
    return linhas


def encerrados(itens: list[dict]) -> list[dict]:
    return [{"rotulo": f"{p['tipo']} {p['numero']}/{p['ano']}", "tipo": p["tipo"], "ano": str(p["ano"]),
             "leitura": _data(p.get("leitura")), "encerramento": _data(p.get("encerramento")),
             "motivo": (p.get("motivo") or "").strip()} for p in itens]


def _ano(rotulo: str) -> int:
    return int(rotulo.rsplit("/", 1)[1])


def _refazer(arquivo, campos, novas: list[dict], anos: set[int], chave) -> None:
    """Troca as linhas dos anos refeitos e mantém as outras, em ordem estável."""
    linhas = [l for l in ler_csv(arquivo) if chave(l) not in anos] + novas
    linhas.sort(key=lambda l: tuple(l[c] for c in campos))
    gravar_csv(arquivo, campos, linhas)
    log(f"{arquivo.name}: {len(novas)} linhas dos anos refeitos, {len(linhas)} no total")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Relatorias, desfechos e contagens do webservice do SPLEGIS.")
    ap.add_argument("--desde", type=int, help="primeiro ano (padrão: os últimos 8 anos)")
    args = ap.parse_args(argv)
    atual = datetime.now(C.FUSO).year
    anos = list(range(args.desde or atual - 7, atual + 1))
    anos_contagem = anos if args.desde else anos[-2:]

    areas = sorted(({"sigla": a["sigla"], "nome": a["nome"].strip()} for a in _json("AreasDeTramitacaoJSON")),
                   key=lambda a: a["sigla"])
    gravar_csv(C.DIR_DADOS / "areas.csv", CAMPOS_AREAS, areas)
    log(f"areas.csv: {len(areas)} áreas")

    rel, enc, cont = [], [], []
    for ano in anos:
        for tipo in TIPOS:
            rel += relatorias(_json(f"ProjetosReunioesDeComissaoJSON?ano={ano}&tipo={tipo}"))
        enc += [e for e in encerrados(_json(f"ProjetosEncerradosJSON?ano={ano}")) if e["tipo"] in TIPOS]
        if ano in anos_contagem:
            por_tipo: dict[str, int] = {}
            for p in _json(f"ProjetosPorAnoJSON?Ano={ano}"):
                if p.get("tipo") in TIPOS:
                    por_tipo[p["tipo"]] = por_tipo.get(p["tipo"], 0) + 1
            cont += [{"ano": str(ano), "tipo": t, "projetos": str(por_tipo.get(t, 0))} for t in TIPOS]
        log(f"{ano}: {len(rel)} relatorias e {len(enc)} encerrados até aqui")

    feitos = set(anos)
    _refazer(C.DIR_DADOS / "relatorias.csv", CAMPOS_RELATORIAS, rel, feitos, lambda l: _ano(l["rotulo"]))
    _refazer(C.DIR_DADOS / "encerrados.csv", CAMPOS_ENCERRADOS, enc, feitos, lambda l: int(l["ano"]))
    _refazer(C.DIR_DADOS / "projetos_por_ano.csv", CAMPOS_CONTAGEM, cont, set(anos_contagem), lambda l: int(l["ano"]))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
