#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
open "$DIR/dist/AccountingDemoXcodeApp.app"
