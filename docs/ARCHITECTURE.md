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

O `dvc.yaml` encadeia seis estágios locais, executados com `uv run dvc repro`:

```text
data/default of credit card clients.xls -> acquire -> eda -> prepare -> explore -> train -> evaluate
```

| Estágio | Entrada | Saída |
|---|---|---|
| `acquire` | workbook XLS da UCI | `data/raw/default_of_credit_card_clients.csv`, `reports/acquisition_provenance.json` |
| `eda` | CSV bruto | `reports/eda/eda_summary.json` (auditoria estrutural), `reports/figures/eda/` |
| `prepare` | CSV bruto + `eda_summary.json` | `data/processed/{train,validation,test}.csv`, `data/processed/preparation_report.json`, `data/reference/reference.csv` |
| `explore` | `data/processed/train.csv` | `reports/explore/train_exploration.json`, `reports/figures/explore/` |
| `train` | treino + validação | `models/credit_model.joblib`, `models/credit_model_metadata.json`, `reports/metrics.json`, `reports/figures/model/` |
| `evaluate` | modelo congelado + `data/processed/test.csv` | `reports/test_metrics.json` |

Fronteiras que o DAG impõe:

- `acquire` reconstrói o CSV bruto a partir do XLS versionado e falha se os hashes
  esperados divergirem; o bruto tem um único dono (o estágio), sem ponteiro `.dvc` avulso.
- `eda` faz **auditoria estrutural** do bruto; nenhuma relação feature-alvo é calculada.
  `explore` calcula as relações feature-alvo **apenas sobre o treino**.
- `train` é o estágio de **seleção**: valida o contrato antes de qualquer `fit`, ajusta no
  treino, compara na validação e congela o modelo. Ele **não** lê o conjunto de teste.
- `evaluate` é o estágio de **avaliação final**: lê o artefato congelado, confere o hash
  registrado na seleção, valida o lote de teste contra o contrato e só então prevê.

O `prepare` depende do resumo do EDA e confere o SHA-256 do CSV bruto, garantindo que a preparação
só rode após o EDA do mesmo dado. Os parâmetros vêm de `configs/project.yaml`. DagsHub Storage é
o remote planejado; ainda não está configurado em `.dvc/config` neste checkout. Consulte
[`DAGSHUB.md`](DAGSHUB.md) para conexão e configuração local de credenciais.

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
