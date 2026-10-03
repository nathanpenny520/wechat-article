"""wxenv —— 统一路径、状态与配置解析层。

本模块是整个 skill 的"唯一真相来源"，负责把两个上游项目的两套约定收敛成一套：

| 上游 | 原约定 | 本 skill 的收敛方式 |
|------|--------|---------------------|
| wewrite | 用户状态在 `~/.wewrite/`（`$WEWRITE_HOME`） | 统一到 `~/.wxarticle/`，由本模块注入 `WEWRITE_HOME` 环境变量，不改动其源码 |
| wechat-article-skills | 账号配置在**工作区** `.aws-article/`，密钥在同级 `aws.env` | 工作区放一个指向状态目录的 `.aws-article` 软链，使上游代码零改动即可读写同一份配置 |

因此"同一份配置"只存在一处：`~/.wxarticle/config.yaml`；工作区的 `.aws-article`
是一个兼容软链。若工作区存在真实的 `.wxarticle/` 目录，则以它为本项目的覆盖层
（`.aws-article` 指向它），用于一个仓库对应一个公众号的场景。

所有解析结果都可通过 `wxart env` 打印，便于排障。
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------- 目录常量

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
REFERENCES_DIR = SKILL_ROOT / "references"
ASSETS_DIR = SKILL_ROOT / "assets"
TESTS_DIR = SKILL_ROOT / "tests"

WXENGINE_PKG_DIR = SCRIPTS_DIR / "wxengine"
AWS_DIR = SCRIPTS_DIR / "aws"

# 工作区兼容软链名（上游 wechat-article-skills 的约定，不要改）
AWS_LINK_NAME = ".aws-article"
# 本 skill 的项目覆盖层目录名
PROJECT_DIR_NAME = ".wxarticle"

# 工作区业务文件
DRAFTS_DIR_NAME = "drafts"
PUBLISHED_DIR_NAME = "published"
ENV_FILE_NAMES = ("aws.env", ".env")

# 需要的最小运行依赖（供 doctor / bootstrap 使用）
REQUIRED_MODULES = ("yaml", "markdown", "bs4", "cssutils", "requests", "pygments", "PIL")


# ---------------------------------------------------------------- 状态目录


def state_home() -> Path:
    """用户级状态目录：`$WXARTICLE_HOME` 或 `~/.wxarticle`。

    仍兼容 `$WEWRITE_HOME`——若用户显式设置了它，说明用户希望沿用旧目录，
    此时状态目录就是旧目录，不再套一层。
    """
    explicit = os.environ.get("WXARTICLE_HOME", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    legacy = os.environ.get("WEWRITE_HOME", "").strip()
    if legacy:
        return Path(legacy).expanduser()
    return Path.home() / ".wxarticle"


def legacy_state_home() -> Path:
    """上一个版本的状态目录，`wxart migrate` 会从这里搬数据。

    `$WXARTICLE_LEGACY_HOME` 可显式覆盖（旧状态放在别处、或做隔离测试时用）。
    """
    explicit = os.environ.get("WXARTICLE_LEGACY_HOME", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return Path.home() / ".wewrite"


def venv_dir() -> Path:
    return state_home() / "venv"


def venv_python() -> Path:
    return venv_dir() / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_state_home() -> Path:
    home = state_home()
    for sub in ("output", "runs", "exemplars", "corpus", "lessons", "themes", "personas"):
        (home / sub).mkdir(parents=True, exist_ok=True)
    return home


# ---------------------------------------------------------------- 工作区


def _is_workspace_marker(directory: Path) -> bool:
    """这个目录是不是工作区根。

    ⚠️ 关键：**状态目录自己就叫 `.wxarticle`**，所以不能只看"存在 `.wxarticle`"——
    否则从任何项目向上找都会命中 `$HOME/.wxarticle`，把家目录当成工作区，
    相对路径（`.aws-article`、`drafts_root`）就会全部指错地方。
    真正的项目标记要么是指向别处的 `.aws-article` 兼容入口，要么是 `.git`。
    """
    try:
        home = state_home().resolve()
    except OSError:  # pragma: no cover
        home = state_home()
    for name in (PROJECT_DIR_NAME, AWS_LINK_NAME):
        marker = directory / name
        if not marker.exists():
            continue
        try:
            if marker.resolve() == home:
                continue  # 就是状态目录本身，不是项目标记
        except OSError:
            continue
        return True
    return (directory / ".git").exists()


def workspace_root() -> Path:
    """工作区根：显式 env > 当前目录向上第一个真正的工作区标记 > 当前目录。"""
    explicit = os.environ.get("WXARTICLE_WORKSPACE", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    cur = Path.cwd().resolve()
    for cand in (cur, *cur.parents):
        if _is_workspace_marker(cand):
            return cand
    return cur


def project_dir() -> Path:
    """本项目的配置覆盖层目录（不一定存在）。"""
    return workspace_root() / PROJECT_DIR_NAME


def aws_link() -> Path:
    """上游约定名，始终由 `ensure_config_dir()` 保证可用。"""
    return workspace_root() / AWS_LINK_NAME


def primary_env_file() -> Path:
    """密钥的唯一真源：状态目录的 `.env`。

    另一个引擎按工作区相对路径找 `aws.env`，由 `ensure_env_link()` 建软链指到同一份，
    所以"密钥只写一处"是真的：`~/.wxarticle/.env`。
    """
    proj = project_dir()
    if proj.is_dir() and not proj.is_symlink():
        return proj / ".env"
    return state_home() / ".env"


def ensure_env_link(in_dir: Path | None = None) -> Path | None:
    """在工作区建 `aws.env` 兼容入口指向 `primary_env_file()`。

    用户自己放了真实 `aws.env` 就原样沿用，不覆盖。
    """
    base = Path(in_dir) if in_dir is not None else workspace_root()
    link = base / "aws.env"
    target = primary_env_file()
    if link.is_symlink():
        try:
            if link.resolve() == target.resolve():
                return target
        except OSError:
            pass
        try:
            link.unlink()
        except OSError:
            return target
    elif link.exists():
        return target
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch(exist_ok=True)
        link.symlink_to(os.path.relpath(target, link.parent))
        return target
    except (OSError, NotImplementedError):
        return target


def config_dir() -> Path:
    """当前生效的配置目录（决定 aws 引擎读写哪里）。

    优先级：
    1. `$WXARTICLE_CONFIG_DIR`（显式指定，排障用）
    2. 工作区存在真实 `.wxarticle/` → 本项目覆盖层
    3. 工作区已存在真实 `.aws-article/`（老用户）→ 原样沿用，不动用户目录
    4. 否则 → 用户级状态目录（`~/.wxarticle`），多个工作区共用同一账号配置
    """
    explicit = os.environ.get("WXARTICLE_CONFIG_DIR", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    proj = project_dir()
    if proj.is_dir() and not proj.is_symlink():
        return proj
    link = aws_link()
    if link.is_dir() and not link.is_symlink():
        return link.resolve()
    return state_home()


def config_file() -> Path:
    return config_dir() / "config.yaml"


def env_file_candidates() -> list[Path]:
    """密钥文件查找顺序（先命中先赢）。

    1. 项目覆盖层 `.wxarticle/`（一个仓库一个公众号时用）
    2. 状态目录 `~/.wxarticle/`（唯一真源）
    3. 工作区根 `aws.env`（用户显式放的项目级密钥文件）

    **不读工作区根的 `.env`**：那个名字太通用，容易误吞无关项目的密钥。
    """
    out: list[Path] = []
    proj = project_dir()
    if proj.is_dir() and not proj.is_symlink():
        out += [proj / ".env", proj / "aws.env"]
    out += [state_home() / ".env", state_home() / "aws.env"]
    out.append(workspace_root() / "aws.env")

    seen: set[Path] = set()
    dedup: list[Path] = []
    for p in out:
        try:
            key = p.resolve()
        except OSError:
            key = p
        if key in seen:
            continue
        seen.add(key)
        dedup.append(p)
    return dedup


def ensure_config_link(in_dir: Path | None = None) -> Path | None:
    """在 `in_dir`（默认工作区根）建立 `.aws-article` 兼容入口。

    上游引擎按 **CWD 相对路径**找 `.aws-article/config.yaml`，所以链接必须建在
    命令真正执行的那个目录里，否则相对路径会把参数指错地方。
    建不成软链（Windows 等）时退化为真实目录，配置仍可用，只是不再与状态目录共享。
    """
    target = config_dir()
    base = Path(in_dir) if in_dir is not None else workspace_root()
    link = base / AWS_LINK_NAME
    if link.is_symlink():
        try:
            if link.resolve() == target.resolve():
                return target
        except OSError:
            pass
        # 指向别处（换了状态目录、或指向已被删掉的旧目录）→ 重新指向，别留断链
        try:
            link.unlink()
        except OSError:
            return target
    elif link.exists():
        # 真实目录：老用户按原样沿用，不动
        return target
    try:
        link.symlink_to(os.path.relpath(target, link.parent))
        return target
    except (OSError, NotImplementedError):
        try:
            target.mkdir(parents=True, exist_ok=True)
            link.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None
        return target


def ensure_config_dir(create_link: bool = True) -> Path:
    """保证配置目录可用，并在工作区根建好兼容入口。"""
    ensure_state_home()
    target = config_dir()
    if create_link:
        ensure_config_link(workspace_root())
        ensure_env_link(workspace_root())
    return target


def drafts_root() -> Path:
    cfg = load_config()
    raw = str(cfg.get("drafts_root") or DRAFTS_DIR_NAME)
    p = Path(raw).expanduser()
    return p if p.is_absolute() else workspace_root() / p


def published_root() -> Path:
    cfg = load_config()
    raw = str(cfg.get("published_root") or PUBLISHED_DIR_NAME)
    p = Path(raw).expanduser()
    return p if p.is_absolute() else workspace_root() / p


# ---------------------------------------------------------------- 配置


def _read_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:  # pragma: no cover - 由 doctor 给出安装指引
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except (OSError, Exception):
        return {}
    return data if isinstance(data, dict) else {}


def config_search_order() -> list[Path]:
    return [config_file(), state_home() / "config.yaml", legacy_state_home() / "config.yaml"]


def load_config(force_reload: bool = False) -> dict:
    """合并后的配置：项目覆盖层 > 用户级 > 旧状态目录（**只补空缺**）。

    旧目录必须按"补空缺"而不是"参与覆盖"来合并：`wxart init` 生成的模板里
    `article_category: ""`、`wechat.appid: ""` 这类空占位如果参与覆盖，会把用户在
    旧目录里填好的真实值清空——迁移过的用户会突然"凭证丢了"。
    需要清空某个键时，请显式写 `null` 或删除该行，而不是留空字符串。
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None and not force_reload:
        return _CONFIG_CACHE

    legacy = legacy_state_home() / "config.yaml"
    primary_paths = [p for p in config_search_order() if p != legacy]

    merged: dict = {}
    seen: list[Path] = []
    for path in reversed(primary_paths):  # 低优先级先合并
        if path in seen or not path.exists():
            continue
        seen.append(path)
        merged = _deep_merge(merged, _read_yaml(path))

    if legacy.exists() and legacy not in seen:
        merged = _fill_gaps(merged, _read_yaml(legacy))

    _CONFIG_CACHE = merged
    return merged


