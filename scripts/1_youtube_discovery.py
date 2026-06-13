import os
#from dotenv import load_dotenv
from googleapiclient.discovery import build
import pandas as pd
import numpy as np
from datetime import datetime, date
import time

#load_dotenv()

# Set to True to test the pipeline with fake data (no API calls, no quota used)
DRY_RUN = False

#YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_API_KEY = "****************"

if not DRY_RUN:
    from googleapiclient.discovery import build
    if not YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY not found. Check your .env file.")
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


# Practitioner-vocabulary queries
QUERIES = [
    '"AI content workflow" SEO',
    '"AI content brief" SEO process',
    '"GEO" generative engine optimization',
    '"AEO" answer engine optimization SEO',
    '"AI SEO" content workflow 2025',
    '"how I use AI" SEO content',
    '"Surfer SEO" AI content workflow',
    '"content ops" AI SEO',
    '"programmatic SEO" AI',
]


# ---------------------------------------------------------------------------
# Real API functions (only used when DRY_RUN = False)
# ---------------------------------------------------------------------------

def search_videos(query, max_results=15):
    resp = youtube.search().list(
        q=query, type="video", part="snippet",
        maxResults=max_results, order="relevance",
        publishedAfter="2024-01-01T00:00:00Z"
    ).execute()
    out = []
    for item in resp.get("items", []):
        out.append({
            "channel_name": item["snippet"]["channelTitle"],
            "channel_id":   item["snippet"]["channelId"],
            "video_title":  item["snippet"]["title"],
            "video_id":     item["id"]["videoId"],
            "published_at": item["snippet"]["publishedAt"][:10],
            "query":        query,
        })
    return out


def channel_stats(channel_id):
    resp = youtube.channels().list(id=channel_id, part="statistics").execute()
    if not resp["items"]:
        return {"subscriber_count": 0, "video_count": 0}
    s = resp["items"][0]["statistics"]
    return {
        "subscriber_count": int(s.get("subscriberCount", 0)),
        "video_count":      int(s.get("videoCount", 0)),
    }


def get_recent_video_stats(channel_id, n=5):
    """Fetch view counts and dates for the N most recent videos."""
    search_resp = youtube.search().list(
        channelId=channel_id, type="video", part="snippet",
        order="date", maxResults=n
    ).execute()

    video_ids = [item["id"]["videoId"] for item in search_resp.get("items", [])]
    dates = [item["snippet"]["publishedAt"][:10] for item in search_resp.get("items", [])]

    if not video_ids:
        return {"avg_recent_views": 0, "days_since_last_upload": 9999, "upload_dates": []}

    stats_resp = youtube.videos().list(
        id=",".join(video_ids), part="statistics"
    ).execute()

    views = [int(v["statistics"].get("viewCount", 0)) for v in stats_resp.get("items", [])]
    avg_views = sum(views) / len(views) if views else 0

    last_date = max(dates)
    days_since = (date.today() - datetime.strptime(last_date, "%Y-%m-%d").date()).days

    return {
        "avg_recent_views": avg_views,
        "days_since_last_upload": days_since,
        "upload_dates": dates,
    }


# ---------------------------------------------------------------------------
# Shared helper functions (used in both DRY_RUN and real mode)
# ---------------------------------------------------------------------------

def posting_cadence_days(upload_dates):
    """Average days between uploads — lower = more frequent."""
    if len(upload_dates) < 2:
        return 999
    dates_sorted = sorted([datetime.strptime(d, "%Y-%m-%d") for d in upload_dates], reverse=True)
    gaps = [(dates_sorted[i] - dates_sorted[i + 1]).days for i in range(len(dates_sorted) - 1)]
    return sum(gaps) / len(gaps)


def normalise(s):
    return (s - s.min()) / (s.max() - s.min()) if s.max() != s.min() else s * 0


def ratio_score(r):
    """10-20% view/sub ratio is the 'healthy engaged audience' benchmark."""
    if r >= 0.10:
        return min(1.0, r / 0.20)
    return r / 0.10 * 0.5


# ---------------------------------------------------------------------------
# Fake data generator (only used when DRY_RUN = True)
# ---------------------------------------------------------------------------

