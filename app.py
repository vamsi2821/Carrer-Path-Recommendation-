from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from investment_engine import InvestmentAdvisor

try:
    from indian_market_data import get_daily_market_context
except Exception:
    get_daily_market_context = None

try:
    from live_market_scraper import get_live_market_payload
except Exception:
    get_live_market_payload = None

app = Flask(__name__)
# Allow browser pages opened as file:// to call http://127.0.0.1:5000/api (Origin: null).
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=False)

advisor = InvestmentAdvisor()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/recommend", methods=["POST"])
def recommend():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    required = [
        "age",
        "income",
        "savings",
        "monthly_expenses",
        "debt",
        "is_student",
        "dependents",
        "investment_experience",
        "risk_tolerance",
        "goal",
        "horizon",
    ]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    try:
        result = advisor.generate_recommendation(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/options", methods=["GET"])
def get_options():
    return jsonify({
        "goals": ["Wealth Building", "Retirement Planning", "Child Education", "Emergency Fund", "Home Purchase", "Tax Saving", "Regular Income"],
        "risk_levels": ["Conservative", "Moderate", "Aggressive"],
        "horizons": ["Short-term (< 1 year)", "Medium-term (1-5 years)", "Long-term (5-15 years)", "Very Long-term (15+ years)"],
        "experience_levels": ["Beginner", "Intermediate", "Advanced"],
        "student_options": ["No", "Yes"]
    })


@app.route("/api/news", methods=["GET"])
def stock_news():
    """Headlines from Yahoo Finance (via yfinance) — real-world market news."""
    try:
        return jsonify(advisor.get_public_news())
    except Exception as e:
        return jsonify({"error": str(e), "items": []}), 500


@app.route("/api/market-chart", methods=["GET"])
def market_chart():
    """Recent index prices for charts (NIFTY 50 trend)."""
    try:
        return jsonify(advisor.get_market_chart_data())
    except Exception as e:
        return jsonify({"error": str(e), "labels": [], "closes": []}), 500


@app.route("/api/market-tracker", methods=["GET"])
def market_tracker():
    """
    Live-style market tracker: watchlist with sparklines + NIFTY/S&P daily up/down bar series.
    """
    try:
        return jsonify(advisor.get_live_market_tracker())
    except Exception as e:
        return jsonify({"error": str(e), "instruments": []}), 500


@app.route("/api/live-market-scrape", methods=["GET"])
def live_market_scrape():
    """
    Aggregated RSS + NSE snapshot + light HTML meta reads; cached to data/live_market_cache.json.
    """
    if get_live_market_payload is None:
        return jsonify({"error": "live_market_scraper not available", "rss_headlines": []}), 200
    try:
        return jsonify(get_live_market_payload())
    except Exception as e:
        return jsonify({"error": str(e), "rss_headlines": []}), 500


@app.route("/api/market-brief", methods=["GET"])
def market_brief():
    """India daily context + links to Groww, NSE, Moneycontrol, ET (education)."""
    if get_daily_market_context is None:
        return jsonify(
            {
                "error": "Market module unavailable. Install: pip install requests",
                "summary_lines": [],
                "links": [],
            }
        )
    try:
        return jsonify(get_daily_market_context())
    except Exception as e:
        return jsonify({"error": str(e), "summary_lines": [], "links": []}), 500


if __name__ == "__main__":
    import threading
    import webbrowser

    try:
        import requests  # noqa: F401
    except ImportError:
        print("WARNING: install dependencies with: python -m pip install -r requirements.txt")

    def _open_browser():
        webbrowser.open("http://127.0.0.1:5000/")

    # Single process: open browser after the server starts listening.
    # use_reloader=False avoids a second Flask process (which would open two tabs).
    threading.Timer(1.0, _open_browser).start()
    app.run(debug=True, port=5000, use_reloader=False)