# LaTeX 格式规范

本文件定义经管类课程论文的 LaTeX 格式要求。writer_agent 和 coder_agent 必须遵守。

---

## 标准文档头

所有论文必须使用以下文档头（基于 ctexart）：

```latex
\documentclass[a4paper,12pt]{ctexart}
\usepackage[margin=2.5cm]{geometry}
\usepackage{booktabs}        % 三线表（\toprule, \midrule, \bottomrule）
\usepackage{threeparttable}  % 表注
\usepackage{graphicx}        % 图片
\usepackage{float}           % [H] 浮动控制
\usepackage{amsmath}         % 数学公式
\usepackage{hyperref}        % 超链接
\usepackage{adjustbox}       % 表格宽度自适应
\usepackage{tabularx}        % 自动列宽表格
\usepackage{longtable}       % 跨页长表格
\usepackage{caption}         % 标题定制
```

writer_agent 生成文档头时必须包含以上所有包。不得遗漏。

---

## 表格规范

### 宽度控制

| 情况 | 处理方式 |
|------|---------|
| 列数 ≤ 5，行数 ≤ 15 | 普通 `tabular` 环境 |
| 列数 > 5 | 用 `\begin{adjustbox}{width=\textwidth}` 包裹 |
| 行数 > 20 | 用 `longtable` 环境（支持跨页） |
| 列宽不均匀 | 用 `tabularx` 的 `X` 列类型自动分配宽度 |

### 示例：adjustbox 包裹

```latex
\begin{table}[H]
\centering
\caption{表格标题}
\label{tab:xxx}
\begin{adjustbox}{width=\textwidth}
\begin{threeparttable}
\begin{tabular}{lcccccc}
\toprule
...
\bottomrule
\end{tabular}
\begin{tablenotes}
\footnotesize
\item 注：表注说明。
\end{tablenotes}
\end{threeparttable}
\end{adjustbox}
\end{table}
```

### 示例：longtable 跨页

```latex
\begin{longtable}{lccc}
\caption{表格标题} \label{tab:xxx} \\
\toprule
列1 & 列2 & 列3 & 列4 \\
\midrule
\endfirsthead
\toprule
列1 & 列2 & 列3 & 列4 \\
\midrule
\endhead
\bottomrule
\endfoot
数据 & 数据 & 数据 & 数据 \\
...
\end{longtable}
```

### 三线表规则

- 必须使用 `booktabs` 包的 `\toprule`、`\midrule`、`\bottomrule`
- 禁止使用 `\hline` 和 `|`
- 表注用 `threeparttable` 的 `tablenotes` 环境
- 数值右对齐（`r`），文字左对齐（`l`）

---

## 图片规范

### 必须引用所有已存在的图

`figures/` 目录下的每个 `.png` 文件都必须在论文中被 `\includegraphics` 引用。不得遗漏。

### 图片引用格式

```latex
\begin{figure}[H]
\centering
\includegraphics[width=0.8\textwidth]{figures/xxx.png}
\caption{图标题}
\label{fig:xxx}
\end{figure}
```

### 图片放置规则

- 图放在引用它的段落之后、下一个段落之前
- 用 `[H]` 固定位置（需要 `float` 包）
- 宽度默认 `0.8\textwidth`，不超过 `0.9\textwidth`
- 必须有 `\caption` 和 `\label`

---

## 引用规范

### cite key 命名规则

**禁止使用中文字符作为 cite key。** 统一使用英文 + 年份格式：

| 正确 | 错误 |
|------|------|
| `\cite{fried2002}` | `\cite{Fried2002}` |
| `\cite{li2020}` | `\cite{李康}` |
| `\cite{wang2021}` | `\cite{王甲旬}` |

**理由**：中文 cite key 在某些编译环境下会导致引用显示 `[?]`。

### thebibliography 规则

- 使用 `\begin{thebibliography}{99}` 环境
- 每个 `\bibitem{key}` 的 key 必须与 `\cite{key}` 完全匹配
- 引用格式使用 GB/T 7714

### 已知问题

- `hyperref` 包有时会干扰引用渲染，建议在 `thebibliography` 前加 `\phantomsection`
- 如果编译后引用仍显示 `[?]`，检查 cite key 是否包含特殊字符

---

## 列表和编号

- 正文中不使用 `\begin{enumerate}` 或 `\begin{itemize}`，直接用文字叙述
- 表格编号：`tab:xxx` 格式
- 图片编号：`fig:xxx` 格式
- 公式编号：`(1)` `(2)` 格式（用 `\tag{}` 或自动编号）

---

## 编译要求

- 使用 XeLaTeX 编译（支持中文）
- 编译命令：`xelatex -interaction=nonstopmode paper.tex`
- 编译后检查 `.log` 文件中的 `[?]` 警告
- 如果有未定义的引用，检查 cite key 是否匹配

### 特殊字符预检查

编译前必须扫描正文中未转义的 LaTeX 特殊字符，否则会导致编译失败，所有 `\ref{}`/`\cite{}` 渲染为 `[?]`：

| 字符 | 正确写法 | 常见错误场景 |
|------|---------|-------------|
| `&` | `\&` | R&D、表格列分隔符之外的正文中的 & |
| `%` | `\%` | 百分比符号 |
| `_` | `\_` | 变量名中的下划线 |
| `#` | `\#` | 井号 |
| `$` | `\$` | 美元符号（非数学模式） |

**检查方式**：编译前用 `grep -Pn '(?<!\\)[&%_#]' paper.tex | grep -v '\\\\'` 扫描未转义字符。特别注意 `R&D` 必须写成 `R\&D`。

---

## writer_agent 生成检查清单

在输出 paper_draft.tex 前，逐项检查：

1. [ ] 文档头包含所有必需包
2. [ ] 所有表格使用 booktabs 三线表
3. [ ] 列数 > 5 的表格用 adjustbox 包裹
4. [ ] 行数 > 20 的表格用 longtable
5. [ ] figures/ 目录下所有 .png 都被引用
6. [ ] 每张图都有 caption 和 label
7. [ ] cite key 全部使用英文+年份格式（如选择交叉引用格式）
8. [ ] 每个 \cite{} 都有对应 \bibitem{}（如选择交叉引用格式）
9. [ ] 无中文字符作为 cite key
10. [ ] 正文中无未转义的特殊字符（&、%、_、#），R&D 必须为 R\&D
11. [ ] 正文中无括号内嵌显著性标记（如"系数为X（1%显著）"）
