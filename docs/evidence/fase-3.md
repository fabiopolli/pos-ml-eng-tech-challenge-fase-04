# Etapa 3 | Observabilidade de pipelines e modelos

O comando operacional abre uma tentativa por lote e registra processamento, contrato,
inferência e consulta ao resultado congelado de drift da Etapa 2. O registro local tem um
ID próprio e é espelhado no MLflow. O painel operacional consulta o histórico local e
identifica o run correspondente.

## Cobertura das entregas

| ID | Implementação e verificação |
|---|---|
| 3.1 | Eventos JSONL correlacionados e resumo atômico por ID. Os testes cobrem encerramento em sucesso, rejeição e falha. |
| 3.2 | Duração e CPU em segundos, pico de memória em MiB e volume do lote contado uma vez. |
| 3.3 | Experimento local `credit-scoring-fase-04` em SQLite e artefatos locais. Teste verifica leitura posterior pela API do MLflow. |
| 3.4 | Registro de SHA Git, estado do checkout, configuração, lockfiles, hashes e métricas congeladas por origem. Os testes conferem a associação do run e o resumo anexado. |
| 3.5 | Streamlit com seleção por ID, última tentativa, última bem-sucedida, saúde, histórico, métricas e HTML. A matriz sintética exercita o painel via AppTest. |
| 3.6 | Alertas deduplicados por tentativa, tipo e feature. A fonte do alerta PSI é o snapshot M2 verificado. |
| 3.7 | Matriz automatizada com fixtures e matriz executada com os objetos oficiais M2. Os IDs e resultados estão abaixo. |

## Reproduzir o aceite oficial

Na raiz do repositório, use Python 3.12 e configure o acesso local conforme
[DagsHub e DVC](../DAGSHUB.md). Recupere apenas os objetos necessários:

```bash
uv sync --dev --locked --extra observability --extra drift
uv run --no-sync dvc pull data/reference/reference.csv data/production/v1.0.2/original.csv data/production/v1.0.2/modified.csv data/production/v1.0.2/manifest.json models/credit_model.joblib models/credit_model_metadata.json reports/drift/prediction_summary-v1.0.2.json
```

Execute cada cenário em um processo separado. A saída contém o ID da tentativa e do run.

```bash
uv run --no-sync python -m credit_monitoring.monitoring.observe original
uv run --no-sync python -m credit_monitoring.monitoring.observe modified
uv run --no-sync python -m credit_monitoring.monitoring.observe invalid
uv run --no-sync python -m credit_monitoring.monitoring.observe execution-error
```

| Cenário | Estado esperado | Entrada / aprovados / rejeitados / inferidos | Alertas esperados |
|---|---|---|---|
| Original | `succeeded` | 4500 / 4500 / 0 / 4500 | 0 pelo snapshot oficial M2 |
| Modificado | `succeeded` | 4500 / 4500 / 0 / 4500 | `LIMIT_BAL` e `PAY_AMT1` pelo snapshot M2 |
| Inválido | `rejected` | 4500 / 0 / 4500 / 0 | `contract_failure` por limite de crédito não positivo |
| Erro de execução | `failed` | 4500 / 4500 / 0 / 0 | `execution_failure` na etapa de inferência |
| Diretório vazio | Histórico vazio | Indisponível | Sem ocorrências |

Os números da tabela são critérios de aceite. Use os IDs reais produzidos acima para comparar
`observability/runs/<id>/events.jsonl`, `summary.json`, o run MLflow e a tela.
Os códigos de saída são 0 para sucesso registrado, 1 para falha, 2 para rejeição e 3 para
processamento bem-sucedido com tracking indisponível.

Abra os dois serviços em terminais separados, a partir da raiz. Encerre com Ctrl+C.

