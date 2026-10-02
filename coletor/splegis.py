# -*- coding: utf-8 -*-
"""
Acesso ao relatório "Projetos em Análise nas Comissões" do SPLEGIS.

O relatório é uma tabela DataTables alimentada por um endpoint JSON público;
pedimos todos os tipos de matéria (o filtro de tipo fica para quem consome os dados).
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime

from coletor import config as C
from coletor.util import log

# ----------------------------------------------------------------------------- HTTP


def _get_json(params: dict) -> dict:
    url = C.URL_RELATORIO + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": C.USER_AGENT,
                                               "Accept": "application/json"})
    for tentativa in range(1, C.TENTATIVAS + 1):
        try:
            with urllib.request.urlopen(req, timeout=C.TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8"))
        # URLError, HTTPError e timeout são OSError; JSON truncado é ValueError.
        except (OSError, ValueError) as e:
            if tentativa == C.TENTATIVAS:
                raise
            espera = 15 * 2 ** (tentativa - 1)
            log(f"  falha na tentativa {tentativa} ({e}); nova tentativa em {espera} s")
            time.sleep(espera)
    raise AssertionError("inalcançável")


def baixar_comissao(cod_depto: int) -> list[dict]:
    """Todas as matérias em análise na comissão, de todos os tipos."""
    registros: list[dict] = []
    vistos: set = set()
    inicio = 0
    while True:
        resp = _get_json({
            "draw": 1, "start": inicio, "length": C.TAMANHO_PAGINA,
            "depto": cod_depto, "tipos": "", "numero": 0, "ano": 0,
            "autor": 0, "relator": 0, "interna": 0, "recebido": 0, "inconsistencia": 0,
        })
        pagina, total = resp["data"], resp["recordsFiltered"]
        for r in pagina:
            if r["id"] not in vistos:
                vistos.add(r["id"])
                registros.append(r)
        inicio += len(pagina)
        if not pagina or inicio >= total:
            break
    if len(registros) != total:
        raise RuntimeError(f"depto {cod_depto}: o SPLEGIS anunciou {total} matérias "
                           f"mas entregou {len(registros)}")
    return registros


# ----------------------------------------------------------------------------- normalização
_RX_ROTULO = re.compile(r"^(\S+) (\d+)/(\d{4})$")
_FORMATOS_DATA = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y")


def _texto(valor) -> str:
    if valor is None:
        return ""
    return str(valor).replace("\r\n", "\n").replace("\r", "\n").strip()


def _data(valor) -> str:
    """'24/08/2026 15:43:00' -> '2026-08-24T15:43:00' (horário de Brasília, sem offset).
    Formato desconhecido é mantido como veio, para não perder a informação."""
    s = _texto(valor)
    if not s:
        return ""
    for fmt in _FORMATOS_DATA:
        try:
            return datetime.strptime(s, fmt).isoformat()
        except ValueError:
            pass
    log(f"  aviso: data em formato inesperado mantida como veio: {s!r}")
    return s


def normalizar(reg: dict, comissao: str) -> tuple[dict, dict, list[dict]]:
    """Um registro do relatório -> (linha do acervo, linha de matéria, autorias)."""
    externa = reg.get("tramitacaoExterna") or {}
    envio = externa.get("envio") or {}
    recebimento = externa.get("recebimento") or {}
    interna = reg.get("tramitacaoInterna") or {}
    relator = reg.get("relator") or {}
    materia_id = str(reg["id"])

    area = _texto(recebimento.get("area"))
    if area and area != comissao:
        log(f"  aviso: {reg.get('rotulo')} listado na {comissao} mas recebido por {area}")

    linha = {
        "comissao": comissao,
        "materia_id": materia_id,
        "rotulo": _texto(reg.get("rotulo")),
        "relator_codigo": _texto(relator.get("codigo")),
        "relator": _texto(relator.get("texto")),
        "enviado_por": _texto(envio.get("area")),
        "enviado_em": _data(envio.get("data")),
        "recebido_em": _data(recebimento.get("data")),
        "interna_data": _data(interna.get("data")),
        "interna_area": _texto(interna.get("area")),
        "interna_tipo": _texto(interna.get("tipo")),
        "interna_comentario": _texto(interna.get("comentario")),
        # Resumo textual do SPLEGIS (hora em 12h, sem AM/PM). Só acrescenta informação
        # quando os campos da tramitação interna vêm vazios; nos demais casos é redundante.
        "ultima_interna": "" if interna.get("data") else _texto(reg.get("ultimaInterna")),
    }

    m = _RX_ROTULO.match(linha["rotulo"])
    materia = {
        "materia_id": materia_id,
        "rotulo": linha["rotulo"],
        "tipo": m.group(1) if m else "",
        "numero": m.group(2) if m else "",
        "ano": m.group(3) if m else "",
        "ementa": _texto(reg.get("ementa")),
    }

    autores = reg.get("autor") or []
    if isinstance(autores, str):  # o front do SPLEGIS prevê autor como texto simples
        autores = [{"texto": autores}]
    autorias = [{
        "materia_id": materia_id,
        "ordem": str(i),
        "autor_codigo": _texto(a.get("codigo")),
        "autor": _texto(a.get("texto")),
        "classe": _texto(a.get("classe")),
    } for i, a in enumerate(autores, 1)]

    return linha, materia, autorias
