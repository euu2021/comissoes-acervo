# -*- coding: utf-8 -*-
"""
Conferências da reconstrução:
  A. estado final: as presenças que chegam ao fim do feed batem com o retrato real?
  B. coerência: toda tramitação interna numa comissão acontece durante uma presença
     da matéria naquela comissão?
  C. histórico oficial: numa amostra de matérias, a presença em cada comissão, dia a
     dia, bate com o histórico de movimentações da própria matéria?
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from datetime import date, timedelta

from reconstrucao import fontes
from reconstrucao.eventos import COMISSOES, Evento
from reconstrucao.linha_do_tempo import DESCONHECIDO, Presenca


def estado_final(presencas: dict[str, list[Presenca]], ancoras: dict[str, dict],
                 movimentadas: set[str]) -> dict:
    """A. Para matérias com eventos externos: comissão no fim do feed × retrato real;
    datas de envio e recebimento; e último passo interno, quando veio do feed."""
    cont: Counter = Counter()
    exemplos: dict[str, list] = defaultdict(list)
    for rotulo in set(presencas) | set(ancoras):
        abertas = [p for p in presencas.get(rotulo, []) if p.ate is None]
        prevista = abertas[0] if abertas else None
        real = ancoras.get(rotulo)
        if rotulo in movimentadas:
            ok = (prevista.comissao if prevista else None) == (real["comissao"] if real else None)
            cont["comissão certa" if ok else "comissão errada"] += 1
            if not ok:
                exemplos["comissão"].append((rotulo, prevista and prevista.comissao,
                                             real and real["comissao"]))
        if not (prevista and real and prevista.comissao == real["comissao"]):
            continue
        for campo in ("enviado_em", "recebido_em"):
            valor = getattr(prevista, campo)
            if rotulo in movimentadas and valor not in (None, DESCONHECIDO):
                cont[f"{campo} idêntico"] += valor == real[campo]
                ok = valor[:10] == real[campo][:10]
                cont[f"{campo} mesmo dia" if ok else f"{campo} outro dia"] += 1
                if not ok:
                    exemplos[campo].append((rotulo, valor, real[campo]))
        ultimo = prevista.passos[-1] if prevista.passos else None
        if ultimo and ultimo.fonte == "feed":
            ok = (ultimo.data, ultimo.area, ultimo.passo) == (
                real["interna_data"], real["interna_area"], real["interna_tipo"])
            cont["passo interno certo" if ok else "passo interno errado"] += 1
            if not ok:
                exemplos["passo"].append((rotulo, (ultimo.data, ultimo.area, ultimo.passo),
                                          (real["interna_data"], real["interna_area"],
                                           real["interna_tipo"])))
    return {"cont": cont, "exemplos": exemplos}


def coerencia(eventos: list[Evento], presencas: dict[str, list[Presenca]]) -> dict:
    """B. Tramitação interna em comissão × presença da matéria na comissão, por ano."""
    por_ano: dict[str, Counter] = defaultdict(Counter)
    exemplos = []
    for e in eventos:
        if e.tipo != "interna" or e.comissao not in COMISSOES:
            continue
        dentro = any(p.comissao == e.comissao
                     and (p.desde in (None, DESCONHECIDO) or p.desde <= e.t)
                     and (p.ate is None or e.t < p.ate)
                     for p in presencas.get(e.rotulo, []))
        por_ano[e.t[:4]]["coerentes" if dentro else "incoerentes"] += 1
        if not dentro:
            exemplos.append((e.rotulo, e.t, e.comissao))
    return {"por_ano": dict(sorted(por_ano.items())), "exemplos": exemplos}


def _local_pelo_historico(linhas: list[tuple[str, str, str]], t: str) -> str | None:
    """Destino do último envio até t (a regra do relatório); antes do primeiro envio,
    a área do registro inicial."""
    loc = None
    for i, (ti, acao, _) in enumerate(linhas):
        if ti > t:
            break
        if "/Encaminhado para " in acao:
            loc = acao.split("/Encaminhado para ", 1)[1].strip()
        elif i == 0 and "/" not in acao:
            loc = acao
    return loc


def sortear(presencas: dict[str, list[Presenca]], tamanho: int, semente: int = 2026) -> list[str]:
    candidatas = sorted(presencas)
    return random.Random(semente).sample(candidatas, min(tamanho, len(candidatas)))


def historicos(presencas: dict[str, list[Presenca]], eventos_por_materia: dict[str, list[Evento]],
               ids: dict[str, str], amostra: list[str], inicio: date, fim: date,
               passo_dias: int = 7) -> dict:
    """C. Amostra de matérias que passaram por comissões: presença a cada `passo_dias`
    dias × histórico oficial. Divergência em matéria cujo envio ou recebimento foi
    excluído depois é esperada: o histórico de hoje não mostra mais o que foi desfeito."""
    fontes.baixar_historicos([ids[r] for r in amostra if r in ids])
    dias = [inicio + timedelta(days=i) for i in range(0, (fim - inicio).days + 1, passo_dias)]
    cont: Counter = Counter()
    exemplos = []
    for rotulo in amostra:
        if rotulo not in ids:
            cont["matérias sem id (fora da conta)"] += 1
            continue
        linhas = fontes.historico(ids[rotulo])
        if not linhas:
            cont["matérias sem histórico (fora da conta)"] += 1
            continue
        reescrito = any(e.tipo in ("excl_envio", "excl_receb") for e in eventos_por_materia.get(rotulo, []))
        divergiu = False
        for d in dias:
            t = f"{d}T23:59:59"
            rec = next((p.comissao for p in presencas[rotulo]
                        if (p.desde in (None, DESCONHECIDO) or p.desde <= t)
                        and (p.ate is None or p.ate > t)), None)
            ofi = _local_pelo_historico(linhas, t)
            ofi = ofi if ofi in COMISSOES else None
            if rec == ofi:
                cont["dias iguais"] += 1
            else:
                cont["dias diferentes (registro reescrito)" if reescrito else "dias diferentes"] += 1
                divergiu = True
                if len(exemplos) < 40:
                    exemplos.append((rotulo, str(d), rec, ofi, "reescrito" if reescrito else ""))
        cont["matérias divergentes" if divergiu else "matérias iguais em todos os dias"] += 1
    return {"cont": cont, "exemplos": exemplos, "amostra": len(amostra), "dias": len(dias)}


def saltos(serie: list[dict], quantos: int = 12) -> list[tuple]:
    """Maiores variações de um dia para o outro no total de matérias de cada comissão."""
    por_comissao: dict[str, list] = defaultdict(list)
    for linha in serie:
        if linha["grupo"] == "todas":
            por_comissao[linha["comissao"]].append((linha["data"], int(linha["materias"])))
    variacoes = []
    for comissao, pontos in por_comissao.items():
        for (_, a), (d, b) in zip(pontos, pontos[1:]):
            variacoes.append((abs(b - a), d, comissao, b - a, b))
    return sorted(variacoes, reverse=True)[:quantos]
