# Fase 1 — Validação de Dados e Contratos

> Plano de execução, revisado em 2026-10-26 após a análise de estado do código. Expande os IDs
> 1.1–1.7; **não atesta implementação**. Os estados citados como "verificado" são observações de
> 2026-10-26 registradas em
> [`reports/analise-estado-fase-1.md`](../../reports/analise-estado-fase-1.md); os demais itens
> continuam sendo trabalho planejado.

> **Status de execução (2026-10-26):** os pacotes 1.1a, 1.1b, 1.2, 1.3, 1.4, 1.5, 1.6 e 1.7
> foram executados no branch `fase-1-bill` e verificados; o registro por ID, com comandos, códigos
> de saída e hashes, está em [`docs/evidence/fase-1.md`](../../docs/evidence/fase-1.md).
> A seção 2.1 abaixo é o **diagnóstico anterior à execução** e permanece como referência
> histórica — não como estado corrente do repositório. Onde os dois registros divergirem, vale
> o registro de evidências, verificado por execução.

- **Plano geral:** [escopo, protocolo e aceites](plano-de-trabalho-TC4.md).
- **Próxima fase:** [Simulação e Detecção de Drift](fase-2-simulacao-deteccao-drift.md).
- **Referências:** [arquitetura](../ARCHITECTURE.md), [checklist](../CHECKLIST.md),
  [dataset](../DATASET.md), [DagsHub](../DAGSHUB.md) e [governança](../GOVERNANCE.md).
- **Diagnóstico de partida:** [análise de estado do código](../../reports/analise-estado-fase-1.md).

## 1. Resultado e fronteiras

Produzir dados auditados, contrato Pandera integrado, comparação de Regressão Logística e
Random Forest, modelo selecionado/congelado e recuperação verificável de dados/modelo via DVC.
Atende à etapa de validação do enunciado; a comparação dos dois algoritmos e o DagsHub são
escolhas internas. Não inclui simulação de drift nem dashboard integrado.

Aplicar o protocolo agêntico da seção 11 do plano geral a cada pacote. A semana 1 é relativa.
Aceites abaixo são observações esperadas para a implementação futura, não resultados obtidos
nesta revisão.

A revisão de 2026-10-26 não muda o escopo da fase. Ela **corrige o diagnóstico inicial** (o plano
anterior partia de um código e de um ambiente não verificados), **acrescenta a peça de aquisição
do bruto**, que não existia, e **desfaz a ambiguidade da ordem de execução**: sem o bruto
recuperado, o caminho local não passa de 1.2.

## 2. Entrada e diagnóstico inicial

### 2.1 Estado verificado em 2026-10-26

Verificado por execução local (uv 0.12.18, Python 3.12.14) e leitura de código:

| Item | Estado verificado |
|---|---|
| Ambiente | `uv sync --dev --locked` funciona (8,2 s); `uv` **não está no PATH padrão** do shell (`~/.local/bin/uv`) |
| Qualidade | `uv run pytest` → **24 passed**; `ruff check` e `ruff format --check` limpos |
| Pipeline | `dvc dag` = `eda → prepare → train`; **reproduz de ponta a ponta em 24 s** (30 s CPU) |
| Relatórios versionados | `reports/metrics.json` e `reports/eda/eda_summary.json` são **reproduzidos byte-a-byte** pelo código atual |
| Split | 21.000/4.500/4.500, seed 42, taxa do alvo 0,2212/0,2211/0,2213; IDs disjuntos por asserção; referência = treino (hash idêntico) |
| Modelos | LR e RF treinados e comparados na validação; RF selecionado (ROC-AUC 0,7741 vs. 0,7145); teste RF ROC-AUC 0,7772 |
| Limpeza | **Removeu 0 linhas** no dado real (nenhuma das cinco regras disparou); caminho exercitado apenas por fixture sintética |
| Bruto | **Ausente** do disco, do cache DVC e de qualquer remote; só existe o XLS original da UCI **versionado no Git** (5,5 MB) |
| Cache/remote DVC | `.dvc/cache` inexistente (`.dvc/` com 8 KB); `.dvc/config` sem remote; `dvc remote list` vazio |
| `dvc.lock` | **Inconsistente** com o código e com os relatórios versionados; `dvc repro` altera 46 linhas do lock |
| Contrato (1.7) | **Inexistente**: nenhum módulo importa `pandera`; o bloco `contract:` da config só é lido como filtro histórico em `prepare.py` |
| Acoplamento do teste | `train` carrega e avalia `test.csv` **a cada execução** (`src/credit_monitoring/models/train.py:133` e `:144`) |
| Desempate | `select_best` usa ordem de dicionário e métricas **já arredondadas** a 6 casas (`train.py:78-80`) |
| EDA | Mistura auditoria estrutural com exploração supervisionada no bruto completo; o resultado está **versionado** em `reports/eda/eda_summary.json` |
| Artefatos | `models/` e `scripts/` contêm apenas `README.md`; `data/processed/` e `data/reference/` estão vazios |
| Dependências | `pandera`, `evidently`, `mlflow`, `streamlit` e `ucimlrepo` declaradas e **não usadas** pelo código |
| CI | `uv sync` → `ruff format --check` → `ruff check` → `pytest` → `uv build`; **não** executa `dvc repro` nem valida o `dvc.lock` |

