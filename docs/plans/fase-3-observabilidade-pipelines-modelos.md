# Fase 3 — Observabilidade de Pipelines e Modelos

> Plano de execução, revisado em 2026-11-02 contra o estado real do código após a conclusão de
> M1 e M2. Expande os IDs 3.1–3.7; não atesta implementação.

- **Plano geral:** [escopo, protocolo e aceites](plano-de-trabalho-TC4.md).
- **Entrada:** [fase 2](fase-2-simulacao-deteccao-drift.md), marco M2 — concluído.
- **Próxima fase:** [Governança e Apresentação](fase-4-governanca-apresentacao.md).
- **Referências:** [arquitetura](../ARCHITECTURE.md), [checklist](../CHECKLIST.md),
  [governança](../GOVERNANCE.md), [evidência M1](../evidence/fase-1.md),
  [evidência M2](../evidence/fase-2.md) e
  [adendo 1.6-O6](1.6-O6-data-drift-no-laboratorio.md).

## 1. Resultado e fronteiras

Construir uma trilha observável entre etapas, dados/modelo, resultados e alertas, exibida no
MLflow local e no Streamlit. Demonstrar controle, drift válido, rejeição de contrato e falha de
execução, além do estado sem execuções. Medir recursos do processo local com unidades e limites.

Não criar serviço de alertas externo, compute remoto ou retreinamento automático. Um alerta de
drift pode coexistir com execução tecnicamente bem-sucedida; contrato inválido bloqueia o modelo.
O Streamlit é consumidor de evidências, não deve treinar nem refazer inferência ao renderizar.

### 1.1 Estado real verificado na data da revisão

| Item | Estado observado | Consequência para a fase 3 |
|---|---|---|
| `src/credit_monitoring/monitoring/` | Contém `drift.py`, `drift_snapshot.py`, `report_context.py` e `drift_report_template.html` | Criar módulos operacionais **novos** ao lado desses; não duplicar o detector de drift |
| `logging`/MLflow em `src/` | Nenhuma ocorrência de `import logging`, `logging.getLogger` ou `mlflow` | 3.1 e 3.3 começam do zero; nada de logging existe para "centralizar" |
| `dashboard/app.py` | Shell de 15 linhas com três `st.metric` de placeholder (`"Aguardando execução"`, `"-"`, `"-"`) | 3.5 substitui os placeholders; não há integração parcial a preservar |
| `dashboard/app_dev.py` | Laboratório read-only que já lê o snapshot `1.0.2` de drift | Fronteira mantida: o laboratório **não** é o painel operacional |
| `InferenceResult.duration_s` | Mede apenas a chamada `predict_proba`, não a etapa | Não é registro operacional completo; 3.2 precisa de escopo declarado |
| `score_production` | Grava resumo `_stable_inference_summary` **sem** duração, por desenho | Output DVC deve permanecer imutável; registros variáveis vão para fora do DVC |
| `train.py` / `tune.py` | Já medem `wall_time_s`, `cpu_time_s`, RSS e pico via `measure_resources`/`_rss_mib` | 3.2 reaproveita o padrão existente em vez de inventar outra métrica |
| `ContractViolation` | Preserva regra, coluna e contagem, sem linhas nem valores | Base pronta para o alerta de contrato em 3.6 |
| Suíte de testes | 18 arquivos; `test_app_dev.py` existe, **não** há teste de `dashboard/app.py` | 3.5 precisa de suíte nova |
| `.gitignore` | Já ignora `mlruns/`, `mlflow.db`, `*.log`, `reports/run_resources.json` e `reports/optimization/*/resources.json` | Precedente de destino local já ignorado. **Não** reutilizar `reports/run_resources.json`: ele é gravado pelo estágio `train`; os registros de execução M3 precisam de caminho próprio, também ignorado |

## 2. Entrada e dependências

M2 está concluído. A entrada da fase 3 não é abstrata: são artefatos existentes, versionados por
hash, com schema definido.

### 2.1 Artefatos de entrada (existentes, não a criar)

