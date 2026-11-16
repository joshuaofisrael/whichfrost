# Which Frost (whichfrost.com)

Median last spring and first fall frost dates for large U.S. cities, from NOAA NCEI 1991 to 2020 climate normals, plus the 2023 USDA hardiness zone and a planting calendar where a state extension page was transcribed. Static site, GitHub Pages (branch `main`, folder `/`).

Joshua Israel Ventures LLC. The LLC name appears only on the legal pages.

## Status

v1 is built with `noindex` on every page. The switch is `SITE_INDEXABLE` in `_build/config.py` (default `False`). Paths are always root relative. `CNAME` is `whichfrost.com`.

`python3 _build/build.py --launch` turns on indexing and the Cloudflare beacon for that run. Do that only after whichfrost.com DNS points at GitHub Pages. Today the domain answers at a registrar parking address, not at this site.

## Build

```
python3 _build/build.py
python3 _build/check.py
python3 _build/legal_gate.py check
```

`check.py` must report 0 issues. The legal gate must report 0 HOLD_REVIEW.

The city and station cache is `_build/cache/` (retrieved 16 Nov 2026). Rebuild HTML from that cache without downloading again. `_build/prepare_data.py` rebuilds the cache from a local copy of the NCEI by station archive, the Census 2024 place files, and the PRISM 2023 ZIP zone tables. It does not invent a frost date. A station is used only when NOAA published a frost product.

## What v1 contains

- 341 city pages at `/{st}/{city}/` for incorporated places of at least 100,000 people (Census 2024) whose nearest frost product station is within 50 miles.
- 45 state hubs, a state index, 15 USDA zone pages with a "what to plant now" section, home search, FAQPage schema, sitemap, robots (including the AI crawlers), llms.txt, IndexNow key file.
- Planting calendars transcribed from CSU Extension GardenNotes #720 (Colorado), UGA Extension Circular 943 (Georgia, middle Georgia baseline), and the UNH Extension vegetable fact sheet (New Hampshire). Other states say the calendar is not transcribed.

## Gaps

- No city page for Delaware, Hawaii, Maine, Vermont, West Virginia, or Wyoming. Those states have no incorporated place of 100,000 people inside the 50 mile station cap. Honolulu is omitted because Honolulu International Airport has no computed 32°F date (NOAA flag Y) and the nearest computed date is about 110 miles away.
- 33 warm city pages (including Miami, Los Angeles, and San Diego) have no computed 32°F date. The page says "Not computed" and still shows any 36°F dates and the growing season length NOAA did publish.
- Most states have no transcribed extension planting calendar.
- Contact form posts to joshuaofisrael@gmail.com through FormSubmit and also shows that address as a mailto link. FormSubmit may ask the inbox to confirm the first time.
- IndexNow is not pinged until the domain serves this site.
