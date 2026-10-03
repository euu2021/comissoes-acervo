# Validação da reconstrução

- Eventos de 2018-10-26 a 2026-10-02; série de 2018-11-01 a 2026-10-02; retrato-âncora de 2026-10-03T02:48:17.
- Eventos do feed: 427.296 (interna 204.958. envio 106.944. receb 99.387. outro 10.400. excl_envio 2.908. excl_interna 1.955. excl_receb 744).
- Matérias que passaram por comissões: 11.589; presenças: 25.364.
- Correções na fonte: {'recebimento suspeito confirmado': 1984, 'recebimento suspeito não resolvido (mantido)': 123, 'recebimento suspeito sem id': 2, 'recebimento suspeito sem histórico': 98, 'recebimento com dia/mês trocados (movido)': 51, 'excl_receb desconsiderada': 155, 'excl_envio desconsiderada': 16}.
- Incoerências na sequência de eventos externos (quase todas fora das comissões): {'recebida': 509, 'recebimento': 41, 'enviada': 899, 'envio': 399, 'retrato': 1}.
- Presenças iniciadas antes do feed, completadas com o histórico oficial: {'não completadas': 109, 'completadas': 1679}.

## A. Estado final × retrato real

- Comissão onde a matéria está: 11.286/11.292 (99.95%)
- Data de envio à comissão. mesmo dia: 3.821/3.821 (100.00%) (3.790 idênticas até o segundo)
- Data de recebimento. mesmo dia: 3.821/3.821 (100.00%) (3.821 idênticas até o segundo)
- Último passo interno: 3.120/3.137 (99.46%)

## B. Coerência: tramitação interna acontece durante uma presença na comissão

- Total: 204.361/204.547 (99.91%)
  - 2018: 6.368/6.400 (99.50%)
  - 2019: 35.425/35.465 (99.89%)
  - 2020: 12.562/12.606 (99.65%)
  - 2021: 24.344/24.360 (99.93%)
  - 2022: 21.758/21.770 (99.94%)
  - 2023: 24.414/24.434 (99.92%)
  - 2024: 22.076/22.079 (99.99%)
  - 2025: 36.994/37.005 (99.97%)
  - 2026: 20.420/20.428 (99.96%)

## C. Presença × histórico oficial (500 matérias sorteadas, 414 dias, de 7 em 7)

- Dias iguais: 204.052/204.516 (99.77%)
- Dias diferentes em matérias cujo envio ou recebimento foi excluído depois (o histórico de hoje não mostra mais o que foi desfeito): 464
- Dias diferentes sem explicação: 0
- {'dias iguais': 204052, 'matérias iguais em todos os dias': 478, 'dias diferentes (registro reescrito)': 464, 'matérias divergentes': 16, 'matérias sem histórico (fora da conta)': 6}

## Dados desconhecidos (matéria-dias com idade ou passo interno marcados "?")

- 2018: idade 0.8%, passo interno 4.1%
- 2019: idade 0.6%, passo interno 3.8%
- 2020: idade 0.3%, passo interno 3.6%
- 2021: idade 0.1%, passo interno 3.2%
- 2022: idade 0.1%, passo interno 2.7%
- 2023: idade 0.1%, passo interno 2.5%
- 2024: idade 0.1%, passo interno 2.2%
- 2025: idade 0.1%, passo interno 2.4%
- 2026: idade 0.0%, passo interno 1.7%

## Maiores variações diárias (todas as matérias)

- 2025-01-23 CCJ: -437 (ficou em 268)
- 2026-03-06 CCJ: +319 (ficou em 2065)
- 2021-01-27 CCJ: -273 (ficou em 599)
- 2025-01-16 CCJ: -266 (ficou em 1049)
- 2025-01-14 CCJ: -237 (ficou em 1315)
- 2025-01-20 CCJ: -220 (ficou em 829)
- 2021-01-05 FIN: -210 (ficou em 585)
- 2025-01-13 CCJ: -175 (ficou em 1552)
- 2021-01-30 CCJ: -175 (ficou em 304)
- 2025-01-23 FIN: -136 (ficou em 443)
- 2020-05-28 CCJ: +132 (ficou em 844)
- 2025-01-21 URB: -130 (ficou em 111)

## Exemplos

