# Arquitetura inicial

## Princípios

- Execução local, reproduzível e suficiente para os critérios da FIAP.
- Código reutilizável em `src`; notebooks apenas para exploração e comunicação.
- Dados de referência e produção fisicamente separados.
- Validação acontece antes de treino ou inferência.
- Configuração, seeds e ponteiros DVC versionados no Git; conteúdos de dados/modelos ficam fora
  do Git e no remote DagsHub Storage quando aprovados e configurados.
- Evidências distinguem Data Drift de Concept Drift e de degradação de performance.

## Pipeline implementado (DVC)

O `dvc.yaml` encadeia sete estágios locais, executados com `uv run dvc repro`:

```text
data/default of credit card clients.xls (objeto DVC) -> acquire -> eda -> prepare -> explore -> tune -> train -> evaluate
```

| Estágio | Entrada | Saída |
|---|---|---|
| `acquire` | workbook XLS da UCI | `data/raw/default_of_credit_card_clients.csv`, `reports/acquisition_provenance.json` |
| `eda` | CSV bruto | `reports/eda/eda_summary.json` (auditoria estrutural), `reports/figures/eda/` |
| `prepare` | CSV bruto + `eda_summary.json` | `data/processed/{train,validation,test}.csv`, `data/processed/preparation_report.json`, `data/reference/reference.csv` |
| `explore` | `data/processed/train.csv` | `reports/explore/train_exploration.json`, `reports/figures/explore/` |
| `tune` | `data/processed/train.csv` + `configs/optimization.yaml` | `reports/optimization/<exp>/tuning/`, `models/optimization/<exp>/finalists/` |
| `train` | treino + validação + finalistas | `models/credit_model.joblib`, `models/credit_model_metadata.json`, `models/candidates/`, `models/optimization/<exp>/{incumbent,selection}/`, `reports/metrics.json`, `reports/optimization/<exp>/selection/comparison.json`, `reports/figures/model/` |
| `evaluate` | modelo congelado + `data/processed/test.csv` | `reports/test_metrics.json` |

Fronteiras que o DAG impõe:

- `acquire` reconstrói o CSV bruto a partir do workbook original (objeto DVC, fora do Git) e
  falha se os hashes esperados divergirem; o CSV bruto tem um único dono (o estágio), sem
  ponteiro `.dvc` avulso.
- `eda` faz **auditoria estrutural** do bruto; nenhuma relação feature-alvo é calculada.
  `explore` calcula as relações feature-alvo **apenas sobre o treino**.
- `tune` é a campanha de otimização do plano 1.6: lê **somente** `train.csv`, executa
  controles, busca, uma ablação e a checagem de estabilidade, e **congela um finalista por
  algoritmo**. Não conhece a validação nem o teste.
- `train` é o estágio de **seleção**: valida o contrato antes de qualquer `fit`, ajusta no
  treino, compara na validação e congela o modelo. Ele **não** lê o conjunto de teste. Com a
  campanha habilitada, a rodada de validação inclui o RF vigente (incumbente) e os dois
  finalistas, e a decisão segue os critérios pré-declarados em `configs/optimization.yaml`.
- `evaluate` é o estágio de **avaliação final**: lê o artefato congelado, confere o hash
  registrado na seleção, valida o lote de teste contra o contrato e só então prevê.

Cada saída tem um único dono: `models/credit_model.joblib` pertence a `train`, e os
artefatos da campanha ficam isolados em `models/optimization/<experiment_id>/`. O relatório
de comparação (`reports/optimization/<experiment_id>/selection/comparison.json`) é escrito
pelo estágio de seleção **antes** de qualquer execução de teste.

O `prepare` depende do resumo do EDA e confere o SHA-256 do CSV bruto, garantindo que a preparação
só rode após o EDA do mesmo dado. Os parâmetros vêm de `configs/project.yaml`. DagsHub Storage é
o remote planejado; ainda não está configurado em `.dvc/config` neste checkout. Consulte
[`DAGSHUB.md`](DAGSHUB.md) para conexão e configuração local de credenciais.

## Campanha de otimização dos modelos (plano 1.6)

A campanha é um recorte **limitado** do plano 1.6, executado antes do aceite integrado da
fase 2. Ela é descrita por `configs/optimization.yaml` (protocolo congelado) e por
`src/credit_monitoring/models/`:

