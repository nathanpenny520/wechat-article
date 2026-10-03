# 发布：草稿箱与群发

发布是**唯一不可逆的对外动作**。默认引擎是 **aws**（`wxart publish …`：多账号槽位、封面裁剪框、自动压缩、`publish_method` 抽象）；备选 wx 引擎（`wxart publish --engine wx`）用于单账号快速推草稿。

## 0. 四条前置门禁（缺一不可）

1. **`article.html` 存在，且由当前正文生成**（生成与校验规则见 [05-format.md](05-format.md)）——不是上一版残留。
2. **封面在文章目录根**（`cover.png` / `.jpg` / `.jpeg` / `.webp`），**不在 `imgs/` 里**。
3. **正文与 HTML 都不含 `placeholder`**。
4. **用户已在本轮明确授权**（见第 1 节）。

**`publish_completed` 只在四项全过、且发布命令成功并拿到回执（`media_id` 或 `publish_id`）之后才写 `true`。** 任一不满足 → 只能标记为**「已提交草稿，未闭环」**，**不得**写回 `true`。

`publish.py` **不读、不改** `article.yaml` 的 `publish_completed`——`media_id` / `publish_id` 只打印，写回由你做。**只凭「草稿创建成功」不能宣布全流程完成**；正文仍有 `placeholder` 时必须报「草稿已提交，正文配图未完成」。

## 1. 授权通道与 `publish_method`

```bash
wxart run permission publish allow   # 用户本轮明确要求发布时才执行
wxart run permission publish deny    # 用户撤回时执行
```

**这是唯一的授权通道。** 用户本轮明确说「推到草稿箱 / 发布」时先执行 `allow`。「写一篇」「完整制作」「只要排版」都**不授予**发布权限。`mode=publish` 建任务时会自动置 `permissions.publish=true`；其余情况一律需要显式授权。

**授权缺失只能出本地预览。** 这一点不接受任何「已经做好了所以顺手发一下」的理由。发布还必须同时满足 `flags.skip_publish=false`，且用户本轮没有撤回。

`publish_method` 在 `config.yaml` 顶层：

| 值 | 含义 | `full` 的行为 |
|---|---|---|
| **`draft`**（默认） | 只进**草稿箱** | 创建草稿后**不**调 freepublish |
| **`published`** | 草稿 ＋ 提交发布 | 创建草稿后继续提交发布（异步）；`full --publish` 在 `draft` 下**单次强制**带发布 |
| **`none`** | 用户明确不填微信 | **立即退出**，不调任何微信接口（`--publish` 也被忽略并提示）；其它子命令仍要凭证，照常报错 |

**建议首次运行用 `draft` 确认效果，再切 `published` 真正群发。**

## 2. 元数据：必须用脚本，不许手写

```bash
wxart article-init {run_dir} --title "标题" --author "作者" --digest "摘要" \
                   [--links "名|URL; 名|URL"] [--overwrite]
```

**必须用这个脚本初始化，不要手写。** 手写一定会漏字段——实测三篇连着漏掉 `image_medium`，配图媒介的「平手时避开上一篇」因此永远查不到东西。脚本还会在 `config.yaml` 声明了对应键时补齐预设字段（初始为空列表 `[]`，仅补缺不覆盖）；**`default_format_preset` 与 `default_format_scheme` 即使 config 里没有也照样建**——否则 `format.py` 读不到就静默退回内置默认模版，一篇本该用「资讯」的稿子会长成「亲和」的样子，日志里只有一行「主题来自内置默认」。

`article.yaml` 字段全表：

| 字段 | 说明 |
|---|---|
| `title` | 标题。微信限 **≤ 32 字** |
| `author` | 作者。微信限 **≤ 16 字**。为空时回退 `config.yaml` 的 `default_author` |
| `digest` | 摘要。微信限 **≤ 128 字**（仅单图文）；`converter` 自动生成的摘要按 **120 字节 UTF-8** 截断并补 `...` |
| `cover_image` | 封面路径 |
| `pic_crop_235_1` / `pic_crop_1_1` | 手填的封面裁剪框，`X1_Y1_X2_Y2` 归一化（第 3 节） |
| `content_source` | 原文链接，写入 `content_source_url`。脚本默认写 `article.html` |
| `need_open_comment` | 是否开启评论（0/1）。脚本默认 `1` |
| `only_fans_can_comment` | 是否仅粉丝可评（0/1）。脚本默认 `0` |
| `publish_completed` | 只在第 0 节四项全过并有回执后才写 `true` |
| `image_source` | 只允许 `generated` / `user` |
| `image_medium` | 本篇信息位配图的媒介（白板 / 便签 / 终端等宽…）。见 [06-visual.md](06-visual.md) |
| `user_images_dir` | 用户供图目录，默认 `imgs/` |
| `img_analysis_file` | 用户供图分析文件，默认 `img_analysis.md` |
| 本篇预设单选字段 | `default_structure`、`default_closing_block`、`default_title_style`、`default_format_preset`、`default_format_scheme`、`default_cover_image_style`、`default_sticker_style`——**必须是单元素列表**；`default_article_image_style` 例外，保持多元素候选池 |

