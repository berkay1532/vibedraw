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


def test_label_upm_confidence_low_for_grid_and_high_for_scatter():
    from core.perception.calibration import label_upm_confidence
    from core.perception.parse import YaziText
    grid = [YaziText("ODA", (x * 50.0, y * 50.0)) for x in range(4) for y in range(4)]      # tablo: hep 50 birim
    assert label_upm_confidence(grid) <= 0.3
    import random
    random.seed(1)
    scatter = [YaziText("ODA", (random.uniform(0, 3000), random.uniform(0, 3000))) for _ in range(20)]
    assert label_upm_confidence(scatter) >= 0.9
    assert label_upm_confidence(grid[:3]) == 0.3
