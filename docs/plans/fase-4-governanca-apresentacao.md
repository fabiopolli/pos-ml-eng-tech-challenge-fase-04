# Fase 4 — Governança e Apresentação

> Plano de execução, revisado em 2026-11-02 contra o estado real do código após a conclusão de
> M1 e M2. Expande os IDs 4.1–4.7; não atesta implementação.

- **Plano geral:** [escopo, protocolo e aceites](plano-de-trabalho-TC4.md).
- **Entrada técnica:** [fase 3](fase-3-observabilidade-pipelines-modelos.md), marco M3.
- **Referências:** [governança](../GOVERNANCE.md), [dataset](../DATASET.md),
  [arquitetura](../ARCHITECTURE.md), [checklist](../CHECKLIST.md), [DagsHub](../DAGSHUB.md),
  [README](../../README.md), [evidência M1](../evidence/fase-1.md) e
  [evidência M2](../evidence/fase-2.md).

## 1. Resultado e fronteiras

Consolidar evidências de governança e causalidade no README, comprovar reprodução em ambiente
separado e entregar vídeo STAR acessível de até cinco minutos. A documentação deve descrever
o que foi efetivamente observado, distinguindo controles implementados de propostas para a
fintech hipotética. Não declarar conformidade jurídica, ausência de viés ou aptidão para concessão
real de crédito a partir desta demonstração acadêmica.

Privacidade, atribuição e minimização começam na aquisição. Esta fase consolida, revisa e
expõe lacunas; não serve para autorizar retroativamente compartilhamento indevido. Datas de
entrega e disponibilidade para gravação continuam a confirmar.

### 1.1 Fundações já implementadas (não refazer)

A fase 4 **consolida**; não reconstrói o que as fases anteriores já provaram.

| Fundação | Onde está | Estado |
|---|---|---|
| Proveniência completa (DOI, CC BY 4.0, atribuição, conversão XLS→CSV, hashes, 30.000 linhas, 19 features, 4 features de governança, Taiwan/2005/NT$) | [`docs/DATASET.md`](../DATASET.md) | Pronto e validado |
| Fluxo de tratamento e minimização, distinção ID técnico × PII × categorias sensíveis | [`docs/GOVERNANCE.md`](../GOVERNANCE.md) §"Origem e finalidade" e §"Inventário e minimização" | Parcial; lista de "Pontos a concluir" aberta |
| Exposição prévia do teste, revalidações independentes, prova de recuperação DVC remota | [`docs/evidence/fase-1.md`](../evidence/fase-1.md) | Concluído |
| Resultado de Data Drift `1.0.2`, hashes, três comparações, ressalva de Concept Drift, HTML pt-BR v6 | [`docs/evidence/fase-2.md`](../evidence/fase-2.md) | Concluído |
| Estado da implementação, comandos, contrato, limites de drift, seção "Dados e privacidade" | [`README.md`](../../README.md) | Consolidado, mas **sem** seções substantivas de governança e causalidade |
| Controles de acesso, retenção e limites do armazenamento por hash | [`docs/DAGSHUB.md`](../DAGSHUB.md) | Operacionais; falta formalizar retenção/prazos/responsáveis |
| Arquitetura, decisões de escopo e fronteiras entre componentes | [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) | Consolidado |

### 1.2 Pendências reais que esta fase precisa fechar

| Pendência | Situação observada |
|---|---|
| Inventário completo por artefato | `GOVERNANCE.md` descreve minimização em abstrato; não lista cada artefato com cópias locais/remotas e retenção |
| Base legal proposta e matriz de acesso | Ausentes; só há a distinção uso acadêmico × cenário hipotético |
| Retenção com responsável e prazo | Ausente; `DAGSHUB.md` diz que retenção "abrange objetos remotos e caches" sem prazos |
| Avaliação agregada de viés por grupo | Planejada em 4.3, nunca executada |
| Análise causal | Planejada em 4.4, nunca executada |
| Seções de governança e causalidade no README | Ausentes; hoje o README só aponta para `GOVERNANCE.md` |
| Registro de evidências da fase 4 | `docs/evidence/fase-4.md` não existe |
| Índice de evidências | `docs/evidence/README.md` não existe |
| Vídeo STAR | Roteiro e material de apoio não produzidos |
| Reprodução do pacote final | Provas de M1 existem; a do pacote completo ainda não |

## 2. Entrada e sequência

