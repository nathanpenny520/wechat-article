---
name: wechat-article
description: |
  微信公众号推文制作唯一入口：一条命令覆盖选题、素材、写作、审稿、排版、配图、草稿箱发布，
  以及学习飞轮、数据复盘、多平台改写、贴图与小绿书、业务资料库。
  触发关键词：公众号、微信推文、微信文章、写公众号、写一篇、草稿箱、微信排版、公众号配图、
  公众号封面、公众号选题、今天写什么、一条龙、完整制作、一稿多发、公众号数据复盘。
  只在微信公众号生态内触发；通用文章/博客/邮件/短视频脚本/网站 SEO/PPT 不触发。
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - WebSearch
  - WebFetch
---

# 微信推文制作

一个 skill 跑完公众号推文的全流程。**prompt 负责判断，Python 负责确定性**：
所有打分、转换、校验、接口调用走 `wxart` 命令，写作、事实、观点与编辑判断由你来做。

```bash
python3 {skill_dir}/scripts/wxart.py <命令>        # 下文简写为 wxart
```

`{skill_dir}` 是本 SKILL.md 所在目录。命令缺失或依赖报错时，先读
[references/01-setup.md](references/01-setup.md) 完成安装与自检。

## 运行原则

1. **一条链默认跑完正文**：选题 → 任务书 → 主张与证据 → 初稿 → 审稿 → 成稿，中间不停下来。
   用户说「交互模式」或「每步确认」时，才在选题、框架、成稿三处暂停确认。
2. **不可逆动作永远要门禁**：推送公众号、生成图片（产生费用）、覆盖已有文件——
   这三件事必须等用户在本轮明确要求后才做，并先报数量与预估费用。
3. **一篇文章一个任务目录**：`{state_home}/runs/<run_id>/`，多篇并行互不覆盖，随时可恢复。
4. **正文封存后不可改写**：`wxart run finish` 之后，原始正文、来源与写作字段只读；
   配图和排版只能产出新文件（`article-illustrated.md`、`article.html`）。
5. **不编造**：搜索失败可以继续写分析和经验判断，但不得把模型记忆包装成已核实的事实；
   只有用户在本轮提供的经历才能写成作者亲历。
6. **工具分数只提示，不替代编辑判断**：`wxart score` 的分不能用来放行或否决一篇稿子。

## 默认动作与显式授权

| 用户说法 | 做完什么就停 |
|---|---|
| 写一篇 / 帮我写篇公众号文章 | 只交付审过的本地成稿，**不生图、不发布、不排版** |
| 完整制作 / 一条龙 | 成稿 + 配图 + 本地排版预览（仍**不发布**） |
| 推到草稿箱 / 发布 | 在上述基础上推送草稿箱；**不会因此自动生图** |
| 只做某一环（只要选题/只排版/只配图/只审稿…） | 只做这一环，缺前置自己补齐 |

## 决策与路由

先判断用户要的是「整条链」还是「某一环」。整条链一律走本文件；单环按下面的表跳转。

| 用户意图 | 读哪份 references | 主要命令 |
|---|---|---|
| 环境/安装/首次配置/换风格 | [01-setup.md](references/01-setup.md) | `wxart doctor` `wxart init` |
| 今天写什么 / 找选题 / 起标题 | [02-topic.md](references/02-topic.md) | `wxart hotspots` `wxart search-articles` `wxart seo` |
| 就这个选题写正文 | [03-write.md](references/03-write.md) | `wxart llm-write` `wxart sources` `wxart draft` |
| 检查一下 / 审稿 / 校对 / 敏感词 | [04-review.md](references/04-review.md) | `wxart score` `wxart content-eval` |
| 排版 / 转 HTML / 换主题 / 看排版效果 / 加纸纹花边背景 | [05-format.md](references/05-format.md) | `wxart format` `wxart gallery` `wxart validate` `wxart shot` `wxart deco` |
| 封面 / 配图 / 内文图 / 图片提示词 | [06-visual.md](references/06-visual.md) | `wxart image` |
| 推到草稿箱 / 发布 / 换图重发 / 只换版式不新建 | [07-publish.md](references/07-publish.md) | `wxart publish` `wxart redraft` `wxart image-post` |
| 学习我的修改 / 导入范文 / 学排版 | [10-learn.md](references/10-learn.md) | `wxart learn-edits` `wxart exemplar` `wxart learn-theme` |
| 看看文章数据 / 复盘 | [11-stats.md](references/11-stats.md) | `wxart stats` |
| 改写成小红书 / 抖音版 | [12-rewrite.md](references/12-rewrite.md) | `wxart similarity` `wxart score` |
| 写自家产品/服务介绍 | [13-products.md](references/13-products.md) | `wxart presets` `wxart product-image` |
| 全流程细节、状态契约、恢复 | [00-workflow.md](references/00-workflow.md) | `wxart run …` |

