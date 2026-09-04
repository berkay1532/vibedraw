# tests/test_run_stamp.py
from datetime import datetime, timezone, timedelta
from pathlib import Path

from core.perception.run_stamp import code_hash, check_fresh, make_stamp


def test_code_hash_changes_with_content(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n"); h1 = code_hash(tmp_path, ("*.py",))
    assert len(h1) == 12 and code_hash(tmp_path, ("*.py",)) == h1          # deterministik
    (tmp_path / "a.py").write_text("x = 2\n")
    assert code_hash(tmp_path, ("*.py",)) != h1                            # içerik değişince değişir


def test_check_fresh_reasons(tmp_path):
    j = tmp_path / "f.json"; j.write_text("{}")
    now = datetime.now(timezone.utc)
    ok = {"fail_stage": None, "stamp": {"code_hash": "abc", "started_at": (now - timedelta(minutes=1)).isoformat()}}
    assert check_fresh(ok, j, "abc") is None
    assert "kayıt yok" in check_fresh(None, j, "abc")
    assert "hatalı" in check_fresh({**ok, "fail_stage": "geometry"}, j, "abc")
    assert "damgasız" in check_fresh({"fail_stage": None}, j, "abc")
    assert "kod değişmiş" in check_fresh(ok, j, "zzz")
    late = {**ok, "stamp": {**ok["stamp"], "started_at": (now + timedelta(minutes=1)).isoformat()}}
    assert "eski" in check_fresh(late, j, "abc")
    assert "JSON yok" in check_fresh(ok, tmp_path / "missing.json", "abc")


def test_make_stamp_fields():
    st = make_stamp()
    assert set(st) == {"code_hash", "git_commit", "git_dirty", "started_at"} and len(st["code_hash"]) == 12
