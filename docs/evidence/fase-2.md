# Evidências — Fase 2 (Simulação e Detecção de Drift)

**Execução local:** 2026-11-02, branch `feat/bill/phase-2-drift`.
**Entrada:** M1 já concluído; não se repetiu treino nem avaliação do teste.
**Estado:** Data Drift `1.0.2` implementado, testado, enviado ao DagsHub e recuperado em cache
isolado. A versão `1.0.1` também foi preservada no remote. Por decisão de Bill (2026-11-02),
Concept Drift não é gate pré-entrega; a docência avaliará o plano após a entrega.

## Ambiente e entrada M1

| Item | Evidência |
|---|---|
| Python / plataforma | Python 3.12.15; Linux 7.2.8-9-omarchy, x86_64, glibc 2.44 |
| Pacotes usados | Evidently 0.7.23; NumPy 2.5.4; pandas 2.3.3; scikit-learn 1.9.1; Pandera 0.34.1; DVC 3.67.1 |
| Instalação | `$HOME/.local/bin/uv sync --dev --locked --extra drift --extra model_lab` — exit 0; Evidently e Streamlit instalados para integração/suíte completa |
| Treino/referência | 21.000 linhas; SHA-256 `9ebd48b6d31c67f46cc28aff0bde36b48f62936aff0011007b7cb78d26108c26`; referência igual ao treino |
| Validação | 4.500 linhas; SHA-256 `e910967511f31406edbc3c9fe0528571d079c45da10116dba4e53e379d285106`; IDs únicos e disjuntos do treino |
| Modelo congelado | SHA-256 `a5a4a740902fab9efa5138f98917a8a7f447c5af7f7d97b707290c205c1e0464`; idêntico ao valor nos metadados |
| Contrato/limiar | versão `1.0.0`; limiar de classe `0.5`, lido dos metadados M1 |

O workbook UCI não está materializado neste checkout: `uv run dvc status` continua reportando
somente `acquire` como alterado/ausente. Os artefatos M1 acima estão presentes e tiveram seus
hashes conferidos. Por isso, os estágios novos foram executados individualmente com
`dvc repro --single-item`; não se executou o DAG inteiro nem se recuperou novamente o remote.

## Primeira execução — protocolo 1.0.1 (histórico preservado)

As seções abaixo registram a primeira execução e os objetos `1.0.1`, publicados antes do ajuste de
precisão de probabilidade. O desenho das transformações e PSI foi mantido em `1.0.2`.

## 2.1–2.3 — Produção e cenário 1.0.1

Bill aprovou o protocolo proposto em 2026-11-02 antes da comparação. O primeiro ensaio falhou antes
de gravar arquivos ou calcular PSI: dois valores `PAY_AMT1=1` arredondariam para zero com `×0,5`
e `half_to_even`. Bill escolheu preservar exatamente a máscara de zeros; o protocolo foi
versionado para `1.0.1`, com piso `1` para pagamentos originalmente positivos. Os 778 zeros da
validação permanecem 778 no lote modificado.

Configuração congelada em `configs/project.yaml`:

- `LIMIT_BAL × 1,5`; `PAY_AMT1 × 0,5`; arredondamento `half_to_even`; nenhuma amostragem aleatória
  (seed registrada como `42`).
- PSI customizado nas 19 features financeiras; até 10 quantis calculados apenas na referência,
  bordas repetidas colapsadas, extremos fora da faixa nas faixas abertas, massa de zero separada,
  regra explícita para referência constante e suavização aditiva `1e-6` normalizada para somar 1.
- Limiar por feature `0,20`; drift iff `PSI > 0,20`; alerta global se qualquer feature exceder.
  `unused_p_value_alpha: 0.05` não entra no PSI e nenhum p-value é calculado.

Saídas em `data/production/v1.0.1/` (local/DVC):

| Artefato | SHA-256 |
|---|---|
| `original.csv` | `d9f855a77f8fb6916fded48b880d18fa48e4c4816070167f4caf8af6ad874d65` |
| `modified.csv` | `8da682f306f25003c98e851e84dda427b25daac41dfdf9474a13b6f641f71fc7` |
| `manifest.json` | `0f7030f227e26e3f9b1568811d8bb9e85239636a2e45b8cce1f141430293cb03` |

