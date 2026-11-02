# Guia de uso — Laboratório de modelos (`dashboard/app_dev.py`)

Guia operacional da aplicação local que permite **inspecionar, comparar e testar** os modelos
congelados do projeto: o modelo publicado, os dois controles serializados e os finalistas da
campanha de otimização (plano 1.6, recorte **1.6-O6**).

Todos os números cited neste guia foram verificados por execução em 2026-10-26 e podem ser
reconferidos com os comandos indicados em cada seção.

---

## 1. O que este laboratório é — e o que não é

| | `dashboard/app_dev.py` (laboratório) | `dashboard/app.py` (fase 3) |
|---|---|---|
| Objetivo | comparar e testar modelos | observar a saúde do pipeline |
| Executa inferência | sim, sob demanda explícita | não |
| Lê o conjunto de teste | nunca | nunca |
| Treina ou promove | nunca | nunca |

O laboratório é **somente leitura**: não treina, não promove, não avalia o conjunto de teste e
não grava sobre datasets, sobre as métricas oficiais nem sobre o `dvc.lock`. Cada comparação é
disparada por botão; um recarregamento da página não repete a operação.

---

## 2. Pré-requisitos

- Python 3.12 e [`uv`](https://docs.astral.sh/uv/);
- os **artefatos locais** do modelo e da campanha:

| Artefato | Caminho | Origem |
|---|---|---|
| Modelo publicado | `models/credit_model.joblib` | estágio DVC `train` |
| Controles serializados | `models/candidates/` | estágio DVC `train` |
| Finalistas da campanha | `models/optimization/<experiment_id>/finalists/` | estágio DVC `tune` |
| Incumbente arquivado | `models/optimization/<experiment_id>/incumbent/` | estágio DVC `train` |
| Relatório congelado | `reports/optimization/<experiment_id>/selection/comparison.json` | estágio DVC `train` |
| Probabilidades da rodada | `models/optimization/<experiment_id>/selection/validation_predictions.csv` | estágio DVC `train` |

Em um clone novo eles vêm do remote com `uv run dvc pull -r dagshub` (ver
[`docs/DAGSHUB.md`](../DAGSHUB.md)) ou são reconstruídos pelo pipeline
(`uv run dvc repro tune && uv run dvc repro train`). Sem eles, a aplicação **abre** e informa
quais artefatos estão indisponíveis, com o motivo.

---

## 3. Executar

```bash
uv sync --dev --locked --extra model_lab
uv run --extra model_lab streamlit run dashboard/app_dev.py --server.address 127.0.0.1
```

- Abra `http://127.0.0.1:8501`. Use `--server.port <n>` para outra porta e `--server.headless
  true` para não abrir o navegador automaticamente.
- O processo escuta **apenas em `127.0.0.1`** — não o exponha em rede.
- Para encerrar, interrompa o comando no terminal (`Ctrl+C`).
- O extra `model_lab` instala apenas o Streamlit: o ambiente padrão de treino continua sem ele,
  e o extra `observability` da fase 3 segue atendendo ao painel operacional.

**Problemas comuns**

| Sintoma | Causa e solução |
|---|---|
| "Nenhum artefato de modelo encontrado" | faltam os artefatos DVC: rode `uv run dvc pull -r dagshub` ou `uv run dvc repro` |
| "Nenhum dos modelos selecionados esta disponivel" | o artefato foi movido ou o hash divergiu: confira a aba "Artefatos e prontidao" e o expander de rastreabilidade |
| Porta 8501 ocupada | use `--server.port 8502` |
| A primeira carga demora alguns segundos | o catálogo e os pipelines são carregados por sessão e recalculados quando os artefatos mudam |

---

## 4. Anatomia da tela

**Barra lateral**

- **"Modelos para comparar"** — seletor múltiplo. A seleção inicial é o modelo **vigente**,
  marcado pela decisão registrada da campanha (não por um botão de promoção).
- **"Rastreabilidade"** — um expander por artefato com algoritmo, versão, papel
  (controle/finalista/vigente), `candidate_id`, `experiment_id`, SHA-256, número de features e
  limiar.
- **"Artefatos indisponiveis"** — lista o que não pôde ser carregado, com o motivo.

**Abas**

1. **Artefatos e prontidao** — disponibilidade, hashes, manifesto, decisão e contrato.
2. **Comparacao dos modelos** — a rodada única de validação, lado a lado.
3. **Predicao** — registro individual e lote CSV.
4. **Cenarios de contrato** — predefinições sintéticas de lote válido e inválido.

---

## 5. Aba "Artefatos e prontidao"

Confirme, antes de qualquer interpretação, **quatro** artefatos: `logistic_regression` (controle),
`random_forest` (controle **e vigente**), `logistic_regression_finalist` (finalista) e
`random_forest_finalist` (finalista).

A coluna **"vigente"** é preenchida pela decisão registrada na campanha — hoje
`keep_current`, com o RF mantido. O finalist do RF tem ROC-AUC de validação **maior** (0,775245
contra 0,774103) e mesmo assim **não** é o vigente, porque o ganho não satisfaz os critérios
pré-declarados (ver §6).

Expanders: **"Manifesto da campanha"**, **"Decisao congelada da campanha"** e **"Contrato de
dados"**.

---

## 6. Aba "Comparacao dos modelos"

Fonte de todos os números: o relatório congelado `comparison.json`. A aplicação **não
recalcula** avaliações, não produz nova rodada e **não** mistura a média de CV com a métrica de
validação.

| Elemento | Como ler |
|---|---|
| Tabela lado a lado | ROC-AUC, average precision, precision, recall, F1, accuracy, Brier, delta de ROC-AUC contra o RF vigente e limites do intervalo pareado, por modelo |
| "Matriz de confusao e intervalo - {modelo}" | contagens no limiar 0,5 e o bootstrap pareado do contraste |
| "Decisao congelada" | `action`, `selected` e a justificativa — aqui `keep_current`: *"Nenhum finalista satisfaz todos os criterios: ganho insuficiente ou inconclusivo. O RF vigente e mantido."* |
| "Criterios - {modelo}" | resultado de cada critério: ganho de validação, ganho de CV, limite inferior do intervalo, estabilidade e integridade |
| Curvas ROC/PR e distribuição de probabilidades | desenhadas a partir das probabilidades **da mesma rodada**; sem o artefato, a tela informa "indisponivel" em vez de fabricar curvas |

Resumo da rodada de validação (4.500 linhas, limiar 0,5):

| Modelo | Papel | ROC-AUC | Average precision | Precision | Recall | F1 | Brier | Matriz (fn/fp/tn/tp) |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `random_forest` | vigente | 0,774103 | 0,545323 | 0,496985 | 0,579899 | 0,535250 | 0,178755 | 418 / 584 / 2921 / 577 |
| `random_forest_finalist` | finalista | 0,775245 | 0,540936 | 0,476457 | 0,600000 | 0,531139 | 0,177954 | 398 / 656 / 2849 / 597 |
| `logistic_regression_finalist` | finalista | 0,714509 | 0,499806 | 0,367690 | 0,638191 | 0,466569 | 0,208521 | 360 / 1092 / 2413 / 635 |

Contrastes contra o RF vigente (bootstrap pareado e estratificado, 2.000 réplicas, seed 42,
intervalo de 97,5% por contraste):

| Contraste | Δ ROC-AUC | IC 97,5% | Réplicas com Δ > 0 |
|---|---:|---|---:|
| `random_forest_finalist` − `random_forest` | **+0,001141** | **[−0,002859; +0,004968]** | 1.421 / 2.000 |
| `logistic_regression_finalist` − `random_forest` | **−0,059595** | **[−0,075027; −0,044677]** | 0 / 2.000 |

O intervalo do finalista RF **inclui zero**: a diferença observada não é distinguível de ruído
nesta validação. Detalhes em
[`docs/evidence/1.6-otimizacao-modelos.md`](../evidence/1.6-otimizacao-modelos.md) (§9).

---

## 7. Aba "Predicao" — painel "Registro individual"

1. Preencha `ID`, as 19 features financeiras e os quatro atributos de governança (§10).
2. **Role até o fim do formulário**: o botão **"Pontuar o registro"** fica depois dos campos de
   governança, no rodapé do formulário.
3. A saída traz a tabela por modelo (probabilidade média, positivos previstos no limiar 0,5,
   duração local), as **divergências entre os modelos** e a prévia com a classe no limiar.

**Exemplo verificado** — registro sintético padrão (limite 50.000, faturas 20.000, pagamentos
2.000, `PAY_0` = 0, idade 30), com `random_forest` e `logistic_regression` selecionados:

| Modelo | Probabilidade | Classe no limiar 0,5 | Duração local |
|---|---:|---|---:|
| `random_forest` | 0,3332 | 0 (adimplente) | 0,0371 s |
| `logistic_regression` | 0,5203 | 1 (inadimplente) | 0,0012 s |

Divergências: `max_abs_difference` 0,1871 · `rows_with_divergence` 1 · `class_disagreements` 1.

O aviso azul *"Um registro isolado produz apenas previsoes..."* é o comportamento correto: com
uma linha não existe base para medir qualidade. Um registro isolado produz **previsões**, nunca
ROC-AUC, F1 ou Brier.

---

## 8. Aba "Predicao" — painel "Lote CSV"

### 8.1 Como configurar

| Requisito | Detalhe |
|---|---|
| Separador e decimal | vírgula e **ponto** (`.`) — um CSV salvo pelo Excel em pt-BR (`;` e `,`) quebra a leitura |
| Cabeçalho | exatamente os nomes canônicos: `ID`, as 19 features financeiras e as 4 de governança |
| Coluna de alvo | **ausente**: se `default_payment_next_month` estiver presente, o upload é recusado ("esta tela e de inferencia, nao de avaliacao") |
| Colunas extras | aceitas e **ignoradas** pelo modelo (o contrato não é estrito) — úteis para rotular os casos |
| IDs | únicos dentro do lote |
| Linhas | acima de **500** o laboratório avisa o limite por chamada (o lote ainda é pontuado) |

**Ordem de execução:** o lote é validado **inteiro, antes de qualquer chamada**; só então o mesmo
lote validado é enviado a todos os modelos selecionados. Uma linha que viola o contrato faz o
lote inteiro ser **recusado**, com diagnóstico por regra e coluna e **zero chamadas a qualquer
modelo**.

### 8.2 Os 6 perfis e a leitura esperada

Lote `data/test/lote_perfis_6.csv`: seis perfis construídos à mão, todos dentro da faixa
empírica do dataset, para ver como o modelo responde a cada tipo de comportamento financeiro.

| Perfil | O que caracteriza | RF | classe | LR | classe |
|---|---|---:|---|---:|---|
| `uso_intenso_sem_atraso` | limite 500.000, fatura = pagamento (120.000) | 0,1530 | 0 | 0,0278 | 0 |
| `pagador_exemplar` | limite 200.000, sem atraso, paga 30.000 por mês | 0,2889 | 0 | 0,3232 | 0 |
| `credito_na_fatura` | `BILL_AMT1` = −5.000 (crédito na fatura) | 0,4188 | 0 | 0,5384 | **1** |
| `fatura_alta_limite_curto` | limite 30.000, fatura 250.000, paga 5.000 | 0,4899 | 0 | 0,5441 | **1** |
| `atraso_longo` | `PAY_0` = 8 … `PAY_6` = 3, fatura 150.000, pagamento 0 | 0,8148 | 1 | 0,9954 | 1 |
| `adimplente_tipico` | limite 20.000, fatura 80.000, paga 1.000, atraso 1–2 meses | 0,8381 | 1 | 0,7972 | 1 |

**O que a tabela ensina**

- O escore responde ao **comportamento de pagamento** (fatura × pagamento), ao **histórico de
  atraso** e à **relação entre limite e fatura** — não ao valor absoluto do limite.
- `uso_intenso_sem_atraso` tem a maior fatura do lote (120.000) e é o **menor** escore: uso
  intenso sem atraso não é risco.
- `adimplente_tipico` (fatura 80.000, limite 20.000) pontua **mais alto** que
  `fatura_alta_limite_curto` (fatura 250.000, limite 30.000): as duas têm fatura alta, mas a
  primeira tem histórico de atraso — o que o modelo lê.
- `credito_na_fatura` mostra que **fatura negativa é dado legítimo**, não erro: o contrato não a
  restringe e o modelo a aceita.
- Perto de 0,5 os dois modelos discordam: em `credito_na_fatura` e `fatura_alta_limite_curto` o
  RF fica abaixo do limiar e a LR acima.

### 8.3 Interpretando a saída

Lote `data/test/lote_teste_200.csv` (200 linhas), com `random_forest` e `logistic_regression`:

| Modelo | média | mediana | mín | máx | positivos @0,5 | duração local |
|---|---:|---:|---:|---:|---:|---:|
| `random_forest` | 0,4311 | 0,3737 | 0,1490 | 0,9202 | **54 (27,0%)** | ~0,04 s |
| `logistic_regression` | 0,4585 | 0,4467 | 0,0091 | 0,9954 | **71 (35,5%)** | ~0,01 s |

Divergências: máxima **0,3593** · 200 linhas com divergência · **33 linhas com discordância de
classe (16,5%)**.

**(a) Tabela por modelo**

- `probabilidade_media` — média das probabilidades do lote. Com **um** registro, é a
  probabilidade daquele cliente; com um **lote**, é uma estatística de carteira que **esconde a
  dispersão**. Compare sempre com a mediana (0,3737 no RF): a média é puxada para cima por
  poucos clientes de risco alto.
- `positivos_previstos` — **quantos** registros ficaram com probabilidade ≥ 0,5, isto é, quantos
  foram **marcados** pela regra de decisão. **Não** é "quantos vão ficar inadimplentes": na
  validação, o RF marcou 1.161 clientes e 577 deles realmente inadimpleceram (precisão 49,7%),
  com 418 inadimplentes não marcados (recall 58,0%). A LR sinaliza 38,4% do lote com precisão
  36,8% — é sistematicamente mais "alarmista", e por isso diverge do RF perto do limiar.
- `duracao_local_s` — tempo de inferência **nesta máquina**, para este lote. Não é métrica de
  qualidade: a LR é linear e ~30× mais rápida aqui, enquanto o RF faz 300 árvores — mas o RF é o
  vigente porque discrimina melhor (0,774103 contra 0,714509 de ROC-AUC).

**(b) "Divergencias entre os modelos"** — a informação mais útil de um lote

- `max_abs_difference` — maior diferença absoluta de probabilidade entre o par de modelos.
- `rows_with_divergence` — quantas linhas divergiram além da tolerância numérica (1e-12), ou
  seja, divergência real.
- `class_disagreements` — quantas linhas os modelos colocaram em **classes opostas** no limiar
  0,5. É o número que interessa para uma política de decisão: perto de 0,5, diferenças
  pequenas de escore viram decisões opostas. Com um registro só, esse número é 0 ou 1 e não diz
  nada; com 200, vira um indicador de **estabilidade entre modelos** (aqui 16,5%).

**(c) Tabela de prévia** — as 50 primeiras linhas, com `classe_no_limiar_0.5` (do **primeiro**
modelo selecionado; não é consenso) e a probabilidade de cada modelo. Use para inspecionar os
casos de maior divergência.

### 8.4 Lotes prontos

[`data/test/`](../../data/test/) traz fixtures versionadas, todas derivadas **apenas** da
partição de treino, com IDs novos e jitter determinístico:

| Arquivo | Linhas | Para quê |
|---|---:|---|
| `lote_teste_200.csv` | 200 | lote principal (6 perfis + 194 do treino) |
| `lote_perfis_6.csv` | 6 | os seis perfis rotulados (§8.2) |
| `lote_rejeitado.csv` | 4 | viola 4 regras do contrato — demonstra a recusa integral |
| `lote_com_alvo.csv` | 200 | demonstra a recusa do upload com coluna de alvo |
| `exemplo_lote_inferencia.csv` | 3 | teste rápido de fumaça |

Regeneração: `uv run python scripts/gerar_lotes_teste.py` (seed 42). Proveniência, licença e
resultados esperados: [`data/test/README.md`](../../data/test/README.md).

### 8.5 Limites de interpretação

1. **O lote de teste é in-sample.** As linhas vêm do treino, então as probabilidades são
   otimistas. Para "cliente novo", a referência honesta é a rodada de validação (4.500 linhas).
2. **Média do lote ≠ risco do lote.** Taxa de sinalização (27,0%) e dispersão (mediana 0,3737)
   descrevem a carteira melhor do que a média 0,4311.
3. **Sinalizados ≠ inadimplentes.** 54 sinalizados é uma decisão de limiar, não uma previsão de
   desfecho.
4. **A probabilidade não é uma "chance" calibrada.** Ver §11.

---

## 9. Aba "Cenarios de contrato"

Cinco predefinições sintéticas, cada uma em um expander com o resultado esperado, o observado e
o diagnóstico por regra e coluna:

| Preset | Esperado |
|---|---|
| lote válido | aceito |
| ID duplicado | recusado (`require_unique_id`) |
| limite não positivo | recusado (`require_positive_limit_bal`) |
| idade fora do intervalo | recusado (`age_out_of_range`) |
| feature ausente/nula | recusado (`reject_null_features`) |

Um lote inválido é recusado **por inteiro** e **não chama nenhum modelo** — os testes do projeto
comprovam isso com spies sobre `predict_proba`.

---

## 10. Referência rápida das variáveis

Fonte: dataset público UCI 350 (*Default of Credit Card Clients*, Taiwan, pagamentos de abril a
setembro de 2005, valores em **NT$**). Proveniência completa em
[`docs/DATASET.md`](../DATASET.md).

**Features financeiras — são as que o modelo usa (19)**

| Campo | Significado | Valores possíveis | Observação |
|---|---|---|---|
| `LIMIT_BAL` | limite de crédito concedido (individual + familiar suplementar) | NT$ > 0; observado 10.000 a 1.000.000, mediana 140.000 | o contrato exige **> 0** |
| `PAY_0` | status de pagamento de **setembro/2005** (mês mais recente) | `-2`, `-1`, `0`, `1`…`8` | `-1` = pago em dia; `1`…`8` = meses de atraso; `0` e `-2` = sem consumo (códigos não documentados, preservados) |
| `PAY_2` a `PAY_6` | status de pagamento de **agosto … abril/2005** | mesmos códigos | o índice cresce com a idade do mês |
| `BILL_AMT1` a `BILL_AMT6` | valor da **fatura**, de setembro (1) a abril (6) | observado −339.603 a 1.664.089; mediana ≈ 17.000–22.000 | **pode ser negativo**: é crédito na fatura, não erro |
| `PAY_AMT1` a `PAY_AMT6` | valor **pago** no mês anterior, de setembro (1) a abril (6) | NT$ ≥ 0 (0 = não pagou) | "pagou muito menos que a fatura" é o sinal de risco mais forte |

**Governança — validadas, mas não são preditores (4)**

| Campo | Valores possíveis | Observação |
|---|---|---|
| `ID` | inteiro, **único no lote** | o `9999999` do formulário é placeholder sintético |
| `SEX` | `1` = masculino, `2` = feminino | fora do modelo |
| `EDUCATION` | `1` = pós-graduação, `2` = universidade, `3` = ensino médio, `4` = outros (o dataset traz `0`, `5`, `6`, preservados) | fora do modelo |
| `MARRIAGE` | `1` = casado, `2` = solteiro, `3` = outros (o dataset traz `0`, preservado) | fora do modelo |
| `AGE` | anos; o contrato exige **18 a 100** (observado 21 a 79) | fora do modelo |

**Regras do contrato aplicadas na hora de pontuar:** `ID` único · `LIMIT_BAL` > 0 ·
18 ≤ `AGE` ≤ 100 · nenhuma feature obrigatória nula · todas as colunas presentes e com tipo
correto. O alvo binário é exigido apenas no esquema rotulado, que esta tela não usa.

**Dica de uso:** os valores padrão do formulário formam um cliente sintético de pagamento
regular (RF responde 0,3332, classe 0). Para explorar a resposta do modelo, experimente pagar
menos que a fatura, atrasos altos em `PAY_0`…`PAY_6` ou limite pequeno frente à fatura. Mantenha
os valores dentro das faixas observadas: valores muito fora são extrapolação e a probabilidade
perde significado.

---

## 11. Como falar sobre os resultados

O modelo foi avaliado quanto a **ordenar** risco, não quanto a **calibrar** probabilidades. A
tabela de confiabilidade do RF vigente na validação (450 clientes por decil) mostra o contraste:

| Decil | média prevista | inadimplência **observada** |
|---:|---:|---:|
| 1 | 0,196 | 0,036 |
| 2 | 0,239 | 0,060 |
| 3 | 0,274 | 0,120 |
| 5 | 0,349 | 0,164 |
| 7 | 0,433 | 0,184 |
| 9 | 0,679 | 0,422 |
| 10 | 0,856 | 0,689 |

A ordenação é monótona e confiável (3,6% → 68,9%), mas o **risco absoluto é inflado**: o modelo
prevê 0,196 onde se observou 0,036.

| Frase | Veredito |
|---|---|
| "O modelo atribui escore de risco 0,33 e classifica como adimplente no limiar 0,5" | ✅ |
| "O cliente está no decil de risco X do lote" | ✅ |
| "54 clientes foram sinalizados pela regra de 0,5; 49,7% deles inadimpleceram" | ✅ |
| "Este cliente tem 33% de chance de inadimplentar" | ❌ não calibrado |
| "A probabilidade média do lote é 0,64, então o lote tem 64% de chance" | ❌ a média não descreve cliente nem agrega risco |
| "Foram identificados 2 positivos no lote" | ⚠️ correto, mas não são "2 inadimplentes" |

Para sustentar a leitura absoluta ("X% de chance") seria preciso medir a curva de confiabilidade
e decidir o limiar contra um custo aprovado de falso positivo/negativo — o plano 1.6 registra
que **não existe** esse custo aprovado, e por isso o limiar 0,5 é o do protocolo, não um ponto
operacional ótimo.

---

## 12. Verificação e manutenção

```bash
uv run --extra model_lab pytest tests/test_app_dev.py   # testes da aplicação
uv run --extra model_lab pytest -q                        # suíte completa
uv run python scripts/gerar_lotes_teste.py                # regenera data/test/
```

Os testes da aplicação usam `streamlit.testing.v1.AppTest` e fixtures locais: não retreinam nem
avaliam o conjunto de teste. Sem o extra `model_lab`, o arquivo de teste é ignorado e o restante
da suíte continua valendo. O CI executa esse arquivo com o extra.

---

## 13. Referências

- Recorte **1.6-O6** do plano: [`docs/plans/1.6-otimizacao-modelos.md`](../plans/1.6-otimizacao-modelos.md) (§5.1)
- Evidência da campanha e da inspeção visual: [`docs/evidence/1.6-otimizacao-modelos.md`](../evidence/1.6-otimizacao-modelos.md)
- Roteiro resumido do laboratório: [`dashboard/README.md`](../../dashboard/README.md)
- Arquitetura e fronteiras entre componentes: [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md)
