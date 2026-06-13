import pandas as pd
import numpy as np

yt = pd.read_csv("scripts/output/youtube_candidates.csv")
li_profiles = pd.read_csv("scripts/output/linkedin_profiles_found.csv")
li_posts = pd.read_csv("scripts/output/linkedin_authors_ranked.csv")

def norm(s):
    return str(s).lower().strip()

yt["name_norm"] = yt["channel_name"].apply(norm)
li_profiles["name_norm"] = li_profiles["name"].apply(norm)
li_posts["name_norm"] = li_posts["author"].apply(norm)

merged = yt.merge(li_profiles[["name_norm","linkedin_url"]], on="name_norm", how="left")
merged = merged.merge(
    li_posts[["name_norm","appearances"]].rename(columns={"appearances":"li_post_appearances"}),
    on="name_norm", how="left"
)
merged["li_post_appearances"] = merged["li_post_appearances"].fillna(0)
merged["has_linkedin"] = merged["linkedin_url"].notna().astype(int)
merged["cross_source_bonus"] = (
    merged["has_linkedin"] * 0.1 +
    (merged["li_post_appearances"] > 0).astype(int) * 0.1
)

merged["combined_score"] = merged["final_score"] + merged["cross_source_bonus"]
merged = merged.sort_values("combined_score", ascending=False)

merged.head(15).to_csv("scripts/output/final_ranked_candidates.csv", index=False)
print(merged[["channel_name","combined_score","final_score","appearances",
               "li_post_appearances","linkedin_url","latest_video"]].head(15).to_string(index=False))
