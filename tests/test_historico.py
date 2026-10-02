# -*- coding: utf-8 -*-
"""Testes da lógica de intervalos. Rodar da raiz: python -m unittest"""
import unittest

from coletor.esquema import CAMPOS_ESTADO
from coletor.historico import atualizar, desfazer


def linha(comissao, materia_id, **estado):
    base = {c: "" for c in CAMPOS_ESTADO}
    base.update(estado)
    return {"comissao": comissao, "materia_id": str(materia_id), **base}


def acervo_em(historico, data):
    """Reconstrói o acervo de uma data a partir dos intervalos."""
    return {(h["comissao"], h["materia_id"]): h["relator"] for h in historico
            if h["desde"] <= data and (not h["ate"] or data <= h["ate"])}


class TestHistorico(unittest.TestCase):

    def setUp(self):
        self.d1 = [linha("CCJ", 1, relator="A"), linha("CCJ", 2), linha("FIN", 3)]
        self.h1, _ = atualizar([], "2026-10-01", self.d1, None)

    def test_primeira_coleta_abre_tudo(self):
        self.assertEqual(len(self.h1), 3)
        self.assertTrue(all(h["desde"] == "2026-10-01" and h["ate"] == "" for h in self.h1))

    def test_sem_mudanca_nao_mexe_em_nada(self):
        h2, resumo = atualizar(self.h1, "2026-10-02", self.d1, "2026-10-01")
        self.assertEqual(h2, self.h1)
        self.assertEqual(resumo, {})

    def test_mudanca_entrada_saida(self):
        d2 = [linha("CCJ", 1, relator="B"),   # mudou de relator
              linha("FIN", 2),                # saiu da CCJ e entrou na FIN
              linha("FIN", 3)]                # sem mudança
        h2, resumo = atualizar(self.h1, "2026-10-02", d2, "2026-10-01")
        self.assertEqual(resumo["CCJ"], {"entradas": 0, "saidas": 1, "mudancas": 1})
        self.assertEqual(resumo["FIN"], {"entradas": 1, "saidas": 0, "mudancas": 0})
        self.assertEqual(acervo_em(h2, "2026-10-01"),
                         {("CCJ", "1"): "A", ("CCJ", "2"): "", ("FIN", "3"): ""})
        self.assertEqual(acervo_em(h2, "2026-10-02"),
                         {("CCJ", "1"): "B", ("FIN", "2"): "", ("FIN", "3"): ""})
        # A linha sem mudança é a mesma, intocada.
        self.assertIn(self.h1[2], h2)

    def test_reentrada_abre_novo_intervalo(self):
        h2, _ = atualizar(self.h1, "2026-10-02", self.d1[:2], "2026-10-01")
        h3, resumo = atualizar(h2, "2026-10-05", self.d1, "2026-10-02")
        fin3 = [h for h in h3 if h["materia_id"] == "3"]
        self.assertEqual([(h["desde"], h["ate"]) for h in fin3],
                         [("2026-10-01", "2026-10-01"), ("2026-10-05", "")])
        self.assertEqual(resumo["FIN"]["entradas"], 1)
        self.assertNotIn(("FIN", "3"), acervo_em(h3, "2026-10-02"))

    def test_recoletar_o_mesmo_dia_substitui(self):
        d2a = [linha("CCJ", 1, relator="B"), linha("FIN", 3)]
        d2b = [linha("CCJ", 1, relator="C"), linha("CCJ", 2), linha("FIN", 3), linha("URB", 4)]
        h2a, _ = atualizar(self.h1, "2026-10-02", d2a, "2026-10-01")
        h2b, _ = atualizar(desfazer(h2a, "2026-10-02", "2026-10-01"),
                           "2026-10-02", d2b, "2026-10-01")
        direto, _ = atualizar(self.h1, "2026-10-02", d2b, "2026-10-01")
        self.assertEqual(h2b, direto)

    def test_desfazer_a_primeira_coleta_esvazia(self):
        self.assertEqual(desfazer(self.h1, "2026-10-01", None), [])

    def test_coleta_fora_de_ordem_falha(self):
        with self.assertRaises(ValueError):
            atualizar(self.h1, "2026-09-30", self.d1, "2026-10-01")

    def test_abertos_sem_coleta_anterior_falha(self):
        with self.assertRaises(ValueError):
            atualizar(self.h1, "2026-10-02", self.d1, None)


if __name__ == "__main__":
    unittest.main()