`--links "名|URL; 名|URL"` 会生成 `closing.md`（存在时排版自动追加到文末；`closing.md` 自己的首个 `#` 会保留，只有 `article.md` 的首个 `#` 被当作文章标题跳过）。

## 3. 封面裁剪框

微信只收一张封面（`thumb_media_id`），但 `draft/add` 可附带两个裁剪框，分别决定 **2.35:1**（订阅号信息流首图）与 **1:1**（分享卡片、公众号主页、历史列表）怎么裁。**不传时微信自行居中裁切。**

- 取值为相对原图的归一化坐标 **`X1_Y1_X2_Y2`**（0~1，六位小数）。
- 脚本按封面实际尺寸自动算出两个框（**需 Pillow**；未安装则跳过并交给微信默认行为）。
- **`article.yaml` 显式给了就用给的值，不覆盖作者的手动裁剪**——只有两个都手填时才整体跳过自动计算。
- **设计取向：2.35:1 优先**，1:1 作降级视图。所以封面按 2.35:1 构图即可，不必为迁就方形牺牲主视图。
- 裁出区域的宽高比**必须与目标比例一致**，否则接口返回 **53402「封面裁剪失败」**。处置：删掉手填值让脚本自动算，或改对比例。

**⚠️ 关键事实：`draft/get` 不回显 `pic_crop_*`。** 它把值归一化后放进 `cover_info.crop_percent_list`，`ratio` 用下划线写法：

```json
"cover_info": {
  "crop_percent_list": [
    {"ratio": "2.35_1", "x1": "0.001515", "y1": "0", "x2": "0.998485", "y2": "1"},
    {"ratio": "1_1",    "x1": "0.287879", "y1": "0", "x2": "0.712121", "y2": "1"}
  ]
}
```

在 `news_item[0]` 里查 `pic_crop_235_1` 只会拿到 `None`，**别据此误判成「微信忽略了裁剪框」**。校验请读 `cover_info.crop_percent_list`。实测（1584x672 封面）微信原样存下，六位小数完全一致。

## 4. 命令细节

```bash
wxart publish check-screening                  # 校验 config.yaml 的 publish_method
wxart publish check-wechat-env                 # 按 config.yaml 槽位检查 aws.env 凭证是否已填
wxart publish check                            # 环境检查：aws.env、各槽位、依赖、可选探测 token
wxart publish accounts                         # 列出各槽位名称并标记缺项
wxart publish token                            # 获取 access_token（有效期 7200s）
wxart publish upload-thumb IMG                 # 上传封面（永久素材，自动压缩到 10MB 内）
wxart publish upload-content-image IMG         # 上传正文图（自动压缩到 1MB 内），返回 URL
wxart publish create-draft <article.yaml>      # 从 YAML 创建草稿
wxart publish publish <media_id>               # 提交发布（异步）并轮询状态
wxart publish status <publish_id>              # 查询发布结果（JSON）
wxart publish full <article_dir> [--publish] [--account N]
wxart publish recent-articles [-n N]           # 最近已发布文章（默认 5）
wxart getdraft list | get <media_id> | published-list | published-fields | publish-get <id> | article-get <id>
```

- **`full`** 一键全流程：上传封面 → 上传正文图并替换路径 → 建草稿 → 视配置提交发布。`<article_dir>` 需含 `article.yaml` 与 `article.html`。
- **`--account` 是全局选项，必须放在子命令之前**：`wxart publish --account 1 full <dir>`。也可写 `config.yaml` 的 `wechat_publish_slot: <整数>`；**CLI 优先**。
- `getdraft` 与 `publish` **相互独立**，走 `freepublish/*` 接口，用于补齐往期推荐链接。**需要公众号具备对应接口权限**，没权限就直接告诉用户手填。
- `wxart publish --engine wx <md> --cover cover.png --title T [--digest D] [--theme sspai]` 是备选路径：从 Markdown 直接转换并推草稿，单账号、无裁剪框与压缩策略。

