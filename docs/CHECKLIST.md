# Checklist das entregas

Status possíveis: `Pendente`, `Em andamento`, `Em revisão`, `Concluído`.

Os 28 IDs correspondem ao [plano geral](plans/plano-de-trabalho-TC4.md); não definem ordem
obrigatória. Na fase 1, integrar 1.7 antes de 1.4/1.5. Itens sem status explícito estão pendentes;
links de código não significam aceite verificado. O **grau de prova** de cada entrega da fase 1
(execução original × revalidação independente por execução) está na seção "Grau de evidência por
seção" de [`docs/evidence/fase-1.md`](evidence/fase-1.md).

## Semana 1 - Validação de dados e contratos

- [x] **1.1** Configuração inicial e DagsHub - Concluído - `dvc[s3]` e `xlrd` travados no `uv.lock`; `dvc.lock` regularizado e `dvc status` limpo; remote `dagshub` configurado, 25 objetos enviados e **recuperação provada em checkout/cache separado**; workbook original migrado do Git para o DVC. Ver [`docs/evidence/fase-1.md`](evidence/fase-1.md) §1.1 e §1.6.1. **Revalidado por execução** em §1.1.1 (clone novo do GitHub sem cache: instalação travada, recuperação remota do zero, integridade dos hashes e inferência sobre o modelo recuperado); o item ali achado — a reavaliação das dependências de fases futuras — foi **fechado** no mesmo dia: `evidently`, `mlflow`, `streamlit` e `ucimlrepo` passaram para os extras `drift`, `observability` e `provenance`, com o ambiente padrão reduzido de 244 para 170 pacotes.
- [x] **1.2** Aquisição e exploração - Concluído - estágio `acquire` reconstrói o bruto a partir do XLS com hashes conferidos; proveniência (DOI, CC BY 4.0, hashes, parâmetros de leitura) em [`docs/DATASET.md`](DATASET.md); auditoria estrutural (`eda`) separada da exploração supervisionada no treino (`explore`); **exposição prévia do teste declarada** em [`docs/evidence/fase-1.md`](evidence/fase-1.md) §1.2.1.
- [x] **1.3** Preparação e split 70/15/15 - Concluído - `src/credit_monitoring/data/prepare.py`; auditoria de IDs disjuntos, seed 42, referência = treino por hash, linhas úteis ≥ 5.000 e união das remoções (0 linhas no dado real, caminho de remoção coberto por fixture controlada) em `data/processed/preparation_report.json`; **revalidada por execução** em [`docs/evidence/fase-1.md`](evidence/fase-1.md) §1.3.1, com a falha por IDs compartilhados coberta por teste e o relatório vinculado à impressão digital da configuração, às razões de split e ao arredondamento das taxas.
- [x] **1.4** Treinamento da Regressão Logística - Concluído - `src/credit_monitoring/models/train.py`; contrato precede o `fit` (spy com zero chamadas em falha); ROC-AUC de validação 0,714497; convergência e custo local registrados. **Revalidado por execução** em [`docs/evidence/fase-1.md`](evidence/fase-1.md) §1.4.1, com o escopo do `fit` (só o treino) agora provado por teste e por perturbação da validação. **Baseline serializado** como artefato versionado (`models/candidates/`), com hash nos metadados (§1.5.2).
- [x] **1.5** Treinamento do Random Forest - Concluído - mesmo estágio de treino, mesmas entradas e hashes do baseline; ROC-AUC de validação 0,774103; custo local registrado; não se exige que vença o baseline. **Revalidado por execução** em §1.5.1, com a recalculabilidade das métricas e a soma da matriz de confusão agora provadas por teste. **Todos os candidatos serializados** e auditáveis por artefato (§1.5.2), sem avaliar o baseline no teste.
- [x] **1.6** Seleção, serialização e versionamento - Concluído - `train` (seleção) e `evaluate` (avaliação final) em estágios separados; desempate explícito pelo baseline sobre métricas não arredondadas; recarga verificada (tolerância 1e-12); metadados completos com limiar, hashes, SHA do código, versão do contrato e exposição declarada; **recuperação remota provada** (hashes conferidos e inferência do modelo recuperado com diferença de 3,33e-16). **Caminho local revalidado por execução** em §1.6.2.
- [x] **1.7** Pandera antes do treino/inferência - Concluído - `src/credit_monitoring/contracts/`; lote válido aceito, 7+ perturbações isoladas rejeitadas com rejeição integral do lote e diagnóstico por regra/coluna/contagem; CLI com saída não zero; evidência em [`docs/evidence/fase-1.md`](evidence/fase-1.md) §1.7; **revalidada por execução** em §1.7.1, com o spy de predição (zero chamadas em falha) e a prova de validação do lote integral antes da seleção das 19 entradas agora automatizadas e verificadas por mutação.

