# -*- coding: utf-8 -*-
"""Testes da reconstrução que não dependem de rede."""
import unittest
from datetime import date

from reconstrucao.eventos import Evento, interpretar, recebimentos_suspeitos
from reconstrucao.linha_do_tempo import (DESCONHECIDO, Passo, Presenca, completar_com_historico,
                                         marcar_desconhecidos, presencas, trechos)
from reconstrucao.serie import calcular, categoria, etapa


def ev(t, rotulo="PL 1/2026", **kw):
    return Evento(t=t, ordem=0, rotulo=rotulo, **kw)


class TestInterpretar(unittest.TestCase):

    def test_envio_com_motivo_e_area_com_ponto(self):
        self.assertEqual(
            interpretar("Matéria DOCREC 1/2016: tramitada da área FIN para a área LIDER. PT.  Obs: x."),
            {"tipo": "envio", "de": "FIN", "para": "LIDER. PT", "motivo": "Obs: x."})

    def test_recebimento(self):
        self.assertEqual(interpretar("Matéria PL 1/2026: recebida na área CCJ (enviada da área PROC-CMSP)."),
                         {"tipo": "receb", "para": "CCJ", "de": "PROC-CMSP"})

    def test_exclusoes(self):
        self.assertEqual(interpretar("Matéria PL 1/2026: excluída tramitação da área SGP22 para a área FIN."),
                         {"tipo": "excl_envio", "de": "SGP22", "para": "FIN"})
        self.assertEqual(interpretar("Matéria PL 1/2026: excluído recebimento na área FIN."),
                         {"tipo": "excl_receb", "para": "FIN"})

    def test_interna_com_e_sem_comentario(self):
        a = interpretar("Matéria PL 1/2026: tramitação interna - CCJ/Secretaria (SGP12)/Em Condição de Pauta - PRAZO VENCIDO.")
        self.assertEqual((a["comissao"], a["area"], a["passo"], a["comentario"]),
                         ("CCJ", "Secretaria (SGP12)", "Em Condição de Pauta", "PRAZO VENCIDO."))
        b = interpretar("Matéria PR 83/2025: tramitação interna - CCJ/Secretaria (SGP12)/Aguardando Informações do(a) Autor(a) - ")
        self.assertEqual((b["passo"], b["comentario"]), ("Aguardando Informações do(a) Autor(a)", ""))

    def test_vazio_e_outro(self):
        self.assertEqual(interpretar("Matéria PL 502/2026: ")["tipo"], "outro")


