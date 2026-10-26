# Fase 2 — Simulação e Detecção de Drift

> Plano de execução, revisado em 2026-10-26. Expande os IDs 2.1–2.7; não atesta implementação.

- **Plano geral:** [escopo, protocolo e aceites](plano-de-trabalho-TC4.md).
- **Entrada:** [fase 1](fase-1-validacao-dados-contratos.md), marco M1.
- **Próxima fase:** [Observabilidade](fase-3-observabilidade-pipelines-modelos.md).
- **Referências:** [arquitetura](../ARCHITECTURE.md), [checklist](../CHECKLIST.md) e
[convenção de produção](../../data/production/README.md).

## 1. Resultado e pergunta experimental

Demonstrar que alterações reproduzíveis em `LIMIT_BAL` e `PAY_AMT1`, em um lote válido, são
detectadas frente à referência de treino. Gerar HTML Evidently com controle original,
estatísticas, métodos, limiares e limites de interpretação. A previsão usa o modelo congelado;
esta fase não reabre seleção, hiperparâmetros ou avaliação de teste.

**Hipótese operacional:** sob o protocolo fixado em 2.2, ambas as features alteradas serão
identificadas com drift em comparação à referência. Resultado de controle mede a diferença já
existente entre treino e validação; não é uma garantia de zero alertas.

**O que sustenta o aceite:** as duas features sinalizam conforme o protocolo, os lotes passam
pelo contrato, e efeitos/estatísticas são rastreáveis ao controle e à intervenção.
**O que enfraquece ou impede:** falta de detecção de uma feature, lote inválido, alteração não
planejada de outras colunas, método oculto ou alertas indistinguíveis do controle sem explicação.
Preservar resultado negativo e revisar o desenho com histórico; não ajustar parâmetros em silêncio.

## 2. Entrada e ordem de execução

Conferir M1, SHA/lock, hashes da referência/validação/modelo, versão do contrato, features e
limiar. Confirmar que a seleção terminou e que os IDs de validação não pertencem ao treino.
Na ausência de M1, desenvolver apenas funções/testes locais com fixtures; isso não completa M2.

```text
M1 → 2.1 → 2.2 → 2.3 → 2.4 ──┐
               └──→ 2.5 ─────┴→ 2.6 → 2.7 → M2
```

2.5 pode ser desenvolvido com fixtures após fixar o método em 2.2. Comparações de distribuição
não dependem matematicamente das predições, mas o aceite integrado requer contrato/inferência
e a distribuição das probabilidades. Executar os pacotes sequencialmente por padrão.

### Cobertura de Concept Drift

O contexto do enunciado cita Concept Drift, mas a rubrica detalha Data Drift. Levar à docência
uma pergunta objetiva: a alteração marginal de duas features atende à demonstração exigida, ou
é necessário cenário separado de mudança de `P(y|X)`? Registrar resposta, data e consequência
em 2.2, sem atribuir à docência uma decisão ainda não recebida.

Enquanto isso, implementar Data Drift localmente. Sem resolução da cobertura, não declarar
cumprimento integral da etapa/enunciado. Se exigido, detalhar recorte de 2.2/2.3 com mecanismo
gerador, controle, sementes e rótulos explicitamente sintéticos, avaliação independente e
evidências próprias. Não alterar rótulos reais nem apresentar testes marginais como detector
de Concept Drift; esse recorte exige revisão do plano antes de execução de aceite.

## 3. Interfaces e artefatos propostos

| Artefato | Conteúdo e invariante |
|---|---|
| `data/reference/reference.csv` | Referência imutável da fase 1; remover alvo/ID/demografia apenas da visão estatística |
| `data/production/original.csv` | Validação sem alvo, preservando ID e atributos de contrato/governança |
| `data/production/modified.csv` | Cópia do original; só `LIMIT_BAL` e `PAY_AMT1` modificadas |
| Manifesto de simulação | Versão do cenário, origem/hashes, seed 42, transformações, contagens, métodos e limiares |
| Predições por cenário | ID técnico, probabilidade e classe, hash do modelo/entrada, limiar; objeto local/DVC autorizado |
| Resultados de drift | Registro estruturado por comparação/feature e resumo; sem rótulos exigidos |
| `reports/drift/` | HTML Evidently e interpretação agregada do controle e do cenário alterado |

