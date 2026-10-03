# 全流程工作流与状态契约

这份文档定义**唯一**的状态真源、目录约定、阶段门禁与恢复规则。主入口只在需要细节时读它。

## 1. 两层状态：用户级 + 本篇级

整合前两个项目各有一套状态约定，这里是收敛后的结论：

| 层 | 位置 | 谁写 | 放什么 |
|---|---|---|---|
| **用户级状态** | `~/.wxarticle/`（`$WXARTICLE_HOME` 覆盖） | `wxart` 与两个引擎 | `config.yaml`（账号配置）、`.env`（密钥）、`style.yaml`（写作风格）、`history.yaml`（历史与数据）、`playbook.md`（学习规则）、`runs/`（所有文章任务）、`exemplars/`（范文库）、`corpus/`（历史语料）、`lessons/`（修改学习）、`themes/`、`personas/`、`presets/`（预设库）、`products/`（业务资料库） |
| **项目覆盖层**（可选） | `<工作区>/.wxarticle/` | 用户 | 只放需要按项目区分的同名字段；不建则全部走用户级 |
| **兼容软链** | `<工作区>/.aws-article` → 上面二者之一 | `wxart init` | 仅为了让上游引擎零改动地读到同一份配置 |

**一个仓库对应一个公众号**时才需要项目覆盖层。工作区根存在真实的 `.wxarticle/` 目录时它就是生效的配置目录；否则生效的是 `~/.wxarticle/`。

密钥**只写**在 `~/.wxarticle/.env`（或工作区根的 `aws.env`），不写进 `config.yaml`。

```bash
wxart env      # 打印上述所有实际路径与来源
wxart doctor   # 检查依赖、配置、凭证、发布方式
```

## 2. 本篇任务目录

一篇文章 = 一个目录：`{state_home}/runs/<run_id>/`，`run_id` 形如 `20260715-120000-a1b2c3`。

这里是**两个引擎共用同一个目录**——这是整套整合的关键。左边是 wx 引擎的产物，
右边是 aws 引擎的产物，同一篇文章把它们放在一起，互相读对方的输出。

```
runs/<run_id>/
├── state.yaml               # 任务真源（version 4）。只通过 wxart run 读写，禁止手改
├── brief.yaml               # 文章任务书（写作阶段）
├── claims.yaml              # 主张与证据（写作阶段）
├── sources.yaml             # 事实来源账本（wxart sources add）
├── draft.md                 # 初稿——不是成稿
├── assessment.yaml          # 审稿临时输入（Agent 写，content-eval 消费）
├── review-report.json       # 编辑报告：五维分、阻断项、publishable、改动幅度
├── article.md               # 成稿。审稿通过后写入；封存后只读
├── article.yaml             # 本篇发文元数据（wxart article-init 生成）
├── article.html             # 微信兼容 HTML（排版产物，发布正文来源）
├── cover.png                # 封面（2.35:1）
├── imgs/                    # 正文配图
├── article-illustrated.md   # 带图副本。原始 article.md 永不被覆盖
├── image-prompts.md         # 图片提示词（无图片服务时的降级产物）
├── images.json              # 批量生图清单
├── preview.html             # 本地预览页
├── format.log               # 排版日志（上游约定：脚本输出一律落盘）
├── image-generation.log     # 生图日志
├── publish.log              # 发布日志
├── source.md                # 多平台改写的源稿副本
├── xiaohongshu.md           # 小红书版
└── douyin.md                # 抖音版
```

**约定**：脚本输出一律落盘到本篇目录的 `<环节>.log`（`format.log` / `image-generation.log` /
`cover-generation.log` / `publish.log`）。屏幕上滚过去就没了，日志是排障的唯一凭据。

## 3. 命令速查（按阶段）

