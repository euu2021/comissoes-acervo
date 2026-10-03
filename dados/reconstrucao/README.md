# Acervo reconstruído (nov/2018 a out/2026)

O acervo das 7 Comissões Permanentes dia a dia, de 01/11/2018 até o início da coleta diária deste repositório. Ele foi reconstruído a partir dos eventos de tramitação que o SPLEGIS publica para cada dia (serviço `MateriasEventosJSON`, completo a partir de 26/10/2018) e ancorado no retrato da primeira coleta real, de 02/10/2026 (refeito a partir de `dados/historico.csv`, para que novas coletas não mudem a reconstrução). A partir dessa data, valem os retratos reais em [`dados/`](../).

É uma reconstrução, com três diferenças em relação aos retratos reais:

- **Sem relator.** Nenhuma fonte pública do SPLEGIS registra quem foi designado relator no passado, só quem é o relator hoje.
- **Valores desconhecidos aparecem como `?`.** São dados de matérias que já estavam numa comissão quando o feed começou e que o histórico oficial da matéria não permitiu completar, sobretudo documentos recebidos (DOCREC) antigos, que não têm histórico.
- **Passos internos ficam na data em que foram lançados.** Quando um passo é lançado depois com data retroativa, o feed o registra na data do lançamento, enquanto o retrato mostra a data retroativa.

## Como foi feita

1. **Eventos.** Para cada dia, o feed lista as tramitações: envio de uma área para outra, recebimento, exclusão de envio ou de recebimento e tramitação interna, que é o passo dentro da comissão (como "Relator(a) / Estudo para manifestação do relator"). Até 2021 ele também registrava a exclusão de passos internos. Ficam de fora os tipos de matéria que o relatório de comissões não lista (como RDS).
2. **Correções da fonte.** Alguns recebimentos aparecem com dia e mês trocados (o de 09/04 surge em 04/09). Todo recebimento fora de lugar na sequência da matéria é conferido no histórico oficial dela e, se for o caso, movido para a data certa. Exclusões de envio ou de recebimento seguidas de tramitação interna na mesma comissão são desconsideradas: foram correções, já que matéria fora da comissão não tramita nela.
3. **Linha do tempo.** Como no relatório do SPLEGIS, a matéria está no destino do último envio vigente, recebida ou não; o recebimento só marca a data. Excluir um envio devolve a matéria à estada anterior. A situação anterior ao primeiro envio sai dele (matéria enviada pela CCJ estava na CCJ); a de matérias sem nenhum envio sai do retrato real. Recebimentos numa área onde a matéria não está são ignorados, porque costumam ser registros tardios de tramitações antigas, a não ser que a matéria depois saia daquela área, sinal de que o envio para lá faltou no feed.
4. **Antes do feed.** Para matérias que já estavam numa comissão em 26/10/2018, a data de envio, a de recebimento e o passo interno vigente vêm do histórico oficial da matéria (`Pesquisa/HistoricoMovimentacoes`). O mesmo vale quando o envio à comissão faltou no feed.
5. **Série diária.** Cada dia é avaliado às 23h59, com as mesmas regras do SPLEGIS: matérias enviadas à comissão e ainda não recebidas fazem parte do acervo, e a idade conta períodos completos de 24 horas desde o recebimento.

O código está em [`reconstrucao/`](../../reconstrucao/).

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| [`serie.csv`](serie.csv) | Série diária por comissão, para todas as matérias e só para projetos (PL, PDL, PR e PLO). |
| [`presencas.csv`](presencas.csv) | Uma linha por período em que uma matéria esteve no acervo de uma comissão. |
| [`passos_internos.csv`](passos_internos.csv) | Os passos da tramitação interna de cada matéria em cada comissão. |
| [`materias.csv`](materias.csv) | Tipo, número, ano, id e ementa de cada matéria que passou por comissões. |
| [`autorias.csv`](autorias.csv) | Autores de cada matéria, como o feed os informa. |
| [`validacao.md`](validacao.md) | Relatório gerado pela reconstrução, com todas as conferências. |

Datas no formato ISO 8601 (`2019-03-14T10:42:00`), no horário de Brasília.

### `serie.csv`

| Coluna | Descrição |
|---|---|
| `data`, `comissao` | Dia e sigla da comissão. `TODAS` soma as 7; a mediana dela é a de todas as matérias juntas. |
| `grupo` | `todas` as matérias ou só `projetos` (PL, PDL, PR e PLO). |
| `materias` | Tamanho do acervo no fim do dia. |
| `pendentes` | Matérias enviadas à comissão e ainda não recebidas. |
| `idade_ate30`, `idade_31a90`, `idade_91a180`, `idade_181a365`, `idade_mais365` | Matérias recebidas, pela idade em dias desde o recebimento. |
| `idade_desconhecida` | Matérias com data de recebimento desconhecida. |
| `mediana_dias` | Mediana da idade das matérias recebidas com idade conhecida. |
| `passo_relator`, `passo_presidente`, `passo_secretaria`, `passo_procuradoria`, `passo_consultoria`, `passo_outro` | Matérias pela área do passo interno vigente: relator(a), presidente da comissão, secretaria (SGP-12), procuradoria, consultoria ou outra. |
| `passo_nenhum` | Matérias que ainda não tiveram passo interno na comissão. |
| `passo_desconhecido` | Matérias cujo passo interno vigente é desconhecido. |
| `etapa_sem_relator`, `etapa_estudo`, `etapa_diligencia`, `etapa_pauta`, `etapa_votado`, `etapa_outra` | As mesmas matérias (menos as de passo desconhecido) pela etapa da tramitação, deduzida do passo interno vigente: sem relator (ainda sem passo ou à espera da designação ou redesignação do relator), em estudo (com o relator ou na assessoria técnica), em diligência (à espera de informações, ofício ou audiência pública), na pauta (em condição de pauta, relatada, adiada ou com vista), votada (deliberada ou com parecer a publicar) ou outra. `etapa_sem_relator` é a estimativa de matérias sem relator: no retrato de 02/10/2026, deu 1.170, e o relatório apontava 1.156. |
| `parado_ate30`, `parado_31a90`, `parado_91a180`, `parado_181a365`, `parado_mais365` | Matérias recebidas pelos dias completos sem movimentação interna: desde o último passo interno ou, se ainda não houve nenhum, desde o recebimento. |
| `parado_desconhecido` | Matérias recebidas sem data de referência conhecida para esse cálculo. |