Os nomes de arquivos novos são propostas, não comandos/artefatos já disponíveis. Implementar em
`src/credit_monitoring/data/` (simulação), `models/` (inferência) e `monitoring/` (drift), usando
uma configuração versionada. Metadados podem acompanhar as saídas DVC. Arquivos DVC novos não
devem disputar propriedade com saídas de estágios existentes.

Fixar schema de resultados para consumo da fase 3: `scenario_id`, hashes, versão do protocolo,
feature, método, estatística/efeito, limiar, indicador de drift e contagens. Se houver p-value,
usar campo separado com correção identificada; não chamar qualquer score de probabilidade.

## 4. Pacotes executáveis

### 2.1 — Definição dos datasets de referência e produção

**Dependências:** M1 e seleção congelada.

**Ações do agente:**
1. Verificar hashes da referência e validação entregues; falhar em versão divergente.
2. Copiar validação para produção original sem o alvo canônico, mantendo ID e demografia.
   Não extrair registros do teste ou criar nova divisão para melhorar os resultados.
3. Demonstrar IDs únicos, nenhuma interseção referência/produção e correspondência entre
   produção e a validação de origem. Documentar que a validação já participou da seleção.
4. Registrar esquema, tamanhos, seed da origem e hashes antes de qualquer transformação.

**Verificação/aceite:** referência permanece igual ao treino; produção não contém alvo;
IDs/valores das colunas preservadas correspondem à validação. Testes com ID compartilhado,
alvo indevido ou hash incompatível bloqueiam a construção do cenário de aceite.

### 2.2 — Definição do cenário de drift

**Dependências:** 2.1; decisão de cobertura com a docência para aceite integral.

**Ações do agente:**
1. Escrever protocolo versionado antes de observar comparações de aceite: features, direção,
   intensidade, arredondamento, zeros, seed, método por feature e regra global de alerta.
2. Como proposta inicial de transformação, multiplicar `LIMIT_BAL` por 1.5 e `PAY_AMT1` por 0.5,
   arredondando valores monetários para inteiros e preservando os zeros de pagamentos. Documentar
   que reduzir pagamentos nulos continua nulo e que a intervenção não representa passagem real de tempo.
3. Como proposta inicial de método, usar **PSI como medida de efeito** nas 19 features financeiras,
   com limiar por feature `0.20`, e alerta global quando ao menos uma feature ultrapassar o
   limiar. Esses números são escolhas de desenho a revisar/registrar, não exigências oficiais
   nem limiares universalmente válidos. As duas features-alvo devem sinalizar para o aceite.
4. Definir bins só na referência: até 10 faixas por quantis, bordas repetidas colapsadas,
   extremos abertos para valores fora da faixa e suavização positiva normalizada explícita
   (proposta `1e-6`). Documentar tratamento de feature constante e de massa em zero; se necessário,
   separar zero e calcular faixas positivas. Não recalcular bins com a produção.
5. Verificar se a API Evidently travada permite esse protocolo. Se precisar de teste customizado,
   integrar uma única implementação ao relatório e ao JSON, com teste numérico independente;
   se for adotado método nativo diferente, revisar/registrar o protocolo antes do aceite.
6. Explicitar que `drift.alpha=0.05` não é limiar PSI. Se a equipe optar por KS/p-values, fixar
   família de testes, correção (por exemplo Holm), adequação a empates/discretização e regra
   de agregação; não misturar decisões PSI e p-value sob um único nome `alpha`.