**多账号槽位（必须请用户选）**：

```bash
wxart publish accounts   # 例如：您有 2 个账号：1. xiaoming，2. xiaoz
```

**必须请用户选一个，不要替他挑。** 槽位的**数量与名称只来自 `config.yaml`**（`wechat_accounts` ＋ `wechat_{i}_name`）；`aws.env` 里**只有凭证**（`WECHAT_{i}_APPID`、`WECHAT_{i}_APPSECRET`、可选的 `WECHAT_{i}_API_BASE`）。

**⛔ `aws.env` 里没有 `NUMBER_ACCOUNTS` / `WECHAT_N_NAME` 这类键，写了也不会被读。** 目录里某些示例文件仍会列出它们，照着抄不会生效。

## 5. 接口要点与错误码

| 接口 | 方法 路径 | 用途 |
|---|---|---|
| 获取 token | GET `/cgi-bin/token` | `grant_type=client_credential&appid=…&secret=…`，返回 `access_token`（有效期 7200s，需缓存复用，**不落盘**） |
| 上传永久素材 | POST `/cgi-bin/material/add_material?type=image` | 上传封面，字段名 `media`，返回 `media_id`（即 `thumb_media_id`）。**永久素材上限 100,000 张** |
| 上传正文图片 | POST `/cgi-bin/media/uploadimg` | 字段名 `media`，返回可直接在正文使用的 URL；**不占用素材库配额** |
| 新增草稿 | POST `/cgi-bin/draft/add` | 请求体 `{"articles":[{title, author, digest, content, thumb_media_id, content_source_url, need_open_comment, only_fans_can_comment}]}`，返回 `media_id` |
| 发布草稿 | POST `/cgi-bin/freepublish/submit` | 请求体 `{"media_id": …}`，返回 `publish_id`、`msg_data_id`。**异步**：返回成功只表示任务提交成功 |
| 查询发布状态 | POST `/cgi-bin/freepublish/get` | 请求体 `{"publish_id": …}`，返回 `publish_status` |

**常见错误码**：

| 码 | 含义 | 处置 |
|---|---|---|
| 40001 | access_token 无效 | 重新获取 token；核对凭证 |
| 40004 | 不合法的媒体文件类型 | 检查图片格式（支持 bmp / png / jpeg / jpg / gif） |
| 40009 | 图片大小超限 | 封面 ≤ 10MB，正文图 ≤ 1MB |
| 45009 | API 调用超限 | 等待后重试 |
| 45028 | 接口无权限 | 检查公众号类型和权限 |
| 48001 | API 未授权 | 检查公众号开发者设置 |
| 40013 / 40125 / 40164 / 89004 | AppID 不合法 / AppSecret 无效 / 调用方 IP 不在白名单 / 同上 | 脚本对这四个统一提示「多为 AppID/AppSecret 错误或 IP 未加白名单」，检查 `aws.env` 对应槽位 |
| **53402** | 封面裁剪失败 | 手填的 `pic_crop_*` 宽高比与目标比例不一致（第 3 节） |
| **45166** | invalid content | 正文 HTML 仍含 `tempkey` 预览链（见第 6 节） |

**`publish_status` 含义**：`0` 发布成功 / `1` 发布中 / `2` 原创失败 / `3` 常规失败 / `4` 平台审核不通过 / `5` 已删除 / `6` 已封禁。脚本最多轮询 **60 秒**（每 3 秒一次）；仍在进行中会给出稍后查询的命令。

**凭证与权限前置**：需要已认证的服务号或订阅号；AppID / AppSecret 在「开发 → 基本配置」获取；**调用服务器 IP 必须加入白名单**（`token` 报 errcode 多半是这条）。密钥只写在 `~/.wxarticle/.env` 或工作区 `aws.env`，**不写进 `config.yaml`**。

## 6. 正文图片替换与上传压缩

**路径替换机制**：`full` 只上传 `article.html` 中**实际引用**的 `imgs/` 文件（`_content_image_refs_flat` 提取引用名）。每个文件上传后返回 URL，脚本把 HTML 里的 `imgs/文件名` **和**裸 `文件名` 两种写法**都替换**成该 URL。**HTML 引用了不存在的图片会直接报错退出**（`正文引用了不存在的图片: imgs/xxx`）——所以先核对引用，再发布。

