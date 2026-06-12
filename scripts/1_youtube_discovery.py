from googleapiclient.discovery import build
import pandas as pd
import numpy as np
from datetime import datetime, date
import time

import os
#from dotenv import load_dotenv

#load_dotenv()

# Set to True to test the pipeline with fake data (no API calls, no quota used)
DRY_RUN = True

#YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

YOUTUBE_API_KEY = "YOUR_YOUTUBE_KEY"
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

if not DRY_RUN:
    from googleapiclient.discovery import build
    if not YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY not found. Check your .env file.")
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


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

def get_fake_data():
    """Fake data matching the real API's shape, for testing the pipeline."""
    fake_channels = [
        ("Kevin Indig", "CHAN_001", 85000),
        ("Eli Schwartz", "CHAN_002", 32000),
        ("Ross Hudgens", "CHAN_003", 18000),
        ("Brendan Hufford", "CHAN_004", 9500),
        ("Irina Maltseva", "CHAN_005", 4200),
    ]
    all_videos = []
    for i, q in enumerate(QUERIES):
        for name, cid, _ in fake_channels[:3]:  # each query "finds" 3 channels
            all_videos.append({
                "channel_name": name,
                "channel_id":   cid,
                "video_title":  f"Sample video about {q}",
                "video_id":     f"vid_{i}_{cid}",
                "published_at": "2025-03-15",
                "query":        q,
            })
    stats_lookup = {cid: {"subscriber_count": subs, "video_count": 120}
                    for _, cid, subs in fake_channels}
    return all_videos, stats_lookup

# --- Run ---
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
        stats = stats_lookup.get(r["channel_id"], {"subscriber_count": 0, "video_count": 0})
    else:
        stats = channel_stats(r["channel_id"])
        time.sleep(0.3)
    rows.append({**r.to_dict(), **stats})

out = pd.DataFrame(rows)

today = date.today()
def recency_score(d):
    try:
        last = datetime.strptime(d, "%Y-%m-%d").date()
        months = (today - last).days / 30
        return max(0, 1 - months/12)
    except:
        return 0

def normalise(s):
    return (s - s.min()) / (s.max() - s.min()) if s.max() != s.min() else s*0

out["recency"]   = out["latest_video"].apply(recency_score)
out["freq_norm"] = normalise(out["appearances"])
out["subs_norm"] = normalise(np.log1p(out["subscriber_count"]))
out["score"]     = out["freq_norm"]*0.4 + out["recency"]*0.3 + out["subs_norm"]*0.3
out["youtube_url"] = "https://youtube.com/channel/" + out["channel_id"]

out = out.sort_values("score", ascending=False)
out.to_csv("scripts/output/youtube_candidates.csv", index=False)
print(out[["channel_name","score","appearances","subscriber_count","latest_video"]].head(20).to_string())