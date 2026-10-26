# Dataset: Default of Credit Card Clients

Fonte: UCI Machine Learning Repository (ID 350). Arquivo local: `data/raw/default_of_credit_card_clients.csv`
(30.000 linhas, 25 colunas, separador `;`), reconstruído pelo estágio DVC `acquire` e
versionado com DVC.

## Proveniência e atribuição

| Item | Valor |
|---|---|
| Repositório | UCI Machine Learning Repository, dataset ID 350 |
| Arquivo original | `data/default of credit card clients.xls` (5.539.328 B) — **versionado pelo DVC**, não pelo Git (ponteiro `data/default of credit card clients.xls.dvc`) |
| md5 do XLS | `c0a9cb828ded9c446574ede877bf1f6e` |
| DOI | [10.24432/C55S3H](https://doi.org/10.24432/C55S3H) |
| Licença | CC BY 4.0 (Creative Commons Attribution 4.0 International) |
| Atribuição exigida | Yeh, I. (2009). *Default of Credit Card Clients* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C55S3H |
| Período dos dados | Pagamentos de abril a setembro de 2005 (Taiwan); valores monetários em NT$ |

A licença CC BY 4.0 permite compartilhamento e adaptação, com crédito apropriado. A
atribuição acima deve acompanhar qualquer redistribuição do CSV, dos artefatos derivados
ou dos relatórios que os reaproveitem.

### Conversão XLS→CSV

A UCI distribui o original em XLS; o projeto consome um CSV. A conversão é um **estágio
versionado** (`python -m credit_monitoring.data.acquire`), não um passo manual: sem o
script não existe CSV com proveniência.

| Parâmetro | Valor |
|---|---|
| Script | `src/credit_monitoring/data/acquire.py` (estágio DVC `acquire`) |
| Planilha lida | `Data` |
| Linha de cabeçalho | `header_row=1` (a linha 0 é `X1..X23;Y`, descartada) |
| Separador | `;` |
| `index` | `False` |
| Terminador de linha | `\r\n` |
| Codificação | UTF-8 com BOM (`utf-8-sig`) |
| Linha de placeholder | `;X1;X2;…;X23;Y` |

O script confere os hashes esperados e **falha com erro explícito** se houver divergência:

| Artefato | md5 | sha256 |
|---|---|---|
| `data/default of credit card clients.xls` (objeto DVC) | `c0a9cb828ded9c446574ede877bf1f6e` | `63c47faa4cf5e224c3494cd5f776721bcdc4a374ecf16665632f3afab8f38a44` |
| `data/raw/default_of_credit_card_clients.csv` | `a6ee086d1eafba5566f666b3ff2ed2c9` | `1fc7fe04822413cf48d0f5ca974cbe47061b21ea10fa1d114bb56b8feac79358` |

> O workbook original saiu do Git e passou a ser objeto do DVC (decisão da equipe em 2026-10-26,
> durante a fase 1). Um clone novo precisa de `uv run dvc pull -r dagshub` para obter a fonte —
> ver [`DAGSHUB.md`](DAGSHUB.md).

O registro gerado pela aquisição fica em `reports/acquisition_provenance.json` (versionado no
Git), com os hashes das duas fontes e todos os parâmetros de leitura. Os hashes esperados
estão em `configs/project.yaml` (`dataset.acquisition`), como fonte única de verdade.

> Os valores esperados no `configs/project.yaml` foram conferidos contra a página oficial do
> dataset em 2026-10-26 (DOI, licença, arquivo e tamanho). Qualquer alteração do XLS ou da
> receita de conversão invalida a via e exige revisar a decisão de proveniência.

## Descrição

Pesquisa sobre pagamentos inadimplentes de clientes em Taiwan que compara a acurácia preditiva da
probabilidade de default entre seis métodos de mineração de dados. Do ponto de vista de gestão de
risco, a probabilidade estimada de default é mais valiosa que o resultado binário
(cliente confiável ou não). Como a probabilidade real é desconhecida, o estudo propõe o *Sorting
Smoothing Method* para estimá-la: com a probabilidade real como resposta (Y) e a probabilidade
prevista como variável independente (X), a regressão linear simples (Y = A + BX) mostrou que a
rede neural obteve o maior coeficiente de determinação, com intercepto (A) próximo de zero e
coeficiente (B) próximo de um. Entre as seis técnicas, a rede neural foi a única capaz de estimar
com precisão a probabilidade real de default.

> Texto original (inglês) em *Additional Information* da página do dataset na UCI.

## Variáveis

A variável resposta é binária: pagamento em default (Sim = 1, Não = 0). São 23 variáveis
explicativas. O CSV traz uma primeira linha `X1..X23;Y`, descartada na leitura, e uma segunda linha
com os nomes reais, usados no projeto.

| Original | Coluna | Descrição |
|---|---|---|
| - | `ID` | Identificador do cliente |
| X1 | `LIMIT_BAL` | Crédito concedido (NT$), individual e familiar (suplementar) |
| X2 | `SEX` | 1 = masculino; 2 = feminino |
| X3 | `EDUCATION` | 1 = pós-graduação; 2 = universidade; 3 = ensino médio; 4 = outros |
| X4 | `MARRIAGE` | 1 = casado; 2 = solteiro; 3 = outros |
| X5 | `AGE` | Idade (anos) |
| X6 a X11 | `PAY_0`, `PAY_2` a `PAY_6` | Status de pagamento de setembro (X6) a abril (X11) de 2005 |
| X12 a X17 | `BILL_AMT1` a `BILL_AMT6` | Valor da fatura (NT$) de setembro (X12) a abril (X17) de 2005 |
| X18 a X23 | `PAY_AMT1` a `PAY_AMT6` | Valor pago no mês anterior (NT$) de setembro (X18) a abril (X23) de 2005 |
| Y | `default_payment_next_month` | Alvo: 1 = default; 0 = adimplente (no CSV: `default payment next month`) |

Escala do status de pagamento (`PAY_*`) segundo a documentação: -1 = pago em dia; 1 = atraso de um
mês; 2 = atraso de dois meses; ...; 8 = oito meses; 9 = nove meses ou mais. A coluna `PAY_0`
corresponde a "PAY_1" (setembro) e mantém esse nome no arquivo.

Uso no projeto (ver `configs/project.yaml`):

- **Features do modelo (19):** `LIMIT_BAL`, `PAY_0`, `PAY_2` a `PAY_6`, `BILL_AMT1` a `BILL_AMT6` e
  `PAY_AMT1` a `PAY_AMT6`.
- **Governança (fora do modelo):** `SEX`, `EDUCATION`, `MARRIAGE` e `AGE`, reservadas a análises
  agregadas de qualidade e viés.

## Observações da exploração

Detalhes em `notebooks/01_eda.ipynb` e `reports/eda/eda_summary.json`.

- Sem nulos, sem linhas duplicadas e sem `ID` repetido; alvo com cerca de 22,1% de default.
- Códigos fora da documentação: `EDUCATION` 0, 5 e 6; `MARRIAGE` 0; `PAY_*` com -2 e 0 (muito
  frequentes). Eles são preservados, não recodificados.
- `BILL_AMT1..6` contém valores negativos (crédito na fatura) e as colunas monetárias têm cauda longa.
