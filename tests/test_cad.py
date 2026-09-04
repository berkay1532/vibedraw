# tests/test_cad.py
import ezdxf
from core.perception.ir_v1 import Room
from core.electrical.ir import RoomDesign, Symbol, Circuit, DesignIR
from core.electrical.cad import write_dxf


def _design():
    room = Room(raw_name="Salon", label_xy=(100.0, 200.0), area_m2=14.0, room_type="living")
    rd = RoomDesign(
        room=room,
        fixtures=[Symbol("light", (100.0, 200.0), "general-L")],
        sockets=[Symbol("socket", (130.0, 200.0), "general-P"),
                 Symbol("socket", (160.0, 200.0), "general-P")],
        circuit_id="general-L",
    )
    return DesignIR(rooms=[rd], circuits=[Circuit("general-L", "lighting", ["Salon"]),
                                          Circuit("general-P", "socket", ["Salon"])])


def test_write_dxf_preserves_source_and_adds_layers(synthetic_dxf, tmp_path):
    out = str(tmp_path / "out.dxf")
    write_dxf(_design(), source_path=synthetic_dxf, out_path=out)

    doc = ezdxf.readfile(out)
    layer_names = {l.dxf.name for l in doc.layers}
    assert {"EL-AYDINLATMA", "EL-PRIZ", "EL-LINYE"} <= layer_names
    # mimari altlık korunmuş (YAZI hâlâ var)
    assert "YAZI" in layer_names

    msp = doc.modelspace()
    inserts = [e for e in msp if e.dxftype() == "INSERT"]
    used_blocks = {e.dxf.name for e in inserts}
    assert "EL_LIGHT" in used_blocks
    assert "EL_SOCKET" in used_blocks


def test_write_dxf_draws_circuit_polyline(synthetic_dxf, tmp_path):
    out = str(tmp_path / "out2.dxf")
    write_dxf(_design(), source_path=synthetic_dxf, out_path=out)
    doc = ezdxf.readfile(out)
    msp = doc.modelspace()
    linye = [e for e in msp if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "EL-LINYE"]
    assert len(linye) >= 1
