# Governança, privacidade e causalidade

> Documento da fase 4 (IDs 4.1–4.4). Descreve o que foi **efetivamente observado** neste
> repositório e rotula o restante como **proposta** (cenário hipotético de fintech) ou
> **pendente** (depende de decisão humana). Não é parecer jurídico, não declara conformidade
> com a LGPD, não declara ausência de viés e não atesta aptidão do modelo para conceder crédito.
> Evidências e comandos: [`docs/evidence/fase-4.md`](evidence/fase-4.md).

**Legenda:** `Realizado` = verificado no repositório; `Proposta` = desenho para a fintech
hipotética, sem operação real; `Pendente` = precisa de decisão/confirmação humana.

**Premissas da entrega simulada (decididas pelo grupo em 2026-11-14):**

- a **revisão jurídica é simulada**: o Jurídico é fictício e não há parecer de profissional real.
  Base legal, prazos e demais enquadramentos são tratados como **proposta acadêmica**, não como
  validados;
- os prazos de retenção de produção adotados são **5 anos** (logs de inferência) e **24 meses**
  (datasets de treino e validação), como parâmetros propostos (§2.5);
- a instituição fictícia que representa o grupo é **premissa de cenário**: considera-se um
  "órgão de pesquisa" (LGPD art. 5º, XVIII) para discutir o art. 7º, IV. Nenhuma constituição
  legal, sede ou ausência de fins lucrativos é afirmada como fato (§2.1);
- o término do tratamento do protótipo segue o critério da LGPD (arts. 15 e 16), sem prazo
  numérico próprio (§2.5);
- o acesso de leitura dos avaliadores aos repositórios foi **declarado** liberado pelo grupo (§2.4);
- a distribuição de papéis e SLAs foi **comunicada ao grupo** (§3.3).

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

- **Categorias sensíveis (LGPD art. 5º, II):** origem racial ou étnica, convicção religiosa,
  opinião política, filiação a sindicato ou a organização de caráter religioso, filosófico ou
  político, saúde ou vida sexual, dado genético ou biométrico, quando vinculado a uma pessoa
  natural. O dataset **não contém** essas variáveis. Sexo, escolaridade, estado civil e idade
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
| Base legal | Não está definida: o art. 4º, II, "b", afasta a LGPD de tratamento **exclusivamente** acadêmico, **mas mantém a aplicação dos arts. 7º e 11**; o art. 7º, § 3º, exige considerar finalidade, boa-fé e interesse público de dados de acesso público. O art. 7º, IV (estudos por "órgão de pesquisa", art. 5º, XVIII) só serve se a entidade responsável se enquadrar nessa definição; segundo o estudo técnico da ANPD (ver §2.2), quem não se enquadra precisa de outra hipótese, como consentimento ou legítimo interesse. **Premissa do cenário simulado:** a instituição fictícia que representa o grupo é um órgão de pesquisa, o que permite apoiar o uso acadêmico no art. 7º, IV, com anonimização "sempre que possível". Isso **não é fato verificado** e exige revisão jurídica real em um uso verdadeiro | Ver §2.2 |

### 2.2 Base legal proposta (Proposta — revisão jurídica simulada)

Para o cenário hipotético, hipóteses a submeter à revisão do encarregado/jurídico, **sem
afirmar que estejam validadas**. A empresa é uma **fintech fictícia**, criada só para ilustrar o
tema em um projeto acadêmico: seu porte, natureza jurídica, papel (controladora ou operadora) e
eventual regulação **não estão definidos** e não devem ser lidos como fato. Por isso as hipóteses
abaixo são condicionais.

- **Proteção do crédito** (LGPD art. 7º, X) como hipótese principal para análise de risco de
  inadimplência;
- **execução de contrato** (art. 7º, V) para dados necessários ao contrato com o titular, quando
  aplicável;
- **cumprimento de obrigação legal ou regulatória** (art. 7º, II): mantido **apenas como
  hipótese condicional**, que só vale se a instituição estiver sujeita a normas prudenciais do
  BACEN/CMN que exijam modelagem de perda esperada. Neste projeto acadêmico, a fintech é
  **fictícia** e **nenhuma autorização ou licença real é afirmada**; se o cenário não pressupuser
  uma instituição regulada, o inciso deve ser removido para evitar enquadramento indevido.

