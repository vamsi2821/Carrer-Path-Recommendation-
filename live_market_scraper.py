"""
Live market collector: RSS + NSE APIs + light HTML meta scrape.
Caches successful runs to data/live_market_cache.json so the UI still shows content when offline.

Note: Many broker sites (Groww, INDmoney) are JavaScript apps — we extract <title>/OpenGraph
meta only, or rely on public RSS. Full page scraping may violate site terms; use for education.
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_PATH = Path(__file__).resolve().parent / "data" / "live_market_cache.json"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 WealthMindEducational/1.0"
)

# RSS feeds (structured public syndication — preferred over raw HTML scraping)
RSS_SOURCES = (
    ("Livemint · Markets", "https://www.livemint.com/rss/markets"),
    ("Economic Times · Markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Economic Times · Stocks", "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms"),
    ("Moneycontrol · Business", "https://www.moneycontrol.com/rss/business.xml"),
    ("Business Standard · Markets", "https://www.business-standard.com/rss/markets-106.rss"),
    ("Investing.com India · Indices", "https://in.investing.com/rss/stock_Indices.rss"),
    ("Investing.com · Popular", "https://in.investing.com/rss/news_285.rss"),
    ("Yahoo Finance · NIFTY", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5ENSEI&region=IN&lang=en-IN"),
    ("CNBC · Markets", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
)

# Pages where we only read <title> + og:description (fast, low impact)
META_SCRAPE_PAGES = (
    ("Groww · Markets (meta)", "https://groww.in/markets"),
    ("INDmoney · Stocks (meta)", "https://www.indmoney.com/stocks"),
    ("Business Standard · Markets (meta)", "https://www.business-standard.com/markets"),
    ("NSE India · Home (meta)", "https://www.nseindia.com/"),
)


def _ensure_requests():
    try:
        import requests

        return requests
    except ImportError:
        return None


def _ensure_bs4():
    try:
        from bs4 import BeautifulSoup

        return BeautifulSoup
    except ImportError:
        return None


def _parse_rss_items(xml_bytes: bytes, source_name: str, limit: int) -> list[dict]:
    out = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return out
    for elem in root.iter():
        if not (elem.tag.endswith("item") or elem.tag == "item"):
            continue
        if len(out) >= limit:
            break
        title, link = None, None
        for ch in elem:
            tag = ch.tag.split("}")[-1].lower()
            if tag == "title" and ch.text:
                title = html_lib.unescape(ch.text.strip())
            elif tag == "link" and ch.text:
                link = ch.text.strip()
        if title and link:
            out.append(
                {
                    "type": "rss",
                    "source": source_name,
                    "title": title[:300],
                    "link": link,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }
            )
    return out


def _fetch_rss(session, url: str, source_name: str, per_feed: int = 5) -> list[dict]:
    requests = _ensure_requests()
    if session is None and requests is None:
        return []
    try:
        if session:
            r = session.get(url, timeout=22)
            if not r.ok:
                return []
            data = r.content
        else:
            import urllib.request

            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=22) as resp:
                data = resp.read()
        return _parse_rss_items(data, source_name, per_feed)
    except Exception as e:
        logger.debug("rss %s: %s", url[:48], e)
        return []


def _scrape_page_meta(url: str, label: str) -> dict | None:
    """Best-effort: title + og:description. Many sites block bots or return shell HTML."""
    requests = _ensure_requests()
    BeautifulSoup = _ensure_bs4()
    if not requests or not BeautifulSoup:
        return {
            "type": "meta",
            "source": label,
            "url": url,
            "title": None,
            "snippet": "Install beautifulsoup4: pip install beautifulsoup4",
            "ok": False,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
    try:
        r = requests.get(url, timeout=14, headers={"User-Agent": _USER_AGENT})
        if not r.ok:
            return {
                "type": "meta",
                "source": label,
                "url": url,
                "title": f"HTTP {r.status_code}",
                "snippet": "Page not reachable or blocked (403/404).",
                "ok": False,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
        soup = BeautifulSoup(r.text, "html.parser")
        title_el = soup.find("title")
        title = title_el.get_text(strip=True)[:200] if title_el else ""
        og = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        snippet = ""
        if og and og.get("content"):
            snippet = og["content"].strip()[:400]
        if not snippet and title:
            snippet = title[:400]
        return {
            "type": "meta",
            "source": label,
            "url": url,
            "title": title or label,
            "snippet": snippet or "(No static description — site may be SPA/React.)",
            "ok": True,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {
            "type": "meta",
            "source": label,
            "url": url,
            "title": None,
            "snippet": str(e)[:200],
            "ok": False,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }


def _nse_snapshot_block() -> dict:
    try:
        from indian_market_data import nse_index_row

        rows = []
        for name, idx in (("NIFTY 50", "NIFTY 50"), ("NIFTY Bank", "NIFTY BANK")):
            r = nse_index_row(idx)
            if r:
                rows.append(
                    {
                        "name": name,
                        "last": r["last"],
                        "change_pct": r["change_pct"],
                        "updated": r.get("last_update", ""),
                    }
                )
        return {"type": "nse_api", "indices": rows, "ok": bool(rows)}
    except Exception as e:
        return {"type": "nse_api", "indices": [], "ok": False, "error": str(e)[:120]}


def collect_live_market() -> dict:
    """Run all collectors; merge into one payload."""
    requests = _ensure_requests()
    session = requests.Session() if requests else None
    if session:
        session.headers.update({"User-Agent": _USER_AGENT, "Accept": "application/rss+xml, application/xml, */*"})

    rss_items: list[dict] = []
    for pub, url in RSS_SOURCES:
        rss_items.extend(_fetch_rss(session, url, pub, per_feed=3))

    meta_items: list[dict] = []
    for label, url in META_SCRAPE_PAGES:
        m = _scrape_page_meta(url, label)
        if m:
            meta_items.append(m)

    nse_block = _nse_snapshot_block()

    as_of = datetime.now(timezone.utc).isoformat()
    payload = {
        "as_of": as_of,
        "source_label": "live_market_scraper",
        "nse": nse_block,
        "rss_headlines": rss_items[:30],
        "page_meta": meta_items,
        "disclaimer": (
            "Educational aggregation. RSS feeds and public NSE APIs only; "
            "meta snippets are best-effort. Respect site terms; not for trading."
        ),
    }
    return payload


def load_cache() -> dict | None:
    if not _CACHE_PATH.is_file():
        return None
    try:
        with open(_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def save_cache(payload: dict) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = payload.copy()
        tmp["cached_at"] = datetime.now(timezone.utc).isoformat()
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(tmp, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning("Could not save cache: %s", e)


def get_live_market_payload(use_cache_on_failure: bool = True) -> dict:
    """
    Fresh collect; on failure return last cache with stale=True.
    """
    try:
        fresh = collect_live_market()
        save_cache(fresh)
        fresh["stale"] = False
        fresh["from_cache"] = False
        return fresh
    except Exception as e:
        err = {"error": str(e), "as_of": datetime.now(timezone.utc).isoformat()}
        if use_cache_on_failure:
            cached = load_cache()
            if cached:
                cached = dict(cached)
                cached["stale"] = True
                cached["from_cache"] = True
                cached["error_note"] = str(e)[:200]
                return cached
        err["stale"] = True
        err["from_cache"] = False
        return err
