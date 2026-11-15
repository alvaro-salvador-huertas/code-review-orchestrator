# Publicar v1.2.0 después de revisar y fusionar la PR

Este procedimiento queda **pendiente**. La PR de preparación no crea tags ni
releases. Ejecutarlo solo después de aprobar sus [notas](notas-v1.2.0.md), revisar
la evidencia de su SHA y fusionarla en `main`. No requiere modificar el checkout
original: usar el worktree de preparación o un clon de publicación limpio.

## Comprobar la base que se va a publicar

Desde la raíz del repositorio, en Bash con Git y `gh` autenticado para publicar:

```bash
set -euo pipefail
repo=alvaro-salvador-huertas/code-review-orchestrator
release_branch=release/v1.2.0
test -z "$(git status --porcelain)"
git fetch origin --tags

# Identificar una única PR fusionada de esta rama, sin usar el main móvil como tag.
release_pr=$(gh pr list --repo "$repo" --head "$release_branch" --base main \
  --state merged --json number --jq 'if length == 1 then .[0].number else error("Se esperaba una PR fusionada") end')
test "$(gh pr view "$release_pr" --repo "$repo" --json state --jq .state)" = MERGED
release_head=$(gh pr view "$release_pr" --repo "$repo" --json headRefOid --jq .headRefOid)
release_sha=$(gh pr view "$release_pr" --repo "$repo" --json mergeCommit --jq .mergeCommit.oid)
git merge-base --is-ancestor "$release_sha" origin/main
printf 'HEAD revisado: %s\nMerge a publicar: %s\n' "$release_head" "$release_sha"

gh pr checks "$release_pr" --repo "$repo" --watch
gh run list --repo "$repo" --commit "$release_head" --event pull_request \
  --json databaseId,headSha,status,conclusion,url
gh run list --repo "$repo" --commit "$release_sha" --event push \
  --json databaseId,headSha,status,conclusion,url
```

Revisar los resultados antes de continuar. En el HEAD de la PR tienen que pasar
`tests` y **Integración real de Podman rootless**, con 13 integraciones y cero
omisiones, sin recursos residuales. Esperar también a `tests` del push del merge
con `gh run watch ID --repo "$repo" --exit-status`; inspeccionar los jobs con
`gh run view ID --repo "$repo"`. En ese push el job Podman se omite por diseño.
No confundir esa omisión con la evidencia real de la PR. Detener la publicación
ante cualquier fallo, ejecución ausente o SHA distinto del revisado.

## Crear y verificar el tag

Después de la comprobación anterior, conservar las variables en la misma sesión:

```bash
if git show-ref --verify --quiet refs/tags/v1.2.0; then
  echo 'El tag local v1.2.0 ya existe; detenerse y revisar.' >&2
  exit 1
fi
remote_tag=$(git ls-remote --tags origin refs/tags/v1.2.0)
if test -n "$remote_tag"; then
  echo 'El tag remoto v1.2.0 ya existe; detenerse y revisar.' >&2
  exit 1
fi
git tag -a v1.2.0 "$release_sha" -m 'v1.2.0 — Revisión local y evaluación aislada'
test "$(git rev-parse 'v1.2.0^{commit}')" = "$release_sha"
git push origin refs/tags/v1.2.0
test "$(git ls-remote origin 'refs/tags/v1.2.0^{}' | cut -f1)" = "$release_sha"
```

El tag es anotado y apunta al merge exacto, aunque `main` haya avanzado después.
No se fuerza, mueve ni recrea un tag existente. El workflow actual no se dispara
por tags ni publica releases automáticamente.

## Preparar, revisar y publicar la release en GitHub

Extraer las notas del mismo commit y convertir sus enlaces relativos en enlaces
al árbol publicado, para que funcionen también fuera de `docs/`:

```bash
notes_file=$(mktemp /tmp/notas-v1.2.0.XXXXXX.md)
git show "$release_sha:docs/notas-v1.2.0.md" > "$notes_file"
python3 -B - "$notes_file" "$repo" "$release_sha" <<'PYTHON'
import re, sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit
path, repo, sha = sys.argv[1:]
base = f'https://github.com/{repo}/blob/{sha}/docs/'
def absolute(match):
    label, target = match.groups()
    return f'[{label}]({target if urlsplit(target).scheme or target.startswith("#") else urljoin(base, target)})'
p = Path(path)
p.write_text(re.sub(r'\[([^\]]+)\]\(([^\s)]+)\)', absolute, p.read_text()))
PYTHON
gh release create v1.2.0 --repo "$repo" --verify-tag --target "$release_sha" \
  --title 'v1.2.0 — Revisión local y evaluación aislada' --notes-file "$notes_file" --draft
gh release view v1.2.0 --repo "$repo" --json tagName,targetCommitish,isDraft,body,url
```

Revisar el borrador y sus enlaces antes de publicar. Las notas conservan el
contexto de preparación; no atribuyen al tag las mediciones de PR anteriores.
Si ya existe una release para ese tag, detenerse e inspeccionarla, sin duplicarla.
Solo tras esa revisión:

```bash
gh release edit v1.2.0 --repo "$repo" --draft=false --latest
gh release view v1.2.0 --repo "$repo" \
  --json tagName,targetCommitish,isDraft,isPrerelease,publishedAt,url
test "$(gh api "repos/$repo/releases/latest" --jq .tag_name)" = v1.2.0
git ls-remote origin 'refs/tags/v1.2.0^{}'
rm -- "$notes_file"
```

Confirmar release publicada estable y tag resuelto al merge conservado en
`release_sha`. Después, preparar otro cambio documental que identifique v1.2.0
como publicada en el README, sin alterar el tag ni su árbol. La incorporación
de cambios al producto y la publicación siguen bajo decisión humana.