**`tempkey=` 检查**：正文里出现 `tempkey=` 或 `tempkey%3D` 时直接报错退出。这种预览链常见于 `getdraft list-fields` 返回的 `url`，`draft/add` 会因此返回 **45166 invalid content**。处置：改用**已群发文章的永久链接**（后台对该文「复制链接」），或从正文去掉相关超链后重试。**正文里挂着未群发文章的链接也会被微信拒。**

**大小上限与压缩策略**（需 Pillow；未安装则跳过压缩并提示 `pip install Pillow`）：

| 目标 | 上限 | 策略 |
|---|---|---|
| 封面（永久素材） | **10MB** | JPEG `quality` 从 **85** 起，每步 **−10**，直到 **20**；仍超限则 `thumbnail(1920, 1920, LANCZOS)` 后按 `quality=60` 存 |
| 正文图 | **1MB** | 同上；仍超限时 `thumbnail(1080, 1080, LANCZOS)` |
| 其它 | 建议 < 5MB | 微信对正文图片来源亦有建议上限 |

- 压缩输出为源图旁的 **`<stem>_compressed.jpg`**。
- **这个文件不会被自动清理**，也**不会被当作正文图上传**（上传的是 HTML 里引用的那个文件名）。要清理自己清。
- 单篇正文图片**最多 10 张**（视频算 1 张），脚本与 `validate` 都会拦。

## 7. 三处回退与超时

| 项 | 回退顺序 |
|---|---|
| **作者名** | 本篇 `article.yaml` 的 `author` → `config.yaml` 的 `default_author` |
| **API 端点** | `aws.env` 的 `WECHAT_{N}_API_BASE` → `config.yaml.wechat_api_base` → 官方 `https://api.weixin.qq.com` |
| **账号槽位** | 命令行 `--account`（**CLI 优先**）→ `config.yaml` 的 `wechat_publish_slot` |

- `base_url` 类配置**须为完整端点路径**（含 `/cgi-bin` 之后的接口路径），脚本据此判断调用模式。
- 自配反代的域名下线时全路径返回 404，而错误信息若只说「网络异常，可稍后重试」会让人一直重试——脚本会带上实际请求的端点并区分「端点配错了」和「网络抖动」。看到「这是自配的反代，不是官方接口——重试不会好转」就去确认地址，或先清空该项改回官方。
- **超时**：`WECHAT_REQUEST_TIMEOUT` 默认 **60** 秒；`WECHAT_UPLOAD_TIMEOUT` 默认 **120** 秒。都写在 `aws.env`。
- **网络类失败自动重试 1 次**：`URLError`、`TimeoutError`、HTTP ≥ 500 时等 1 秒重试一次。仍失败就报错，**不要反复重跑**。

## 8. 发布失败四类

| 类型 | 线索 | 动作 |
|---|---|---|
| **网络类** | 超时、连接失败、5xx | 脚本已自动重试 1 次。仍失败 → 告知「网络不可用，请稍后重试或检查代理」，**不要反复重跑** |
| **凭证/配置类** | token 失败带 errcode、缺字段 | 提示**第几槽位**，检查 APPID / APPSECRET / **IP 白名单**；用户改正后再跑 `full`。**不要静默降级** |
| **封面裁剪 53402** | 「封面裁剪失败」 | 手填的 `pic_crop_*` 宽高比与目标比例不一致。删掉手填值让脚本自动算，或改对比例 |
| **中间产物缺失** | 封面缺失、正文有 `placeholder` | **先补产物再发。** 用户坚持先发草稿 → 必须明确告知「正文配图未完成」，且 `publish_completed` 保持 `false` |

其它会在提交前拦下的情况：`tempkey` 预览链（45166）、正文引用了不存在的图片、图片超过 10 张、`publish_method` 取值非法。

**接口权限不足**（缺 `freepublish` 权限、未认证号等）属于「凭证/配置类」：直接告诉用户手填，不要反复试。

## 9. 贴图 / 小绿书

```bash
wxart image-post p1.jpg p2.jpg -t "标题" [-c "内容"]
```

- `article_type="newspic"`，显示为横向轮播（3:4，类似小红书）。**第一张即封面。**
- **1–20 张**（脚本硬限；实际内容规划按 **≤ 9 张**）。**标题 ≤ 32 字**，`-c` 是纯文本描述、**不带 HTML**、约 ≤ 1000 字。
- 图片先以 `upload_thumb` 上传成永久素材，拿 `media_id` 列表再建草稿。

