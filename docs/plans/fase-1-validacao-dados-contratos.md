# Fase 1 — Validação de Dados e Contratos

> Plano de execução, revisado em 2026-10-26. Expande os IDs 1.1–1.7; não atesta implementação.

- **Plano geral:** [escopo, protocolo e aceites](plano-de-trabalho-TC4.md).
- **Próxima fase:** [Simulação e Detecção de Drift](fase-2-simulacao-deteccao-drift.md).
- **Referências:** [arquitetura](../ARCHITECTURE.md), [checklist](../CHECKLIST.md),
[dataset](../DATASET.md), [DagsHub](../DAGSHUB.md) e [governança](../GOVERNANCE.md).

## 1. Resultado e fronteiras

Produzir dados auditados, contrato Pandera integrado, comparação de Regressão Logística e
Random Forest, modelo selecionado/congelado e recuperação verificável de dados/modelo via DVC.
Atende à etapa de validação do enunciado; a comparação dos dois algoritmos e o DagsHub são
escolhas internas. Não inclui simulação de drift nem dashboard integrado.

Aplicar o protocolo agêntico da seção 11 do plano geral a cada pacote. Responsáveis, revisores
e datas por ID precisam ser confirmados; a semana 1 é relativa. Aceites abaixo são observações
esperadas para a implementação futura, não resultados obtidos nesta revisão.

## 2. Entrada e diagnóstico inicial

- Ambiente local com Python 3.12, uv e espaço para cache/artefatos; confirmar disponibilidade.
- Fonte UCI 350 e configuração `configs/project.yaml`; autorização antes de publicar objetos.
- Existem `eda.py`, `data/prepare.py`, `models/train.py`, testes e estágios `eda → prepare → train`.
  Inspecionar o comportamento em vez de reescrever componentes automaticamente.
- O EDA atual analisa relações com o alvo no bruto completo. Separar auditoria estrutural da
  exploração supervisionada; registrar exposição anterior, sem prometer teste intocado.
- O treino atual carrega o teste e o avalia a cada execução, embora só avalie o escolhido.
  Separar seleção repetível da avaliação final explícita, preservando o histórico.
- Pandera não está integrado; o remote DagsHub e `dvc[s3]` ainda são pendências de 1.1.

### Ordem de execução

```text
1.1 (ambiente local) → 1.2 → 1.3 → 1.7 → 1.4 → 1.5 → 1.6 → M1
1.1 (remote/acesso) ────────────────────────────────────────┘
```

1.4 e 1.5 não dependem dos resultados um do outro, mas compartilham código/configuração; executar
sequencialmente por padrão. Sem acesso remoto, dados/contrato/modelos locais podem avançar,
mas 1.1/1.6 e M1 continuam sem o aceite de recuperação. Projetar o contrato junto a 1.3;
validar os dados preparados antes de qualquer ajuste de modelo.

## 3. Interfaces e artefatos

| Elemento | Contrato para execução |
|---|---|
| Fonte | Bruto imutável, hash SHA-256, URL/DOI/licença, conversão XLS/CSV e parâmetros de leitura |
| Dados preparados | `data/processed/{train,validation,test}.csv`, ID preservado, alvo canônico, 19 features e atributos de governança |
| Referência | `data/reference/reference.csv` igual ao treino intacto, inclusive IDs e serialização |
| Contrato | Esquema rotulado e esquema de inferência; retorno de sucesso ou diagnóstico de falha sem dados pessoais |
| Seleção | Métricas de validação dos dois modelos, regra de decisão, limiar e fingerprint da configuração |
| Modelo | `models/credit_model.joblib`, metadados de seleção/versões/hashes, predição reproduzível após carga |
| Avaliação final | Métricas do escolhido no teste e vínculo com a seleção congelada; exposição anterior declarada |
| Versionamento | Ponteiros/`dvc.lock` no Git; objetos aprovados no DagsHub e prova de leitura com cache separado |

