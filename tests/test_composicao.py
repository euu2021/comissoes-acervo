# -*- coding: utf-8 -*-
"""Testes da autoria usada na composição do acervo."""
import unittest

from painel.composicao import EXECUTIVO, autorias, categoria, classe


class TestComposicao(unittest.TestCase):

    def test_classe_pelo_codigo_e_pelo_nome(self):
        executivo = set(EXECUTIVO)
        self.assertEqual(classe("RICARDO NUNES", "2229", executivo), "Executivo")  # como prefeito
        self.assertEqual(classe("RICARDO NUNES", "1990", executivo), "Vereadores")  # como vereador
        self.assertEqual(classe("MESA DA CAMARA MUNICIPAL DE SAO PAULO", "2284", executivo), "Mesa Diretora")
        self.assertEqual(classe("COMISSÃO DE FINANÇAS E ORÇAMENTO", "1", executivo), "Outros ou desconhecido")
        self.assertEqual(classe("Executivo - FULANO", "9999", executivo), "Executivo")

    def test_relatorio_completa_e_corrige_o_feed(self):
        reconstruidas = [{"rotulo": "PL 1/2026", "ordem": "1", "autor_codigo": "3000", "autor": "FULANA"},
                         {"rotulo": "PL 2/2018", "ordem": "1", "autor_codigo": "2229", "autor": "RICARDO NUNES"},
                         {"rotulo": "PL 3/2020", "ordem": "2", "autor_codigo": "10", "autor": "BELTRANO"},
                         {"rotulo": "PL 3/2020", "ordem": "1", "autor_codigo": "3000", "autor": "FULANA"}]
        coletadas = [{"materia_id": "9", "ordem": "1", "autor_codigo": "3000", "autor": "Executivo - FULANA",
                      "classe": "Promovente"}]
        materias = [{"materia_id": "9", "rotulo": "PL 1/2026"}]
        por = autorias(reconstruidas, coletadas, materias)
        # FULANA virou prefeita: o relatório a marca como Executivo, e o código vale para todo projeto dela.
        self.assertEqual(por, {"PL 1/2026": "Executivo", "PL 2/2018": "Executivo", "PL 3/2020": "Executivo"})

    def test_categoria(self):
        self.assertEqual(categoria("DOCREC 1/2026", {}), "Documentos e outros tipos")
        self.assertEqual(categoria("PL 9/2026", {}), "Outros ou desconhecido")
        self.assertEqual(categoria("PL 9/2026", {"PL 9/2026": "Vereadores"}), "Vereadores")


if __name__ == "__main__":
    unittest.main()
