# Tech Challenge - Fase 4 | ML Engineering

[![CI](https://github.com/fabiopolli/pos-ml-eng-tech-challenge-fase-04/actions/workflows/ci.yml/badge.svg)](https://github.com/fabiopolli/pos-ml-eng-tech-challenge-fase-04/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/dependencies-uv-DE5FE9)](https://docs.astral.sh/uv/)

Solução local e reproduzível de **Credit Scoring**, com contratos de qualidade de dados,
simulação e detecção de drift, rastreamento de experimentos e documentação de governança.

> **Status atual:** Fase 1 (validação de dados e contratos) implementada e verificada localmente
> na branch `fase-1-bill`: aquisição versionada do bruto, auditoria estrutural, preparação
> auditada, contrato Pandera integrado antes do treino, dois modelos comparados na validação,
> modelo congelado e avaliação final em estágio separado. Simulação de drift e observabilidade
> ainda serão implementadas; nenhum resultado de drift é alegado nesta versão. A recuperação dos
> objetos no DagsHub continua pendente de autorização — ver
> [`docs/evidence/fase-1.md`](docs/evidence/fase-1.md).

## Equipe e frentes de trabalho

| Integrante | GitHub | Frente inicial |
|---|---|---|
| Fábio Polli | [`fabiopolli`](https://github.com/fabiopolli) | Repositório, arquitetura, CI e integração |
| Willian "Bill" Kopp | [`bill-kopp`](https://github.com/bill-kopp) | Plano técnico e modelagem |
| Denis Barros Melo | [`denisbmelo`](https://github.com/denisbmelo) | Engenharia e qualidade de dados |
| Romario Silva | [`romagrinho`](https://github.com/romagrinho) | Observabilidade, dashboard e integração |

O detalhamento de cada entrega fica em [`docs/CHECKLIST.md`](docs/CHECKLIST.md); a tabela acima é
o ponto de partida para a organização do trabalho em grupo.

## Objetivo

Demonstrar validação de dados, detecção de alterações de distribuição e monitoramento de um
modelo de risco de crédito em um cenário hipotético de fintech. O projeto usa o dataset público
**UCI Default of Credit Card Clients (ID 350)** e separa dados de referência dos lotes simulados
de produção; drift sintético não comprova perda real de desempenho.

O plano detalhado, com 28 entregas distribuídas em quatro semanas, está em
[`docs/plans/plano-de-trabalho-TC4.md`](docs/plans/plano-de-trabalho-TC4.md). O enunciado oficial
está em [`docs/plans/MLET - Tech Challenge - Fase 4.pdf`](docs/plans/MLET%20-%20Tech%20Challenge%20-%20Fase%204.pdf).

O plano geral também indexa os [quatro planos de execução agêntica](docs/plans/plano-de-trabalho-TC4.md#planos-de-execução-por-etapa),
com pacotes por ID, dependências, interfaces, verificações e transferência entre fases.

## Critérios oficiais

| Critério | Peso | Evidência mínima esperada |
|---|---:|---|
| Validação de Dados | 25% | Contrato com pelo menos três regras e lote inválido bloqueado |
| Detecção de Drift | 25% | Duas distribuições alteradas e relatório estatístico claro |
| Observabilidade e Logs | 20% | Métricas, logs, alertas e visualização do pipeline/modelo |
| Governança (LGPD) | 15% | Privacidade, base legal, retenção, riscos e mitigação |
| Vídeo STAR | 15% | Demonstração técnica objetiva com até cinco minutos |

## Dataset e estratégia de modelagem

O **Default of Credit Card Clients**, publicado pela UCI, possui 30.000 registros, 23
variáveis preditoras e alvo binário de inadimplência no mês seguinte. A configuração canônica
fica em [`configs/project.yaml`](configs/project.yaml).

- **Preditores iniciais:** 19 variáveis financeiras de limite, atraso, fatura e pagamento.
- **Governança:** sexo, escolaridade, estado civil e idade ficam fora do modelo inicial e são
  preservados para análises agregadas de qualidade e viés.
- **Split:** treino 70%, validação 15% e teste 15%, de forma estratificada e com seed fixa.
- **Baseline:** Regressão Logística com pré-processamento em pipeline.
- **Candidato:** Random Forest com parâmetros simples e controle de overfitting.
- **Seleção:** ROC-AUC como métrica principal; precision, recall, F1, accuracy e matriz de
  confusão como evidências complementares.

O protocolo planejado reserva o teste para avaliar apenas o modelo escolhido após congelar as
decisões. Toda transformação aprendida deve ser ajustada no treino. **Limitação registrada:** o
EDA executado antes da fase 1 calculou correlações com o alvo no bruto completo, incluindo as
linhas do conjunto de teste. A exposição está declarada em
[`docs/evidence/fase-1.md`](docs/evidence/fase-1.md) (seção 1.2.1) e o artefato histórico ficou
preservado em `reports/eda/history/`. A partir da fase 1, a exploração que orienta modelagem é
calculada **somente sobre o treino**, a seleção e a avaliação final são estágios separados e o
estágio de treino não lê o conjunto de teste. A avaliação final é, portanto, uma reavaliação
sob protocolo congelado — não uma avaliação intocada.

## Stack definida

| Finalidade | Tecnologia |
|---|---|
| Processamento | Pandas e NumPy |
| Modelagem | Scikit-learn: Regressão Logística e Random Forest |
| Contratos de dados | Pandera |
| Drift | Evidently AI e testes estatísticos |
| Experimentos | MLflow |
| Dashboard | Streamlit |
| Versionamento de datasets e modelos | DVC + DagsHub Storage |
| Qualidade | Pytest, Ruff e GitHub Actions |

O DVC rastreia dados e artefatos do pipeline; seus ponteiros e metadados ficam no GitHub,
enquanto os objetos ficam no DagsHub Storage. O remote ainda precisa ser configurado para o
repositório DagsHub do projeto. Veja [`docs/DAGSHUB.md`](docs/DAGSHUB.md); não coloque tokens ou
credenciais em arquivos versionados.

## Arquitetura planejada

```text
UCI 350 (XLS, objeto DVC)
  -> aquisição versionada (hash conferido) -> CSV bruto
  -> auditoria estrutural do bruto
  -> preparação + split 70/15/15 + referência = treino
  -> explorationsupervisionada no treino
  -> contrato Pandera antes do treino
  -> treino + seleção na validação -> modelo congelado
  -> avaliação do escolhido no teste (estágio separado)
  -> produção original = features da validação + cópia com drift
  -> contrato + inferência + Evidently (controle e lote alterado)
  -> MLflow local + relatórios -> dashboard Streamlit
  -> laboratório Streamlit de comparação e teste dos modelos (plano 1.6)

Datasets/modelo <-> cache DVC <-> DagsHub Storage
Código, parâmetros, ponteiros e dvc.lock -> GitHub
```

As decisões e fronteiras entre componentes estão em [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Contratos, drift e observabilidade

### Contrato de dados

O contrato Pandera está **implementado** (`src/credit_monitoring/contracts/`) e é aplicado antes
de qualquer ajuste de modelo e antes de qualquer inferência. Um lote que viola uma regra rígida
é **rejeitado por inteiro**, com diagnóstico por regra, coluna e contagem — sem remover linhas e
sem imprimir valores de registro. As regras vêm do bloco `contract:` de `configs/project.yaml`:

- identificador único no lote;
- `LIMIT_BAL` positivo;
- `AGE` entre 18 e 100 anos;
- ausência de nulos nas features obrigatórias;
- presença e tipo de todas as colunas; alvo binário obrigatório no esquema rotulado.

O contrato de inferência não exige alvo. ID e atributos de governança ficam disponíveis ao
contrato, mas não entram como preditores. A preparação histórica documenta remoções; um lote
operacional inválido é rejeitado inteiro antes do modelo, sem limpeza silenciosa. Faturas
negativas e códigos de pagamento não documentados permanecem aceitos: são fatos documentados da
fonte, não defeitos.

Validação pontual de um lote:

```bash
uv run credit-monitoring-validate --input <lote.csv>            # rotulado
uv run credit-monitoring-validate --input <lote.csv> --inference # sem alvo
```

Saída `0` (aceito) ou `2` (rejeitado, com o diagnóstico em JSON).

### Cenário de drift

A referência é a cópia do treino. Após congelar a seleção, as features da validação originam
o lote de produção original e uma cópia com mudanças em `LIMIT_BAL` e `PAY_AMT1`. Esses lotes
não compartilham IDs com a referência e não usam o teste; a validação reutilizada não constitui
novo holdout de desempenho. Comparar referência com original (controle) e modificada sob
métodos/limiares registrados antes do aceite, respeitando o contrato.

Alterar features mantendo rótulos originais demonstra **Data Drift**; isso não prova Concept
Drift ou perda real de performance. O enunciado cita Concept Drift no contexto, mas não o detalha
na rubrica: a interpretação deve ser confirmada com a docência, conforme a pendência no plano.

### Sinais operacionais mínimos

- status e duração da última execução;
- registros processados e rejeitados;
- contagem de falhas/alertas, tempo de CPU e pico de memória do processo, com unidades;
- métricas e versão do modelo selecionado;
- quantidade de features com drift e resultados estatísticos;
- distribuição das probabilidades previstas;
- alertas de contrato, execução e drift.

## Estrutura

```text
configs/                 configuração versionada do experimento
dashboard/               aplicação Streamlit
data/                    zonas raw, processed, reference, production e test (fixtures)
docs/                    arquitetura, checklist e governança
models/                  artefatos locais ignorados pelo Git
notebooks/               exploração e evidências reproduzíveis
reports/                 relatórios de drift e figuras
scripts/                 pontos de entrada operacionais
src/credit_monitoring/   código reutilizável do projeto
tests/                   testes automatizados
```

## Início rápido

Requer Python 3.12 e [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --dev --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Pipeline de dados e modelo. O bruto é reconstruído a partir do workbook original da UCI pelo
estágio `acquire`, que confere os hashes esperados e falha se divergir. O workbook é um **objeto
DVC**, não um arquivo do Git: em um clone novo ele vem do remote com `uv run dvc pull -r dagshub`
(ver [`data/raw/README.md`](data/raw/README.md) e [`docs/DATASET.md`](docs/DATASET.md)):

```bash
uv run dvc repro      # acquire -> eda -> prepare -> explore -> tune -> train -> evaluate
uv run dvc dag        # ordem dos estágios
uv run dvc metrics show
```

O notebook [`notebooks/01_eda.ipynb`](notebooks/01_eda.ipynb) apresenta a auditoria estrutural
do bruto e [`notebooks/02_explore_train.ipynb`](notebooks/02_explore_train.ipynb) a exploração
supervisionada restrita ao treino; a descrição do dataset está em
[`docs/DATASET.md`](docs/DATASET.md).

### Campanha de otimização dos modelos (plano 1.6)

O estágio `tune` executa a campanha limitada descrita em
[`docs/plans/1.6-otimizacao-modelos.md`](docs/plans/1.6-otimizacao-modelos.md): controles,
busca de hiperparâmetros, uma ablação de razões financeiras e a checagem de estabilidade do
Random Forest, **somente sobre o conjunto de treino**. O estágio `train` recebe os finalistas
congelados, roda a rodada única de validação e registra a decisão `promote` ou `keep_current`
antes de qualquer avaliação de teste.

```bash
uv run dvc repro tune    # campanha: só o treino é lido
uv run dvc repro train   # rodada de validação e decisão
uv run dvc repro evaluate # avaliação final do modelo efetivamente publicado
```

O protocolo (folds, sementes, orçamento, critérios e lista de trials) fica congelado em
`configs/optimization.yaml`; o manifesto com hashes, versões e a lista efetiva de trials é
gravado em `reports/optimization/<experiment_id>/tuning/manifest.json` **antes** dos
resultados. A decisão congelada fica em
`reports/optimization/<experiment_id>/selection/comparison.json`, e a evidência textual em
[`docs/evidence/1.6-otimizacao-modelos.md`](docs/evidence/1.6-otimizacao-modelos.md).

### Laboratório de modelos

Aplicação local (`dashboard/app_dev.py`) para **inspecionar, comparar e testar** os modelos
congelados: o publicado, os dois controles serializados e os finalistas da campanha do plano
1.6. Ela não treina, não promove, não avalia o conjunto de teste e não altera datasets,
métricas oficiais nem o `dvc.lock`. O painel operacional da fase 3 (`dashboard/app.py`) é outra
aplicação, destinada à observabilidade do pipeline.

**Pré-requisitos:** Python 3.12, [`uv`](https://docs.astral.sh/uv/) e os artefatos locais do
modelo e da campanha (`models/credit_model.joblib`, `models/candidates/`,
`models/optimization/<experiment_id>/` e `reports/optimization/<experiment_id>/selection/`). Em
um clone novo, eles vêm do remote com `uv run dvc pull -r dagshub` (ver
[`docs/DAGSHUB.md`](docs/DAGSHUB.md)) ou são reconstruídos pelo pipeline; sem eles, a aplicação
abre e informa quais artefatos estão indisponíveis.

**Instalação e execução** (o processo abre apenas em `127.0.0.1`):

```bash
uv sync --dev --locked --extra model_lab
uv run --extra model_lab streamlit run dashboard/app_dev.py --server.address 127.0.0.1
```

Acesse `http://127.0.0.1:8501` (use `--server.port <n>` para outra porta e `--server.headless
true` sem abrir o navegador). Para encerrar, interrompa o comando no terminal (`Ctrl+C`). O extra
`model_lab` instala apenas o Streamlit: o ambiente padrão de treino continua sem ele.

**Roteiro de uso**

1. **Barra lateral — "Modelos para comparar".** Selecione dois ou mais artefatos para a
   comparação. A seleção inicial é o modelo **vigente**, marcado pela decisão registrada da
   campanha, não por um botão de promoção. Os expanders de "Rastreabilidade" mostram algoritmo,
   versão, papel, `candidate_id`, `experiment_id`, SHA-256, número de features e limiar de cada
   artefato; artefatos ausentes ou com hash divergente aparecem como indisponíveis, com o motivo.
2. **Aba "Artefatos e prontidao".** Confirme a disponibilidade de modelo, manifesto, contrato e
   relatório, e abra os expanders de manifesto, decisão congelada e contrato de dados.
3. **Aba "Comparacao dos modelos".** Tabela lado a lado da **rodada única de validação** da
   campanha (ROC-AUC, average precision, precision, recall, F1, accuracy, Brier, delta contra o
   RF vigente e limites do intervalo pareado), matrizes de confusão por modelo, a **decisão
   congelada** (`promote` ou `keep_current`) com os critérios de cada finalista, e as **curvas
   ROC/PR** da rodada com a distribuição das probabilidades. Todos os números vêm do relatório
   congelado (`comparison.json`): a aplicação não recalcula avaliações e não mistura a média de
   CV com a métrica de validação. Sem o artefato de probabilidades da rodada, a tela informa
   "indisponível" em vez de fabricar curvas.
4. **Aba "Predicao" — painel "Registro individual".** Preencha o ID, as 19 features financeiras e
   os quatro atributos de governança e clique em **"Pontuar o registro"**. O resultado traz a
   probabilidade de inadimplência, a classe no limiar `0.5` e as divergências entre os modelos
   selecionados. Um registro isolado produz **previsões**, nunca métricas de generalização.
5. **Aba "Predicao" — painel "Lote CSV".** Envie um CSV **sem a coluna de alvo** e clique em
   **"Pontuar o lote nos modelos selecionados"**. O lote é validado por inteiro antes de
   qualquer chamada: um lote inválido é recusado com diagnóstico por regra e coluna, com
   **zero chamadas a qualquer modelo**. A saída mostra a probabilidade média, os positivos
   previstos no limiar `0.5`, as divergências entre modelos e a duração local da chamada
   (tempo de inferência nesta máquina, não métrica de qualidade do modelo).
6. **Aba "Cenarios de contrato".** Cinco predefinições sintéticas — lote válido, ID duplicado,
   limite não positivo, idade fora do intervalo e feature nula — cada uma com o resultado
   esperado, o observado e o diagnóstico agregado por regra e coluna.

**Formato do lote de inferência:** colunas canônicas do projeto (`ID`, as 19 features
financeiras e as quatro de governança) e **sem** a coluna de alvo — o upload com alvo é recusado
por ser uma tela de inferência, não de avaliação. Acima de 500 linhas o laboratório avisa o
limite por chamada.

**Lotes prontos para testar:** [`data/test/`](data/test/) traz um lote de 200 linhas, um lote
didático de seis perfis rotulados, um lote que viola o contrato e um lote com coluna de alvo
(recusado no upload). Todos são derivados **apenas** da partição de treino, com IDs novos e
jitter determinístico, e são regeneráveis por
`uv run python scripts/gerar_lotes_teste.py`; a proveniência e os resultados esperados estão
em [`data/test/README.md`](data/test/README.md).

**Limites:** trocar a seleção de modelos ou o lote invalida o resultado guardado, e o valor
antigo deixa de ser apresentado como resultado atual. Os exemplos são sintéticos: nenhum
registro real de cliente entra nas telas, nas exportações ou na evidência. A aplicação não
treina, não promove, não grava sobre datasets, sobre as métricas oficiais nem sobre o
`dvc.lock`.

**Verificação dos testes da aplicação:**

```bash
uv run --extra model_lab pytest tests/test_app_dev.py
```

O roteiro completo, com os estados previstos e a distinção frente ao painel da fase 3, está em
[`dashboard/README.md`](dashboard/README.md); a evidência de execução e de inspeção visual, em
[`docs/evidence/1.6-otimizacao-modelos.md`](docs/evidence/1.6-otimizacao-modelos.md) (§11).

O dashboard inicial já pode ser aberto; a integração de observabilidade e os dados de produção
simulados serão concluídos nas etapas seguintes. `streamlit` e `mlflow` são **extras** e não são
instalados no ambiente padrão — instale o extra da fase 3 antes de usá-los:

```bash
uv sync --dev --locked --extra observability
uv run streamlit run dashboard/app.py
```

### Convenções locais

```bash
# Ativar o MLflow local quando a Etapa 3 estiver implementada
# (requer o extra observability, instalado acima)
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db

# Copiar configurações locais sem versionar segredos
cp .env.example .env
```

No PowerShell, use `Copy-Item .env.example .env` no lugar de `cp` se preferir o comando nativo.

## Etapas e evidências

1. **Validação:** dois modelos comparados e lote inválido bloqueado pelo Pandera.
2. **Drift:** ao menos duas features alteradas e relatório estatístico/HTML gerado.
3. **Observabilidade:** logs, métricas e artefatos rastreados no MLflow e Streamlit.
4. **Governança:** LGPD, causalidade, riscos, mitigação e vídeo STAR de até cinco minutos.

O acompanhamento operacional está em [`docs/CHECKLIST.md`](docs/CHECKLIST.md).

## Estado da implementação

| Entrega | Estado | Evidência atual |
|---|---|---|
| Fundação do repositório e remote | Concluído | `dvc[s3]` e `xlrd` travados; pipeline e `dvc.lock` coerentes; workbook original migrado do Git para o DVC; remote DagsHub configurado, objetos enviados e **recuperação provada em checkout separado** |
| Aquisição, auditoria e preparação | Concluído | Estágios `acquire`/`eda`/`prepare`/`explore`; proveniência com DOI e licença em [`docs/DATASET.md`](docs/DATASET.md); exposição do teste declarada em [`docs/evidence/fase-1.md`](docs/evidence/fase-1.md) |
| Modelos e Data Contract | Concluído | Contrato Pandera integrado antes do `fit`; seleção na validação e avaliação final em estágios separados; [`docs/evidence/fase-1.md`](docs/evidence/fase-1.md) |
| Campanha de otimização (plano 1.6) | Concluído | Estágio `tune` (só treino) + rodada única de validação com decisão registrada; laboratório Streamlit de comparação e teste; [`docs/evidence/1.6-otimizacao-modelos.md`](docs/evidence/1.6-otimizacao-modelos.md) |
| Simulação e relatório de drift | Pendente | Cenário inicial documentado |
| MLflow e Streamlit | Em preparação | Shell do dashboard criada |
| Governança e vídeo | Em preparação | Documento-base e roteiro de entregas |

## Fluxo de colaboração

- branch: `<tipo>/<integrante>/<descricao-curta>`;
- commits semânticos e focados;
- PR com evidências, comandos de validação e impacto no checklist;
- dados, modelos e execuções locais fora do Git.

Consulte [`CONTRIBUTING.md`](CONTRIBUTING.md) e [`AGENTS.md`](AGENTS.md) antes de iniciar uma
tarefa.

## Dados e privacidade

Dados brutos, processados, lotes de produção e modelos não devem ser adicionados diretamente ao
Git. Os dados e modelos autorizados para compartilhamento serão versionados pelo DVC e armazenados
no DagsHub Storage; o GitHub conterá apenas código, configurações, documentação e ponteiros DVC.
A única zona de dados versionada no Git é [`data/test/`](data/test/): fixtures de inferência
pequenas (~60 KB), derivadas da partição de treino e com IDs novos, existindo para que um
revisor reproduza a demonstração do laboratório sem depender de artefatos DVC — a exceção está
documentada em [`data/test/README.md`](data/test/README.md). Tokens e credenciais permanecem em
configuração local não versionada. Antes de enviar dados ao serviço, confirmar a origem, os
termos de uso e a autorização para armazenamento remoto. O plano de governança será consolidado
em [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md) e resumido aqui antes da entrega.

## Escopo deliberadamente excluído

Para concentrar o trabalho nos critérios de avaliação, esta fase não prevê API em tempo real,
infraestrutura própria de cloud ou compute remoto, Kubernetes, Airflow, banco dedicado, filas,
AutoML, redes neurais, alertas externos ou retreinamento automático. DagsHub Storage é a exceção
planejada para armazenamento remoto versionado de dados e modelos; o treinamento permanece local.

## Documentação

- [`docs/user_guides/README.md`](docs/user_guides/README.md): guias de uso das aplicações —
  começo pelo [laboratório de modelos](docs/user_guides/laboratorio-de-modelos.md).
- [`docs/plans/plano-de-trabalho-TC4.md`](docs/plans/plano-de-trabalho-TC4.md): plano técnico das
  quatro semanas.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): fluxo, componentes e decisões de escopo.
- [`docs/CHECKLIST.md`](docs/CHECKLIST.md): 28 entregas e suas evidências.
- [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md): base para LGPD, viés, retenção e causalidade.
- [`docs/DAGSHUB.md`](docs/DAGSHUB.md): configuração e uso seguro do remote DVC no DagsHub.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): convenções de colaboração e qualidade.
