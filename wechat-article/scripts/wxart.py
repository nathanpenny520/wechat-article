#!/usr/bin/env python3
"""wxart —— 微信推文制作统一 CLI。

一个命令覆盖「选题 → 写作 → 审稿 → 排版 → 配图 → 发布」以及学习飞轮、数据复盘、
多平台改写、业务资料库。内部把两个上游引擎收敛到同一套路径、配置与状态之上：

- **wx 引擎**（vendored `wewrite`）：18 套主题排版、微信兼容自动修复、HTML 校验、
  质量评分、热点/搜索/SEO、学习飞轮、数据复盘、多平台原创度。
- **aws 引擎**（vendored `wechat-article-skills`）：模版 × 配色两层排版 + 版式组件、
  封面/配图生成与确定性检查、微信草稿与发布（含封面裁剪框）、业务资料库与预设包。

用法：`wxart <命令> [参数…]`，任意命令加 `--help` 看细节。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wxenv  # noqa: E402

VERSION_FILE = wxenv.SKILL_ROOT / "VERSION"


def version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


# ------------------------------------------------------------------ 命令表

AWS = wxenv.AWS_DIR

#: 命令 → (引擎, 目标, 一句话说明)
#: 引擎 `w` = wewrite 子命令；`a` = aws 脚本路径（相对 scripts/）；`n` = 本模块原生实现
COMMANDS: dict[str, tuple[str, str, str]] = {
    # —— 环境与工作区 ——
    "doctor": ("n", "", "环境 + 配置自检（合并两套上游自检）"),
    "init": ("n", "", "初始化工作区：状态目录、配置模板、预设库、兼容软链"),
    "env": ("n", "", "打印解析后的路径、配置来源与依赖状态"),
    "home": ("n", "", "打印状态目录"),
    "migrate": ("n", "", "从 ~/.wewrite 与 .aws-article 迁移旧状态"),
    # —— 选题 ——
    "hotspots": ("w", "hotspots", "多平台实时热点（微博/头条/百度）"),
    "search-articles": ("w", "search-articles", "搜狗微信搜索：垂类高频需求"),
    "seo": ("w", "seo", "SEO 关键词量化评分（百度/360）"),
    # —— 写作 ——
    "draft": ("a", "aws/aws-wechat-article-writing/scripts/write.py", "调写作模型出稿 / 只出提示词 / 正文校验 / 剥离溯源"),
    "llm-write": ("w", "llm-write", "混合路由写作（可交给独立写作模型）"),
    "score": ("w", "score", "写作质量评分（11 项机械检测）"),
    "content-eval": ("w", "content-eval", "汇总编辑判断与初稿修改幅度"),
    "sources": ("w", "sources", "文章事实来源账本"),
    # —— 排版 ——
    "format": ("e", "format", "Markdown → 微信 HTML（默认 wx 引擎，--engine aws 走模版×配色+组件）"),
    "preview": ("w", "preview", "wx 引擎排版与本地预览（18 主题）"),
    "themes": ("w", "themes", "列出 wx 引擎主题"),
    "gallery": ("w", "gallery", "浏览器内并排预览全部主题"),
    "validate": ("w", "validate", "HTML 微信兼容性校验"),
    # —— 配图 ——
    "image": ("e", "image", "生成封面/正文配图（默认 aws 引擎，--engine wx 走 wx 生图）"),
    "image-post": ("w", "image-post", "小绿书 / 图片帖（横滑轮播）"),
    "image-prepare": ("a", "aws/aws-wechat-article-images/scripts/user_image_prepare.py", "用户自备图片预处理"),
    "image-check": ("a", "aws/aws-wechat-article-images/scripts/image_create.py", "出图后确定性检查（尺寸/近单色）"),
    # —— 发布 ——
    "publish": ("e", "publish", "推送公众号草稿箱/发布（默认 aws 引擎，--engine wx 走 wx 发布）"),
    "article-init": ("a", "aws/aws-wechat-article-publish/scripts/article_init.py", "初始化本篇 article.yaml（勿手写）"),
    "getdraft": ("a", "aws/aws-wechat-article-publish/scripts/getdraft.py", "拉取草稿箱内容"),
    # —— 学习飞轮 ——
    "learn-edits": ("w", "learn-edits", "从人工修改中学习写作偏好"),
    "learn-theme": ("w", "learn-theme", "从公众号文章 URL 学一套排版主题"),
    "exemplar": ("w", "exemplar", "范文风格库（导入 / 列出）"),
    "fetch-article": ("w", "fetch-article", "公众号文章 URL → Markdown"),
    "build-playbook": ("w", "build-playbook", "从历史语料生成 playbook"),
    # —— 复盘与分发 ——
    "stats": ("w", "stats", "回填公众号阅读数据并给选题建议"),
    "similarity": ("w", "similarity", "多平台版本原创度检查"),
    # —— 业务资料库与预设包 ——
    "presets": ("a", "aws/aws-wechat-article-assets/scripts/import_presets_aws.py", "导入/导出 .aws 预设包"),
    "product-image": ("a", "aws/aws-wechat-article-assets/scripts/product_image_ingest.py", "业务图入库到 products/"),
    # —— 任务管理 ——
    "run": ("w", "run", "文章任务：开始/恢复/更新/封存/授权"),
    # —— 安全栅栏 ——
    "guard": ("n", "", "容器相容性检查与 HTML 微信兼容门禁（两个引擎通用）"),
    "cover": ("n", "", "没有生图模型时，本地合成「纯色大字」封面（确定性，零 API）"),
    "preview-page": ("n", "", "把排版产物放进 375px 手机宽度预览页，并排对比多个主题"),
    "shot": ("n", "", "排版产物截成手机宽度 PNG（核对观感，含多主题对照图）"),
    "deco": ("n", "", "给正文加纸纹底 / 花边框（底图上传图床再写进 background-image）"),
    "redraft": ("n", "", "原地更新草稿箱里的一条草稿（换版式不新建）"),
    # —— 上游自检 ——
    "validate-env": ("a", "aws/aws-wechat-article-main/scripts/validate_env.py", "aws 侧配置校验"),
}

GROUPS: list[tuple[str, list[str]]] = [
    ("环境与工作区", ["doctor", "init", "env", "home", "migrate"]),
    ("选题", ["hotspots", "search-articles", "seo"]),
    ("写作", ["draft", "llm-write", "score", "content-eval", "sources"]),
    ("排版", ["format", "preview", "preview-page", "shot", "deco", "themes", "gallery", "validate"]),
    ("配图", ["image", "cover", "image-post", "image-prepare", "image-check"]),
    ("发布", ["publish", "redraft", "article-init", "getdraft"]),
    ("学习飞轮", ["learn-edits", "learn-theme", "exemplar", "fetch-article", "build-playbook"]),
    ("复盘与分发", ["stats", "similarity"]),
    ("业务资料库", ["presets", "product-image"]),
    ("任务与自检", ["run", "guard", "validate-env"]),
]

# 需要 `--engine` 开关的命令及其两个引擎实现
ENGINE_SWITCH = {
    "format": {
        "wx": ("w", "preview"),
        "aws": ("a", "aws/aws-wechat-article-formatting/scripts/format.py"),
    },
    "image": {
        "wx": ("w", "image-gen"),
        "aws": ("a", "aws/aws-wechat-article-images/scripts/image_create.py"),
    },
    "publish": {
        "wx": ("w", "publish"),
        "aws": ("a", "aws/aws-wechat-article-publish/scripts/publish.py"),
    },
}

DEFAULT_ENGINE = {"format": "wx", "image": "aws", "publish": "aws"}


# ------------------------------------------------------------------ 输出


def _c(text: str, code: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return text
    return f"\033[{code}m{text}\033[0m"


def info(msg: str) -> None:
    print(_c("• ", "36") + msg)


def warn(msg: str) -> None:
    print(_c("! ", "33") + msg, file=sys.stderr)


def err(msg: str) -> None:
    print(_c("✗ ", "31") + msg, file=sys.stderr)


def ok(msg: str) -> None:
    print(_c("✓ ", "32") + msg)


def usage() -> str:
    lines = [f"wxart {version()} — 微信推文制作统一 CLI", f"状态目录: {wxenv.state_home()}", ""]
    lines.append("用法: wxart <命令> [参数…]   （命令后加 --help 看细节）")
    lines.append("")
    for title, names in GROUPS:
        lines.append(f"{title}:")
        for name in names:
            kind, target, desc = COMMANDS[name]
            suffix = ""
            if name in ENGINE_SWITCH:
                suffix = f"  [--engine {'|'.join(ENGINE_SWITCH[name])}]"
            lines.append(f"  {name:<16}{desc}{suffix}")
        lines.append("")
    lines += [
        "环境变量:",
        "  WXARTICLE_HOME        状态目录（默认 ~/.wxarticle）",
        "  WXARTICLE_WORKSPACE   工作区根（默认自动探测）",
        "  WXARTICLE_CONFIG_DIR  强制指定配置目录",
        "",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------ 运行时准备


def maybe_reexec_into_venv() -> None:
    """若受管 venv 存在且当前解释器缺依赖，静默切换过去。"""
    if os.environ.get("WXARTICLE_NO_REEXEC"):
        return
    vp = wxenv.venv_python()
    try:
        if not vp.exists() or Path(sys.executable).resolve() == vp.resolve():
            return
    except OSError:
        return
    if not wxenv.missing_modules():
        return
    os.execv(str(vp), [str(vp), str(Path(__file__).resolve()), *sys.argv[1:]])


def dispatch_wxengine(command: str, args: list[str]) -> int:
    wxenv.sys_path_prelude()
    missing = wxenv.missing_modules()
    if missing:
        err(f"缺少运行依赖：{', '.join(missing)}")
        err("先运行 `wxart init`（会建受管 venv 并安装依赖），或 `pip3 install -r scripts/requirements.txt`")
        return 3
    import wxengine.cli as wx_cli

    old = sys.argv
    sys.argv = ["wxart", command, *args]
    try:
        wx_cli.main()
    finally:
        sys.argv = old
    return 0


def dispatch_aws(script_rel: str, args: list[str]) -> int:
    import runpy

    script = wxenv.SKILL_ROOT / "scripts" / script_rel
    if not script.exists():
        err(f"找不到脚本：{script}")
        return 3
    old_argv, old_cwd = sys.argv, Path.cwd()
    wxenv.ensure_config_dir()
    # 上游脚本按 CWD 找 .aws-article；在真正执行的目录里也建一份兼容入口，
    # 这样既不改变传入的相对路径，也能读到同一份配置。
    wxenv.ensure_config_link(old_cwd)
    wxenv.ensure_env_link(old_cwd)
    missing = [m for m in wxenv.missing_modules() if m in ("yaml", "PIL")]
    if "yaml" in missing:
        err("缺少 PyYAML，先运行 `wxart init` 或 `pip3 install pyyaml`")
        return 3
    sys.argv = [script.name, *args]
    try:
        try:
            runpy.run_path(str(script), run_name="__main__")
        except SystemExit as exc:  # 上游脚本用 sys.exit 表达结果
            code = exc.code
            return code if isinstance(code, int) else (0 if code is None else 1)
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
    return 0


# ------------------------------------------------------------------ 原生命令


def cmd_home(_: list[str]) -> int:
    print(wxenv.state_home())
    return 0


def cmd_env(args: list[str]) -> int:
    import json

    snap = wxenv.describe()
    if "--json" in args:
        print(json.dumps(snap, ensure_ascii=False, indent=2))
        return 0
    for key, val in snap.items():
        print(f"{key:<22}{val}")
    return 0


def cmd_doctor(args: list[str]) -> int:
    """合并 wewrite `diagnose` 与 aws `validate_env` 的自检。"""
    import json

    as_json = "--json" in args
    snapshot = wxenv.describe()
    checks: list[dict] = []

    def add(name: str, level: str, detail: str, hint: str = "") -> None:
        checks.append({"check": name, "level": level, "detail": detail, "hint": hint})

    # 1) Python 与依赖
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 11):
        add("python", "ok", f"{sys.version.split()[0]}")
    else:
        add("python", "error", f"{sys.version.split()[0]} 过低", "需要 Python 3.11+（wx 引擎要求）")
    miss = snapshot["missing_modules"]
    if not miss:
        add("deps", "ok", "全部运行依赖可用")
    elif snapshot["venv_exists"]:
        add("deps", "error", f"当前解释器缺少 {', '.join(miss)}", "用 `wxart` 启动会自动切到受管 venv，或加 --engine 检查")
    else:
        add("deps", "warn", f"缺少 {', '.join(miss)}", "运行 `wxart init` 建立受管 venv 并安装依赖")

    # 2) 配置
    if snapshot["config_file_exists"]:
        add("config", "ok", snapshot["config_file"])
    else:
        add("config", "warn", "尚无 config.yaml", "运行 `wxart init` 生成模板")

    cfg = wxenv.load_config()
    for field in ("article_category", "target_reader", "default_author"):
        val = str(cfg.get(field) or "").strip()
        if val:
            add(f"config.{field}", "ok", val)
        else:
            add(f"config.{field}", "warn", "未填写", "写入 config.yaml；审稿与写作会用默认值")

    author = str((cfg.get("wechat") or {}).get("author") or "").strip()
    add("config.wechat.author", "ok" if author else "warn", author or "未填写", "" if author else "签名与作者信息使用默认值")

    env = wxenv.load_env()
    has_appid = bool(env.get("WECHAT_1_APPID") or (cfg.get("wechat") or {}).get("appid"))
    has_secret = bool(env.get("WECHAT_1_APPSECRET") or (cfg.get("wechat") or {}).get("secret"))
    if has_appid and has_secret:
        add("wechat.credentials", "ok", "已配置")
    else:
        add("wechat.credentials", "warn", "未配置微信凭证", "仅发布需要；写作/排版/配图不受影响")
    add(
        "models.writing",
        "ok" if (env.get("WRITING_MODEL_API_KEY") or (cfg.get("writing_model") or {}).get("model")) else "warn",
        "已配置" if (env.get("WRITING_MODEL_API_KEY") or (cfg.get("writing_model") or {}).get("model")) else "未配置（不阻断，由当前 Agent 代写）",
    )
    add(
        "models.image",
        "ok" if (env.get("IMAGE_MODEL_API_KEY") or (cfg.get("image_model") or {}).get("model") or (cfg.get("image") or {}).get("api_key")) else "warn",
        "已配置" if (env.get("IMAGE_MODEL_API_KEY") or (cfg.get("image_model") or {}).get("model") or (cfg.get("image") or {}).get("api_key")) else "未配置（不阻断，可只出提示词）",
    )

    # 3) 状态与工作区
    add("state_home", "ok" if snapshot["state_home_exists"] else "warn", snapshot["state_home"], "" if snapshot["state_home_exists"] else "运行 `wxart init`")
    link_kind = snapshot["aws_link_kind"]
    if link_kind in ("symlink", "dir"):
        add("workspace.aws_link", "ok", f"{snapshot['aws_link']} ({link_kind})")
    elif link_kind == "broken":
        add("workspace.aws_link", "warn", f"{snapshot['aws_link']} 是断链",
            "运行 `wxart init` 重新指向当前状态目录")
    else:
        add("workspace.aws_link", "warn", "缺失", "运行 `wxart init` 建立 .aws-article 兼容软链")
    if cfg.get("publish_method") in (None, "draft", "published", "none"):
        add("publish_method", "ok", str(cfg.get("publish_method") or "draft（默认）"))
    else:
        add("publish_method", "error", f"非法值 {cfg.get('publish_method')}", "只能是 draft / published / none")

    if snapshot["legacy_state_home_exists"] and not snapshot["state_home_exists"]:
        add("legacy", "warn", f"发现旧目录 {snapshot['legacy_state_home']}", "运行 `wxart migrate` 迁移")

    # 4) 上游自检
    for label, rel in (
        ("upstream.wxengine", "wxengine/commands/diagnose.py"),
        ("upstream.aws", "aws/aws-wechat-article-main/scripts/validate_env.py"),
    ):
        add(label, "ok", "存在" if (wxenv.SKILL_ROOT / "scripts" / rel).exists() else "缺失")

    errors = [c for c in checks if c["level"] == "error"]
    warns = [c for c in checks if c["level"] == "warn"]

    if as_json:
        print(json.dumps({"snapshot": snapshot, "checks": checks,
                          "errors": len(errors), "warnings": len(warns)}, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    print(_c(f"wxart doctor {version()}", "1"))
    for c in checks:
        mark = {"ok": _c("✓", "32"), "warn": _c("!", "33"), "error": _c("✗", "31")}[c["level"]]
        print(f"  {mark} {c['check']:<24}{c['detail']}")
        if c["hint"] and c["level"] != "ok":
            print(f"      → {c['hint']}")
    print()
    if errors:
        print(_c(f"存在 {len(errors)} 项阻塞问题", "31"))
        return 1
    if warns:
        print(_c(f"{len(warns)} 项提示（不阻断写作/排版/配图）", "33"))
    else:
        print(_c("全部通过", "32"))
    return 0


CONFIG_TEMPLATE = """# wxart 账号配置（合并 wewrite 与 wechat-article-skills 两套字段）
# 位置：{config_path}
# 密钥不要写这里，写同目录的 .env（或仓库根 aws.env）。

