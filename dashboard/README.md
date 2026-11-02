# Laboratorio de modelos (dashboard/app_dev.py)

Aplicacao Streamlit local para **inspecionar, comparar e testar** os modelos do
projeto: o modelo publicado, os dois controles serializados e os finalistas da
campanha de otimizacao (plano 1.6, recorte **1.6-O6**).

O guia operacional completo — com as variaveis do formulario, os seis perfis de
teste, a interpretacao dos resultados em lote e os limites do que se pode
afirmar — esta em
[`docs/user_guides/laboratorio-de-modelos.md`](../docs/user_guides/laboratorio-de-modelos.md).

Esta aplicacao e distinta do painel operacional da fase 3:

| | `dashboard/app_dev.py` (laboratorio) | `dashboard/app.py` (fase 3) |
|---|---|---|
| Objetivo | comparar e testar modelos | observar a saude do pipeline |
| Executa inferencia | sim, sob demanda explicita | nao |
| Le o conjunto de teste | nunca | nunca |
| Treina ou promove | nunca | nunca |

## Instalacao e execucao

```bash
uv sync --dev --locked --extra model_lab
uv run --extra model_lab streamlit run dashboard/app_dev.py --server.address 127.0.0.1
```

O processo abre apenas em `127.0.0.1`. Para encerrar, interrompa o comando no
terminal (`Ctrl+C`).

O extra `model_lab` instala apenas o Streamlit; o ambiente padrao de treino
continua sem ele, e o `observability` da fase 3 segue atendendo ao painel
operacional.

## Telas

1. **Artefatos e prontidao** — disponibilidade, hash, versao, papel (vigente,
   controle, finalista) e manifesto da campanha. Artefato ausente ou com hash
   divergente aparece como indisponivel, com o motivo.
2. **Comparacao dos modelos** — tabela lado a lado da **rodada unica de
   validacao** da campanha (ROC-AUC, average precision, precision, recall, F1,
   accuracy, Brier), deltas contra o RF vigente, intervalos pareados do bootstrap,
   matrizes de confusao, curvas ROC/PR e distribuicao das probabilidades. Os
   numeros vem do relatorio congelado (`comparison.json`): a aplicacao nao
   recalcula avaliacoes nem mistura a media de CV com a metrica de validacao.
3. **Predicao individual e em lote** — formulario editavel com as 19 features
   financeiras, o ID e os quatro atributos de governanca; e upload de CSV **sem a
   coluna de alvo**. O lote validado e enviado a todos os modelos selecionados, e a
   tela mostra a probabilidade de inadimplencia, a classe no limiar `0.5`, as
   divergencias entre modelos e a duracao local da chamada.
4. **Cenarios de contrato** — predefinicoes sinteticas: lote valido, ID
   duplicado, limite nao positivo, idade fora do intervalo e feature nula. Cada
   cenario mostra o resultado esperado, o observado e o diagnostivo por
   regra/coluna. Um lote invalido e recusado por inteiro e **nao chama nenhum
   modelo**.
5. **Data Drift — cenário 1.0.2** — leitura do snapshot agregado congelado em
   `reports/drift/results-v1.0.2.json` e
   `reports/drift/prediction_summary-v1.0.2.json`. A comparação, tabela PSI das
   19 features, bins persistidos de `LIMIT_BAL`/`PAY_AMT1` e quantis dos scores
   são independentes dos modelos e lotes selecionados nas outras abas. O HTML
   versionado v6 fica disponível para download quando está materializado.

### Leitura e limites de Data Drift

- A aba não executa inferência, detector PSI, treino, avaliação nem criação de
  alertas. Ela valida e apresenta apenas os dois JSONs agregados do cenário
  `phase-2-1.0.2`, protocolo `1.0.2`, contrato `1.0.0` e o SHA do modelo M2.
- O seletor oferece somente as três comparações armazenadas. A tabela mostra
  score PSI, limiar, booleano original do detector e denominadores para todas
  as 19 features; ordenação visual não oculta features sem alerta.
- Os gráficos reproduzem os labels, bordas e proporções já persistidos, com a
  categoria zero separada e valores monetários em NT$. Os resumos de scores são
  agregados e não permitem reconstruir histogramas ou linhas individuais.
- Data Drift descreve mudança na distribuição de entradas. Não demonstra
  Concept Drift, degradação, causalidade ou desempenho; as probabilidades são
  previsões, não inadimplência observada. A validação usada para produção já
  participou da seleção do modelo.
- Artefato ausente, versão não suportada ou incoerência de hashes/contagens
  deixa a aba indisponível com motivo controlado. A ausência do HTML v6 não
  bloqueia os resumos JSON nem dispara geração do relatório.
- Nenhuma linha, ID, alvo ou dado do conjunto de teste é lido ou exportado por
  esta aba. Uploads de inferência continuam sem diagnóstico automático de drift.

## Estados e limites

- Um registro isolado produz **previsoes**, nunca metricas de generalizacao.
- O upload com a coluna de alvo e recusado: a tela de inferencia nao avalia.
- As curvas dependem do artefato de probabilidades da rodada; enquanto ele nao
  existir, a tela informa "indisponivel" em vez de fabricar curvas.
- Trocar a selecao de modelos ou o lote invalida o resultado guardado: o valor
  antigo deixa de ser apresentado como resultado atual.
- Os exemplos sao sinteticos. Nenhum registro real de cliente entra nas telas,
  nas exportacoes ou na evidencia.
- A aplicacao nao treina, nao promove, nao grava sobre datasets, sobre as
  metricas oficiais nem sobre o `dvc.lock`.

## Testes

```bash
uv run --extra model_lab pytest tests/test_app_dev.py
uv run --extra model_lab pytest tests/test_drift_snapshot.py
```

Os testes de aplicacao usam `streamlit.testing.v1.AppTest` e fixtures locais; nao
retreinam nem avaliam o conjunto de teste. Sem o extra `model_lab`, o arquivo de
teste e ignorado e o restante da suite continua valendo.
