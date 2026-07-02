// WealthMind AI - Frontend Logic
// If you open this page as a local file (file://), API calls must target the Flask server explicitly.
function apiUrl(path) {
  const p = path.startsWith("/") ? path : `/${path}`;
  if (typeof window !== "undefined" && window.location && window.location.protocol === "file:") {
    const base = (window.API_BASE || "http://127.0.0.1:5000").replace(/\/$/, "");
    return `${base}${p}`;
  }
  return p;
}

function showConnectionHelpIfNeeded() {
  const el = document.getElementById("connection-banner");
  if (!el) return;
  if (window.location.protocol === "file:") {
    el.hidden = false;
    el.innerHTML =
      "<strong>This page was opened as a file.</strong> Charts and news need the Flask API. " +
      "In a terminal run: <code>python app.py</code> then open " +
      "<a href=\"http://127.0.0.1:5000/\">http://127.0.0.1:5000/</a> (not the HTML file directly).";
  }
}

let selectedRisk = "";

const COLORS = [
  "#c9a84c","#00c9b1","#60a5fa","#f472b6","#a78bfa",
  "#34d399","#fb923c","#f87171","#e8c97a","#4ade80"
];

const INSTRUMENTS_STATIC = [
  { icon:"📈", name:"Equity Stocks", cat:"High Risk", catClass:"cat-high", desc:"Direct ownership in companies. Best for aggressive investors with long horizon.", ret:"12–18% p.a.", min:"₹500", liq:"High" },
  { icon:"💹", name:"Equity Mutual Funds", cat:"Medium-High Risk", catClass:"cat-high", desc:"Professionally managed diversified equity portfolio.", ret:"10–15% p.a.", min:"₹500", liq:"High" },
  { icon:"🔄", name:"SIP", cat:"Medium Risk", catClass:"cat-medium", desc:"Disciplined monthly investment in mutual funds. Rupee-cost averaging.", ret:"10–14% p.a.", min:"₹100/mo", liq:"High" },
  { icon:"🧾", name:"ELSS", cat:"Tax-Saving", catClass:"cat-medium", desc:"Best tax-saving + growth combo. 3-year lock-in under Sec 80C.", ret:"12–15% p.a.", min:"₹500", liq:"Low" },
  { icon:"🏦", name:"Fixed Deposit (FD)", cat:"Low Risk", catClass:"cat-low", desc:"Guaranteed returns. Safe parking for capital. Ideal for conservative investors.", ret:"6.5–8.5% p.a.", min:"₹1,000", liq:"Medium" },
  { icon:"🏛️", name:"PPF", cat:"Low Risk", catClass:"cat-low", desc:"Government-backed, completely tax-free EEE returns. 15-year lock-in.", ret:"7.1% p.a.", min:"₹500/yr", liq:"Low" },
  { icon:"🌅", name:"NPS", cat:"Low-Medium Risk", catClass:"cat-low", desc:"Government pension scheme. Extra ₹50K deduction under 80CCD(1B).", ret:"8–12% p.a.", min:"₹500", liq:"Very Low" },
  { icon:"🥇", name:"Gold / SGBs", cat:"Medium Risk", catClass:"cat-medium", desc:"Inflation hedge. SGBs are best form — 2.5% extra interest + capital gains.", ret:"8–10% p.a.", min:"₹100", liq:"Medium" },
  { icon:"📊", name:"Debt Mutual Funds", cat:"Low-Medium Risk", catClass:"cat-low", desc:"Better than FD for short to medium term. Invests in bonds/govt securities.", ret:"6–9% p.a.", min:"₹500", liq:"High" },
  { icon:"🏘️", name:"Real Estate / REITs", cat:"Medium-High Risk", catClass:"cat-high", desc:"Tangible asset with appreciation + rental. REITs give affordable exposure.", ret:"8–12% p.a.", min:"₹300", liq:"Medium" },
  { icon:"💰", name:"Recurring Deposit (RD)", cat:"Low Risk", catClass:"cat-low", desc:"Monthly savings with fixed return. Great for emergency fund building.", ret:"5.5–7.5% p.a.", min:"₹100/mo", liq:"Low" }
];

function selectRisk(btn) {
  document.querySelectorAll(".risk-btn").forEach(b => b.classList.remove("selected"));
  btn.classList.add("selected");
  selectedRisk = btn.getAttribute("data-value");
}

function validateForm() {
  const age = parseInt(document.getElementById("age").value);
  const income = parseFloat(document.getElementById("income").value);
  const savings = parseFloat(document.getElementById("savings").value);
  const monthlyExpenses = parseFloat(document.getElementById("monthly_expenses").value);
  const debt = parseFloat(document.getElementById("debt").value);
  const isStudent = document.getElementById("is_student").value;
  const dependents = parseInt(document.getElementById("dependents").value, 10);
  const investmentExperience = document.getElementById("investment_experience").value;
  const goal = document.getElementById("goal").value;
  const horizon = document.getElementById("horizon").value;

  if (!age || age < 18 || age > 80) return "Enter a valid age (18–80)";
  if (!income || income <= 0) return "Enter a valid monthly income";
  if (savings < 0 || isNaN(savings)) return "Enter a valid savings amount (0 or more)";
  if (!monthlyExpenses || monthlyExpenses <= 0) return "Enter valid monthly expenses";
  if (debt < 0 || isNaN(debt)) return "Enter a valid debt amount (0 or more)";
  if (!isStudent) return "Please select student status";
  if (isNaN(dependents) || dependents < 0) return "Enter valid dependents count";
  if (!investmentExperience) return "Please select your investment experience";
  if (!selectedRisk) return "Please select your risk tolerance";
  if (!goal) return "Please select your investment goal";
  if (!horizon) return "Please select your investment horizon";
  return null;
}

