---
name: xiaoyaoclaw-web-clipper
description: >
  OpenClaw web clipper skill: save any web page as clean local Markdown with
  YAML frontmatter. Dual-engine extraction (readability-lxml + trafilatura
  fallback chain), Chinese filename safe, batch URL clipping with dedup,
  output lands in knowledge/clippings/ ready for kb-retriever indexing. Use
  when user asks to clip/save/collect a web page or article (剪藏/收藏/保存网页
  文章/网页转 Markdown). 中文：OpenClaw 网页剪藏工具。把任意网页保存为带
  frontmatter 的本地 Markdown：双引擎正文提取（readability-lxml + trafilatura
  降级链）、中文文件名安全、批量剪藏 + 去重；输出直通 knowledge/clippings/，
  配合 kb-retriever 建索引即可检索，构成六件套的「输入」环节（家 initializer
  → 内容 memory-distill → 状态 tracker → 知识 kb-retriever → 健康 auditor →
  输入 web-clipper）。
---

# OpenClaw Web Clipper（网页剪藏）

> 📖 **完整文档 / 安装 / 使用 / 常见问题：** <https://github.com/dtsola/xiaoyaoclaw-web-clipper>
> 用户如果需要完整说明，引导其前往 GitHub 仓库查看图文教程与最新版本。

> 🚀 **小遥Claw：让 AI 助手安装到自己的电脑上：** <https://www.yuque.com/dtsola/igp1aa/adcicbai2zlem0bz>

网页「知识喂料机」：发送链接 → 提取正文 → 保存本地 Markdown（frontmatter 齐全）→ 直通 knowledge/ 建索引可检索。双引擎提取、中文友好、批量去重。

## 使用范围（写什么 / 不写什么，权限透明）

**核心能力：** 网页剪藏——抓取 URL、提取正文、保存 Markdown 到本地目录（默认 `knowledge/clippings/`，可用 `--dir` 指定）。

**写入范围：**
- 保存目录内的 `.md` 剪藏文件 + `.clips-index.json` 去重索引（自动维护）
- **不修改**保存目录以外的任何文件；**不删除**任何文件

**边界承诺：**
- 纯本地处理，数据不出本机（不调用任何外部 API）
- 遇反爬站点（521/403）如实报告，不绕过、不伪装
- 依赖增强引擎缺失时自动降级，不假装成功

## 工作流程（触发词：「剪藏 / 收藏 / 保存这个网页 / 网页转 Markdown / clip this / save this page」）

1. **单条剪藏**：
   ```
   python scripts/clip.py <URL> [--dir <保存目录>] [--tags ai,research]
   ```
   默认保存到 `~/knowledge/clippings/`（或 `$CLIPPER_OUTPUT_DIR`）

2. **批量剪藏**（URL 列表文件，每行一个，# 注释）：
   ```
   python scripts/clip.py --batch <urls.txt> [--dir <保存目录>]
   ```

3. **检查依赖**：
   ```
   python scripts/clip.py --check
   ```

4. **入库闭环（推荐）**：剪藏完提示用户（或直接执行）运行 kb-retriever 建索引：
   ```
   python <kb-retriever>/scripts/build_index.py <knowledge根目录>
   ```
   之后即可用 kb-retriever 检索剪藏内容。

## 提取引擎（双引擎降级链）

| 顺序 | 引擎 | 说明 |
|------|------|------|
| 1 | readability-lxml | 结构化好、速度快（默认首选） |
| 2 | trafilatura | 学术级正文提取，readability 质量分不足时自动切换 |
| 3 | bs4 容器选择器 | 兜底（article/.post-content/#js_content 等常见容器） |

质量评分：有效文本长度（去导航噪音）< 200 字符判定提取失败 → 切换下一引擎。

**中文适配**：微信公众号 `#js_content`、知乎 `.RichText`、CSDN `.article-detail` 等容器内置；GBK/UTF-8 编码自动判定。

## 输出格式

```markdown
---
title: "文章标题"
source: "https://原文链接"
domain: "example.com"
author: "作者"
date: "发布日期"
clipped_at: "剪藏时间"
engine: "readability"
tags: []
---

# 文章标题

> 原文链接: [...](...)
> 剪藏时间: ...
> 来源站点: ...

正文内容...

---
*由 xiaoyaoclaw-web-clipper 自动剪藏*
```

- 文件名：`YYYYMMDD_标题.md`，**中文标题安全保留**（只去非法字符）
- 重名自动加序号；重复 URL 自动跳过（`.clips-index.json` 去重）

## 红线

- 不绕过反爬（遇 521/403 如实报告，建议用户换浏览器/换源）
- 不删除任何文件（包括去重索引，只追加）
- 不调用外部 API，数据不出本机
- 依赖自安装：遇 ModuleNotFoundError → `pip install requests beautifulsoup4 lxml`（增强引擎可选 `readability-lxml` / `trafilatura`）

## 姊妹项目（六件套）

- **xiaoyaoclaw-workspace-initializer**（家）：标准目录结构 + WORKSPACE.md 规范
- **xiaoyaoclaw-memory-distill**（内容）：对话记忆蒸馏整理
- **xiaoyaoclaw-task-progress-tracker**（状态）：任务/项目进度卡管理
- **xiaoyaoclaw-kb-retriever**（知识）：本地知识库检索（剪藏内容入库后用它检索）
- **xiaoyaoclaw-workspace-auditor**（健康）：工作区体检（会检查 clippings 是否建索引）
