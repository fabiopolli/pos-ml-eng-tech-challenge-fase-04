# Governança, privacidade e causalidade

> Documento da fase 4 (IDs 4.1–4.4). Descreve o que foi **efetivamente observado** neste
> repositório e rotula o restante como **proposta** (cenário hipotético de fintech) ou
> **pendente** (depende de decisão humana). Não é parecer jurídico, não declara conformidade
> com a LGPD, não declara ausência de viés e não atesta aptidão do modelo para conceder crédito.
> Evidências e comandos: [`docs/evidence/fase-4.md`](evidence/fase-4.md).

**Legenda:** `Realizado` = verificado no repositório; `Proposta` = desenho para a fintech
hipotética, sem operação real; `Pendente` = precisa de decisão/confirmação humana.

## 1. Origem e finalidade (4.1)

- **Dataset:** UCI *Default of Credit Card Clients* (ID 350), 30.000 clientes de cartão de crédito
  em Taiwan (2005), valores em NT$. Proveniência, hashes e conversão XLS→CSV em
  [`docs/DATASET.md`](DATASET.md).
- **Licença:** CC BY 4.0. A atribuição e a descrição das transformações são preservadas. Fonte
  consultada em 2026-10-26: [UCI 350](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients),
  DOI [10.24432/C55S3H](https://doi.org/10.24432/C55S3H). A licença autoriza reutilização do
  dado; **não é base legal** nem autorização para tratar dados de clientes reais.
- **Finalidade (Realizado):** acadêmica — estudar risco de inadimplência e monitoramento de
  degradação. O sistema **não toma decisões reais de crédito**.
- **Limite de transferência:** os dados são de Taiwan/2005; não presumir validade para outro
  país, período ou política de crédito.
- **Reidentificação:** ser um dataset público não elimina o risco de reidentificação. Não se
  presume anonimização apenas porque não há nome ou documento.

### 1.1 Fluxo de tratamento (Realizado)

```text
UCI 350 (XLS) -> aquisição (hash conferido) -> CSV bruto -> auditoria estrutural
  -> limpeza/contrato + split 70/15/15 (seed 42) -> referência = treino
  -> treino/seleção -> modelo congelado -> avaliação final (estágio separado)
  -> produção simulada (original e modificada) -> inferência -> drift -> observabilidade
```

Partições: treino 21.000, validação 4.500, teste 4.500 (taxa de inadimplência ≈ 22,1% em cada
uma). A preparação não removeu linhas (30.000 de entrada, 30.000 de saída). Os dados de
**referência** (cópia do treino) e de **produção simulada** ficam em diretórios separados.

### 1.2 Variáveis pessoais e minimização

| Grupo | Variáveis | Uso no modelo | Observação |
|---|---|---|---|
| Identificador técnico | `ID` | Não | Número de linha do dataset; **não** é identidade civil. Só é usado para checar unicidade e alinhar predições. |
| Demográficas (governança) | `SEX`, `EDUCATION`, `MARRIAGE`, `AGE` | **Não** | Dados pessoais. Ficam fora da predição e são usadas apenas em análises agregadas de qualidade e viés. |
| Financeiras | `LIMIT_BAL`, `PAY_0`, `PAY_2`–`PAY_6`, `BILL_AMT1`–`6`, `PAY_AMT1`–`6` | Sim (19 features) | Dados pessoais financeiros em tese; no dataset estão sem nome ou documento. |
| Alvo | `default_payment_next_month` | Rótulo (só em treino/validação/teste) | Ausente nos lotes de produção simulados. |

- **Categorias sensíveis (LGPD art. 5º, II):** origem racial/étnica, convicção religiosa, opinião
  política, filiação sindical/religiosa/política, saúde, vida sexual, dado genético ou
  biométrico. O dataset **não contém** essas variáveis. Sexo, escolaridade, estado civil e idade
  são dados pessoais, mas não constam dessa lista legal.
- **Justificativa de exclusão da demografia do modelo:** minimização e redução do risco de
  discriminação direta. Isso **não elimina proxies** (por exemplo, limite de crédito ou padrão de
  pagamento podem se correlacionar com idade ou escolaridade) nem garante ausência de viés
  (ver §3.2).
- **Saídas e demonstração:** relatórios, métricas, relatório de viés, capturas e vídeo devem
  conter apenas agregados. O relatório de viés é validado por teste para não conter `ID`. As
  fixtures de [`data/test/`](../data/test/) são derivadas do treino, com IDs novos (~60 KB).

### 1.3 Inventário por artefato (Realizado)

| Artefato | Local | Versionamento | Cópias / destinatários |
|---|---|---|---|
| Workbook original `.xls` | `data/default of credit card clients.xls` | DVC + remote DagsHub (fora do Git) | Cache DVC local de cada integrante; remote |
| CSV bruto | `data/raw/` | DVC | Idem |
| `train`/`validation`/`test.csv`, `preparation_report.json` | `data/processed/` | DVC | Idem |
| Referência (`reference.csv`) | `data/reference/` | DVC | Idem |
| Lotes de produção simulados `v1.0.1`, `v1.0.2` (manifesto, predições) | `data/production/` | DVC | Idem |
| Modelo congelado e candidatos | `models/` | DVC (`.joblib` ignorado pelo Git) | Idem |
| Métricas de seleção e teste, auditorias, otimização, resultados de drift (JSON) | `reports/` | **Git** (JSON pequeno, agregado e canônico) | Repositório GitHub |
| Relatório de viés agregado | `reports/bias/validation_bias.json` | **Git** (agregado, sem linhas) | Repositório GitHub |
| HTML de drift pt-BR v6 | `reports/drift/` | Git + objeto no DagsHub | Repositório; remote |
| Figuras | `reports/figures/` | DVC (parcial) | Cache e remote |
| Fixtures do laboratório | `data/test/` | **Git** (exceção documentada) | Repositório |
| Banco e artefatos MLflow, logs de execução, recursos | `mlflow.db`, `mlruns/`, `observability/`, `*.log` | **Fora do Git** (ignorados) | Somente local |
| Credenciais | `.env`, `.dvc/config.local` | **Fora do Git** (ignorados) | Somente local |
| Evidências textuais | `docs/evidence/` | Git | Repositório |
| Vídeo STAR | Link externo | Fora do Git | A definir pelo responsável pela gravação |

Conferido contra `.gitignore`, `dvc.yaml` e `git ls-files` em 2026-11-14. Nenhum binário de
dados ou modelo está no Git.

## 2. Plano de privacidade e LGPD (4.2)

### 2.1 Uso acadêmico × cenário hipotético

| Aspecto | Uso acadêmico (Realizado) | Fintech hipotética (Proposta) |
|---|---|---|
| Dados | Dataset público, CC BY 4.0, de terceiros | Dados reais de clientes da própria instituição |
| Finalidade | Estudo de monitoramento de modelos | Apoio à análise de risco de crédito |
| Decisão sobre pessoas | Nenhuma | Qualquer uso em crédito exigiria base legal, avaliação de impacto e supervisão humana |
| Base legal | Não se aplica (dado público, sem decisão sobre titulares) | Ver §2.2 |

### 2.2 Base legal proposta (Proposta — revisão jurídica pendente)

Para o cenário hipotético, hipóteses a submeter à revisão do encarregado/jurídico, **sem
afirmar que estejam validadas**:

- **Proteção do crédito** (LGPD art. 7º, X) como hipótese principal para análise de risco de
  inadimplência;
- **execução de contrato** (art. 7º, V) para dados necessários ao contrato com o titular, quando
  aplicável;
- **cumprimento de obrigação legal ou regulatória** (art. 7º, II) para exigências de órgãos
  reguladores, quando aplicável.

Princípios do art. 6º a observar: finalidade, adequação, necessidade, livre acesso, qualidade,
transparência, segurança, prevenção, **não discriminação** e responsabilização.

Referências oficiais: [Lei 13.709/2018 (Planalto)](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
e [texto na Câmara dos Deputados](https://www2.camara.leg.br/legin/fed/lei/2018/lei-13709-14-agosto-2018-787077-publicacaooriginal-156212-pl.html).
Consulta de 2026-11-14: apenas o art. 20 foi confirmado (portal da Câmara); o portal do
Planalto estava inacessível. **Pendente:** conferir os demais artigos citados no texto
atualizado e consultar as orientações da [ANPD](https://www.gov.br/anpd/pt-br) sobre decisões
automatizadas e proteção do crédito.

### 2.3 Transparência, contestação e supervisão (Proposta)

- **Transparência:** informar o titular sobre finalidade, critérios gerais e fatores relevantes
  da análise. O protótipo **não** implementa essa comunicação.
- **Contestação:** o titular pode solicitar a revisão de decisões tomadas unicamente com base em
  tratamento automatizado (LGPD art. 20). O protótipo **não** decide sobre pessoas; em um uso
  real, a saída do modelo seria apoio, com revisão humana antes de qualquer negativa.
- **Supervisão humana:** alertas de contrato, execução ou drift são **sinais de investigação**
  para um responsável (a definir). Nenhum alerta aprova crédito, retreina o modelo ou altera
  política automaticamente.
- **Probabilidades:** a saída é `predict_proba` do Random Forest, **não calibrada**; não deve ser
  comunicada como probabilidade real de inadimplência.

### 2.4 Matriz de acesso

| Recurso | Quem acessa | Estado |
|---|---|---|
| Repositório GitHub (código, docs, JSON agregados) | Equipe do projeto | Realizado |
| Objetos DVC no DagsHub | Integrantes com token de leitura/escrita | Realizado; **Pendente:** confirmar acesso de leitura dos avaliadores |
| Token DagsHub | Cada integrante, em `.env` / `.dvc/config.local` (ignorados pelo Git) | Realizado; nunca versionado |
| MLflow, logs, dashboard | Máquina local de quem executa | Realizado (sem servidor compartilhado) |
| Vídeo STAR | A definir | Pendente: confirmar acesso sem credencial pessoal do autor |

Segregação de ambientes (Realizado): referência e produção simulada separadas em diretórios,
estágios e versionamento; apenas o estágio `evaluate` lê `test.csv`.

### 2.5 Retenção e descarte (Proposta — responsáveis e prazos a confirmar)

Não há prazo legal inventado aqui. A tabela propõe **gatilhos**; prazos e responsáveis são
decisões humanas pendentes.

| Classe | Onde existe | Gatilho de revisão proposto | Descarte (procedimento) |
|---|---|---|---|
| Dados brutos e partições | Cache DVC local, objetos no DagsHub | Fim do uso acadêmico / encerramento do projeto | Remover cópia local; exclusão remota exige decisão e autorização explícitas |
| Modelo e candidatos | Cache DVC, DagsHub | Substituição ou descontinuação do modelo | Idem |
| Lotes de produção simulados | Cache DVC, DagsHub | Fim da demonstração | Idem |
| Relatórios JSON/HTML agregados | Git, DagsHub | Fim do projeto; sem dado pessoal | Permanecem no histórico Git; remoção exigiria reescrita de histórico (não proposta) |
| MLflow, logs, recursos | Somente local | Após a avaliação | Apagar pastas locais |
| Cópias de avaliadores | Cache DVC deles | Fim da avaliação | Responsabilidade do avaliador; **Pendente** |
| Capturas e vídeo | Plataforma de vídeo | Fim da avaliação | A definir pelo responsável |

**Limites do armazenamento por hash:** apagar um ponteiro `.dvc`/`dvc.lock` do Git **não** apaga
o objeto no remote nem no cache local; o histórico Git continua apontando para versões antigas.
Descarte completo exige verificar cópias (cache DVC, DagsHub, MLflow, capturas) e autorização
específica. Este plano **não executa** coleta de lixo, exclusão ou revogação.

## 3. Governança do modelo (4.3)

### 3.1 Ficha do modelo (Realizado)

| Item | Valor | Origem |
|---|---|---|
| Finalidade | Estimar risco de inadimplência no mês seguinte para fins de estudo e monitoramento | Escopo do projeto |
| Uso excluído | Concessão real de crédito, decisão automática sobre pessoas, uso em outro país/período | Este documento |
| Algoritmo | Random Forest (300 árvores, `max_depth` 8, `min_samples_leaf` 20, `class_weight=balanced_subsample`, seed 42) | `configs/project.yaml` |
| Features | 19 financeiras; demografia fora do modelo | `models/credit_model_metadata.json` |
| Limiar | 0,5 (fixo; não é parâmetro de ajuste) | `reports/metrics.json` |
| Contrato | Versão `1.0.0` (Pandera, antes de treino e inferência) | `reports/metrics.json` |
| Seleção | Maior ROC-AUC na validação: Random Forest 0,774103 × Regressão Logística 0,714497 | `reports/metrics.json` |
| Otimização | Campanha `opt-20261026-01`: nenhum finalista atingiu o critério; Random Forest vigente mantido | `reports/metrics.json` |
| Hash do modelo oficial (DVC) | `a5a4a740902fab9efa5138f98917a8a7f447c5af7f7d97b707290c205c1e0464` | `reports/test_metrics.json` |
| Teste (reavaliação congelada) | ROC-AUC 0,777198; precisão 0,497; recall 0,605; F1 0,546; acurácia 0,777 | `reports/test_metrics.json` |
| Exposição histórica do teste | O EDA anterior à fase 1 usou o bruto completo; o teste **não** é holdout intocado | [`evidence/fase-1.md`](evidence/fase-1.md) §1.2.1 |

A classe 1 significa **risco de inadimplência**, não aprovação ou negativa de crédito. As métricas
de teste e validação são medidas sobre dados rotulados do UCI; métricas sobre lotes de
produção simulados **não** são desempenho real (não há rótulos em produção).

### 3.2 Análise agregada de viés (Realizado — descritiva)

Comando: `uv run python -m credit_monitoring.models.bias`. Saída:
[`reports/bias/validation_bias.json`](../reports/bias/validation_bias.json).

**Protocolo fixado antes da leitura dos resultados:**

- partição: **validação original rotulada** (4.500 linhas), modelo e limiar congelados. A
  validação já participou da seleção do modelo, então o resultado é **descritivo e possivelmente
  otimista**. O **teste não foi consultado**;
- grupos: `SEX`, `EDUCATION`, `MARRIAGE` por código original (sem atribuir significado a códigos
  fora da documentação) e `AGE` em faixas `≤29`, `30–39`, `40–49`, `≥50`;
- grupo com menos de 30 linhas: só `n` (suprimido). Taxa com denominador menor que 30:
  indefinida (inconclusiva);
- proporções com intervalo de Wilson 95%. Intervalo largo ou grupo suprimido = inconclusivo,
  **nunca** "sem viés";
- a execução recusa gerar o relatório se modelo e partição não reproduzirem a matriz de
  confusão de validação registrada em `reports/metrics.json` (verificação feita).

**Resultado** (TPR = recall entre inadimplentes reais; FPR = proporção de bons pagadores
sinalizados como risco; entre colchetes, IC 95%):

| Grupo | n | Positivos reais | Prevalência | Taxa de predição positiva | TPR | FPR |
|---|---:|---:|---:|---:|---|---|
| **Total** | 4.500 | 995 | 22,1% | 25,8% | 58,0% [54,9–61,0] | 16,7% [15,5–17,9] |
| `SEX` = 1 | 1.797 | 402 | 22,4% | 27,2% | 60,4% [55,6–65,1] | 17,6% [15,7–19,6] |
| `SEX` = 2 | 2.703 | 593 | 21,9% | 24,9% | 56,3% [52,3–60,3] | 16,1% [14,6–17,7] |
| `EDUCATION` = 1 | 1.626 | 279 | 17,2% | 21,6% | 59,1% [53,3–64,7] | 13,9% [12,1–15,8] |
| `EDUCATION` = 2 | 2.111 | 533 | 25,2% | 27,6% | 57,4% [53,2–61,5] | 17,5% [15,7–19,4] |
| `EDUCATION` = 3 | 711 | 177 | 24,9% | 30,8% | 59,9% [52,5–66,8] | 21,2% [17,9–24,8] |
| `EDUCATION` = 0, 4, 5, 6 | 2; 15; 29; 6 | — | — | — | suprimido (n < 30) | suprimido (n < 30) |
| `MARRIAGE` = 1 | 2.070 | 490 | 23,7% | 26,0% | 57,3% [52,9–61,7] | 16,3% [14,5–18,2] |
| `MARRIAGE` = 2 | 2.373 | 494 | 20,8% | 25,7% | 59,1% [54,7–63,4] | 17,0% [15,3–18,7] |
| `MARRIAGE` = 3 | 51 | 10 | 19,6% | 19,6% | indefinido (10 positivos) | 14,6% [6,9–28,4] |
| `MARRIAGE` = 0 | 6 | — | — | — | suprimido (n < 30) | suprimido (n < 30) |
| `AGE` ≤ 29 | 1.468 | 333 | 22,7% | 28,3% | 59,5% [54,1–64,6] | 19,1% [16,9–21,5] |
| `AGE` 30–39 | 1.632 | 317 | 19,4% | 23,3% | 57,1% [51,6–62,4] | 15,1% [13,3–17,2] |
| `AGE` 40–49 | 983 | 247 | 25,1% | 25,5% | 56,3% [50,0–62,3] | 15,2% [12,8–18,0] |
| `AGE` ≥ 50 | 417 | 98 | 23,5% | 27,6% | 60,2% [50,3–69,3] | 17,6% [13,8–22,1] |

**Leitura permitida (descritiva):**

- as TPR por grupo ficam em 56–60% e seus intervalos se sobrepõem amplamente; nesta amostra
  **não há evidência de diferença** de recall entre os grupos, o que é diferente de afirmar
  igualdade;
- a FPR varia mais: `EDUCATION` = 3 (21,2%) e `AGE` ≤ 29 (19,1%) têm FPR acima do total
  (16,7%), enquanto `EDUCATION` = 1 (13,9%) fica abaixo. Para `EDUCATION` = 3 e = 1 os
  intervalos não se sobrepõem. Isso indica **mais bons pagadores sinalizados como risco** nesses
  grupos, e merece investigação antes de qualquer uso real;
- `EDUCATION` = 3 também tem a maior taxa de predição positiva (30,8%) com prevalência real
  (24,9%) semelhante à de `EDUCATION` = 2 (25,2%), o que é compatível com a FPR maior;
- a diferença observada **não prova causa nem discriminação**: pode refletir proxies
  (histórico de pagamento, limite), composição dos grupos ou ruído amostral.

**Limitações:** análise descritiva sobre uma partição já usada na seleção; sem correção para
comparações múltiplas; códigos fora da documentação preservados sem interpretação; grupos
pequenos suprimidos; **não** valida equidade nem causalidade. Uma revisão motivada por viés deve
abrir **nova versão de modelo e protocolo**, sem ajustar o limiar consultando o teste reservado.

**Rastreabilidade:** o relatório foi (re)gerado em 2026-11-14 com os objetos **oficiais**
recuperados do DagsHub por `dvc pull`: modelo `a5a4a740902f…` (igual ao de
`reports/test_metrics.json`) e validação `e910967511f3…` (igual ao de `reports/metrics.json`);
ambos coincidem com o `dvc.lock`. O relatório reproduz a matriz de confusão de validação
registrada (TN 2.921, FP 584, FN 418, TP 577; ROC-AUC 0,774103). Uma execução anterior, feita com
artefatos regenerados localmente no Windows, produziu **exatamente os mesmos resultados**.

### 3.3 Responsabilidade e versões (Proposta)

- Cada versão do modelo é identificada por hash, contrato, configuração e `dvc.lock`; os
  registros de execução ficam no MLflow local.
- Revisão de alertas e de uso do modelo: responsável a definir (**Pendente**).
- **Suspensão/reavaliação:** em um uso real, suspender ou revisar a versão quando houver
  (a) falha de contrato recorrente, (b) drift confirmado e investigado sem explicação benigna,
  (c) degradação de desempenho ou diferença adversa entre grupos **comprovada com rótulos**.
  Gatilhos numéricos são decisão humana pendente.

## 4. Análise causal e resposta (4.4)

### 4.1 O que foi observado × o que é hipótese

| Categoria | Conteúdo |
|---|---|
| **Intervenção conhecida por construção** | O lote "modificado" é derivado do lote "original" multiplicando `LIMIT_BAL` por 1,5 e `PAY_AMT1` por 0,5 (protocolo `1.0.2`, seed 42). A causa da mudança de distribuição **é a transformação programada**. |
| **Efeito medido** | PSI referência × modificado: `LIMIT_BAL` 0,7525 e `PAY_AMT1` 0,4647 (limiar 0,20). Controle (referência × original): nenhuma das 19 features excede o limiar (maior PSI 0,004). Nas saídas previstas, a média do score vai de 42,31% a 41,99% (−0,32 p.p.) e a contagem prevista da classe 1 vai de 1.161 a 1.154. |
| **Hipóteses de contexto (não testadas)** | Inflação, mudança de limites concedidos, novo perfil de clientes ou mudança de política podem **inspirar** esse tipo de deslocamento num cenário real, mas **não são causas identificadas** por este experimento. |

Fonte: [`reports/drift/results-v1.0.2.json`](../reports/drift/results-v1.0.2.json) e
[`evidence/fase-2.md`](evidence/fase-2.md).

### 4.2 Limites do experimento

- É **Data Drift** sintético. **Não** é Concept Drift: não há rótulos em produção, então não se
  mede mudança em `P(y|X)` nem perda de desempenho. Frases como "o modelo piorou" ou "houve
  concept drift" **não são sustentadas** por estas evidências. A docência avaliará o plano após
  a entrega; se pedirem experimento adicional, deve ser identificado como sintético.
- O score médio cai pouco (−0,32 p.p.) mesmo com PSI alto. Isso descreve a **saída** do modelo,
  não a qualidade das previsões.
- PSI é medida de tamanho de efeito, não p-valor; o limiar 0,20 é convenção, não prova.

### 4.3 Explicações alternativas e evidência adicional

Num alerta real de drift, antes de atribuir causa econômica, considerar e testar:

| Explicação alternativa | Evidência que ajudaria a avaliá-la |
|---|---|
| Erro de processamento ou de unidade/moeda | Logs da fonte, comparação de schema e de unidades, reprocessamento |
| Mudança de fonte ou de schema | Procedência e histórico de versões da fonte |
| Seleção amostral diferente (outro canal ou campanha) | Comparar coortes comparáveis e período |
| Sensibilidade do teste (PSI, discretização) | Repetir com outro método/discretização e checar controle |
| Mudança real da população ou da economia | Série temporal, dados externos e, depois, rótulos posteriores |

### 4.4 Matriz de resposta por sinal (Proposta)

| Sinal | Resposta proposta | O que **não** fazer |
|---|---|---|
| Contrato falhou | Rejeitar o lote inteiro, investigar a origem e corrigir/reenviar | Corrigir silenciosamente ou inferir mesmo assim |
| Execução falhou | Corrigir a etapa e reexecutar com novo ID de tentativa | Apagar o registro da falha |
| Data Drift sinalizado | Investigar origem e impacto, revisar a decisão de uso com o responsável | Retreinar automaticamente ou tratar como perda comprovada |
| Desempenho ou viés adverso **comprovado** com rótulos | Avaliação humana e possível suspensão/revisão de versão | Ajustar limiar consultando o teste reservado |

Impacto potencial (ex.: mais decisões erradas se a população mudar) **não é perda medida**.
Responsáveis e escalonamento: **Pendente** de confirmação.

## 5. Riscos e mitigação

| Risco | Mitigação existente | Lacuna |
|---|---|---|
| Vazamento do teste ou seleção enviesada | Estágios separados; exposição histórica declarada | EDA original expôs o teste (declarado) |
| Reidentificação / PII em artefatos | Relatórios agregados; ID técnico; fixtures com IDs novos | Não há avaliação formal de reidentificação |
| Credenciais expostas | `.env` e `.dvc/config.local` ignorados pelo Git | Rotação de token não documentada |
| Viés entre grupos | Análise agregada por grupo (§3.2) | Descritiva; proxies não investigados |
| Concept Drift não detectável | Limitação declarada | Sem rótulos em produção simulada |
| Dados fora do contexto (Taiwan/2005) | Limite declarado | Sem validação em dados atuais |
| Retenção indefinida em cache/remote | Procedimento descrito (§2.5) | Prazos e responsáveis pendentes |

## 6. Pendências que dependem de decisão humana

- revisão jurídica da base legal proposta e conferência do texto atualizado da LGPD/ANPD;
- prazos e responsáveis de retenção/descarte; responsável por revisar alertas;
- confirmação do acesso de leitura dos avaliadores aos objetos DVC e ao vídeo;
- gatilhos numéricos de suspensão/revisão do modelo.
