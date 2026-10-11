# tests/test_openings.py
import ezdxf
import pytest

from core.perception.openings import _cluster_doors


def test_door_barriers_pick_closed_leaf():
    from core.perception.openings import _door_barriers
    walls = [((0, 0), (300, 0))]                       # yatay duvar y=0
    # menteşe (100,0); uç1 (190,0) duvar üstünde (kapalı), uç2 (100,90) odaya açık
    sw = [((100.0, 0.0), (0.7, 0.7), (190.0, 0.0), (100.0, 90.0))]
    b = _door_barriers(sw, walls)
    assert b == [((100.0, 0.0), (190.0, 0.0))]
    assert _door_barriers(sw, []) == []


def test_cluster_doors_merges_near_points():
    pts = [(0, 0), (2, 1), (50, 50), (51, 49)]
    clusters = _cluster_doors(pts, radius=15.0)
    assert len(clusters) == 2


def test_cluster_doors_tags_sources():
    from core.perception.openings import _cluster_doors
    out = _cluster_doors([(0, 0), (5, 0), (100, 0)], radius=25.0, tags=["block", "arc", "arc"])
    assert len(out) == 2 and out[0][1] == {"block", "arc"} and out[1][1] == {"arc"}


def _door_block_doc(name="95 KAPI", with_arc=False, width=90.0, rot=0.0, scale=1.0):
    """Yaysız (ya da yaylı) blok kapı içeren küçük DXF."""
    import ezdxf
    doc = ezdxf.new("R2010")
    blk = doc.blocks.new(name=name)
    blk.add_line((0, 0), (width, 0))
    blk.add_line((0, 0), (0, 5))
    if with_arc:
        blk.add_arc((0, 0), width, 0, 90)
    msp = doc.modelspace()
    msp.add_blockref(name, (100, 100), dxfattribs={"rotation": rot, "xscale": scale, "yscale": scale})
    return doc, msp


def test_block_door_candidates_name_only():
    """Sözlükle kapı sınıfı alan yaysız blok → aday; konum blok merkezi, genişlik blok uzun kenarı × ölçek."""
    from core.perception.names import block_geom_stats_for, classify_blocks, NameMap, refine_blocks_with_stats
    from core.perception.openings import block_door_candidates
    doc, msp = _door_block_doc()
    nm = NameMap(blocks=classify_blocks([b.name for b in doc.blocks], None))
    assert nm.block_cls("95 KAPI").value == "door"
    nm.block_stats = block_geom_stats_for(msp, 100.0, (50.0, 130.0))
    refine_blocks_with_stats(nm, nm.block_stats, (50.0, 130.0))
    cands = block_door_candidates(msp, doc, (0, 0, 1000, 1000), nm, (50.0, 130.0), (50.0, 260.0))
    assert len(cands) == 1
    cx, cy, w, bn = cands[0]
    assert bn == "95 KAPI" and abs(w - 90.0) < 1e-6
    assert abs(cx - 145.0) < 1.0 and abs(cy - 102.5) < 1.0       # blok merkezi (açıklık orta noktası)


def test_block_door_candidates_skip_arc_and_band_and_class():
    """Yaylı blok (yay yolundan gelir), genişlik bandı dışı blok ve kapı olmayan ad aday ÜRETMEZ."""
    from core.perception.names import block_geom_stats_for, classify_blocks, NameMap, refine_blocks_with_stats
    from core.perception.openings import block_door_candidates
    for name, kw, band in (("95 KAPI", dict(with_arc=True), (50.0, 260.0)),      # yaylı
                           ("95 KAPI", dict(width=600.0), (50.0, 260.0)),        # 6 m: bant dışı
                           ("DOLAP", {}, (50.0, 260.0))):                        # mobilya adı
        doc, msp = _door_block_doc(name, **kw)
        nm = NameMap(blocks=classify_blocks([b.name for b in doc.blocks], None))
        nm.block_stats = block_geom_stats_for(msp, 100.0, (50.0, 130.0))
        refine_blocks_with_stats(nm, nm.block_stats, (50.0, 130.0))
        assert block_door_candidates(msp, doc, (0, 0, 1000, 1000), nm, (50.0, 130.0), band) == [], name
