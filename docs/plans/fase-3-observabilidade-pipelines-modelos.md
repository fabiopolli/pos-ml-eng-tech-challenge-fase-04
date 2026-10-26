# Fase 3 — Observabilidade de Pipelines e Modelos

> Plano de execução, revisado em 2026-10-26. Expande os IDs 3.1–3.7; não atesta implementação.

- **Plano geral:** [escopo, protocolo e aceites](plano-de-trabalho-TC4.md).
- **Entrada:** [fase 2](fase-2-simulacao-deteccao-drift.md), marco M2.
- **Próxima fase:** [Governança e Apresentação](fase-4-governanca-apresentacao.md).
- **Referências:** [arquitetura](../ARCHITECTURE.md), [checklist](../CHECKLIST.md) e
[governança](../GOVERNANCE.md).

## 1. Resultado e fronteiras

Construir uma trilha observável entre etapas, dados/modelo, resultados e alertas, exibida no
MLflow local e no Streamlit. Demonstrar controle, drift válido, rejeição de contrato e falha de
execução, além do estado sem execuções. Medir recursos do processo local com unidades e limites.

Não criar serviço de alertas externo, compute remoto ou retreinamento automático. Um alerta de
drift pode coexistir com execução tecnicamente bem-sucedida; contrato inválido bloqueia o modelo.
O Streamlit é consumidor de evidências, não deve treinar nem refazer inferência ao renderizar.

Aplicar o protocolo comum do plano geral. Código
inicial existente: `dashboard/app.py` é uma shell com placeholders, não monitoramento integrado.
Verificar o estado real dos módulos e logs produzidos nas fases 1/2 antes de duplicar instrumentação.

## 2. Entrada e dependências

Receber M2 com modelo, contrato, lotes/protocolo, predições, JSON/HTML e seus hashes. Ter comandos
locais capazes de executar um cenário sem refazer treino ou teste final. Desenvolvimento de
logging/dashboard com fixtures pode preceder M2, mas o aceite integrado depende dos artefatos reais.

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

Após decisão do contrato, o invariante é `entrada = aprovados + rejeitados`. Antes da leitura
ou conclusão da validação, contagens ainda desconhecidas são indisponíveis, não zeros fictícios;
erro de leitura não significa que todo o lote foi rejeitado pelo contrato. Lote rejeitado integralmente tem
zero aprovados/inferidos e rejeitados iguais à entrada. Contagens por motivo podem se sobrepor
e ficam em estrutura separada. Falha depois do contrato pode ter aprovados positivos e inferidos
zero; se houve saída parcial, registrar explicitamente, sem publicar predições como completas.

Métricas do modelo carregadas de M1 usam namespace de validação/teste e hashes do modelo;
não são medições de acurácia do lote em produção. Métricas de drift e operação usam namespaces
próprios. Não trocar resultado desconhecido por zero nem chamar score PSI de p-value.

### Execução e cache

DVC representa dependências/artefatos determinísticos; MLflow representa tentativas reais.
Separar instrumentação operacional de efeitos cacheáveis: `dvc repro` pode restaurar saídas
sem executar código. Nesse caso registrar restauração/cache, sem fabricar duração ou sucesso
de um novo processamento. Uma nova tentativa ganha novo `execution_id`; reabrir um registro
para consulta não cria outra tentativa nem duplica alertas.

## 4. Pacotes executáveis

### 3.1 — Implementação de logs

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

### 3.2 — Coleta de métricas operacionais

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

**Verificação/aceite:** unidades corretas, valores finitos não negativos quando disponíveis e
invariantes de volumes nos casos válido/inválido/falha. Não comparar pico medido com alocação
teórica nem prometer medir pressão total da máquina por uma métrica de processo.

### 3.3 — Configuração do MLflow

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

### 3.4 — Registro de métricas e artefatos

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

### 3.5 — Desenvolvimento do dashboard Streamlit

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

**Verificação/aceite:** teste de aplicação ou smoke test com fixtures reproduz vazio, sucesso,
rejeição e falha; uma nova tentativa aparece sem misturar métricas da anterior. UI apresenta
indisponível, não zero, nos campos sem medição. Inspeção visual confere unidades e legibilidade.

### 3.6 — Implementação de alertas

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

**Verificação/aceite:** cada cenário aciona apenas alertas compatíveis; drift não aparece como
prova de perda real de performance. Controle pode ter alerta de drift se M2 assim mediu; a UI
nunca força estado verde para satisfazer roteiro. Contagens persistem estáveis após rerender.

### 3.7 — Integração e validação do monitoramento

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

**Ações finais do agente:** conferir concordância entre logs, resumo, MLflow e tela; coletar
capturas agregadas com IDs/versões, documentar sequência de reprodução e corrigir divergências.
Falha de tracking deve ter teste adicional de resiliência, sem exigir aprovação como se todos
os sinais estivessem completos. Rodar testes de integração isolados e checks do projeto.

**Verificação/aceite:** todos os cenários da matriz demonstrados; último estado não contradiz
logs, contagens ou artefatos; estabilidade local medida e limitações reportadas. Uma captura
isolada sem vínculo a execução não comprova o monitoramento.

## 5. Operação local e verificações

Comandos de visualização existentes, a usar após configurar a mesma URI na aplicação:

```bash
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1
uv run streamlit run dashboard/app.py --server.address 127.0.0.1
```

São processos locais persistentes; abrir em terminais separados e documentar encerramento.
O comando Streamlit já abre a shell atual, mas só terá dados após implementar a integração.
Os novos comandos de execução dos cenários devem ser implementados e documentados com retorno
em falha; o plano não presume que existam hoje.

Testes devem cobrir schemas/contagens, encerramento em exceção, coleta/unidades, integração
MLflow isolada e estados de UI/alertas. Executar `uv run pytest`, `uv run ruff check .`,
`uv run ruff format --check .` e `git diff --check` após mudanças de código. Não retreinar nem
consultar o teste para validar alteração meramente visual do dashboard.

## 6. Gate M3 e transferência

M3 exige M2 e quatro cenários operacionais rastreáveis, estado vazio correto, recursos medidos
e alertas coerentes. Cada cenário tem `execution_id`, run MLflow quando tracking funcional,
SHA/hashes, logs/resumo e evidência de UI; falta de recurso/acesso impede o aceite correspondente.

Transferir à fase 4: mapa de evidências/execuções, comandos de início/fim e reprodução, contratos
de dados/resultados, métricas com unidades, limitações e demonstração sanitizada. Recomenda-se
registro textual `docs/evidence/fase-3.md`, com seções 3.1–3.7 e matriz preenchida com resultados reais.

**Primeira ação do agente:** confirmar interface dos artefatos M2 e fechar o schema de 3.1;
implementar uma execução válida do início ao registro antes de expandir a UI.