Verificado: 4.500 linhas em cada lote; IDs únicos, mesma ordem entre cenários e sem interseção
com referência; alvo ausente; só `LIMIT_BAL` e `PAY_AMT1` diferem; `LIMIT_BAL` segue positivo;
fonte de validação inalterada. Hash do protocolo no manifesto/resultados:
`1ec8a7f50a3ef3409363814f0c85965eee068e7640ee7fe086a15e30b9c6778a`.

## 2.4 — Inferência

`score_production` confere SHA-256 do modelo contra os metadados, valida cada lote completo com
Pandera, rejeita lote vazio na camada de inferência e usa apenas as 19 features financeiras para
predizer. As saídas DVC associam cada probabilidade/classe ao ID técnico de origem, sem target ou
atributos demográficos. Cada cenário contém 4.500 predições finitas em `[0,1]`; classe pelo
limiar congelado `0,5`. O JSON contém resumos agregados de probabilidades e hashes, sem linhas de
clientes.

| Artefato | SHA-256 |
|---|---|
| `predictions/original.csv` | `0a6a0bad7529b22beebb8f00a9d45b9d14cb593ec2eea1bba1989fa98fa1c12f` |
| `predictions/modified.csv` | `d287f5b37be6be50a9ec1239b174bc66bb020d17c8696a8a3426eb74b072065d` |
| `reports/drift/prediction_summary.json` | `535e8990e058e03d60bb4f3c98ac5a5f3f678823ba672ad4cde68eaeee14e0ed` |

## 2.5–2.7 — Detecção e relatório

Evidently 0.7.23 foi instalado do extra travado `drift`. A inspeção prática mostrou que o
`DataDriftPreset` não aceita a callback PSI customizada no novo `ValueDrift`; a renderização de
`DataSummaryPreset` falha com `KeyError` na versão usada. Para respeitar o protocolo aprovado,
uma implementação PSI única alimenta o JSON e as tabelas HTML; um `Report` do Evidently fornece o
contexto de contagem. O detector nativo do Evidently não é usado. O HTML inclui proveniência,
versões, comparações, resultados por feature, resumo de probabilidades e limites interpretativos;
não inclui IDs nem alvo.

| Comparação | Resultado observado |
|---|---|
| referência × produção original (controle) | Nenhuma das 19 features excedeu `0,20`; PSI de `LIMIT_BAL` `0,001009`, `PAY_AMT1` `0,001775` |
| referência × produção modificada | `LIMIT_BAL` PSI `0,752498`; `PAY_AMT1` PSI `0,464748`; ambas excederam `0,20` |
| produção original × modificada | `LIMIT_BAL` PSI `0,777132`; `PAY_AMT1` PSI `0,459644`; ambas excederam `0,20` |

Nenhuma outra feature sinalizou drift. Esses resultados sustentam o aceite local de Data Drift sob
o protocolo congelado; não demonstram mudança real no tempo, Concept Drift nem perda de desempenho.

| Artefato | SHA-256 |
|---|---|
| `reports/drift/results-v1.0.1.json` | `975b923af9af928e0e4713ee5c1909defc0830942296780fe132201818ac6832` |
| `reports/drift/phase-2-drift-v1.0.1.html` | `ca14e3ae83b233c48fb9e7bb57da55b1fe8f160d4de139d18447f960d9f75729` |

O HTML abriu e foi inspecionado com Chromium headless (`--dump-dom`): as três comparações, ambas
features, proveniência, probabilidades e limitações estão presentes no DOM renderizado.

## Revisão final — protocolo 1.0.2

As duas execuções independentes do Random Forest diferiram em 1.482/4.500 probabilidades somente
na precisão de máquina; delta máximo `3.3306690738754696e-16`, sem valores a `1e-10` do limiar
`0.5`. Bill aprovou persistência `half_to_even` a 12 casas e classe calculada a partir do valor
persistido. O máximo de arredondamento é `5e-13` e nenhuma classe observada mudou. Dois processos
independentes da CLI `score_production` produziram os mesmos hashes das predições.

O protocolo v1.0.2 mantém as transformações e o PSI de v1.0.1; acrescenta apenas a precisão
determinística de persistência. As saídas original/modificada mantêm hashes, tamanhos, IDs, zeros e
features alteradas idênticos à versão anterior.

