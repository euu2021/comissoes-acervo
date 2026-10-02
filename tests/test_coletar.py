# -*- coding: utf-8 -*-
"""Testes da trava contra queda brusca do acervo."""
import unittest

from coletor.coletar import _queda_brusca


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


if __name__ == "__main__":
    unittest.main()
