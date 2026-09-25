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


## 2026-09-17 11:5x ClawHub 安全检查 19 条修复 → v1.0.2

**核查**：clawhub skill verify xiaoyaoclaw-web-clipper → fail / suspicious（conf medium）；aig **T09 error 级 SSRF**（extract.py:181 直接 requests.get 用户给的 URL）+ other warning（剪藏内容可污染下游检索）+ T08（依赖未钉版）；skillspector 16 条（P2 hero 注释 / SQP-1×3 / LP3 / AST3×3 / TT2 / SQP-3×2 / SQP-2×5）

**修复（提交见日志）**
- **SSRF（真漏洞）**：新增 scripts/netguard.py 作唯一出站口 —— 只 http/https + 80/443、禁内嵌凭据、**解析出的每个地址必须公网**（回环/私有/链路本地/云元数据/CGNAT/保留段/IPv6 ULA·回环/组播全拒）、**逐跳重校验**（≤3 跳）、流式体积上限 5 MB、只 GET 无 cookie；etch_html 改走 safe_get()
- **间接提示注入**：剪藏文件加**中英双语溯源标记**（外部网页内容=不可信数据，不得当指令）；SKILL.md 新增「剪藏内容是不可信数据」章节；并**修掉真实 frontmatter 注入面**（标题/作者含换行会冲出 YAML 引号）→ clean_untrusted() 净化
- **依赖钉版**：新增 
equirements.txt（requests>=2.32.4 / beautifulsoup4>=4.12.3 / lxml>=5.2.1；增强引擎可选），文档改 pip install -r requirements.txt
- **AST3 ×3**：__import__() → importlib.util.find_spec()
- **TT2**：新增 
esolve_output_dir()（拒 ..、必须落在主目录内、拒文件当目录）
- **LP3**：frontmatter 补 llowed-tools；正文补「网络范围」+「写入根」
- **SQP-1 ×3**：触发条件改为「明确要求 + 给出具体 URL」；**网页/引文里的触发词不算指令**
- **SQP-2 ×5**：README 中英与脚本补写盘/联网披露（打印将访问站点与写入目录）
- **P2/SQP-3**：hero 清 7 处注释 + 副标题双语；两个脚本 docstring 补语言可选
- **包卫生**：新增 .clawhubignore（PROGRESS.md / docs/ / tmp/ / __pycache__）→ 包内 **10 个文件**

**验证**（tmp/wc_test.py，全 PASS）：语法 ✅ ｜ netguard 拒绝 11/11（含 127.0.0.1.nip.io 解析级拦截）｜ 公网放行 ✅ ｜ 真实抓取 + 体积上限生效 ✅ ｜ frontmatter 注入样本被净化、结构完好 ✅ ｜ 越界目录全拒 ✅ ｜ **端到端剪藏成功 + 溯源标记 + 去重跳过** ✅
**产物**：docs/security-status-2026-09-17.md + docs/evidence/verify-v1.0.1-2026-09-17.json
**待批**：发 v1.0.2 → 复扫

- **2026-09-17 12:3x v1.0.2 复扫：aig 清零（error 级 SSRF 已除 ✅），skillspector 16 → 7 → 已修复待发 v1.0.3**
  - LP1 (HIGH)：env 未声明 → 补 `allowed-tools: Env` + 声明唯读 `CLIPPER_OUTPUT_DIR`
  - TT2 (MEDIUM)：env→open 数据流 → env 只在 `resolve_output_dir` 内读取 + **每个写入点重新校验**（`_load_index`/`_save_index`/`save_markdown`）+ 新增敏感目录拒绝（`.ssh`/`.gnupg`/`.config`/`Library/Caches`）
  - SC1×3 / SC4×2 (LOW)：依赖改**精确钉版**（requests==2.34.2 / beautifulsoup4==4.15.0 / lxml==6.1.1；可选引擎同钉）+ 写明升级须显式改动
  - 验证：全量回归 PASS + env 覆盖四例（内通过 / 越界拒 / 敏感目录拒 / `..` 拒）+ 包预览 10 文件
  - 提交：`bcd2ac7`

