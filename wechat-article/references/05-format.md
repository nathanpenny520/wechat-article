# 排版：Markdown → 微信可粘贴 HTML

排版是**确定性转换**：读成稿、出一份全内联样式的 HTML。判断只发生在「选哪个引擎、哪套主题」这一步。

## 读什么 / 做什么 / 产物

```bash
wxart format {run_dir}/article.md               # 默认 wx 引擎
wxart format {run_dir}/article-illustrated.md   # 有带图副本时优先用它
wxart format {run_dir}/article.md -o {run_dir}/article.html > {run_dir}/format.log 2>&1
```

| 项 | 内容 |
|---|---|
| 读 | `article.md` 或 `article-illustrated.md`、`article.yaml`（本篇预设）、`config.yaml`（全局候选池）、主题 YAML、组件 YAML |
| 写 | `article.html` |
| 日志 | stdout 与 stderr 一起重定向到 `{run_dir}/format.log`。**脚本输出一律落盘**——屏幕滚过去就没了，日志是排障唯一凭据 |
| 不写 | 不改 `article.md`；正文不含文章标题（首个 `#` 被跳过，标题在后台单独填） |

## 1. 先定引擎

| 判据 | 选 |
|---|---|
| 要省事、主题现成、自动规避微信坑、要 `validate` 校验；稿子里有代码块/外链/中英混排 | **wx**（默认） |
| 要「模版 × 配色」两层组合、要 `:::` 版式组件（编号小标题 / 金句卡 / 数据卡 / 对比两栏 / 结构分层）；已有品牌模版 YAML | **aws** |

**铁律：同一篇不要混用两个引擎的产物。** 两个引擎的 `:::` 容器名**不通用**——wx 认 `dialogue/timeline/callout/quote/pullquote/label/steps/highlight/summary`，aws 认 `section-title/lead/quote-card/stat/steps/compare/layers/checklist/closing`。名字重合的只有 `steps` 一个，语义与参数完全不同（wx 的 `steps` 不带方括号参数，aws 的 `steps[标题]` 第一行是表头）。

**换引擎或换主题 → 必须整篇重跑，并重新跑 `wxart validate`。** 不许在上一版 HTML 上局部改。混了两种容器的 HTML，两边都渲染不出来。

## 2. wx 引擎

### 命令与参数

```bash
wxart preview <md> -t sspai -o preview.html --no-open   # wx 引擎主命令
wxart format  <md>                                      # 同名别名，默认就是 wx
```

| 参数 | 说明 | 默认 |
|---|---|---|
| `-t` / `--theme NAME` | 主题名（YAML 文件名，不带 `.yaml`） | `professional-clean` |
| `-o OUT` | 输出路径 | 与输入同名的 `.html` |
| `--no-open` | 不自动打开浏览器 | 打开 |
| `--no-paste-safe` | 关闭粘贴加固（不做 `<span leaf="">` 包裹） | 开启加固 |

输出是**完整 HTML 页面**（含 `<head>`/`<style>`）用于浏览器预览；`validate` 只看 `<body>` 内容，因为预览包装的 `<head>/<style>` 不参与粘贴与发布。

其他：

```bash
wxart themes                 # 列 18 个主题名 + 一句话描述
wxart gallery [<md>] -o out.html --no-open   # 全部主题并排预览（不给 md 用内置样张）
wxart validate <html> [--json]
```

### 18 个主题（按用途分组）

| 组 | 主题名 |
|---|---|
| 通用商务 | `professional-clean`（干净专业，适合大多数商业内容）、`minimal`（极简黑白灰，内容至上）、`minimal-gold`（白底金色细线，高端品牌） |
| 技术与产品 | `tech-modern`（蓝紫渐变）、`bytedance`（白底品牌蓝、大间距）、`github`（白底蓝链、等宽代码块）、`midnight`（深蓝黑底白字，深夜阅读） |
| 文化与阅读 | `newspaper`（米黄底深棕衬线）、`ink`（宣纸底墨色、中文衬线、留白疏朗）、`warm-editorial`（暖色编辑风）、`sspai`（暖白底红点缀，清爽文艺） |
| 生活向 | `elegant-rose`（浅粉底玫瑰点缀） |
| 强观点 / 高饱和 | `bauhaus`（纯白底黑主、红蓝黄色块）、`bold-green`（森林绿）、`bold-navy`（藏青）、`focus-red`（中国红标题与引用边框） |
| 品牌专属 | `impeccable`（衬线正文＋无衬线标题，深青＋琥珀双色，反 AI 味）、`lobster-notes`（橙红主调、深色代码块、移动端优先） |

### 主题 YAML 的字段

**必填四项**，缺一个 `load_theme` 直接抛 `ValueError`：`name`（主题名）、`description`（一句话描述，`wxart themes` 打印它）、`base_css`、`colors`。