| Artefato | SHA-256 | Papel na fase 3 |
|---|---|---|
| `models/credit_model.joblib` | `a5a4a740902fab9efa5138f98917a8a7f447c5af7f7d97b707290c205c1e0464` | Modelo vigente (Random Forest) |
| `data/reference/reference.csv` | `9ebd48b6d31c67f46cc28aff0bde36b48f62936aff0011007b7cb78d26108c26` | Referência = treino, base do PSI |
| `data/production/v1.0.2/original.csv` | `d9f855a77f8fb6916fded48b880d18fa48e4c4816070167f4caf8af6ad874d65` | Lote de controle (4.500 linhas) |
| `data/production/v1.0.2/modified.csv` | `8da682f306f25003c98e851e84dda427b25daac41dfdf9474a13b6f641f71fc7` | Lote com drift sintético (4.500 linhas) |
| `data/production/v1.0.2/manifest.json` | `d0e983fa175115e96f508d08512006b23af4e00f3a7f81e4368bd58ded528ee9` | Protocolo `1.0.2`, `scenario_id=phase-2-1.0.2`, seed 42 |
| `data/production/v1.0.2/predictions/{original,modified}.csv` | `76c3821e…` / `49748dd0…` | Predições com ID de origem associado |
| `reports/drift/prediction_summary-v1.0.2.json` | `a92f59f6c525877be209cd4804c603334161153a23093237ded53ab2696a742a` | Resumo agregado por cenário |
| `reports/drift/results-v1.0.2.json` | `f0c02e97fbb3a6301ec1cf65593c9c7977f051bd4c4a2eec7c1276b45ec4bd48` | Schema `1.0.0` com comparações, hashes e limitações |
| `reports/drift/phase-2-drift-v1.0.2-ptbr-v6.html` | `d47a792b1dfb7d94ee4469ada01298d2bf0e0809e7beda2c4641ae4cf284a451` | Relatório pt-BR — **apenas no cache DVC local, ainda não no remote** |

Protocolo: `protocol_sha256=e160b86e5d6f62382859df8828f053ef16bef438a6f0967e022a99cb4ae536fb`,
contrato `1.0.0`, limiar `0,5`, Evidently `0.7.23`.

### 2.2 Schema de referência já existente

`results-v1.0.2.json` (schema `1.0.0`) é o formato canônico de drift. Suas chaves são
`comparisons`, `contract_version`, `evidently_version`, `feature_set`, `hashes`, `limitations`,
`model_sha256`, `probability_summaries`, `protocol_sha256`, `protocol_version`, `scenario_id`,
`schema_version`, `seed` e `threshold_model`. Cada comparação traz `comparison_id`,
`current_rows`, `drifted_feature_count`, `drifted_features`, `features`, `global_alert`,
`global_alert_rule`, `method`, `reference_rows`.

**Requisito:** o painel da fase 3 consome esse schema sem alterá-lo e sem inventar formato
incompatível. Novas chaves exigem `schema_version` novo, com o anterior ainda aceito.

### 2.3 Resultado observado que a fase 3 deve conseguir reproduzir

| Cenário | Resultado M2 já registrado |
|---|---|
| referência × original (controle) | Nenhuma das 19 features excedeu `0,20` |
| referência × modificada | `LIMIT_BAL` PSI `0,752498`; `PAY_AMT1` PSI `0,464748` — ambas acima do limiar |
| original × modificada | `LIMIT_BAL` PSI `0,777132`; `PAY_AMT1` PSI `0,459644` |
| Probabilidades | Média `0,423073079990242` (original) → `0,4198523230775716` (modificada); classe 1 de `1.161` → `1.154` |

A fase 3 exibe esses números como linha de base do alerta de drift. Não os recalcula: o alerta
consome o resultado congelado de M2.

### 2.4 Sequência

```text
M2 → 3.1 → 3.2 ───────────┐
     3.3 ────────────────┴→ 3.4 → 3.5 → 3.6 → 3.7 → M3
```

Configurar MLflow (3.3) não depende do cálculo de CPU/memória, mas compartilha o schema de
execuções de 3.1. Fechar esse schema antes de integrar produtores/consumidores; priorizar uma
fatia vertical de execução válida, depois adicionar alertas e cenários de falha.

## 3. Contrato de observabilidade proposto

Implementar em `src/credit_monitoring/monitoring/` e reutilizar nos pontos de entrada existentes.
O contrato abaixo é uma proposta de implementação a validar, não API já disponível.

