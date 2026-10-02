# -*- coding: utf-8 -*-
"""Configuração central do coletor."""
from datetime import timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_DADOS = RAIZ / "dados"

ARQ_ACERVO = DIR_DADOS / "acervo.csv"        # retrato do dia (sobrescrito a cada coleta)
ARQ_HISTORICO = DIR_DADOS / "historico.csv"  # intervalos de validade de cada estado
ARQ_MATERIAS = DIR_DADOS / "materias.csv"    # catálogo cumulativo das matérias
ARQ_AUTORIAS = DIR_DADOS / "autorias.csv"    # autores de cada matéria
ARQ_COLETAS = DIR_DADOS / "coletas.csv"      # registro de cada coleta, por comissão

# Endpoint JSON (padrão DataTables) que alimenta o relatório público
# "Projetos em Análise nas Comissões":
# https://splegisconsulta.saopaulo.sp.leg.br/Relatorio/IndexComissaoProjetoTramitacaoInterna
URL_RELATORIO = ("https://splegisconsulta.saopaulo.sp.leg.br/"
                 "Relatorio/PageDataComissaoProjetoTramitacaoInterna")

# As 7 Comissões Permanentes: sigla -> código do departamento no SPLEGIS (campo "depto").
COMISSOES = {
    "ADM": 23,
    "CCJ": 20,
    "ECON": 24,
    "EDUC": 25,
    "FIN": 21,
    "SAUDE": 26,
    "URB": 22,
}

# Horário de Brasília. Offset fixo porque o Brasil não tem horário de verão desde 2019
# e porque zoneinfo exige o pacote tzdata no Windows.
FUSO = timezone(timedelta(hours=-3))

# Registros pedidos por requisição. Hoje a maior comissão (CCJ) tem ~2.500 matérias,
# então uma página basta; a paginação existe só por garantia.
TAMANHO_PAGINA = 5000
TIMEOUT = 300            # segundos; a CCJ leva ~45 s para responder
TENTATIVAS = 4           # por requisição, com backoff exponencial

# Trava de sanidade: aborta (sem gravar nada) se o acervo de uma comissão cair mais
# que isso em relação à coleta anterior. Uma resposta truncada do SPLEGIS seria
# registrada como saída em massa de matérias e corromperia o histórico.
QUEDA_MAXIMA = 0.5
QUEDA_PISO = 20          # comissões com menos matérias que isso não são checadas

USER_AGENT = ("Mozilla/5.0 (compatible; comissoes-acervo/1.0; "
              "+https://github.com/euu2021/comissoes-acervo)")
