# -*- coding: utf-8 -*-
"""Testes das votações por mês e do tempo de cada etapa."""
import unittest
from datetime import date

from painel.etapas import calcular, conjunta, motivo_da_saida, passos_por_materia


def rec(comissao, rotulo, data, area, passo, fonte="feed"):
    return {"comissao": comissao, "rotulo": rotulo, "data": data, "area": area, "passo": passo,
            "comentario": "", "fonte": fonte}


def cap(comissao, rotulo, data, area, passo, tipo="interna"):
    return {"data": data, "rotulo": rotulo, "tipo": tipo, "comissao": comissao, "area": area, "passo": passo,
            "comentario": ""}


def passagem(comissao, rotulo, desde, ate=None, recebido=None, motivo=""):
    return {"comissao": comissao, "rotulo": rotulo, "desde": desde, "recebido": recebido, "ate": ate,
            "origem": "PROC-CMSP", "destino": "SGP12" if ate else "", "motivo": motivo}


class TestEtapas(unittest.TestCase):

    def test_reuniao_conjunta(self):
        self.assertTrue(conjunta("Motivo: A pedido. Obs: Aprovado em Reunião Conjunta."))
        self.assertTrue(conjunta("Obs: passou em reunião conjunta."))
        self.assertFalse(conjunta("Motivo: Para reunião conjunta."))
        self.assertFalse(conjunta(""))

    def test_motivo_da_saida(self):
        self.assertEqual(motivo_da_saida("Motivo: Encerrado-TERMINO DE LEGISLATURA (ART. 275 REG. INT.).", True), "legislatura")
        self.assertEqual(motivo_da_saida("", True), "votada")
        self.assertEqual(motivo_da_saida("Motivo: Com parecer publicado.", False), "votada")
        self.assertEqual(motivo_da_saida("Obs: aprovado em reunião conjunta.", False), "conjunta")
        self.assertEqual(motivo_da_saida("Motivo: Encerrado-RETIRADO PELO AUTOR.", False), "retirada")
        self.assertEqual(motivo_da_saida("Motivo: A pedido. Obs: Decurso de prazo - Art. 363 do RI.", False), "prazo")
        self.assertEqual(motivo_da_saida("", False), "outros")

    def test_passos_juntam_reconstrucao_e_feed(self):
        ancora = "2026-10-03T06:53:36"
        passos = passos_por_materia(
            [rec("CCJ", "PL 1/2025", "2026-09-01T10:00:00", "Presidente da Comissão", "Designar Relator"),
             rec("CCJ", "PL 1/2025", "2026-09-01T09:00:00", "", "", fonte="chegada"),  # marcação: fica de fora
             rec("CCJ", "PL 1/2025", "2026-10-03T07:00:00", "Relator(a)", "Assinar Relatório")],  # depois da âncora
            [cap("CCJ", "PL 1/2025", "2026-10-02T10:00:00", "Relator(a)", "Estudo"),  # antes da âncora
             cap("CCJ", "PL 1/2025", "2026-10-05T10:00:00", "Relator(a)", "Estudo para manifestação do relator"),
             cap("CCJ", "PL 1/2025", "2026-10-06T10:00:00", "Secretaria (SGP12)", "Em Condição de Pauta"),
             cap("CCJ", "PL 1/2025", "2026-10-07T10:00:00", "Secretaria (SGP12)", "Em Condição de Pauta",
                 tipo="excl_interna")],
            ancora)
        self.assertEqual(passos[("CCJ", "PL 1/2025")], [("2026-09-01T10:00:00", "etapa_sem_relator"),
                                                        ("2026-10-05T10:00:00", "etapa_estudo")])

    def test_votacoes_e_tempos(self):
        passos = {("CCJ", "PL 1/2025"): [("2025-03-01T10:00:00", "etapa_sem_relator"),
                                          ("2025-03-11T10:00:00", "etapa_estudo"),
                                          ("2025-04-10T10:00:00", "etapa_pauta"),
                                          ("2025-04-17T10:00:00", "etapa_votado")],
                  ("FIN", "PL 2/2025"): [("2025-05-01T10:00:00", "etapa_sem_relator")]}
        lista = [passagem("CCJ", "PL 1/2025", "2025-03-01T09:00:00", "2025-04-20T10:00:00",
                          recebido="2025-03-01T10:00:00"),
                 passagem("FIN", "PL 2/2025", "2025-05-01T09:00:00", "2025-06-02T10:00:00",
                          motivo="Motivo: A pedido. Obs: Aprovado em Reunião Conjunta.")]
        j = calcular(lista, passos, "2026-10-03")
        m = j["meses"]
        votadas = j["producao"]["projetos"]["TODAS"]["votadas"]
        conjuntas = j["producao"]["projetos"]["TODAS"]["conjunta"]
        self.assertEqual(votadas[m.index("2025-04")], 1)
        self.assertEqual(conjuntas[m.index("2025-06")], 1)
        self.assertEqual(sum(votadas) + sum(conjuntas), 2)
        tempos = j["tempos"]["projetos"]["CCJ"]
        k = j["anos"].index(2025)
        self.assertEqual([tempos[e]["mediana"][k] for e in ("relator", "estudo", "pauta")], [10, 30, 7])
        self.assertEqual(j["tempos"]["projetos"]["FIN"]["relator"]["n"][k], 0)  # nunca saiu de "sem relator"
        # Calendário: 4 passos da CCJ em dias diferentes; a votação em 17/04/2025.
        cal = j["calendario"]["projetos"]["CCJ"]
        self.assertEqual(sum(cal["passos"][1::2]), 4)
        self.assertEqual(cal["votos"], [(date(2025, 4, 17) - date(2018, 11, 1)).days, 1])


if __name__ == "__main__":
    unittest.main()
