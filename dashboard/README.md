# Dashboard — painel operacional e laboratório de modelos

Este diretório contém **duas aplicações Streamlit distintas**, com finalidades e fases
diferentes:

| | `dashboard/app.py` (painel operacional) | `dashboard/app_dev.py` (laboratório) |
|---|---|---|
| Fase / recorte | Fase 3 — observabilidade do pipeline | Recorte **1.6-O6** do plano 1.6 |
| Objetivo | observar a saúde do pipeline | inspecionar, comparar e testar modelos congelados |
| Extra de dependências | `observability` (MLflow + Streamlit) | `model_lab` (Streamlit) |
| Estado atual | shell inicial com métricas placeholder; a integração da observabilidade é a entrega **3.5**, ainda pendente | implementado e verificado (**1.6-O6** concluído) |
| Executa inferência | não | sim, sob demanda explícita |
| Lê o conjunto de teste | nunca | nunca |
| Treina ou promove | nunca | nunca |

As duas podem ser executadas no mesmo checkout, em processos e portas separados.

---

## `dashboard/app.py` — painel operacional da fase 3

Aplicação de observabilidade do pipeline. **É o destino da fase 3**: histórico de execuções,
métricas operacionais, alertas e resultados do monitoramento de drift.

### O que existe hoje

[`dashboard/app.py`](app.py) é um **shell inicial de 15 linhas**, e não uma tela de
observabilidade funcional:

- lê **nenhum** artefato — nem `reports/metrics.json`, nem MLflow, nem DVC, nem datasets;
- exibe três `st.metric` com valores fixos, escolhidos no código;
- não executa inferência, não treina, não promove e não lê o conjunto de teste.

A leitura de resumos e do MLflow, a lista de execuções, as métricas operacionais e os alertas
(entregas 3.1–3.7 da fase 3) **ainda não estão implementadas**; o status está em
[`docs/CHECKLIST.md`](../docs/CHECKLIST.md) e o desenho em
[`docs/plans/fase-3-observabilidade-pipelines-modelos.md`](../docs/plans/fase-3-observabilidade-pipelines-modelos.md)
(§3.5). O painel não deve ser apresentado como observabilidade do pipeline enquanto isso não
acontecer.

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

Verificado por execução local em 2026-11-02:

- título **Credit Scoring - Observabilidade**;
- um aviso informando que a fundação do dashboard foi criada e que as métricas de execução,
  qualidade e drift serão conectadas na Etapa 3;
- três métricas **placeholder**: `Status do pipeline` = `Aguardando execução`,
  `Features com drift` = `-`, `Alertas ativos` = `-`.

Não há pré-requisito de artefato: o painel abre em um clone novo, sem `dvc pull`, porque não
lê nada do disco. As três métricas são literais, não medições — leia `-` como *indisponível*,
nunca como zero.

### Limites

- Um rerender não executa o pipeline, não altera dados e não gera alertas.
- Nenhuma linha, ID ou alvo é exibido ou exportado.
- O backend do MLflow é local (`sqlite:///mlflow.db`); a UI do MLflow é um processo separado e
  só tem execuções depois que 3.3 e 3.4 existirem:

  ```bash
  uv run --extra observability mlflow ui --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1
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
```

Os testes de aplicação usam `streamlit.testing.v1.AppTest` e fixtures locais; não retreinam nem
avaliam o conjunto de teste. Sem o extra `model_lab`, o arquivo de teste é ignorado e o restante
da suíte continua valendo.

O shell `dashboard/app.py` **não tem teste automatizado**: ele ainda não implementa a
observabilidade da fase 3 (entrega 3.5), e um teste sobre os placeholders não acrescentaria
evidência sobre o pipeline.
