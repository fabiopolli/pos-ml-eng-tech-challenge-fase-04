# Dashboard — painel operacional e laboratório de modelos

Este diretório contém **duas aplicações Streamlit distintas**, com finalidades e fases
diferentes:

| | `dashboard/app.py` (painel operacional) | `dashboard/app_dev.py` (laboratório) |
|---|---|---|
| Fase / recorte | Fase 3 — observabilidade do pipeline | Recorte **1.6-O6** do plano 1.6 |
| Objetivo | observar a saúde do pipeline | inspecionar, comparar e testar modelos congelados |
| Extra de dependências | `observability` (MLflow + Streamlit) | `model_lab` (Streamlit) |
| Estado atual | histórico operacional, métricas e alertas; aceite descrito na [evidência da Etapa 3](../docs/evidence/fase-3.md) | implementado e verificado (**1.6-O6** concluído) |
| Executa inferência | não | sim, sob demanda explícita |
| Lê o conjunto de teste | nunca | nunca |
| Treina ou promove | nunca | nunca |

As duas podem ser executadas no mesmo checkout, em processos e portas separados.

---

## `dashboard/app.py` — painel operacional da fase 3

O painel lê o histórico local de execução e identifica o run correspondente no MLflow.
Use **Atualizar execuções** para reler o diretório, ou selecione um ID para inspecionar uma
tentativa anterior. O painel mantém visíveis a tentativa mais recente e a última bem-sucedida.

### Instalação e execução

```bash
uv sync --dev --locked --extra observability
uv run --extra observability streamlit run dashboard/app.py --server.address 127.0.0.1
```

O processo abre apenas em `127.0.0.1`. Para encerrar, interrompa o comando no terminal
(`Ctrl+C`).

O extra `observability` instala Streamlit e MLflow; o ambiente padrão de treino continua sem
eles.

### O que esperar na tela

- Estado da tentativa, duração, CPU, pico de memória e contagens do lote.
- Métricas de avaliação congeladas, distribuição agregada de scores, PSI e alertas.
- Estado vazio, indicação de tracking indisponível e acesso ao HTML verificado por hash.

O painel abre sem materializar objetos DVC. Consulte a
[evidência da Etapa 3](../docs/evidence/fase-3.md) para popular o histórico.

### Limites

- Um rerender não executa o pipeline, não altera dados e não gera alertas.
- Nenhuma linha, ID ou alvo é exibido ou exportado.
- A UI do MLflow roda em processo separado com o mesmo backend SQLite do produtor:

  ```bash
  uv run --extra observability mlflow ui --backend-store-uri sqlite:///observability/mlflow.db --host 127.0.0.1
  ```

---

## `dashboard/app_dev.py` — laboratório de modelos

Aplicação Streamlit local para **inspecionar, comparar e testar** os modelos do projeto: o
modelo publicado, os dois controles serializados e os finalistas da campanha de otimização
(plano 1.6, recorte **1.6-O6**).

O guia operacional completo — com as variáveis do formulário, os seis perfis de teste, a
interpretação dos resultados em lote e os limites do que se pode afirmar — está em
[`docs/user_guides/laboratorio-de-modelos.md`](../docs/user_guides/laboratorio-de-modelos.md).

Esta aplicação é distinta do painel operacional da fase 3 (`dashboard/app.py`): o laboratório
compara e testa **modelos**, o painel operacional acompanha **execuções** do pipeline.

### Instalação e execução

```bash
uv sync --dev --locked --extra model_lab
uv run --extra model_lab streamlit run dashboard/app_dev.py --server.address 127.0.0.1
```

O processo abre apenas em `127.0.0.1`. Para encerrar, interrompa o comando no terminal
(`Ctrl+C`).

O extra `model_lab` instala apenas o Streamlit: o ambiente padrão de treino continua sem ele, e
o `observability` da fase 3 segue atendendo ao painel operacional.

### Telas

1. **Artefatos e prontidão** — disponibilidade, hash, versão, papel (vigente, controle, finalista)
   e manifesto da campanha. Artefato ausente ou com hash divergente aparece como indisponível,
   com o motivo.
2. **Comparação dos modelos** — tabela lado a lado da **rodada única de validação** da campanha
   (ROC-AUC, average precision, precision, recall, F1, accuracy, Brier), deltas contra o RF
   vigente, intervalos pareados do bootstrap, matrizes de confusão, curvas ROC/PR e distribuição
   das probabilidades. Os números vêm do relatório congelado (`comparison.json`): a aplicação não
   recalcula avaliações nem mistura a média de CV com a métrica de validação.
