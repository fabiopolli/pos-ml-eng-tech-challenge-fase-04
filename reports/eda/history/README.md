# Histórico contaminante do EDA

`eda_summary_contaminated_2026-10-26.json` é o resumo do EDA executado antes da entrega 1.2
da Fase 1. Ele **não** é um resultado válido para decide modelagem.

## Por que está aqui

Naquela execução, `src/credit_monitoring/eda.py` calculava relações entre features e alvo
sobre o **bruto completo de 30.000 linhas**, incluindo as linhas que a preparação posterior
atribuiria ao conjunto de teste:

- `top_target_correlations`: correlação de Pearson de cada uma das 19 features financeiras com
  `default_payment_next_month`, calculada nas 30.000 linhas do bruto;
- taxa de default por grupo demográfico (`SEX`, `EDUCATION`, `MARRIAGE`) e por faixa de `AGE`,
  também nas 30.000 linhas;
- as figuras `02_categorical_default_rate.png`, `03_age.png`, `04_pay_status.png`,
  `08_correlation_heatmap.png` e `09_target_correlation.png` mostravam as mesmas relações.

As figuras não foram versionadas (o diretório `reports/figures/` é ignorado pelo Git); o JSON
foi, e é preservado aqui apenas como registro histórico marcado como contaminante.

## Consequência

A seleção de modelo, a escolha de features e a leitura de relações feature-alvo **não podem**
ser apresentadas como Derived exclusivamente do treino. A avaliação final do modelo congelado
na fase 1 é uma **reavaliação sob protocolo congelado**, não uma avaliação intocada. A
declaração formal da exposição está em
[`docs/evidence/fase-1.md`](../../../docs/evidence/fase-1.md) (seção 1.2) e é reproduzida nos
metadados do modelo (`models/credit_model_metadata.json`).

## Mitigação aplicada

A partir da entrega 1.2:

- `src/credit_monitoring/eda.py` faz **auditoria estrutural** do bruto (shape, nulos,
  duplicatas, domínios de códigos, distribuições marginais) e nenhuma relação feature-alvo;
- `src/credit_monitoring/explore.py` (estágio DVC `explore`) calcula as relações
  feature-alvo **apenas sobre `data/processed/train.csv`**;
- `notebooks/01_eda.ipynb` passou a ser a auditoria estrutural e
  `notebooks/02_explore_train.ipynb` a exploração supervisionada no treino.

O histórico não é apagado: a exposição é declarada, não escondida.
