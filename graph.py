# graph.py
from __future__ import annotations
from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from core.perception.ir_v1 import BuildingIR
from core.perception.pipeline import select_plan
from core.perception.semantics import classify
from core.electrical.rules import load_rules, decide
from core.electrical.layout import place
from core.electrical.cad import write_dxf
from core.perception.validate import validate_building
from core.electrical.validate import validate_design


class PipelineState(TypedDict, total=False):
    dxf_path: str
    out_path: str
    rules_path: str
    building: object       # BuildingIR
    design: object         # DesignIR


def _parse_node(s: PipelineState) -> PipelineState:
    """Genel yol (Adım 4): katman-bağımsız etiket → ölçek → plan seçimi."""
    sel = select_plan(s["dxf_path"])
    if sel.floor is None:
        raise ValueError("DXF'te ≥3 odalı kat kümesi bulunamadı")
    return {"building": BuildingIR(floors=[sel.floor], source_path=s["dxf_path"])}


def _semantics_node(s: PipelineState) -> PipelineState:
    b = classify(s["building"])
    validate_building(b)
    return {"building": b}


def _decide_node(s: PipelineState) -> PipelineState:
    rules = load_rules(s.get("rules_path", "rules/residential.yaml"))
    return {"design": decide(s["building"], rules)}


def _layout_node(s: PipelineState) -> PipelineState:
    d = place(s["design"])
    validate_design(d)
    return {"design": d}


def _cad_node(s: PipelineState) -> PipelineState:
    write_dxf(s["design"], source_path=s["dxf_path"], out_path=s["out_path"])
    return {}


def build_graph():
    g = StateGraph(PipelineState)
    g.add_node("parse", _parse_node)
    g.add_node("semantics", _semantics_node)
    g.add_node("decide", _decide_node)
    g.add_node("layout", _layout_node)
    g.add_node("cad", _cad_node)
    g.add_edge(START, "parse")
    g.add_edge("parse", "semantics")
    g.add_edge("semantics", "decide")
    g.add_edge("decide", "layout")
    g.add_edge("layout", "cad")
    g.add_edge("cad", END)
    return g.compile()


def run_pipeline(dxf_path: str, out_path: str, rules_path: str = "rules/residential.yaml") -> dict:
    app = build_graph()
    return app.invoke({
        "dxf_path": dxf_path,
        "out_path": out_path,
        "rules_path": rules_path,
    })
