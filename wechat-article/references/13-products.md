# 业务资料库与预设包

触发语：素材库入库 / 上传图到素材库 / 写自家产品介绍 / 保存为产品介绍 / `.aws` / 预设包 /
导入预设 / 主题包 / `aiworkskills.cn` 链接 / `.aws` 下载地址。

两个目录，别混：

| 目录 | 是什么 | 谁写 |
|---|---|---|
| `{home}/products/` | **用户自家业务的事实素材**：产品/服务/品牌介绍、截图、实拍图 | 你（介绍用 Write，图片走脚本） |
| `{home}/presets/` | **模板与风格**：结构、文末区块、标题风格、排版模版×配色、封面/配图/贴图风格、版式组件 | 脚本导入 + 你手改 |

工作区里的 `.aws-article` 是**指向配置目录的软链**（默认就是 `{home}`；建了项目覆盖层
`.wxarticle/` 时指向它），不是第二份数据——**永远不要在 `.aws-article/` 里另存一份再指望它生效**；
用 `{home}/...` 描述，落到磁盘上是同一个位置。

## 一、业务资料库（`{home}/products/{产品名}/`）

```
{home}/products/{产品名}/
├─ 项目介绍.md          # 业务介绍 .md 直挂产品根；命名按行业：产品介绍.md / 服务介绍.md / 品牌介绍.md
├─ (其它业务文档.md)
└─ images/
   ├─ 配置首页.png
   └─ 配置首页.md       # 图片说明，与图片同名
```

### 读：写涉及用户自身业务的内容前必须先查

对外介绍、教程、案例、自家安利、业务配图这类任务，**先 `ls {home}/products/`**，
识别相关产品，读它根下的 `*.md`、查 `images/` 里的同名 `.md`，把已有素材当**底稿与配图候选**，
**优先复用 `images/` 里现成的配图**再考虑新生成。产品名要用户确认，不要拿相似目录顶替。

### 写：两种触发

- **你主动识别**：刚生成/改写的内容明确属于用户自家业务介绍（产品/服务/品牌/项目/团队/业务范围）→
  问用户：「这段是 [产品名] 的业务介绍，要不要保存到产品资料库？下次写涉及业务的文章会自动用上。」
- **用户主动指令**：「保存为产品介绍 / 业务介绍 / 服务介绍 / 入库到产品 / 存到产品资料库」。

保存流程：① `ls {home}/products/` 确认产品名（已有目录提示复用，新产品向用户要名字）；
② 确认文件名，默认 `项目介绍.md`，可按行业改成 `产品介绍.md` / `服务介绍.md` / `品牌介绍.md`；
③ `mkdir -p {home}/products/{产品名}/images/`（即便暂时为空也把骨架建齐）；
④ 用 Write 工具把内容落到 `{home}/products/{产品名}/{文件名}.md`；
⑤ 回报完整路径并说明「下次涉及 [产品名] 的业务内容会自动用上」。

### 什么时候**不要**入库

- 主题是行业资讯、通用教程、与用户业务无关 → 不读也不写。
- 用户明确说内容「还没定型」→ 不主动引导保存。
- 拿不准是不是用户自家业务 → **宁可不提，也不要乱塞**。

`products/` 是底稿来源，塞进去的每一份后续都会被当成**事实**引用；塞错的成本比漏存高。

## 二、业务图入库

```bash
wxart product-image <源图片> --product "产品名" --stem "文件名" [--content "客观描述"]
```

- `--product` / `--stem` **必填**；产品目录与 `images/` 不存在时自动创建；`--repo` 默认当前目录，
  且该目录必须含 `.aws-article` 或 `.git`，否则报错退出（避免写错地方）。
- 允许的扩展名：`png` / `jpg` / `jpeg` / `webp` / `gif`，其它直接报错。
- 重名自动加序号：`配置首页` → `配置首页2` → `配置首页3`…（图片与同名 `.md` 一起判重）。
- **脚本不读图**：读图定中文主文件名、写客观画面描述是**你的活**。入库时带 `--content`；
  不传会写占位句「请根据图片补全（客观描述画面内容即可）。」——这是**预期行为，不是脚本故障**，
  要么入库时带上，要么入库后编辑同名 `.md` 替换占位段。
