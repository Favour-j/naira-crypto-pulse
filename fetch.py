"""
============================================
Pulls top 50 coins (USD + NGN) from CoinGecko's free public API.
Appends each run as a new row-block to data/prices.parquet.
Run manually for now. GitHub Actions will schedule this later.

"""

import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
import time

# ── Config ────────────────────────────────────────────────────────────────────

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
DATA_PATH = Path("data/prices.parquet")

# CoinGecko gives us USD price. We'll fetch NGN separately.
NGN_RATE_URL = "https://api.coingecko.com/api/v3/simple/price"

PARAMS_USD = {
    "vs_currency": "usd",
    "order": "market_cap_desc",
    "per_page": 50,
    "page": 1,
    "sparkline": False,
    "price_change_percentage": "1h,24h,7d",
}

PARAMS_NGN = {
    "vs_currency": "ngn",
    "order": "market_cap_desc",
    "per_page": 50,
    "page": 1,
    "sparkline": False,
}

# ── Fetch ──────────────────────────────────────────────────────────────────────

def fetch_coins(params: dict) -> list[dict]:
    """Call CoinGecko markets endpoint. Returns list of coin dicts."""
    response = requests.get(COINGECKO_URL, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def fetch_usd_ngn_rate() -> float:
    """Get current USD/NGN rate via BTC priced in both currencies."""
    usd = requests.get(NGN_RATE_URL, params={"ids": "bitcoin", "vs_currencies": "usd"}, timeout=10).json()
    ngn = requests.get(NGN_RATE_URL, params={"ids": "bitcoin", "vs_currencies": "ngn"}, timeout=10).json()
    btc_usd = usd["bitcoin"]["usd"]
    btc_ngn = ngn["bitcoin"]["ngn"]
    return btc_ngn / btc_usd  # implied rate: 1 USD = X NGN


# ── Transform ──────────────────────────────────────────────────────────────────

def build_snapshot(coins_usd: list, coins_ngn: list, usd_ngn_rate: float) -> pd.DataFrame:
    """
    Merge USD and NGN data into a single flat DataFrame.
    Each row = one coin at one snapshot timestamp.
    """
    snapshot_time = datetime.now(timezone.utc)

    # Build NGN lookup: coin_id -> current_price in NGN
    ngn_lookup = {c["id"]: c["current_price"] for c in coins_ngn}

    rows = []
    for coin in coins_usd:
        coin_id = coin["id"]
        price_usd = coin["current_price"]
        price_ngn_market = ngn_lookup.get(coin_id)  # what CoinGecko shows in NGN

        # NGN Premium: how much more (%) does it cost in NGN vs USD-converted-to-NGN
        # Positive = Nigerian market pays a premium (common during FX stress)
        if price_ngn_market and price_usd and usd_ngn_rate:
            implied_ngn = price_usd * usd_ngn_rate
            ngn_premium_pct = ((price_ngn_market - implied_ngn) / implied_ngn) * 100
        else:
            ngn_premium_pct = None

        rows.append({
            "snapshot_time":        snapshot_time,
            "coin_id":              coin_id,
            "symbol":               coin["symbol"].upper(),
            "name":                 coin["name"],
            "rank":                 coin["market_cap_rank"],
            "price_usd":            price_usd,
            "price_ngn":            price_ngn_market,
            "usd_ngn_rate":         usd_ngn_rate,
            "ngn_premium_pct":      round(ngn_premium_pct, 4) if ngn_premium_pct is not None else None,
            "market_cap_usd":       coin["market_cap"],
            "volume_24h_usd":       coin["total_volume"],
            "change_1h_pct":        coin.get("price_change_percentage_1h_in_currency"),
            "change_24h_pct":       coin.get("price_change_percentage_24h_in_currency"),
            "change_7d_pct":        coin.get("price_change_percentage_7d_in_currency"),
            "ath_usd":              coin.get("ath"),
            "ath_change_pct":       coin.get("ath_change_percentage"),
        })

    return pd.DataFrame(rows)


# ── Store ──────────────────────────────────────────────────────────────────────

def append_to_parquet(df: pd.DataFrame, path: Path) -> None:
    """Append new snapshot to the running Parquet file."""
    if path.exists():
        existing = pd.read_parquet(path)
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df

    combined.to_parquet(path, index=False)
    print(f"  ✓ Saved {len(df)} rows → {path}  (total rows: {len(combined)})")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"\n[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}] Fetching snapshot...")

    print("  → Fetching USD prices...")
    coins_usd = fetch_coins(PARAMS_USD)
    time.sleep(2)

    print("  → Fetching NGN prices...")
    coins_ngn = fetch_coins(PARAMS_NGN)
    time.sleep(2)

    print("  → Fetching USD/NGN implied rate...")
    usd_ngn_rate = fetch_usd_ngn_rate()

    print("  → Building snapshot...")
    df = build_snapshot(coins_usd, coins_ngn, usd_ngn_rate)

    print("  → Writing to Parquet...")
    append_to_parquet(df, DATA_PATH)

    
    print("\n── Snapshot preview (top 5 by rank) ──────────────────────────────")
    preview = df[["rank", "symbol", "price_usd", "price_ngn", "ngn_premium_pct", "change_24h_pct"]].head()
    print(preview.to_string(index=False))
    print("──────────────────────────────────────────────────────────────────\n")


if __name__ == "__main__":
    main()
