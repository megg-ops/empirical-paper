import json

from check_word_count import count_words_file, load_requirement


def test_manifest_requirement_and_file_count(tmp_path):
    paper = tmp_path / "paper.md"
    paper.write_text("# 标题\n正文内容 test 42\n# 参考文献\n忽略", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"paper_requirements": {"word_count": {
        "mode": "minimum", "minimum": 5, "source": "user", "confirmed_by_user": True
    }}}), encoding="utf-8")
    req = load_requirement(str(manifest))
    assert req["minimum"] == 5
    assert count_words_file(str(paper), req["scope"])["total"] == 6


def test_requirement_must_be_confirmed(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"paper_requirements": {"word_count": {
        "mode": "exact", "target": 8000, "source": "framework", "confirmed_by_user": False
    }}}), encoding="utf-8")
    try:
        load_requirement(str(manifest))
    except ValueError as exc:
        assert "用户确认" in str(exc)
    else:
        raise AssertionError("unconfirmed requirement must fail")
