#!/usr/bin/env python3
"""Build whichfrost.com. Paths are always root-relative. CNAME is always written.

  python3 _build/build.py            # noindex on every page (SITE_INDEXABLE in config.py)
  python3 _build/build.py --launch   # indexable, Cloudflare beacon, GA4 after consent

Then: python3 _build/check.py [--launch] && python3 _build/legal_gate.py check
"""
import json, os, sys, html, math, re, shutil
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (SITE_INDEXABLE, BRAND, DOMAIN, BASE_URL, PUBLISHED, PUBLISHED_H,
                    INDEXNOW_KEY, CF_BEACON_TOKEN, GA4_ID, CONTACT_EMAIL, US, ALIASES, NEIGHBORS, MONTHS,
                    GROWING_SEASON_PAGES_PUBLISHED, GROWING_SEASON_PAGES_PUBLISHED_H,
                    ZONE_REFRESH_PUBLISHED, ZONE_REFRESH_PUBLISHED_H,
                    LEGAL_UPDATED, LEGAL_UPDATED_H,
                    TOMATO_GUIDE_PUBLISHED, TOMATO_GUIDE_PUBLISHED_H, ADSENSE_PUB,
                    ANCHORAGE_REFRESH, ANCHORAGE_REFRESH_H,
                    HARD_FREEZE_GUIDE_PUBLISHED, HARD_FREEZE_GUIDE_PUBLISHED_H, FROST_HERO)
from planting import SOURCES, GA_SOURCE, GA_MONTHS, offset_rows

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "_build", "cache")
INDEXABLE = SITE_INDEXABLE or ("--launch" in sys.argv)
E = html.escape
SITEMAP = []

LOGO = ('<svg width="34" height="34" viewBox="0 0 64 64" aria-hidden="true" focusable="false">'
        '<rect width="64" height="64" rx="14" fill="#0b3954"/>'
        '<path d="M32 8v48M8 32h48M15 15l34 34M49 15L15 49" stroke="#e6f4f1" stroke-width="4" stroke-linecap="round"/>'
        '<circle cx="32" cy="32" r="5" fill="#ffb347"/></svg>')
LEGAL_LINE = ("© 2026 Joshua Israel Ventures LLC. All rights reserved. "
              "Which Frost is a trade name of Joshua Israel Ventures LLC, a Florida limited liability company.")
FOOT = ("Which Frost lists median last and first frost dates for U.S. cities from NOAA climate normals, "
        "with the USDA hardiness zone and a planting calendar only where a state extension page was transcribed. "
        "These are long term averages, not a forecast.")
NOAA_HOME = "https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals"
NOAA_METHOD = "https://www.ncei.noaa.gov/data/normals-annualseasonal/1991-2020/doc/Normals_Calculation_Methodology_2020.pdf"
NWS_FROST = "https://forecast.weather.gov/glossary.php?word=frost"
NWS_FREEZE = "https://forecast.weather.gov/glossary.php?word=Freeze"
NWS_COLD = "https://www.weather.gov/safety/cold-ww"
NWS_HAZ = "https://www.weather.gov/news/243009-cold-hazard-simplification"
NWS_SCN = "https://www.weather.gov/media/notification/pdf_2023_24/scn23-44_public_program_text_products_freeze_cold_aab.pdf"
NWS_RAH = "https://www.weather.gov/rah/FrostFreezemaps"
UAF_GARLIC = "https://www.uaf.edu/ces/publications/database/gardening/garlic.php"
CENSUS_POP = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/cities/totals/sub-est2024.csv"
PHZM = "https://planthardiness.ars.usda.gov/"
PRISM = "https://prism.oregonstate.edu/phzm/"

COMP = {
    "S": "Standard. NOAA had 24 or more years, and could fill missing months from nearby stations",
    "R": "Representative. NOAA had at least 10 years, and could fill missing months from nearby stations",
    "P": "Provisional. NOAA had at least 10 years, and could not fill missing months",
    "E": "Estimated. NOAA had at least 2 years, and estimated the normal from nearby stations that have a standard record",
}

def u(path):
    return path if path == "/" else path

def url(path):
    if path == "/":
        return BASE_URL
    rel = path.strip("/")
    if "." in rel.split("/")[-1]:
        return BASE_URL + rel
    return BASE_URL + rel + "/"

def clip(s, n=155):
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= n:
        return s
    cut = s[:n - 1].rsplit(" ", 1)[0].rstrip(".,;:")
    if len(cut) < 40:
        cut = s[:n - 1].rstrip()
    return cut + "."

def haversine(lat1, lon1, lat2, lon2):
    r = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

def miles_text(m):
    if m is None:
        return "an unknown distance"
    if m < 0.5:
        return "under 1 mile"
    return f"{m:.1f} miles"

def commas(n):
    return f"{n:,}"

def station_label(name):
    keep = {"AP", "AFB", "WSO", "INTL", "NAS", "MUNI", "WSFO", "NWS", "COOP"}
    out = []
    for w in name.split():
        suffix = ""
        if w.endswith(","):
            suffix, w = ",", w[:-1]
        if w in keep or (len(w) <= 2 and w.isalpha()):
            out.append(w + suffix)
            continue
        parts = [p[:1].upper() + p[1:].lower() for p in w.split("-") if p]
        out.append("-".join(parts) + suffix)
    return " ".join(out)

def fmt_date(val):
    val = (val or "").strip()
    if not re.match(r"\d{2}/\d{2}$", val):
        return None
    month, day = int(val[:2]), int(val[3:])
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{MONTHS[month - 1]} {day}"

def cell(val):
    val = (val or "").strip()
    if val.startswith("-6666"):
        return "Too rare to compute"
    if val.startswith("-4444"):
        return "Year round risk"
    if val.startswith("-9999"):
        return "Not computed"
    pretty = fmt_date(val)
    return pretty or "Not published"

def gsl_days(val):
    val = (val or "").strip()
    if not val or val.startswith("-"):
        return None
    try:
        return int(round(float(val)))
    except ValueError:
        return None

def meta_sentence(meta):
    if not meta:
        return ""
    bits = []
    years = (meta.get("years") or "").strip()
    if years:
        bits.append(f"NOAA used {years} years for this element")
    flag = (meta.get("flag") or "").strip()
    if flag == "Y":
        bits.append("measurement flag Y means there were not enough values to compute it")
    elif flag == "V":
        bits.append("measurement flag V means year round frost risk, too cold to compute")
    comp = (meta.get("comp") or "").strip()
    if comp in COMP:
        bits.append("Completeness flag " + comp + ": " + COMP[comp])
    return ". ".join(b.rstrip(".") for b in bits) + ("." if bits else "")

def clean_output():
    keep = {".git", "_build", "assets", "favicon.svg", "README.md", ".gitignore", "_config.yml", ".nojekyll", "LAUNCH-NOTES.md", "indexnow.sh"}
    for name in os.listdir(ROOT):
        if name in keep:
            continue
        path = os.path.join(ROOT, name)
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

def disk_for(path):
    if path == "/":
        return os.path.join(ROOT, "index.html")
    folder = os.path.join(ROOT, path.strip("/"))
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "index.html")

def crumbs_html(crumbs):
    if not crumbs:
        return ""
    items = []
    for i, (href, name) in enumerate(crumbs):
        if i == len(crumbs) - 1:
            items.append(f'<li aria-current="page">{E(name)}</li>')
        else:
            items.append(f'<li><a href="{href}">{E(name)}</a></li>')
    return '<nav class="crumbs" aria-label="Breadcrumb"><ol>' + "".join(items) + "</ol></nav>"

def crumb_ld(crumbs):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": name, "item": url(href)}
        for i, (href, name) in enumerate(crumbs)]}

def faq_html(faqs):
    if not faqs:
        return ""
    body = "".join(f"<details><summary>{E(q)}</summary><p>{E(a)}</p></details>" for q, a in faqs)
    return f'<section class="faq" aria-labelledby="faq-h"><h2 id="faq-h">Frequently asked questions</h2>{body}</section>'

def faq_ld(faqs):
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]}

# Consent Mode v2 defaults stay denied. gtag.js is requested only from consent.js after Allow.
GA4_SNIPPET = """<script id="ga4-loader">
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('consent', 'default', {
  'ad_storage': 'denied',
  'ad_user_data': 'denied',
  'ad_personalization': 'denied',
  'analytics_storage': 'denied',
  'wait_for_update': 500
});
gtag('set', 'ads_data_redaction', true);
gtag('set', 'url_passthrough', true);
window.WF_GA4_ID = __GA4__;
window.wfLoadGA4 = function () {
  var id = window.WF_GA4_ID || '';
  if (!/^G-[A-Z0-9]+$/.test(id)) return;
  if (document.getElementById('ga4-gtag')) return;
  var s = document.createElement('script');
  s.id = 'ga4-gtag';
  s.async = true;
  s.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(id);
  document.head.appendChild(s);
  gtag('js', new Date());
  gtag('config', id);
};
</script>
<script src="/assets/consent.js?v=1" defer></script>"""

# AdSense low-value-content fix (20 Nov 2026): paths listed in _build/thin-noindex.txt
# get noindex,follow and stay out of the sitemap until they have real unique substance.
_THIN_NOINDEX = set()
try:
    import os as _os
    with open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "thin-noindex.txt"), encoding="utf-8") as _fh:
        _THIN_NOINDEX = {l.strip().strip("/") for l in _fh if l.strip() and not l.startswith("#")}
except FileNotFoundError:
    pass


def _is_thin(path):
    return str(path).strip("/") in _THIN_NOINDEX


def page(path, title, desc, body, crumbs=None, schemas=None, noindex=False, legal=False, nav_current=None, lastmod=None):
    if _is_thin(path):
        noindex = True
    title = re.sub(r"\s+", " ", title).strip()
    if len(title) >= 60:
        raise SystemExit(f"title {len(title)} >= 60: {title}")
    desc = clip(desc)
    canon = url(path)
    robots = "noindex, follow" if (noindex or not INDEXABLE) else "index, follow, max-image-preview:large"
    bits = schemas[:] if schemas else []
    if crumbs:
        bits.insert(0, crumb_ld(crumbs))
    if path == "/":
        bits.insert(0, {"@context": "https://schema.org", "@type": "WebSite", "name": BRAND, "url": BASE_URL,
                        "publisher": {"@type": "Organization", "name": BRAND, "url": BASE_URL, "logo": url("/logo.png")}})
        bits.insert(0, {"@context": "https://schema.org", "@type": "Organization", "name": BRAND, "url": BASE_URL,
                        "logo": url("/logo.png")})
    scripts = "".join('<script type="application/ld+json">' + json.dumps(b, ensure_ascii=False) + "</script>" for b in bits)
    if INDEXABLE:
        beacon = ("<!-- Cloudflare Web Analytics --><script defer src='https://static.cloudflareinsights.com/beacon.min.js' "
                  f"data-cf-beacon='{{\"token\": \"{CF_BEACON_TOKEN}\"}}'></script><!-- End Cloudflare Web Analytics -->")
        ga4 = GA4_SNIPPET.replace("__GA4__", json.dumps(GA4_ID))
        adsense = (f'<meta name="google-adsense-account" content="{ADSENSE_PUB}">'
                   f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE_PUB}" '
                   f'crossorigin="anonymous"></script>')
    else:
        beacon = "<!-- cf-beacon: added when SITE_INDEXABLE is true -->"
        ga4 = ""
        adsense = ""
    nav = [("Home", "/"), ("States", "/states/"), ("Zones", "/zones/"), ("Sources", "/methodology/")]
    nav_html = "".join(
        f'<a href="{href}"' + (' aria-current="page"' if nav_current == href else "") + f">{label}</a>"
        for label, href in nav)
    legal_html = f'<p class="legal-line">{E(LEGAL_LINE)}</p>' if legal else ""
    crumb = crumbs_html(crumbs)
    doc = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title><meta name="description" content="{E(desc)}"><link rel="canonical" href="{canon}">
<meta name="robots" content="{robots}">
<meta property="og:type" content="website"><meta property="og:site_name" content="{BRAND}"><meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{canon}"><meta property="og:image" content="{url("/og.png")}"><meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/assets/style.css?v=4">{adsense}{scripts}
</head><body><a class="skip" href="#main">Skip to content</a>
<header class="site"><div class="wrap"><a class="brand" href="/">{LOGO}<span>{BRAND}</span></a><nav class="main" aria-label="Main">{nav_html}</nav></div></header>
<main id="main" class="wrap">{crumb}{body}{legal_html}<!-- ad-slot: below-content (reserved; no ad code) --></main>
<footer class="site"><div class="wrap"><p class="fbrand"><strong>{BRAND}</strong>: {E(FOOT)}</p>
<p class="flinks"><a href="/about/">About</a> | <a href="/methodology/">Sources and methods</a> | <a href="/image-policy/">Image policy</a> | <a href="/terms/">Terms of use</a> | <a href="/privacy/">Privacy</a> | <a href="/disclaimer/">Disclaimer</a> | <a href="/ad-disclosure/">Advertising disclosure</a> | <a href="/copyright/">Copyright and DMCA</a> | <a href="/contact/">Contact</a> | <a href="/privacy/#cookies" id="cookie-settings">Cookie settings</a></p>
</div></footer>
<script src="/assets/site.js?v=1" defer></script>{ga4}{beacon}
</body></html>'''
    if "—" in doc or "–" in doc:
        raise SystemExit("emdash in " + path)
    open(disk_for(path), "w", encoding="utf-8").write(doc)
    if not noindex:
        SITEMAP.append((path, lastmod or PUBLISHED))
    return doc

def article(headline, path, published=None, modified=None, image=None):
    when = published or PUBLISHED
    mod = modified or when
    return {"@context": "https://schema.org", "@type": "Article", "headline": headline,
            "datePublished": when, "dateModified": mod,
            "image": url(image or "/og.png"),
            "author": {"@type": "Organization", "name": BRAND, "url": BASE_URL},
            "publisher": {"@type": "Organization", "name": BRAND, "url": BASE_URL,
                          "logo": {"@type": "ImageObject", "url": url("/logo.png")}},
            "mainEntityOfPage": url(path)}

def load_cities():
    raw = json.load(open(os.path.join(CACHE, "cities.json"), encoding="utf-8"))
    stations = json.load(open(os.path.join(CACHE, "stations.json"), encoding="utf-8"))
    used = set()
    cities = []
    for c in raw:
        census = c["name"]
        name, slug = census, c["slug"]
        if census in ALIASES:
            name, slug = ALIASES[census]
        base = slug
        n = 2
        while (c["st"], slug) in used:
            slug = f"{base}-{n}"
            n += 2
        used.add((c["st"], slug))
        item = dict(c)
        item["name"] = name
        item["slug"] = slug
        item["census"] = census
        item["station_rec"] = stations[c["station"]]
        cities.append(item)
    return cities

def spring50(city):
    return fmt_date(city["station_rec"]["dates"].get("prblst-t32fp50", ""))

def fall50(city):
    return fmt_date(city["station_rec"]["dates"].get("prbfst-t32fp50", ""))

def frost_table(dates):
    def row(label, prefix):
        cells = "".join(f"<td>{E(cell(dates.get(prefix + p, '')))}</td>" for p in ("fp10", "fp50", "fp90"))
        return f"<tr><th scope=\"row\">{label}</th>{cells}</tr>"
    head = "<tr><th>Threshold</th><th>10 percent</th><th>50 percent</th><th>90 percent</th></tr>"
    spring = ("<div class=\"tablewrap\"><table class=\"list\"><caption>Last spring freeze. "
              "NOAA: the chance the last freeze is on or after this date.</caption>"
              f"<thead>{head}</thead><tbody>"
              + row("36°F", "prblst-t36") + row("32°F", "prblst-t32") + row("28°F", "prblst-t28")
              + "</tbody></table></div>")
    fall = ("<div class=\"tablewrap\"><table class=\"list\"><caption>First fall freeze. "
            "NOAA: the chance the first freeze is on or before this date.</caption>"
            f"<thead>{head}</thead><tbody>"
            + row("36°F", "prbfst-t36") + row("32°F", "prbfst-t32") + row("28°F", "prbfst-t28")
            + "</tbody></table></div>")
    return spring + fall

def ga_place_note(city, cities):
    refs = {}
    for c in cities:
        if c["st"] == "GA" and c["name"] in ("Columbus", "Macon", "Augusta"):
            refs[c["name"]] = c["lat"]
    if len(refs) < 3:
        return ("UGA writes this calendar for middle Georgia, a belt from Columbus through Macon to Augusta. "
                "Spring dates can be 2 to 3 weeks earlier in extreme south Georgia, and 1 to 3 weeks later in north Georgia. "
                "Fall dates move the other way. The months below are the middle Georgia baseline, not a shifted date.")
    lo, hi = min(refs.values()), max(refs.values())
    if lo - 0.15 <= city["lat"] <= hi + 0.15:
        where = "inside the latitude band of the Columbus, Macon, and Augusta places on this site, which is the belt UGA calls middle Georgia. The calendar below is written for that belt."
    elif city["lat"] > hi:
        where = ("north of the Columbus, Macon, and Augusta belt. UGA says spring dates are 1 to 3 weeks later in north Georgia, "
                 "and fall dates about 2 weeks earlier. The months below stay the middle Georgia baseline. This page does not shift them.")
    else:
        where = ("south of the Columbus, Macon, and Augusta belt. UGA says spring dates can be as much as 2 to 3 weeks earlier in extreme south Georgia, "
                 "and fall dates as much as 2 weeks later. The months below stay the middle Georgia baseline. This page does not shift them.")
    return "UGA Extension Circular 943 says to treat middle Georgia as the belt from Columbus through Macon to Augusta. This city is " + where

def planting_block(city, cities):
    st = city["st"]
    mmdd = city["station_rec"]["dates"].get("prblst-t32fp50", "")
    if not fmt_date(mmdd):
        mmdd = None
    if st == "GA":
        months = "".join(
            f'<div class="month" data-month="{m}"><h3>{MONTHS[m-1]}</h3><p>{E(text)}</p></div>'
            for m, text in GA_MONTHS.items())
        return f'''<h2>Planting calendar</h2>
