# core/devices.py
"""M2: cihaz yerleşimi (aydınlatma, anahtar, priz, beyaz eşya).

Temel (poligonsuz): GÜVENİLİR verilere dayanır —
  - oda ETİKET konumu (DXF metninden, odanın içinde garanti nokta)
  - gerçek DUVAR parçaları (floor.walls) → cihazlar duvara SNAP edilir, yüzmez
  - kapı MENTEŞELERİ (floor.doors)
Saf fonksiyon (DXF okumaz); deterministiktir.
"""
from __future__ import annotations
import math

from core.ir import BuildingIR, Floor, Room, Door, Device

# Oda ismi -> kanonik tip
_WET = {"banyo", "wc", "tuvalet", "mutfak"}           # kapaklı priz
_SWITCH_OUTSIDE = {"banyo", "wc", "tuvalet"}           # anahtar kapı dışında
_NO_SOCKET = {"merdiven"}                              # salt geçiş → priz yok
_COVERED_EXTRA = {"balkon"}                            # dış mekân → kapaklı
# Sirkülasyon (geçiş) odaları — ıslak hacim anahtarı buraya (girişe) bakar
_CIRCULATION = {"hol", "kat holü", "kat holu", "antre", "giriş", "giris",
                "koridor", "sahanlık", "sahanlik"}

# Yerleşim parametreleri (1cm/birim)
_BESIDE = 32.0        # kapı yanında duvar boyu kayma
_OFF_WALL = 8.0       # duvardan oda içine küçük itme (sembol görünürlüğü)
_SOCKET_PROBE = 140.0 # yan-duvar prizi için karşı duvara sonda mesafesi
_DOOR_NEAR = 90.0     # kapının duvara snap sonrası geçerli sayılma eşiği


def _norm(name: str) -> str:
    return (name or "").strip().casefold()


def is_wet(room_name: str) -> bool:
    return _norm(room_name) in _WET


def switch_outside(room_name: str) -> bool:
    return _norm(room_name) in _SWITCH_OUTSIDE


def _covered(room_name: str) -> bool:
    return is_wet(room_name) or _norm(room_name) in _COVERED_EXTRA


def _ref(room: Room):
    """Odanın güvenilir iç referans noktası: etiket konumu."""
    return room.label_xy


# ---- duvar geometrisi yardımcıları -------------------------------------------

def _proj(p, a, b):
    """p noktasının [a,b] parçası üzerindeki en yakın noktası."""
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy or 1.0
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return (ax + t * dx, ay + t * dy)


def _nearest_wall(p, walls):
    """p'ye en yakın duvar: (ayak_noktası, a, b, uzaklık) veya None."""
    best, bd = None, float("inf")
    for a, b in walls:
        f = _proj(p, a, b)
        d = math.hypot(f[0] - p[0], f[1] - p[1])
        if d < bd:
            bd, best = d, (f, a, b)
    if best is None:
        return None
    return best[0], best[1], best[2], bd


def _ray_hit(ref, u, walls):
    """ref'ten u yönünde ilk duvar kesişimi (nokta, uzaklık) veya None."""
    ox, oy = ref; ux, uy = u
    best, bt = None, float("inf")
    for (a, b) in walls:
        ax, ay = a; ex, ey = b[0] - a[0], b[1] - a[1]
        det = ex * uy - ux * ey
        if abs(det) < 1e-9:
            continue
        rx, ry = ax - ox, ay - oy
        t = (rx * (-ey) + ex * ry) / det   # ray parametresi (mesafe, |u|=1)
        s = (ux * ry - uy * rx) / det       # segment parametresi
        if t > 1.0 and -0.02 <= s <= 1.02 and t < bt:
            bt, best = t, (ox + ux * t, oy + uy * t)
    if best is None:
        return None
    return best, bt


_DIRS4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]      # kardinal: oda çevresi sağlam
_MAX_RAY = 460.0                                  # bundan uzak = kapıdan kaçak


def _room_wall_points(ref, walls, dirs=_DIRS4, max_dist=_MAX_RAY):
    """Etiketten ışınlarla odayı ÇEVRELEYEN duvar noktaları (kendi duvarları).

    Kapı boşluğundan kaçıp uzak duvara çarpan ışınlar max_dist ile elenir.
    """
    pts = []
    for u in dirs:
        hit = _ray_hit(ref, u, walls)
        if hit is not None and hit[1] <= max_dist:
            pts.append(hit[0])                 # kesişim noktası
    return pts


