# -*- coding: utf-8 -*-
"""Testes do coletor: trava contra queda brusca e dia de referência."""
import unittest
from datetime import datetime

from coletor.coletar import _queda_brusca, dia_de_referencia
from coletor.config import FUSO


def coletas(data, **por_comissao):
    return [{"data": data, "coletado_em": "", "comissao": c, "materias": str(n)}
            for c, n in por_comissao.items()]


class TestQuedaBrusca(unittest.TestCase):

    def test_primeira_coleta_passa(self):
        self.assertIsNone(_queda_brusca({"CCJ": 0}, []))

    def test_variacao_normal_passa(self):
        anteriores = coletas("2026-10-01", CCJ=2445, FIN=446)
        self.assertIsNone(_queda_brusca({"CCJ": 2400, "FIN": 300}, anteriores))

    def test_queda_brusca_barra(self):
        anteriores = coletas("2026-10-01", CCJ=2445, FIN=446)
        self.assertIn("CCJ", _queda_brusca({"CCJ": 0, "FIN": 446}, anteriores))

    def test_compara_com_a_coleta_mais_recente(self):
        anteriores = coletas("2026-09-30", CCJ=2445) + coletas("2026-10-01", CCJ=1000)
        self.assertIsNone(_queda_brusca({"CCJ": 900}, anteriores))

    def test_comissao_pequena_nao_e_checada(self):
        anteriores = coletas("2026-10-01", ECON=10)
        self.assertIsNone(_queda_brusca({"ECON": 0}, anteriores))


class TestDiaDeReferencia(unittest.TestCase):

    def test_coleta_da_noite_vale_para_o_proprio_dia(self):
        self.assertEqual(dia_de_referencia(datetime(2026, 10, 2, 21, 47, tzinfo=FUSO)), "2026-10-02")

    def test_coleta_atrasada_de_madrugada_vale_para_o_dia_anterior(self):
        self.assertEqual(dia_de_referencia(datetime(2026, 10, 3, 2, 48, tzinfo=FUSO)), "2026-10-02")

    def test_depois_das_9h_ja_e_o_novo_dia(self):
        self.assertEqual(dia_de_referencia(datetime(2026, 10, 3, 9, 0, tzinfo=FUSO)), "2026-10-03")


if __name__ == "__main__":
    unittest.main()
