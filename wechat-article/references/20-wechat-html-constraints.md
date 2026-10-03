# 微信 HTML 判据：能用什么、什么被删

判据手册。设计版式、写要进正文的 HTML 之前先对一遍。微信官方没有公开白名单，本文以实测为准。

**等级标注**：`实测` = 已进草稿箱回读核对；`没测` = 无实测数据，只作风险提示。

## 1. 铁律：只有内联样式

`<style>` 块、外部 `<link>` 样式表一律被剥离。样式只能写在元素的 `style` 属性里。

| 推论 | 原因 | 后果 |
|---|---|---|
| 没有伪元素 | `::before` / `::after` 需要 CSS 规则 | 标题前的小图标、引用块的大引号，必须**真的插一个元素**进 HTML |
| 没有伪类 | `:hover` / `:first-child` 同理 | 无交互态、无结构性选择器 |
| 没有 `@media` / `@keyframes` | 同上 | 做不了响应式断点、关键帧动画 |

**最关键的一条**：装饰必须作为真实元素插进 HTML。只给标签配内联样式的模版，最多只能改颜色和间距，
永远做不出带角标的标题或带引号的引用块。

## 2. 标签表

可用：`<p>` `<h1>`–`<h6>` `<br>` `<strong>` `<b>` `<em>` `<i>` `<u>` `<ul>` `<ol>` `<li>`
`<a>` `<img>` `<table>` `<tr>` `<th>` `<td>` `<section>` `<span>` 内联 `<svg>`
`<mpvoice>` `<mpvideo>`。

| 标签 | 关键说明 |
|---|---|
| `<img>` | 自动套 `max-width:100%`；**iOS 上须带 `width` / `height` 属性**，否则占位高度算不出来。`style` 里的 `width` 不受影响 |
| `<a>` | 外链会触发安全提示 |
| `<table>` | 可用，也是 flex 不可靠时的降级布局手段 |
| `<section>` `<span>` | 各家编辑器（秀米 / 135）产出的主力容器，保留良好 |
| `<ul>` `<ol>` | 原生列表在粘贴路径不稳，见第 16 节 |

**会被剥离**：`<script>` `<iframe>` `<style>` `<object>` `<embed>` `<form>` `<input>`，
以及 `onclick` 等**一切事件属性**。

## 3. 实测通过清单（11 项）

2026-09-05 探针稿：`draft/add` 上传 → `draft/get` 回读 → 渲染回读到的 HTML。**11 项全部通过，微信一个字节都没删、没改写、没注入 class。**

```
display:flex + gap          inline SVG（circle / text / polygon）
display:inline-block 并排    box-shadow + border-radius
linear-gradient 荧光笔底纹   嵌套三层 <section>
linear-gradient 渐变色条     transform:rotate
<table> 两栏                纯色背景块（对照组）
```

**适用边界**：1) **走 `draft/add`，不经过网页编辑器清洗器**——「flex 不可靠、渐变支持不明」
这类经验来自*在网页编辑器里粘贴*，粘贴清洗器比 API 激进得多；2) **验证环境是 WebKit 桌面浏览器，
不是微信客户端 webview**——客户端仍可能在渲染时忽略个别属性，新版式上线前真机看一眼；
3) 当时 `position` 与 `id` **没测**（若真被删，SVG 内 `url(#…)` 会整个断掉，混测会污染结论）。

## 4. 中文字体指定了也没用

**手机微信里，`font-family` 对中文完全无效。**（2026-09-06 探针稿，iPhone 微信实测）

18 个字体各一行、同一句「永和九年岁在癸丑 Ag123」：

| 环境 | 结果 |
|---|---|
| 桌面浏览器 | 中文差异非常明显——宋体横细竖粗有衬脚、楷体手写体、黑体粗细均匀 |
| iPhone 微信 | **中文一点差异都没有**，只有英文（Georgia / Menlo）看得出区别 |

