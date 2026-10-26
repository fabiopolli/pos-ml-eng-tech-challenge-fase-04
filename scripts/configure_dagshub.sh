#!/usr/bin/env bash
# Configura o remote DagsHub do DVC a partir do arquivo .env local.
#
# O .env NUNCA é versionado (.gitignore) e os segredos ficam em
# .dvc/config.local, também ignorado. Este script apenas traduz as variáveis
# de ambiente em configuração do DVC; ele não imprime os valores.
#
# Uso:
#   scripts/configure_dagshub.sh [caminho_do_env]
#
# Depois de configurado:
#   uv run dvc remote list
#   uv run dvc push -r dagshub
#   uv run dvc pull -r dagshub   # em checkout/cache separado

set -euo pipefail

# O uv nem sempre esta no PATH do shell de login desta maquina.
if ! command -v uv >/dev/null 2>&1; then
  for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" /usr/local/bin/uv; do
    if [ -x "$candidate" ]; then
      PATH="$(dirname "$candidate"):$PATH"
      export PATH
      break
    fi
  done
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "uv nao encontrado no PATH. Instale o uv ou exporte o caminho de ~/.local/bin." >&2
  exit 1
fi

ENV_FILE="${1:-.env}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f "$ENV_FILE" ]; then
  echo "Arquivo $ENV_FILE nao encontrado. Copie .env.example para .env e preencha." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "./$ENV_FILE"
set +a

missing=()
for name in DAGSHUB_OWNER DAGSHUB_REPO DAGSHUB_TOKEN; do
  if [ -z "${!name:-}" ]; then
    missing+=("$name")
  fi
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "Variaveis ausentes ou vazias em $ENV_FILE: ${missing[*]}" >&2
  exit 1
fi

# A pagina do DagsHub mostra URLs como
# https://dagshub.com/<owner>/<repo>/src/branch/<branch>.
# O remote precisa apenas do slug do repositorio; se a URL colada for maior,
# extrai-se o slug e avisa-se.
normalize_repo_slug() {
  local value="$1" owner="$2"
  if [[ "$value" == *"://"* ]]; then
    local rest="${value#*://}"
    rest="${rest#*/}"
    local first="${rest%%/*}"
    local second
    second="$(printf '%s' "$rest" | cut -d/ -f2)"
    if [ "$first" != "$owner" ] || [ -z "$second" ]; then
      return 1
    fi
    printf '%s' "$second"
    return 0
  fi
  printf '%s' "$value"
}

REPO_SLUG="$(normalize_repo_slug "$DAGSHUB_REPO" "$DAGSHUB_OWNER")" || {
  echo "DAGSHUB_REPO nao corresponde a DAGSHUB_OWNER. Use o slug do repositorio" >&2
  echo "(por exemplo 'meu-repositorio') ou a URL completa do repositorio." >&2
  exit 1
}
if [ "$REPO_SLUG" != "$DAGSHUB_REPO" ]; then
  echo "DAGSHUB_REPO continha uma URL; usando o slug '$REPO_SLUG'."
  DAGSHUB_REPO="$REPO_SLUG"
fi
if [[ "$DAGSHUB_OWNER" == *"/"* || "$DAGSHUB_REPO" == *"/"* ]]; then
  echo "DAGSHUB_OWNER e DAGSHUB_REPO nao podem conter '/'." >&2
  exit 1
fi

if uv run dvc remote list | grep -q '^dagshub'; then
  uv run dvc remote modify dagshub url s3://dvc
else
  uv run dvc remote add dagshub s3://dvc
fi
uv run dvc remote modify dagshub endpointurl \
  "https://dagshub.com/${DAGSHUB_OWNER}/${DAGSHUB_REPO}.s3"
uv run dvc remote default dagshub

# Credenciais apenas na configuracao local; nunca no arquivo versionado.
# O DagsHub usa o mesmo token nos dois campos (guia oficial do DVC Storage).
uv run dvc remote modify dagshub --local access_key_id "${DAGSHUB_TOKEN}"
uv run dvc remote modify dagshub --local secret_access_key "${DAGSHUB_TOKEN}"

unset DAGSHUB_TOKEN

echo "Remote dagshub configurado para ${DAGSHUB_OWNER}/${DAGSHUB_REPO}."
uv run dvc remote list
echo "Confira o acesso antes de sincronizar: uv run dvc status -c -r dagshub"