## 状态模型（先记住这三层）

| 层 | 位置 | 放什么 |
|---|---|---|
| 用户级状态 | `~/.wxarticle/`（`$WXARTICLE_HOME` 可改） | `config.yaml`、`.env`、`style.yaml`、`history.yaml`、`playbook.md`、`runs/`、`exemplars/`、`lessons/`、`themes/`、`personas/` |
| 账号配置 | 同上 `config.yaml`；工作区 `.wxarticle/` 可覆盖 | 账号定位、文风、模型端点、发布方式、预设候选 |
| 本篇任务 | `~/.wxarticle/runs/<run_id>/` | 见下表 |

任务目录里的产物（**两个引擎共用同一个目录**，这是整合的关键）：

| 文件 | 产出阶段 | 说明 |
|---|---|---|
| `state.yaml` | 全流程 | 任务真源，只通过 `wxart run` 读写，**不要手改** |
| `brief.yaml` | 写作 | 文章任务书：读者、问题、核心判断、新意、反方、边界 |
| `claims.yaml` | 写作 | 主张与证据：fact / inference / opinion / user_experience |
| `sources.yaml` | 写作 | 事实来源账本（`wxart sources add`） |
| `draft.md` | 写作 | 初稿，**不是成稿** |
| `review-report.json` | 审稿 | 五维评分、阻断项、`publishable`、改动幅度 |
| `article.md` | 审稿 | 编辑通过后的**成稿**（唯一可发布的正文源头） |
| `article.yaml` | 发布前 | 本篇发文元数据：标题/摘要/封面/裁剪框/发布状态 |
| `article.html` | 排版 | 微信兼容 HTML（发布正文来源） |
| `cover.png`、`imgs/` | 配图 | 封面与内文图 |
| `article-illustrated.md` | 配图 | 带图副本；原始 `article.md` 永不被覆盖 |
| `preview.html`、`image-prompts.md` | 预览/配图 | 本地预览页与图片提示词 |

`wxart env` 打印所有实际路径；`wxart run show` 打印当前任务的全部产物路径。

## 主流程

### Step 0 · 环境自检（必须先做）

```bash
wxart doctor
```

- 退出码 0：继续。缺 `style.yaml` 是**正常首次状态**，不是错误。
- 退出码 1：按提示修复后重跑；不要跳过直接写稿。

### Step 1 · 建立或恢复任务

```bash
wxart run start --topic "{选题，可为空}" --mode draft --visual-mode none
```

- `--mode draft`＝只出成稿；`--mode complete`＝成稿+配图+预览；`--mode publish`＝用户已明确要发布。
- 用户说「继续上次 / 接着之前的进度」：先 `wxart run list`，确认唯一任务后 `wxart run resume <run_id>`，**不要新建**。
- 把自检结果写进任务：

```bash
wxart run update --patch '{"flags":{"skip_publish":false,"skip_image_gen":false,"use_writer_model":false,"needs_onboard":false,"diagnosed_at":"YYYY-MM-DD"}}'
```

### Step 2 · 选题

用户已经给了选题就记录到 `topic` 并跳过；否则读 [02-topic.md](references/02-topic.md)。
完成时：

```bash
wxart run step topic completed
```

### Step 3 · 写作（任务书 → 主张与证据 → 初稿）

读 [03-write.md](references/03-write.md)。**进入写稿前先落盘 `brief.yaml` 与 `claims.yaml`**，
再写 `draft.md`；网页素材同步 `wxart sources add`。初稿不是成稿。

### Step 4 · 审稿（编辑门禁）

读 [04-review.md](references/04-review.md)。按准确、观点、有用、合声、好读五项判断；
**发现可修问题就直接改稿并复审**（最多两轮）。只有编辑决定为 `pass` 且报告
`publishable=true`，才把它写成 `article.md`。

