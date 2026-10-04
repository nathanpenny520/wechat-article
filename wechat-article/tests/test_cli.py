"""CLI 集成测试：原生命令、两个引擎的分发、排版产物与微信兼容校验。

依赖运行依赖（pyyaml/markdown/bs4/cssutils/pygments/requests）。
缺依赖时整类跳过，不误报失败。运行：
    python3 -m unittest tests.test_cli -v
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

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

    def test_doctor_hints_about_the_offline_docs_mirror(self) -> None:
        """首次自检要提示可以抓一份官方文档，但**不能**把它算成待办。

        用 info 而不是 warn：这是「要不要顺手抓一份」的建议。判成 warn 会把
        「全部通过」改成「N 项提示」，等于把可选建议算进待处理清单。
        """
        res = self.run_cli("doctor", "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        report = json.loads(res.stdout)
        entry = next(c for c in report["checks"] if c["check"] == "docs.mirror")
        self.assertEqual(entry["level"], "info")
        self.assertIn("wxart docs fetch", entry["hint"])
        self.assertEqual(report["info"], 1)
        # 关键：info 不进 warnings，也不影响退出码
        self.assertNotIn("docs.mirror", [c["check"] for c in report["checks"] if c["level"] == "warn"])
        self.assertEqual(report["errors"], 0)

    def test_doctor_reports_a_fetched_mirror_with_page_count(self) -> None:
        """抓过之后就变成 ok 并带上页数；INDEX.md 不算一页。"""
        root = self.state / "wechat-docs" / "doc" / "subscription" / "api"
        root.mkdir(parents=True)
        for i in range(3):
            (root / f"p{i}.md").write_text("x" * 300, encoding="utf-8")
        (self.state / "wechat-docs" / "INDEX.md").write_text("# 索引", encoding="utf-8")

        res = self.run_cli("doctor", "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        report = json.loads(res.stdout)
        entry = next(c for c in report["checks"] if c["check"] == "docs.mirror")
        self.assertEqual(entry["level"], "ok")
        self.assertIn("3 页", entry["detail"])
        self.assertEqual(report["info"], 0)

    def test_doctor_stays_non_interactive(self) -> None:
        """doctor 会被 agent 与脚本非交互调用——卡在 input() 上比少问一句严重得多。

        用闭合的 stdin 跑：任何 input() 都会立刻 EOFError。
        """
        env = dict(self.env)
        res = subprocess.run(
            [sys.executable, str(WXART), "doctor"],
            cwd=str(self.workspace), env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("Traceback", res.stderr)

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

    @unittest.skipUnless(BROWSER, "本机没有 Chromium 内核浏览器")
    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_shot_keeps_every_input_when_names_collide(self) -> None:
        """对比不同主题时输入往往同名（各有各目录的 article.html），不能互相覆盖。"""
        a = self.workspace / "t1"
        b = self.workspace / "t2"
        for d, color in ((a, "#FF0000"), (b, "#0000FF")):
            d.mkdir()
            (d / "article.html").write_text(
                f'<section style="padding:16px;color:{color}"><p>主题对比</p></section>',
                encoding="utf-8")
        out = self.workspace / "cmp.png"
        res = self.run_cli("shot", str(a / "article.html"), str(b / "article.html"), "-o", str(out))
        self.assertEqual(res.returncode, 0, res.stderr)
        produced = sorted(p.name for p in self.workspace.glob("cmp-*.png"))
        self.assertEqual(len(produced), 3, f"应出两张单图 + 一张对照图，实际 {produced}")

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

    @unittest.skipUnless(BROWSER, "本机没有 Chromium 内核浏览器")
    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_shot_resolves_relative_body_images(self) -> None:
        """正文图是相对路径，而截图会把片段搬进临时目录——不补 <base> 就整篇图裂。

        判据用内容高度：图在时高度里含图的高度，图裂时只剩 alt 文字那一丁点。
        """
        from PIL import Image

        d = self.workspace / "art"
        (d / "imgs").mkdir(parents=True)
        # 686x800 的实心图：按 width:100% 渲染到 375px 宽时约 437px 高，差异足够明显
        Image.new("RGB", (686, 800), (200, 30, 30)).save(d / "imgs" / "x.png")
        (d / "article.html").write_text(
            '<section><img src="imgs/x.png" style="display:block;width:100%;height:auto;"></section>',
            encoding="utf-8")

        res = self.run_cli("shot", str(d / "article.html"), "-o", str(self.workspace / "s.png"))
        self.assertEqual(res.returncode, 0, res.stderr)
        height = int(re.search(r"内容高度 (\d+)px", res.stdout).group(1))
        self.assertGreater(height, 300, f"图没渲染出来（内容高度只有 {height}px）")

    # ------------------------------------------------------------ 装饰底图（deco）

    _ACCENT_HTML = (
        '<section style="color:#111111; background:#F4F5F7;">'
        + "".join(f'<p style="color:#2E7BF6;">第 {i} 段</p>' for i in range(6))
        + '<p style="color:#111111;">中性色出现更多但不该被选中</p></section>'
    )

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_deco_detects_the_theme_accent_from_the_product(self) -> None:
        """装饰色必须跟主题一致，否则会变成「第二套配色」。

        产物里出现最多的是灰、近黑这类中性色，它们不是主色，必须被排除。
        """
        md = self._write("acc.md", "# 标题\n\n正文一段。\n")
        html = self.workspace / "acc.html"
        self.assertEqual(self.run_cli("format", str(md), "-o", str(html)).returncode, 0)
        html.write_text(self._ACCENT_HTML, encoding="utf-8")
        out = self.workspace / "acc-deco.html"
        res = self.run_cli("deco", str(html), "-o", str(out), "--no-upload", "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        report = json.loads(res.stdout)
        self.assertEqual(report["accent"], "#2E7BF6")
        self.assertIn("#2E7BF6", report["accent_source"])

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_deco_accepts_an_explicit_accent(self) -> None:
        html = self._write("exp.html", self._ACCENT_HTML)
        res = self.run_cli("deco", str(html), "-o", str(self.workspace / "exp-d.html"),
                           "--no-upload", "--accent", "#0F4C81", "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        report = json.loads(res.stdout)
        self.assertEqual(report["accent"], "#0F4C81")
        self.assertIn("命令行指定", report["accent_source"])

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_deco_writes_real_background_image_declarations(self) -> None:
        """`--no-upload` 的产物要能被本地渲染：底图内联、写法与线上完全一致。"""
        html = self._write("d1.html", self._ACCENT_HTML)
        out = self.workspace / "d1-out.html"
        res = self.run_cli("deco", str(html), "-o", str(out), "--skin", "full", "--no-upload")
        self.assertEqual(res.returncode, 0, res.stderr)
        body = out.read_text(encoding="utf-8")
        self.assertIn("data:image/png;base64,", body, "本地预览必须内联底图")
        self.assertIn("background-image:url(", body)
        self.assertIn("background-repeat:repeat", body, "纸纹必须可平铺")
        self.assertIn("border-radius:20px", body, "花边框的四角靠 border-radius")
        self.assertIn("background-position:center center", body, "花边带要居中不重复")
        # 关键：不能出现定位声明 —— 微信把 position 整条删掉，
        # 靠它定位的角标会全部堆到正文最前面。注意 background-position 不在其列。
        for bad in ("position:absolute", "position:fixed", "position:relative", "position: sticky"):
            self.assertNotIn(bad, body)

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_deco_paper_skin_only_adds_texture(self) -> None:
        html = self._write("d2.html", self._ACCENT_HTML)
        out = self.workspace / "d2-out.html"
        res = self.run_cli("deco", str(html), "-o", str(out), "--skin", "paper", "--no-upload")
        self.assertEqual(res.returncode, 0, res.stderr)
        body = out.read_text(encoding="utf-8")
        self.assertIn("background-repeat:repeat", body)
        self.assertNotIn("border-radius:20px", body, "paper 皮肤不加花边框")
        self.assertNotIn("background-position:center center", body, "paper 皮肤没有花边带")

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_deco_refuses_to_silently_inline_when_publishing(self) -> None:
        """要进草稿箱就不能退化成 data: URI——微信不认，图会全丢。

        隔离工作区里没有微信凭证，所以必须**失败**，而不是悄悄内联一个发不出去的产物。
        """
        html = self._write("d3.html", self._ACCENT_HTML)
        out = self.workspace / "d3-out.html"
        res = self.run_cli("deco", str(html), "-o", str(out))
        self.assertNotEqual(res.returncode, 0, "没有凭证时不该成功")
        self.assertFalse(out.exists(), "失败时不该留下一个内联底图的半成品")
        self.assertNotIn("data:image", res.stdout + res.stderr)

    def test_deco_reports_missing_input(self) -> None:
        res = self.run_cli("deco", str(self.workspace / "nope.html"), "-o", str(self.workspace / "o.html"))
        self.assertEqual(res.returncode, 2)
        self.assertIn("文件不存在", res.stderr)

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


class MakeDecoTest(unittest.TestCase):
    """底图生成器的确定性契约。

    这些不是「画得好不好看」的测试——观感靠 `wxart shot` 看。这里测的是**再生成一次
    必须一模一样**，以及平铺/翻转这两个会被 background 参数依赖的性质。
    """

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_assets_are_deterministic(self) -> None:
        """同一主色两次生成必须逐字节一致——目录名按指纹去重，不一致会白白多传图。"""
        import io

        import make_deco

        accent = (0x2E, 0x7B, 0xF6)
        cases = {
            "tile": lambda: make_deco.make_dot(accent),
            "band": lambda: make_deco.make_band(accent),
            "band_flip": lambda: make_deco.make_band(accent, flip=True),
        }
        for name, make in cases.items():
            a, b = io.BytesIO(), io.BytesIO()
            make().save(a, "PNG")
            make().save(b, "PNG")
            self.assertEqual(a.getvalue(), b.getvalue(), f"{name} 两次生成不一致")

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_tile_grid_period_divides_the_canvas(self) -> None:
        """平铺的接缝：点阵周期必须整除画布边长，否则接缝处会出现半截点。"""
        import make_deco

        im = make_deco.make_dot((0x2E, 0x7B, 0xF6))
        n = im.size[0]
        self.assertEqual(n % make_deco.TILE_CSS, 0)
        # 点是画在 (0,0) 与正中的，两者颜色相同 → 平铺后是规整网格
        self.assertEqual(im.getpixel((0, 0)), im.getpixel((n // 2, n // 2)))
        self.assertNotEqual(im.getpixel((0, 0)), im.getpixel((n // 4, n // 4)),
                            "点与底必须有色差，否则平铺看不见")

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_band_flip_is_the_vertical_mirror(self) -> None:
        import make_deco
        from PIL import Image

        accent = (0xC0, 0x39, 0x2B)
        base = make_deco.make_band(accent)
        flipped = make_deco.make_band(accent, flip=True)
        self.assertEqual(flipped.tobytes(),
                         base.transpose(Image.FLIP_TOP_BOTTOM).tobytes())

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_no_skin_uses_positioning(self) -> None:
        """四角定位需要 position:absolute，而微信把 position 整条删掉。

        删掉之后角标会依次堆在正文最前面，比没有装饰更糟——所以干脆不生成角标。
        """
        import make_deco

        self.assertFalse(hasattr(make_deco, "make_corner"))


class MakeChartTest(unittest.TestCase):
    """正文配图生成器的确定性契约（观感靠 `wxart shot` 看，这里测结构与不变量）。"""

    def _spec(self, tmp: Path, body: str) -> Path:
        p = tmp / "spec.yaml"
        p.write_text(body, encoding="utf-8")
        return p

    def _run(self, tmp: Path, body: str, out_name: str = "c.png"):
        import make_chart

        spec = yaml.safe_load(body)
        im = make_chart.render(spec)
        out = tmp / out_name
        im.save(out)
        return im, out

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_canvas_width_is_fixed_regardless_of_label_length(self) -> None:
        """标签再长也不能把画布撑宽——图与正文同宽，宽度一变就会缩放变形。"""
        import make_chart

        for label in ("laya", "SemIf-OpenJev", "一个非常非常长的中文项目名称用来测试换行"):
            im = make_chart.render({
                "kind": "bar", "title": "T",
                "items": [{"label": label, "value": 100}],
            })
            self.assertEqual(im.size[0], make_chart.W, f"标签 {label!r} 把画布撑宽了")

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_all_kinds_render(self) -> None:
        specs = {
            "bar": {"kind": "bar", "title": "T", "items": [{"label": "a", "value": 3},
                                                           {"label": "b", "value": 9}]},
            "kpi": {"kind": "kpi", "title": "T", "items": [{"value": "82 亿", "label": "对价"}]},
            "timeline": {"kind": "timeline", "title": "T",
                         "items": [{"date": "9/28", "text": "收购", "note": "同日"}]},
            "compare": {"kind": "compare", "title": "T",
                        "left": {"title": "L", "items": ["甲"]},
                        "right": {"title": "R", "items": ["乙"]}},
        }
        import make_chart

        for kind, spec in specs.items():
            im = make_chart.render(spec)
            self.assertEqual(im.size[0], make_chart.W, kind)
            self.assertGreater(im.size[1], 100, kind)

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_source_line_is_drawn_when_given(self) -> None:
        """图表有很强的视觉权威感，出处必须留在图上——给了 source 就该变高。"""
        import make_chart

        base = {"kind": "kpi", "title": "T", "items": [{"value": "1", "label": "x"}]}
        without = make_chart.render(dict(base)).size[1]
        withsrc = make_chart.render({**base, "source": "数据来源：GitHub REST API"}).size[1]
        self.assertGreater(withsrc, without)

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_unknown_kind_is_rejected(self) -> None:
        import make_chart

        with self.assertRaises(SystemExit):
            make_chart.render({"kind": "pie", "title": "T", "items": []})

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_missing_items_is_rejected(self) -> None:
        import make_chart

        for kind in ("bar", "kpi", "timeline"):
            with self.assertRaises(SystemExit):
                make_chart.render({"kind": kind, "title": "T", "items": []})


class MakeDecoSkinTest(unittest.TestCase):
    """底子 × 花边两维扩展后的契约。"""

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_every_skin_builds_exactly_its_assets(self) -> None:
        import tempfile

        import make_deco

        with tempfile.TemporaryDirectory() as td:
            for skin, (texture, frame) in make_deco.SKINS.items():
                made = make_deco.build(texture, frame, "#2E7BF6", Path(td) / skin)
                self.assertEqual(sorted(made), sorted(make_deco.assets_for(texture, frame)),
                                 f"皮肤 {skin} 产物与声明不一致")

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_flags_override_the_skin_preset(self) -> None:
        import make_deco

        self.assertEqual(make_deco.resolve("full", None, None), ("dot", "single"))
        self.assertEqual(make_deco.resolve("full", "kraft", None), ("kraft", "single"))
        self.assertEqual(make_deco.resolve("full", None, "double"), ("dot", "double"))
        self.assertEqual(make_deco.resolve("paper", "none", "double"), ("none", "double"))

    def test_unknown_texture_or_frame_is_rejected(self) -> None:
        import make_deco

        with self.assertRaises(SystemExit):
            make_deco.resolve("full", "marble", None)
        with self.assertRaises(SystemExit):
            make_deco.resolve("full", None, "triple")

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_double_band_is_taller_than_single(self) -> None:
        """花边带的 CSS 高度必须跟着图走，否则菱形会被压扁。"""
        import make_deco

        self.assertEqual(make_deco.band_height("double"), make_deco.band_height("single") * 2)

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_kraft_stays_warm_under_a_cool_accent(self) -> None:
        """牛皮纸的识别特征是「暖」。主色是冷色时底子不能跟着变灰紫。"""
        import make_deco

        for cool in ("#5B4BFF", "#24406B", "#1F6F5F"):
            im = make_deco.make_kraft(make_deco.parse_hex(cool))
            r, g, b = im.convert("RGB").resize((1, 1)).getpixel((0, 0))
            self.assertGreater(r, b, f"主色 {cool} 下底子偏冷了（R={r} B={b}）")

    @unittest.skipUnless(HAVE_DEPS, "缺少运行依赖")
    def test_grid_and_kraft_tiles_are_seamless(self) -> None:
        """平铺不无缝就会在接缝处出现半截图案。

        判据：把图横向平铺两张，接缝处（第 n-1 列与第 n 列之间）的色差
        不应明显大于图内部的相邻列色差。
        """
        import make_deco
        from PIL import Image

        for builder in (make_deco.make_grid, make_deco.make_kraft):
            tile = builder((0x5B, 0x4B, 0xFF))
            n = tile.size[0]
            doubled = Image.new("RGB", (n * 2, n))
            doubled.paste(tile, (0, 0))
            doubled.paste(tile, (n, 0))

            def coldiff(x):
                a = [doubled.getpixel((x, y)) for y in range(n)]
                b = [doubled.getpixel((x + 1, y)) for y in range(n)]
                return sum(abs(p - q) for pa, pb in zip(a, b) for p, q in zip(pa, pb)) / n

            seam = coldiff(n - 1)
            inner = max(coldiff(x) for x in range(1, n - 2))
            self.assertLessEqual(
                seam, inner * 2 + 30,
                f"{builder.__name__} 接缝色差 {seam:.0f} 明显高于内部 {inner:.0f}，平铺会露馅")


class WeChatDocsTest(unittest.TestCase):
    """文档镜像的纯函数部分（不联网）。"""

    def test_page_to_path_maps_urls_into_a_tree(self) -> None:
        import wechat_docs

        cases = {
            "https://developers.weixin.qq.com/doc/subscription/api/base/api_getaccesstoken.html":
                "doc/subscription/api/base/api_getaccesstoken.md",
            "https://developers.weixin.qq.com/doc/subscription/guide/":
                "doc/subscription/guide/index.md",
        }
        for url, want in cases.items():
            self.assertEqual(str(wechat_docs.page_to_path(url)), want)

    def test_links_stay_inside_the_subscription_scope(self) -> None:
        """同一站点还有小程序 / 支付 / 企业微信；跟着爬会平白多出几千页。"""
        import wechat_docs

        html = """
        <a href="/doc/subscription/api/base/api_getaccesstoken.html">in</a>
        <a href="/doc/miniprogram/dev/api.html">out</a>
        <a href="/doc/oplatform/openApi/api.html">out</a>
        <a href="https://developers.weixin.qq.com/doc/subscription/guide/dev/start.html">in</a>
        <a href="https://example.com/doc/subscription/x.html">out</a>
        """
        got = wechat_docs._links(html, "")
        self.assertEqual(got, [
            "https://developers.weixin.qq.com/doc/subscription/api/base/api_getaccesstoken.html",
            "https://developers.weixin.qq.com/doc/subscription/guide/dev/start.html",
        ])

    def test_markdown_extraction_skips_the_navigation_tree(self) -> None:
        """导航树与正文同层，取「文本最多的 div」会把 170 多项菜单一起抓进来。"""
        import wechat_docs

        html = """
        <html><head><title>新增草稿 | 微信公众号文档</title></head><body>
          <div class="nav"><a>基础接口</a><a>获取接口调用凭据</a><a>自定义菜单</a></div>
          <div class="page-inner"><div class="content custom">
            <h1>新增草稿</h1>
            <p>本接口用于新增草稿。</p>
            <h2>请求参数</h2>
            <table><tr><th>参数</th><th>说明</th></tr>
                   <tr><td>media_id</td><td>素材 id</td></tr></table>
            <pre>POST /cgi-bin/draft/add</pre>
          </div></div>
        </body></html>
        """
        md = wechat_docs.html_to_markdown(html, "https://example.com/x.html")
        self.assertIn("# 新增草稿", md)
        self.assertIn("POST /cgi-bin/draft/add", md)
        self.assertIn("| media_id | 素材 id |", md)
        self.assertNotIn("基础接口", md, "导航树被带进来了")
        self.assertNotIn("获取接口调用凭据", md)

    def test_search_without_a_mirror_tells_you_how_to_get_one(self) -> None:
        """没有镜像时要说清下一步，而不是抛一个找不到目录的 traceback。"""
        with tempfile.TemporaryDirectory(prefix="wxart-docs-") as td:
            env = dict(os.environ, WXARTICLE_HOME=td, WXARTICLE_NO_REEXEC="1")
            res = subprocess.run(
                [sys.executable, str(WXART), "docs", "search", "draft"],
                cwd=td, env=env, capture_output=True, text=True)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("docs fetch", res.stderr)


class ValidateNodeleafTest(unittest.TestCase):
    """nodeleaf 容器：官方规范只允许单个图片/视频/官方组件。

    2026-10-04 真机实测：容器里放 <p> 时 draft/get 回读保留、手机上整段消失，
    所以这一条必须是 ERROR（见 references/20-wechat-html-constraints.md 第 3、7 节）。
    """

    @staticmethod
    def _rules(html: str) -> list[str]:
        from wxengine.commands.validate_html import validate_html
        return [i["rule"] for i in validate_html(html)]

    def test_block_child_inside_nodeleaf_is_error(self) -> None:
        self.assertIn("nodeleaf_content",
                      self._rules('<section nodeleaf="nodeleaf"><p>文字</p></section>'))

    def test_nested_section_inside_nodeleaf_is_error(self) -> None:
        self.assertIn("nodeleaf_content",
                      self._rules('<section nodeleaf><section><img src="a.png"></section></section>'))

    def test_two_children_inside_nodeleaf_is_error(self) -> None:
        self.assertIn("nodeleaf_content",
                      self._rules('<section nodeleaf><img src="a.png"><img src="b.png"></section>'))

    def test_unclosed_nodeleaf_still_reports(self) -> None:
        """未闭合时按到文末处理——宁可多报，也不要因为缺 </section> 就静默放过。"""
        self.assertIn("nodeleaf_content", self._rules("<section nodeleaf><p>文字</p>"))

    def test_single_image_inside_nodeleaf_passes(self) -> None:
        self.assertNotIn("nodeleaf_content",
                         self._rules('<section nodeleaf><img src="a.png" alt=""></section>'))

    def test_empty_nodeleaf_is_warning_not_error(self) -> None:
        issues = [i for i in __import__("wxengine.commands.validate_html",
                                        fromlist=["validate_html"]).validate_html(
            "<section nodeleaf></section>")]
        self.assertEqual([i["level"] for i in issues], ["WARN"])

    def test_plain_section_and_attributes_are_untouched(self) -> None:
        """普通 section、以及属性里带 `>` 的写法都不该被误伤。"""
        self.assertEqual(self._rules("<section><p>正常段落</p></section>"), [])
        self.assertEqual(self._rules('<section data-x="a>b"><p>文字</p></section>'), [])


class ValidateQuotedUrlTest(unittest.TestCase):
    """url() 带引号：2026-10-04 探针实测——整个元素会被拆掉，不只是属性被删。

    逐项验证过：单引号/双引号、http/https、有无 repeat/size、section 内有无内容，
    五种构造全部失败；只有不带引号的 `url(http://…)` 活下来。
    """

    @staticmethod
    def _rules(html: str) -> list[str]:
        from wxengine.commands.validate_html import validate_html
        return [i["rule"] for i in validate_html(html)]

    def test_single_quote_is_error(self) -> None:
        self.assertIn("quoted_url",
                      self._rules("<section style=\"background-image:url('https://a.com/x.png')\"></section>"))

    def test_double_quote_is_error(self) -> None:
        self.assertIn("quoted_url",
                      self._rules('<section style=\'background-image:url("https://a.com/x.png")\'></section>'))

    def test_bare_url_passes(self) -> None:
        self.assertEqual(
            self._rules('<section style="background-image:url(https://a.com/x.png);background-repeat:repeat"></section>'),
            [])

    def test_font_family_quotes_are_not_flagged(self) -> None:
        """引号本身不是问题，`url()` 里的引号才是——别误伤 font-family。"""
        self.assertEqual(self._rules('<p style="font-family:&quot;Menlo&quot;,Consolas,monospace">x</p>'), [])
