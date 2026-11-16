#!/usr/bin/env python3
"""Extract NOAA 1991-2020 frost normals and match them to large US cities.

Reads the local NCEI by-station archive, the Census place gazetteer and
population estimates, and the 2023 USDA/PRISM ZIP zone tables. Writes a
compact cache under _build/cache so pages can be rebuilt without refetching.

Nothing in this script invents a frost date. A station contributes a date
only when NOAA published one. Special values -6666 (threshold too rare to
compute) and -4444 (year-round risk) are kept as flags, not turned into dates.
"""
import csv, io, json, math, os, re, tarfile, zipfile
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "_build", "cache")
SRC = os.environ.get("WHICHFROST_SRC", "/tmp/whichfrost-data")
os.makedirs(CACHE, exist_ok=True)

RETRIEVED = "2026-11-16"
NORMALS_TAR = os.path.join(SRC, "normals.tar.gz")
INVENTORY = os.environ.get("WHICHFROST_INVENTORY", "/tmp/inventory_30yr.txt")

US = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
FIPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT",
    "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL",
    "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
    "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE",
    "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI", "56": "WY",
}

# NOAA agricultural normals we keep. Names are the published element IDs.
THRESHOLDS = (28, 32, 36)
PROBS = (10, 50, 90)
ELEMENTS = []
for season, code in (("lst", "PRBLST"), ("fst", "PRBFST")):
    for t in THRESHOLDS:
        for p in PROBS:
            ELEMENTS.append(f"ANN-TMIN-{code}-T{t:02d}FP{p:02d}")
ELEMENTS.append("ANN-TMIN-PRBGSL-T32FP50")

# Nearest station with a published 32 F product. Farther than this is not
# "this city's" station, so the city is skipped rather than assigned a date.
MAX_MILES = 50.0
# Minimum population. Lowered automatically if the matched set is under 300.
POP_FLOOR = 100000
POP_FLOOR_MIN = 70000

def haversine(lat1, lon1, lat2, lon2):
    r = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

def slug(name):
    s = name.lower().replace("&", " and ")
    s = s.replace(".", "").replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s

def load_inventory():
    """GHCN id -> state code, for the 50 states and DC."""
    out = {}
    rx = re.compile(r"^(\S{11})\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+\S+\s+([A-Z]{2})\s+")
    for line in open(INVENTORY, encoding="latin1"):
        m = rx.match(line)
        if not m:
            continue
        sid, lat, lon, st = m.group(1), float(m.group(2)), float(m.group(3)), m.group(4)
        if st in US:
            out[sid] = st
    return out

def parse_value(raw):
    raw = (raw or "").strip()
    if raw == "":
        return None
    if raw in ("-6666", "-4444", "-6666.0", "-4444.0"):
        return raw.split(".")[0]
    return raw

def extract_stations(us_ids):
    stations = {}
    tar = tarfile.open(NORMALS_TAR, "r:gz")
    n = 0
    for member in tar:
        if not member.name.endswith(".csv"):
            continue
        sid = os.path.basename(member.name)[:-4]
        if sid not in us_ids:
            continue
        f = tar.extractfile(member)
        if f is None:
            continue
        text = f.read().decode("latin1")
        row = next(csv.reader(io.StringIO(text)))
        # header is the same layout; read it from this file
        # The file is one header + one data row. Re-read properly.
        reader = csv.reader(io.StringIO(text))
        header = next(reader)
        try:
            data = next(reader)
        except StopIteration:
            continue
        idx = {h: i for i, h in enumerate(header)}
        def col(name):
            i = idx.get(name)
            if i is None or i >= len(data):
                return None
            return parse_value(data[i])
        dates = {}
        meta = {}
        any_product = False
        for el in ELEMENTS:
            val = col(el)
            if val is None:
                continue
            key = el.replace("ANN-TMIN-", "").lower()
            dates[key] = val
            if val in ("-6666", "-4444") or re.match(r"\d{2}/\d{2}", val):
                any_product = True
            i = idx.get(el)
            if i is not None and i + 3 < len(data):
                years = (data[i + 3] or "").strip()
                comp = (data[i + 2] or "").strip()
                flag = (data[i + 1] or "").strip()
                if years or comp or flag:
                    meta[key] = {"years": years, "comp": comp, "flag": flag}
        if not any_product:
            continue
        try:
            lat = float(data[idx["LATITUDE"]])
            lon = float(data[idx["LONGITUDE"]])
            elev = float(data[idx["ELEVATION"]])
        except (KeyError, ValueError):
            continue
        name = (data[idx["NAME"]] or "").strip()
        stations[sid] = {
            "id": sid,
            "name": name,
            "st": us_ids[sid],
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "elev_m": round(elev, 1),
            "dates": dates,
            "meta": meta,
        }
        n += 1
        if n % 1000 == 0:
            print("stations", n, flush=True)
    tar.close()
    print("stations with a  frost product", len(stations), flush=True)
    return stations