Os diretórios `contracts/` dentro de `src/credit_monitoring/` e arquivos de seleção/avaliação
separados são propostas de implementação. Preservar consumidores de `reports/metrics.json`
ou migrá-los e documentar a mudança. Para entradas inválidas, nenhuma predição ou artefato de
sucesso deve ser produzido; não confundir arquivo antigo com resultado da tentativa atual.

## 4. Pacotes executáveis

### 1.1 — Configuração do repositório

**Dependências:** contas, owner/endpoint reais e autorização para conexão/sincronização externa.

**Ações do agente:**
1. Conferir branch, CI, `.gitignore`, `pyproject.toml`, `uv.lock` e `.dvc/config`; preservar ajustes locais.
2. Adicionar o extra S3 ao grupo dev via uv e atualizar o lock com a ferramenta, não manualmente.
3. Executar instalação travada e testes existentes antes de atribuir falhas à nova mudança.
4. Seguir o guia DagsHub para conexão/configuração autorizada. Credenciais só em configuração
   local ignorada; endpoint/owner não devem ser adivinhados nem tokens copiados ao registro.
5. Definir com a equipe o acesso de leitura e quais saídas DVC podem ser compartilhadas;
   preparar recuperação isolada a ser concluída em 1.6 quando existirem os objetos finais.

**Arquivos:** `pyproject.toml`, `uv.lock`, configuração DVC compartilhável e guia DagsHub.

**Verificação/aceite:** `uv sync --dev --locked` funciona; suporte S3 carregável; configuração
aponta ao repositório correto sem segredos no diff. Registrar recuperação do bruto quando
autorizada e completar a prova dos artefatos finais em 1.6. Sem uv/acesso, registrar o bloqueio.

### 1.2 — Aquisição e auditoria do dataset

**Dependências:** ambiente local de 1.1; origem do arquivo identificável.

**Ações do agente:**
1. Verificar procedência UCI 350, licença/atribuição, DOI, arquivo original e conversão utilizada.
   Se só houver CSV, registrar a lacuna de proveniência até conseguir comprovar a conversão.
2. Conferir separador `;`, segunda linha como cabeçalho na configuração atual, nomes e unidades NT$;
   não assumir que outro download terá o mesmo layout. Hash identifica a versão efetivamente lida.
3. Auditar contagens, tipos, nulos, IDs duplicados e códigos; preservar bruto e emitir resumo agregado.
4. Restringir o EDA anterior ao split a estrutura/qualidade. Mover correlações com alvo e demais
   análises orientadoras da modelagem para o treino após 1.3; ajustar notebook e dependências DVC.
5. Registrar qual análise histórica já acessou dados hoje reservados ao teste e sua consequência.

**Arquivos:** `src/credit_monitoring/eda.py`, `data/loading.py`, notebook e `docs/DATASET.md`.

**Verificação/aceite:** leitura confere com esquema e fonte documentados; resumo contém hash do
bruto e contagens reproduzíveis; falha explícita para arquivo/layout incompatível. A preparação
continua dependente de auditoria do mesmo hash, sem criar ciclo EDA supervisionado → split → EDA.

### 1.3 — Preparação dos dados

**Dependências:** auditoria estrutural de 1.2; regras iniciais do contrato conhecidas.

**Ações do agente:**
1. Revisar limpeza existente, distinguindo preparação histórica de rejeição operacional.
   Preservar ID, demografia e alvo; selecionar as 19 features somente na fronteira do modelo.
2. Registrar união das remoções e motivos sobrepostos: `entrada = saída + removidos únicos`.
   Não somar motivos como registros distintos nem truncar/recodificar valores sem justificativa.
3. Gerar split estratificado 70/15/15 com seed 42; registrar tamanhos reais, taxas e arredondamento.
4. Demonstrar IDs únicos em cada partição, interseções vazias entre as três e cobertura dos
   registros válidos. Confirmar pelo menos 5.000 amostras úteis após limpeza.