| Campo/grupo | Regra |
|---|---|
| Identidade | `execution_id` único da aplicação; `mlflow_run_id` quando criado; `scenario_id`, etapa e versão do schema |
| Tempo | Início/fim em ISO-8601 com timezone; duração por relógio monotônico em segundos |
| Estado da execução | `succeeded`, `rejected` ou `failed` como estados finais; etapa atual e motivo sanitizado |
| Estado do drift | Avaliado com/sem alerta, ou `not_evaluated`; nunca interpretar ausência como ausência de drift |
| Rastreabilidade | SHA Git e indicador de árvore modificada, configuração/lock, hashes de dados/referência/modelo e protocolo |
| Volume | `input_rows`, `accepted_rows`, `rejected_rows`, `inferred_rows`; inteiros não negativos quando conhecidos, indisponível explicitamente identificado |
| Recursos | Duração, `cpu_time_s` e `peak_memory_mib` com plataforma/método/escopo; indisponível é nulo com motivo |
| Artefatos | Caminhos/IDs e hashes de métricas, predições e HTML; distinguir gerado agora de recuperado do cache |
| Tracking | Estado do registro MLflow, inclusive falha; execução sem tracking não vira aceite completo |

### 3.a Registro de execução como arquivo versionado

O contrato precisa de um formato concreto e persistível, não apenas de uma tabela. Requisito:

- arquivo **por execução**, fora dos outputs DVC, em caminho ignorado pelo Git;
- `schema_version` próprio, independente do `schema_version` de M2;
- escrita atômica (arquivo temporário + `os.replace`) para que um encerramento abrupto não deixe
  registro pela metade no lugar de registro completo;
- campos ausentes permanecem `null` com `reason`, nunca `0`.

**Invariante:** `entrada = aprovados + rejeitados`. Antes da leitura ou conclusão da validação,
contagens ainda desconhecidas são indisponíveis, não zeros fictícios; erro de leitura não significa
que todo o lote foi rejeitado pelo contrato. Lote rejeitado integralmente tem zero
aprovados/inferidos e rejeitados iguais à entrada. Contagens por motivo podem se sobrepor e ficam
em estrutura separada. Falha depois do contrato pode ter aprovados positivos e inferidos zero; se
houve saída parcial, registrar explicitamente, sem publicar predições como completas.

Métricas do modelo carregadas de M1 usam namespace de validação/teste e hashes do modelo; não são
medições de acurácia do lote em produção. Métricas de drift e operação usam namespaces próprios.
Não trocar resultado desconhecido por zero nem chamar score PSI de p-value.

### 3.b Reuso obrigatório do diagnóstico já existente

`ContractViolation` (`src/credit_monitoring/contracts/diagnostics.py`) já carrega `rejected_rows` e
a tupla de `FailedRule` com regra, coluna e contagem. 3.1 e 3.6 **não** reimplementam essa
extração: convertem a exceção em registro de execução e em alerta. A regra de minimização
permanece: nenhuma linha, valor de cliente ou feature individual em log, alerta ou tela.

### 3.c Separação entre snapshot determinístico e registro de execução

Dois artefatos com ciclos de vida diferentes, que não devem ser confundidos:

| | Snapshot M2 | Registro de execução M3 |
|---|---|---|
| Conteúdo | PSI, comparações, hashes, resumos agregados | Estado, duração, recursos, contagens, alertas, IDs |
| Variabilidade | Determinístico; muda só com o protocolo | Muda a cada execução |
| Versionamento | DVC, com hash estável | Fora do DVC, local e ignorado pelo Git |
| Consumidor | `drift_snapshot.py`, laboratório (`app_dev.py`) | `dashboard/app.py`, MLflow, alertas |

`drift_snapshot.py` já é o padrão de leitura defensiva do projeto: valida schema, protocolo,
cenário, contrato, hashes do modelo e dos lotes, resumo de predições, 19 features, três
comparações, contagens, `drift == (score > threshold)`, proporções e bins; não calcula PSI, não
infere e não lê linhas individuais. A fase 3 deve aplicar o mesmo rigor ao registro de execução.

**Restrição:** outputs DVC existentes (`results-v1.0.2.json`, `prediction_summary-v1.0.2.json`,
CSV de predições) **não** podem ser reescritos para carregar `execution_id`, duração ou resources.
`score_production` foi desenhado para produzir resumo estável; alterar isso invalidaria os hashes
já publicados no DagsHub. Registros operacionais vão para arquivos próprios.

