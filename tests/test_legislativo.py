# -*- coding: utf-8 -*-
"""Testes das relatorias, pareceres e desfechos tirados do webservice do SPLEGIS."""
import unittest

from coletor.legislativo import encerrados, relatorias
from painel.legislativo import assunto_util, conclusao, desfecho, montar, partido_na_data


class TestLegislativo(unittest.TestCase):

    def test_relatorias_so_das_comissoes_permanentes(self):
        itens = [{"tipo": "PL", "numero": 2, "ano": 2019, "encaminhamentos": [
            {"sequencia": 1, "data": "2019-03-14T13:59:57", "comissoes": [
                {"nome": "CCJ", "relator": "Ver. RICARDO NUNES (MDB)", "nomePolitico": "RICARDO NUNES",
                 "relatorio": {"numero": 1678, "ano": 2019}, "dataParecer": "2019-09-04T00:00:00",
                 "conclusao": "LEGALIDADE COM SUBSTITUTIVO"},
                {"nome": "CPI", "relator": "Ver. FULANO (PT)", "nomePolitico": "FULANO"},
                {"nome": "URB", "relator": "Ver. TONINHO PAIVA (PL)", "nomePolitico": "TONINHO PAIVA"}]}]}]
        linhas = relatorias(itens)
        self.assertEqual([(l["comissao"], l["relator"], l["partido"], l["parecer"]) for l in linhas],
                         [("CCJ", "RICARDO NUNES", "MDB", "1678/2019"), ("URB", "TONINHO PAIVA", "PL", "")])
        self.assertEqual(linhas[0]["rotulo"], "PL 2/2019")

    def test_conclusoes_e_desfechos(self):
        self.assertEqual(conclusao("FAVORÁVEL AO SUBSTITUTIVO DA COMISSÃO DE JUSTIÇA"), "favoravel")
        self.assertEqual(conclusao("LEG. E FAV. COM SUBSTITUTIVO (REUNIAO CONJUNTA)"), "favoravel")
        self.assertEqual(conclusao("LEGALIDADE COM SUBSTITUTIVO"), "legalidade")
        self.assertEqual(conclusao("ILEGALIDADE/INCONSTITUCIONALIDADE"), "ilegalidade")
        self.assertEqual(conclusao("CONTRÁRIO AO SUBSTITUTIVO (REUNIÃO CONJUNTA)"), "contrario")
        self.assertEqual(conclusao("REDAÇÃO FINAL"), "outros")
        self.assertEqual(desfecho("Encerrado-PROMULGADO"), "lei")
        self.assertEqual(desfecho("Encerrado-VETO PARCIAL ACEITO"), "lei")
        self.assertEqual(desfecho("Encerrado-VETO TOTAL ACEITO"), "vetado")
        self.assertEqual(desfecho("Encerrado-ILEGALIDADE (ART. 79 REG. INT.)"), "rejeitado")
        self.assertEqual(desfecho("Encerrado-TERMINO DE LEGISLATURA (ART. 275 REG. INT.)"), "legislatura")

    def test_montar(self):
        rel = [{"rotulo": "PL 1/2025", "comissao": "CCJ", "relator": "A", "partido": "PT", "parecer_em": "2025-03-10T00:00:00",
                "conclusao": "LEGALIDADE"},
               {"rotulo": "PL 1/2025", "comissao": "FIN", "relator": "B", "partido": "PL", "parecer_em": "",
                "conclusao": ""}]
        enc = encerrados([{"tipo": "PL", "numero": 1, "ano": 2025, "leitura": "2025-01-06T00:00:00",
                           "encerramento": "2025-12-01T10:00:00", "motivo": "Encerrado-PROMULGADO"}])
        j = montar(rel, enc, [{"ano": "2025", "tipo": "PL", "projetos": "10"}], "2026-10-03")
        k = j["meses"].index("2025-03")
        self.assertEqual(j["pareceres"]["CCJ"]["legalidade"][k], 1)
        self.assertEqual(j["pareceres"]["TODAS"]["legalidade"][k], 1)
        self.assertEqual(j["pareceres_por_relator"]["CCJ"], [k, 0, 0, 1])  # sem parecer, B não conta
        a = j["anos"].index(2025)
        self.assertEqual((j["desfechos"]["lei"][a], j["em_tramitacao"][a]), (1, 9))

    def test_partido_na_data_e_assuntos(self):
        filiacoes = {"FULANO": [("2020-03-11", "S/PARTIDO"), ("2021-06-01", "NOVO"), ("2023-07-25", "PL")]}
        self.assertEqual(partido_na_data(filiacoes, "FULANO", "2022-01-10T00:00:00"), "NOVO")
        self.assertEqual(partido_na_data(filiacoes, "FULANO", "2023-07-25T10:00:00"), "PL")
        self.assertEqual(partido_na_data(filiacoes, "FULANO", "2019-01-01"), "S/PARTIDO")  # antes da primeira
        self.assertFalse(assunto_util("ALTERACAO"))
        self.assertFalse(assunto_util("LEI 14.485/2007"))
        self.assertTrue(assunto_util("PESSOA COM DEFICIENCIA"))


if __name__ == "__main__":
    unittest.main()
