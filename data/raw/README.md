# Dados brutos

Cópia imutável do UCI 350 (`default_of_credit_card_clients.csv`), reconstruída de forma
reproduzível pelo estágio DVC `acquire` a partir do workbook original
`data/default of credit card clients.xls` (5.539.328 B, md5 `c0a9cb828ded9c446574ede877bf1f6e`).

O CSV resultante é saída do estágio `acquire` (`python -m credit_monitoring.data.acquire`):
conversão XLS→CSV com `sheet="Data"`, `header_row=1`, separador `;`, `index=False`,
`lineterminator="\r\n"` e BOM UTF-8, prefixado pela linha `X1..X23;Y`. O script confere os
hashes esperados e falha se houver divergência (`md5 a6ee086d1eafba5566f666b3ff2ed2c9`,
`sha256 1fc7fe04822413cf48d0f5ca974cbe47061b21ea10fa1d114bb56b8feac79358`).

O conteúdo fica no cache local do DVC e, após a configuração do remote, no DagsHub Storage;
o ponteiro e o `dvc.lock` vão para o Git. No checkout atual ainda não há remote configurado.
Para obter os passos de configuração e recuperação, consulte
[`docs/DAGSHUB.md`](../../docs/DAGSHUB.md). Proveniência completa (DOI, licença CC BY 4.0,
atribuição e parâmetros de leitura) em [`docs/DATASET.md`](../../docs/DATASET.md).
