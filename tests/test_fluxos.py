# -*- coding: utf-8 -*-
"""Testes das passagens pelas comissões (reconstrução + retratos diários) e da captura
das tramitações do feed."""
import unittest

from coletor.tramitacoes import extrair, juntar
from painel.fluxos import estadas, montar, passagens

COLETAS = [{"data": "2026-10-02", "coletado_em": "2026-10-03T06:53:36-03:00"},
           {"data": "2026-10-03", "coletado_em": "2026-10-03T21:47:00-03:00"},
           {"data": "2026-10-05", "coletado_em": "2026-10-05T21:47:00-03:00"}]
DIAS = ["2026-10-02", "2026-10-03", "2026-10-05"]


def hist(comissao, rotulo, desde, ate="", enviado_por="PROC-CMSP", enviado_em="2026-09-01T10:00:00", passo="A"):
    return {"comissao": comissao, "rotulo": rotulo, "desde": desde, "ate": ate,
            "enviado_por": enviado_por, "enviado_em": enviado_em, "recebido_em": "2026-09-02T10:00:00",
            "interna_tipo": passo}


def rec(comissao, rotulo, desde="2026-09-01T10:00:00", ate="", destino="", enviado_por="PROC-CMSP"):
    return {"comissao": comissao, "rotulo": rotulo, "materia_id": "", "desde": desde, "ate": ate,
            "enviado_por": enviado_por, "enviado_em": desde, "recebido_em": "", "destino": destino}


def tram(data, rotulo, de, para, tipo="envio", motivo=""):
    return {"data": data, "rotulo": rotulo, "tipo": tipo, "de": de, "para": para, "motivo": motivo}


class TestEstadas(unittest.TestCase):

    def test_intervalos_seguidos_formam_uma_estada(self):
        lista = estadas([hist("CCJ", "PL 1/2026", "2026-10-02", "2026-10-02"),
                         hist("CCJ", "PL 1/2026", "2026-10-03", passo="B")], DIAS)
        self.assertEqual(len(lista), 1)
        self.assertEqual((lista[0]["primeiro"], lista[0]["ultimo"]), ("2026-10-02", ""))

    def test_lacuna_separa_estadas(self):
        lista = estadas([hist("CCJ", "PL 1/2026", "2026-10-02", "2026-10-02"),
                         hist("CCJ", "PL 1/2026", "2026-10-05")], DIAS)
        self.assertEqual([(e["primeiro"], e["ultimo"]) for e in lista],
                         [("2026-10-02", "2026-10-02"), ("2026-10-05", "")])

    def test_envio_novo_sem_lacuna_e_saida_e_volta(self):
        lista = estadas([hist("CCJ", "PL 1/2026", "2026-10-02", "2026-10-02"),
                         hist("CCJ", "PL 1/2026", "2026-10-03", enviado_em="2026-10-03T12:00:00")], DIAS)
        self.assertEqual(len(lista), 2)
        self.assertEqual(lista[0]["volta"], "2026-10-03T12:00:00")