def get_fake_data():
    """Fake data matching the real API's shape, for testing the pipeline."""
    today_str = date.today().strftime("%Y-%m-%d")

    fake_channels = [
        # name, channel_id, subscribers, avg_recent_views, days_since_last_upload, upload_dates
        ("Kevin Indig",     "CHAN_001", 85000, 14000, 3,  ["2025-06-01","2025-05-20","2025-05-10","2025-04-28","2025-04-15"]),
        ("Eli Schwartz",    "CHAN_002", 32000, 7000,  10, ["2025-05-25","2025-05-05","2025-04-10","2025-03-15","2025-02-20"]),
        ("Ross Hudgens",    "CHAN_003", 18000, 4500,  5,  ["2025-06-05","2025-05-28","2025-05-21","2025-05-14","2025-05-07"]),
        ("Brendan Hufford", "CHAN_004", 9500,  3200,  20, ["2025-05-15","2025-04-15","2025-03-15","2025-02-15","2025-01-15"]),
        ("Irina Maltseva",  "CHAN_005", 4200,  150,   200,["2024-11-01","2024-09-01","2024-07-01","2024-05-01","2024-03-01"]),
    ]

    all_videos = []
    for i, q in enumerate(QUERIES):
        for name, cid, _, _, _, _ in fake_channels[:3]:  # each query "finds" 3 channels
            all_videos.append({
                "channel_name": name,
                "channel_id":   cid,
                "video_title":  f"Sample video about {q}",
                "video_id":     f"vid_{i}_{cid}",
                "published_at": "2025-03-15",
                "query":        q,
            })

    stats_lookup = {}
    for name, cid, subs, avg_views, days_since, upload_dates in fake_channels:
        stats_lookup[cid] = {
            "subscriber_count":       subs,
            "video_count":            120,
            "avg_recent_views":       avg_views,
            "days_since_last_upload": days_since,
            "upload_dates":           upload_dates,
        }

    return all_videos, stats_lookup


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

if DRY_RUN:
    print("DRY RUN MODE — using fake data, no API calls made\n")
    all_videos, stats_lookup = get_fake_data()
else:
    all_videos = []
    for q in QUERIES:
        print(f"Searching: {q}")
        all_videos.extend(search_videos(q))
        time.sleep(1)

df = pd.DataFrame(all_videos)

agg = df.groupby(["channel_name", "channel_id"]).agg(
    appearances=("video_id", "count"),
    latest_video=("published_at", "max"),
    sample_titles=("video_title", lambda x: " | ".join(list(x)[:3])),
    matched_queries=("query", lambda x: ", ".join(set(x))),
).reset_index().sort_values("appearances", ascending=False).head(30)

print("\nFetching channel stats...")
rows = []
for _, r in agg.iterrows():
    if DRY_RUN:
        s = stats_lookup.get(r["channel_id"], {
            "subscriber_count": 0, "video_count": 0,
            "avg_recent_views": 0, "days_since_last_upload": 9999,
            "upload_dates": [],
        })
        stats = {
            "subscriber_count":       s["subscriber_count"],
            "video_count":            s["video_count"],
            "avg_recent_views":       s["avg_recent_views"],
            "days_since_last_upload": s["days_since_last_upload"],
            "posting_cadence_days":   posting_cadence_days(s["upload_dates"]),
        }
    else:
        stats = channel_stats(r["channel_id"])
        recent = get_recent_video_stats(r["channel_id"], n=5)
        stats["avg_recent_views"]       = recent["avg_recent_views"]
        stats["days_since_last_upload"] = recent["days_since_last_upload"]
        stats["posting_cadence_days"]   = posting_cadence_days(recent["upload_dates"])
        time.sleep(0.3)

    rows.append({**r.to_dict(), **stats})

out = pd.DataFrame(rows)

# --- Scoring ---

# View-to-subscriber ratio
out["view_sub_ratio"] = out["avg_recent_views"] / out["subscriber_count"].replace(0, 1)

# Recency: full score if posted today, decays to 0 over 60 days
out["recency"] = out["days_since_last_upload"].apply(lambda d: max(0, 1 - (d / 60)))

# Cadence: full score if posting every day, decays to 0 at 30+ day gaps
out["cadence_score"] = out["posting_cadence_days"].apply(lambda d: max(0, 1 - (d / 30)))

# Engagement: 10-20% view/sub ratio is the healthy benchmark
out["engagement_score"] = out["view_sub_ratio"].apply(ratio_score)

# Cross-query frequency
out["freq_norm"] = normalise(out["appearances"])

# Final combined score
out["final_score"] = (
    out["freq_norm"]        * 0.25 +
    out["recency"]          * 0.25 +
    out["cadence_score"]    * 0.20 +
    out["engagement_score"] * 0.30
)

out["youtube_url"] = "https://youtube.com/channel/" + out["channel_id"]
out = out.sort_values("final_score", ascending=False)

os.makedirs("scripts/output", exist_ok=True)
out.to_csv("scripts/output/youtube_candidates.csv", index=False)

print(out[["channel_name", "final_score", "view_sub_ratio", "recency",
           "cadence_score", "engagement_score", "subscriber_count"]].head(20).to_string())
print("\nSaved scripts/output/youtube_candidates.csv")