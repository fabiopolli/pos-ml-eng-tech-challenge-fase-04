# Fixtures de inferência do laboratório de modelos

Lotes de teste para a aba "Predicao" → "Lote CSV" do laboratório
(`dashboard/app_dev.py`, recorte **1.6-O6** do plano 1.6). São **fixtures de teste
liberadas**, não dados de produção nem o split de teste do dataset: o split de
avaliação do modelo é `data/processed/test.csv`, e este diretório existe apenas para
exercitar a tela de inferência e o contrato de lote.

> Esta zona é a **exceção** do repositório à regra de manter dados fora do Git: os
> arquivos abaixo são pequenos (≈ 60 KB), são **derivados** e não brutos, e estão no
> Git para que um revisor reproduza a demonstração sem depender de artefatos DVC.

## Proveniência

| Item | Valor |
|---|---|
| Gerador | [`scripts/gerar_lotes_teste.py`](../../scripts/gerar_lotes_teste.py) (seed 42) |
| Fonte | **apenas** a partição de treino (`data/processed/train.csv`, sha256 `9ebd48b6d31c67f46cc28aff0bde36b48f62936aff0011007b7cb78d26108c26`, 21.000 linhas) |
| Validação e teste | **nunca lidos** |
| IDs | novos e sequenciais (`800001+` e `900001+`): nenhum cliente real é reproduzido |
| Transformação | jitter multiplicativo determinístico de ±2% nas features monetárias; códigos de status (`PAY_*`) e atributos de governança mantidos |
| Coluna de alvo | removida dos lotes de inferência; presente apenas em `lote_com_alvo.csv`, para demonstrar a recusa do upload |
| Manifiesto | [`manifest.json`](manifest.json) com sha256, contagem de linhas e colunas de cada arquivo |
| Atribuição e licença | derivação do dataset público UCI 350 (*Default of Credit Card Clients*, DOI [10.24432/C55S3H](https://doi.org/10.24432/C55S3H), **CC BY 4.0**). Atribuição completa em [`docs/DATASET.md`](../../docs/DATASET.md) |

Regeneração (requer o treino materializado — `uv run dvc repro prepare` ou
`uv run dvc pull -r dagshub`):

```bash
uv run python scripts/gerar_lotes_teste.py
```

## Arquivos

| Arquivo | Linhas | Finalidade |
|---|---:|---|
| `lote_teste_200.csv` | 200 | Lote principal: 6 perfis construídos + 194 linhas do treino com jitter. Formato canônico exato (24 colunas, sem alvo) |
| `lote_perfis_6.csv` | 6 | Os seis perfis com a coluna extra `perfil` (ignorada pelo modelo) para leitura didática |
| `lote_rejeitado.csv` | 4 | Viola quatro regras do contrato: `ID` duplicado, `LIMIT_BAL` = 0, `AGE` = 17, `PAY_AMT1` nulo — demonstra a recusa integral do lote |
| `lote_com_alvo.csv` | 200 | O lote principal com a coluna de alvo — demonstra a recusa do upload com alvo |
| `exemplo_lote_inferencia.csv` | 3 | Lote mínimo para um teste rápido de fumaça |

## Resultados esperados (verificados em 2026-10-26 pelo serviço de inferência)

Com `random_forest` (vigente) e `logistic_regression` (controle) selecionados:

| Modelo | média | mediana | mín | máx | positivos @0,5 | duração local |
|---|---:|---:|---:|---:|---:|---:|
| `random_forest` | 0,4311 | 0,3737 | 0,1490 | 0,9202 | 54 (27,0%) | ~0,04 s |
| `logistic_regression` | 0,4585 | 0,4467 | 0,0091 | 0,9954 | 71 (35,5%) | ~0,01 s |

Divergência: máxima 0,3593; 200 linhas com divergência; **33 linhas com discordância de
classe** (16,5% do lote).

## Limite de interpretação

As linhas vêm do **treino**, então as probabilidades são *in-sample* e otimistas. Para a
leitura honesta de "cliente novo", a referência é a rodada de validação congelada
(4.500 linhas), registrada em
[`docs/evidence/1.6-otimizacao-modelos.md`](../../docs/evidence/1.6-otimizacao-modelos.md)
(§9 e §9.5). A tabela de divergência mede **estabilidade entre modelos**, não qualidade.
