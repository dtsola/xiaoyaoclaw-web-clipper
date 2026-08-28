# xiaoyaoclaw-web-clipper 设计文档

## 定位

六件套第六件——**输入**环节：

> 家（initializer）→ 内容（memory-distill）→ 状态（tracker）→ 知识（kb-retriever）→ 健康（auditor）→ **输入（web-clipper）**

补上五件套缺的「知识喂料」入口：网页 → 干净 Markdown → knowledge/ → 建索引 → AI 可检索。

## 上游

ClawHub `@freedompixels/cn-web-clipper`（MIT-0，965 downloads，7 versions，latest 1.2.7）。

**复用**：readability 提取骨架 + meta 元数据（作者/日期）+ 本地 Markdown 落盘的分层结构。

**上游已知问题（已修复/规避）**：
1. 中文文件名被 `\w`（ASCII）sanitize 删光 → 改为保留中文只去非法字符
2. 飞书保存是 mock（返回假 URL）→ 砍掉，只留本地 Markdown
3. Notion 支持未实现（变量存在函数缺失）→ 砍掉
4. SKILL.md 夹带 AISoBrand 品牌广告 → 去除
5. 宣传「批量 URL」但脚本只收单 URL → 真实现 `--batch`
6. readability 对中文站适配一般 → 加 trafilatura 引擎 + 中文容器选择器

## 架构

```
scripts/
  clip.py       # 主入口：单 URL / 批量 / 去重 / frontmatter / 依赖检查
  extract.py    # 提取模块：双引擎降级链 / 元数据 / 编码处理
```

`extract.py` 可独立运行（`python extract.py <url>` 输出 JSON），便于调试与测试。

## 提取引擎降级链

| 顺序 | 引擎 | 触发条件 | 输出 |
|------|------|----------|------|
| 1 | readability-lxml | 总是先试 | title + HTML + text |
| 2 | trafilatura | readability 质量分 < 200 | text（无 HTML） |
| 3 | bs4 容器选择器 | trafilatura 也失败 | text |

质量分 = 有效文本长度（过滤 <12 字符的短行）。分数 >= 200 判定成功。

**降级链细节**：readability 失败时，trafilatura 若也失败，取两者中分数较高者（若 > 0）作为最后结果；全 0 则报错。

**实测数据**（阮一峰周刊 287 期）：
- readability: score 5339 / text 6393 字符
- trafilatura: score 10206 / text 11333 字符
- 两者都能提取；readability 先命中（分数达标即用，速度优先）

## 中文适配

- **容器选择器**：微信公众号 `#js_content`、知乎 `.RichText`、CSDN `.article-detail`、GitHub `.markdown-body` 等
- **编码**：`resp.encoding` 显式 charset 优先；ISO-8859-1/ascii 时用 `apparent_encoding` 判定（GBK/UTF-8 兼容）
- **文件名**：只去 Windows 非法字符 `\/:*?"<>|` + 控制字符，中文完整保留

## 元数据规则

| 字段 | 来源优先级 |
|------|-----------|
| title | og:title → h1 → <title> |
| author | meta[name=author] → article:author → [rel=author] → .author/.byline 等，清理「作者：」前缀 |
| publish_date | article:published_time → meta[name=publishdate/pubdate] → time[datetime]，截断到秒 |
| description | og:description → meta[name=description]，截断 300 字 |

## 去重

- `.clips-index.json`：`{ md5(url)[:12]: {file, title, clipped_at} }`
- 重复 URL 跳过不重复剪藏；失败（404/超时等）不入索引，批量重试仍会尝试
- 重名文件自动加序号（`_2.md`）

## 反爬策略

- 默认浏览器 UA；**不绕过** 521（CSDN JS 挑战）/ 403（知乎）——如实报告，建议用户换浏览器/换源
- 超时 30s，失败快速失败不重试轰炸

## 知识库闭环（kb-retriever）

1. 默认输出 `~/knowledge/clippings/`（`$CLIPPER_OUTPUT_DIR` 可改）
2. 剪藏后提示（或直接执行）kb-retriever `build_index.py <knowledge根>` 重建索引
3. auditor 的知识库健康检查会覆盖 clippings 目录（未建索引 = 孤儿文件提示）

**实测**：剪藏 407 期 → knowledge/clippings/ → build_index.py → data_structure.md 收录 1 文件 ✅

## 依赖策略

不提供 requirements.txt（指挥官决策，保持轻量）：

| 包 | 级别 | 缺失时 |
|----|------|--------|
| requests / beautifulsoup4 / lxml | 硬依赖 | `--check` 报错提示安装 |
| readability-lxml | 增强 | 降级到 trafilatura/bs4 |
| trafilatura | 增强 | 降级到 bs4 |

**Windows 环境坑（本机实测）**：
- chardet 7.x DLL 加载失败 → 需降级 `chardet<6`（readability 依赖）
- regex 安装损坏（DLL 占用）→ 清理 site-packages 后重装（trafilatura 依赖）

## 测试记录

| 场景 | URL | 结果 |
|------|-----|------|
| 中文博客单剪 | ruanyifeng 周刊 287 | ✅ readability，6393 字，中文文件名保留 |
| 批量 3 条真实 | 周刊 408/409/410 | ✅ 3/3 成功 |
| 去重 | 重复 URL | ✅ 跳过（索引命中） |
| 404 | 不存在的期刊号 | ✅ 失败入汇总，不入索引 |
| 反爬 | CSDN（521）/ 知乎（403） | ✅ 如实报错 |
| 作者清理 | 阮一峰「作者：」前缀 | ✅ 修复后为「阮一峰」 |
| **微信公众号** | WorkBuddy 文章（指挥官提供） | ✅ readability 提取成功，标题/正文/文件名全对；**修复 bug：作者误取 meta[name=author] 宣传语 → 改为公众号优先 #js_name，正确为「腾讯WorkBuddy」**（commit cfa6b57） |
| trafilatura 独立 | 287 期 | ✅ score 10206 |
| 知识库闭环 | 407 期 → build_index | ✅ data_structure.md 收录 |