### 2.2 Lacunas que condicionam a execução

1. **Bruto ausente.** Não há CSV em `data/raw/`, nem no cache, nem no remote. Sem ele, `eda`,
   `prepare` e `train` não rodam e nenhuma evidência nova pode ser produzida.
2. **`dvc.lock` defasado.** Não descreve o código nem os relatórios do repositório; `dvc status`
   nasce sujo e o lock não serve para verificar recuperação de nada.
3. **Proveniência não documentada.** `docs/DATASET.md` não registra hash do bruto, md5 do XLS,
   parâmetros de conversão, DOI nem licença CC BY 4.0.
4. **Contrato ausente.** 1.4, 1.5 e 1.6 dependem de 1.7; sem ele, não há aceite de treino.
5. **Ausência de separação seleção × avaliação.** 1.6 exige comandos/estágios distintos e o
   `test_pipeline_definition.py` fixa hoje o acoplamento que precisa ser desfeito.
6. **DagsHub inacessível.** Sem `dvc[s3]`, sem remote e sem credenciais, o aceite de recuperação
   de 1.1/1.6 e o marco M1 permanecem abertos.

### 2.3 Decisões do executor do plano (não do agente)

Todas as três foram decididas pelo executor do plano em 2026-10-26; a tabela é registro do
diagnóstico, não pendência em aberto.

| Decisão | Impacto se não decidida |
|---|---|
| Autorização de rede e credenciais do DagsHub (owner, endpoint, chave/segredo) | 1.1 e 1.6 ficam sem aceite de recuperação; M1 não fecha |
| Manter ou mover o XLS de 5,5 MB do Git para o DVC | 1.2 fica sem política de proveniência; o repositório mantém um dataset binário no histórico |
| Como registrar a exposição prévia do teste | 1.6 pode declarar avaliação final sem descrever a exposição |

### 2.4 Ordem de execução

```text
1.1a (ambiente + lock + dependências) → 1.2 (aquisição) → 1.3 → 1.7 → 1.4 → 1.5 → 1.6-local
1.1b (remote/acesso + recuperação) ─────────────────────────────────────────────────────────┘ → M1
```

Mudanças em relação ao plano anterior, todas derivadas do diagnóstico:

- **1.2 ganhou a responsabilidade de restaurar o bruto.** O plano anterior pressuponha o CSV
  disponível; o diagnóstico mostrou que ele só existe como XLS no Git. A conversão XLS→CSV é
  verificadamente reproduzível e precisa ser transformada em artefato versionado, não em
  passo manual.
- **1.1 ganhou a regularização do `dvc.lock`.** Um lock inconsistente invalida qualquer
  evidência de versionamento posterior.
- **1.1 e 1.6 se dividem em dois recortes** (local e remoto), porque só o remoto depende de
  autorização externa.

