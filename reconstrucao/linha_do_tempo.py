# -*- coding: utf-8 -*-
"""
Linha do tempo de cada matéria: por quais comissões passou (presenças) e por quais
passos de tramitação interna, a partir dos eventos corrigidos e ancorada no retrato real.

Valores desconhecidos (anteriores ao início do feed e não recuperados do histórico
oficial) são marcados com "?".
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from reconstrucao.eventos import COMISSOES, Evento

DESCONHECIDO = "?"


@dataclass(slots=True)
class Trecho:
    """Situação externa de uma matéria a partir de `inicio` (None = desde antes do feed).

    `estada` é quando a matéria foi enviada a `loc` (None = antes do feed). Campos None
    são desconhecidos; recebido_em "" significa envio ainda não recebido."""
    inicio: str | None
    loc: str | None
    estada: str | None
    enviado_por: str | None = None
    enviado_em: str | None = None
    recebido_em: str | None = None


def trechos(externos: list[Evento], ancora: dict | None) -> tuple[list[Trecho], list[str]]:
    """Trechos de localização da matéria e as incoerências encontradas na sequência.

    Como no relatório do SPLEGIS, a matéria está no destino do último envio vigente
    (recebida ou não); recebimentos só marcam a data de recebimento. Os envios formam uma
    pilha: excluir um envio devolve a matéria à estada anterior, com as datas dela. A
    situação anterior ao primeiro envio sai dele (matéria enviada pela CCJ estava na CCJ);
    sem envios, vale o retrato.

    Recebimento numa área onde a matéria não está é ignorado: costuma ser o registro
    tardio de uma tramitação antiga (há DOCRECs arquivados em 2011 "recebidos" em 2019).
    Mas, se depois a matéria sai dessa área (ou o retrato a mostra lá), o envio para ela
    faltou no feed, e a estada passa a contar do recebimento."""
    movimentos = [e for e in externos if e.tipo in ("envio", "excl_envio")]
    if not movimentos:
        if ancora is None:
            return [Trecho(None, None, None)], []
        pilha = [Trecho(None, ancora["comissao"], None, ancora["enviado_por"],
                        ancora["enviado_em"], None)]
    else:
        m0 = movimentos[0]
        pilha = [Trecho(None, m0.de if m0.tipo == "envio" else m0.para, None)]

    lista = [pilha[-1]]
    anomalias: list[str] = []
    ignorados: dict[str, str] = {}  # área -> recebimento ignorado desde a última mudança

    def registrar(t: str) -> None:
        lista.append(replace(pilha[-1], inicio=t))

    for e in externos:
        topo = pilha[-1]
        if e.tipo == "envio":
            if topo.loc != e.de:
                anomalias.append(f"{e.t} enviada de {e.de} estando em {topo.loc}")
                if e.de in ignorados:  # o envio para `de` faltou no feed
                    t = ignorados[e.de]
                    pilha.append(Trecho(t, e.de, t, None, None, t))
                    registrar(t)
            pilha.append(Trecho(e.t, e.para, e.t, e.de, e.t, ""))
            ignorados = {}
        elif e.tipo == "excl_envio":
            if topo.loc != e.para:
                anomalias.append(f"{e.t} envio para {e.para} excluído estando em {topo.loc}")
                continue
            pilha.pop()
            if not pilha:  # a estada anterior começou antes do feed
                pilha.append(Trecho(None, e.de, None))
            ignorados = {}
        elif e.tipo == "receb":
            if topo.loc != e.para:
                anomalias.append(f"{e.t} recebida em {e.para} estando em {topo.loc}")
                ignorados[e.para] = e.t
                continue
            pilha[-1] = replace(topo, recebido_em=e.t)
        else:  # excl_receb
            if topo.loc != e.para:
                anomalias.append(f"{e.t} recebimento excluído em {e.para} estando em {topo.loc}")
                continue
            pilha[-1] = replace(topo, recebido_em="")
        registrar(e.t)

    if ancora is not None and pilha[-1].loc != ancora["comissao"] and ancora["comissao"] in ignorados:
        t = ignorados[ancora["comissao"]]  # o retrato confirma: o envio faltou no feed
        anomalias.append(f"{t} retrato em {ancora['comissao']} estando em {pilha[-1].loc}")
        pilha.append(Trecho(t, ancora["comissao"], t, None, None, t))
        registrar(t)
    lista.sort(key=lambda tr: tr.inicio or "")  # estadas recuperadas de recebimentos ignorados
    return lista, anomalias


@dataclass(slots=True)
class Passo:
    data: str
    area: str
    passo: str
    comentario: str
    fonte: str              # feed | chegada | exclusao | historico | retrato | desconhecido


@dataclass(slots=True)
class Presenca:
    """Período em que a matéria esteve no acervo de uma comissão: de `desde` (envio à
    comissão; None = antes do feed) até `ate` (saída; None = continua no retrato)."""
    comissao: str
    rotulo: str
    desde: str | None
    ate: str | None
    enviado_por: str | None
    enviado_em: str | None
    recebido_em: str | None
    destino: str | None
    passos: list[Passo]


def _passos_do_feed(p: Presenca, internas: list[Evento]) -> list[Passo]:
    """Passos internos da presença, na ordem. Quando o passo vigente é excluído, o
    anterior volta a valer a partir da exclusão (registrado com fonte "exclusao")."""
    vigentes: list[Passo] = []
    saida: list[Passo] = []
    for e in internas:
        if (e.comissao != p.comissao or (p.desde is not None and e.t < p.desde)
                or (p.ate is not None and e.t >= p.ate)):
            continue
        if e.tipo == "interna":
            x = Passo(e.t, e.area, e.passo, e.comentario, "feed")
            vigentes.append(x)
            saida.append(x)
            continue
        alvo = next((i for i in range(len(vigentes) - 1, -1, -1)
                     if (vigentes[i].area, vigentes[i].passo) == (e.area, e.passo)), None)
        if alvo is None:
            continue  # passo anterior ao feed
        era_o_vigente = alvo == len(vigentes) - 1
        del vigentes[alvo]
        if era_o_vigente:
            if vigentes:
                volta = vigentes[-1]
                saida.append(Passo(e.t, volta.area, volta.passo, volta.comentario, "exclusao"))
            else:
                vazio = "" if p.desde is not None else DESCONHECIDO
                saida.append(Passo(e.t, vazio, vazio, "", "exclusao"))
    return saida


def presencas(rotulo: str, lista: list[Trecho], internas: list[Evento],
              ancora: dict | None, inicio_feed: str) -> list[Presenca]:
    """Agrupa os trechos em presenças nas comissões e distribui os passos internos
    (`internas` traz os eventos "interna" e "excl_interna" da matéria)."""
    grupos: list[list[Trecho]] = []
    for tr in lista:
        if grupos and (grupos[-1][-1].loc, grupos[-1][-1].estada) == (tr.loc, tr.estada):
            grupos[-1].append(tr)
        else:
            grupos.append([tr])

    saida = []
    for i, g in enumerate(grupos):
        if g[0].loc not in COMISSOES:
            continue
        seguinte = grupos[i + 1][0] if i + 1 < len(grupos) else None
        ultimo = g[-1]
        p = Presenca(g[0].loc, rotulo, g[0].inicio, seguinte.inicio if seguinte else None,
                     ultimo.enviado_por, ultimo.enviado_em, ultimo.recebido_em,
                     seguinte.loc if seguinte else None, [])
        p.passos = _passos_do_feed(p, internas)
        if p.ate is None and ancora is not None and ancora["comissao"] == p.comissao:
            # Presença que chega ao retrato: completa o que os eventos não disseram.
            if p.enviado_em is None:
                p.enviado_por, p.enviado_em = ancora["enviado_por"], ancora["enviado_em"]
            if p.recebido_em is None:
                p.recebido_em = ancora["recebido_em"]
            if p.desde is None and p.enviado_em and p.enviado_em > inicio_feed:
                p.desde = p.enviado_em  # o envio caiu numa lacuna do feed
            if not p.passos:
                p.passos = [Passo(ancora["interna_data"], ancora["interna_area"],
                                  ancora["interna_tipo"], ancora["interna_comentario"], "retrato")]
        if p.desde is not None and (not p.passos or p.passos[0].data > p.desde):
            # Chegou durante o feed: até o primeiro passo interno, não há passo.
            p.passos.insert(0, Passo(p.desde, "", "", "", "chegada"))
        saida.append(p)
    return saida


def precisa_do_historico(p: Presenca) -> bool:
    """Presença iniciada antes do feed com algo ainda desconhecido."""
    return p.desde is None and (p.enviado_em is None or p.recebido_em is None
                                or not p.passos or p.passos[0].fonte == "feed")


def completar_com_historico(p: Presenca, linhas: list[tuple[str, str, str]], inicio_feed: str) -> bool:
    """Completa uma presença sem início conhecido com o histórico oficial da matéria:
    o envio que a levou à comissão (ou o registro inicial feito nela), o recebimento e o
    passo interno vigente antes do primeiro passo do feed. Em geral a estada começou antes
    do feed; se começou depois (o envio faltou no feed, ou a matéria foi registrada já na
    comissão), a presença passa a contar dali. Só usa o histórico se ele mostrar a
    matéria na comissão até a saída registrada no feed."""
    c = p.comissao
    envio = None
    for i, (ti, acao, _) in enumerate(linhas):
        if p.ate is not None and (ti > p.ate or (ti == p.ate and acao.startswith(f"{c}/"))):
            break  # chegou à saída (ou passou dela)
        if acao.endswith(f"/Encaminhado para {c}") or (i == 0 and acao == c):
            envio = i
        elif acao.startswith(f"{c}/Encaminhado para "):
            envio = None  # saiu da comissão
    if envio is None:
        return False
    t_envio, acao_envio, _ = linhas[envio]
    if p.enviado_em is None:
        origem = acao_envio.split("/", 1)[0] if "/" in acao_envio else ""  # "" = registro inicial
        p.enviado_por, p.enviado_em = origem, t_envio
    p.desde = t_envio
    if p.recebido_em is None:
        p.recebido_em = next((ti for ti, acao, _ in linhas[envio + 1:]
                              if acao in (c, f"{c}/Recebido")
                              and (p.ate is None or ti < p.ate)), "")
    primeiro = p.passos[0].data if p.passos and p.passos[0].fonte == "feed" else inicio_feed
    anterior = None
    for ti, acao, obs in linhas[envio + 1:]:
        if ti >= primeiro:
            break
        partes = acao.split("/", 2)
        if len(partes) == 3 and partes[0] == c:
            anterior = Passo(ti, partes[1], partes[2], obs, "historico")
    p.passos = [x for x in p.passos if x.fonte != "retrato"]
    p.passos.insert(0, anterior or Passo(t_envio, "", "", "", "historico"))
    return True


def marcar_desconhecidos(p: Presenca, inicio_feed: str) -> None:
    """O que continuou desconhecido recebe "?"."""
    if p.enviado_em is None:
        p.enviado_por = p.enviado_por or DESCONHECIDO
        p.enviado_em = DESCONHECIDO
    if p.recebido_em is None:
        p.recebido_em = DESCONHECIDO
    if p.desde is None and (not p.passos or p.passos[0].fonte == "feed"):
        p.passos.insert(0, Passo(inicio_feed, DESCONHECIDO, DESCONHECIDO, "", "desconhecido"))
