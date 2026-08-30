---
type: project
status: active
progress: 90
created: 2026-08-28
updated: 2026-08-28
docs:
  - docs/DESIGN.md
---

# xiaoyaoclaw-web-clipper（网页剪藏）

## 目标 / 背景

六件套第六件——**输入**：家（initializer）→ 内容（memory-distill）→ 状态（tracker）→ 知识（kb-retriever）→ 健康（auditor）→ **输入（web-clipper）**。

上游：ClawHub `@freedompixels/cn-web-clipper`（MIT-0，965 downloads，7 versions）——复用其 readability 提取骨架，修复 bug + 增强中文适配 + 闭环 kb-retriever。

核心差异化：双引擎提取（readability-lxml + trafilatura 降级链）、中文站点适配（公众号/知乎/CSDN）、批量 URL + 去重、输出直通 knowledge/ + kb-retriever 建索引闭环。

## 当前状态

全流程完成（90%）：开发 + 测试（含公众号实测 + bug 修复）+ GitHub 发布 + 全局技能同步 + 六件套 README 互链 + **ClawHub v1.0.0 提交 pending-publication（等指挥官确认公开）**。

## 进度日志

- 2026-08-28 17:20：指挥官拍板立项（复用 cn-web-clipper 骨架 + 增强）；已核实上游 MIT-0 license、代码质量（中文文件名 bug / 假飞书 Notion / 广告 / 批量名不副实）
- 2026-08-28 17:13：上游包已拉取研究（tmp/cn-web-clipper-study/，含 clip_webpage.py 7.6KB）
- 2026-08-28 17:24-17:46：核心开发——scripts/extract.py（双引擎降级链 + 元数据 + 编码）+ scripts/clip.py（单/批量/去重/frontmatter/依赖检查）；环境坑：chardet 7.x DLL 崩溃（降级<6）、regex 安装损坏（清理重装）、PowerShell GBK 打印 emoji 失败（stdout reconfigure UTF-8）
- 2026-08-28 17:46-18:15：测试——阮一峰周刊单剪/批量 3 条全成功、去重跳过、404/521/403 如实报错、作者前缀清理、trafilatura 独立验证、knowledge/clippings 闭环建索引（data_structure.md 收录）✅
- 2026-08-28 18:15-18:20：文档——SKILL.md（对齐姊妹项目格式）+ README.md/README.en.md（六件套同构）+ docs/DESIGN.md（引擎降级链/元数据规则/测试记录）+ LICENSE + assets（hero.svg 自绘 + community-qr 复制）；hero.svg 经 Chrome 渲染 + PIL 像素验证 + recognize.ps1 AI 视觉三重校验通过
- 2026-08-28 18:36-18:40：**公众号实测（指挥官提供 WorkBuddy 文章）**——剪藏成功，发现并修复 bug：作者误取 meta[name=author] 宣传语 → 公众号优先 #js_name（正确「腾讯WorkBuddy」，commit cfa6b57）；全局技能同步 MATCH
- 2026-08-28 18:43：**GitHub 发布** dtsola/xiaoyaoclaw-web-clipper（public/main/MIT/8 topics，commit 9dcbb4e）；全局技能同步（SKILL.md + scripts，哈希 MATCH）；六件套 10 个 README 互链 push（initializer c356311 / memory-distill 406239d / tracker 72f8432 / kb-retriever b1b4bc4 / auditor c1d6dbf）
- 2026-08-28 18:43：**ClawHub v1.0.0 提交** pending-publication（versionId k972bvj2yzkga0rcte0s2hfd4s8db4bs，10 文件，等指挥官确认公开）

## 文档索引

| 文档 | 说明 | 更新 |
|------|------|------|
| docs/DESIGN.md | 设计文档（引擎降级链 / 元数据规则 / 测试记录） | 2026-08-28 |
| SKILL.md | 技能主体（触发词 / 工作流程 / 红线） | 2026-08-28 |
| README.md / README.en.md | 中英双语 README（六件套同构） | 2026-08-28 |

<!--
使用说明（agent 维护，用户可忽略）：
- status: active | paused | archived
- progress: 0-100，时刻维护（每次更新进度日志时同步调整）
- 进度日志只追加不删除
- 重要文档：移入 docs/ 或记录路径，追加到 docs 数组（机器可读）+ 本表格（人可读）
- 项目完结：status 改 archived + 关键结论记入 MEMORY.md（供 memory-distill 蒸馏）
-->