| Módulo | Responsabilidade |
|---|---|
| `models/tune.py` | estágio `tune`: controles, busca no treino, uma ablação financeira, checagem de estabilidade e congelamento dos finalistas |
| `models/features.py` | transformador serializável das três razões financeiras (opcional, interno ao pipeline) |
| `models/metrics.py` | métricas compartilhadas entre seleção, campanha e avaliação |
| `models/promotion.py` | rodada única de validação, bootstrap pareado e decisão `promote`/`keep_current` |
| `models/inference.py` | serviço local de inferência: validação integral do lote, seleção das 19 entradas e `predict_proba` |
| `models/lab.py` | catálogo somente leitura dos artefatos exibidos pelo laboratório |

Regras estruturais:

- a campanha lê **somente** `data/processed/train.csv`; não existe caminho de código que abra
  `validation.csv` ou `test.csv`;
- scaler e razões financeiras são passos do `Pipeline` e são ajustados **dentro** de cada fold;
- os cinco folds são os mesmos para todos os candidatos e controles
  (`StratifiedKFold(5, shuffle=True, random_state=42)`);
- o número de ajustes é limitado pelo orçamento declarado em `configs/optimization.yaml`;
- falhas são registradas, nunca viram score zero e nunca saem da contagem de tentativas;
- a decisão é gravada em `reports/optimization/<experiment_id>/selection/comparison.json`
  **antes** de qualquer execução de teste.

O **laboratório de modelos** (`dashboard/app_dev.py`) é uma aplicação Streamlit local de
inspeção, comparação e teste dos artefatos congelados. Ela não treina, não promove, não
escreve sobre datasets, métricas oficiais ou `dvc.lock`, e nunca expõe o conjunto de teste.
O painel operacional da fase 3 (`dashboard/app.py`) continua com a observabilidade do pipeline.
Ver [`dashboard/README.md`](../dashboard/README.md).

## Contrato de dados

`src/credit_monitoring/contracts/` define os esquemas Pandera rotulado e de inferência, lidos do
bloco `contract:` de `configs/project.yaml`. A rejeição é **integral**: um lote operacional
inválido é recusado por inteiro, com diagnóstico por regra, coluna e contagem, sem remover
linhas e sem imprimir valores de registro. A limpeza histórica de `prepare.py` é distinta e
não pode ser usada como filtro de lote operacional.


## Fluxo planejado

1. Aquisição do UCI 350 para `data/raw`.
2. Normalização do esquema e preparação em `data/processed`.
3. Divisão estratificada 70/15/15, seed 42, IDs disjuntos e referência = treino sem alterações.
4. Validação Pandera antes de treino e inferência.
5. Ajuste no treino, comparação na validação, congelamento das decisões e teste do escolhido.
6. Serialização em `models`, versionamento DVC/DagsHub e rastreamento local no MLflow na fase 3.
7. Cópia das features da validação para produção original, mais cópia modificada em duas features;
   sem reutilizar o teste ou compartilhar IDs com a referência. A validação já foi usada na seleção.
8. Contrato antes da inferência e comparação da referência com controle/original e modificada,
   com métodos, intensidades e limiares fixados antes do aceite.
9. Consolidação de métricas, consumo local de recursos e alertas no Streamlit, por execução.

Este fluxo é requisito de planejamento: os estágios de produção, drift e observabilidade ainda
precisam ser implementados. A revisão da fase 1 **registrou** a exposição prévia do teste (o EDA
histórico calculou relações feature-alvo sobre as 30.000 linhas do bruto) e separou a exploração
supervisada no treino; a avaliação final é uma reavaliação sob protocolo congelado, não uma
avaliação intocada. Ver [`evidence/fase-1.md`](evidence/fase-1.md) e
[`reports/eda/history/`](../reports/eda/history/README.md).

## Componentes previstos

| Componente | Responsabilidade |
|---|---|
| `data` | aquisição, normalização, split e simulação |
| `contracts` | esquema Pandera e rejeição de lotes inválidos |
| `models` | pipelines de treino, avaliação, seleção e inferência |
| `monitoring` | drift, métricas operacionais, logs e alertas |
| `dashboard` | leitura e apresentação dos artefatos de observabilidade |
| DVC + DagsHub Storage | versionamento/reprodução de datasets e modelos; GitHub guarda os ponteiros, DagsHub os objetos |

O projeto não inclui API em tempo real, infraestrutura própria de cloud/compute, Kubernetes,
Airflow, filas, banco dedicado ou retreinamento automático. DagsHub Storage é a exceção de
armazenamento remoto; o processamento e treinamento continuam locais.