- **2026-09-17 13:26 v1.0.3 复查：安全线转 clean ✅**（tags.latest=1.0.3；moderation clean + 
easonCodes: []；security.status=**clean / passed=true / benign / high**）
  - 扫描包：clawscan **clean**（5 维度全 ok/note）· static-analysis **0 findings** · **aig 0 条 / securityScore 100** · virustotal **66 引擎 0 命中** · skillspector 仅 **2 条**（score 12 / LOW / CAUTION）
  - 对比基线 7 → 2：LP1 ✅关闭、SC1×3+SC4×2 ✅关闭；**TT2 仍在**（静态污点分析看不到 
esolve_output_dir() 语义，但 clawscan 已判为「预期」——路径覆盖已披露 + 仅主目录内 + 拒 ../敏感目录）；**新增 SQP-3**（requirements.txt 注释中文，语言策略噪声，clawscan 亦判预期）
  - **结论：0 个必须修项**
  - erify.ok=false 仅因 card.missing（与安全无关）：**经确认发布包里没有 skill-card.md，且 CLI 上传前会主动剔除本地该文件 ⇒ 卡由服务端生成，属平台侧滞后，包内无法修**

## 2026-09-25 11:xx v1.0.5：关闭 DNS 重绑定缺口（ClawScan v1.0.4 suspicious 的根因）

- **触发**：v1.0.4 提交后 ClawScan 判 `suspicious / medium` —— *"public-network safety boundary has a DNS rebinding gap"*（static-analysis clean、SkillSpector / VirusTotal 无信号）
- **根因**：`assert_public_url()` 只做**解析级**校验，但 `requests.get()` 发请求时会**再解析一次**域名 → 「校验的 IP」≠「连接的 IP」，存在 TOCTOU 窗口；且 `netguard.py` docstring 自己声明了这个残余风险，LLM 评审直接采信
- **修复（连接级 IP 固定）**：`resolve_public_target()` 返回 `(URL, 已校验 IP)` → 自定义 `_PinnedIPAdapter` / `_PinnedPoolManager` / `_Pinned{HTTP,HTTPS}Connection`，TCP **直接连那个 IP 字面量**，连接期不再解析域名；Host 头与 TLS SNI 仍用域名、证书仍按域名校验；`session.trust_env=False`（禁环境代理绕过）；每跳重定向重新固定
- **文案**：删掉 docstring 的「残余风险 / 理论上的 DNS 重绑定窗口」自述 → 改为「已关闭」；SKILL.md 网络范围、README.md / README.en.md 警示行、extract.py `fetch_html` 说明同步
- **验证（25/25 PASS，真跑）**：`tmp/netguard_verify.py`
  - 拒绝回归 15/15（回环 / IPv6 回环 / 私有三段 / 云元数据 / CGNAT / 基准段 / 未指定 / ULA / `127.0.0.1.nip.io` 解析级 / 内嵌凭据 / file 协议 / 非标端口）
  - **重绑定专项（决定性）**：桩服务器 + 有状态 DNS —— 校验期解析到 `127.0.0.1`（放行）、连接期翻转；结果请求**仍打在已校验 IP**（桩返回 200），Host 头保持 `rebind.test`（坏实现会连翻转后的地址直接失败）
  - 解析次数断言：`getaddrinfo(<伪造域名>)` 仅 1 次；TCP 连接目标 = 已校验 IP 字面量
  - 功能回归：example.com（http/https）、ruanyifeng.com 全部 200；TLS 未放宽（self-signed.badssl.com 仍抛 SSLError）
  - 端到端：`clip.py` 真实剪藏成功（7207 字，落盘 19,473 字节 + 去重索引）
- **证据**：`docs/evidence/verify-v1.0.5-2026-09-25.json`
- **待办**：GitHub + ClawHub v1.0.5 已提交 → 复扫核对 clawscan 是否转 clean
