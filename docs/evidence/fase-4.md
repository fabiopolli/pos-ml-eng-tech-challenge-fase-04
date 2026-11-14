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
| 4.2 | Plano de privacidade/LGPD | `GOVERNANCE.md` §2 | Documentado como **proposta**; base legal, prazos, responsáveis e acesso dos avaliadores **pendentes** |
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

### 2.1 Integridade dos insumos usados nesta execução

| Verificação | Resultado |
|---|---|
| `data/raw/default_of_credit_card_clients.csv` SHA-256 | `1fc7fe04…79358`, igual a `expected_csv_sha256` |
| Partições após normalizar CRLF→LF (MD5) | treino `dd57d28d…`, validação `b3b78304…`, teste `43d9bfda…` — **iguais ao `dvc.lock`** |
| SHA-256 da validação normalizada | `e910967511f3…`, igual ao registrado em `reports/metrics.json` |
| Matriz de confusão da validação com o modelo local | TN 2.921, FP 584, FN 418, TP 577; ROC-AUC 0,774103 — **igual** ao registrado |
| Hash do modelo local | `fb20f6f96d80…` — **diferente** do oficial `a5a4a740…` |

Os arquivos locais de `data/processed/` têm quebras de linha CRLF (gerados no Windows) e por
isso o hash bruto difere do `dvc.lock`; o conteúdo é o mesmo. O modelo local foi treinado em
23/10 no Windows: reproduz a validação oficial, mas **não é o objeto DVC oficial**.
**Ação pendente:** após `dvc pull`, reexecutar o comando e conferir `model_file_sha256`.

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

- **DVC neste checkout:** `uv run dvc status` falha com
  `config file error: extra keys not allowed @ data['remote']['dagshub']['auth']`. O
  `.dvc/config.local` desta máquina tem as chaves `auth` e `user`, que o DVC 3.67.1 rejeita para
  um remote S3; as credenciais devem ficar em `access_key_id`/`secret_access_key`, conforme
  [`DAGSHUB.md`](../DAGSHUB.md) (`scripts/configure_dagshub.sh`). Sem corrigir isso, não é
  possível fazer `dvc pull` aqui. Não foi alterada nenhuma configuração local.
- O workbook `.xls` não está materializado neste checkout; o estágio `acquire` só roda após
  `dvc pull`.
- Não foi feita reprodução em checkout e cache separados, nem conferência do acesso dos
  avaliadores.

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

- decisão humana: base legal, prazos e responsáveis de retenção, gatilhos de suspensão,
  responsável por alertas (`GOVERNANCE.md` §6);
- `dvc pull` com credenciais corrigidas e reexecução da análise de viés com o modelo oficial;
- acesso de leitura dos avaliadores (DagsHub e vídeo);
- link do vídeo no README (4.5/4.6);
- reprodução em checkout/cache separado e conferência das 28 entregas (4.7).
