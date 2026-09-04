# tests/test_graph.py
import pytest

pytest.importorskip("langgraph")   # elektrik prototipi opsiyonel (requirements-electrical.txt)
from graph import build_graph, run_pipeline  # noqa: E402


def test_run_pipeline_end_to_end(synthetic_dxf, tmp_path, monkeypatch):
    # LLM'i tamamen mock'la (gerekçe + bilinmeyen isim ihtimaline karşı)
    import core.perception.semantics as S
    import core.electrical.rules as R
    monkeypatch.setattr(S.llm, "normalize_room_name", lambda raw: "other")
    monkeypatch.setattr(R, "_rationale", lambda *a, **k: "test gerekçe")

    out = str(tmp_path / "result.dxf")
    state = run_pipeline(synthetic_dxf, out_path=out, target_floor=0,
                         gap=200.0, rules_path="rules/residential.yaml")
    assert state["out_path"] == out

    import ezdxf
    doc = ezdxf.readfile(out)
    layer_names = {l.dxf.name for l in doc.layers}
    assert "EL-AYDINLATMA" in layer_names


def test_build_graph_is_constructible():
    g = build_graph()
    assert g is not None
