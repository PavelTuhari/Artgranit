#!/usr/bin/env bash
# Архив TexFlow = ровно то, что лежит в git (HEAD): код, тесты, документация MD и HTML,
# акт тестирования, презентация, скриншоты, образцы этикеток + запись в docs/TexFlow/.
#   tools/make_archive.sh [каталог-вывода]      → dist/texflow-<версия>-<коммит>.zip
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=$(git rev-parse --show-toplevel)
REL=$(git rev-parse --show-prefix); REL=${REL%/}
OUTDIR=${1:-dist}
mkdir -p "$OUTDIR"
VER=$(python3 -c "import texflow; print(texflow.__version__)")
SHA=$(git rev-parse --short HEAD)
if [ -n "$(git status --porcelain -- . "$REPO/docs/TexFlow")" ]; then
  echo "ВНИМАНИЕ: есть незакоммиченные изменения — в архив попадёт только версия из git (HEAD $SHA)"
fi
NAME="texflow-$VER-$SHA"
ZIP="$(cd "$OUTDIR" && pwd)/$NAME.zip"
git -C "$REPO" archive --format=zip --prefix="$NAME/" -o "$ZIP" HEAD "$REL" docs/TexFlow
echo "$ZIP"
unzip -l "$ZIP" | tail -1