- 产出：`{home}/products/{产品名}/images/{stem}.{ext}` + 同名 `.md`，固定两行格式：

```markdown
**图片路径**：`.aws-article/products/产品名/images/配置首页.png`

**图片描述**：……
```

## 三、`.aws` 预设包导入

```bash
wxart presets <bundle.aws|https://aiworkskills.cn/**/*.aws> [--dry-run]
```

扩展名 `.aws`，**实质是 ZIP**。包根应含与预设库一致的目录（可以多出别的文件，脚本只处理白名单）：
`closing-blocks` / `cover-styles` / `formatting` / `image-styles` / `sticker-styles` / `structures` /
`title-styles`，另可有根级 `config.yaml`。包根解析：有 `presets/<名>/` 优先用它；
整包多套一层 `<名>/<名>/` 会自动以内层为合并根。

### 三条必须先知道的语义

1. **七个预设目录是替换式合并**：包内**有**该子目录 → **先清空本地同名目录**再写入包内内容
   （旧包里被删掉的文件不会残留）；包内**没有** → 本地对应目录**保持不动**，不受本次导入影响。
   不在白名单的目录会被跳过并打日志 `【跳过】…不在预设白名单`。
2. **`config.yaml` 不覆盖**：本地没有 → 从包内复制；本地已有 → 只按包内字段与本地同名键**递归比对**，
   差异以 **JSON 数组**打到 **stdout**（每条 `{"key": "点分路径", "old": …, "new": …}`），
   说明日志走 stderr。**拿到差异必须问过用户再手改配置**，绝不自动写。
3. **密钥会进 `aws.env`**：按映射表增量写入工作区根 `aws.env`：

   | 包内 `config.yaml` 字段 | `aws.env` 键 |
   |---|---|
   | `wechat_appid` | `WECHAT_1_APPID` |
   | `wechat_appsecret` | `WECHAT_1_APPSECRET` |
   | `writing_model.api_key` | `WRITING_MODEL_API_KEY` |
   | `image_model.api_key` | `IMAGE_MODEL_API_KEY` |

  策略：包内字段为空 → **不动**现有键；无该键 → 追加；值相同 → 跳过；**值不同 → 先备份
  `aws.env.bak.<时间戳>` 再覆盖**。日志**只打印键名，不打印密钥值**，并保留原文件的顺序、
  空行与注释。当前导出只支持单微信账号，固定槽位 1，`WECHAT_2_*` 等键不受影响。
  **确认新配置可用后应删掉备份文件**——里面是明文密钥，留着就是多一份泄露面。

### 安全边界

- **URL 白名单**：必须 `https://`；host 为 `aiworkskills.cn` **或其子域**；路径以 `.aws` 结尾；
  下载内容必须是有效 ZIP。任一不满足 → **直接报错退出，不写任何文件**。
- URL 模式下载缓存落 `.aws-article/downloads/<原文件名>`（不受 tmp 清空影响，留作事后核对）。
- **ZIP slip 防御**：逐项校验成员路径，拒绝绝对路径、含 `..` 段、或解析后指向解压目录外的路径，
  任一违反立即退出且**不写入任何文件**。
- 解压目录固定 `.aws-article/tmp/`，**每次执行前整目录删除再重建**，合并完成后**保留**供核对，
  下次导入再清空。
- 所有写入限制在工作区配置目录（即 `{home}`）内；`--dry-run` 下不写 `presets/` 与 `config.yaml`，
  但 **URL 模式仍会实际下载**以便校验 ZIP 结构。

导入后先核对 `.aws-article/tmp/` 里的包内容，再按第 4 节字段检查落地的预设。

## 四、七类预设的文件形式与字段

文件名（不含后缀）即预设名。`config.yaml` 的 `custom_*` 非空时覆盖同名 `default_*`，
本篇 `article.yaml` 再覆盖两者；**多候选进入写作/排版前必须在本篇收敛成单元素列表**。

