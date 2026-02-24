"""ARASAAC pictogram search and download."""

import json
import os
import hashlib
from urllib.request import urlopen, Request
from urllib.parse import quote
import gettext

_ = gettext.gettext

ARASAAC_API = "https://api.arasaac.org/v1"
ARASAAC_STATIC = "https://static.arasaac.org"
VALID_RESOLUTIONS = [300, 500, 2500]


def search_pictograms(query, language="en"):
    """Search ARASAAC for pictograms matching query. Returns list of dicts."""
    url = f"{ARASAAC_API}/pictograms/{language}/search/{quote(query)}"
    try:
        req = Request(url, headers={"User-Agent": "AsTeRICS-Board-Editor/0.1"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            results = []
            for item in data[:50]:  # limit results
                pid = item.get("_id")
                keywords = []
                for kw in item.get("keywords", []):
                    if isinstance(kw, dict):
                        keywords.append(kw.get("keyword", ""))
                    else:
                        keywords.append(str(kw))
                results.append({
                    "id": pid,
                    "keywords": keywords,
                    "url_300": pictogram_url(pid, 300),
                    "url_500": pictogram_url(pid, 500),
                    "url_2500": pictogram_url(pid, 2500),
                })
            return results
    except Exception as e:
        print(f"ARASAAC search error: {e}")
        return []


def pictogram_url(pictogram_id, resolution=500):
    """Get static URL for a pictogram at given resolution."""
    if resolution not in VALID_RESOLUTIONS:
        resolution = 500
    return f"{ARASAAC_STATIC}/pictograms/{pictogram_id}/{pictogram_id}_{resolution}.png"


def download_pictogram(url, cache_dir=None):
    """Download a pictogram and return local path. Uses caching."""
    if cache_dir is None:
        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "asterics-board-editor", "pictograms")
    os.makedirs(cache_dir, exist_ok=True)

    url_hash = hashlib.md5(url.encode()).hexdigest()
    ext = ".png"
    local_path = os.path.join(cache_dir, f"{url_hash}{ext}")

    if os.path.exists(local_path):
        return local_path

    try:
        req = Request(url, headers={"User-Agent": "AsTeRICS-Board-Editor/0.1"})
        with urlopen(req, timeout=15) as resp:
            data = resp.read()
        with open(local_path, "wb") as f:
            f.write(data)
        return local_path
    except Exception as e:
        print(f"Download error: {e}")
        return None
