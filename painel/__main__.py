# -*- coding: utf-8 -*-
"""
Gera os dados do painel em site/dados/ a partir de dados/:

- até a primeira coleta, a série reconstruída (dados/reconstrucao/serie.csv);
- dali em diante, a série dos retratos reais (dados/historico.csv), calculada com a
  mesma agregação da reconstrução e mais a contagem de matérias sem relator.

Grava um arquivo por grupo (serie-projetos.json e serie-todas.json), em colunas:
uma lista de datas e, para cada comissão (e TODAS), uma lista por métrica. Grava também
o retrato do dia (retrato.json), matéria a matéria, para as visões do retrato atual; as
passagens das matérias pelas comissões (fluxos.json), para os gráficos de entradas e
saídas, permanência e rotas (ver fluxos.py); e as votações por mês e o tempo de cada
etapa (tramitacao.json, ver etapas.py).

Uso (da raiz do repositório):  python -m painel
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime

from coletor import config as C
from coletor.util import ler_csv, log
from painel import composicao, etapas, fluxos, legislativo, retrato
from reconstrucao import serie as S

SAIDA = C.RAIZ / "site" / "dados"
METRICAS = [*S.CAMPOS[3:], "sem_relator", "relatores"]


def serie_real(coletas: list[dict], historico: list[dict]) -> list[dict]:
    """Uma linha por dia de coleta × comissão (mais TODAS) × grupo, a partir dos intervalos."""
    instantes = {c["data"]: c["coletado_em"] for c in coletas}
    linhas_hist = sorted(historico, key=lambda h: h["desde"])
    comissoes = sorted(C.COMISSOES)
    linhas, proxima, ativas = [], 0, []
    for dia in sorted(instantes):
        # A idade é contada no instante da coleta, como o SPLEGIS faz no relatório.
        instante = datetime.fromisoformat(instantes[dia]).replace(tzinfo=None)
        while proxima < len(linhas_hist) and linhas_hist[proxima]["desde"] <= dia:
            ativas.append(linhas_hist[proxima])
            proxima += 1
        ativas = [h for h in ativas if not h["ate"] or dia <= h["ate"]]
        itens = []
        relatores: dict[tuple, set] = defaultdict(set)  # relatores com matérias distribuídas
        for h in ativas:
            recebido = datetime.fromisoformat(h["recebido_em"]) if h["recebido_em"] else None
            faixa, dias = S.idade(recebido, instante)
            projeto = h["rotulo"].split()[0] in S.PROJETOS
            sem_mexer = None
            if faixa != "pendentes":
                passo = h["interna_data"] or retrato.data_do_resumo(h.get("ultima_interna", ""))
                sem_mexer = S.parado([datetime.fromisoformat(passo) if passo else None, recebido], instante)
            itens.append((h["comissao"], projeto, faixa, dias, S.categoria(h["interna_area"]),
                          S.etapa(h["interna_area"], h["interna_tipo"]), not h["relator_codigo"], sem_mexer))
            if h["relator_codigo"]:
                for comissao in (h["comissao"], S.TODAS):
                    for grupo in ("todas", "projetos") if projeto else ("todas",):
                        relatores[(comissao, grupo)].add(h["relator_codigo"])
        for linha in S.agregar(dia, itens, comissoes, com_relator=True):
            linha["relatores"] = str(len(relatores[(linha["comissao"], linha["grupo"])]))
            linhas.append(linha)
    return linhas


def colunas(linhas: list[dict], grupo: str) -> tuple[list[str], dict]:
    datas = sorted({l["data"] for l in linhas})
    pos = {d: i for i, d in enumerate(datas)}
    comissoes: dict[str, dict] = {}
    for l in linhas:
        if l["grupo"] != grupo:
            continue
        serie = comissoes.setdefault(l["comissao"], {m: [None] * len(datas) for m in METRICAS})
        for m in METRICAS:
            valor = l.get(m, "")
            serie[m][pos[l["data"]]] = int(valor) if valor != "" else None
    return datas, comissoes


def main() -> int:
    coletas = ler_csv(C.ARQ_COLETAS)
    historico = ler_csv(C.ARQ_HISTORICO)
    reais = serie_real(coletas, historico)
    inicio_coleta = min(l["data"] for l in reais)
    reconstruida = [l for l in ler_csv(C.DIR_DADOS / "reconstrucao" / "serie.csv")
                    if l["data"] < inicio_coleta]
    linhas = reconstruida + reais
    ultima = max(coletas, key=lambda c: c["coletado_em"])

    SAIDA.mkdir(parents=True, exist_ok=True)
    for grupo in ("projetos", "todas"):
        datas, comissoes = colunas(linhas, grupo)
        conteudo = {"grupo": grupo, "inicio_coleta": inicio_coleta,
                    "atualizado_em": ultima["coletado_em"], "datas": datas, "comissoes": comissoes}
        arquivo = SAIDA / f"serie-{grupo}.json"
        arquivo.write_text(json.dumps(conteudo, ensure_ascii=False, separators=(",", ":")),
                           encoding="utf-8")
        log(f"{arquivo.name}: {len(datas)} dias, {arquivo.stat().st_size / 1e6:.1f} MB")

    conteudo = retrato.montar(ler_csv(C.ARQ_ACERVO), ler_csv(C.ARQ_MATERIAS),
                              ler_csv(C.ARQ_AUTORIAS), ultima)
    arquivo = SAIDA / "retrato.json"
    arquivo.write_text(json.dumps(conteudo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"{arquivo.name}: {len(conteudo['materias'])} matérias, {arquivo.stat().st_size / 1e6:.1f} MB")

    lista = fluxos.passagens(ler_csv(C.DIR_DADOS / "reconstrucao" / "presencas.csv"), historico,
                             coletas, ler_csv(C.ARQ_TRAMITACOES))
    autorias = composicao.autorias(ler_csv(C.DIR_DADOS / "reconstrucao" / "autorias.csv"), ler_csv(C.ARQ_AUTORIAS),
                                   ler_csv(C.ARQ_MATERIAS))
    nomes_areas = {a["sigla"]: a["nome"] for a in ler_csv(C.DIR_DADOS / "areas.csv")}
    conteudo = fluxos.montar(lista, max(c["data"] for c in coletas), inicio_coleta, ultima["coletado_em"], autorias,
                             nomes_areas)
    arquivo = SAIDA / "fluxos.json"
    arquivo.write_text(json.dumps(conteudo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"{arquivo.name}: {len(lista)} passagens, {arquivo.stat().st_size / 1e6:.1f} MB")

    ancora = min(coletas, key=lambda c: c["data"])["coletado_em"][:19]
    passos = etapas.passos_por_materia(ler_csv(C.DIR_DADOS / "reconstrucao" / "passos_internos.csv"),
                                       ler_csv(C.ARQ_PASSOS_FEED), ancora)
    conteudo = {**etapas.calcular(lista, passos, max(c["data"] for c in coletas)), "inicio_coleta": inicio_coleta}
    arquivo = SAIDA / "tramitacao.json"
    arquivo.write_text(json.dumps(conteudo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"{arquivo.name}: {len(conteudo['meses'])} meses, {arquivo.stat().st_size / 1e3:.0f} kB")

    conteudo = legislativo.montar(ler_csv(C.DIR_DADOS / "relatorias.csv"), ler_csv(C.DIR_DADOS / "encerrados.csv"),
                                  ler_csv(C.DIR_DADOS / "projetos_por_ano.csv"), max(c["data"] for c in coletas),
                                  ler_csv(C.DIR_DADOS / "filiacoes.csv"), ler_csv(C.DIR_DADOS / "cargos_comissoes.csv"),
                                  ler_csv(C.DIR_DADOS / "assuntos.csv"), lista)
    eventos = [{"data": e["data"], "texto": e["texto"], "descricao": e["descricao"]} for e in ler_csv(C.DIR_DADOS / "eventos.csv")]
    (SAIDA / "eventos.json").write_text(json.dumps(eventos, ensure_ascii=False), encoding="utf-8")
    arquivo = SAIDA / "legislativo.json"
    arquivo.write_text(json.dumps(conteudo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"{arquivo.name}: {len(conteudo['relatores'])} relatores, {arquivo.stat().st_size / 1e3:.0f} kB")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