5. Gerar referência idêntica ao treino intacto; não aplicar scaler ou outras transformações
   aprendidas antes do split. Associar relatório de preparação a hashes/configuração.

**Arquivos:** `data/prepare.py`, configuração, testes de preparação e estágios DVC.

**Verificação/aceite:** mesma entrada/configuração produz mesmas partições; hash bruto divergente,
razões inválidas ou IDs compartilhados falham. Regras removem apenas o previsto em fixtures
controladas; referência e treino têm igualdade de conteúdo. 1.7 valida os resultados antes do treino.

### 1.7 — Implementação do Data Contract

**Dependências:** esquema e dados de 1.3; deve terminar antes de 1.4/1.5.

**Ações do agente:**
1. Implementar esquema Pandera de dados rotulados e de inferência, com mesma definição das
   features; presença/tipos/nulos explícitos. O alvo binário é obrigatório só no esquema rotulado.
2. Exigir ID único, `LIMIT_BAL > 0`, `18 ≤ AGE ≤ 100` e features obrigatórias sem nulos.
   Não proibir faturas negativas nem códigos de pagamento documentados por conveniência.
3. Validar o lote integral antes de selecionar apenas as entradas do modelo. Não chamar a
   limpeza histórica para descartar linhas de um lote operacional inválido.
4. Integrar validação ao treino e definir função reutilizável para a inferência da fase 2.
   Diagnóstico deve identificar regra/coluna e contagem, sem imprimir registros completos.
5. Definir comportamento de CLI: saída não zero em falha, sem execução do modelo; em sucesso,
   continuar com o lote aceito e registrar a versão do contrato.

**Arquivos propostos:** `src/credit_monitoring/contracts/`, testes do contrato e integração no treino.

**Verificação/aceite:** lote válido passa; perturbações isoladas de duplicidade, limite, idade,
nulo, coluna ausente, tipo incompatível e alvo inválido falham. Testar limites 18/100 aceitos e
17/101 rejeitados; inferência sem alvo passa. Spy/mock de `fit`/predição comprova zero chamadas
em falha. Se várias regras falharem, o lote é contado uma só vez como rejeitado.

### 1.4 — Treinamento da Regressão Logística

**Dependências:** 1.3 e 1.7 aceitos; exploração supervisionada restrita ao treino.

**Ações do agente:**
1. Reutilizar o pipeline `StandardScaler → LogisticRegression` existente e parâmetros versionados.
2. Garantir `fit` de scaler/classificador somente no treino; validação apenas para avaliação.
3. Usar ordem/nome das 19 features e classe positiva 1; registrar seed, parâmetros, versões,
   convergência, tempo e métricas de validação sem carregar o teste no ciclo de desenvolvimento.
4. Tratar avisos de convergência explicitamente; qualquer ajuste usa apenas treino/validação e
   fica no histórico. Não expandir para busca extensa de hiperparâmetros.

**Arquivos:** `models/train.py`, configuração, testes de treino e métricas de validação.

**Verificação/aceite:** contrato precede `fit`; scaler foi ajustado no treino; demografia/ID não
chegam ao estimador; probabilidades são finitas no intervalo [0,1]. Execução de seleção funciona
mesmo sem acesso ao arquivo de teste, comprovando isolamento por comportamento.

### 1.5 — Treinamento do Random Forest

**Dependências:** mesmas entradas/contrato de 1.4; comparabilidade entre os modelos.

**Ações do agente:**
1. Reutilizar `RandomForestClassifier` com parâmetros da configuração: 300 árvores, profundidade
   8 e mínimo de 20 amostras por folha como ponto inicial, não promessa de desempenho.
2. Ajustar apenas no treino e avaliar nas mesmas features/linhas de validação do baseline.
3. Registrar recursos e custo local; se `n_jobs=-1` inviabilizar o ambiente, limitar recursos
   explicitamente e registrar a alteração, sem silenciosamente mudar as condições da comparação.
