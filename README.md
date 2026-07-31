# 💹 Naira Crypto Pulse

**A live crypto market dashboard tracking the price premium Nigerians pay for cryptocurrency versus the global market.**

🔗 **[View the live dashboard →](https://naira-crypto-pulse.streamlit.app/)**

---

## What this is

Most crypto dashboards show USD prices. For a Nigerian buyer, that's only half the story — the price you actually pay in Naira often sits *above* what the global dollar price would imply, because of FX restrictions, parallel-market rates, and local demand pressure.

**Naira Crypto Pulse measures that gap.** It tracks the top 50 cryptocurrencies in both USD and NGN, and surfaces a custom metric — the **NGN Premium** — that quantifies how much more (or less) Nigerians are paying relative to the global market. That premium widens under currency stress and narrows when conditions stabilise, making it a live economic signal that isn't published anywhere else.

---

## The signature metric: NGN Premium

```
NGN Premium % = ((Price in NGN − (Price in USD × implied USD/NGN rate))
                 ÷ (Price in USD × implied USD/NGN rate)) × 100
```

- **Positive** → Nigerians are paying above the global USD-equivalent price (a sign of FX stress or local demand).
- **Negative** → local prices sit below global parity (possible arbitrage or thin liquidity).

The USD/NGN rate itself is derived live from Bitcoin priced in both currencies, giving an implied market rate rather than an official one.

---

## Architecture

This project uses a **hybrid data model** so the dashboard is always current while still building a history over time:

| Layer | What it does | Tool |
|-------|--------------|------|
| **Live fetch** | Pulls top-50 prices (USD + NGN) the moment the page loads | CoinGecko API |
| **Background ingestion** | Snapshots the market on a schedule and appends to a running dataset | `fetch.py` + GitHub Actions |
| **Storage** | Columnar, fast-read historical store | Parquet |
| **Dashboard** | Interactive UI with a coin selector, KPIs, and charts | Streamlit + Plotly |
| **Hosting** | Free public URL, auto-deploys on every push | Streamlit Community Cloud |

**Why hybrid?** Live-on-load means the numbers are never stale — open the link and you see the current market. The scheduled snapshots run separately in the background to accumulate the price history that powers the trend charts.

---

## What the dashboard shows

- **Coin Spotlight** — pick any of the top 50 coins and see its full stats: USD/NGN price, 1h / 24h / 7d change, NGN premium, market cap, and volume.
- **Market Overview** — implied USD/NGN rate, average NGN premium across all 50 coins, total market cap, and market breadth (gainers vs losers).
- **Market Snapshot** — a full sortable table of all 50 coins.
- **NGN Premium by Coin** — the signature chart, ranking every coin by its local premium.
- **Price History** — compare price trajectories over time (built from accumulated snapshots).
- **Volume vs 24h Change** — a momentum scatter highlighting coins with confirmed moves.

---

## Tech stack

- **Python** — data fetching and transformation
- **pandas** — cleaning and shaping API responses
- **Streamlit** — the web app framework (no HTML/JS required)
- **Plotly** — interactive charts
- **CoinGecko API** — live market data (free, keyless)
- **GitHub Actions** — scheduled background ingestion
- **Parquet** — efficient columnar storage
- **Streamlit Community Cloud** — deployment

---

## Run it locally

```bash
# clone the repo
git clone https://github.com/Favour-j/naira-crypto-pulse.git
cd naira-crypto-pulse

# install dependencies
pip install -r requirements.txt

# (optional) collect a data snapshot
python fetch.py

# launch the dashboard
streamlit run dashboard.py
```

The app opens at `http://localhost:8501`.

---

## Repository structure

```
naira-crypto-pulse/
├── dashboard.py                    # the Streamlit app (live + historical)
├── fetch.py                        # market snapshot ingestion script
├── requirements.txt                # dependencies
├── data/
│   └── prices.parquet              # accumulated price snapshots
└── .github/
    └── workflows/
        └── fetch_schedule.yml      # scheduled background ingestion
```

---

## A note on how this was built

I scoped the architecture, chose the stack, designed the NGN Premium metric, and made the analytical decisions. I used AI (Claude by Anthropic) to accelerate the code I hadn't written before — the same way an analyst uses documentation or Stack Overflow. The thinking, the framing, and the choice of what to measure are my own.

---

**Built by Favour Jokparose** — Data Analyst,  🇳🇬