Princípios do art. 6º a observar: finalidade (I), adequação (II), necessidade (III), livre acesso
(IV), qualidade (V), transparência (VI), segurança (VII), prevenção (VIII), **não discriminação**
(IX) e responsabilização e prestação de contas (X). O art. 7º, § 6º, estabelece que a dispensa de
consentimento não desobriga os agentes das demais obrigações da lei, em especial os princípios e
os direitos do titular; o art. 20 garante a revisão de decisões automatizadas, inclusive de perfil
de crédito; e o art. 37 exige registro das operações de tratamento.

Recomendação preventiva para um uso real (Proposta): elaborar o **Relatório de Impacto à Proteção
de Dados Pessoais (RIPD)** (definido no art. 5º, XVII) antes de entrar em produção, documentando
as métricas de não discriminação (§3.2) e o fluxo de atendimento ao art. 20. O art. 38 apenas
prevê que a ANPD **pode determinar** a elaboração do RIPD; a elaboração prévia é boa prática, não
exigência literal do texto. Quanto ao art. 12, os dados anonimizados deixam de ser pessoais
**salvo** se a anonimização for reversível com esforços razoáveis; o projeto **não presume
anonimização** do dataset público e trata todo registro sob controles de dados pessoais.

**Conferência no texto oficial (2026-11-14).** Os artigos 4º, 5º, 6º, 7º, 12, 15, 16, 20, 37, 38 e
48 foram conferidos contra a cópia local [`docs/LGPD.txt`](LGPD.txt) (texto da Lei nº
13.709/2018 com o cabeçalho da Presidência da República, incluindo alterações até a Lei nº
15.352/2026). O art. 20 também havia sido visto no portal da Câmara. As hipóteses do art. 7º
(II, V e X) e os princípios do art. 6º (I, III, VI e IX) citados acima **coincidem** com o texto.
A conferência confirma o que a lei diz; **não** valida o enquadramento. Os arts. 15 e 16 tratam do
término do tratamento e da eliminação (com exceções de conservação, como obrigação legal), mas
**não fixam prazos**: os prazos de §2.5 continuam propostas sem base legal conferida.

> Origem: parte desta seção e das §2.5, §3.3 e §4.4 vem de uma pesquisa interna sem referências
> primárias. O que **não** foi conferido: a base normativa de cada prazo de retenção, as
> orientações da ANPD e o enquadramento jurídico (revisão humana pendente).

