# tests/test_binding.py
from core.perception.ir_v1 import Room
from core.perception.binding import _room_by_swing, pair_names_with_areas
from core.perception.parse import YaziText


def test_room_by_swing_prefers_direction_over_distance():
    salon = Room(raw_name="Salon", label_xy=(300.0, 0.0)); hol = Room(raw_name="Hol", label_xy=(-60.0, 0.0))
    # menteşe orijinde, yay +x yönüne açılıyor → uzak ama yöndeki Salon
    assert _room_by_swing((0.0, 0.0), (1.0, 0.0), [salon, hol]) is salon


def test_pair_names_with_areas_nearest_area_text():
    texts = [YaziText("Salon", (0, 0)), YaziText("A: 20m²", (0, -5)), YaziText("Banyo", (300, 0)), YaziText("A: 5m²", (300, -5))]
    rooms = {r.raw_name: r.area_m2 for r in pair_names_with_areas(texts)}
    assert rooms == {"Salon": 20.0, "Banyo": 5.0}
