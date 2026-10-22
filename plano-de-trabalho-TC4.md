# Tech Challenge — Fase 4
## Plano de Trabalho: Credit Scoring, Data Drift e Observabilidade

**Duração:** 4 semanas  
**Organização:** 4 etapas, com 7 entregas por etapa  
**Total:** 28 entregas  
**Dataset:** UCI Default of Credit Card Clients (ID 350)

---

## 1. Objetivo do projeto

Desenvolver uma solução simplificada de Machine Learning para classificação de risco de inadimplência de clientes de cartão de crédito, incorporando mecanismos de validação de dados, detecção de drift, observabilidade e governança.

O projeto simulará um cenário no qual uma fintech possui um modelo de Credit Scoring em operação e precisa monitorar a qualidade dos dados e identificar alterações que possam comprometer a confiabilidade de suas previsões.

O desenvolvimento será realizado localmente, utilizando ferramentas open-source, sem necessidade de infraestrutura cloud ou sistemas complexos de implantação.

## 2. Stack tecnológica

| Componente | Tecnologia definida |
|---|---|
| Linguagem | Python |
| Dataset | UCI Default of Credit Card Clients |
| Processamento | Pandas e NumPy |
| Modelo baseline | Scikit-learn — LogisticRegression |
| Modelo candidato principal | Scikit-learn — RandomForestClassifier |
| Contratos de dados | Pandera |
| Detecção de drift | Evidently AI |
| Rastreamento | MLflow |
| Dashboard | Streamlit |
| Versionamento | Git e GitHub |
| Documentação | Markdown |

### Dataset selecionado

O dataset **Default of Credit Card Clients**, disponibilizado pela UCI Machine Learning Repository, contém:

- 30.000 registros de clientes.
- 23 variáveis preditoras.
- Variável-alvo binária que indica inadimplência no mês seguinte.
- Histórico de pagamentos, valores de faturas, pagamentos efetuados e informações demográficas.

**Fonte:** https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients

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

A seleção será realizada com base no desempenho de validação e na simplicidade da solução. Apenas o modelo selecionado seguirá para as etapas de simulação e monitoramento.

---

## 3. Semana 1 — Validação de Dados e Contratos

**Disciplina:** Validação de Dados e Bibliotecas de Qualidade.

**Objetivo:** preparar os dados, treinar e selecionar um modelo baseline de Credit Scoring e implementar um contrato de validação que impeça a ingestão de dados inválidos.

| ID | Entrega | Atividades |
|---|---|---|
| **1.1** | Configuração do repositório | Criar repositório GitHub, definir estrutura de diretórios, dependências Python e instruções iniciais de execução. |
| **1.2** | Aquisição e exploração do dataset | Obter o dataset UCI, identificar variáveis, tipos, distribuição do alvo, valores ausentes, duplicatas e possíveis inconsistências. |
| **1.3** | Preparação dos dados | Selecionar as 19 features financeiras, preparar os dados e realizar divisão estratificada em treino (70%), validação (15%) e teste (15%). |
| **1.4** | Treinamento da Regressão Logística | Implementar pipeline de pré-processamento e treinar o classificador baseline com Scikit-learn. |
| **1.5** | Treinamento do Random Forest | Treinar o segundo classificador, utilizando parâmetros iniciais simples para controlar o overfitting. |
| **1.6** | Avaliação e seleção do modelo | Comparar ROC-AUC, precision, recall, F1-score e matriz de confusão. Selecionar e serializar o modelo final, registrando a justificativa. |
| **1.7** | Implementação do Data Contract | Criar pelo menos três regras rígidas com Pandera e demonstrar que um lote contendo dados inválidos é rejeitado antes da inferência. |

### Regras iniciais do Data Contract

1. Identificadores de clientes não podem estar duplicados no lote.
2. `LIMIT_BAL` deve apresentar valor positivo.
3. `AGE` deve estar dentro de um intervalo válido para clientes adultos.
4. Features obrigatórias não podem conter valores nulos.

As regras definitivas serão ajustadas ao esquema original do dataset.

### Critério de conclusão

A etapa estará concluída quando:

- Os dois algoritmos estiverem treinados e avaliados.
- Um modelo tiver sido formalmente selecionado.
- O modelo selecionado realizar predições sobre dados válidos.
- O contrato Pandera bloquear comprovadamente um lote inválido.

**Entregável oficial:** modelo baseline treinado e script funcional de validação de dados.

