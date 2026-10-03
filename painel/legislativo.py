# -*- coding: utf-8 -*-
"""
Pareceres, relatores e desfecho dos projetos para o painel (site/dados/legislativo.json), a
partir do que coletor/legislativo.py guarda do webservice do SPLEGIS:

- pareceres: quantos pareceres cada comissão deu por mês, pela conclusão (favorável, pela
  legalidade, pela ilegalidade, contrário, outros);
- relatores: quantos pareceres cada relator deu em cada comissão, por mês, com o partido do
  relator na data do parecer (pelas filiações do cadastro de vereadores);
- presidentes: quem presidiu (e foi vice de) cada comissão, com as datas;
- assuntos: os assuntos dos projetos que chegaram a cada comissão, por mês, sem os termos
  genéricos do vocabulário (criação, alteração, prazo...);
- desfechos: como terminaram os projetos apresentados em cada ano (lei, veto, rejeição,
  retirada, apensamento, arquivamento no fim da legislatura) e quantos seguem em tramitação,
  também pela autoria e pelo partido do primeiro autor;
- prazos: quanto tempo cada comissão levou para dar o parecer, por ano e por autoria;
- membros: quantos membros de cada partido cada comissão tinha, mês a mês;
- funil: até onde chegaram os projetos apresentados em cada ano, por autoria.
"""
from __future__ import annotations

import re
import unicodedata
from bisect import bisect_right
from collections import defaultdict
from datetime import date
from statistics import quantiles

from painel import composicao
from reconstrucao.serie import TODAS

CONCLUSOES = ["favoravel", "legalidade", "ilegalidade", "contrario", "outros"]
DESFECHOS = ["lei", "vetado", "rejeitado", "retirado", "apensado", "legislatura", "outros"]
PRIMEIRO_ANO = 2013
# Termos do vocabulário que descrevem a ação do projeto, não o assunto.
GENERICOS = set("""ALTERACAO CRIACAO EVENTOS INFORMACAO DIVULGACAO PARCERIA AUTORIZACAO PRAZO PROIBICAO ACESSO
INCENTIVO COMBATE PMSP CONVENIO OBRIGATORIEDADE IDENTIFICACAO VALOR ATENDIMENTO SETOR_PRIVADO CONSCIENTIZACAO
REDUCAO PROTECAO POLITICAS_PUBLICAS FISCALIZACAO CMSP SOCIEDADE_CIVIL ACOMPANHAMENTO PAGAMENTO CADASTRO INSTALACAO
MULTA PENALIDADE UTILIZACAO MEMBROS ORIENTACAO PERCENTAGEM INCLUSAO PRIORIDADE QUANTIDADE COMPROVACAO APOIO
COMPETENCIA PARTICIPACAO NORMAS PERIODO DADOS DISPONIBILIDADE RESPONSAVEL CRITERIOS GARANTIA LIMITACAO DESTINACAO
CONTRATACAO AVALIACAO REVOGACAO FUNCIONAMENTO DENUNCIA DIRETRIZ FORNECIMENTO VALORIZACAO ORGAOS_PUBLICOS
ORGAOS_MUNICIPAIS RISCOS MANUTENCAO VAGA COMERCIALIZACAO PRESTACAO_DE_SERVICO AUMENTO PROGRAMA REQUISITOS AMPLIACAO
RELATORIO TREINAMENTO RESPONSABILIDADE BENEFICIO VENDA AQUISICAO ENCAMINHAMENTO IDADE INTEGRACAO PREVENCAO
SEGURANCA GRATUIDADE ISENCAO EMPRESA PLACA IMOVEL RECURSOS_FINANCEIROS CURSOS COMUNICACAO PUBLICIDADE CONSTRUCAO
SERVIDOR HOMENAGEM""".replace("_", " ").split()) | {"SETOR PRIVADO", "POLITICAS PUBLICAS", "SOCIEDADE CIVIL",
    "ORGAOS PUBLICOS", "ORGAOS MUNICIPAIS", "PRESTACAO DE SERVICO", "RECURSOS FINANCEIROS"}
