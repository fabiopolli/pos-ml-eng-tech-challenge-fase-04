# Tech Challenge - Fase 4 | ML Engineering

[![CI](https://github.com/fabiopolli/pos-ml-eng-tech-challenge-fase-04/actions/workflows/ci.yml/badge.svg)](https://github.com/fabiopolli/pos-ml-eng-tech-challenge-fase-04/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/dependencies-uv-DE5FE9)](https://docs.astral.sh/uv/)

Solução local e reproduzível de **Credit Scoring**, com contratos de qualidade de dados,
simulação e detecção de drift, rastreamento de experimentos e documentação de governança.

> **Status atual:** fundação do projeto criada. O pipeline de dados, os modelos e o
> monitoramento ainda serão implementados incrementalmente; nenhum resultado de modelo ou
> drift é alegado nesta versão inicial.

## Equipe e frentes de trabalho

| Integrante | GitHub | Frente inicial |
|---|---|---|
| Fábio Polli | [`fabiopolli`](https://github.com/fabiopolli) | Repositório, arquitetura, CI e integração |
| Willian "Bill" Kopp | [`bill-kopp`](https://github.com/bill-kopp) | Plano técnico e modelagem |
| Denis Barros Melo | [`denisbmelo`](https://github.com/denisbmelo) | Engenharia e qualidade de dados |
| Romario Silva | [`romagrinho`](https://github.com/romagrinho) | Observabilidade, dashboard e integração |

As responsabilidades detalhadas de cada entrega devem ser registradas no GitHub Projects e em
[`docs/CHECKLIST.md`](docs/CHECKLIST.md); a tabela acima é o ponto de partida, não uma limitação
de colaboração.

## Objetivo

Demonstrar como uma fintech pode detectar degradação silenciosa em um modelo de risco de
crédito. O projeto usa o dataset público **UCI Default of Credit Card Clients (ID 350)** e
separa explicitamente dados de referência dos lotes simulados de produção.

O plano detalhado, com 28 entregas distribuídas em quatro semanas, está em
[`plano-de-trabalho-TC4.md`](plano-de-trabalho-TC4.md). O enunciado oficial está em
[`MLET - Tech Challenge - Fase 4.pdf`](MLET%20-%20Tech%20Challenge%20-%20Fase%204.pdf).

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

O conjunto de teste permanece isolado até a avaliação final. Toda transformação aprendida deve
ser ajustada apenas no treino para evitar vazamento de dados.

## Stack definida

| Finalidade | Tecnologia |
|---|---|
| Processamento | Pandas e NumPy |
| Modelagem | Scikit-learn: Regressão Logística e Random Forest |
| Contratos de dados | Pandera |
| Drift | Evidently AI e testes estatísticos |
| Experimentos | MLflow |
| Dashboard | Streamlit |
| Qualidade | Pytest, Ruff e GitHub Actions |

## Arquitetura planejada

```text
UCI 350
  -> aquisição e preparação
  -> contrato Pandera
  -> treino e seleção do modelo
  -> dataset de referência
  -> simulação de lote de produção
  -> contrato + inferência
  -> Evidently/testes estatísticos
  -> MLflow + relatórios
  -> dashboard Streamlit
```

As decisões e fronteiras entre componentes estão em [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Contratos, drift e observabilidade

### Contrato de dados

O Pandera deverá rejeitar o lote antes da inferência quando qualquer regra rígida falhar. O
contrato inicial exige:

- identificador único no lote;
- `LIMIT_BAL` positivo;
- `AGE` entre 18 e 100 anos;
- ausência de nulos nas features obrigatórias.

### Cenário de drift

O lote de produção será derivado de um conjunto independente e terá mudanças reproduzíveis em
`LIMIT_BAL` e `PAY_AMT1`, respeitando o contrato. Evidently e testes como KS/PSI compararão
referência e produção. Alterar features mantendo rótulos originais demonstra **Data Drift**;
isso não será apresentado como prova automática de Concept Drift ou perda real de performance.

### Sinais operacionais mínimos

- status e duração da última execução;
- registros processados e rejeitados;
- métricas e versão do modelo selecionado;
- quantidade de features com drift e resultados estatísticos;
- distribuição das probabilidades previstas;
- alertas de contrato, execução e drift.

## Estrutura

```text
configs/                 configuração versionada do experimento
dashboard/               aplicação Streamlit
data/                    zonas raw, processed, reference e production
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
uv sync --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

O dashboard inicial já pode ser aberto; os dados reais serão conectados na Etapa 3:

```bash
uv run streamlit run dashboard/app.py
```

### Convenções locais

```bash
# Ativar o MLflow local quando a Etapa 3 estiver implementada
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
| Fundação do repositório | Concluída | Estrutura, dependências, CI, testes e documentação inicial |
| Aquisição e EDA | Pendente | Diretórios e configuração preparados |
| Modelos e Data Contract | Pendente | Contratos arquiteturais definidos |
| Simulação e relatório de drift | Pendente | Cenário inicial documentado |
| MLflow e Streamlit | Em preparação | Shell do dashboard criada |
| Governança e vídeo | Em preparação | Documento-base e roteiro de entregas |

## Fluxo de colaboração

- branch: `<tipo>/<integrante>/<descricao-curta>`;
- commits semânticos e focados;
- PR com evidências, comandos de validação e impacto no checklist;
- revisão de outro integrante;
- dados, modelos e execuções locais fora do Git.

Consulte [`CONTRIBUTING.md`](CONTRIBUTING.md) e [`AGENTS.md`](AGENTS.md) antes de iniciar uma
tarefa.

## Dados e privacidade

Dados brutos, processados, lotes de produção, modelos e execuções locais não devem ser
versionados. Somente documentação, código, configurações e pequenas evidências não sensíveis
podem entrar no Git. O plano de governança será consolidado em
[`docs/GOVERNANCE.md`](docs/GOVERNANCE.md) e resumido aqui antes da entrega.

## Escopo deliberadamente excluído

Para concentrar o trabalho nos critérios de avaliação, esta fase não prevê API em tempo real,
cloud, Kubernetes, Airflow, banco dedicado, filas, AutoML, redes neurais, alertas externos ou
retreinamento automático.

## Documentação

- [`plano-de-trabalho-TC4.md`](plano-de-trabalho-TC4.md): plano técnico das quatro semanas.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): fluxo, componentes e decisões de escopo.
- [`docs/CHECKLIST.md`](docs/CHECKLIST.md): 28 entregas e suas evidências.
- [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md): base para LGPD, viés, retenção e causalidade.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): convenções de colaboração e qualidade.

