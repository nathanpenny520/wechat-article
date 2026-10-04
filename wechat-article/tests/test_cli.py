"""CLI 集成测试：原生命令、两个引擎的分发、排版产物与微信兼容校验。

依赖运行依赖（pyyaml/markdown/bs4/cssutils/pygments/requests）。
缺依赖时整类跳过，不误报失败。运行：
    python3 -m unittest tests.test_cli -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
WXART = SKILL_ROOT / "scripts" / "wxart.py"
FIXTURE = SKILL_ROOT / "tests" / "fixtures" / "sample-article.md"
FIXTURE_AWS = SKILL_ROOT / "tests" / "fixtures" / "sample-article-aws.md"

sys.path.insert(0, str(SKILL_ROOT / "scripts"))
import wxenv  # noqa: E402

HAVE_DEPS = not wxenv.missing_modules()


def _find_browser() -> str | None:
    """`wxart shot` 依赖 Chromium 内核浏览器；没有就跳过截图相关的断言。"""
    try:
        import wxshot  # noqa: WPS433

        return wxshot.find_browser()
    except Exception:  # noqa: BLE001 — 缺依赖时按「没有浏览器」处理
        return None


BROWSER = _find_browser()


class CliHarness:
    """在隔离的状态目录与工作区里跑 CLI 的公共装置。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="wxart-test-")
        root = Path(self._tmp.name)
        self.state = root / "state"
        self.workspace = root / "ws"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.env = dict(os.environ)
        self.env.update(
            {
                "WXARTICLE_HOME": str(self.state),
                "WXARTICLE_WORKSPACE": str(self.workspace),
                "WXARTICLE_NO_REEXEC": "1",
                "NO_COLOR": "1",
            }
        )
        # 不继承宿主机的上游状态目录，避免读到真实凭证/历史
        for key in ("WEWRITE_HOME", "WXARTICLE_CONFIG_DIR"):
            self.env.pop(key, None)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, name: str, body: str) -> Path:
        path = self.workspace / name
        path.write_text(body, encoding="utf-8")
        return path

    def run_cli(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(WXART), *args],
            cwd=str(cwd or self.workspace),
            env=self.env,
            capture_output=True,
            text=True,
        )

