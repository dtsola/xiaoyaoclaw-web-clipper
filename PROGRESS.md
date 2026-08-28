---
type: project
status: active
progress: 70
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

开发 + 测试完成（70%）：核心脚本双引擎 + 批量去重 + frontmatter，真实 URL 全链路测试通过（中文博客/批量/去重/404/反爬/知识库闭环），SKILL.md + README 中英 + DESIGN + LICENSE + hero.svg（视觉验证通过）+ community-qr 全部就绪。

下一步：git init + GitHub 建仓发布 → 全局技能同步 → 六件套 README 互链 → ClawHub 提交（等指挥官确认公开）。

## 进度日志

- 2026-08-28 17:20：指挥官拍板立项（复用 cn-web-clipper 骨架 + 增强）；已核实上游 MIT-0 license、代码质量（中文文件名 bug / 假飞书 Notion / 广告 / 批量名不副实）
- 2026-08-28 17:13：上游包已拉取研究（tmp/cn-web-clipper-study/，含 clip_webpage.py 7.6KB）
- 2026-08-28 17:24-17:46：核心开发——scripts/extract.py（双引擎降级链 + 元数据 + 编码）+ scripts/clip.py（单/批量/去重/frontmatter/依赖检查）；环境坑：chardet 7.x DLL 崩溃（降级<6）、regex 安装损坏（清理重装）、PowerShell GBK 打印 emoji 失败（stdout reconfigure UTF-8）
- 2026-08-28 17:46-18:15：测试——阮一峰周刊单剪/批量 3 条全成功、去重跳过、404/521/403 如实报错、作者前缀清理、trafilatura 独立验证、knowledge/clippings 闭环建索引（data_structure.md 收录）✅
- 2026-08-28 18:15-18:20：文档——SKILL.md（对齐姊妹项目格式）+ README.md/README.en.md（六件套同构）+ docs/DESIGN.md（引擎降级链/元数据规则/测试记录）+ LICENSE + assets（hero.svg 自绘 + community-qr 复制）；hero.svg 经 Chrome 渲染 + PIL 像素验证 + recognize.ps1 AI 视觉三重校验通过
- 2026-08-28 18:20：测试产物清理（tmp 截图/脚本/测试输出），PROGRESS 更新至 70%

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
