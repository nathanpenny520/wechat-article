# 学习飞轮、范文库、排版学习与风格设置

四条子路径，触发语互不重叠。`wxart` = `python3 {skill_dir}/scripts/wxart.py`；
`{home}` = `~/.wxarticle`（`$WXARTICLE_HOME` 可改），工作区 `.aws-article` 是指向它的软链，
两条路径是同一份状态，下文统一写 `{home}/`。

| 用户说 | 子路径 | 命令 | 落盘 |
|---|---|---|---|
| 学习我的修改 / 我改了，学习一下 / 我从草稿箱改了 | 编辑飞轮 | `wxart learn-edits` | `{home}/lessons/<日期>-diff.yaml`、`{home}/playbook.md` |
| 导入范文 / 学习这篇文章 / 查看范文库 | 范文库 | `wxart exemplar`、`wxart fetch-article` | `{home}/exemplars/` |
| 学习排版 / 学排版 + URL | 排版学习 | `wxart learn-theme` | `{home}/themes/<name>.yaml` |
| 缺 `{home}/style.yaml` / 重新设置风格 / 换写作人格 / 改主题偏好 | 风格设置 | 交互式；`wxart themes` / `wxart gallery` / `wxart build-playbook` | `{home}/style.yaml` |

## 一、编辑飞轮（`wxart learn-edits`）

目标是**减少重复修改**，不是把一次改稿变成所有文章的永久模板。

### 1. 拿原稿与终稿

原稿优先用用户点名的文件，否则用历史里该任务的 `draft_file`（见 [11-stats.md](11-stats.md)）；
终稿由用户提供。**多个候选必须问用户确认，不许按文件修改时间猜。**

```bash
wxart learn-edits --draft {draft_path} --final {final_path}
```

命令算结构化 diff、写 lesson YAML（`patterns: []` 留空），并打印标题修改、H2 结构对比、
增删行数与字数变化。

### 2. lesson 文件

路径 `{home}/lessons/<YYYY-MM-DD>-diff.yaml`，同日已存在则顺延 `-diff-2.yaml`、`-diff-3.yaml`…。
顶层字段：`date`、`timestamp`（ISO，就是聚合时 `first_seen`/`last_seen` 的来源）、
`draft_file`、`final_file`（`--from-wechat` 时写成 `wechat:<原稿路径>`）、
`diff_summary{title_changed, draft_title, final_title, structure_changed, lines_added, lines_deleted, char_diff}`、
`patterns`（初写为空数组，由**你**读原稿和终稿后逐条填）。

### 3. pattern 字段

| 字段 | 取值 |
|---|---|
| `type` | `word_sub` / `para_delete` / `para_add` / `structure` / `title` / `tone` / `expression` |
| `key` | 短且唯一的标识，如 `avoid_jiangzhen`、`shorter_paragraphs` |
| `description` | 这次改了什么，如「这次把教程中的长段拆短」 |
| `rule` | **可执行的祈使句**。好：「段落不超过 80 字，长段必须在 3 句内换行」；坏：「用户偏好简短段落」 |
| `scope` | `global` / `content_type` / `framework` / `persona`；非白名单值会被归一到 `global` |
| `scope_value` | 与 scope 对应的具体值（如 `tutorial`）；`global` 留空 |
| `confirmed` | 只有用户**明确说这是长期偏好**才写 `true` |

优先选**最窄且真实**的范围；结构、标题、语气的单次修改通常与题型有关，不要默认全局。
相同 `key + scope + scope_value` 才累计次数。

### 4. confidence 与 hard（`--summarize` 按当前日期重算）

```bash
wxart learn-edits --summarize --json   # Agent 用
wxart learn-edits --summarize          # 人看：置信度条 + scope + seen Nx + hard
```

- 聚合键**只有** `key + scope + scope_value`：`occurrences` 累加、`confirmed` 取或、
  `rule`/`description` 取最近一次、`first_seen`/`last_seen` 取最小/最大值。
- 基础分：1 次 = **3**；2 次 = **5**；3 次及以上 = `min(8, 1 + 2n)`。
- 近期加成：`occurrences >= 2` 且距 `last_seen` **≤ 7 天**，**+0.5**。
- 衰减：距 `last_seen` **每满 30 天 −1**（`days_since // 30`）。
- 结果**钳到 1–10**，保留 1 位小数，按 confidence 降序输出；衰减到**低于 2** 的规则不再使用。
- **硬规则：`hard = confirmed or (occurrences >= 2 and confidence >= 5)`。单次修改永远只是软参考。**

### 5. 使用纪律

- `--summarize --json` 之后**必须重写 `{home}/playbook.md`**，否则这次学习不影响下一篇。
- 写作前**必须重新 summarize**，不许沿用 playbook 里的缓存分数；已衰减或消失的规则不能永久留在里面；
  只应用 `global` 或与当前 `content_type` / `framework` / `persona` 匹配的规则，`hard=true` 才是硬约束。
- `playbook.md` 是**给人看的文件，不是自动生效的配置**——不重跑 summarize 等于没学。

### 6. `--from-wechat`

