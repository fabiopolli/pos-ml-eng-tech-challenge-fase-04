# Evidências — Fase 1 (Validação de Dados e Contratos)

**Janela de execução:** 2026-10-26 (branch `fase-1-bill`).
**Plano:** [`docs/plans/plano-de-trabalho-TC4.md`](../plans/plano-de-trabalho-TC4.md) (seção 11) e
[`docs/plans/fase-1-validacao-dados-contratos.md`](../plans/fase-1-validacao-dados-contratos.md).
**Estado do marco M1:** **concluído** — todos os itens de aceite 1.1–1.7 estão verificados,
incluindo a prova de recuperação remota no DagsHub (seção 1.6.1).

## Ambiente da execução

| Item | Valor |
|---|---|
| Sistema | Linux 7.2.8-9-omarchy, x86_64, glibc 2.44 |
| `uv` | 0.12.18 (`~/.local/bin/uv`; fora do PATH padrão do shell) |
| Python | 3.12.14 (gerenciado pelo uv, `.python-version` = `3.12`) |
| scikit-learn / pandas / numpy | 1.9.1 / 2.3.3 / 2.5.4 |
| Pandera / joblib | 0.34.1 / 1.6.0 |
| Branch | `fase-1-bill` (base `main` @ `c560b46`), publicada em `origin/fase-1-bill` |
| Commit do código que gerou os artefatos | `fb5ee7b` (registrado em `models/credit_model_metadata.json` como `git_sha`) |

> `git_sha` registra o commit do **código** que produziu o artefato; o commit que versiona o
> artefato vem logo depois, na linha de tempo do Git.

## Comandos e códigos de saída

| Comando | Código de saída | Resultado |
|---|---|---|
| `uv sync --dev --locked` | 0 | ambiente travado instalado (247 pacotes) |
| `uv run pytest` | 0 | 69 passed |
| `uv run ruff check .` | 0 | All checks passed |
| `uv run ruff format --check .` | 0 | 52 files already formatted |
| `uv run dvc dag` | 0 | `acquire → eda → prepare → explore → train → evaluate` |
| `uv run dvc repro` | 0 | 6 estágios reproduzidos |
| `uv run dvc repro -f` (2× consecutivas) | 0 | `dvc.lock` e artefatos **byte-a-byte idênticos** |
| `uv run dvc status` | 0 | `Data and pipelines are up to date.` |
| `uv run dvc remote list` | 0 | `dagshub s3://dvc` (default) — remote configurado |
| `uv run dvc status -c -r dagshub` | 0 | `Cache and remote 'dagshub' are in sync.` |
| `uv run dvc push -r dagshub` | 0 | 25 objetos enviados |
| `git diff --check` | 0 | sem saída |

## Hashes dos artefatos

| Artefato | SHA-256 |
|---|---|
| `data/default of credit card clients.xls` (fonte, versionada no Git) | `63c47faa4cf5e224c3494cd5f776721bcdc4a374ecf16665632f3afab8f38a44` (md5 `c0a9cb828ded9c446574ede877bf1f6e`) |
| `data/raw/default_of_credit_card_clients.csv` | `1fc7fe04822413cf48d0f5ca974cbe47061b21ea10fa1d114bb56b8feac79358` (md5 `a6ee086d1eafba5566f666b3ff2ed2c9`) |
| `data/processed/train.csv` | `9ebd48b6d31c67f46cc28aff0bde36b48f62936aff0011007b7cb78d26108c26` |
| `data/processed/validation.csv` | `e910967511f31406edbc3c9fe0528571d079c45da10116dba4e53e379d285106` |
| `data/processed/test.csv` | `70642cbcc74972400e63df96e78e1e07497f15b6b15fe278f232aaf18b725729` |
| `data/reference/reference.csv` | `9ebd48b6d31c67f46cc28aff0bde36b48f62936aff0011007b7cb78d26108c26` (igual ao treino) |
| `models/credit_model.joblib` | `a5a4a740902fab9efa5138f98917a8a7f447c5af7f7d97b707290c205c1e0464` |
| `reports/eda/eda_summary.json` | `cd33ed3a49e52c27339d88b67dbbb1a4afcfe06a09b649205272e426a5f1dd65` |
| `reports/explore/train_exploration.json` | `0f6b8b8af79a4ad51ecedb545707f3c77597a34ad9cf7c2bccf391d6df840628` |
| `reports/metrics.json` (seleção) | `37a3fc84c371af2cf44f035f94791f4da9751f93c1b2ca0357cce477539a0050` |
| `reports/test_metrics.json` (avaliação final) | `f9aa6f218a76df552e78f0cad3dff1c2622358994bfdc4816f25ec603daf38a8` |

---

## 1.1 — Configuração do repositório

**Recorte 1.1a (local) — implementado e verificado.**

| Ação do plano | Evidência |
|---|---|
| Conferir branch, CI, `.gitignore`, `pyproject.toml`, `uv.lock`, `.dvc/config` | Feito; ajustes locais preservados. O `.gitignore` ganhou `reports/run_resources.json` (medições não reprodutíveis fora dos artefatos versionados). |
| `uv add --dev 'dvc[s3]>=3,<4'` | `dvc-s3==3.3.0` no `uv.lock`; suporte S3 carregável. |
| Dependência de leitura de `.xls` declarada e travada | `xlrd>=2,<3` em dependências de runtime (`xlrd==2.0.2` no lock). |
| Instalação travada e testes antes de atribuir falhas | `uv sync --dev --locked` → 0; `uv run pytest` → 69 passed. |
| Regularizar o `dvc.lock` | `dvc.lock` reescrito a partir do código vigente; `uv run dvc status` → limpo. A divergência histórica (lock gerado contra um código anterior, com 46 linhas alteradas e CSVs em CRLF) está registrada em [`reports/analise-estado-fase-1.md`](../../reports/analise-estado-fase-1.md) §3.8 e §4. |