## Extensão do plano 1.6 — campanha de otimização dos modelos

Extensão **planejada** por Bill Kopp, sem criar uma quinta fase e sem substituir o aceite
histórico de M1. Detalhes em [`docs/plans/1.6-otimizacao-modelos.md`](plans/1.6-otimizacao-modelos.md);
evidência em [`docs/evidence/1.6-otimizacao-modelos.md`](evidence/1.6-otimizacao-modelos.md).

- [x] **1.6-O1** Protocolo e preservação - Concluído - `configs/optimization.yaml` congela folds, sementes, orçamento, critérios e espaços de busca; manifesto com hashes, versões, fontes e lista efetiva de trials gravado em `reports/optimization/<exp>/tuning/manifest.json` antes de qualquer resultado.
- [x] **1.6-O2** Busca no treino - Concluído - `src/credit_monitoring/models/tune.py` lê **somente** `train.csv`; controles, 24 configurações de RF e 12 de LR nos mesmos cinco folds, com pré-processamento ajustado dentro dos folds; falhas registradas, nunca convertidas em score zero.
- [x] **1.6-O3** Ablação e finalistas - Concluído - uma única variante de razões financeiras por família (`src/credit_monitoring/models/features.py`), repetição do RF com as sementes 17 e 73 sem escolher a melhor, e um finalista congelado por algoritmo.
- [x] **1.6-O4** Seleção e promoção - Concluído - rodada única de validação com o RF vigente e os dois finalistas, bootstrap pareado e estratificado (2.000 reamostragens, seed 42, intervalo de 97,5% por contraste), decisão explícita `promote` ou `keep_current` em `reports/optimization/<exp>/selection/comparison.json`, sem acesso ao teste.
- [x] **1.6-O5** Congelamento e transferência - Concluído - decisão integrada ao estágio de seleção (`src/credit_monitoring/models/train.py`): artefato publicado, metadados estendidos (algoritmo e versão candidata separados), incumbente arquivado e recarregado com paridade de probabilidades, `dvc.lock` coerente e sem dois donos para a mesma saída.
- [x] **1.6-O6** Laboratório de modelos - Concluído - `dashboard/app_dev.py` (Streamlit, extra `model_lab`) com artefatos e prontidão, comparação lado a lado com curvas ROC/PR, predição individual e em lote e cenários de contrato; serviço de inferência compartilhado em `src/credit_monitoring/models/inference.py`; testes com `streamlit.testing.v1.AppTest` e `dashboard/README.md`. Inspeção visual em navegador local registrada na evidência (§11.3), com o defeito de renderização encontrado e corrigido durante a inspeção (§11.4) e teste de regressão correspondente.

## Semana 2 - Simulação e detecção de drift

- [x] **2.1** Concluído localmente — `data/production/v1.0.2/original.csv` foi derivado da validação sem alvo; referência = treino; 4.500 IDs únicos, sem interseção referência/produção, mesma ordem entre cenários; hashes e proveniência em [`docs/evidence/fase-2.md`](evidence/fase-2.md).
- [x] **2.2** Concluído — protocolo Data Drift `1.0.2` congelado antes das comparações; máscara de zeros preservada por decisão de Bill. Concept Drift está explicitamente fora da demonstração desta entrega; a docência avaliará o plano após a entrega, sem ser gate.
- [x] **2.3** Concluído — simulação determinística declarada no DAG/`dvc.lock`; objetos de `1.0.2` enviados e recuperados em cache isolado (7 outputs); hashes verificados.
- [x] **2.4** Concluído localmente — contrato integral antes da inferência, modelo/hash/limiar congelados, 4.500 predições por cenário e associação um-para-um com IDs; nenhum alvo em produção.
- [x] **2.5** Concluído localmente — PSI customizado integrado ao HTML Evidently e ao JSON com bins/suavização/limiar explícitos; versão/aplicabilidade registradas em [`docs/evidence/fase-2.md`](evidence/fase-2.md).
- [x] **2.6** Concluído localmente para Data Drift — 19 features por comparação, controle sem alertas; `LIMIT_BAL` e `PAY_AMT1` sinalizam apenas no cenário modificado e na comparação original×modificado. PSI não é p-value.
- [x] **2.7** Concluído — HTML `1.0.2` ampliado e inspecionado em `reports/drift/phase-2-drift-v1.0.2-ptbr-v6.html`: perfil do dataset, estratégia/modelos, resultados separados de CV/validação/teste e explicação quantitativa do efeito do drift nos scores, sem alterar JSON/PSI/protocolo. A nova revisão foi enviada ao DagsHub e está versionada no Git como entrega do tech challenge; a geração é determinística e reproduz o mesmo hash. Concept Drift não é demonstrado e será avaliado pela docência após a entrega.