| 字段 | 说明 |
|---|---|
| `base_css` | 主题 CSS 源码。解析成「选择器 → 属性表」时**只保留简单选择器**：含 `:` `@` `>` `+` `~` `[` `*` 的整条丢弃（等于没有伪类、伪元素、媒体查询、组合子）。`var(--x)` 按 `colors` 的键替换（去掉 `--`，也尝试 `-`→`_`） |
| `colors` | 颜色字典。`text`、`primary`、`secondary`、`highlight_bg`、`highlight_border`、`summary_bg`、`summary_border` 被 converter 直接读取 |
| `aigc_footer` | **默认 `true`**：正文末尾追加一行居中的「本文由 AI 辅助创作，作者进行了实测验证和编辑修改。」合规需要，只有显式写 `false` 才关闭 |
| `section_numbering` | 为 `true` 时给每个 `<h2>` 前置两位编号 `01`、`02`……（`{i:02d}`，主色、字重 800、右边距 10px） |
| `darkmode` | 字典，**非空才注入** `data-darkmode-*`。键与默认值：`text` `#c8c8c8`、`background` `#1e1e1e`、`primary` `#6aadff`、`code_bg` `#2d2d2d`、`code_color` `#d4d4d4`、`quote_bg` `#2a2a2a` |

主题查找顺序：`{home}/themes/`（用户主题，见 10-learn.md）→ 内置 18 套（`{skill_dir}/scripts/wxengine/toolkit/themes/`）。

### 微信兼容自动修复清单

`convert()` 按固定顺序执行下面这些；**不需要手工处理，也不要手工再改一遍**：

1. **外链 → 上标脚注 + 文末参考链接**。除 `#` 锚点外，每个 `<a>` 换成「原文字 ＋ `<sup>[N]</sup>`」（计数从 1）；文末追加 `hr` + 「参考链接」＋ 每行 `[N] 原文字: URL`（12px、`word-break: break-all`）。
2. **CJK-Latin 自动空格**。CJK 集 `[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef]`、拉丁集 `[A-Za-z0-9]`，两侧边界各插一个空格。**围栏代码块内跳过**。
3. **加粗后的中文标点外移**：`(<strong>)(.*?)([，。！？；：、]+)(</strong>)` → 标点移到 `</strong>` 之后。
4. **`<ul>/<ol>` → `<section>`**。原生列表渲染不稳。每个 `li` 变 `display:flex` section：无序用主色 `•`（18px），有序用主色 `N.`（700 字重），正文落在 `flex:1` 的 span。
5. **暗黑模式 `data-darkmode-*`**。带 `color` 的 `p`/`span`/`section` 加 `data-darkmode-color` + `data-darkmode-bgcolor="transparent"`；`h1`–`h4` 同上；`pre`/`code`/`blockquote` 按 `darkmode` 各键取值；`strong` 用 `darkmode.primary`。
6. **全 CSS 内联**：`base_css` 逐选择器套进元素 `style`；**元素已有内联样式优先**，主题值只补缺键。
7. **`<div>` → `<section>`**：来源是 codehilite 的 `<div class="codehilite">` 与 fenced_code 的 `language-*`。
8. **清 `class` / `id`**：全部删除（微信会剥离，留着还占字节）。
9. **`<p>` 强制 `color`**：缺 `color` 的补 `colors.text`（默认 `#333333`）。
10. **`<pre>` 保留空白**：缺 `white-space` 的补 `white-space: pre-wrap; word-wrap: break-word`。
11. **GIF 角标**：`src` 去掉 `?` 后以 `.gif` 结尾的 `<img>`，前面插右对齐 `GIF` 小标签（`rgba(0,0,0,0.55)` 底、白字 11px、圆角 4px、字距 1px）——**不用 `absolute` 定位**。
12. **图片响应式**：缺 `max-width` 的 `<img>` 补 `max-width:100%; height:auto; display:block;`，上下外边距 24px（GIF 为 `4px auto 24px`）。

### wx 的 `:::` 容器（9 个，只此一集合）

块首 `:::` 与块尾 `:::` 必须各自独占一行，中间是内容。

| 容器 | 语法 | 渲染 |
|---|---|---|
| `dialogue` | `:::dialogue` | 聊天气泡。行首 `> ` 的走右侧（主色底白字、圆角 `12px 12px 2px 12px`），其余走左侧（`#f3f4f6` 底、圆角 `12px 12px 12px 2px`），最大宽 80% |
| `timeline` | `:::timeline` | 竖向时间轴。每行一个节点：主色圆点（10×10、`border-radius:50%`）＋ `#e5e7eb` 竖线，右侧正文 |
| `callout` | `:::callout tip` / `warning` / `info` / `danger` | 左侧 4px 实色边框的提示框。四型配色：tip `#059669`/`#ecfdf5`/💡、warning `#d97706` /`#fffbeb`/⚠️、info `#2563eb`/`#eff6ff`/ℹ️、danger `#dc2626`/`#fef2f2`/🚨。标题行是「图标 ＋ 类型大写」。**认不出的类型退回 `info`** |
| `quote` | `:::quote` | 左主色粗边、浅渐变底、斜体、内容两侧加英文双引号 |
| `pullquote` | `:::pullquote` | 居中的独立金句：主色大引号、18px/600 字重、下方一条 36×2 主色短横 |
| `label` | `:::label`（左竖条式）/ `:::label pill`（实色药丸式） | 小节标签。默认：4px 主色竖条 ＋ 16px/700 标题；`pill`：主色底白字、13px、`border-radius:999px`、字距 1px |
| `steps` | `:::steps` | 步骤卡。每行一步自动编号（22×22 主色圆、白字、居中），行首的 `-` 会被吃掉 |
| `highlight` | `:::highlight` | 琥珀色信息框。**第一行是标题（主色/700），其余是正文**；底色取 `colors.highlight_bg`（默认 `#fef7e8`） |
| `summary` | `:::summary` | 青绿色总结框。**第一行是标题（默认「总结」），其余是正文**；底色取 `colors.summary_bg`（默认 `#e8f5f0`） |

