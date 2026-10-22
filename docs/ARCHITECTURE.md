# Arquitetura inicial

## Princípios

- Execução local, reproduzível e suficiente para os critérios da FIAP.
- Código reutilizável em `src`; notebooks apenas para exploração e comunicação.
- Dados de referência e produção fisicamente separados.
- Validação acontece antes de treino ou inferência.
- Configuração e seeds versionadas; dados e artefatos pesados ficam fora do Git.
- Evidências distinguem Data Drift de Concept Drift e de degradação de performance.

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

O projeto não inclui API em tempo real, cloud, Kubernetes, Airflow, filas, banco dedicado ou
retreinamento automático.