---

## 4. Semana 2 — Simulação e Detecção de Drift

**Disciplina:** Data Drift.

**Objetivo:** simular alterações nas distribuições das variáveis financeiras dos clientes e identificar estatisticamente essas mudanças usando Evidently AI.

| ID | Entrega | Atividades |
|---|---|---|
| **2.1** | Definição dos datasets de referência e produção | Preservar um conjunto de referência sem alterações e separar um lote independente para representar os dados de produção. |
| **2.2** | Definição do cenário de drift | Selecionar duas variáveis financeiras para alteração, preferencialmente `LIMIT_BAL` e `PAY_AMT1`, e documentar as mudanças pretendidas. |
| **2.3** | Script de simulação | Implementar em Python a geração reproduzível de um lote de produção com distribuições modificadas. |
| **2.4** | Inferência sobre dados de produção | Executar o Data Contract e gerar predições utilizando o modelo selecionado na Semana 1. |
| **2.5** | Integração com Evidently | Configurar a comparação estatística entre os datasets de referência e produção. |
| **2.6** | Detecção estatística de drift | Executar testes adequados às variáveis, como Kolmogorov-Smirnov ou PSI, e identificar alterações nas distribuições. |
| **2.7** | Relatório de drift | Gerar relatório HTML do Evidently, destacando variáveis com drift, resultados estatísticos e interpretações. |

### Estratégia de simulação

Será utilizado um conjunto de produção original e uma versão modificada desse conjunto.

A simulação deverá alterar intencionalmente duas variáveis financeiras, preservando os limites estabelecidos pelo contrato de dados.

Os resultados permitirão comparar:

- Distribuições de referência e produção.
- Resultados dos testes estatísticos.
- Distribuições das probabilidades previstas pelo modelo.

A simulação será tratada como um experimento de **Data Drift**. Alterações artificiais nas features, mantendo os rótulos originais, não serão interpretadas como prova de Concept Drift ou degradação real de desempenho.

### Critério de conclusão

A etapa estará concluída quando o grupo demonstrar, utilizando o Evidently, alterações estatisticamente detectáveis em pelo menos duas variáveis e produzir um relatório HTML documentando os resultados.

**Entregável oficial:** relatório de drift em HTML com identificação das variáveis afetadas.

---

## 5. Semana 3 — Observabilidade de Pipelines e Modelos

**Disciplina:** Monitoramento de Pipelines e Infraestrutura.

**Objetivo:** implementar mecanismos simples para registrar execuções, rastrear os experimentos de Machine Learning e visualizar métricas e alertas relacionados à saúde do pipeline.

O MLflow será responsável pelo rastreamento de experimentos e artefatos. O Streamlit será utilizado para construir o dashboard.

| ID | Entrega | Atividades |
|---|---|---|
| **3.1** | Implementação de logs | Registrar início, término, sucesso e falha nas etapas de validação, processamento, inferência e detecção de drift. |
| **3.2** | Coleta de métricas operacionais | Registrar duração das execuções, quantidade de registros processados, registros rejeitados e falhas. |
| **3.3** | Configuração do MLflow | Criar ambiente local de rastreamento e configurar um experimento para o modelo selecionado. |
| **3.4** | Registro de métricas e artefatos | Integrar o pipeline ao MLflow, registrando parâmetros, métricas do modelo e relatórios de drift. |
| **3.5** | Desenvolvimento do dashboard Streamlit | Criar interface simples para visualizar execuções, métricas operacionais e resultados dos testes de drift. |
| **3.6** | Implementação de alertas | Definir e exibir alertas quando ocorrerem falhas de contrato, falhas de execução ou drift acima dos limites configurados. |
| **3.7** | Integração e validação do monitoramento | Executar o pipeline em cenários normais e com falhas, demonstrando os registros no MLflow e os resultados no Streamlit. |

### Métricas mínimas do dashboard

**Saúde do pipeline:**
- Status da última execução.
- Duração do processamento.
- Quantidade de registros processados.
- Quantidade de registros rejeitados.

**Monitoramento do modelo:**
- Métricas do modelo selecionado.
- Quantidade de features com drift.
- Resultados estatísticos do monitoramento.
- Distribuição das predições.

**Alertas:**
- Falha de validação.
- Falha de execução.
- Detecção de drift.

A infraestrutura será local. Quando necessário, métricas simples de consumo de recursos do processo poderão ser registradas para complementar as informações sobre sua estabilidade.