AUTORIAS = ["Vereadores", "Executivo", "Mesa Diretora", "Outros"]
TODAS_AUTORIAS = "Todas"
MINIMO_PRAZOS = 10  # pareceres para a mediana de um ano entrar no gráfico
_RX_NORMA = re.compile(r"^(LEI|DECRETO|EMENDA|RESOLUCAO|PORTARIA)\b")


def _texto(t: str) -> str:
    return unicodedata.normalize("NFD", t or "").encode("ascii", "ignore").decode().upper()


def conclusao(texto: str) -> str:
    t = _texto(texto)
    if t.startswith("CONTRAR"):
        return "contrario"
    if "ILEGAL" in t or t.startswith("INCONSTITUC"):
        return "ilegalidade"
    if t.startswith(("FAVOR", "LEG. E FAV", "LEGALIDADE E FAVOR")):
        return "favoravel"
    if t.startswith(("LEGALIDADE", "CONSTITUCIONALIDADE")):
        return "legalidade"
    return "outros"


def desfecho(motivo: str) -> str:
    t = _texto(motivo)
    if "PROMULGADO" in t or "VETO PARCIAL" in t:
        return "lei"
    if "VETO TOTAL" in t:
        return "vetado"
    if "ILEGALIDADE" in t or "REJEITADO" in t or "CONTRARIO" in t:
        return "rejeitado"
    if "RETIRADO" in t:
        return "retirado"
    if "APENSADO" in t:
        return "apensado"
    if "TERMINO DE LEGISLATURA" in t:
        return "legislatura"
    return "outros"


def partido_na_data(filiacoes: dict[str, list[tuple]], vereador: str, data: str) -> str:
    """Partido do vereador na data, pelas filiações (a mais recente que começou até lá)."""
    lista = filiacoes.get(vereador, [])
    k = bisect_right(lista, (data[:10] + "~",)) - 1
    return lista[k][1] if k >= 0 else (lista[0][1] if lista else "")


def assunto_util(termo: str) -> bool:
    return bool(termo) and termo not in GENERICOS and not _RX_NORMA.match(termo)


def autoria_dos_projetos(autores: list[dict], filiacoes: dict[str, list[tuple]]) -> dict[str, tuple[str, str]]:
    """{rótulo: (autoria, partido do primeiro autor na leitura)}; o partido só para vereadores."""
    executivo = set(composicao.EXECUTIVO)
    primeiro: dict[str, dict] = {}
    for a in autores:
        if a["rotulo"] not in primeiro or int(a["ordem"]) < int(primeiro[a["rotulo"]]["ordem"]):
            primeiro[a["rotulo"]] = a
    saida = {}
    for rotulo, a in primeiro.items():
        classe = composicao.classe(a["autor"], a["autor_codigo"], executivo)
        classe = classe if classe in AUTORIAS else "Outros"
        data = a["leitura"] or f"{rotulo.rsplit('/', 1)[1]}-07-01"
        partido = partido_na_data(filiacoes, a["autor"], data) or "sem partido" if classe == "Vereadores" else ""
        saida[rotulo] = (classe, partido)
    return saida


def _quartis(v: list[int]) -> tuple:
    if len(v) < MINIMO_PRAZOS:
        return None, None, None
    q = quantiles(v, n=4, method="inclusive")
    return round(q[0]), round(q[1]), round(q[2])