async function getRecommendation() {
  const errEl = document.getElementById("form-error");
  errEl.textContent = "";

  const err = validateForm();
  if (err) { errEl.textContent = err; return; }

  const btnText = document.getElementById("btn-text");
  const btnLoader = document.getElementById("btn-loader");
  btnText.style.display = "none";
  btnLoader.style.display = "inline";

  const payload = {
    age: document.getElementById("age").value,
    income: document.getElementById("income").value,
    savings: document.getElementById("savings").value,
    monthly_expenses: document.getElementById("monthly_expenses").value,
    debt: document.getElementById("debt").value,
    is_student: document.getElementById("is_student").value,
    dependents: document.getElementById("dependents").value,
    investment_experience: document.getElementById("investment_experience").value,
    risk_tolerance: selectedRisk,
    goal: document.getElementById("goal").value,
    horizon: document.getElementById("horizon").value
  };

  try {
    const res = await fetch(apiUrl("/api/recommend"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.error) { errEl.textContent = data.error; return; }
    renderResults(data);
  } catch (e) {
    errEl.textContent = "Connection error. Make sure the Flask server is running.";
  } finally {
    btnText.style.display = "inline";
    btnLoader.style.display = "none";
  }
}

function destroyCharts() {
  if (window._chartAlloc) {
    window._chartAlloc.destroy();
    window._chartAlloc = null;
  }
  if (window._chartMarket) {
    window._chartMarket.destroy();
    window._chartMarket = null;
  }
  if (window._chartBar) {
    window._chartBar.destroy();
    window._chartBar = null;
  }
}

function shortLabel(name) {
  if (!name) return "";
  let n = String(name).replace(/\s*\([^)]*\)\s*/g, " ").trim();
  if (n.length > 24) n = n.slice(0, 22) + "…";
  return n;
}

/** Short stable labels for horizontal bar chart (avoids canvas clipping on long names). */
function chartLabel(inst) {
  const byKey = {
    equity_stocks: "Equity stocks",
    mutual_funds_equity: "Equity mutual funds",
    sip: "SIP",
    elss: "ELSS",
    fd: "Fixed deposit",
    ppf: "PPF",
    nps: "NPS",
    gold: "Gold / SGB",
    debt_funds: "Debt mutual funds",
    real_estate: "Real estate / REITs",
    rd: "Recurring deposit",
  };
  if (inst && inst.key && byKey[inst.key]) return byKey[inst.key];
  return shortLabel(inst.name);
}