**Divergência histórica registrada.** O `dvc.lock` versionado antes desta fase não correspondia
ao código do repositório: todos os hashes de fonte e de relatório divergiam (deltas de 32–263 B),
e os CSVs gerados localmente usam LF enquanto os hashes do lock correspondiam a arquivos CRLF
(+1 B por linha). O lock atual foi regenerado pelo código atual e é reprodutível.

**Decisão de equipe sobre o XLS (2026-10-26): migrar o workbook original do Git para o DVC.**
O operador optou por tirar o binário de 5,5 MB do histórico do Git; o arquivo passou a ser objeto
do DVC, com ponteiro `data/default of credit card clients.xls.dvc` no repositório. Verificado:
remover o arquivo da árvore e rodar `uv run dvc checkout` o restaura do cache com o md5
esperado, e o pipeline segue íntegro. **Consequência a registrar:** um clone novo só reproduz o
pipeline depois de `uv run dvc pull -r dagshub`, porque a fonte do bruto não está mais no Git —
isso acopla a reprodução ao remote da entrega 1.1b, configurado e com a recuperação provada
(seção 1.6.1). O histórico Git anterior continua contendo o XLS; a remoção é do estado atual do
repositório.

**Recorte 1.1b (remoto) — executado e verificado.** O operador preencheu o `.env` (ignorado
pelo Git) e a configuração foi concluída em 2026-10-26.

Diagnóstico do acesso (o `.env` inicial não autenticava):

| Sintoma | Causa verificada | Correção |
|---|---|---|
| `dvc status -c -r dagshub` → `401 Unauthorized` (HeadObject e ListObjects) | O gateway do DagsHub autentica pelo `access_key_id` e espera **o mesmo token nos dois campos** (guia oficial do DVC Storage). O token de 40 caracteres estava no campo `secret_access_key`, e o valor de 13 caracteres em `access_key_id` não é o token | Token único em `DAGSHUB_TOKEN`, usado nos dois campos |
| Endpoint `https://dagshub.com/<owner>/<repo>.s3` respondia `302` para `/user/login` | Repositório privado; o redirect é esperado sem autenticação, e não era a causa do 401 | — |
| `DAGSHUB_REPO` continha a URL completa do repositório (`.../src/feat/<branch>`) | O endpoint exige o **slug** do repositório | Script normaliza e extrai o slug, avisando o operador |

| Verificação | Resultado |
|---|---|
| `scripts/configure_dagshub.sh` | Remote `dagshub` = `s3://dvc`, endpoint `https://dagshub.com/deniscelclaro/pos-ml-eng-tech-challenge-fase-04.s3`; credenciais só em `.dvc/config.local` (ignorado pelo Git) |
| `uv run dvc push -r dagshub` | **25 objetos enviados** (workbook da UCI, CSV bruto, splits, referência, modelo, figuras) |
| `uv run dvc status -c -r dagshub` | `Cache and remote 'dagshub' are in sync.` |
| Segredos no repositório | Nenhum: `.env` e `.dvc/config.local` verificados como ignorados pelo Git; `.dvc/config` versionado contém apenas URL e endpoint |
| Quais saídas podem ser compartilhadas | Enviado o conjunto de objetos do DVC: o dataset é público (UCI 350, CC BY 4.0) e o repositório é privado. A chave de distribuição do repositório na DagsHub não foi alterada por esta execução |

## 1.2 — Aquisição e auditoria do dataset

**Implementado e verificado.**

| Ação do plano | Evidência |
|---|---|
| Restaurar o bruto | Estágio DVC `acquire` reconstrói o CSV a partir do XLS. Hash conferido: `sha256 1fc7fe04…`, `md5 a6ee086d…`, idênticos ao ponteiro `.dvc` anterior e ao registrado no `eda_summary.json` histórico. Divergência de hash **falha o comando** (`AcquisitionError`), invalidando a via. |
| Versionar a aquisição | `src/credit_monitoring/data/acquire.py` (script versionado, entry point `credit-monitoring-acquire`) registra md5/sha256 do XLS, md5/sha256/tamanho do CSV e todos os parâmetros de leitura em `reports/acquisition_provenance.json`. |
| Procedência UCI, licença, DOI | `docs/DATASET.md` registra DOI **10.24432/C55S3H**, licença **CC BY 4.0**, atribuição (Yeh, I. 2009), URL da fonte, hashes e parâmetros de leitura. Conferidos na página oficial do dataset em 2026-10-26. |
| Conferir separador, cabeçalho, nomes e unidades | `sep=";"`, `header_row=1`, linha `;X1;…;X23;Y` descartada; unidades NT$ documentadas. O hash identifica a versão efetivamente lida. |
| Auditar contagens, tipos, nulos, IDs duplicados e códigos | `reports/eda/eda_summary.json`: 30.000 linhas, 25 colunas, 0 nulos, 0 linhas duplicadas, 0 IDs duplicados, `LIMIT_BAL` de 10.000 a 1.000.000 (0 não positivos), `AGE` de 21 a 79, 3.932 valores negativos em `BILL_AMT*`, 0 em `PAY_AMT*`, códigos não documentados reportados e **não** recodificados (`EDUCATION` 0/5/6, `MARRIAGE` 0, `PAY_*` −2/0). |
| Separar auditoria estrutural de exploração supervisionada | `eda.py` agora é **auditoria estrutural** (sem relação feature-alvo); `explore.py` (estágio `explore`) calcula as relações feature-alvo **apenas sobre `data/processed/train.csv`**. Notebooks `01_eda.ipynb` (bruto) e `02_explore_train.ipynb` (treino) reescritos e reexecutados. |