| 目录 | 文件形式 | 关键字段 / 结构 |
|---|---|---|
| `structures/` | Markdown | 必有 `## 标准结构`（代码块画结构树：标题、摘要、开头类型、正文小标题与段落节奏、结尾类型、配图密度建议）与 `## 要求`（如小标题 ≤15 字、每段 3–5 行、核心观点放段首）。config 键 `default_structure` / `custom_structure` |
| `closing-blocks/` | 一段 Markdown | 文末固定引导区块：关注引导、公众号名片、往期推荐、行动号召。可用四种嵌入标记：`{embed:profile:名称}`、`{embed:miniprogram:名称}`、`{embed:miniprogram_card:名称}`、`{embed:link:名称}`。名片与小程序以 `config.yaml` 的 `embeds` 为准；**只有往期链接**可在本篇 `article.yaml` 写 `embeds.related_articles` 与全局合并 |
| `title-styles/` | Markdown，五节 | `## 特点`、`## 核心技巧`、`## 适用场景`、`## 示例句式`（可含 XX、N 占位符）、`## 注意事项`。内置五型：悬念型、干货型、数字型、反问型、故事型 |
| `formatting/` | YAML | 模版×配色两层。字段：`name`、`displayName`、`skeleton`（骨架名）、`sort_order`、`description`、`when_to_use`、`when_not_to_use`、`variables`（`primary-color` / `text-color` / `text-muted` / `secondary-color`）、`default_scheme`、`schemes[]`（每档 `name` + `variables` + `description`）、`styles{}`（`p` / `strong` / `em` / `a` / `h1` / `h2` / `h3` / `ul` / `ol` / `li` / `blockquote` / `figcaption` / `img` / `code` / `pre` / `table` / `th` / `td` / `hr`）。内置 8 模版（手账/技术/活力/硬朗/书卷/亲和/杂志/资讯），每套 3 档配色；样式里用 `{primary-color}`、`{primary-ink}`、`{text-color}`、`{text-muted}` 占位 |
| `cover-styles/` | Markdown，五字段 | `## 用于`、`## 主体`、`## 影调`、`## 文案`（**不可缺省**）、`## 版式`，加 `## 可轮换维度`。封面 2.35:1（信息流缩略图仅 345×147px，元素 ≤3，不重复标题），主体自明就别加字。封面风格目录与正文配图目录**分开管理** |
| `image-styles/` | Markdown，五字段 | 同上五字段 + `## 可轮换维度`；**信息位**模板另有 `## 媒介`（流程步骤 / 结构分层 / 数据图表 / 对比两栏 / 清单要点必须有真实内容；概念隐喻 / 场景还原 / 金句卡片是节奏位）。正文图 16:9、宽 1080px，信息密度可以高 |
| `sticker-styles/` | Markdown，三节 | `## 画面调性`、`## 张数`（按 `config.yaml` 的 `multi_image_count`，默认 6）、`## 配文`（每张一句短文案，可悬念递进或并列要点） |

`formatting` 的模版与配色也可以直接用 `wxart format --engine aws --list-themes` 查看，见 [05-format.md](05-format.md)；
封面/配图的用法见 [06-visual.md](06-visual.md)。

## 五、自定义审稿规则与版式组件

- **审稿规则** `{home}/presets/review-rules.yaml`：

  ```yaml
  custom_rules:
    - name: 品牌名称规范
      check: 正文中「XX公司」必须使用全称，不能简写
      level: 必须        # 必须 / 建议
  ```

  审稿时**追加在标准检查项之后**执行；`level: 必须` 记为 🔴 阻断项，`level: 建议` 记为 🟡 提示。
  这是用户自己写的业务规则，见 [04-review.md](04-review.md)。

- **版式组件** `{home}/presets/components/`：排版引擎的版式骨架组件，**不由 `.aws` 包管理**——
  组件绑骨架、随模版走，不单独下发；而且它是本地定制，不该被别人的包覆盖。放同名文件即可覆盖内置组件。

## 六、备份

`{home}/products/`（事实素材）与 `{home}/presets/`（模板风格）默认都不进 git。要备份就整目录打包：

```bash
tar czf wxarticle-backup-$(date +%Y%m%d).tgz \
  -C ~/.wxarticle products presets style.yaml history.yaml playbook.md
```

包含 `.env` 的备份是**明文密钥**，单独加密保管或干脆不打包它。工作区的 `.aws-article` 是软链，
**不要**把它一起打包（会打成链接本身或重复一份），要恢复就在新工作区重跑 `wxart init` 重建软链。