容器内的 `**加粗**`、`*斜体*`、`` `行内代码` `` 在预渲染阶段就被转成 HTML（否则 markdown 会跳过整块 HTML 里的行内语法，星号原样漏出）。

### 粘贴加固 `<span leaf="">`

微信编辑器在**粘贴**时会重排不在 leaf span 内的文本、剥掉空元素的样式。`make_paste_safe()` 做两件事：

1. 每个非空文本节点包一层 `<span leaf="">`（`<pre>` / `<code>` 内跳过，已在 leaf span 内的跳过）；
2. 每个无文字的 `section`/`span` 补 `<span leaf=""><br></span>` 占位，防样式被剥（装饰短横、竖条、圆点都靠这条活着）。

**适用场景：只用于预览/粘贴路径。** API 发布草稿箱不经过编辑器改写，`article.html` 不需要 leaf 包裹——`--no-paste-safe` 就是给这条路径用的。

### `wxart validate`：16 条 ERROR + 4 条 WARN

```bash
wxart validate {run_dir}/article.html
wxart validate {run_dir}/article.html --json
```

只校验 `<body>` 内的内容（有 `<body>` 就取它）。

**16 条 ERROR**（微信会过滤该写法或样式失效）——左列是规则名，括号内是触发正则语义：

| 规则（触发条件） | 说明 |
|---|---|
| `style_tag`（`<style` + 空白/`>`） | `<style>` 会被过滤，样式必须内联 |
| `script_tag`（`<script` + 空白/`>`） | `<script>` 会被过滤 |
| `link_tag`（`<link` + 空白/`>`） | 外部 CSS / 字体 `<link>` 会被过滤 |
| `div_tag`（`</?div` + 空白/`>`） | 客户端不渲染 `<div>` 的内联样式（真机实测），应用 `<section>` |
| `class_attr`（标签内 ` class=`） | class 无规则可挂（`<style>` 会被删），样式必须内联 |
| `id_attr`（标签内 ` id=`） | id 会被剥离 |
| `position_unsupported`（`position:` 为 `fixed`/`absolute`/`sticky`） | 这三种定位在微信正文不生效 |
| `float_css`（`float:` 为 `left`/`right`） | float 布局不可靠，应用 flex |
| `media_query`（出现 `@media`） | 不被支持；暗黑模式改用 `data-darkmode-*` |
| `keyframes`（`@keyframes` 或 `animation:`） | CSS 动画不被支持 |
| `import_css`（出现 `@import`） | 不被支持 |
| `display_grid`（`display:` 为 `grid`） | 不被支持，应用 flex |
| `css_var`（`var(` + `--`） | CSS 变量不被支持，颜色要写实际值 |
| `external_font`（`url('…http(s)://….woff2/woff/ttf/otf/eot`） | 外部字体文件不会被加载 |
| `nodeleaf_content`（`<section nodeleaf>` 内出现块级元素，或顶层子元素 > 1） | 官方只允许单个图片/视频/官方组件；真机实测块级内容会**整段消失** |
| `quoted_url`（`url(` 后紧跟引号） | `url('…')` 会让**整个元素被拆掉**（背景图连同 `<section>` 一起消失），引号必须去掉 |

**4 条 WARN**（不阻断）：

| 规则（触发条件） | 说明 |
|---|---|
| `iframe_tag`（出现 `<iframe`） | 仅白名单来源（腾讯视频等）可用 |
| `external_link`（`<a href="http(s)://…` 且目标非 `mp.weixin.qq.com`） | 未认证号会被过滤；wx 正常产物应已转成脚注，出现即说明有手改或外部 HTML |
| `too_many_images`（`<img>` 数量 > 10） | 超过微信正文上限 10 张，发布时会移除末尾多余的 |
| `nodeleaf_empty`（`<section nodeleaf>` 内没有任何元素） | 这个容器只用于承载单个图片/视频/官方组件，空着没意义 |

**门禁：`validate` 不会自动阻断。** 排版命令只在 stderr 打印一行告警就继续，退出码始终是 0。所以**必须显式跑一次 `wxart validate` 并要求退出码为 0**（存在任一 ERROR 时退出码为 1）。不跑就等于没有校验。

上面这些规则背后的实测边界——什么能活、什么会被删、中文字体为什么指定了也没用、字重与着重号、SVG 的 `id` 坑、满版贴边为什么做不到——见 [20-wechat-html-constraints.md](20-wechat-html-constraints.md)。设计新主题或新组件前先对一遍那份限制，再动手。

## 3. aws 引擎

### 命令与参数

```bash
wxart format <md> --engine aws [--theme 杂志] [--scheme 石青] [--color '#C0392B'] \
                 [--font-size 15px] [-o out.html] [--no-preformat]
wxart format --engine aws --list-themes
wxart format --engine aws --preview [模版名] -o preview.html
wxart format --engine aws --export-theme 亲和 > my-brand.yaml
```

