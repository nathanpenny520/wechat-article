# 任务书、证据与初稿

写作不是「从选题直接生成一篇文章」。动笔前先把**读者、判断、证据和个人材料边界**落成两份 YAML，再让模型或自己按它们写。这一环的产物是初稿，不是成稿。

**顺序是硬性的：`brief.yaml` → `claims.yaml` → `draft.md`。** 先写正文再补任务书，等于事后为已成文的东西编理由——**禁止**。

## 读取

- `{home}/config.yaml`（工作区存在 `.wxarticle/` 覆盖层时以它为准，`wxart env` 看生效来源）：至少确认 **`article_category`、`target_reader`、`default_author` 三项 trim 后非空**。缺失就逐项问用户并写回该文件，**先于写稿**，**禁止**从草稿静默抄录。
- `{home}/writing-spec.md`：用户写作规范。不存在就跳过这一维度，不报错。
- `{home}/style.yaml`：账号语感、`content_style`、`topics`。
- 学习规则：**不要直接相信 `{home}/playbook.md` 的缓存分数**，先跑 `wxart learn-edits --summarize --json` 取仍在有效期内的规则。只用与当前 content_type / framework / persona 匹配的规则；**`hard=true` 才是硬约束**，其余仅作参考；全局结构或语气规则若只是单次修改，不得强制执行。
- 范文库：`wxart exemplar --list`，**最多读 2 篇**相关范文（`wxart exemplar FILE`）。标 `ownership=user` 且确为用户本人创作 / 修改的范文可帮助校准声音与结构；第三方或缺少元数据的范文一律按第三方处理，只能参考节奏与结构。**任何范文都不能提供可复用的个人经历、人物、对话、具体细节、观点或句子。**
- 当前任务：`wxart run show`，并 `wxart run step write in_progress`。

## 产出与边界

- `{run_dir}/brief.yaml`、`claims.yaml`（**先落盘、非空**）、`sources.yaml`（经 `wxart sources add` 累积）、`draft.md`（初稿，**不是成稿**）、`topic-card.md`（仅走模型出稿时需要）。
- `state.yaml` 的 `framework`、`enhance_strategy`、`persona`、`word_count`、`provenance`。
- **越界禁止**：本阶段不写 `article.md`、不剥离 `（资料路径：…）`、不排版、不配图。

## 命令

```bash
wxart learn-edits --summarize --json          # 取仍在有效期内的硬规则
wxart exemplar --list                         # 范文库（最多读 2 篇）
wxart sources add --title "…" --claim "…" --url "https://…" --status verified
wxart sources list --json
wxart draft prompt draft {run_dir}/topic-card.md          # 只出提示词 JSON，不调 LLM
wxart draft draft  {run_dir}/topic-card.md -o {run_dir}/draft.md
wxart llm-write --brief {run_dir}/brief.md --output {run_dir}/draft.md
wxart draft check  {run_dir}/draft.md
```

在**工作区根**执行 `wxart draft …`：aws 引擎按 CWD 找 `.aws-article/config.yaml`，而 `wxart init` 已把 `.aws-article` 软链到 `{home}`，两边读到同一份配置。`wxart draft` 的输入文件路径用**真实相对或绝对路径**，不要写占位符。

## 第一步：写 `brief.yaml`

字段可补充，**不能省略**核心项。

```yaml
version: 1
audience: {who: "具体读者", context: "读者在什么情境下阅读", question: "读者真正要解决的问题"}
goal: {takeaway: "读完能复述的一个结论", action: "读完可以采取的行动；纯观点文写判断方法"}
thesis: {statement: "全文核心判断", novelty: "相较常见说法新增了什么", boundary: "结论在什么条件下成立", counterpoint: "最强反方或替代解释"}
personal_materials: {available: false, items: []}   # items 只记录用户在本次任务明确提供的经历、观察或原话
framework: "观点"            # 7 框架之一
sections:
  - {purpose: "本节推进什么", claim_ids: [C1]}
constraints: {desired_length: "1200-2500 字", must_include: [], must_avoid: []}
```

`novelty` 不是强行唱反调——找不到可靠的新角度时，**缩小问题、补充适用条件或提供更好用的判断框架**。`action` 必须与题目相称，不为凑「干货」制造步骤。每一节至少要服务一个 `claim_ids`；**无法对应主张的段落默认删除**。正文通常 1200–2500 字，按 `desired_length` 与 `target_word_count` 调整。