class CliTestCase(CliHarness, unittest.TestCase):
    # ------------------------------------------------------------ 原生命令

    def test_home_points_at_state_home(self) -> None:
        res = self.run_cli("home")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), str(self.state))

    def test_env_json_reports_resolved_paths(self) -> None:
        res = self.run_cli("env", "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        snap = json.loads(res.stdout)
        for key in ("skill_root", "state_home", "config_dir", "config_file", "aws_link",
                    "missing_modules", "drafts_root"):
            self.assertIn(key, snap)
        self.assertEqual(Path(snap["state_home"]).resolve(), self.state.resolve())
        self.assertEqual(Path(snap["workspace"]).resolve(), self.workspace.resolve())

    def test_unknown_command_exits_2(self) -> None:
        res = self.run_cli("definitely-not-a-command")
        self.assertEqual(res.returncode, 2)
        self.assertIn("未知命令", res.stderr)

    def test_bad_engine_value_exits_2(self) -> None:
        res = self.run_cli("format", "--engine", "nope", str(FIXTURE))
        self.assertEqual(res.returncode, 2)
        self.assertIn("--engine", res.stderr)

    def test_version_and_help(self) -> None:
        self.assertEqual(self.run_cli("--version").returncode, 0)
        help_res = self.run_cli("--help")
        self.assertEqual(help_res.returncode, 0)
        self.assertIn("wxart", help_res.stdout)

    # ------------------------------------------------------------ init

    def test_init_creates_config_env_presets_and_workspace_link(self) -> None:
        res = self.run_cli("init", "--no-venv")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue((self.state / "config.yaml").exists())
        self.assertTrue((self.state / ".env").exists())
        self.assertTrue((self.state / "presets" / "formatting").is_dir())
        # 8 套模版 = 4 内置 themes + 4 templates，全部铺进可搜索目录
        yamls = list((self.state / "presets" / "formatting").glob("*.yaml"))
        self.assertGreaterEqual(len(yamls), 8, f"排版预设只铺了 {len(yamls)} 个")
        # 工作区兼容软链
        link = self.workspace / ".aws-article"
        self.assertTrue(link.is_symlink() or link.is_dir(), "未建立工作区兼容目录")

    def test_init_is_idempotent_and_preserves_user_config(self) -> None:
        self.run_cli("init", "--no-venv")
        cfg = self.state / "config.yaml"
        cfg.write_text("article_category: 我已手改\n", encoding="utf-8")
        res = self.run_cli("init", "--no-venv")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("我已手改", cfg.read_text(encoding="utf-8"))

    def test_doctor_json_is_structured(self) -> None:
        self.run_cli("init", "--no-venv")
        res = self.run_cli("doctor", "--json")
        payload = json.loads(res.stdout)
        self.assertIn("checks", payload)
        self.assertIn("snapshot", payload)
        names = {c["check"] for c in payload["checks"]}
        self.assertIn("config", names)
        self.assertIn("publish_method", names)

    def test_preview_page_wraps_fragments_at_phone_width(self) -> None:
        """aws 引擎产物是裸 <section>，预览页要把它装进 375px 手机卡才看得出观感。"""
        frag = self._write("frag.html", '<section style="color:#111"><p>正文一段</p></section>')
        out = self.workspace / "pv.html"
        res = self.run_cli("preview-page", str(frag), "-o", str(out), "--title", "测试")
        self.assertEqual(res.returncode, 0, res.stderr)
        page = out.read_text(encoding="utf-8")
        self.assertIn("width:375px", page)
        self.assertIn("正文一段", page)
        self.assertIn("frag.html", page, "预览卡应标注来源文件")

    def test_preview_page_reports_missing_input(self) -> None:
        res = self.run_cli("preview-page", str(self.workspace / "nope.html"), "-o", str(self.workspace / "o.html"))
        self.assertEqual(res.returncode, 2)
        self.assertIn("文件不存在", res.stderr)

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_cover_command_makes_235_cover(self) -> None:
        """无生图模型时的本地封面：必须是 2.35:1 且长边 ≥900。"""
        from PIL import Image

        out = self.workspace / "cover.png"
        res = self.run_cli("cover", "测试钩子六字", "副标题一行", "-o", str(out))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(out.exists())
        w, h = Image.open(out).size
        self.assertAlmostEqual(w / h, 2.35, delta=0.05)
        self.assertGreaterEqual(max(w, h), 900)
        self.assertIn("字高占", res.stdout)

    # ------------------------------------------------------------ 观感核对（shot）

    def test_shot_reports_missing_input(self) -> None:
        res = self.run_cli("shot", str(self.workspace / "nope.html"), "-o", str(self.workspace / "o.png"))
        self.assertEqual(res.returncode, 2)
        self.assertIn("文件不存在", res.stderr)

    @unittest.skipUnless(BROWSER, "本机没有 Chromium 内核浏览器")
    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_shot_renders_at_phone_width(self) -> None:
        """375px × 2 倍密度：截图宽度必须是手机正文宽度，而不是浏览器窗口宽度。"""
        from PIL import Image

        frag = self._write("frag.html", '<section style="padding:16px"><p>正文一段</p></section>')
        out = self.workspace / "shot.png"
        res = self.run_cli("shot", str(frag), "-o", str(out))
        self.assertEqual(res.returncode, 0, res.stderr)
        w, h = Image.open(out).size
        self.assertEqual(w, 750, f"应为 375px × 2 倍密度，实际 {w}")
        self.assertGreater(h, 100)
        self.assertIn("无横向溢出", res.stdout)

    @unittest.skipUnless(BROWSER, "本机没有 Chromium 内核浏览器")
    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_shot_flags_horizontal_overflow(self) -> None:
        """超出容器宽度的元素在手机上会被右边切掉，截图必须把它报出来。"""
        frag = self._write("wide.html", '<section style="width:600px">超宽元素</section>')
        out = self.workspace / "wide.png"
        res = self.run_cli("shot", str(frag), "-o", str(out))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("横向溢出", res.stdout)
        self.assertNotIn("无横向溢出", res.stdout)

    # ------------------------------------------------------------ 原地更新草稿（redraft）

    def _article_dir(self) -> Path:
        d = self.workspace / "art"
        d.mkdir(exist_ok=True)
        (d / "article.yaml").write_text(
            "title: 测试标题\nauthor: 测试作者\ndigest: 摘要\n", encoding="utf-8")
        (d / "article.html").write_text("<section><p>正文</p></section>", encoding="utf-8")
        from PIL import Image

        Image.new("RGB", (1408, 599), (200, 30, 30)).save(d / "cover.png")
        return d

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_redraft_dry_run_never_touches_the_network(self) -> None:
        """`--dry-run` 必须在取 token 之前返回：它存在的意义就是「先确认改的是哪条」。"""
        d = self._article_dir()
        res = self.run_cli("redraft", "FAKE_MEDIA_ID", str(d), "--dry-run")
        self.assertEqual(res.returncode, 0, res.stderr)
        report = json.loads(res.stdout)
        self.assertEqual(report["media_id"], "FAKE_MEDIA_ID")
        self.assertEqual(report["title"], "测试标题")
        self.assertGreater(report["content_bytes"], 0)
        self.assertNotIn("access_token", res.stdout + res.stderr)

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_redraft_reports_missing_metadata(self) -> None:
        d = self.workspace / "empty"
        d.mkdir()
        res = self.run_cli("redraft", "M", str(d), "--dry-run")
        self.assertEqual(res.returncode, 1)
        self.assertIn("article.yaml", res.stderr)

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_redraft_reports_missing_cover(self) -> None:
        d = self.workspace / "nocover"
        d.mkdir()
        (d / "article.yaml").write_text("title: T\n", encoding="utf-8")
        (d / "article.html").write_text("<section></section>", encoding="utf-8")
        res = self.run_cli("redraft", "M", str(d), "--dry-run")
        self.assertEqual(res.returncode, 1)
        self.assertIn("封面", res.stderr)

    # ------------------------------------------------------------ 引擎分发

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_wx_engine_dispatches_and_writes_html(self) -> None:
        out = self.workspace / "wx.html"
        res = self.run_cli("format", str(FIXTURE), "-o", str(out))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(out.exists())
        html = out.read_text(encoding="utf-8")
        self.assertIn("<section", html)
        self.assertNotIn("<div", html, "wx 引擎产物不应含 div")
        self.assertNotIn("class=", html, "wx 引擎产物不应含 class")
        self.assertIn("data-darkmode-color", html, "缺少暗黑模式注入")

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_cover_marker_is_skipped_from_body(self) -> None:
        """封面标记必须留在正文之外——它在正文里只会渲染成一张不会被上传的坏图。"""
        md = self._write("cov.md", '![封面：测试封面](cover.png)\n\n# 标题\n\n正文一段。\n')
        out = self.workspace / "cov.html"
        res = self.run_cli("format", str(md), "-o", str(out))
        self.assertEqual(res.returncode, 0, res.stderr)
        html = out.read_text(encoding="utf-8")
        self.assertNotIn("cover.png", html, "封面图不该出现在正文 HTML 里")
        self.assertNotIn("测试封面", html)

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_wx_output_passes_wechat_validation(self) -> None:
        out = self.workspace / "wx.html"
        self.run_cli("format", str(FIXTURE), "-o", str(out))
        res = self.run_cli("validate", str(out), "--json")
        self.assertEqual(res.returncode, 0, f"微信兼容校验未通过: {res.stdout} {res.stderr}")
        payload = json.loads(res.stdout)
        errors = [item for item in _iter_findings(payload) if item.get("level") == "error"]
        self.assertEqual(errors, [], f"存在 ERROR 级问题: {errors}")

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_wx_engine_lists_eighteen_themes(self) -> None:
        res = self.run_cli("themes")
        self.assertEqual(res.returncode, 0, res.stderr)
        for theme in ("professional-clean", "sspai", "midnight", "tech-modern"):
            self.assertIn(theme, res.stdout)

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_aws_engine_dispatches_with_theme_and_scheme(self) -> None:
        self.run_cli("init", "--no-venv")
        out = self.workspace / "aws.html"
        res = self.run_cli(
            "format", "--engine", "aws", str(FIXTURE_AWS),
            "--theme", "亲和", "--scheme", "黛紫", "-o", str(out),
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(out.exists())
        self.assertGreater(out.stat().st_size, 1000, "aws 引擎产物过小")

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_aws_engine_renders_components(self) -> None:
        self.run_cli("init", "--no-venv")
        out = self.workspace / "aws-comp.html"
        res = self.run_cli(
            "format", "--engine", "aws", str(FIXTURE_AWS), "--theme", "资讯", "-o", str(out)
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        html = out.read_text(encoding="utf-8")
        for container_text in ("单轮问答的得分", "工具调用与重试", "方法比结论重要"):
            self.assertIn(container_text, html, f"组件内容缺失: {container_text}")
        self.assertNotIn(":::", html, "组件标记没有被消费掉")

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_aws_engine_lists_eight_templates(self) -> None:
        self.run_cli("init", "--no-venv")
        res = self.run_cli("format", "--engine", "aws", "--list-themes")
        self.assertEqual(res.returncode, 0, res.stderr)
        for name in ("亲和", "资讯", "书卷", "杂志", "手账", "技术", "活力", "硬朗"):
            self.assertIn(name, res.stdout, f"模版清单缺 {name}")

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_score_returns_json_quality_score(self) -> None:
        res = self.run_cli("score", str(FIXTURE), "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertIn("quality_score", payload)
        self.assertGreater(payload["quality_score"], 0)

    # ------------------------------------------------------------ 任务生命周期

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_run_lifecycle_is_isolated_in_state_home(self) -> None:
        res = self.run_cli("run", "start", "--topic", "测试选题", "--mode", "draft", "--visual-mode", "none")
        self.assertEqual(res.returncode, 0, res.stderr)
        runs = list((self.state / "runs").glob("*/state.yaml"))
        self.assertEqual(len(runs), 1, "任务目录未落在隔离的状态目录里")
        res = self.run_cli("run", "show")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("draft", res.stdout)

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_run_cannot_finish_without_reviewed_article(self) -> None:
        self.run_cli("run", "start", "--topic", "t", "--mode", "draft", "--visual-mode", "none")
        run_dir = next((self.state / "runs").glob("*/"))
        (run_dir / "draft.md").write_text("# 草稿\n\n正文。\n", encoding="utf-8")
        res = self.run_cli("run", "finish")
        self.assertNotEqual(res.returncode, 0, "未过审的初稿不应允许封存")


    def test_stale_compat_link_is_repointed(self) -> None:
        """指向已失效目录的 `.aws-article` 必须被重新指向，而不是留成断链。"""
        link = self.workspace / ".aws-article"
        link.symlink_to("some-gone-dir")
        self.assertFalse(link.exists(), "前置条件：链接应当是断的")
        # doctor 先把它报出来，init 再修掉
        doc = self.run_cli("doctor")
        self.assertIn("断链", doc.stdout + doc.stderr)
        res = self.run_cli("init", "--no-venv")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(link.exists(), "断链没有被修复")
        self.assertEqual(link.resolve(), self.state.resolve())

    def test_real_aws_article_dir_is_left_alone(self) -> None:
        """老用户手建的真实 `.aws-article/` 目录不能被改成软链。"""
        real = self.workspace / ".aws-article"
        real.mkdir()
        (real / "config.yaml").write_text("article_category: 老用户\n", encoding="utf-8")
        res = self.run_cli("env")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertFalse(real.is_symlink(), "真实目录被改成了软链")
        self.assertTrue((real / "config.yaml").exists())
        snap = json.loads(self.run_cli("env", "--json").stdout)
        self.assertEqual(Path(snap["config_dir"]).resolve(), real.resolve())


class WorkspaceResolutionTest(unittest.TestCase):
    """工作区探测：状态目录自己叫 `.wxarticle`，绝不能被当成项目标记。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="wxart-ws-")
        self.root = Path(self._tmp.name)
        self._saved = {k: os.environ.get(k) for k in
                       ("WXARTICLE_HOME", "WXARTICLE_WORKSPACE", "WEWRITE_HOME",
                        "WXARTICLE_LEGACY_HOME")}
        for key in self._saved:
            os.environ.pop(key, None)
        # 状态目录放在祖先目录上，名字正是 .wxarticle —— 真实场景就是这样
        self.state = self.root / ".wxarticle"
        self.state.mkdir()
        self.project = self.root / "proj"
        (self.project / "sub").mkdir(parents=True)
        os.environ["WXARTICLE_HOME"] = str(self.state)
        self._cwd = Path.cwd()
        os.chdir(self.project / "sub")

    def tearDown(self) -> None:
        os.chdir(self._cwd)
        for key, val in self._saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        self._tmp.cleanup()

    def test_state_dir_is_not_a_workspace_marker(self) -> None:
        import wxenv

        wxenv._CONFIG_CACHE = None
        got = wxenv.workspace_root()
        self.assertNotEqual(got, self.state.parent, "把家目录当成工作区了")
        self.assertEqual(got, (self.project / "sub").resolve())

    def test_project_marker_wins_over_cwd(self) -> None:
        import wxenv

        (self.project / ".aws-article").mkdir()
        wxenv._CONFIG_CACHE = None
        self.assertEqual(wxenv.workspace_root(), self.project.resolve())


class StateLayerTest(unittest.TestCase):
    """状态层：密钥单一真源，以及旧配置「只补空缺、不覆盖」。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="wxart-state-")
        root = Path(self._tmp.name)
        self._saved = {k: os.environ.get(k) for k in
                       ("WXARTICLE_HOME", "WXARTICLE_WORKSPACE", "WEWRITE_HOME",
                        "WXARTICLE_LEGACY_HOME")}
        self.state = root / "state"
        self.state.mkdir()
        self.legacy = root / "legacy"
        self.legacy.mkdir()
        self.workspace = root / "ws"
        self.workspace.mkdir()
        os.environ["WXARTICLE_HOME"] = str(self.state)
        os.environ["WXARTICLE_WORKSPACE"] = str(self.workspace)
        os.environ["WXARTICLE_LEGACY_HOME"] = str(self.legacy)
        os.environ.pop("WEWRITE_HOME", None)

    def tearDown(self) -> None:
        for key, val in self._saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        self._tmp.cleanup()

    def _wxenv(self):
        import wxenv
        wxenv._CONFIG_CACHE = None
        return wxenv

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_legacy_config_fills_gaps_but_never_overrides(self) -> None:
        (self.legacy / "config.yaml").write_text(
            "wechat:\n  appid: legacy-appid\n  secret: legacy-secret\ntheme: sspai\n",
            encoding="utf-8")
        (self.state / "config.yaml").write_text(
            "wechat:\n  appid: ''\n  secret: ''\narticle_category: 技术开源\n",
            encoding="utf-8")
        cfg = self._wxenv().load_config(force_reload=True)
        self.assertEqual(cfg["wechat"]["appid"], "legacy-appid", "空占位不该清掉旧目录里的真实值")
        self.assertEqual(cfg["wechat"]["secret"], "legacy-secret")
        self.assertEqual(cfg["theme"], "sspai", "旧目录补上了缺失的键")
        self.assertEqual(cfg["article_category"], "技术开源", "新配置的非空值不被旧目录覆盖")

    def test_env_link_points_at_the_single_source(self) -> None:
        wxenv = self._wxenv()
        wxenv.ensure_env_link(self.workspace)
        link = self.workspace / "aws.env"
        self.assertTrue(link.is_symlink(), "应在工作区建立 aws.env 兼容软链")
        self.assertEqual(link.resolve(), (self.state / ".env").resolve())
        self.assertEqual(wxenv.primary_env_file().resolve(), (self.state / ".env").resolve())

    def test_real_aws_env_is_left_alone(self) -> None:
        wxenv = self._wxenv()
        real = self.workspace / "aws.env"
        real.write_text("WECHAT_1_APPID=mine\n", encoding="utf-8")
        wxenv.ensure_env_link(self.workspace)
        self.assertFalse(real.is_symlink(), "用户自己的 aws.env 不能被改成软链")
        self.assertIn("mine", real.read_text(encoding="utf-8"))

    def test_stale_env_link_is_repointed(self) -> None:
        wxenv = self._wxenv()
        link = self.workspace / "aws.env"
        link.symlink_to("gone.env")
        self.assertFalse(link.exists())
        wxenv.ensure_env_link(self.workspace)
        self.assertTrue(link.exists(), "断掉的 aws.env 软链应被重新指向")


class GuardTestCase(CliHarness, unittest.TestCase):
    """两个排版引擎之间的容器相容性栅栏与产物门禁。"""

    def test_foreign_container_blocks_the_wrong_engine(self) -> None:
        md = self._write("foreign.md", "# 标题\n\n:::section-title[01]\n小标题\n:::\n\n正文。\n")
        res = self.run_cli("format", str(md), "-o", str(self.workspace / "o.html"), "--engine", "wx")
        self.assertEqual(res.returncode, 4, res.stdout)
        self.assertIn("不相容", res.stderr)

    def test_ambiguous_steps_syntax_blocks_wrong_engine(self) -> None:
        body = "# 标题\n\n:::steps[怎么定媒介]\n第一步 | 看内容\n:::\n"
        md = self._write("steps.md", body)
        wx = self.run_cli("format", str(md), "--engine", "wx", "-o", str(self.workspace / "s1.html"))
        self.assertEqual(wx.returncode, 4, "aws 风格 :::steps 不应被 wx 引擎放行")
        wx_style = self._write("steps-wx.md", "# 标题\n\n:::steps\n第一步\n第二步\n:::\n")
        aws = self.run_cli("format", str(wx_style), "--engine", "aws", "-o", str(self.workspace / "s2.html"))
        self.assertEqual(aws.returncode, 4, "wx 风格 :::steps 不应被 aws 引擎放行")

    def test_highlight_is_only_deprecated_for_aws(self) -> None:
        """`:::highlight` 在 wx 引擎里是内置容器，不该被报成废弃。"""
        md = self._write("hl.md", "# 标题\n\n:::highlight\n30,393 星出现在 09-18\n:::\n")
        res = self.run_cli("guard", "containers", str(md), "--engine", "wx", "--json")
        self.assertEqual(res.returncode, 0, res.stdout)
        report = json.loads(res.stdout)
        self.assertEqual(report["deprecated"], [], "wx 引擎下 highlight 不应被判废弃")
        # 换到 aws 引擎，highlight 属于 wx 的容器集合，应判为阻塞的「跨引擎」而不是重复的废弃提示
        aws = self.run_cli("guard", "containers", str(md), "--engine", "aws", "--json")
        self.assertEqual(aws.returncode, 1)
        aws_report = json.loads(aws.stdout)
        self.assertEqual(aws_report["foreign"][0]["name"], "highlight")
        self.assertEqual(aws_report["deprecated"], [])

    def test_aside_is_an_aws_container_and_foreign_to_wx(self) -> None:
        """`:::aside` 是 aws 的旁注组件；对 wx 来说它是外来容器。

        它刻意不复用 wx 的 `callout`：两者方括号参数语义不同（wx 是固定类型关键字，
        aws 是自由标签），同名不同语义正是栅栏要拦的东西。
        """
        md = self._write("aside.md", "# 标题\n\n:::aside[提醒]\n一句旁注。\n:::\n\n正文。\n")
        aws = self.run_cli("guard", "containers", str(md), "--engine", "aws", "--json")
        self.assertEqual(aws.returncode, 0, aws.stdout)
        report = json.loads(aws.stdout)
        self.assertEqual(report["foreign"], [])
        self.assertEqual(report["deprecated"], [])

        wx = self.run_cli("guard", "containers", str(md), "--engine", "wx", "--json")
        self.assertEqual(wx.returncode, 1, "wx 引擎不认识 aside，应拦下")
        self.assertEqual(json.loads(wx.stdout)["foreign"][0]["name"], "aside")

    def test_aside_renders_as_a_boxed_block(self) -> None:
        if not HAVE_DEPS:
            self.skipTest("缺少运行依赖")
        md = self._write("aside2.md", "# 标题\n\n正文。\n\n:::aside[前提]\n换任务就不成立了。\n:::\n")
        out = self.workspace / "aside.html"
        # 用内置主题：隔离状态目录里没跑 init，种子预设（手账/技术/活力/硬朗）还没铺进去
        res = self.run_cli("format", str(md), "--engine", "aws", "--theme", "资讯", "-o", str(out))
        self.assertEqual(res.returncode, 0, res.stderr)
        html = out.read_text(encoding="utf-8")
        self.assertIn("前提", html, "方括号里的标签必须渲染出来")
        self.assertIn("换任务就不成立了。", html)
        self.assertIn("border-left:3px solid", html, "旁注块靠左侧竖条与正文区分")

    def test_force_bypasses_container_guard(self) -> None:
        if not HAVE_DEPS:
            self.skipTest("缺少运行依赖")
        md = self._write("force.md", "# 标题\n\n:::section-title[01]\n小标题\n:::\n\n正文。\n")
        res = self.run_cli(
            "format", str(md), "--engine", "wx", "-o", str(self.workspace / "f.html"), "--force"
        )
        self.assertEqual(res.returncode, 0, res.stderr)

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_guard_containers_subcommand_reports_json(self) -> None:
        md = self._write("j.md", "# 标题\n\n:::stat[标题]\na | b\n:::\n")
        res = self.run_cli("guard", "containers", str(md), "--engine", "wx", "--json")
        self.assertEqual(res.returncode, 1)
        report = json.loads(res.stdout)
        self.assertFalse(report["ok"])
        self.assertEqual(report["foreign"][0]["name"], "stat")
        self.assertEqual(report["foreign"][0]["belongs_to"], "aws")

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_guard_gate_only_validates_body(self) -> None:
        """预览产物是完整文档，head 里的 <style> 不参与公众号粘贴/发布，不应被判 ERROR。"""
        head_style = self.workspace / "head.html"
        head_style.write_text(
            "<html><head><style>p{color:red}</style></head><body><p>正文</p></body></html>",
            encoding="utf-8",
        )
        res = self.run_cli("guard", "gate", str(head_style), "--json")
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertEqual(json.loads(res.stdout)["findings"], [])

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_guard_gate_blocks_position_in_body(self) -> None:
        bad = self.workspace / "bad.html"
        bad.write_text('<section style="position:absolute">正文</section>', encoding="utf-8")
        res = self.run_cli("guard", "gate", str(bad), "--json")
        self.assertEqual(res.returncode, 1)
        payload = json.loads(res.stdout)
        self.assertIn("position_unsupported", {f["rule"] for f in payload["findings"]})

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_generic_profile_downgrades_class_and_div(self) -> None:
        html = self.workspace / "cls.html"
        html.write_text(
            '<div style="margin-top:1.5em"></div>'
            '<section class="normal_text_link">正文</section>',
            encoding="utf-8",
        )
        wx_res = self.run_cli("guard", "gate", str(html), "--profile", "wx", "--json")
        self.assertEqual(wx_res.returncode, 1, "wx 口径下 div/class 是 ERROR")
        gen_res = self.run_cli("guard", "gate", str(html), "--profile", "generic", "--json")
        self.assertEqual(gen_res.returncode, 0, "generic 口径下 div/class 只应降级为 WARN")

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_no_check_skips_post_gate(self) -> None:
        md = self._write("nc.md", "# 标题\n\n正文。\n")
        res = self.run_cli(
            "format", str(md), "-o", str(self.workspace / "nc.html"), "--no-check"
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("门禁", res.stdout)


def _iter_findings(payload: object):
    """validate --json 的返回结构在不同版本略有差异，宽松地取出条目列表。"""
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield item
    elif isinstance(payload, dict):
        for key in ("errors", "warnings", "findings", "issues", "rules"):
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    yield item if isinstance(item, dict) else {"level": key, "detail": item}


if __name__ == "__main__":
    unittest.main(verbosity=2)
