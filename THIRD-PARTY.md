# 第三方组件与许可

本仓库的 `wechat-article/scripts/` 下内嵌了两套第三方开源代码（vendored），
**许可证与版权归各自的作者所有**，原件全文见 `third_party/`。

| 内嵌路径 | 来源项目 | 许可证 | 许可全文 |
|---|---|---|---|
| `wechat-article/scripts/wxengine/` | `imraywang/wewrite` | MIT | [third_party/LICENSE-wewrite](third_party/LICENSE-wewrite) |
| `wechat-article/scripts/aws/` | `aiworkskills/wechat-article-skills` | Apache-2.0 | [third_party/LICENSE-wechat-article-skills](third_party/LICENSE-wechat-article-skills) |

两个上游项目**未随本仓库分发**（它们的独立 Git 仓库只保留在本地 `reference/`，已加入 `.gitignore`）。
需要对照原始版本时请自行克隆：

```bash
git clone https://github.com/imraywang/wewrite.git reference/wewrite
git clone https://github.com/aiworkskills/wechat-article-skills.git reference/wechat-article-skills
```

## 对内嵌代码所做的修改（按 Apache-2.0 第 4(b) 条声明）

1. **目录与包名**：`wewrite` 包改名为 `wxengine`（含其内部命令表的模块路径），避免与外部安装的
   同名包冲突。**代码逻辑本身未改动**，仅改路径解析。
2. **状态与配置解析**：新增 `wechat-article/scripts/wxenv.py`，由它注入 `WEWRITE_HOME` 指向统一的
   状态目录 `~/.wxarticle`，并在工作区建立 `.aws-article` / `aws.env` 兼容软链，
   使两套引擎共用同一份配置与密钥。**上游源码中读写路径的分支未被修改。**
3. **封面标记处理**：`wxengine/toolkit/converter.py` 的 `_process_images` 增加一条规则——
   alt 含「封面」或 `cover` 开头的图片不进正文（与另一套引擎行为对齐，避免正文出现不会被上传的坏图）。
4. **新增模块**：`wechat-article/scripts/wxart.py`（统一 CLI）、`wxguard.py`（引擎容器栅栏与产物门禁）、
   `make_cover.py`（无生图模型时的本地封面合成）、`wxshot.py`（排版产物截图核对观感）、
   `redraft.py`（走 `draft/update` 原地更新草稿）、`make_deco.py` + `wxdeco.py`
   （装饰底图生成与图床换链，做 `background-image` 的纸纹/花边）为本项目原创。
5. **新增版式组件**：`aws/aws-wechat-article-formatting/references/components/aside.yaml`（旁注块）
   为本项目新增，上游没有这个组件。**未修改任何既有组件或主题 YAML。**
   命名选出 `aside` 而非复用 wx 引擎的 `callout`，是因为两者的方括号参数语义不同
   （wx 是固定类型关键字 `tip`/`warning`/`info`/`danger`，aws 组件是自由标签）——
   同名不同语义会被 `wxguard.py` 的容器栅栏判为冲突。同处新增 `aside` 到该栅栏的 aws 容器集合。
6. **文档**：`references/20-wechat-html-constraints.md` 增补了 2026-10-04 的第二批探针结果
   （11 项，10 通过 / 1 被删），属本项目实测记录，非上游内容。

## 本项目原创部分的许可

除上表内嵌的第三方代码外，本仓库的文档、提示词层、`wxart` / `wxguard` / `wxenv` /
`make_cover` / `wxshot` / `redraft` / `make_deco` / `wxdeco` 等原创代码按 [LICENSE](LICENSE) 授权。
