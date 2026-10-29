"""Collect metric-bearing items for the GMAI Engagement component (gmai-formula.md §3.2c).

The regional collectors gather news, which never carries reach/likes/comments/
shares, so Engagement sat at the neutral 0.5 (engagement_known=false) almost
every day. This script fetches interaction metrics from public, no-auth sources
and writes them to data/engagement/{DATE}/{REGION}.json. compute_gmai.py feeds
these items into Engagement ONLY (never Sentiment/Buzz/SOV).

Sources:
- Bluesky public AppView search (per region by post language):
  reach = author followers, likes, comments = replies, shares = reposts + quotes.
- YouTube RSS of the official Gucci channel (global, added to every region):
  reach = views, likes = like count.

Fail-soft: any network/parse error is recorded in the output and the script
still exits 0, so the daily pipeline never stops on it.

Usage: python scripts/collect_engagement.py [YYYY-MM-DD] [--root ROOT]
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BSKY = "https://api.bsky.app/xrpc"
YT_CHANNEL = "UCo6fjlKg6GuCmEMeqYbGJng"  # youtube.com/@gucci (official)
WINDOW_DAYS = 7          # recency weight in compute_gmai (half-life 3d) handles decay
YT_WINDOW_DAYS = 30
MIN_FOLLOWERS = 1        # zero-follower accounts have no audience to react
UA = {"User-Agent": "gucci-intel-engagement/1.0"}
MASTODON_INSTANCES = ["mastodon.social", "mstdn.jp"]
MASTODON_TAGS = ["gucci", "구찌", "グッチ"]
YT_API = "https://www.googleapis.com/youtube/v3"
# (regionCode, relevanceLanguage, query) per GMAI region; ~11 searches x 100 units/day
YT_REGION_QUERIES = {
    "NEA": [("KR", "ko", "구찌|gucci"), ("JP", "ja", "グッチ|gucci")],
    "SEA": [("TH", "th", "กุชชี่|gucci"), ("ID", "id", "gucci"), ("PH", "en", "gucci")],
    "NA": [("US", "en", "gucci"), ("CA", "en", "gucci")],
    "EU": [("FR", "fr", "gucci"), ("IT", "it", "gucci"), ("DE", "de", "gucci"), ("GB", "en", "gucci")],
}

# Region = post language. Local-script brand names catch posts that never write "gucci".
REGION_LANGS = {
    "NEA": {"ko": ["gucci", "구찌"], "ja": ["gucci", "グッチ"], "zh": ["gucci", "古驰", "古馳"]},
    "SEA": {"th": ["gucci", "กุชชี่"], "id": ["gucci"], "vi": ["gucci"], "ms": ["gucci"], "tl": ["gucci"]},
    "NA": {"en": ["gucci"]},
    "EU": {"fr": ["gucci"], "de": ["gucci"], "it": ["gucci"], "es": ["gucci"], "nl": ["gucci"]},
}


def get_json(url, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.load(r)


def bsky_search(q, lang, since, until, max_pages=3):
    params = {"q": q, "lang": lang, "sort": "latest", "limit": 100,
              "since": since + "T00:00:00Z", "until": until + "T00:00:00Z"}
    posts = []
    for n in range(max_pages):
        try:
            page = get_json(f"{BSKY}/app.bsky.feed.searchPosts?" + urllib.parse.urlencode(params))
        except Exception:  # noqa: BLE001 - later pages may 403 without auth; keep what we have
            if n == 0:
                raise
            break
        posts += page.get("posts", [])
        if not page.get("cursor"):
            break
        params["cursor"] = page["cursor"]
    return posts


def bsky_followers(dids):
    out = {}
    for i in range(0, len(dids), 25):
        qs = urllib.parse.urlencode([("actors", d) for d in dids[i:i + 25]])
        for p in get_json(f"{BSKY}/app.bsky.actor.getProfiles?{qs}").get("profiles", []):
            out[p["did"]] = p.get("followersCount") or 0
    return out


def collect_bsky(region, ref_day, errors):
    since = (ref_day - timedelta(days=WINDOW_DAYS - 1)).isoformat()
    until = (ref_day + timedelta(days=1)).isoformat()
    posts = {}
    for lang, terms in REGION_LANGS[region].items():
        for q in terms:
            try:
                for p in bsky_search(q, lang, since, until):
                    posts[p["uri"]] = p
            except Exception as e:  # noqa: BLE001 - fail-soft by design
                errors.append(f"bluesky {lang}/{q}: {e}")
    try:
        followers = bsky_followers(sorted({p["author"]["did"] for p in posts.values()}))
    except Exception as e:  # noqa: BLE001
        errors.append(f"bluesky profiles: {e}")
        followers = {}
    items = []
    for uri, p in posts.items():
        reach = followers.get(p["author"]["did"], 0)
        if reach < MIN_FOLLOWERS:
            continue
        items.append({
            "id": uri, "platform": "bluesky", "source_type": "sns", "tier": "T3",
            "media": "earned", "author": p["author"]["did"],
            "published_at": (p.get("record", {}).get("createdAt") or p.get("indexedAt", ""))[:10],
            "url": "https://bsky.app/profile/{}/post/{}".format(p["author"]["handle"], uri.rsplit("/", 1)[-1]),
            "reach": reach,
            "likes": p.get("likeCount") or 0,
            "comments": p.get("replyCount") or 0,
            "shares": (p.get("repostCount") or 0) + (p.get("quoteCount") or 0),
        })
    return items


def collect_mastodon(ref_day, errors):
    """Public #gucci tag timelines (no auth), all regions; routed by post language."""
    oldest = ref_day - timedelta(days=WINDOW_DAYS - 1)
    statuses = {}
    for inst in MASTODON_INSTANCES:
        for tag in MASTODON_TAGS:
            url = f"https://{inst}/api/v1/timelines/tag/{urllib.parse.quote(tag)}?limit=40"
            for _ in range(3):
                try:
                    page = get_json(url)
                except Exception as e:  # noqa: BLE001
                    errors.append(f"mastodon {inst}/#{tag}: {e}")
                    break
                if not page:
                    break
                for s in page:
                    statuses[s.get("uri") or s["url"]] = s
                if page[-1]["created_at"][:10] < oldest.isoformat():
                    break
                url = (f"https://{inst}/api/v1/timelines/tag/{urllib.parse.quote(tag)}"
                       f"?limit=40&max_id={page[-1]['id']}")
    items = []
    for uri, s in statuses.items():
        day = s["created_at"][:10]
        reach = (s.get("account") or {}).get("followers_count") or 0
        if not (oldest.isoformat() <= day <= ref_day.isoformat()) or reach < MIN_FOLLOWERS:
            continue
        if s.get("reblog"):
            continue
        items.append({
            "id": uri, "platform": "mastodon", "source_type": "sns", "tier": "T3",
            "media": "earned", "author": s["account"].get("acct") or s["account"].get("url"),
            "lang": s.get("language") or "",
            "published_at": day, "url": s.get("url") or uri,
            "reach": reach,
            "likes": s.get("favourites_count") or 0,
            "comments": s.get("replies_count") or 0,
            "shares": s.get("reblogs_count") or 0,
        })
    return items


