# Which Frost launch notes

Status 16 Nov 2026: the committed site is the preview build. `SITE_INDEXABLE` stays `False` in `_build/config.py`, so every committed page carries `noindex`. `CNAME` is `whichfrost.com`. Paths are root-relative in both the preview build and the launch build. `GA4_ID` in `_build/config.py` is an empty string until the owner pastes a `G-` measurement id.

whichfrost.com currently resolves to 162.255.119.238 (Namecheap registrar DNS). That is not GitHub Pages. Do not commit a launch build, and do not ping IndexNow, until the A records point at GitHub Pages and HTTPS is issued.

## Exact launch command

Paste the Google Analytics 4 measurement id into `GA4_ID` in `_build/config.py` (`G-` plus the id from the Google Analytics admin). While that constant is empty, `check.py --launch` exits non-zero and prints `GA4_ID empty`.

```
python3 _build/build.py --launch
python3 _build/check.py --launch
python3 _build/legal_gate.py check
```

`build.py --launch` forces indexable pages for that run without editing `SITE_INDEXABLE`. It keeps root-relative paths and writes `CNAME` as `whichfrost.com`. It also rewrites `sitemap.xml` (every URL has `lastmod`), `robots.txt` (Googlebot, Bingbot, and the AI crawlers stay allowed), `llms.txt`, and the IndexNow key file `c4e1a9b27f6d8043e5a1c8d09b2f74e6.txt`.

`check.py --launch` must report `issues 0`. It fails if `GA4_ID` is empty, if any page lacks the Cloudflare Web Analytics beacon, or if any page lacks the GA4 loader (`wfLoadGA4` and `https://www.googletagmanager.com/gtag/js?id=`). In launch output, only `404.html` contains `noindex`. `contact/thanks/` is indexable.

The legal gate must report `0 HOLD_REVIEW`.

## When Joshua says the DNS is ready

1. Paste the GA4 measurement id into `GA4_ID`.
2. Point the apex at the GitHub Pages A records (185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153) and www at joshuaofisrael.github.io.
3. Run the exact launch command above.
4. Commit and push main.
5. Confirm `https://whichfrost.com/` returns 200, `noindex` appears only in `404.html`, and www redirects to the apex.
6. `./indexnow.sh` (key file is already in the repo).
7. Add the domain property in Google Search Console and Bing. Bing import needs Joshua's Microsoft sign in.
8. Add whichfrost.com to the Cloudflare Web Analytics host list after the beacon loads.

The launch build loads the shared JI Ventures Analytics 2 beacon on every page, including before a cookie choice. Google Analytics 4 uses Consent Mode v2 defaults of denied and does not request gtag.js until the visitor chooses Allow analytics. Cookie settings in the footer reopens that choice. The privacy page names both Cloudflare Web Analytics and Google Analytics 4.

AdSense is not part of v1. The ad disclosure says the site shows no ads.