| 参数 | 语义 | 默认 |
|---|---|---|
| `--theme` | 模版名。**显式指定始终优先** | `亲和` |
| `--scheme` | 配色名（`--list-themes` 里的名字）。省略则读本篇 `default_format_scheme`，再无则用模版的 `default_scheme` | 模版声明 |
| `--color` | 覆盖主色（如 `#0F4C81`）。派生色（`primary-fill` / `primary-ink` / 淡底 / 高亮笔）按主色自动重算 | 主题默认 |
| `--font-size` | 口径**不是「设一个字号」**：它把主题 `p` 与 `li` 里**硬编码的 `font-size` 一并正则替换**（`font-size:\s*[^;]+;?` → `font-size:{值};`）。所以主题若用 `{font-size}` 变量，这次覆盖同样生效 | `16px` |
| `-o` | 输出路径 | 同名 `.html` |
| `--no-preformat` | 跳过 Markdown 预格式化 | 执行预格式化 |
| `--list-themes` | 列出模版：长相 / 适合 / 不适合 / 每套配色的色值与口径，并带 `[内置]` `[自定义]` 来源标记 | |
| `--preview [模版名]` | 渲成对照页（每栏 375px，与真机同宽）。给模版名 → 并列它的三套配色；不给 → 并列所有模版的默认色 | |
| `--export-theme <名>` | 以 YAML 导出主题（合并默认变量与样式，`{变量}` 引用保持原样），可重定向成自定义主题起点 | |

**预格式化**（默认开启）只作用于正文文字：中英文间加空格、ASCII 引号转「」、合并空行。**围栏代码块、行内代码、链接/图片目标、`{embed:…}`、原生 HTML 标签与裸 URL 原样保留**，行内代码内容做 HTML 转义。

### 8 套模版 × 3 配色

`模版`（骨架）＝ 标题装饰、导语、金句卡、图片处理、分隔、文末；`配色`只覆盖一组变量，版式不动。

| 模版 | 骨架 | 适合 | 不适合 | 三套配色（第一个是默认） |
|---|---|---|---|---|
| `亲和` | kuai | 教程、职场、面向新手的解释性长文 | 严肃议题、财报解读；品牌调性偏冷硬或极简的号 | 黛紫 `#6B5B95` / 松绿 `#4E7D6B` / 靛蓝 `#3F5F9E` |
| `资讯` | bao | 快讯、评测、行业观察 | 抒情散文、个人随笔；段落很短的碎片化内容 | 墨绿 `#1F6F5F` / 绛红 `#9B2D30` / 藏青 `#24406B` |
| `书卷` | shu | 人文、读书、历史、深度长文 | 工程文档、数据密集的评测；追求现代感或年轻化的号 | 朱砂 `#9E3D30` / 黛蓝 `#2F4A6D` / 苍绿 `#3F5E4A` |
| `杂志` | yi | 品牌故事、人物访谈、生活方式；图多的稿子 | 纯文字无配图的稿子；信息型短文 | 石青 `#4A5D6E` / 驼褐 `#8A6A4B` / 铁锈 `#9C4F3B` |
| `活力` | cai | 产品发布、增长复盘、面向年轻读者 | 严肃议题与坏消息；很长的深度稿 | 靛青 `#5B4BFF`+`#17A398` / 玫紫 `#B83280`+`#6B46C1` / 暮橙 `#D9480F`+`#A61E4D` |
| `手账` | shou | 个人笔记、复盘、学习记录；第一人称 | 对外的官方公告、白皮书；加粗特别多的稿子 | 朱红·黄笔 `#C8553D`+`#FFE066` / 墨蓝·粉笔 `#2C4A7A`+`#FFC2D9` / 深绿·薄荷笔 `#2F6B4F`+`#C6F0C2` |
| `硬朗` | gou | 观点、宣言、立场鲜明的内容 | 温和的科普与教程；需要亲和力的品牌内容 | 蓝黄 `#1F4FD6`+`#F2C230` / 赤黑 `#C0392B`+`#1A1A1A` / 绿橙 `#2A9D8F`+`#E76F51` |
| `技术` | ma | 工程实践、技术文档、代码讲解 | 情绪向和故事向内容；完全没有代码和数据的稿子 | 蓝 `#2563EB`+`#E5E7EB` / 紫 `#7C3AED`+`#E5E7EB` / 绿 `#047857`+`#E5E7EB` |

`sort_order` 依次为 亲和 1、手账 2、书卷 3、杂志 4、活力 5、资讯 6、硬朗 7、技术 8。内置搜索路径里放 4 套（亲和 / 资讯 / 书卷 / 杂志），另外 4 套（活力 / 手账 / 硬朗 / 技术）由 `wxart init` 从 `presets/templates/` 铺进 `presets/formatting/`。**不要只按名字猜**，先跑 `--list-themes`，再按 `--preview` 的实际观感定。

### 主题 YAML schema

