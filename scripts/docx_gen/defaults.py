"""默认格式规则 —— 无模板时的 fallback 格式定义。

定义经管类课程论文的默认 Word 格式：字号、字体、对齐、行距等。
gen_docx.py 在没有 template_rules 时使用此模块。
extract_word_template_rules.py 在合并规则时将此作为 fallback 层。
"""

PT_TO_CHINESE = {
    42: "初号", 36: "小初",
    26: "一号", 24: "小一",
    22: "二号", 18: "小二",
    16: "三号", 15: "小三",
    14: "四号", 12: "小四",
    10.5: "五号", 9: "小五",
    7.5: "六号", 6.5: "小六",
    5.5: "七号", 5: "八号",
}

CHINESE_TO_PT = {v: k for k, v in PT_TO_CHINESE.items()}

FALLBACK_DEFAULTS = {
    "title": {
        "font_name": "Times New Roman",
        "font_name_east_asia": "黑体",
        "font_size_pt": 16,
        "font_size_chinese": "三号",
        "bold": True,
        "alignment": "居中",
    },
    "heading1": {
        "font_name": "Times New Roman",
        "font_name_east_asia": "楷体",
        "font_size_pt": 14,
        "font_size_chinese": "四号",
        "bold": False,
        "alignment": "居中",
    },
    "heading2": {
        "font_name": "Times New Roman",
        "font_name_east_asia": "宋体",
        "font_size_pt": 14,
        "font_size_chinese": "四号",
        "bold": True,
        "alignment": "左对齐",
    },
    "heading3": {
        "font_name": "Times New Roman",
        "font_name_east_asia": "宋体",
        "font_size_pt": 10.5,
        "font_size_chinese": "五号",
        "bold": True,
        "alignment": "左对齐",
    },
    "body": {
        "font_name": "Times New Roman",
        "font_name_east_asia": "宋体",
        "font_size_pt": 10.5,
        "font_size_chinese": "五号",
        "bold": False,
        "alignment": "两端对齐",
        "first_line_indent_chars": 2,
        "line_spacing": "1.1",
    },
    "abstract": {
        "font_name": "Times New Roman",
        "font_name_east_asia": "宋体",
        "font_size_pt": 10.5,
        "font_size_chinese": "五号",
        "bold": False,
        "alignment": "两端对齐",
    },
    "keywords": {
        "font_name": "Times New Roman",
        "font_name_east_asia": "宋体",
        "font_size_pt": 10.5,
        "font_size_chinese": "五号",
        "bold": False,
    },
    "table_caption": {
        "font_name": "Times New Roman",
        "font_name_east_asia": "宋体",
        "font_size_pt": 10.5,
        "font_size_chinese": "五号",
        "bold": False,
        "alignment": "居中",
    },
    "figure_caption": {
        "font_name": "Times New Roman",
        "font_name_east_asia": "宋体",
        "font_size_pt": 10.5,
        "font_size_chinese": "五号",
        "bold": False,
        "alignment": "居中",
    },
    "table": {
        "font_name": "Times New Roman",
        "font_name_east_asia": "宋体",
        "font_size_pt": 10.5,
        "font_size_chinese": "五号",
        "table_style": "three_line",
    },
    "references": {
        "font_name": "Times New Roman",
        "font_name_east_asia": "宋体",
        "font_size_pt": 10.5,
        "font_size_chinese": "五号",
        "bold": False,
        "alignment": "两端对齐",
    },
}