Não serão implementados sistemas externos de notificações ou plataformas adicionais de monitoramento.

### Critério de conclusão

A etapa estará concluída quando uma execução do pipeline produzir logs, métricas e artefatos rastreáveis no MLflow, e o dashboard Streamlit apresentar o status das execuções e os alertas correspondentes.

**Entregável oficial:** ambiente de rastreamento e dashboard demonstrando a saúde do pipeline e os alertas de degradação.

---

## 6. Semana 4 — Governança e Apresentação

**Disciplinas:** Privacy By Design e Privacy By Default.

**Objetivo:** consolidar a documentação de governança, privacidade e causalidade, finalizar o repositório e apresentar os resultados do trabalho.

| ID | Entrega | Atividades |
|---|---|---|
| **4.1** | Documentação de tratamento de dados | Descrever a origem do dataset, finalidade de utilização, variáveis pessoais existentes e medidas de proteção adotadas. |
| **4.2** | Plano de conformidade LGPD | Documentar a base legal aplicável ao cenário hipotético da fintech, princípios de privacidade, retenção e descarte dos dados. |
| **4.3** | Governança do modelo | Documentar critérios de seleção do algoritmo, features utilizadas, métricas, rastreabilidade e possíveis riscos de vieses. |
| **4.4** | Análise causal da degradação | Discutir possíveis causas das alterações de distribuição, seu impacto potencial e estratégias de investigação e mitigação. |
| **4.5** | Consolidação do README | Documentar arquitetura, instalação, execução, modelos treinados, contratos, drift, observabilidade, governança e causalidade. |
| **4.6** | Produção do vídeo STAR | Gravar demonstração de até cinco minutos, abordando Situation, Task, Action e Result. |
| **4.7** | Revisão e entrega final | Verificar funcionamento dos scripts, documentação, relatórios, dashboard, histórico de commits e link do vídeo. |

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

Sugere-se dividir a equipe em quatro frentes:

| Frente | Responsabilidade |
|---|---|
| Engenharia de Dados | Dataset, pré-processamento e Pandera |
| Machine Learning | Regressão Logística, Random Forest e Evidently |
| MLOps e Observabilidade | Pipeline, logs, MLflow e Streamlit |
| Governança e Integração | Documentação, LGPD, causalidade e apresentação |

Cada entrega deverá possuir evidência verificável no repositório, como código, relatório, teste, captura de tela ou documentação.

O desenvolvimento deverá ocorrer de forma incremental: as funcionalidades produzidas em uma semana serão reutilizadas na semana seguinte.

## 8. Escopo simplificado

Para concentrar o trabalho nos critérios de avaliação da FIAP, não serão desenvolvidos:

- Infraestrutura cloud ou Kubernetes.
- APIs de inferência em tempo real.
- Bancos de dados e filas dedicadas.
- Orquestradores complexos de pipelines.
- Redes neurais ou sistemas de AutoML.
- Otimização extensa de hiperparâmetros.
- Sistemas externos de alertas.
- Retreinamento automático.
- Plataformas adicionais de monitoramento.

O projeto utilizará apenas os dois algoritmos definidos e as ferramentas essenciais de validação, drift, rastreamento e visualização.

## 9. Critérios de avaliação

| Critério oficial | Peso | Etapa principal |
|---|---:|---|
| Validação de Dados | 25% | Semana 1 |
| Detecção de Drift | 25% | Semana 2 |
| Observabilidade e Logs | 20% | Semana 3 |
| Governança (LGPD) | 15% | Semana 4 |
| Vídeo STAR | 15% | Semana 4 |

## 10. Resultado final esperado

Ao final das quatro semanas, o grupo deverá possuir:

1. Um modelo de Credit Scoring selecionado a partir da comparação entre Regressão Logística e Random Forest.
2. Um Data Contract Pandera capaz de bloquear lotes inválidos.
3. Um mecanismo reproduzível de simulação de Data Drift.
4. Um relatório Evidently demonstrando as alterações de distribuição.
5. Um ambiente MLflow registrando métricas, parâmetros e artefatos.
6. Um dashboard Streamlit apresentando a saúde do pipeline e seus alertas.
7. Um repositório GitHub documentado, acompanhado do vídeo STAR.

**Princípio orientador:** implementar somente o necessário para demonstrar, de forma clara e reproduzível, os requisitos de validação, detecção de drift, observabilidade e governança definidos no Tech Challenge.