```yaml
name: 我的品牌              # 显示名
skeleton: kuai              # 骨架名 → 用 components/<skeleton>/ 下的装饰组件
sort_order: 9               # 列表排序
description: 品牌专用排版
when_to_use: …              # 什么时候用（--list-themes 会打印）
when_not_to_use: …          # 什么时候别用
variables:                  # 默认变量；顶层就是「默认那一档配色」
  primary-color: "#A93226"
default_scheme: 朱砂         # 默认配色名的唯一来源（不再靠 schemes 下标猜）
schemes:                    # 3 档配色，每项只是一组 variables 覆盖
  - name: 朱砂
    variables: {primary-color: "#9E3D30"}
    description: 中式暖红
styles:                     # 样式规则，可用 {变量名} 引用变量
  p: "font-size:{font-size}; line-height:1.8; color:#3a3a3a; margin:10px 0;"
```

**可用变量**（`styles` 与组件模板里都能引用，括号内是默认值）：

- 颜色：`primary-color`（`#0F4C81`）、`bg-accent-color`（`#F0F4F8`）、`text-color`（`#333333`）、`text-light`（`#666666`）、`text-muted`（`#999999`）、`bg-light`（`#F7F7F7`）、`border-color`（`#EEEEEE`）、`link-color`（`#576B95`）、`secondary-color`（次色，渐变类模版用，各模版自定）
- 排版：`font-size`（`16px`，`--font-size` 可覆盖）、`font-family`（system fonts）、`line-height`（`1.8`）、`paragraph-spacing`（`1.5em`）
- **派生变量**（由主色自动算，不要手填）：`primary-fill`、`primary-ink`、`highlight-soft`、`highlight-pen`、`bg-accent-soft`、`secondary-on-fill`、`secondary-soft`。`primary-ink` 保证在白底上对比度 ≥ 4.5

**可用样式键**：`h1` `h2` `h3` `h4` `p` `strong` `em` `a` `blockquote` `ul` `ol` `li` `hr` `img` `figcaption` `code` `pre` `table` `th` `td` `del` `strong-color`。`p` / `strong` / `a` / `table`/`th`/`td` 留空时走内置默认。

自定义主题放在 `presets/formatting/<名>.yaml`（工作区 `.wxarticle/presets/formatting/` 优先），**同名覆盖内置**，`--theme <名>` 立即可用。

### aws 的 `:::` 组件（10 个，只此一集合）

语法：`:::组件名[方括号参数]` → 正文 → `:::`。方括号参数用 `/` 或 `|` 切成 `{arg0}` `{arg1}`……（只认这两种分隔符），`{arg}` 是整个参数原文；切出的空位补空串。

| 组件 | 参数 | body | 用途与硬约束 |
|---|---|---|---|
| `section-title` | 编号（两位数字，如 `01`） | `single` | 编号小标题。正文分 3 段以上且各段并列/递进时才用。编号必须连续；**不要写「第一节」**（角标会撑成长胶囊）；标题 ≤ 14 字 |
| `lead` | 无 | `free` | 导语。开篇两三句说清「讲什么、为什么值得读」。不超过四行；**不要和引用块混用**（导语走上下细线题眉式，引用块保持卡片式） |
| `quote-card` | 出处（人名/机构/报告名，可为空） | `free` | 金句卡。全文最值得被单独记住、脱离上下文仍成立的一句。**一篇最多一张**；句子 ≤ 40 字 |
| `stat` | 卡片标题 | `rows`×2 列 | 数据卡。第一列只放数字与简短单位，第二列是解释。**两到三行最好看，超过四行会挤**；数字之间要可比 |
| `steps` | 流程标题 | `rows`×2 列 | 步骤流程。序号自动编（`{n}`），**不要自己写「1.」**；步骤名 ≤ 12 字（细节放第二列）；不超过六步；「准备工作」不要编成第 1 步 |
| `compare` | `左标题 / 右标题` | `rows`×2 列 | 对比两栏。每格 ≤ 20 字；两边必须同一维度；左右标题不能用同一个词；只列优点不列缺点会露馅 |
| `layers` | 分层标题 | `rows`×2 列 | 结构分层。只用于**纯并列罗列**；有包含/嵌套或数据流向就用配图。不超过五层，两层不值得起块 |
| `checklist` | 清单标题 | `rows`×2 列，带 `row_map` | 要点清单。第一列只认 `done`/`todo`/`warn`，映射成 `✓`/`○`/`!`。**不要写中文状态**；事项 ≤ 18 字 |
| `closing` | 作者名 | `free` | 文末区块。互动引导 + 署名。一篇只能一个；引导语要具体（抛回给读者一个问题），不要「感谢阅读，下期再见」 |
| `aside` | 短标签（提醒 / 注意 / 前提 / 补充） | `free` | 旁注块。与正文区分开的补充：使用前提、例外、易错点。**一篇文章最多两处**；正文 ≤ 3 行；标签 ≤ 4 字；**关键结论不要只写在这里**（旁注的视觉地位低于正文） |

上面的 `rows` 列分隔符默认都是 `|`。**解析规则**：逐行切列并 strip，**列不足补空串、多余的列丢弃**（不会因为多打一个分隔符就整块渲染失败）。`checklist` 的 `row_map_default` 是漏写状态时的兜底：某列配了 `row_map` 却填了表外的值、且总列数不够时，右移一格、该列取默认符号 `○`。行模板可用 `{n}`（序号）、`{n2}`（两位序号）、`{nz}`（中文数字，1–99）、`{c0}` `{c1}`……，未用到的列位会被清掉；**`{nr}`** 是罗马数字（1–39），给纸书感模版的 `h2-deco` 做章节编号。

