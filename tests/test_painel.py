# -*- coding: utf-8 -*-
"""Testes da série dos retratos reais usada no painel."""
import unittest

from painel.__main__ import colunas, serie_real


def linha(comissao, rotulo, desde, ate="", recebido="2026-09-01T10:00:00", relator="", area="Relator(a)"):
    return {"comissao": comissao, "rotulo": rotulo, "desde": desde, "ate": ate,
            "recebido_em": recebido, "relator_codigo": relator, "interna_area": area}


class TestSerieReal(unittest.TestCase):

    def setUp(self):
        coletas = [{"data": "2026-10-02", "coletado_em": "2026-10-03T02:48:17-03:00"},
                   {"data": "2026-10-03", "coletado_em": "2026-10-03T21:47:00-03:00"}]
        historico = [linha("CCJ", "PL 1/2026", "2026-10-02", relator="123"),
                     linha("CCJ", "DOCREC 1/2020", "2026-10-02", area=""),
                     linha("FIN", "PL 2/2026", "2026-10-02", ate="2026-10-02", recebido=""),
                     linha("FIN", "PL 3/2026", "2026-10-03", recebido="")]
        self.linhas = {(l["data"], l["comissao"], l["grupo"]): l for l in serie_real(coletas, historico)}

    def test_contagens_e_total(self):
        self.assertEqual(self.linhas[("2026-10-02", "CCJ", "todas")]["materias"], "2")
        self.assertEqual(self.linhas[("2026-10-02", "CCJ", "projetos")]["materias"], "1")
        self.assertEqual(self.linhas[("2026-10-02", "TODAS", "todas")]["materias"], "3")
        self.assertEqual(self.linhas[("2026-10-03", "TODAS", "todas")]["materias"], "3")

    def test_sem_relator_e_pendentes(self):
        self.assertEqual(self.linhas[("2026-10-02", "TODAS", "projetos")]["sem_relator"], "1")
        self.assertEqual(self.linhas[("2026-10-03", "FIN", "todas")]["pendentes"], "1")

    def test_idade_conta_no_instante_da_coleta(self):
        # Recebida em 01/09 às 10h, coletada em 03/10 às 02h48: 31 dias completos.
        self.assertEqual(self.linhas[("2026-10-02", "CCJ", "projetos")]["mediana_dias"], "31")
        self.assertEqual(self.linhas[("2026-10-02", "CCJ", "projetos")]["idade_31a90"], "1")

    def test_colunas(self):
        datas, comissoes = colunas(list(self.linhas.values()), "todas")
        self.assertEqual(datas, ["2026-10-02", "2026-10-03"])
        self.assertEqual(comissoes["FIN"]["materias"], [1, 1])
        self.assertEqual(comissoes["CCJ"]["passo_nenhum"], [1, 1])


if __name__ == "__main__":
    unittest.main()