class TestPassagens(unittest.TestCase):

    def setUp(self):
        reconstruidas = [
            rec("CCJ", "PL 1/2026"),                                     # vai para a ADM
            rec("FIN", "PL 2/2026"),                                     # some sem tramitação
            rec("URB", "PL 3/2025", "2025-01-01T10:00:00", "2025-02-01T10:00:00", "SGP21"),
            rec("EDUC", "DOCREC 9/2015"),                                # não está no retrato
            rec("SAUDE", "PL 4/2026"),                                   # sai e volta entre coletas
            rec("ECON", "PL 5/2026"),                                    # envio a ela desfeito
        ]
        historico = [
            hist("CCJ", "PL 1/2026", "2026-10-02", "2026-10-02"),
            hist("ADM", "PL 1/2026", "2026-10-03", enviado_por="CCJ", enviado_em="2026-10-03T15:00:00"),
            hist("FIN", "PL 2/2026", "2026-10-02", "2026-10-02"),
            hist("FIN", "PL 2/2026", "2026-10-03", "2026-10-03", passo="B"),
            hist("SAUDE", "PL 4/2026", "2026-10-02", "2026-10-02"),
            hist("SAUDE", "PL 4/2026", "2026-10-03", enviado_por="SGP12", enviado_em="2026-10-03T12:00:00"),
            hist("ECON", "PL 5/2026", "2026-10-02", "2026-10-03"),
        ]
        tramitacoes = [
            tram("2026-10-03T15:00:00", "PL 1/2026", "CCJ", "ADM", motivo="Motivo: A pedido."),
            tram("2026-10-03T09:00:00", "PL 4/2026", "SAUDE", "SGP12"),
            tram("2026-10-03T12:00:00", "PL 4/2026", "SGP12", "SAUDE"),
            tram("2026-10-04T10:00:00", "PL 5/2026", "SGP22", "ECON", "excl_envio"),
            tram("2026-09-20T10:00:00", "PL 2/2026", "FIN", "SGP21"),  # antes da estada: ignorada
        ]
        self.lista = passagens(reconstruidas, historico, COLETAS, tramitacoes)
        self.por = {}
        for p in self.lista:
            self.por.setdefault((p["comissao"], p["rotulo"]), []).append(p)

    def test_saida_com_destino_da_tramitacao(self):
        [p] = self.por[("CCJ", "PL 1/2026")]
        self.assertEqual((p["desde"], p["ate"], p["destino"], p["motivo"]),
                         ("2026-09-01T10:00:00", "2026-10-03T15:00:00", "ADM", "Motivo: A pedido."))
        self.assertEqual(p["recebido"], "2026-09-02T10:00:00")  # do retrato: a reconstrução não tinha

    def test_entrada_depois_da_primeira_coleta(self):
        [p] = self.por[("ADM", "PL 1/2026")]
        self.assertEqual((p["desde"], p["ate"], p["origem"], p["destino"]),
                         ("2026-10-03T15:00:00", None, "CCJ", ""))

    def test_saida_sem_tramitacao_vale_no_dia_da_coleta(self):
        [p] = self.por[("FIN", "PL 2/2026")]
        self.assertEqual((p["ate"], p["destino"]), ("2026-10-05", "?"))

    def test_passagem_encerrada_na_reconstrucao_fica_como_esta(self):
        [p] = self.por[("URB", "PL 3/2025")]
        self.assertEqual((p["ate"], p["destino"]), ("2025-02-01T10:00:00", "SGP21"))

    def test_divergencia_com_o_retrato_sai_na_primeira_coleta(self):
        [p] = self.por[("EDUC", "DOCREC 9/2015")]
        self.assertEqual((p["ate"], p["destino"]), ("2026-10-02", "?"))

    def test_saida_e_volta_entre_coletas(self):
        primeira, segunda = sorted(self.por[("SAUDE", "PL 4/2026")], key=lambda p: p["desde"])
        self.assertEqual((primeira["ate"], primeira["destino"]), ("2026-10-03T09:00:00", "SGP12"))
        self.assertEqual((segunda["desde"], segunda["origem"], segunda["ate"]),
                         ("2026-10-03T12:00:00", "SGP12", None))

    def test_envio_desfeito_devolve_a_quem_enviou(self):
        [p] = self.por[("ECON", "PL 5/2026")]
        self.assertEqual((p["ate"], p["destino"]), ("2026-10-04T10:00:00", "SGP22"))

    def test_montar_em_colunas(self):
        j = montar(self.lista, "2026-10-05", "2026-10-02", "2026-10-05T21:47:00-03:00")
        self.assertEqual(len(j["comissao"]), 8)  # a SAÚDE tem duas passagens
        self.assertNotIn("?", j["areas"])
        k = {j["comissoes"][c]: i for i, c in enumerate(j["comissao"])}
        self.assertEqual(j["ate"][k["FIN"]], 2901)  # 05/10/2026, contado desde 26/10/2018
        self.assertIsNone(j["destino"][k["FIN"]])  # saiu para destino desconhecido
        self.assertEqual(j["projeto"][k["EDUC"]], 0)  # DOCREC


class TestTramitacoes(unittest.TestCase):

    def test_extrair_so_envios_que_tocam_comissoes(self):
        itens = [{"Sigla": "PL", "Numero": 7, "Ano": 2026, "Eventos": [
                     {"Data": "2026-10-01T12:16:00", "Descricao": "Matéria PL 7/2026: tramitada da área SGP22 para a área FIN.  Motivo: A pedido."},
                     {"Data": "2026-10-01T13:00:00", "Descricao": "Matéria PL 7/2026: recebida na área FIN (enviada da área SGP22)."},
                     {"Data": "2026-10-01T14:00:00", "Descricao": "Matéria PL 7/2026: tramitada da área SGP21 para a área SGP23. "},
                     {"Data": "2026-10-01T15:00:00", "Descricao": "Matéria PL 7/2026: excluída tramitação da área SGP22 para a área FIN."},
                     {"Data": "2026-10-01T16:00:00", "Descricao": "Matéria PL 7/2026: tramitação interna - FIN/Relator(a)/Estudo para manifestação do relator -"},
                     {"Data": "2026-10-01T17:00:00", "Descricao": "Matéria PL 7/2026: tramitação interna - SGP21/Secretaria/Para Ciência -"}]},
                 {"Sigla": "RDS", "Numero": 1, "Ano": 2026, "Eventos": [
                     {"Data": "2026-10-01T12:00:00", "Descricao": "Matéria RDS 1/2026: tramitada da área CCJ para a área SGP21."}]}]
        envios, passos = extrair(itens)
        self.assertEqual(envios, [
            {"data": "2026-10-01T12:16:00", "rotulo": "PL 7/2026", "tipo": "envio", "de": "SGP22", "para": "FIN",
             "motivo": "Motivo: A pedido."},
            {"data": "2026-10-01T15:00:00", "rotulo": "PL 7/2026", "tipo": "excl_envio", "de": "SGP22", "para": "FIN",
             "motivo": ""}])
        self.assertEqual(passos, [
            {"data": "2026-10-01T16:00:00", "rotulo": "PL 7/2026", "tipo": "interna", "comissao": "FIN",
             "area": "Relator(a)", "passo": "Estudo para manifestação do relator", "comentario": ""}])

    def test_juntar_nao_repete_e_ordena(self):
        a = tram("2026-10-02T10:00:00", "PL 1/2026", "CCJ", "ADM")
        b = tram("2026-10-01T10:00:00", "PL 2/2026", "FIN", "SGP21")
        self.assertEqual(juntar([a], [b, a], list(a)), [b, a])


if __name__ == "__main__":
    unittest.main()