- A/comissão: ('DOCREC 203/2020', 'ADM', None)
- A/comissão: ('DOCREC 501/2017', 'URB', None)
- A/comissão: ('DOCREC 891/2015', 'URB', None)
- A/comissão: ('DOCREC 953/2015', 'URB', None)
- A/comissão: ('DOCREC 992/2015', 'URB', None)
- A/comissão: ('REC 71/2016', 'CCJ', None)
- A/passo: ('PL 110/2023', ('2025-05-14T17:55:15', 'Secretaria (SGP12)', 'Em Condição de Pauta'), ('2025-04-07T17:21:37', 'Relator(a)', 'Assinar Relatório'))
- A/passo: ('PL 197/2023', ('2026-08-25T17:24:53', 'Secretaria (SGP12)', 'Aguardando Informações do Executivo'), ('2026-05-15T10:00:00', 'Secretaria (SGP12)', 'Aguardando Informações do Executivo'))
- A/passo: ('PL 309/2024', ('2026-06-25T15:50:33', 'Secretaria (SGP12)', 'Aguardando Informações do Executivo'), ('2025-04-23T18:16:55', 'Presidente da Comissão', 'Assinar Pedido de Informação ao Executivo'))
- A/passo: ('PL 315/2019', ('2026-03-31T16:43:02', 'Relator(a)', 'Estudo para manifestação do relator'), ('2025-08-28T11:44:31', 'Secretaria (SGP12)', 'Em Condição de Pauta'))
- A/passo: ('PL 380/2024', ('2026-08-25T17:23:11', 'Secretaria (SGP12)', 'Aguardando Informações do Executivo'), ('2026-06-15T10:00:00', 'Secretaria (SGP12)', 'Aguardando Informações do Executivo'))
- A/passo: ('PL 385/2021', ('2026-08-05T18:50:19', 'Consultoria (SGP.52)', 'Para análise'), ('2026-08-05T18:31:28', 'Consultoria (SGP.52)', 'Para análise'))
- A/passo: ('PL 528/2025', ('2026-08-06T17:54:08', 'Secretaria (SGP12)', 'Aguardando Informações do Executivo'), ('2026-07-14T15:42:08', 'Relator(a)', 'Estudo para manifestação do relator'))
- A/passo: ('PL 545/2024', ('2026-08-25T17:21:10', 'Secretaria (SGP12)', 'Aguardando Informações do Executivo'), ('2026-06-15T10:00:00', 'Secretaria (SGP12)', 'Aguardando Informações do Executivo'))
- A/passo: ('PL 618/2025', ('2025-11-12T16:28:21', 'Secretaria (SGP12)', 'Aguardando Notas Taquigráficas'), ('', '', ''))
- A/passo: ('PL 640/2018', ('2026-04-30T16:08:59', 'URB', ''), ('2026-04-30T16:08:59', 'Secretaria (SGP12)', 'Aguardando Audiência Pública'))
- B: ('PL 157/2017', '2018-11-06T12:41:31', 'ADM')
- B: ('PL 866/2017', '2018-11-06T12:41:35', 'ADM')
- B: ('PL 353/2018', '2018-11-06T12:41:38', 'ADM')
- B: ('PL 459/2018', '2018-11-06T12:41:40', 'ADM')
- B: ('PL 327/2018', '2018-11-06T12:41:42', 'ADM')
- B: ('PL 269/2018', '2018-11-06T12:41:45', 'ADM')
- B: ('PL 206/2018', '2018-11-06T12:41:47', 'ADM')
- B: ('PL 418/2018', '2018-11-06T12:41:50', 'ADM')
- B: ('PL 486/2018', '2018-11-06T12:41:52', 'ADM')
- B: ('PL 424/2018', '2018-11-06T12:41:55', 'ADM')
- C: ('PL 157/2017', '2018-11-08', None, 'ADM', 'reescrito')
- C: ('PL 157/2017', '2018-11-15', None, 'ADM', 'reescrito')
- C: ('PL 157/2017', '2018-11-22', None, 'ADM', 'reescrito')
- C: ('PL 157/2017', '2018-11-29', None, 'ADM', 'reescrito')
- C: ('PL 157/2017', '2018-12-06', None, 'ADM', 'reescrito')
- C: ('PL 157/2017', '2018-12-13', None, 'ADM', 'reescrito')
- C: ('PL 157/2017', '2018-12-20', None, 'ADM', 'reescrito')
- C: ('PL 157/2017', '2018-12-27', None, 'ADM', 'reescrito')
- C: ('PL 157/2017', '2019-01-03', None, 'ADM', 'reescrito')
- C: ('PL 157/2017', '2019-01-10', None, 'ADM', 'reescrito')
- correções: ('data trocada', 'PL 66/2020', 'SAUDE', '2026-06-04T12:18:00', '2026-04-06T12:18:00')
- correções: ('data trocada', 'PL 662/2020', 'ECON', '2026-06-04T13:51:00', '2026-04-06T13:51:00')
- correções: ('data trocada', 'PL 78/2021', 'FIN', '2026-07-04T18:47:00', '2026-04-07T18:47:00')
- correções: ('data trocada', 'PL 385/2021', 'SAUDE', '2026-06-04T12:18:00', '2026-04-06T12:18:00')
- correções: ('data trocada', 'PL 41/2022', 'FIN', '2026-07-04T18:47:00', '2026-04-07T18:47:00')
- correções: ('data trocada', 'PL 671/2022', 'SAUDE', '2026-06-04T12:18:00', '2026-04-06T12:18:00')
- correções: ('data trocada', 'PL 42/2023', 'FIN', '2026-07-04T18:47:00', '2026-04-07T18:47:00')
- correções: ('data trocada', 'PL 439/2023', 'FIN', '2026-07-04T18:47:00', '2026-04-07T18:47:00')
- correções: ('data trocada', 'PL 628/2023', 'CCJ', '2026-06-04T13:23:00', '2026-04-06T13:23:00')
- correções: ('data trocada', 'PL 694/2023', 'ECON', '2026-08-04T12:08:00', '2026-04-08T12:08:00')