`materias` é a soma de `pendentes` com as faixas de idade (incluída a desconhecida), e também a soma das colunas `passo_*`.

### `presencas.csv`

| Coluna | Descrição |
|---|---|
| `comissao`, `rotulo`, `materia_id` | Comissão, matéria (`PL 502/2026`) e id dela no SPLEGIS, quando conhecido. |
| `desde` | Quando a matéria passou a constar no acervo da comissão (o envio a ela). `?` indica que ela já estava lá quando o feed começou, em data desconhecida. |
| `ate` | Quando saiu do acervo. Vazio significa que continuava nele no retrato de 02/10/2026. |
| `enviado_por`, `enviado_em` | Área de origem e data do envio que levou a matéria à comissão. Origem vazia indica matéria registrada já na comissão. |
| `recebido_em` | Recebimento pela comissão. Vazio significa que não chegou a ser recebida nessa presença; `?`, que a data é desconhecida. |
| `destino` | Para onde a matéria foi ao sair. |
| `motivo_saida` | Motivo e observação do envio que tirou a matéria da comissão, como o feed os registra: `Motivo: Encerrado-TERMINO DE LEGISLATURA (ART. 275 REG. INT.).`, `Motivo: A pedido. Obs: Aprovado em Reunião Conjunta.` etc. Vazio quando o envio não tinha motivo, quando foi desfeito ou quando a matéria continuava no acervo. |

Uma matéria está no acervo de uma comissão no dia `d` se `desde <= d 23:59:59 < ate` (com `ate` vazio valendo como infinito).

### `passos_internos.csv`

| Coluna | Descrição |
|---|---|
| `comissao`, `rotulo` | Comissão e matéria. |
| `data` | Quando o passo foi lançado. |
| `area`, `passo`, `comentario` | O passo, como `Relator(a)` / `Estudo para manifestação do relator`. Área vazia significa que a matéria ainda não tinha passo interno; `?`, que o passo é desconhecido. |
| `fonte` | De onde veio: `feed`, `chegada` (a matéria acabou de entrar na comissão), `exclusao` (o passo vigente foi excluído e o anterior voltou a valer), `historico` (histórico oficial), `retrato` (retrato real) ou `desconhecido`. |

O passo vigente num momento é o último lançado até ali dentro da presença da matéria na comissão.

## Validação

Resumo da reconstrução publicada; o relatório completo, com exemplos de cada divergência, está em [`validacao.md`](validacao.md).

| Conferência | Resultado |
|---|---|
| Comissão de cada matéria no fim do período × retrato real de 02/10/2026 | 11.286 de 11.292 (99,95%) |
| Datas de envio e de recebimento × retrato real | 100% no mesmo dia |
| Último passo interno × retrato real | 99,5% |
| Tramitação interna acontece durante uma presença da matéria na comissão (204.539 passos) | 99,9% |
| Presença dia a dia × histórico oficial de 500 matérias sorteadas (204.516 matéria-dias, de 7 em 7 dias) | 99,77% |

Todas as diferenças em relação ao histórico oficial são de matérias que tiveram um envio ou recebimento excluído depois. O histórico de hoje não mostra mais o lançamento desfeito; a reconstrução registra o que valia em cada dia, inclusive o período em que o lançamento existiu.

Correções aplicadas à fonte: 51 recebimentos com dia e mês trocados, todos lançados entre 1º e 9 de abril de 2026, foram movidos para a data certa; 171 exclusões desmentidas por tramitação interna posterior foram desconsideradas.

Limitações conhecidas:

- **Relator:** não há.
- **Datas desconhecidas:** 109 presenças começaram antes do feed sem que o histórico oficial permitisse datá-las (`?`). São quase todas de DOCRECs antigos, que não têm histórico. Em 7 delas, o histórico indica que a matéria já tinha saído da comissão, e só lançamentos posteriores, depois desfeitos, a colocam lá.
- **Passos lançados com data retroativa** ficam na data do lançamento.
- **Valores `?` nos projetos** (PL, PDL, PR e PLO): somam 1,6% dos matéria-dias de idade e 0,2% dos de passo interno em 2018, e praticamente zero a partir de 2021. Considerando todas as matérias, o passo interno desconhecido fica entre 4% (2018) e 2% (2026), por causa dos DOCRECs antigos.

## Como reproduzir

```sh
python -m reconstrucao baixar --inicio 2018-10-26 --fim 2026-10-02
python -m reconstrucao gerar
```

O cache dos downloads fica em `reconstrucao/cache/`, fora do git.