Receber M1/M2/M3, configuração/lock, fonte/licença, metadados do modelo, avaliação
congelada, protocolo/resultados de drift, quatro cenários de observabilidade e limites conhecidos.
Iniciar inventário/privacidade/roteiro antes de M3 quando houver informação verificada, mantendo
seções pendentes explícitas até integrar a versão final.

### 2.1 Entrada concretizada por M1 e M2

| Item | Valor verificado | Origem |
|---|---|---|
| Modelo vigente | Random Forest, SHA-256 `a5a4a740902fab9efa5138f98917a8a7f447c5af7f7d97b707290c205c1e0464` | `models/credit_model_metadata.json` |
| Contrato / limiar | versão `1.0.0`; limiar de classe `0,5` | metadados M1 |
| Partições | treino 21.000; validação 4.500; teste 4.500 (seed 42) | `prepare` (M1) |
| Referência | cópia do treino, SHA-256 `9ebd48b6d31c67f46cc28aff0bde36b48f62936aff0011007b7cb78d26108c26` | `prepare` (M1) |
| Protocolo de drift | `1.0.2`, `protocol_sha256=e160b86e5d6f62382859df8828f053ef16bef438a6f0967e022a99cb4ae536fb`, `scenario_id=phase-2-1.0.2` | `data/production/v1.0.2/manifest.json` |
| Lotes de produção | original `d9f855a7…`; modified `8da682f3…`; ambos 4.500 linhas | M2 |
| Resultado de drift | `results-v1.0.2.json` (SHA-256 `f0c02e97fbb3a6301ec1cf65593c9c7977f051bd4c4a2eec7c1276b45ec4bd48`), schema `1.0.0` | M2 |
| Relatório pt-BR v6 | SHA-256 `d47a792b1dfb7d94ee4469ada01298d2bf0e0809e7beda2c4641ae4cf284a451` — enviado ao remote DagsHub e versionado no Git | M2 |
| Grupos de governança | `SEX`, `EDUCATION`, `MARRIAGE`, `AGE` | `configs/project.yaml` §`dataset.governance_features` |

### 2.2 Sequência

```text
M1/M2 → 4.1 → 4.2 ──────────────────┐
M1/M2 → 4.3 → 4.4 ──────────────────┼→ 4.5 → ensaio de reprodução → 4.6 → 4.7 → M4
M3 ────────────────────────────────┘
```

Executar um ensaio local de 4.7 antes da gravação para detectar comandos quebrados; o aceite
final 4.7 só fecha depois de vídeo, README e versão candidata estabilizados. Isso não cria
ciclo: o ensaio é uma verificação parcial, e a revisão final inspeciona o pacote completo.

## 3. Artefatos e padrão de evidência

| Artefato | Conteúdo esperado | Estado atual |
|---|---|---|
| [`docs/GOVERNANCE.md`](../GOVERNANCE.md) | Inventário, finalidade, acesso, retenção, riscos, supervisão, análise de viés e resposta a drift | Documento inicial; seções a consolidar |
| [`README.md`](../../README.md) | Seções substantivas de governança e causalidade, resultados/limitações, comandos e link do vídeo | Sem essas seções |
| Registro de avaliação agregada | Dataset/partição, modelo/limiar, grupos/denominadores/métricas e incerteza; sem linhas de clientes | Inexistente |
| Matriz de cobertura | Requisito do enunciado → ID → evidência/versão → resultado observado/pendência | Inexistente |
| Registro de reprodução | SHA/lock, ambiente, comandos/códigos de saída, hashes recuperados e verificação de cenário/UI | Inexistente |
| Roteiro/vídeo | Tempos STAR, cenas e IDs de execução; duração medida e acesso verificado após publicação autorizada | Inexistente |

Proposta de localização dos registros: `docs/evidence/fase-4.md` e índice
`docs/evidence/README.md`, criados na implementação. O índice aponta às evidências das quatro
fases sem duplicar dados/modelos/banco MLflow no Git. Capturas só com conteúdo agregado aprovado.

Cada afirmação de resultado deve apontar a arquivo/execução/versão. Afirmação jurídica ou sobre
a fonte deve indicar referência primária, data de consulta e aplicabilidade; proposta fica rotulada
como proposta. Não transformar uma recomendação do agente em aprovação do responsável humano.

## 4. Pacotes executáveis