_CONFIG_CACHE: dict | None = None


def _is_empty_value(value: object) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _fill_gaps(base: dict, filler: dict) -> dict:
    """只把 `filler` 里非空、而 `base` 里缺失或为空的值补进来。"""
    out = dict(base)
    for key, val in filler.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _fill_gaps(out[key], val)
        elif _is_empty_value(out.get(key)) and not _is_empty_value(val):
            out[key] = val
    return out


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for key, val in overlay.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def load_env(export: bool = False) -> dict:
    """读取密钥文件（`KEY=VALUE` 行），可选写入 os.environ。"""
    values: dict[str, str] = {}
    for path in env_file_candidates():
        if not path.exists():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key and key not in values:
                    values[key] = val
        except OSError:
            continue
    if export:
        for key, val in values.items():
            os.environ.setdefault(key, val)
    return values


# ---------------------------------------------------------------- 运行时


def _module_available(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None


def missing_modules() -> list[str]:
    return [m for m in REQUIRED_MODULES if not _module_available(m)]


def python_exe() -> str:
    """优先用受管 venv 的解释器；不存在则用当前解释器。"""
    vp = venv_python()
    if vp.exists():
        return str(vp)
    return sys.executable


def inject_engine_env() -> None:
    """把两套引擎的环境变量对齐到同一份状态。

    - `WEWRITE_HOME` → 统一状态目录（we分 write 源码零改动）
    - `PATH` 前置 venv/bin，便于上游脚本用 `python3` 兜底调用
    """
    os.environ.setdefault("WEWRITE_HOME", str(state_home()))
    vp = venv_python()
    if vp.exists():
        os.environ["PATH"] = str(vp.parent) + os.pathsep + os.environ.get("PATH", "")
    load_env(export=True)


def sys_path_prelude() -> None:
    """让 `import wxengine` 命中随 skill 自带的包。"""
    p = str(SCRIPTS_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)


def which_python_command() -> str:
    """上游文档里的 `{python}` 占位符：Windows 用 `py -3 -X utf8`，其他用 `python3`。"""
    if os.name == "nt":
        return "py -3 -X utf8"
    return "python3"


# ---------------------------------------------------------------- 自检


def _link_kind() -> str:
    """工作区兼容入口的形态：symlink / broken / dir / absent。"""
    link = aws_link()
    if link.is_symlink():
        return "symlink" if link.exists() else "broken"
    return "dir" if link.is_dir() else "absent"


def describe() -> dict:
    """给 `wxart env` / doctor 用的结构化快照。"""
    return {
        "skill_root": str(SKILL_ROOT),
        "state_home": str(state_home()),
        "state_home_exists": state_home().exists(),
        "legacy_state_home": str(legacy_state_home()),
        "legacy_state_home_exists": legacy_state_home().exists(),
        "workspace": str(workspace_root()),
        "config_dir": str(config_dir()),
        "config_file": str(config_file()),
        "config_file_exists": config_file().exists(),
        "aws_link": str(aws_link()),
        "aws_link_kind": _link_kind(),
        "env_files_present": [str(p) for p in env_file_candidates() if p.exists()],
        "python": sys.executable,
        "python_version": sys.version.split()[0],
        "venv_python": str(venv_python()),
        "venv_exists": venv_python().exists(),
        "missing_modules": missing_modules(),
        "drafts_root": str(drafts_root()),
        "published_root": str(published_root()),
        "git": shutil.which("git"),
    }
