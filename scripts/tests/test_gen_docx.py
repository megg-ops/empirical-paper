import json
from pathlib import Path

from gen_docx import load_assets_manifest


def test_assets_are_resolved_relative_to_manifest(tmp_path):
    output = tmp_path / "03_coder/output"
    (output / "tables").mkdir(parents=True)
    table = output / "tables/table.md"
    table.write_text("| x |\n|---|\n| 1 |", encoding="utf-8")
    manifest = output / "assets_manifest.json"
    manifest.write_text(json.dumps({
        "tables": [{"id": "t1", "path": "tables/table.md"}], "figures": []
    }), encoding="utf-8")
    assets = load_assets_manifest(str(manifest))
    assert assets["tables"][0]["path"] == str(table.resolve())