## 第二步：写 `claims.yaml`

```yaml
version: 1
claims:
  - {id: C1, text: "正文准备表达的主张", type: fact, source_ids: [], status: supported, boundary: "适用范围或不确定性"}
```

- `type`：`fact` / `inference` / `opinion` / `user_experience`。`status`：`supported`（有直接来源）/ `bounded`（有来源但只在一定范围成立）/ `unsupported`（不可进正文）。
- `fact` 必须有能直接支持它的来源；否则删除或标 `unsupported`，**不得进入正文**。`inference` 要列出依据并在正文里明确这是推断。`opinion` 不伪装成共识，`source_ids` 可为空。`user_experience` 只能来自本次任务明确提供的材料，并在来源账本标 `user_provided`。
- 范文、模型记忆、人格示例都不是用户经历，也都不是 `fact` 的来源。
- 围绕文章真正需要证明的 **3–6 个主张**去搜索；每条要进文章的数据、引述、案例或时效性事实，都要在**原页面**核对并**立即**记录。

## 素材来源：`wxart sources add`

```bash
wxart sources add --title "报告标题" --claim "这份报告支持的具体主张" \
  --url "https://example.com/report" --publisher "发布方" --published-at "2026-01-01" --status verified
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `--title` / `--claim` | 是 | 来源标题；该页面支持的具体主张（不是泛泛的主题词） |
| `--url` | 视状态 | `verified` / `unverified` **必须有 http(s) URL**；`user_provided` 可省（自动填 `user-provided://material`） |
| `--publisher` / `--published-at` | 否 | 发布方 / 发布日期 |
| `--status` | 否 | `verified` / `unverified` / `user_provided`，默认 `verified` |

`verified`＝你**在原页面核对过**，页面直接支持该主张（优先原始报告、官方文档、当事方信息）；`unverified`＝有 URL 但未逐项核对，或页面只是间接相关；`user_provided`＝用户在本轮提供的材料。**不得把搜索摘要、范文或模型记忆标为 `verified`**——尤其**不得把模型记忆标为 `verified`**。来源 id 由脚本按 `url + claim` 生成，同一 URL 配不同 claim 是两条来源；任务 `completed` 后不可再改。

`wxart sources list --json` 供审稿阶段逐项回对（见 [04-review.md](04-review.md)）。

**搜索不可用时**：只写不依赖最新数据的分析和**有边界的**判断；**删掉无法核实的数字、引述和「研究显示」**；用 `wxart run step write failed --error "搜索不可用"` 记录降级，然后继续。

## 7 框架速查

| 框架 | 适用 | 基本推进 |
|---|---|---|
| 痛点 | 读者有明确困难 | 场景 → 根因 → 解法 → 边界 |
| 故事 | 人物与变化是核心 | 冲突 → 选择 → 结果 → 含义 |
| 清单 | 读者要快速行动 | 目标 → 条目 → 用法 → 避坑 |
| 对比 | 需要做选择 | 标准 → A/B 证据 → 适用人群 → 建议 |
| 热点解读 | 事件正在变化 | 发生了什么 → 为什么 → 影响 → 观察点 |
| 观点 | 核心价值是判断 | 主张 → 证据 → 反方 → 边界 |
| 复盘 | 过程经验可迁移 | 目标 → 做法 → 偏差 → 学到什么 |

按**读者问题**选框架，不按热度选。框架是组织工具，不是必须填满的模板；材料不足时**缩小主张**，不用空话补齐结构。写进 `brief.framework` 与 `state.framework`。

## 安全内容增强（选一项主策略）

| 框架 | 主策略 | 具体做法 | 输出到 |
|---|---|---|---|
| 观点 / 热点解读 | 可支持的新角度 | 先列共识、分歧、被忽略的条件，再选一个有证据的贡献：更准确的因果解释 / 更清楚的适用边界 / 对具体读者的影响 / 更好用的判断框架 | `thesis.novelty` + 对应主张 |
| 痛点 / 清单 | 行动可用性 | 逐节检查读者能否开始行动，补齐步骤、条件、成本、风险和失败信号；工具、参数、价格、版本都属**事实**，必须核实并注明时效 | `goal.action`、章节目的、主张边界 |
| 故事 / 复盘 | 有来源的真实细节 | 只用用户明确提供或可靠来源明确记载的时间、地点、对话、细节；直接引语必须能逐字核对，转述标明来源 | `personal_materials`、来源账本、主张清单 |
| 对比 | 决策条件 | 先定义共同标准，再比较证据、限制、总成本和适用人群；官方信息用于功能与价格，用户评价只代表被引用者的体验 | 一个清楚的「什么情况下选什么」 |