<p>From <a href="{GA_SOURCE["url"]}" rel="nofollow noopener">{E(GA_SOURCE["title"])}</a>, {E(GA_SOURCE["reviewed"])}. {E(ga_place_note(city, cities))} UGA says the recommendations follow long term average last and first killing frost dates, and that a given year may not match the average.</p>
<p id="now-label">The full year is listed below. With JavaScript on, the current month is marked.</p>
<noscript><p>Find the current month in the list.</p></noscript>
{months}'''
    if st in SOURCES:
        src = SOURCES[st]
        rows = offset_rows(src, mmdd)
        if not mmdd:
            intro = "This station does not have a computed 32°F median last spring freeze, so no planting date is calculated from it."
        else:
            intro = f"Dates are counted from this city's NOAA 50 percent last spring freeze ({spring50(city)}). They are the extension's offsets, not a separate forecast."
        trs = []
        for r in rows:
            when = r["when"] or "No date calculated"
            trs.append(f"<tr><td>{E(r['crops'])}</td><td>{E(when)}</td><td>{E(r['says'])}</td></tr>")
        # Month index for "what to plant now": crops whose counted window hits that month.
        blocks = []
        for m in range(1, 13):
            hits = [r["crops"] for r in rows if m in r["months"]]
            if not hits:
                text = "No crop in this transcribed chart has a counted window in this month."
            else:
                text = "Counted window overlaps this month: " + "; ".join(hits) + "."
            blocks.append(f'<div class="month" data-month="{m}"><h3>{MONTHS[m-1]}</h3><p>{E(text)}</p></div>')
        return f'''<h2>Planting calendar</h2>
<p>From <a href="{src["url"]}" rel="nofollow noopener">{E(src["title"])}</a>, {E(src["reviewed"])}. {E(intro)}</p>
<div class="tablewrap"><table class="list"><thead><tr><th>Crops</th><th>Counted from the NOAA date</th><th>What the extension says</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>
<p>{E(src["extra"])}</p>
<h2>What to plant now</h2>
<p id="now-label">Each month below is filled only where the extension offset, counted from this city's frost date, lands in that month.</p>
<noscript><p>Find the current month in the list.</p></noscript>
{"".join(blocks)}'''
    return '''<h2>Planting calendar</h2>
<p>This page does not print a vegetable planting calendar for this state. Which Frost only prints timing transcribed from that state's cooperative extension, and this build does not have one yet. The frost table above is the NOAA normal for the station named here. See <a href="/methodology/">sources and methods</a>.</p>'''

def lookup_city(cities, st, slug):
    for c in cities:
        if c["st"] == st and c["slug"] == slug:
            return c
    raise SystemExit("missing city " + st + "/" + slug)

def season_days(c):
    return gsl_days(c["station_rec"]["dates"].get("prbgsl-t32fp50", ""))

def season_place(city, cities):
    ranked = []
    for c in cities:
        g = season_days(c)
        if g is not None:
            ranked.append((g, c))
    ranked.sort(key=lambda t: (t[0], t[1]["st"], t[1]["name"]))
    g = season_days(city)
    shorter = sum(1 for x, _ in ranked if x < g)
    return g, shorter + 1, len(ranked), ranked[0][1], ranked[0][0]

def city_link(c):
    return f'<a href="/{c["st"].lower()}/{c["slug"]}/">{E(c["name"])}</a>'

def anchorage_refresh_block(city, cities):
    """Station-specific reading of the three NOAA thresholds, plus zone 5a peers.
    Numbers come from the same cache as the tables. Not a second frost dataset.
    """
    msp = lookup_city(cities, "MN", "minneapolis")
    mad = lookup_city(cities, "WI", "madison")
    bil = lookup_city(cities, "MT", "billings")
    bend = lookup_city(cities, "OR", "bend")
    raw32 = city["station_rec"]["dates"].get("prblst-t32fp50", "")
    raw28 = city["station_rec"]["dates"].get("prblst-t28fp50", "")
    t36 = fmt_date(city["station_rec"]["dates"].get("prblst-t36fp50", ""))
    t28 = fmt_date(raw28)
    f28 = fmt_date(city["station_rec"]["dates"].get("prbfst-t28fp50", ""))
    gap = int(raw32[3:5]) - int(raw28[3:5]) if raw32[:2] == raw28[:2] else None
    if gap is None:
        raise SystemExit("anchorage 28/32 spring dates are not in the same month")
    g, rank, n, shortest, short_g = season_place(city, cities)
    if rank == 2 and shortest["slug"] == "bend":
        rank_bit = (f"That {g} day season is the second shortest among {n} cities on this site with a computed NOAA figure. "
                    f"Only {city_link(shortest)}, {E(US[shortest['st']])}, is shorter, at {short_g:.0f} days.")
    else:
        rank_bit = (f"Among {n} cities on this site with a computed NOAA growing season, this one ranks {rank} "
                    f"(shortest is {city_link(shortest)} at {short_g:.0f} days).")
    peers = (
        f'{city_link(msp)} (last 32°F {E(spring50(msp))}, {season_days(msp):.0f} days), '
        f'{city_link(mad)} ({E(spring50(mad))}, {season_days(mad):.0f} days), and '
        f'{city_link(bil)} ({E(spring50(bil))}, {season_days(bil):.0f} days)')
    mid = related_reads([
        ("/states/ak/", "Alaska frost dates",
         "Why Anchorage is the only Alaska city here, and how the zone 5a peers compare."),
        ("/zones/5a/", "USDA zone 5a",
         "The winter band Anchorage shares, with each city's NOAA frost date."),
        (f"/{msp['st'].lower()}/{msp['slug']}/", f"{msp['name']} frost dates",
         f"Same zone, median last 32°F freeze on {spring50(msp)}."),
        ("/longest-and-shortest-growing-season/", "Longest and shortest growing season",
         f"Anchorage at {g} days sits near the short end of the NOAA list."),
    ])
    return f'''<h2>What 36°F, 32°F, and 28°F mean on this station</h2>
<p>The 50 percent spring dates above are {E(t36)} at 36°F, {E(spring50(city))} at 32°F, and {E(t28)} at 28°F. The 50 percent first fall date at 28°F is {E(f28)}. Those are 1991 to 2020 medians at Eagle River Nature Center, not a warning for a given night, and not a guarantee that this year will match them.</p>
<p>The <a href="{NWS_FROST}" rel="nofollow noopener">NWS glossary</a> describes frost as ice crystals on the ground or on plants. It often shows up with the thermometer still in the middle 30s, because the surface cools below the air. A frost advisory, in that glossary, is for widespread frost in the growing season, usually with surface temperatures in the middle 30s. <a href="{NWS_RAH}" rel="nofollow noopener">NWS Raleigh</a> publishes a local version of the same idea: 33 to 36°F for a frost advisory, 32°F or lower for a freeze warning, and 28°F or lower for a hard freeze. That office's cutoffs are not a national rule. Other offices set their own.</p>
<p>The <a href="{NWS_FREEZE}" rel="nofollow noopener">glossary entry for a freeze</a> is surface air expected at 32°F or below over a wide area for a climatologically significant time. A hard freeze, on the same page, is 28°F or lower for an extended period, which the glossary says kills most vegetation. The <a href="{NWS_COLD}" rel="nofollow noopener">NWS cold weather page</a> uses the same split for action: a freeze warning when the forecast goes below 32°F for a long period (some crops and garden plants die), and it says temperatures below 28°F for an extended period can kill most of them. On this station the median last 28°F date and the median last 32°F date are {gap} days apart ({E(t28)} versus {E(spring50(city))}).</p>
<p>A separate Hard Freeze Warning is no longer its own product. <a href="{NWS_SCN}" rel="nofollow noopener">Service Change Notice 23-44</a> (updated 26 March 2024) set the change for on or about 1 October 2024: the hard freeze watch and warning were folded into the freeze watch and warning, and the warning text can still say "hard freeze" when the forecast low is 28°F or lower. The <a href="{NWS_HAZ}" rel="nofollow noopener">NWS hazard simplification note</a> describes the same consolidation. Both were checked {ANCHORAGE_REFRESH_H}.</p>
<p>{rank_bit} Both figures are NOAA's own growing season element, listed on the <a href="/longest-and-shortest-growing-season/">season ranking</a>. This site does not subtract the spring date from the fall date to invent a third number.</p>
<p><a href="{UAF_GARLIC}" rel="nofollow noopener">UAF Cooperative Extension HGA-00047</a> (Growing Garlic in Alaska, revised 27 May 2025, checked {ANCHORAGE_REFRESH_H}) calls a killing frost the first autumn night the air reaches about 32°F, and says to plant garlic a week or two after that, or four to six weeks before the ground freezes, generally from the middle of September to the middle of October. This station's median first 32°F date is {E(fall50(city))}, inside that wide window. UAF points gardeners to the Alaska Garden Helper for a local date. This page does not turn the garlic note into one planting day.</p>
<aside class="compare" aria-label="Check another city">
<h2>Check another zone 5a city</h2>
<p>Anchorage is USDA zone 5a, the same winter band as {peers}. The frost dates are not the same number. The <a href="/states/ak/">Alaska page</a> lists every zone 5a city on this site, and <a href="/{bend["st"].lower()}/{bend["slug"]}/">{E(bend["name"])}</a> is the short season comparison, in zone {E(bend.get("zone") or "")} rather than 5a.</p>
<p class="note">A USDA zone is the average coldest winter temperature, not a planting day. These dates are medians, not a guarantee for this year.</p>
</aside>
{mid}'''

