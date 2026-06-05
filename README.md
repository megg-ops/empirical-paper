# Empirical Paper Skill v0.7.0

自动撰写中文经管类实证结课论文。适用于本科/硕士课程论文、期末论文、课程作业型实证论文。

## 快速开始

### 0. 安装 Skill

将本仓库下载到项目的 `.claude/skills/` 目录下：

```bash
# 在你的项目根目录执行
mkdir -p .claude/skills
git clone https://github.com/<your-username>/empirical-paper.git .claude/skills/empirical-paper
```

安装 Python 依赖：

```bash
pip install -r .claude/skills/empirical-paper/scripts/requirements.txt
# 或使用 uv: uv pip install -r .claude/skills/empirical-paper/scripts/requirements.txt
```

Word 输出还需要 [pandoc](https://pandoc.org/installing.html)，请确认已安装：

```bash
pandoc --version
```

### 1. 准备材料

在项目根目录准备以下文件：

```
你的项目/
├── 研究框架.docx        # 或 .md 或 .pdf（必须）
├── 建模数据.xlsx        # 或 .csv（必须）
├── 论文模板.tex          # （可选）
└── references/           # 参考文献目录（可选）
    ├── ref1.pdf
    ├── ref2.pdf
    └── ...
```

### 2. 在 Claude Code 中启用

在对话中输入：

```
/empirical-paper
```

或直接说：

```
使用 empirical-paper skill 帮我写论文
```

### 3. 等待完成

skill 会自动：
1. 识别你的材料，生成 manifest.json
2. 审计数据质量，生成变量映射
3. 设计研究方案，选择合适模型（**需要你确认五项内容**）
4. 跑代码生成表格和图
5. 撰写完整论文（**你可以审阅并提出修改，最多 2 轮**）
6. 质量审查 + 验证 + 最终整合
7. 输出最终论文到 `paper_workspace/final_paper/`

## v0.7.0 新特性

### 引言政策搜索与交叉验证

- writer 撰写引言前自动搜索与研究主题相关的国家重大战略/政策
- 三重验证策略：来源多样性（至少 2 个独立来源）、内容一致性、原文可达性
- 验证通过的政策自然融入引言 Hook 段落，不堆砌政策名称
- 搜索结果记录在 `policy_references.md`，便于审查
- 新增 `references/policy_search_protocol.md` 定义搜索协议

### 独立专家审稿人（Stage 6，可选）

- 论文全部完成后，询问用户是否启动独立专家审稿人
- 以经管领域资深专家视角审查：方法设计、统计原理、格式规范
- AI 味评分（0-100 分，低于 30 分为安全），4 维度 16 项指标逐项打分
- 完全隔离：不读取任何 Stage 1-5 的中间产物，不修改论文
- 新增 `agents/expert_reviewer_agent.md` 和 `references/independent_review_rubric.md`

## v0.6.0 特性

### Blocking Gate 程序化强制

- Stage 2 五项确认和 Stage 4 用户审阅现在通过 `AskUserQuestion` 工具强制执行
- 用户确认后写入 `user_confirmed.flag` 文件，后续 Stage 的 GATE 会检查此文件
- Stage 3 方法降级：coder 如果需要降级模型，写 `method_approximation.flag` 后暂停，等待用户决定

### 内容规划驱动字数

- modeler 输出各章论点提纲（每章 3-5 个论点），writer 按提纲写，确保内容密度
- writer 完成后执行"先扩后停"字数自检：不足 7500 字时有针对性扩写，达标后再触发 BLOCKING
- 扩写方向指定：文献综述多引文献、稳健性分析解释系数、结论增加异质性讨论

### LaTeX 格式规范

- 新增 `references/latex_formatting.md`：标准文档头、三线表、宽度控制、图片引用、cite key 规范
- writer 新增 R5（表格宽度）、R6（英文 cite key）
- R3 改为双向约束：不仅不能引用不存在的文件，还必须引用所有已存在的图和表
- reviewer 新增维度 6：LaTeX 格式审查

### Coder 分步检查点

- 从 8 步扁平流程改为 5 步检查点流程，每步增量写入 results_summary.md
- 方法库不可用时写 flag 文件暂停，不再自行降级

### 反幻觉机制

- 5 条红线：禁止编造统计结果、禁止编造引用、禁止代码-论文不一致、禁止方法误用、禁止字数/结构不达标
- 验证脚本 `scripts/verify_consistency.py` 自动检查数字/引用/图表一致性

### 质量审查

- 审查手（reviewer_agent）6 维度审查：数字一致性、引用完整性、代码-论文一致性、方法正确性、写作质量、LaTeX 格式规范
- 每个维度 pass/warn/block 评级

## 推荐文件命名

使用以下名称可提高自动识别准确率：

```
研究框架.docx / research_framework.docx / 研究框架.md
建模数据.xlsx / data.xlsx / 数据.xlsx
论文模板.tex / template.tex
references/ / refs/ / 文献/
```

## 适合 / 不适合

**适合：**
- 期末课程论文
- 本科/硕士课程作业
- 已有数据和大致研究主题的实证论文

**不适合：**
- 需要投稿发表的高强度论文
- 没有任何数据的论文
- 需要复杂因果识别但数据不支持的研究

## 研究框架格式

研究框架是告诉 skill"写什么、怎么写"的文档。支持 `.docx`、`.md`、`.pdf` 三种格式。

### 必须包含的内容

| 内容 | 说明 |
|------|------|
| 论文标题 | 一句话 |
| 目标字数 | 总字数 |
| 章节安排 | 每章标题、字数、子节 |
| 子节写作指引 | 每个子节写什么 |
| 公式标记 | 哪些子节需要公式推导（写"公式""推导""模型"等关键词） |
| 表格/图标记 | 哪些子节需要表格或图（写"表格""描述性统计""回归结果"等关键词） |
| 参考文献要求 | 必引文献、数量、比例 |
| 变量说明 | 变量名、含义、来源 |

### Markdown 格式示例

```markdown
# 数字化转型对企业绩效的影响研究——基于A股上市公司面板数据

目标字数：8000字

## 摘要（300字）

包含：研究问题、方法、主要发现、政策含义

关键词：数字化转型 / 企业绩效 / 固定效应 / 面板数据 / 异质性分析

## 一、引言（1000字）

### 研究背景
数字经济背景下企业数字化转型的战略意义

### 文献综述
数字化转型的测度方法、绩效影响的实证发现、现有研究的不足

### 研究贡献
样本期更新、细化数字化转型维度、考虑行业异质性

## 二、研究设计（1500字）

### 2.1 模型设定
【公式】双向固定效应模型推导，变量定义，经济含义

### 2.2 变量说明
【表格】被解释变量（ROA/ROE）、核心解释变量（数字化转型指数）、控制变量（企业规模、资产负债率、企业年龄等）

### 2.3 数据来源与样本选择
数据来源、样本范围、缺失值处理

## 三、实证分析（3000字）

### 3.1 描述性统计
【表格】各变量均值/标准差/最大最小值

### 3.2 基准回归
【表格】数字化转型对企业绩效的影响，逐步加入控制变量

### 3.3 稳健性检验
替换被解释变量 / 更换核心解释变量 / 缩尾处理

### 3.4 异质性分析
按行业/地区/企业规模分组回归

### 3.5 机制分析（如数据支持）
中介效应或调节效应

## 四、结论与政策建议（800字）

### 主要发现
归纳3条

### 政策建议
针对不同类型企业的差异化数字化策略

### 研究局限
内生性问题、指标构建、样本范围

## 参考文献

25-30篇，中英各半

变量说明：
- 被解释变量：ROA（总资产收益率）、ROE（净资产收益率）
- 核心解释变量：数字化转型指数（文本分析法构建）
- 控制变量：企业规模（总资产对数）、资产负债率、企业年龄、股权集中度
```

## 工作目录结构

skill 执行后会创建以下目录：

```
paper_workspace/
├── your_project_20260605_120000_a1b2c3/  ← run_id 隔离目录
│   ├── 00_intake/                         # 材料识别
│   │   └── output/
│   │       ├── manifest.json              # 文件识别结果
│   │       └── framework.md               # 统一格式的框架
│   │
│   ├── 01_audit/                          # 数据审计
│   │   └── output/
│   │       ├── data_audit.md              # 审计报告
│   │       └── variable_map.json          # 变量映射
│   │
│   ├── 02_modeler/                        # 研究设计
│   │   └── output/
│   │       ├── model_plan.md              # 模型选择方案
│   │       └── 实证设计.md                 # 公式推导
│   │
│   ├── 03_coder/                          # 代码分析
│   │   └── output/
│   │       ├── analysis.py                # 分析代码
│   │       ├── tables/                    # LaTeX 表格
│   │       ├── figures/                   # 图文件
│   │       ├── results_summary.md
│   │       ├── model_diagnostics.md
│   │       └── run_log.md
│   │
│   ├── 04_writer/                         # 论文写作
│   │   └── output/
│   │       ├── paper_draft.tex
│   │       ├── references_used.md
│   │       ├── writing_checklist.md
│   │       └── policy_references.md
│   │
│   ├── final_paper/                       # 最终输出
│   │   ├── paper_final.tex
│   │   ├── quality_check.md
│   │   └── compile_log.txt
│   │
│   └── 06_expert_review/                  # 独立专家审稿（可选）
│       └── output/
│           └── expert_review_report.md
```

## 流程说明

| 阶段 | Agent | 职责 | 输入 | 输出 |
|------|-------|------|------|------|
| Stage 0 | 主Agent | 材料识别 | 用户文件 | manifest.json + framework.md |
| Stage 1 | 数据审计 | 数据质量检查 | 数据 + 框架 | data_audit.md + variable_map.json |
| Stage 2 | 研究设计手 | 模型选择 + 公式推导 | 框架 + 审计结果 | model_plan.md + 实证设计.md |
| Stage 3 | 编程手 | 跑代码 + 生成表格/图 | 数据 + 变量映射 + 实证设计 | 代码 + 表格 + 结果 + 诊断 |
| Stage 4 | 论文手 | 写全文（含政策搜索） | 所有素材 | paper_draft.tex + 引用清单 + 政策记录 |
| Stage 5 | 审查手 | 质量审查 + 验证 | 初稿 + 所有中间产物 | paper_final.tex + quality_check.md |
| Stage 6 | 独立审稿人 | 专家审稿 + AI味评分（可选） | 最终论文 | expert_review_report.md |

## 模型选择规则

skill 会根据数据结构自动选择合适的模型：

| 数据情况 | 推荐模型 |
|----------|----------|
| 只有截面数据 | 描述统计 + 相关分析 + OLS |
| 有年份和个体 ID | 双向固定效应优先 |
| 因变量为 0/1 | Logit/Probit |
| 因变量受限 | Tobit |
| 效率评价 | DEA/SFA |
| 政策冲击 + 处理组 | DID |
| 数据不支持 | 降级到可接受的分析 |

不会强行推荐数据不支持的复杂模型。

## 常见问题

### Q: 我只有数据和研究框架，没有 LaTeX 模板怎么办？

skill 会生成默认模板（ctexart 文档类，A4 纸，标准页边距）。

### Q: 我没有参考文献怎么办？

论文手会尝试搜索补充，但建议至少提供几篇核心文献。补充的文献会标记为"待确认"。

### Q: 数据审计发现变量不匹配怎么办？

skill 会列出未匹配的变量，询问你是否继续。你可以修改数据列名或框架变量名后重新运行。

### Q: 编程手跑的代码报错了怎么办？

skill 会自动分析错误并重试一次。你也可以手动检查 `paper_workspace/03_coder/output/analysis.py`。

### Q: 我想修改某个章节的内容怎么办？

在 Stage 4 审阅初稿时提出修改意见，论文手会增量修改。最多 2 轮修改循环。

### Q: 最终论文的 LaTeX 编译报错怎么办？

检查 `paper_workspace/final_paper/compile_log.txt`，常见问题：
- 表格路径错误：检查 `tables/` 目录是否存在
- 中文编码：确保使用 XeLaTeX 编译
- 字体缺失：确保系统安装了 ctex 所需字体

### Q: 我想让某个阶段重做怎么办？

删除对应阶段的 `output/` 目录内容（包括 `user_confirmed.flag`），然后重新启用 skill。可以用 `python scripts/stage_guard.py --stage N` 检查当前状态。

## 注意事项

- 建议用户提供尽量清洗好的数据
- 编程手的代码设置随机种子，保证结果可复现
- 所有表格数据来自真实计算，不允许编造
- 参考文献不会编造，无法确认的会标记为"待确认"
- 引用格式默认使用 GB/T 7714
- `paper_workspace/` 目录保留所有中间产物，方便检查和调试

## 断点续接与上下文恢复

本 skill 使用 `paper_workspace/session_state.md` 记录当前流水线状态。每个 Stage 完成后自动更新。

续接对话或上下文压缩后，执行者应先读取 `paper_workspace/session_state.md`，并运行：

```bash
python scripts/stage_guard.py --infer
```

若检查通过，可从 `session_state.md` 中记录的"下一阶段"继续执行；若检查失败，应根据缺失项恢复输入文件或询问用户。

只有在 `session_state.md` 缺失或无法判断阶段时，才需要重读完整 `SKILL.md`。`SKILL.md` 是最后兜底，不是默认动作。

## Word 输出管线

Word 路径采用：

`paper_draft.md → pandoc → raw.docx → python-docx 后处理 → paper_final.docx`

设计原因：

1. Markdown 用于稳定承载 LaTeX 公式；
2. pandoc 负责将公式转换为 Word 原生公式；
3. python-docx 不生成公式，只做格式后处理；
4. validate_docx.py 检查 Word 可打开性、公式、图表、表格、引用和格式；
5. 若验证脚本发现 BLOCKER，最终论文不得标记为通过。

## 文件结构

```
.claude/skills/empirical-paper/
├── SKILL.md                           # 主协调者
├── README.md                          # 本文件
├── LICENSE                            # MIT 开源协议
├── .gitignore
├── agents/
│   ├── audit_agent.md                 # 数据审计
│   ├── modeler_agent.md               # 研究设计
│   ├── coder_agent.md                 # 编程手
│   ├── writer_agent.md                # 论文手
│   ├── reviewer_agent.md              # 审查手
│   └── expert_reviewer_agent.md       # 独立审稿人
├── scripts/
│   ├── stage_guard.py                 # Stage 入口检查
│   ├── update_session_state.py        # session_state 更新
│   ├── check_word_count.py            # 字数统计
│   ├── extract_word_template_rules.py # Word 模板规则提取
│   ├── gen_docx.py                    # Markdown → Word 生成
│   ├── validate_docx.py               # Word 验证
│   ├── verify_consistency.py          # 一致性验证
│   ├── final_quality_gate.py          # 最终质量门禁
│   └── requirements.txt               # Python 依赖
└── references/
    ├── ai_patterns_zh.md              # 中文去 AI 味规范
    ├── writing_standards.md           # 写作规范
    ├── citation_rules.md              # 引用规范
    ├── failure_modes.md               # 故障模式清单
    ├── handoff_schemas.md             # 阶段间数据传递合约
    ├── latex_formatting.md            # LaTeX 格式规范
    ├── model_selection_tree.md        # 模型选择树
    ├── method_guardrails.md           # 方法红线
    ├── policy_search_protocol.md      # 政策搜索协议
    ├── results_schema.md              # 结构化结果规范
    ├── review_rubric.md               # 审查分级规则
    ├── word_format_rules.md           # Word 格式规则
    ├── independent_review_rubric.md   # AI 味评分细则
    └── routing_map.md                 # 阶段引用路由表
```

## 免责声明

本项目用于生成可审阅的实证论文草稿、分析代码与质量检查报告。使用者需自行核验数据、方法、引用和最终文本，并遵守所在机构的学术诚信要求。