**通过检查（四条全过）**：新角度能由已有证据和逻辑支持，不是为不同而不同；具体信息都有来源或明确边界；没有把第三方故事、范文片段或模型记忆改写成作者亲历；每个增强点都服务读者问题和核心主张，删掉后毫无影响的内容不加入。
材料不足 → 缩小主张或换框架。**禁止**「合理重建」、拼接人物、添加感官细节或替用户补经历。

## 人格：选法与字段差异

**加载优先级**：`{home}/personas/<name>.yaml`（用户自定义）→ `{skill_dir}/assets/personas/<name>.yaml`（内置 7 个）→ 回退 `midnight-friend`。人格只控制**表达偏好**，**不能覆盖事实、个人材料和文章任务书**。选定后写进 `state.persona`。

| `name` | 适合 | `voice_density` | `uncertainty_rate` | `paragraph_max_length` | `opening_style` | `closing_tendency` | `avoid`（要点） |
|---|---|---|---|---|---|---|---|
| `sharp-journalist` | 新闻评论、深度报道 | 0.4 | 0.05 | 80 | `cold_open` | `sharp_statement` | 抒情、冗长铺垫、模棱两可、网络流行语 |
| `industry-observer` | 科技媒体、行业分析 | 0.6 | 0.08 | 100 | `news_hook` | `open_question` | 过度口语化、感性表达、无来源断言、报告式堆砌 |
| `cold-analyst` | 财经、投研、研究机构 | 0.3 | 0.10 | 120 | `thesis` | `implications` | 口语与网络用语、强烈情感判断、无来源数据、过度简化的类比 |
| `tech-coder` | 技术教程、架构解析 | 0.5 | 0.03 | 70 | `problem_statement` | `checklist` | 抒情铺垫、无代码的纯文字技术描述、模糊技术表述、无版本标注的 API |
| `warm-editor` | 生活方式、文化、情感 | 0.7 | 0.10 | 90 | `scene` | `image` | 冷硬术语、攻击或讽刺、密集数据堆砌、急促节奏 |
| `midnight-friend` | 个人号、自媒体、科技博主 | 0.6 | 0.15 | 60 | `personal_moment_if_supplied_else_observation_or_thesis` | `trailing_off` | 总结性收尾、全文同一温度、报告式数据罗列、每段首句承接上段 |
| `humor-storyteller` | 泛科技娱乐、行业辣评 | 0.9 | 0.15 | 60 | `bait` | `callback` | 正经总结收尾、连续三段以上无包袱、冒犯特定群体、尬笑网络用语堆砌 |

每个人格文件还含 `personal_material_policy: "only_current_user_supplied"`、`fallback_opening_style`、`data_reaction_style`、`emotional_arc`、`single_sentence_paragraph_rate`、`uncertainty_expressions`、`rhythm_examples`。**`personal_material_policy` 必须保持 `only_current_user_supplied`，不得改写。** `uncertainty_expressions` 是**备选池**，从中选取，不要每次用同一句；它表达不确定，**不能替代事实核查**。`rhythm_examples` 是节奏手法，**不设数量配额**。

**个人材料边界（`personal_materials.available=false`）**：**可以写**作者判断——「我认为」「我的判断是」「在我看来」。**禁止写**：作者经历过的事件、时间、地点、动作、感官细节；朋友、同事、家人、采访对象、现场对话；任何以「我有个朋友」「上周我」开头的亲历叙事。人格要求私人开场或故事开场时（`opening_style: scene` / `bait` / `personal_moment_if_supplied_else_observation_or_thesis`），**自动改用 `fallback_opening_style`**：观察、问题或核心判断开场。**不得补造材料**。

## 初稿硬性写法规则

链路是「markdown 语法 → 按语法输出 → 渲染器排版」。写错的标记不报错，读者会在正文里直接看见 `__加粗__`、`###### 六级`、`[^1]`。