iOS 系统本身装着 Songti SC 与 Kaiti SC，Safari 里也能渲染。所以不是设备缺字体，
是微信 webview 限制了中文字体。iPhone 上都不行，即全平台不行。推论：

- 中文衬线 / 楷体 / 黑体的字体名写进 `font-family` **纯属废重**。它们会被内联到每一个
  p / h2 / li 上；此前 16 套主题因此多背 9943 字节（占样式总量 16%，个别主题高达 41%）。
  删除后只保留西文与等宽，占比降到 5%。
- **主题的识别特征不能依赖字形。** 必须落在几何特征上——版框、双线、色块、角标、留白节奏。
  剥掉全部字体后两两相似度比对，16 套最高 0.62，无一对撞车。
- **预览必须与手机一致。** 门户预览跑桌面浏览器，衬线会正常显示——那是交付不了的承诺。
  删掉中文字体声明后，预览自动等于微信所得。

**西文有效字体**（实测渲染出真字形）：`Georgia` 让英文变衬线；`Menlo` / `Consolas` 让代码变等宽；
`Didot` / `Baskerville` / `"Snell Roundhand"` / `"Avenir Next"` / `Futura` 全部渲染出真字形，
Didot 可做高对比衬线 masthead。**含数字的字体名必须加引号**（`"Bodoni 72"`），不加引号整条
失效——这是 CSS 语法要求，不是微信限制；回读后引号编码成 `&#39;`，渲染正常。
「`url()` 里引号会被过滤」那条只针对 `background:url()`，与 `font-family` 无关。

## 5. 字重：中文有效，5 个档位

与中文**字体名**完全无效相反，`font-weight` 对中文**有效**——渲染引擎按数值选重/合成，
不需要点名某个字体。（2026-09-06 探针稿，iPhone 微信实测）

| 数值 | 观感 |
|---|---|
| 100 | 极细 |
| 200 ~ 300 | 细 |
| 400 | 常规 |
| 500 ~ 600 | 中粗 |
| 700 ~ 900 | 粗（中文到 700 就到顶，英文还能继续变粗） |

- 关键字 `lighter` / `bolder` 同样生效（实测）。
- `font-variant-numeric: tabular-nums` 也实测有效（等宽数字）。几行数字竖排时，不等宽字形会让
  小数点错位，读者没法竖着比大小——功能性收益，不是装饰。
- **这是字号被基线锁死后唯一还能拉开层级的手段。** 字重差本身就是层级工具：
  「标题 600 / 正文 400」差 200，「标题 800 / 正文 300」差 500，尺寸一个像素都不用动。

两条注意：

- **正文 300 要克制。** 16px 细体在低亮度屏上发虚，只适合本来就走留白路线、且配了收窄行长的
  主题；墨色必须保持近黑（`#1F1F1F` 一带），不能再调浅。
- **`strong` 要跟着正文走。** 正文 300 时 strong 用 600 就够醒目；正文 400 时用 700。
  **差值维持在 300 左右**是「看得见但不吵」的区间。

## 6. 会被删或不可靠的属性

| 属性 | 情况 |
|---|---|
| `position`（absolute / fixed / relative） | **整条被删**。布局只能走文档流，不能做定位叠加 |
| `id` 属性 | **整个删掉**，HTML 与 SVG 内的都删。锚点、SVG 内部引用全部失效 |
| `z-index` | 依赖 position，同样失效 |
| `transform` | `rotate` **实测通过**；iOS 上 SVG 的 `transform-origin` 据资料仍不稳，谨慎使用 |
| `display:flex` | **实测通过**（含 `gap`）。仍建议为老编辑器场景保留 `inline-block` / `<table>` 降级 |
| 渐变 `background` | **实测通过**。荧光笔底纹与渐变色条都正常渲染 |
| 百分比做位移 | 如 `margin-top:-100%` 不可靠 |
| `text-decoration-thickness` | **被删**（2026-09-07 实测）。下划线粗细控不了 |
| `text-underline-offset` | **被删**（同上）。下划线离字底的距离控不了 |
| `calc()` | **含 calc 的整条属性被删**（2026-09-07 实测）。`width:calc(100% + 32px)` 连 `width` 一起没了；`margin:0 0 0 calc(50% - 50vw)` 连 `margin` 一起没了。`100vw` / `vw` 单位本身保留 |
| `<img width="…">` 属性 | **被剥掉**，`height` 属性保留（2026-09-07 回读实测）。微信同时把 `src` 改成 `data-src` 懒加载、`http` 改 `https`、尾缀 `/0` 改 `/640`。style 里的 `width:` 不受影响 |

