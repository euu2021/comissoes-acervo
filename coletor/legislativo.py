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
  assuntos.csv         assuntos de cada projeto, no vocabulário da Câmara (ProjetosAssuntos)
  autores.csv          autores de cada projeto, na ordem, com a data de leitura (ProjetosAutores)
  vetos.csv            projetos vetados, total ou parcialmente, pelos autores de autores.csv
                       (ProjetosVetadosPorPromovente). O veto aparece aqui logo que é dado; em
                       encerrados.csv, só quando a Câmara o aprecia, às vezes anos depois.
  filiacoes.csv        partidos de cada vereador, com as datas (VereadoresCMSP)
  cargos_comissoes.csv presidentes, vices e membros das 7 comissões, com as datas (VereadoresCMSP)

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
CAMPOS_ASSUNTOS = ["rotulo", "assuntos"]
CAMPOS_AUTORES = ["rotulo", "leitura", "ordem", "autor_codigo", "autor"]
CAMPOS_VETOS = ["rotulo", "veto"]
CAMPOS_FILIACOES = ["vereador", "partido", "inicio", "fim"]
CAMPOS_CARGOS = ["comissao", "cargo", "vereador", "inicio", "fim"]
# Comissões permanentes no cadastro de cargos, pelo nome (as extraordinárias ficam de fora).
_NOMES_COMISSOES = [("JUSTIÇA", "CCJ"), ("FINANÇAS", "FIN"), ("POLÍTICA URBANA", "URB"), ("ADMINISTRAÇÃO PÚBLICA", "ADM"),
                    ("TRÂNSITO", "ECON"), ("EDUCAÇÃO", "EDUC"), ("SAÚDE", "SAUDE")]
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


def assuntos(itens: list[dict]) -> list[dict]:
    return [{"rotulo": f"{p['tipo']} {p['numero']}/{p['ano']}",
             "assuntos": " | ".join(dict.fromkeys(a["texto"].strip() for a in p.get("assuntos") or [] if a.get("texto")))}
            for p in itens if p.get("assuntos")]


def autores(itens: list[dict]) -> list[dict]:
    return [{"rotulo": f"{p['tipo']} {p['numero']}/{p['ano']}", "leitura": _data(p.get("leitura")), "ordem": str(k),
             "autor_codigo": str(a.get("chave") or ""), "autor": (a.get("nome") or "").strip()}
            for p in itens for k, a in enumerate(p.get("autores") or [], 1)]


def vetos(itens: list[dict]) -> list[dict]:
    return [{"rotulo": f"{p['tipo']} {p['numero']}/{p['ano']}", "veto": ((p.get("veto") or {}).get("nome") or "").strip()}
            for p in itens if p.get("tipo") in TIPOS]


def vereadores(itens: list[dict]) -> tuple[list[dict], list[dict]]:
    """(filiações partidárias, cargos nas 7 comissões permanentes) de cada vereador."""
    filiacoes, cargos = [], []
    for v in itens:
        for f in v.get("filiacoes") or []:
            filiacoes.append({"vereador": v["nome"], "partido": (f.get("partido") or {}).get("sigla", ""),
                              "inicio": _data(f.get("inicio")), "fim": _data(f.get("fim"))})
        for c in v.get("cargos") or []:
            ente = ((c.get("ente") or {}).get("nome") or "").upper()
            if not ente.startswith("COMISSÃO - COMISSÃO DE") or "EXTRA" in ente:
                continue
            sigla = next((s for chave, s in _NOMES_COMISSOES if chave in ente), None)
            if sigla:
                cargos.append({"comissao": sigla, "cargo": c.get("nome", ""), "vereador": v["nome"],
                               "inicio": _data(c.get("inicio")), "fim": _data(c.get("fim"))})
    return filiacoes, cargos


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

    filiacoes, cargos = vereadores(_json("VereadoresCMSPJSON"))
    gravar_csv(C.DIR_DADOS / "filiacoes.csv", CAMPOS_FILIACOES, sorted(filiacoes, key=lambda f: (f["vereador"], f["inicio"])))
    gravar_csv(C.DIR_DADOS / "cargos_comissoes.csv", CAMPOS_CARGOS,
               sorted(cargos, key=lambda c: (c["comissao"], c["inicio"], c["cargo"], c["vereador"])))
    log(f"vereadores: {len(filiacoes)} filiações, {len(cargos)} cargos nas comissões")

    rel, enc, cont, ass, aut = [], [], [], [], []
    for ano in anos:
        for tipo in TIPOS:
            rel += relatorias(_json(f"ProjetosReunioesDeComissaoJSON?ano={ano}&tipo={tipo}"))
            ass += assuntos(_json(f"ProjetosAssuntosJSON?ano={ano}&tipo={tipo}"))
            aut += autores(_json(f"ProjetosAutoresJSON?ano={ano}&tipo={tipo}&numero="))
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
    _refazer(C.DIR_DADOS / "assuntos.csv", CAMPOS_ASSUNTOS, ass, feitos, lambda l: _ano(l["rotulo"]))
    _refazer(C.DIR_DADOS / "autores.csv", CAMPOS_AUTORES, aut, feitos, lambda l: _ano(l["rotulo"]))

    # Vetos: a consulta é por autor, com os projetos de todos os anos; ficam só os dos anos refeitos.
    codigos = sorted({a["autor_codigo"] for a in aut if a["autor_codigo"]}, key=int)
    vet: dict[str, dict] = {}
    for codigo in codigos:
        for v in vetos(_json(f"ProjetosVetadosPorPromoventeJSON?Codigo={codigo}")):
            if _ano(v["rotulo"]) in feitos:
                vet[v["rotulo"]] = v
    log(f"vetos: {len(codigos)} autores consultados")
    _refazer(C.DIR_DADOS / "vetos.csv", CAMPOS_VETOS, list(vet.values()), feitos, lambda l: _ano(l["rotulo"]))
    _refazer(C.DIR_DADOS / "projetos_por_ano.csv", CAMPOS_CONTAGEM, cont, set(anos_contagem), lambda l: int(l["ano"]))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
