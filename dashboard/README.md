# Laboratorio de modelos (dashboard/app_dev.py)

Aplicacao Streamlit local para **inspecionar, comparar e testar** os modelos do
projeto: o modelo publicado, os dois controles serializados e os finalistas da
campanha de otimizacao (plano 1.6, recorte **1.6-O6**).

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
```

Os testes de aplicacao usam `streamlit.testing.v1.AppTest` e fixtures locais; nao
retreinam nem avaliam o conjunto de teste. Sem o extra `model_lab`, o arquivo de
teste e ignorado e o restante da suite continua valendo.
