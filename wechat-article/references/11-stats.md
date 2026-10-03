# 数据复盘（`wxart stats`）

触发语：看看文章数据 / 文章数据怎么样 / 效果复盘 / 看看表现 / 阅读量怎么样。
需要公众号上下文；通用的「数据分析」不触发。

## 1. 命令与前置

```bash
wxart stats [--days N]      # N 默认 3
```

**前置**：`{home}/config.yaml` 里的微信凭证（`wechat.appid` / `wechat.secret`，等价于
`{home}/.env` 或工作区根 `aws.env` 里的 `WECHAT_1_APPID` / `WECHAT_1_APPSECRET`）。

**没有凭证时明确告知用户**：「数据复盘需要配置公众号 API（`{home}/config.yaml` 或 `.env`），
当前只能基于 `{home}/history.yaml` 已有记录做定性分析」，然后就现有内容能分析多少分析多少。
**不要假装拿到了数据，也不要把估算值写进 `stats` 字段。**

刚发布的文章（不足 24 小时）→ 告知等一天后再看，数据尚未稳定。

## 2. 回填机制（脚本做的部分）

1. 取 `access_token`，然后**从昨天开始往前逐日**调微信数据分析接口
   `/datacube/getarticlesummary`（每日汇总），共 `--days` 天。
2. 返回里没有 `list` 时：`errcode == 61500` **视为该日无数据**（静默返回空）；
   其它 errcode 打 stderr 告警后同样返回空。**空不等于零，不要把它读成「阅读量为 0」。**
3. 逐条匹配 `{home}/history.yaml` 的条目，**按 `media_id` 优先、`title` 回退**。
   匹配不到就跳过，不动任何记录。
4. 命中则覆盖该条目的 `stats` 字段：

| 字段 | 取值 |
|---|---|
| `read_count` | `int_page_read_count` |
| `share_count` | `share_count` |
| `like_count` | `old_like_count + like_count`（**旧赞 + 新增赞**，不是只取 `like_count`） |
| `read_rate` | `round(int_page_read_count / max(target_user, 1) * 100, 1)`，即阅读率百分比 |

`history.yaml` 不存在时打印「No history.yaml found.」；没有可匹配的文章时打印
「No matching articles found in stats data.」——两种情况都要如实汇报，不要包装成「已复盘」。

## 3. `history.yaml` 的条目字段

`wxart run finish` 写入，`stats` 由本节命令回填。规范化形态是
`{"version": 1, "articles": [...]}`；**兼容旧的纯 list 形态**（读取时自动包装，
写回时统一成规范化形态，不要手工改回 list）。

| 字段 | 来源 |
|---|---|
| `run_id` | 任务 id，形如 `20260715-120000-a1b2c3`（历史条目的唯一键，同一任务重复写入会合并而非追加） |
| `date` | 任务创建日期 `YYYY-MM-DD` |
| `title` | `seo.title` > `topic.title` > `未命名文章` |
| `topic_source` | 选题来源（热点 / 搜索 / 用户指定…） |
| `topic_keywords` | 选题关键词列表 |
| `output_file` | 成稿 `article.md` 路径（`--from-wechat` 也靠它定位原稿） |
| `draft_file` / `brief_file` / `review_file` / `sources_file` | 初稿、任务书、审稿报告、来源账本路径 |
| `framework` | 写作框架 |
| `enhance_strategy` | 增强策略 |
| `word_count` | 字数 |
| `media_id` | 发布后的微信 `media_id`（stats 的首选匹配键） |
| `writing_persona` | 本篇人格 |
| `dimensions` | 维度列表 |
| `closing_type` | 结尾类型 |
| `quality_score` | 质量分 |
| `editorial` | 编辑决定与可发布性等审稿结果 |
| `provenance` | `verified_sources` / `unverified_sources` 等来源账 |
| `status` | 任务状态 |
| `stats` | 本命令回填；未回填时为 `null` |

## 4. 复盘怎么做

**读什么**：`{home}/history.yaml` 的全部条目（尤其 `stats` 非空的），需要时对照各任务的
`{run_dir}/review-report.json` 和 `{run_dir}/article.md` 标题。

**比什么**：把有数据的样本按维度分组对比，每组至少 3 篇才动手写结论——

| 维度 | 看什么 |
|---|---|
| 选题来源 `topic_source` | 热点 / 搜索 / 用户指定哪类更吃得开 |
| 框架 `framework` | 观点、清单、故事、测评…哪种在这个号上表现更好 |
| 标题风格 | 数字型 / 悬念型 / 反问型 / 陈述型在 `read_rate` 上的差别（标题影响打开，优先看 `read_rate`） |
| 字数 `word_count` | 长文与短文的分界在哪 |
| 人格 `writing_persona` | 同一账号换人格后数据有没有变化 |

**输出什么**：给出**选题、标题、框架**三类**具体可执行**的调整建议（例如「下个月把清单体
提到每周 2 篇」「标题优先用带具体数字的句式」），并且**每条建议都要指明依据的历史样本**
（`run_id` + 日期 + 具体数字），例如「依据 `20260701-…`（3 篇清单体平均 `read_rate` 18.2% vs
其余 5 篇 9.1%）」。

**不要越权改文件**：本命令只回填 `stats`；`framework`、`title`、`word_count` 等写作字段
由写作阶段通过 `wxart run update --patch` 维护。汇报时区分清楚哪些数字是脚本回填的、
哪些是人工补的。

## 5. 硬规则

- **样本不足时不得宣称结论。** 「人工后续修改率目标逐步降到 15% 以内」这类目标，**没有样本时
  不得宣称已经达标**；同理，只有 1–2 篇数据时只能说「样本太少，先观察」，不能下判断。
- **阅读量受分发影响，不能与文内质量直接画等号。** 粉丝基数、发布时间、平台推荐都会造成差异；
  `read_rate` 比绝对阅读量更接近内容本身的表现，但仍然不能单篇定论。
- 工具分数（`quality_score`）只提示机械语言风险，**不参与数据结论**，也不能用来解释阅读量。
- 数据回填是幂等的：重复跑 `wxart stats` 只会用最新数据覆盖 `stats`，不会追加重复条目；
  但它**不会**凭空补出缺失的历史文章。
- 回填的数据会被选题环节读取（哪种框架/策略表现好会加权到下次推荐），所以**不要把演示数据或
  估算值写进 `stats`**——那会污染下一次的偏好判断。另一条闭环是改稿飞轮，见 [10-learn.md](10-learn.md)。