**贴图制作流程**：规划 → `imgs/outline.md`（每张的用途、配文、文件名、prompt 要点）→ 展示方案**等用户确认**（生图花钱）→ 生成 → 整组审核 → 交付。

- **张数 ≤ 9**（微信限制）。
- **全组统一一个形态**——组图的价值就在整齐，每张换一个等于没有风格。信息型贴图选信息位形态，氛围型选节奏位。
- 风格加载优先级：用户当次指定 → 本篇 `custom_sticker_style` **>** `default_sticker_style`（须为字符串列表；多元素时**先择一并写回本篇为单元素列表**）→ `presets/sticker-styles/` 自定义 → 兜底从正文配图形态池里按主题选一个。
- 贴图类型与典型张数：场景故事 4–6 / 知识卡片 6–9 / 产品展示 3–6 / 节日祝福 1–3 / 投票互动 2–4。
- 整组审核要点：风格统一（色调、构图、字体、留白都是一套）、第一张在缩略图尺寸下仍清晰可辨、**图片比例统一**（混比例在信息流里会显得像凑数）、图序按叙事线读得通、配文与画面**互补**而不是复述、无版权风险元素（真实 logo、名人肖像、他人作品）。

**⛔ 不要在贴图目录上直接跑 `wxart publish full`。** 它硬性要求文章目录下同时有 `article.yaml`、`article.html` 和封面 `cover.*`，一个只有 `imgs/` 和 `outline.md` 的贴图目录跑 `full` **必然报错**——把那个报错当成环境问题排查是白费功夫。两条落地路径：

- **A. 拼成一篇图文发**（能全自动走完）：把 `outline.md` 的配文与图片写成 `article.md`（每张一段 `![形态：画面](imgs/0N.png "配文")`——**配文写在 title 参数里才会出图注**）→ `article-init` 落元数据 → 把第一张（或专门做的一张）作为根目录 `cover.*` → 跑排版 → 再走 `full`。
- **B. 只交付图，用户自己在后台发图片消息**：产出 `imgs/` 整组图 ＋ `outline.md` 里的配文，并明确告诉用户「图片消息要在公众号后台手动发」。**这条路径下不要跑 `publish`，也不要声称发布闭环完成。**

**「九宫格」指一张图内部排成 3×3 网格的构图**（多主题概览，每格一个主题、统一色调），**不是**把九张独立的图拼成一张——**没有拼图脚本**。要九张独立图就是九张，靠 `outline.md` 保证风格与顺序统一。

**只交付图不发布时，不得声称发布闭环完成。**

## 10. 发布后

**换图重发（草稿箱里的图不会自动更新）**：用户说「这篇配图不满意，换成我上传的新图并重新发草稿箱」时——新图放进 `imgs/` 并更新 `img_analysis.md`（仍须「封面仅 1 张」）→ 把 `image_source` 改为 `user` → 按 `img_analysis.md` 重新映射图片到正文对应章节 → **重新跑排版生成整份 `article.html`**（不要只改旧 HTML 的局部）→ 终审确认 `article.md` / `article.html` 里没有 `placeholder` 且引用的图片都存在 → **重新上传并重建草稿**（草稿箱里的旧草稿不会因为本地换图而变）。

**归档**：发布闭环后把本篇目录归档到 `published_root`（以 `config.yaml` 为准）。

## 11. 日志与汇报

**日志**：`{run_dir}/publish.log`。**stdout 与 stderr 一起落盘**：

```bash
wxart publish full {run_dir} > {run_dir}/publish.log 2>&1
```

为什么必须落盘：正文图传成了哪个 URL、压缩到第几档 quality、封面裁剪框算成了什么值——**关键信息只在里面**，屏幕上滚过去就没了。

**向用户汇报**：标题、账号槽位、`media_id`（草稿）或 `publish_id`（发布）、发布状态、是否闭环（`publish_completed` 写了什么、为什么没写）、以及中途发生的任何降级（网络重试、压缩、跳过裁剪框、未走专用 API 等）。

**排障顺序**：`wxart doctor`（依赖、配置、凭证、发布方式）→ `wxart env`（解析到的路径与来源）→ `{run_dir}/publish.log` → 再回本文对应小节。发布失败时退化为本地预览，**不改文章的完成状态**。