下划线要控粗细或位置，只能改用 `border-bottom`——它能定粗细与颜色，代价是紧贴内容框底边、
离字底的距离不可调。`text-decoration:underline` 本身可用。

**要冲出边距用固定负值** `margin:0 -16px`，不要用 calc 算。

**单位**：优先 `px`；`vw` / `vh` 可用；**不要用百分比做定位**。

## 7. HTML 活着但手机不渲染

属性原样躺在回读的 HTML 里，手机上没效果。与第 4 节（中文字体）同源的第二类陷阱。

| 手法 | 现象 |
|---|---|
| `filter:grayscale()` / `filter:blur()` | 属性原样在 HTML 里，图片仍是彩色/清晰。**灰度和模糊做不了**，要黑白图就传黑白图 |
| `float:left` | 图在左，但文字不绕图、从图下方开始。**文字绕图做不了** |

「HTML 里活着 ≠ 渲得出来」。第一次证实是中文字体，第二次是这两条。

## 8. 满版贴边做不了

探针 2 · 2026-09-07 手机实测。四种绕开 calc 的写法全部失败，元素都停在文字列宽内：

```
margin:0 -20px + padding:20px + box-sizing:content-box   失败
margin:0 -20px 不给 width（等 auto 拉伸）                  失败
图片当 section 背景 + 负 margin                            失败
img width:120%; max-width:120%                            失败（被微信注入的 max-width:100% 压回）
```

**结论：微信正文有约 20px 的固定边距，块级元素和图片都被限制在这个列宽内，无法贴到屏幕两边。**
calc 被删、vw 被 max-width 压回、负 margin 只平移不拉伸。

| 量 | 值 |
|---|---|
| 正文宽度 | 约 **375px**（手机逻辑像素），所有版式决定都要在这个宽度下成立 |
| 可用满宽 | 约 **335px** |
| 单侧微出血 | `margin-left:-16px` 可把元素拉到距屏约 **4px**（探针 1 截图实测），但到不了边 |

边到边照片在公众号里**不可复制**。

## 9. 行内元素加底色：别用 padding

**padding 会撑高行盒**——带底色的那一行比周围行距明显大，整页出现波浪。
strong 一篇里出现几十次，波浪就是几十道。两个规避写法，都实测可用：

```
半高高亮笔   background:linear-gradient(transparent 58%, #BBD0E4 58%)
满高色块     background:linear-gradient(#E9EFF6, #E9EFF6); box-shadow:0 0 0 3px #E9EFF6
```

渐变是背景、box-shadow 是绘制层，两者都不进盒模型，所以行距不变。

## 10. 核心层的三条约束

正文里**每篇出现几十次**的元素只有三个能加装饰：**加粗、链接、列表符号**。
正文段落本身只能动字号/行高/段距/缩进/对齐（那是排版不是装饰）；标签层不能插子元素，
所以 SVG、角标这类手法在这里一律不可用。

1. **加粗与链接的「手法集合」必须不同。** 两者都用底线时读者分不清哪个能点。
   手法维度：**线 / 底 / 彩字 / 重字 / 字距**。一个用「线」另一个用「彩字」即可。
2. **列表符号不能取 `none`。** 两条列表项在页面上就是两个普通段落，读者认不出是列表。
3. **装饰要「轻但持续」。** 出现几十次的元素，重一点就是灾难——这也是第 9 节为什么要紧。