1.4 e 1.5 não dependem dos resultados um do outro, mas compartilham código/configuração; executar
sequencialmente por padrão. Sem acesso remoto, dados/contrato/modelos locais podem avançar, mas
1.1b/1.6 e M1 continuam sem o aceite de recuperação. Projetar o contrato junto a 1.3; validar os
dados preparados antes de qualquer ajuste de modelo.

## 3. Interfaces e artefatos

| Elemento | Contrato para execução |
|---|---|
| Fonte | Bruto imutável, hash SHA-256, URL/DOI/licença, conversão XLS/CSV e parâmetros de leitura |
| Aquisição | Script versionado que reconstrói o CSV a partir do XLS e registra os dois hashes; nenhum passo manual sem registro |
| Dados preparados | `data/processed/{train,validation,test}.csv`, ID preservado, alvo canônico, 19 features e atributos de governança |
| Referência | `data/reference/reference.csv` igual ao treino intacto, inclusive IDs e serialização |
| Contrato | Esquema rotulado e esquema de inferência; retorno de sucesso ou diagnóstico de falha sem dados pessoais |
| Seleção | Métricas de validação dos dois modelos, regra de decisão, limiar e fingerprint da configuração |
| Modelo | `models/credit_model.joblib`, metadados de seleção/versões/hashes, predição reproduzível após carga |
| Avaliação final | Métricas do escolhido no teste e vínculo com a seleção congelada; exposição anterior declarada |
| Versionamento | Ponteiros/`dvc.lock` coerente com o código no Git; objetos aprovados no DagsHub e prova de leitura com cache separado |

Os diretórios `contracts/` dentro de `src/credit_monitoring/` e arquivos de seleção/avaliação
separados são propostas de implementação. Preservar consumidores de `reports/metrics.json`
ou migrá-los e documentar a mudança. Para entradas inválidas, nenhuma predição ou artefato de
sucesso deve ser produzido; não confundir arquivo antigo com resultado da tentativa atual.

**Nota de versionamento:** `reports/metrics.json` está hoje versionado no Git (e declarado como
`metrics` com `cache: false`), enquanto o modelo que o produziu está fora do Git. Antes de
regerar, decidir explicitamente onde vivem métricas e metadados de seleção, para que o resultado
pertença a um artefato recuperável.

## 4. Pacotes executáveis

### 1.1 — Configuração do repositório

**Dependências:** contas, owner/endpoint reais e autorização para conexão/sincronização externa.

**Ações do agente (recorte 1.1a — local):**
1. Conferir branch, CI, `.gitignore`, `pyproject.toml`, `uv.lock` e `.dvc/config`; preservar ajustes locais.
2. Adicionar o extra S3 ao grupo dev via uv e atualizar o lock com a ferramenta, não manualmente:
   `uv add --dev 'dvc[s3]>=3,<4'`. Reavaliar `ucimlrepo`, `evidently`, `mlflow` e `streamlit`
   como dependências de fases futuras: mantê-las declaradas sem uso amplia a superfície do
   ambiente e confunde "instalado" com "implementado".
3. Executar instalação travada e testes existentes antes de atribuir falhas à nova mudança.
4. **Regularizar o `dvc.lock`:** com o bruto restaurado (1.2), rodar `dvc repro` e versionar o
   lock resultante, de modo que `uv run dvc status` fique limpo e o lock descreva artefatos que
   o repositório de fato contém. Registrar a divergência histórica em `docs/evidence/fase-1.md`.
5. Introduzir a dependência de leitura de `.xls` necessária à conversão (xlrd) como dependência
   declarada e travada, não como instalação ad hoc.

**Ações do agente (recorte 1.1b — remoto):**
6. Seguir o guia DagsHub para conexão/configuração autorizada. Credenciais só em configuração
   local ignorada; endpoint/owner não devem ser adivinhados nem tokens copiados ao registro.
7. Definir com a equipe o acesso de leitura e quais saídas DVC podem ser compartilhadas;
   preparar recuperação isolada a ser concluída em 1.6 quando existirem os objetos finais.

