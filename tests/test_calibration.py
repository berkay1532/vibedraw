# tests/test_calibration.py
from core.perception.calibration import estimate_units_per_meter, scaled_params, BASE, BASE_UPM, FileParams
from core.perception.parse import YaziText


def test_estimate_units_per_meter():
    # cm ölçeğinde 3.5 m aralıklı odalar → ~100 birim/m
    cm = [YaziText("A", (0, 0)), YaziText("B", (350, 0)), YaziText("C", (0, 350)), YaziText("D", (350, 350))]
    assert 70 < estimate_units_per_meter(cm) < 140
    # mm ölçeği → ~1000
    mm = [YaziText(t.content, (t.xy[0] * 10, t.xy[1] * 10)) for t in cm]
    assert 700 < estimate_units_per_meter(mm) < 1400
    assert estimate_units_per_meter([YaziText("A", (0, 0))]) == 100.0  # tek etiket: varsayılan


def test_scaled_params_scale_linearly():
    p = scaled_params(BASE_UPM)
    assert p["res"] == BASE["res"] and p["seal"] == BASE["seal"]
    q = scaled_params(2 * BASE_UPM)
    assert abs(q["res"] - 2 * BASE["res"]) < 1e-9 and abs(q["margin"] - 2 * BASE["margin"]) < 1e-9
    assert FileParams(units_per_meter=100).to_mm((1.0, 2.0)) == (10.0, 20.0)
