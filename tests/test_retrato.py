# -*- coding: utf-8 -*-
"""Testes do retrato do dia usado no painel."""
import unittest

from painel.retrato import montar, nome_proprio, pessoa


class TestNomes(unittest.TestCase):

    def test_nome_proprio(self):
        self.assertEqual(nome_proprio("SILVIA DA BANCADA FEMINISTA"), "Silvia da Bancada Feminista")
        self.assertEqual(nome_proprio("DR. MILTON FERREIRA"), "Dr. Milton Ferreira")
        self.assertEqual(nome_proprio("TRIBUNAL DE CONTAS DO MUNICÍPIO DE SÃO PAULO"),
                         "Tribunal de Contas do Município de São Paulo")

    def test_pessoa(self):
        self.assertEqual(pessoa("Ver. ROBERTO TRÍPOLI (PV)"), ("Roberto Trípoli", "PV"))
        self.assertEqual(pessoa("Executivo - RICARDO NUNES"), ("Executivo", "Executivo"))
        self.assertEqual(pessoa("MESA DA CAMARA MUNICIPAL DE SAO PAULO - 01/01/2026 a 31/12/2026"),
                         ("Mesa Diretora", "Mesa Diretora"))
        self.assertEqual(pessoa("SECRETARIA MUNICIPAL DA FAZENDA"), ("Secretaria Municipal da Fazenda", "Outros"))


class TestMontar(unittest.TestCase):

    def test_materia(self):
        acervo = [{"comissao": "CCJ", "materia_id": "1", "rotulo": "PL 1/2026", "relator": "Ver. A B (PT)",
                   "recebido_em": "2026-09-01T10:00:00", "interna_data": "", "interna_area": "",
                   "interna_tipo": "", "ultima_interna": "02/09/2026 03:08 - Presidente da Comissão / Assinar"},
                  {"comissao": "FIN", "materia_id": "2", "rotulo": "DOCREC 5/2020", "relator": "",
                   "recebido_em": "", "interna_data": "", "interna_area": "", "interna_tipo": "",
                   "ultima_interna": ""}]
        materias = [{"materia_id": "1", "ementa": "Institui algo."}]
        autorias = [{"materia_id": "1", "ordem": "1", "autor": "Ver. A B (PT)"},
                    {"materia_id": "1", "ordem": "2", "autor": "Ver. C D (PSOL)"}]
        r = montar(acervo, materias, autorias, {"data": "2026-10-02", "coletado_em": "2026-10-03T02:48:17-03:00"})
        pl, docrec = r["materias"]
        self.assertEqual(r["pessoas"][pl["rel"]], ["A B", "PT"])
        self.assertEqual([r["pessoas"][a] for a in pl["a"]], [["A B", "PT"], ["C D", "PSOL"]])
        self.assertEqual((pl["p"], pl["dc"], pl["dp"], pl["e"]), (1, 31, 31, "Institui algo."))
        self.assertEqual((docrec["p"], docrec["rel"], docrec["dc"], docrec["dp"], docrec["a"]), (0, None, None, None, []))


if __name__ == "__main__":
    unittest.main()