**Decisão de equipe:** manter ou mover o XLS de 5,5 MB do Git para o DVC. Enquanto a decisão não
existe, **não remover o XLS do Git** — ele é a única cópia local da fonte.

**Arquivos:** `pyproject.toml`, `uv.lock`, `dvc.lock`, configuração DVC compartilhável e guia DagsHub.

**Verificação/aceite:** `uv sync --dev --locked` funciona; suporte S3 carregável; configuração
aponta ao repositório correto sem segredos no diff; `uv run dvc status` sem estágios modificados
após a regularização. Registrar recuperação do bruto quando autorizada e completar a prova dos
artefatos finais em 1.6. Sem uv/acesso, registrar o bloqueio.

### 1.2 — Aquisição e auditoria do dataset

**Dependências:** ambiente local de 1.1a; origem do arquivo identificável.

**Ações do agente:**
1. **Restaurar o bruto.** O CSV bruto (`data/raw/default_of_credit_card_clients.csv`) não existe
   no disco, no cache DVC nem em remote. Duas vias, na ordem de preferência:
   a. *via remote*, quando 1.1b estiver autorizada e o objeto existir no DagsHub;
   b. *via conversão do XLS* já versionado no Git. A conversão é verificadamente reproduzível:
   ler a planilha `Data` do `data/default of credit card clients.xls` com `header=1`, gravar
   `sep=";"`, `index=False`, `lineterminator="\r\n"`, prefixados pela linha `X1..X23;Y` e BOM
   UTF-8. O resultado tem `sha256 = 1fc7fe04822413cf48d0f5ca974cbe47061b21ea10fa1d114bb56b8feac79358`
   e `md5 = a6ee086d1eafba5566f666b3ff2ed2c9`, **idênticos** ao hash do ponteiro `.dvc` e ao
   registrado em `reports/eda/eda_summary.json`. Qualquer divergência de hash invalida a via.
2. **Versionar a aquisição.** O passo de conversão deixa de ser manual e passa a ser um script
   versionado em `scripts/` (ou em `src/credit_monitoring/data/`), que registre o md5 do XLS, o
   hash do CSV resultante e os parâmetros de leitura. Um CSV reobtido sem script é um CSV sem
   proveniência.
3. Verificar procedência UCI 350, licença/atribuição, DOI e arquivo original; registrar
   **CC BY 4.0**, o DOI e a atribuição exigidos pelo plano geral. Se a conversão não puder ser
   comprovada, registrar a lacuna em vez de omiti-la.
4. Conferir separador `;`, segunda linha como cabeçalho na configuração atual, nomes e unidades NT$;
   não assumir que outro download terá o mesmo layout. Hash identifica a versão efetivamente lida.
5. Auditar contagens, tipos, nulos, IDs duplicados e códigos; preservar bruto e emitir resumo agregado.
6. **Registrar a exposição prévia do teste.** O EDA atual calcula correlações com o alvo e taxa de
   default por grupo demográfico no bruto completo de 30.000 linhas, e o resultado está versionado
   em `reports/eda/eda_summary.json`. Separar auditoria estrutural (bruto) de exploração
   supervisionada (treino, após 1.3) e **declarar formalmente** a exposição: data, variáveis,
   arquivo e consequência. Mover as análises orientadoras de modelagem para o treino, ajustando o
   notebook e as dependências DVC; manter a exploração já feita apenas como registro histórico
   marcado como contaminante.
7. Declarar, no registro da fase, qual análise histórica acessou dados hoje reservados ao teste
   e qual decisão isso afeta. Não é preciso (nem possível) apagar o histórico; é preciso descrevê-lo.

**Arquivos:** `src/credit_monitoring/eda.py`, `data/loading.py`, script de aquisição,
`notebooks/01_eda.ipynb` e `docs/DATASET.md`.

**Verificação/aceite:** leitura confere com esquema e fonte documentados; resumo contém hash do
bruto e contagens reproduzíveis; falha explícita para arquivo/layout incompatível; `docs/DATASET.md`
passa a conter hash do bruto, hash do XLS, parâmetros de leitura/conversão, DOI e licença. A
preparação continua dependente de auditoria do mesmo hash, sem criar ciclo EDA supervisionado →
split → EDA.

