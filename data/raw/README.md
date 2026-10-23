# Dados brutos

Cópia imutável do UCI 350 (`default_of_credit_card_clients.csv`). O arquivo é versionado com DVC:
o ponteiro `default_of_credit_card_clients.csv.dvc` vai para o Git e o CSV fica no cache local do DVC.
Não há remote DVC configurado; para recuperar o dado, coloque o CSV nesta pasta e rode
`uv run dvc status` para conferir o hash. Colunas descritas em [`docs/DATASET.md`](../../docs/DATASET.md).

