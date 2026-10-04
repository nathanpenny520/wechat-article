# 微信服务端 API 速查（本流水线真正用到的那部分）

这份是**我们自己写的摘要**，只覆盖本 skill 依赖的接口与限制。它不是官方文档的替代：
字段级细节、完整错误码、各账号类型的权限差异都要以官方原文为准。

- 官方入口：<https://developers.weixin.qq.com/doc/subscription/api/>
- **离线全文镜像**：`wxart docs fetch`（抓 191 页到状态目录，**不进本仓库**——内容版权归腾讯）。
  之后 `wxart docs search <正则>` / `wxart docs show <路径>` 可离线查。
- 下面每条都标了官方页面路径，镜像抓过之后可以直接 `wxart docs show` 打开。

## 0. 为什么需要这一层

`references/20-wechat-html-constraints.md` 记的是**渲染层**的行为（微信保留哪些 CSS）。
这份记的是**接口层**的规定（字段上限、必经流程、错误码）。两者都实测过一部分，
但实测只能覆盖试过的情形；规定是写死的、可以照抄。先查规定，再决定要不要探。

## 1. 草稿箱（本流水线的落点）

官方页面：`subscription/api/draftbox/draftmanage/`

| 接口 | 路径 | 用途 |
|---|---|---|
| 新增草稿 | `POST /cgi-bin/draft/add` | `wxart publish full` 走这个 |
| 更新草稿 | `POST /cgi-bin/draft/update` | `wxart redraft` 走这个，**原地替换不新建** |
| 获取草稿详情 | `POST /cgi-bin/draft/get` | 回读核对（写成功 ≠ 写对条目） |
| 获取草稿列表 | `POST /cgi-bin/draft/batchget` | 每页最多 20 条 |
| 删除草稿 | `POST /cgi-bin/draft/delete` | 探针稿清理 |
| 草稿总数 | `POST /cgi-bin/draft/count` | — |
| 草稿箱开关 | `POST /cgi-bin/draft/switch` | — |

`draft/update` 的请求体是 `{media_id, index, articles}`：`index` 是**多图文里的第几篇**（第一篇为 0）。

## 2. `content` 字段的硬限制（最常踩）

| 限制 | 值 |
|---|---|
| 字符数 | **少于 2 万字符** |
| 体积 | **小于 1M** |
| 脚本 | **会去除 JS** |
| 图片 | **必须来自「上传图文消息内的图片获取 URL」接口；外部图片 URL 将被过滤** |
| 图片消息（newspic） | 仅纯文本 + 部分特殊标签，商品数 ≤ 50 |

**第 4 条是这套流水线最关键的一条规定**，也是「为什么背景装饰要绕一圈」的官方依据：
正文里的图片与 `background-image` 都必须先经上传换成 `mmbiz.qpic.cn` 链接。
`references/20-wechat-html-constraints.md` 第 3 节有对应的实测结论。

**2 万字符这条要盯着。** 一篇 1800 字的稿子排完版大约 2 万字符上下——加上装饰底图与
正文图的 `data:`/`mmbiz` 链接后很容易顶到线。所以 `wxart deco` 默认走图床换链而不是内联
（内联的 base64 会直接把体积顶爆），`--no-upload` 只用于本地预览。

## 3. 图片上传的两个接口（别混）

| 接口 | 路径 | 用在哪 | 上限 |
|---|---|---|---|
| 上传图文消息内的图片获取 URL | `POST /cgi-bin/media/uploadimg` | **正文图**、`background-image` 底图 | 1MB |
| 上传永久素材 | `POST /cgi-bin/material/add_material?type=image` | **封面**（要 `media_id`） | 10MB |

正文图拿回来的是**URL**，封面拿回来的是**`media_id`**。混用会失败：
正文里写 `media_id` 解析不出图，封面填 URL 则草稿创建报错。

## 4. access_token

- `POST /cgi-bin/token`，**有效期 7200 秒**。多进程同时刷新会让旧 token 失效——
  所以本流水线的 token 获取集中在发布链路里，不做并发刷新。
- 有稳定版凭据接口（`/cgi-bin/stable_token`），但本流水线用普通版即可。
- **IP 白名单**：调用方 IP 必须在公众号后台白名单里，否则报 **40164**。

## 5. 常见错误码（本流水线遇到过的）

| 码 | 含义 | 处置 |
|---|---|---|
| `40164` | 调用方 IP 不在白名单 | 去公众号后台加 IP；这是**配置问题**，重试无用 |
| `40001` | access_token 无效 | 重新取 token |
| `45009` | 接口调用频率超限 | 退避重试 |
| `45166` | `content` 非法 | **最常见的成因**：正文里还有预览链（含 `tempkey=`）。改用永久链接，或去掉那几条超链。`publish.py` 对此有专门的检查与提示 |
| `53402` | 素材类型/尺寸不符 | 检查是正文图（1MB）还是封面（10MB） |
| `41001` | 缺少 access_token 参数 | — |
| `48001` | 接口未授权 | 账号主体类型不支持该接口（如未认证订阅号缺部分权限） |

## 6. 发布与群发（本流水线默认不碰）

- `publish_method: draft`（默认）只创建草稿；`published` 才会走 `POST /cgi-bin/freepublish/submit`。
- **发布是不可逆的对外动作**，授权规则见 [07-publish.md](07-publish.md) 第 1 节。
- `freepublish/*` 系列接口需要账号具备相应权限；没权限时不要绕，直接告诉用户手填。

## 7. 与渲染层的分界

| 问题 | 看哪份 |
|---|---|
| 这个 CSS 微信保不保留 | [20-wechat-html-constraints.md](20-wechat-html-constraints.md) |
| 正文能多长、图片怎么传、报错什么意思 | 本文 |
| 字段级细节、权限集 id、云调用 | `wxart docs show <路径>` 看官方原文 |
