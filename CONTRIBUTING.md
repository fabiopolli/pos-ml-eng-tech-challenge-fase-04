# Como contribuir

1. Atualize a `main` e crie uma branch `<tipo>/<integrante>/<descricao-curta>`.
2. Consulte `docs/CHECKLIST.md` e associe a mudança a uma entrega do plano.
3. Faça commits semânticos e pequenos, como `feat: add credit data contract`.
4. Rode `uv run ruff format --check .`, `uv run ruff check .` e `uv run pytest`.
5. Abra PR com objetivo, validações executadas, evidências e impacto no checklist.
6. Solicite revisão de outro integrante.

Não envie datasets ou modelos binários diretamente ao Git: use DVC/DagsHub para objetos
autorizados e versione ponteiros/metadados no Git. Não envie informações pessoais, segredos,
ambientes virtuais, bancos do MLflow ou relatórios locais sensíveis. Não faça force-push na `main`.

Alterações exclusivamente documentais devem verificar links, consistência com o plano/enunciado
e `git diff --check`; testes/lint de código são necessários quando a mudança afeta execução.