### 1.2.1 — Exposição prévia do conjunto de teste (declaração formal)

| Item | Registro |
|---|---|
| **Data** | Execução do EDA anterior a 2026-10-26; artefato congelado em `reports/eda/history/eda_summary_contaminated_2026-10-26.json` |
| **Dados** | Bruto completo, 30.000 linhas (inclui as linhas que a estratificação depois atribuiu a validação e teste) |
| **Variáveis** | 19 features financeiras × `default_payment_next_month` (correlação de Pearson); taxa de default por `SEX`, `EDUCATION`, `MARRIAGE` e faixa de `AGE`; `LIMIT_BAL` por alvo; `PAY_0` por alvo |
| **Arquivos** | `reports/eda/history/eda_summary_contaminated_2026-10-26.json` (versionado, marcado como contaminante) e as figuras antigas, que nunca foram versionadas |
| **Decisão afetada** | Nenhuma decisão de modelagem da fase 1 depende de forma nova dessas relações: a lista de 19 features, a seed e o protocolo de seleção vêm do plano e da configuração. As relações orientadoras passaram a ser calculadas **no treino**. |
| **Consequência** | A avaliação final em `reports/test_metrics.json` é uma **reavaliação sob protocolo congelado**, não uma avaliação intocada. A declaração está replicada em `models/credit_model_metadata.json` (`test_exposure`) e em `reports/test_metrics.json` (`test_exposure`). |

O histórico **não** foi apagado. O resumo histórico permanece no repositório, marcado como
contaminante, com a explicação em
[`reports/eda/history/README.md`](../../reports/eda/history/README.md).

**Margem inevitável e declarada.** O EDA estrutural mantém a contagem marginal de classe do
bruto (`target_rate` 0,2212). Essa informação é inerente ao protocolo de split estratificado
exigido pelo plano: `train_test_split(stratify=y)` usa o vetor de alvo completo para definir as
proporções de classe de cada partição. A margem global de classe do conjunto de teste é, portanto,
determinística pelo protocolo — não é uma exposição adicional. O que **não** é inerente ao
protocolo — relações feature-alvo sobre o bruto completo — foi movido para o treino.

### 1.2.2 — Revalidação independente da aquisição (2026-10-26, 11:40–11:45)

Execução posterior, em nova sessão, com o objetivo de reexecutar a etapa 1.2 pelo caminho
previsto no plano (restaurar o bruto a partir da fonte versionada) e conferir, de primeira mão,
cada aceite da seção 1.2 — sem depender das afirmações das sessões anteriores.

**Aquisição reexecutada do zero.** O bruto e o registro de proveniência foram removidos do disco
e reconstruídos pelo estágio DVC:

| Passo | Comando | Código de saída | Resultado |
|---|---|---|---|
| 1 | `rm data/raw/default_of_credit_card_clients.csv reports/acquisition_provenance.json` | 0 | bruto **ausente do disco** |
| 2 | `uv run dvc repro acquire` | 0 | `Bruto reconstruido: default_of_credit_card_clients.csv (sha256=1fc7fe04822413cf48d0f5ca974cbe47061b21ea10fa1d114bb56b8feac79358, rows=30000)` |
| 3 | `cmp` com a cópia do bruto anterior | 0 | **byte-a-byte idêntico** |
| 4 | `diff` com a proveniência anterior | 0 | **idêntica** (md5, sha256, tamanho, parâmetros de leitura) |
| 5 | `uv run dvc status` | 0 | `Data and pipelines are up to date.` |
| 6 | `git status --short` | 0 | sem saída (saídas DVC não sujam a árvore) |

Hashes conferidos na sessão: XLS `sha256 63c47faa…f38a44` / `md5 c0a9cb82…1bf6e`; CSV
`sha256 1fc7fe04…79358` / `md5 a6ee086d…ed2c9` — idênticos aos esperados em
`configs/project.yaml`, ao ponteiro `.dvc` e a `docs/DATASET.md`.

**Falhas explícitas (o caminho de erro também é verificado).**

| Cenário induzido | Resultado observado |
|---|---|
| XLS adulterado (byte alterado no offset 1024) | `AcquisitionError: Source workbook md5 diverged: got 82b78cf83e6cfcfd2450e87b0db01e9a, expected c0a9cb828ded9c446574ede877bf1f6e` — exit 1, nenhum CSV produzido |
| Planilha inexistente no workbook | `AcquisitionError: Sheet 'Sheet_inexistente' not found in default of credit card clients.xls; available sheets: ['Data']` |
| CSV com layout incompatível | `ValueError: Raw dataset is missing columns: ['ID', 'LIMIT_BAL', …]` (`data/loading.py:37`) |
| EDA gerado de outro bruto | `ValueError: EDA summary was generated from a different raw file. Re-run the EDA.` (`data/prepare.py:121`) — a preparação continua dependente da auditoria do **mesmo** hash, sem ciclo EDA supervisionado → split → EDA |

