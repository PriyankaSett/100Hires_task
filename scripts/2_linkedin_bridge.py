import requests
import pandas as pd
import time

SERPAPI_KEY = "**************************"

def find_linkedin(name, topic_hint="SEO AI content"):
    q = f'site:linkedin.com/in "{name}" {topic_hint}'
    r = requests.get("https://serpapi.com/search",
                      params={"q": q, "api_key": SERPAPI_KEY, "num": 3, "engine": "google"})
    if r.status_code != 200:
        return None
    for res in r.json().get("organic_results", []):
        url = res.get("link", "")
        if "linkedin.com/in/" in url:
            return {"name": name, "linkedin_url": url, "snippet": res.get("snippet","")}
    return None

yt = pd.read_csv("scripts/output/youtube_candidates.csv")
names = yt.sort_values("final_score", ascending=False)["channel_name"].head(25).tolist()

results = []
for name in names:
    print(f"Searching LinkedIn for: {name}")
    res = find_linkedin(name)
    results.append(res or {"name": name, "linkedin_url": None, "snippet": ""})
    time.sleep(1.5)

pd.DataFrame(results).to_csv("scripts/output/linkedin_profiles_found.csv", index=False)
print("Saved scripts/output/linkedin_profiles_found.csv")