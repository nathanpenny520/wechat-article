#!/usr/bin/env bash
# wxart（wechat-article skill）安装脚本
#
# 做四件事：
#   1. 在状态目录建受管 venv 并安装运行依赖
#   2. 把本 skill 链接到各 agent 的 skills 目录
#   3. 清理指向本仓库旧路径的失效软链（只删断链，不动有效链接）
#   4. 跑 `wxart init` 生成配置模板、预设库与工作区兼容软链
#
# 幂等，可重复运行。用法：bash install.sh [--no-venv] [--no-link] [--clean-stale]

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_HOME="${WXARTICLE_HOME:-$HOME/.wxarticle}"
VENV_DIR="$STATE_HOME/venv"
PYTHON="${PYTHON:-python3}"

DO_VENV=1
DO_LINK=1
DO_CLEAN=1

for arg in "$@"; do
  case "$arg" in
    --no-venv) DO_VENV=0 ;;
    --no-link) DO_LINK=0 ;;
    --no-clean-stale) DO_CLEAN=0 ;;
    -h|--help)
      sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "未知参数: $arg" >&2; exit 2 ;;
  esac
done

info() { printf '\033[36m•\033[0m %s\n' "$1"; }
ok()   { printf '\033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '\033[33m!\033[0m %s\n' "$1" >&2; }
err()  { printf '\033[31m✗\033[0m %s\n' "$1" >&2; }

# ---------------------------------------------------------------- 1. Python 检查

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  err "找不到 $PYTHON；需要 Python 3.11+（可用 PYTHON=/path/to/python3 指定）"
  exit 1
fi

PY_OK="$("$PYTHON" -c 'import sys; print(1 if sys.version_info[:2] >= (3, 11) else 0)')"
if [ "$PY_OK" != "1" ]; then
  warn "$("$PYTHON" -V) 低于 3.11；wx 引擎要求 3.11+，部分能力可能不可用"
fi
ok "Python: $("$PYTHON" -V 2>&1) ($(command -v "$PYTHON"))"

# ---------------------------------------------------------------- 2. 受管 venv

if [ "$DO_VENV" = "1" ]; then
  mkdir -p "$STATE_HOME"
  if [ ! -x "$VENV_DIR/bin/python" ] && [ ! -x "$VENV_DIR/Scripts/python.exe" ]; then
    info "创建受管 venv: $VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
  fi
  VENV_PY="$VENV_DIR/bin/python"
  [ -x "$VENV_PY" ] || VENV_PY="$VENV_DIR/Scripts/python.exe"
  if [ -x "$VENV_PY" ]; then
    info "安装运行依赖…"
    "$VENV_PY" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
    if "$VENV_PY" -m pip install --quiet -r "$SKILL_DIR/scripts/requirements.txt"; then
      ok "依赖安装完成"
    else
      warn "依赖安装失败；手动重试：$VENV_PY -m pip install -r $SKILL_DIR/scripts/requirements.txt"
    fi
  else
    warn "venv 创建失败，跳过依赖安装"
  fi
else
  info "跳过 venv（--no-venv）"
fi

# ---------------------------------------------------------------- 3. 沙盒可用的 wxart 包装

BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
WRAPPER="$BIN_DIR/wxart"
if [ -x "$VENV_DIR/bin/python" ]; then
  RUNNER="$VENV_DIR/bin/python"
elif [ -x "$VENV_DIR/Scripts/python.exe" ]; then
  RUNNER="$VENV_DIR/Scripts/python.exe"
else
  RUNNER="$PYTHON"
fi
cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
exec "$RUNNER" "$SKILL_DIR/scripts/wxart.py" "\$@"
EOF
chmod +x "$WRAPPER"
ok "已安装 wxart 命令: $WRAPPER"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) warn "$BIN_DIR 不在 PATH；加一行到 shell 配置：export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

# ---------------------------------------------------------------- 4. 链接到各 agent

if [ "$DO_LINK" = "1" ]; then
  DESTS=()
  [ -n "${CLAUDE_SKILLS_DIR:-}" ] && DESTS+=("$CLAUDE_SKILLS_DIR") || DESTS+=("$HOME/.claude/skills")
  [ -n "${AGENTS_SKILLS_DIR:-}" ] && DESTS+=("$AGENTS_SKILLS_DIR") || DESTS+=("$HOME/.agents/skills")
  [ -d "$HOME/.codex" ] && DESTS+=("$HOME/.codex/skills")
  [ -d "$HOME/.openclaw" ] && DESTS+=("$HOME/.openclaw/skills")

  for dest in "${DESTS[@]}"; do
    [ -d "$(dirname "$dest")" ] || continue
    mkdir -p "$dest"
    # 防呆：目标目录本身是指回本仓库的软链时不动
    if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$SKILL_DIR" ]; then
      warn "跳过 $dest（它就是本仓库的软链）"
      continue
    fi
    if [ -e "$dest/wechat-article" ] && [ ! -L "$dest/wechat-article" ]; then
      warn "跳过 $dest/wechat-article（已存在真实目录，请手工处理）"
      continue
    fi
    ln -sfn "$SKILL_DIR" "$dest/wechat-article"
    ok "已链接: $dest/wechat-article"
  done

  # 清理指向本仓库旧路径的失效软链（只删断链）
  if [ "$DO_CLEAN" = "1" ]; then
    for dest in "${DESTS[@]}"; do
      [ -d "$dest" ] || continue
      for entry in "$dest"/*; do
        [ -L "$entry" ] || continue
        [ -e "$entry" ] && continue            # 有效链接不动
        name="$(basename "$entry")"
        case "$name" in
          wewrite|wewrite-*)
            rm -f "$entry"
            warn "已删除失效软链: $dest/$name"
            ;;
        esac
      done
    done
  fi
else
  info "跳过链接（--no-link）"
fi

# ---------------------------------------------------------------- 5. 初始化

info "初始化状态目录与配置模板…"
"$RUNNER" "$SKILL_DIR/scripts/wxart.py" init --no-venv || warn "init 未完全成功，请手动跑：wxart init"

# ---------------------------------------------------------------- 6. 自检

echo
info "自检…"
"$RUNNER" "$SKILL_DIR/scripts/wxart.py" doctor || true

cat <<'EOF'

下一步：
  1. 填 ~/.wxarticle/config.yaml 的 article_category / target_reader / default_author
  2. 需要发布或生图时填 ~/.wxarticle/.env
  3. 对 agent 说「写一篇公众号文章」开始

安装位置：
EOF
echo "  skill : $SKILL_DIR"
echo "  状态  : $STATE_HOME"
echo "  命令  : $WRAPPER"