### 4.1 — Documentação de tratamento de dados (4.1)

**Dependências:** origem e artefatos de dados da fase 1; inventário atualizado das fases 2/3.

**Ações do agente:**
1. Rastrear UCI 350 → bruto → conversão → limpeza/splits → referência/produção → predições/
   relatórios, com responsáveis operacionais a confirmar e finalidade de cada transformação.
2. Criar inventário por classe de artefato: conteúdo, atributos, origem, acesso, localização,
   cópias locais/remotas, retenção proposta e destinatários autorizados.
3. Distinguir ID técnico, variáveis pessoais/demográficas e categorias sensíveis legais;
   não chamar ID de identidade civil nem presumir anonimização por mera remoção de nomes.
4. Justificar as 19 features, demografia restrita à avaliação/governança e separação de alvo.
   Documentar minimização em logs, capturas, HTML, predições e dados de demonstração.
5. Confirmar licença/atribuição/DOI e descrição da conversão/transformações nas versões utilizadas.
   Registrar contexto histórico de Taiwan/2005 e limites de transferência para crédito atual.

**Cobertura já existente a reutilizar:** proveniência, hashes, parâmetros de leitura e
atribuição já estão em `docs/DATASET.md`; o fluxo já está em `docs/ARCHITECTURE.md` e no README.
A parte **pendente** é o inventário por artefato com o estado real de versionamento.

**Inventário a produzir (com o estado real verificado):**

| Artefato | Onde vive | Versionado como |
|---|---|---|
| Workbook original `.xls` | `data/default of credit card clients.xls` | Objeto DVC + remote DagsHub (fora do Git) |
| CSV bruto | `data/raw/default_of_credit_card_clients.csv` | DVC |
| `train/validation/test.csv`, `reference.csv`, `preparation_report.json` | `data/processed/`, `data/reference/` | DVC |
| `data/production/v1.0.1/` e `v1.0.2/` (lotes, manifesto, predições) | `data/production/` | DVC |
| `results-v1.0.1.json` e `results-v1.0.2.json` | `reports/drift/` | Git (exceção deliberada: JSON pequeno e canônico) |
| HTML de drift (incluindo pt-BR v6) | `reports/drift/*.html` | v6 enviado ao remote DagsHub e versionado no Git; demais revisões são saídas intermediárias locais |
| Modelo e candidatos | `models/` | DVC + remote; nunca no Git |
| Banco e artefatos MLflow | `mlflow.db`, `mlruns/` | Fora do Git (já ignorado) |
| Recursos de execução | `reports/run_resources.json` (estágio `train`), `reports/optimization/*/resources.json` | Fora do Git (já ignorado) |
| Fixtures do laboratório | `data/test/*.csv` | **Git** — exceção documentada (~60 KB, derivados do treino, IDs novos) |
| Relatórios e figuras | `reports/figures/` | DVC (parcial) |
| Registros de execução M3 | a definir em 3.1 | Fora do Git, ignorado |
| Evidências textuais | `docs/evidence/` | Git (texto agregado) |
| Vídeo e capturas | a definir em 4.6 | Link externo + referência no README; **nada** de mídia pesada no Git |

**Verificação/aceite:** todos os artefatos efetivamente usados têm origem/finalidade/localização;
inventário coincide com configuração/DAG e não inclui afirmação de controle inexistente.
Bruto, cache DVC, objetos DagsHub, banco/artefatos MLflow e material do vídeo estão cobertos.

### 4.2 — Plano de privacidade/LGPD (4.2)

**Dependências:** inventário 4.1 e condições reais de compartilhamento/acesso.

**Ações do agente:**
1. Separar uso acadêmico da base pública da proposta de tratamento numa fintech hipotética.
   Licença de reutilização não deve ser apresentada como base legal ou autorização irrestrita.
2. Consultar texto oficial atualizado da LGPD e orientações primárias pertinentes da ANPD;
   registrar links, data, escopo e questões para revisão humana. Formular base legal proposta
   para o cenário, sem afirmar validação jurídica ou operação real que não ocorreu.
3. Descrever transparência, finalidade/necessidade, revisão/contestação de decisão e supervisão
   propostas, distinguindo capacidades implementadas no protótipo de obrigações do cenário real.
4. Definir matriz de acesso e verificar o que foi configurado localmente/DagsHub: leitura da
   equipe/avaliadores, tokens locais e ausência de segredos nos artefatos compartilhados.
