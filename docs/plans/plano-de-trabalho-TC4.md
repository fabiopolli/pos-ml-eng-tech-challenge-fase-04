# Tech Challenge — Fase 4
## Plano de Trabalho: Credit Scoring, Data Drift e Observabilidade

- **Horizonte planejado:** 4 semanas relativas; datas de início e entrega a confirmar.
- **Organização:** 4 fases (etapas do enunciado), com 7 entregas por fase.
- **Total:** 28 entregas.
- **Dataset:** UCI Default of Credit Card Clients (ID 350).
- **Revisão documental:** 2026-10-26; requisitos planejados, não declaração de implementação.

Referência de aceite: [enunciado oficial](MLET%20-%20Tech%20Challenge%20-%20Fase%204.pdf),
páginas 2–7. As quatro etapas e os pesos são oficiais; quatro semanas, 28 entregas, dois modelos,
MLflow + Streamlit e DVC/DagsHub são escolhas da equipe. O status operacional fica no
[`docs/CHECKLIST.md`](../CHECKLIST.md), sem confundir existência de código com aceite.

### Planos de execução por etapa

Os documentos abaixo expandem os mesmos 28 IDs para execução agêntica incremental. Este plano
geral define escopo e aceites; os planos de fase detalham como implementá-los e verificá-los.
Nenhum deles declara as entregas realizadas. Todos usam o [protocolo comum](#11-protocolo-de-execução-agêntica).

| Etapa | Plano detalhado | IDs | Marco de saída |
|---|---|---|---|
| 1 — Validação de Dados e Contratos | [Execução da fase 1](fase-1-validacao-dados-contratos.md) | 1.1–1.7 | M1: contrato, modelo congelado e recuperação DVC |
| 2 — Simulação e Detecção de Drift | [Execução da fase 2](fase-2-simulacao-deteccao-drift.md) | 2.1–2.7 | M2: controle e drift reproduzíveis com relatório |
| 3 — Observabilidade de Pipelines e Modelos | [Execução da fase 3](fase-3-observabilidade-pipelines-modelos.md) | 3.1–3.7 | M3: quatro cenários rastreáveis no MLflow/Streamlit |
| 4 — Governança e Apresentação | [Execução da fase 4](fase-4-governanca-apresentacao.md) | 4.1–4.7 | M4: evidências consolidadas, reprodução e vídeo |

---

## 1. Objetivo do projeto

Desenvolver uma solução simplificada de Machine Learning para classificação de risco de inadimplência de clientes de cartão de crédito, incorporando mecanismos de validação de dados, detecção de drift, observabilidade e governança.

O projeto simulará um cenário no qual uma fintech possui um modelo de Credit Scoring em operação e precisa monitorar a qualidade dos dados e identificar alterações que possam comprometer a confiabilidade de suas previsões.

O desenvolvimento e a execução do pipeline serão locais, utilizando ferramentas open-source, sem
infraestrutura própria de cloud ou sistemas complexos de implantação. O DagsHub Storage será usado
como armazenamento remoto gerenciado para os objetos versionados pelo DVC.

## 2. Stack tecnológica

| Componente | Tecnologia definida |
|---|---|
| Linguagem | Python |
| Ambiente e dependências | Python 3.12, uv e `uv.lock` |
| Dataset | UCI Default of Credit Card Clients |
| Processamento | Pandas e NumPy |
| Modelo baseline | Scikit-learn — LogisticRegression |
| Modelo candidato principal | Scikit-learn — RandomForestClassifier |
| Contratos de dados | Pandera |
| Detecção de drift | Evidently AI |
| Rastreamento | MLflow |
| Dashboard | Streamlit |
| Código e documentação | Git e GitHub |
| Versionamento de datasets e modelos | DVC e DagsHub Storage |
| Qualidade e integração contínua | Pytest, Ruff e GitHub Actions |
| Documentação | Markdown |

O DVC mantém os arquivos ponteiro e metadados (`.dvc`, `dvc.yaml` e `dvc.lock`) no Git; os
conteúdos dos datasets e modelos rastreados pelo DVC ficam no remote DagsHub Storage. As credenciais
de acesso ao remote são locais e nunca entram no Git. A configuração depende de um repositório
DagsHub conectado ao GitHub; detalhes em [`docs/DAGSHUB.md`](../DAGSHUB.md).
O suporte S3 do DVC é necessário para o endpoint proposto e deve compor o ambiente reproduzível
na entrega 1.1. DagsHub Storage não substitui o MLflow local nem implica uso de Model Registry,
deploy remoto ou outro serviço da plataforma.

### Dataset selecionado

O dataset **Default of Credit Card Clients**, disponibilizado pela UCI Machine Learning Repository, contém:

- 30.000 registros de clientes.
- 23 variáveis preditoras.
- Variável-alvo binária que indica inadimplência no mês seguinte.
- Histórico de pagamentos, valores de faturas, pagamentos efetuados e informações demográficas.

**Fonte:** https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients

A UCI distribui o original em XLS; a origem e a conversão para o CSV usado pelo projeto devem
ser documentadas com hashes, nomes das colunas e parâmetros de leitura. O histórico de pagamentos
é de abril a setembro de 2005, em Taiwan; os valores monetários são em NT$. Os lotes simulam uma
sequência operacional, não uma validação temporal real nem a população brasileira atual.
Licença indicada pela UCI: CC BY 4.0; preservar atribuição, DOI e descrição das transformações.

Para simplificar o modelo, serão utilizadas inicialmente 19 variáveis financeiras:

- `LIMIT_BAL` — limite de crédito.
- `PAY_0`, `PAY_2` a `PAY_6` — histórico de pagamentos.
- `BILL_AMT1` a `BILL_AMT6` — valores de faturas.
- `PAY_AMT1` a `PAY_AMT6` — pagamentos realizados.

As variáveis demográficas serão preservadas para análises de governança, mas não utilizadas inicialmente como preditoras.

### Estratégia de modelagem

Serão treinados dois classificadores:

**Regressão Logística:** modelo baseline de referência, com implementação simples e interpretação relativamente direta.

**Random Forest:** modelo candidato principal, capaz de representar relações não lineares e interações entre atributos financeiros.

Os dois modelos serão avaliados sob as mesmas condições, utilizando ROC-AUC, precision, recall, F1-score e matriz de confusão. A accuracy será registrada como métrica complementar, considerando o desbalanceamento entre as classes.

A seleção usa o maior ROC-AUC de validação; em empate, prioriza a Regressão Logística, mais
simples. O alvo positivo é inadimplência (`1`); o limiar inicial de classificação é `0.5`, como
no código atual. Caso o limiar seja ajustado, usar apenas a validação e registrar a decisão
antes da avaliação de teste. Não há meta numérica de desempenho aprovada: relatar métricas,
desbalanceamento e limitações, sem declarar o modelo apto a conceder crédito real.

### Protocolo de dados e avaliação

| Partição/artefato | Origem e uso permitido |
|---|---|
| Treino (70%) | Ajustar modelos e toda transformação aprendida; a cópia intacta em `data/reference/reference.csv` é a referência de monitoramento exigida pelo enunciado. |
| Validação (15%) | Selecionar modelo/limiar; após congelar essas decisões, suas features serão a origem do lote de produção original para a demonstração de drift. |
| Teste (15%) | Avaliar apenas o modelo escolhido com protocolo congelado; não usar para selecionar features, hiperparâmetros, limiares ou intensidade de drift. |
| Produção original/modificada | Cópias versionadas das features da validação, com os mesmos IDs entre cenários; a modificada recebe as intervenções sintéticas. Não misturar esses IDs com a referência. |

As divisões são estratificadas, disjuntas por ID, com seed `42` e tamanhos registrados após
limpeza. Produção é independente do treino/referência, mas reutiliza a validação e **não** é um
holdout novo de desempenho. Não retornar à seleção do modelo a partir da demonstração de drift.
ID e variáveis demográficas permanecem no lote para contrato/governança, fora das 19 entradas do
modelo. O alvo é separado de features e não é exigido para inferência ou testes de Data Drift.

Auditoria estrutural do bruto pode preceder o split; análises de relações com o alvo que orientem
decisões devem usar treino. Isolar o teste do ciclo de exploração e registrar qualquer exposição
prévia. O pipeline atual gera correlações com o alvo no bruto completo e avalia o teste em cada
execução de `train`; revisar essas limitações antes de alegar avaliação final sem contaminação.

### Ordem de execução e dependências

Os IDs identificam entregas, não a ordem obrigatória. Na fase 1, o contrato 1.7 deve estar
integrado **antes** de 1.4/1.5 e da inferência: `1.1 → 1.2 → 1.3 → 1.7 → (1.4, 1.5) → 1.6`.
A preparação histórica pode remover registros inválidos com contagens e motivos; um lote
operacional inválido deve ser rejeitado inteiro, sem limpeza silenciosa seguida de inferência.
Controles de governança começam na aquisição, com consolidação na fase 4.

---

## 3. Fase 1 / Semana 1 — Validação de Dados e Contratos

**Disciplina:** Validação de Dados e Bibliotecas de Qualidade.

**Objetivo:** preparar os dados, treinar e selecionar um modelo baseline de Credit Scoring e implementar um contrato de validação que impeça a ingestão de dados inválidos.

| ID | Entrega | Atividades |
|---|---|---|
| **1.1** | Configuração do repositório | Definir diretórios, ambiente travado e suporte DVC/S3, conectar GitHub ao DagsHub, configurar o remote sem versionar credenciais e documentar recuperação e limites de acesso/armazenamento. |
| **1.2** | Aquisição e auditoria do dataset | Registrar fonte, licença, conversão XLS/CSV e hashes; auditar esquema, nulos e duplicatas. Restringir a exploração que orienta modelagem ao treino após 1.3. |
| **1.3** | Preparação dos dados | Preservar ID e atributos de governança, separar as 19 entradas do modelo e gerar treino/validação/teste 70/15/15, referência = treino, seed e relatório de limpeza; verificar IDs disjuntos. |
| **1.4** | Treinamento da Regressão Logística | Implementar pipeline de pré-processamento e treinar o classificador baseline com Scikit-learn. |
| **1.5** | Treinamento do Random Forest | Treinar o segundo classificador, utilizando parâmetros iniciais simples para controlar o overfitting. |
| **1.6** | Avaliação, seleção e versionamento do modelo | Comparar na validação, congelar modelo/limiar, avaliar o escolhido no teste sem realimentar seleção; serializar modelo e metadados e demonstrar recuperação dos objetos DVC no DagsHub em checkout/cache separado. |
| **1.7** | Implementação do Data Contract | Integrar Pandera antes do treino/inferência, com ao menos três regras rígidas; verificar lote válido aceito e lotes inválidos rejeitados sem executar o modelo, com diagnóstico e saída de falha. |

### Regras iniciais do Data Contract

1. Identificadores de clientes não podem estar duplicados no lote.
2. `LIMIT_BAL` deve apresentar valor positivo.
3. `AGE` deve estar entre 18 e 100 anos, inclusive, conforme a configuração inicial.
4. Features obrigatórias não podem conter valores nulos.

Validar também presença de colunas e tipos. No esquema rotulado, exigir alvo binário; no de
inferência, não exigir alvo. Os ajustes devem ser justificados e versionados, preservando códigos
documentados no EDA; não proibir faturas negativas nem recodificar automaticamente valores sem
evidência. Demonstrar cada regra com uma perturbação isolada e ao menos um lote válido.

### Critério de conclusão

A etapa estará concluída quando:

- Os dois algoritmos estiverem treinados e comparados na validação, com splits auditados.
- Um modelo tiver sido formalmente selecionado.
- O modelo selecionado realizar predições sobre dados válidos.
- O contrato Pandera bloquear comprovadamente lotes inválidos antes do modelo e aceitar o válido.
- O dataset de entrada e as saídas de dados/modelo rastreadas por DVC podem ser recuperadas do DagsHub Storage, sem credenciais no Git.

**Entregável oficial:** modelo baseline treinado e script funcional de validação de dados.

---

## 4. Fase 2 / Semana 2 — Simulação e Detecção de Drift

**Disciplina:** Data Drift.

**Objetivo:** simular alterações nas distribuições das variáveis financeiras dos clientes e identificar estatisticamente essas mudanças usando Evidently AI.

**Entrada:** contrato integrado, modelo congelado, referência e validação identificadas por hashes
da fase 1. Não alterar o modelo nem usar o conjunto de teste para construir o cenário.

| ID | Entrega | Atividades |
|---|---|---|
| **2.1** | Definição dos datasets de referência e produção | Usar referência = treino e produção original = features da validação após a seleção; verificar ausência de IDs compartilhados entre referência e produção e registrar hashes/tamanhos. |
| **2.2** | Definição do cenário de drift | Fixar mudanças em `LIMIT_BAL` e `PAY_AMT1`, intensidade, seed, testes e limiares antes de verificar os resultados; documentar a interpretação temporal simulada. |
| **2.3** | Script de simulação | Gerar cópias original e modificada com os mesmos IDs e sem sobrescrever a origem; versionar lotes e parâmetros por DVC. |
| **2.4** | Inferência sobre dados de produção | Executar o Data Contract e gerar predições utilizando o modelo selecionado na Semana 1. |
| **2.5** | Integração com Evidently | Configurar a comparação estatística entre os datasets de referência e produção. |
| **2.6** | Detecção estatística de drift | Comparar referência com produção original (controle) e modificada, aplicando o protocolo pré-definido e relatando estatísticas, magnitude, limiares e limitações. |
| **2.7** | Relatório de drift | Gerar relatório HTML do Evidently, destacando variáveis com drift, resultados estatísticos e interpretações. |

### Estratégia de simulação

Será utilizado um conjunto de produção original e uma versão modificada desse mesmo conjunto,
mantendo tamanho e IDs entre os cenários. Referência e origens permanecem imutáveis.

A simulação deverá alterar intencionalmente duas variáveis financeiras, preservando tipos e
limites do contrato. Fixar transformações reproduzíveis que tratem zeros e caudas longas de
`PAY_AMT1`, sem tornar inválido o lote nem modificar outras features por acidente.

Escolher e registrar o método de cada feature e o limiar global de alerta. A configuração atual
traz `alpha = 0.05`, mas ainda não define teste, correção para múltiplas comparações, intensidade
ou critério de agregação. Não usar o valor como se fosse simultaneamente limiar de PSI e de
p-value. Para KS, justificar adequação a valores discretizados/empates e controlar múltiplos
testes quando aplicável; para PSI, definir bins na referência, tratamento de zeros e limiar de
efeito. Se o Evidently escolher outro método por padrão, explicitá-lo ou configurá-lo: não
rotular seu resultado como KS/PSI sem verificar. Relatar os resultados do controle, inclusive
alertas inesperados, sem prometer ausência absoluta de falsos positivos.

Os resultados permitirão comparar:

- Distribuições de referência e produção.
- Resultados dos testes estatísticos.
- Distribuições das probabilidades previstas pelo modelo.

A simulação será tratada como um experimento de **Data Drift**. Alterações artificiais nas features, mantendo os rótulos originais, não serão interpretadas como prova de Concept Drift ou degradação real de desempenho.

**Limite de cobertura do enunciado:** a página 2 cita Data Drift e Concept Drift, enquanto as
tarefas e a rubrica de drift detalham alteração de distribuições. Confirmar essa interpretação
com a docência antes do aceite final. Se for exigida demonstração de Concept Drift, planejar em
2.2/2.3 um experimento sintético separado com mudança explícita de `P(y|X)` e rótulos gerados sob
esse mecanismo; comparar com seu controle e identificar os rótulos como sintéticos. Não alterar
os rótulos reais nem alegar que Evidently sobre features, sozinho, detecta Concept Drift. A
pendência deve permanecer visível até haver decisão e evidência de cobertura.

### Critério de conclusão

A etapa estará concluída quando lotes válidos passarem pelo contrato e pela inferência, o
Evidently demonstrar drift nas duas variáveis sob critérios pré-definidos e o relatório HTML
incluir controle, métodos, estatísticas, limiares, hashes, seed e interpretação. Registrar também
distribuições de probabilidades previstas; não usar métricas calculadas com rótulos antigos de
features modificadas como evidência de perda real de desempenho. Resolver a cobertura de Concept
Drift antes de declarar atendimento integral ao enunciado.

**Entregável oficial:** relatório HTML ou painel customizado com identificação das variáveis
afetadas (enunciado, p. 5). A equipe escolheu HTML do Evidently, com interpretação e controle.

---

## 5. Fase 3 / Semana 3 — Observabilidade de Pipelines e Modelos

**Disciplina:** Monitoramento de Pipelines e Infraestrutura.

**Objetivo:** implementar mecanismos simples para registrar execuções, rastrear os experimentos de Machine Learning e visualizar métricas e alertas relacionados à saúde do pipeline.

O MLflow local será responsável pelo rastreamento de experimentos e artefatos. O Streamlit será
utilizado para construir o dashboard. DVC/DagsHub guarda versões dos objetos, enquanto MLflow
vincula execuções, parâmetros, métricas e relatórios a essas versões. Logs básicos começam nas
fases 1/2; esta fase centraliza sua visualização e correlação.

| ID | Entrega | Atividades |
|---|---|---|
| **3.1** | Implementação de logs | Registrar início, término, sucesso e falha nas etapas de validação, processamento, inferência e detecção de drift. |
| **3.2** | Coleta de métricas operacionais | Registrar duração, volumes, rejeições, falhas, alertas e sinais mínimos locais de estabilidade (tempo de CPU e pico de memória do processo), com unidades e limitações. |
| **3.3** | Configuração do MLflow | Criar ambiente local de rastreamento e configurar um experimento para o modelo selecionado. |
| **3.4** | Registro de métricas e artefatos | Integrar MLflow com ID de execução, SHA Git, hashes DVC/modelo/dados, configuração, versões, parâmetros, métricas e relatórios; distinguir métricas de validação/teste de sinais operacionais. |
| **3.5** | Desenvolvimento do dashboard Streamlit | Criar interface simples para visualizar execuções, métricas operacionais e resultados dos testes de drift. |
| **3.6** | Implementação de alertas | Definir e exibir alertas quando ocorrerem falhas de contrato, falhas de execução ou drift acima dos limites configurados. |
| **3.7** | Integração e validação do monitoramento | Demonstrar controle, drift em lote válido, rejeição de contrato e falha de execução controlada; verificar status, métricas e alertas coerentes no MLflow/Streamlit, incluindo estado sem execuções. |

### Métricas mínimas do dashboard

**Saúde do pipeline:**
- Status da última execução.
- Duração do processamento.
- Quantidade de registros processados.
- Quantidade de registros rejeitados.
- Contagens de entrada, aprovados e rejeitados sem dupla contagem; em rejeição integral, zero
  registros inferidos. Motivos podem se sobrepor e não devem ser somados como pessoas distintas.
- Número de falhas/alertas, tempo de CPU (s) e pico de memória do processo (MiB), com plataforma
  e método de coleta. Um valor não coletado deve aparecer como indisponível, não zero.

**Monitoramento do modelo:**
- Métricas do modelo selecionado.
- Quantidade de features com drift.
- Resultados estatísticos do monitoramento.
- Distribuição das predições.

**Alertas:**
- Falha de validação.
- Falha de execução.
- Detecção de drift.

O processamento e o rastreamento serão locais, com evidências de estabilidade do processo,
sem exigir monitoramento de uma infraestrutura cloud. O acesso ao armazenamento DagsHub requer
rede apenas para sincronização; com cache disponível, treino e dashboard permanecem locais.

Não serão implementados sistemas externos de notificações ou plataformas adicionais de monitoramento.

### Critério de conclusão

A etapa estará concluída quando os quatro cenários de 3.7 tiverem evidências por ID de execução,
logs, métricas e artefatos rastreáveis no MLflow e no dashboard, incluindo consumo local de
recursos. Um contrato inválido bloqueia inferência; um alerta de drift sinaliza investigação e
não dispara retreinamento automático nem se apresenta como prova de degradação real.

**Entregável oficial:** dashboard ou ambiente de rastreamento evidenciando saúde do pipeline,
estabilidade da infraestrutura e alertas (enunciado, p. 5). A equipe escolheu MLflow + Streamlit.

---

## 6. Fase 4 / Semana 4 — Governança e Apresentação

**Disciplinas:** Privacy By Design e Privacy By Default.

**Objetivo:** consolidar a documentação de governança, privacidade e causalidade, finalizar o repositório e apresentar os resultados do trabalho.

Minimização, atribuição/licença e proteção de credenciais são transversais e devem estar presentes
desde a fase 1; a semana 4 consolida o que foi efetivamente realizado.

| ID | Entrega | Atividades |
|---|---|---|
| **4.1** | Documentação de tratamento de dados | Descrever a origem do dataset, finalidade de utilização, variáveis pessoais existentes e medidas de proteção adotadas. |
| **4.2** | Plano de privacidade/LGPD | Distinguir o uso acadêmico dos dados públicos do cenário hipotético de crédito; documentar base legal proposta, acesso, retenção e descarte, incluindo cópias locais/remotas e limites do armazenamento por hash. |
| **4.3** | Governança do modelo | Documentar seleção, features, métricas, versões e análises agregadas de viés por grupos com denominadores e limitações amostrais; excluir demografia do modelo não garante ausência de viés. |
| **4.4** | Análise causal e resposta | Distinguir intervenções sintéticas conhecidas de hipóteses sobre economia/perfis; discutir explicações alternativas, impacto potencial e ações de investigação, revisão e mitigação sem alegar causalidade identificada. |
| **4.5** | Consolidação do README | Documentar arquitetura, instalação, execução, modelos treinados, contratos, drift, observabilidade, governança e causalidade. |
| **4.6** | Produção do vídeo STAR | Gravar demonstração de até cinco minutos, abordando Situation, Task, Action e Result. |
| **4.7** | Revisão e entrega final | Reproduzir em checkout/cache separado com dependências travadas e `dvc pull`, conferir logs/relatórios/dashboard, acesso dos avaliadores, histórico, vídeo e matriz de cobertura do enunciado. |

### Estrutura do vídeo STAR

| Etapa | Tempo sugerido | Conteúdo |
|---|---|---|
| Situation | 45 s | Contexto da fintech e risco de degradação silenciosa |
| Task | 45 s | Objetivos e requisitos do Tech Challenge |
| Action | 2 min 20 s | Demonstração dos contratos, modelo, Evidently, MLflow e Streamlit |
| Result | 1 min 10 s | Alertas, resultados, lições aprendidas e governança |

### Critério de conclusão

A etapa estará concluída quando o README apresentar toda a documentação de governança e análise causal, o projeto puder ser executado conforme as instruções e o vídeo STAR estiver disponível por link.

**Entregável oficial:** documentação de Governança e Causalidade no README, acompanhada do link para o vídeo.

---

## 7. Organização do trabalho em grupo

As 28 entregas serão acompanhadas pelo GitHub Projects, com registro de responsáveis e status.

As frentes iniciais registradas no README são:

| Integrante | Frente inicial (não atribui automaticamente cada entrega) |
|---|---|
| Fábio Polli | Repositório, arquitetura, CI e integração |
| Bill Kopp | Plano técnico e modelagem |
| Denis Barros Melo | Engenharia e qualidade de dados |
| Romario Silva | Observabilidade, dashboard e integração |

Para cada ID, confirmar responsável único, revisor, dependências, prazo e link de evidência no
GitHub Projects e no checklist. Atribuição de governança/causalidade e o revisor de cada entrega
ainda precisam ser confirmados; a tabela não representa aceite de responsabilidade individual.

Cada entrega deverá possuir evidência verificável: código/testes/documentação no Git e, para
objetos grandes, hash DVC e recuperação no DagsHub. Capturas/relatórios compartilháveis devem
referenciar commit e execução, sem dados pessoais ou credenciais. Um arquivo presente não basta
para marcar a entrega concluída sem verificar o critério de aceite.

O desenvolvimento deverá ocorrer de forma incremental: as funcionalidades produzidas em uma semana serão reutilizadas na semana seguinte.

### Marcos, caminho crítico e recursos

| Marco | Dependência e evidência para avançar |
|---|---|
| M1 — fim da fase 1 | Contrato bloqueia lotes inválidos; modelo selecionado com protocolo de avaliação registrado; dados/modelo recuperáveis do remote. |
| M2 — fim da fase 2 | M1 + cenários e relatório de drift reproduzíveis, com controle e limiares registrados. |
| M3 — fim da fase 3 | M2 + quatro cenários operacionais correlacionados no MLflow/Streamlit e sinais de recursos locais. |
| M4 — entrega | M3 + governança/causalidade no README, reprodução independente, vídeo acessível e cobertura do enunciado resolvida. |

O caminho crítico é dados/contrato → seleção/versionamento → simulação/relatório → integração
de monitoramento → reprodução e vídeo. Documentação e governança progridem em paralelo.
O cronograma de quatro semanas é uma estimativa relativa; início, prazo oficial e disponibilidade
da equipe não foram informados. Confirmá-los antes de prometer datas, sem reduzir os aceites.

Recursos previstos: máquina local com Python 3.12/uv, espaço para cache DVC e artefatos MLflow,
contas GitHub/DagsHub e acesso de leitura para equipe/avaliação. Medir duração e memória da
primeira execução para confirmar viabilidade. Não há orçamento nem cota de serviço aprovados;
verificar acesso, visibilidade e limites de armazenamento antes da sincronização inicial.

## 8. Escopo simplificado

Para concentrar o trabalho nos critérios de avaliação da FIAP, não serão desenvolvidos:

- Infraestrutura própria de cloud/compute remoto ou Kubernetes; DagsHub Storage é a exceção
  gerenciada de armazenamento, mantendo processamento, MLflow e dashboard locais.
- APIs de inferência em tempo real.
- Serviços de banco dedicados e filas; o arquivo SQLite local do MLflow está dentro do escopo.
- Orquestradores complexos de pipelines.
- Redes neurais ou sistemas de AutoML.
- Otimização extensa de hiperparâmetros.
- Sistemas externos de alertas.
- Retreinamento automático.
- Plataformas adicionais de monitoramento.

O projeto utilizará apenas os dois algoritmos definidos e as ferramentas essenciais de validação,
drift, rastreamento, versionamento (DVC/DagsHub Storage) e visualização.

### Riscos e decisões ainda necessárias

| Risco/pendência | Controle e próxima ação |
|---|---|
| Cobertura de Concept Drift | Bill/equipe deve confirmar com a docência a interpretação da p. 2; registrar resposta e eventual cenário sintético antes do aceite final. |
| Exposição do teste durante EDA/reexecuções | Revisar 1.2/1.6, registrar uso prévio e congelar protocolo; não apresentar o teste já consultado como avaliação intocada nem simplesmente trocar seed até obter resultado melhor. |
| DagsHub ainda não configurado e suporte S3 não declarado | Concluir 1.1 com owner/endpoint real, credenciais locais e dependências S3 travadas; só declarar recuperação após teste em cache separado. |
| Métodos/limiares e intensidades de drift incompletos | Fixar em 2.2 antes da execução de aceite; reportar falhas/controle e revisar o desenho com histórico se o cenário não funcionar. |
| Prazo, responsáveis e capacidade local não confirmados | Confirmar datas e responsáveis por ID; medir a primeira execução e ajustar a estimativa sem inventar compromisso da equipe. |

Essas pendências não representam resultados obtidos. Contrato Pandera, simulação, integração
MLflow/Streamlit e os controles acima devem ser implementados/verificados nas entregas indicadas.

## 9. Critérios de avaliação

| Critério oficial | Peso | Fase / evidência de aceite |
|---|---:|---|
| Validação de Dados | 25% | 1 — pelo menos três regras rígidas, controles válido/inválidos e bloqueio antes da inferência. |
| Detecção de Drift | 25% | 2 — duas variáveis alteradas, testes/limiares explícitos e relatório HTML com controle. |
| Observabilidade e Logs | 20% | 3 — logs correlacionados, métricas operacionais/recursos e alertas visíveis nos cenários de teste. |
| Governança (LGPD) | 15% | 4 — privacidade, base legal proposta, retenção, viés, riscos e causalidade consolidados no README. |
| Vídeo STAR | 15% | 4 — demonstração técnica, impacto e limitações, link acessível e duração total ≤ 5 min. |

O dataset financeiro binário deve manter pelo menos 5.000 amostras úteis (enunciado, p. 7);
registrar contagem após limpeza. Pesos somam 100%. DagsHub, comparação de dois modelos e o uso
conjunto de MLflow/Streamlit são critérios internos adicionais, não exigências da rubrica oficial.

## 10. Resultado final esperado

Ao final das quatro semanas, o grupo deverá possuir:

1. Um modelo de Credit Scoring selecionado a partir da comparação entre Regressão Logística e Random Forest.
2. Um Data Contract Pandera capaz de bloquear lotes inválidos.
3. Um mecanismo reproduzível de simulação de Data Drift.
4. Um relatório Evidently demonstrando as alterações de distribuição.
5. Um ambiente MLflow registrando métricas, parâmetros e artefatos.
6. Um dashboard Streamlit apresentando a saúde do pipeline e seus alertas.
7. Um repositório GitHub documentado, acompanhado do vídeo STAR.
8. Ponteiros e metadados DVC no GitHub, com datasets e modelos aprovados recuperáveis do DagsHub Storage.

**Princípio orientador:** implementar somente o necessário para demonstrar, de forma clara e reproduzível, os requisitos de validação, detecção de drift, observabilidade e governança definidos no Tech Challenge.

## 11. Protocolo de execução agêntica

### Unidade de trabalho e autonomia

Executar um ID por vez, ou um recorte verificável dele, com um agente executor e revisão humana
atribuída pela equipe. A solicitação atual de detalhamento é de Bill Kopp; os responsáveis e
revisores da implementação continuam a confirmar. Os planos não pressupõem subagentes,
execução paralela automática ou nova plataforma de orquestração.

Antes de editar, ler `AGENTS.md`, este plano, o plano da fase, o checklist e a arquitetura;
inspecionar branch, diff, configuração, testes e artefatos atuais. Reaproveitar implementação
existente após verificá-la. Trabalhar em branch `<tipo>/<integrante>/<descricao-curta>`, respeitar
o trabalho de outros integrantes e confirmar o responsável do ID no início da execução.

O agente pode inspecionar, implementar e testar localmente dentro da tarefa autorizada. Commit,
push, PR, publicação de objetos DVC/vídeo, criação de recursos externos e exclusão de versões
dependem da autorização aplicável; o plano não concede essas permissões. Se uma dependência
externa bloquear um aceite, continuar apenas trabalho local independente e relatar o bloqueio.
Não declarar o marco completo sem a evidência faltante.

### Ciclo de execução

1. **Reconstruir:** verificar entradas, hashes, versão do ambiente, dependências e estado real.
2. **Delimitar:** registrar ID, objetivo, arquivos, responsável/revisor e teste de aceite antes
   de implementar; decompor mudanças grandes em recortes que preservem um caminho funcional.
3. **Executar:** fazer a menor mudança que satisfaça o recorte, com configuração explícita e
   efeitos locais previsíveis. Não sobrescrever lotes, resultados ou decisões de outra execução.
4. **Verificar:** executar teste proporcional e controle negativo quando o requisito envolve
   bloqueio/detecção; registrar comando, versão, código de saída e evidência, inclusive falhas.
5. **Revisar:** inspecionar diff, privacidade e consistência entre código, configuração e docs;
   encaminhar para revisão com limitações e dependências ainda abertas.
6. **Transferir:** informar o que mudou, o que passou, o que não foi executado e o próximo ID.
   Atualizar o checklist apenas quando status, aceite, responsável ou evidência realmente mudar.

Usar `Pendente`, `Em andamento`, `Em revisão` e `Concluído` como no checklist. Registrar bloqueio
como motivo junto ao status existente, sem inventar conclusão. Aceite técnico verificado segue
para revisão; somente registrar conclusão após a revisão definida pela equipe.

### Contrato de entrada e saída da tarefa

Usar este modelo no pedido ao agente e no handoff; campos não verificados ficam explicitamente
pendentes. Datas e estimativas dependem da disponibilidade confirmada, sem compromissos fictícios.

```text
ID / recorte:
Objetivo e limite da mudança:
Responsável / revisor / prazo confirmado ou pendente:
Dependências aceitas e entradas (caminho + hash/versão):
Branch / SHA de base / alterações preexistentes relevantes:
Arquivos permitidos e interfaces a preservar:
Passos e teste de aceite (resultado esperado antes de executar):
Decisões/propostas ainda não aprovadas:
Resultado observado / comandos / códigos de saída / ambiente:
Evidências (arquivo, SHA Git, hash DVC, run_id quando aplicável):
Bloqueios, testes não executados e limitações:
Próximo recorte e condição para retomada:
```

Como convenção proposta, registrar evidências textuais agregadas em `docs/evidence/fase-N.md`,
com seção por ID, e indexá-las na entrega 4.7. Esses arquivos ainda serão criados durante a
implementação. Não copiar linhas de clientes, segredos ou resultados fictícios para o registro.
Dados/modelos e relatórios autorizados ficam no DVC; logs, banco e artefatos MLflow ficam locais.
Referenciar seus hashes/IDs no registro textual em vez de adicioná-los diretamente ao Git.

### Retomada e critérios de interrupção

Ao retomar, conferir o estado atual: não repetir treino, teste final ou sincronização só porque
uma conversa anterior os propôs. Reusar artefatos compatíveis por hash e verificar o que falta.
Se código/configuração/dados mudaram, invalidar as evidências dependentes e explicar quais
precisam de nova execução. Não reutilizar resultados de versões diferentes como um único aceite.

Interromper o caminho dependente quando houver vazamento de dados, contrato burlado, origem
incompatível, permissão externa ausente ou resultado divergente do protocolo. Registrar causa,
evidência e decisão necessária. Um experimento sem detecção esperada é inconclusivo/falho para
o aceite: preservar o resultado e versionar um novo desenho, sem ajustar até passar em silêncio.