def load_places():
    z = zipfile.ZipFile(os.path.join(SRC, "places.zip"))
    name = z.namelist()[0]
    raw = z.read(name).decode("latin1").splitlines()
    header = [h.strip() for h in raw[0].split("\t")]
    # GEOID, INTPTLAT, INTPTLONG, NAME, USPS
    ig = header.index("GEOID")
    ila = header.index("INTPTLAT")
    ilo = header.index("INTPTLONG")
    ina = header.index("NAME")
    ist = header.index("USPS")
    out = {}
    for line in raw[1:]:
        p = line.split("\t")
        if len(p) <= ilo:
            continue
        st = p[ist].strip()
        if st not in US:
            continue
        try:
            lat, lon = float(p[ila]), float(p[ilo])
        except ValueError:
            continue
        out[p[ig].strip()] = {"name": p[ina].strip(), "st": st, "lat": lat, "lon": lon}
    return out

def load_population():
    """Incorporated places and DC, 2024 estimate."""
    pops = {}
    with open(os.path.join(SRC, "sub-est2024.csv"), encoding="latin1", newline="") as f:
        for row in csv.DictReader(f):
            if row["SUMLEV"] not in ("162", "170", "157"):
                continue
            # 157 is county subdivisions (New England towns). Keep only if we
            # later need them. Default: incorporated places (162) and
            # consolidated cities (170). DC Washington is SUMLEV 157? handled below.
            if row["SUMLEV"] == "157":
                continue
            st = FIPS.get(row["STATE"])
            if not st:
                continue
            geoid = row["STATE"].zfill(2) + row["PLACE"].zfill(5)
            try:
                pop = int(row["POPESTIMATE2024"])
            except ValueError:
                continue
            name = re.sub(r"\s+(city|town|village|municipality|borough|CDP)$", "", row["NAME"], flags=re.I).strip()
            # "city (balance)" leftovers
            name = re.sub(r"\s+\(balance\)$", "", name, flags=re.I).strip()
            pops[geoid] = {"pop": pop, "name": name, "st": st, "sumlev": row["SUMLEV"]}
    # Washington, DC is often a county-equivalent, not a place. Pull it if present.
    with open(os.path.join(SRC, "sub-est2024.csv"), encoding="latin1", newline="") as f:
        for row in csv.DictReader(f):
            if row["STATE"] == "11" and row["NAME"].lower().startswith("washington") and row["SUMLEV"] in ("157", "061", "050", "162"):
                print("DC row", row["SUMLEV"], row["NAME"], row["POPESTIMATE2024"])
    return pops

