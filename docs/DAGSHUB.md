# DagsHub: versionamento remoto com DVC

## Papel no projeto

DagsHub Storage será o remote de objetos do DVC para armazenar datasets e artefatos do pipeline,
incluindo o modelo produzido pelo estágio `train`. O GitHub continua sendo o remoto canônico de
código e documentação. Arquivos ponteiro `.dvc`, `dvc.yaml`, `dvc.lock` e configurações não
secretas do DVC são versionados no Git; conteúdos grandes ficam no remote DagsHub.

O repositório já rastreia o CSV bruto e declara os datasets preparados e modelos como saídas DVC.
No estado atual, `.dvc/config` ainda não define um remote. A integração só estará ativa depois que
o projeto GitHub for conectado/importado no DagsHub e as credenciais forem configuradas localmente.

## Configuração inicial (por integrante)

1. Conectar o repositório GitHub existente ao DagsHub seguindo o
   [guia oficial de conexão](https://dagshub.com/docs/quick_start/connect_existing_project/).
2. Na página do repositório DagsHub, abrir a opção de configuração de DVC Storage e copiar os
   valores exibidos para o remote daquele repositório. Não presumir owner, slug, endpoint ou token.
3. Dentro deste checkout, configurar o remote compartilhável e o endpoint informado pelo DagsHub:

   ```bash
   DAGSHUB_OWNER='owner-do-repositorio'
   DAGSHUB_REPO='nome-do-repositorio'
   uv run dvc remote add -d dagshub s3://dvc
   uv run dvc remote modify dagshub endpointurl "https://dagshub.com/${DAGSHUB_OWNER}/${DAGSHUB_REPO}.s3"
   ```

   Se o remote já existir, atualize-o em vez de tentar criá-lo novamente:

   ```bash
   uv run dvc remote modify dagshub url s3://dvc
   uv run dvc remote default dagshub
   ```

4. Armazenar `access_key_id` e `secret_access_key` localmente, com os valores/token fornecidos pelo
   DagsHub. O `--local` grava em `.dvc/config.local`, que não deve ser commitado:

   ```bash
   read -rsp 'DagsHub access key: ' DAGSHUB_ACCESS_KEY_ID; printf '\n'
   uv run dvc remote modify dagshub --local access_key_id "$DAGSHUB_ACCESS_KEY_ID"
   unset DAGSHUB_ACCESS_KEY_ID
   read -rsp 'DagsHub secret key: ' DAGSHUB_SECRET_ACCESS_KEY; printf '\n'
   uv run dvc remote modify dagshub --local secret_access_key "$DAGSHUB_SECRET_ACCESS_KEY"
   unset DAGSHUB_SECRET_ACCESS_KEY
   ```

   Nunca passe tokens em commits, `.env.example`, documentação, logs ou configuração DVC
   compartilhada. As linhas `read` solicitam os valores sem exibi-los nem incluí-los no histórico
   do shell.

## Sincronizar dados e modelos

Após adicionar/atualizar arquivos rastreados pelo DVC e commitar seus ponteiros/`dvc.lock` no Git:

```bash
uv run dvc push -r dagshub
```

Em um checkout autorizado, recuperar os objetos necessários para o commit atual:

```bash
uv run dvc pull -r dagshub
```

O fluxo continua reproduzível localmente com `uv run dvc repro`; DagsHub fornece armazenamento e
visualização dos arquivos/pipelines DVC, não compute para treinar o modelo. A equipe deve
sincronizar os metadados Git correspondentes aos objetos DVC e evitar misturar ponteiros de um
commit com objetos de outra versão.

## Controles e verificação

- Só enviar dados públicos/aprovados para compartilhamento e compatíveis com os termos da fonte.
- Não adicionar datasets ou modelos binários diretamente ao Git; o Git recebe apenas os ponteiros
  gerados pelo DVC e metadados do pipeline.
- Manter separados dados de referência e dados de produção simulados também no versionamento.
- Não versionar tokens, `.dvc/config.local`, dados pessoais, segredos ou artefatos não aprovados.
- Antes da primeira sincronização, confirmar que o repositório DagsHub existe, o remote aponta para
  ele, os objetos DVC selecionados estão autorizados e o acesso funciona.
- Verificar configuração com `uv run dvc remote list`, integridade local com `uv run dvc status` e
  disponibilidade do cache remoto com `uv run dvc status -c`.

## Referências

- [DagsHub — integração DVC e Storage](https://dagshub.com/docs/integration_guide/dvc/)
- [DagsHub — conectar repositório existente](https://dagshub.com/docs/quick_start/connect_existing_project/)
- [DagsHub — versionar dados](https://dagshub.com/docs/quick_start/version_data/)

Documentação consultada em 2026-10-26. Valores de remote e credenciais são específicos da conta
e do repositório e devem ser copiados da interface do DagsHub.