```bash
# 环境
wxart doctor                                    # 自检，退出码 0 才继续
wxart init                                      # 建状态目录/配置模板/预设库/受管 venv
wxart env                                       # 看路径与来源

# 任务
wxart run start --topic "…" --mode draft --visual-mode none
wxart run list / show / resume <run_id>
wxart run update --patch '<JSON>'
wxart run step <topic|write|review|visual|publish> <状态>
wxart run permission publish allow|deny
wxart run finish

# 选题
wxart hotspots --limit 30
wxart search-articles "AI编程" -n 15 -t 2
wxart seo --json "关键词"

# 写作
wxart draft prompt …                             # 只出写作提示词
wxart draft draft … / rewrite … / continue …     # 调写作模型出稿
wxart draft check … / strip-citations …          # 正文校验 / 剥离溯源标注
wxart llm-write --brief … --output …             # wx 引擎混合路由写作
wxart sources add --title … --claim … [--url … --status verified]
wxart sources list --json
wxart score <file> --json                        # 机械风险分（不参与放行判断）
wxart content-eval --draft … --final … --assessment … --output …

# 排版
wxart format <article.md>                        # 默认 wx 引擎（自带容器检查 + 产物门禁）
wxart format <article.md> --engine aws [--theme 杂志 --scheme 石青]
wxart format --engine aws --list-themes
wxart preview <article.md> --theme sspai -o preview.html --no-open
wxart themes / gallery / validate <article.html>
wxart guard containers <article.md> --engine wx|aws   # 只查容器相容性
wxart guard gate <article.html> --profile wx|generic  # 只查产物

# 配图
wxart image generate <prompt.md> --size 2.35:1 -o cover.png
wxart image --engine wx --manifest images.json --max-images 4 --max-cost 2
wxart image-check <cover.png>

# 发布
wxart article-init <run_dir> --title "…" --author "…" --digest "…"
wxart publish check-wechat-env
wxart publish full <article.yaml>                # 默认 aws 引擎
wxart publish <article.md> --cover cover.png --title "…"   # wx 引擎
wxart image-post p1.jpg p2.jpg -t "标题"          # 小绿书/图片帖
```

## 4. 阶段门禁（硬性）

进入下一步前必须核对。**禁止跳步并宣称完成。**

| 阶段 | 入口条件 | 出口产物 | 不满足时 |
|---|---|---|---|
| 环境自检 | — | `wxart doctor` 退出码 0 | 按提示修复，不要绕过 |
| 任务建立 | 自检通过 | `state.yaml` 存在 | 先 `wxart run start` |
| 选题 | 任务存在或用户直接给了选题 | `topic.title` 已写入 | 读 [02-topic.md](02-topic.md) |
| 写作 | `brief.yaml` 与 `claims.yaml` **先落盘** | `draft.md` 非空 | 不许先写正文再补任务书 |
| 审稿 | `draft.md` 非空 | `review-report.json` 且 `publishable=true`，**才**写 `article.md` | 改稿并复审，最多两轮 |
| 封存 | `article.md` 非空且审稿通过 | `status=completed`，历史已写入 | 重跑 `wxart run finish` |
| 配图 | 正文已封存 | `cover.png` 存在；正文与 HTML 无 `placeholder` | 读 [06-visual.md](06-visual.md) |
| 排版 | 有 `article.md`（有带图副本则优先用它） | `article.html` 由**当前**正文重新生成；`wxart format` 自身的门禁退出码为 0（等价于 `wxart validate` 无 ERROR） | 重跑 `wxart format` |
| 发布 | 用户**本轮明确**授权 + 元数据齐全 + 封面存在 + 排版校验通过 | `wxart publish` 成功且回执可用 | 回退为本地预览 |

「草稿创建成功」不是全流程完成的证据。正文仍有 `placeholder` 时，状态必须报
**「草稿已提交，正文配图未完成」**。

## 5. 任务生命周期

```
run start ──→ step topic ──→ step write ──→ step review ──→ run finish ──→ [封存]
                                                                              │
                                              step visual / step publish ◀────┘
                                              （封存后仍可追加，但不得改写原始正文）
```

- `mode=draft`：只出成稿。`mode=complete`：成稿 + 配图 + 本地预览。`mode=publish`：用户已明确要发布。
- 三种 mode 的 `visual.mode` 默认都是 `none`——**排版和发布都不许偷偷触发生图**。
- `finish` 的硬约束：`article.md` 必须非空；如果存在非空 `draft.md`，则 `editorial.decision=pass`
  且 `publishable=true`，否则 CLI 直接报错拒绝封存。
- 封存后 `resume` 会报 `immutable`；要改内容就**新建任务**，不要试图改旧任务。
- 受保护字段（`run_id` / `created` / `status` / `mode` / `permissions`）不能被 `run update` 修改。

### 发布授权是独立通道

```bash
wxart run permission publish allow   # 用户本轮明确要求发布时才执行
wxart run permission publish deny    # 用户撤回时执行
```

`mode=publish` 会在建任务时自动置 `permissions.publish=true`；其余情况一律需要显式授权。
**没有授权就只能生成本地预览**，这一点不接受任何「已经做好了所以顺手发一下」的理由。

## 6. 恢复规则

```bash
wxart run step <阶段> failed --error "简短原因"
```

