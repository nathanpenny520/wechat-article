# 安装、自检与首次配置

## 1. 环境要求

| 项 | 要求 | 说明 |
|---|---|---|
| Python | **3.11+**（3.10 起部分能力可用） | wx 引擎要求 3.11+；aws 引擎要求 3.10+ |
| PyYAML | **必需** | 读主题、人格、配置、预设 |
| markdown / beautifulsoup4 / cssutils / Pygments | 排版必需 | wx 引擎的转换器依赖 |
| requests | 抓取、发布必需 | wx 引擎 |
| Pillow | **可选** | 图片压缩、按比例裁切、封面裁剪框、出图后检查、`<img>` 补尺寸。缺了会跳过这几步，不阻断排版与发布 |
| 微信凭证 | 仅发布需要 | 写作、排版、配图都不需要 |
| 写作 / 画图模型 API Key | 可选 | 不配时由当前 Agent 直接写、直接画；配了走你指定的模型 |

依赖不装也能用纯提示词流程，但 `wxart format`、`wxart publish`、`wxart image`、`wxart score`
这些确定性命令会不可用。

## 2. 安装

```bash
cd <本 skill 目录>
bash install.sh
```

`install.sh` 做三件事：

1. 在状态目录建受管 venv（`~/.wxarticle/venv`）并安装 `scripts/requirements.txt`；
2. 把本 skill 链接到 `~/.claude/skills/`、`~/.agents/skills/`（存在 `~/.codex`、`~/.openclaw` 时一并链接）；
3. 跑一次 `wxart init`（配置模板、预设库、工作区兼容软链）。

不想用脚本就手动：

```bash
# 1) 建受管 venv
python3 -m venv ~/.wxarticle/venv
~/.wxarticle/venv/bin/python -m pip install -r scripts/requirements.txt

# 2) 初始化状态目录与配置模板
python3 scripts/wxart.py init --no-venv

# 3) 链接到 agent 的 skills 目录（按你用的 agent 选一行）
ln -sfn "$PWD" ~/.claude/skills/wechat-article
ln -sfn "$PWD" ~/.agents/skills/wechat-article
ln -sfn "$PWD" ~/.codex/skills/wechat-article
```

**Windows**：用 `py -3 -X utf8`，不要用 `python3`——没装 Python 时它是系统预置的应用执行别名，
会静默打开 Microsoft Store 而不报错。链接那步改用目录联接或直接复制目录。

**命令前缀**：本文档里 `wxart` 等价于 `python3 {skill_dir}/scripts/wxart.py`。
`install.sh` 会把 `wxart` 包装脚本放进 `~/.local/bin/`（若该目录不在 PATH，用它输出里的提示加一下）。

## 3. 自检

```bash
wxart doctor          # 人类可读
wxart doctor --json   # 结构化（Agent 用）
wxart env             # 只打印解析后的路径与来源
```

`doctor` 检查八类，退出码 **0 = 可继续，1 = 有阻塞问题**：

| 检查项 | 阻塞 | 说明 |
|---|---|---|
| `python` | 是 | 低于 3.11 会报错（wx 引擎要求） |
| `deps` | 是 | 缺 markdown/bs4/cssutils/requests/yaml/pygments；用 `wxart` 启动会自动切到受管 venv |
| `config` | 否 | 没有 `config.yaml` 只提示，`wxart init` 生成模板 |
| `config.article_category` / `target_reader` / `default_author` | 否 | 空只提示；填了写作与审稿才有硬约束 |
| `config.wechat.author` | 否 | 空则用默认署名 |
| `wechat.credentials` | 否 | **仅发布需要**；写作/排版/配图不受影响 |
| `models.writing` / `models.image` | 否 | 不配不阻断，由当前 Agent 代写/代画 |
| `state_home` / `workspace.aws_link` / `publish_method` | 否 | 缺失提示 `wxart init`；`publish_method` 非法值报错 |

**关键纪律**：`doctor` 退出码 1 时本轮只谈环境修复，不要接着写稿。
缺 `style.yaml` 是**正常首次状态**，不是错误。

## 4. 首次配置

```bash
wxart init
```

它建出：

```
~/.wxarticle/
├── config.yaml      # 账号配置模板（含逐行注释）
├── .env             # 密钥模板（写进 git 会出事）
├── presets/         # 预设库：structures / closing-blocks / title-styles /
│                    # formatting（8 模版 × 3 配色）/ cover-styles /
│                    # image-styles / sticker-styles / components
├── runs/  exemplars/  corpus/  lessons/  themes/  personas/  output/
└── venv/            # 受管解释器（如已建）
```

并在工作区根建一个 `.aws-article` **软链**指向上面这个目录。它的存在只有一个原因：
让 vendored 的上游引擎零改动地读到同一份配置。**你不需要在 `.aws-article/` 里放任何东西**，
它始终是 `~/.wxarticle/` 的别名。

要一个仓库对应一个公众号时，才在工作区建真实的 `.wxarticle/` 目录作为项目覆盖层；
此时 `.aws-article` 指向它，配置优先级变成「项目 > 用户」：

```
wxart env   # config_dir 一行会告诉你当前生效的是哪一份
```

### 4.1 必填三项

打开 `~/.wxarticle/config.yaml`，填满：

```yaml
article_category: ""   # 你的账号写什么领域
target_reader: ""      # 写给谁看
default_author: ""     # 默认署名
```

这三项直接约束写作与审稿。**不要从历史草稿或对话记忆里反推着填**——问用户，得到当轮答复再写。

### 4.2 密钥

只写 `~/.wxarticle/.env`（或工作区根的 `aws.env`）：

