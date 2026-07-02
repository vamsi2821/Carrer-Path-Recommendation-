"""
Indian market data: NSE India (official quotes) + Nifty Indices (historical OHLC via niftyindices.com).
Used when Yahoo Finance is rate-limited or unreliable. Same underlying feeds brokers and apps use.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar
from urllib.parse import quote

try:
    import requests
except ImportError:
    requests = None  # type: ignore

try:
    import yfinance as yf
except Exception:
    yf = None  # type: ignore

logger = logging.getLogger(__name__)

# One shared session + cookies — NSE often needs a homepage visit before JSON APIs respond.
_NSE_SESSION = None
_NSE_WARMED = False

_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-IN,en;q=0.9",
}

_NIFTY_INDICES_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/json; charset=UTF-8",
    "Origin": "https://niftyindices.com",
    "Referer": "https://niftyindices.com/reports/historical-data",
    "X-Requested-With": "XMLHttpRequest",
}


def _get_nse_session():
    global _NSE_SESSION
    if requests is None:
        return None
    if _NSE_SESSION is None:
        _NSE_SESSION = requests.Session()
        _NSE_SESSION.headers.update(_NSE_HEADERS)
    return _NSE_SESSION


def _nse_warmup_once() -> None:
    """Prime cookies from nseindia.com (required on many networks)."""
    global _NSE_WARMED
    if _NSE_WARMED:
        return
    s = _get_nse_session()
    if s is None:
        return
    try:
        s.get("https://www.nseindia.com/", timeout=18)
    except Exception as e:
        logger.debug("nse warmup: %s", e)
    _NSE_WARMED = True


def _nse_json_urllib(url: str) -> dict | list | None:
    """Fallback when requests is missing or blocked."""
    try:
        jar = CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        opener.addheaders = [
            ("User-Agent", _NSE_HEADERS["User-Agent"]),
            ("Accept", "application/json"),
            ("Accept-Language", "en-IN,en;q=0.9"),
        ]
        opener.open("https://www.nseindia.com/", timeout=18)
        req = urllib.request.Request(url, headers=dict(opener.addheaders))
        with opener.open(req, timeout=22) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError, ValueError) as e:
        logger.debug("nse urllib %s: %s", url[:60], e)
        return None


def nse_index_row(index_name: str) -> dict | None:
    """Latest session snapshot for an NSE index (e.g. 'NIFTY 50', 'NIFTY BANK')."""
    enc = quote(index_name, safe="")
    url = f"https://www.nseindia.com/api/equity-stockIndices?index={enc}"
    _nse_warmup_once()
    s = _get_nse_session()
    try:
        payload = None
        if s is not None:
            r = s.get(url, timeout=22)
            if r.ok:
                payload = r.json()
        if payload is None:
            payload = _nse_json_urllib(url)
            if not isinstance(payload, dict):
                return None
        data = payload.get("data") or []
        if not data:
            return None
        row = data[0]
        last = float(row.get("lastPrice") or 0)
        prev = float(row.get("previousClose") or last)
        chg_pct = float(row.get("pChange") or 0)
        if last and prev:
            calc = ((last - prev) / prev * 100.0) if prev else 0.0
            if abs(chg_pct) < 0.001 and abs(calc) > 0.001:
                chg_pct = calc
        return {
            "name": row.get("index") or index_name,
            "last": round(last, 2),
            "previous_close": round(prev, 2),
            "change_pct": round(chg_pct, 2),
            "day_high": float(row.get("dayHigh") or 0),
            "day_low": float(row.get("dayLow") or 0),
            "last_update": row.get("lastUpdateTime") or "",
        }
    except Exception as e:
        logger.debug("nse_index_row %s: %s", index_name, e)
        return None


def nse_equity_row(symbol: str) -> dict | None:
    """Latest quote for an NSE equity symbol (e.g. RELIANCE)."""
    enc_sym = quote(symbol, safe="")
    url = f"https://www.nseindia.com/api/quote-equity?symbol={enc_sym}"
    _nse_warmup_once()
    s = _get_nse_session()
    try:
        if s is not None:
            r = s.get(url, timeout=22)
            if not r.ok:
                j = None
            else:
                j = r.json()
        else:
            j = None
        if j is None:
            ju = _nse_json_urllib(url)
            j = ju if isinstance(ju, dict) else None
        if not j:
            return None
        pi = j.get("priceInfo") or {}
        last = float(pi.get("lastPrice") or 0)
        prev = float(pi.get("previousClose") or pi.get("basePrice") or last)
        pchg = float(pi.get("pChange") or 0)
        if last and prev and abs(pchg) < 0.0001:
            pchg = ((last - prev) / prev * 100.0) if prev else 0.0
        ih = pi.get("intraDayHighLow") or {}
        day_high = float(ih.get("max") or last)
        day_low = float(ih.get("min") or last)
        return {
            "name": (j.get("info") or {}).get("companyName") or symbol,
            "symbol": symbol,
            "last": round(last, 2),
            "previous_close": round(prev, 2),
            "change_pct": round(pchg, 2),
            "day_high": round(day_high, 2),
            "day_low": round(day_low, 2),
        }
    except Exception as e:
        logger.debug("nse_equity_row %s: %s", symbol, e)
        return None


def nifty_index_history(symbol: str, days: int = 70) -> list[dict]:
    """
    Daily OHLC from Nifty Indices (official index compiler). Returns newest-last rows.
    symbol examples: 'NIFTY 50', 'NIFTY BANK'
    """
    if requests is None:
        return []
    end = datetime.now()
    start = end - timedelta(days=max(days, 14))
    start_s = start.strftime("%d-%b-%Y")
    end_s = end.strftime("%d-%b-%Y")
    payload = {
        "cinfo": (
            "{'name':'"
            + symbol
            + "','startDate':'"
            + start_s
            + "','endDate':'"
            + end_s
            + "','indexName':'"
            + symbol
            + "'}"
        )
    }
    try:
        r = requests.post(
            "https://niftyindices.com/Backpage.aspx/getHistoricaldatatabletoString",
            headers=_NIFTY_INDICES_HEADERS,
            json=payload,
            timeout=25,
        )
        if not r.ok:
            return []
        outer = r.json()
        inner = json.loads(outer.get("d") or "[]")
        if not inner:
            return []
        out = []
        for rec in inner:
            try:
                dt = rec.get("HistoricalDate") or rec.get("Date") or ""
                close = float(rec.get("CLOSE") or rec.get("Close") or 0)
                if close <= 0:
                    continue
                out.append(
                    {
                        "date": str(dt),
                        "close": round(close, 2),
                    }
                )
            except (TypeError, ValueError):
                continue
        return out
    except Exception as e:
        logger.debug("nifty_index_history %s: %s", symbol, e)
        return []


def closes_and_labels_from_history(rows: list[dict], max_points: int = 65) -> tuple[list[str], list[float]]:
    if not rows:
        return [], []
    # API returns newest date first; charts need oldest → newest
    chunk = rows[:max_points]
    chunk = list(reversed(chunk))
    labels = []
    closes = []
    for r in chunk:
        closes.append(float(r["close"]))
        ds = r.get("date", "")
        labels.append(str(ds)[:11].replace("-", " "))
    return labels, closes


def daily_pct_moves_from_closes(closes: list[float]) -> tuple[list[str], list[float]]:
    """Skip first day; label aligned with change for day i vs i-1."""
    if len(closes) < 2:
        return [], []
    labels = []
    changes = []
    for i in range(1, len(closes)):
        prev_c = closes[i - 1]
        cur = closes[i]
        pct = ((cur - prev_c) / prev_c * 100.0) if prev_c else 0.0
        changes.append(round(pct, 3))
        labels.append(f"D{i}")
    return labels, changes


def coingecko_btc_inr() -> dict | None:
    """Spot BTC/INR (global crypto; shown for context only)."""
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin&vs_currencies=inr&include_24hr_change=true"
    )
    try:
        if requests is not None:
            r = requests.get(
                url,
                headers={"User-Agent": _NSE_HEADERS["User-Agent"]},
                timeout=12,
            )
            if not r.ok:
                return None
            j = r.json().get("bitcoin") or {}
        else:
            req = urllib.request.Request(url, headers={"User-Agent": _NSE_HEADERS["User-Agent"]})
            with urllib.request.urlopen(req, timeout=12) as resp:
                body = json.loads(resp.read().decode("utf-8", errors="replace"))
            j = body.get("bitcoin") or {}
        inr = float(j.get("inr") or 0)
        chg = float(j.get("inr_24h_change") or 0)
        if inr <= 0:
            return None
        return {"last_inr": round(inr, 0), "change_pct_24h": round(chg, 2)}
    except Exception:
        return None


def snapshot_items_india() -> tuple[list[dict], bool]:
    """
    Rows for the advisory market snapshot card: India-first instruments.
    """
    items = []
    ok = False
    for label, index_name in (
        ("NIFTY 50", "NIFTY 50"),
        ("NIFTY Bank", "NIFTY BANK"),
    ):
        row = nse_index_row(index_name)
        if row:
            ok = True
            items.append(
                {
                    "name": label,
                    "ticker": index_name,
                    "last_price": row["last"],
                    "change_pct": row["change_pct"],
                }
            )

    gold = nse_equity_row("GOLDBEES")
    if gold:
        ok = True
        items.append(
            {
                "name": "Gold ETF (NSE: GOLDBEES)",
                "ticker": "GOLDBEES",
                "last_price": gold["last"],
                "change_pct": gold["change_pct"],
            }
        )

    btc = coingecko_btc_inr()
    if btc:
        ok = True
        items.append(
            {
                "name": "Bitcoin (INR, indicative)",
                "ticker": "BTC-INR",
                "last_price": btc["last_inr"],
                "change_pct": btc["change_pct_24h"],
            }
        )

    return items, ok


def _direction_from_pct(change_pct: float) -> str:
    if change_pct > 0.08:
        return "up"
    if change_pct < -0.08:
        return "down"
    return "flat"


def tracker_instrument_from_index(name: str, index_name: str) -> dict | None:
    snap = nse_index_row(index_name)
    if not snap:
        return None
    hist = nifty_index_history(index_name, days=45)
    spark_labels, spark_closes = [], []
    if len(hist) >= 2:
        seg = hist[: min(14, len(hist))]
        seg = list(reversed(seg))
        spark_closes = [float(x["close"]) for x in seg]
        spark_labels = [str(x.get("date", ""))[:11] for x in seg]
    chg = snap["change_pct"]
    return {
        "name": name,
        "ticker": index_name,
        "currency": "INR",
        "last": snap["last"],
        "prev_close": snap["previous_close"],
        "change_pct": round(chg, 2),
        "change_abs": round(snap["last"] - snap["previous_close"], 2),
        "day_high": round(snap["day_high"], 2),
        "day_low": round(snap["day_low"], 2),
        "sparkline_labels": spark_labels,
        "sparkline_closes": [round(x, 2) for x in spark_closes],
        "direction": _direction_from_pct(chg),
    }


def tracker_instrument_from_equity(display_name: str, symbol: str) -> dict | None:
    snap = nse_equity_row(symbol)
    if not snap:
        return None
    chg = snap["change_pct"]
    sparkline_labels = []
    sparkline_closes = []
    if yf is not None:
        try:
            hist = yf.Ticker(f"{symbol}.NS").history(period="20d")
            if hist is not None and not hist.empty:
                tail = hist.tail(min(12, len(hist)))
                sparkline_closes = [round(float(x), 2) for x in tail["Close"].tolist()]
                sparkline_labels = [
                    (idx.strftime("%d %b") if hasattr(idx, "strftime") else str(idx)[:10])
                    for idx in tail.index
                ]
        except Exception:
            sparkline_labels = []
            sparkline_closes = []
    return {
        "name": display_name,
        "ticker": symbol,
        "currency": "INR",
        "last": snap["last"],
        "prev_close": snap["previous_close"],
        "change_pct": round(chg, 2),
        "change_abs": round(snap["last"] - snap["previous_close"], 2),
        "day_high": snap["day_high"],
        "day_low": snap["day_low"],
        "sparkline_labels": sparkline_labels,
        "sparkline_closes": sparkline_closes,
        "direction": _direction_from_pct(chg),
    }


def tracker_instrument_btc() -> dict | None:
    cg = coingecko_btc_inr()
    if not cg:
        return None
    last = float(cg["last_inr"])
    chg = float(cg["change_pct_24h"])
    prev = last / (1.0 + chg / 100.0) if chg is not None else last
    return {
        "name": "Bitcoin (INR)",
        "ticker": "BTC-INR",
        "currency": "INR",
        "last": round(last, 0),
        "prev_close": round(prev, 0),
        "change_pct": round(chg, 2),
        "change_abs": round(last - prev, 0),
        "day_high": round(last, 0),
        "day_low": round(last, 0),
        "sparkline_labels": [],
        "sparkline_closes": [],
        "direction": _direction_from_pct(chg),
    }


def build_market_tracker_payload() -> dict:
    """Watchlist + two Indian benchmark daily-move series (no Yahoo required)."""
    as_of = datetime.now(timezone.utc).isoformat()
    instruments = []
    for name, idx in (
        ("NIFTY 50", "NIFTY 50"),
        ("NIFTY Bank", "NIFTY BANK"),
        ("NIFTY IT", "NIFTY IT"),
        ("Reliance", "RELIANCE"),
        ("TCS", "TCS"),
        ("HDFC Bank", "HDFCBANK"),
        ("Infosys", "INFY"),
        ("ICICI Bank", "ICICIBANK"),
        ("SBI", "SBIN"),
        ("L&T", "LT"),
        ("ITC", "ITC"),
        ("Bharti Airtel", "BHARTIARTL"),
        ("Axis Bank", "AXISBANK"),
        ("Kotak Bank", "KOTAKBANK"),
    ):
        if idx in ("NIFTY 50", "NIFTY BANK", "NIFTY IT"):
            row = tracker_instrument_from_index(name, idx)
        else:
            row = tracker_instrument_from_equity(name, idx)
        if row:
            instruments.append(row)

    btc = tracker_instrument_btc()
    if btc:
        instruments.append(btc)
    instruments = instruments[:15]

    nifty_hist = nifty_index_history("NIFTY 50", days=55)
    bank_hist = nifty_index_history("NIFTY BANK", days=55)
    n_labels, n_closes = closes_and_labels_from_history(nifty_hist, max_points=45)
    b_labels, b_closes = closes_and_labels_from_history(bank_hist, max_points=45)

    def series_from_closes(labels: list[str], closes: list[float], title: str, ticker: str):
        if len(closes) < 2:
            return {
                "labels": [],
                "changes_pct": [],
                "name": title,
                "ticker": ticker,
                "status": "empty",
            }
        ch_labels = []
        changes = []
        for i in range(1, len(closes)):
            prev_c = closes[i - 1]
            cur = closes[i]
            pct = ((cur - prev_c) / prev_c * 100.0) if prev_c else 0.0
            changes.append(round(pct, 3))
            ch_labels.append(labels[i] if i < len(labels) else "")
        return {
            "labels": ch_labels,
            "changes_pct": changes,
            "name": f"{title} — daily % move",
            "ticker": ticker,
            "status": "ok",
        }

    nifty_moves = series_from_closes(n_labels, n_closes, "NIFTY 50", "NIFTY 50")
    bank_moves = series_from_closes(b_labels, b_closes, "NIFTY Bank", "NIFTY BANK")

    advancers = sum(1 for r in instruments if r.get("direction") == "up")
    decliners = sum(1 for r in instruments if r.get("direction") == "down")

    return {
        "as_of": as_of,
        "source": "nse_india+niftyindices+coin_gecko",
        "status": f"{len(instruments)} symbols · {advancers} up / {decliners} down (vs prior close / 24h crypto)",
        "instruments": instruments,
        "nifty_daily_moves": nifty_moves,
        "sp500_daily_moves": bank_moves,
        "refresh_hint_sec": 120,
        "note": "India indices & stocks: NSE + Nifty Indices (official). Crypto: CoinGecko (indicative). Not for order placement.",
    }


def nifty_line_chart(days: int = 65) -> dict:
    """Line chart: NIFTY 50 daily closes from Nifty Indices."""
    hist = nifty_index_history("NIFTY 50", days=days + 10)
    labels, closes = closes_and_labels_from_history(hist, max_points=days)
    if len(closes) < 4:
        return {
            "labels": [],
            "closes": [],
            "name": "",
            "ticker": "",
            "status": "empty",
            "hint": "Could not load NIFTY history from Nifty Indices.",
        }
    return {
        "labels": labels,
        "closes": [round(c, 2) for c in closes],
        "ticker": "NIFTY 50",
        "name": "NIFTY 50 (India)",
        "status": "ok",
        "source": "niftyindices",
        "hint": "Daily closing values from Nifty Indices (official index compiler).",
    }


def demo_tracker_payload() -> dict:
    """
    Deterministic sample series so charts always render when NSE/Yahoo are unreachable.
    Clearly flagged as demo — not live prices.
    """
    import math

    as_of = datetime.now(timezone.utc).isoformat()
    n = 28
    labels = []
    nifty_pct = []
    bank_pct = []
    for i in range(n):
        labels.append(f"T-{n - i}")
        nifty_pct.append(round(math.sin(i / 3.1) * 0.85 + (i % 4 - 1.5) * 0.12, 3))
        bank_pct.append(round(math.cos(i / 2.8) * 1.05 + (i % 5 - 2) * 0.14, 3))

    base_nifty = 22650.0
    base_bank = 51200.0
    instruments = [
        {
            "name": "NIFTY 50 (demo)",
            "ticker": "DEMO-NIFTY",
            "currency": "INR",
            "last": round(base_nifty + nifty_pct[-1] * 12, 2),
            "prev_close": round(base_nifty, 2),
            "change_pct": round(nifty_pct[-1], 2),
            "change_abs": round(nifty_pct[-1] * 12, 2),
            "day_high": round(base_nifty + 40, 2),
            "day_low": round(base_nifty - 35, 2),
            "sparkline_labels": labels[-8:],
            "sparkline_closes": [round(base_nifty + nifty_pct[j] * 12, 2) for j in range(-8, 0)],
            "direction": "up" if nifty_pct[-1] > 0.08 else ("down" if nifty_pct[-1] < -0.08 else "flat"),
        },
        {
            "name": "NIFTY Bank (demo)",
            "ticker": "DEMO-BANK",
            "currency": "INR",
            "last": round(base_bank + bank_pct[-1] * 25, 2),
            "prev_close": round(base_bank, 2),
            "change_pct": round(bank_pct[-1], 2),
            "change_abs": round(bank_pct[-1] * 25, 2),
            "day_high": round(base_bank + 90, 2),
            "day_low": round(base_bank - 70, 2),
            "sparkline_labels": labels[-8:],
            "sparkline_closes": [round(base_bank + bank_pct[j] * 25, 2) for j in range(-8, 0)],
            "direction": "up" if bank_pct[-1] > 0.08 else ("down" if bank_pct[-1] < -0.08 else "flat"),
        },
        {
            "name": "Reliance (demo)",
            "ticker": "DEMO",
            "currency": "INR",
            "last": 1388.5,
            "prev_close": 1375.0,
            "change_pct": 0.98,
            "change_abs": 13.5,
            "day_high": 1395.0,
            "day_low": 1370.0,
            "sparkline_labels": [],
            "sparkline_closes": [],
            "direction": "up",
        },
    ]

    return {
        "as_of": as_of,
        "source": "demo_offline",
        "demo_mode": True,
        "status": "Demo data — NSE/Yahoo unreachable. Start server with internet; open http://127.0.0.1:5000 (not file://).",
        "instruments": instruments,
        "nifty_daily_moves": {
            "labels": labels,
            "changes_pct": nifty_pct,
            "name": "NIFTY 50 — daily % (demo)",
            "ticker": "DEMO",
            "status": "ok",
        },
        "sp500_daily_moves": {
            "labels": labels,
            "changes_pct": bank_pct,
            "name": "NIFTY Bank — daily % (demo)",
            "ticker": "DEMO",
            "status": "ok",
        },
        "refresh_hint_sec": 120,
        "note": "Illustration only. For real Indian prices use NSE-backed data when the API connects.",
    }


# Curated resources (education — not endorsements). Same data class as NSE-backed apps.
INDIAN_MARKET_LINKS = (
    {
        "name": "Groww — Markets & news",
        "url": "https://groww.in/markets",
        "why": "Daily market mood, movers, and explainers (broker; uses exchange data).",
    },
    {
        "name": "NSE India — market snapshot",
        "url": "https://www.nseindia.com/market-data/analysis",
        "why": "Official exchange statistics, indices, and circulars.",
    },
    {
        "name": "Moneycontrol — Markets",
        "url": "https://www.moneycontrol.com/markets/",
        "why": "Indian business & market news, results calendar, and sector view.",
    },
    {
        "name": "Economic Times — Markets",
        "url": "https://economictimes.indiatimes.com/markets",
        "why": "Macro and India equity headlines through the trading day.",
    },
    {
        "name": "INDmoney — Stocks & insights",
        "url": "https://www.indmoney.com/stocks",
        "why": "Popular India app for stocks & MF; market summaries (read in app/site).",
    },
    {
        "name": "Business Standard — Markets",
        "url": "https://www.business-standard.com/markets",
        "why": "Daily market and corporate news (website; RSS may be blocked on some networks).",
    },
)


def get_daily_market_context() -> dict:
    """
    Short India-focused context line + headline sample + trusted links for 'daily situation'.
    """
    as_of = datetime.now(timezone.utc).isoformat()
    nifty = nse_index_row("NIFTY 50")
    bank = nse_index_row("NIFTY BANK")
    lines = []
    if nifty:
        lines.append(
            f"NIFTY 50 last session: {nifty['last']:,.2f} ({nifty['change_pct']:+.2f}% vs prev close)."
        )
    if bank:
        lines.append(
            f"NIFTY Bank: {bank['last']:,.2f} ({bank['change_pct']:+.2f}% vs prev close)."
        )
    if not lines:
        lines.append(
            "Could not reach NSE live quotes from this network — refresh later or check your connection."
        )
    return {
        "as_of": as_of,
        "summary_lines": lines,
        "links": list(INDIAN_MARKET_LINKS),
        "data_note": "Quotes from NSE public APIs when reachable. Apps like Groww show the same underlying exchange prices.",
    }
