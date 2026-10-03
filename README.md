# Acervo das Comissões — CMSP

Série histórica do acervo das 7 Comissões Permanentes da Câmara Municipal de São Paulo: quais matérias estão em análise em cada comissão, com qual relator e em que estado da tramitação interna, dia após dia.

O SPLEGIS mostra só o retrato do momento. Este repositório tira um retrato por dia e guarda a evolução, para responder perguntas como "o acervo da CCJ está crescendo ou diminuindo?" ou "quanto tempo as matérias passaram sem relator ao longo do ano?".

**Painel:** https://prototiposlegisla.github.io/comissoes-acervo/

**Situação:** coleta diária automática desde 02/10/2026, mais uma reconstrução do acervo de novembro de 2018 até essa data.

**Autoria:** criado e mantido por [André Marcon](mailto:andremarcon@saopaulo.sp.leg.br) e Kauê Negrão.

## Como funciona

- **Fonte:** o relatório público [Projetos em Análise nas Comissões](https://splegisconsulta.saopaulo.sp.leg.br/Relatorio/IndexComissaoProjetoTramitacaoInterna) do SPLEGIS. O coletor lê o endpoint JSON que alimenta a tabela do relatório, com todos os tipos de matéria.
- **Quando:** um GitHub Action ([`.github/workflows/coleta.yml`](.github/workflows/coleta.yml)) roda todo dia às 10h07, às 15h07 e às 21h47 (horário de Brasília) e faz commit dos dados em [`dados/`](dados/); cada coleta substitui a anterior do mesmo dia, e a da noite fecha o retrato. Uma repescagem às 23h47 coleta só se o dia ainda estiver sem coleta. O agendamento do GitHub às vezes atrasa horas; por isso, coletas feitas até as 9h valem para o dia anterior, cujo fim elas retratam.
- **Tramitações:** depois de cada coleta, o coletor guarda os envios do dia de e para as comissões e os passos da tramitação interna, tirados do [feed diário de eventos](https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx) do SPLEGIS. O retrato mostra que uma matéria saiu do acervo e só guarda o último passo interno de cada coleta; as tramitações dizem quando, para onde e por que ela saiu, e tudo o que aconteceu entre uma coleta e outra.
- **Idempotente:** coletar de novo para o mesmo dia substitui a coleta daquele dia.
- **À prova de resposta truncada:** se alguma comissão falhar, nada é gravado. Se o acervo de uma comissão cair mais de 50% de um dia para o outro, a coleta também é barrada, porque isso indica resposta incompleta do SPLEGIS e seria registrado como uma saída em massa de matérias.
- **Sem dependências:** só a biblioteca padrão do Python.

## Os dados

Todos os arquivos estão em UTF-8, separados por vírgula. As datas seguem o formato ISO 8601 (`2026-08-24T15:43:00`), no horário de Brasília.

| Arquivo | Conteúdo |
|---|---|
| [`dados/acervo.csv`](dados/acervo.csv) | Retrato do dia: uma linha por comissão × matéria. O histórico do git guarda os retratos anteriores. |
| [`dados/historico.csv`](dados/historico.csv) | Os mesmos estados em intervalos de validade (`desde`/`ate`). É o arquivo para a série histórica. |
| [`dados/materias.csv`](dados/materias.csv) | Catálogo cumulativo de toda matéria já vista: rótulo, tipo, número, ano e ementa. |
| [`dados/autorias.csv`](dados/autorias.csv) | Autores de cada matéria. |
| [`dados/coletas.csv`](dados/coletas.csv) | Data, hora e tamanho do acervo de cada comissão em cada coleta. |
| [`dados/tramitacoes.csv`](dados/tramitacoes.csv) | Envios de e para as comissões registrados no feed do SPLEGIS desde o início da coleta diária, com o motivo. |
| [`dados/passos_internos.csv`](dados/passos_internos.csv) | Passos da tramitação interna nas comissões registrados no feed desde o início da coleta diária. |
| [`dados/relatorias.csv`](dados/relatorias.csv) | Relator, parecer e conclusão de cada projeto (PL, PDL, PR, PLO) apresentado desde 2013 em cada comissão permanente, por despacho. |
| [`dados/encerrados.csv`](dados/encerrados.csv) | Como terminou cada projeto encerrado desde 2013: promulgado, vetado, retirado, arquivado etc. |
| [`dados/projetos_por_ano.csv`](dados/projetos_por_ano.csv) | Quantos projetos de cada tipo foram apresentados por ano. |
| [`dados/eventos.csv`](dados/eventos.csv) | Eventos marcados nos gráficos de tempo (como a pandemia): `data`, `texto` curto do marco e `descricao`. Editado à mão. |
| [`dados/areas.csv`](dados/areas.csv) | Nome de cada área de tramitação do SPLEGIS (`SGP21` = Equipe de Apoio ao Plenário etc.). |
| [`dados/assuntos.csv`](dados/assuntos.csv) | Assuntos de cada projeto apresentado desde 2013, no vocabulário que a Câmara usa para indexar os projetos. |
| [`dados/autores.csv`](dados/autores.csv) | Autores de cada projeto apresentado desde 2013, na ordem, com a data de leitura. Dá a autoria (vereadores, Executivo, Mesa) e o partido do primeiro autor. |
| [`dados/filiacoes.csv`](dados/filiacoes.csv) | Partidos de cada vereador, com as datas de filiação. Dá o partido do relator na data do parecer. |
| [`dados/cargos_comissoes.csv`](dados/cargos_comissoes.csv) | Presidentes, vices e membros das 7 comissões permanentes, com as datas. |

### `acervo.csv` e `historico.csv`

| Coluna | Descrição |
|---|---|
| `comissao` | Sigla da comissão: `ADM`, `CCJ`, `ECON`, `EDUC`, `FIN`, `SAUDE` ou `URB`. |
| `materia_id` | Identificador da matéria no SPLEGIS. Liga com `materias.csv` e `autorias.csv`. |
| `desde`, `ate` | Só no histórico. Primeira e última data de coleta em que a matéria foi vista nesse estado, nessa comissão. `ate` vazio significa que o estado continuava vigente na última coleta. |
| `rotulo` | Tipo, número e ano, como `PL 502/2026`. |
| `relator_codigo`, `relator` | Relator designado; vazio significa sem relator. O código é o mesmo usado para autores em `autorias.csv`. |
| `enviado_por`, `enviado_em` | Área de origem e data do envio da matéria à comissão (tramitação externa). |
| `recebido_em` | Data do recebimento pela comissão. Vazio significa envio ainda pendente de recebimento. |
| `interna_data`, `interna_area`, `interna_tipo`, `interna_comentario` | Última tramitação interna na comissão, como `Relator(a)` / `Estudo para manifestação do relator`. |
| `ultima_interna` | Resumo textual da última tramitação interna, como o SPLEGIS o exibe. Só vem preenchido quando os campos `interna_*` estão vazios, porque nos demais casos repete a mesma informação. |

Uma mudança em qualquer coluna de estado (relator, tramitação etc.) fecha o intervalo anterior e abre um novo. O acervo de qualquer data coletada `d` é o conjunto das linhas com `desde <= d` e (`ate` vazio ou `d <= ate`). Por exemplo, com [DuckDB](https://duckdb.org/):

```sql
SELECT comissao, count(*) AS materias
FROM read_csv('dados/historico.csv', types = {'desde': 'DATE', 'ate': 'DATE'})
WHERE desde <= DATE '2026-10-15' AND (ate IS NULL OR ate >= DATE '2026-10-15')
GROUP BY comissao
ORDER BY comissao;
```

As contagens de dias não são gravadas, porque mudariam todo dia em toda linha. Para reproduzir os números do SPLEGIS, conte os períodos completos de 24 horas entre `recebido_em` (dias na comissão) ou `interna_data` (dias no estado atual) e o `coletado_em` da coleta, em `coletas.csv`.

O relatório traz todos os tipos de matéria: `PL`, `PDL`, `PR`, `PLO`, `DOCREC` (documentos recebidos), `RDP`, `REC` e outros. Para olhar só os projetos, filtre pelo `tipo` em `materias.csv`.

### `materias.csv`, `autorias.csv`, `coletas.csv`, `tramitacoes.csv` e `passos_internos.csv`

- `materias.csv`: `materia_id`, `rotulo`, `tipo`, `numero`, `ano`, `ementa`. Matérias que saem das comissões continuam no catálogo, com a última versão vista.
- `autorias.csv`: `materia_id`, `ordem`, `autor_codigo`, `autor`, `classe` (`Vereador`, `Remetente` ou `Promovente`).
- `coletas.csv`: `data`, `coletado_em` (com fuso), `comissao`, `materias` (tamanho do acervo naquela coleta).
- `tramitacoes.csv`: `data`, `rotulo`, `tipo` (`envio`, ou `excl_envio` quando o envio foi desfeito), `de` e `para` (áreas, como `CCJ` ou `SGP21`) e `motivo`, como o feed o registra (`Motivo: A pedido. Obs: Aprovado em Reunião Conjunta.`). Só os envios que saem de uma comissão ou chegam a ela, das matérias que o relatório lista.
- `passos_internos.csv`: `data`, `rotulo`, `tipo` (`interna`, ou `excl_interna` quando o passo foi excluído), `comissao`, `area`, `passo` e `comentario`, como `Relator(a)` / `Estudo para manifestação do relator`. Só os passos nas 7 comissões.
- Os dois arquivos só acrescentam: cada coleta baixa o feed do dia de referência e do anterior e junta o que faltava. `python -m coletor.tramitacoes --desde AAAA-MM-DD` preenche lacunas.

### `relatorias.csv`, `encerrados.csv`, `projetos_por_ano.csv`, `areas.csv`, `assuntos.csv`, `autores.csv`, `filiacoes.csv` e `cargos_comissoes.csv`

Vêm do [webservice do SPLEGIS](https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx) (operações `ProjetosReunioesDeComissao`, `ProjetosEncerrados`, `ProjetosPorAno`, `AreasDeTramitacao`, `ProjetosAssuntos`, `ProjetosAutores` e `VereadoresCMSP`), por `python -m coletor.legislativo`, uma vez por dia, para os projetos dos últimos oito anos; `--desde 2013` refaz tudo.

- `relatorias.csv`: `rotulo`, `comissao`, `despacho` (número do despacho que mandou o projeto às comissões) e `despachado_em`, `relator` e `partido` (o que o SPLEGIS registra hoje para o vereador, que pode não ser o da época; o painel usa o da data do parecer, por `filiacoes.csv`), `parecer` (número/ano), `parecer_em` e `conclusao` (como `FAVORÁVEL`, `LEGALIDADE COM SUBSTITUTIVO`, `CONTRÁRIO`). Não traz a data da designação do relator.
- `encerrados.csv`: `rotulo`, `tipo`, `ano`, `leitura`, `encerramento` e `motivo` (`Encerrado-PROMULGADO`, `Encerrado-VETO TOTAL ACEITO`, `Encerrado-TERMINO DE LEGISLATURA (ART. 275 REG. INT.)` etc.).
- `projetos_por_ano.csv`: `ano`, `tipo`, `projetos`.
- `areas.csv`: `sigla`, `nome`.
- `assuntos.csv`: `rotulo` e `assuntos`, separados por ` | ` (como `DENOMINACAO | LOGRADOURO PUBLICO`). O painel deixa de fora os termos que descrevem a ação do projeto (criação, alteração, prazo...) e as referências a normas.
- `autores.csv`: `rotulo`, `leitura`, `ordem` (1 = primeiro autor), `autor_codigo` e `autor`. Os prefeitos são reconhecidos pelo código de autor, como na composição do acervo.
- `filiacoes.csv`: `vereador`, `partido`, `inicio`, `fim`. Inclui os vereadores de legislaturas anteriores.
- `cargos_comissoes.csv`: `comissao`, `cargo` (`Presidente`, `Vice-presidente`, `Membro`...), `vereador`, `inicio`, `fim`. As comissões extraordinárias ficam de fora.

## Série reconstruída (nov/2018 a out/2026)

Para que a série não precise de anos para ganhar profundidade, [`dados/reconstrucao/`](dados/reconstrucao/) traz o acervo de cada dia desde novembro de 2018. Ele foi reconstruído a partir dos eventos de tramitação que o SPLEGIS publica dia a dia e ancorado no primeiro retrato real. A reconstrução não tem relator, porque nenhuma fonte pública registra quem foi designado no passado, e marca com `?` o que não pôde ser recuperado. Método, arquivos e validação estão em [`dados/reconstrucao/README.md`](dados/reconstrucao/README.md).

## Rodar localmente

Requer Python 3.10 ou mais recente.

```sh
python -m coletor.coletar              # coleta e grava em dados/
python -m coletor.coletar --se-faltar  # só coleta se hoje ainda não tiver coleta
python -m coletor.coletar --forcar     # ignora a trava contra queda brusca do acervo
python -m coletor.tramitacoes          # envios do dia de referência e do anterior, do feed
python -m coletor.legislativo          # relatorias, desfechos e contagens (últimos 8 anos)
python -m unittest                     # testes

python -m reconstrucao baixar --inicio 2018-10-26 --fim 2026-10-02  # feed de eventos (cache)
python -m reconstrucao gerar                                        # refaz dados/reconstrucao/

python -m painel                    # gera site/dados/ a partir de dados/
python -m http.server -d site 8000  # abre o painel em http://localhost:8000
```

O painel ([`site/`](site/)) tem duas visões. O **Retrato do dia** traz o acervo atual com os indicadores do relatório (acervo ativo, relatores, sem relator, mais de 180 e de 365 dias, mediana), as distribuições por relator e por estado da tramitação, a pesquisa por autor ou partido (com seleção múltipla e resultado próprio) e a lista das matérias de cada recorte, com links para o SPLEGIS e exportação em CSV, Excel e PDF, além do relatório consolidado em XLSX com uma aba por comissão. A **Evolução** traz as séries diárias desde 2018 (tamanho, idade, etapa da tramitação e área do passo interno do acervo, mais a estimativa de matérias sem relator, que só se conhece com exatidão a partir da coleta diária), o crescimento das comissões em base 100, a composição do acervo por legislatura de apresentação, tipo e autoria, as votações e os pareceres por mês, quem relata, um calendário diário de votações e passos internos, a mediana do tempo de cada etapa por ano, por que as matérias saem de cada comissão, o tempo sem movimentação, como terminam os projetos e, a partir das passagens de cada matéria por cada comissão, as entradas e saídas por mês com a origem e o destino, a curva de permanência (quanto tempo as matérias ficam na comissão, pelo estimador de Kaplan-Meier) e a matriz de rotas entre as comissões. É publicado no GitHub Pages pelo workflow [`painel.yml`](.github/workflows/painel.yml), a cada push e depois de cada coleta. Ele junta a série reconstruída com a dos retratos reais, calculada com a mesma regra (e as passagens da reconstrução com as dos retratos, completadas pelas tramitações), e usa [Observable Plot](https://observablehq.com/plot/) e [D3](https://d3js.org/) (licença ISC, copiados em `site/vendor/`).

Se o SPLEGIS bloquear o acesso a partir do GitHub, o coletor respeita as variáveis de ambiente `HTTPS_PROXY`/`HTTP_PROXY`. Basta defini-las no workflow a partir de um secret.

## Licença

Código sob a [licença MIT](LICENSE). Os dados são públicos e vêm do SPLEGIS, da Câmara Municipal de São Paulo.
