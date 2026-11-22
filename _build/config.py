#!/usr/bin/env python3
"""Site-wide constants. SITE_INDEXABLE is the one noindex switch.

False (default): every page carries <meta name="robots" content="noindex, follow">.
True: content pages are indexable. Only the 404 page stays noindex.

Leave this False until whichfrost.com is on DNS and the launch build is intentional.
`python3 _build/build.py --launch` forces True for that run without editing this file.
Paths are always root-relative, and the build always writes CNAME as whichfrost.com.

GA4_ID is the Google Analytics 4 measurement id. Keep it "" until the owner pastes a
G- id from the Google Analytics admin. `python3 _build/check.py --launch` fails while
it is empty. The id is public once a visitor allows gtag. Do not put a secret here.
"""
SITE_INDEXABLE = False

BRAND = "Which Frost"
DOMAIN = "whichfrost.com"
BASE_URL = "https://whichfrost.com/"
PUBLISHED = "2026-11-16"          # first publication of this dataset. Never replace with a build clock.
PUBLISHED_H = "16 Nov 2026"
# Explicit, one time publish date for a page added after launch (not the build clock).
# Set this to the day a given page actually went live, then leave it fixed.
GROWING_SEASON_PAGES_PUBLISHED = "2026-11-18"
GROWING_SEASON_PAGES_PUBLISHED_H = "18 Nov 2026"
# Explicit publish dates for pages whose content changed after launch (not the build clock).
ZONE_REFRESH_PUBLISHED = "2026-11-19"
ZONE_REFRESH_PUBLISHED_H = "19 Nov 2026"
LEGAL_UPDATED = "2026-11-19"
LEGAL_UPDATED_H = "19 Nov 2026"
TOMATO_GUIDE_PUBLISHED = "2026-11-19"
TOMATO_GUIDE_PUBLISHED_H = "19 Nov 2026"
# Anchorage city page and the Alaska state hub. The NOAA station file is still
# the 16 Nov 2026 retrieval. This date is the day those pages were rewritten.
ANCHORAGE_REFRESH = "2026-11-20"
ANCHORAGE_REFRESH_H = "20 Nov 2026"
# Guide written 20 Nov 2026. If the frost photo arrives on a later day, set
# this to that day before the page is merged. Do not use the build clock.
HARD_FREEZE_GUIDE_PUBLISHED = "2026-11-20"
HARD_FREEZE_GUIDE_PUBLISHED_H = "20 Nov 2026"
FROST_HERO = "/assets/images/frost-covered-lawn-dawn.png"
INDEXNOW_KEY = "c4e1a9b27f6d8043e5a1c8d09b2f74e6"
# Google AdSense publisher id. Head script + meta only; no ad units in v1.
ADSENSE_PUB = "ca-pub-5681559774142917"
# Shared JI Ventures Analytics 2 token, same beacon Which Cabin uses at launch. Launch build only.
CF_BEACON_TOKEN = "eac63f2b5dbc4539a2d95249baab6472"
# Owner pastes G-XXXXXXXXXX. Empty on purpose until then. Launch check fails while empty.
GA4_ID = "G-31Y999EGZ5"
CONTACT_EMAIL = "joshuaofisrael@gmail.com"
MAX_MILES = 50.0

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

# Census consolidated-place names -> (public name, slug). The public name is the
# city people look up. The census name is still printed on the page.
ALIASES = {
    "Nashville-Davidson metropolitan government": ("Nashville", "nashville"),
    "Louisville/Jefferson County metro government": ("Louisville", "louisville"),
    "Lexington-Fayette urban county": ("Lexington", "lexington"),
    "Augusta-Richmond County consolidated government": ("Augusta", "augusta"),
    "Athens-Clarke County unified government": ("Athens", "athens"),
    "San Buenaventura (Ventura)": ("Ventura", "ventura"),
    "Macon-Bibb County": ("Macon", "macon"),
    "Indianapolis city": ("Indianapolis", "indianapolis"),
    "Boise City": ("Boise", "boise"),
}

NEIGHBORS = {
    "AL": ["MS", "TN", "GA", "FL"],
    "AK": [],
    "AZ": ["CA", "NV", "UT", "CO", "NM"],
    "AR": ["MO", "TN", "MS", "LA", "TX", "OK"],
    "CA": ["OR", "NV", "AZ"],
    "CO": ["WY", "NE", "KS", "OK", "NM", "AZ", "UT"],
    "CT": ["NY", "MA", "RI"],
    "DE": ["MD", "PA", "NJ"],
    "DC": ["MD", "VA"],
    "FL": ["AL", "GA"],
    "GA": ["FL", "AL", "TN", "NC", "SC"],
    "HI": [],
    "ID": ["MT", "WY", "UT", "NV", "OR", "WA"],
    "IL": ["WI", "IN", "KY", "MO", "IA"],
    "IN": ["MI", "OH", "KY", "IL"],
    "IA": ["MN", "WI", "IL", "MO", "NE", "SD"],
    "KS": ["NE", "MO", "OK", "CO"],
    "KY": ["IL", "IN", "OH", "WV", "VA", "TN", "MO"],
    "LA": ["TX", "AR", "MS"],
    "ME": ["NH"],
    "MD": ["VA", "WV", "PA", "DE", "DC"],
    "MA": ["RI", "CT", "NY", "NH", "VT"],
    "MI": ["WI", "IN", "OH"],
    "MN": ["ND", "SD", "IA", "WI"],
    "MS": ["LA", "AR", "TN", "AL"],
    "MO": ["IA", "IL", "KY", "TN", "AR", "OK", "KS", "NE"],
    "MT": ["ND", "SD", "WY", "ID"],
    "NE": ["SD", "IA", "MO", "KS", "CO", "WY"],
    "NV": ["OR", "ID", "UT", "AZ", "CA"],
    "NH": ["ME", "MA", "VT"],
    "NJ": ["NY", "DE", "PA"],
    "NM": ["AZ", "UT", "CO", "OK", "TX"],
    "NY": ["PA", "NJ", "CT", "MA", "VT"],
    "NC": ["VA", "TN", "GA", "SC"],
    "ND": ["MN", "SD", "MT"],
    "OH": ["MI", "PA", "WV", "KY", "IN"],
    "OK": ["KS", "MO", "AR", "TX", "NM", "CO"],
    "OR": ["WA", "ID", "NV", "CA"],
    "PA": ["NY", "NJ", "DE", "MD", "WV", "OH"],
    "RI": ["CT", "MA"],
    "SC": ["NC", "GA"],
    "SD": ["ND", "MN", "IA", "NE", "WY", "MT"],
    "TN": ["KY", "VA", "NC", "GA", "AL", "MS", "AR", "MO"],
    "TX": ["NM", "OK", "AR", "LA"],
    "UT": ["ID", "WY", "CO", "NM", "AZ", "NV"],
    "VT": ["NH", "MA", "NY"],
    "VA": ["MD", "DC", "NC", "TN", "KY", "WV"],
    "WA": ["OR", "ID"],
    "WV": ["OH", "PA", "MD", "VA", "KY"],
    "WI": ["MI", "MN", "IA", "IL"],
    "WY": ["MT", "SD", "NE", "CO", "UT", "ID"],
}

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
