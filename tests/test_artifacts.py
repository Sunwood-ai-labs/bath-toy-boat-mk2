from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_print_models_exist() -> None:
    expected = [
        "cad/out/bath_boat_mk2.step",
        "cad/out/bath_boat_mk2_ams3color_A.3mf",
        "cad/out/bath_boat_mk2_ams3color_B.3mf",
        "cad/slicer/hrx02_mk2_patternB_a1mini.gcode.3mf",
    ]
    for rel in expected:
        p = ROOT / rel
        assert p.is_file(), f"Missing model artifact: {rel}"
        assert p.stat().st_size > 0


def test_eval_json_valid() -> None:
    eval_path = ROOT / "cad/out/eval.json"
    assert eval_path.is_file()
    data = json.loads(eval_path.read_text(encoding="utf-8"))
    assert isinstance(data, list) and len(data) > 0
