#!/usr/bin/env python3
"""Site QA. Usage: check.py [--launch]

Fails on broken JSON-LD, missing or extra noindex, a missing canonical, more than one h1,
the owner or LLC name outside legal pages, a missing legal line, a broken root-relative link,
a duplicate title, a meta description over 155 characters, a city page that does not cite its
station, or a frost date on the page that is not the cached NOAA value.
"""
import glob, json, os, re, sys, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import SITE_INDEXABLE, US, ALIASES
from build import fmt_date, load_cities

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCH = "--launch" in sys.argv or SITE_INDEXABLE
LEGAL = {"terms", "privacy", "disclaimer", "copyright", "ad-disclosure"}
bad = 0
titles = {}

def fail(msg):
    global bad
    bad += 1
    print(msg)

files = [f for f in glob.glob(ROOT + "/**/*.html", recursive=True) if "/_build/" not in f]
for f in files:
    raw = open(f, encoding="utf-8").read()
    rel = os.path.relpath(f, ROOT)
    top = rel.split("/")[0]
    for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', raw, re.S):
        try:
            json.loads(m)
        except Exception as e:
            fail(f"JSONLD {rel} {e}")
    vis = re.sub(r"<script.*?</script>", "", raw, flags=re.S)
    if top not in LEGAL and re.search(r"Joshua|Israel Ventures|©", vis):
        fail(f"LLC {rel}")
    if top in LEGAL and "is a trade name of Joshua Israel Ventures LLC" not in raw:
        fail(f"nolegalline {rel}")
    if not re.search(r'<link rel="canonical" href="https://whichfrost.com/', raw):
        fail(f"canonical {rel}")
    if "github.io" in raw:
        fail(f"github.io {rel}")
    h1s = raw.count("<h1")
    if h1s != 1:
        fail(f"h1count {rel} {h1s}")
    if LAUNCH:
        if rel != "404.html" and not rel.startswith("contact/thanks") and "noindex" in raw:
            fail(f"noindex {rel}")
        if "static.cloudflareinsights.com/beacon.min.js" not in raw:
            fail(f"nobeacon {rel}")
    else:
        if "noindex" not in raw:
            fail(f"preview-missing-noindex {rel}")
    if "—" in raw or "–" in raw:
        fail(f"dash {rel}")
    title = re.search(r"<title>(.*?)</title>", raw)
    if not title:
        fail(f"notitle {rel}")
    else:
        t = html.unescape(title.group(1))
        titles.setdefault(t, []).append(rel)
        if len(t) > 70:
            print("longtitle", len(t), t)
    desc = re.search(r'<meta name="description" content="(.*?)"', raw)
    if not desc:
        fail(f"nodesc {rel}")
    elif len(html.unescape(desc.group(1))) > 155:
        fail(f"longdesc {len(html.unescape(desc.group(1)))} {rel}")
    for link in re.findall(r'(?:href|src)="(/[^"#?]*)', raw):
        if link.startswith("//"):
            fail(f"prefix {rel} {link}")
            continue
        target = os.path.join(ROOT, link.lstrip("/"))
        if not (os.path.isfile(target) or os.path.isfile(os.path.join(target, "index.html"))):
            fail(f"broken {rel} {link}")

for t, fs in titles.items():
    if len(fs) > 1:
        fail(f"duptitle {t} {fs}")

# City pages must repeat the cached station and the cached 32 F 50 percent date.
cities = load_cities()
if len(cities) < 300:
    fail(f"citycount {len(cities)}")
for c in cities:
    rel = os.path.join(c["st"].lower(), c["slug"], "index.html")
    path = os.path.join(ROOT, rel)
    if not os.path.isfile(path):
        fail(f"missingcity {rel}")
        continue
    raw = open(path, encoding="utf-8").read()
    sid = c["station"]
    if sid not in raw:
        fail(f"nostation {rel}")
    if "ncei.noaa.gov" not in raw:
        fail(f"nosource {rel}")
    spring = fmt_date(c["station_rec"]["dates"].get("prblst-t32fp50", ""))
    if spring:
        if f"The median last spring freeze at 32°F is {spring}." not in raw:
            fail(f"springdate {rel} expected {spring}")
    else:
        if "NOAA did not compute a median last spring freeze at 32°F for this station." not in raw:
            fail(f"springmissing {rel}")
    if 'type="FAQPage"' not in raw and '"FAQPage"' not in raw:
        fail(f"nofaq {rel}")

need = [("tx", "austin"), ("co", "denver"), ("ga", "atlanta"), ("il", "chicago"), ("mn", "minneapolis"),
        ("or", "portland"), ("wa", "seattle"), ("ny", "new-york"), ("ma", "boston"), ("pa", "philadelphia"),
        ("nc", "raleigh"), ("tn", "nashville"), ("mo", "kansas-city"), ("oh", "columbus"),
        ("ut", "salt-lake-city"), ("az", "phoenix"), ("tx", "dallas"), ("ca", "sacramento"), ("mi", "detroit")]
for st, slug in need:
    if not os.path.isfile(os.path.join(ROOT, st, slug, "index.html")):
        fail(f"spec {st}/{slug}")

cname = open(os.path.join(ROOT, "CNAME"), encoding="utf-8").read().strip()
if cname != "whichfrost.com":
    fail(f"cname {cname}")
if "Sitemap: https://whichfrost.com/sitemap.xml" not in open(os.path.join(ROOT, "robots.txt"), encoding="utf-8").read():
    fail("robots sitemap")
robots = open(os.path.join(ROOT, "robots.txt"), encoding="utf-8").read()
for bot in ["Googlebot", "Bingbot", "GPTBot", "ClaudeBot", "PerplexityBot", "OAI-SearchBot", "CCBot", "Google-Extended", "Applebot-Extended", "Bytespider"]:
    if f"User-agent: {bot}" not in robots:
        fail(f"robot {bot}")
if not os.path.isfile(os.path.join(ROOT, "llms.txt")):
    fail("llms")
# sitemap locs should exist
sm = open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8").read()
for loc in re.findall(r"<loc>(.*?)</loc>", sm):
    if "noindex" in loc:
        fail(f"sitemap noindex url {loc}")
    path = loc.replace("https://whichfrost.com", "")
    if path in ("", "/"):
        disk = os.path.join(ROOT, "index.html")
    else:
        disk = os.path.join(ROOT, path.strip("/"), "index.html")
    if not os.path.isfile(disk):
        fail(f"sitemap missing {loc}")
    else:
        page = open(disk, encoding="utf-8").read()
        if f'href="{loc}"' not in page and f"href='{loc}'" not in page:
            # canonical uses the loc
            if f'<link rel="canonical" href="{loc}">' not in page:
                fail(f"sitemap canonical {loc}")

print("files", len(files), "issues", bad)
sys.exit(1 if bad else 0)
