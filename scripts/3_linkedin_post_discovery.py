import requests
import pandas as pd
import re
import time

SERPAPI_KEY = "****************************"

QUERIES = [
    'site:linkedin.com/posts "AI content workflow" SEO',
    'site:linkedin.com/posts "AI content brief" SEO',
    'site:linkedin.com/posts "GEO" "generative engine optimization"',
    'site:linkedin.com/posts "AI SEO" content 2025',
    'site:linkedin.com/posts "content ops" AI',
]

def google_search(q, num=10):
    r = requests.get("https://serpapi.com/search",
                      params={"q": q, "api_key": SERPAPI_KEY, "num": num, "engine": "google"})
    return r.json().get("organic_results", []) if r.status_code == 200 else []

def extract_author(url):
    m = re.search(r"linkedin\.com/posts/([a-z0-9\-]+)_", url)
    if not m:
        return "Unknown"
    parts = [p.capitalize() for p in m.group(1).split("-") if not p.isdigit() and len(p) > 1]
    return " ".join(parts[:3])

rows = []
for q in QUERIES:
    print(f"Searching: {q}")
    for r in google_search(q):
        url = r.get("link", "")
        rows.append({
            "author":  extract_author(url),
            "url":     url,
            "title":   r.get("title",""),
            "snippet": r.get("snippet",""),
            "query":   q,
        })
    time.sleep(1)

df = pd.DataFrame(rows)
freq = df.groupby("author").agg(
    appearances=("url","count"),
    sample=("title", lambda x: " | ".join(list(x)[:2]))
).reset_index().sort_values("appearances", ascending=False)

df.to_csv("scripts/output/linkedin_posts_raw.csv", index=False)
freq.to_csv("scripts/output/linkedin_authors_ranked.csv", index=False)
print(freq.head(15).to_string(index=False))