**未知组件名或缺少结尾 `:::` → 按原文输出并告警，不吞内容。** `:::highlight` 和 `:::note` 保持删除状态（没有模版定义过 `highlight`，兜底一路退回 `blockquote`，渲出来和普通引用块逐字相同）。**需要提示框用内置的 `:::aside`**——它按当前主题派生底色与竖条，八套骨架下都跟随配色。

**为什么不把 `aside` 直接叫 `callout`**：wx 引擎的 `:::callout` 参数是**固定类型关键字**（`tip`/`warning`/`info`/`danger`），aws 组件的参数是**自由标签**（`{arg}` 原样渲染）。同名不同语义正是 `wxart guard containers` 要拦的东西，所以这里换名而不合并。相应地，`wxart guard containers --engine aws` 认识 `aside`，认不得 `callout`。

### 标准 markdown 能自动触发的组件

写作侧只产出标准 markdown，识别结构是排版层的事。渲染器认这些形态：

| 作者写的 | 排版层做的事与触发条件 |
|---|---|
| `**加粗**` | 上本模版的重点色或荧光底——正文里唯一的扫读落点 |
| `- **标签**：说明` | 走 `li-label` 组件，标签视觉上提出来。正则 `^\*\*([^*]+)\*\*[：:]?\s*(.*)$`，且冒号后**必须有内容** |
| `- [ ]` / `- [x]` | 换成该骨架的三态图标（取 `checklist` 组件的 `row_map`，四套骨架各有方言）。正则 `^\[([ xX])\]\s+(.*)$`；**不处理的话方括号会原样漏进正文** |
| `> 金句。 —— 出处` | 排成金句卡。引用整块匹配 `^(.*?)\s*(?:——\|—\|--)\s*([^\s—][^—]{0,24})$`，即出处 **≤ 25 字符**且破折号前非空 |
| `>` 出现在第一个 `##` 之前 | 走 `lead` 组件（导语）。条件：尚未进入引用块、且尚未出现过 `##` |
| `> 引文` | 非金句卡形态的普通引用，前面补一个大引号（`quote-mark` 组件） |
| `![图](x "图注")` | 走 `img-deco` 组件（四角标）＋ 图注。**只有括号里路径之后引号中的才是图注**；alt 冒号后那段是给生图模型看的画面指令，不显示给读者。**没写 title 就不出图注** |
| `---` / `##` / 正文末尾 | 分别走 `hr-deco` 装饰分隔、`h2-deco` 标题装饰（笔锋 / 折角块；`h3-deco` 同理）、`article-end.yaml` 文末记号（每篇一次）。**骨架目录里有同名组件才生效** |

图注还受合并配置的 `caption_style` 控制：`有图注` 全出、`无图注` 全不出、`关键图有` 只有信息位的图出（`alt` 冒号前的类型名属于 `{信息图, 实证, 流程图, 对比}` 才算信息位；认不出就不出——不替用户放宽他刚设的限制）。

**只认形态，不推断语义。** 看见 `1. 2. 3.` 不会渲染成「第一步 第二步」——有序列表在 markdown 里只表示枚举，那是替作者断言一个他没说的顺序。真稿实测：三组多项有序列表里只有一组真有先后。

### 组件查找顺序与用户覆盖

```
内置基础版  →  内置的骨架专属版（components/<骨架名>/）  →  用户自定义（.wxarticle/presets/components/）
```

后者覆盖前者。找到 spec 需同时有 `name` 和 `template`。组件模板里的 `{primary-color}` `{text-color}` 等占位符从当前主题取值，所以组件与任何主题组合都不会脱节。每个组件 YAML 带 `when_to_use` / `when_not_to_use` / `anti_pattern`——**选组件前先读这三项**，它们拦住「因为好看所以用」。

### `{embed:…}` 的合并规则（四类）

① **名片与小程序**以全局 `config.yaml` 的 `embeds` 为准；② **「往期链接」是唯一例外**——本篇 `article.yaml` 可写 `embeds.related_articles`，与全局 `related_articles` **深度合并**（用于每篇不同的推荐，**至多 3 条**）；③ **只有合并结果里 `embeds` 非空时才解析** `{embed:profile|miniprogram|miniprogram_card|link:名称}`，为空则不做任何替换（视为无配置）；④ 认不出或找不到配置的占位符渲染成注释 `<!-- 未找到…配置: 名称 -->`，不会静默消失。**占位符与配置对不上时排版阶段会失败。**

## 4. 主题解析顺序与预设收敛

**通用规则**：命令行显式指定 > 本篇 `article.yaml` > `config.yaml` 的 `custom_*` > `config.yaml` 的 `default_*` > 内置默认。

- **wx**：`-t/--theme` 优先；不传则**只读同目录 `article.yaml`**；主题名对应内置或自定义 YAML。
- **aws**：`--theme` 优先；不传时**只读与 `article.md` 同目录的 `article.yaml` 的 `default_format_preset`**——该键**必须是 YAML 列表**（`[]` 或单元素 `[主题名]`），**多候选直接报错**；为空则用内置默认 `亲和`。配色同理：`--scheme` > `default_format_scheme`（单元素）> 模版的 `default_scheme`。