function buildCharts(data) {
  destroyCharts();
  if (typeof Chart === "undefined") return;

  const alloc = data.allocation || [];
  const mc = data.market_chart || {};

  const ctxA = document.getElementById("chartAllocation");
  if (ctxA && alloc.length) {
    try {
    window._chartAlloc = new Chart(ctxA, {
      type: "doughnut",
      data: {
        labels: alloc.map((a) => `${a.icon || ""} ${chartLabel(a)}`.trim()),
        datasets: [
          {
            data: alloc.map((a) => a.allocation_percent),
            backgroundColor: COLORS.slice(0, alloc.length),
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { color: "#a0a8b8", boxWidth: 12, font: { size: 11 } } },
          title: { display: true, text: "Recommended mix (%)", color: "#7a8299", font: { size: 12 } },
        },
      },
    });
    } catch (e) {
      console.warn("Allocation chart", e);
    }
  }

  const ctxB = document.getElementById("chartBarSolutions");
  if (ctxB && alloc.length) {
    try {
    window._chartBar = new Chart(ctxB, {
      type: "bar",
      data: {
        labels: alloc.map((a) => chartLabel(a)),
        datasets: [
          {
            label: "Allocation %",
            data: alloc.map((a) => a.allocation_percent),
            backgroundColor: COLORS.slice(0, alloc.length),
            borderRadius: 6,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { left: 8, right: 16, top: 8, bottom: 8 } },
        plugins: {
          legend: { display: false },
          title: { display: true, text: "Best-fit solutions (ranked weight)", color: "#7a8299", font: { size: 12 } },
        },
        scales: {
          x: { max: 100, ticks: { color: "#7a8299" }, grid: { color: "rgba(255,255,255,0.06)" } },
          y: {
            ticks: { color: "#c4c9d4", font: { size: 11 }, maxRotation: 0, autoSkip: false },
            grid: { display: false },
          },
        },
      },
    });
    } catch (e) {
      console.warn("Bar chart", e);
    }
  }

  const ctxM = document.getElementById("chartMarket");
  if (ctxM && mc.labels && mc.labels.length && mc.closes && mc.closes.length) {
    try {
    window._chartMarket = new Chart(ctxM, {
      type: "line",
      data: {
        labels: mc.labels,
        datasets: [
          {
            label: mc.name || "Index — daily close",
            data: mc.closes,
            borderColor: "#c9a84c",
            backgroundColor: "rgba(201,168,76,0.08)",
            fill: true,
            tension: 0.25,
            pointRadius: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#a0a8b8" } },
          title: {
            display: true,
            text: mc.source === "niftyindices" ? "NIFTY 50 — daily close (Nifty Indices)" : "Recent index trend",
            color: "#7a8299",
            font: { size: 12 },
          },
        },
        scales: {
          x: { ticks: { color: "#7a8299", maxTicksLimit: 10 }, grid: { color: "rgba(255,255,255,0.06)" } },
          y: { ticks: { color: "#7a8299" }, grid: { color: "rgba(255,255,255,0.06)" } },
        },
      },
    });
    } catch (e) {
      console.warn("Market trend chart", e);
    }
  }
}

function renderResults(data) {
  document.getElementById("results-empty").style.display = "none";
  const content = document.getElementById("results-content");
  content.style.display = "block";

  const alloc = data.allocation;
  const summary = data.summary;
  const market = data.market_snapshot || { items: [], status: "No market data available." };
  const mc = data.market_chart || {};
  const hasTrend = mc.labels && mc.labels.length && mc.closes && mc.closes.length;
  const health =
    data.financial_health && typeof data.financial_health.score === "number"
      ? data.financial_health
      : { score: 0, label: "Planning readiness (heuristic)", breakdown: [], summary: "" };
  const methodology = data.methodology || [];
  const priority = data.priority_actions || [];
  const guidancePlan = data.guidance_plan || null;
  saveCurrentPlan(data, guidancePlan);
  updateProfilePlanUI();

  const trendPanel = hasTrend
    ? `<div class="chart-panel chart-panel-wide">
        <canvas id="chartMarket" height="240"></canvas>
        <p class="chart-footnote">${escapeHtml(mc.hint || "")}</p>
      </div>`
    : `<div class="chart-panel chart-panel-wide chart-panel-fallback">
        <h4 class="subsection-title">Market index trend</h4>
        <p class="muted chart-fallback-msg">${escapeHtml(
          mc.hint ||
            "No chart data returned (Yahoo/network/region). Use the Live Market Tracker section on this page for indices and stocks, or try again in a minute."
        )}</p>
        <p class="muted chart-fallback-status">Technical: ${escapeHtml(String(mc.status || "no_data"))}</p>
      </div>`;

  const legendHTML = alloc.map((a, i) => `
    <div class="legend-item">
      <div class="legend-dot" style="background:${COLORS[i]}"></div>
      <span class="legend-name">${a.icon} ${a.name}</span>
      <span class="legend-pct">${a.allocation_percent}%</span>
    </div>
  `).join("");

  const allocHTML = alloc.map((a, i) => `
    <div class="alloc-item" style="border-left-color:${COLORS[i]}">
      <div class="alloc-header">
        <span class="alloc-name">${a.icon} ${a.name}</span>
        <span class="alloc-pct">${a.allocation_percent}%</span>
      </div>
      <div class="alloc-meta">
        <span>📊 Return: ${a.expected_return}</span>
        <span>💧 Liquidity: ${a.liquidity}</span>
        <span>💵 Min: ${a.min_investment}</span>
      </div>
      <div class="alloc-bar"><div class="alloc-bar-fill" style="width:${a.allocation_percent}%;background:${COLORS[i]}"></div></div>
    </div>
  `).join("");

  const insightsHTML = data.insights.map((i) => `<div class="insight-item">${i}</div>`).join("");

  const monthlyAmt = `₹${summary.monthly_recommended.toLocaleString("en-IN")}`;
  const emergencyAmt = `₹${summary.emergency_fund_target.toLocaleString("en-IN")}`;
  const dti = `${(summary.debt_to_income_ratio * 100).toFixed(0)}%`;
  const marketRows = (market.items || [])
    .map((item) => {
      const isUp = item.change_pct >= 0;
      const num = Number(item.last_price);
      const priceStr =
        item.ticker === "BTC-INR" && !Number.isNaN(num)
          ? "₹" + Math.round(num).toLocaleString("en-IN")
          : Number.isFinite(num)
            ? num.toLocaleString("en-IN", { maximumFractionDigits: 2 })
            : item.last_price;
      return `
      <div class="market-row">
        <span>${item.name}</span>
        <span>${priceStr}</span>
        <span class="${isUp ? "up" : "down"}">${isUp ? "▲" : "▼"} ${Math.abs(item.change_pct)}%</span>
      </div>
    `;
    })
    .join("");

  const newsItems = (data.stock_news && data.stock_news.items) || [];
  const newsHTML = newsItems
    .slice(0, 6)
    .map(
      (n) => `
    <div class="news-item">
      <a class="news-link" href="${n.link || "#"}" target="_blank" rel="noopener noreferrer">${escapeHtml(n.title)}</a>
      <div class="news-meta">${escapeHtml(n.publisher || "")}${n.published ? " · " + escapeHtml(n.published) : ""}</div>
    </div>
  `
    )
    .join("");

  const priorityHTML = priority
    .map(
      (p) => `
    <div class="priority-item">
      <span class="priority-step">${p.step}</span>
      <div>
        <strong>${escapeHtml(p.action)}</strong>
        <p class="priority-why">${escapeHtml(p.why)}</p>
      </div>
    </div>
  `
    )
    .join("");

  const methodHTML = methodology.map((m) => `<li>${escapeHtml(m)}</li>`).join("");

  const healthBreakdown = (health.breakdown || [])
    .map(
      (b) => `
    <div class="health-factor">
      <span class="health-factor-label">${escapeHtml(b.label)}</span>
      <span class="health-factor-delta">${escapeHtml(b.delta)}</span>
      <p class="health-factor-note">${escapeHtml(b.note)}</p>
    </div>
  `
    )
    .join("");

  content.innerHTML = `
    <div class="profile-badge" style="color:${data.profile_color};border-color:${data.profile_color};background:${data.profile_color}18">
      ${data.profile_label}
    </div>

    <div class="health-row">
      <div class="health-label">${health.label || "Planning readiness"}</div>
      <div class="health-bar-wrap">
        <div class="health-bar-fill" style="width:${health.score}%"></div>
      </div>
      <span class="health-score">${health.score}/100</span>
    </div>
    ${health.summary ? `<p class="health-summary muted">${escapeHtml(health.summary)}</p>` : ""}
    ${healthBreakdown ? `<div class="health-breakdown">${healthBreakdown}</div>` : ""}

    <div class="charts-grid">
      <div class="chart-panel">
        <canvas id="chartAllocation" height="220"></canvas>
      </div>
      <div class="chart-panel">
        <canvas id="chartBarSolutions" height="220"></canvas>
      </div>
      ${trendPanel}
    </div>

    <div class="donut-section donut-section-legacy">
      <div class="mini-legend-wrap">
        <h4 class="subsection-title">Allocation legend</h4>
        <div class="legend">${legendHTML}</div>
      </div>
    </div>

    <div class="summary-grid">
      <div class="summary-item">
        <label>Monthly Invest (surplus-based)</label>
        <span>${monthlyAmt}</span>
      </div>
      <div class="summary-item">
        <label>Emergency Target</label>
        <span>${emergencyAmt}</span>
      </div>
      <div class="summary-item">
        <label>Goal</label>
        <span>${summary.investment_goal}</span>
      </div>
      <div class="summary-item">
        <label>Horizon</label>
        <span>${summary.time_horizon.split("(")[0].trim()}</span>
      </div>
      <div class="summary-item">
        <label>Debt to Income</label>
        <span>${dti}</span>
      </div>
    </div>

    ${
      guidancePlan
        ? `<div class="plan-section">
      <h4>Current guidance plan</h4>
      <div class="plan-grid">
        <div class="summary-item"><label>Plan</label><span>${escapeHtml(guidancePlan.title || "-")}</span></div>
        <div class="summary-item"><label>Valid For</label><span>${escapeHtml(String(guidancePlan.validity_days || "-"))} days</span></div>
        <div class="summary-item"><label>Review / Expiry</label><span>${escapeHtml(guidancePlan.review_on || "-")}</span></div>
      </div>
      <p class="muted">${escapeHtml(guidancePlan.guidance || "")}</p>
      <p class="muted">${escapeHtml(guidancePlan.renewal_note || "")}</p>
    </div>`
        : ""
    }

    <div class="priority-section">
      <h4>Priority actions (real-world order)</h4>
      ${priorityHTML || "<p class=\"muted\">No extra steps.</p>"}
    </div>

    <div class="method-section">
      <h4>How this advice is built</h4>
      <ul class="method-list">${methodHTML || "<li>Rule-based suitability and planning heuristics.</li>"}</ul>
    </div>

    <div class="market-section">
      <h4>Live Market Snapshot</h4>
      ${marketRows || `<div class="market-empty">${market.status}</div>`}
      ${market.source ? `<p class="market-status">Source: ${market.source} · ${market.status}</p>` : ""}
      ${market.overall_sentiment ? `<p class="market-sentiment">Broad tone: <strong>${market.overall_sentiment}</strong></p>` : ""}
    </div>

    <div class="news-inline">
      <h4>Related headlines</h4>
      ${newsHTML || "<p class=\"muted\">No headlines loaded. Check internet / try again later.</p>"}
    </div>

    <div class="allocation-list">${allocHTML}</div>

    <div class="insights-section">
      <h4>Real-world style insights</h4>
      ${insightsHTML}
    </div>

    <p class="disclaimer">⚠️ ${data.disclaimer}</p>
  `;

  requestAnimationFrame(() => buildCharts(data));

  document.getElementById("results-panel").scrollIntoView({ behavior: "smooth", block: "start" });
}

function saveCurrentPlan(data, guidancePlan) {
  const summary = data?.summary || {};
  const payload = {
    planTitle: guidancePlan?.title || "Custom guidance plan",
    risk: summary.risk_level || "-",
    horizon: summary.time_horizon || "-",
    reviewOn: guidancePlan?.review_on || "-",
    note: guidancePlan?.guidance || "Guidance active until review.",
    status: "Active",
  };
  localStorage.setItem("wm_current_plan", JSON.stringify(payload));
}

function getCurrentPlan() {
  try {
    return JSON.parse(localStorage.getItem("wm_current_plan") || "null");
  } catch (e) {
    return null;
  }
}

function updateProfilePlanUI() {
  const plan = getCurrentPlan();
  const planTitle = document.getElementById("profile-plan-title");
  const risk = document.getElementById("profile-risk");
  const horizon = document.getElementById("profile-horizon");
  const review = document.getElementById("profile-review-date");
  const status = document.getElementById("profile-plan-status");
  const note = document.getElementById("profile-plan-note");
  if (!plan) return;
  if (planTitle) planTitle.textContent = plan.planTitle || "-";
  if (risk) risk.textContent = plan.risk || "-";
  if (horizon) horizon.textContent = plan.horizon || "-";
  if (review) review.textContent = plan.reviewOn || "-";
  if (status) status.textContent = plan.status || "Active";
  if (note) note.textContent = plan.note || "";
}

function escapeHtml(s) {
  if (!s) return "";
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function renderInstruments() {
  const grid = document.getElementById("instruments-grid");
  grid.innerHTML = INSTRUMENTS_STATIC.map(inst => `
    <div class="inst-card">
      <div class="inst-icon">${inst.icon}</div>
      <div class="inst-name">${inst.name}</div>
      <div class="inst-cat ${inst.catClass}">${inst.cat}</div>
      <div class="inst-desc">${inst.desc}</div>
      <div class="inst-meta">
        <div class="inst-meta-item"><label>Returns</label><span>${inst.ret}</span></div>
        <div class="inst-meta-item"><label>Min. Invest</label><span>${inst.min}</span></div>
        <div class="inst-meta-item"><label>Liquidity</label><span>${inst.liq}</span></div>
      </div>
    </div>
  `).join("");
}

const TRACKER_REFRESH_MS = 120000;
let trackerAutoRefreshId = null;
let authMode = "login";

function destroyTrackerCharts() {
  if (window._chartDailyNifty) {
    window._chartDailyNifty.destroy();
    window._chartDailyNifty = null;
  }
  if (window._chartDailySP500) {
    window._chartDailySP500.destroy();
    window._chartDailySP500 = null;
  }
  (window._trackerSparkCharts || []).forEach((c) => {
    try {
      c.destroy();
    } catch (e) {
      /* ignore */
    }
  });
  window._trackerSparkCharts = [];
}

function formatTrackerNumber(val, currency) {
  if (val == null || Number.isNaN(val)) return "—";
  if (currency === "FX") return val.toFixed(2);
  if (currency === "INR") return "₹" + Number(val).toLocaleString("en-IN", { maximumFractionDigits: 2 });
  return "$" + Number(val).toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function buildDailyMovesBarChart(canvasId, series, chartKey) {
  const el = document.getElementById(canvasId);
  if (!el || typeof Chart === "undefined") return;
  const labels = series.labels || [];
  const vals = series.changes_pct || [];
  if (!labels.length || !vals.length) return;

  if (chartKey === "nifty" && window._chartDailyNifty) window._chartDailyNifty.destroy();
  if (chartKey === "sp500" && window._chartDailySP500) window._chartDailySP500.destroy();

  const colors = vals.map((v) =>
    v >= 0 ? "rgba(52, 211, 153, 0.82)" : "rgba(248, 113, 113, 0.82)"
  );

  const cfg = {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Daily % Δ",
          data: vals,
          backgroundColor: colors,
          borderWidth: 0,
          borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const v = ctx.raw;
              const sign = v >= 0 ? "+" : "";
              return `${sign}${Number(v).toFixed(2)}% vs prior close`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "#7a8299", maxRotation: 45, maxTicksLimit: 14, font: { size: 10 } },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
        y: {
          ticks: {
            color: "#7a8299",
            callback: (v) => (v >= 0 ? "+" : "") + v + "%",
          },
          grid: { color: "rgba(255,255,255,0.06)" },
          title: { display: true, text: "% change", color: "#5c6478", font: { size: 10 } },
        },
      },
    },
  };

  const ch = new Chart(el, cfg);
  if (chartKey === "nifty") window._chartDailyNifty = ch;
  else window._chartDailySP500 = ch;
}

function buildWatchlistSparkCharts(instruments) {
  if (typeof Chart === "undefined") return;
  window._trackerSparkCharts = window._trackerSparkCharts || [];
  instruments.forEach((row, i) => {
    const ctx = document.getElementById(`tracker-spark-${i}`);
    if (!ctx || !row.sparkline_closes || !row.sparkline_closes.length) return;
    const lineColor =
      row.direction === "up" ? "#34d399" : row.direction === "down" ? "#f87171" : "#8b92a8";
    const fillUnder =
      row.direction === "up"
        ? "rgba(52,211,153,0.15)"
        : row.direction === "down"
          ? "rgba(248,113,113,0.15)"
          : "rgba(139,146,168,0.1)";
    const ch = new Chart(ctx, {
      type: "line",
      data: {
        labels: row.sparkline_labels || [],
        datasets: [
          {
            data: row.sparkline_closes,
            borderColor: lineColor,
            backgroundColor: fillUnder,
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { display: false }, tooltip: { enabled: true } },
        scales: {
          x: { display: false },
          y: { display: false },
        },
      },
    });
    window._trackerSparkCharts.push(ch);
  });
}

async function loadLiveMarketScraper() {
  const panel = document.getElementById("live-scrape-panel");
  const statusEl = document.getElementById("scraper-status");
  if (!panel) return;
  if (statusEl) statusEl.textContent = "Fetching RSS, NSE, and page meta…";
  panel.innerHTML = '<p class="muted">Loading…</p>';
  try {
    const res = await fetch(apiUrl("/api/live-market-scrape"));
    const data = await res.json();
    if (data.error && !data.rss_headlines && !data.nse) {
      panel.innerHTML = `<p class="muted">${escapeHtml(data.error)}</p>`;
      if (statusEl) statusEl.textContent = "Error";
      return;
    }
    const stale = data.stale ? " · Showing cached file (network failed)" : "";
    const fc = data.from_cache ? " · Served from data/live_market_cache.json" : "";
    if (statusEl) {
      statusEl.textContent = `Updated ${data.as_of ? new Date(data.as_of).toLocaleString() : ""}${stale}${fc}`;
    }

    const nse = data.nse || {};
    const nseRows = (nse.indices || [])
      .map(
        (x) => `
      <div class="scraper-nse-row">
        <span>${escapeHtml(x.name)}</span>
        <strong>${Number(x.last).toLocaleString("en-IN", { maximumFractionDigits: 2 })}</strong>
        <span class="${x.change_pct >= 0 ? "up" : "down"}">${x.change_pct >= 0 ? "+" : ""}${x.change_pct}%</span>
      </div>
    `
      )
      .join("");

    const rss = (data.rss_headlines || [])
      .map(
        (x) => `
      <div class="scraper-rss-item">
        <a href="${escapeHtml(x.link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(x.title)}</a>
        <span class="scraper-src">${escapeHtml(x.source)}</span>
      </div>
    `
      )
      .join("");

    const meta = (data.page_meta || [])
      .map(
        (x) => `
      <div class="scraper-meta-card">
        <div class="scraper-meta-title">${escapeHtml(x.source)} ${x.ok ? "" : "(limited)"}</div>
        <p class="scraper-meta-snippet">${escapeHtml(x.snippet || x.title || "")}</p>
        <a class="scraper-meta-link" href="${escapeHtml(x.url)}" target="_blank" rel="noopener noreferrer">Open site →</a>
      </div>
    `
      )
      .join("");

    panel.innerHTML = `
      <div class="scraper-columns">
        <div class="scraper-col">
          <h3 class="scraper-col-title">NSE snapshot (API)</h3>
          ${nseRows || "<p class=\"muted\">NSE indices unavailable.</p>"}
        </div>
        <div class="scraper-col scraper-col-wide">
          <h3 class="scraper-col-title">RSS headlines (scraped feeds)</h3>
          <div class="scraper-rss-list">${rss || "<p class=\"muted\">No RSS items (check network / firewall).</p>"}</div>
        </div>
        <div class="scraper-col scraper-col-full">
          <h3 class="scraper-col-title">Page meta (title / description)</h3>
          <div class="scraper-meta-grid">${meta || "<p class=\"muted\">No meta (install beautifulsoup4, or sites blocked).</p>"}</div>
        </div>
      </div>
      <p class="scraper-disclaimer">${escapeHtml(data.disclaimer || "")}</p>
    `;
  } catch (e) {
    panel.innerHTML =
      '<p class="muted">Connection error. Run <code>python app.py</code> and open <code>http://127.0.0.1:5000</code></p>';
    if (statusEl) statusEl.textContent = "Not connected";
  }
}

async function loadMarketBrief() {
  const el = document.getElementById("market-brief-panel");
  if (!el) return;
  el.innerHTML = '<p class="muted">Loading context…</p>';
  try {
    const res = await fetch(apiUrl("/api/market-brief"));
    const data = await res.json();
    if (data.error && !data.summary_lines?.length) {
      el.innerHTML = `<p class="muted">${escapeHtml(data.error)}</p>`;
      return;
    }
    const lines = (data.summary_lines || []).map((l) => `<li>${escapeHtml(l)}</li>`).join("");
    const links = (data.links || [])
      .map(
        (x) => `
      <a class="brief-link-card" href="${escapeHtml(x.url)}" target="_blank" rel="noopener noreferrer">
        ${escapeHtml(x.name)}
        <small>${escapeHtml(x.why)}</small>
      </a>
    `
      )
      .join("");
    el.innerHTML = `
      <ul class="brief-lines">${lines || "<li>Snapshot unavailable.</li>"}</ul>
      <p class="subsection-title" style="margin-bottom:10px">Where to read daily market situation (India)</p>
      <div class="brief-links">${links}</div>
      ${data.data_note ? `<p class="brief-footnote">${escapeHtml(data.data_note)}</p>` : ""}
    `;
  } catch (e) {
    el.innerHTML =
      '<p class="muted">Could not load context. Start the Flask server (<code>python app.py</code>) and refresh.</p>';
  }
}

async function loadMarketTracker() {
  const statusEl = document.getElementById("tracker-status");
  const listEl = document.getElementById("tracker-watchlist");
  if (!listEl || !statusEl) return;

  statusEl.textContent = "Updating…";
  destroyTrackerCharts();

  try {
    const res = await fetch(apiUrl("/api/market-tracker"));
    if (!res.ok) {
      let msg = `Server error (${res.status}).`;
      try {
        const err = await res.json();
        if (err.error) msg = err.error;
      } catch (e) {
        /* ignore */
      }
      statusEl.textContent = msg;
      listEl.innerHTML = `<p class="muted">${escapeHtml(msg)} Run <code>python -m pip install -r requirements.txt</code> then <code>python app.py</code>.</p>`;
      return;
    }
    const data = await res.json();

    const asOf = data.as_of ? new Date(data.as_of).toLocaleString() : "";
    let line = `${data.status || "OK"} · Last fetch: ${asOf}`;
    if (data.note) line += ` · ${data.note}`;
    if (data.demo_mode) line = "[DEMO — not live NSE] " + line;
    statusEl.textContent = line;

    const nifty = data.nifty_daily_moves || {};
    const spx = data.sp500_daily_moves || {};
    requestAnimationFrame(() => {
      buildDailyMovesBarChart("chartDailyNifty", nifty, "nifty");
      buildDailyMovesBarChart("chartDailySP500", spx, "sp500");
    });

    const instruments = (data.instruments || []).map((row) => {
      if (row.sparkline_closes && row.sparkline_closes.length >= 2) return row;
      const prev = Number(row.prev_close);
      const last = Number(row.last);
      if (Number.isFinite(prev) && Number.isFinite(last)) {
        return {
          ...row,
          sparkline_labels: ["Prev", "Now"],
          sparkline_closes: [prev, last],
        };
      }
      return row;
    });
    if (!instruments.length) {
      listEl.innerHTML = `<p class="muted">${escapeHtml(data.status || "No watchlist data. Check internet or try Refresh.")}</p>`;
      return;
    }

    listEl.innerHTML = instruments
      .map(
        (row, i) => `
      <div class="tracker-card tracker-${escapeHtml(row.direction || "flat")}">
        <div class="tracker-card-head">
          <span class="tracker-name">${escapeHtml(row.name)}</span>
          <code class="tracker-tick">${escapeHtml(row.ticker)}</code>
        </div>
        <div class="tracker-card-mid">
          <span class="tracker-price">${escapeHtml(formatTrackerNumber(row.last, row.currency))}</span>
          <span class="tracker-chg chg-${escapeHtml(row.direction || "flat")}">${row.change_pct >= 0 ? "+" : ""}${row.change_pct}%</span>
        </div>
        <div class="tracker-hl">Session bar H ${escapeHtml(formatTrackerNumber(row.day_high, row.currency))} · L ${escapeHtml(formatTrackerNumber(row.day_low, row.currency))}</div>
        <div class="tracker-spark-wrap"><canvas id="tracker-spark-${i}" height="70"></canvas></div>
      </div>
    `
      )
      .join("");

    requestAnimationFrame(() => buildWatchlistSparkCharts(instruments));
  } catch (e) {
    statusEl.textContent = "Could not load tracker. Is the server running?";
    listEl.innerHTML = "<p class=\"muted\">Connection error.</p>";
  }
}

async function loadNewsFeed() {
  const el = document.getElementById("news-feed");
  if (!el) return;
  try {
    const res = await fetch(apiUrl("/api/news"));
    const data = await res.json();
    const items = data.items || [];
    if (!items.length) {
      el.innerHTML = `<p class="muted">${escapeHtml(data.status || "No headlines available.")}</p>`;
      return;
    }
    el.innerHTML = items
      .map(
        (n) => `
      <article class="news-card">
        <a href="${n.link || "#"}" target="_blank" rel="noopener noreferrer">${escapeHtml(n.title)}</a>
        <div class="news-card-meta">${escapeHtml(n.publisher || "")}${n.related_symbol ? " · " + escapeHtml(n.related_symbol) : ""}</div>
      </article>
    `
      )
      .join("");
  } catch (e) {
    el.innerHTML = "<p class=\"muted\">Could not load news. Is the server running?</p>";
  }
}

function isStrongPassword(password) {
  if (!password) return false;
  const strongPattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*[^A-Za-z0-9]).{8,}$/;
  return strongPattern.test(password);
}

function getStoredUsers() {
  try {
    return JSON.parse(localStorage.getItem("wm_users") || "[]");
  } catch (e) {
    return [];
  }
}

function saveStoredUsers(users) {
  localStorage.setItem("wm_users", JSON.stringify(users));
}

function setCurrentUser(user) {
  localStorage.setItem("wm_current_user", JSON.stringify(user));
}

function getCurrentUser() {
  try {
    return JSON.parse(localStorage.getItem("wm_current_user") || "null");
  } catch (e) {
    return null;
  }
}

function updateAccountUI(user) {
  const welcomeEl = document.getElementById("welcome-text");
  const accountName = document.getElementById("account-name");
  const accountUsername = document.getElementById("account-username");
  const accountCreated = document.getElementById("account-created");
  if (welcomeEl) {
    const firstName = (user?.name || user?.username || "User").split(" ")[0];
    welcomeEl.textContent = `Welcome back, ${firstName}`;
  }
  if (accountName) accountName.textContent = user?.name || "-";
  if (accountUsername) accountUsername.textContent = user?.username || "-";
  if (accountCreated) {
    accountCreated.textContent = user?.createdAt ? new Date(user.createdAt).toLocaleString() : "-";
  }
}

function setAuthMode(mode) {
  authMode = mode === "signup" ? "signup" : "login";
  const tabLogin = document.getElementById("tab-login");
  const tabSignup = document.getElementById("tab-signup");
  const nameGroup = document.getElementById("signup-name-group");
  const loginBtn = document.getElementById("login-btn");
  const title = document.getElementById("login-title");
  const subtitle = document.getElementById("login-subtitle");
  const errorEl = document.getElementById("login-error");

  if (tabLogin) tabLogin.classList.toggle("active", authMode === "login");
  if (tabSignup) tabSignup.classList.toggle("active", authMode === "signup");
  if (nameGroup) nameGroup.classList.toggle("is-hidden", authMode !== "signup");
  if (loginBtn) loginBtn.textContent = authMode === "signup" ? "Create Account" : "Login";
  if (title) title.textContent = authMode === "signup" ? "Create Your Account" : "Welcome back to WealthMind AI";
  if (subtitle) {
    subtitle.textContent =
      authMode === "signup"
        ? "Sign up once, then login to continue with your personalized dashboard."
        : "Login to continue with your personalized dashboard.";
  }
  if (errorEl) errorEl.textContent = "";
}

function switchPage(pageId) {
  const pages = document.querySelectorAll(".feature-page");
  pages.forEach((page) => {
    page.classList.toggle("active", page.id === pageId);
  });

  const navButtons = document.querySelectorAll(".nav-page-link");
  navButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-page") === pageId);
  });

  if (pageId === "market-page" && document.getElementById("live-market")?.classList.contains("active")) {
    loadMarketTracker();
  }
  if (pageId === "profile-page") {
    updateProfilePlanUI();
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
}

