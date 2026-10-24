# Dados processados

Saídas do estágio `prepare` do `dvc.yaml`: `train.csv`, `validation.csv`, `test.csv` (split estratificado
70/15/15, seed 42) e `preparation_report.json` (linhas removidas por regra e taxa do alvo por split).
Regeneráveis com `uv run dvc repro`.