```bash
wxart learn-edits --from-wechat
```

三个硬前提，缺一条就报错，**不许按文件名猜草稿**：① `{home}/config.yaml` 有 `wechat.appid` 与
`wechat.secret`；② `{home}/history.yaml` 里有带 `media_id` 的记录；③ 该记录 `output_file` 指向的
本地文件**仍存在**（相对路径按 `{home}/` 解析）。内容一致就打印「没有修改」且**不写 lesson**；
有差异才落 lesson，由你继续填 `patterns`。比对在纯文本上做（剥掉 markdown 标记），
`diff_summary` 描述的是纯文本差异。

### 7. 学习后自动进范文库

`--draft/--final` 这条路径在学习完成后会把终稿抽成范文：`ownership=user`、
`authenticity=user_edited`；**`quality_score >= 50` 才真正入库**，低于 50 只提示「机械语言风险较高，
先复审」。`--from-wechat` 不触发自动入库。

## 二、范文库（`wxart exemplar`）

```bash
wxart fetch-article <URL> -o out.md          # 采集（--file x.html 走本地 HTML，--json 结构化）
wxart exemplar out.md -s "账号名"              # 导入，第三方
wxart exemplar mine.md --user-authored        # 明确是本人创作
wxart exemplar a.md b.md c.md                 # 批量
wxart exemplar FILE -c tech-opinion -s "来源"  # 指定类别
wxart exemplar --list                         # 按类别列出，带质量条
```

- 类别 5 个：`tech-opinion` / `story-emotional` / `list-practical` / `hot-take` / `general`。不传 `-c`
  时自动判定并取最高分：技术观点 = 真实来源标记数 ×2；故事情绪 = 故事标记词 ×1.5；
  清单实用 = H2 数 ×3（H2 ≥ 5 才计）；热点锐评 = 负面标记 ×2 + 来源标记（正文 < 2000 字才计）；general = 5。
- 落盘 `{home}/exemplars/<类别>-NNN.md`（NNN 三位，取下一个空号），索引 `{home}/exemplars/index.yaml`，
  条目字段 `file` / `source` / `category` / `quality_score` / `ownership` / `authenticity` / `extracted_at`，
  按类别、再按质量降序。
- frontmatter 字段全列：`source`、`category`、`quality_score`、`ownership`、`authenticity`、
  `allowed_uses`、`personal_materials_reusable`、`sentence_stddev`、`vocab_temperature`
  （`cold`/`warm`/`hot`/`wild` 四档占比）、`negative_ratio`、`paragraph_cv`、`short_paragraphs`、
  `extracted_at`。提取对象另有 `title`、`segments`、`char_count`：`opening` 取开头段落至 250 字、
  `emotional_peak` 取负面情绪密度最高的段、`transition` 取自纠/转折词最多的段、`closing` 从后往前至
  250 字；有内容的 segment 才写进 `## 开头钩子` / `## 情绪高峰` / `## 转折/自纠` / `## 收尾`。
- 所有权：`--user-authored` → `user` + `user_authored`；否则 `third_party` + `published`。
  从 URL 或普通文件导入**默认第三方**；缺元数据的旧范文按第三方、未验证处理。

**范文铁律**：`allowed_uses` 只有 `["style","structure"]`，`personal_materials_reusable` 永远 `false`。
范文**只校准结构与节奏**，第三方内容不提供观点和个人经历；即便是用户自己的旧文，其中的个人经历
也必须由用户在本次任务重新提供或确认。写作时最多读 2 篇相关范文，见 [03-write.md](03-write.md)。

## 三、排版学习（`wxart learn-theme`）

```bash
wxart learn-theme <公众号文章URL> --name <名字> [--output-dir DIR]
```

- `--name` 只允许字母、数字、连字符、下划线（`^[a-zA-Z0-9_-]+$`）；同名文件会被**覆盖**（先告警）。
- 落 `{home}/themes/<name>.yaml`（`--output-dir` 可改）。结构：`name`、`description`
  （`从「<文章标题>」学习的排版主题`）、`colors`（`primary` / `secondary` / `text` / `text_light` /
  `background` / `code_bg` / `code_color` / `quote_border` / `quote_bg` / `border_radius` + 派生 `darkmode`）、
  `base_css`。
- 提取要点：只读正文 `#js_content` 的**内联样式**，按标签分组取众数。`primary` 取自
  `strong/section/h1-h3/span` 中非灰、非正文色、字号 ≥20px 权重 ×5 的最高分强调色；`secondary` 取
  第二名，只有一个时按 `primary` 亮度 +0.10（封顶 0.90）；底色取前 10 个 `section` 里亮度 >0.85 的；
  `text_light` 取灰且亮度落在 0.15–0.85 的最亮值；引用边框优先 `blockquote` 的 `border-left`。
  暗色派生：底 `#1e1e1e`、正文亮度 0.80、次要字 0.60、主色 +0.15（封顶 0.85）、代码底 `#2d2d2d`、
  代码字 `#d4d4d4`、引用底 `#252525`。