### 1.3 — Preparação dos dados

**Dependências:** auditoria estrutural de 1.2; regras iniciais do contrato conhecidas.

**Ações do agente:**
1. Revisar limpeza existente, distinguindo preparação histórica de rejeição operacional.
   Preservar ID, demografia e alvo; selecionar as 19 features somente na fronteira do modelo.
2. Registrar união das remoções e motivos sobrepostos: `entrada = saída + removidos únicos`.
   Não somar motivos como registros distintos nem truncar/recodificar valores sem justificativa.
   **Registrar explicitamente que, no dado real, a remoção foi de 0 linhas** e que o caminho de
   remoção é coberto por fixture controlada (não pelo dado de produção) — ausência de remoção não
   é ausência de verificação.
3. Gerar split estratificado 70/15/15 com seed 42; registrar tamanhos reais, taxas e arredondamento.
4. Demonstrar IDs únicos em cada partição, interseções vazias entre as três e cobertura dos
   registros válidos. Confirmar pelo menos 5.000 amostras úteis após limpeza.
5. Gerar referência idêntica ao treino intacto; não aplicar scaler ou outras transformações
   aprendidas antes do split. Associar relatório de preparação a hashes/configuração.

**Arquivos:** `data/prepare.py`, configuração, testes de preparação e estágios DVC.

**Verificação/aceite:** mesma entrada/configuração produz mesmas partições; hash bruto divergente,
razões inválidas ou IDs compartilhados falham. Regras removem apenas o previsto em fixtures
controladas; referência e treino têm igualdade de conteúdo (verificada por hash e por teste). 1.7
valida os resultados antes do treino.

### 1.7 — Implementação do Data Contract

**Dependências:** esquema e dados de 1.3; deve terminar antes de 1.4/1.5.

**Ações do agente:**
1. Implementar esquema Pandera de dados rotulados e de inferência, com mesma definição das
   features; presença/tipos/nulos explícitos. O alvo binário é obrigatório só no esquema rotulado.
   Reutilizar o bloco `contract:` de `configs/project.yaml` como fonte única das regras, hoje
   consumido apenas como filtro histórico.
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

### 1.6 — Avaliação, seleção e versionamento

**Dependências:** 1.4/1.5 e contrato aceitos; acesso remoto de 1.1b para completar M1.

**Ações do agente:**
1. Selecionar pelo maior ROC-AUC de validação, com desempate explicitamente favorecendo baseline,
   **sem depender da ordem incidental de um dicionário nem do arredondamento apresentado no
   relatório**. Hoje `select_best` resolve o empate pela ordem de `modeling.candidates` e
   compara métricas arredondadas a 6 casas; a regra deve ser explícita e aplicada sobre valores
   não arredondados, preservando o resultado atual (RF selecionado) como verificação de não
   regressão.
2. Congelar modelo, features, configuração e limiar 0.5; ajuste de limiar, se necessário, usa
   só validação e precisa ser documentado antes do teste. Persistir decisão e hashes de entrada.
3. **Separar comando/estágio de seleção do comando/estágio explícito de avaliação final.**
   Atualizar o DAG e os testes hoje acoplados a `eda → prepare → train` — em particular
   `tests/test_pipeline_definition.py`, que exige `test.csv` como dependência do estágio `train`;
   a revisão do teste é parte do trabalho, não uma concessão para manter uma ordem obsoleta.
   Nunca executar teste a cada treino por padrão.
4. Avaliar o escolhido no teste com protocolo congelado. Registrar hash, métricas e exposição
   histórica; reexecução idêntica por reprodução não cria uma avaliação independente nova.
5. Serializar pipeline completo e metadados. Recarregar artefato confiável, verificar hash e
   comparar predições com a instância anterior à serialização.
6. Atualizar DVC sem rastrear o mesmo arquivo como saída de dois estágios. Sob autorização,
   enviar objetos antes da publicação dos ponteiros Git e recuperar em checkout/cache separado.
   Conferir hashes e inferência do modelo recuperado; não limpar o cache de trabalho para testar.
