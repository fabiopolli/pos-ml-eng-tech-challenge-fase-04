# Evidências | Fase 4 — Governança e apresentação

> Registro de verificação da documentação 4.1–4.5, gerado em 2026-11-14 na branch
> `docs/denis/fase-4-governanca`. Distingue o que foi **executado e conferido** do que
> permanece **pendente**. O vídeo (4.6) e a reprodução final (4.7) não estão cobertos aqui.

- Documento principal: [`docs/GOVERNANCE.md`](../GOVERNANCE.md); resumo no [`README`](../../README.md).
- Plano de execução: [`docs/plans/fase-4-governanca-apresentacao.md`](../plans/fase-4-governanca-apresentacao.md).

## 1. Cobertura das entregas

| ID | Entrega | Onde está | Estado |
|---|---|---|---|
| 4.1 | Tratamento e origem dos dados | `GOVERNANCE.md` §1 (fluxo, variáveis pessoais, inventário por artefato) | Documentado; inventário conferido contra `.gitignore`, `dvc.yaml` e `git ls-files` |
| 4.2 | Plano de privacidade/LGPD | `GOVERNANCE.md` §2 | Documentado como **proposta acadêmica** com revisão jurídica **simulada** (decisão do grupo, 2026-11-14); acesso dos avaliadores declarado, sem verificação independente; eliminação de dados a executar e registrar após a avaliação |
| 4.3 | Governança do modelo e viés agregado | `GOVERNANCE.md` §3; `src/credit_monitoring/models/bias.py`; `reports/bias/validation_bias.json` | Implementado e executado; resultado descritivo |
| 4.4 | Análise causal e resposta | `GOVERNANCE.md` §4 | Documentado; ancorado em `reports/drift/results-v1.0.2.json` |
| 4.5 | README consolidado | `README.md` (seções "Governança e LGPD" e "Análise causal") | **Parcial**: falta o link do vídeo e a validação por outro integrante |
| 4.6 | Vídeo STAR | — | Pendente (outro integrante) |
| 4.7 | Reprodução e matriz final | §4 e §5 abaixo (rascunho) | Pendente |

## 2. Análise de viés agregada (4.3)

Comando (na raiz, com o ambiente `uv sync --dev --locked`):

```bash
uv run python -m credit_monitoring.models.bias
```

Saída esperada: `Analise de vies: random_forest em 4500 linhas de validacao`, e o arquivo
`reports/bias/validation_bias.json` (agregado; sem linhas nem IDs).

Controles implementados e testados em `tests/test_bias.py`:

- o teste não é lido (o teste remove `test.csv` antes de executar);
- o relatório soma exatamente 4.500 linhas em cada família de grupos e não contém `ID`;
- grupos com menos de 30 linhas são suprimidos; taxas com denominador menor que 30 ficam
  indefinidas;
- a execução **recusa** gerar o relatório se modelo e partição não reproduzirem a matriz de
  confusão de validação de `reports/metrics.json`.

### 2.1 Integridade dos insumos

Execução final (2026-11-14), com os objetos oficiais recuperados por `dvc pull -r dagshub`:

| Verificação | Resultado |
|---|---|
| Modelo (`models/credit_model.joblib`) | MD5 `95e041c6…` (igual ao `dvc.lock`); SHA-256 `a5a4a740902f…`, **igual** ao de `reports/test_metrics.json` |
| Validação (`data/processed/validation.csv`) | MD5 `b3b78304…` (igual ao `dvc.lock`); SHA-256 `e910967511f3…`, **igual** ao de `reports/metrics.json` |
| Matriz de confusão da validação | TN 2.921, FP 584, FN 418, TP 577 — **igual** ao registrado em `reports/metrics.json` |
| Resultados da análise | **Idênticos** aos de uma execução anterior com artefatos regenerados localmente no Windows (que tinha hash de modelo diferente e arquivos com CRLF) |

A execução anterior serviu de pré-verificação: o modelo local reproduzia a validação oficial, mas
não era o objeto DVC. Com o `dvc pull`, `model_file_sha256` do relatório passou a ser o oficial.

## 3. Verificações executadas

| Verificação | Resultado |
|---|---|
| `uv run ruff check .` | Sem problemas |
| `uv run ruff format --check .` | 93 arquivos formatados |
| `uv run pytest tests/test_bias.py` | 5 testes passaram |
| `uv run pytest` (excluindo `test_evaluate`, `test_promotion`, `test_train`, `test_tuning`) | 114 passaram, 2 falharam |

