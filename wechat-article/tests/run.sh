#!/usr/bin/env bash
# 跑 skill 自带的回归测试。
#
# 依赖：PyYAML、markdown、beautifulsoup4、cssutils、Pygments、requests。
# 解释器优先级：$WXARTICLE_PYTHON → ~/.wxarticle/venv/bin/python → python3
#
# 用法：bash tests/run.sh [unittest 参数…]

set -uo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SKILL_DIR"

pick_python() {
  if [ -n "${WXARTICLE_PYTHON:-}" ] && [ -x "${WXARTICLE_PYTHON}" ]; then
    echo "$WXARTICLE_PYTHON"; return
  fi
  local venv="${WXARTICLE_HOME:-$HOME/.wxarticle}/venv"
  if [ -x "$venv/bin/python" ]; then echo "$venv/bin/python"; return; fi
  if [ -x "$venv/Scripts/python.exe" ]; then echo "$venv/Scripts/python.exe"; return; fi
  echo "python3"
}

PY="$(pick_python)"
echo "解释器: $PY ($("$PY" -V 2>&1))"

if ! "$PY" -c "import yaml, markdown, bs4, cssutils, pygments, requests" 2>/dev/null; then
  echo "! 缺少运行依赖，先执行：bash install.sh" >&2
  echo "  或用 WXARTICLE_PYTHON=<带依赖的解释器> 再跑一次" >&2
  exit 3
fi

exec "$PY" -m unittest tests.test_contracts tests.test_cli "$@"