| 要表达的 | 写法 | 说明 |
|---|---|---|
| 小标题 | `## 二级` `### 三级` | 井号后必须有空格；**不写 `# 一级`**（文章标题由后台单独填） |
| 加粗 / 斜体 | `**加粗**` / `*斜体*` | **不用** `__加粗__`、`_斜体_`；中文里慎用斜体 |
| 链接 | `[文字](https://…)` | 必须有可点的锚文本；**不留裸 URL** |
| 配图 | `![类型名：画面内容](placeholder "图注")` | 图注写在引号里；不写引号就没有图注 |
| 列表 | `- 一项` / `1. 一项` | 减号后必须有空格；有序列表只在**真有先后**时用，并列的几项用 `-` |
| 待办 | `- [ ]` `- [x]` | **少用**，只有真正的检查项才用 |
| 引用 | `> 引文` | 每行都要有 `>` |
| 表格 | `\| a \| b \|` + `\|---\|---\|` | 分隔行不能省 |
| 代码 | 行内 `` `x` ``；成块用三反引号围栏 | **不用**四空格缩进 |
| 分隔 | `---` 独占一行 | 上下各留一个空行，排版会换成本模版的分隔装饰 |

**禁止**：HTML 标签（`<br>` `<div>`）；四空格缩进代码块；Setext 式标题（`====` / `----`）；裸 URL 当正文。

**关于 `:::`**：默认不用——它把作者绑在某一个引擎的私有语法上。但当本篇**明确要走模版排版**（写进 `brief.constraints.must_include` 或用户点名）时，允许手写**目标引擎自己那一套**容器，并且必须先跑 `wxart guard containers <draft.md> --engine wx|aws` 确认没有跨引擎写法：wx 的容器与 aws 的组件名**不通用**，`steps` 更是同名不同语法（见 [05-format.md](05-format.md)）。拿不准就退回标准 markdown，靠引擎的自动触发（导语 / 金句卡 / 标签列表 / 任务列表 / 分隔线）出效果。

### 产出配额（不是可选项）

- **摘要**：第一个 `##` 之前写一段 `> ` 引用块，80–128 字。第一个 `##` 之前没有 `>`，导语版式整篇不会出现。**这段导语不要和 `article.yaml` 的摘要字段写成同一句话**——摘要给还没点进来的人看，导语给已经点进来的人看。
- **加粗 = 划重点**。验收标准：**把全文的加粗按顺序抽出来连读，应该是一篇能独立看懂的缩写版。** 读起来像词云（「透明度 / 瓶颈 / 采用」）或像把段落重念一遍，都是挑错了。据此倒推：**每 100 字左右就该有一个落点**（手机上约 4–5 行），**连续 200 字不许一个都没有**；每个 `##` 小节至少一处，结尾段也要有；一段里最多两处。每处都要**能独立看懂**：数字连着它的意思（`**省 88% Token**`），判断连着它的对象（`**打断不等于撤销**`），术语连着它的定性（`**按问题找证据**`）。关键数字尽量覆盖到。**不要**加粗整句的概括，**不要**每段都加在首句同一位置。密度按**字数**算，不按段数——段是会伸缩的单位。
- **三项以上的并列**：写成 `- **标签**：说明` 列表，不要压进一个长段落。即使段落偏好要求「完整自然段」，那管的是叙述段，枚举仍用列表。
- **金句恰好一处**：最值得截图转发的那一句写成 `> 金句。 —— 出处`，排版会排成金句卡。写两处以上卡片就退化成装饰条；不写出处就是普通引用。**出处不超过 25 个字符**（写人名或机构，如「张三」「微软研究院」；别塞论文全名或书名副标题，超了排版就不成卡）。
- **段距**：段与段之间空**一行**；空两行或用两个空格换行都不需要，段距由版式控制。
- **电头**：正文必须**直接以 `#` 标题开头**，标题前后**严禁**「作者署名 / 发自某地 / 记者 / 媒体名报道」之类电头（如「马斯 发自 北京」「XX 发自 凹非寺」「量子位报道」「本报记者」）。作者与原创标注属发布时的元数据，不写进正文。
- **交互型收尾**：**直接写成一句自然的话**（一句抛给读者的开放式提问即可）。**严禁**加「互动话题」「互动时间」「话题互动」「互动引导」这类标题或加粗标签。结构指引里的【开头】【结尾】【金句节奏】等元标签同样**严禁**当正文标题输出。