**预设收敛（硬性）**：全局候选池可以是多元素列表，但**进入排版与配图前必须在本篇 `article.yaml` 里收敛成单元素列表**：`default_structure`、`default_closing_block`、`default_title_style`、`default_format_preset`、`default_format_scheme`、`default_cover_image_style`、`default_sticker_style`。**唯一例外是 `default_article_image_style`**——正文是**每个图位各选一个形态**，收敛成一个等于整篇配图用同一种形态。

## 5. 核对观感：`wxart shot`（非阻塞）

前面所有门禁检的都是 HTML 的**正确性**——标签闭合、内联样式、兼容清单、占位符。没有一条检**观感**。结果是「主题没选对、组件用错了、标题折行难看」这类问题一路通过门禁，直到人打开草稿箱才发现。

`wxart shot` 把观感也变成可核对的产物：

```bash
wxart shot article.html -o 首屏.png                              # 375px 宽整篇截图
wxart shot article.html -o 首屏.png --crop 0,1400                 # 只看首屏
wxart shot a.html b.html -o 对比.png --sheet-height 1500          # 每张单独出 + 一张横向对照图
```

要点：

- **默认 375px 宽、2 倍像素密度**。375 是微信正文宽度；宽度按容器而非浏览器视口控制（Chrome 的 `--window-size` 只决定裁切范围，布局视口会停在 500px，用 `margin:0 auto` 居中会被裁掉右边一半）。
- **同时报横向溢出**。每个元素右边界超过容器就计数并打印摘要。375px 下溢出的元素在手机上会被右边切掉，而桌面浏览器全宽时看不出来。
- **多份输入出一张对照图**，换主题、换骨架前拿它比一眼，不用靠猜。
- 需要 Chromium 内核浏览器（Chrome / Chromium / Edge / Brave）。找不到时**打印已查找的路径并返回 3**，同时提示退回 `wxart preview-page`——不静默失败，也不联网下载浏览器。
- `--crop` 和对照图需要 Pillow（受管 venv 里有；缺了只有这两项不可用，整篇截图仍能出）。

**它是辅助步骤，不进硬门禁**：截图依赖本机浏览器，把「有没有浏览器」变成发布前置条件会误伤干净环境。但**换了主题或骨架之后应当跑一次**——「是否要换」的判断不该由没有眼睛的那一方做。

## 6. 门禁

| 门禁 | 判据 | 不通过 |
|---|---|---|
| 正文已封存 | `article.md` 非空、`state.yaml` 的 `status=completed` | 回到审稿，不许先排版 |
| 产物由**当前**正文生成 | `article.html` 内容对应当前 `article.md`；换引擎/换主题也必须整篇重跑 | 重跑 `wxart format`，不许拿旧 HTML 交付、不许局部改 |
| 校验通过 | **显式跑** `wxart validate <article.html>`，**退出码 0**（没有任何 ERROR） | 修 `article.md` 或换主题后整篇重跑 |
| 无残留占位符 | `article.html` 与正文里都不含 `placeholder` | 先走 [06-visual.md](06-visual.md) 补齐配图 |
| 图片数量 | `<img>` ≤ 10 | 减图或合并，微信发布时会移除末尾多余的 |