# —— 账号定位（写稿与审稿的硬约束，建议填满）——
article_category: ""          # 你的账号写什么领域
target_reader: ""             # 写给谁看
default_author: ""            # 默认署名

# —— 写作风格入口（wx 引擎）——
# 可选人格：midnight-friend / warm-editor / industry-observer / sharp-journalist
#          / cold-analyst / humor-storyteller / tech-coder；也可放 ~/.wxarticle/personas/
writing_persona: midnight-friend
theme: professional-clean     # wx 引擎默认排版主题（wxart themes 查看）

# —— 发布行为 ——
publish_method: draft         # draft=只写草稿箱 / published=提交发布 / none=不接微信
wechat_accounts: 1            # 账号槽位数量（槽位名用 wechat_1_name）
wechat_publish_slot: 1        # 本篇默认槽位，对应 .env 里的 WECHAT_<N>_*
drafts_root: drafts           # 本篇目录根（相对工作区）
published_root: published     # 发布后归档根
cover_aspect: "2.35:1"        # 封面比例（信息流首图）

# —— 本篇默认预设：wxart init 后由 assets/presets 提供候选 ——
default_structure: []
default_closing_block: []
default_title_style: []
default_format_preset: []     # aws 引擎模版名（手账/技术/活力/硬朗/书卷/亲和/杂志/资讯）
default_format_scheme: []     # aws 引擎配色名
default_cover_image_style: []
default_article_image_style: []   # 保持多元素候选池：正文每个图位各选一个
default_sticker_style: []