### 配图标记

格式 `![类型名：画面内容](placeholder)`，方括号内用**全角冒号 `：`**分成两段。**每个占位独占一行，前后各留一空行**；**封面占位放在标题 `#` 行之前**。

| 类型名（冒号前只能填这四个） | 下游拿它做什么 | 示例 |
|---|---|---|
| `封面` | 排版跳过它不进正文；发布时拿它当文章封面 | `![封面：透明水杯与小闹钟，宽幅留白适合标题](placeholder)` |
| `实证` | **必须是真实素材**（官方原帖截图、界面实拍），不许生成；说明文件放 `imgs/sources/` | `![实证：官方发布原帖](placeholder)` |
| `信息图` | 信息位——流程 / 结构 / 数据 / 对比都算；冒号后**必须含具体数据点或维度** | `![信息图：5个工具对比，列=名称/价格/特点](placeholder)` |
| `氛围` | 节奏位——只为换口气，不承载信息，不出图注 | `![氛围：清晨厨房窗台一杯温水](placeholder)` |

不得出现字面「类型」二字；**冒号后**写画面内容的简短概括即可（「淘米」「小孩钓鱼」），**禁止**「配图」「示意图」等敷衍词，**禁止**冒号后等于类型名本身。**图注**写在路径后的引号里，给读者看；冒号后的画面内容是给生图模型的指令。**绝大多数图不需要图注**——写不出有信息量的图注（数据出处、一句判断、反常识细节）就不写第三个参数。

**密度是硬配额，写完自己数一遍**（`image_density` 未配置时默认**每节一图**）：`每节一图`＝每个 `##` 小节各配一张，不多不少；`按需配图`＝只在文字讲不清的地方配（流程、对比、数据），其余不配；`少图`＝全篇只配 1–2 张最关键的；`多图`＝每 2–3 个自然段配一张。

`image_source=user`（用户供图）时**不输出 `placeholder`**，改用真实路径 `![类型名：画面内容](imgs/文件名)`；封面只能 1 张且放标题前；不得虚构不存在的文件名。

### 事实处标溯源

走参考资料库（业务资料 / 用户文档）写稿时，凡**实际依据**了某条资料的句子或段落，必须在该句 / 段**结束之后立刻**写出标注，整段用**一对中文全角括号**包住：

```
（资料路径：`.aws-article/products/<产品名>/某介绍.md`）
```

反引号内的路径必须与资料库条目里的 `资料路径：` **完全一致**。这两条标注由 `wxart draft` 的写作提示词强制注入；**剥离它只在审稿定稿时做**（`wxart draft strip-citations`，见 [04-review.md](04-review.md)），本阶段**保留**。

## 两条出稿路（含降级）

**路 A · 调第三方写作模型**：`wxart draft draft {run_dir}/topic-card.md -o {run_dir}/draft.md`。`{run_dir}/topic-card.md` 是选题卡与任务书要点的可读版；它所在目录决定脚本读哪份 `article.yaml`（`default_structure` / `default_closing_block` 等预设必须在本篇收敛为**单元素列表**）。业务资料用 `--reference .aws-article/products/<产品名>/<文件名>.md`，可重复、**最多 5 个**。

| 退出码 | 含义 | 做什么 |
|---|---|---|
| 0 | 成功，正文已写入 `-o` | 下一步 |
| 1 | 硬错误（API 失败、YAML 解析、文件缺失） | 读 stderr 修配置；仍不行就走路 B |
| 2 | **写作模型未配置**（stderr 含 `[NO_MODEL]`，仅 `draft`/`rewrite`/`continue`） | **自动降级**走路 B，**无须**「本次例外」 |
| 3 | `wxart llm-write` 未配置写作模型（`WRITER_NOT_CONFIGURED`） | 同上，降级为 Agent 直写 |
| 4 | `wxart llm-write` 调用失败 | 可重试一次，再降级 |

**路 B · Agent 直写**：`wxart draft prompt draft {run_dir}/topic-card.md` 只输出 `{"system_prompt":…,"user_prompt":…}`，**不调 LLM、不需要模型配置**，退出码 0；诊断走 stderr，stdout 是纯 JSON。拿到提示词后**按同一套约束**自己写 `draft.md`——不许因为「自己写」就放宽配额。