def prazos(relatorias: list[dict], autoria: dict[str, tuple[str, str]], anos: list[int]) -> dict:
    """Dias até o parecer, pelo ano do parecer. O prazo de cada comissão conta do despacho ou,
    se outra comissão do mesmo despacho deu parecer antes, do último desses pareceres: as
    comissões opinam uma depois da outra. Só conta o primeiro despacho de cada projeto: os
    seguintes são em geral da segunda discussão, com parecer no mesmo dia, em reunião
    conjunta. Ficam de fora também redação final, emendas e vetos."""
    primeiro: dict[str, int] = {}
    for r in relatorias:
        if r["despacho"].isdigit():
            primeiro[r["rotulo"]] = min(primeiro.get(r["rotulo"], 10**6), int(r["despacho"]))
    por_despacho: dict[tuple, list[dict]] = defaultdict(list)
    for r in relatorias:
        if (r["parecer_em"] and r["despachado_em"] and conclusao(r["conclusao"]) != "outros"
                and r["despacho"].isdigit() and int(r["despacho"]) == primeiro[r["rotulo"]]):
            por_despacho[(r["rotulo"], r["despacho"])].append(r)
    duracoes: dict[tuple, list[int]] = defaultdict(list)
    for lista in por_despacho.values():
        datas = sorted({r["parecer_em"][:10] for r in lista})
        for r in lista:
            dia = r["parecer_em"][:10]
            antes = [d for d in datas if d < dia]
            inicio = max([r["despachado_em"][:10], *antes])
            dias = (date.fromisoformat(dia) - date.fromisoformat(inicio)).days
            ano = int(dia[:4])
            if dias < 0 or ano not in anos:
                continue
            classe = autoria.get(r["rotulo"], ("Outros", ""))[0]
            for c in (r["comissao"], TODAS):
                for a in (classe, TODAS_AUTORIAS):
                    duracoes[(c, a, ano)].append(dias)
    series: dict[str, dict] = {}
    for c in sorted({c for c, _, _ in duracoes}):
        series[c] = {}
        for a in [TODAS_AUTORIAS, *AUTORIAS]:
            s = {"mediana": [], "p25": [], "p75": [], "n": []}
            for ano in anos:
                v = duracoes.get((c, a, ano), [])
                p25, med, p75 = _quartis(v)
                s["p25"].append(p25)
                s["mediana"].append(med)
                s["p75"].append(p75)
                s["n"].append(len(v))
            series[c][a] = s
    return series