| Artefato v1.0.2 | SHA-256 |
|---|---|
| `data/production/v1.0.2/original.csv` | `d9f855a77f8fb6916fded48b880d18fa48e4c4816070167f4caf8af6ad874d65` |
| `data/production/v1.0.2/modified.csv` | `8da682f306f25003c98e8519b174bc66bb020d17c8696a8a3426eb74b072065d` |
| `data/production/v1.0.2/manifest.json` | `d0e983fa175115e96f508d08512006b23af4e00f3a7f81e4368bd58ded528ee9` |
| `predictions/original.csv` | `76c3821ef5a39ca37b98b16d16f8a7e5e81e57368aec7cca7effffba0e9d5f81` |
| `predictions/modified.csv` | `49748dd0442cec340e9e4dc554d4d2cd177684fd70dff17da00c21cf455deaae` |
| `prediction_summary-v1.0.2.json` | `a92f59f6c525877be209cd4804c603334161153a23093237ded53ab2696a742a` |
| `results-v1.0.2.json` | `f0c02e97fbb3a6301ec1cf65593c9c7977f051bd4c4a2eec7c1276b45ec4bd48` |
| `phase-2-drift-v1.0.2-final.html` | `23930e2e578e9bf90a60ce8e2f8ac2c3b2c5151277b57b4b288435ae94e6d356` |

Protocolo SHA-256: `e160b86e5d6f62382859df8828f053ef16bef438a6f0967e022a99cb4ae536fb`. PSI observado
permanece igual ao relatado para v1.0.1: controle sem alertas; `LIMIT_BAL` e `PAY_AMT1` acima de
0,20 somente em referência×modificada e original×modificada. O resumo DVC não contém caminhos locais
nem tempo variável; o HTML renderizado inclui precisão/rounding, proveniência e todas as comparações.

## Comandos e verificações

### Reexecução e privacidade do resumo v1.0.2

Uma segunda execução de `uv run python -m credit_monitoring.models.score_production` gerou os mesmos
hashes dos dois CSVs de predição. `prediction_summary-v1.0.2.json` contém apenas agregados, hashes e
precisão fixa; não inclui caminhos locais nem duração variável.

| Comando | Resultado |
|---|---|
| `uv run dvc dag` | exit 0; DAG inclui `simulate_production → score_production → detect_drift` |
| `uv run dvc repro --single-item simulate_production` | exit 0; 4.500 linhas; outputs no cache DVC local |
| `uv run dvc repro --single-item score_production` | exit 0; predições originais/modificadas e resumo agregado |
| `uv run dvc repro --single-item detect_drift` | exit 0; três comparações; duas features detectadas na modificada |
| `uv run dvc push -r dagshub simulate_production score_production detect_drift` (v1.0.1) | exit 0; **6 arquivos enviados** |
| `uv run dvc fetch -r dagshub simulate_production score_production detect_drift` (cache isolado v1.0.1) | exit 0; **6 arquivos recuperados**; status local/remote em sincronia |
| `uv run dvc push -r dagshub simulate_production score_production detect_drift` (v1.0.2) | exit 0; **5 novos objetos enviados**; dados comuns já existiam no remote |
| `uv run dvc fetch -r dagshub simulate_production score_production detect_drift` (cache isolado v1.0.2) | exit 0; **7 arquivos recuperados**; status local/remote em sincronia |
| `uv run dvc status -c -r dagshub simulate_production score_production detect_drift` | exit 0; cache/remote em sincronia após restaurar o cache DVC padrão |
| Reexecução `score_production` v1.0.2 | exit 0; os mesmos dois hashes de predição após persistir com 12 casas |
| `uv run dvc status` | somente `acquire` ausente/alterado pelo workbook não materializado; novos estágios sem divergência |
| Chromium headless / inspeção do HTML v1.0.2 | exit 0; comparações, proveniência, precisão e limitações presentes |
| `uv run pytest -q` | exit 0; **156 passed**, 6 warnings de depreciação do seaborn/Matplotlib |
| `uv run ruff check .` | exit 0; All checks passed |
| `uv run ruff format --check .` | exit 0; 80 files already formatted |
| `git diff --check` | exit 0; sem whitespace inválido |

### Pendências e próximos passos

1. Registrar que Concept Drift não é demonstrado; a docência avaliará o plano após a entrega, sem
   condicionar a execução ou o gate M2 Data Drift.
