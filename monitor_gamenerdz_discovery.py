import json
import os
import re
from pathlib import Path
from typing import List, Set, Tuple

import requests
from bs4 import BeautifulSoup

DISCOVERY_URLS = [
    "https://www.gamenerdz.com/one-piece",
    "https://www.gamenerdz.com/preorders",
]

STATE_FILE = Path("known_links.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    )
}

TARGET_PATTERNS = [
    "op-16", "op16",
    "op-17", "op17",
]

BOX_TERMS = [
    "booster box",
    "display box",
    "booster",
    "box",
]

ONE_PIECE_TERMS = [
    "one piece",
    "one piece tcg",
]


def load_seen() -> Set[str]:
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data.get("seen_urls", []))
    return set()


def save_seen(urls: Set[str]) -> None:
    STATE_FILE.write_text(
        json.dumps({"seen_urls": sorted(urls)}, indent=2),
        encoding="utf-8",
    )


def send_discord(message: str) -> None:
    webhook = os.environ.get("DISCORD_WEBHOOK")
    print("Webhook exists:", bool(webhook))

    if not webhook:
        print("DISCORD_WEBHOOK not set; skipping alert.")
        return

    resp = requests.post(webhook, json={"content": message}, timeout=20)
    print("Discord status:", resp.status_code)
    print("Discord body:", resp.text)
    resp.raise_for_status()
    print("Discord alert sent successfully.")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def fetch_html(url: str) -> str:
    print("Fetching:", url)
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def title_matches(title: str, href: str) -> bool:
    hay = normalize(f"{title} {href}")

    has_set = any(term in hay for term in TARGET_PATTERNS)
    has_one_piece = any(term in hay for term in ONE_PIECE_TERMS)
    has_boxish = any(term in hay for term in BOX_TERMS)

    return has_set and has_box and has_one_piece


def extract_candidates(html: str) -> List[Tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    candidates = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        title = a.get_text(" ", strip=True)

        if not title:
            continue

        if href.startswith("/"):
            full_url = "https://www.gamenerdz.com" + href
        elif href.startswith("http"):
            full_url = href
        else:
            continue

        if "gamenerdz.com" not in full_url:
            continue

        if title_matches(title, full_url):
            candidates.append((title, full_url))

    seen = set()
    deduped = []
    for item in candidates:
        if item[1] not in seen:
            deduped.append(item)
            seen.add(item[1])

    return deduped


def main() -> None:
    seen_urls = load_seen()
    current_seen = set(seen_urls)
    new_hits = []

    for url in DISCOVERY_URLS:
        html = fetch_html(url)
        candidates = extract_candidates(html)

        for title, product_url in candidates:
            print("Found candidate:", title, product_url)
            current_seen.add(product_url)

            if product_url not in seen_urls:
                new_hits.append((title, product_url))

    for title, product_url in new_hits:
        send_discord(
            "🔥 NEW GAME NERDZ OP PRODUCT PAGE DETECTED\n"
            f"Title: {title}\n"
            f"URL: {product_url}"
        )

    save_seen(current_seen)
    print("Saved seen URLs:", len(current_seen))


if __name__ == "__main__":
    main()