def membros(cargos: list[dict], filiacoes: dict[str, list[tuple]], fim: str) -> dict:
    """Membros de cada comissão por partido, no dia 15 de cada mês desde 2013 (no último mês,
    no último dia de dados). Quem ocupa mais de um cargo na mesma comissão conta uma vez."""
    meses, m = [], date(PRIMEIRO_ANO, 1, 1)
    while m.isoformat()[:7] <= fim[:7]:
        meses.append(m.isoformat()[:7])
        m = date(m.year + m.month // 12, m.month % 12 + 1, 1)
    por_comissao: dict[str, list[dict]] = defaultdict(list)
    for c in cargos:
        if not c["fim"] or c["fim"] >= f"{PRIMEIRO_ANO}-01-01":
            por_comissao[c["comissao"]].append(c)
    contagem: dict[str, dict[tuple, int]] = defaultdict(lambda: defaultdict(int))
    partidos: dict[str, int] = defaultdict(int)  # cadeiras × mês desde nov/2018, para ordenar
    for i, mes in enumerate(meses):
        dia = min(f"{mes}-15", fim[:10])
        for comissao, lista in por_comissao.items():
            presentes = {c["vereador"] for c in lista if c["inicio"][:10] <= dia and (not c["fim"] or c["fim"][:10] >= dia)}
            for v in presentes:
                p = partido_na_data(filiacoes, v, dia) or "sem partido"
                contagem[comissao][(i, p)] += 1
                contagem[TODAS][(i, p)] += 1
                if mes >= "2018-11":
                    partidos[p] += 1
    ordem = sorted({p for d in contagem.values() for _, p in d}, key=lambda p: (-partidos[p], p))
    idx = {p: k for k, p in enumerate(ordem)}
    return {"meses": meses, "partidos": ordem,
            # por comissão: [mês, partido, membros, ...]
            "por_comissao": {c: [v for (i, p), n in sorted(d.items(), key=lambda x: (x[0][0], idx[x[0][1]]))
                                 for v in (i, idx[p], n)] for c, d in contagem.items()}}


ETAPAS_FUNIL = ["apresentados", "relator", "parecer", "comissoes", "aprovados", "lei"]


def funil(relatorias: list[dict], encerrados: list[dict], autoria: dict[str, tuple[str, str]], anos: list[int]) -> dict:
    """Até que etapa chegou cada projeto: apresentado, com relator em alguma comissão, com algum
    parecer, com o parecer de todas as comissões do primeiro despacho, aprovado pela Câmara (virou
    lei ou teve veto total) e virou lei. As etapas são encaixadas: o projeto que chegou a uma conta
    também em todas as anteriores (o aprovado sem parecer de alguma comissão, com parecer dado em
    plenário, conta como se tivesse passado por elas)."""
    por_projeto: dict[str, list[dict]] = defaultdict(list)
    for r in relatorias:
        por_projeto[r["rotulo"]].append(r)
    fim = {e["rotulo"]: desfecho(e["motivo"]) for e in encerrados}
    contagem = {a: [[0] * len(ETAPAS_FUNIL) for _ in anos] for a in AUTORIAS}
    for rotulo, (classe, _) in autoria.items():
        ano = int(rotulo.rsplit("/", 1)[1])
        if ano not in anos:
            continue
        linhas = por_projeto.get(rotulo, [])
        despachos = [int(r["despacho"]) for r in linhas if r["despacho"].isdigit()]
        primeiro = [r for r in linhas if despachos and r["despacho"] == str(min(despachos))]
        etapa = 0
        if linhas:
            etapa = 1
        if any(r["parecer_em"] and conclusao(r["conclusao"]) != "outros" for r in linhas):
            etapa = 2
        if primeiro and all(r["parecer_em"] for r in primeiro):
            etapa = 3
        if fim.get(rotulo) in ("lei", "vetado"):
            etapa = 4
        if fim.get(rotulo) == "lei":
            etapa = 5
        linha = contagem[classe][anos.index(ano)]
        for k in range(etapa + 1):
            linha[k] += 1
    return {"etapas": ETAPAS_FUNIL, "por_autoria": contagem}  # por autoria: [projetos em cada etapa] por ano


def montar(relatorias: list[dict], encerrados: list[dict], contagem: list[dict], fim: str,
           filiacoes: list[dict] = (), cargos: list[dict] = (), assuntos: list[dict] = (),
           passagens: list[dict] = (), autores: list[dict] = ()) -> dict:
    meses = []
    m = date(2018, 11, 1)
    while m.isoformat()[:7] <= fim[:7]:
        meses.append(m.isoformat()[:7])
        m = date(m.year + m.month // 12, m.month % 12 + 1, 1)
    pos = {mes: i for i, mes in enumerate(meses)}
    por_vereador: dict[str, list[tuple]] = defaultdict(list)
    for f in filiacoes:
        por_vereador[f["vereador"]].append((f["inicio"][:10], f["partido"]))
    for lista in por_vereador.values():
        lista.sort()
    partidos: dict[str, int] = {}

    comissoes = sorted({r["comissao"] for r in relatorias})
    pareceres = {c: {k: [0] * len(meses) for k in CONCLUSOES} for c in [*comissoes, TODAS]}
    relatores: dict[tuple, int] = {}
    por_relator: dict[str, dict[tuple, int]] = defaultdict(lambda: defaultdict(int))
    for r in relatorias:
        if not r["parecer_em"] or r["parecer_em"][:7] not in pos:
            continue
        i = pos[r["parecer_em"][:7]]
        k = conclusao(r["conclusao"])
        for c in (r["comissao"], TODAS):
            pareceres[c][k][i] += 1
        if r["relator"]:
            idx = relatores.setdefault(r["relator"], len(relatores))
            na_epoca = partido_na_data(por_vereador, r["relator"], r["parecer_em"]) or r["partido"]
            p = partidos.setdefault(na_epoca or "sem partido", len(partidos))
            por_relator[r["comissao"]][(i, idx, p)] += 1

    anos = list(range(PRIMEIRO_ANO, int(fim[:4]) + 1))
    apresentados = defaultdict(int)
    for c in contagem:
        apresentados[int(c["ano"])] += int(c["projetos"])
    desfechos = {k: [0] * len(anos) for k in DESFECHOS}
    for e in encerrados:
        ano = int(e["ano"])
        if ano in anos:
            desfechos[desfecho(e["motivo"])][anos.index(ano)] += 1
    encerrados_ano = [sum(desfechos[k][i] for k in DESFECHOS) for i in range(len(anos))]

    # Desfecho pela autoria e pelo partido do primeiro autor (só projetos com autor conhecido).
    autoria = autoria_dos_projetos(autores, por_vereador)
    motivo = {e["rotulo"]: e["motivo"] for e in encerrados}
    vazio = lambda: {k: [0] * len(anos) for k in [*DESFECHOS, "aberto"]}  # noqa: E731
    por_autoria = {a: vazio() for a in AUTORIAS}
    por_partido: dict[str, dict] = defaultdict(vazio)
    for rotulo, (classe, partido) in autoria.items():
        ano = int(rotulo.rsplit("/", 1)[1])
        if ano not in anos:
            continue
        k = desfecho(motivo[rotulo]) if rotulo in motivo else "aberto"
        por_autoria[classe][k][anos.index(ano)] += 1
        if partido:
            por_partido[partido][k][anos.index(ano)] += 1

    hoje = fim[:10]
    atual = {v: partido_na_data(por_vereador, v, hoje) for v in relatores}
    presidentes = defaultdict(list)
    for c in sorted(cargos, key=lambda c: c["inicio"]):
        if c["cargo"] in ("Presidente", "Vice-presidente") and (not c["fim"] or c["fim"] >= "2013-01-01"):
            presidentes[c["comissao"]].append([c["cargo"], c["vereador"], partido_na_data(por_vereador, c["vereador"], c["inicio"]),
                                               c["inicio"][:10], c["fim"][:10]])

    # Assuntos dos projetos pela chegada a cada comissão (e, em TODAS, pela primeira chegada).
    termos_por = {a["rotulo"]: [t for t in a["assuntos"].split(" | ") if assunto_util(t)] for a in assuntos}
    # Só os 300 assuntos mais frequentes: a cauda longa do vocabulário pesaria no arquivo sem aparecer na lista.
    frequencia = defaultdict(int)
    for lista in termos_por.values():
        for t in lista:
            frequencia[t] += 1
    principais = set(sorted(frequencia, key=lambda t: -frequencia[t])[:300])
    termos_por = {r: [t for t in lista if t in principais] for r, lista in termos_por.items()}
    termos: dict[str, int] = {}
    por_assunto: dict[str, dict[tuple, int]] = defaultdict(lambda: defaultdict(int))
    chegadas: dict[str, list[int]] = defaultdict(lambda: [0] * len(meses))
    primeira: dict[str, str] = {}
    for p in passagens:
        if p["desde"] and p["rotulo"] in termos_por:
            primeira[p["rotulo"]] = min(primeira.get(p["rotulo"], p["desde"]), p["desde"])
    entradas = [(p["comissao"], p["rotulo"], p["desde"]) for p in passagens if p["desde"] and p["rotulo"] in termos_por]
    entradas += [(TODAS, r, d) for r, d in primeira.items()]
    for comissao, rotulo, desde in entradas:
        if desde[:7] not in pos:
            continue
        i = pos[desde[:7]]
        chegadas[comissao][i] += 1
        for t in termos_por[rotulo]:
            por_assunto[comissao][(i, termos.setdefault(t, len(termos)))] += 1
    return {
        "meses": meses,
        "pareceres": pareceres,
        "relatores": [[r, atual[r]] for r in relatores],  # nome e partido de hoje
        "partidos": list(partidos),
        # por comissão: [mês, relator, partido na época, pareceres, ...]
        "pareceres_por_relator": {c: [v for (i, idx, p), n in sorted(d.items()) for v in (i, idx, p, n)]
                                  for c, d in por_relator.items()},
        "presidentes": presidentes,  # por comissão: [cargo, vereador, partido no início, início, fim]
        "assuntos": list(termos),
        # por comissão: [mês, assunto, projetos que chegaram, ...]; chegadas: projetos com assunto por mês
        "assuntos_por_mes": {c: [v for (i, t), n in sorted(d.items()) for v in (i, t, n)] for c, d in por_assunto.items()},
        "chegadas_com_assunto": chegadas,
        "anos": anos,
        "apresentados": [apresentados.get(a) for a in anos],
        "desfechos": desfechos,
        "em_tramitacao": [None if apresentados.get(a) is None else max(0, apresentados[a] - encerrados_ano[i])
                          for i, a in enumerate(anos)],
        # por autoria e por partido do primeiro autor: {desfecho ou "aberto": [projetos por ano]}
        "desfechos_autoria": por_autoria,
        "desfechos_partido": dict(sorted(por_partido.items())),
        "prazos": prazos(relatorias, autoria, anos),
        "membros": membros(cargos, por_vereador, fim),
        "funil": funil(relatorias, encerrados, autoria, anos),
    }