### 3.d Execução e cache

DVC representa dependências/artefatos determinísticos; MLflow representa tentativas reais.
Separar instrumentação operacional de efeitos cacheáveis: `dvc repro` pode restaurar saídas
sem executar código. Nesse caso registrar restauração/cache, sem fabricar duração ou sucesso
de um novo processamento. Uma nova tentativa ganha novo `execution_id`; reabrir um registro
para consulta não cria outra tentativa nem duplica alertas.

## 4. Pacotes executáveis

### 4.1 — Implementação de logs (3.1)

**Dependências:** interfaces das fases 1/2 e schema de execução definido.

**Ações do agente:**
1. Criar contexto de execução compartilhado por validação, processamento, inferência e drift;
   emitir eventos estruturados de início/fim/erro com etapa, ID, horário e status.
2. Garantir que exceção/cancelamento finalize o estado quando tecnicamente possível e preserve
   causa sanitizada. Tentativa interrompida sem finalização não deve aparecer como sucesso.
3. Aplicar às rotinas existentes sem imprimir dataframes, tokens, variáveis de ambiente ou
   predições individuais em logs. Mensagens incluem contagem/regra, não linha completa do cliente.
4. Persistir logs locais em localização ignorada pelo Git; evitar handlers duplicados ao repetir
   importação ou recarregar Streamlit. Definir schema para leitura do resumo de cada execução.

**Verificação/aceite:** eventos possuem mesmo ID e ordem temporal coerente; sucesso, rejeição
e falha têm encerramento distinguível. Teste com exceção controlada preserva diagnóstico e não
gera sucesso. Registrar a limitação para término abrupto que impede coleta/finalização.

### 4.2 — Coleta de métricas operacionais (3.2)

**Dependências:** 3.1 e fronteiras mensuráveis de cada etapa.

**Ações do agente:**
1. Medir duração monotônica e CPU do processo; definir se inclui filhos, carregamento e I/O.
2. Coletar pico de memória com método compatível com a plataforma. Preferir processo isolado por
   tentativa se usar high-water mark do processo; não subtrair dois picos como se fossem consumo
   do intervalo. Em Linux, converter KiB para MiB quando esse for o formato da API utilizada.
3. Registrar método/unidade/plataforma, inclusive se memória de filhos não estiver coberta.
   Valor não coletado deve ser indisponível, sem assumir zero ou estimar precisão inexistente.
4. Derivar contagens sem dupla contagem; registrar falhas/alertas por execução e por tipo.
   Definir contagem de alertas como ocorrências distintas, evitando somar cada rerender da tela.
5. Medir primeira execução e registrar duração/CPU/memória como evidência de capacidade local,
   sem inventar SLA ou limite de infraestrutura que a equipe não aprovou.

**Reuso obrigatório:** `train.py` já expõe `measure_resources()` com `wall_time_s`, `cpu_time_s`,
`rss_before_mib`, `rss_after_mib`, `rss_delta_mib`, `process_peak_rss_mib`, `method` e
`platform`; `tune.py` expõe `_rss_mib()` e `cpu_time_s` por trial. O coletor da fase 3 deve
**generalizar esse padrão existente** para as etapas da fase 2, preservando os mesmos nomes de
campo e a mesma conversão KiB→MiB, em vez de criar uma segunda métrica concorrente.

**Escopo declarado (lacuna conhecida):** `InferenceResult.duration_s` mede somente a chamada
`predict_proba`. Ao reusá-lo, marcar explicitamente que é **tempo de inferência**, não duração da
etapa; a duração da etapa vem do contexto de execução de 3.1.

**Verificação/aceite:** unidades corretas, valores finitos não negativos quando disponíveis e
invariantes de volumes nos casos válido/inválido/falha. Não comparar pico medido com alocação
teórica nem prometer medir pressão total da máquina por uma métrica de processo.

### 4.3 — Configuração do MLflow (3.3)

**Dependências:** ambiente travado e convenção local de tracking; schema 3.1 para integração.

**Ações do agente:**
1. Configurar tracking local explícito, experimento do projeto e armazenamento de artefatos local,
   preferindo SQLite local conforme escopo. Garantir que aplicação e UI apontem ao mesmo backend.