**Auditoria estrutural e separação da exploração supervisionada.** `reports/eda/eda_summary.json`
confere: `scope: "structural_audit_only"`, `supervised_analysis: false`, 30.000 linhas, 25
colunas, 0 nulos, 0 linhas duplicadas, 0 IDs duplicados, `LIMIT_BAL` de 10.000 a 1.000.000 (0 não
positivos), `AGE` de 21 a 79, 3.932 valores negativos em `BILL_AMT*`, 0 em `PAY_AMT*`, códigos não
documentados reportados e não recodificados, `raw_sha256` = `1fc7fe04…`. As relações feature-alvo
existem apenas em `reports/explore/train_exploration.json` (`split: train`), cujo estágio depende
**somente** de `data/processed/train.csv`. Notebooks conferidos: `01_eda.ipynb` carrega o bruto e
consome o resumo estrutural; `02_explore_train.ipynb` lê o treino.

**Procedência reconferida na fonte.** Página oficial da UCI lida em 2026-10-26: DOI
**10.24432/C55S3H**, licença **CC BY 4.0**, citação *Yeh, I. (2009)*, arquivo
`default of credit card clients.xls` (5,3 MB), 30.000 instâncias, 23 features, unidades em NT$,
pagamentos de abril a setembro de 2005 — todos conferem com `docs/DATASET.md`.

**Linha de base da fase.** `uv sync --dev --locked` → 0 (247 pacotes); `uv run pytest -q` → 0,
**70 passed**; `uv run ruff check .` → 0, *All checks passed*; `uv run ruff format --check .` → 0,
*53 files already formatted*; `uv run dvc dag` → `acquire → eda → prepare → explore → train →
evaluate`. A contagem de testes deste registro (70) é superior à anotada antes (69) porque o
teste `test_source_workbook_is_an_object_of_dvc_and_not_a_git_file` entrou junto com a migração do
XLS para o DVC (`0e20346`), depois da última atualização da tabela de comandos.

## 1.3 — Preparação dos dados

**Implementado e verificado** (`data/processed/preparation_report.json`).

| Item | Valor observado |
|---|---|
| Remoção no dado real | **0 linhas** — nenhuma das cinco regras disparou (nulo/não numérico 0, `ID` duplicado 0, alvo inválido 0, `LIMIT_BAL ≤ 0` 0, `AGE` fora de 18–100 0) |
| Declaração sobre a ausência de remoção | O relatório afirma explicitamente que a remoção foi 0 no dado real e que **o caminho de remoção continua coberto por fixture controlada** (`tests/test_data_preparation.py`); ausência de remoção não é ausência de verificação |
| União das remoções | `removed_rows` conta linhas **únicas** removidas; `rows_matching_multiple_reasons` registra a sobreposição de motivos. A razão pela qual uma linha com nulos não é contada em outras regras está no código (`~null_mask & …`) |
| Split | 21.000 / 4.500 / 4.500, seed 42, taxas 0,2212 / 0,2211 / 0,2213 (arredondadas a 4 casas no relatório) |
| Auditoria de IDs | IDs únicos dentro de cada partição, interseções vazias, cobertura completa (30.000 = soma das partições) |
| Linhas úteis | 30.000 após limpeza ≥ 5.000 exigido pelo enunciado |
| Referência | `data/reference/reference.csv` com SHA-256 **idêntico** ao de `train.csv` (igualdade verificada por hash e por teste) |
| Transformações aprendidas | Nenhuma: o split é anterior a qualquer `scaler` ou ajuste de modelo |

### 1.3.1 — Revalidação independente da preparação (2026-10-26, 12:05–12:25)

A 1.3 já estava implementada; esta sessão reexecutou a etapa do zero e conferiu cada ação do
plano de primeira mão. Duas lacunas reais foram encontradas e fechadas nesta passagem.

**Reexecução do zero, com byte-a-byte.** Os cinco artefatos da etapa (`train.csv`,
`validation.csv`, `test.csv`, `preparation_report.json` e `data/reference/reference.csv`) foram
removidos do disco e reconstruídos:

| Passo | Comando | Código de saída | Resultado |
|---|---|---|---|
| 1 | `rm` dos cinco artefatos de `data/processed/` e `data/reference/` | 0 | diretórios com apenas os `README.md` |
| 2 | `uv run dvc repro prepare` | 0 | estágio restaurado do cache; `cmp` com as cópias anteriores: **idêntico** nos cinco arquivos |
| 3 | `uv run dvc repro --force prepare` | 0 | reexecução real do `acquire → eda → prepare`; `Preparacao concluida: {'train': 21000, 'validation': 4500, 'test': 4500}` |
| 4 | `sha256sum` dos artefatos antes e depois | 0 | **inalterado** — `train.csv` = `9ebd48b6…8c26`, `preparation_report.json` = `60fc337b…3a6` |
| 5 | `uv run dvc status` | 0 | `Data and pipelines are up to date.` · `git status --short` sem saída |