列表符号的非标准取值（桌面浏览器实测生效）：

```
cjk-ideographic / simp-chinese-informal   一、二、三   中文数字，比 1. 2. 地道
decimal-leading-zero                      01. 02.      编辑部气质
lower-alpha / upper-alpha / lower-roman   a. / A. / i.
hiragana / katakana                       あ、い、
```

**2026-09-07 探针稿实测微信保留**：`cjk-ideographic` / `simp-chinese-informal` /
`decimal-leading-zero` / `lower-alpha` 逐项核对，四个全部原样存回。

## 11. 强调不止「加粗」

中文正统强调手法有两个是加粗之外的，**2026-09-07 探针稿实测微信保留**：

```
text-emphasis:filled circle 色          着重号，逐字加点
text-emphasis-position:under right      点在字下（默认在字上）
letter-spacing:3px; font-weight:500     疏排，把字撑开而不加重
```

- 着重号三种写法（**点 / 实心圆 / 芝麻**）连同 `-webkit-` 前缀和 `position` 全部原样保留。
- 疏排 **2px 偏弱，3px 配 500 字重才明显可辨**。
- 两者都「轻但持续」，正好适合核心层。

核心层可选写法由此扩出一整个维度：加粗 / 变色 / 加线 / 加底之外，
着重号与疏排是第五、第六种，而且是中文特有的。

## 12. SVG 的坑与能力

### 硬坑

- **不能有 `id`**（会被删，导致内部 `url(#…)` 引用全断）
- 不能含 `<style>` `<script>` `<a>`
- `background` 的 `url()` 里**地址不能加引号**，单双引号都会被过滤
- `<image>` 标签的图片**必须是微信素材库地址**，外链和 Base64 都不行
- iOS 上 `transform-origin` 不可靠

### `id` 限制定义了整个设计空间

要 `id` 才能用的东西全部不可用——不是「少一个特性」，是砍掉一整片：

```
不可用  linearGradient / radialGradient      渐变
不可用  pattern                              网点、斜线、纸纹底纹
不可用  clipPath / mask                      文字形状的窗口、图片裁成异形
不可用  filter                               feTurbulence 做真纸纹、模糊、投影
不可用  <use> / marker                       复用图形、箭头端点
```

渐变归 CSS 管——`style` 里的 `linear-gradient` 是活的。SVG 只管 CSS 做不出的那件事：**不规则的形状**。

### 可用元素与属性

```
可用  path / rect / circle / polygon / polyline / line   字面色填充与描边
可用  <text>                                             实测能渲染（编号环、印章里验过）
可用  opacity / fill-opacity / stroke-opacity
可用  stroke-dasharray  ⭐ 画弧、画进度环、画长短不一的断线，全靠它
可用  stroke-linecap / linejoin / transform（iOS 上 transform-origin 不可靠）
```

### 三层用法

| 层 | 例子 | 定位 |
|---|---|---|
| 信息层 | 条形图 · 火花线 · 环形进度 · 对比条 · 评分点阵 | 图形本身承载信息。「45s vs 14s」画成两根不等长的条，读者不用心算。最容易被忽略，价值最大 |
| 结构层 | 时间轴 · 配图四角标 · 流程连接线 | 把元素之间的关系画出来 |
| 装饰层 | 笔锋底线 · 引号 · 落款印章 · 装饰分隔 | 纯装饰。做得再好也只是这一层 |

全部落在「任意形状 + 平涂色」范围内，不需要 `id`。

### SVG 不会跟着文字换行

高度写死的。375px 下 h2 经常折两行，所以：SVG 放在标题上方 / 下方 / 旁边（flex 并排）**可以**，
几行都不影响；**文字压在 SVG 上（负 margin 垫上去）不行**——实测两行时笔刷只盖住第一行，
折角块的第二行直接漏到白底外面。

同一个形状踩过两次：标题装饰第二行漏出；时间轴竖线在步骤文案变长时断成几截。