3. **Predição individual e em lote** — formulário editável com as 19 features financeiras, o ID e
   os quatro atributos de governança; e upload de CSV **sem a coluna de alvo**. O lote validado é
   enviado a todos os modelos selecionados, e a tela mostra a probabilidade de inadimplência, a
   classe no limiar `0.5`, as divergências entre modelos e a duração local da chamada.
4. **Cenários de contrato** — predefinições sintéticas: lote válido, ID duplicado, limite não
   positivo, idade fora do intervalo e feature nula. Cada cenário mostra o resultado esperado, o
   observado e o diagnóstico por regra/coluna. Um lote inválido é recusado por inteiro e **não
   chama nenhum modelo**.
5. **Data Drift — cenário 1.0.2** — leitura do snapshot agregado congelado em
   `reports/drift/results-v1.0.2.json` e `reports/drift/prediction_summary-v1.0.2.json`. A
   comparação, tabela PSI das 19 features, bins persistidos de `LIMIT_BAL`/`PAY_AMT1` e quantis
   dos scores são independentes dos modelos e lotes selecionados nas outras abas. O HTML
   versionado v6 fica disponível para download quando está materializado.

### Leitura e limites de Data Drift

- A aba não executa inferência, detector PSI, treino, avaliação nem criação de alertas. Ela
  valida e apresenta apenas os dois JSONs agregados do cenário `phase-2-1.0.2`, protocolo
  `1.0.2`, contrato `1.0.0` e o SHA do modelo M2.
- O seletor oferece somente as três comparações armazenadas. A tabela mostra score PSI, limiar,
  booleano original do detector e denominadores para todas as 19 features; ordenação visual não
  oculta features sem alerta.
- Os gráficos reproduzem os labels, bordas e proporções já persistidos, com a categoria zero
  separada e valores monetários em NT$. Os resumos de scores são agregados e não permitem
  reconstruir histogramas ou linhas individuais.
- Data Drift descreve mudança na distribuição de entradas. Não demonstra Concept Drift,
  degradação, causalidade ou desempenho; as probabilidades são previsões, não inadimplência
  observada. A validação usada para produção já participou da seleção do modelo.
- Artefato ausente, versão não suportada ou incoerência de hashes/contagens deixa a aba
  indisponível com motivo controlado. A ausência do HTML v6 não bloqueia os resumos JSON nem
  dispara geração do relatório.
- Nenhuma linha, ID, alvo ou dado do conjunto de teste é lido ou exportado por esta aba. Uploads
  de inferência continuam sem diagnóstico automático de drift.

### Estados e limites

- Um registro isolado produz **previsões**, nunca métricas de generalização.
- O upload com a coluna de alvo é recusado: a tela de inferência não avalia.
- As curvas dependem do artefato de probabilidades da rodada; enquanto ele não existir, a tela
  informa "indisponível" em vez de fabricar curvas.
- Trocar a seleção de modelos ou o lote invalida o resultado guardado: o valor antigo deixa de
  ser apresentado como resultado atual.
- Os exemplos são sintéticos. Nenhum registro real de cliente entra nas telas, nas exportações ou
  na evidência.
- A aplicação não treina, não promove, não grava sobre datasets, sobre as métricas oficiais nem
  sobre o `dvc.lock`.

---

## Executar as duas aplicações

Cada aplicação abre em `http://127.0.0.1:8501` por padrão; para rodarem juntas, use portas
distintas:

```bash
# painel operacional da fase 3
uv run --extra observability streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501

# laboratório de modelos
uv run --extra model_lab streamlit run dashboard/app_dev.py --server.address 127.0.0.1 --server.port 8502
```

As duas são processos locais persistentes: abra em terminais separados e interrompa cada um com
`Ctrl+C`.

## Testes

```bash
uv run --extra model_lab pytest tests/test_app_dev.py
uv run --extra model_lab pytest tests/test_drift_snapshot.py
uv run --extra observability pytest tests/test_observability.py
```

Os testes de aplicação usam `streamlit.testing.v1.AppTest` e fixtures locais; não retreinam nem
avaliam o conjunto de teste. Sem o extra `model_lab`, o arquivo de teste é ignorado e o restante
da suíte continua valendo.

O teste operacional percorre estado vazio, controle, drift, rejeição e falha com fixtures locais
e um banco MLflow isolado.
