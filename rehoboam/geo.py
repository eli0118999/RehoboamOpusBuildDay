"""Shared geography: the ONE mapping from districts/places/subjects to compass bearings.

Bearings are degrees clockwise from north. Radius is a fraction of the plinth radius (0 = council
tower). The circle draws a subject at its bearing; the 3D world places it at (bearing, radius);
focal coordinates are derived from the same pair. Deterministic: no RNG, only stable hashes.
"""
import hashlib
import math

from . import config
from .schemas import Archive, Geo, ResidentState


def _h(*parts: str) -> float:
    """Stable 0-1 hash of strings."""
    d = hashlib.sha256("|".join(parts).encode()).digest()
    return int.from_bytes(d[:8], "big") / 2**64


def assign_district_arcs(districts) -> dict[str, tuple[float, float]]:
    order = sorted(districts, key=lambda d: (config.DISTRICT_BEARING.get(d.character, 0.0), d.district_id))
    n = max(len(order), 1)
    span = 360.0 / n
    first_centre = config.DISTRICT_BEARING.get(order[0].character, 0.0) if order else 0.0
    arcs = {}
    for i, d in enumerate(order):
        centre = (first_centre + i * span) % 360
        arcs[d.district_id] = ((centre - span / 2) % 360, (centre + span / 2) % 360)
    return arcs


def arc_span(arc: tuple[float, float]) -> float:
    return (arc[1] - arc[0]) % 360 or 360.0


def arc_point(arc: tuple[float, float], t: float) -> float:
    """Bearing at fraction t (0-1) through a clockwise arc."""
    return (arc[0] + arc_span(arc) * t) % 360


def bearing_in_arc(bearing: float, arc: tuple[float, float]) -> bool:
    return (bearing - arc[0]) % 360 <= arc_span(arc)


def place_polar(archive: Archive, arcs) -> dict[str, tuple[float, float]]:
    districts = {d.district_id: d for d in archive.city.districts}
    by_district: dict[str, list] = {}
    for lm in archive.city.landmarks:
        by_district.setdefault(lm.district_id, []).append(lm)
    out = {}
    for did, lms in by_district.items():
        arc = arcs.get(did, (0.0, 360.0))
        char = districts[did].character if did in districts else "residential"
        r0, r1 = config.DISTRICT_RADIUS.get(char, (0.4, 0.8))
        lms = sorted(lms, key=lambda l: l.place_id)
        for i, lm in enumerate(lms):
            if lm.kind == "council":
                out[lm.place_id] = (0.0, 0.0)
                continue
            t = (i + 0.5 + (_h(lm.place_id, "t") - 0.5) * 0.4) / len(lms)
            r = r0 + (r1 - r0) * _h(lm.place_id, "r")
            out[lm.place_id] = (round(arc_point(arc, 0.1 + 0.8 * t), 2), round(r, 3))
    return out


def resident_polar(archive: Archive, states: list[ResidentState], places) -> dict[str, tuple[float, float]]:
    arcs = assign_district_arcs(archive.city.districts)
    out = {}
    crowd: dict[str, int] = {}
    for st in sorted(states, key=lambda s: s.resident_id):
        if st.current_place and st.current_place in places:
            b, r = places[st.current_place]
            k = crowd.get(st.current_place, 0)
            crowd[st.current_place] = k + 1
            # fan subjects sharing a place around it so capsules don't overlap
            ang = k * 2.4
            b = (b + math.degrees(0.035 * math.sin(ang)) / max(r, 0.15)) % 360
            r = min(0.97, max(0.05, r + 0.035 * math.cos(ang) + 0.04))
        else:
            arc = arcs.get(st.current_district, (0.0, 360.0))
            b = arc_point(arc, 0.2 + 0.6 * _h(st.resident_id, "b"))
            r = 0.5 + 0.35 * _h(st.resident_id, "r")
        out[st.resident_id] = (round(b, 2), round(r, 3))
    return out


def coords(bearing: float, radius: float) -> str:
    rad = math.radians(bearing)
    lat = config.ORIGIN_LAT + radius * config.DEG_PER_UNIT_RADIUS * math.cos(rad)
    lon = config.ORIGIN_LON + radius * config.DEG_PER_UNIT_RADIUS * math.sin(rad) / math.cos(math.radians(lat))
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{abs(lat):.4f}° {ns}, {abs(lon):.4f}° {ew}"


def build_geo(archive: Archive, states: list[ResidentState]) -> Geo:
    arcs = assign_district_arcs(archive.city.districts)
    places = place_polar(archive, arcs)
    return Geo(origin_lat=config.ORIGIN_LAT, origin_lon=config.ORIGIN_LON, district_arcs=arcs,
               place_polar=places, resident_polar=resident_polar(archive, states, places))


def spread_label(arc_spread_deg: float, concentrated: bool) -> str:
    """Show's convention: concentrated events get coordinates only."""
    if concentrated:
        return ""
    if arc_spread_deg >= 1:
        v = round(arc_spread_deg, 1)
        return f"{v:g} ARC DEGREE{'S' if v != 1 else ''}"
    minutes = arc_spread_deg * 60
    if minutes >= 1:
        return f"{round(minutes, 1):g} ARC MINUTES"
    return f"{round(minutes * 60, 1):g} ARC SECONDS"