**União das remoções e sobreposição de motivos, em fixture controlada.** Fixture de 600 linhas
com motivos sobrepostos (uma linha com `ID` duplicado **e** alvo inválido) e motivos isolados:

| Métrica | Valor observado |
|---|---|
| `input_rows` / `output_rows` / `removed_rows` | 600 / 595 / 5 |
| `entrada = saída + removidos únicos` | **True** |
| Soma dos motivos por regra | 6 — **não** é a contagem de linhas removidas |
| `rows_matching_multiple_reasons` | 1 (a linha com dois motivos é removida uma vez) |
| Motivos preservados | nulo 1, `ID` duplicado 1, alvo inválido 1, `LIMIT_BAL ≤ 0` 1, `AGE` fora de 18–100 2; a linha com nulo não é recontada nas demais regras (`~null_mask & …`) |

**Determinismo e sensibilidade à seed.** Mesma entrada e mesma configuração → partições
idênticas; `random_state=7` → partição diferente. Na reexecução forcada do estágio DVC, os
hashes de `train.csv`, `validation.csv` e `test.csv` não se alteraram: a mesma entrada e a mesma
configuração produzem as mesmas partições.

**Caminhos de erro, verificados por execução.**

| Cenário induzido | Resultado observado |
|---|---|
| Razões de split inválidas (0,70/0,20/0,20) | `ValueError: Split ratios must sum to 1: {'train': 0.7, 'validation': 0.2, 'test': 0.2}` |
| IDs compartilhados entre partições | `AssertionError: ID leakage between splits` (`data/prepare.py:111`) — **agora coberto por teste**, ver lacunas abaixo |
| Hash do bruto divergente do EDA | `ValueError: EDA summary was generated from a different raw file. Re-run the EDA.` (`data/prepare.py:121`) |
| EDA ausente | `FileNotFoundError: EDA summary not found: … Run the EDA first.` |

**Fronteira do modelo.** O `train.csv` tem 25 colunas: `ID` + 19 features financeiras + 4 de
demografia (`SEX`, `EDUCATION`, `MARRIAGE`, `AGE`) + alvo. A demografia e o `ID` ficam de fora da
fronteira do modelo (`feature_columns` = 19 features financeiras, em `config.py:20`), e a seleção
acontece em `models/train.py:190` — nunca na preparação. Nenhum `scaler` é ajustado antes do
split: `StandardScaler` aparece apenas dentro do `Pipeline` ajustado no treino.

**Lacunas encontradas e fechadas nesta passagem.**