def _dist_to(p, segs):
    """p'nin segment listesine en kısa mesafesi (boş liste → sonsuz)."""
    best = float("inf")
    for a, b in segs:
        f = _proj(p, a, b)
        d = math.hypot(f[0] - p[0], f[1] - p[1])
        if d < best:
            best = d
    return best


def _avoid_windows(xy, floor, clearance=35.0, step=22.0, n=10):
    """Cihaz pencereye denk geldiyse duvar boyunca kaydırıp katı duvara taşı."""
    if not floor.windows or _dist_to(xy, floor.windows) >= clearance:
        return xy
    nw = _nearest_wall(xy, floor.walls)
    if nw is None:
        return xy
    foot, a, b, _ = nw
    L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    for s in range(1, n + 1):
        for sign in (1.0, -1.0):
            c = (xy[0] + sign * s * step * ux, xy[1] + sign * s * step * uy)
            nw2 = _nearest_wall(c, floor.walls)
            if (_dist_to(c, floor.windows) >= clearance
                    and nw2 is not None and nw2[3] <= 25.0):
                return c
    return xy                                       # katı yer bulunamadı


def _on_wall(anchor, walls, ref, *, beside=0.0, off=_OFF_WALL, outward=False):
    """anchor'ı en yakın duvara snap et; duvar boyu `beside`, duvardan `off` ittir.

    outward=False → oda içine (ref'e doğru); True → dışarı (ref'ten uzağa, ıslak).
    """
    nw = _nearest_wall(anchor, walls)
    if nw is None:
        return anchor
    foot, a, b, _ = nw
    L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L      # duvar boyu birim
    nx, ny = -uy, ux                                    # duvar normali
    # normal yönünü ref'e (oda içine) çevir
    if (ref[0] - foot[0]) * nx + (ref[1] - foot[1]) * ny < 0:
        nx, ny = -nx, -ny
    # duvar boyu yön: ref'e yakın taraf (içeri) ya da uzak (dışarı)
    c1 = (foot[0] + ux * beside, foot[1] + uy * beside)
    c2 = (foot[0] - ux * beside, foot[1] - uy * beside)
    d1 = math.hypot(c1[0] - ref[0], c1[1] - ref[1])
    d2 = math.hypot(c2[0] - ref[0], c2[1] - ref[1])
    pos = c1 if ((d1 < d2) != outward) else c2
    s = -1.0 if outward else 1.0
    return (pos[0] + s * nx * off, pos[1] + s * ny * off)


# ---- kapı ↔ oda eşleşmesi (etiket tabanlı) -----------------------------------

def _room_doors(room: Room, floor: Floor):
    """Odaya ait kapılar: M1'de açılış yayı yönüyle atanmış door.room_name eşleşmesi."""
    return [d for d in floor.doors if d.room_name == room.raw_name]


def _entrance_door(room: Room, floor: Floor):
    """Odanın giriş kapısı: ait kapılardan etikete en yakını (yoksa None)."""
    cands = _room_doors(room, floor)
    if not cands:
        return None
    ref = _ref(room)
    return min(cands, key=lambda d: math.hypot(d.xy[0] - ref[0], d.xy[1] - ref[1]))


# ---- yerleştiriciler ---------------------------------------------------------

def place_lighting(floor: Floor) -> None:
    """Her odanın merkezine 1 aydınlatma armatürü."""
    for room in floor.rooms:
        if room.center is None:
            continue
        floor.devices.append(Device(
            kind="light", xy=room.center, room_name=room.raw_name,
            circuit="aydinlatma"))


def _strike_side(door, ref, outward):
    """Anahtar = KİLİT sövesi tarafı, MENTEŞE DUVARI üstünde (dik duvar yoksa fallback)."""
    hx, hy = door.xy
    sx, sy = door.strike_xy
    ax, ay = sx - hx, sy - hy
    n = math.hypot(ax, ay) or 1.0
    ux, uy = ax / n, ay / n
    bx, by = sx + ux * 18.0, sy + uy * 18.0
    nx, ny = -uy, ux
    if (ref[0] - bx) * nx + (ref[1] - by) * ny < 0:
        nx, ny = -nx, -ny
    if outward:
        nx, ny = -nx, -ny
    return (bx + nx * _OFF_WALL, by + ny * _OFF_WALL)


