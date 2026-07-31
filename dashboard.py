"""
dashboard.py — Naira Crypto Market Dashboard 
=====================================================================
Streamlit app. Hybrid data model:
  • LIVE prices fetched from CoinGecko the moment the page loads (always current)
  • HISTORICAL snapshots read from data/prices.parquet (built by fetch.py via
    GitHub Actions) to power the price-history charts

Deploy free to Streamlit Community Cloud.
Design: pink branding frame + professional/neutral data colors.
by Favour Jokparose.
"""

import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime, timezone

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Naira Crypto Pulse",
    page_icon="₦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Palette ───────────────────────────────────────────────────────────────────
BRAND_PINK   = "#c2185b"
BG           = "#fdf7f9"
PANEL        = "#ffffff"
BORDER       = "#f3d9e3"
TEXT_MUTED   = "#8a6f7d"
DATA_TEAL    = "#0f766e"
DATA_SLATE   = "#64748b"
DATA_NAVY    = "#1e3a5f"
DATA_AMBER   = "#b45309"
DATA_PLUM    = "#6b4c6b"
GRID         = "#eadfe4"
ZEROLINE     = "#cbb5bf"
UP_GREEN     = "#2e9e6b"
DOWN_RED     = "#d1476a"

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap');
  html, body, [class*="css"] {{ font-family: 'Space Grotesk', sans-serif; background-color: {BG}; color: #2b1d26; }}
  .main {{ background-color: {BG}; }}
  .block-container {{ padding: 2rem 2.5rem 2rem 2.5rem; max-width: 1400px; }}
  .hero-label {{ font-family: 'Space Mono', monospace; font-size: 0.65rem; letter-spacing: 0.2em; color: {BRAND_PINK}; text-transform: uppercase; margin-bottom: 0.25rem; }}
  .hero-title {{ font-size: 2.4rem; font-weight: 700; color: #1f1119; line-height: 1.1; margin-bottom: 0.5rem; }}
  .hero-sub {{ font-size: 0.95rem; color: {TEXT_MUTED}; margin-bottom: 0rem; }}
  .live-dot {{ display:inline-block; width:8px; height:8px; border-radius:50%; background:{UP_GREEN}; margin-right:6px; animation: pulse 1.6s infinite; }}
  @keyframes pulse {{ 0%{{opacity:1;}} 50%{{opacity:0.3;}} 100%{{opacity:1;}} }}
  .kpi-card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; padding: 1.1rem 1.3rem; margin-bottom: 0.5rem; box-shadow: 0 1px 3px rgba(194, 24, 91, 0.05); }}
  .kpi-label {{ font-family: 'Space Mono', monospace; font-size: 0.6rem; letter-spacing: 0.15em; color: #b08a9e; text-transform: uppercase; margin-bottom: 0.3rem; }}
  .kpi-value {{ font-size: 1.6rem; font-weight: 700; color: #1f1119; line-height: 1; }}
  .kpi-sub {{ font-size: 0.75rem; color: {TEXT_MUTED}; margin-top: 0.3rem; }}
  .positive {{ color: {UP_GREEN}; }}
  .negative {{ color: {DOWN_RED}; }}
  .neutral  {{ color: {TEXT_MUTED}; }}
  .spotlight {{ background: linear-gradient(135deg, #ffffff 0%, #fdeef4 100%); border: 1px solid {BORDER}; border-radius: 14px; padding: 1.4rem 1.6rem; box-shadow: 0 2px 10px rgba(194, 24, 91, 0.08); margin-bottom: 0.5rem; }}
  .spotlight-name {{ font-size: 1.3rem; font-weight: 700; color: #1f1119; margin-bottom: 0.1rem; }}
  .spotlight-symbol {{ font-family: 'Space Mono', monospace; font-size: 0.7rem; letter-spacing: 0.12em; color: {BRAND_PINK}; text-transform: uppercase; margin-bottom: 1rem; }}
  .spotlight-price {{ font-size: 2.2rem; font-weight: 700; color: #1f1119; line-height: 1; }}
  .spotlight-ngn {{ font-size: 1rem; color: {TEXT_MUTED}; margin-top: 0.25rem; margin-bottom: 0.8rem; }}
  .stat-mini-label {{ font-family: 'Space Mono', monospace; font-size: 0.55rem; letter-spacing: 0.12em; color: #b08a9e; text-transform: uppercase; }}
  .stat-mini-value {{ font-size: 1.05rem; font-weight: 600; line-height: 1.3; }}
  .section-header {{ font-family: 'Space Mono', monospace; font-size: 0.65rem; letter-spacing: 0.2em; color: {BRAND_PINK}; text-transform: uppercase; border-bottom: 1px solid {BORDER}; padding-bottom: 0.5rem; margin-bottom: 1rem; margin-top: 2rem; }}
  hr {{ border-color: {BORDER}; }}
  #MainMenu {{ visibility: hidden; }}
  footer {{ visibility: hidden; }}
  header {{ visibility: hidden; }}
  .stDataFrame {{ background: {PANEL}; border-radius: 10px; }}
</style>
""", unsafe_allow_html=True)

# ── LIVE fetch from CoinGecko (runs on every page load) ───────────────────────

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"

@st.cache_data(ttl=120, show_spinner=False)  # cache 2 min so rapid reloads don't hammer the API
def fetch_live() -> pd.DataFrame:
    """Fetch top 50 coins in USD and NGN live, compute NGN premium. Returns a DataFrame."""
    params_usd = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 50,
                  "page": 1, "sparkline": False, "price_change_percentage": "1h,24h,7d"}
    params_ngn = {"vs_currency": "ngn", "order": "market_cap_desc", "per_page": 50,
                  "page": 1, "sparkline": False}

    usd = requests.get(COINGECKO_URL, params=params_usd, timeout=15)
    usd.raise_for_status()
    coins_usd = usd.json()

    ngn = requests.get(COINGECKO_URL, params=params_ngn, timeout=15)
    ngn.raise_for_status()
    coins_ngn = ngn.json()

    # implied USD/NGN rate via BTC in both currencies
    btc_usd = next((c["current_price"] for c in coins_usd if c["id"] == "bitcoin"), None)
    btc_ngn = next((c["current_price"] for c in coins_ngn if c["id"] == "bitcoin"), None)
    usd_ngn_rate = (btc_ngn / btc_usd) if (btc_usd and btc_ngn) else None

    ngn_lookup = {c["id"]: c["current_price"] for c in coins_ngn}

    rows = []
    for coin in coins_usd:
        cid = coin["id"]
        price_usd = coin["current_price"]
        price_ngn = ngn_lookup.get(cid)
        if price_ngn and price_usd and usd_ngn_rate:
            implied = price_usd * usd_ngn_rate
            premium = ((price_ngn - implied) / implied) * 100
        else:
            premium = None
        rows.append({
            "rank": coin["market_cap_rank"],
            "symbol": coin["symbol"].upper(),
            "name": coin["name"],
            "price_usd": price_usd,
            "price_ngn": price_ngn,
            "usd_ngn_rate": usd_ngn_rate,
            "ngn_premium_pct": round(premium, 4) if premium is not None else None,
            "market_cap_usd": coin["market_cap"],
            "volume_24h_usd": coin["total_volume"],
            "change_1h_pct": coin.get("price_change_percentage_1h_in_currency"),
            "change_24h_pct": coin.get("price_change_percentage_24h_in_currency"),
            "change_7d_pct": coin.get("price_change_percentage_7d_in_currency"),
        })
    return pd.DataFrame(rows)

# ── HISTORICAL snapshots from the Parquet file (built by GitHub Actions) ──────

DATA_PATH = Path("data/prices.parquet")

@st.cache_data(ttl=120, show_spinner=False)
def load_history() -> pd.DataFrame:
    if not DATA_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(DATA_PATH)
    df["snapshot_time"] = pd.to_datetime(df["snapshot_time"], utc=True)
    return df

# ── Load both sources ─────────────────────────────────────────────────────────

try:
    df_live = fetch_live()
    live_ok = True
except Exception as e:
    df_live = pd.DataFrame()
    live_ok = False
    live_error = str(e)

df_hist = load_history()

# If live failed, fall back to the newest historical snapshot so the page still works
if df_live.empty and not df_hist.empty:
    latest_time = df_hist["snapshot_time"].max()
    df_live = df_hist[df_hist["snapshot_time"] == latest_time].copy()

# Hard stop only if we have nothing at all
if df_live.empty:
    st.markdown('<p class="hero-label">System Status</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-title">Could not load market data.</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-sub">CoinGecko may be rate-limiting. Refresh in a minute.</p>', unsafe_allow_html=True)
    st.stop()

usd_ngn_rate = df_live["usd_ngn_rate"].iloc[0]
n_snapshots = df_hist["snapshot_time"].nunique() if not df_hist.empty else 0

# ── Helpers ───────────────────────────────────────────────────────────────────

def pct_color(v):
    if pd.isna(v): return TEXT_MUTED
    return UP_GREEN if v >= 0 else DOWN_RED

def pct_str(v):
    if pd.isna(v): return "—"
    return f"{v:+.2f}%"

def fmt_large(n):
    if pd.isna(n): return "—"
    if n >= 1e12: return f"${n/1e12:.2f}T"
    if n >= 1e9:  return f"${n/1e9:.1f}B"
    if n >= 1e6:  return f"${n/1e6:.1f}M"
    return f"${n:,.0f}"

# ── Hero header ────────────────────────────────────────────────────────────────

now_str = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

col_title, col_refresh = st.columns([5, 1])
with col_title:
    st.markdown('<p class="hero-label">Live Market Intelligence</p>', unsafe_allow_html=True)
    st.markdown('<h1 class="hero-title">Naira Crypto Pulse</h1>', unsafe_allow_html=True)
    source_note = "live from CoinGecko" if live_ok else "last saved snapshot (live feed retrying)"
    hist_note = f" · {n_snapshots} snapshots in history" if n_snapshots else ""
    st.markdown(
        f'<p class="hero-sub"><span class="live-dot"></span>Top 50 coins · USD vs NGN · '
        f'Fetched {now_str} ({source_note}){hist_note}</p>',
        unsafe_allow_html=True,
    )
with col_refresh:
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("↻ Refresh", width='stretch'):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# ── COIN SELECTOR + SPOTLIGHT ─────────────────────────────────────────────────

st.markdown('<div class="section-header">Coin Spotlight — Pick Any Coin</div>', unsafe_allow_html=True)

coin_options = (df_live.sort_values("rank")
                .apply(lambda r: f"{r['name']} ({r['symbol']})", axis=1).tolist())
default_index = next((i for i, l in enumerate(coin_options) if "(BTC)" in l), 0)

sel_col, _ = st.columns([2, 3])
with sel_col:
    chosen_label = st.selectbox("Select a coin to see its full stats", coin_options, index=default_index)

chosen_symbol = chosen_label.split("(")[-1].replace(")", "").strip()
coin = df_live[df_live["symbol"] == chosen_symbol].iloc[0]

spot_left, spot_right = st.columns([1, 2])
with spot_left:
    st.markdown(f"""
    <div class="spotlight">
      <div class="spotlight-name">{coin['name']}</div>
      <div class="spotlight-symbol">{coin['symbol']} · Rank #{int(coin['rank'])}</div>
      <div class="spotlight-price">${coin['price_usd']:,.4f}</div>
      <div class="spotlight-ngn">₦{coin['price_ngn']:,.2f}</div>
    </div>""", unsafe_allow_html=True)

with spot_right:
    r1c1, r1c2, r1c3 = st.columns(3)
    r2c1, r2c2, r2c3 = st.columns(3)
    with r1c1:
        st.markdown(f'<div class="kpi-card"><div class="stat-mini-label">1h Change</div><div class="stat-mini-value" style="color:{pct_color(coin["change_1h_pct"])}">{pct_str(coin["change_1h_pct"])}</div></div>', unsafe_allow_html=True)
    with r1c2:
        st.markdown(f'<div class="kpi-card"><div class="stat-mini-label">24h Change</div><div class="stat-mini-value" style="color:{pct_color(coin["change_24h_pct"])}">{pct_str(coin["change_24h_pct"])}</div></div>', unsafe_allow_html=True)
    with r1c3:
        st.markdown(f'<div class="kpi-card"><div class="stat-mini-label">7d Change</div><div class="stat-mini-value" style="color:{pct_color(coin["change_7d_pct"])}">{pct_str(coin["change_7d_pct"])}</div></div>', unsafe_allow_html=True)
    with r2c1:
        st.markdown(f'<div class="kpi-card"><div class="stat-mini-label">NGN Premium</div><div class="stat-mini-value" style="color:{pct_color(coin["ngn_premium_pct"])}">{pct_str(coin["ngn_premium_pct"])}</div></div>', unsafe_allow_html=True)
    with r2c2:
        st.markdown(f'<div class="kpi-card"><div class="stat-mini-label">Market Cap</div><div class="stat-mini-value" style="color:#1f1119">{fmt_large(coin["market_cap_usd"])}</div></div>', unsafe_allow_html=True)
    with r2c3:
        st.markdown(f'<div class="kpi-card"><div class="stat-mini-label">24h Volume</div><div class="stat-mini-value" style="color:#1f1119">{fmt_large(coin["volume_24h_usd"])}</div></div>', unsafe_allow_html=True)

st.markdown("---")

# ── MARKET-WIDE KPI row ───────────────────────────────────────────────────────

st.markdown('<div class="section-header">Market Overview</div>', unsafe_allow_html=True)
k1, k2, k3, k4 = st.columns(4)
market_cap_total = df_live["market_cap_usd"].sum()
avg_premium = df_live["ngn_premium_pct"].mean()
gainers = (df_live["change_24h_pct"] > 0).sum()
loser_count = 50 - gainers

with k1:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">USD / NGN Rate</div><div class="kpi-value">₦{usd_ngn_rate:,.0f}</div><div class="kpi-sub neutral">Implied from market</div></div>', unsafe_allow_html=True)
with k2:
    cls = "positive" if avg_premium >= 0 else "negative"
    sign = "+" if avg_premium >= 0 else ""
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Avg NGN Premium</div><div class="kpi-value {cls}">{sign}{avg_premium:.2f}%</div><div class="kpi-sub neutral">Across all 50 coins</div></div>', unsafe_allow_html=True)
with k3:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Total Market Cap</div><div class="kpi-value">{fmt_large(market_cap_total)}</div><div class="kpi-sub neutral">Top 50 combined (T = trillion)</div></div>', unsafe_allow_html=True)
with k4:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Market Breadth</div><div class="kpi-value"><span style="color:{UP_GREEN}">{gainers}↑</span> <span style="color:{DOWN_RED}">{loser_count}↓</span></div><div class="kpi-sub neutral">Gaining vs losing 24h</div></div>', unsafe_allow_html=True)

# ── Market overview table ──────────────────────────────────────────────────────

st.markdown('<div class="section-header">Market Snapshot — Top 50</div>', unsafe_allow_html=True)
cols_show = ["rank", "symbol", "name", "price_usd", "price_ngn", "ngn_premium_pct",
             "change_1h_pct", "change_24h_pct", "change_7d_pct", "market_cap_usd", "volume_24h_usd"]
display = df_live[cols_show].copy().sort_values("rank")
display.columns = ["Rank", "Symbol", "Name", "Price (USD)", "Price (NGN)", "NGN Premium %",
                   "1h %", "24h %", "7d %", "Market Cap", "Volume 24h"]

def color_pct(val):
    if pd.isna(val): return f"color: {TEXT_MUTED}"
    return f"color: {UP_GREEN}" if val >= 0 else f"color: {DOWN_RED}"

styled = (display.style
    .format({"Price (USD)": "${:,.4f}", "Price (NGN)": "₦{:,.2f}", "NGN Premium %": "{:+.2f}%",
             "1h %": "{:+.2f}%", "24h %": "{:+.2f}%", "7d %": "{:+.2f}%",
             "Market Cap": "${:,.0f}", "Volume 24h": "${:,.0f}"}, na_rep="—")
    .map(color_pct, subset=["NGN Premium %", "1h %", "24h %", "7d %"])
    .set_properties(**{"background-color": PANEL, "color": "#2b1d26", "border-color": BORDER}))

st.dataframe(styled, width='stretch', height=420, hide_index=True)

# ── NGN Premium chart ─────────────────────────────────────────────────────────

st.markdown('<div class="section-header">NGN Premium by Coin</div>', unsafe_allow_html=True)
st.caption("Positive = Nigerians paying above global USD-equivalent price. A signal of FX stress or local demand premium.")
premium_df = df_live[["symbol", "ngn_premium_pct"]].dropna().sort_values("ngn_premium_pct", ascending=False)
colors = [DATA_TEAL if v >= 0 else DATA_SLATE for v in premium_df["ngn_premium_pct"]]
fig_premium = go.Figure(go.Bar(
    x=premium_df["symbol"], y=premium_df["ngn_premium_pct"], marker_color=colors,
    text=[f"{v:+.2f}%" for v in premium_df["ngn_premium_pct"]], textposition="outside",
    textfont=dict(size=9, color=TEXT_MUTED)))
fig_premium.update_layout(
    paper_bgcolor=BG, plot_bgcolor=PANEL, font=dict(family="Space Grotesk", color=TEXT_MUTED, size=11),
    xaxis=dict(tickfont=dict(size=9), gridcolor=GRID),
    yaxis=dict(title="Premium %", gridcolor=GRID, zerolinecolor=ZEROLINE),
    margin=dict(l=0, r=0, t=10, b=0), height=320)
st.plotly_chart(fig_premium, width='stretch')

# ── Price history (from saved snapshots) ──────────────────────────────────────

if n_snapshots > 1:
    st.markdown('<div class="section-header">Price History — Compare Coins</div>', unsafe_allow_html=True)
    st.caption("Built from saved snapshots collected automatically over time.")
    top_symbols = df_live.sort_values("rank")["symbol"].head(20).tolist()
    selected = st.multiselect("Choose coins to compare", options=top_symbols, default=["BTC", "ETH", "BNB"])
    if selected:
        history = df_hist[df_hist["symbol"].isin(selected)][["snapshot_time", "symbol", "price_usd"]].copy()
        fig_line = px.line(history, x="snapshot_time", y="price_usd", color="symbol",
            color_discrete_sequence=[DATA_NAVY, DATA_TEAL, DATA_AMBER, DATA_SLATE, DATA_PLUM, "#0891b2"])
        fig_line.update_layout(
            paper_bgcolor=BG, plot_bgcolor=PANEL, font=dict(family="Space Grotesk", color=TEXT_MUTED, size=11),
            xaxis=dict(title="Time (UTC)", gridcolor=GRID), yaxis=dict(title="Price (USD)", gridcolor=GRID),
            legend=dict(bgcolor=PANEL, bordercolor=BORDER), margin=dict(l=0, r=0, t=10, b=0), height=360)
        st.plotly_chart(fig_line, width='stretch')
else:
    st.markdown('<div class="section-header">Price History — Compare Coins</div>', unsafe_allow_html=True)
    st.caption("Price-history charts appear here once a few snapshots have been collected in the background. "
               "The live data above is always current.")

# ── Scatter ───────────────────────────────────────────────────────────────────

st.markdown('<div class="section-header">Volume vs 24h Price Change</div>', unsafe_allow_html=True)
st.caption("Coins in the top-right quadrant (high volume, rising price) are seeing confirmed momentum.")
scatter_df = df_live[["symbol", "volume_24h_usd", "change_24h_pct", "market_cap_usd"]].dropna()
fig_scatter = px.scatter(scatter_df, x="change_24h_pct", y="volume_24h_usd", size="market_cap_usd",
    text="symbol", size_max=50, color="change_24h_pct",
    color_continuous_scale=[DATA_SLATE, "#cbd5e1", DATA_TEAL], range_color=[-15, 15])
fig_scatter.update_traces(textposition="top center", textfont=dict(size=9, color=TEXT_MUTED))
fig_scatter.update_layout(
    paper_bgcolor=BG, plot_bgcolor=PANEL, font=dict(family="Space Grotesk", color=TEXT_MUTED, size=11),
    xaxis=dict(title="24h Price Change %", gridcolor=GRID, zerolinecolor=ZEROLINE),
    yaxis=dict(title="24h Volume (USD)", gridcolor=GRID),
    coloraxis_showscale=False, margin=dict(l=0, r=0, t=10, b=0), height=400)
st.plotly_chart(fig_scatter, width='stretch')

# ── Footer ─────────────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown(
    f'<p style="font-family: Space Mono, monospace; font-size: 0.65rem; color: #b08a9e; text-align: center;">'
    'Built by Favour Jokparose · Live data: CoinGecko API · '
    '</p>', unsafe_allow_html=True)