class TestLinhaDoTempo(unittest.TestCase):

    def test_passagem_por_duas_comissoes(self):
        externos = [ev("2026-08-01T10:00:00", tipo="envio", de="PROC-CMSP", para="CCJ"),
                    ev("2026-08-02T10:00:00", tipo="receb", de="PROC-CMSP", para="CCJ"),
                    ev("2026-08-20T10:00:00", tipo="envio", de="CCJ", para="SAUDE",
                       motivo="Motivo: A pedido. Obs: Aprovado em Reunião Conjunta."),
                    ev("2026-08-24T10:00:00", tipo="receb", de="CCJ", para="SAUDE")]
        internas = [ev("2026-08-02T10:00:00", tipo="interna", comissao="CCJ", area="Presidente da Comissão",
                       passo="Designar Relator")]
        lista, anomalias = trechos(externos, None)
        self.assertEqual(anomalias, [])
        ps = presencas("PL 1/2026", lista, internas, None, "2026-07-01T00:00:00")
        self.assertEqual([(p.comissao, p.desde, p.ate, p.recebido_em, p.destino) for p in ps], [
            ("CCJ", "2026-08-01T10:00:00", "2026-08-20T10:00:00", "2026-08-02T10:00:00", "SAUDE"),
            ("SAUDE", "2026-08-20T10:00:00", None, "2026-08-24T10:00:00", None)])
        self.assertEqual([x.fonte for x in ps[0].passos], ["chegada", "feed"])
        self.assertEqual([p.motivo_saida for p in ps], ["Motivo: A pedido. Obs: Aprovado em Reunião Conjunta.", None])

    def test_recebimento_tardio_nao_move_a_materia(self):
        # DOCREC arquivado em 2011 cujo envio antigo à FIN foi "recebido" em 2019.
        externos = [ev("2019-09-05T10:13:00", rotulo="DOCREC 1517/2011", tipo="receb", de="SGP22", para="FIN")]
        lista, _ = trechos(externos, None)
        self.assertEqual(presencas("DOCREC 1517/2011", lista, [], None, "2018-10-26T00:00:00"), [])

    def test_envio_que_faltou_no_feed(self):
        externos = [ev("2019-05-01T10:00:00", tipo="envio", de="CCJ", para="SGP21"),
                    ev("2020-01-10T10:00:00", tipo="receb", de="SGP21", para="URB"),
                    ev("2020-03-01T10:00:00", tipo="envio", de="URB", para="SGP21")]
        lista, anomalias = trechos(externos, None)
        ps = presencas("PL 1/2019", lista, [], None, "2018-10-26T00:00:00")
        self.assertEqual([(p.comissao, p.desde, p.ate) for p in ps], [
            ("CCJ", None, "2019-05-01T10:00:00"),
            ("URB", "2020-01-10T10:00:00", "2020-03-01T10:00:00")])
        self.assertEqual(len(anomalias), 2)

    def test_exclusoes_desfazem_os_envios_em_ordem(self):
        # PL 1435/2025: ida e volta à SGP12 desfeitas; a estada original na CCJ continua.
        externos = [ev("2025-11-27T18:45:00", tipo="envio", de="PROC-CMSP", para="CCJ"),
                    ev("2025-12-02T11:10:00", tipo="receb", de="PROC-CMSP", para="CCJ"),
                    ev("2026-03-13T15:12:00", tipo="envio", de="CCJ", para="SGP12"),
                    ev("2026-03-13T15:13:00", tipo="envio", de="SGP12", para="CCJ"),
                    ev("2026-03-13T15:14:22", tipo="excl_envio", de="SGP12", para="CCJ"),
                    ev("2026-03-13T15:14:33", tipo="excl_envio", de="CCJ", para="SGP12")]
        lista, _ = trechos(externos, None)
        ps = presencas("PL 1435/2025", lista, [], None, "2018-10-26T00:00:00")
        self.assertEqual((ps[-1].comissao, ps[-1].ate, ps[-1].enviado_em, ps[-1].recebido_em),
                         ("CCJ", None, "2025-11-27T18:45:00", "2025-12-02T11:10:00"))

    def test_excluir_envio_duplicado_nao_devolve(self):
        # PL 185/2020: dois envios ao ARQUIVO; excluir o segundo mantém a matéria lá.
        externos = [ev("2021-02-25T12:12:00", tipo="envio", de="SGP22", para="CCJ"),
                    ev("2021-07-05T19:00:00", tipo="envio", de="CCJ", para="ARQUIVO"),
                    ev("2021-07-05T20:19:00", tipo="envio", de="CCJ", para="ARQUIVO"),
                    ev("2021-07-05T22:10:17", tipo="excl_envio", de="CCJ", para="ARQUIVO")]
        lista, _ = trechos(externos, None)
        ps = presencas("PL 185/2020", lista, [], None, "2018-10-26T00:00:00")
        self.assertEqual([(p.comissao, p.desde, p.ate) for p in ps],
                         [("CCJ", "2021-02-25T12:12:00", "2021-07-05T19:00:00")])

    def test_historico_completa_estada_anterior_ao_feed(self):
        p = Presenca("FIN", "DOCREC 15/2012", None, "2026-08-10T10:00:00", None, None, None, "ver. X", [])
        linhas = [("2012-01-05T16:05:38", "SGP22/Encaminhado para FIN", ""),
                  ("2019-09-05T10:13:00", "FIN/Recebido", "")]
        self.assertTrue(completar_com_historico(p, linhas, "2018-10-26T00:00:00"))
        self.assertEqual((p.desde, p.enviado_por, p.recebido_em, p.passos[0].fonte),
                         ("2012-01-05T16:05:38", "SGP22", "2019-09-05T10:13:00", "historico"))

    def test_historico_mostra_registro_feito_ja_na_comissao(self):
        # RSC 5/2019: registrada na CCJ e arquivada no mesmo segundo, em 2020.
        p = Presenca("CCJ", "RSC 5/2019", None, "2020-02-06T17:44:00", None, None, None, "ARQUIVO", [])
        linhas = [("2020-02-06T17:44:00", "CCJ", ""),
                  ("2020-02-06T17:44:00", "CCJ/Encaminhado para ARQUIVO", "")]
        self.assertTrue(completar_com_historico(p, linhas, "2018-10-26T00:00:00"))
        self.assertEqual((p.desde, p.enviado_por), ("2020-02-06T17:44:00", ""))

    def test_passo_excluido_devolve_o_anterior(self):
        externos = [ev("2019-03-01T10:00:00", tipo="envio", de="SGP22", para="ADM")]
        internas = [ev("2019-03-02T10:00:00", tipo="interna", comissao="ADM", area="Relator", passo="Para Relatar"),
                    ev("2019-03-05T10:00:00", tipo="interna", comissao="ADM", area="Secretaria", passo="Deliberado"),
                    ev("2019-03-05T10:05:00", tipo="excl_interna", comissao="ADM", area="Secretaria",
                       passo="Deliberado")]
        lista, _ = trechos(externos, None)
        ps = presencas("PL 1/2019", lista, internas, None, "2018-10-26T00:00:00")
        self.assertEqual([(x.data, x.area, x.fonte) for x in ps[0].passos], [
            ("2019-03-01T10:00:00", "", "chegada"),
            ("2019-03-02T10:00:00", "Relator", "feed"),
            ("2019-03-05T10:00:00", "Secretaria", "feed"),
            ("2019-03-05T10:05:00", "Relator", "exclusao")])

    def test_envio_desfeito_devolve_a_materia(self):
        externos = [ev("2026-08-01T10:00:00", tipo="excl_receb", para="FIN"),
                    ev("2026-08-01T10:01:00", tipo="excl_envio", de="SGP22", para="FIN")]
        lista, _ = trechos(externos, None)
        ps = presencas("DOCREC 1/2016", lista, [], None, "2026-07-01T00:00:00")
        self.assertEqual([(p.comissao, p.desde, p.ate, p.destino, p.motivo_saida) for p in ps],
                         [("FIN", None, "2026-08-01T10:01:00", "SGP22", "")])

    def test_parada_desde_antes_usa_o_retrato(self):
        ancora = {"comissao": "ADM", "enviado_por": "ATM", "enviado_em": "1992-09-17T12:18:00",
                  "recebido_em": "1992-09-18T15:00:00", "interna_data": "", "interna_area": "",
                  "interna_tipo": "", "interna_comentario": ""}
        lista, _ = trechos([], ancora)
        ps = presencas("DOCREC 361/1992", lista, [], ancora, "2018-10-26T00:00:00")
        self.assertEqual((ps[0].comissao, ps[0].desde, ps[0].ate, ps[0].recebido_em),
                         ("ADM", None, None, "1992-09-18T15:00:00"))
        self.assertEqual(ps[0].passos[0].fonte, "retrato")

    def test_desconhecidos_recebem_interrogacao(self):
        lista, _ = trechos([ev("2026-08-05T10:00:00", tipo="envio", de="CCJ", para="FIN")], None)
        ps = presencas("PL 1/2026", lista, [], None, "2026-08-01T00:00:00")
        marcar_desconhecidos(ps[0], "2026-08-01T00:00:00")
        self.assertEqual((ps[0].comissao, ps[0].enviado_em, ps[0].recebido_em, ps[0].passos[0].area),
                         ("CCJ", DESCONHECIDO, DESCONHECIDO, DESCONHECIDO))

    def test_recebimento_depois_de_tramitacao_interna_e_suspeito(self):
        eventos = [ev("2026-04-06T17:48:00", tipo="envio", de="SGP22", para="CCJ"),
                   ev("2026-08-20T15:59:56", tipo="interna", comissao="CCJ", area="Relator(a)", passo="x"),
                   ev("2026-09-04T15:08:00", tipo="receb", de="SGP22", para="CCJ")]
        self.assertEqual([e.t for e in recebimentos_suspeitos(eventos)], ["2026-09-04T15:08:00"])

    def test_passo_interno_antes_do_recebimento_e_comum(self):
        eventos = [ev("2026-04-06T17:48:00", tipo="envio", de="SGP22", para="CCJ"),
                   ev("2026-04-07T10:00:00", tipo="interna", comissao="CCJ", area="Procuradoria", passo="x"),
                   ev("2026-04-20T15:08:00", tipo="receb", de="SGP22", para="CCJ")]
        self.assertEqual(recebimentos_suspeitos(eventos), [])


