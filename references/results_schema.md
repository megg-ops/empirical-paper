# results.json Schema

Stage 3 输出的最小结构化结果文件。论文中的关键实证数字必须来自此文件，不得从 `results_summary.md` 自由抄数。

## 路径

`<workspace>/03_coder/output/results.json`

## 结构

```json
{
  "meta": {
    "method": "",
    "sample_size": null,
    "notes": []
  },
  "reportable_values": [
    {
      "key": "main.result_001",
      "label": "主结果指标 1",
      "value_raw": 1.23456,
      "value_display": "1.235",
      "precision": 3,
      "allowed_text_forms": ["1.235"],
      "source": "table_main_01",
      "must_report": true
    }
  ],
  "warnings": []
}
```

## 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `meta.method` | string | 是 | 使用的研究方法名称 |
| `meta.sample_size` | int \| null | 是 | 最终样本量 |
| `meta.notes` | string[] | 否 | 备注信息 |
| `reportable_values` | array | 是 | 论文中可报告的关键数字列表，不得为空 |
| `reportable_values[].key` | string | 是 | 稳定唯一标识 |
| `reportable_values[].label` | string | 是 | 数字含义 |
| `reportable_values[].value_raw` | number | 是 | 原始计算值 |
| `reportable_values[].value_display` | string | 是 | 论文中应使用的展示值 |
| `reportable_values[].precision` | int | 是 | 小数位数 |
| `reportable_values[].allowed_text_forms` | string[] | 是 | 允许出现在论文中的文本形式 |
| `reportable_values[].source` | string | 是 | 来源表格、模型或图 |
| `reportable_values[].must_report` | bool | 是 | 是否必须出现在论文中 |

## key 命名规范

使用中性前缀，不绑定具体方法或论文：

- `main.result_*`：主模型结果
- `main.metric_*`：主指标
- `robustness.result_*`：稳健性检验结果
- `heterogeneity.result_*`：异质性分析结果
- `descriptive.*`：描述性统计
- `diagnostic.*`：诊断检验结果

## 使用规则

1. **coder**：所有准备写进论文正文、摘要、结论或图表说明的关键数字，都必须放入 `reportable_values`
2. **writer**：必须使用 `value_display`，不得自行四舍五入或重算
3. **reviewer**：论文中的关键实证数字必须匹配 `value_display` 或 `allowed_text_forms`
4. `results_summary.md` 只作为人类可读摘要，不是数字真源