As falhas e exclusões decorrem do **ambiente Windows**, não desta mudança: `train.py` e
`tune.py` importam o módulo Unix `resource` (4 arquivos de teste não coletam;
`test_app_dev::test_the_application_never_fits_or_evaluates_a_model` falha pelo mesmo motivo),
e `test_features::test_reload_preserves_the_transformation_and_the_probabilities` falha por falta
de `lz4`. Rodar a suíte completa em Linux/CI continua pendente. O módulo `bias.py` evita
importar `train` justamente para funcionar no Windows.

## 4. Observações para a reprodução final (4.7)

- **DVC neste checkout:** a configuração local foi corrigida (credenciais em
  `access_key_id`/`secret_access_key` de `.dvc/config.local`, conforme
  [`DAGSHUB.md`](../DAGSHUB.md)) e o `dvc pull -r dagshub` recuperou os objetos oficiais, com
  hashes conferidos (§2.1). Isso não é a prova de recuperação em **checkout e cache separados**,
  que continua pendente (4.7): o cache local deste diretório já existia.
- **`dvc status` com o Git limpo (investigado em 2026-11-14):** o comando lista quase todo o
  código em `src/`, `configs/optimization.yaml` e os JSON/HTML de `reports/` como modificados.
  **Causa: quebras de linha**, não alteração de conteúdo. O checkout Windows tem
  `core.autocrlf=true` e não há `.gitattributes`; o Git guarda LF (`git ls-files --eol` mostra
  `i/lf w/crlf`), mas o DVC calcula o MD5 sobre os bytes do disco (CRLF). Conferência feita
  sobre **todos** os arquivos de `dvc.lock` que existem no disco: 44 arquivos, dos quais 29
  coincidem com o `dvc.lock` apenas após normalizar CRLF→LF, 15 coincidem direto e **0 divergem**
  (10 entradas são diretórios ou não existem no disco e não foram comparadas). Portanto o
  `dvc.lock` está coerente com o código versionado. Não foi alterada nenhuma configuração do Git;
  uma opção é adotar um `.gitattributes` com `eol=lf` (decisão do time, afeta todos os
  checkouts). Em Linux/CI, ou em checkout com LF, o `dvc status` deve ficar limpo.
- **Remote:** `uv run dvc status -c -r dagshub` retorna "Cache and remote 'dagshub' are in sync"
  (2026-11-14), ou seja, os objetos do `dvc.lock`, incluindo os lotes `v1.0.1` e `v1.0.2`
  referenciados pelo pipeline, estão no remote.
- **Conferência de números:** as tabelas de viés de `GOVERNANCE.md` e do README e os valores de
  PSI, score e contagem da classe 1 foram comparados automaticamente com
  `reports/bias/validation_bias.json` e `reports/drift/results-v1.0.2.json`: 115 valores
  conferidos, nenhuma divergência. Premissas do dataset (Taiwan, 2005, NT$) conferem com
  [`DATASET.md`](../DATASET.md).
- **Acesso dos avaliadores:** o grupo declarou em 2026-11-14 que todos os repositórios estão
  liberados para os avaliadores. É declaração, **sem captura de tela nem verificação
  independente** (não foi testado com uma conta sem permissão).

## 5. Matriz de cobertura (rascunho, por critério oficial)

Não substitui a conferência das 28 entregas, que continua pendente (4.7).

| Critério (peso) | IDs | Evidência | Estado |
|---|---|---|---|
| Validação de dados (25%) | 1.7, 2.4 | [`fase-1.md`](fase-1.md), testes do contrato | Concluído nas fases anteriores |
| Detecção de drift (25%) | 2.2, 2.6, 2.7 | [`fase-2.md`](fase-2.md), `reports/drift/results-v1.0.2.json` | Concluído (Data Drift; Concept Drift não demonstrado) |
| Observabilidade (20%) | 3.1–3.7 | [`fase-3.md`](fase-3.md) | Concluído |
| Governança (15%) | 4.1–4.5 | Este arquivo e `GOVERNANCE.md` | Documentado; pendências humanas listadas |
| Vídeo STAR (15%) | 4.6 | — | Pendente |

## 6. Pendências

- limitações assumidas (`GOVERNANCE.md` §6): revisão jurídica simulada, prazos de 5 anos e 24
  meses como propostas acadêmicas, resumo da ANPD não verificado na fonte, acesso dos avaliadores
  apenas declarado;
- `dvc pull` com credenciais corrigidas — **feito**; falta apenas a prova em checkout/cache separado (4.7);
- acesso de leitura ao vídeo, quando publicado;
- eliminação de objetos e caches após a conclusão da avaliação, com evidência;
- link do vídeo no README (4.5/4.6);
- reprodução em checkout/cache separado e conferência das 28 entregas (4.7).