**路 C · `wxart llm-write`（混合路由，文件→文件）**：适合把长文生成卸载给便宜的写作模型，stdout 只回简短摘要，正文不回灌上下文。`--brief` 要写清：选题 / 框架 / **真实素材锚点** / 人格 / 目标字数 / 定向修改指令。

**无论走哪条路**，都必须告知用户当前用的是哪种：`ℹ️ 使用写作模型（{model}）出稿` / `ℹ️ 写作模型未配置，本次由当前对话模型直接写稿（使用相同写作约束）` / `ℹ️ 第三方 API 不可用，本次由当前对话模型代写（使用相同写作约束）` + 原因。写完都要**通读一遍**：修正归属、重复、跳跃、越界内容，核对每节是否服务 `brief.sections` 与对应 claim。

## 自检：`wxart draft check`

**硬性项（不达标 → 退出码 1）**：第一个 `##` 之前没有 `>` 摘要；加粗密度（正文中文字数 ≥300 时需求数 = `max(1, 中文字数 // 100)`，不足则不过）；有连续 **200 字**没有任何加粗落点（落点含列表里的 `- **标签**：`）；没有带出处的金句，或金句出处超过 **25 字符**（正则 `^(.*?)\s*(?:——|—|--)\s*([^\s—][^—]{0,24})$`，**整段锚定**，与排版侧逐字一致）。

**提醒项（WARN，不影响退出码）**：加粗偏长（显示单位 > 12，一个汉字算 1、一串连续数字 / 英文算 1）；裸名词（纯中文且 ≤4 字的加粗占全部加粗 **> 50%**）；数字覆盖（正文 ≥3 个带单位数字：`%` `倍` `美元` `分` `万` `亿` `个百分点`，而带数字的加粗数 × 3 < 加粗总数）；加粗位置（落在段落首句的比例 **> 60%**）；带出处的引用超过一处（金句应恰好一处）；全文没有 `- **标签**：说明` 列表。

脚本还会把**全文加粗串成一行**打印出来。**退出码为 0 只代表机械项通过**——那一串读起来像不像一份能独立看懂的提要，必须自己再读一遍；串不起来就是挑错了，不是数量不够。脚本管不到、需手工核对的两项：**配图占位数与 `image_density` 是否一致**、格式是否合法；禁用词、段落长度、开头吸睛度、小标题密度的粗扫。
⛔ 本步**不替代审稿**：合规、敏感词、文末 embed、引用标注剥离都归 [04-review.md](04-review.md)。

## 落盘

```bash
wxart run update --patch '{"framework":"观点","enhance_strategy":"新角度","persona":"industry-observer","word_count":0,"provenance":{"verified_sources":0,"unverified_sources":0,"exemplars":[],"playbook_rules":[]}}'
wxart run step write completed
```

`provenance` 的数字用 `wxart sources list --json` 的真实统计填；`exemplars` 填读过的范文路径，`playbook_rules` 填生效的 `hard=true` 规则名。**不要凭印象填。** 用户单独要这一环时，告诉用户初稿、任务书、主张清单与来源账本的路径，并说明**初稿不是成稿**，需要继续审稿。

## 分支

| 情况 | 处理 |
|---|---|
| 三项账号约束缺失 | 逐项问用户并写回 `{home}/config.yaml`，**先于写稿** |
| `writing-spec.md` / `style.yaml` 不存在 | 前者跳过该维度；后者提示跑 `wxart init`，不要凭空假设账号语感 |
| `playbook.md` 有缓存分数 | 以 `wxart learn-edits --summarize --json` 的实时结果为准 |
| 范文库为空 | 跳过，不阻断 |
| 搜索失败 | 删掉无法核实的数字与引述，只写有边界的判断，`run step write failed` 记录 |
| `wxart draft draft` 退出码 2 / `llm-write` 退出码 3 | 自动降级为 Agent 直写，用 `prompt` 的同一套提示词 |
| `--reference` 路径不合法 | 只接受 `.aws-article/products/<产品名>/<文件名>.md`，不接受 `images/` 子目录 |
| 材料不足以支撑主张 | 缩小主张或换框架；**不得**补造故事或制造「内幕」 |
| 人格要求私人开场但 `available=false` | 换成 `fallback_opening_style` |
| `check` 有硬性项未过 | 先补再往下；不许带着 FAIL 交审 |
