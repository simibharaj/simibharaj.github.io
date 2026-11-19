#!/usr/bin/env python3
"""Daily live data for simibharaj.me.

Runs in GitHub Actions once a day and writes data/live.json, which the site
reads on load. Uses only public sources and the Python standard library:
  - GitHub contribution calendar (public profile) since CONTRIB_SINCE
  - public repos: last push date and language
  - the newsletter RSS feed (essays and editions)
  - which interactive editions exist in the aiimo repo
If a source fails, the previous value is kept, so the site never goes blank.
"""
import datetime as dt
import html
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

USER = "simibharaj"
CONTRIB_SINCE = "2026-09-01"
FEED = "https://aiimo.substack.com/feed"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "live.json")
UA = {"User-Agent": "simibharaj.me-live-data"}
# Substack sits behind Cloudflare, which turns away script-looking requests
BROWSER = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def get(url, accept=None):
    headers = dict(UA) if "github.com" in url else dict(BROWSER)
    if accept:
        headers["Accept"] = accept
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com"):
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def contributions(since):
    total = 0
    start_year = int(since[:4])
    today = dt.date.today()
    for year in range(start_year, today.year + 1):
        page = get(f"https://github.com/users/{USER}/contributions?from={year}-01-01&to={year}-12-31")
        cells = re.findall(r'<td[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="([^"]+)"', page)
        tips = dict(re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page))
        if not cells or not tips:
            raise ValueError("contribution calendar format changed")
        for day, cell_id in cells:
            if day < since:
                continue
            m = re.match(r"\s*([\d,]+) contribution", tips.get(cell_id, ""))
            if m:
                total += int(m.group(1).replace(",", ""))
    return total


def repos():
    data = json.loads(get(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner"))
    out = {}
    for r in data:
        if r.get("fork") or r.get("private"):
            continue
        out[r["name"]] = {"pushed": r.get("pushed_at"), "lang": r.get("language")}
    return out


def post_item(title, sub, link, iso, img):
    title = html.unescape((title or "").strip())
    m = re.match(r"edition\s+(\d+)\s*:\s*(.*)", title, re.I)
    return {
        "title": m.group(2).strip() if m else title,
        "sub": html.unescape((sub or "").strip()),
        "url": (link or "").strip(),
        "date": iso,
        "img": img or "",
        "edition": m.group(1).zfill(2) if m else None,
    }


def posts():
    try:
        return posts_direct()
    except Exception:
        # Cloudflare blocks GitHub's servers from the feed, so fall back to a public RSS relay
        return posts_relay()


def posts_relay():
    url = "https://api.rss2json.com/v1/api.json?rss_url=" + urllib.parse.quote(FEED, safe="")
    d = json.loads(get(url))
    if d.get("status") != "ok":
        raise ValueError("relay: " + str(d.get("message")))
    items = []
    for it in d.get("items", []):
        enc = it.get("enclosure") or {}
        img = enc.get("link", "") if str(enc.get("type", "image")).startswith("image") else ""
        items.append(post_item(it.get("title"), it.get("description"), it.get("link"), (it.get("pubDate") or "")[:10], img))
    if not items:
        raise ValueError("relay returned no posts")
    return items


def posts_direct():
    root = ET.fromstring(get(FEED).encode("utf-8"))
    items = []
    for it in root.find("channel").findall("item"):
        date = it.findtext("pubDate") or ""
        try:
            iso = dt.datetime.strptime(date[:25], "%a, %d %b %Y %H:%M:%S").strftime("%Y-%m-%d")
        except ValueError:
            iso = ""
        enc = it.find("enclosure")
        img = enc.get("url") if enc is not None and (enc.get("type") or "").startswith("image") else ""
        items.append(post_item(it.findtext("title"), it.findtext("description"), it.findtext("link"), iso, img))
    return items


def editions_live():
    tree = json.loads(get(f"https://api.github.com/repos/{USER}/aiimo/git/trees/main"))
    return sorted(t["path"] for t in tree.get("tree", []) if t["type"] == "tree" and re.fullmatch(r"\d{2}", t["path"]))


def main():
    try:
        with open(OUT) as f:
            prev = json.load(f)
    except (OSError, ValueError):
        prev = {}
    out = dict(prev)
    out.setdefault("github", {})
    notes = []

    try:
        out["github"]["contributions"] = contributions(CONTRIB_SINCE)
        out["github"]["since"] = CONTRIB_SINCE
    except Exception as e:  # keep the last good number
        notes.append(f"contributions: {e}")
    try:
        r = repos()
        out["github"]["repos"] = r
        out["github"]["public_repos"] = len(r)
    except Exception as e:
        notes.append(f"repos: {e}")
    try:
        fresh = posts()
        seen = {p["url"] for p in fresh}
        older = [p for p in prev.get("posts", []) if p.get("url") not in seen]
        allp = sorted(fresh + older, key=lambda p: p.get("date", ""), reverse=True)
        out["posts"] = allp
        out["post_count"] = len(allp)
    except Exception as e:
        notes.append(f"posts: {e}")
    try:
        out["editions_live"] = editions_live()
    except Exception as e:
        notes.append(f"editions: {e}")

    out["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out["problems"] = notes
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(json.dumps({k: out[k] for k in ("updated", "post_count", "problems") if k in out}))
    print("contributions:", out["github"].get("contributions"), "repos:", out["github"].get("public_repos"))


if __name__ == "__main__":
    main()