1. **Falha por IDs compartilhados sem cobertura de teste.** O guarda `AssertionError: ID leakage
   between splits` existia, mas nenhum teste o exercitava — a aceitação do plano ("IDs
   compartilhados falham") estava garantida apenas por leitura de código. Acrescentados
   `test_split_fails_when_ids_are_shared_between_splits` (dublando `train_test_split` para
   devolver partições com IDs repetidos) e `test_id_audit_reports_shared_ids_between_splits`
   (interseção `train&validation` = 50 reportada e `coverage_complete` = False).
2. **Relatório não vinculado à configuração.** O relatório registrava o hash do bruto e a seed,
   mas não a configuração consumida nem o arredondamento das taxas — exigência das ações 3 e 5 do
   plano. Acrescentados ao relatório: `config.sha256` (impressão digital SHA-256 de
   `project.random_seed` + `dataset` + `contract`, o mesmo escopo dos parâmetros DVC do estágio),
   `config.params`, `split_ratios` e `target_rate_rounding_decimals` (4). O fingerprint é estável
   para entradas equivalentes e muda com seed, razões de split ou `contract` — coberto por
   `test_config_fingerprint_is_stable_and_sensitive_to_used_params` e
   `test_preparation_report_binds_config_ratios_and_rounding`.

**Estado do repositório após a mudança.** `dvc.lock` atualizado (hash da dependência
`prepare.py` e do novo `preparation_report.json`; os hashes de `train.csv`, `validation.csv` e
`test.csv` **não** mudaram). `uv run dvc push` enviou 1 objeto novo
(`data/processed/preparation_report.json`) e `uv run dvc status -c -r dagshub` voltou a
responder *Cache and remote 'dagshub' are in sync*. Suíte: `uv run pytest -q` → 0, **74 passed**
(70 anteriores + 4 novos); `uv run ruff check .` → 0, *All checks passed*;
`uv run ruff format --check .` → 0, *53 files already formatted*.

## 1.4 — Treinamento da Regressão Logística

**Implementado sob o contrato; aceite verificado.**

| Item | Evidência |
|---|---|
| Pipeline e parâmetros versionados | `StandardScaler → LogisticRegression(C=1.0, max_iter=1000, class_weight=balanced)`, seed 42, conforme `configs/project.yaml` |
| `fit` apenas no treino | O scaler e o classificador são ajustados em `train.csv`; a validação só avalia |
| Ajuste em treino/validação, sem carregar o teste | O estágio `train` **não tem** `data/processed/test.csv` entre suas dependências; `tests/test_pipeline_definition.py::test_train_stage_never_depends_on_the_test_split` fixa isso e `tests/test_train.py::test_selection_runs_without_the_test_split` prova o isolamento por comportamento |
| Contrato precede o `fit` | `tests/test_train.py::test_contract_violation_stops_the_fit` conta as chamadas a `Pipeline.fit` com um lote de treino inválido e verifica **zero chamadas** |
| Convergência registrada | `fit.logistic_regression.converged = true`, sem avisos |
| Métricas de validação | ROC-AUC **0,714497** · precision 0,367477 · recall 0,638191 · F1 0,466397 · accuracy 0,677111 · matriz TN 2.412 / FP 1.093 / FN 360 / TP 635 |
| Recursos | wall 0,091 s · CPU 0,264 s · ΔRSS 30,6 MiB (medições em `reports/run_resources.json`, fora dos artefatos versionados) |

## 1.5 — Treinamento do Random Forest

**Implementado sob o contrato; aceite verificado.**

| Item | Evidência |
|---|---|
| Parâmetros | 300 árvores, `max_depth=8`, `min_samples_leaf=20`, `class_weight=balanced_subsample`, seed 42 — ponto de partida, não promessa de desempenho |
| Comparabilidade | Mesmas features e mesmas linhas de validação do baseline; hashes de entrada idênticos aos de 1.4 |
| Custo local | wall 1,472 s · CPU 10,478 s · ΔRSS 23,5 MiB · pico de RSS do processo 303,7 MiB. `n_jobs=-1` (configurado) usa todos os núcleos locais; não inviabilizou o ambiente e está registrado na configuração |
| Métricas de validação | ROC-AUC **0,774103** · precision 0,496985 · recall 0,579899 · F1 0,535250 · accuracy 0,777333 · matriz TN 2.921 / FP 584 / FN 418 / TP 577 |
| Matriz conferível | TN+FP+FN+TP = 4.500 = linhas de validação |

## 1.7 — Data Contract (Pandera)

**Implementado e verificado.** Implementado **antes** de 1.4/1.5, como exige o plano.

| Item | Evidência |
|---|---|
| Esquemas | `credit_monitoring_labeled_v1.0.0` (alvo binário obrigatório) e `credit_monitoring_inference_v1.0.0` (sem alvo), com a mesma definição das 19 features |
| Fonte única das regras | Bloco `contract:` de `configs/project.yaml` (`age_min`, `age_max`, `require_unique_id`, `require_positive_limit_bal`, `reject_null_features`) |
| Regras rígidas | ID único · `LIMIT_BAL > 0` · `18 ≤ AGE ≤ 100` · features obrigatórias sem nulo · presença e tipo de todas as colunas · alvo em {0,1} no esquema rotulado |
| Não proibido | Faturas negativas e códigos de pagamento não documentados permanecem aceitos (`test_negative_bill_amounts_and_undocumented_codes_are_accepted`) |
| Validação do lote integral | `validate_batch` valida o lote inteiro (inclusive colunas de governança) **antes** de selecionar as 19 entradas do modelo; a limpeza histórica de `prepare.py` não é usada como filtro de lote operacional |
| Rejeição integral | `ContractViolation` interrompe a execução; nenhuma linha é descartada. O lote é contado **uma única vez** como rejeitado, mesmo com várias regras quebradas (`test_batch_is_counted_once_when_several_rules_fail`) |
| Diagnóstico | Regra, coluna e contagem, agregados; os valores que a biblioteca devolve por linha **não** são copiados (`test_diagnostic_reports_rule_column_and_count_without_client_records`) |
| CLI | `python -m credit_monitoring.contracts.validate --input <csv> [--inference]`: saída **0** (aceito) ou **2** (rejeitado, com o diagnóstico em JSON); **1** para erro de leitura. Nenhum modelo é executado |
| Perturbações isoladas | 7 testes: duplicidade de ID, `LIMIT_BAL ≤ 0`, `AGE` 17, `AGE` 101, nulo em feature, coluna ausente, tipo incompatível, alvo inválido — todas rejeitadas; limites 18 e 100 aceitos; inferência sem alvo aceita |
| Bloqueio antes do modelo | Spy de `Pipeline.fit` com **zero chamadas** quando o contrato falha (`tests/test_train.py::test_contract_violation_stops_the_fit`) |
| Versão do contrato | `1.0.0`, propagada para `reports/metrics.json`, `models/credit_model_metadata.json` e `reports/test_metrics.json` |

Exemplo de diagnóstico (lote com 21.000 linhas e cinco violações):

```json
{
  "rejected_rows": 21000,
  "failed_rules": [
    {"rule": "age_out_of_range", "column": "AGE", "count": 1},
    {"rule": "invalid_target", "column": "default_payment_next_month", "count": 1},
    {"rule": "reject_null_features", "column": "BILL_AMT1", "count": 1},
    {"rule": "require_positive_limit_bal", "column": "LIMIT_BAL", "count": 1},
    {"rule": "require_unique_id", "column": "ID", "count": 2}
  ]
}
```

## 1.6 — Avaliação, seleção e versionamento

**Recorte local — implementado e verificado. Recorte remoto — bloqueado.**

| Item | Evidência |
|---|---|
| Regra de seleção | Maior ROC-AUC de validação, sobre métricas **não arredondadas** (`scores` em `reports/metrics.json`), com desempate explícito pelo **baseline** (`logistic_regression`) — `modeling.baseline` e `modeling.tie_break` na configuração. O resultado **não** depende da ordem de dicionário nem do arredondamento: `select_best` compara valores brutos, ordena os empatados e prefere o baseline (`test_select_best_keeps_baseline_on_tie`, `test_selection_uses_unrounded_metrics`) |
| Resultado preservado | RF selecionado (0,774103) contra LR (0,714497) — igual ao resultado histórico, verificado como não regressão |
| Decisões congeladas | Modelo, 19 features, limiar 0,5, seed, hiperparâmetros e fingerprint da configuração gravados em `models/credit_model_metadata.json` |
| Seleção × avaliação separadas | Estágios DVC distintos (`train` e `evaluate`). `train` não depende do teste; `evaluate` não altera a seleção (`tests/test_evaluate.py::test_evaluation_does_not_change_the_selection`) |
| Protocolo congelado na avaliação final | `evaluate` confere o `model_sha256` do artefato contra o congelado, confere a lista de features e só então prevê; um artefato adulterado é recusado (`test_evaluation_refuses_a_model_that_does_not_match_the_frozen_hash`) |
| Recarga do modelo | Verificada a cada execução: diferença máxima de probabilidade 0,0 dentro da tolerância declarada de 1e-12 (`reload_check` em `reports/metrics.json`) |
| Metadados completos | Limiar, features, seed, `config_sha256`, `train_sha256`, `validation_sha256`, `model_sha256`, `git_sha`, versão do contrato, exposição do teste, ambiente (Python, scikit-learn, pandas, numpy, plataforma) e `reload_check` |
| Exposição declarada | `test_exposure` nos metadados e no relatório de avaliação final |
| Avaliação final (teste, RF) | ROC-AUC **0,777198** · precision 0,497115 · recall 0,605422 · F1 0,545948 · accuracy 0,777111 · matriz TN 2.894 / FP 610 / FN 393 / TP 603 |
| Reprodutibilidade | `uv run dvc repro -f` duas vezes consecutivas produz `dvc.lock` e artefatos **byte-a-byte idênticos** (`dvc status` limpo ao final) |
| Sem arquivo com dois donos | Teste `test_no_file_is_tracked_as_the_output_of_two_stages` garante que nenhum arquivo é saída de dois estágios |
| Recuperação remota | **Proveda** — ver a seção 1.6.1 abaixo |

### Observação sobre reprodutibilidade e metadados

Duas decisões de projeto merecem registro:

1. **Sem carimbo de tempo nos artefatos versionados.** Um `created_at` tornaria `dvc.lock`
   instável a cada execução. A proveniência temporal vem do histórico Git e do próprio `dvc.lock`;
   a versão do ambiente fica nos metadados.
2. **Medições de recursos fora dos artefatos versionados.** Tempo e memória variam a cada
   execução. Elas ficam em `reports/run_resources.json` (ignorado pelo Git, não é saída DVC) e
   serão registradas no MLflow na fase 3. A fase 3 deve tratar esse arquivo como entrada
   opcional, não como fonte versionada.

### 1.6.1 — Prova de recuperação remota (DagsHub)

Executada em 2026-10-26, em **checkout e cache DVC separados** do projeto de origem, conforme o
plano exige ("não limpar o cache de trabalho para testar").

| Passo | Comando | Resultado |
|---|---|---|
| 1 | `git clone --branch fase-1-bill https://github.com/fabiopolli/pos-ml-eng-tech-challenge-fase-04.git` | Clone novo, **sem cache DVC** (`.dvc/cache` inexistente) |
| 2 | `scripts/configure_dagshub.sh <caminho_do_.env>` | Remote configurado no clone; credenciais só em `.dvc/config.local` |
| 3 | `uv run dvc pull -r dagshub` | `25 files fetched and 23 files added` |
| 4 | `uv run dvc status` | `Data and pipelines are up to date.` |
| 5 | `diff dvc.lock` (clone × projeto de origem) | **Idêntico** |
| 6 | `uv run dvc repro -f` no clone | Todos os artefatos **byte-a-byte idênticos** aos do projeto de origem |
| 7 | Inferência com o modelo recuperado | Probabilidades equivalentes em `3,33e-16` (tolerância declarada 1e-12); ROC-AUC **0,777198**, igual ao publicado |

Hashes conferidos no clone recuperado (todos iguais aos do projeto de origem):

| Artefato | SHA-256 |
|---|---|
| `data/default of credit card clients.xls` | `63c47faa4cf5e224c3494cd5f776721bcdc4a374ecf16665632f3afab8f38a44` |
| `data/raw/default_of_credit_card_clients.csv` | `1fc7fe04822413cf48d0f5ca974cbe47061b21ea10fa1d114bb56b8feac79358` |
| `data/processed/train.csv` | `9ebd48b6d31c67f46cc28aff0bde36b48f62936aff0011007b7cb78d26108c26` |
| `data/processed/validation.csv` | `e910967511f31406edbc3c9fe0528571d079c45da10116dba4e53e379d285106` |
| `data/processed/test.csv` | `70642cbcc74972400e63df96e78e1e07497f15b6b15fe278f232aaf18b725729` |
| `data/reference/reference.csv` | `9ebd48b6d31c67f46cc28aff0bde36b48f62936aff0011007b7cb78d26108c26` |
| `models/credit_model.joblib` | `a5a4a740902fab9efa5138f98917a8a7f447c5af7f7d97b707290c205c1e0464` |

**Defeito encontrado e corrigido por esta prova.** Na primeira tentativa, o clone recuperado
divergiu do `dvc.lock`: o diretório `src/credit_monitoring/contracts` é uma dependência do estágio
`train`, e o hash do diretório incluía `__pycache__`, presente na árvore de trabalho do projeto de
origem e ausente no clone. O `dvc.lock` passava a descrever o mesmo código de forma diferente em
máquinas diferentes. Correção: `.dvcignore` passou a excluir `__pycache__/` e `*.py[cod]`, e o
lock foi regenerado e republicado (commit `80c9694`).

**Observação sobre o `git_sha` nos metadados.** Ao reexecutar `dvc repro -f` no clone, o único
arquivo cujo hash muda no `dvc.lock` é `models/credit_model_metadata.json`: o campo `git_sha`
registra o commit do checkout que produziu o artefato (no clone, o HEAD é diferente). Todas as
demais saídas — dados, modelo e relatórios — permanecem byte-a-byte idênticas. É o comportamento
esperado de metadados que registram a versão do código, e está documentado no registro de
transferência.

---

## Checklist do gate M1

- [x] Bruto recuperado com hash conferido e script de aquisição versionado; proveniência (hash
      XLS, hash CSV, DOI, licença CC BY 4.0) em `docs/DATASET.md`.
- [x] `uv run dvc status` sem estágios modificados; `dvc.lock` coerente com o código.
- [x] Contrato Pandera integrado antes do `fit`: lote válido aceito, 7+ perturbações isoladas
      rejeitadas, zero chamadas ao estimador em falha.
- [x] Split 70/15/15 auditado (tamanhos, taxas, seed, IDs disjuntos) e referência = treino por hash.
- [x] Dois modelos comparados na validação; regra de desempate explícita e testada.
- [x] Seleção e avaliação final em estágios separados; o ciclo de treino não avalia o teste.
- [x] Modelo recarregado com probabilidades equivalentes dentro de tolerância declarada.
- [x] Metadados completos: limiar, features, seed, hashes de dados/modelo, SHA Git, versões,
      versão do contrato, exposição do teste declarada.
- [x] Objetos DVC no DagsHub e recuperação em checkout/cache separado, com hashes conferidos e
      inferência do modelo recuperado (seção 1.6.1).
- [x] `docs/evidence/fase-1.md` com seções 1.1–1.7, comandos, códigos de saída e hashes.

**M1: concluído.** Os dez itens do checklist estão verificados, com evidência registrada em
`docs/evidence/fase-1.md`: caminho local e prova de recuperação remota executados e
documentados. A manutenção do remote e do `dvc.lock` continua a cada commit de código (push e lock
precisam andar juntos).

## Transferência para a fase 2

| Item | Valor |
|---|---|
| SHA do código | `80c9694` (`git_sha` nos metadados; commit de código anterior ao commit de artefatos) |
| `dvc.lock` | versionado no branch `fase-1-bill`, coerente com o código |
| Hash do treino / validação / teste / referência | `9ebd48b6…` / `e9109675…` / `70642cbc…` / `9ebd48b6…` |
| Hash do modelo | `a5a4a740…` (5.490.002 B) |
| Features | 19 features financeiras (`LIMIT_BAL`, `PAY_0`, `PAY_2`–`PAY_6`, `BILL_AMT1`–`BILL_AMT6`, `PAY_AMT1`–`PAY_AMT6`) |
| Versão do contrato | `1.0.0` |
| Seleção e limiar | `random_forest`, limiar 0,5, ROC-AUC de validação 0,774103 |
| Exposição do teste | declarada na seção 1.2.1 |
| Relatório de preparação | `data/processed/preparation_report.json` |
| Comandos válidos | `uv run dvc repro`; `uv run dvc push -r dagshub` (após autorização); `uv run dvc pull -r dagshub` (em checkout/cache separado) |

## Pendências que exigem a equipe

1. **Credenciais do DagsHub** — resolvido em 2026-10-26: remote configurado, 25 objetos enviados
   e recuperação provada em checkout separado (seção 1.6.1).
2. **Decisão sobre o XLS de 5,5 MB no Git** — **resolvida em 2026-10-26**: o workbook original foi
   migrado para o DVC (ponteiro versionado no Git, objeto no cache e no remote). O `dvc push`
   seguinte a cada commit de código mantém o remote em dia com o `dvc.lock`.
3. **Cobertura de Concept Drift** (citada na p. 2 do enunciado, não detalhada na rubrica) —
   pendência que a fase 2 deve tratar antes do aceite final.
4. **Publicação da branch** — concluída: a branch `fase-1-bill` foi publicada em
   `origin/fase-1-bill` com autorização do operador. O PR para `main` continua sendo decisão da
   equipe.

## Limitações conhecidas desta execução

- **A CI não valida o `dvc.lock`.** O workflow executa `uv sync --dev --locked`, formatação,
  lint, testes e `uv build`, mas não `dvc repro` nem `dvc status`. A coerência do lock foi
  verificada localmente nesta execução. Acrescentar essa verificação à CI exigiria decidir se as
  figuras (saídas DVC) são byte-idênticas entre plataformas — verificação não feita aqui.
  A versão do `uv` na CI foi alinhada em `0.12.18`, a mesma que gravou o `uv.lock`.
- **Nenhum modelo foi avaliado em outro hardware.** As métricas de recursos valem para a
  máquina local registrada em `reports/run_resources.json`.
- **Ressalva de comparabilidade estatística:** o dataset é de Taiwan (2005) e o modelo é
  acadêmico; não há base para alegar desempenho em população brasileira atual nem para conceder
  crédito real.
