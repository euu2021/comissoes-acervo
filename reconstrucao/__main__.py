# -*- coding: utf-8 -*-
"""
Reconstrução retroativa do acervo das Comissões a partir do feed de eventos do SPLEGIS,
ancorada no primeiro retrato real (o da primeira coleta, refeito a partir de
dados/historico.csv). Assim a reconstrução termina onde a série real começa e não muda
quando novas coletas chegam.

O feed só fica completo a partir de 26/10/2018 (antes disso há eventos esparsos).

Uso (da raiz do repositório):
  python -m reconstrucao baixar --inicio 2018-10-26 --fim 2026-10-02
  python -m reconstrucao gerar

`gerar` lê o feed do cache (baixando o que faltar), corrige as falhas conhecidas da
fonte, monta as presenças e os passos internos, completa com o histórico oficial o
que começou antes do feed e grava dados/reconstrucao/, com o relatório de validação.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date

from coletor import config as C
from coletor.util import gravar_csv, ler_csv, log
from reconstrucao import eventos as E
from reconstrucao import fontes
from reconstrucao import linha_do_tempo as L
from reconstrucao import serie as S
from reconstrucao import validacao as V

DIR_SAIDA = C.DIR_DADOS / "reconstrucao"

CAMPOS_PRESENCAS = ["comissao", "rotulo", "materia_id", "desde", "ate", "enviado_por",
                    "enviado_em", "recebido_em", "destino", "motivo_saida"]
CAMPOS_PASSOS = ["comissao", "rotulo", "data", "area", "passo", "comentario", "fonte"]
CAMPOS_MATERIAS = ["rotulo", "materia_id", "tipo", "numero", "ano", "ementa"]
CAMPOS_AUTORIAS = ["rotulo", "ordem", "autor_codigo", "autor"]


def _chave(rotulo: str) -> tuple:
    sigla, resto = rotulo.split(" ", 1)
    numero, ano = resto.split("/")
    return sigla, int(ano), int(numero)


def _primeiro_retrato() -> tuple[str, str, list[dict]]:
    """(dia, instante da coleta, linhas do acervo) da primeira coleta real."""
    coletas = ler_csv(C.ARQ_COLETAS)
    dia = min(c["data"] for c in coletas)
    instante = next(c["coletado_em"] for c in coletas if c["data"] == dia)[:19]
    acervo = [h for h in ler_csv(C.ARQ_HISTORICO)
              if h["desde"] <= dia and (not h["ate"] or dia <= h["ate"])]
    return dia, instante, acervo


def gerar(inicio: date, serie_desde: date, amostra: int) -> int:
    dia_ancora, t_ancora, acervo = _primeiro_retrato()
    fim = date.fromisoformat(dia_ancora)
    inicio_feed = f"{inicio}T00:00:00"
    log(f"Retrato-âncora: {dia_ancora} (coletado em {t_ancora}); eventos a partir de {inicio}")

    fim_eventos = date.fromisoformat(t_ancora[:10])  # a coleta pode ter sido na madrugada seguinte
    fontes.baixar_eventos(inicio, fim_eventos)
    eventos, fichas = E.carregar(inicio, fim_eventos, t_ancora)
    log(f"{len(eventos)} eventos: {dict(Counter(e.tipo for e in eventos))}")

    catalogo_real = {m["rotulo"]: m for m in ler_csv(C.ARQ_MATERIAS)}
    ids = {r: m["materia_id"] for r, m in catalogo_real.items()}
    ids.update({r: i for r, i in fontes.ids_em_cache().items() if i})
    eventos, correcoes_cont, correcoes = E.corrigir(eventos, fichas, ids, inicio_feed)
    log(f"Correções: {dict(correcoes_cont)}")
    ids.update({r: i for r, i in fontes.ids_em_cache().items() if i})

    grupos = E.por_materia(eventos)
    ancoras = {r["rotulo"]: r for r in acervo}
    presencas: dict[str, list[L.Presenca]] = {}
    anomalias: Counter = Counter()
    movimentadas = set()
    for rotulo in sorted(set(grupos) | set(ancoras)):
        if rotulo.split()[0] not in E.TIPOS_DO_RELATORIO:
            continue
        evs = grupos.get(rotulo, [])
        externos = [e for e in evs if e.tipo in E.EXTERNOS]
        if externos:
            movimentadas.add(rotulo)
        lista, anom = L.trechos(externos, ancoras.get(rotulo))
        anomalias.update(a.split(" ", 2)[1] for a in anom)
        ps = L.presencas(rotulo, lista, [e for e in evs if e.tipo in ("interna", "excl_interna")],
                         ancoras.get(rotulo), inicio_feed)
        if ps:
            presencas[rotulo] = ps
    todas = [p for ps in presencas.values() for p in ps]
    log(f"{len(presencas)} matérias passaram por comissões; {len(todas)} presenças")

    # Presenças que começaram antes do feed: completa com o histórico oficial.
    precisam = [p for p in todas if L.precisa_do_historico(p)]
    sem_id = {p.rotulo: (fichas[p.rotulo].tipo_cod, fichas[p.rotulo].numero, fichas[p.rotulo].ano)
              for p in precisam if p.rotulo not in ids and p.rotulo in fichas}
    ids.update(fontes.buscar_ids(sem_id))
    fontes.baixar_historicos([ids[p.rotulo] for p in precisam if p.rotulo in ids])
    completadas = Counter()
    for p in precisam:
        ok = p.rotulo in ids and L.completar_com_historico(p, fontes.historico(ids[p.rotulo]), inicio_feed)
        completadas["completadas" if ok else "não completadas"] += 1
    for p in todas:
        L.marcar_desconhecidos(p, inicio_feed)
    log(f"Presenças anteriores ao feed: {dict(completadas)}")

    # Arquivos.
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    ordem = sorted(todas, key=lambda p: (_chave(p.rotulo), p.desde or ""))
    gravar_csv(DIR_SAIDA / "presencas.csv", CAMPOS_PRESENCAS, [{
        "comissao": p.comissao, "rotulo": p.rotulo, "materia_id": ids.get(p.rotulo, ""),
        "desde": p.desde or (p.enviado_em if p.enviado_em != L.DESCONHECIDO else L.DESCONHECIDO),
        "ate": p.ate or "", "enviado_por": p.enviado_por or "",
        "enviado_em": p.enviado_em, "recebido_em": p.recebido_em, "destino": p.destino or "",
        "motivo_saida": p.motivo_saida or "",
    } for p in ordem])
    gravar_csv(DIR_SAIDA / "passos_internos.csv", CAMPOS_PASSOS, [{
        "comissao": p.comissao, "rotulo": p.rotulo, "data": x.data, "area": x.area,
        "passo": x.passo, "comentario": x.comentario, "fonte": x.fonte,
    } for p in ordem for x in p.passos])
    materias, autorias = [], []
    for rotulo in sorted(presencas, key=_chave):
        ficha, real = fichas.get(rotulo), catalogo_real.get(rotulo)
        sigla, ano, numero = _chave(rotulo)
        materias.append({"rotulo": rotulo, "materia_id": ids.get(rotulo, ""), "tipo": sigla,
                         "numero": str(numero), "ano": str(ano),
                         "ementa": (real["ementa"] if real else "") or (ficha.ementa if ficha else "")})
        if ficha:
            autorias += [{"rotulo": rotulo, "ordem": str(i), "autor_codigo": str(a.get("Chave", "")),
                          "autor": (a.get("Nome") or "").strip()}
                         for i, a in enumerate(ficha.autores, 1)]
    gravar_csv(DIR_SAIDA / "materias.csv", CAMPOS_MATERIAS, materias)
    gravar_csv(DIR_SAIDA / "autorias.csv", CAMPOS_AUTORIAS, autorias)

    log("Calculando a série diária...")
    serie = S.calcular(todas, serie_desde, fim)
    gravar_csv(DIR_SAIDA / "serie.csv", S.CAMPOS, serie)

    # Validação.
    log("Validando...")
    final = V.estado_final(presencas, ancoras, movimentadas)
    coer = V.coerencia(eventos, presencas)
    sorteadas = V.sortear(presencas, amostra)
    ids.update(fontes.buscar_ids({r: (fichas[r].tipo_cod, fichas[r].numero, fichas[r].ano)
                                  for r in sorteadas if r not in ids and r in fichas}))
    hist = V.historicos(presencas, grupos, ids, sorteadas, serie_desde, fim)
    relatorio = _relatorio(t_ancora, inicio, serie_desde, fim, eventos, correcoes_cont, correcoes, anomalias,
                           presencas, todas, completadas, serie, final, coer, hist)
    (DIR_SAIDA / "validacao.md").write_text(relatorio, encoding="utf-8", newline="\n")
    print(relatorio, flush=True)
    return 0


def _pct(bons: int, total: int) -> str:
    return f"{bons:,}/{total:,} ({100 * bons / total:.2f}%)".replace(",", ".") if total else "—"


def _relatorio(t_ancora, inicio, serie_desde, fim, eventos, correcoes_cont, correcoes, anomalias, presencas,
               todas, completadas, serie, final, coer, hist) -> str:
    f, h = final["cont"], hist["cont"]
    tipos = Counter(e.tipo for e in eventos)
    desconhecidas = Counter()
    for linha in serie:
        if linha["grupo"] == "todas" and linha["comissao"] != S.TODAS:
            ano = linha["data"][:4]
            desconhecidas[(ano, "materias")] += int(linha["materias"])
            desconhecidas[(ano, "idade")] += int(linha["idade_desconhecida"])
            desconhecidas[(ano, "passo")] += int(linha["passo_desconhecido"])
    anos = sorted({a for a, _ in desconhecidas})
    coer_total = Counter()
    for c in coer["por_ano"].values():
        coer_total.update(c)
    linhas = [
        "# Validação da reconstrução", "",
        f"- Eventos de {inicio} a {fim}; série de {serie_desde} a {fim}; retrato-âncora de {t_ancora}.",
        f"- Eventos do feed: {len(eventos):,} ({', '.join(f'{k} {v:,}' for k, v in tipos.most_common())}).".replace(",", "."),
        f"- Matérias que passaram por comissões: {len(presencas):,}; presenças: {len(todas):,}.".replace(",", "."),
        f"- Correções na fonte: {dict(correcoes_cont)}.",
        f"- Incoerências na sequência de eventos externos (quase todas fora das comissões): {dict(anomalias)}.",
        f"- Presenças iniciadas antes do feed, completadas com o histórico oficial: {dict(completadas)}.", "",
        "## A. Estado final × retrato real", "",
        f"- Comissão onde a matéria está: {_pct(f['comissão certa'], f['comissão certa'] + f['comissão errada'])}",
        f"- Data de envio à comissão, mesmo dia: {_pct(f['enviado_em mesmo dia'], f['enviado_em mesmo dia'] + f['enviado_em outro dia'])}"
        f" ({f['enviado_em idêntico']:,} idênticas até o segundo)".replace(",", "."),
        f"- Data de recebimento, mesmo dia: {_pct(f['recebido_em mesmo dia'], f['recebido_em mesmo dia'] + f['recebido_em outro dia'])}"
        f" ({f['recebido_em idêntico']:,} idênticas até o segundo)".replace(",", "."),
        f"- Último passo interno: {_pct(f['passo interno certo'], f['passo interno certo'] + f['passo interno errado'])}", "",
        "## B. Coerência: tramitação interna acontece durante uma presença na comissão", "",
        f"- Total: {_pct(coer_total['coerentes'], coer_total['coerentes'] + coer_total['incoerentes'])}",
    ]
    for ano, c in coer["por_ano"].items():
        linhas.append(f"  - {ano}: {_pct(c['coerentes'], c['coerentes'] + c['incoerentes'])}")
    iguais = h["dias iguais"]
    linhas += [
        "", f"## C. Presença × histórico oficial ({hist['amostra']} matérias sorteadas, {hist['dias']} dias, de 7 em 7)", "",
        f"- Dias iguais: {_pct(iguais, iguais + h['dias diferentes'] + h['dias diferentes (registro reescrito)'])}",
        f"- Dias diferentes em matérias cujo envio ou recebimento foi excluído depois (o histórico de hoje não mostra mais o que foi desfeito): {h['dias diferentes (registro reescrito)']}",
        f"- Dias diferentes sem explicação: {h['dias diferentes']}",
        f"- {dict(h)}", "",
        "## Dados desconhecidos (matéria-dias com idade ou passo interno marcados \"?\")", "",
    ]
    for ano in anos:
        m = desconhecidas[(ano, "materias")]
        linhas.append(f"- {ano}: idade {100 * desconhecidas[(ano, 'idade')] / m:.1f}%,"
                      f" passo interno {100 * desconhecidas[(ano, 'passo')] / m:.1f}%")
    linhas += ["", "## Maiores variações diárias (todas as matérias)", ""]
    for _, d, comissao, delta, total in V.saltos(serie):
        linhas.append(f"- {d} {comissao}: {delta:+d} (ficou em {total})")
    linhas += ["", "## Exemplos", ""]
    for nome, lista in [("A/comissão", final["exemplos"]["comissão"]),
                        ("A/envio", final["exemplos"]["enviado_em"]),
                        ("A/recebimento", final["exemplos"]["recebido_em"]),
                        ("A/passo", final["exemplos"]["passo"]),
                        ("B", coer["exemplos"]), ("C", hist["exemplos"]),
                        ("correções", correcoes)]:
        for ex in lista[:10]:
            linhas.append(f"- {nome}: {ex}")
    return "\n".join(linhas) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m reconstrucao")
    sub = ap.add_subparsers(dest="comando", required=True)
    b = sub.add_parser("baixar", help="baixa (com cache) o feed diário de eventos")
    b.add_argument("--inicio", type=date.fromisoformat, required=True)
    b.add_argument("--fim", type=date.fromisoformat, required=True)
    g = sub.add_parser("gerar", help="reconstrói o acervo e grava dados/reconstrucao/")
    g.add_argument("--inicio", type=date.fromisoformat, default=date(2018, 10, 26),
                   help="primeiro dia de eventos usado (o feed fica completo em 26/10/2018)")
    g.add_argument("--serie-desde", type=date.fromisoformat, default=date(2018, 11, 1),
                   help="primeiro dia da série diária")
    g.add_argument("--amostra", type=int, default=500,
                   help="matérias sorteadas para conferir contra o histórico oficial")
    args = ap.parse_args(argv)

    if args.comando == "baixar":
        fontes.baixar_eventos(args.inicio, args.fim)
        return 0
    return gerar(args.inicio, args.serie_desde, args.amostra)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
