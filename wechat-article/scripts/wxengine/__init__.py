"""WeWrite runtime — 公众号内容管道的确定性工具层（CLI: `wewrite`）。"""

# 版本单一真源 = 仓库根 VERSION 文件（pyproject 经 tool.setuptools.dynamic 同源读取）；
# 已安装的包读打包时写入的 metadata，源码运行（PYTHONPATH=src）回退读 VERSION
def _resolve_version() -> str:
    try:
        from pathlib import Path
        source_version = Path(__file__).resolve().parents[2] / "VERSION"
        if source_version.exists():
            return source_version.read_text().strip()
    except Exception:
        pass
    try:
        from importlib.metadata import version
        return version("wewrite")
    except Exception:
        pass
    return "0.0.0+unknown"


__version__ = _resolve_version()