Referências oficiais: [Lei 13.709/2018 (Planalto)](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
e [texto na Câmara dos Deputados](https://www2.camara.leg.br/legin/fed/lei/2018/lei-13709-14-agosto-2018-787077-publicacaooriginal-156212-pl.html).
**Pendente:** orientações finais da ANPD sobre decisões automatizadas e proteção do crédito.

**Orientação da ANPD sobre uso acadêmico (consultada em 2026-11-14).** O
[Estudo Técnico "A LGPD e o tratamento de dados pessoais para fins acadêmicos e para a realização de estudos por órgão de pesquisa"](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/documentos-tecnicos-orientativos/estudo-tecnico-a-lgpd-e-o-tratamento-de-dados-pessoais-para-fins-academicos-e-para-a-realizacao-de-estudos-por-orgao-de-pesquisa.pdf/@@display-file/file)
(Texto para Discussão nº 1/2022, abril/2022) foi lido diretamente. Ele é **preliminar**: declara
que "não representa necessariamente a opinião final da ANPD". Dele se extrai, como leitura
cautelosa, que o art. 7º, IV exige entidade que se enquadre no art. 5º, XVIII (por exemplo,
instituições de ensino superior públicas ou privadas **sem fins lucrativos**), e que quem não se
enquadra precisa amparar o tratamento em outra hipótese legal, como consentimento ou legítimo
interesse. O mesmo estudo define órgão de pesquisa como entidade constituída sob as leis
brasileiras, com sede e foro no País, sem fins lucrativos (se privada) e com pesquisa em sua
missão. **Premissa adotada:** a instituição fictícia do grupo atende a esses requisitos; é uma
suposição de cenário, não um fato. A camada da **fintech hipotética**, com fins lucrativos, **não**
se apoia no art. 7º, IV (§2.2).

**Dados de origem estrangeira (art. 4º, IV).** Pelo texto da lei, a exclusão exige que os dados
venham de fora do território nacional **e** não sejam objeto de comunicação ou uso compartilhado
com agentes de tratamento brasileiros, nem de transferência internacional a país diferente do de
origem, **e** que o país de origem ofereça grau de proteção adequado. Como o dataset é usado por
agentes brasileiros (o grupo), leitura provisória: a exceção **provavelmente não** cobre o
projeto, que por isso adota controles de dados pessoais. É leitura do texto, não parecer: fica
para a revisão jurídica.

**Art. 20 e revisão humana.** O texto atual do art. 20 **não exige** que a revisão seja feita por
pessoa natural (o § 3º, que tratava disso, foi vetado, conforme `docs/LGPD.txt`). A revisão
humana adotada neste documento é uma **escolha de desenho proposta**, não uma exigência
literal. Afirmações de blogs sobre a posição da ANPD em "intervenção humana significativa" **não
foram verificadas** em fonte primária e não são usadas aqui.

### 2.3 Transparência, contestação e supervisão (Proposta)

- **Transparência:** informar o titular sobre finalidade, critérios gerais e fatores relevantes
  da análise. O protótipo **não** implementa essa comunicação.
- **Contestação:** o titular pode solicitar a revisão de decisões tomadas unicamente com base em
  tratamento automatizado (LGPD art. 20). O protótipo **não** decide sobre pessoas; em um uso
  real, a saída do modelo seria apoio, com revisão humana antes de qualquer negativa. A
  contestação exige revisão pelo controlador e informações claras sobre os critérios (respeitado o
  segredo comercial e industrial); **não** gera, por si, comunicação à ANPD. Se o controlador
  negar as informações alegando segredo industrial, a ANPD pode realizar auditoria (art. 20, § 2º).
- **Incidente de segurança:** o art. 48 manda comunicar **à ANPD e ao titular** o incidente que
  possa acarretar risco ou dano relevante aos titulares, em prazo definido pela autoridade
  (§ 1º). Segundo o art. 6º da
  [Resolução CD/ANPD nº 15/2024](https://www.in.gov.br/en/web/dou/-/resolucao-cd/anpd-n-15-de-24-de-abril-de-2024-556243024)
  (DOU, consultado em 2026-11-14), deve ocorrer em **três dias úteis** contados do conhecimento
  de que o incidente afetou dados pessoais.
- **Supervisão humana:** alertas de contrato, execução ou drift são **sinais de investigação**
  para os responsáveis definidos em §3.3 (simulação acadêmica). Nenhum alerta aprova crédito, retreina o modelo ou altera
  política automaticamente.
- **Probabilidades:** a saída é `predict_proba` do Random Forest, **não calibrada**; não deve ser
  comunicada como probabilidade real de inadimplência.

### 2.4 Matriz de acesso

| Recurso | Quem acessa | Estado |
|---|---|---|
| Repositório GitHub (código, docs, JSON agregados) | Equipe do projeto | Realizado |
| Objetos DVC no DagsHub | Integrantes com token de leitura/escrita | Realizado; leitura dos avaliadores **declarada liberada pelo grupo para todos os repositórios** em 2026-11-14 (declaração; sem captura de tela nem verificação independente) |
| Token DagsHub | Cada integrante, em `.env` / `.dvc/config.local` (ignorados pelo Git) | Realizado; nunca versionado |
| MLflow, logs, dashboard | Máquina local de quem executa | Realizado (sem servidor compartilhado) |
| Vídeo STAR | A definir | Pendente: confirmar acesso sem credencial pessoal do autor |

Segregação de ambientes (Realizado): referência e produção simulada separadas em diretórios,
estágios e versionamento; apenas o estágio `evaluate` lê `test.csv`.

### 2.5 Retenção e descarte (Proposta — responsáveis e prazos a confirmar)

Os prazos abaixo são **parâmetros propostos**, não exigência legal verificada. Os arts. 15 e 16 da
LGPD não fixam prazo: o término ocorre quando a finalidade é alcançada ou os dados deixam de ser
necessários (art. 15) e a conservação é autorizada, entre outros casos, para cumprimento de
obrigação legal ou regulatória (art. 16, I). Para o prazo de 5 anos, uma pesquisa interna indica
como fundamentos o CDC art. 43, § 1º (informação negativa em cadastros por no máximo 5 anos; Súmula
323 do STJ), o CDC art. 27 (prescrição de 5 anos da pretensão por fato do serviço) e o Código
Civil art. 206, § 5º, I (cobrança de dívida líquida). Esses dispositivos **não foram conferidos em
texto oficial** e têm funções diferentes: o CDC art. 43, § 1º é um **teto** para cadastros de
inadimplentes, não uma regra de retenção de logs de inferência, e os prazos prescricionais correm
de marcos distintos. Cabe ao encarregado/Jurídico validar a aplicação e segregar base ativa de
arquivo para defesa judicial.

**Protótipo acadêmico (Proposta).** Gatilho: o **término do tratamento**. Pela LGPD, ele ocorre
quando a finalidade é alcançada ou os dados deixam de ser necessários (art. 15, I), e os dados são
então eliminados "no âmbito e nos limites técnicos das atividades" (art. 16). A lei **não fixa
número de dias**; por isso o protótipo não adota prazo numérico próprio. Para o projeto, a
finalidade (estudo acadêmico e demonstração) é considerada alcançada com a **conclusão da
avaliação**; a eliminação ocorre a partir daí, dentro dos limites técnicos (o grupo pode, se
quiser, registrar uma data operacional, sem valor legal). Escopo:

- o dataset de origem é **público e real** (UCI 350, CC BY 4.0), não fictício; fictícios são
  apenas o cenário da fintech e os lotes de produção **sintéticos** derivados dele. Por isso a
  exclusão é uma medida de minimização e de coerência com o plano de retenção, não uma exigência
  da licença;
- o que seria excluído são as **cópias e os objetos de dados e modelos** (cache DVC local, objetos
  no DagsHub, MLflow, logs); o **repositório Git** (código, documentação e JSON agregados, sem
  dados de clientes) **permanece** como caso de estudo, e o histórico do Git não é reescrito;
- a reprodutibilidade não depende dos objetos remotos para os dados de origem: o workbook pode ser
  obtido de novo na UCI e conferido pelos hashes registrados em `configs/project.yaml`
  (`expected_xls_md5`); os modelos e lotes sintéticos seriam regenerados pelo pipeline;
- a exclusão **só será declarada como feita com evidência** (comando, data e conferência), por
  quem executa (Denis Barros Melo, simulado) e com ciência do DPO simulado (Fábio Polli). Até lá,
  é **proposta**. A coleta de lixo do DVC e a exclusão no DagsHub **não foram executadas**;
- **riscos a registrar:** após a exclusão, um `dvc pull` deixa de funcionar para quem precisar
  reproduzir o projeto; por isso a eliminação só ocorre após a conclusão da avaliação. O art. 16,
  IV admite conservar dados **anonimizados** para uso exclusivo do controlador, o que sustenta
  manter os relatórios agregados no Git. Cópias de avaliadores
  e a plataforma do vídeo **não estão sob controle do grupo**: pode-se apenas **solicitar** a
  eliminação.

| Classe (protótipo) | Onde existe | Gatilho proposto | Descarte (procedimento) |
|---|---|---|---|
| Dados brutos e partições | Cache DVC local, objetos no DagsHub | Conclusão da avaliação (art. 15, I) | Remover cópia local e objetos remotos; registrar evidência. Dado de origem é recuperável na UCI |
| Modelo e candidatos | Cache DVC, DagsHub | Idem | Idem; regenerável pelo pipeline |
| Lotes de produção simulados | Cache DVC, DagsHub | Idem | Idem; regeneráveis (protocolo `1.0.2`, seed 42) |
| Relatórios JSON/HTML agregados | Git, DagsHub | Não se aplica; sem dado pessoal | Permanecem no Git como caso de estudo; reescrever histórico não é proposto |
| MLflow, logs, recursos | Somente local | Conclusão da avaliação (art. 15, I) | Apagar pastas locais |
| Cópias de avaliadores | Cache DVC deles | Fim da avaliação | **Solicitar** a eliminação; sem controle do grupo |
| Capturas e vídeo | Plataforma de vídeo | A definir | Só agregados; decisão do responsável pela gravação (**Pendente**) |

**Cenário de produção com dados reais (Proposta, a validar):**

| Classe | Retenção proposta | Descarte proposto |
|---|---|---|
| Logs de inferência e predição | 5 anos após o fim da relação contratual ou da última consulta de crédito | Exclusão lógica no vencimento e expurgo físico (sobrescrita) em até 30 dias |
| Datasets de treino e validação | 24 meses em ambiente isolado e pseudonimizado, para auditoria de viés e reprodutibilidade | Eliminação ou anonimização irreversível ao fim do ciclo (LGPD, arts. 15 e 16, a conferir) |

Responsáveis (simulação acadêmica, ver §3.3): definição e auditoria dos prazos —
Encarregado (DPO) **Fábio Polli**, com o Jurídico fictício; execução técnica do expurgo —
Engenharia de Dados **Denis Barros Melo**. O encarregado não executa o expurgo, para manter a
separação entre quem define e quem executa.

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
  (16,7%), enquanto `EDUCATION` = 1 (13,9%) fica abaixo. A evidência é **mais forte para
  `EDUCATION`**: os intervalos de `EDUCATION` = 3 [17,9–24,8] e `EDUCATION` = 1 [12,1–15,8] não se
  sobrepõem. Para `AGE` ≤ 29 [16,9–21,5] a evidência é **mais fraca**: o intervalo se sobrepõe
  marginalmente aos de 30–39 [13,3–17,2] e 40–49 [12,8–18,0]. Isso indica **mais bons pagadores
  sinalizados como risco** nesses grupos, e merece investigação antes de qualquer uso real. A
  comparação de intervalos é um critério informal, sem teste formal de diferença;
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
- **Suspensão/reavaliação:** em um uso real, suspender ou revisar a versão quando houver
  (a) falha de contrato recorrente, (b) drift confirmado e investigado sem explicação benigna,
  (c) degradação de desempenho ou diferença adversa entre grupos **comprovada com rótulos**.

#### Gatilhos numéricos

**Regras ativas no protótipo (Realizado, `configs/project.yaml`):**

- **Contrato de dados:** o processamento é em lote; qualquer violação de esquema, tipo ou nulos
  fora do contrato bloqueia o lote inteiro antes da inferência.
- **PSI por feature:** alerta quando o PSI é **maior que 0,20** (`comparison: ">"`), com revisão
  humana; o alerta não dispara retreino automático.

**Regras adicionais para um cenário real (Proposta, referência de mercado a validar):**

| Gatilho | Revisão (amarelo) | Suspensão preventiva (vermelho) | Observação |
|---|---|---|---|
| PSI das features ou do score | 0,10 a 0,25 | acima de 0,25 | O protótipo usa um único limiar de 0,20 para testes |
| AUC-ROC | queda relativa > 5% frente à validação | queda > 10% | Exige rótulos reais (safra); **não se aplica ao protótipo** |
| KS | — | abaixo de 0,20 | Idem |
| Equidade | — | razão mínima/máxima entre grupos da taxa do **desfecho favorável** (não ser sinalizado como risco, isto é, 1 − taxa de predição positiva) abaixo de 0,80 | Regra dos 80% é referência técnica externa (EEOC, EUA), **não exigência da LGPD**. Aplicada à taxa de predição positiva (classe 1 = risco), a razão seria calculada sobre o desfecho **adverso** e daria resultado diferente; ver verificação abaixo |

**Verificação dos gatilhos nos dados do projeto (2026-11-14, descritiva).** Aplicados aos
resultados já existentes (`results-v1.0.2.json` e `validation_bias.json`; grupos com n ≥ 100):

- **PSI:** o controle tem PSI máximo 0,004 (nenhum alerta em qualquer esquema). `LIMIT_BAL`
  (0,7525) e `PAY_AMT1` (0,4647) ficam acima de 0,25 (**vermelho**) e acima do limiar do protótipo
  (0,20). Como são intervenções sintéticas, o resultado é coerente com o desenho, não prova que
  as faixas são adequadas;
- **Equidade (razão mínima/máxima, desfecho favorável = não sinalizado):** `EDUCATION` 0,883,
  `AGE` 0,935, `SEX` 0,970 e `MARRIAGE` 0,997, todos **acima de 0,80**. Pela taxa de sinalização
  de risco (desfecho adverso), `EDUCATION` daria 0,703 e `AGE` 0,824, o que mostra que a escolha
  do desfecho muda a conclusão: a definição deve ser fixada **antes** de usar o gatilho;
- AUC, KS e a queda relativa **não podem ser verificados** sem rótulos de produção, que o projeto
  não tem.

#### Papéis e responsáveis (simulação acadêmica)

Os papéis são da fintech hipotética. Por se tratar de projeto acadêmico, foram atribuídos aos
integrantes do grupo, seguindo as frentes iniciais do [README](../README.md#equipe-e-frentes-de-trabalho),
e o papel jurídico é **fictício**. A atribuição é uma **simulação para fins de documentação**:
**não** constitui atribuição formal de responsabilidade individual. A revisão jurídica é
**simulada** (premissa da entrega); o Jurídico fictício não valida nada. Em 2026-11-14 o grupo foi
informado da distribuição de papéis e dos SLAs (declaração, sem registro formal).

| Papel | Responsável (simulado) | Frente inicial |
|---|---|---|
| Encarregado (DPO) | Fábio Polli | Repositório, arquitetura, CI e integração |
| Engenharia de Dados (qualidade, contrato, expurgo) | Denis Barros Melo | Engenharia e qualidade de dados |
| MLOps / operação do monitoramento | Romario Silva | Observabilidade, dashboard e integração |
| Cientista de Dados líder | Willian Kopp | Plano técnico e modelagem |
| Responsável de produto de crédito | Denis Barros Melo | Atribuição simulada |
| Jurídico | Advogado(a) fictício(a), do "Escritório Fictício Exemplo & Associados" (papel simulado, sem existência real) | — |

#### Revisão de alertas e escalonamento (Proposta)

Nenhum alerta técnico dispara retreino automático; toda ação corretiva exige revisão humana
prévia. Os SLAs são propostos, sem base normativa.

| Nível | Tipo de alerta | Responsável (simulado) | SLA | Ação e escalonamento |
|---|---|---|---|---|
| N1 (operacional) | Falha de contrato no lote, falha de execução ou drift moderado | Romario Silva (MLOps) | até 4 h | Bloquear o lote inválido ou diagnosticar features; escala para N2 se persistir por mais de 24 h |
| N2 (tático/negócio) | Drift severo ou desvio na taxa de predição positiva | Willian Kopp (Cientista de Dados líder) e Denis Barros Melo (produto de crédito) | até 24 h | Revisão humana, com possível retreino ou revisão do limiar em nova versão; escala para N3 se houver risco regulatório ou viés |
| N3 (crítico/privacidade) | Contestação do art. 20, suspeita de discriminação ilícita (art. 6º, IX) ou incidente de segurança (art. 48) | Comitê simulado: Fábio Polli (DPO), Willian Kopp (modelo) e o Jurídico fictício | imediato (até 2 h) | Suspensão preventiva do modelo, com fallback manual; incidente com risco relevante segue o prazo da Resolução CD/ANPD nº 15/2024 (§2.3) |

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
Responsáveis e escalonamento propostos em §3.3; a atribuição nominal está **pendente**.

## 5. Riscos e mitigação

| Risco | Mitigação existente | Lacuna |
|---|---|---|
| Vazamento do teste ou seleção enviesada | Estágios separados; exposição histórica declarada | EDA original expôs o teste (declarado) |
| Reidentificação / PII em artefatos | Relatórios agregados; ID técnico; fixtures com IDs novos | Não há avaliação formal de reidentificação |
| Credenciais expostas | `.env` e `.dvc/config.local` ignorados pelo Git | Rotação de token não documentada |
| Viés entre grupos | Análise agregada por grupo (§3.2) | Descritiva; proxies não investigados |
| Concept Drift não detectável | Limitação declarada | Sem rótulos em produção simulada |
| Dados fora do contexto (Taiwan/2005) | Limite declarado | Sem validação em dados atuais |
| Retenção indefinida em cache/remote | Procedimento descrito (§2.5); responsáveis simulados em §3.3 | Prazos propostos (5 anos e 24 meses) sem validação jurídica real (revisão simulada) |

## 6. Limitações e pendências

**Limitações assumidas pela entrega simulada (não impedem a conclusão acadêmica):**

- a revisão jurídica é simulada; base legal (art. 7º, II, V e X; IV para a camada acadêmica),
  leitura do art. 4º, IV e fundamentos dos prazos de 5 anos e 24 meses (CDC e Código Civil, não
  conferidos em texto oficial) **não foram validados por profissional**. Os artigos da LGPD
  citados foram conferidos contra `docs/LGPD.txt` (§2.2) e o estudo técnico da ANPD foi lido
  (preliminar);
- as orientações da ANPD sobre decisões automatizadas e crédito constam de um **resumo fornecido
  pelo grupo** (`docs/Diretrizes da ANPD.txt`), que o grupo informa ser resumo de fonte primária;
  ele cita blogs e portais jurídicos e **não foi verificado diretamente na fonte**, por isso não é
  usado para fundamentar afirmações deste documento;
- o acesso dos avaliadores é declaração do grupo, sem captura de tela;
- os gatilhos numéricos do cenário real (§3.3) são referência de mercado, não validados.

**Pendências de execução:**

- executar e **registrar evidência** da eliminação de objetos e caches após a conclusão da
  avaliação (§2.5), e solicitar a eliminação às cópias de avaliadores;
- confirmar o acesso de leitura dos avaliadores ao vídeo, quando publicado.