7. Registrar pergunta/resposta sobre Concept Drift e estimativa de impacto caso haja ampliação.

**Verificação/aceite:** configuração sem parâmetros estatísticos ambíguos; cenário e protocolo
possuem versão/hash registrados antes dos resultados. Ensaio exploratório pode motivar nova
versão, mas deve ficar distinguido da execução de aceite. Manter controle e resultados prévios.

### 2.3 — Script de simulação

**Dependências:** 2.1/2.2, contrato disponível.

**Ações do agente:**
1. Implementar transformação pura sobre uma cópia; entrada/hash esperados e destinos explícitos.
2. Preservar ordem, tamanho e IDs entre original/modificada; modificar somente as duas features.
3. Validar o lote gerado, tipos e finitude; transformação não pode tornar limite não positivo.
4. Gravar manifesto e saídas em versão própria; ao retomar, conferir compatibilidade antes de
   reutilizar. Não sobrescrever a validação nem a referência ou corrigir lote inválido silenciosamente.
5. Declarar parâmetros/dependências/saídas na DAG e rastrear objetos aprovados por DVC.
   Publicação remota segue autorização e sequência de objetos antes dos ponteiros.

**Verificação/aceite:** mesma entrada/protocolo gera mesmos valores/hashes; fixtures com zeros,
caudas, arredondamento e limite baixo permanecem válidas. Comparação coluna a coluna comprova
igualdade em tudo que não era alvo da intervenção; fonte continua inalterada após a execução.

### 2.4 — Inferência sobre dados de produção

**Dependências:** 2.3 e modelo/contrato de M1.

**Ações do agente:**
1. Carregar modelo confiável pelo hash esperado; validar lote completo antes da predição.
2. Selecionar exatamente as 19 features na ordem registrada, mantendo ID só para alinhamento.
3. Emitir probabilidades/classes pelo limiar congelado e metadados por cenário. Não usar alvo
   ou demografia para gerar previsões e não calcular suposta acurácia usando rótulos antigos
   associados a features artificialmente alteradas.
4. Produzir resumo agregado das distribuições de probabilidades do original e modificado.
5. Falhar com diagnóstico quando contrato/modelo/schema forem incompatíveis; sem artefato de sucesso.

**Verificação/aceite:** uma previsão por ID, probabilidades finitas em [0,1], classes consistentes
com o limiar e ordem estável. Lote inválido gera saída de falha e zero chamadas ao estimador.
Resultados não podem ser confundidos com predições de uma execução anterior.

### 2.5 — Integração com Evidently

**Dependências:** protocolo 2.2; 2.3 para uso dos lotes reais.

**Ações do agente:**
1. Inspecionar API da versão efetivamente travada de Evidently; não copiar exemplos de outra
   versão sem validar imports, tipos e geração/exportação do relatório.
2. Criar adaptador que recebe referência, lote e configuração, com mapeamento das 19 features
   financeiras. Excluir ID, alvo e atributos de governança das contagens de drift financeiro.
3. Tornar método, bins, limiares e regra global explícitos; não depender de escolha automática
   não registrada. Integrar o método decidido em 2.2 e exportar resultado estruturado estável.
4. Manter análise de distribuição das probabilidades separada da contagem das 19 features.
5. Associar cada relatório à comparação, versão do protocolo, bibliotecas e hashes reais.

**Verificação/aceite:** fixture idêntica tem efeito nulo conforme tolerância declarada;
fixture com mudança conhecida sinaliza; coluna fora do schema e entrada vazia não geram
relatório de sucesso enganoso. Teste numérico confirma score/limiar/flag, inclusive borda exata
da regra de comparação escolhida; HTML e JSON têm o mesmo resultado.

### 2.6 — Detecção estatística de drift

**Dependências:** 2.3/2.4/2.5 e protocolo congelado.

**Ações do agente:**
1. Executar referência × original e referência × modificada com o mesmo protocolo/bins.
2. Registrar por feature método, score, limiar, flag, magnitude/resumos e tamanhos dos lotes;
   p-values ajustados só se o protocolo realmente os calcular.
