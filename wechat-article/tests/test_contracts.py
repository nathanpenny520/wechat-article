"""静态契约测试：SKILL.md 与 references 的结构、门禁与内部链接。

这些测试不依赖第三方库，可直接跑：
    python3 -m unittest tests.test_contracts -v
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = SKILL_ROOT / "SKILL.md"
REFERENCES = SKILL_ROOT / "references"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestSkillFrontmatter(unittest.TestCase):
    def setUp(self) -> None:
        self.text = read(SKILL_MD)

    def test_has_frontmatter_with_name_and_description(self) -> None:
        self.assertTrue(self.text.startswith("---\n"), "SKILL.md 必须以 YAML frontmatter 开头")
        end = self.text.index("\n---\n", 4)
        fm = self.text[4:end]
        self.assertIn("name: wechat-article", fm)
        self.assertRegex(fm, r"description:")
        self.assertIn("allowed-tools:", fm)

    def test_description_has_wechat_triggers_and_negative_scope(self) -> None:
        fm = self.text[: self.text.index("\n---\n", 4)]
        for kw in ("公众号", "微信推文", "草稿箱", "排版"):
            self.assertIn(kw, fm, f"触发关键词缺 {kw}")
        for excluded in ("博客", "邮件", "PPT"):
            self.assertIn(excluded, fm, f"负向边界缺 {excluded}")

    def test_single_entry_mentions_allowed_tools(self) -> None:
        for tool in ("Bash", "Read", "Write", "Edit", "Glob", "Grep"):
            self.assertIn(tool, self.text)


class TestHardGates(unittest.TestCase):
    """主入口必须写明四道不可绕过的门禁。"""

    def setUp(self) -> None:
        self.text = read(SKILL_MD)

    def test_publish_requires_explicit_permission(self) -> None:
        self.assertIn("wxart run permission publish allow", self.text)
        self.assertRegex(self.text, r"不可逆动作")

    def test_image_and_publish_never_auto_trigger(self) -> None:
        self.assertRegex(self.text, r"排版和发布都不许偷偷触发生图|不会因此自动生图|不得为了排版或发布自动触发生图")

    def test_review_gate_blocks_article_md(self) -> None:
        self.assertIn("publishable", self.text)
        self.assertRegex(self.text, r"只有.*publishable.*才.*article\.md|只有编辑决定为 `pass`")

    def test_finish_before_format_and_publish(self) -> None:
        self.assertIn("wxart run finish", self.text)
        i_finish = self.text.index("wxart run finish")
        i_format = self.text.index("references/05-format.md")
        self.assertLess(i_finish, i_format, "封存必须排在排版之前")

    def test_writes_are_before_draft(self) -> None:
        self.assertRegex(self.text, r"brief\.yaml.*claims\.yaml.*再写 `draft\.md`|先落盘 `brief\.yaml` 与 `claims\.yaml`")

    def test_no_fabrication_rule_present(self) -> None:
        self.assertRegex(self.text, r"不编造|不得把模型记忆")

    def test_gate_table_exists(self) -> None:
        self.assertIn("中间产物门禁", self.text)
        self.assertRegex(self.text, r"禁止跳步")

    def test_single_task_dir_rule(self) -> None:
        self.assertRegex(self.text, r"一篇文章一个任务目录|runs/<run_id>/")


class TestReferenceLinks(unittest.TestCase):
    def test_every_referenced_doc_exists(self) -> None:
        text = read(SKILL_MD)
        linked = set(re.findall(r"\]\(references/([^)]+\.md)\)", text))
        self.assertGreaterEqual(len(linked), 13, f"主入口应引用全部阶段文档，实际 {len(linked)}")
        for name in sorted(linked):
            self.assertTrue((REFERENCES / name).exists(), f"引用了不存在的文档: references/{name}")

    def test_cross_references_inside_references_resolve(self) -> None:
        for doc in REFERENCES.glob("*.md"):
            body = read(doc)
            for target in re.findall(r"\]\((\d\d-[a-z-]+\.md)\)", body):
                self.assertTrue(
                    (REFERENCES / target).exists(),
                    f"{doc.name} 引用了不存在的 {target}",
                )

    def test_all_stage_docs_are_non_trivial(self) -> None:
        expected = [
            "00-workflow.md", "01-setup.md", "02-topic.md", "03-write.md", "04-review.md",
            "05-format.md", "06-visual.md", "07-publish.md", "10-learn.md", "11-stats.md",
            "12-rewrite.md", "13-products.md", "20-wechat-html-constraints.md",
            "21-quality-rubric.md",
        ]
        for name in expected:
            path = REFERENCES / name
            self.assertTrue(path.exists(), f"缺少 {name}")
            lines = len(read(path).splitlines())
            self.assertGreater(lines, 60, f"{name} 只有 {lines} 行，内容过于单薄")


class TestWorkflowContract(unittest.TestCase):
    def setUp(self) -> None:
        self.text = read(REFERENCES / "00-workflow.md")

    def test_defines_two_tier_state(self) -> None:
        self.assertIn("~/.wxarticle/", self.text)
        self.assertIn(".aws-article", self.text)
        self.assertRegex(self.text, r"软链|symlink|alias")

    def test_lists_engine_defaults(self) -> None:
        for cmd in ("wxart format", "wxart image", "wxart publish"):
            self.assertIn(cmd, self.text)
        self.assertRegex(self.text, r"--engine")

    def test_lists_task_artifacts(self) -> None:
        for artifact in (
            "state.yaml", "brief.yaml", "claims.yaml", "draft.md", "review-report.json",
            "article.md", "article.yaml", "article.html", "article-illustrated.md",
        ):
            self.assertIn(artifact, self.text)

    def test_gate_table_marks_placeholders(self) -> None:
        self.assertIn("placeholder", self.text)


class TestSetupContract(unittest.TestCase):
    def setUp(self) -> None:
        self.text = read(REFERENCES / "01-setup.md")

    def test_documents_required_and_optional_deps(self) -> None:
        self.assertIn("PyYAML", self.text)
        self.assertIn("Pillow", self.text)
        self.assertRegex(self.text, r"可选")

    def test_documents_exit_code_semantics(self) -> None:
        self.assertRegex(self.text, r"退出码 1 是硬错误|退出码 2 才是")

    def test_warns_about_windows_python3(self) -> None:
        self.assertIn("Microsoft Store", self.text)

    def test_credentials_discipline(self) -> None:
        self.assertRegex(self.text, r"不要向用户索取密钥")


class TestDocCliSync(unittest.TestCase):
    """文档与 CLI 的同步守卫：文档里出现的命令必须真实存在。

    反方向（新命令必须被文档提到）不强制——`home`、`validate-env` 这类诊断命令
    可以不进用户文档。
    """

    def _corpus(self) -> dict[str, str]:
        docs = {"SKILL.md": read(SKILL_MD)}
        for path in sorted(REFERENCES.glob("*.md")):
            docs[path.name] = read(path)
        return docs

    def _known_commands(self) -> set[str]:
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        import wxart  # noqa: WPS433

        return set(wxart.COMMANDS) | set(wxart.ENGINE_SWITCH) | {"home", "diagnose"}

    def test_documented_commands_exist(self) -> None:
        known = self._known_commands()
        offenders: list[str] = []
        for name, body in self._corpus().items():
            for cmd in re.findall(r"wxart ([a-z][a-z0-9-]*)", body):
                if cmd not in known:
                    offenders.append(f"{name}: wxart {cmd}")
        self.assertEqual(sorted(set(offenders)), [], f"文档引用了不存在的命令: {sorted(set(offenders))}")

    def test_every_engine_switch_is_documented(self) -> None:
        for body in self._corpus().values():
            if "--engine" in body:
                break
        else:
            self.fail("文档里没有任何 --engine 说明")

    def test_workflow_documents_the_engine_collision(self) -> None:
        body = read(REFERENCES / "00-workflow.md")
        self.assertIn("steps", body)
        self.assertRegex(body, r"同名")
        self.assertIn("wxart guard containers", body)
        self.assertIn("--force", body)
        self.assertIn("--no-check", body)


class TestComponentGuardSync(unittest.TestCase):
    """版本组件与容器栅栏必须同步。

    这条守的是一个**静默失效**：新增一个内置 aws 组件、却忘了把它登记进
    `wxguard.ENGINE_CONTAINERS["aws"]`，结果是渲染器认识它、栅栏不认识——
    `wxart guard containers` 会把合法的 `:::新组件` 判成「外来容器」而拦下排版。
    反过来，栅栏里留着一个已经不存在的组件名，则会让真正写错的容器悄悄过闸。
    所以两侧必须**恰好相等**。
    """

    COMPONENTS = (SKILL_ROOT / "scripts" / "aws" / "aws-wechat-article-formatting"
                  / "references" / "components")
    #: 骨架目录里的内部组件：不是 `:::` 容器，由渲染器按结构自动触发。
    INTERNAL = {"article-end", "h2-deco", "hr-deco", "img-deco", "li-label"}

    def _generic_names(self) -> set[str]:
        return {p.stem for p in self.COMPONENTS.glob("*.yaml")}

    def _guard_aws_names(self) -> set[str]:
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        import wxguard  # noqa: WPS433

        return set(wxguard.ENGINE_CONTAINERS["aws"])

    def test_generic_components_match_the_aws_container_set(self) -> None:
        generic, guard = self._generic_names(), self._guard_aws_names()
        self.assertEqual(
            sorted(guard - generic), [],
            "栅栏认识这些容器，但内置组件里没有 —— 写了会渲染成普通文本却过闸",
        )
        self.assertEqual(
            sorted(generic - guard), [],
            "这些内置组件没登记进栅栏 —— 用它们会被误判成外来容器而拦下排版",
        )

    def test_skeleton_overrides_only_reuse_known_names(self) -> None:
        """骨架专属版只能是「通用组件」或「内部装饰件」，不能凭空造新容器名。"""
        allowed = self._generic_names() | self.INTERNAL
        offenders = []
        for sub in sorted(p for p in self.COMPONENTS.iterdir() if p.is_dir()):
            for f in sorted(sub.glob("*.yaml")):
                if f.stem not in allowed:
                    offenders.append(f"{sub.name}/{f.name}")
        self.assertEqual(offenders, [], f"骨架目录出现了未登记的新名字: {offenders}")

    def test_note_and_highlight_stay_removed(self) -> None:
        """`note` 与 `highlight` 是已删除的名字，不能被重新占用（栅栏里仍登记为废弃）。"""
        generic = self._generic_names()
        for gone in ("note", "highlight"):
            self.assertNotIn(gone, generic, f"{gone} 曾被删除，不应重新出现")
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        import wxguard  # noqa: WPS433

        for gone in ("note", "highlight"):
            self.assertIn(gone, wxguard.DEPRECATED, f"{gone} 应仍在废弃表里")


class TestNoUpstreamLeakage(unittest.TestCase):
    """交付文档里不应残留上游品牌与迁移叙事。

    `aiworkskills.cn` 是预设包下载地址的白名单域名（功能事实，代码里强校验），
    `~/.wewrite` / `$WEWRITE_HOME` 是迁移旧状态时必须点名的历史路径——这两类放行。
    """

    FORBIDDEN = ("wewrite", "clawhub", "aws-wechat-article")
    ALLOWED_PATTERNS = (
        r"~/\.wewrite",
        r"\$WEWRITE_HOME",
        r"WEWRITE_HOME",
        r"aiworkskills\.cn",
    )

    def _scan(self, body: str) -> list[str]:
        cleaned = body
        for pattern in self.ALLOWED_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.I)
        hits = []
        low = cleaned.lower()
        for token in self.FORBIDDEN:
            if token in low:
                hits.append(token)
        return hits

    def test_references_do_not_mention_upstream_names(self) -> None:
        offenders = []
        for doc in list(REFERENCES.glob("*.md")) + [SKILL_MD]:
            for token in self._scan(read(doc)):
                offenders.append(f"{doc.name}: {token}")
        self.assertEqual(offenders, [], f"文档残留上游命名: {offenders}")

    def test_skill_md_stays_self_contained(self) -> None:
        self.assertEqual(self._scan(read(SKILL_MD)), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