- **加载优先级**：显式指定的主题目录 > `{home}/themes/` > 内置 18 套
  （`{skill_dir}/scripts/wxengine/toolkit/themes/`）；同名用户主题胜出。
- 学完告诉用户怎么启用：写进 `{home}/style.yaml` 的 `theme:`，或排版时传 `--theme <名字>`，
  见 [05-format.md](05-format.md)。

## 四、风格设置（onboard，交互式）

**触发**：主管道发现 `{home}/style.yaml` 不存在；或用户说「重新设置风格 / 修改风格配置 /
设置公众号风格 / 换写作人格 / 改排版主题偏好」。这是**配置动作**，不要被「改文风」「润色」触发。
本模块交互式，不受全自动约束：一轮问 1–2 个问题，像聊天一样。

**Phase 1 · 收集**。必问三项：① 公众号叫什么、主要做什么方向 → `name` + `industry`；
② 主要写哪几个方向 → `topics`；③ 希望是什么风格 → `tone`。
选问（不答用默认）：`target_audience`（从 industry 推断）、`voice`（默认「第一人称，像一个懂行的朋友」）、
`blacklist`（空）、`reference_accounts`（空）、`author`（取 `name`）、`writing_persona`（从 tone 推断）、
`theme`（默认 `professional-clean`，可先 `wxart gallery` 预览 18 套）、`cover_style`（从 industry 推断）、
`cover_template`（默认不设）。
tone → persona：轻松/有趣/朋友/聊天 → `midnight-friend`；温暖/共鸣/故事/治愈 → `warm-editor`；
专业/分析/深度/行业 → `industry-observer`；犀利/锐评/观点/新闻 → `sharp-journalist`；
严谨/数据/研究/财经 → `cold-analyst`。
**快捷路径**：用户甩一段描述（「我做科技自媒体，风格像虎嗅」）→ 抽字段、只补问缺的；说
「不设置 / 用默认的 / 直接写」→ 复制内置 `style.example.yaml` 为 `{home}/style.yaml`，跳过问答。

**Phase 2 · 生成配置**。写 `{home}/style.yaml`，并确保 `{home}/history.yaml` 初始化为
`version: 1` + `articles: []`、`{home}/corpus/` 与 `{home}/lessons/` 存在。生成后**把全文给用户看一遍**
问「这个配置 OK 吗」，确认再继续。字段全列：`name`、`industry`、`topics`（列表）、`tone`、`voice`、
`word_count`（如 `1500-2500`）、`content_style`（干货/故事/情绪/热点/测评，影响选题偏好与框架推荐）、
`writing_persona`、`blacklist{words: [], topics: []}`、`reference_accounts`（列表）、`theme`、
`cover_style`、`cover_template`（设了跳过 AI 生成封面）、`author`、`target_audience`。

**7 个人格速查**（详见 [03-write.md](03-write.md)）：`midnight-friend` 个人号/自媒体，像给熟悉的朋友
解释一件事；`warm-editor` 生活/文化/情感，故事驱动、温暖克制；`industry-observer` 行业媒体/分析，
专业分析、偶尔锐利；`sharp-journalist` 新闻/评论，短句利落、观点鲜明；`cold-analyst` 财经/投研，
数据优先、边界清楚；`humor-storyteller` 娱乐/热点评论，用幽默承载观点；`tech-coder` 技术教程/开发者，
示例先行、务实精炼。

**人格只控制表达偏好，不能覆盖事实、个人材料和文章任务书。** 人格要求私人或故事开场而
`personal_materials.available=false` 时改用观察、问题或判断开场——这条边界不因风格设置放宽。

**Phase 3 · Playbook（可选，不阻断）**。问用户有没有 20 篇以上旧文；有就让他把 `.md`/`.txt`
放进 `{home}/corpus/`，然后跑：

```bash
wxart build-playbook [--batch-size N] [--stats-only]
```

脚本只做确定性工作：输出语料统计（篇数、平均字数、平均标题长度与区间、平均段落数、平均 H2 数）
和**分批分析提示**（默认每批 10 篇，单篇超 3000 字符截断）；**脚本自身不调 LLM**。由你逐批阅读，
按提示要求的八节——标题模式 / 开头模式 / 段落节奏 / 用词指纹 / H2 命名习惯 / 结尾模式 / 情绪基调 /
配图风格——写出 `{home}/playbook.md`，每个结论都要有百分比、平均值或区间支撑。没有语料就跳过，
告诉用户「先用通用风格写，随时说『学习我的修改』让我逐渐适应」。

**Phase 4 · 试跑**。问「要不要现在试写一篇」：是则回主管道；否则告诉他下次直接说「写一篇公众号文章」。
**重设**：以现有 `style.yaml` 为基线，只改用户点到的字段，改完展示全文让他确认。

## 五、边界

- 单次修改**永远不升级为全局硬规则**；要成硬约束，必须重复出现或用户明确确认。
- `playbook.md` 是人可读文件，**不是自动生效的配置**；写作前必须重跑 `--summarize`。
- 范文只借结构与节奏，不借观点、句子和个人经历。
- `--from-wechat` 找不到精确的原稿路径就报错，**不要拿同名或最新的文件顶替**。