3. Comparar também original × modificada por resumos/distribuições para descrever a intervenção;
   não substituir com isso a comparação obrigatória contra a referência.
4. Relatar todos os alertas do controle e de features não alteradas. Se método e entradas por
   feature são idênticos, alterações em resultados de colunas intactas pedem investigação.
5. Verificar a hipótese das duas features-alvo e registrar resultado antes de qualquer revisão.
   Não trocar seed, intensidade ou limiar na mesma versão para forçar uma detecção.

**Verificação/aceite:** resultados de todas as features disponíveis e as duas alteradas
detectadas sob critérios pré-definidos. Se não detectar ambas, marcar experimento insuficiente
para o aceite, preservar evidência e propor nova versão de 2.2/2.3. Modelo permanece congelado.

### 2.7 — Relatório de drift

**Dependências:** resultados íntegros de 2.6 e inferência de 2.4.

**Ações do agente:**
1. Exportar HTML Evidently identificável para cada comparação, ou relatório conjunto que
   preserve separadamente controle e modificado, junto ao resultado estruturado consumido na fase 3.
2. Incluir tabela interpretativa: feature, mudança aplicada, método, efeito/estatística,
   limiar, flag do controle/modificado e limitação. Apresentar probabilidades previstas agregadas.
3. Registrar origem, hashes, seed, configuração/versões e decisão de cobertura de Concept Drift.
4. Inspecionar HTML para linhas de dados/IDs, caminhos privados e conteúdo inadequado para
   compartilhamento. Armazenar só objetos autorizados no DVC, mantendo resumo agregado no Git.
5. Documentar comando de reprodução implementado e abri-lo em navegador para conferir legibilidade.

**Verificação/aceite:** HTML abre e corresponde ao JSON/manifestos; duas features-alvo e controle
estão claros. Texto não afirma causalidade econômica, Concept Drift ou perda real de desempenho
com base apenas nas features alteradas. Resultados negativos não são omitidos.

## 5. Verificação e execução reproduzível

Implementar CLI dos novos módulos antes de publicar comandos de simulação, inferência e drift.
Documentar argumentos, entrada/saída, retorno em falha e como executar um cenário específico.
Evitar um único comando que refaça treino/avaliação final para produzir um relatório.

Após implementar os estágios, `uv run dvc dag` deve mostrar dependências de dados, modelo,
contrato, protocolo e código. Não usar efeitos colaterais MLflow como saídas de um estágio
cacheável. Verificar invalidação: mudar cenário invalida simulação/inferência/relatórios,
mas não o modelo congelado; mudar referência/protocolo invalida comparações dependentes.

Executar testes de invariantes/estatística/integração e depois `uv run pytest`, `uv run ruff check .`,
`uv run ruff format --check .` e `git diff --check` quando houver código. Evidências devem citar
comandos reais e versões. O plano não implica que essas operações já estejam implementadas.

## 6. Gate M2 e transferência

M2 exige M1, contratos/inferência nos lotes, protocolo anterior à execução, detecção das duas
features, HTML com controle e hashes/versões rastreáveis. Registrar a decisão da docência para
declarar cobertura integral. Uma implementação parcial pode ser integrada em desenvolvimento
com limitações explícitas, mas não equivale ao marco aceito.

Transferir à fase 3: lotes e manifesto, modelo/contrato imutáveis, predições, JSON/HTML por
comparação, configuração de alertas e comandos válidos, inclusive como rejeitar um lote inválido.
Recomenda-se registro textual `docs/evidence/fase-2.md`, com seções 2.1–2.7 e histórico experimental.

**Primeira ação do agente:** validar o pacote M1 e os hashes de entrada em 2.1; abrir a decisão
de protocolo/cobertura em 2.2 antes de rodar qualquer comparação de aceite.
