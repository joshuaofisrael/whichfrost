#!/bin/bash
# Ping IndexNow with every sitemap URL, or the URLs given. Use only after whichfrost.com serves this site.
KEY=c4e1a9b27f6d8043e5a1c8d09b2f74e6
cd "$(dirname "$0")"
if [ $# -gt 0 ]; then URLS=$(printf '"%s",' "$@"); else URLS=$(grep -o '<loc>[^<]*' sitemap.xml | sed 's/<loc>//' | sed 's/.*/"&"/' | paste -sd, -); fi
curl -s -o /dev/null -w "IndexNow HTTP %{http_code}\n" -H "Content-Type: application/json; charset=utf-8" https://api.indexnow.org/indexnow \
 -d "{\"host\":\"whichfrost.com\",\"key\":\"$KEY\",\"keyLocation\":\"https://whichfrost.com/$KEY.txt\",\"urlList\":[${URLS%,}]}"
