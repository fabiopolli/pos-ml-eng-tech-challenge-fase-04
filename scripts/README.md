# Scripts

As CLIs de fase 2 são instaladas como entry points do pacote e ficam documentadas em `README.md`:

- `credit-monitoring-simulate`: verifica os hashes M1, cria as cópias originais/modificadas e o
  manifesto imutável; opções de caminhos em `--help`.
- `credit-monitoring-score-production`: valida, carrega o modelo congelado e grava predições
  associadas aos IDs e resumos agregados; opções em `--help`.
- `credit-monitoring-drift`: valida os lotes, calcula as três comparações PSI e gera JSON/HTML;
  opções em `--help`.

O fluxo recomendado é executar os estágios `simulate_production`, `score_production` e
`detect_drift` do DVC individualmente após verificar a disponibilidade dos artefatos M1.