7. **Completar os metadados**, que hoje não registram: limiar, hash do próprio modelo, SHA do Git,
   versão do contrato, exposição do teste declarada e ambiente completo (Python, scikit-learn,
   pandas).

**Verificação/aceite:** teste não altera a seleção; desempate tem teste controlado; modelo
recarregado preserva probabilidades dentro de tolerância numérica declarada. Recuperação remota
do bruto, preparados, referência e modelo deve funcionar sem depender do cache principal.
Relatório e metadados não descrevem a avaliação como intocada se houve exposição anterior.

## 5. Estratégia de verificação e comandos

Linha de base verificada em 2026-10-26: 24 testes passando, lint limpo, pipeline completo em 24 s.
Tratar essa linha de base como referência — qualquer regressão deve ser atribuída à mudança em
curso, não ao estado anterior.

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

Comandos adicionais previstos para esta fase:

```bash
uv run dvc repro          # após restaurar o bruto; deve terminar sem avaliar o teste
uv run dvc status         # deve indicar ausência de estágios modificados
uv run dvc push -r dagshub # somente após autorização e após versionar os ponteiros
uv run dvc pull -r dagshub # em checkout/cache separado, como prova de recuperação
```

## 6. Gate M1 e transferência

M1 exige todos os aceites 1.1–1.7: contrato bloqueante demonstrado, splits auditados, comparação
de modelos, decisão congelada, avaliação rastreável e recuperação remota dos objetos. Sem a
prova remota, reportar prontidão local parcial, mantendo M1 aberto.

Checklist do gate, a ser verificado item a item antes de propor M1 como concluído:

- [ ] Bruto recuperado com hash conferido e script de aquisição versionado; proveniência
      (hash XLS, hash CSV, DOI, licença CC BY 4.0) em `docs/DATASET.md`.
- [ ] `uv run dvc status` sem estágios modificados; `dvc.lock` coerente com o código.
- [ ] Contrato Pandera integrado antes do `fit`: lote válido aceito, 7 perturbações isoladas
      rejeitadas, zero chamadas ao estimador em falha.
- [ ] Split 70/15/15 auditado (tamanhos, taxas, seed, IDs disjuntos) e referência = treino por hash.
- [ ] Dois modelos comparados na validação; regra de desempate explícita e testada.
- [ ] Seleção e avaliação final em comandos/estágios separados; o ciclo de treino não avalia o teste.
- [ ] Modelo recarregado com probabilidades equivalentes dentro de tolerância declarada.
- [ ] Metadados completos: limiar, features, seed, hashes de dados/modelo, SHA Git, versões,
      versão do contrato, exposição do teste declarada.
- [ ] Objetos DVC no DagsHub e recuperação em checkout/cache separado, com hashes conferidos e
      inferência do modelo recuperado.
- [ ] `docs/evidence/fase-1.md` com seções 1.1–1.7, comandos, códigos de saída e hashes.

Transferir à fase 2: SHA de código e lock, hashes do treino/referência/validação/modelo, features,
versão do contrato, seleção/limiar, exposição do teste, relatório de preparação, comandos válidos
e evidências. Recomenda-se registro textual `docs/evidence/fase-1.md`, com seções 1.1–1.7.

**Primeira ação do agente:** 1.1a — inspecionar ambiente, adicionar `dvc[s3]` e a dependência de
leitura de `.xls`, regularizar o `dvc.lock` e abrir o registro do recorte local. Em seguida, 1.2
para restaurar o bruto; se o acesso externo faltar, seguir pela conversão do XLS versionado e
registrar a dependência pendente para 1.1b.

> **Cumprida em 2026-10-26** (1.1a, 1.2 e 1.1b). O checklist do gate acima permanece aqui como
> especificação; a verificação item a item, com os comandos executados e os hashes conferidos,
> está em [`docs/evidence/fase-1.md`](../../docs/evidence/fase-1.md) ("Checklist do gate M1").