**第二道门禁（可选、不阻断）：微信官方校验器。** `wxart validate` 是 16 条**正则 + 2 条结构检查**，测不了布局；
官方那套（[`wechatjs/verify-article-structure-spec`](https://github.com/wechatjs/verify-article-structure-spec)）
用真实浏览器测量固定宽度、`line-height` 叠字、`height` 溢出、暗色对比度。本机装好后：

```bash
python3 scripts/official_check.py article.html     # 0 通过 / 1 违规 / 2 异常
```

它**不进硬门禁**——依赖 node + Chromium，缺了就明确 SKIP、退出码仍为 0；
要 CI 严格模式加 `--strict`。换主题或骨架后建议跑一次。判据与本手册的对照见
[20-wechat-html-constraints.md](20-wechat-html-constraints.md) 第 17 节。

**「草稿创建成功」不等于排版完成。** 正文仍有 `placeholder` 时，状态必须报「草稿已提交，正文配图未完成」。

## 7. 加背景装饰：`wxart deco`（秀米那种底）

模版本身给的是**版面语法**（字体、间距、编号、卡片），版面之外还有一层**页面质感**：纸纹底、花色边框。这一层在微信里只能靠 `background-image` 做，而它的规矩很硬（实测见 [20-wechat-html-constraints.md](20-wechat-html-constraints.md) 第 3 节）：

- `background-image` 指向**外链 → 整条被删**，`<section>` 还在、声明没了；
- 指向**微信自己的图床链接（`mmbiz.qpic.cn`）→ 连同 `background-repeat` / `background-size` / `background-position` 一起完整保留**。

所以链路必须绕这一圈：**本地画图 → 传进图床换链接 → 写进 `background-image`**。`wxart deco` 把后两步接起来。

```bash
wxart deco article.html -o article-deco.html --skin full            # 纸纹 + 花边框（要上传）
wxart deco article.html -o preview.html  --skin full --no-upload    # 本地看效果，不联网
wxart deco article.html -o out.html --skin paper --accent "#2E7BF6"
```

装饰是两个**正交**的维度，不是一串并列的皮肤名——底子（纸）和花边（框）是两件独立的事：

| 维度 | 取值 | 观感 |
|---|---|---|
| `--texture` 底子 | `dot` / `grid` / `kraft` / `none` | 轻点阵纸 / 方格纸 / 牛皮纸 / 不铺底 |
| `--frame` 花边 | `none` / `single` / `double` | 无框 / 单色带（细线 + 菱形）/ 双色带（粗细两条线 + 大小方块） |

`--skin` 只是两维的常用组合，`--texture` / `--frame` 可以单独覆盖它：

| 皮肤 | 底子 × 花边 |
|---|---|
| `paper` | `dot` × `none` |
| `grid` | `grid` × `none` |
| `kraft` | `kraft` × `none` |
| `frame` | `none` × `single` |
| `double` | `none` × `double` |
| `full`（默认） | `dot` × `single` |
| `graph` | `grid` × `single` |
| `craft` | `kraft` × `double` |

怎么选：**底子与花边都要跟主题性格一致**。冷色主色（靛蓝、石青）配 `grid` 干净利落；
暖色主色（赤红、驼褐）配 `kraft` 更像纸；`double` 比 `single` 重一档，
配 `kraft` / `grid` 这类本身明显的底子才压得住。`dot` + `single` 是最不容易出错的一档。

`kraft` 的底色**以牛皮纸本色（暖黄褐）为主，主色只掺 8%**——牛皮纸的识别特征是「暖」，
早先按主色掺 55% 做，遇到冷色主色整张底就变成灰紫，那是灰纸不是牛皮纸。

要点：

- **主色自动从产物里认**。装饰色跟主题不一致，「好看的底」就变成「第二套配色」。产物里已经渲进了模版的全部色值，取其中出现最多的**彩色**即可——判中性色**只看饱和度**（近白 `#F7EEEE` 饱和度 0.04、近黑 `#111111` 为 0，都会被滤掉）。`--accent` 可显式覆盖。
- **底图只取决于「皮肤 + 主色」，换链结果进缓存**（状态目录的 `deco-cache.json`）。同一套配色的多篇文章复用同一条图床链接，不重复上传。
- **`--no-upload` 只用于本地预览**：底图内联成 `data:` URI，微信不认。要进草稿箱必须去掉它；没有凭证时命令会**失败**，不会悄悄交给一个发不出去的产物。
- **装饰一律加在外层容器上，不动正文内部结构**。内部标题被 `h2-deco` 包在 `display:flex` 行里，事后插东西会插进 flex 行内部把版式搞坏。外层容器是稳定锚点：**不猜结构，只包一层**。
- **没有角标**。四角装饰需要 `position:absolute`，而微信把 `position` 整条删掉——删掉后四张角标会依次堆在正文最前面，比不装饰更糟。四角用 CSS `border-radius`。
- 产物过同一个微信兼容门禁（退出码 5 为未通过，`--no-check` 跳过）。

**装饰不能救版式。** 纸纹和花边是「页面质感」，标题层级、段距、卡片节奏仍然是模版的职责——先把模版选对（第 3 节），再考虑加不加底。

## 8. 排障

按顺序查，不要跳：`wxart doctor`（依赖与配置，退出码 0 才继续）→ `wxart env`（打印实际解析到的路径与来源，确认配置读的是哪一份）→ `{run_dir}/format.log`（模版从哪个文件加载、配色有没有应用、端点/字体告警——**关键信息只在日志里**）→ 再按现象定位：

| 现象 | 原因与处置 |
|---|---|
| 主题没生效，渲染成默认样子 | `default_format_preset` 是**多元素列表**（aws 会报错），或键不存在（wx 静默退回默认）。跑 `--list-themes` 对照真名 |
| aws 组件原样出现在正文里 | 组件名拼错、或缺少结尾 `:::`。渲染器按原文输出并告警，不吞内容——去 stderr 找那一行 |
| `{embed:…}` 原样漏出 | `embeds` 合并结果为空，或占位符名与配置对不上。对不上时排版失败 |
| `validate` 报 `external_link` | 有手改过的 HTML 或外部来源 HTML；wx 正常产物应已把外链转成上标脚注 |
| 粘贴进编辑器后样式掉了 | 把 API 路径的产物直接粘贴了。粘贴路径要用带 `<span leaf="">` 的预览产物 |
| 改了正文但 HTML 没变 | 排的是 `article.md`，而带图内容是 `article-illustrated.md`。有带图副本时优先用它 |
| 暗黑模式反色错乱 / 末尾多一行 AI 声明 | 前者＝主题 YAML 缺 `darkmode` 段（非空才注入 `data-darkmode-*`）；后者＝`aigc_footer` 默认 `true`（合规需要，确实要关就写 `false`） |
| 图片在手机上塌成 0 高 | iOS 微信懒加载（`src` → `data-src`）需要 `width`/`height` 属性。本地能读到原图时脚本会补，缺 Pillow 就不补 |
| `--font-size` 只改了部分文字 | 符合预期：它替换的是主题 `p`/`li` 里的 `font-size`。想例外就单独给那段内联样式 |