```bash
wxart run step review completed
```

### Step 5 · 封存正文

`article.md` 存在、编辑已通过、报告已保存后立即：

```bash
wxart run finish
```

封存后会写入历史并冻结原始正文。**这一步之前不要排版或发布。**

### Step 6 · 按需追加（各自独立）

用户没要求就不做。三项互不自动触发：

- **配图** → [06-visual.md](references/06-visual.md)：`visual.mode` 设 `cover` / `full` / `prompts`，
  严守 `max_images` 与 `max_cost`，只产出独立图片和带图副本。
- **排版与发布** → [05-format.md](references/05-format.md) / [07-publish.md](references/07-publish.md)：
  优先排版带图副本，没有则用成稿。发布前必须 `wxart run permission publish allow`。
- **「完整制作」快捷方式**＝成稿 → 配图 → 本地预览 的连续调用，**不授予发布权限**。

## 中间产物门禁

进入下一步前先查上一步产物；缺什么补什么，**禁止跳步并宣称完成**。

| 阶段 | 必要产物 | 缺失时 |
|---|---|---|
| 写稿完成 | `brief.yaml`、`claims.yaml`、`draft.md` 均非空 | 回到写作补齐 |
| 审稿完成 | `review-report.json` 且 `publishable=true`；`article.md` 非空 | 改稿并复审，不许先写 `article.md` |
| 封存完成 | `state.yaml` 的 `status=completed`；历史已写入 | 重跑 `wxart run finish` |
| 排版完成 | `article.html` 由**当前** `article.md` 重新生成；`wxart format` 的产物门禁退出码为 0 | 重跑 `wxart format` |
| 配图完成 | 存在 `cover.png`（或 jpg/webp）；正文与 HTML 里没有 `placeholder` | 重跑配图并替换引用 |
| 发布就绪 | `article.yaml` 含 `title/author/digest/content_source`；封面存在；排版门禁已过（`article.html` 无 ERROR） | 补元数据或先修排版 |

**只凭「草稿创建成功」不能宣布全流程完成。** 正文仍有 `placeholder` 时，状态必须报
「草稿已提交，正文配图未完成」。

## 收尾汇报

结束时告诉用户：标题、成稿路径、带图副本路径、来源数量、图片与预览结果、
是否进入草稿箱、以及中途发生的任何降级。

## 失败与恢复

```bash
wxart run step <topic|write|review|visual|publish> failed --error "简短原因"
```

- 内容步骤失败：保留任务，下次 `wxart run resume` 只重做失败或未完成的步骤。
- 正文已封存后：配图或发布失败不改变文章的完成状态。
- 发布失败退化为本地预览；生图失败保留提示词；搜索失败删掉无法核实的数字与引述。
- 命令报错先看 `wxart doctor` 和 `wxart env`，再读对应的 references 文档。

## 引用的文档（按需加载，不要一次全读）

| 文档 | 什么时候读 |
|---|---|
| [00-workflow.md](references/00-workflow.md) | 需要完整流程、状态字段、恢复与授权规则 |
| [01-setup.md](references/01-setup.md) | 安装、自检、首次配置、换风格 |
| [02-topic.md](references/02-topic.md) | 选题、标题、摘要 |
| [03-write.md](references/03-write.md) | 任务书、主张证据、框架、人格、初稿 |
| [04-review.md](references/04-review.md) | 审稿、校对、敏感词、AI 味 |
| [05-format.md](references/05-format.md) | 排版、主题×配色、版式组件 |
| [06-visual.md](references/06-visual.md) | 封面与配图方法、形态池、媒介轮换 |
| [07-publish.md](references/07-publish.md) | 草稿箱、发布、贴图、小绿书 |
| [10-learn.md](references/10-learn.md) | 编辑飞轮、范文库、学排版 |
| [11-stats.md](references/11-stats.md) | 数据复盘与选题反哺 |
| [12-rewrite.md](references/12-rewrite.md) | 小红书 / 抖音改写 |
| [13-products.md](references/13-products.md) | 业务资料库与 `.aws` 预设包 |
| [20-wechat-html-constraints.md](references/20-wechat-html-constraints.md) | 需要知道微信 HTML 到底禁什么 |
| [21-quality-rubric.md](references/21-quality-rubric.md) | 需要内容质量的完整判定标准 |