def collect_youtube_search(region, ref_day, errors):
    """Earned YouTube videos about Gucci per region (YouTube Data API v3, free
    quota; needs YOUTUBE_API_KEY, skipped without it). order=date samples by
    recency, not by YouTube's relevance ranking, which favors already-popular
    videos (selection bias). reach = views. Brand-owned uploads are excluded."""
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return []
    after = (ref_day - timedelta(days=WINDOW_DAYS - 1)).isoformat() + "T00:00:00Z"
    before = (ref_day + timedelta(days=1)).isoformat() + "T00:00:00Z"
    ids = []
    for code, lang, q in YT_REGION_QUERIES[region]:
        params = {"part": "id", "type": "video", "q": q, "regionCode": code,
                  "relevanceLanguage": lang, "order": "date", "maxResults": 50,
                  "publishedAfter": after, "publishedBefore": before, "key": key}
        try:
            res = get_json(f"{YT_API}/search?" + urllib.parse.urlencode(params))
            ids += [r["id"]["videoId"] for r in res.get("items", []) if r.get("id", {}).get("videoId")]
        except Exception as e:  # noqa: BLE001
            errors.append(f"youtube search {code}: {str(e).replace(key, '***')}")
    items, seen = [], set()
    ids = [i for i in ids if not (i in seen or seen.add(i))]
    for i in range(0, len(ids), 50):
        params = {"part": "snippet,statistics", "id": ",".join(ids[i:i + 50]), "key": key}
        try:
            res = get_json(f"{YT_API}/videos?" + urllib.parse.urlencode(params))
        except Exception as e:  # noqa: BLE001
            errors.append(f"youtube videos: {str(e).replace(key, '***')}")
            continue
        for v in res.get("items", []):
            sn, st = v.get("snippet", {}), v.get("statistics", {})
            if sn.get("channelId") == YT_CHANNEL or "viewCount" not in st:
                continue
            items.append({
                "id": "yt:" + v["id"], "platform": "youtube", "source_type": "sns", "tier": "T3",
                "media": "earned", "author": sn.get("channelId"),
                "published_at": (sn.get("publishedAt") or "")[:10],
                "url": "https://www.youtube.com/watch?v=" + v["id"],
                "reach": int(st["viewCount"]),
                "likes": int(st["likeCount"]) if "likeCount" in st else None,
                "comments": int(st["commentCount"]) if "commentCount" in st else None,
                "shares": None,
            })
    return items