```bash
uv run --no-sync mlflow ui --backend-store-uri sqlite:///observability/mlflow.db --host 127.0.0.1
uv run --no-sync streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

Para usar outro diretório, configure `OBSERVABILITY_DIR` no ambiente de ambos os processos e
obtenha a URI correspondente com `uv run --no-sync python -m credit_monitoring.monitoring.observe tracking-uri`.
Use um diretório local vazio para demonstrar o estado sem execuções. Aplique `MLFLOW_EXPERIMENT_NAME`
no ambiente do produtor para escolher outro experimento.

## Limites das medições e do registro

- Duração monotônica e CPU cobrem o processamento da tentativa até sua finalização, antes do
  envio ao MLflow. As etapas têm medições próprias. `predict_proba_s` mede somente a chamada
  ao modelo. O serviço de inferência verifica novamente o contrato antes da predição.
- O pico de memória é do processo atual, desde seu início. Linux usa `getrusage` em KiB,
  macOS em bytes e Windows usa o pico do working set em bytes. O resumo converte para MiB.
  Processos filhos ficam fora da medição.
- O cenário inválido altera em memória um limite de crédito. A falha controlada é injetada
  na inferência, após aprovação pelo contrato. Os dois preservam as entradas DVC.
- Um encerramento abrupto pode deixar a última etapa com registro incompleto. O resumo conserva
  o estado em curso ou interrompido. Uma nova tentativa recebe outro ID.
- O PSI é lido do snapshot agregado M2 após conferir a identidade dos artefatos. O HTML é
  identificado como relatório congelado. A recuperação por DVC e a consulta ao painel ficam
  fora da contagem de tentativas. As métricas de validação e teste provêm de M1.

## Execução no checkout atual

O DVC recuperou os sete objetos oficiais com uma credencial já configurada em outro checkout
e disponibilizada temporariamente ao processo de download. Cada cenário foi executado em um
processo separado e produziu um resumo local e um run MLflow.

| Cenário | Estado | Execução | Run MLflow | Entrada / aprovados / rejeitados / inferidos |
|---|---|---|---|---|
| Original | `succeeded` | `9af206137f454721ab2b39060fb8bb17` | `f060332717824db496d6d164c3984072` | 4500 / 4500 / 0 / 4500 |
| Modificado | `succeeded` | `897a4a101d684f3abfade93d6c8acb45` | `3104469c264e4e4aa4d6a59fcc755494` | 4500 / 4500 / 0 / 4500 |
| Inválido | `rejected` | `d0d02b2d213043b29657b34abae3301b` | `9eb0d3fd9d9940c4997ecf268901b51f` | 4500 / 0 / 4500 / 0 |
| Erro de execução | `failed` | `5cc1ec5ee47349fcb7f05a30257250a8` | `6b1410d029f3455e87609b720939b5a9` | 4500 / 4500 / 0 / 0 |

O controle não emitiu alertas. O cenário modificado sinalizou `LIMIT_BAL` (PSI 0,752498) e
`PAY_AMT1` (PSI 0,464748). Os cenários inválido e de erro emitiram, respectivamente,
`contract_failure` e `execution_failure`.

A tentativa anterior `7afff2d7755242779a15687ffedb73e0` preserva a evidência de entrada ausente,
com estado `failed` e run MLflow `cea35492c2d24f01a30977b3195bb7be`.

### Validação no navegador com Playwright

Playwright 1.65.1 executou os quatro cenários oficiais e o estado vazio no Microsoft Edge,
com o Streamlit em loopback. Para cada cenário, o teste selecionou o ID da tentativa e
conferiu o ID do run MLflow, o estado, as quatro contagens e os alertas. Para as duas
execuções bem-sucedidas, baixou o relatório e comparou o SHA-256 com o resumo da tentativa.
No estado vazio, verificou o aviso e a ausência de seletor e métricas. Os cinco casos passaram.

Capturas do painel em [`docs/evidence/fase-3-playwright/`](fase-3-playwright/).

- [Lote de controle](fase-3-playwright/01-original.png) — 4.500 inferências e zero alertas.
- [Lote modificado](fase-3-playwright/02-modified.png) — 4.500 inferências e dois alertas de drift.
- [Lote inválido](fase-3-playwright/03-invalid.png) — 4.500 rejeições e zero inferências.
- [Falha controlada](fase-3-playwright/04-execution-error.png) — falha após aprovação e zero inferências.
- [Painel sem execuções](fase-3-playwright/05-sem-execucoes.png) — estado vazio.
- [Detalhe do PSI](fase-3-playwright/06-detalhe-psi.png) — distribuição de scores e tabela do lote modificado.

### Matriz sintética verificada em 11/11/2026

| Cenário | Estado | Execução | Run MLflow | Duração (s) | CPU (s) | Pico (MiB) |
|---|---|---|---|---:|---:|---:|
| Original | `succeeded` | `88a877fd8f3941dcabb5ac32b615294f` | `9e602879e7834dd798c0e9fda345c098` | 0,175 | 0,172 | 346,4 |
| Modificado | `succeeded` | `f245d80138d140de851333419d9e0a9f` | `7ce871e09f2a4fd882aa3193cf887288` | 0,065 | 0,062 | 379,1 |
| Inválido | `rejected` | `117f8f4973a54139989c9767dcf0d1f7` | `52925da21add427f9c9a51c633b9b797` | 0,035 | 0,031 | 379,7 |
| Erro de execução | `failed` | `133a39a95c2d4f02b3966f9fd2c8b012` | `0e13f9e3e5c34fc5b84fa77536346769` | 0,034 | 0,031 | 380,1 |

Os lotes sintéticos têm 12 registros e compartilham o mesmo processo de teste. A medição de
pico é acumulada no processo. O AppTest confirmou o estado vazio, a consulta dos quatro IDs e
a contagem de alertas por tentativa. Os testes também verificaram falha de tracking, preservação
do motivo primário e interrupção antes da inferência quando o hash do lote diverge.

Ruff e a checagem de formatação passaram. No Windows, passaram 109 testes, incluindo os quatro
testes de observabilidade. Quatro módulos antigos foram excluídos da coleta por dependerem do
módulo Unix `resource`. Dois casos adicionais foram excluídos após reproduzir dependências do
mesmo módulo e de um caminho fixo `/tmp`.