def _switch_open_side(door, ref, walls, outward):
    """Anahtar = kapının AÇILDIĞI yöndeki dik komşu duvarda (referans konvansiyonu).

    Kanat açıkken menteşe duvarına DİK, oda içine doğru uzanır; anahtar o yöndeki
    duvara konur (kilit tarafı). Kapı genişliği = |menteşe-kilit|.
    """
    hx, hy = door.xy
    sx, sy = door.strike_xy
    ax, ay = sx - hx, sy - hy
    w = math.hypot(ax, ay) or 60.0                  # kapı genişliği = menteşe→kilit
    ux, uy = ax / w, ay / w                          # menteşe duvarı yönü
    nx, ny = -uy, ux                                 # duvara dik (açılış yönü adayı)
    if (ref[0] - hx) * nx + (ref[1] - hy) * ny < 0:  # oda içine çevir
        nx, ny = -nx, -ny
    if outward:                                      # ıslak hacim → dışarı
        nx, ny = -nx, -ny
    # açık kanat ucu: menteşeden dik yönde ~kapı genişliği kadar; oraya en yakın
    # (dik) duvara snap → anahtar o duvarda
    tip = (hx + nx * w, hy + ny * w)
    return _on_wall(tip, walls, ref, beside=0.0, outward=outward)


def _wet_switch(door, floor, room):
    """Islak hacim (banyo/WC) anahtarı: DIŞARIDA, girişin yapıldığı sirkülasyon
    odasına (Hol/Kat Holü) doğru duvarda — odaya girerken kullanılır."""
    circ = [r for r in floor.rooms
            if _norm(r.raw_name) in _CIRCULATION and r is not room]
    target = min(circ or floor.rooms,
                 key=lambda r: math.hypot(r.label_xy[0] - door.xy[0],
                                          r.label_xy[1] - door.xy[1]))
    tx, ty = target.label_xy
    dx, dy = tx - door.xy[0], ty - door.xy[1]
    n = math.hypot(dx, dy) or 1.0
    pre = (door.xy[0] + dx / n * 55.0, door.xy[1] + dy / n * 55.0)
    return _on_wall(pre, floor.walls, (tx, ty))     # sirkülasyon tarafı duvara snap


def place_switches(floor: Floor) -> None:
    """Oda başına 1 anahtar; giriş kapısının KİLİT tarafında duvarda. Banyo/WC dışarıda."""
    for room in floor.rooms:
        ref = _ref(room)
        door = _entrance_door(room, floor)
        outward = switch_outside(room.raw_name)
        if door is not None and door.strike_xy is not None and outward:
            # ıslak hacim → dışarıda, sirkülasyon (Hol) tarafında
            xy = _wet_switch(door, floor, room)
            label = None
        elif door is not None and door.strike_xy is not None:
            # anahtar = kapının açıldığı yöndeki dik komşu duvarda (kilit tarafı)
            xy = _switch_open_side(door, ref, floor.walls, outward)
            label = None
        elif door is not None:
            xy = _on_wall(door.xy, floor.walls, ref, beside=_BESIDE, outward=outward)
            label = None
        else:
            # kapı yok → etiketin en yakın duvarına, işaretli
            xy = _on_wall(ref, floor.walls, ref, beside=0.0)
            label = "FALLBACK(kapı yok)"
        xy = _avoid_windows(xy, floor)             # pencereye denk gelirse kaydır
        floor.devices.append(Device(
            kind="switch", xy=xy, room_name=room.raw_name,
            circuit="aydinlatma", label=label))


def place_sockets(floor: Floor) -> None:
    """Oda başına 2 priz: biri kapı yanı, biri karşı duvarda. Islak/dış kapaklı."""
    for room in floor.rooms:
        if _norm(room.raw_name) in _NO_SOCKET:
            continue
        ref = _ref(room)
        cov = _covered(room.raw_name)
        door = _entrance_door(room, floor)

        if door is not None:
            # 1) kapı yanı priz — kapının diğer yanına (anahtarla çakışmasın)
            s1 = _on_wall(door.xy, floor.walls, ref, beside=-_BESIDE)
            label = None
        else:
            s1 = _on_wall(ref, floor.walls, ref, beside=_BESIDE)
            label = "FALLBACK(kapı yok)"

        # 2) karşı duvar prizi: s1'i oda merkezine göre YANSIT → karşı duvara snap.
        # (Işın-kasti kapı/açıklıktan kaçabiliyordu; yansıma oda içinde kalır, kaçmaz.)
        refl = (2 * ref[0] - s1[0], 2 * ref[1] - s1[1])
        s2 = _on_wall(refl, floor.walls, ref)

        for xy in (s1, s2):
            xy = _avoid_windows(xy, floor)          # pencereye denk gelirse kaydır
            floor.devices.append(Device(
                kind="socket", xy=xy, room_name=room.raw_name,
                circuit="priz", covered=cov, label=label))