def city_page(city, cities):
    st = city["st"]
    name = city["name"]
    state = US[st]
    s = city["station_rec"]
    dates = s["dates"]
    label = station_label(s["name"])
    sid = s["id"]
    path = f"/{st.lower()}/{city['slug']}/"
    sp = spring50(city)
    fa = fall50(city)
    gsl = gsl_days(dates.get("prbgsl-t32fp50"))
    zone = city.get("zone")
    zrange = city.get("zone_range") or ""
    dist = miles_text(city["miles"])
    h1 = f"{name}, {state} frost dates and planting calendar"
    title = f"Which frost date for {name}, {state}"
    if sp and fa:
        desc = f"Median last 32°F freeze in {name}, {state}: {sp} in spring and {fa} in fall, from NOAA 1991 to 2020 normals."
        lead_frost = (f"The median last spring freeze at 32°F is {sp}. "
                      f"The median first fall freeze at 32°F is {fa}.")
    elif sp:
        desc = f"Median last 32°F spring freeze in {name}, {state} is {sp}, from NOAA 1991 to 2020 normals at {label}."
        lead_frost = f"The median last spring freeze at 32°F is {sp}. NOAA did not compute a median first fall freeze at 32°F for this station."
    elif fa:
        desc = f"Median first 32°F fall freeze in {name}, {state} is {fa}. A spring date was not computed for the nearest station."
        lead_frost = f"NOAA did not compute a median last spring freeze at 32°F for this station. The median first fall freeze at 32°F is {fa}."
    else:
        desc = f"{name}, {state}: NOAA did not compute a 32°F frost date at {label}. Other thresholds and the source are on this page."
        lead_frost = "NOAA did not compute a median last spring freeze at 32°F for this station."
    gsl_bit = f" The median growing season at 32°F is {gsl} days (the season is at least this long in 50 percent of years)." if gsl else ""
    if zone:
        zone_html = (f'The USDA hardiness zone for ZIP {E(city["zip"])}, the zoned ZIP whose centroid is nearest the city center '
                     f'({miles_text(city["zone_miles"])} away), is <a href="/zones/{zone}/">{E(zone)}</a> ({E(zrange)}°F).')
    else:
        zone_html = "No USDA zone is shown, because no zoned ZIP centroid was within 30 miles."
    record = meta_sentence(s["meta"].get("prblst-t32fp50") or s["meta"].get("prbgsl-t32fp50"))
    census_note = ""
    if city["census"] != name:
        census_note = f" Census place name: {city['census']}."
    elev_ft = round(s["elev_m"] * 3.28084)
    same = [c for c in cities if c["st"] == st and c["slug"] != city["slug"]]
    same.sort(key=lambda c: haversine(city["lat"], city["lon"], c["lat"], c["lon"]))
    sibs = same[:6]
    sib_html = ", ".join(f'<a href="/{c["st"].lower()}/{c["slug"]}/">{E(c["name"])}</a>' for c in sibs) or "none on this site"
    neigh_links = []
    for n in NEIGHBORS.get(st, []):
        if any(c["st"] == n for c in cities):
            neigh_links.append(f'<a href="/states/{n.lower()}/">{E(US[n])}</a>')
    oth_html = ", ".join(neigh_links) or "none with a city page in this build"
    p10 = fmt_date(dates.get("prblst-t32fp10", ""))
    if sp and p10:
        late = (f"In the 1991 to 2020 normals, NOAA gives a 10 percent chance that the last 32°F freeze in this record is still to come on or after {p10}. "
                f"Planting on the 50 percent date ({sp}) still leaves a later freeze possible. This page is not a forecast. If a freeze is predicted after you plant, wait or protect seedlings. That is not agricultural advice.")
    elif sp:
        late = (f"The 50 percent date ({sp}) is a median, not a promise that the last freeze is over. "
                "NOAA did not compute the 10 percent spring date for this station. This page is not a forecast.")
    else:
        late = "This station does not have a computed 32°F spring date, so there is no median to plant against. Use a forecast for the next few nights, not this normals page, if a freeze is a concern. This is not agricultural advice."
    define = (" When NOAA publishes a date, the spring figure is the chance the last spring freeze happens on or after that day, and the fall figure is the chance the first fall freeze happens on or before that day. A 50 percent date is the median for 1991 to 2020. It is not a forecast for this year.")
    faqs = [
        (f"What does a frost date mean in {name}?",
         lead_frost + define),
        (f"Why can {name} have more than one weather station?",
         f"This page uses {label} ({sid}), the nearest NOAA normals station with a published frost product, {dist} from the city center. Another station in the same area can sit at a different elevation or closer to water, and NOAA can publish a different date there. Which Frost does not average stations together."),
        (f"What should I do about a late frost in {name}?", late),
    ]
    sources = [
        (f"NOAA NCEI U.S. Climate Normals 1991 to 2020, station {s['name']} ({sid})", NOAA_HOME),
        ("NOAA Normals Calculation Methodology 2020 (frost freeze probability dates)", NOAA_METHOD),
        ("U.S. Census Bureau, Population Estimates Program, sub-est2024, incorporated places", CENSUS_POP),
        ("2023 USDA Plant Hardiness Zone Map", PHZM),
        ("PRISM Climate Group, Oregon State University, 2023 ZIP code zone tables", PRISM),
    ]
    if st == "GA":
        sources.append((GA_SOURCE["title"], GA_SOURCE["url"]))
    elif st in SOURCES:
        sources.append((SOURCES[st]["title"], SOURCES[st]["url"]))
    is_anchorage = st == "AK" and city["slug"] == "anchorage"
    verified = ANCHORAGE_REFRESH_H if is_anchorage else PUBLISHED_H
    anchorage_html = ""
    end_related = ""
    source_note = (f"Normals retrieved {PUBLISHED_H} from the NCEI 1991 to 2020 annual and seasonal by station archive "
                   "(v1.0.1, file dated 20230404). Zone ZIP tables retrieved the same day.")
    if is_anchorage:
        title = "Last frost date in Anchorage: around May 16"
        desc = ("Anchorage median last freeze: May 16 at 32°F and May 1 at 28°F, from NOAA 1991 to 2020 normals. "
                "Zone 5a peers are earlier.")
        faqs.append((
            "Why is the Anchorage date an estimate?",
            "NOAA's completeness flag on the 32°F spring element at Eagle River Nature Center is E, and the file lists 9 years. "
            "Flag E means NOAA had at least 2 years and estimated the normal from nearby stations that have a standard record. "
            "Which Frost prints that estimate. It does not swap in a different station."))
        faqs.append((
            "Does zone 5a give Anchorage the same frost date as Minneapolis?",
            "No. Both are USDA zone 5a on this site, a winter minimum of -20 to -15°F. "
            "Minneapolis's median last spring freeze at 32°F is April 23, and its median growing season is 175 days. "
            "Anchorage's median last spring freeze at 32°F is May 16, and its season is 125 days. "
            "The zone is not a planting day."))
        sources.extend([
            ("NWS glossary: frost", NWS_FROST),
            ("NWS glossary: freeze and hard freeze", NWS_FREEZE),
            ("NWS: freeze warning, freeze watch, and frost advisory", NWS_COLD),
            ("NWS Service Change Notice 23-44 (hard freeze folded into the freeze warning, 26 March 2024)", NWS_SCN),
            ("NWS Raleigh frost and freeze criteria (one office's local thresholds)", NWS_RAH),
            ("UAF Cooperative Extension HGA-00047, Growing Garlic in Alaska", UAF_GARLIC),
        ])
        anchorage_html = anchorage_refresh_block(city, cities)
        bend = lookup_city(cities, "OR", "bend")
        bil = lookup_city(cities, "MT", "billings")
        end_related = related_reads([
            (f"/{bend['st'].lower()}/{bend['slug']}/", f"{bend['name']}, {US[bend['st']]} frost dates",
             f"Shortest NOAA growing season on this site, {season_days(bend):.0f} days, in zone {bend.get('zone')}."),
            (f"/{bil['st'].lower()}/{bil['slug']}/", f"{bil['name']}, {US[bil['st']]} frost dates",
             f"Another zone 5a city. Median last 32°F freeze on {spring50(bil)}."),
            ("/methodology/", "Sources and methods",
             "How the nearest frost station is chosen, and what flag E means."),
            ("/states/", "Frost dates by state",
             "Every state hub, including the Alaska comparison."),
        ])
        source_note = (f"Station file retrieved {PUBLISHED_H} from the NCEI 1991 to 2020 annual and seasonal by station archive "
                       f"(v1.0.1, file dated 20230404). On {ANCHORAGE_REFRESH_H} the NCEI product page still called the 1991 to 2020 "
                       "normals the latest release and said a new set is issued about every 10 years. The freeze probability dates "
                       "on this page were not replaced. NWS and UAF pages linked here were checked the same day. Zone ZIP tables were retrieved 16 Nov 2026.")
    src_html = "".join(f'<li><a href="{href}" rel="nofollow noopener">{E(t)}</a></li>' for t, href in sources)
    body = f'''<article class="prose wide"><h1>{E(h1)}</h1>
<p class="byline">By {BRAND}. Last verified {verified}.</p>
<div class="answer"><p>{E(lead_frost)}{E(gsl_bit)}</p>
<p>Station {E(label)} ({E(sid)}), {E(dist)} from the city center. Elevation {s["elev_m"]} m ({elev_ft} ft, converted from the NOAA meters). {E(record)}</p>
<p>{zone_html}</p></div>
<p class="note">These figures are 1991 to 2020 climate normals, not a forecast and not a guarantee for this year. A given year can freeze earlier or later. This is not legal advice, not insurance guidance, and not agricultural advice.{E(census_note)} Census 2024 population estimate: {commas(city["pop"])}.</p>
<h2>Freeze probability dates</h2>
<p>Thresholds are the minimum temperature. 36°F is a light frost in many extension guides, 32°F is a freeze, and 28°F is a harder freeze. Blank results use NOAA's own codes, described under the tables. Spring 90 percent is an earlier date (a freeze is still likely). Spring 10 percent is a later date (only a 10 percent chance the last freeze is still to come).</p>
{frost_table(dates)}
<p class="note">Not computed means the file stores -9999 with measurement flag Y (not enough values). Too rare to compute means -6666 (NOAA requires at least a 10 percent chance the temperature occurs). Year round risk means -4444.</p>
{anchorage_html}
{planting_block(city, cities)}
{end_related}
<h2>More pages</h2>
<p>Other {E(state)} cities: {sib_html}. Neighboring states: {oth_html}. This state: <a href="/states/{st.lower()}/">{E(state)}</a>. <a href="/states/">All states</a>. <a href="/zones/">All zones</a>. Forecast words for the 36°F, 32°F, and 28°F columns: <a href="/guides/hard-freeze-vs-frost/">hard freeze, frost, and a freeze warning</a>.</p>
{faq_html(faqs)}
<section class="sources"><h2>Sources</h2><ul>{src_html}</ul>
<p class="note">{source_note}</p></section>
</article>'''
    # zone_bit already contains an anchor and was not escaped as a whole. lead uses E() except zone_bit which is inserted raw inside a <p> that started after escaped text.
    # The paragraph above mixes escaped and raw. zone_bit is safe (we built it). Fix: the sentence "USDA zone..." is inside a <p> with zone_bit unescaped. Good.
    crumbs = [("/", "Home"), (f"/states/{st.lower()}/", state), (path, name)]
    modified = ANCHORAGE_REFRESH if is_anchorage else None
    schemas = [article(h1, path, published=PUBLISHED, modified=modified), faq_ld(faqs)]
    page(path, title, desc, body, crumbs, schemas, nav_current=None, lastmod=modified)

def alaska_state_page(group, all_cities):
    """One Alaska city, an estimated station, and a zone 5a comparison that is not the city page."""
    st = "AK"
    state = US[st]
    path = "/states/ak/"
    anchorage = group[0]
    peers = [c for c in all_cities if c.get("zone") == "5a" and spring50(c)]
    peers.sort(key=lambda c: c["station_rec"]["dates"].get("prblst-t32fp50", "99/99"))
    earliest, latest = peers[0], peers[-1]
    falls = [c for c in peers if fall50(c)]
    first_fall = min(falls, key=lambda c: c["station_rec"]["dates"].get("prbfst-t32fp50", "99/99"))
    shortest = min(peers, key=lambda c: season_days(c) if season_days(c) is not None else 9999)
    g, rank, n, short_city, short_g = season_place(anchorage, all_cities)
    rows = []
    for c in peers:
        gsl = season_days(c)
        rows.append(
            f'<tr><td>{city_link(c)}, {E(US[c["st"]])}</td>'
            f'<td>{E(spring50(c))}</td><td>{E(fall50(c) or "Not computed")}</td>'
            f'<td>{gsl:.0f} days</td></tr>')
    t36 = fmt_date(anchorage["station_rec"]["dates"].get("prblst-t36fp50", ""))
    t28 = fmt_date(anchorage["station_rec"]["dates"].get("prblst-t28fp50", ""))
    s = anchorage["station_rec"]
    sid = s["id"]
    label = station_label(s["name"])
    meta = s["meta"].get("prblst-t32fp50") or {}
    msp = lookup_city(all_cities, "MN", "minneapolis")
    mad = lookup_city(all_cities, "WI", "madison")
    sui = lookup_city(all_cities, "SD", "sioux-falls")
    mid = related_reads([
        ("/ak/anchorage/", "Anchorage frost dates",
         "Full 10, 50, and 90 percent table, plus the UAF seed timing counted from May 16."),
        ("/zones/5a/", "USDA zone 5a",
         "Winter minimum band shared by Anchorage and the cities in the table below."),
        (f"/{msp['st'].lower()}/{msp['slug']}/", f"{msp['name']} frost dates",
         f"Earliest median last 32°F spring date in this zone on this site: {spring50(msp)}."),
        (f"/{short_city['st'].lower()}/{short_city['slug']}/", f"{short_city['name']} frost dates",
         f"Shortest NOAA season on this site, {short_g:.0f} days."),
    ])
    end = related_reads([
        ("/longest-and-shortest-growing-season/", "Longest and shortest growing season",
         f"Anchorage ranks {rank} of {n} at {g:.0f} days."),
        (f"/{sui['st'].lower()}/{sui['slug']}/", f"{sui['name']} frost dates",
         f"Zone 5a. Median last 32°F freeze on {spring50(sui)}."),
        (f"/{mad['st'].lower()}/{mad['slug']}/", f"{mad['name']} frost dates",
         f"Zone 5a. Median last 32°F freeze on {spring50(mad)}."),
        ("/methodology/", "Sources and methods",
         "Station distance cap, Census population floor, and NOAA completeness flags."),
    ])
    h1 = "Alaska frost dates, and why zone 5a is not the frost date"
    faqs = [
        ("Why is Anchorage the only Alaska city on this site?",
         "A city page is an incorporated place with a 2024 Census population of at least 100,000 whose nearest NOAA frost station is within 50 miles. "
         f"Anchorage is the only Alaska place in this build, at a Census estimate of {anchorage['pop']:,}. "
         "This page does not add smaller Alaska towns by copying Anchorage's dates onto them."),
        ("Is the Anchorage frost date a full 30 year record at that station?",
         f"No. NOAA's file for {label} ({sid}) lists {meta.get('years', 'an unstated number of')} years on the 32°F spring element, "
         "with completeness flag E. Flag E means NOAA had at least 2 years and estimated the normal from nearby stations with a standard record. "
         "The dates are still the published 1991 to 2020 normal. They are medians, not a guarantee for this year."),
        ("Minneapolis is also zone 5a. Why is Anchorage's last frost later?",
         "USDA zone 5a is the average coldest winter temperature, -20 to -15°F, not a spring frost date. "
         f"On this site Minneapolis's median last 32°F freeze is {spring50(msp)} and the season is {season_days(msp):.0f} days. "
         f"Anchorage's median is {spring50(anchorage)} and the season is {g:.0f} days. "
         "The zone number does not move the frost date."),
    ]
    body = f'''<article class="prose wide"><h1>{E(h1)}</h1>
<p class="byline">By {BRAND}. Last verified {ANCHORAGE_REFRESH_H}.</p>
<div class="answer"><p>Anchorage is the only Alaska city in this build. At {E(label)} ({E(sid)}), {E(miles_text(anchorage["miles"]))} from the city center, NOAA's median last spring freeze at 32°F is {E(spring50(anchorage))} and the median first fall freeze is {E(fall50(anchorage))}. The median growing season is {g:.0f} days. These are 1991 to 2020 medians, not a forecast and not a guarantee for a given year.</p></div>
<p>The station file lists {E(str(meta.get("years") or ""))} years for that 32°F element and completeness flag {E(meta.get("comp") or "")}. Flag E means NOAA estimated the normal from nearby stations that have a standard record. Elevation in the file is {s["elev_m"]} m. Another station in the same area can sit at a different elevation or closer to water, and NOAA can publish a different date there. This site does not average stations. The <a href="/ak/anchorage/">Anchorage page</a> has the 10 and 90 percent columns. <a href="/methodology/">How the station is chosen</a>.</p>
<h2>The one city</h2>
<div class="tablewrap"><table class="list"><thead><tr><th>City</th><th>Zone</th><th>Last 32°F</th><th>First 32°F</th><th>Station distance</th></tr></thead><tbody>
<tr><td><a href="/ak/anchorage/">Anchorage</a></td><td><a href="/zones/5a/">5a</a></td><td>{E(spring50(anchorage))}</td><td>{E(fall50(anchorage))}</td><td>{E(miles_text(anchorage["miles"]))}</td></tr>
</tbody></table></div>
<p class="note">Census 2024 population estimate: {anchorage["pop"]:,}. No other Alaska incorporated place of 100,000 people is inside the 50 mile station cap in this build, so the table has one row.</p>
<h2>Same zone, later spring</h2>
<p>Anchorage's ZIP zone is <a href="/zones/5a/">5a</a> (-20 to -15°F). Zone 5a on this site also includes cities with an earlier median last 32°F freeze. The earliest in the table is {city_link(earliest)} on {E(spring50(earliest))}. The latest is {city_link(latest)} on {E(spring50(latest))}. The shortest season in the zone is {city_link(shortest)} at {season_days(shortest):.0f} days. The earliest median first fall 32°F date in the zone is {city_link(first_fall)} on {E(fall50(first_fall))}.</p>
<div class="tablewrap"><table class="list"><thead><tr><th>Zone 5a city</th><th>Last spring 32°F</th><th>First fall 32°F</th><th>Growing season</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<p>Among {n} cities on this site with a computed NOAA growing season, Anchorage is number {rank} from the short end, at {g:.0f} days. The shortest anywhere in the build is {city_link(short_city)}, {E(US[short_city["st"]])}, at {short_g:.0f} days. <a href="/longest-and-shortest-growing-season/">The full ranking</a> uses NOAA's own season element.</p>
<aside class="compare" aria-label="Check another lookup">
<h2>Check another city</h2>
<p>Open <a href="/ak/anchorage/">Anchorage</a> for the 10 and 90 percent dates and the UAF seed chart counted from {E(spring50(anchorage))}. Or open a zone 5a city with an earlier spring: {city_link(msp)}, {city_link(sui)}, {city_link(mad)}.</p>
<p class="note">Do not plant from the zone number. The frost date is the city row.</p>
</aside>
{mid}
<h2>What the three Anchorage temperatures are called</h2>
<p>At this station the median spring dates are {E(t36)} at 36°F, {E(spring50(anchorage))} at 32°F, and {E(t28)} at 28°F. The <a href="{NWS_FROST}" rel="nofollow noopener">NWS glossary</a> describes frost as ice on surfaces, often while the thermometer is still in the middle 30s. A <a href="{NWS_FREEZE}" rel="nofollow noopener">freeze</a> is widespread air at 32°F or below, and a hard freeze is 28°F or lower for long enough that the glossary says it kills most vegetation. The <a href="/guides/hard-freeze-vs-frost/">hard freeze guide</a> puts those three words next to the warning products. The Anchorage page has the full station table. Checked {ANCHORAGE_REFRESH_H}.</p>
<p><a href="https://www.uaf.edu/ces/publications/database/gardening/easy-steps-gardening-alaska.php" rel="nofollow noopener">UAF Cooperative Extension HGA-00134</a>, checked the same day, says wind off the water keeps soil cool around Anchorage, the Kenai, and Bristol Bay, and that a frost pocket should be planted only with frost resistant vegetables. The seed start weeks from that publication are counted on the <a href="/ak/anchorage/">city page</a> from the NOAA 50 percent date. They are not repeated here, and they are not a forecast.</p>
<h2>Nearby states</h2>
<p>No neighboring state has a city page in this build. <a href="/states/">All states</a>. <a href="/zones/">All zones</a>.</p>
{end}
{faq_html(faqs)}
<section class="sources"><h2>Sources</h2><ul>
<li><a href="{NOAA_HOME}" rel="nofollow noopener">NOAA NCEI U.S. Climate Normals 1991 to 2020</a>, station {E(s["name"])} ({E(sid)})</li>
<li><a href="{NOAA_METHOD}" rel="nofollow noopener">NOAA Normals Calculation Methodology 2020</a></li>
<li><a href="{CENSUS_POP}" rel="nofollow noopener">U.S. Census Bureau, sub-est2024</a></li>
<li><a href="{PHZM}" rel="nofollow noopener">2023 USDA Plant Hardiness Zone Map</a></li>
<li><a href="{NWS_FROST}" rel="nofollow noopener">NWS glossary, frost</a></li>
<li><a href="{NWS_FREEZE}" rel="nofollow noopener">NWS glossary, freeze and hard freeze</a></li>
<li><a href="https://www.uaf.edu/ces/publications/database/gardening/easy-steps-gardening-alaska.php" rel="nofollow noopener">UAF Cooperative Extension HGA-00134</a></li>
</ul>
<p class="note">Station cache retrieved {PUBLISHED_H} (NCEI v1.0.1, file dated 20230404). On {ANCHORAGE_REFRESH_H} the NCEI product page still named the 1991 to 2020 normals as the latest set. NWS and UAF pages were checked the same day. Medians, not a guarantee.</p>
</section>
</article>'''
    page(path, "Alaska frost dates: Anchorage around May 16",
         "Only Anchorage is listed for Alaska. NOAA median last 32°F freeze is May 16. Other zone 5a cities freeze earlier.",
         body, [("/", "Home"), ("/states/", "States"), (path, state)],
         [article(h1, path, published=PUBLISHED, modified=ANCHORAGE_REFRESH), faq_ld(faqs)],
         nav_current="/states/", lastmod=ANCHORAGE_REFRESH)