## Semana 3 - Observabilidade

- [x] **3.1** Logs estruturados por tentativa e etapa, com encerramento testado nos quatro cenários sintéticos.
- [x] **3.2** Contagens por lote, duração, CPU e pico de memória do processo com unidades/plataforma; verificados localmente.
- [x] **3.3** MLflow local com SQLite e experimento do projeto; registro e leitura verificados.
- [x] **3.4** Registro de métricas, artefatos e proveniência verificado com os objetos oficiais recuperados via DVC; quatro runs vinculados às respectivas tentativas.
- [x] **3.5** Dashboard operacional verificado com AppTest e Playwright no Edge. Capturas locais mostram estado, métricas, volumes, alertas e detalhe do PSI.
- [x] **3.6** Alertas persistidos de contrato, execução e drift; deduplicação e exibição cobertas pela matriz sintética.
- [x] **3.7** Matriz oficial com quatro cenários registrada no MLflow e conferida no navegador com Playwright. O estado vazio também passou. Ver [evidências e reprodução](evidence/fase-3.md).

## Semana 4 - Governança e apresentação

- [x] **4.1** Concluído - origem, finalidade, variáveis pessoais, minimização e inventário por artefato (com versionamento Git/DVC e cópias) em [`docs/GOVERNANCE.md`](GOVERNANCE.md) §1, conferido contra `.gitignore`, `dvc.yaml` e `git ls-files`. Ver [`docs/evidence/fase-4.md`](evidence/fase-4.md).
- [ ] **4.2** Em revisão - uso acadêmico × cenário hipotético, base legal **proposta**, acesso, retenção e descarte (incluindo DVC/DagsHub e limites do armazenamento por hash) em [`docs/GOVERNANCE.md`](GOVERNANCE.md) §2. Pendente de decisão humana: revisão jurídica, prazos e responsáveis de retenção, acesso de leitura dos avaliadores; o texto da LGPD foi confirmado só em parte.
- [ ] **4.3** Em revisão - ficha do modelo e análise agregada de viés por `SEX`, `EDUCATION`, `MARRIAGE` e `AGE` (`src/credit_monitoring/models/bias.py`, `tests/test_bias.py`, `reports/bias/validation_bias.json`), com denominadores, intervalos e limitações; teste não consultado. Gerada com o modelo local, que reproduz a matriz de confusão oficial da validação mas tem hash diferente do objeto DVC; fechar após `dvc pull` e nova execução. Ver [`docs/evidence/fase-4.md`](evidence/fase-4.md) §2.
- [x] **4.4** Concluído - intervenção sintética conhecida × hipóteses de contexto, explicações alternativas, evidência adicional e matriz de resposta, ancoradas em `reports/drift/results-v1.0.2.json`; sem alegar causalidade identificada nem Concept Drift. [`docs/GOVERNANCE.md`](GOVERNANCE.md) §4.
- [ ] **4.5** Em andamento - seções "Governança e LGPD" e "Análise causal" no README, com resultados de viés e limitações. Faltam o link do vídeo e a validação do README por outro integrante.
- [ ] **4.6** Pendente - vídeo STAR de até cinco minutos, a ser gravado por outro integrante do grupo.
- [ ] **4.7** Pendente - reprodução em checkout/cache separado, acesso dos avaliadores aos objetos/relatórios, histórico e matriz de cobertura/limitações; a docência avaliará o plano após a entrega. Rascunho da matriz por critério em [`docs/evidence/fase-4.md`](evidence/fase-4.md) §5.
