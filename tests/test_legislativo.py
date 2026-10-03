# -*- coding: utf-8 -*-
"""Testes das relatorias, pareceres e desfechos tirados do webservice do SPLEGIS."""
import unittest

from coletor.legislativo import encerrados, relatorias
from painel.legislativo import (assunto_util, autoria_dos_projetos, conclusao, desfecho, membros, montar,
                                partido_na_data, prazos)


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
                "conclusao": "LEGALIDADE", "despacho": "1", "despachado_em": "2025-02-01T10:00:00"},
               {"rotulo": "PL 1/2025", "comissao": "FIN", "relator": "B", "partido": "PL", "parecer_em": "",
                "conclusao": "", "despacho": "1", "despachado_em": "2025-02-01T10:00:00"}]
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


    def test_autoria_e_desfecho_por_partido(self):
        filiacoes = {"FULANO": [("2020-01-01", "NOVO"), ("2024-01-01", "PL")]}
        autores = [{"rotulo": "PL 1/2023", "leitura": "2023-02-01T00:00:00", "ordem": "2", "autor_codigo": "9", "autor": "BELTRANO"},
                   {"rotulo": "PL 1/2023", "leitura": "2023-02-01T00:00:00", "ordem": "1", "autor_codigo": "7", "autor": "FULANO"},
                   {"rotulo": "PL 2/2023", "leitura": "", "ordem": "1", "autor_codigo": "2229", "autor": "RICARDO NUNES"},
                   {"rotulo": "PR 3/2023", "leitura": "", "ordem": "1", "autor_codigo": "5", "autor": "MESA DA CAMARA MUNICIPAL DE SAO PAULO"}]
        self.assertEqual(autoria_dos_projetos(autores, filiacoes),
                         {"PL 1/2023": ("Vereadores", "NOVO"), "PL 2/2023": ("Executivo", ""), "PR 3/2023": ("Mesa Diretora", "")})
        enc = encerrados([{"tipo": "PL", "numero": 1, "ano": 2023, "leitura": "", "encerramento": "", "motivo": "Encerrado-PROMULGADO"}])
        j = montar([], enc, [], "2026-10-03", autores=autores,
                   filiacoes=[{"vereador": "FULANO", "partido": "NOVO", "inicio": "2020-01-01", "fim": ""}])
        a = j["anos"].index(2023)
        self.assertEqual(j["desfechos_partido"]["NOVO"]["lei"][a], 1)
        self.assertEqual(j["desfechos_autoria"]["Executivo"]["aberto"][a], 1)

    def test_prazos_contam_da_vez_da_comissao(self):
        base = {"rotulo": "PL 5/2024", "despacho": "1", "despachado_em": "2024-02-01T15:00:00", "conclusao": "FAVORÁVEL"}
        rel = [{**base, "comissao": "CCJ", "parecer_em": "2024-02-11T00:00:00", "conclusao": "LEGALIDADE"},
               {**base, "comissao": "URB", "parecer_em": "2024-03-12T00:00:00"},
               {**base, "comissao": "FIN", "parecer_em": "2024-03-12T00:00:00"},  # conjunta com a URB
               {**base, "comissao": "ADM", "parecer_em": "2024-05-01T00:00:00", "conclusao": "REDAÇÃO FINAL"},
               {**base, "comissao": "EDUC", "despacho": "2", "despachado_em": "2024-06-01T10:00:00",
                "parecer_em": "2024-06-01T00:00:00"}]  # segunda discussão
        import painel.legislativo as L
        minimo, L.MINIMO_PRAZOS = L.MINIMO_PRAZOS, 1
        try:
            s = prazos(rel * 1, {"PL 5/2024": ("Vereadores", "PT")}, [2024])
        finally:
            L.MINIMO_PRAZOS = minimo
        self.assertEqual(s["CCJ"]["Todas"]["mediana"], [10])
        self.assertEqual(s["URB"]["Vereadores"]["mediana"], [30])  # do parecer da CCJ
        self.assertEqual(s["FIN"]["Todas"]["n"], [1])
        self.assertNotIn("ADM", s)  # redação final não conta
        self.assertNotIn("EDUC", s)  # nem o segundo despacho

    def test_membros_por_partido(self):
        filiacoes = {"A": [("2010-01-01", "PT")], "B": [("2010-01-01", "PSDB")]}
        cargos = [{"comissao": "CCJ", "cargo": "Membro", "vereador": "A", "inicio": "2013-01-01T00:00:00", "fim": ""},
                  {"comissao": "CCJ", "cargo": "Presidente", "vereador": "A", "inicio": "2013-01-01T00:00:00", "fim": ""},
                  {"comissao": "CCJ", "cargo": "Membro", "vereador": "B", "inicio": "2013-02-20T00:00:00", "fim": "2013-03-01T00:00:00"}]
        m = membros(cargos, filiacoes, "2013-03-20")
        self.assertEqual(m["meses"], ["2013-01", "2013-02", "2013-03"])
        pt = m["partidos"].index("PT")
        self.assertEqual(m["por_comissao"]["CCJ"], [0, pt, 1, 1, pt, 1, 2, pt, 1])
        self.assertEqual(m["por_comissao"]["TODAS"][:3], [0, pt, 1])
        self.assertEqual(m["partidos"], ["PT"])  # B entrou depois do dia 15 e saiu antes do seguinte


if __name__ == "__main__":
    unittest.main()