# Beyaz eşyalar: (etiket, ev sahibi oda) — her biri AYRI linye + KAPAKLI priz ile
# sonlanır (su koruması). Konum: tespit edilebilirse (ocak) gerçek yer, yoksa
# ev sahibi odanın duvarına sezgisel.
_APPLIANCES = [
    ("Ocak/Fırın", "mutfak"),
    ("Bulaşık Mak.", "mutfak"),
    ("Buzdolabı", "mutfak"),
    ("Çamaşır Mak.", "banyo"),
    ("Kombi", "balkon"),
    ("Klima", "salon"),
]


def _distinct(pts, min_sep=45.0):
    out = []
    for p in pts:
        if all(math.hypot(p[0] - g[0], p[1] - g[1]) > min_sep for g in out):
            out.append(p)
    return out


def place_appliances(floor: Floor) -> None:
    """Beyaz eşyalar: her biri AYRI linye + KAPAKLI priz. Tespit edilen (ocak)
    gerçek yere; diğerleri ev sahibi odanın duvarına sezgisel."""
    by_room = {}
    for label, host in _APPLIANCES:
        by_room.setdefault(host, []).append(label)
    for room in floor.rooms:
        items = by_room.get(_norm(room.raw_name))
        if not items:
            continue
        ref = _ref(room)
        wps = sorted(_room_wall_points(ref, floor.walls),
                     key=lambda p: math.hypot(p[0] - ref[0], p[1] - ref[1]))
        feet = _distinct(wps)
        i = 0
        for label in items:
            if label in floor.appliance_pts:        # tespit edilmiş (ör. ocak)
                xy = _on_wall(floor.appliance_pts[label], floor.walls, ref)
            elif feet:
                xy = _on_wall(feet[i % len(feet)], floor.walls, ref)
                i += 1
            else:
                xy = ref
            xy = _avoid_windows(xy, floor)
            floor.devices.append(Device(
                kind="appliance", xy=xy, room_name=room.raw_name,
                circuit=label, covered=True, label=label))   # hepsi kapaklı


# Apartman girişi = ortak alana (merdiven sahanlığı) bağlanan eşik
_ENTRY_LANDING = {"kat holü", "kat holu", "merdiven", "sahanlık", "sahanlik",
                  "antre", "giriş", "giris"}


def place_panel(floor: Floor) -> None:
    """1 pano (sigorta kutusu): apartman GİRİŞİNE yakın, iç tarafta duvarda.

    Giriş kapısı = ortak alana (Kat Holü/merdiven sahanlığı) en yakın kapı. Pano
    o kapının iç (hizmet ettiği oda) tarafında duvara konur.
    """
    if not floor.doors:
        return
    landing = [r for r in floor.rooms if _norm(r.raw_name) in _ENTRY_LANDING]
    refs = landing or floor.rooms
    ent = min(floor.doors,
              key=lambda d: min(math.hypot(d.xy[0] - r.label_xy[0],
                                           d.xy[1] - r.label_xy[1]) for r in refs))
    # panonun konacağı iç oda = kapının hizmet ettiği oda (yay yönü)
    served = next((r for r in floor.rooms if r.raw_name == ent.room_name), None)
    iref = (served or min(floor.rooms, key=lambda r: math.hypot(
        r.label_xy[0] - ent.xy[0], r.label_xy[1] - ent.xy[1]))).label_xy
    xy = _on_wall(ent.xy, floor.walls, iref, beside=45)
    floor.devices.append(Device(kind="panel", xy=xy,
                                room_name=ent.room_name, circuit="pano", label="Pano"))


def place_junctions(floor: Floor) -> None:
    """Aydınlatma linyesi için oda başına 1 buat (tavan birleşim kutusu, armatür yanı).

    Topoloji: pano → buat → armatür + anahtar (anahtar buat üzerinden aydınlatmada).
    """
    for room in floor.rooms:
        if room.center is None:
            continue
        floor.devices.append(Device(
            kind="junction", xy=(room.center[0], room.center[1] + 18),
            room_name=room.raw_name, circuit="aydinlatma", label="buat"))


def place_devices(building: BuildingIR) -> BuildingIR:
    """M2 giriş noktası — aydınlatma + anahtar + priz + beyaz eşya."""
    for floor in building.floors:
        floor.devices = []
        place_lighting(floor)
        place_switches(floor)
        place_sockets(floor)
        place_appliances(floor)
    return building


def place_m3_nodes(building: BuildingIR) -> BuildingIR:
    """M3 başlangıcı: pano + buatlar (linye routing'den önce düğümler)."""
    for floor in building.floors:
        place_panel(floor)
        place_junctions(floor)
    return building