5. Propor retenção por classe e gatilho de revisão, com responsável e prazo a confirmar; incluir
   caches, versões remotas, cópias do avaliador, MLflow, capturas e vídeo. Não inventar prazo legal.
6. Descrever procedimento de descarte com autorização específica e verificação de cópias;
   apagar ponteiro Git não apaga objeto por hash. Não executar GC, exclusão ou revogação como
   parte da elaboração do plano nem afirmar apagamento completo sem prova.

**Estado atual verificável:** tokens e credenciais ficam em `.env` e `.dvc/config.local`, ambos
ignorados pelo Git; `.gitignore` bloqueia `data/raw/`, `data/processed/`, `data/reference/`,
`data/production/`, `models/`, `mlruns/`, `mlflow.db` e `*.log`. O remote é `dagshub`
(`s3://dvc`) sem credenciais versionadas. A fase 4 precisa transformar isso em **matriz de acesso
e tabela de retenção com responsáveis e prazos a confirmar**, não em nova descrição de mecânica.

**Verificação/aceite:** README e documento distinguem realizado/proposto/pendente; fonte pública
não é tratada como isenção geral. Acesso e retenção são verificáveis ou têm responsável/decisão
pendentes; nenhuma aprovação jurídica ou política institucional é inventada.

### 4.3 — Governança do modelo e viés agregado (4.3)

**Dependências:** decisão/métricas congeladas de M1 e predições alinhadas a dados rotulados.

**Ações do agente:**
1. Criar ficha do modelo: finalidade/uso excluído, treino/validação/teste, features, classes,
   parâmetros/limiar, hashes, versões, seleção e exposição histórica do teste.
2. Relatar métricas globais e desbalanceamento com origem/partição; não tratar resultados sobre
   produção modificada com rótulos antigos como desempenho real.
3. Executar análise agregada de viés com os grupos predefinidos na documentação do dataset
   (`SEX`, `EDUCATION`, `MARRIAGE`, `AGE`), sem renomear códigos ou inferir significados ausentes.
   Propor uso da validação original com modelo/limiar congelados e declarar seu uso prévio na
   seleção; não criar novo holdout fictício.
4. Por grupo, registrar `n`, positivos/negativos reais, prevalência, taxa de predição positiva,
   recall/TPR e FPR/FNR quando definidos. Classe 1 é risco de inadimplência, não aprovação de crédito.
   Explicitar denominadores e métricas indefinidas em grupos sem casos positivos/negativos.
5. Definir antes da análise critérios para grupos pequenos, agregação/supressão e incerteza
   (por exemplo, intervalos de proporções com método identificado). Baixo tamanho e incerteza
   tornam resultado inconclusivo; não provar ausência de viés por falta de significância.
6. Distinguir análise descritiva de validação de equidade/causalidade. Revisão motivada por viés
   deve abrir nova versão de modelo/protocolo, não ajustar limiar consultando o teste reservado.
7. Documentar quem revisa alertas/uso e como uma versão é suspensa/reavaliada no cenário proposto.

**Restrições de dados (não negociáveis):**

- O grupo de análise por viés é a **validação original rotulada** (4.500 linhas). Ela já
  participou da seleção do modelo; declarar isso significa que o resultado é descritivo e
  potencialmente otimista, não uma estimativa independente de desempenho.
- O **teste (4.500 linhas) não é consultado** por esta análise. A exposição histórica do EDA ao
  conjunto de teste já está declarada em `docs/evidence/fase-1.md` §1.2.1 e não deve ser
  descrito como holdout intocado.
- As features demográficas (`SEX`, `EDUCATION`, `MARRIAGE`, `AGE`) **não entram no modelo**; isso
  não elimina proxies nem prova ausência de viés.
- A saída é agregada: sem linhas, sem IDs, sem valores de clientes.

**Verificação/aceite:** tabela agregada recalculável, grupos e denominadores corretos, IDs
alinhados sem duplicidade e hash do modelo/partição. Excluir demografia dos preditores não é
apresentado como garantia de ausência de proxies/discriminação. Resultado/risco permanece visível.

### 4.4 — Análise causal e resposta (4.4)

**Dependências:** desenho/resultados M2, estados M3 e governança do modelo em 4.3.

