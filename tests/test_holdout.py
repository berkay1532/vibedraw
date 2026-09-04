# tests/test_holdout.py — holdout listesi: evaluate ayrı satır basar, calibrate reddeder
import pytest
from learning.calibrate import HoldoutError, holdout_files, is_holdout, tuning_set


def test_holdout_config_and_refusal(tmp_path):
    hold = holdout_files()
    assert "tip-6_mimari" in hold
    for n in ("tip-6_mimari", "tip-1_mimari", "x"):
        (tmp_path / f"{n}.json").write_text("{}")
    files = tuning_set(tmp_path)
    assert [p.stem for p in files] == ["tip-1_mimari", "x"]           # holdout dışarıda
    with pytest.raises(HoldoutError):
        tuning_set(tmp_path, ["tip-6_mimari"])
    assert is_holdout("tip-6_mimari") and not is_holdout("tip-1_mimari")
