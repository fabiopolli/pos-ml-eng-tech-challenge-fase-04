# Dataset: Default of Credit Card Clients

Fonte: UCI Machine Learning Repository (ID 350). Arquivo local: `data/raw/default_of_credit_card_clients.csv`
(30.000 linhas, 25 colunas, separador `;`, versionado com DVC).

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