4. Calcular ROC-AUC, precision, recall, F1, accuracy e matriz de confusão com limiar 0.5.

**Arquivos:** mesmos pontos de treino/configuração e testes usados no baseline.

**Verificação/aceite:** entradas/hashes coincidem com 1.4, contrato é aplicado, métricas são
recalculáveis e somas da matriz correspondem à validação. Não exigir que RF vença o baseline.

### 1.6 — Avaliação, seleção e versionamento do modelo

**Dependências:** 1.4/1.5 e contrato aceitos; acesso remoto de 1.1 para completar M1.

**Ações do agente:**
1. Selecionar pelo maior ROC-AUC de validação, com desempate explicitamente favorecendo baseline,
   sem depender da ordem incidental de um dicionário ou do arredondamento apresentado no relatório.
2. Congelar modelo, features, configuração e limiar 0.5; ajuste de limiar, se necessário, usa
   só validação e precisa ser documentado antes do teste. Persistir decisão e hashes de entrada.
3. Separar comando/estágio de seleção do comando/estágio explícito de avaliação final. Atualizar
   DAG e testes hoje acoplados a `eda → prepare → train`; nunca executar teste a cada treino por padrão.
4. Avaliar o escolhido no teste com protocolo congelado. Registrar hash, métricas e exposição
   histórica; reexecução idêntica por reprodução não cria uma avaliação independente nova.
5. Serializar pipeline completo e metadados. Recarregar artefato confiável, verificar hash e
   comparar predições com a instância anterior à serialização.
6. Atualizar DVC sem rastrear o mesmo arquivo como saída de dois estágios. Sob autorização,
   enviar objetos antes da publicação dos ponteiros Git e recuperar em checkout/cache separado.
   Conferir hashes e inferência do modelo recuperado; não limpar o cache de trabalho para testar.

**Verificação/aceite:** teste não altera a seleção; desempate tem teste controlado; modelo
recarregado preserva probabilidades dentro de tolerância numérica declarada. Recuperação remota
do bruto, preparados, referência e modelo deve funcionar sem depender do cache principal.
Relatório e metadados não descrevem a avaliação como intocada se houve exposição anterior.

## 5. Estratégia de verificação e comandos

Primeiro aproveitar `tests/test_data_preparation.py`, `test_eda.py`, `test_train.py` e
`test_pipeline_definition.py`. Ao mudar a DAG, verificar dependências e comportamento, sem
preservar uma ordem obsoleta apenas para manter um teste verde.

Comandos existentes, executados na raiz e com ambiente disponível:

```bash
uv sync --dev --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run dvc dag
uv run dvc status
git diff --check
```

`uv run dvc repro` existe, mas hoje inclui a avaliação de teste dentro de `train`. Inspecionar
e corrigir o protocolo antes de usá-lo como rotina de desenvolvimento. Os novos pontos de entrada
de seleção/avaliação devem ser implementados, testados e documentados antes de serem usados como
comandos prontos. Não inventar saída de execução quando uv, dados ou acesso estiverem indisponíveis.

## 6. Gate M1 e transferência

M1 exige todos os aceites 1.1–1.7: contrato bloqueante demonstrado, splits auditados, comparação
de modelos, decisão congelada, avaliação rastreável e recuperação remota dos objetos. Sem a
prova remota, relatar prontidão local parcial, mantendo M1 aberto.

Transferir à fase 2: SHA de código e lock, hashes do treino/referência/validação/modelo, features,
versão do contrato, seleção/limiar, exposição do teste, relatório de preparação, comandos válidos
e evidências. Recomenda-se registro textual `docs/evidence/fase-1.md`, com seções 1.1–1.7.

**Primeira ação do agente:** inspecionar ambiente/DVC em 1.1 e abrir o registro do recorte local;
se acesso externo faltar, avançar 1.2 com a fonte existente verificável e registrar a dependência.