| 情况 | 处理 |
|---|---|
| 内容步骤失败 | 保留任务；`wxart run resume <run_id>` 后只重做失败或未完成的步骤 |
| 搜索失败 | 删掉无法核实的具体数字与引述，可以继续写分析与经验判断 |
| 生图失败 | 保留 `image-prompts.md`，正文与 HTML 里不能留 `placeholder` |
| 发布失败 | 退化为本地预览，不改文章的完成状态 |
| 正文已封存后配图/发布失败 | 不影响 `status=completed` |
| 要改已封存文章的内容 | 新建任务重写，不要改旧任务的 `article.md` |

## 7. 配置与优先级

**账号配置**（`config.yaml`）：`article_category`、`target_reader`、`default_author` 三项建议填满，
它们直接约束写作与审稿。其余字段见 `wxart init` 生成的模板。

**本篇覆盖**（`article.yaml`）优先级最高：

```
本篇 article.yaml  >  config.yaml 的 custom_*  >  config.yaml 的 default_*
```

全局的预设候选可以是多元素列表；**进入排版与配图前必须在本篇 `article.yaml` 里收敛成单元素列表**
（`default_structure` / `default_closing_block` / `default_title_style` / `default_format_preset` /
`default_format_scheme` / `default_cover_image_style` / `default_sticker_style`）。

**例外**：`default_article_image_style` 保持多元素候选池——正文是**每个图位各选一个形态**，
收敛成一个等于整篇配图用同一种形态。

## 8. 两个引擎的分工

整合保留了上游两套确定性实现，都挂在同一个 CLI 下。默认值按各自的长处选：

| 能力 | 默认引擎 | 换引擎 |
|---|---|---|
| 排版 | **wx**：18 套主题、微信兼容自动修复、粘贴加固、暗黑模式 | `wxart format --engine aws`：模版 × 配色两层 + 版式组件 YAML |
| 配图 | **aws**：比例结构化、出图后确定性检查、prompt 文件规范 | `wxart image --engine wx`：多 provider fallback、数量与费用上限 |
| 发布 | **aws**：多账号、封面裁剪框、自动压缩、`publish_method` 抽象 | `wxart publish --engine wx` |

**选型判据**：

- 想省事、主题现成、要自动规避微信坑（外链脚注、CJK 间距、暗黑模式、粘贴加固）→ **wx 引擎**。
- 想要「模版 × 配色」组合与 `:::` 版式组件（导语 / 编号小标题 / 金句卡 / 数据卡 / 步骤流程 /
  对比两栏 / 结构分层 / 要点清单 / 文末区块）→ **aws 引擎**。
- 配图与封面优先用 aws 引擎出图；缺图片服务时降级为提示词。

### 两个引擎的 `:::` 容器不通用 ⛔

这是整合里最需要小心的一处：**`steps` 在两个引擎里同名但语义完全不同。**

| 容器 | wx 引擎 | aws 引擎 |
|---|---|---|
| `steps` | `:::steps`，每行一步，自动编号、无参数 | `:::steps[标题]`，每行「步骤名 \| 说明」两列 |
| `highlight` | `:::highlight`，首行当标题的琥珀色盒 | **已废弃**，会退化成普通文本 |
| `label` / `section-title` | `:::label`、`:::label pill` | `:::section-title[01]` |

写错引擎**不会报错**，只会渲染成完全不同的结构。所以 `wxart format` 自带两道栅栏：

1. **排版前**：扫描正文里的 `:::` 块。出现只属于另一个引擎的容器、`steps` 写法与目标引擎不符、
   或块缺少结尾的 `:::` → **直接中止**（退出码 4），并列出每一行的行号与期望写法。
   确实知道自己在做什么时加 `--force` 跳过。
2. **排版后**：对产物跑微信兼容门禁，有 ERROR 则退出码 5。wx 引擎按完整规则判
   （含 `div` / `class` / `id`）；aws 引擎按 `generic` 口径判，这三项降级为提示。
   加 `--no-check` 跳过。

两个引擎的**产物形态也不同**：wx 引擎产出完整 HTML 文档（含 `<style>`，供浏览器预览与粘贴），
aws 引擎产出可直接作为草稿 `content` 的单段 `<section>`。**换引擎必须重跑排版**并重新过门禁。

单独查这两件事：

```bash
wxart guard containers <article.md> --engine wx --json    # 退出码 1 = 有不相容的容器
wxart guard gate <article.html> --profile generic --json  # 退出码 1 = 有 ERROR
```

## 9. 日志与排障顺序

1. `wxart doctor` —— 依赖、配置、凭证、发布方式。
2. `wxart env` —— 解析到的路径与来源（配置读的是哪一份，一看就知道）。
3. 本篇目录下的 `<环节>.log`。
4. 再读对应的阶段 references。