def load_zones():
    zones = {}
    for fn in ("phzm_us.csv", "phzm_ak.csv", "phzm_hi.csv"):
        with open(os.path.join(SRC, fn), encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                zc = row["zipcode"].strip().zfill(5)
                zones[zc] = {"zone": row["zone"].strip().lower(), "trange": row["trange"].strip(), "title": row["zonetitle"].strip()}
    z = zipfile.ZipFile(os.path.join(SRC, "zcta.zip"))
    raw = z.read(z.namelist()[0]).decode("latin1").splitlines()
    header = [h.strip() for h in raw[0].split("\t")]
    ig, ila, ilo = header.index("GEOID"), header.index("INTPTLAT"), header.index("INTPTLONG")
    pts = []
    for line in raw[1:]:
        p = line.split("\t")
        if len(p) <= ilo:
            continue
        zc = p[ig].strip().zfill(5)
        if zc not in zones:
            continue
        try:
            lat, lon = float(p[ila]), float(p[ilo])
        except ValueError:
            continue
        pts.append((lat, lon, zc))
    print("zone zips with centroids", len(pts), "zone rows", len(zones))
    return zones, pts

def nearest_station(lat, lon, stations, grid):
    """Grid is a dict of (ilat, ilon) -> list of stations, 1-degree cells."""
    best = None
    best_d = 1e9
    # search expanding rings of 1-degree cells. 1 deg lat ~ 69 miles.
    base_i, base_j = int(math.floor(lat)), int(math.floor(lon))
    for rad in range(0, 4):
        for i in range(base_i - rad, base_i + rad + 1):
            for j in range(base_j - rad, base_j + rad + 1):
                if rad and abs(i - base_i) != rad and abs(j - base_j) != rad:
                    continue
                for s in grid.get((i, j), ()):
                    d = haversine(lat, lon, s["lat"], s["lon"])
                    if d < best_d:
                        best_d = d
                        best = s
        if best is not None and best_d <= MAX_MILES:
            # a farther cell could still be closer near a corner; 1 more ring
            # is checked by continuing only if best is inside the current radius
            # in miles. Conservative: if best_d + 70 < rad*69, stop.
            if best_d + 50 < rad * 60:
                break
    return best, best_d

def nearest_zip(lat, lon, pts):
    # pts is large (~30k). A coarse grid keeps this fast.
    best = None
    best_d = 1e9
    # built by caller as grid; here pts is the grid dict
    base_i, base_j = int(math.floor(lat * 2)), int(math.floor(lon * 2))  # 0.5 deg
    for rad in range(0, 6):
        found = False
        for i in range(base_i - rad, base_i + rad + 1):
            for j in range(base_j - rad, base_j + rad + 1):
                if rad and abs(i - base_i) != rad and abs(j - base_j) != rad:
                    continue
                for lat2, lon2, zc in pts.get((i, j), ()):
                    d = haversine(lat, lon, lat2, lon2)
                    if d < best_d:
                        best_d = d
                        best = zc
                        found = True
        if best is not None and best_d < 15 and rad >= 1:
            break
    return best, best_d

def main():
    us_ids = load_inventory()
    print("inventory US ids", len(us_ids))
    stations = extract_stations(us_ids)
    places = load_places()
    print("places", len(places))
    pops = load_population()
    print("pop rows", len(pops))
    zones, zpts = load_zones()
    zgrid = defaultdict(list)
    for lat, lon, zc in zpts:
        zgrid[(int(math.floor(lat * 2)), int(math.floor(lon * 2)))].append((lat, lon, zc))
    sgrid = defaultdict(list)
    slist = list(stations.values())
    for s in slist:
        sgrid[(int(math.floor(s["lat"])), int(math.floor(s["lon"])))].append(s)

    candidates = []
    for geoid, pop in pops.items():
        place = places.get(geoid)
        if not place:
            continue
        if pop["pop"] < POP_FLOOR_MIN:
            continue
        candidates.append({
            "geoid": geoid,
            "name": pop["name"] or place["name"],
            "st": pop["st"],
            "pop": pop["pop"],
            "lat": place["lat"],
            "lon": place["lon"],
        })
    candidates.sort(key=lambda c: -c["pop"])
    print("candidates >=", POP_FLOOR_MIN, len(candidates))

    matched = []
    skipped = []
    for c in candidates:
        stn, dist = nearest_station(c["lat"], c["lon"], stations, sgrid)
        rec = dict(c)
        rec["miles"] = round(dist, 1) if stn else None
        rec["station"] = stn["id"] if stn else None
        if not stn or dist > MAX_MILES:
            skipped.append(rec)
            continue
        # A published 32 F spring or fall date, or an official special value.
        d = stn["dates"]
        has32 = any(d.get(k) for k in (
            "prblst-t32fp50", "prbfst-t32fp50", "prblst-t32fp90", "prbfst-t32fp90",
            "prblst-t32fp10", "prbfst-t32fp10"))
        if not has32:
            skipped.append(rec)
            continue
        zc, zd = nearest_zip(c["lat"], c["lon"], zgrid)
        if zc and zd <= 30:
            rec["zip"] = zc
            rec["zone"] = zones[zc]["zone"]
            rec["zone_range"] = zones[zc]["trange"]
            rec["zone_miles"] = round(zd, 1)
        else:
            rec["zip"] = None
            rec["zone"] = None
            rec["zone_range"] = None
            rec["zone_miles"] = round(zd, 1) if zc else None
        matched.append(rec)

    # Keep every match at or above POP_FLOOR. If that is under 300, take the
    # largest matches down to POP_FLOOR_MIN.
    top = [m for m in matched if m["pop"] >= POP_FLOOR]
    floor_used = POP_FLOOR
    if len(top) < 300:
        top = matched[:]  # already limited to POP_FLOOR_MIN
        floor_used = POP_FLOOR_MIN
    # Unique path slugs inside a state. Prefer the larger population.
    used = set()
    cities = []
    for m in sorted(top, key=lambda x: -x["pop"]):
        base = slug(m["name"])
        path_slug = base
        n = 2
        while (m["st"], path_slug) in used:
            path_slug = f"{base}-{n}"
            n += 1
        used.add((m["st"], path_slug))
        m["slug"] = path_slug
        cities.append(m)

    # Stations actually cited.
    cited = {c["station"] for c in cities}
    station_out = {sid: stations[sid] for sid in cited}

    # Distance report
    miles = sorted(c["miles"] for c in cities)
    print("MATCHED published", len(cities), "floor", floor_used)
    if miles:
        print("miles min/median/p90/max", miles[0], miles[len(miles)//2], miles[int(len(miles)*0.9)], miles[-1])
    print("skipped over cap or no product (among candidates)", len(skipped))
    far = [s for s in skipped if s["pop"] >= floor_used and (s["miles"] or 999) > MAX_MILES]
    far.sort(key=lambda s: -s["pop"])
    print("largest skipped:")
    for s in far[:25]:
        print(f"  {s['name']}, {s['st']} pop {s['pop']} miles {s['miles']} station {s['station']}")
    nozone = sum(1 for c in cities if not c["zone"])
    print("cities missing a zone", nozone)

    # Required first-20 check
    need = [
        ("TX", "austin"), ("CO", "denver"), ("GA", "atlanta"), ("IL", "chicago"),
        ("MN", "minneapolis"), ("OR", "portland"), ("WA", "seattle"), ("NY", "new-york"),
        ("MA", "boston"), ("PA", "philadelphia"), ("NC", "raleigh"), ("TN", "nashville"),
        ("MO", "kansas-city"), ("OH", "columbus"), ("UT", "salt-lake-city"),
        ("AZ", "phoenix"), ("TX", "dallas"), ("CA", "sacramento"), ("MI", "detroit"),
    ]
    have = {(c["st"], c["slug"]) for c in cities}
    for key in need:
        print("NEED", key, "OK" if key in have else "MISSING")

    meta = {
        "retrieved": RETRIEVED,
        "normals": "NOAA NCEI U.S. Climate Normals 1991-2020, annual/seasonal, v1.0.1 (file c20230404)",
        "normals_url": "https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals",
        "dataset": "https://www.ncei.noaa.gov/data/normals-annualseasonal/1991-2020/",
        "methodology": "https://www.ncei.noaa.gov/data/normals-annualseasonal/1991-2020/doc/Normals_Calculation_Methodology_2020.pdf",
        "inventory": "https://www.ncei.noaa.gov/data/normals-annualseasonal/1991-2020/doc/inventory_30yr.txt",
        "population": "U.S. Census Bureau, Population Estimates Program, sub-est2024.csv, POPESTIMATE2024, incorporated places",
        "population_url": "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/cities/totals/sub-est2024.csv",
        "gazetteer": "U.S. Census Bureau 2024 Gazetteer place and ZCTA national files",
        "zones": "2023 USDA Plant Hardiness Zone Map, ZIP code tables published by the PRISM Climate Group, Oregon State University",
        "zones_url": "https://planthardiness.ars.usda.gov/",
        "zones_data": "https://prism.oregonstate.edu/phzm/",
        "max_miles": MAX_MILES,
        "pop_floor": floor_used,
        "city_count": len(cities),
        "station_count": len(station_out),
    }
    json.dump(station_out, open(os.path.join(CACHE, "stations.json"), "w"), separators=(",", ":"))
    json.dump(cities, open(os.path.join(CACHE, "cities.json"), "w"), separators=(",", ":"))
    json.dump({"skipped_large": [
        {"name": s["name"], "st": s["st"], "pop": s["pop"], "miles": s["miles"], "station": s["station"]}
        for s in far[:40]
    ]}, open(os.path.join(CACHE, "skipped.json"), "w"), indent=2)
    json.dump(meta, open(os.path.join(CACHE, "retrieval.json"), "w"), indent=2)
    print("wrote cache", len(cities), "cities", len(station_out), "stations")

if __name__ == "__main__":
    main()