def collect_youtube(ref_day, errors):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={YT_CHANNEL}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            xml = r.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        errors.append(f"youtube rss: {e}")
        return []
    items = []
    for entry in xml.split("<entry>")[1:]:
        vid = re.search(r"<yt:videoId>(.*?)</yt:videoId>", entry)
        pub = re.search(r"<published>(\d{4}-\d{2}-\d{2})", entry)
        views = re.search(r'<media:statistics views="(\d+)"', entry)
        likes = re.search(r'<media:starRating count="(\d+)"', entry)
        if not (vid and pub and views):
            continue
        age = (ref_day - date.fromisoformat(pub.group(1))).days
        if age < 0 or age > YT_WINDOW_DAYS:
            continue
        items.append({
            "id": "yt:" + vid.group(1), "platform": "youtube", "source_type": "sns", "tier": "T2",
            "media": "owned", "author": YT_CHANNEL,
            "published_at": pub.group(1),
            "url": "https://www.youtube.com/watch?v=" + vid.group(1),
            "reach": int(views.group(1)),
            "likes": int(likes.group(1)) if likes else 0,
            "comments": None, "shares": None,
        })
    return items


def run(date_str, root):
    ref_day = date.fromisoformat(date_str)
    out_dir = Path(root) / "data" / "engagement" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    shared_errors = []
    yt_items = collect_youtube(ref_day, shared_errors)
    masto_all = collect_mastodon(ref_day, shared_errors)
    lang_region = {lang: r for r, langs in REGION_LANGS.items() for lang in langs}
    for region in REGION_LANGS:
        errors = list(shared_errors)
        bsky_items = collect_bsky(region, ref_day, errors)
        masto_items = [it for it in masto_all if lang_region.get(it["lang"][:2]) == region]
        yts_items = collect_youtube_search(region, ref_day, errors)
        doc = {
            "date": date_str, "region": region,
            "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sources": {"bluesky": len(bsky_items), "mastodon": len(masto_items),
                        "youtube_search": len(yts_items), "youtube": len(yt_items)},
            "errors": errors,
            "items": bsky_items + masto_items + yts_items + yt_items,
        }
        with open(out_dir / f"{region}.json", "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        print(f"{region}: bluesky={len(bsky_items)} mastodon={len(masto_items)} "
              f"youtube_search={len(yts_items)} youtube_owned={len(yt_items)} errors={len(errors)}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("date", nargs="?", default=date.today().isoformat())
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    a = ap.parse_args()
    try:
        return run(a.date, a.root)
    except Exception as e:  # noqa: BLE001 - never break the pipeline
        print(f"WARN: engagement collection failed: {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
