"""公式保护 -- 确保数学对象不被后处理破坏。"""

from docx import Document
from docx.oxml.ns import qn


def protect_math_objects(doc: Document) -> int:
    """Ensure m:oMath / m:oMathPara elements are not disturbed.
    This is a no-op guard: we log count but do not modify math elements."""
    count = 0
    body = doc.element.body
    # Count m:oMathPara (block math)
    count += len(body.findall(f".//{qn('m:oMathPara')}"))
    # Count m:oMath that are NOT inside m:oMathPara (inline math)
    for omath in body.findall(f".//{qn('m:oMath')}"):
        parent = omath.getparent()
        if parent is not None and parent.tag != qn("m:oMathPara"):
            count += 1
    return count
