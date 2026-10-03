# Acervo das Comissões — CMSP

Série histórica do acervo das 7 Comissões Permanentes da Câmara Municipal de São Paulo: quais matérias estão em análise em cada comissão, com qual relator e em que estado da tramitação interna, dia após dia.

O SPLEGIS mostra só o retrato do momento. Este repositório tira um retrato por dia e guarda a evolução, para responder perguntas como "o acervo da CCJ está crescendo ou diminuindo?" ou "quanto tempo as matérias passaram sem relator ao longo do ano?".

**Situação:** coleta diária automática desde 02/10/2026, mais uma reconstrução do acervo de novembro de 2018 até essa data. O site no GitHub Pages ainda está em construção.

## Como funciona

- **Fonte:** o relatório público [Projetos em Análise nas Comissões](https://splegisconsulta.saopaulo.sp.leg.br/Relatorio/IndexComissaoProjetoTramitacaoInterna) do SPLEGIS. O coletor lê o endpoint JSON que alimenta a tabela do relatório, com todos os tipos de matéria.
- **Quando:** um GitHub Action ([`.github/workflows/coleta.yml`](.github/workflows/coleta.yml)) roda todo dia às 21h47 (horário de Brasília) e faz commit dos dados em [`dados/`](dados/). Uma repescagem às 23h47 coleta só se a primeira execução tiver falhado.
- **Idempotente:** coletar de novo no mesmo dia substitui a coleta daquele dia.
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

### `materias.csv`, `autorias.csv` e `coletas.csv`

- `materias.csv`: `materia_id`, `rotulo`, `tipo`, `numero`, `ano`, `ementa`. Matérias que saem das comissões continuam no catálogo, com a última versão vista.
- `autorias.csv`: `materia_id`, `ordem`, `autor_codigo`, `autor`, `classe` (`Vereador`, `Remetente` ou `Promovente`).
- `coletas.csv`: `data`, `coletado_em` (com fuso), `comissao`, `materias` (tamanho do acervo naquela coleta).

## Série reconstruída (nov/2018 a out/2026)

Para que a série não precise de anos para ganhar profundidade, [`dados/reconstrucao/`](dados/reconstrucao/) traz o acervo de cada dia desde novembro de 2018. Ele foi reconstruído a partir dos eventos de tramitação que o SPLEGIS publica dia a dia e ancorado no primeiro retrato real. A reconstrução não tem relator, porque nenhuma fonte pública registra quem foi designado no passado, e marca com `?` o que não pôde ser recuperado. Método, arquivos e validação estão em [`dados/reconstrucao/README.md`](dados/reconstrucao/README.md).

## Rodar localmente

Requer Python 3.10 ou mais recente.

```sh
python -m coletor.coletar              # coleta e grava em dados/
python -m coletor.coletar --se-faltar  # só coleta se hoje ainda não tiver coleta
python -m coletor.coletar --forcar     # ignora a trava contra queda brusca do acervo
python -m unittest                     # testes

python -m reconstrucao baixar --inicio 2018-10-26 --fim 2026-10-02  # feed de eventos (cache)
python -m reconstrucao gerar                                        # refaz dados/reconstrucao/
```

Se o SPLEGIS bloquear o acesso a partir do GitHub, o coletor respeita as variáveis de ambiente `HTTPS_PROXY`/`HTTP_PROXY`. Basta defini-las no workflow a partir de um secret.

## Licença

Código sob a [licença MIT](LICENSE). Os dados são públicos e vêm do SPLEGIS, da Câmara Municipal de São Paulo.