**需要「有形状又能长高」时拆两段**：SVG 只做固定尺寸的那一截（顶边），会长高的交给 CSS。
实测一行两行都撑得住：

```html
<section>
  <svg height="20">…右上角切一刀的路径…</svg>      固定高度，只管形状
  <section style="background:同色; padding:…">{content}</section>   自动长高
</section>
```

SVG 能做的形状，CSS 一个都做不出来：

```
笔刷底线    两端不齐、中段有粗细变化的手绘线
折角块      右上角切掉一块的底
渐隐色带    linear-gradient 填的 rect（左实右虚）
编号环      描边圆 + 居中的 <text>
角标括号    「」形的两笔
双线        一粗一细、长短不一
```

## 13. 参照手法能力表（25 条 · 2026-09-07 探针稿 · 手机微信实测）

对着两组杂志风参照图（满版照片、文字压图、描边字、竖排、Didot 大字）把用到的手法逐条发进
草稿箱，回读 HTML 比对 + 手机微信逐条看渲染。**HTML 层 25 条只删了 `calc()`**，但手机上又倒了 3 条。

```
文字压在照片上   section 的 background:url(微信CDN) center/cover + 内部文字
                 position 死了但这条活着，杂志风最核心的手法可用
文字叠图底部     <img> 后接 section 用 margin-top:-64px 拉上去
半透明色带压图   同上 + background:rgba(0,0,0,.45)
描边空心字       -webkit-text-stroke:2px #111; color:transparent
竖排             writing-mode:vertical-rl
iOS 西文字体     Didot / Baskerville / "Snell Roundhand" / "Avenir Next" / Futura
渐变填充文字     background:linear-gradient(...) + -webkit-background-clip:text + color:transparent
巨号字 + 紧行距  font-size:96px; line-height:.85 + vertical-align:top; margin-left:-30px
text-shadow      0 2px 8px rgba(0,0,0,.7)，白字压浅图的可读性
object-fit:cover 配固定 height；裁成横条/方块不变形，微信剥掉 width 属性也不影响
mask-image 渐隐  -webkit-mask-image:linear-gradient(#000 45%, transparent)
clip-path        polygon(0 0,100% 0,100% 70%,0 100%)，斜切、异形裁图
圆形裁图         border-radius:50% + object-fit:cover
mix-blend-mode   overlay，能渲染，效果依赖图片明暗，偏弱
其它             overflow:hidden + 固定高 / white-space:nowrap / opacity /
                 aspect-ratio / text-transform:uppercase / letter-spacing:6px 全部正常
```

**HTML 活着、手机不渲染**：见第 7 节。**做不了**：见第 8 节（含任何依赖定位的叠层）。

### 对模版设计的含义

**能做**：嵌套 `<section>` 容器、纯色/边框/圆角/阴影、`inline-block` 并排、居中对齐、
内联 SVG 静态装饰——够做出卡片式标题、编号角标、带框引用、装饰分隔线这类「设计过」的版式。

**做不到**：任何依赖定位的叠层效果、hover 交互、动画、响应式断点。

**关键结论**：没有伪元素，**装饰必须作为真实元素插进 HTML**。模版不能只是「给每个标签配一段
内联样式」——那样永远做不出带角标的标题。模版得能声明**元素模板**（这个标签渲染成什么样的
HTML 结构），而不只是样式串。

## 14. 还没测的

1. `position` / `id` 的实际渲染表现（关系到能否做叠层效果，需单独探针）
2. 嵌套超过三层的 `<section>`
3. 微信客户端 webview 与桌面浏览器的其它渲染差异（中文字体一项已实测，见第 4 节）

**微信偶发清空 `style=""`**：非确定性。同样内容重传通常就好。**不要据此反推某个标签或属性不被支持**——先重传一次再判定。

## 15. validate 规则表

`wxart validate <article.html>` —— 14 条 ERROR + 3 条 WARN。

