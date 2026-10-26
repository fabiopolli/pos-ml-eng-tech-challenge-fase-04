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

O `dvc.yaml` encadeia três estágios locais, executados com `uv run dvc repro`:

```text
data/raw (dvc add) -> eda -> prepare -> train
```

| Estágio | Entrada | Saída |
|---|---|---|
| `eda` | CSV bruto | `reports/eda/eda_summary.json`, `reports/figures/eda/` |
| `prepare` | CSV bruto + `eda_summary.json` | `data/processed/{train,validation,test}.csv`, `data/reference/reference.csv` |
| `train` | splits processados | `models/credit_model.joblib`, `reports/metrics.json`, `reports/figures/model/` |

O `prepare` depende do resumo do EDA e confere o SHA-256 do CSV bruto, garantindo que a preparação
só rode após o EDA do mesmo dado. Os parâmetros vêm de `configs/project.yaml`. O DVC declara o CSV
bruto e as saídas de preparação/treino (incluindo o modelo) para versionamento. DagsHub Storage é
o remote planejado; ainda não está configurado em `.dvc/config` neste checkout. Consulte
[`DAGSHUB.md`](DAGSHUB.md) para conexão e configuração local de credenciais.

## Fluxo planejado

1. Aquisição do UCI 350 para `data/raw`.
2. Normalização do esquema e preparação em `data/processed`.
3. Divisão estratificada 70/15/15 e persistência da referência.
4. Validação Pandera antes de treino e inferência.
5. Comparação justa entre Regressão Logística e Random Forest.
6. Serialização do modelo selecionado em `models` e registro no MLflow.
7. Geração reproduzível de lote de produção com drift em duas features.
8. Comparação reference versus production com Evidently e testes estatísticos.
9. Consolidação de métricas e alertas no Streamlit.

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
