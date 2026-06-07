"""docx_gen -- Markdown -> Word 文档生成模块"""

from .styles import (
    normalize_heading_styles,
    normalize_paragraphs,
    normalize_abstract_keywords,
    set_run_fonts,
    superscript_numeric_citations,
)
from .tables import (
    apply_three_line_tables,
    fix_table_formatting,
)
from .assets import (
    replace_asset_placeholders,
    insert_images,
)
from .formulas import protect_math_objects
from .output import save_and_roundtrip_check, write_build_log