**Ações do agente:**
1. Separar fatos observados, intervenção conhecida por construção e hipóteses externas. Exemplo:
   a transformação aplicada é causa programada da mudança no lote; inflação ou novo perfil de
   clientes não são causas identificadas por esse experimento.
2. Comparar controle/modificado com magnitude/limites; discutir explicações alternativas como
   seleção amostral, alteração de fonte/schema, erro de processamento e sensibilidade do teste.
3. Descrever qual evidência adicional permitiria avaliar cada hipótese: procedência temporal,
   logs da fonte, população/coortes comparáveis e rótulos posteriores quando disponíveis.
4. Criar matriz de resposta por sinal: contrato falhou → rejeitar/investigar lote; execução
   falhou → corrigir etapa/reexecutar com novo ID; drift → investigar origem/impacto e revisar;
   desempenho/viés adverso comprovado → avaliação humana e possível suspensão/revisão de versão.
5. Distinguir impacto potencial de perda medida; alertas não autorizam automaticamente retreino,
   aprovação de crédito ou mudança de política. Registrar responsáveis/escalonamento a confirmar.
6. Incorporar a decisão do operador: a fase 2 demonstra Data Drift e não reivindica Concept Drift;
   a docência avaliará o plano após a entrega. Se uma avaliação futura solicitar experimento
   separado, identificá-lo como sintético e referenciar evidências próprias.

**Ancoragem obrigatória no resultado já observado (não recalcular nem estimar):**

| Observação | Valor registrado | O que a análise pode e não pode afirmar |
|---|---|---|
| PSI `LIMIT_BAL`, referência × modificada | `0,752498` (limiar `0,20`) | A mudança de distribuição é programada e mensurável |
| PSI `PAY_AMT1`, referência × modificada | `0,464748` (limiar `0,20`) | Idem |
| Controle (referência × original) | Nenhuma das 19 features excedeu `0,20` | O detector não sinaliza o lote inalterado |
| Média do score previsto | `42,31%` → `41,99%` (−0,32 p.p.) | Efeito **nas saídas previstas**; não é desempenho |
| Classe 1 | `1.161` → `1.154` | Contagem prevista; sem rótulo em produção |
| Rótulos em produção | Ausentes por construção | **Não é possível** medir degradação de desempenho |

Qualquer texto que sugira "o modelo piorou", "houve concept drift" ou "a perda de performance foi
de X" é incorreto frente a essas evidências.

**Verificação/aceite:** texto oferece investigação/mitigação acionáveis, sem alegar causalidade
econômica identificada. Cada recomendação tem condição de uso e limite; resultados de drift não
são apresentados como perda real de desempenho. Governança e causalidade aparecem no README.

### 4.5 — Consolidação do README (4.5)

**Dependências:** 4.1–4.4 e pacote técnico M3 para completar a documentação.

**Ações do agente:**
1. Atualizar estado real, arquitetura e comandos a partir das interfaces implementadas; remover
   instruções obsoletas com migração documentada, preservando distinção entre plano e resultado.
2. Descrever instalação travada, aquisição/recuperação autorizada, preparação/seleção, avaliação
   final explícita, contrato, cenários, HTML, MLflow e Streamlit. Separar operações repetíveis
   do teste final para evitar consultas desnecessárias na rotina de demonstração.
3. Inserir seções substantivas de governança e causalidade no próprio README; links ao documento
   complementar não substituem essas seções exigidas pelo enunciado.
4. Referenciar evidências por ID, hashes/run IDs e comandos; diferenciar checks automatizados de
   inspeção visual/revisão humana. Incluir limitações/pendências e consumo local medido.
5. Manter instruções de credenciais sem valores reais e explicar o que requer rede e o que roda
   com cache local. Validar links e acessibilidade dos materiais autorizados para avaliadores.

**Estado atual a alterar:** o README já cobre estado M1/M2, arquitetura, comandos, contrato,
limites de Data Drift, alerta sobre probabilidade não calibrada, seção "Dados e privacidade" e a
distinção entre laboratório e painel operacional. Faltam as **seções substantivas** de governança
e de causalidade exigidas pelo enunciado (hoje há apenas um ponteiro para `docs/GOVERNANCE.md`), o
link final do vídeo e a matriz de resultados agregados de viés.

**Verificação/aceite:** outro integrante segue o README sem depender do histórico da conversa;
nenhum comando de módulo ainda inexistente aparece como funcional. Métricas/resultados/limitações
coincidem com os artefatos. O ensaio de reprodução identifica correções antes de gravar o vídeo.