function bindPageNavigation() {
  document.querySelectorAll(".nav-page-link").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const pageId = btn.getAttribute("data-page");
      if (pageId) switchPage(pageId);
    });
  });

  const beginBtn = document.querySelector('.hero-cta a[href="#advisor"]');
  if (beginBtn) {
    beginBtn.addEventListener("click", (e) => {
      e.preventDefault();
      switchPage("advisor-page");
    });
  }

  const howBtn = document.querySelector('.hero-cta a[href="#how"]');
  if (howBtn) {
    howBtn.addEventListener("click", (e) => {
      e.preventDefault();
      switchPage("home-page");
      const howSection = document.getElementById("how");
      if (howSection) howSection.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  document.querySelectorAll(".market-nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-target");
      if (!targetId) return;

      document.querySelectorAll(".market-nav-btn").forEach((b) => {
        b.classList.toggle("active", b === btn);
      });
      document.querySelectorAll(".market-pane").forEach((pane) => {
        pane.classList.toggle("active", pane.id === targetId);
      });

      if (targetId === "live-market") {
        loadMarketTracker();
      }

      const targetEl = document.getElementById(targetId);
      if (targetEl) targetEl.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function handleLogin() {
  const nameEl = document.getElementById("signup-name");
  const usernameEl = document.getElementById("login-username");
  const passwordEl = document.getElementById("login-password");
  const errorEl = document.getElementById("login-error");
  if (!usernameEl || !passwordEl || !errorEl) return false;

  const fullName = (nameEl?.value || "").trim();
  const username = usernameEl.value.trim();
  const password = passwordEl.value;
  errorEl.textContent = "";

  if (!username || !password) {
    errorEl.textContent = "Please enter both username/email and password.";
    return false;
  }

  if (!isStrongPassword(password)) {
    errorEl.textContent =
      "Password must be at least 8 characters and include uppercase, lowercase, and special character.";
    return false;
  }

  const users = getStoredUsers();
  if (authMode === "signup") {
    if (!fullName) {
      errorEl.textContent = "Please enter your name for signup.";
      return false;
    }
    const existing = users.find((u) => u.username.toLowerCase() === username.toLowerCase());
    if (existing) {
      errorEl.textContent = "Account already exists. Please login instead.";
      return false;
    }
    const newUser = { name: fullName, username, password, createdAt: new Date().toISOString() };
    users.push(newUser);
    saveStoredUsers(users);
    setCurrentUser({ name: newUser.name, username: newUser.username, createdAt: newUser.createdAt });
    updateAccountUI(newUser);
  } else {
    const existing = users.find((u) => u.username.toLowerCase() === username.toLowerCase());
    if (!existing) {
      errorEl.textContent = "Account not found. Please sign up first.";
      return false;
    }
    if (existing.password !== password) {
      errorEl.textContent = "Incorrect password.";
      return false;
    }
    setCurrentUser({ name: existing.name, username: existing.username, createdAt: existing.createdAt });
    updateAccountUI(existing);
  }

  const loginScreen = document.getElementById("login-screen");
  const appShell = document.getElementById("app-shell");
  if (loginScreen) loginScreen.classList.add("is-hidden");
  if (appShell) appShell.classList.remove("is-hidden");

  initializeApp();
  return true;
}

function bindLogin() {
  const loginBtn = document.getElementById("login-btn");
  const logoutBtn = document.getElementById("logout-btn");
  const passwordEl = document.getElementById("login-password");
  const tabLogin = document.getElementById("tab-login");
  const tabSignup = document.getElementById("tab-signup");
  if (loginBtn) loginBtn.addEventListener("click", handleLogin);
  if (passwordEl) {
    passwordEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") handleLogin();
    });
  }
  if (tabLogin) tabLogin.addEventListener("click", () => setAuthMode("login"));
  if (tabSignup) tabSignup.addEventListener("click", () => setAuthMode("signup"));
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      localStorage.removeItem("wm_current_user");
      window._appInitialized = false;
      const loginScreen = document.getElementById("login-screen");
      const appShell = document.getElementById("app-shell");
      if (appShell) appShell.classList.add("is-hidden");
      if (loginScreen) loginScreen.classList.remove("is-hidden");
      setAuthMode("login");
    });
  }
}

function initializeApp() {
  if (window._appInitialized) return;
  window._appInitialized = true;

  showConnectionHelpIfNeeded();
  bindPageNavigation();
  updateProfilePlanUI();
  renderInstruments();
  loadMarketBrief();
  loadLiveMarketScraper();
  loadNewsFeed();
  loadMarketTracker();

  const btnTr = document.getElementById("tracker-refresh");
  if (btnTr) btnTr.addEventListener("click", () => loadMarketTracker());
  const btnNews = document.getElementById("news-refresh");
  if (btnNews) btnNews.addEventListener("click", () => loadNewsFeed());
  const btnScrape = document.getElementById("scraper-refresh");
  if (btnScrape) btnScrape.addEventListener("click", () => loadLiveMarketScraper());

  if (!trackerAutoRefreshId) {
    trackerAutoRefreshId = setInterval(() => loadMarketTracker(), TRACKER_REFRESH_MS);
  }
}

// INIT
bindLogin();
setAuthMode("login");