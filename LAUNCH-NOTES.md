# Which Frost launch notes

Status 16 Nov 2026: v1 is in the repo with noindex on every page (`SITE_INDEXABLE = False` in `_build/config.py`). CNAME is whichfrost.com. Root relative paths in both modes.

whichfrost.com currently resolves to 162.255.119.238 (Namecheap registrar DNS). That is not GitHub Pages. Do not flip the indexable flag, and do not ping IndexNow, until the A records point at GitHub Pages and HTTPS is issued.

## When Joshua says the DNS is ready

1. Point the apex at the GitHub Pages A records (185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153) and www at joshuaofisrael.github.io.
2. `python3 _build/build.py --launch && python3 _build/check.py --launch && python3 _build/legal_gate.py check`
3. Commit and push main.
4. Confirm `https://whichfrost.com/` returns 200, `noindex` count is 0, and www redirects to the apex.
5. `./indexnow.sh` (key file is already in the repo).
6. Add the domain property in Google Search Console and Bing. Bing import needs Joshua's Microsoft sign in.

The launch build adds the shared JI Ventures Analytics 2 beacon. Add whichfrost.com to the analytics host list after the beacon loads.

AdSense is not part of v1. The ad disclosure says the site shows no ads.