### 4.6 — Produção do vídeo STAR (4.6)

**Dependências:** 4.5, ensaio bem-sucedido de reprodução e evidências M1/M2/M3 consistentes.

**Ações do agente e participação humana:**
1. Preparar roteiro e ordem de cenas, usando os IDs de execução das evidências e dados agregados.
   Agente pode compor roteiro/checklist e preparar telas; atribuir gravação/narração a integrante
   confirmado, sem alegar que o vídeo foi produzido apenas por escrever o roteiro.
2. Ensaiar com serviços locais prontos e artefatos já gerados. Marcar edição/cortes honestamente;
   não apresentar relatório antigo como execução ao vivo de outra versão.
3. Capturar contrato bloqueando lote inválido, modelo selecionado, controle/drift, MLflow/UI,
   recursos/alertas e síntese de governança/causalidade. Ocultar tokens e linhas individuais.
4. Medir duração do arquivo final, revisar legibilidade/áudio e fidelidade ao README.
5. Publicar somente após autorização e confirmar acesso do avaliador ao link sem credenciais
   pessoais do autor; inserir link final no README, não um placeholder como evidência concluída.

| STAR | Limite planejado | Cena/objetivo |
|---|---:|---|
| Situation | 45 s | Fintech hipotética, problema de qualidade/drift e contexto do dataset |
| Task | 45 s | Requisitos, contrato e objetivo da demonstração local |
| Action | 140 s | Contrato, modelo, controle/drift, relatórios, rastreamento, recursos e alertas |
| Result | 70 s | Resultados medidos, limites, governança e ação de resposta |
| Total máximo | 300 s | Até cinco minutos; ensaiar abaixo do teto para acomodar transições |

**Distinção obrigatória:** "roteiro e material de apoio prontos" ≠ "4.6 concluído" ≠ "M4 concluído".
A gravação e a publicação são ações humanas externas. O agente prepara o roteiro, os comandos e as
telas; a gravação, a narração e a publicação dependem de integrante confirmado e de autorização
explícita.

**Verificação/aceite:** duração real ≤300 s, quatro partes identificáveis, demonstração técnica
legível e link acessível. Falta de gravação/publicação/autorização mantém 4.6 e M4 pendentes,
mesmo com roteiro pronto. Não substituir evidência dinâmica por promessa de implementação.

### 4.7 — Revisão e entrega final (4.7)

**Dependências:** M1/M2/M3, 4.1–4.6 e versão candidata identificada.

**Ações do agente:**
1. Criar índice/matriz de cobertura do enunciado com requisito, peso quando aplicável, ID,
   caminho/hash/run ID, resultado observado e pendência. Conferir as 28 entregas.
2. Identificar SHA candidato e lock; usar checkout separado no mesmo SHA com cache DVC vazio
   próprio, sem apagar nem reutilizar o cache principal. Preparar diretório de trabalho
   aprovado, confirmar espaço e registrar caminhos do ensaio sem credenciais.
3. Instalar com `uv sync --dev --locked`; configurar acesso de leitura local e executar
   `uv run dvc pull -r dagshub`. Conferir hashes esperados do bruto, splits, referência e modelo.
   Não copiar objetos do cache principal para simular prova de leitura remota.
4. Executar testes/lint e cenários documentados com o modelo recuperado, reconstruindo logs/
   tracking local quando necessário. Conferir HTML, quatro estados operacionais, recursos e UI.
   Como MLflow não é compartilhado pelo Git, não presumir que seu banco exista no novo checkout.
5. Distinguir recuperação de reexecução: cache restaurado não comprova nova computação. Quando
   reproduzir estágio, registrar comando/versão e comparar conteúdo/métricas com tolerância
   declarada; byte a byte de um modelo retreinado pode variar entre ambientes. Não reabrir seleção
   ou consultar teste final sem necessidade; eventual reprodução explícita não muda decisões.
6. Conferir histórico/diff, links, atribuição, ausência de binários/segredos indevidos no pacote,
   acesso de leitura dos avaliadores e vídeo final. Resultado faltante continua pendente.
7. Atualizar checklist com aceite/evidência real e preparar resumo final. Commit, push, PR,
   publicação final ou submissão acadêmica seguem solicitação/autorização explícita; não tratar
   revisão local aprovada como se a entrega externa já tivesse ocorrido.