# —— 模型端点（可选；不配则由当前 Agent 直接写/画）——
writing_model:
  base_url: ""
  model: ""
  provider: ""                # openai | volcengine | qwen | gemini
image_model:
  base_url: ""
  model: ""
  provider: ""

# —— wx 引擎兼容命名空间（等价写法，二者任一即可）——
wechat:
  appid: ""
  secret: ""
  author: ""
image:
  provider: ""
  api_key: ""
  model: ""
"""

ENV_TEMPLATE = """# wxart 密钥文件（不要提交到 git）
# 只放密钥与凭证；非密钥配置一律写 config.yaml。

# 写稿模型（可选）
WRITING_MODEL_API_KEY=

# 画图模型（可选；很多 coding plan 不支持生图，需要单独配）
IMAGE_MODEL_API_KEY=

# 微信公众号（仅发布需要）
WECHAT_1_APPID=
WECHAT_1_APPSECRET=

# wx 引擎兼容命名（与上面等价，填一组即可）
WECHAT_APPID=
WECHAT_SECRET=
"""


def cmd_init(args: list[str]) -> int:
    create_venv = "--no-venv" not in args
    home = wxenv.ensure_state_home()
    ok(f"状态目录: {home}")

    cfg_path = home / "config.yaml"
    if cfg_path.exists():
        info(f"配置已存在，保留: {cfg_path}")
    else:
        cfg_path.write_text(CONFIG_TEMPLATE.format(config_path=cfg_path), encoding="utf-8")
        ok(f"已生成配置模板: {cfg_path}")

    env_path = home / ".env"
    if env_path.exists():
        info(f"密钥文件已存在，保留: {env_path}")
    else:
        env_path.write_text(ENV_TEMPLATE, encoding="utf-8")
        ok(f"已生成密钥模板: {env_path}")

    target = wxenv.ensure_config_dir()
    link = wxenv.aws_link()
    if link.is_symlink():
        ok(f"兼容软链就绪: {link} → {os.readlink(link)}")
    elif link.is_dir() and link != target:
        info(f"检测到真实 {wxenv.AWS_LINK_NAME}/，按老用户方式沿用")

    # 预设库
    presets = home / "presets"
    seeded = _seed_presets(presets)
    if seeded:
        ok(f"已铺默认预设 {seeded} 项: {presets}")

    if create_venv:
        _bootstrap_venv()
    else:
        info("跳过 venv（--no-venv）")

    missing = [m for m in wxenv.missing_modules() if m != "PIL"]
    if not missing:
        ok("运行依赖就绪")
    else:
        warn(f"当前解释器仍缺 {', '.join(missing)}；用 `wxart` 启动会自动切到受管 venv")
    print()
    print("下一步：")
    print(f"  1. 填 {cfg_path} 的账号定位三项（article_category / target_reader / default_author）")
    print(f"  2. 需要发布或生图时，填 {env_path}")
    print("  3. 跑 `wxart doctor` 确认")
    return 0


def _seed_presets(dest: Path) -> int:
    """把内置预设铺到配置目录，作为用户可改的默认候选。

    上游的 `custom_* > default_*` 约定不变：这里铺的是"内置默认"，
    用户在工作区 `.wxarticle/presets/<目录>/` 放同名文件即可覆盖。
    """
    import shutil

    main_presets = wxenv.AWS_DIR / "aws-wechat-article-main" / "references" / "presets"
    fmt = wxenv.AWS_DIR / "aws-wechat-article-formatting" / "references" / "presets"
    comp = wxenv.AWS_DIR / "aws-wechat-article-formatting" / "references" / "components"
    count = 0

    def copy_tree(src: Path, dst: Path) -> int:
        n = 0
        if not src.exists():
            return 0
        for item in sorted(src.rglob("*")):
            if not item.is_file():
                continue
            rel = item.relative_to(src)
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(item, target)
                n += 1
        return n

    # 7 类文本预设
    if main_presets.exists():
        for sub in sorted(p for p in main_presets.iterdir() if p.is_dir()):
            count += copy_tree(sub, dest / sub.name)
    # 排版：模版 × 配色
    count += copy_tree(fmt / "templates", dest / "formatting")
    count += copy_tree(fmt / "themes", dest / "formatting")
    # 版式组件（用户可在 presets/components/ 放同名文件覆盖）
    count += copy_tree(comp, dest / "components")

    # article_init.py 会读配置目录下的 article.example.yaml
    example = wxenv.AWS_DIR / "articles" / "article.example.yaml"
    if not example.exists():
        example = wxenv.SKILL_ROOT / "templates" / "article.example.yaml"
    if example.exists() and not (dest / "article.example.yaml").exists():
        shutil.copy2(example, dest / "article.example.yaml")
        count += 1
    return count


def _bootstrap_venv() -> None:
    import venv

    vd = wxenv.venv_dir()
    vp = wxenv.venv_python()
    if not vp.exists():
        info(f"创建受管 venv: {vd}")
        try:
            venv.EnvBuilder(with_pip=True, clear=False).create(str(vd))
        except Exception as exc:  # pragma: no cover
            warn(f"创建 venv 失败：{exc}")
            return
    req = wxenv.SCRIPTS_DIR / "requirements.txt"
    if not req.exists():
        warn("缺少 scripts/requirements.txt，跳过依赖安装")
        return
    info("安装运行依赖（首次可能需要一两分钟）…")
    proc = subprocess.run([str(vp), "-m", "pip", "install", "-q", "-r", str(req)])
    if proc.returncode == 0:
        ok("依赖安装完成")
    else:
        warn("依赖安装失败，可手动执行：")
        warn(f"  {vp} -m pip install -r {req}")


def cmd_guard(args: list[str]) -> int:
    import wxguard

    return wxguard.main(args)


def cmd_preview_page(args: list[str]) -> int:
    import make_preview

    return make_preview.main(list(args))


def cmd_cover(args: list[str]) -> int:
    """本地合成封面：没有生图模型时的确定性方案（形态「纯色大字」）。"""
    import make_cover

    return make_cover.main(["--"] + list(args))


def cmd_shot(args: list[str]) -> int:
    """排版产物 → 手机宽度 PNG。让「好不好看」成为可核对的确定性产物。"""
    import wxshot

    return wxshot.main(list(args))


def cmd_deco(args: list[str]) -> int:
    """给正文加纸纹底 / 花边框（底图先传图床，再写进 background-image）。"""
    import wxdeco

    return wxdeco.main(list(args))


def cmd_redraft(args: list[str]) -> int:
    """原地更新草稿箱里的一条草稿，避免「换模版＝多一条草稿」。"""
    import redraft

    return redraft.main(list(args))


def cmd_migrate(args: list[str]) -> int:
    import shutil

    dry = "--dry-run" in args
    home = wxenv.ensure_state_home()
    moved = 0

    legacy = wxenv.legacy_state_home()
    if legacy.is_dir() and legacy.resolve() != home.resolve():
        info(f"迁移 {legacy} → {home}")
        for item in legacy.iterdir():
            dest = home / item.name
            if dest.exists():
                continue
            if dry:
                print(f"  将复制 {item.name}")
            else:
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
            moved += 1

    link = wxenv.aws_link()
    if link.is_dir() and not link.is_symlink():
        info(f"检测到真实的 {link}（老约定）；配置仍按原样沿用，未做改动")
        print(f"  如需收敛到状态目录：把 {link} 内容复制到 {home} 后删除该目录，再跑 `wxart init`")

    if moved == 0:
        info("没有需要迁移的内容")
    elif dry:
        info(f"预演完成，共 {moved} 项")
    else:
        ok(f"迁移完成，共 {moved} 项")
    return 0


# ------------------------------------------------------------------ 主入口

NATIVE = {
    "doctor": cmd_doctor,
    "init": cmd_init,
    "env": cmd_env,
    "home": cmd_home,
    "migrate": cmd_migrate,
    "guard": cmd_guard,
    "cover": cmd_cover,
    "preview-page": cmd_preview_page,
    "shot": cmd_shot,
    "deco": cmd_deco,
    "redraft": cmd_redraft,
}

#: 原生命令里需要第三方依赖（Pillow / PyYAML）的几个。
#:
#: 原生命令在 `maybe_reexec_into_venv()` **之前**分发，这是有意的：`env` 的职责就是
#: 如实报告当前解释器缺哪些依赖，先切 venv 会让它永远报「依赖齐全」。所以只给确实
#: 需要依赖的命令单独补一次切换，而不是整体提前。
_NATIVE_NEEDS_DEPS = {"cover", "shot", "deco", "redraft"}


# ------------------------------------------------------------------ format 的引擎栅栏

#: 需要跟一个取值的选项（用于从参数里挑出输入文件）
_VALUED_OPTS = {
    "-o", "--output", "-t", "--theme", "--scheme", "--color", "--font-size", "--export-theme",
}
#: 一旦出现就说明不是「把某篇稿子排版」的模式，跳过栅栏
_INSPECT_OPTS = {"--list-themes", "--preview", "--export-theme"}
#: 由 wxart 自己消费、不能透传给上游引擎的开关
_OWN_FLAGS = {"--force", "--no-check"}


def _find_input(args: list[str]) -> str | None:
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in _VALUED_OPTS:
            i += 2
            continue
        if arg.startswith("-"):
            i += 1
            continue
        return arg
    return None


def _output_path(args: list[str], input_path: str, engine: str) -> Path:
    for flag in ("-o", "--output"):
        if flag in args:
            idx = args.index(flag)
            if idx + 1 < len(args):
                return Path(args[idx + 1]).expanduser()
    return Path(input_path).with_suffix(".html")


def run_format_guard(*, engine: str, rest: list[str]) -> tuple[int | None, list[str]]:
    """排版前后的两道栅栏。返回 (提前退出码或 None, 清理后的参数)。

    1. 排版前：`:::` 容器是否与目标引擎相容——同名不同义的静默漂移会渲染成完全不同的结构，
       这里把它变成显式报错（`--force` 可跳过）。
    2. 排版后：对产物跑微信兼容门禁——ERROR 一律失败（`--no-check` 可跳过）。
    """
    import wxguard

    if any(opt in rest for opt in _INSPECT_OPTS):
        return None, rest

    clean = [a for a in rest if a not in _OWN_FLAGS]
    force = "--force" in rest
    no_check = "--no-check" in rest

    input_path = _find_input(clean)
    if not input_path:
        return None, clean
    src = Path(input_path).expanduser()
    if not src.exists():
        return None, clean

    report = wxguard.check_containers(src.read_text(encoding="utf-8"), engine)
    if not report["ok"] and not force:
        err("::: 容器与目标引擎不相容 —— 已中止排版，避免静默渲染成别的结构")
        print(wxguard.format_container_report(report), file=sys.stderr)
        err("改写这些块、换引擎，或确认无误后加 --force")
        return 4, clean
    for item in report["deprecated"]:
        warn(f"第 {item['line']} 行 :::{item['name']} 已废弃：{item['hint']}")

    # wx 引擎的 preview 默认会打开浏览器，Agent 流程里不需要
    if engine == "wx" and "--no-open" not in clean:
        clean.append("--no-open")

    return None, clean


def run_format_gate(*, engine: str, rest: list[str], no_check: bool = False) -> int:
    """排版后校验产物。返回 0 通过 / 5 有 ERROR。"""
    import wxguard

    if no_check or any(opt in rest for opt in _INSPECT_OPTS):
        return 0
    input_path = _find_input(rest)
    if not input_path:
        return 0
    out = _output_path(rest, input_path, engine)
    if not out.exists():
        return 0
    profile = "wx" if engine == "wx" else "generic"
    findings = wxguard.gate(out.read_text(encoding="utf-8"), profile)
    errors = [f for f in findings if f["level"] == "ERROR"]
    stream = sys.stderr if errors else sys.stdout
    print(wxguard.format_gate_report(findings, str(out), profile), file=stream)
    if errors:
        err("产物未通过微信兼容门禁：修排版或换主题后重跑（确认无碍可加 --no-check）")
        return 5
    return 0



def main(argv: list[str] | None = None) -> int:
    global COMMANDS
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help", "help"):
        print(usage())
        return 0
    if argv[0] in ("-V", "--version"):
        print(version())
        return 0

    command, rest = argv[0], argv[1:]

    # 命令别名：兼容两个上游的常用叫法
    alias = {"diagnose": "doctor", "format-aws": "format", "image-gen": "image", "publish-wechat": "publish"}
    command = alias.get(command, command)

    if command not in COMMANDS and command not in ENGINE_SWITCH:
        err(f"未知命令: {command}")
        print()
        print(usage())
        return 2

    # --engine 解析。**只对真正带引擎开关的命令生效**——其它命令（如 `guard`）
    # 自己就有 `--engine`，全局解析器不能吞掉它，否则会静默用错引擎。
    engine = None
    if command in ENGINE_SWITCH:
        if "--engine" in rest:
            idx = rest.index("--engine")
            if idx + 1 >= len(rest):
                err("--engine 需要一个取值")
                return 2
            engine = rest[idx + 1]
            rest = rest[:idx] + rest[idx + 2:]
        table = ENGINE_SWITCH[command]
        engine = engine or DEFAULT_ENGINE[command]
        if engine not in table:
            err(f"{command} 的 --engine 只能是 {' / '.join(table)}")
            return 2
        kind, target = table[engine]
    else:
        kind, target, _ = COMMANDS[command]
        if "--engine" in rest and command != "guard":
            warn(f"{command} 没有 --engine 开关，已忽略")

    if kind == "n":
        if command in _NATIVE_NEEDS_DEPS:
            maybe_reexec_into_venv()
        return NATIVE[command](rest)

    maybe_reexec_into_venv()
    wxenv.inject_engine_env()

    if command == "format":
        no_check = "--no-check" in rest
        early, rest = run_format_guard(engine=engine, rest=rest)
        if early is not None:
            return early
    else:
        no_check = False

    if kind == "w":
        code = dispatch_wxengine(target, rest)
    else:
        code = dispatch_aws(target, rest)

    if command == "format" and code == 0:
        gate_code = run_format_gate(engine=engine, rest=rest, no_check=no_check)
        if gate_code:
            return gate_code
    return code


if __name__ == "__main__":
    raise SystemExit(main())