2. Centralizar URI/caminhos configuráveis e validar resolução a partir da raiz; manter banco,
   artefatos e credenciais fora do Git/DVC compartilhado por padrão.
3. Criar execução mínima em diretório temporário de teste e verificar leitura de parâmetros,
   métricas e artefato; documentar como abrir a UI apenas na interface local.
4. Não trocar tracking pelo DagsHub ou provisionar servidor remoto; DagsHub guarda objetos DVC.

**Verificação/aceite:** aplicação registra e UI consulta o mesmo experimento; dados persistem
ao reiniciar a visualização. Falta de backend/permissão local gera diagnóstico, não indicação
falsa de registro. Testes usam armazenamento isolado e não poluem o experimento real.

### 4.4 — Registro de métricas e artefatos (3.4)

**Dependências:** 3.1/3.2/3.3; artefatos de M1/M2 compatíveis por hash.

**Ações do agente:**
1. Vincular `execution_id` ao run MLflow e registrar SHA/dirty flag, hashes DVC e SHA-256
   identificados pelo algoritmo, ambiente/lock, parâmetros, contrato e versão do cenário/protocolo.
2. Anexar resumos/relatórios aprovados, evitando cópia desnecessária de linhas/previsões individuais;
   referenciar objetos grandes por versão/caminho DVC. MLflow local não substitui recuperação DVC.
3. Registrar métricas de validação/teste como provenientes do artefato de avaliação congelado,
   não recalcular o teste para preencher o dashboard. Separar operação, modelo e drift.
4. Mapear estados da aplicação aos estados suportados pelo MLflow, preservando `rejected` em
   tag/campo próprio se o backend não tiver esse estado. Fechar run em exceções de forma coerente.
5. Se tracking falhar, preservar log/resumo local e expor falha de observabilidade. Não transformar
   ausência de registro em sucesso e não ocultar uma falha primária com exceção de logging.

**Verificação/aceite:** partir de uma linha de execução e encontrar dados/modelo/configuração
e HTML correspondentes. Hash incompatível impede associar artefatos. Rejeição/falha também é
consultável, inclusive quando não há HTML/predições. Nova tentativa não sobrescreve a anterior.

### 4.5 — Desenvolvimento do dashboard Streamlit (3.5)

