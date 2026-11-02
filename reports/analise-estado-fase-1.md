# Análise de estado do código — Fase 1 (Validação de Dados e Contratos)

> ## ⚠️ Estado inicial, superado pela execução da fase
>
> Este documento é o **diagnóstico do repositório antes da execução da Fase 1** (base `main` @
> `b27e077`), preservado como registro histórico e como ponto de partida do plano. As marcações
> `✅ / ⚠️ / ❌` da seção 5 e os "bloqueadores de M1" da seção 6.1 descrevem **o estado naquela
> data** — não o estado atual.
>
> **O que aconteceu depois:** a Fase 1 foi implementada e verificada por execução, e o gate **M1
> foi concluído** em 2026-10-26. O registro de aceite, com comandos, códigos de saída e hashes, está
> em [`docs/evidence/fase-1.md`](../docs/evidence/fase-1.md) (seções 1.1–1.7 e "Checklist do gate
> M1"). Os achados abaixo **não foram apagados**: eles medem o ponto de partida e explicam por que
> o plano existe.

**Data da análise:** 2026-10-26
**Base analisada:** `main` / branch de trabalho `docs/bill/planos-execucao-agentica` @ `b27e077`
**Escopo:** confronto entre o que foi planejado em `docs/plans/plano-de-trabalho-TC4.md` e
`docs/plans/fase-1-validacao-dados-contratos.md` e o que existe/executa de fato no repositório,
com foco em `models/`, `notebooks/` e `scripts/`.
**Natureza:** diagnóstico de estado (observação + reprodução). Nenhuma entrega da Fase 1 foi
declarada aceita por este documento; nenhuma mudança foi aplicada no repositório.

**Atualização posterior (2026-10-26):** por decisão do operador, o gate de atribuição de
responsável/revisor por ID foi removido dos planos (`docs/plans/`), do checklist e da
documentação de fase; o aceite técnico verificado encerra o ID. As referências a esse gate nas
seções 7 e 10 deste relatório descrevem o diagnóstico na data da análise e não refletem o plano
vigente.

---

## 1. Resumo executivo

O repositório tem uma **fundação de pipeline real e funcional** (EDA → preparação/split → treino
com dois modelos), coberta por 24 testes automatizados e lint limpo. O pipeline **reproduz
byte-a-byte os relatórios já versionados** e roda de ponta a ponta em **24 s** de CPU local.

Porém, o marco M1 **está bloqueado** por quatro lacunas concretas, todas verificáveis *(situação
**na data da análise** — ver o aviso no topo deste documento: as quatro foram resolvidas depois e
M1 foi concluído)*:

| # | Lacuna | Gravidade |
|---|---|---|
| 1 | **Contrato Pandera (1.7) não existe.** `pandera` está declarado em `pyproject.toml` e nenhum módulo do projeto o importa. As regras de contrato existem apenas em `configs/project.yaml` e são consumidas como *filtro histórico* em `prepare.py` — não como bloqueio de lote operacional. | **Alta** (25% da nota oficial) |
| 2 | **Versionamento não é evidência:** `dvc.lock` não corresponde nem ao código versionado nem aos relatórios versionados; não há cache DVC e não há remote. `dvc status` nasce sujo. Nada é recuperável do DagsHub. | **Alta** |
| 3 | **Bruto ausente e sem script de aquisição:** o CSV bruto não existe no disco, nem no cache, nem no remote. Só existe o XLS original da UCI **versionado no Git** (5,5 MB, binário — conflita com a regra 3 do `AGENTS.md`). A conversão XLS→CSV não está documentada nem versionada. | **Alta** |
| 4 | **Protocolo de avaliação violado:** `train` carrega e avalia o **teste a cada execução**, e a seleção depende de ordem de dicionário e de métricas já arredondadas — exatamente o que o plano (1.6) proíbe. | **Alta** |

Além disso, `models/` e `scripts/` estão **vazios** (apenas `README.md`), `notebooks/` contém um
único EDA já executado, e a **documentação de proveniência** (`docs/DATASET.md`) não registra hash
do bruto, parâmetros de conversão, DOI nem licença — itens obrigatórios de 1.2.

Verificações executadas nesta análise: `uv sync --dev --locked`, `uv run pytest` (24 passed),
`uv run ruff check .`, `uv run ruff format --check .`, `uv run dvc dag`, `uv run dvc status`,
`uv run dvc remote list`, `git log/status/diff`, e **reprodução completa do pipeline em clone
limpo** (fora do repositório, em `/home/bill/.positronic/runtime/tmp/opencode/audit-fase1`).

---

## 2. Ambiente de verificação

| Item | Valor observado |
|---|---|
| `uv` | 0.12.18 (`~/.local/bin/uv`; **não está no PATH padrão** do shell) |
| Python | 3.12.14 (gerenciado pelo uv), `.python-version` = `3.12` |
| `uv sync --dev --locked` | OK (8,2 s, ambiente já em cache) |
| scikit-learn / pandas | 1.9.1 / 2.x (do lockfile) |
| `uv run pytest` | **24 passed**, 15 warnings (depreciação seaborn/matplotlib), 13,4 s |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 38 files already formatted |
| `uv run dvc dag` | `eda → prepare → train` (3 estágios) |
| `uv run dvc remote list` | **vazio** (nenhum remote) |
| `git status` | Limpo, exceto `.obsidian/` e `.positronic/` (não rastreados, pré-existentes) |

Observação: `.venv/` e `src/*.egg-info/` foram criados por esta análise e são cobertos por
`.gitignore`; nenhum arquivo versionado foi alterado.

---

## 3. Estado por diretório

### 3.1 `models/` — **vazio de artefatos**

Conteúdo real: apenas `models/README.md`.

```
models/README.md          295 B   (descreve saídas esperadas do estágio train)
```

O `README.md` declara que o estágio `train` produz `credit_model.joblib` e
`credit_model_metadata.json`, rastreados pelo DVC e ignorados pelo Git — **verdade quanto ao
projeto, falso quanto ao estado atual**: os dois arquivos **não existem** neste checkout, e
`reports/figures/model/` também não existe (só o `README.md`).

Consequências:

- O modelo **não é recuperável** a partir do repositório nem de qualquer remote: não há cache
  DVC (`.dvc/` tem 8 KB, apenas `config` e `.gitignore`) e não há remote configurado.
- O `dvc.lock` versionado referencia `models/credit_model.joblib` (md5 `d2300fcc7cb6fa563b21b23036fa811c`,
  5.490.002 B) e `models/credit_model_metadata.json` (md5 `a5dd8b04e07a2c1a421b678ac755e9cb`) —
  objetos que **não existem** em nenhum lugar acessível.
- Contradição de versionamento: `reports/metrics.json` (métricas do modelo) **está versionado no
  Git**, enquanto o modelo que as produziu está fora do Git e foi perdido. O resultado da fase
  1.4/1.5 sobreviveu sem o artefato que o origina.

### 3.2 `notebooks/` — **um EDA executado, sem vínculo com o DVC**

```
notebooks/01_eda.ipynb    15 células, todas com saída gravada
notebooks/README.md
```

Estado factual da execução:

- As 15 células têm **saídas persistidas** (tabelas de `value_counts`, JSON de códigos não
  documentados, imagens) → o notebook **foi executado** com o bruto real, não é um rascunho.
- O notebook é **autossuficiente e reproduz a lógica do módulo**: importa `run_eda` de
  `src/credit_monitoring/eda.py` e escreve figuras num `tempfile.mkdtemp()` para não tocar nas
  saídas do DVC. Boa prática já adotada.
- **Não é um estágio DVC** e **não é verificado por teste**: `dvc.yaml` não o referencia. Se o
  código de EDA mudar, o notebook pode divergir silenciosamente das figuras versionadas.
- **Conteúdo com exposição do teste**: as células 3, 7, 11 e 13 calculam taxa de default por
  `SEX`/`EDUCATION`/`MARRIAGE`/`AGE`/`PAY_0` e **correlação com o alvo no bruto completo**
  (30.000 linhas, incluindo o futuro conjunto de teste). O resultado está **versionado em
  `reports/eda/eda_summary.json`** (`top_target_correlations`). O plano (1.2) exige registrar
  essa exposição — hoje ela é implícita, não declarada.

### 3.3 `scripts/` — **vazio**

```
scripts/README.md          (descreve "pontos de entrada operacionais serão adicionados por etapa")
```

Nenhum arquivo. Os pontos de entrada atuais são `console_scripts` do `pyproject.toml`
(`credit-monitoring-eda`, `credit-monitoring-prepare`, `credit-monitoring-train`) e módulos
`-m`. Não há script de aquisição do bruto, de conversão XLS→CSV, de inferência, de validação de
lote nem de simulação de drift — todos previstos pelos planos.

### 3.4 `data/` — bruto ausente, preparados ausentes, XLS versionado no Git

| Caminho | Estado real |
|---|---|
| `data/default of credit card clients.xls` | **Presente e versionado no Git** (5.539.328 B, md5 `c0a9cb828ded9c446574ede877bf1f6e` — o md5 publicado do original UCI 350). Binário de dataset dentro do repositório Git. |
| `data/raw/default_of_credit_card_clients.csv` | **Ausente** (dep `deleted` no `dvc status`). Existe apenas o ponteiro `.dvc` (md5 `a6ee086d1eafba5566f666b3ff2ed2c9`, 2.897.299 B). |
| `data/processed/{train,validation,test}.csv`, `preparation_report.json` | **Ausentes** (`not in cache`). |
| `data/reference/reference.csv` | **Ausente** (`not in cache`). |
| `data/production/` | Apenas `README.md` (cenário de drift planejado, não implementado). |

Os quatro `README.md` de zona descrevem corretamente o estado ("regeneráveis com
`uv run dvc repro`", "a simulação ainda não está implementada").

### 3.5 `src/credit_monitoring/` — 5 módulos, boa separação

| Módulo | Linhas | Responsabilidade | Observação |
|---|---:|---|---|
| `config.py` | 32 | carga de YAML, `feature_columns`, `canonical_columns` | OK; `governance_features` deliberadamente fora do modelo |
| `paths.py` | 16 | caminhos canônicos | OK |
| `data/loading.py` | 38 | leitura do CSV (`sep=";"`, `header=1`), SHA-256, checagem de colunas | OK |
| `data/prepare.py` | 173 | limpeza, split estratificado, referência, relatório | OK; **operação de limpeza é tolerante**, coerente com "preparação histórica" |
| `eda.py` | 263 | auditoria estrutural + 9 figuras | **Mistura** auditoria estrutural com exploração supervisionada no bruto |
| `models/train.py` | 204 | treino, comparação, seleção, serialização, métricas | **Acopla teste ao treino**; desempate implícito |

Não existe `src/credit_monitoring/contracts/` (previsto em 1.7), nem `monitoring/`, nem
`inference/`, nem `drift/`.

### 3.6 `tests/` — 24 testes, todos sintéticos

`conftest.py`, `test_scaffold.py`, `test_eda.py` (3), `test_data_preparation.py` (10),
`test_train.py` (6), `test_pipeline_definition.py` (3).

Cobertura real:

- ✅ Preparação:remoções por regra, presença de códigos não documentados, split 70/15/15
  estratificado, reprodutibilidade e sensibilidade à seed, ratios inválidos, EDA-conferido-com-o
  bruto (hash), referência idêntica ao treino.
- ✅ Treino: candidatos da config, rejeição de candidato desconhecido, seleção por maior
  ROC-AUC com empate mantendo o baseline, artefatos e métricas gravados, reprodutibilidade,
  features de governança fora do modelo.
- ⚠️ **Nenhum teste usa o dataset real** — todas as fixtures são sintéticas (`make_raw`).
- ❌ **Nenhum teste de contrato** (não existe contrato).
- ❌ **Nenhum teste de recarga do modelo serializado** (exigido em 1.6).
- ⚠️ `test_pipeline_definition.py` fixa `eda → prepare → train` e exige `test.csv` como dependência
  do estágio `train` — **é exatamente o acoplamento que 1.6 precisa desfazer**; o plano já
  autoriza revisar esse teste, mas ele é o obstacle real para separar seleção de avaliação final.
- ⚠️ `test_select_best_uses_highest_validation_metric_and_keeps_baseline_on_tie` valida o
  comportamento correto, mas o código depende de ordem de dicionário, não de uma regra explícita
  (ver §5.4).

### 3.7 `configs/project.yaml` — parametrização completa e versionada

`project.random_seed: 42`, `dataset.split 0.70/0.15/0.15`, as **19 features** e as 4 features de
governança, `modeling` (LR: `C=1.0`, `max_iter=1000`, `class_weight=balanced`; RF: 300 árvores,
`max_depth=8`, `min_samples_leaf=20`, `balanced_subsample`, `n_jobs=-1`), `contract`
(`age_min 18`, `age_max 100`, `require_unique_id`, `require_positive_limit_bal`,
`reject_null_features`) e `drift` (`features_to_shift: [LIMIT_BAL, PAY_AMT1]`, `alpha: 0.05`).

Observações:

- O bloco `contract:` **não é consumido por nenhum código de contrato** — apenas `age_min/age_max`
  são lidos, e só dentro de `prepare.py` (limpeza histórica).
- `drift.alpha: 0.05` está lá, mas o plano (2.2) proíbe usar esse valor simultaneamente como
  limiar de PSI e de p-value — pendência a resolver na fase 2, não é defeito da fase 1.

### 3.8 `dvc.yaml` / `dvc.lock` / `.dvc/config`

`dvc.yaml`: 3 estágios, com `params` por estágio, `outs` corretos e `metrics:` para
`reports/metrics.json` com `cache: false`.

`.dvc/config`: **apenas** `[core] analytics = false` → **nenhum remote**. Sem `dvc-s3` no
`uv.lock` (`grep -c 'name = "dvc-s3"' uv.lock` = 0), conforme já apontado em `docs/DAGSHUB.md`.

**`dvc.lock` é inconsistente com o repositório — achado verificado:**

| Artefato | Hash no `dvc.lock` (versionado) | Hash real do arquivo versionado | Igual? |
|---|---|---|---|
| `src/credit_monitoring/config.py` | `3bb5d7ec…` (1.019 B) | `dcc6b47d…` (987 B) | ❌ |
| `src/credit_monitoring/data/loading.py` | `9119f42b…` (1.240 B) | `ce9a861d…` (1.202 B) | ❌ |
| `src/credit_monitoring/eda.py` | `eb03006d…` (11.443 B) | `44fbe3ec…` (11.180 B) | ❌ |
| `src/credit_monitoring/data/prepare.py` | `5004e6f2…` (6.969 B) | `b34d33d9…` (6.796 B) | ❌ |
| `src/credit_monitoring/models/train.py` | `de7b4adb…` (8.109 B) | `3a163aee…` (7.905 B) | ❌ |
| `reports/eda/eda_summary.json` | `3a82a2a8…` (1.390 B) | `9d1a4a75…` (1.326 B) | ❌ |
| `reports/metrics.json` | `6a8965f5…` (952 B) | `ba414657…` (906 B) | ❌ |

Todos os tamanhos divergem (32, 38, 263, 173 e 204 B nos fontes; 64 B e 46 B nos relatórios),
compatíveis com reformatação/reescrita entre a geração do lock e o commit do código.

O `dvc.lock` foi gerado em um estado de código **anterior** ao commitado (diferenças de 32–263 B
por arquivo, compatíveis com reformatação). Consequências:

- `uv run dvc status` reporta **todos** os estágios como modificados desde o primeiro uso — não há
  baseline confiável de versionamento.
- O `dvc.lock` **não pode ser usado para verificar recuperação** de nada, porque não descreve os
  artefatos que o repositório de fato contém.
- `dvc repro` reescreveu 46 linhas do lock no clone limpo (§4).

### 3.9 `docs/` — planejamento consistente e honesto

`plans/` (5 documentos, revisados em 2026-10-26), `ARCHITECTURE.md`, `CHECKLIST.md`,
`DATASET.md`, `DAGSHUB.md`, `GOVERNANCE.md` + o PDF do enunciado.

Pontos fortes: os documentos **declaram explicitamente** o que ainda não existe ("Pandera ainda
não está integrado", "DagsHub Storage é o remote planejado; ainda não está configurado",
"o EDA atual inclui relações com o alvo no bruto completo"). Não há alegação falsa de conclusão.

Lacunas documentais:

- `docs/DATASET.md` **não registra** o hash do CSV bruto, o md5 do XLS, os parâmetros de leitura/
  conversão, o DOI nem a licença CC BY 4.0 →requirement obrigatório de 1.2 e do plano geral
  ("A UCI distribui o original em XLS; a origem e a conversão para o CSV usado pelo projeto devem
  ser documentadas com hashes, nomes das colunas e parâmetros de leitura").
- `docs/evidence/fase-1.md` **não existe** (convenção proposta na seção 11 do plano geral).
- `docs/CHECKLIST.md` marca 1.1 "Em andamento", 1.2–1.6 "Em revisão" e 1.7 sem status — coerente
  com o estado real observado, exceto por **1.6**, que declara "Em revisão" sem que exista
  congelo de decisão nem recuperação remota.

### 3.10 `dashboard/app.py` — shell

15 linhas: `st.set_page_config`, título e três `st.metric` com valores placeholder
("Aguardando execução", "-", "-"). Nada é lido de `reports/metrics.json` nem do MLflow. É
coerente com "Etapa 3" e não é defeito da fase 1, mas não satisfaz 3.5.

### 3.11 `pyproject.toml` / `uv.lock` / CI

- `pyproject.toml`: dependências de runtime incluem `pandera[pandas]`, `evidently`, `mlflow`,
  `streamlit`, `ucimlrepo` — **nenhuma usada pelo código** (`grep` em `src/`, `tests/`,
  `dashboard/`: zero importações). O ambiente instala ~4 dependências pesadas sem implementação.
- `ucimlrepo` está declarado, mas a aquisição real nunca usou a API da UCI (o bruto veio de um
  arquivo local).
- CI (`.github/workflows/ci.yml`): `uv sync --dev --locked` → `ruff format --check` → `ruff check`
  → `pytest` → `uv build`. **Não** executa `dvc repro` nem valida o `dvc.lock`. Pins por SHA
  das actions e `persist-credentials: false` — boa prática.

---

## 4. Reprodução verificada (fato, não inferência)

Executado em **clone limpo** do repositório (`git clone` → checkout `b27e077`), fora da árvore de
trabalho, para não sujar o projeto:

```bash
# 1. reconstruir o bruto a partir do XLS versionado (receita nova, ver §5.3)
# 2. recuperar o ambiente
uv sync --dev --locked
# 3. rodar o pipeline completo
uv run dvc repro
```

Resultado observado:

```text
Running stage 'eda':     EDA concluido: 30000 linhas, taxa de default 22.12%
Running stage 'prepare': Preparacao concluida: {'train': 21000, 'validation': 4500, 'test': 4500}
Running stage 'train':   Modelo selecionado: random_forest (teste roc_auc=0.7772)
real  0m24.090s   user  0m30.228s   sys  0m2.068s
```

Achados da reprodução:

| Verificação | Resultado |
|---|---|
| `reports/metrics.json` reproduzido vs. versionado | **Idêntico** (`git diff` vazio) |
| `reports/eda/eda_summary.json` reproduzido vs. versionado | **Idêntico** |
| Split | 21.000 / 4.500 / 4.500; taxa do alvo 0,2212 / 0,2211 / 0,2213 |
| Removidas na limpeza | **0 linhas** (nulo, ID duplicado, alvo inválido, `LIMIT_BAL ≤ 0`, `AGE ∉ [18,100]`: todos zero) |
| Referência vs. treino | **Hash idêntico** (`dd57d28df2ec5b23960b1bbda5e36d00`) → referência = treino intacto ✔ |
| Modelos | RF selecionado (ROC-AUC validação 0,7741 vs. LR 0,7145); teste RF ROC-AUC 0,7772 |
| `dvc.lock` após `repro` | **46 linhas alteradas** → confirma que o lock versionado está defasado |
| Saídas do `train` | `models/credit_model.joblib` (5,49 MB), `credit_model_metadata.json`, 2 figuras — **não reproduzíveis byte-a-byte** (serialização + hashes de CSVs com LF vs. CRLF do lock antigo) |

Métricas reproduzidas (idênticas às versionadas):

- Validação LR: ROC-AUC 0,714497 · precision 0,367477 · recall 0,638191 · F1 0,466397 · acc 0,677111
- Validação RF: ROC-AUC 0,774103 · precision 0,496985 · recall 0,579899 · F1 0,535250 · acc 0,777333
- Teste (RF): ROC-AUC 0,777198 · precision 0,497115 · recall 0,605422 · F1 0,545948 · acc 0,777111
- Matriz de confusão no teste: TN 2.894 · FP 610 · FN 393 · TP 603

> Observação relevante: os CSVs gerados localmente têm terminadores **LF** (2.007.586 B), enquanto
> os hashes do `dvc.lock` correspondem a arquivos 21.001 B maiores (2.028.587 B) — exatamente +1 B
> por linha (21.000 dados + 1 cabeçalho), assinatura de **CRLF** no ambiente original. Isso
> explica o delta e reforça que o lock veio de outro estado de código/ambiente.

**Métricas do ambiente para o item 3.2 (fase 3):** pipeline completo = 24 s de wall clock,
30 s de CPU de usuário, 2 s de sistema, 2,8 MB de dados processados + 5,5 MB de modelo. Serve de
linha de base para tempo de CPU e consumo.

---

## 5. Achados por entrega da Fase 1

Legenda de estado: ✅ aceito pelo código · ⚠️ parcial / não conforme o plano · ❌ ausente.

> **As marcações desta seção descrevem o repositório na data da análise** (base `b27e077`, antes
> da execução da fase) — ver o aviso no topo do documento. O estado posterior, verificado por
> execução, está em [`docs/evidence/fase-1.md`](../docs/evidence/fase-1.md).

### 1.1 — Configuração do repositório — ⚠️ parcial

✅ Diretórios, `uv.lock` travado, `pyproject.toml`, `.gitignore` (regras de dados/modelos),
`.github/workflows/ci.yml`, `dvc.yaml` com 3 estágios, `docs/DAGSHUB.md` com procedimento correto.

❌ `dvc[s3]` **não** declarado (lock sem `dvc-s3`) — o próprio `docs/DAGSHUB.md` já registra isso.
❌ `.dvc/config` sem remote; **nenhum acesso de leitura/escrita ao DagsHub demonstrado**.
❌ Nenhum teste de recuperação em checkout/cache separado.
⚠️ O XLS de 5,5 MB está **versionado no Git**, contrariando `AGENTS.md` regra 3 e o README
("dados brutos… não devem ser adicionados diretamente ao Git"). É o único artefato local que
subsiste do bruto.
⚠️ `.venv/` e `src/*.egg-info/` não estão listados explicitamente no `.gitignore` (cobertos por
padrões genéricos `*.egg-info/`; `.venv/` é coberto).

### 1.2 — Aquisição e auditoria do dataset — ⚠️ parcial

✅ Auditoria estrutural implementada e versionada (`reports/eda/eda_summary.json`): 30.000 linhas,
25 colunas, 0 nulos, 0 linhas duplicadas, 0 IDs duplicados, 0 `LIMIT_BAL ≤ 0`, `AGE ∈ [21,79]`,
`LIMIT_BAL ∈ [10.000, 1.000.000]`, 3.932 valores negativos em `BILL_AMT*`, 0 em `PAY_AMT*`,
códigos não documentados (`EDUCATION` 0/5/6, `MARRIAGE` 0, `PAY_*` −2/0) **reportados e não
recodificados**, outliers IQR por coluna monetária.
✅ `load_raw` valida a presença de todas as colunas canônicas e falha explicitamente em layout
incompatível.
❌ **Procedência não documentada:** sem hash do bruto, sem md5 do XLS, sem parâmetros de conversão,
sem DOI, sem licença CC BY 4.0 em `docs/DATASET.md`.
❌ **Não existe script de aquisição/conversão** versionado — aproveniência depende do `.xls` cru.
❌ **Exploração supervisionada no bruto completo** (correlações com alvo e taxa de default por
grupo demográfico), com o resultado **versionado**; a exposição do teste **não está declarada** em
nenhum documento.

### 1.3 — Preparação dos dados — ✅ (com uma ressalva)

✅ Remoção apenas de linhas estruturalmente inválidas, com contagem por motivo e união de
remoções; ID, demografia e alvo preservados; as 19 features seletas **apenas** na fronteira do
modelo (`feature_columns`); split estratificado 70/15/15 com seed 42; asserção de **IDs disjuntos**
(`sum(len) != len(union)` → `AssertionError`); `assert_eda_matches_raw` impede preparar sem EDA do
mesmo hash; referência idêntica ao treino (verificado por hash **e** por teste).
✅ `preparation_report.json` registra `raw_sha256`, seed, contagens e taxa por split.
⚠️ **A limpeza removeu 0 linhas** neste dataset — o caminho de rejeição existe e está testado por
fixture, mas **nunca foi exercitado sobre o dado real**; o relatório de limpeza é trivial. Como
esse relatório é evidência de aceite de 1.3, vale registrar explicitamente "0 remoções" como
resultado, e não como ausência de verificação.
⚠️ Não há teste que falhe quando o `raw_sha256` diverge **na execução completa** (o caso está
coberto no nível de função, não de pipeline).

### 1.4 / 1.5 — Treinamento dos dois modelos — ⚠️ (implementado, acoplado)

✅ Ambos treinados, comparados na **validação** com as mesmas features/linhas; ROC-AUC como
métrica primária, precision/recall/F1/accuracy + matriz de confusão; limiar 0,5; classe positiva
`1`; `StandardScaler → LogisticRegression` e `RandomForestClassifier(300, depth 8, leaf 20,
balanced_subsample)` conforme a config; seed 42; `fit` só no treino; modelo serializado em
`models/credit_model.joblib` com metadados.
❌ **O contrato não precede o `fit`** (1.7 inexistente) → aceite de 1.4/1.5 não pode ser
declarado.
❌ **`train` carrega e avalia o `test.csv` a cada execução** (`train.py:133` e `:144`).
⚠️ Sem registro de convergência do LR (a config usa `max_iter=1000`; não há checagem de warning).
⚠️ Sem medição de recursos por modelo (exigido em 1.5.3) — a única medição é o total do pipeline.
⚠️ O RF usa `n_jobs=-1`; o plano pede registro explícito se isso inviabilizar o ambiente.

### 1.6 — Avaliação, seleção e versionamento — ⚠️ parcial

✅ Métricas dos dois modelos na validação, regra de maior ROC-AUC, decisão persistida em
`reports/metrics.json` e em `models/credit_model_metadata.json` (features, hiperparâmetros,
seed, fingerprint da config, hashes de treino/validação, versões de Python e scikit-learn).
✅ Artefato serializado e recarregável (coberto indiretamente pelo teste de treino).

❌ **Seleção e avaliação final não são comandos/estágios separados** — o mesmo `train` faz os dois,
e o teste é avaliado a cada execução (viola "nunca executar teste a cada treino por padrão").
❌ **Desempate por ordem de dicionário:** `select_best` usa `max(validation, key=...)`, que em
empate devolve o **primeiro item do dicionário** — hoje `logistic_regression` porque é o primeiro
item de `modeling.candidates` na config. O resultado é o desejado, mas **por coincidência de
ordem**, não por regra explícita; e a comparação usa métricas **já arredondadas a 6 casas**, o que
o plano proíbe explicitamente ("sem depender… do arredondamento apresentado no relatório").
❌ **Não existe verificação de recarga do modelo** (comparar probabilidades antes/depois da
serialização dentro de tolerância declarada).
❌ **Metadados incompletos:** sem `threshold`, sem hash do próprio modelo, sem SHA do Git, sem
versão do contrato, sem exposição do teste declarada, sem timestamp/ambiente completo.
❌ **Nenhum objeto DVC enviado; nenhum remote; nenhuma recuperação demonstrada.** O `dvc.lock`
não referencia os artefatos reais do repositório (§3.8). M1 permanece aberto.

### 1.7 — Data Contract (Pandera) — ❌ **ausente**

❌ Não existe `src/credit_monitoring/contracts/`; **nenhuma linha de código importa `pandera`**.
❌ Nenhum esquema rotulado nem de inferência; nenhuma regra é aplicada antes de `fit` ou de
qualquer inferência.
❌ Nenhum controle: lote válido aceito, lote inválido rejeitado, perturbação isolada por regra,
saída de falha sem executar o modelo.
❌ Nenhum registro de diagnóstico (regra/coluna/contagem) — logo, nada que satisfaça a rubrica de
**Validação de Dados (25%)**.

O que existe hoje é **filtro de preparação histórica** em `prepare.py` (`null_or_non_numeric`,
`duplicated_id`, `invalid_target`, `non_positive_limit`, `age_out_of_range`) que, por desenho
(plano 1.7.3), **não pode** ser reutilizado para rejeitar lote operacional: ele remove linhas e
segue, em vez de rejeitar o lote inteiro com diagnóstico.

Configuração do contrato pronta e não usada:

```yaml
contract:
  age_min: 18
  age_max: 100
  require_unique_id: true
  require_positive_limit_bal: true
  reject_null_features: true
```

### 3.x / 4.x — pré-requisitos transversais já visíveis

❌ Sem logs estruturados (3.1) — nada é registrado em etapas, e o plano observability exige logs
**desde as fases 1/2**.
❌ Sem `docs/evidence/fase-1.md`.
⚠️ O dashboard já reserva o espaço de 3.5, mas não lê nenhum artefato real.

---

## 6. Diagnóstico consolidado

### 6.1 Bloqueadores de M1 (ordenados por dependência)

> **Lista histórica.** Estes eram os bloqueadores na data da análise; **todos foram resolvidos** e
> M1 foi concluído — ver [`docs/evidence/fase-1.md`](../docs/evidence/fase-1.md) ("Checklist do
> gate M1").

1. **Bruto ausente** → nada é executável a partir do repositório. *Mitigação verificada: o bruto é
   reconstruível byte-a-byte a partir do XLS versionado* (§6.2). Alternativa: configurar o remote
   DagsHub e recuperar com `dvc pull`.
2. **Contrato Pandera ausente** → 25% da nota oficial e dependência direta de 1.4/1.5/1.6 e de
   toda a fase 2.
3. **`dvc.lock` defasado** → regenerar e versionar é pré-requisito de qualquer evidência de
   versionamento; sem isso, `dvc status` é ruído.
4. **Remote DagsHub + `dvc[s3]` + recuperação isolada** → única forma de fechar 1.1/1.6 e M1.
5. **Separação seleção × avaliação final** → exige tocar `dvc.yaml`, `train.py` e
   `test_pipeline_definition.py` (que hoje fixa o acoplamento).

### 6.2 Receita de reconstrução do bruto (verificada, ainda não versionada)

O CSV bruto é **reconstruzível byte-a-byte** a partir de `data/default of credit card clients.xls`
(já no Git). Verificado: `sha256 = 1fc7fe04822413cf48d0f5ca974cbe47061b21ea10fa1d114bb56b8feac79358`
e `md5 = a6ee086d1eafba5566f666b3ff2ed2c9` — **idênticos** ao hash registrado no
`reports/eda/eda_summary.json` e ao ponteiro `data/raw/default_of_credit_card_clients.csv.dvc`.

```python
# requer xlrd (não está nas dependências; `uv add --dev xlrd`)
import pandas as pd

xl = pd.ExcelFile("data/default of credit card clients.xls")
df = xl.parse("Data", header=1)  # 30.000 × 25
placeholder = ";".join(["", *[f"X{i}" for i in range(1, 24)], "Y"])
content = "\ufeff" + placeholder + "\r\n" + df.to_csv(sep=";", index=False, lineterminator="\r\n")
Path("data/raw/default_of_credit_card_clients.csv").write_bytes(content.encode("utf-8"))
```

Leitura pelo projeto: `load_raw` com `sep=";"`, `header=1` → 30.000 × 25, colunas canônicas
corretas, alvo 23.364/6.636. O BOM afeta apenas a **primeira** linha (descartada), logo não
contamina o cabeçalho real.

> Esta receita **deve ser transformada em script versionado** (1.2), com hash do XLS, hash do CSV
> resultante e parâmetros de leitura registrados em `docs/DATASET.md`. É o que fecha a lacuna de
> proveniência sem depender de rede.

### 6.3 Riscos de governança

| Risco | Situação observada | Efeito |
|---|---|---|
| Binário de dataset no Git | XLS de 5,5 MB versionado | Contraria `AGENTS.md` 3, README e a política de minimização; fica para sempre no histórico |
| Proveniência não comprovável | sem hashes/DOI/licença na documentação | Risco de reuso sem atribuição (CC BY 4.0) e sem trilha de auditoria |
| Exposição do teste não declarada | correlações com alvo no bruto completo, resultado versionado | Impede alegar "avaliação final intocada"; o plano exige declarar a exposição, não escondê-la |
| Métricas sem artefato | `reports/metrics.json` no Git, modelo fora do Git e perdido | Resultado não auditável (quem gerou? com qual modelo?) |
| Dependências sem implementação | `pandera`, `evidently`, `mlflow`, `streamlit`, `ucimlrepo` | Superfície desnecessária e risco de confundir "instalado" com "implementado" |
| `dvc.lock` inconsistente | 46 linhas divergentes | Qualquer auditoria de versionamento basedada no lock é inválida |

### 6.4 O que **não** foi verificado nesta análise

- Acesso ao DagsHub (sem credenciais, sem remote, sem rede testada) e existência do repositório
  no DagsHub.
- Estado do CI no GitHub (a análise foi local; a badge do README não foi consultada).
- Execução do notebook `01_eda.ipynb` de ponta a ponta (as saídas gravadas são de uma execução
  anterior; a lógica é a mesma do módulo `eda.py`, verificada por leitura).
- Comportamento do `dashboard/app.py` em execução (shell trivial, lido por leitura).
- Qualidade estatística dos modelos (aucácia além do reportado; recall 0,58–0,64 sobre classe
  positiva desbalanceada de 22%).
- `docs/GOVERNANCE.md` e `docs/plans/fase-2/3/4` não foram reavaliados linha a linha.

---

## 7. Sequência recomendada para iniciar a Fase 1

Ordem sugerida, já considerando o que existe (evita retrabalho) e o bloqueio do marco:

| # | Recorte | Entregas | Saída verificável | Depende de |
|---|---|---|---|---|
| **A** | *Fundação recuperável*: adicionar `dvc[s3]` com `uv add --dev 'dvc[s3]>=3,<4'`; versionar script de aquisição XLS→CSV com hashes; reconstruir o bruto; regenerar e versionar `dvc.lock`; remover o XLS do Git (DVC) | 1.1, 1.2 | `dvc status` limpo; `dvc.lock` coerente; script de aquisição com hash registrado em `docs/DATASET.md` | decisão do operador sobre mover o XLS |
| **B** | *Contrato Pandera*: `src/credit_monitoring/contracts/` com esquema rotulado e de inferência, 4+ regras rígidas, rejeição integral do lote, diagnóstico por regra/coluna/contagem, CLI com saída não zero | 1.7 | lote válido aceito; 7 perturbações isoladas rejeitadas (duplicidade, `LIMIT_BAL≤0`, `AGE` 17/101, nulo, coluna ausente, tipo, alvo inválido); spy de `fit` com **zero** chamadas em falha | A (dados válidos para o teste) |
| **C** | *Treino sob contrato*: integrar o contrato antes do `fit`; incluir `scikit-learn` + Pandera no pipeline; registrar convergência do LR; medir CPU/memória por modelo | 1.4, 1.5 | `fit` só após validação; métricas de validação recalculáveis; `n_jobs` justificado | B |
| **D** | *Seleção e avaliação separadas*: estágio `select` (só validação) e estágio `evaluate` (só o escolhido, com protocolo congelado); desempate por **regra explícita** sobre métricas não arredondadas; recarregar o modelo e comparar probabilidades; metadados completos (threshold, hash do modelo, SHA Git, versão do contrato, exposição do teste) | 1.6 | teste não altera a seleção; `dvc repro` **não** avalia o teste no ciclo de treino; `test_pipeline_definition.py` atualizado | C |
| **E** | *Versionamento e recuperação*: `dvc push` para o DagsHub e recuperação em **checkout/cache separado** (bruto, preparados, referência, modelo), conferindo hashes e inferência do modelo recuperado | 1.1, 1.6 | prova de recuperação documentada | A, D, **autorização do operador** |
| **F** | *Registro e exposição*: `docs/evidence/fase-1.md` (seções 1.1–1.7) com comandos, códigos de saída e hashes; declarar formalmente a exposição prévia do teste | 1.2, 1.3 | registro textual indexado | E |
| **G** | *Gate M1*: consolidar o checklist (1.1–1.7) para `Concluído` **somente** após aceite verificado | M1 | decisão de avanço para a fase 2 | F |

Dependências que **não** são de código e precisam do operador antes de E:

1. **Autorização de rede e credenciais do DagsHub** (owner, endpoint, chave/segredo) — sem isso
   1.1/1.6/M1 ficam abertos, mesmo com todo o código pronto.
2. **Decisão sobre o XLS no Git**: manter (com política de proveniência explícita) ou mover para
   DVC. Recomendo mover: é um dataset público de 5,5 MB dentro do histórico Git.
3. **Responsável e revisor por ID** (o plano registra a atribuição como pendente).
4. **Declaração de exposição do teste**: como a equipe quer tratá-la (registro explícito é o
   mínimo; mover as análises supervisionadas para o treino é o correto).

---

## 8. Registro de verificação desta análise

```text
uv sync --dev --locked                       → OK (8,2 s)
uv run pytest                                → 24 passed (13,4 s)
uv run ruff check .                          → All checks passed
uv run ruff format --check .                 → 38 files already formatted
uv run dvc dag                               → eda → prepare → train
uv run dvc status                            → 3 estágios sujos (deps modified/deleted, outs not in cache)
uv run dvc remote list                       → vazio
git diff --check                             → sem saída (exit 0)
git status --short                           → apenas .obsidian/ e .positronic/ não rastreados
```

Clone de auditoria: `/home/bill/.positronic/runtime/tmp/opencode/audit-fase1` (contém artefatos
gerados; descartável). A árvore de trabalho do projeto **não foi modificada**.

Referências: `docs/plans/plano-de-trabalho-TC4.md` (§3, §11), `docs/plans/fase-1-validacao-dados-contratos.md`
(§4), `docs/CHECKLIST.md`, `docs/ARCHITECTURE.md`, `docs/DATASET.md`, `docs/DAGSHUB.md`,
`AGENTS.md`, `CONTRIBUTING.md`.