```
WRITING_MODEL_API_KEY=      # 写稿模型（可选）
IMAGE_MODEL_API_KEY=        # 画图模型（可选；很多 coding plan 不支持生图）
WECHAT_1_APPID=             # 公众号，仅发布需要
WECHAT_1_APPSECRET=
```

**不要向用户索取密钥，也不要代替用户把密钥粘进文件**——只校验键是否存在、是否非空，不读值、不外发值。

### 4.3 模型端点

可选。`config.yaml` 里两组：

```yaml
writing_model:   { base_url: "", model: "", provider: "" }   # openai | volcengine | qwen | gemini
image_model:     { base_url: "", model: "", provider: "" }
```

`provider` 留空时按 `base_url` 自动识别；识别不出会要求你显式填。

### 4.4 发布方式

```yaml
publish_method: draft     # draft=只写草稿箱（默认）/ published=提交发布 / none=不接微信
wechat_publish_slot: 1    # 多账号时本篇默认槽位
```

默认必须是 `draft`。用户明确说「不接微信」才设 `none`（此时发布命令直接跳过）。

## 5. 配置文件的分工（不要混用）

| 文件 | 位置 | 放什么 |
|---|---|---|
| `config.yaml` | `~/.wxarticle/`（工作区可覆盖） | 账号定位、文风、模型端点、发布方式、预设候选 |
| `.env` 或 `aws.env` | `~/.wxarticle/` 或工作区根 | **只放密钥** |
| `article.yaml` | 本篇任务目录 | 本篇标题/摘要/封面/裁剪框/发布状态/本篇预设单选 |
| `style.yaml` | `~/.wxarticle/` | 写作风格：人格、语气、字数、黑名单、主题偏好 |
| `playbook.md` | `~/.wxarticle/` | 学习到的写作规则（写作前必须重新 summarize） |

优先级：

```
用户当次说法 > 本篇 article.yaml > config.yaml 的 custom_* > config.yaml 的 default_* > 内置默认
```

## 6. 换风格与换主题

```bash
wxart themes      # 列出 wx 引擎的 18 套主题
wxart gallery     # 浏览器里并排预览 + 一键复制
wxart format --engine aws --list-themes    # 列出 aws 引擎的 8 套模版与各自 3 档配色
wxart format --engine aws --preview        # 生成模版对照页
```

- 换主题：改 `config.yaml` 的 `theme`，或排版时传 `-t <主题名>`。
- 换写作人格：改 `config.yaml` 的 `writing_persona`。7 个人格见 [03-write.md](03-write.md)。
- 学一套新排版主题：`wxart learn-theme <公众号文章URL> --name <名字>`，见 [10-learn.md](10-learn.md)。
- 重设整套风格：说「重新设置风格」，走 onboard 流程，见 [10-learn.md](10-learn.md)。

## 7. 迁移旧状态

```bash
wxart migrate --dry-run   # 预演
wxart migrate             # 从 ~/.wewrite 复制到 ~/.wxarticle（只复制，不覆盖已有文件，不删除源）
```

- 旧 `~/.wewrite/` → `~/.wxarticle/`（配置、风格、历史、学习产物、输出）。
- 工作区已有的真实 `.aws-article/` → **原样沿用，不做改动**；想收敛到状态目录就把它复制进
  `~/.wxarticle/` 后删掉该目录，再跑 `wxart init`。

## 8. 依赖缺失时的降级行为

| 缺什么 | 会怎样 | 怎么办 |
|---|---|---|
| `markdown`/`bs4`/`cssutils`/`pygments` | `wxart format` / `preview` / `validate` 不可用 | `wxart init` 或 `pip3 install -r scripts/requirements.txt` |
| `PyYAML` | 全部引擎不可用 | 同上（唯一必需项） |
| `requests` | 抓热点/搜索/SEO/发布不可用 | 同上 |
| `Pillow` | 跳过图片压缩、比例裁切、封面裁剪框、出图检查 | 可选；但大图上传会被微信拒（`40009`） |
| 写作模型未配 | `wxart draft draft` 退出码 2；`llm-write` 退出码 3 | 由当前 Agent 直接写，流程照走 |
| 画图模型未配 | `wxart image generate` 退出码 2 | 降级为只交付图片提示词 |
| 微信凭证未配 | 发布不可用 | 只出本地预览 |

**退出码语义要分清**：`wxart image` 的退出码 1 是硬错误（含**跑错目录**，找不到配置文件），
退出码 2 才是「图片模型未配置」。不要把 1 当成 2 去降级。

## 8.5 可选：把官方文档抓一份到本地

接口的字段上限、错误码这类规定，以前靠探针一条条试——试出来的只覆盖试过的那些。
抓一份官方文档到本地，就能先查规定再决定要不要探：

```bash
wxart docs fetch                    # 抓 191 页到状态目录，约 1 分钟（可反复跑续抓）
wxart docs search "2万字符"          # 正则检索
wxart docs show subscription/api/draftbox/draftmanage/api_draft_add
```

- **装不上也无所谓**：仓库里的 [22-wechat-api-reference.md](22-wechat-api-reference.md)
  是我们自己写的摘要，覆盖本流水线真正依赖的那几条规定，离线可用。
- **镜像不进版本库**：文档内容版权归腾讯，所以它落在 `$WXARTICLE_HOME/wechat-docs/`，
  由使用者本地抓取。仓库里只有抓取脚本。
- 抓取需要能访问 `developers.weixin.qq.com`；抓不到时只影响离线检索，不影响写作与发布。

## 9. 排障顺序

1. `wxart doctor` —— 依赖 / 配置 / 凭证 / 发布方式。
2. `wxart env` —— 每一份实际读到的文件路径（配置读错地方一眼可见）。
3. 本篇任务目录下的 `<环节>.log`（`format.log`、`image-generation.log`、`cover-generation.log`、`publish.log`）。
4. 再读对应的阶段文档。