**ERROR（14 条）**

| 规则名 | 正则语义 | 说明 |
|---|---|---|
| `style_tag` | `<style[\s>]` | `<style>` 会被过滤，样式必须内联 |
| `script_tag` | `<script[\s>]` | 会被过滤 |
| `link_tag` | `<link[\s>]` | 外部 `<link>`（CSS/字体）会被过滤 |
| `div_tag` | `</?div[\s>]` | `<div>` 会被微信编辑器改写，应使用 `<section>` |
| `class_attr` | `<[^>]+\sclass\s*=` | `class` 会被剥离 |
| `id_attr` | `<[^>]+\sid\s*=` | `id` 会被剥离 |
| `position_unsupported` | `position\s*:\s*(fixed\|absolute\|sticky)` | 不生效 |
| `float_css` | `float\s*:\s*(left\|right)` | 布局不可靠，应使用 flex |
| `media_query` | `@media` | 不支持（暗黑模式用 `data-darkmode-*`） |
| `keyframes` | `@keyframes\|animation\s*:` | CSS 动画不支持 |
| `import_css` | `@import` | 不支持 |
| `display_grid` | `display\s*:\s*grid` | 不支持，应使用 flex |
| `css_var` | `var\s*\(\s*--` | CSS 变量不支持，颜色需写实际值 |
| `external_font` | `url\s*\(['\"]?https?://[^)]*\.(?:woff2?\|ttf\|otf\|eot)` | 外部字体文件不会被加载 |

**WARN（3 条）**

| 规则名 | 正则/条件 | 说明 |
|---|---|---|
| `iframe_tag` | `<iframe[\s>]` | 仅白名单来源（腾讯视频等）可用 |
| `external_link` | `<a[^>]+href\s*=\s*["\']https?://(?!mp\.weixin\.qq\.com)` | 未认证号会被过滤（已转脚注的正常产物不触发） |
| `too_many_images` | 结构性检查：`<img>` 计数 > 10 | 超过正文上限 10 张，发布时会移除末尾多余 |

传入完整 HTML 页面时**只校验 `<body>` 内容**——预览包装的 `<head>` / `<style>` 不参与粘贴与发布。

**退出码与门禁**

| 命令 | ERROR 时 |
|---|---|
| `wxart validate <article.html>` | **退出码 1**；无 ERROR 时为 0（WARN 不阻断） |
| `wxart format` / `preview` / `publish` | 都不阻断；`preview` 只把命中项以 `⚠ [LEVEL] rule` 打到 stderr |

**结论：`format` / `preview` / `publish` 都不会自动阻断。门禁必须显式跑 `wxart validate` 并要求退出码 0。**

## 16. 转换器自动修复清单（wx 引擎）

以下限制由转换器自动处理，无需手写：

```
外链被屏蔽            转为上标编号脚注 + 文末参考链接列表
中英文混排无间距      CJK-Latin 边界自动插入空格（U+200A）
加粗后中文标点异常    标点自动移到 </strong> 之外
原生 ul/ol 渲染不稳   转为 <section> + 样式化 bullet / number
暗黑模式颜色反转      注入 data-darkmode-color / data-darkmode-bgcolor 属性
<style> 被剥离        所有 CSS 以内联 style 属性注入
<div> 会被改写        div → section
class / id 残留       全部清除（codehilite、fenced code）
<p> 颜色继承不确定    强制写入 color
代码块缩进丢失        <pre> 补 white-space: pre-wrap; word-wrap: break-word
动图无标识            GIF 上方右对齐加 GIF 小标签（flex 右对齐，不用 absolute）
章节无编号            主题 YAML 设 section_numbering: true 时给每个 H2 前缀两位数编号（01 02）
摘要超字节            digest 截到 ≤120 UTF-8 字节，按 UTF-8 边界截断并补 ...
```

发布前 Metadata 门禁另有一条：`article.yaml` 须含 `title` / `author` / `digest` / `content_source`。