def state_page(st, cities):
    if st == "AK":
        alaska_state_page(cities, ALL)
        return
    state = US[st]
    path = f"/states/{st.lower()}/"
    rows = []
    for c in sorted(cities, key=lambda c: c["name"]):
        sp = spring50(c) or "Not computed"
        fa = fall50(c) or "Not computed"
        z = c.get("zone") or ""
        zlink = f'<a href="/zones/{z}/">{E(z)}</a>' if z else ""
        rows.append("<tr><td><a href=\"/{}/{}/\">{}</a></td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            st.lower(), c["slug"], E(c["name"]), zlink, E(sp), E(fa), E(miles_text(c["miles"]))))
    neigh = ", ".join(f'<a href="/states/{n.lower()}/">{E(US[n])}</a>' for n in NEIGHBORS.get(st, []) if any(c["st"] == n for c in ALL))
    zs = sorted({c["zone"] for c in cities if c.get("zone")}, key=lambda z: (int(z[:-1]), z[-1]))
    zhtml = ", ".join(f'<a href="/zones/{z}/">zone {E(z)}</a>' for z in zs)
    zone_block = f'<h2>Zones in {E(state)}</h2><p>{zhtml}. <a href="/zones/">All zones</a>. <a href="/states/">All states</a>.</p>' if zhtml else '<p><a href="/states/">All states</a>. <a href="/zones/">All zones</a>.</p>'
    faqs = [
        (f"Which frost date should I use in {state}?",
         "The date columns are the NOAA 50 percent 32°F last spring freeze and first fall freeze at the nearest station. The 50 percent date is the median for 1991 to 2020. It is not a forecast for this year. Open a city for the 10 and 90 percent dates."),
        (f"How were {state} cities chosen?",
         f"Each city is an incorporated place with a 2024 Census population of at least 100,000, whose nearest NOAA normals station with a frost product is within 50 miles of the city center. {len(cities)} {state} places are on this site.")]
    body = f'''<article class="prose wide"><h1>{E(state)} frost dates</h1>
<p class="byline">By {BRAND}. Last verified {PUBLISHED_H}.</p>
<p class="answer">{len(cities)} {E(state)} cities. The date columns are the NOAA 50 percent 32°F last spring freeze and first fall freeze at the nearest station. Open a city for the full table, the station, and the planting notes.</p>
<div class="tablewrap"><table class="list"><thead><tr><th>City</th><th>Zone</th><th>Last 32°F</th><th>First 32°F</th><th>Station distance</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
{zone_block}
<h2>Nearby states</h2><p>{neigh or "No neighboring state has a city page in this build."}</p>
{faq_html(faqs)}
<p class="note">Source: <a href="{NOAA_HOME}" rel="nofollow noopener">NOAA NCEI 1991 to 2020 climate normals</a>. <a href="/methodology/">How the station is chosen</a>.</p>
</article>'''
    page(path, f"Which frost date should I use in {state}",
         f"Last and first 32°F frost dates for {len(cities)} {state} cities, from NOAA 1991 to 2020 normals at the nearest station.",
         body, [("/", "Home"), ("/states/", "States"), (path, state)],
         [article(f"{state} frost dates", path), faq_ld(faqs)], nav_current="/states/")

def related_reads(items):
    """items: list of (href, title, blurb). Thumbs use the site og mark until article photos exist.

    Each <img> must sit inside an <a href="/image-policy/"> (site photo check).
    """
    cards = []
    for href, title, blurb in items:
        cards.append(
            '<li class="related-card">'
            '<a class="rr-thumb" href="/image-policy/">'
            '<img src="/og.png" width="240" height="126" alt="Which Frost site mark (image policy)" loading="lazy">'
            '</a>'
            '<p class="note"><a href="/image-policy/">Which Frost site mark. Image policy</a></p>'
            f'<a class="rr-text" href="{href}">'
            f'<span class="rr-title">{E(title)}</span>'
            f'<span class="rr-blurb">{E(blurb)}</span></a></li>')
    return ('<section class="related-reads" aria-label="Related pages">'
            '<h2>Related pages</h2>'
            f'<ul class="related-grid">{"".join(cards)}</ul></section>')

def compare_box(zone, near, states):
    near_links = ", ".join(f'<a href="/zones/{z}/">zone {E(z)}</a>' for z in near) or "none on this site"
    state_sample = states[:4]
    state_html = ", ".join(f'<a href="/states/{st.lower()}/">{E(US[st])}</a>' for st in state_sample)
    more = "" if len(states) <= 4 else ', and <a href="/zones/">more on the zones hub</a>'
    return f'''<aside class="compare" aria-label="Check another lookup">
<h2>Check another zone or city</h2>
<p>Compare adjacent hardiness bands: {near_links}. Or open a state hub ({state_html}{more}) and pick a city for its NOAA 50 percent frost date.</p>
<p class="note">A USDA zone is winter cold, not a planting day. The frost date lives on the city page.</p>
</aside>'''

def zone_frost_section(zone, cities):
    """Zone-specific NOAA facts from the same per-station cache as city pages. Not a planting calendar."""
    rows = []
    for c in cities:
        sp = spring50(c)
        fa = fall50(c)
        gsl = gsl_days(c["station_rec"]["dates"].get("prbgsl-t32fp50", ""))
        rows.append((c, sp, fa, gsl))
    with_spring = [t for t in rows if t[1]]
    with_gsl = [t for t in rows if t[3] is not None]
    n = len(cities)
    n_spring = len(with_spring)
    parts = [f'<h2>Frost dates inside zone {E(zone)}</h2>']
    city_word = "cities" if n != 1 else "city"
    parts.append(
        f'<p>USDA zone {E(zone)} is a winter minimum band. The frost dates below are NOAA 1991 to 2020 medians at 32°F for the '
        f'{n} large {city_word} on this site that fall in that band. They are medians, not guarantees for any single year.</p>')
    if with_spring:
        def spring_raw(c):
            return c["station_rec"]["dates"].get("prblst-t32fp50", "99/99")
        earliest = min(with_spring, key=lambda t: spring_raw(t[0]))
        latest = max(with_spring, key=lambda t: spring_raw(t[0]))
        ec, esp, efa, egsl = earliest
        lc, lsp, lfa, lgsl = latest
        if ec["slug"] == lc["slug"] and ec["st"] == lc["st"]:
            bit = f'<p class="answer">The only city on this site in zone {E(zone)} is '
            bit += f'<a href="/{ec["st"].lower()}/{ec["slug"]}/">{E(ec["name"])}, {E(US[ec["st"]])}</a>, '
            bit += f'with a median last spring 32°F freeze of {E(esp)}'
            if efa:
                bit += f' and a median first fall 32°F freeze of {E(efa)}'
            if egsl is not None:
                bit += f". NOAA's median growing season at 32°F is {egsl} days"
            bit += '.</p>'
            parts.append(bit)
        else:
            parts.append(
                f'<p class="answer">Across {n_spring} cities with a computed spring date, the earliest median last spring 32°F freeze is '
                f'{E(esp)} in <a href="/{ec["st"].lower()}/{ec["slug"]}/">{E(ec["name"])}, {E(US[ec["st"]])}</a>. '
                f'The latest is {E(lsp)} in <a href="/{lc["st"].lower()}/{lc["slug"]}/">{E(lc["name"])}, {E(US[lc["st"]])}</a>.</p>')
            if with_gsl:
                shortest = min(with_gsl, key=lambda t: t[3])
                longest = max(with_gsl, key=lambda t: t[3])
                sc, _, _, sg = shortest
                Lc, _, _, Lg = longest
                if sc["slug"] == Lc["slug"] and sc["st"] == Lc["st"]:
                    parts.append(
                        f"<p>NOAA's median growing season at 32°F for cities in this zone on this site is {sg} days "
                        f'(<a href="/{sc["st"].lower()}/{sc["slug"]}/">{E(sc["name"])}</a>).</p>')
                else:
                    parts.append(
                        f"<p>NOAA's median growing season at 32°F in this zone runs from {sg} days in "
                        f'<a href="/{sc["st"].lower()}/{sc["slug"]}/">{E(sc["name"])}, {E(US[sc["st"]])}</a> '
                        f'to {Lg} days in <a href="/{Lc["st"].lower()}/{Lc["slug"]}/">{E(Lc["name"])}, {E(US[Lc["st"]])}</a>.</p>')
    else:
        parts.append(
            '<p>None of the cities in this zone on this site have a computed NOAA last spring 32°F date. '
            'See <a href="/no-computed-frost-date/">cities with no computed 32°F frost date</a>.</p>')
    trs = []
    for c, sp, fa, gsl in sorted(rows, key=lambda t: (-t[0]["pop"])):
        gsl_cell = f"{gsl} days" if gsl is not None else "Not computed"
        trs.append(
            f'<tr><td><a href="/{c["st"].lower()}/{c["slug"]}/">{E(c["name"])}, {E(US[c["st"]])}</a></td>'
            f'<td>{E(sp or "Not computed")}</td><td>{E(fa or "Not computed")}</td>'
            f'<td>{E(gsl_cell)}</td></tr>')
    parts.append(
        '<div class="tablewrap"><table class="list"><thead><tr>'
        '<th>City</th><th>Last spring 32°F</th><th>First fall 32°F</th><th>Growing season</th>'
        '</tr></thead><tbody>' + "".join(trs) + '</tbody></table></div>')
    parts.append(
        '<p class="note">Figures are the same NOAA normals cache every city page cites '
        f'(retrieved {PUBLISHED_H}). Open a city for the 10 and 90 percent dates and the station id.</p>')
    return "\n".join(parts)

def zone_page(zone, cities):
    path = f"/zones/{zone}/"
    zrange = next((c["zone_range"] for c in cities if c.get("zone_range")), "")
    rows = []
    for c in sorted(cities, key=lambda c: (-c["pop"])):
        rows.append(f'<li><a href="/{c["st"].lower()}/{c["slug"]}/">{E(c["name"])}, {E(US[c["st"]])}</a> ({E(spring50(c) or "32°F date not computed")})</li>')
    states = sorted(set(c["st"] for c in cities), key=lambda s: US[s])
    blocks = []
    for st in states:
        if st == "GA":
            months = "".join(f'<div class="month" data-month="{m}"><h3>{MONTHS[m-1]}</h3><p>{E(GA_MONTHS[m])}</p></div>' for m in range(1, 13))
            blocks.append(f'''<h3>{E(US[st])}</h3>
<p>UGA Extension Circular 943, written for middle Georgia. Cities north or south of that belt should read the caveat on the city page. The months are not shifted on this zone page. <a href="{GA_SOURCE["url"]}" rel="nofollow noopener">Source</a>.</p>
{months}''')
        elif st in SOURCES:
            src = SOURCES[st]
            items = "".join(f'<li><strong>{E(g["crops"])}.</strong> {E(g["says"])}</li>' for g in src["groups"])
            blocks.append(f'''<h3>{E(US[st])}</h3>
<p>{E(src["title"])} times these crops from the average last spring frost, not from the zone number. Counted dates are on each city page, using that city&#x27;s NOAA 50 percent date. <a href="{src["url"]}" rel="nofollow noopener">Source</a>.</p>
<ul>{items}</ul>''')
        else:
            names = ", ".join(f'<a href="/{c["st"].lower()}/{c["slug"]}/">{E(c["name"])}</a>' for c in cities if c["st"] == st)
            blocks.append(f"<h3>{E(US[st])}</h3><p>No extension planting calendar is transcribed for {E(US[st])} in this build. Cities: {names}.</p>")
    faqs = [
        (
            f"Does USDA zone {zone} tell me what to plant this week?",
            f"No. Zone {zone} is the 2023 USDA average annual extreme minimum temperature, {zrange}°F. Nurseries use it for which perennial plants can take a typical winter. Vegetable sowing dates on this site come from a state extension page counted against the city's NOAA frost date, when we have transcribed one.",
        ),
        (
            f"What is the frost date for cities in zone {zone}?",
            f"There is no single frost date for zone {zone}. Each city page uses the nearest NOAA station with a frost product. The table on this page lists the median last spring and first fall 32°F dates for the cities in this zone on this site. Those dates are 1991 to 2020 medians, not a forecast.",
        ),
    ]
    ordered = sorted({c["zone"] for c in ALL if c.get("zone")}, key=lambda z: (int(z[:-1]), z[-1]))
    here = ordered.index(zone)
    near = []
    if here > 0:
        near.append(ordered[here - 1])
    if here + 1 < len(ordered):
        near.append(ordered[here + 1])
    near_html = ", ".join(f'<a href="/zones/{z}/">zone {E(z)}</a>' for z in near) or "none"
    state_links = ", ".join(f'<a href="/states/{st.lower()}/">{E(US[st])}</a>' for st in states)
    frost_html = zone_frost_section(zone, cities)
    mid_related = related_reads([
        (f"/zones/{near[0]}/" if near else "/zones/", f"USDA zone {near[0]}" if near else "All USDA zones",
         "Adjacent hardiness band on this site." if near else "Every zone with a city page."),
        ("/longest-and-shortest-growing-season/", "Longest and shortest growing season",
         "NOAA median season length ranked across all cities."),
        (f"/states/{states[0].lower()}/", f"{US[states[0]]} frost dates",
         "State hub for cities that sit in this zone."),
        ("/no-computed-frost-date/", "Cities with no computed 32°F frost date",
         "Where NOAA left the spring 32°F date uncomputed."),
    ])
    end_related = related_reads([
        ("/zones/", "All USDA zones", "Hardiness bands with city lists."),
        ("/states/", "Frost dates by state", "Every state hub on this site."),
        ("/methodology/", "Sources and methods", "How stations and zones are chosen."),
        ("/longest-and-shortest-growing-season/", "Growing season extremes", "Shortest and longest NOAA seasons."),
    ])
    zone_verified = ANCHORAGE_REFRESH_H if zone == "5a" else ZONE_REFRESH_PUBLISHED_H
    body = f'''<article class="prose wide"><h1>USDA zone {E(zone)}: what to plant now</h1>
<p class="byline">By {BRAND}. Last verified {zone_verified}.</p>
<p class="answer">Zone {E(zone)} on the 2023 USDA Plant Hardiness Zone Map is an average annual extreme minimum of {E(zrange)}°F. It is not a frost date and not a sowing date.</p>
{frost_html}
{compare_box(zone, near, states)}
{mid_related}
<h2>Cities in this zone</h2><ul class="cols">{"".join(rows)}</ul>
<h2>What to plant now</h2>
<p id="now-label">Planting notes below are grouped by state, because extension calendars are not the same across a zone. With JavaScript on, the current month is marked inside any month list.</p>
<noscript><p>Find the current month inside any month list below.</p></noscript>
{"".join(blocks)}
<h2>Related hubs</h2>
<p>States with a city in this zone: {state_links}. <a href="/states/">All states</a>.</p>
<p>Adjacent zone numbers on this site: {near_html}. <a href="/zones/">All zones</a>.</p>
{end_related}
{faq_html(faqs)}
<p class="note">Zone source: <a href="{PHZM}" rel="nofollow noopener">USDA Plant Hardiness Zone Map</a>, ZIP tables from the <a href="{PRISM}" rel="nofollow noopener">PRISM Climate Group</a>. A city's zone is the ZIP code whose centroid is nearest the city center. Frost dates: <a href="{NOAA_HOME}" rel="nofollow noopener">NOAA NCEI 1991 to 2020 climate normals</a>.</p>
</article>'''
    page(path, f"USDA zone {zone}: what to plant now",
         f"USDA zone {zone} ({zrange}°F): NOAA frost dates for cities in this band, plus planting notes where transcribed.",
         body, [("/", "Home"), ("/zones/", "Zones"), (path, f"Zone {zone}")],
         [article(f"USDA zone {zone}", path, published=PUBLISHED, modified=ANCHORAGE_REFRESH if zone == "5a" else ZONE_REFRESH_PUBLISHED), faq_ld(faqs)],
         nav_current="/zones/", lastmod=ANCHORAGE_REFRESH if zone == "5a" else ZONE_REFRESH_PUBLISHED)

def growing_season_page(cities):
    path = "/longest-and-shortest-growing-season/"
    data = []
    for c in cities:
        gsl = gsl_days(c["station_rec"]["dates"].get("prbgsl-t32fp50", ""))
        if gsl is not None:
            data.append((c, gsl))
    top = max(g for _, g in data)
    bottom_city, bottom_gsl = min(data, key=lambda x: x[1])
    longest = sorted((d for d in data if d[1] == top), key=lambda x: -x[0]["pop"])
    not_computed_in_longest = sum(1 for c, _ in longest if spring50(c) is None)
    shortest = sorted(data, key=lambda x: x[1])[:20]

    def row(c, gsl, rank=None):
        sp = spring50(c) or "Not computed"
        fa = fall50(c) or "Not computed"
        lead = f"<td>No. {rank}</td>" if rank is not None else ""
        return (f'{"<tr>"}{lead}<td><a href="/{c["st"].lower()}/{c["slug"]}/">{E(c["name"])}, {E(US[c["st"]])}</a></td>'
                f"<td>{E(sp)}</td><td>{E(fa)}</td><td>{gsl:.0f} days</td></tr>")

    longest_rows = "".join(row(c, g) for c, g in longest)
    shortest_rows = "".join(row(c, g, i + 1) for i, (c, g) in enumerate(shortest))
    h1 = "US cities with the longest and shortest growing season"
    desc = (f"NOAA median growing season at 32°F: {len(longest)} of {len(data)} cities on this site tie for longest "
            f"at {top:.0f} days, {bottom_city['name']}, {US[bottom_city['st']]} is shortest at {bottom_gsl:.0f}.")
    faqs = [
        ("What does a 365 day growing season mean?",
         "NOAA's growing season length at 32°F is the number of days, in the middle year of the 1991 to 2020 record, "
         "between the last spring freeze and the first fall freeze at that station. A figure of 365 days means the "
         "station's own history did not show a 32°F freeze often enough, in at least half of those years, for NOAA to "
         "compute a season shorter than the full year. It does not mean a 32°F reading is impossible there, only that "
         "NOAA's median figure for this element is the full year."),
        ("Why does a city with a 365 day season still say Not computed for the spring frost date?",
         "Growing season length and the last spring 32°F date are two different NOAA elements, computed from different "
         "parts of the station record. A station can have enough data for NOAA to publish a growing season figure while "
         "not having enough qualifying years to publish a separate last spring 32°F date, which NOAA then flags -9999. "
         "This site's cities with no computed 32°F frost date page lists which stations that happens at."),
        ("Does this list change often?",
         "No. It is built from the NOAA 1991 to 2020 climate normals, the same one time retrieval every city page on "
         "this site uses. NOAA does not update that record until the next normals period, expected in 2030."),
    ]
    body = f'''<article class="prose wide"><h1>{E(h1)}</h1>
<p class="byline">By {BRAND}. Published {GROWING_SEASON_PAGES_PUBLISHED_H}, from NOAA data retrieved {PUBLISHED_H}.</p>
<div class="answer"><p>{len(longest)} of the {len(data)} cities on this site tie for the longest NOAA median growing season at 32°F, {top:.0f} days. The shortest is {E(bottom_city["name"])}, {E(US[bottom_city["st"]])}, at {bottom_gsl:.0f} days.</p></div>
<p class="note">These are 1991 to 2020 climate normals, not a forecast. A given year can run shorter or longer than the median. This is not agricultural advice.</p>
<h2>Cities tied for the longest growing season</h2>
<p>NOAA computed a 365 day median growing season at 32°F for these {len(longest)} cities, sorted by 2024 Census population. {not_computed_in_longest} of them also have no separate computed last spring 32°F date (shown as Not computed below); see <a href="/no-computed-frost-date/">why that NOAA element is not computed</a> for those cities.</p>
<div class="tablewrap"><table class="list"><thead><tr><th>City</th><th>Last spring 32°F</th><th>First fall 32°F</th><th>Growing season</th></tr></thead><tbody>{longest_rows}</tbody></table></div>
<h2>Cities with the shortest growing season</h2>
<p>The 20 cities on this site with the shortest NOAA median growing season at 32°F.</p>
<div class="tablewrap"><table class="list"><thead><tr><th>Rank</th><th>City</th><th>Last spring 32°F</th><th>First fall 32°F</th><th>Growing season</th></tr></thead><tbody>{shortest_rows}</tbody></table></div>
<h2>How this list is built</h2>
<p>The growing season figure is NOAA's own prbgsl-t32fp50 element from the same 1991 to 2020 Climate Normals by station archive every city page on this site cites, read from the same per station cache (see <a href="/methodology/">sources and methods</a>). It is not calculated here by subtracting the spring and fall dates; NOAA publishes it as its own figure, and a station can carry it even where the separate spring or fall date is not computed.</p>
<h2>Related pages</h2>
<p>Open a city above for its full freeze probability table and any planting calendar. <a href="/no-computed-frost-date/">Cities with no computed 32°F frost date</a>. <a href="/states/">All states</a>. <a href="/zones/">All USDA zones</a>.</p>
{faq_html(faqs)}
<section class="sources"><h2>Sources</h2><ul>
<li><a href="{NOAA_HOME}" rel="nofollow noopener">NOAA NCEI U.S. Climate Normals 1991 to 2020</a></li>
<li><a href="{NOAA_METHOD}" rel="nofollow noopener">NOAA Normals Calculation Methodology 2020</a></li>
<li><a href="{CENSUS_POP}" rel="nofollow noopener">U.S. Census Bureau, Population Estimates Program, sub-est2024</a></li>
</ul>
<p class="note">Normals retrieved {PUBLISHED_H} from the NCEI 1991 to 2020 annual and seasonal by station archive (v1.0.1, file dated 20230404), the same retrieval used on every city page.</p></section>
</article>'''
    crumbs = [("/", "Home"), (path, "Longest and shortest growing season")]
    schemas = [article(h1, path, GROWING_SEASON_PAGES_PUBLISHED), faq_ld(faqs)]
    page(path, "US cities with the longest and shortest growing season", desc, body, crumbs, schemas,
         lastmod=GROWING_SEASON_PAGES_PUBLISHED)

def no_computed_frost_page(cities):
    path = "/no-computed-frost-date/"
    rows_data = [c for c in cities if spring50(c) is None]
    rows_data.sort(key=lambda c: (US[c["st"]], c["name"]))
    states_here = sorted({US[c["st"]] for c in rows_data})

    def row(c):
        t36 = fmt_date(c["station_rec"]["dates"].get("prblst-t36fp50", "")) or "Not published"
        gsl = gsl_days(c["station_rec"]["dates"].get("prbgsl-t32fp50", ""))
        gsl_s = f"{gsl:.0f} days" if gsl is not None else "Not computed"
        return (f'<tr><td><a href="/{c["st"].lower()}/{c["slug"]}/">{E(c["name"])}, {E(US[c["st"]])}</a></td>'
                f"<td>{E(t36)}</td><td>{E(gsl_s)}</td></tr>")

    rows = "".join(row(c) for c in rows_data)
    h1 = "Cities with no computed 32°F frost date"
    desc = (f"{len(rows_data)} of {len(cities)} cities on this site have no NOAA computed last spring 32°F freeze date, "
            f"all in {', '.join(states_here)}. What NOAA computed instead is on this page.")
    faqs = [
        ("Why does my city's page say Not computed for the 32°F frost date?",
         "NOAA flags an element -9999 when the station's history did not show that threshold crossed in enough of the "
         "1991 to 2020 years to compute a median, or set a measurement flag of Y for the same reason. For these cities "
         "that is the last spring freeze at 32°F. The NOAA Normals Calculation Methodology 2020 document, linked in "
         "the sources below, defines those flags."),
        ("Does Not computed mean this city never freezes?",
         "No single normals record can promise that. It means NOAA's own station file did not have enough qualifying "
         "years at 32°F to publish a median for that one element. NOAA did compute the milder 36°F threshold for the "
         "same stations, shown on this page, and the growing season length element separately."),
        ("Which states have cities with no computed 32°F date?",
         f"On this site: {', '.join(states_here)}. That follows from which stations NOAA picked for frost products in "
         "this build, not a claim that every warm weather city in the United States is missing this element."),
    ]
    body = f'''<article class="prose wide"><h1>{E(h1)}</h1>
<p class="byline">By {BRAND}. Published {GROWING_SEASON_PAGES_PUBLISHED_H}, from NOAA data retrieved {PUBLISHED_H}.</p>
<div class="answer"><p>{len(rows_data)} of the {len(cities)} cities on this site have no NOAA computed median last spring freeze at 32°F. All of them are in {E(", ".join(states_here))}, and all show a 365 day median growing season at 32°F, meaning the station's own record rarely or never crosses that threshold.</p></div>
<p class="note">These are 1991 to 2020 climate normals, not a forecast. A given year can still freeze. This is not agricultural advice.</p>
<h2>What NOAA computed instead</h2>
<p>For these stations NOAA did compute a milder 36°F last spring date, shown below, plus the growing season length used on <a href="/longest-and-shortest-growing-season/">the longest and shortest growing season page</a>. The 32°F table on each city page still shows the 90 and 10 percent figures where NOAA published them.</p>
<div class="tablewrap"><table class="list"><thead><tr><th>City</th><th>Last spring 36°F (50 percent)</th><th>Growing season at 32°F (days)</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Related pages</h2>
<p>Open a city above for its full freeze probability table. <a href="/longest-and-shortest-growing-season/">Longest and shortest growing season</a>. <a href="/states/">All states</a>. <a href="/zones/">All USDA zones</a>.</p>
{faq_html(faqs)}
<section class="sources"><h2>Sources</h2><ul>
<li><a href="{NOAA_HOME}" rel="nofollow noopener">NOAA NCEI U.S. Climate Normals 1991 to 2020</a></li>
<li><a href="{NOAA_METHOD}" rel="nofollow noopener">NOAA Normals Calculation Methodology 2020</a></li>
</ul>
<p class="note">Normals retrieved {PUBLISHED_H} from the NCEI 1991 to 2020 annual and seasonal by station archive (v1.0.1, file dated 20230404), the same retrieval used on every city page.</p></section>
</article>'''
    crumbs = [("/", "Home"), (path, "No computed frost date")]
    schemas = [article(h1, path, GROWING_SEASON_PAGES_PUBLISHED), faq_ld(faqs)]
    page(path, "Cities with no computed 32°F frost date", desc, body, crumbs, schemas,
         lastmod=GROWING_SEASON_PAGES_PUBLISHED)

def home(cities):
    by_state = {}
    for c in cities:
        by_state.setdefault(c["st"], []).append(c)
    state_links = []
    for st in sorted(by_state, key=lambda s: US[s]):
        state_links.append(f'<li><a href="/states/{st.lower()}/">{E(US[st])}</a> ({len(by_state[st])})</li>')
    missing = [US[st] for st in US if st not in by_state]
    featured_keys = [("TX", "austin"), ("CO", "denver"), ("GA", "atlanta"), ("IL", "chicago"),
                     ("MN", "minneapolis"), ("OR", "portland"), ("WA", "seattle"), ("NY", "new-york"),
                     ("MA", "boston"), ("PA", "philadelphia"), ("NC", "raleigh"), ("TN", "nashville"),
                     ("MO", "kansas-city"), ("OH", "columbus"), ("UT", "salt-lake-city"), ("AZ", "phoenix"),
                     ("TX", "dallas"), ("CA", "sacramento"), ("MI", "detroit")]
    index = {(c["st"], c["slug"]): c for c in cities}
    feats = []
    for key in featured_keys:
        c = index.get(key)
        if not c:
            raise SystemExit("missing featured " + str(key))
        sp = spring50(c) or "not computed"
        feats.append(f'<li><a href="/{c["st"].lower()}/{c["slug"]}/">{E(c["name"])}, {E(US[c["st"]])}</a>: last 32°F {E(sp)}</li>')
    zones = sorted(set(c["zone"] for c in cities if c.get("zone")), key=lambda z: (int(z[:-1]), z[-1]))
    zlinks = " ".join(f'<a href="/zones/{z}/">{z}</a>' for z in zones)
    faqs = [
        ("Which frost date should I use?",
         "On this site the headline frost date is NOAA's 50 percent probability date at 32°F. For spring, that is the median date with a 50 percent chance the last freeze is still to come on or after it. For fall, it is the median date with a 50 percent chance the first freeze is on or before it. It describes 1991 to 2020, not the coming week. The 10 percent spring date is later, and it is the more cautious planting marker."),
        ("Where do the dates come from?",
         "NOAA National Centers for Environmental Information, U.S. Climate Normals for 1991 to 2020, at the nearest station that publishes a frost product, within 50 miles of the city center. Hardiness zones are the 2023 USDA map, via the PRISM ZIP code tables. Planting dates are transcribed only from the state extension page named on the city."),
        ("Why is a city missing?",
         "v1 includes incorporated places with a 2024 population of at least 100,000 when a frost product station is within 50 miles. Smaller cities, and Honolulu, are not in this build. Honolulu's airport station does not have a computed 32°F date. Delaware, Hawaii, Maine, Vermont, West Virginia, and Wyoming have no page for that reason."),
    ]
    body = f'''<article><section class="hero"><h1>Frost dates and a planting calendar for U.S. cities</h1>
<p class="answer">Average last spring and first fall freeze dates at 32°F, from NOAA 1991 to 2020 climate normals, for {len(cities)} of the largest U.S. cities. Each page names the weather station, the USDA hardiness zone, and a planting calendar only where that state's cooperative extension published timing we transcribed.</p>
<p class="btnrow"><a class="btn" href="#find">Find a city</a> <a class="btn alt" href="/methodology/">Sources and methods</a></p></section>
<h2 id="find">Find a city</h2>
<form class="search" role="search" action="/states/" method="get"><label for="city-q">City or state</label>
<input id="city-q" name="q" type="search" autocomplete="off" placeholder="Austin, Denver, Miami" enterkeyhint="search"></form>
<ul class="results" id="city-results"></ul>
<noscript><p>Search uses JavaScript. The state list below works without it.</p></noscript>
<h2>How a frost date works</h2>
<p>NOAA's spring probability date is the chance the last freeze happens on or after that day. The fall date is the chance the first freeze happens on or before that day. The 50 percent date is the median. The 10 percent spring date is later, and it is the more cautious planting marker. A date on this site is not a forecast, and a cold spring can still freeze after it.</p>
<h2>States</h2><ul class="cols">{"".join(state_links)}</ul>
<p class="note">No city page in this build for {E(", ".join(missing))}. Those states have no incorporated place of 100,000 people within 50 miles of a station with a published frost product, or, for Hawaii, the Honolulu airport station did not get a computed 32°F date.</p>
<h2>Large cities</h2><ul class="cols">{"".join(feats)}</ul>
<h2>Hardiness zones</h2><p>What to plant now, by USDA zone: {zlinks}.</p>
<h2>More lookups</h2>
<p><a href="/longest-and-shortest-growing-season/">Which cities have the longest and shortest growing season</a>. <a href="/no-computed-frost-date/">Cities with no computed 32°F frost date</a>. <a href="/guides/hard-freeze-vs-frost/">Hard freeze, frost, and a freeze warning</a>.</p>
{faq_html(faqs)}
</article>'''
    page("/", "Which frost date should I use? | Which Frost",
         f"Median last and first 32°F frost dates for {len(cities)} U.S. cities, from NOAA 1991 to 2020 normals, plus USDA zones.",
         body, None, [article("Frost dates and a planting calendar for U.S. cities", "/"), faq_ld(faqs)], nav_current="/")

def states_index(cities):
    by_state = {}
    for c in cities:
        by_state.setdefault(c["st"], []).append(c)
    items = []
    for st in sorted(US):
        if st in by_state:
            items.append(f'<li><a href="/states/{st.lower()}/">{E(US[st])}</a> ({len(by_state[st])} cities)</li>')
        else:
            items.append(f"<li>{E(US[st])}: no city in this build</li>")
    faqs = [(
        "Which states have a frost date page?",
        "Delaware, Hawaii, Maine, Vermont, West Virginia, and Wyoming have no city page in this build. Every other state, and the District of Columbia, has one. A city is listed when it is an incorporated place of at least 100,000 people and a NOAA frost station is within 50 miles.")]
    body = f'''<article class="prose"><h1>Frost dates by state</h1>
<p class="byline">By {BRAND}. Last verified {PUBLISHED_H}.</p>
<p>Pick a state to see every city page, the median 32°F dates, and the zone. Each state page links back to its cities.</p>
<ul class="cols">{"".join(items)}</ul>
<p><a href="/longest-and-shortest-growing-season/">Longest and shortest growing season, across all cities</a>. <a href="/no-computed-frost-date/">Cities with no computed 32°F frost date</a>. <a href="/guides/hard-freeze-vs-frost/">Hard freeze, frost, and a freeze warning</a>.</p>
{faq_html(faqs)}</article>'''
    page("/states/", "Which frost date should I use by state",
         "State by state frost dates for the largest U.S. cities, from NOAA 1991 to 2020 climate normals.",
         body, [("/", "Home"), ("/states/", "States")],
         [article("Frost dates by state", "/states/"), faq_ld(faqs)], nav_current="/states/")

def zones_index(cities):
    zones = {}
    for c in cities:
        if c.get("zone"):
            zones.setdefault(c["zone"], []).append(c)
    items = []
    for z in sorted(zones, key=lambda z: (int(z[:-1]), z[-1])):
        rng = zones[z][0].get("zone_range") or ""
        items.append(f'<li><a href="/zones/{z}/">Zone {z}</a> ({E(rng)}°F, {len(zones[z])} cities)</li>')
    faqs = [(
        "Which USDA zone should I use for a frost date?",
        "A USDA zone is the average coldest winter temperature, in 5°F steps on the 2023 map. It is not a vegetable sowing date and not a frost date. Open a zone for the cities in it, then open a city for the NOAA 50 percent frost date.")]
    body = f'''<article class="prose"><h1>USDA zones and what to plant now</h1>
<p class="byline">By {BRAND}. Last verified {PUBLISHED_H}.</p>
<p>A USDA zone is the average coldest winter temperature, in 5°F steps on the 2023 map. It is not a vegetable sowing date. Open a zone for the cities in it and any state extension timing we transcribed. City pages link back here.</p>
<ul class="cols">{"".join(items)}</ul>
<p><a href="/longest-and-shortest-growing-season/">Longest and shortest growing season, across all cities</a>. <a href="/no-computed-frost-date/">Cities with no computed 32°F frost date</a>.</p>
{faq_html(faqs)}
<p class="note">Source: <a href="{PHZM}" rel="nofollow noopener">USDA Plant Hardiness Zone Map</a> and <a href="{PRISM}" rel="nofollow noopener">PRISM ZIP tables</a>.</p>
</article>'''
    page("/zones/", "USDA zones: what to plant now",
         "USDA hardiness zones for cities on Which Frost, and what to plant now where a state extension calendar was transcribed.",
         body, [("/", "Home"), ("/zones/", "Zones")],
         [article("USDA zones", "/zones/"), faq_ld(faqs)], nav_current="/zones/")

def simple(path, title, desc, h1, inner, crumb, legal=False, noindex=False, faqs=None, lastmod=None, published=None, modified=None):
    if faqs:
        inner += faq_html(faqs)
    body = f'<article class="prose"><h1>{E(h1)}</h1>{inner}</article>'
    crumbs = [("/", "Home"), (path, crumb)]
    schemas = [] if noindex else [article(h1, path, published=published, modified=modified or lastmod)]
    if faqs and not noindex:
        schemas.append(faq_ld(faqs))
    page(path, title, desc, body, crumbs, schemas, noindex=noindex, legal=legal, lastmod=lastmod)

def hard_freeze_guide(cities):
    """NWS wording for frost, freeze, and hard freeze, plus two extension pages.
    The hero file is assigned and may be absent. Do not invent a substitute photo.
    """
    path = "/guides/hard-freeze-vs-frost/"
    anchorage = lookup_city(cities, "AK", "anchorage")
    minneapolis = lookup_city(cities, "MN", "minneapolis")
    raw32 = anchorage["station_rec"]["dates"].get("prblst-t32fp50", "")
    raw28 = anchorage["station_rec"]["dates"].get("prblst-t28fp50", "")
    t36 = fmt_date(anchorage["station_rec"]["dates"].get("prblst-t36fp50", ""))
    t32 = spring50(anchorage)
    t28 = fmt_date(raw28)
    gap = int(raw32[3:5]) - int(raw28[3:5]) if raw32[:2] == raw28[:2] else None
    uaf = "https://www.uaf.edu/ces/publications/database/gardening/easy-steps-gardening-alaska.php"
    uf = "https://edis.ifas.ufl.edu/publication/cv106"
    h1 = "Hard freeze, frost, and a freeze warning are not the same thing"
    title = "Hard freeze vs frost: what each does to plants"
    desc = "Frost can form in the middle 30s. A freeze warning is 32°F or below. A hard freeze is 28°F, and it is no longer its own NWS product."
    faqs = [
        ("Is a frost the same thing as a freeze?",
         "No. The NWS glossary describes frost as ice crystals on surfaces, often while the thermometer in the air is still in the middle 30s. "
         "A freeze is surface air at 32°F or below over a wide area for a significant time. A garden can get frost without the air reaching 32°F."),
        ("Does a freeze warning still cover a hard freeze?",
         "Yes. Service Change Notice 23-44, updated 26 March 2024, folded the hard freeze watch and the hard freeze warning into the freeze watch and the freeze warning, effective on or about 1 October 2024. "
         "The warning text can still say hard freeze when the forecast low is 28°F or lower. There is no longer a separate Hard Freeze Warning product."),
        ("Can I treat the date on a city page as tonight's warning?",
         "No. A city page is a 1991 to 2020 median from one NOAA station. A freeze warning is a forecast for a particular night. "
         "The median is not a guarantee that this year will match it, and it is not agricultural advice."),
    ]
    mid = related_reads([
        ("/ak/anchorage/", "Anchorage frost dates",
         f"Worked example: median spring dates of {t36} at 36°F, {t32} at 32°F, and {t28} at 28°F."),
        ("/states/ak/", "Alaska frost dates",
         "Why that station is an estimate, and how other zone 5a cities differ."),
        ("/zones/5a/", "USDA zone 5a",
         "The winter band is not a frost date. The city rows show the spread."),
        ("/methodology/", "Sources and methods",
         "Which station a city page uses, and what the NOAA flags mean."),
    ])
    end = related_reads([
        ("/longest-and-shortest-growing-season/", "Longest and shortest growing season",
         "NOAA's own season length, ranked for every city on this site."),
        ("/no-computed-frost-date/", "No computed 32°F frost date",
         "Stations where NOAA did not publish a median last spring freeze."),
        ("/states/", "Frost dates by state",
         "Pick a state, then a city, and read the 36, 32, and 28 degree columns."),
        ("/zones/", "USDA zones",
         "Winter minimum bands. Open a city for the frost date."),
    ])
    body = f'''<article class="prose wide"><h1>{E(h1)}</h1>
<p class="byline">By {BRAND}. Published {HARD_FREEZE_GUIDE_PUBLISHED_H}. Last verified {HARD_FREEZE_GUIDE_PUBLISHED_H}.</p>
<figure class="hero-photo"><a href="/image-policy/"><img src="{FROST_HERO}" width="1200" height="675" alt="Frost on a lawn in early daylight"></a>
<figcaption><a href="/image-policy/">AI-generated image. Image policy.</a></figcaption></figure>
<div class="answer"><p>A frost is ice on the plant, and the air can still be in the middle 30s. A freeze warning is for air at or below 32°F. A hard freeze is 28°F or lower, long enough that the National Weather Service says it kills most vegetation. Since about 1 October 2024, a hard freeze is no longer its own warning. Those words can still appear inside a freeze warning.</p></div>
<p class="note">The dates on this site are 1991 to 2020 medians, not a forecast for tonight and not a guarantee for this year. Nothing here is agricultural advice.</p>
<h2>Three words, three temperatures</h2>
<p>The <a href="{NWS_FROST}" rel="nofollow noopener">NWS glossary</a> describes frost as thin ice crystals on the ground or on objects. It forms the way dew does, except the surface falls below 32°F, and it often happens with the thermometer in the middle 30s because frost is mostly radiational cooling. A frost advisory, on that same page, is for widespread frost in the growing season, usually with surface temperatures in the middle 30s. The <a href="{NWS_COLD}" rel="nofollow noopener">NWS cold weather page</a> tells a reader to be aware: areas of frost are expected or occurring, and sensitive plants are at risk.</p>
<p>A freeze, in the <a href="{NWS_FREEZE}" rel="nofollow noopener">glossary</a>, is surface air expected at 32°F or below over a wide area for a climatologically significant time. The cold weather page marks a freeze warning as the product to act on: temperatures forecast below 32°F for a long period, a threshold it says kills some commercial crops and residential plants. A freeze watch is the earlier heads up, when widespread freezing is possible in the next 24 to 36 hours, used in autumn until the growing season ends and in spring when it starts.</p>
<p>A hard freeze, same glossary, is surface air at 28°F or lower for an extended period, killing most types of vegetation. The cold weather page says temperatures below 28°F for an extended period can kill most commercial crops and residential plants. <a href="{NWS_RAH}" rel="nofollow noopener">NWS Raleigh</a> prints local cutoffs that match those round numbers: 33 to 36°F for a frost advisory, 32°F or lower for a freeze warning, 28°F or lower for a hard freeze. That is one office. It is not a rule that every office uses the same edges.</p>
<div class="tablewrap"><table class="list"><caption>How the NWS names the cold, checked {HARD_FREEZE_GUIDE_PUBLISHED_H}.</caption>
<thead><tr><th>Word</th><th>Temperature the NWS cites</th><th>Product</th></tr></thead><tbody>
<tr><th scope="row">Frost</th><td>Often the middle 30s, ice on the surface</td><td>Frost advisory during the local growing season</td></tr>
<tr><th scope="row">Freeze</th><td>32°F or below, widespread, for a long enough time</td><td>Freeze warning. A watch can come 24 to 36 hours ahead</td></tr>
<tr><th scope="row">Hard freeze</th><td>28°F or lower for an extended period</td><td>No longer a separate warning. The freeze warning can say hard freeze</td></tr>
</tbody></table></div>
<p><a href="{NWS_SCN}" rel="nofollow noopener">Service Change Notice 23-44</a> (updated 26 March 2024) set that consolidation for on or about 1 October 2024. The hard freeze watch became a freeze watch, and the hard freeze warning became a freeze warning. The notice says the freeze warning may still use the words "hard freeze" in the body, for example in the "what" line, when the shelter temperature is forecast at 28°F or lower. The <a href="{NWS_HAZ}" rel="nofollow noopener">NWS hazard simplification note</a> describes the same change. Both pages were open on {HARD_FREEZE_GUIDE_PUBLISHED_H}.</p>
{mid}
<h2>What extension services say the cold does to plants</h2>
<p>The forecast words are national. The plants are not. Two extension publications, read on {HARD_FREEZE_GUIDE_PUBLISHED_H}, draw the line in different gardens.</p>
<p><a href="{uaf}" rel="nofollow noopener">University of Alaska Fairbanks Cooperative Extension, HGA-00134</a>, says radish, turnip, carrot, leaf lettuce, and pea seed can go in before the danger of frost is past. It also lists a longer set, including beans, that may be seeded up to two weeks before the last killing frost with little danger of loss, and then says beans freeze easily and that an early bean planting needs cover when the night falls near freezing. Tomatoes, it says, go outside after the danger of frost is past and warm weather looks likely to hold. A garden in a frost pocket should be planted only with frost resistant vegetables. A few feet of extra elevation can add days. Those are Alaska sentences. The counted weeks, using a city's own NOAA median, are on the city page where this site has transcribed them. <a href="/ak/anchorage/">Anchorage</a> is the one.</p>
<p><a href="{uf}" rel="nofollow noopener">University of Florida IFAS, Row Covers for Growth Enhancement (CV106)</a>, is about covers in a state where a frost is an occasional event rather than the frame of the season. For frost protection it names soil cover for young crops (commonly potatoes), sprinkler irrigation, and row covers. On sprinklers, UF says freezing water gives up heat to the leaf, the plant stays protected only while water keeps coming in ample quantity, and the method is less effective in wind. On covers, UF says a nonwoven material of about 0.5 ounce per yard protects to about 30°F, and material in the 1.5 to 2.0 ounce range protects to about 25°F. Wire hoops keep the cover off the leaves. This page does not turn those Florida figures into a date for any city.</p>
<h2>How a city page on this site lines up</h2>
<p>Each city table has three spring thresholds and three fall thresholds: 36°F, 32°F, and 28°F. Those are NOAA's freeze probability normals, not a warning. The 50 percent column is the median. At <a href="/ak/anchorage/">Anchorage</a> the median last spring dates are {E(t36)} at 36°F, {E(t32)} at 32°F, and {E(t28)} at 28°F, {gap} days from the 28°F median to the 32°F median. Read that as a spread in the climate record. It is not a claim that a hard freeze warning will fall on {E(t28)} this year. The <a href="/states/ak/">Alaska page</a> shows why a shared USDA zone does not share that spread: <a href="/mn/minneapolis/">Minneapolis</a>, also zone 5a, has a median last 32°F freeze on {E(spring50(minneapolis))}.</p>
<aside class="compare" aria-label="Check another lookup">
<h2>Check another city</h2>
<p>Open the <a href="/states/">state list</a> and pick a city. The 36°F, 32°F, and 28°F columns are the three words on this page. <a href="/ak/anchorage/">Anchorage</a> is the worked example. <a href="/zones/5a/">Zone 5a</a> shows cities that share a winter band and do not share a frost date.</p>
<p class="note">A median is not a warning, and a zone number is not a planting day.</p>
</aside>
{end}
{faq_html(faqs)}
<section class="sources"><h2>Sources</h2><ul>
<li><a href="{NWS_FROST}" rel="nofollow noopener">NWS glossary: frost and frost advisory</a></li>
<li><a href="{NWS_FREEZE}" rel="nofollow noopener">NWS glossary: freeze and hard freeze</a></li>
<li><a href="{NWS_COLD}" rel="nofollow noopener">NWS: freeze watch, freeze warning, and frost advisory</a></li>
<li><a href="{NWS_SCN}" rel="nofollow noopener">NWS Service Change Notice 23-44, updated 26 March 2024</a></li>
<li><a href="{NWS_HAZ}" rel="nofollow noopener">NWS hazard simplification note on cold products</a></li>
<li><a href="{NWS_RAH}" rel="nofollow noopener">NWS Raleigh frost and freeze criteria</a></li>
<li><a href="{uaf}" rel="nofollow noopener">UAF Cooperative Extension HGA-00134, 16 Easy Steps to Gardening in Alaska</a></li>
<li><a href="{uf}" rel="nofollow noopener">UF IFAS, Row Covers for Growth Enhancement (CV106)</a></li>
<li><a href="{NOAA_HOME}" rel="nofollow noopener">NOAA NCEI U.S. Climate Normals 1991 to 2020</a></li>
</ul>
<p class="note">NWS, UAF, UF IFAS, and the NCEI product page were checked {HARD_FREEZE_GUIDE_PUBLISHED_H}. The Anchorage dates are the same station cache retrieved {PUBLISHED_H}.</p>
</section>
</article>'''
    crumbs = [("/", "Home"), (path, "Hard freeze vs frost")]
    page(path, title, desc,
         body, crumbs,
         [article(h1, path, published=HARD_FREEZE_GUIDE_PUBLISHED, modified=HARD_FREEZE_GUIDE_PUBLISHED, image=FROST_HERO),
          faq_ld(faqs)],
         lastmod=HARD_FREEZE_GUIDE_PUBLISHED)

def legal_pages():
    simple("/about/", f"About {BRAND}", "What Which Frost is, and how frost dates and planting notes are chosen.",
           f"About {BRAND}", f'''<p class="byline">By {BRAND}. Last verified {PUBLISHED_H}.</p>
<p>Which Frost is an independent reference for the last spring freeze and the first fall freeze in large U.S. cities, plus a planting calendar where a state extension has published timing we can cite.</p>
<h2>What we publish</h2><p>Every city page names one NOAA station, the 1991 to 2020 normals, and the distance from the city center. If NOAA did not compute a date, the page says so. We do not fill a gap with a guess.</p>
<h2>What we leave out</h2><p>We do not publish a vegetable date unless it comes from that state's cooperative extension. Many states are still open. See <a href="/methodology/">sources and methods</a>.</p>
<p>Something look wrong? <a href="/contact/">Tell us</a> and we will re check the station file.</p>''', "About")
    simple("/methodology/", "Which frost date: sources and methods",
           "How Which Frost picks a NOAA station, reads frost probability dates, assigns a USDA zone, and copies extension planting dates.",
           "Sources and methods", f'''<p class="byline">By {BRAND}. Last verified {PUBLISHED_H}.</p>
<h2>Frost dates</h2>
<p>The numbers are the NOAA NCEI U.S. Climate Normals for 1991 to 2020, annual and seasonal file, version 1.0.1 (archive dated 20230404). Retrieved {PUBLISHED_H}. Product page: <a href="{NOAA_HOME}" rel="nofollow noopener">U.S. Climate Normals</a>. The probability definition is in the <a href="{NOAA_METHOD}" rel="nofollow noopener">Normals Calculation Methodology 2020</a>.</p>
<p>For spring, the published date is the chance the last freeze at that threshold happens on or after that date. For fall, it is the chance the first freeze happens on or before that date. We show 36°F, 32°F, and 28°F at 10, 50, and 90 percent. The growing season length is NOAA's own 50 percent figure for 32°F, the number of days the season lasts at least that long in half of years. We do not subtract the two dates to invent a length.</p>
<p>Special values stay special. -9999 with flag Y is "not computed." -6666 is "too rare to compute" (under a 10 percent chance the temperature occurs). -4444 is "year round risk."</p>
<h2>Which station</h2>
<p>The station inventory is the NCEI 30 year list. A city is matched to the nearest station that has a frost product, using the Census Bureau 2024 Gazetteer city point. The cap is 50 miles. Farther than that, the city is skipped. We do not blend two stations. The page shows how many years NOAA used and the completeness flag (S, R, P, or E) from the NCEI readme.</p>
<h2>Which cities</h2>
<p>Incorporated places in the Census Bureau Population Estimates Program file sub-est2024, population at least 100,000 in the 2024 estimate. Census place names that are consolidated governments are shown under the common city name, and the census name is printed on the page. Urban Honolulu is omitted: Honolulu International Airport does not have a computed 32°F date (flag Y), and the nearest station that does is about 110 miles away, on Maui.</p>
<h2>Hardiness zones</h2>
<p>The zone is the 2023 USDA Plant Hardiness Zone Map value for the ZIP code whose centroid is nearest the city center, from the PRISM Climate Group ZIP tables and the Census 2024 ZCTA gazetteer. The match has to be within 30 miles or we leave the zone off. A neighborhood can sit in a different zone. We do not redraw the map.</p>
<h2>Planting calendars</h2>
<p>Colorado uses CSU Extension GardenNotes #720 (reviewed September 2024). Offsets are counted from the city's NOAA 50 percent last spring freeze. Soil temperature rules in that guide are not turned into dates, because we do not have those soil normals.</p>
<p>Georgia uses University of Georgia Extension Circular 943 (full review 10 March 2026), as the middle Georgia calendar. The north and south adjustments in that circular are quoted. They are not applied as a new set of dates.</p>
<p>New Hampshire uses the UNH Extension fact sheet "Growing Vegetables: When to Plant Your Vegetable Garden," retrieved {PUBLISHED_H}. Offsets are counted from the NOAA date, not from the Memorial Day example in that fact sheet.</p>
<p>Every other state has no transcribed calendar in this build. The city page says so.</p>
<h2>Checked</h2><p>Station files and the city match were retrieved {PUBLISHED_H}. Rebuild from the cache in <code>_build/cache</code> without downloading again. Re check when NCEI publishes a new normals period.</p>
<p>City pages are listed by <a href="/states/">state</a> and by <a href="/zones/">USDA zone</a>, or compared directly on the <a href="/longest-and-shortest-growing-season/">longest and shortest growing season</a> and <a href="/no-computed-frost-date/">no computed frost date</a> pages.</p>''', "Sources and methods",
           faqs=[
               ("How does Which Frost pick a station?",
                "A city is matched to the nearest NOAA station that has a frost product, using the Census Bureau 2024 Gazetteer city point. The cap is 50 miles. Farther than that, the city is skipped. Which Frost does not blend two stations."),
               ("Which planting calendars are transcribed?",
                "Colorado uses CSU Extension GardenNotes #720. Georgia uses University of Georgia Extension Circular 943. New Hampshire uses the UNH Extension fact sheet on when to plant a vegetable garden. Every other state has no transcribed calendar in this build."),
               ("Are there pages that compare cities to each other?",
                "The longest and shortest growing season page and the no computed frost date page both read the same per station cache as every city page and rank or group cities by one NOAA element, without adding a new source."),
           ])
    simple("/image-policy/", f"Image policy | {BRAND}", "Which Frost uses an original mark. The one scene picture is labeled AI-generated.",
           "Image policy", f'''<p class="byline">By {BRAND}. Last verified {HARD_FREEZE_GUIDE_PUBLISHED_H}.</p>
<p>The logo, favicon, and social image are original drawings made for this site: a navy square, a pale snowflake, and a gold center. They are not photographs, not a copy of a weather service mark, and not the USDA zone map.</p>
<p>City pages do not use photos of places. The <a href="/guides/hard-freeze-vs-frost/">hard freeze guide</a> uses one picture of frost on a lawn at dawn. That picture is AI-generated. It is not a photograph of a real yard, and it shows no person, no logo, and no readable text. The caption on that page links here.</p>''', "Image policy",
           lastmod=HARD_FREEZE_GUIDE_PUBLISHED, published=PUBLISHED, modified=HARD_FREEZE_GUIDE_PUBLISHED)
    simple("/disclaimer/", f"Disclaimer | {BRAND}", "Which Frost publishes climate averages, not a forecast and not agricultural, legal, or insurance advice.",
           "Disclaimer", f'''<p>Last updated {PUBLISHED_H}.</p>
<h2>Averages, not a forecast</h2><p>Frost dates are 30 year climate normals. A given year can freeze earlier or later than the median. Nothing on this site is a weather forecast. Check a forecast if you need the next few nights.</p>
<h2>Not professional advice</h2><p>Planting notes repeat a state extension publication and, where the publication uses an offset, count that offset from the NOAA median. This is not legal advice, not insurance guidance, and not agricultural advice. Crop choice, elevation, soil, and a cold spring are yours to judge. The extension page and the station file outrank this summary if they disagree.</p>
<h2>Stations and zones</h2><p>The nearest station is not the same as every backyard in the city. A zone from the nearest ZIP code centroid can differ from a hill or a valley a few miles away.</p>
<h2>Limitation of liability</h2><p>To the extent permitted by law, Joshua Israel Ventures LLC is not liable for any loss from use of this site. See the <a href="/terms/">terms of use</a>.</p>''', "Disclaimer", legal=True)
    simple("/terms/", f"Terms of Use | {BRAND}", "Terms of use for Which Frost (whichfrost.com).",
           "Terms of use", f'''<p>Last updated {PUBLISHED_H}. These terms govern your use of whichfrost.com ("Which Frost", "we", "us"). Which Frost is a trade name of Joshua Israel Ventures LLC, a Florida limited liability company. By using the site you agree to these terms.</p>
<h2>Information only</h2><p>The site publishes climate normals, zone lookups, and cited extension timing to help you plan a garden. It is not legal advice, not insurance guidance, and not agricultural advice. A frost date is not a promise about this year.</p>
<h2>Accuracy</h2><p>We cite the station and the publication. We make no warranty that a page is complete or free of error. Report a mistake on the <a href="/contact/">contact page</a>.</p>
<h2>Acceptable use</h2><p>You may read the site and share links. You may not scrape it in bulk, republish the original text or the compiled city tables without permission, misuse the contact form, or try to disrupt the site.</p>
<h2>Intellectual property</h2><p>Original text, the compiled tables, and the site design belong to Joshua Israel Ventures LLC. NOAA, Census, USDA, and extension names belong to their publishers and are used to identify sources.</p>
<h2>Third party services</h2><p>The site is hosted on GitHub Pages and links to NOAA, Census, USDA, PRISM, and extension sites. The contact form can send mail through FormSubmit. The public site loads Cloudflare Web Analytics, and it loads Google Analytics 4 only if you allow it. See the <a href="/privacy/">privacy policy</a>. We are not responsible for those services.</p>
<h2>Disclaimer of warranties and limitation of liability</h2><p>The site is provided "as is" and "as available". To the fullest extent permitted by law, Joshua Israel Ventures LLC disclaims all warranties, express or implied, and is not liable for indirect, incidental, special, consequential, or punitive damages, or any loss from use of the site. Our total liability for any claim relating to the site is limited to 100 U.S. dollars.</p>
<h2>Indemnity</h2><p>You agree to indemnify Joshua Israel Ventures LLC against claims arising from your misuse of the site or your breach of these terms.</p>
<h2>Governing law</h2><p>These terms are governed by the laws of the State of Florida, without regard to conflict of law rules. Disputes will be heard in the state or federal courts in Florida, and you consent to that jurisdiction.</p>
<h2>Changes</h2><p>We may update these terms. The date above is the latest version.</p>''', "Terms of use", legal=True)
    simple("/privacy/", f"Privacy Policy | {BRAND}", "Privacy policy for Which Frost (whichfrost.com).",
           "Privacy policy", f'''<p>Last updated {LEGAL_UPDATED_H}. This policy explains how Which Frost (whichfrost.com), a trade name of Joshua Israel Ventures LLC, a Florida limited liability company, handles information.</p>
<h2>Analytics</h2><p>Which Frost names the two analytics tools the public site uses.</p>
<p>Cloudflare Web Analytics loads on every public page. It does not use cookies and does not track you across sites. It records basic, aggregated information such as the page, the referrer, the browser, and the country. The preview build does not load it.</p>
<p>Google Analytics 4 loads on a public page only after you choose Allow analytics on the consent banner. The preview build does not load it. The Google tag is not requested until that choice. Until then, Consent Mode v2 defaults keep ad storage, ad user data, ad personalization, and analytics storage denied.</p>
<h2>Contact</h2><p>If you email us or use the contact form, your name, email address, and message are used to reply. The form is delivered by FormSubmit (formsubmit.co). We keep messages only as long as needed to respond.</p>
<h2>Advertising</h2><p>Which Frost loads the Google AdSense script and a <code>google-adsense-account</code> meta tag (publisher {ADSENSE_PUB}) on public pages so the site can be verified for Google AdSense. No ad units are placed on pages today, so you should not see display ads. If we start showing ads, they will be labeled, and this policy and the <a href="/ad-disclosure/">advertising disclosure</a> will say so. You can opt out of personalized advertising at <a href="https://www.google.com/settings/ads" rel="nofollow noopener">Google Ads Settings</a> and <a href="https://www.aboutads.info/choices/" rel="nofollow noopener">aboutads.info/choices</a>.</p>
<h2>Google advertising cookies and your choices</h2><p>Third-party vendors, including Google, use cookies to serve ads based on a user's prior visits to this website or other websites. Google's use of advertising cookies enables it and its partners to serve ads based on your visit to this site and/or other sites on the Internet. You may opt out of personalized advertising by visiting <a href="https://adssettings.google.com/" rel="nofollow noopener">Google Ads Settings</a>. Alternatively, you can opt out of a third-party vendor's use of cookies for personalized advertising at <a href="https://www.aboutads.info/choices/" rel="nofollow noopener">aboutads.info/choices</a>. For more information, see <a href="https://policies.google.com/technologies/partner-sites" rel="nofollow noopener">how Google uses information from sites or apps that use its services</a>.</p>
<h2 id="cookies">Cookies</h2><p>Which Frost does not set its own cookie. The allow or refuse choice is stored in this browser's local storage as wf-ga4-consent, with the value granted or denied, so the banner can stay dismissed. If you allow analytics, Google Analytics 4 may set its own cookies and receive the page address. Consent Mode v2 still defaults ad storage, ad user data, and ad personalization to denied while no ad units are shown.</p>
<p>Choose Cookie settings in the footer to change your choice. Blocking cookies and local storage does not block the frost dates. See the <a href="/ad-disclosure/">advertising disclosure</a>.</p>
<h2>Hosting</h2><p>The site is hosted on GitHub Pages, which may log IP addresses for security and operations.</p>
<h2>Your rights</h2><p>You can ask us to access, correct, or delete personal information we hold. Use the <a href="/contact/">contact page</a>. Residents of some states and countries may have additional rights, which we will honor.</p>
<h2>Children</h2><p>The site is a general audience reference and is not directed at children under 13. We do not knowingly collect personal information from children.</p>
<h2>Changes</h2><p>We will post changes on this page with a new date.</p>''', "Privacy", legal=True,
           lastmod=LEGAL_UPDATED, published=PUBLISHED, modified=LEGAL_UPDATED)
    simple("/copyright/", f"Copyright and DMCA | {BRAND}", "Copyright and DMCA notice for Which Frost (whichfrost.com).",
           "Copyright and DMCA", f'''<p>Last updated {PUBLISHED_H}. Original text, compilation, and design on whichfrost.com are owned by Joshua Israel Ventures LLC. Climate figures are U.S. government work, cited to the station. Extension wording is summarized and linked, not copied as a full publication.</p>
<h2>DMCA notice</h2><p>If you believe a page infringes your copyright, email the contact address on the <a href="/contact/">contact page</a> with: your signature, the work you own, the URL on this site, your contact information, a statement that you have a good faith belief the use is not authorized, and a statement under penalty of perjury that your notice is accurate and that you are the owner or the owner's agent. We will review complete notices and remove material that we agree is infringing.</p>
<h2>Counter notice</h2><p>If you believe a removal was a mistake, send a counter notice with the same contact path, including your signature, the material and URL, a statement under penalty of perjury that the material was removed by mistake, and consent to the jurisdiction of the federal court in your district (or in Florida, if you are outside the United States).</p>''', "Copyright and DMCA", legal=True)
    simple("/ad-disclosure/", f"Advertising disclosure | {BRAND}", "Which Frost has AdSense verification tags but no ad units yet. How ads will be labeled.",
           "Advertising disclosure", f'''<p>Last updated {LEGAL_UPDATED_H}. Which Frost has no affiliate links. Nothing on the site is paid placement by a seed company, a tool maker, or an extension. Editorial frost dates are not for sale.</p>
<p>The public pages load the Google AdSense script and a publisher meta tag ({ADSENSE_PUB}) for site verification. No ad units are placed today, so pages should not show display ads. If that changes, ads will be labeled as advertising, and this page will name the network. Which Frost is a trade name of Joshua Israel Ventures LLC.</p>''', "Advertising disclosure", legal=True,
           lastmod=LEGAL_UPDATED, published=PUBLISHED, modified=LEGAL_UPDATED)
    simple("/contact/", f"Contact {BRAND}", "Contact Which Frost by email about a station, a date, or a correction.",
           "Contact us", f'''<p>Questions and corrections go to <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>
<h2>Corrections</h2><p>Send the page address, the station id, and what looks wrong. We update the verified date when we re check the NOAA file.</p>
<p class="form-status" id="contact-status" role="status" hidden></p>
<form class="contact" action="https://formsubmit.co/{CONTACT_EMAIL}" method="POST">
<input type="hidden" name="_subject" value="Which Frost contact">
<input type="hidden" name="_template" value="table">
<input type="hidden" name="_next" value="https://whichfrost.com/contact/thanks/">
<input type="text" name="_honey" class="hp" tabindex="-1" autocomplete="off" aria-hidden="true">
<input type="hidden" name="_captcha" value="false">
<label for="name">Name</label><input id="name" type="text" name="name" required autocomplete="name">
<label for="email">Email</label><input id="email" type="email" name="email" required autocomplete="email">
<label for="message">Message</label><textarea id="message" name="message" rows="6" required></textarea>
<button class="btn" type="submit">Send message</button></form>
<p class="note">The form is delivered by FormSubmit (formsubmit.co) to the same address. You can also use the email link above. See the <a href="/privacy/">privacy policy</a>.</p>''', "Contact")
    simple("/contact/thanks/", f"Message sent | {BRAND}", "Your message to Which Frost was sent.",
           "Message sent", "<p>Thanks, your message was sent. We will reply by email.</p>",
           "Message sent")

def not_found():
    body = '''<article class="prose"><h1>Page not found</h1>
<p>That address is not on Which Frost. Try the <a href="/">home page</a> or the <a href="/states/">state list</a>.</p></article>'''
    # 404.html at the root, not a folder.
    path = "/404.html"
    # reuse page() but write to 404.html. page() uses disk_for which would make /404.html/index.html.
    # Write it directly.
    title, desc = "Page not found", "That page is not on Which Frost."
    # Build via a temporary path hack: write folder then move. Simpler to call page logic by writing after a custom disk.
    global disk_for
    real = disk_for
    def disk_404(p):
        return os.path.join(ROOT, "404.html")
    globals()["disk_for"] = disk_404
    page("/404.html", title, desc, body, noindex=True)
    globals()["disk_for"] = real

def extras(cities):
    open(os.path.join(ROOT, "CNAME"), "w").write(DOMAIN + "\n")
    open(os.path.join(ROOT, ".nojekyll"), "w").write("")
    open(os.path.join(ROOT, INDEXNOW_KEY + ".txt"), "w").write(INDEXNOW_KEY + "\n")
    # AdSense ads.txt (publisher verification). No ad units on pages yet.
    open(os.path.join(ROOT, "ads.txt"), "w").write(
        f"google.com, pub-{ADSENSE_PUB.split('ca-pub-')[-1]}, DIRECT, f08c47fec0942fa0\n")
    bots = ["*", "Googlebot", "Bingbot", "Mediapartners-Google", "OAI-SearchBot", "ChatGPT-User",
            "GPTBot", "PerplexityBot", "Perplexity-User", "ClaudeBot", "Claude-SearchBot", "Claude-User",
            "Google-Extended", "Applebot", "Applebot-Extended", "DuckAssistBot", "Amazonbot", "CCBot", "Bytespider"]
    robots = "".join(f"User-agent: {b}\nAllow: /\n\n" for b in bots) + f"Sitemap: {BASE_URL}sitemap.xml\n"
    open(os.path.join(ROOT, "robots.txt"), "w").write(robots)
    locs = []
    for path, lm in SITEMAP:
        loc = url(path)
        locs.append(f"  <url><loc>{loc}</loc><lastmod>{lm}</lastmod></url>")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(locs) + "\n</urlset>\n"
    open(os.path.join(ROOT, "sitemap.xml"), "w").write(xml)
    lines = [f"# {BRAND}", "",
             f"> Which Frost ({DOMAIN}) lists median last spring and first fall frost dates for {len(cities)} large U.S. cities, from NOAA NCEI 1991 to 2020 climate normals, with USDA hardiness zones and state extension planting notes where transcribed. Last verified {PUBLISHED_H}.",
             "", "## Start", f"- {url('/')}", f"- {url('/states/')}", f"- {url('/zones/')}", f"- {url('/methodology/')}",
             f"- {url('/guides/hard-freeze-vs-frost/')} Hard freeze, frost, and a freeze warning",
             "", "## States"]
    states = sorted(set(c["st"] for c in cities))
    for st in states:
        lines.append(f"- {url('/states/' + st.lower() + '/')} {US[st]}")
    lines.append("")
    lines.append("## Zones")
    for z in sorted(set(c["zone"] for c in cities if c.get("zone")), key=lambda z: (int(z[:-1]), z[-1])):
        lines.append(f"- {url('/zones/' + z + '/')}")
    lines += ["", "## Cities", "City pages use /{state}/{city}/ with the state postal code."]
    for c in sorted(cities, key=lambda c: (c["st"], c["name"])):
        lines.append(f"- {url('/' + c['st'].lower() + '/' + c['slug'] + '/')} {c['name']}, {US[c['st']]}")
    open(os.path.join(ROOT, "llms.txt"), "w").write("\n".join(lines) + "\n")
    slim = [{"n": c["name"], "s": US[c["st"]], "a": c["st"], "u": f"/{c['st'].lower()}/{c['slug']}/", "z": c.get("zone") or ""} for c in cities]
    json.dump(slim, open(os.path.join(ROOT, "assets", "cities.json"), "w"), separators=(",", ":"))
    make_images()
    cfg = "exclude: [README.md, LAUNCH-NOTES.md, _build, .gitignore, indexnow.sh]\n"
    open(os.path.join(ROOT, "_config.yml"), "w").write(cfg)

def make_images():
    from PIL import Image, ImageDraw, ImageFont
    logo = Image.new("RGB", (256, 256), "#0b3954")
    d = ImageDraw.Draw(logo)
    d.line([(128, 28), (128, 228)], fill="#e6f4f1", width=14)
    d.line([(28, 128), (228, 128)], fill="#e6f4f1", width=14)
    d.line([(48, 48), (208, 208)], fill="#e6f4f1", width=10)
    d.line([(208, 48), (48, 208)], fill="#e6f4f1", width=10)
    d.ellipse((110, 110, 146, 146), fill="#ffb347")
    logo.save(os.path.join(ROOT, "logo.png"))
    og = Image.new("RGB", (1200, 630), "#0b3954")
    d = ImageDraw.Draw(og)
    d.rectangle((0, 560, 1200, 630), fill="#ffb347")
    d.line([(90, 150), (90, 470)], fill="#e6f4f1", width=8)
    font = ImageFont.load_default(size=78)
    small = ImageFont.load_default(size=36)
    d.text((140, 200), "Which Frost", fill="#ffffff", font=font)
    d.text((140, 320), "Frost dates and planting calendars", fill="#e6f4f1", font=small)
    d.text((40, 575), "NOAA 1991 to 2020 normals", fill="#0b3954", font=small)
    og.save(os.path.join(ROOT, "og.png"))

def main():
    global ALL
    clean_output()
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    # assets were deleted by clean_output. Rewrite the static ones from this script's copies? 
    # clean_output removes assets. That is wrong. The keep set includes assets, so CSS survives.
    cities = load_cities()
    ALL = cities
    print("cities", len(cities), "indexable" if INDEXABLE else "noindex")
    home(cities)
    states_index(cities)
    zones_index(cities)
    by_state = {}
    by_zone = {}
    for c in cities:
        by_state.setdefault(c["st"], []).append(c)
        if c.get("zone"):
            by_zone.setdefault(c["zone"], []).append(c)
    for st, group in by_state.items():
        state_page(st, group)
    for z, group in by_zone.items():
        zone_page(z, group)
    for c in cities:
        city_page(c, cities)
    growing_season_page(cities)
    no_computed_frost_page(cities)
    hard_freeze_guide(cities)
    legal_pages()
    not_found()
    extras(cities)
    print("pages in sitemap", len(SITEMAP))

if __name__ == "__main__":
    main()
