"""
investment_engine.py
Personalized AI-Based Investment Advisor - Rule-Based Engine
Covers: Stocks, Mutual Funds, SIP, FD, PPF, NPS, Gold, Real Estate, Bonds, ELSS
"""

import csv
import html
import io
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

try:
    import yfinance as yf
except Exception:  # pragma: no cover - optional dependency at runtime
    yf = None

try:
    from indian_market_data import (
        build_market_tracker_payload,
        demo_tracker_payload,
        get_daily_market_context,
        nifty_line_chart,
        snapshot_items_india,
    )
except Exception as _imd_err:  # pragma: no cover
    import logging

    logging.getLogger(__name__).warning("indian_market_data unavailable: %s", _imd_err)
    build_market_tracker_payload = None
    demo_tracker_payload = None
    nifty_line_chart = None
    snapshot_items_india = None
    get_daily_market_context = None

_RSS_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 WealthMindEducational/1.0"
)
_RSS_FEEDS = (
    ("Livemint · Markets", "https://www.livemint.com/rss/markets"),
    ("Investing.com India · Indices", "https://in.investing.com/rss/stock_Indices.rss"),
    ("Investing.com India · Headlines", "https://in.investing.com/rss/news_285.rss"),
    ("Business Standard · Markets (if reachable)", "https://www.business-standard.com/rss/markets-106.rss"),
    ("Economic Times · Markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Economic Times · Stocks", "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms"),
    ("Moneycontrol · Business", "https://www.moneycontrol.com/rss/business.xml"),
    ("Yahoo Finance · S&P 500", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US"),
    ("Yahoo Finance · NIFTY", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5ENSEI&region=IN&lang=en-IN"),
)

# Tickers used for India + global context (Yahoo symbols)
_NEWS_TICKERS = ("^NSEI", "RELIANCE.NS", "INFY.NS", "HDFCBANK.NS", "TCS.NS")
_CHART_INDEX = "^NSEI"

# Live tracker watchlist: (display name, Yahoo ticker, currency code for UI)
_TRACKER_WATCHLIST = (
    ("NIFTY 50", "^NSEI", "INR"),
    ("NIFTY Bank", "^NSEBANK", "INR"),
    ("Reliance", "RELIANCE.NS", "INR"),
    ("TCS", "TCS.NS", "INR"),
    ("HDFC Bank", "HDFCBANK.NS", "INR"),
    ("INFY", "INFY.NS", "INR"),
    ("ICICI Bank", "ICICIBANK.NS", "INR"),
    ("SBI", "SBIN.NS", "INR"),
    ("Bharti Airtel", "BHARTIARTL.NS", "INR"),
    ("L&T", "LT.NS", "INR"),
    ("ITC", "ITC.NS", "INR"),
    ("Adani Enterprises", "ADANIENT.NS", "INR"),
    ("S&P 500", "^GSPC", "USD"),
    ("Nasdaq 100", "^NDX", "USD"),
    ("USD / INR", "INR=X", "FX"),
    ("Gold ETF (GLD)", "GLD", "USD"),
    ("Bitcoin", "BTC-USD", "USD"),
)


class InvestmentAdvisor:

    INSTRUMENTS = {
        "equity_stocks": {
            "name": "Equity Stocks",
            "category": "High Risk",
            "expected_return": "12–18% p.a.",
            "liquidity": "High",
            "min_investment": "₹500 (1 share)",
            "tax": "STCG 15%, LTCG 10% above ₹1L",
            "icon": "📈",
            "description": "Direct ownership in companies. Best for aggressive investors with 5+ year horizon.",
            "suitable_for": ["aggressive"],
            "ideal_horizon": ["long", "very_long"]
        },
        "mutual_funds_equity": {
            "name": "Equity Mutual Funds",
            "category": "Medium-High Risk",
            "expected_return": "10–15% p.a.",
            "liquidity": "High",
            "min_investment": "₹500 SIP",
            "tax": "STCG 15%, LTCG 10% above ₹1L",
            "icon": "💹",
            "description": "Professionally managed diversified equity portfolio. Great for moderate to aggressive.",
            "suitable_for": ["moderate", "aggressive"],
            "ideal_horizon": ["medium", "long", "very_long"]
        },
        "sip": {
            "name": "SIP (Systematic Investment Plan)",
            "category": "Medium Risk",
            "expected_return": "10–14% p.a.",
            "liquidity": "High",
            "min_investment": "₹100/month",
            "tax": "Based on underlying fund type",
            "icon": "🔄",
            "description": "Disciplined monthly investment in mutual funds. Rupee-cost averaging reduces risk.",
            "suitable_for": ["conservative", "moderate", "aggressive"],
            "ideal_horizon": ["medium", "long", "very_long"]
        },
        "elss": {
            "name": "ELSS (Tax-Saving Mutual Funds)",
            "category": "Medium-High Risk",
            "expected_return": "12–15% p.a.",
            "liquidity": "Low (3-year lock-in)",
            "min_investment": "₹500",
            "tax": "Section 80C deduction up to ₹1.5L; LTCG 10% above ₹1L",
            "icon": "🧾",
            "description": "Equity funds with 3-year lock-in. Best tax-saving + growth combo under Sec 80C.",
            "suitable_for": ["moderate", "aggressive"],
            "ideal_horizon": ["medium", "long"]
        },
        "fd": {
            "name": "Fixed Deposit (FD)",
            "category": "Low Risk",
            "expected_return": "6.5–8.5% p.a.",
            "liquidity": "Medium (premature withdrawal penalty)",
            "min_investment": "₹1,000",
            "tax": "Interest taxable as per slab",
            "icon": "🏦",
            "description": "Guaranteed returns. Safe parking for capital. Ideal for conservative risk-takers.",
            "suitable_for": ["conservative"],
            "ideal_horizon": ["short", "medium"]
        },
        "ppf": {
            "name": "PPF (Public Provident Fund)",
            "category": "Low Risk",
            "expected_return": "7.1% p.a. (govt. revised quarterly)",
            "liquidity": "Low (15-year lock-in, partial after 7 yrs)",
            "min_investment": "₹500/year",
            "tax": "EEE (Exempt-Exempt-Exempt) - completely tax-free",
            "icon": "🏛️",
            "description": "Government-backed, completely tax-free returns. Best long-term safe wealth creation.",
            "suitable_for": ["conservative", "moderate"],
            "ideal_horizon": ["very_long"]
        },
        "nps": {
            "name": "NPS (National Pension System)",
            "category": "Low-Medium Risk",
            "expected_return": "8–12% p.a.",
            "liquidity": "Very Low (till retirement)",
            "min_investment": "₹500/year",
            "tax": "Additional ₹50K deduction under 80CCD(1B)",
            "icon": "🌅",
            "description": "Government pension scheme. Best for retirement planning with tax benefits.",
            "suitable_for": ["conservative", "moderate"],
            "ideal_horizon": ["very_long"]
        },
        "gold": {
            "name": "Gold / Sovereign Gold Bonds",
            "category": "Medium Risk",
            "expected_return": "8–10% p.a. (SGB adds 2.5% interest)",
            "liquidity": "Medium",
            "min_investment": "₹100 (Digital Gold)",
            "tax": "SGB: Tax-free on maturity; Physical: LTCG after 3 years",
            "icon": "🥇",
            "description": "Hedge against inflation and market crashes. SGBs are best form (no storage risk).",
            "suitable_for": ["conservative", "moderate", "aggressive"],
            "ideal_horizon": ["medium", "long"]
        },
        "debt_funds": {
            "name": "Debt Mutual Funds",
            "category": "Low-Medium Risk",
            "expected_return": "6–9% p.a.",
            "liquidity": "High",
            "min_investment": "₹500",
            "tax": "As per income slab (post-2023 change)",
            "icon": "📊",
            "description": "Invests in bonds/govt securities. Better than FD for short to medium horizon with liquidity.",
            "suitable_for": ["conservative", "moderate"],
            "ideal_horizon": ["short", "medium"]
        },
        "real_estate": {
            "name": "Real Estate / REITs",
            "category": "Medium-High Risk",
            "expected_return": "8–12% p.a.",
            "liquidity": "Low (direct); High (REITs)",
            "min_investment": "₹300 (REITs) / ₹20L+ (direct)",
            "tax": "LTCG 20% with indexation (direct)",
            "icon": "🏘️",
            "description": "Tangible asset with appreciation + rental income. REITs give real estate exposure affordably.",
            "suitable_for": ["moderate", "aggressive"],
            "ideal_horizon": ["long", "very_long"]
        },
        "rd": {
            "name": "Recurring Deposit (RD)",
            "category": "Low Risk",
            "expected_return": "5.5–7.5% p.a.",
            "liquidity": "Low (till maturity)",
            "min_investment": "₹100/month",
            "tax": "Interest taxable as per slab",
            "icon": "💰",
            "description": "Monthly savings with fixed return. Great for building emergency funds without market exposure.",
            "suitable_for": ["conservative"],
            "ideal_horizon": ["short", "medium"]
        }
    }

    GOAL_WEIGHTS = {
        "Wealth Building":     {"equity_stocks": 4, "mutual_funds_equity": 4, "sip": 3, "gold": 2, "real_estate": 2},
        "Retirement Planning": {"ppf": 5, "nps": 5, "mutual_funds_equity": 3, "sip": 3, "gold": 2},
        "Child Education":     {"sip": 5, "elss": 4, "ppf": 3, "mutual_funds_equity": 3},
        "Emergency Fund":      {"fd": 5, "rd": 4, "debt_funds": 4, "gold": 2},
        "Home Purchase":       {"fd": 3, "sip": 4, "mutual_funds_equity": 3, "rd": 2},
        "Tax Saving":          {"elss": 5, "ppf": 4, "nps": 4, "fd": 2},
        "Regular Income":      {"fd": 4, "debt_funds": 4, "real_estate": 3, "gold": 2}
    }

    def _get_horizon_key(self, horizon_str):
        h = horizon_str.lower()
        if "< 1" in h or "short" in h:
            return "short"
        elif "1-5" in h or "1–5" in h or "medium" in h:
            return "medium"
        elif "5-15" in h or "5–15" in h or "long" in h:
            return "long"
        else:
            return "very_long"

    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _safe_int(self, value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _score_instruments(self, profile):
        risk = profile["risk_tolerance"].lower()
        horizon = self._get_horizon_key(profile["horizon"])
        goal = profile["goal"]
        age = self._safe_int(profile["age"])
        income = self._safe_float(profile["income"])
        savings = self._safe_float(profile["savings"])
        monthly_expenses = self._safe_float(profile.get("monthly_expenses"))
        debt = self._safe_float(profile.get("debt"))
        is_student = str(profile.get("is_student", "No")).lower() == "yes"
        dependents = self._safe_int(profile.get("dependents"))
        experience = str(profile.get("investment_experience", "Beginner")).lower()

        savings_months = savings / monthly_expenses if monthly_expenses > 0 else 0
        debt_to_income = debt / income if income > 0 else 0

        scores = {}
        goal_weights = self.GOAL_WEIGHTS.get(goal, {})

        for key, inst in self.INSTRUMENTS.items():
            score = 0

            # Risk match
            if risk in inst["suitable_for"]:
                score += 10
            elif risk == "aggressive" and "moderate" in inst["suitable_for"]:
                score += 5
            elif risk == "conservative" and "moderate" in inst["suitable_for"]:
                score += 5

            # Horizon match
            if horizon in inst["ideal_horizon"]:
                score += 8

            # Goal weight
            score += goal_weights.get(key, 0) * 2

            # Age-based adjustments
            if age < 30:
                if key in ["equity_stocks", "mutual_funds_equity", "sip", "elss"]:
                    score += 5
            elif age > 55:
                if key in ["ppf", "nps", "fd", "debt_funds", "rd"]:
                    score += 5
                if key in ["equity_stocks"]:
                    score -= 3

            # Low savings adjustments
            if savings < 50000:
                if key in ["real_estate"]:
                    score -= 5
                if key in ["sip", "rd", "fd"]:
                    score += 3

            # Emergency buffer and debt adjustments
            if savings_months < 3:
                if key in ["fd", "rd", "debt_funds"]:
                    score += 4
                if key in ["equity_stocks", "real_estate"]:
                    score -= 3
            elif savings_months > 9 and key in ["mutual_funds_equity", "sip", "equity_stocks"]:
                score += 2

            if debt_to_income > 0.5:
                if key in ["fd", "rd", "debt_funds"]:
                    score += 3
                if key in ["equity_stocks", "real_estate"]:
                    score -= 4

            # Student and dependents adjustments
            if is_student:
                if key in ["sip", "rd", "debt_funds"]:
                    score += 4
                if key in ["real_estate", "equity_stocks"]:
                    score -= 4

            if dependents > 0:
                if key in ["fd", "ppf", "debt_funds", "sip"]:
                    score += 2
                if dependents >= 2 and key in ["equity_stocks"]:
                    score -= 2

            # Experience adjustments
            if experience == "beginner":
                if key in ["sip", "mutual_funds_equity", "fd"]:
                    score += 2
                if key in ["equity_stocks"]:
                    score -= 2
            elif experience == "advanced" and key in ["equity_stocks", "real_estate"]:
                score += 2

            scores[key] = max(score, 0)

        return scores

    def _allocate_portfolio(self, scores, risk):
        sorted_inst = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top = sorted_inst[:5]

        total_score = sum(s for _, s in top)
        if total_score == 0:
            return []

        allocation = []
        for key, score in top:
            pct = round((score / total_score) * 100)
            if pct > 0:
                inst = self.INSTRUMENTS[key].copy()
                inst["key"] = key
                inst["allocation_percent"] = pct
                allocation.append(inst)

        # Fix rounding to 100%
        diff = 100 - sum(a["allocation_percent"] for a in allocation)
        if allocation:
            allocation[0]["allocation_percent"] += diff

        return allocation

    def _get_insights(self, profile, allocation, market_snapshot=None):
        age = self._safe_int(profile["age"])
        income = self._safe_float(profile["income"])
        debt = self._safe_float(profile.get("debt"))
        monthly_expenses = self._safe_float(profile.get("monthly_expenses"))
        savings = self._safe_float(profile.get("savings"))
        is_student = str(profile.get("is_student", "No")).lower() == "yes"
        dependents = self._safe_int(profile.get("dependents"))
        experience = str(profile.get("investment_experience", "Beginner"))
        risk = profile["risk_tolerance"].lower()
        goal = profile["goal"]
        horizon_key = self._get_horizon_key(profile.get("horizon", ""))
        savings_months = savings / monthly_expenses if monthly_expenses > 0 else 0

        monthly_suggest, surplus_note = self._realistic_monthly_investment(profile)

        insights = []

        # Age-based (life-cycle) — common advisory framing
        equity_glide = max(0, min(100, 100 - age))
        insights.append(
            f"📐 Rule-of-thumb equity share by age: many planners use “100 − age” (~{equity_glide}% equity idea) — adjust for your risk score and goals, not blindly."
        )

        if age < 30:
            insights.append("🚀 Young earner: long horizon favors disciplined equity SIPs; still keep emergency cash before maxing risk assets.")
        elif age < 45:
            insights.append("⚡ Mid-career: balance growth (diversified equity) with debt/PPF/NPS for goals; increase insurance if dependents exist.")
        elif age < 58:
            insights.append("🛡️ Pre-retirement: gradually reduce single-stock concentration; add stable income assets as goal date nears.")
        else:
            insights.append("🏛️ Near/retirement: prioritize capital preservation, predictable cash flows, and liquidity; keep equity only within comfort.")

        if risk == "conservative":
            insights.append("🔒 Conservative: FD, short debt, PPF-style safety first; equity only with long horizon and small steps (e.g. hybrid funds).")
        elif risk == "moderate":
            insights.append("⚖️ Moderate: core equity index/hybrid + debt ladder matches many real portfolios for 5–10 year goals.")
        else:
            insights.append("📊 Aggressive: equity-heavy can work with 7+ year horizon; avoid leverage; rebalance yearly.")

        if horizon_key == "short":
            insights.append("⏱️ Short horizon (under 1 year): avoid volatile equity for the principal; use liquid/debt options — aligns with typical suitability norms.")
        elif horizon_key == "medium":
            insights.append("📆 Medium term (1–5 yrs): blend debt + moderate equity; lumpsum timing risk is real — SIP/STP often preferred in practice.")
        else:
            insights.append("📈 Long horizon: equity compounding matters; stay through cycles if goals are 5+ years away.")

        if goal == "Tax Saving":
            insights.append("💡 Tax: ELSS (80C), PPF, NPS (extra 80CCD) are common combos — verify limits and lock-ins each financial year.")
        elif goal == "Retirement Planning":
            insights.append("🌅 Retirement: NPS + EPF/PPF + equity MF is a typical three-layer structure in India; start early for contribution years.")
        elif goal == "Emergency Fund":
            insights.append("🚨 Emergency: 6 months expenses in liquid/sweep FD or money-market — do not chase stock returns on this bucket.")
        elif goal == "Child Education":
            insights.append("🎓 Education goal: separate SIP, increase amount with inflation assumptions; avoid equity for fees due within 2–3 years.")
        elif goal == "Home Purchase":
            insights.append("🏠 Home down-payment: use debt funds/FD ladder for planned purchase date; equity only if horizon is comfortably long.")

        if is_student:
            insights.append("🎒 Student: small recurring SIP + skill-building; avoid high leverage; build credit hygiene.")

        if debt > income * 0.5:
            insights.append("📉 High debt vs income: real cases often pay costly loans first; investing while paying 18–36% card interest rarely wins.")

        if savings_months < 3:
            insights.append("🧯 Under 3 months buffer: most planners pause aggressive investing until basics are covered.")

        if dependents > 0:
            insights.append("👨‍👩‍👧 Dependents: term life + health cover before chasing returns; allocation should reflect responsibility.")

        insights.append(f"🧠 Experience ({experience}): simpler products until you can explain each holding; avoid complexity bias.")

        if income > 100000:
            insights.append(f"💼 Higher income (₹{income:,.0f}/mo): diversification (REITs, gold hedge) is common — not concentration in one stock.")

        sent = (market_snapshot or {}).get("overall_sentiment")
        if sent == "Cautious":
            insights.append("📰 Recent broad market tone looks weak — if investing lump sums, consider splitting over weeks (STP), not panic selling.")
        elif sent == "Positive":
            insights.append("📰 Markets recently firm — still invest per plan; euphoria is when discipline matters most.")

        insights.append(f"💰 Suggested monthly invest: ₹{monthly_suggest:,.0f}. {surplus_note}")

        return insights

    def _market_sentiment_label(self, daily_change_pct):
        if daily_change_pct is None:
            return "Unavailable"
        if daily_change_pct >= 0.8:
            return "Positive"
        if daily_change_pct <= -0.8:
            return "Cautious"
        return "Neutral"

    def _parse_rss_items_into(self, xml_bytes, publisher_name, max_add, seen_titles, out_list):
        """Append up to max_add unique items from RSS/Atom XML into out_list."""
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError:
            return
        for elem in root.iter():
            if not (elem.tag.endswith("item") or elem.tag == "item"):
                continue
            if max_add <= 0:
                break
            title, link, published = None, None, ""
            for ch in elem:
                tag = ch.tag.split("}")[-1].lower()
                if tag == "title" and ch.text:
                    title = html.unescape(ch.text.strip())
                elif tag == "link" and ch.text:
                    link = ch.text.strip()
                elif tag == "guid" and not link and ch.text and ch.text.strip().startswith("http"):
                    link = ch.text.strip()
                elif tag in ("pubdate", "published", "updated", "date") and ch.text:
                    published = ch.text.strip()
            if not title or not link:
                continue
            key = title.lower()[:240]
            if key in seen_titles:
                continue
            seen_titles.add(key)
            ts = 0.0
            if published:
                try:
                    dt = parsedate_to_datetime(published)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    ts = dt.timestamp()
                except Exception:
                    ts = 0.0
            out_list.append(
                {
                    "title": title[:280],
                    "link": link,
                    "publisher": publisher_name,
                    "published": published,
                    "published_ts": ts,
                    "related_symbol": "",
                }
            )
            max_add -= 1

    def _fetch_rss_market_news(self, limit=14):
        """Fallback headlines from public RSS feeds (ET, Moneycontrol, Yahoo RSS)."""
        out = []
        seen = set()
        per_source = 2
        for pub, url in _RSS_FEEDS:
            if len(out) >= limit:
                break
            need = min(per_source, max(0, limit - len(out)))
            try:
                req = urllib.request.Request(url, headers={"User-Agent": _RSS_USER_AGENT})
                with urllib.request.urlopen(req, timeout=22) as resp:
                    data = resp.read()
            except (urllib.error.URLError, OSError, TimeoutError, ValueError):
                continue
            self._parse_rss_items_into(data, pub, need, seen, out)
        out.sort(key=lambda x: x.get("published_ts", 0), reverse=True)
        return out[:limit]

    def _fetch_stock_news(self, limit=12):
        """Yahoo (yfinance) first; RSS web feeds fill gaps so news usually shows."""
        items = []
        seen_titles = set()
        sources = []

        if yf is not None:
            for sym in _NEWS_TICKERS:
                if len(items) >= limit:
                    break
                try:
                    t = yf.Ticker(sym)
                    raw = getattr(t, "news", None) or []
                    for n in raw:
                        title = (n.get("title") or "").strip()
                        if not title:
                            continue
                        key = title.lower()[:240]
                        if key in seen_titles:
                            continue
                        seen_titles.add(key)
                        ts = n.get("providerPublishTime")
                        if isinstance(ts, (int, float)):
                            pub = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                        else:
                            pub = ""
                        items.append(
                            {
                                "title": title[:280],
                                "publisher": n.get("publisher") or "Yahoo Finance",
                                "link": n.get("link") or "",
                                "related_symbol": sym,
                                "published": pub,
                            }
                        )
                        if len(items) >= limit:
                            break
                except Exception:
                    continue
            if items:
                sources.append("yahoo")

        if len(items) < limit:
            rss_items = self._fetch_rss_market_news(limit - len(items) + 4)
            for r in rss_items:
                if len(items) >= limit:
                    break
                key = r["title"].lower()[:240]
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                items.append(r)
            if rss_items:
                sources.append("rss")

        if not items:
            items = self._demo_india_news_fallback()[:limit]
            sources = ["demo_education"]

        # Keep the feed diverse across trusted publishers (round-robin by source).
        by_pub = {}
        for it in items:
            pub = it.get("publisher") or "Unknown"
            by_pub.setdefault(pub, []).append(it)
        for pub in by_pub:
            by_pub[pub].sort(key=lambda x: x.get("published_ts", 0), reverse=True)
        diverse = []
        pubs = list(by_pub.keys())
        while len(diverse) < limit and pubs:
            next_pubs = []
            for pub in pubs:
                bucket = by_pub.get(pub) or []
                if bucket:
                    diverse.append(bucket.pop(0))
                if bucket and len(diverse) < limit:
                    next_pubs.append(pub)
                if len(diverse) >= limit:
                    break
            pubs = next_pubs

        src = "+".join(sources) if sources else "none"
        status = f"{len(diverse)} headline(s) from {src}." if diverse else "No headlines (check internet / firewall)."
        for it in diverse:
            it.pop("published_ts", None)
        return {"items": diverse[:limit], "source": src, "status": status}

    def _build_guidance_plan(self, profile):
        horizon = self._get_horizon_key(profile.get("horizon", ""))
        risk = str(profile.get("risk_tolerance", "Moderate"))
        goal = str(profile.get("goal", "Wealth Building"))
        validity_by_horizon = {"short": 30, "medium": 90, "long": 180, "very_long": 365}
        validity_days = validity_by_horizon.get(horizon, 90)
        review_on = datetime.now(timezone.utc) + timedelta(days=validity_days)
        title = f"{risk} {goal} Guidance Plan"
        if risk.lower() == "conservative":
            guidance = "Focus on capital protection first: emergency buffer + debt reduction + low-volatility allocation."
        elif risk.lower() == "aggressive":
            guidance = "Growth-focused allocation is suitable only if you can tolerate drawdowns and stay invested through cycles."
        else:
            guidance = "Balanced allocation: mix growth and stability; rebalance if your income, debt, or goal changes."

        if horizon == "short":
            guidance += " Because horizon is short-term, avoid heavy equity concentration."
        elif horizon in ("long", "very_long"):
            guidance += " Long horizon supports gradual equity compounding with periodic rebalancing."
        return {
            "title": title,
            "guidance": guidance,
            "validity_days": validity_days,
            "review_on": review_on.strftime("%d %b %Y"),
            "renewal_note": "Create a new plan on or before review date, or earlier if life events change your profile.",
        }

    def _demo_india_news_fallback(self):
        """Static pointers when RSS/Yahoo are unreachable — not live reporting."""
        return [
            {
                "title": "NSE India — official market data, indices, and circulars",
                "publisher": "Link · NSE",
                "link": "https://www.nseindia.com/",
                "related_symbol": "",
                "published": "",
            },
            {
                "title": "Groww — markets section (movers, news; broker)",
                "publisher": "Link · Groww",
                "link": "https://groww.in/markets",
                "related_symbol": "",
                "published": "",
            },
            {
                "title": "INDmoney — stocks & market insights (broker)",
                "publisher": "Link · INDmoney",
                "link": "https://www.indmoney.com/stocks",
                "related_symbol": "",
                "published": "",
            },
            {
                "title": "Business Standard — Markets news",
                "publisher": "Link · Business Standard",
                "link": "https://www.business-standard.com/markets",
                "related_symbol": "",
                "published": "",
            },
            {
                "title": "Livemint — Markets RSS (used when reachable)",
                "publisher": "Link · Mint",
                "link": "https://www.livemint.com/market",
                "related_symbol": "",
                "published": "",
            },
        ]

    def _fetch_index_chart_series(self, ticker=_CHART_INDEX, days=60):
        """Daily closes for line chart (real historical prices)."""
        if yf is None:
            return {"labels": [], "closes": [], "name": "NIFTY 50", "status": "unavailable"}
        try:
            hist = yf.Ticker(ticker).history(period=f"{days}d")
            if hist is None or hist.empty:
                return {"labels": [], "closes": [], "name": "NIFTY 50", "status": "empty"}
            labels = []
            for idx in hist.index:
                try:
                    labels.append(idx.strftime("%d %b"))
                except Exception:
                    labels.append(str(idx)[:10])
            closes = [round(float(x), 2) for x in hist["Close"].tolist()]
            return {
                "labels": labels,
                "closes": closes,
                "ticker": ticker,
                "name": "NIFTY 50 (proxy)",
                "status": "ok",
            }
        except Exception:
            return {"labels": [], "closes": [], "name": "NIFTY 50", "status": "error"}

    def _market_chart_best_effort(self, days=60):
        """
        Prefer NIFTY 50 daily closes from Nifty Indices (official). Then Yahoo / Stooq fallbacks.
        """
        if nifty_line_chart is not None:
            try:
                mc = nifty_line_chart(days=days)
                if mc.get("closes") and len(mc["closes"]) > 3:
                    return mc
            except Exception:
                pass

        # Try several Yahoo symbols — NIFTY often empty in some regions; US ETFs usually work.
        if yf is None:
            stooq = self._fetch_stooq_closes_chart(("spy.us", "S&P 500 proxy — SPY"), days)
            if stooq:
                return stooq
            return {
                "labels": [],
                "closes": [],
                "name": "",
                "ticker": "",
                "status": "unavailable",
                "hint": "Install yfinance for Yahoo data; Stooq backup also failed or is blocked.",
            }
        candidates = (
            ("^NSEI", "NIFTY 50 (India)"),
            ("^GSPC", "S&P 500 (US)"),
            ("SPY", "S&P 500 ETF — SPY"),
            ("QQQ", "Nasdaq 100 ETF — QQQ"),
            ("INDA", "India ETF — INDA (US-listed)"),
        )
        last_err = "no_data"
        for ticker, display_name in candidates:
            s = self._fetch_index_chart_series(ticker, days=days)
            closes = s.get("closes") or []
            if len(closes) > 3:
                s["name"] = display_name
                s["status"] = "ok"
                s["hint"] = f"Showing {display_name} — Yahoo symbol {ticker}."
                return s
            last_err = s.get("status") or "empty"

        stooq = self._fetch_stooq_closes_chart(("spy.us", "S&P 500 proxy — SPY"), days)
        if stooq:
            return stooq
        stooq2 = self._fetch_stooq_closes_chart(("qqq.us", "Nasdaq 100 proxy — QQQ"), days)
        if stooq2:
            return stooq2

        return {
            "labels": [],
            "closes": [],
            "name": "",
            "ticker": "",
            "status": last_err,
            "hint": "Could not load Yahoo or Stooq history. Check internet / firewall. Use Live Market Tracker or try later.",
        }

    def _fetch_stooq_closes_chart(self, symbol_name_pair, days=60):
        """Free daily CSV from Stooq — backup when Yahoo is empty or blocked."""
        sym, title = symbol_name_pair
        url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _RSS_USER_AGENT})
            with urllib.request.urlopen(req, timeout=14) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError, TimeoutError, ValueError):
            return None
        if not raw or len(raw) < 30:
            return None
        try:
            reader = csv.DictReader(io.StringIO(raw))
            rows = list(reader)
        except Exception:
            return None
        if not rows:
            return None
        rows = rows[-min(days, len(rows)) :]
        labels = []
        closes = []
        for row in rows:
            dt = (row.get("Date") or "").strip()
            cl = row.get("Close")
            if not cl or cl == "0" or cl == "NaN":
                continue
            try:
                v = round(float(cl), 4)
            except ValueError:
                continue
            closes.append(v)
            labels.append(dt[5:].replace("-", " ") if len(dt) >= 10 else dt)
        if len(closes) < 4:
            return None
        return {
            "labels": labels,
            "closes": closes,
            "ticker": sym,
            "name": title,
            "status": "ok",
            "source": "stooq",
            "hint": f"Daily closes from Stooq ({sym}) — backup feed when Yahoo is unavailable.",
        }

    def get_public_news(self):
        return self._fetch_stock_news(limit=14)

    def get_market_chart_data(self):
        return self._market_chart_best_effort(60)

    def _benchmark_daily_pct_series(self, ticker, days=40):
        """
        Per-trading-day % change vs previous close — same idea as broker “daily change” columns.
        Used for green/red bar charts (real historical closes).
        """
        if yf is None:
            return {"labels": [], "changes_pct": [], "name": "", "ticker": ticker, "status": "unavailable"}
        try:
            hist = yf.Ticker(ticker).history(period=f"{days}d")
            if hist is None or len(hist) < 2:
                return {"labels": [], "changes_pct": [], "name": "", "ticker": ticker, "status": "empty"}
            labels = []
            changes = []
            closes = hist["Close"].tolist()
            for i in range(1, len(closes)):
                prev_c = float(closes[i - 1])
                cur = float(closes[i])
                pct = ((cur - prev_c) / prev_c * 100.0) if prev_c else 0.0
                try:
                    labels.append(hist.index[i].strftime("%d %b"))
                except Exception:
                    labels.append(str(hist.index[i])[:10])
                changes.append(round(pct, 3))
            pretty = {"^NSEI": "NIFTY 50", "^GSPC": "S&P 500"}.get(ticker, ticker)
            return {
                "labels": labels,
                "changes_pct": changes,
                "name": f"{pretty} — daily % move",
                "ticker": ticker,
                "status": "ok",
            }
        except Exception:
            return {"labels": [], "changes_pct": [], "name": "", "ticker": ticker, "status": "error"}

    def _tracker_instrument_row(self, name, ticker, currency):
        """One watchlist row: last session move + intraday range from latest bar + sparkline."""
        if yf is None:
            return None
        try:
            hist = yf.Ticker(ticker).history(period="35d")
            if hist is None or hist.empty or len(hist) < 2:
                return None
            last = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            change_pct = ((last - prev) / prev * 100.0) if prev else 0.0
            change_abs = last - prev
            day_high = float(hist["High"].iloc[-1])
            day_low = float(hist["Low"].iloc[-1])
            tail = hist.tail(min(12, len(hist)))
            spark_labels = []
            for x in tail.index:
                try:
                    spark_labels.append(x.strftime("%d %b"))
                except Exception:
                    spark_labels.append(str(x)[:10])
            spark_closes = [round(float(x), 4) for x in tail["Close"].tolist()]
            if change_pct > 0.08:
                direction = "up"
            elif change_pct < -0.08:
                direction = "down"
            else:
                direction = "flat"
            return {
                "name": name,
                "ticker": ticker,
                "currency": currency,
                "last": round(last, 4 if currency == "FX" else 2),
                "prev_close": round(prev, 4 if currency == "FX" else 2),
                "change_pct": round(change_pct, 2),
                "change_abs": round(change_abs, 4 if currency == "FX" else 2),
                "day_high": round(day_high, 4 if currency == "FX" else 2),
                "day_low": round(day_low, 4 if currency == "FX" else 2),
                "sparkline_labels": spark_labels,
                "sparkline_closes": spark_closes,
                "direction": direction,
            }
        except Exception:
            return None

    def get_live_market_tracker(self):
        """
        Watchlist + two daily % bar series. Primary: NSE + Nifty Indices (India). Fallback: Yahoo, then demo.
        """
        as_of = datetime.now(timezone.utc).isoformat()

        def _moves_ok(moves):
            if not moves or not isinstance(moves, dict):
                return False
            return len(moves.get("changes_pct") or []) > 2

        if build_market_tracker_payload is not None:
            try:
                payload = build_market_tracker_payload()
                ins = payload.get("instruments") or []
                if ins and _moves_ok(payload.get("nifty_daily_moves")):
                    return payload
            except Exception:
                pass

        instruments = []
        nifty_moves = {"labels": [], "changes_pct": [], "status": "empty"}
        spx_moves = {"labels": [], "changes_pct": [], "status": "empty"}

        if yf is not None:
            for name, ticker, currency in _TRACKER_WATCHLIST:
                row = self._tracker_instrument_row(name, ticker, currency)
                if row:
                    instruments.append(row)

            nifty_moves = self._benchmark_daily_pct_series("^NSEI", 40)
            spx_moves = self._benchmark_daily_pct_series("^GSPC", 40)

        advancers = sum(1 for r in instruments if r.get("direction") == "up")
        decliners = sum(1 for r in instruments if r.get("direction") == "down")

        live_ok = len(instruments) > 0 and _moves_ok(nifty_moves)
        if live_ok:
            return {
                "as_of": as_of,
                "source": "yahoo_finance",
                "status": f"{len(instruments)} symbols · {advancers} up / {decliners} down (latest session vs prior close)",
                "instruments": instruments,
                "nifty_daily_moves": nifty_moves,
                "sp500_daily_moves": spx_moves,
                "refresh_hint_sec": 120,
                "note": "End-of-day style data from Yahoo Finance. Use your broker for live LTP and order execution.",
            }

        if demo_tracker_payload is not None:
            return demo_tracker_payload()

        return {
            "as_of": as_of,
            "source": "unavailable",
            "status": "Market data unavailable. pip install -r requirements.txt and run python app.py",
            "instruments": [],
            "nifty_daily_moves": {},
            "sp500_daily_moves": {},
            "refresh_hint_sec": 120,
        }

    def _realistic_monthly_investment(self, profile):
        """
        Surplus-based SIP: common practice is invest only after essentials + emergency buffer plan.
        Caps at ~20% of gross income; floor ₹500 if surplus allows.
        """
        income = self._safe_float(profile.get("income"))
        monthly_expenses = self._safe_float(profile.get("monthly_expenses"))
        debt = self._safe_float(profile.get("debt"))
        savings = self._safe_float(profile.get("savings"))
        monthly_exp = monthly_expenses if monthly_expenses > 0 else income * 0.5

        # Rough EMI assumption: ~1% of outstanding debt / month on average (varies widely)
        implied_emi = min(debt * 0.01, income * 0.45) if debt > 0 else 0
        surplus = income - monthly_exp - implied_emi
        rule_20_cap = income * 0.20
        if surplus <= 0:
            return 0, "Surplus is tight — focus on expenses, EMIs, and emergency fund before investing."
        suggested = min(surplus * 0.5, rule_20_cap)
        suggested = max(round(suggested), 0)
        if suggested < 500 and surplus > 2000:
            suggested = min(500, int(surplus * 0.3))
        note = "Based on income minus expenses and a rough debt service estimate; adjust for your actual EMI."
        return suggested, note

    def _financial_health_detail(self, profile):
        """
        0–100 heuristic: emergency cover, debt, surplus — not a credit score.
        Returns score + breakdown so the UI can show why it changed when inputs change.
        """
        income = self._safe_float(profile.get("income"))
        monthly_expenses = self._safe_float(profile.get("monthly_expenses"))
        debt = self._safe_float(profile.get("debt"))
        savings = self._safe_float(profile.get("savings"))
        dependents = self._safe_int(profile.get("dependents"))
        score = 45
        breakdown = []

        months = savings / monthly_expenses if monthly_expenses > 0 else 0
        if months < 1:
            emergency_delta = -14
        elif months < 3:
            emergency_delta = -6
        elif months < 6:
            emergency_delta = 6
        elif months < 10:
            emergency_delta = 14
        else:
            emergency_delta = 18
        score += emergency_delta
        breakdown.append(
            {
                "label": "Emergency buffer",
                "delta": f"{emergency_delta:+d}",
                "note": f"~{months:.1f} months of expenses saved. 6+ months is typically considered stable.",
            }
        )

        dti = (debt / income) if income > 0 else 0
        if dti <= 0.2:
            debt_delta = 16
        elif dti <= 0.4:
            debt_delta = 8
        elif dti <= 0.6:
            debt_delta = -8
        else:
            debt_delta = -16
        score += debt_delta
        breakdown.append(
            {
                "label": "Debt vs income",
                "delta": f"{debt_delta:+d}",
                "note": f"Debt/income ~{dti*100:.0f}%. Higher debt pressure reduces investability.",
            }
        )

        implied_emi = min(debt * 0.01, income * 0.45) if debt > 0 else 0
        surplus = income - monthly_expenses - implied_emi
        surplus_ratio = (surplus / income) if income > 0 else -1
        if surplus_ratio > 0.2:
            surplus_delta = 14
        elif surplus_ratio > 0.1:
            surplus_delta = 8
        elif surplus_ratio > 0:
            surplus_delta = 2
        else:
            surplus_delta = -12
        score += surplus_delta
        breakdown.append(
            {
                "label": "Monthly surplus",
                "delta": f"{surplus_delta:+d}",
                "note": "Based on income minus expenses and rough EMI estimate. More surplus supports safer investing.",
            }
        )

        if dependents > 0:
            dep_delta = -min(dependents * 2, 8)
            score += dep_delta
            breakdown.append(
                {
                    "label": "Family responsibility",
                    "delta": f"{dep_delta:+d}",
                    "note": f"{dependents} dependent(s): cash-flow resilience becomes more important.",
                }
            )

        goal = str(profile.get("goal", ""))
        if "Emergency" in goal and months < 6:
            goal_delta = -6
            score += goal_delta
            breakdown.append(
                {
                    "label": "Goal alignment",
                    "delta": f"{goal_delta:+d}",
                    "note": "Emergency Fund goal selected, but buffer is below 6 months.",
                }
            )
        elif goal == "Tax Saving" and months >= 3:
            goal_delta = 4
            score += goal_delta
            breakdown.append(
                {
                    "label": "Goal alignment",
                    "delta": f"{goal_delta:+d}",
                    "note": "Tax goal with basic cash buffer in place.",
                }
            )

        score = max(8, min(100, int(score)))
        return {
            "score": score,
            "label": "Planning readiness (heuristic)",
            "breakdown": breakdown,
            "summary": "Score moves when you change savings, expenses, debt, income, or goal — same inputs → same score by design.",
        }

    def _build_priority_actions(self, profile, market_snapshot, savings_months, debt_to_income):
        """Real-world order: safety → debt → goals → markets."""
        actions = []
        if savings_months < 3:
            actions.append({"step": 1, "action": "Build 3–6 months of expenses in liquid FD / money-market or short-duration debt funds.", "why": "Standard planner first step before market risk."})
        elif savings_months < 6:
            actions.append({"step": 1, "action": "Top up emergency fund toward 6 months of expenses.", "why": "Aligns with common advisory practice for salaried households."})
        if debt_to_income > 0.4:
            actions.append({"step": 2, "action": "Prioritize high-interest debt (credit cards, personal loans) before raising equity allocation.", "why": "Real-world: cost of debt often exceeds expected equity returns net of risk."})
        actions.append({"step": 3, "action": "Use goal + horizon to choose product mix (e.g. ELSS/PPF for tax; SIP for long goals).", "why": "SEBI emphasizes suitability — match product to goal and time horizon."})
        if market_snapshot and market_snapshot.get("overall_sentiment") == "Cautious":
            actions.append({"step": 0, "action": "In volatile markets, prefer SIP/staggered entry over lump-sum equity; keep horizon 5+ years for equity.", "why": "Reduces timing risk; consistent with long-term equity investing guidance."})
        actions.append({"step": 0, "action": "Review allocation yearly or on life events (job change, marriage, loan).", "why": "Static plans drift from real risk capacity."})
        for i, a in enumerate(actions, start=1):
            a["step"] = i
        return actions

    def _fetch_market_snapshot(self):
        """India-first: NSE + Nifty Indices; Yahoo only as fallback when available."""
        as_of = datetime.now(timezone.utc).isoformat()
        if snapshot_items_india is not None:
            items, ok = snapshot_items_india()
            if ok and items:
                avg_change = sum(item["change_pct"] for item in items) / len(items)
                return {
                    "source": "nse_india+coin_gecko",
                    "as_of": as_of,
                    "items": items,
                    "overall_sentiment": self._market_sentiment_label(avg_change),
                    "status": "Live snapshot from NSE India (indices & GOLDBEES) + CoinGecko (BTC/INR).",
                }

        symbols = {
            "NIFTY 50": "^NSEI",
            "S&P 500": "^GSPC",
            "Gold ETF (GLD)": "GLD",
            "Bitcoin (USD)": "BTC-USD",
        }
        snapshot = []
        market_ok = False
        if yf is None:
            return {
                "source": "fallback",
                "as_of": as_of,
                "items": [],
                "status": "Market data unavailable (install yfinance or check network).",
            }

        for name, ticker in symbols.items():
            try:
                info = yf.Ticker(ticker).history(period="2d")
                if info is None or info.empty:
                    continue
                last = float(info["Close"].iloc[-1])
                prev = float(info["Close"].iloc[-2]) if len(info) > 1 else last
                change_pct = ((last - prev) / prev * 100.0) if prev else 0.0
                snapshot.append(
                    {
                        "name": name,
                        "ticker": ticker,
                        "last_price": round(last, 2),
                        "change_pct": round(change_pct, 2),
                    }
                )
                market_ok = True
            except Exception:
                continue

        if not market_ok:
            return {
                "source": "fallback",
                "as_of": as_of,
                "items": [],
                "status": "Unable to fetch live market data right now.",
            }

        avg_change = sum(item["change_pct"] for item in snapshot) / len(snapshot)
        return {
            "source": "yahoo_finance",
            "as_of": as_of,
            "items": snapshot,
            "overall_sentiment": self._market_sentiment_label(avg_change),
            "status": "Live prices from Yahoo Finance (fallback).",
        }

    def _get_risk_profile_label(self, data):
        risk = str(data.get("risk_tolerance", "Moderate")).lower()

        if risk == "conservative":
            return "Capital Preserver 🏦", "#27AE60"
        elif risk == "moderate":
            return "Balanced Grower ⚖️", "#F39C12"
        else:
            return "Aggressive Wealth Builder 🚀", "#E74C3C"

    def generate_recommendation(self, profile):
        market_snapshot = self._fetch_market_snapshot()
        scores = self._score_instruments(profile)
        allocation = self._allocate_portfolio(scores, profile["risk_tolerance"])
        insights = self._get_insights(profile, allocation, market_snapshot)
        label, color = self._get_risk_profile_label(profile)

        income = self._safe_float(profile["income"])
        monthly_expenses = self._safe_float(profile.get("monthly_expenses"))
        debt = self._safe_float(profile.get("debt"))
        savings = self._safe_float(profile.get("savings"))
        monthly_invest, _inv_note = self._realistic_monthly_investment(profile)

        emergency_fund = monthly_expenses * 6 if monthly_expenses > 0 else income * 6
        debt_to_income = (debt / income) if income > 0 else 0
        savings_months = savings / monthly_expenses if monthly_expenses > 0 else 0

        stock_news = self._fetch_stock_news(limit=10)
        market_chart = self._market_chart_best_effort(60)
        priority_actions = self._build_priority_actions(profile, market_snapshot, savings_months, debt_to_income)
        financial_health = self._financial_health_detail(profile)
        guidance_plan = self._build_guidance_plan(profile)

        methodology = [
            "Uses goal + horizon + risk tolerance + life-stage heuristics (common financial-planning practice, not a forecast).",
            "India market snapshot and NIFTY trend use NSE + Nifty Indices (official exchange/index data), not a prediction.",
            "Apps such as Groww show NSE prices; this project uses the same public NSE/Nifty Indices feeds for quotes and index history (not affiliated).",
            "Headlines mix Investing.com India RSS, Economic Times, Moneycontrol, and Yahoo when available.",
            "Emergency buffer and debt checks come before aggressive equity — aligned with typical suitability logic.",
        ]

        return {
            "profile_label": label,
            "profile_color": color,
            "allocation": allocation,
            "insights": insights,
            "market_snapshot": market_snapshot,
            "market_chart": market_chart,
            "stock_news": stock_news,
            "priority_actions": priority_actions,
            "guidance_plan": guidance_plan,
            "methodology": methodology,
            "financial_health": financial_health,
            "summary": {
                "monthly_recommended": round(monthly_invest),
                "emergency_fund_target": round(emergency_fund),
                "debt_to_income_ratio": round(debt_to_income, 2),
                "risk_level": profile["risk_tolerance"],
                "investment_goal": profile["goal"],
                "time_horizon": profile["horizon"],
            },
            "disclaimer": "Educational tool only — not investment advice. Markets involve risk. Consult a SEBI-registered investment adviser for personalized guidance.",
        }