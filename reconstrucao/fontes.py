# -*- coding: utf-8 -*-
"""
Downloads do SPLEGIS com cache em disco (reconstrucao/cache/, fora do git).

- feed diário de eventos de tramitação (MateriasEventosJSON), com dados desde nov/2018;
- histórico de movimentações de uma matéria (Pesquisa/HistoricoMovimentacoes), o registro
  oficial de hoje, usado para conferir eventos suspeitos e completar estadas antigas;
- id interno de uma matéria a partir de tipo/número/ano.
"""
from __future__ import annotations

import html
import json
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

from coletor import config as C
from coletor.util import log

CACHE = Path(__file__).resolve().parent / "cache"

URL_EVENTOS = ("https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx/"
               "MateriasEventosJSON?dataPesquisa={}")
URL_DETALHE = ("https://splegisconsulta.saopaulo.sp.leg.br/Pesquisa/"
               "DetailsMateriaTramitacaoLegislativa?tipo={}&numero={}&ano={}")
URL_HISTORICO = ("https://splegisconsulta.saopaulo.sp.leg.br/Pesquisa/"
                 "HistoricoMovimentacoes?id={}")

PARALELOS = 3  # requisições simultâneas; o feed leva ~2,5 s por dia


def baixar(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": C.USER_AGENT})
    for tentativa in range(1, C.TENTATIVAS + 1):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                texto = r.read().decode("utf-8")
            time.sleep(0.2)  # cortesia com o servidor
            return texto
        except OSError as e:
            if tentativa == C.TENTATIVAS:
                raise
            espera = 15 * 2 ** (tentativa - 1)
            log(f"  falha em {url[-60:]} ({e}); nova tentativa em {espera} s")
            time.sleep(espera)
    raise AssertionError("inalcançável")


def baixar_json(url: str) -> str:
    """Como `baixar`, mas confere que a resposta é JSON: às vezes o SPLEGIS devolve a
    página "Erro em execução" com status 200, e ela não pode ir para o cache."""
    for tentativa in range(1, C.TENTATIVAS + 1):
        texto = baixar(url)
        try:
            json.loads(texto)
            return texto
        except ValueError:
            if tentativa == C.TENTATIVAS:
                raise
            log(f"  resposta não é JSON em {url[-60:]}; nova tentativa em {10 * tentativa} s")
            time.sleep(10 * tentativa)
    raise AssertionError("inalcançável")


def _gravar(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(caminho.name + ".tmp")
    tmp.write_text(texto, encoding="utf-8", newline="\n")
    tmp.replace(caminho)


def _em_paralelo(funcao, itens: list, rotulo: str) -> None:
    with ThreadPoolExecutor(PARALELOS) as ex:
        for i, _ in enumerate(ex.map(funcao, itens), 1):
            if i % 200 == 0 or i == len(itens):
                log(f"  {rotulo}: {i}/{len(itens)}")


# ----------------------------------------------------------------------------- feed diário
def _arq_eventos(d: date) -> Path:
    return CACHE / "eventos" / str(d.year) / f"{d}.json"


def eventos_do_dia(d: date) -> list[dict]:
    caminho = _arq_eventos(d)
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    texto = baixar_json(URL_EVENTOS.format(d))
    if d < datetime.now(C.FUSO).date():  # o dia corrente ainda vai ganhar eventos
        _gravar(caminho, texto)
    return json.loads(texto)


def baixar_eventos(inicio: date, fim: date) -> None:
    dias = [inicio + timedelta(days=i) for i in range((fim - inicio).days + 1)]
    faltando = [d for d in dias if not _arq_eventos(d).exists()]
    log(f"Feed de eventos: {len(dias) - len(faltando)} dias em cache, {len(faltando)} a baixar")
    _em_paralelo(eventos_do_dia, faltando, "dias")


# ----------------------------------------------------------------------------- histórico por matéria
def _arq_historico(materia_id: str) -> Path:
    return CACHE / "historico" / f"{materia_id}.json"


def historico(materia_id: str) -> list[tuple[str, str, str]]:
    """Linhas (data, área/ação, observação) do histórico, em ordem cronológica.

    Ações: "X/Encaminhado para Y" (envio), "Y/Recebido" ou só "Y" (recebimento ou
    registro inicial) e "C/Área/Passo" (tramitação interna)."""
    caminho = _arq_historico(materia_id)
    if caminho.exists():
        texto = caminho.read_text(encoding="utf-8")
    else:
        texto = baixar_json(URL_HISTORICO.format(materia_id))
        _gravar(caminho, texto)
    linhas = []
    for row in reversed(json.loads(texto)["data"]):  # a fonte vem do mais novo ao mais antigo
        cel = [html.unescape(re.sub(r"<[^>]+>", "", html.unescape(c))).replace("\r\n", "\n").strip()
               if isinstance(c, str) else "" for c in row]
        linhas.append((cel[0][:19], cel[1], cel[3]))
    linhas.sort(key=lambda l: l[0])
    return linhas


def baixar_historicos(ids: list[str]) -> None:
    faltando = sorted({i for i in ids if not _arq_historico(i).exists()})
    if faltando:
        log(f"Históricos de matérias: {len(faltando)} a baixar")
        _em_paralelo(historico, faltando, "históricos")


# ----------------------------------------------------------------------------- id das matérias
_RX_ID = re.compile(r"GerarArquivoProcessoPorID/(\d+)|id: '(\d+)'")
_ARQ_IDS = CACHE / "ids.json"
_trava_ids = threading.Lock()


def ids_em_cache() -> dict[str, str]:
    return json.loads(_ARQ_IDS.read_text(encoding="utf-8")) if _ARQ_IDS.exists() else {}


def buscar_ids(chaves: dict[str, tuple]) -> dict[str, str]:
    """{rótulo: id} para os rótulos pedidos; `chaves` dá o (tipo, número, ano) de cada um."""
    ids = ids_em_cache()
    faltando = [r for r in chaves if r not in ids]

    def buscar(rotulo: str) -> None:
        m = _RX_ID.search(baixar(URL_DETALHE.format(*chaves[rotulo])))
        with _trava_ids:
            ids[rotulo] = (m[1] or m[2]) if m else ""

    if faltando:
        log(f"Ids de matérias: {len(faltando)} a buscar")
        _em_paralelo(buscar, faltando, "ids")
        _gravar(_ARQ_IDS, json.dumps(ids, ensure_ascii=False, sort_keys=True, indent=0))
    return {r: ids[r] for r in chaves if ids.get(r)}