class TestSerie(unittest.TestCase):

    def test_categorias(self):
        self.assertEqual(categoria("Secretaria (SGP.12)"), "passo_secretaria")
        self.assertEqual(categoria("Relator(a)"), "passo_relator")
        self.assertEqual(categoria(""), "passo_nenhum")
        self.assertEqual(categoria(DESCONHECIDO), "passo_desconhecido")

    def test_etapas(self):
        casos = {("", ""): "etapa_sem_relator",
                 ("Presidente da Comissão", "Redesignar Relator"): "etapa_sem_relator",
                 ("Secretaria", "Aguardando Designação de Relator"): "etapa_sem_relator",
                 ("Procuradoria", "Para análise e envio ao(à) relator(a)"): "etapa_estudo",
                 ("Consultoria (SGP.52)", "Elaborar Minuta de Relatório"): "etapa_estudo",
                 ("Relator(a)", "Assinar Pedido de Informação ao Executivo"): "etapa_diligencia",
                 ("Secretaria (SGP12)", "Aguardando 2ª Audiência Pública"): "etapa_diligencia",
                 ("Secretaria (SGP12)", "Em Condição de Pauta"): "etapa_pauta",
                 ("Comissão", "Vistas"): "etapa_pauta",
                 ("Secretaria", "Aguardando Publicação do Parecer"): "etapa_votado",
                 ("Secretaria", "Aguardando Requerimento de Retirada"): "etapa_outra",
                 (DESCONHECIDO, DESCONHECIDO): None}
        for (area, passo), esperado in casos.items():
            self.assertEqual(etapa(area, passo), esperado, (area, passo))

    def test_idade_e_pendencia(self):
        p = Presenca("CCJ", "PL 1/2026", "2026-08-01T10:00:00", "2026-08-10T09:00:00", "SGP22",
                     "2026-08-01T10:00:00", "2026-08-03T12:00:00", "FIN",
                     [Passo("2026-08-01T10:00:00", "", "", "", "chegada")])
        linhas = {(l["data"], l["grupo"]): l for l in calcular([p], date(2026, 8, 1), date(2026, 8, 10))
                  if l["comissao"] == "CCJ"}
        self.assertEqual(linhas[("2026-08-01", "projetos")]["pendentes"], "1")
        self.assertEqual(linhas[("2026-08-01", "projetos")]["etapa_sem_relator"], "1")  # ainda sem passo
        self.assertEqual(linhas[("2026-08-04", "projetos")]["idade_ate30"], "1")
        self.assertEqual(linhas[("2026-08-04", "projetos")]["mediana_dias"], "1")
        self.assertEqual(linhas[("2026-08-10", "todas")]["materias"], "0")


if __name__ == "__main__":
    unittest.main()