> O [laboratório de modelos 1.6-O6](1.6-otimizacao-modelos.md#51-etapa-adicional-16-o6--laboratório-streamlit-de-modelos)
> e o [adendo de Data Drift no laboratório](1.6-O6-data-drift-no-laboratorio.md) já entregam
> `dashboard/app_dev.py`: comparação de modelos, inferência manual e leitura de snapshots
> congelados de drift. Esta entrega mantém `dashboard/app.py` como **consulta operacional de
> execuções**, separada do laboratório. Reaproveitar helpers de leitura compatíveis, preservando
> a regra de que o painel operacional não executa inferência.

**Estado atual a substituir:** `dashboard/app.py` tem 15 linhas, título "Credit Scoring -
Observabilidade", um `st.info` dizendo que as métricas serão conectadas na Etapa 3 e três
`st.metric` com valores `"Aguardando execução"` e `"-"`. Esses placeholders são o que 3.5
substitui.

**Dependências:** contrato de consulta/artefatos de 3.4.

**Ações do agente:**
1. Substituir placeholders de `dashboard/app.py` por leitura de resumos/MLflow, com lista de
   execuções, seleção por ID/cenário e indicação de hora/versão. Mostrar a última tentativa,
   distinguindo-a da última bem-sucedida para não esconder uma rejeição recente.
2. Exibir status, duração, volumes, falhas, CPU e pico de memória, com unidade e indisponibilidade.
3. Exibir versão do modelo e métricas de validação/teste com origem, features com drift, métodos,
   scores/limiares, distribuição agregada de probabilidades e acesso ao HTML compatível.
4. Tratar estados sem execuções, sem HTML, schema antigo/incompatível e tracking indisponível.
   Identificar cache de leitura e atualizar de forma controlada para não mostrar dado obsoleto.
5. Garantir interface de leitura: rerender não executa modelo, modifica dados nem gera alertas.
   Não mostrar dados individuais ou segredos; restringir caminhos de artefatos ao diretório esperado.

**Fronteira com o laboratório (não negociar):** `app_dev.py` lê o snapshot `1.0.2` congelado e
exibe as três comparações, os PSI das 19 features, os bins persistidos e os resumos agregados;
não calcula PSI, não infere e não é o painel operacional. `app.py` exibe **histórico por
execução**, incluindo estados de rejeição e falha que o snapshot congelado não representa. Os dois
aplicativos rodam em portas distintas, conforme `dashboard/README.md`.

**Verificação/aceite:** teste de aplicação (`streamlit.testing.v1.AppTest`, como já usado em
`tests/test_app_dev.py`) com fixtures reproduz vazio, sucesso, rejeição e falha; uma nova
tentativa aparece sem misturar métricas da anterior. UI apresenta indisponível, não zero, nos
campos sem medição. Inspeção visual confere unidades e legibilidade.

### 4.6 — Implementação de alertas (3.6)

**Dependências:** estados de 3.4/3.5 e protocolo de drift de M2.

**Ações do agente:**
1. Definir tipos `contract_failure`, `execution_failure` e `data_drift`, com severidade, etapa,
   ID e mensagem acionável. Reusar a decisão estatística de M2, sem um segundo limiar oculto na UI.
2. Contrato inválido: bloquear inferência, mostrar rejeição e diagnóstico agregado. Erro de
   execução: marcar falha e a etapa. Drift: sinalizar investigação sem reclassificar automaticamente
   a execução como falha nem disparar retreinamento.
3. Diferenciar alerta de qualidade/execução de indisponibilidade do próprio monitoramento.
4. Deduplicar por execução/tipo/feature conforme regra documentada; agrupar exibição sem perder
   contagem de ocorrências. Reabrir tela não cria nova ocorrência nem apaga histórico.
5. Mostrar próxima ação: corrigir lote, investigar erro, ou revisar cenário/distribuição antes
   de qualquer mudança de modelo. Remediação não roda automaticamente.

**Regras de origem (herdadas de M2, não reabertas aqui):** limiar por feature `0,20` com
comparação estrita `>`, alerta global se qualquer feature exceder, `LIMIT_BAL` e `PAY_AMT1` como
features-alvo do protocolo `1.0.2`, `alpha=0,05` inaplicável ao PSI. O alerta de drift deve
consumir `global_alert` e `drifted_features` do snapshot M2, sem recalcular PSI na tela.

**Verificação/aceite:** cada cenário aciona apenas alertas compatíveis; drift não aparece como
prova de perda real de performance. Controle pode ter alerta de drift se M2 assim mediu; a UI
nunca força estado verde para satisfazer roteiro. Contagens persistem estáveis após rerender.

### 4.7 — Integração e validação do monitoramento (3.7)

**Dependências:** 3.1–3.6 e M2; entradas/saídas em diretórios isolados por tentativa.

Executar a matriz de aceite abaixo com modelo/protocolo congelados, registrando IDs e evidências.
Injetar falhas em caminho de teste controlado, sem danificar dados, credenciais ou modelo real.

| Cenário | Execução esperada | Modelo/drift | Evidência obrigatória |
|---|---|---|---|
| Controle original | `succeeded` | Inferência e drift avaliados | Hashes M2, volumes, recursos, resultados reais do controle, MLflow/UI |
| Modificado válido | `succeeded` com alerta | Inferência e duas features-alvo com drift | Protocolo/score/limiar e HTML coerentes com M2, alerta visível |
| Contrato inválido | `rejected` | Zero chamadas ao modelo; drift não avaliado | Entrada rejeitada integralmente, regra, saída de falha e alerta |
| Erro após validação | `failed` | Etapa e eventual saída parcial explicitadas | Exceção simulada sanitizada, volumes corretos, encerramento e alerta |
| Sem execuções | Sem status fictício | Métricas indisponíveis | Dashboard abre e explica ausência, sem executar pipeline |

Os quatro primeiros cenários são os cenários **operacionais** de M3. "Sem execuções" é a quinta
condição de **interface** (estado vazio), não um quinto cenário operacional.

**Ações finais do agente:** conferir concordância entre logs, resumo, MLflow e tela; coletar
capturas agregadas com IDs/versões, documentar sequência de reprodução e corrigir divergências.
Falha de tracking deve ter teste adicional de resiliência, sem exigir aprovação como se todos
os sinais estivessem completos. Rodar testes de integração isolados e checks do projeto.

**Verificação/aceite:** todos os cenários da matriz demonstrados; último estado não contradiz
logs, contagens ou artefatos; estabilidade local medida e limitações reportadas. Uma captura
isolada sem vínculo a execução não comprova o monitoramento.

## 5. Operação local e verificações

`mlflow` e `streamlit` são **extras** (`observability`) e não são instalados no ambiente padrão.
A fase 3 também reaproveita Evidently (`drift`), usado por `detect_drift`. Antes de usar os
comandos abaixo:

```bash
uv sync --dev --locked --extra observability --extra drift
```

Comandos de visualização existentes, a usar após configurar a mesma URI na aplicação:

```bash
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1
uv run streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

O laboratório segue em porta própria e não é parte deste aceite:

```bash
uv run streamlit run dashboard/app_dev.py --server.address 127.0.0.1 --server.port 8502
```

São processos locais persistentes; abrir em terminais separados e documentar encerramento.
O comando Streamlit já abre a shell atual, mas só terá dados após implementar a integração.
Os novos comandos de execução dos cenários devem ser implementados e documentados com retorno
em falha; o plano não presume que existam hoje.

Os três pontos de instrumentação de execução já existem como CLI e como estágio DVC, e são as
âncoras naturais de 3.1/3.2:

| Ponto | CLI | Estágio DVC | Artefato produced |
|---|---|---|---|
| Simulação | `credit-monitoring-simulate` | `simulate_production` | `data/production/v1.0.2/{original,modified}.csv`, `manifest.json` |
| Inferência | `credit-monitoring-score-production` | `score_production` | `data/production/v1.0.2/predictions/*.csv`, `reports/drift/prediction_summary-v1.0.2.json` |
| Drift | `credit-monitoring-drift` | `detect_drift` | `reports/drift/results-v1.0.2.json`, `reports/drift/phase-2-drift-v1.0.2-ptbr-v6.html` |

Testes devem cobrir schemas/contagens, encerramento em exceção, coleta/unidades, integração
MLflow isolada e estados de UI/alertas. `dashboard/app.py` ainda não tem suíte: ela é parte de
3.5, no mesmo padrão de `tests/test_app_dev.py`. Executar `uv run pytest`, `uv run ruff check .`,
`uv run ruff format --check .` e `git diff --check` após mudanças de código. Não retreinar nem
consultar o teste para validar alteração meramente visual do dashboard.

## 6. Gate M3 e transferência

M3 exige M2 e quatro cenários operacionais rastreáveis, estado vazio correto, recursos medidos
e alertas coerentes. Cada cenário tem `execution_id`, run MLflow quando tracking funcional,
SHA/hashes, logs/resumo e evidência de UI; falta de recurso/acesso impede o aceite correspondente.

Restrições a observar no gate:

- O HTML pt-BR v6 está no cache DVC local e **ainda não no remote DagsHub**. Um ensaio de
  reprodução que dependa do remote não recupera esse artefato específico; o painel deve tolerar
  HTML ausente sem quebrar a leitura do restante do registro.
- Os outputs DVC de M2 (`results-v1.0.2.json`, `prediction_summary-v1.0.2.json`, CSV de
  predições) permanecem imutáveis. Qualquer nova informação de execução é registrada fora deles.
- A suíte atual tem 159 testes verdes e lint limpo; a fase 3 adiciona casos, não substitui os
  existentes.

Transferir à fase 4: mapa de evidências/execuções, comandos de início/fim e reprodução, contratos
de dados/resultados, métricas com unidades, limitações e demonstração sanitizada. Recomenda-se
registro textual `docs/evidence/fase-3.md`, com seções 3.1–3.7 e matriz preenchida com resultados
reais, junto de um índice `docs/evidence/README.md` que aponte às quatro fases — ambos ainda
inexistentes.

**Primeira ação do agente:** implementar a entrega 3.1 sobre o schema de execução descrito em 3.a
e 3.c, ancorando em `credit-monitoring-score-production` como primeira execução válida, do log ao
registro, antes de expandir a UI.