**Estado das provas de reprodução na data da revisão:**

| Prova | Situação | Vale para M4? |
|---|---|---|
| M1: recuperação remota em checkout/cache separado | **Já provada** (`docs/evidence/fase-1.md` §1.6.1 e §1.1.1) | Não como prova nova; é precedente de método |
| M2: objetos `1.0.1` e `1.0.2` enviados e recuperados em cache isolado | **Já provada** (`docs/evidence/fase-2.md`) | Não como prova nova |
| HTML pt-BR v6 | Enviado ao remote DagsHub e versionado no Git; geração determinística | O ensaio do pacote final o recupera via `dvc pull` ou Git, sem depender de regeneração |
| M3: banco MLflow, logs e registros de execução | Locais e fora do Git por desenho | O checkout novo precisa **reconstruir** a observabilidade |
| M4: pacote completo (bruto → modelo → drift → observabilidade → UI → vídeo) | **Não provada** | É a prova que 4.7 precisa produzir |

**Consequência prática:** o HTML v6 já foi enviado ao remote DagsHub e está versionado no Git,
e sua geração é determinística (regerar o estágio reproduz o mesmo SHA-256). O ensaio do pacote
final pode obtê-lo por `dvc pull` ou pelo Git, sem depender de regeneração. Se o checkout novo
optar por regenerar com `uv run dvc repro --force --single-item detect_drift`, a convergência deve
ser verificada contra o hash registrado, e não presumida.

**Verificação/aceite:** reprodução independente por hash, README executável, vídeo acessível e
matriz completa conferida. Se houver correção de código/configuração
após o ensaio, selecionar nova versão candidata e repetir apenas os aceites invalidados, além
de revisar se vídeo/README ainda correspondem ao pacote.

## 5. Matriz mínima para revisão do pacote

| Critério | Peso | Evidência a localizar |
|---|---:|---|
| Validação | 25% | 1.7: regras, controles, bloqueio antes do modelo e rejeição integral |
| Drift | 25% | 2.2/2.6/2.7: protocolo, controle, duas features, scores/limiares e HTML |
| Observabilidade | 20% | 3.7: quatro cenários, logs/run IDs, recursos locais, MLflow/Streamlit |
| Governança | 15% | 4.1–4.5: origem, base legal proposta, retenção, viés, causalidade e resposta no README |
| Vídeo STAR | 15% | 4.6: duração medida, demonstração fiel e acesso ao link |
| Controles internos | Sem peso oficial adicional | 1.6/4.7: comparação de modelos, DVC/DagsHub e recuperação independente |
| Cobertura transversal | Verificar no enunciado | Base financeira binária, ≥5.000 amostras úteis, Data Drift demonstrado e limitações de Concept Drift registradas; docência avalia pós-entrega |

Os **quatro cenários operacionais** de M3 são: controle, drift válido, contrato inválido e falha
de execução. O estado "sem execuções" é uma condição adicional de interface, não um quinto
cenário operacional, e não substitui nenhum dos quatro.

Matriz é checklist de verificação, não pontuação autoatribuída. Não preencher resultado apenas
porque o arquivo existe; revisar o conteúdo e a coerência com a versão candidata.

## 6. Gate M4 e handoff final

M4 exige M3, governança/causalidade no README, matriz de cobertura e limitações documentadas,
reprodução independente, vídeo acessível e revisão final. A avaliação da docência sobre Concept
Drift ocorre após a entrega e não é dependência de execução. Datas/responsáveis/acessos não
confirmados devem ser resolvidos ou explicitamente impedir o aceite correspondente, sem afirmar
compromisso de terceiros.

Handoff final: o que foi implementado e verificado, SHA/lock e hashes, matriz/evidências, link
e duração do vídeo, resultados/limitações, decisões humanas e situação real da publicação/
submissão. Guardar instruções de retomada e preservação de artefatos; não descartar ambientes
ou versões como parte automática do encerramento.

Ações externas que permanecem sujeitas a autorização explícita: commit, push, PR, merge,
publicação do vídeo, submissão acadêmica e qualquer envio de artefato ao remote.

**Primeira ação do agente:** inventariar evidências/fontes em 4.1 reaproveitando `docs/DATASET.md`
e o inventário por artefato já levantado aqui; caso M3 ainda não exista,
adiantar somente documentação verificável, decisões de privacidade e preparação do roteiro.
