import os
import re
import random
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from bs4 import BeautifulSoup

# ==============================
# CONFIGURATION & CONSTANTS
# ==============================
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "da490jhr01qo2j87elqgda490jhr01qo2j87elr0")
NPR_STREAM_URL = "https://npr-ice.streamguys1.com/live.mp3"

GAINERS_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", 
    "NFLX", "INTC", "PLTR", "COIN", "MARA", "RIOT", "BABA", "SMCI"
]

TICKER_REGEX = re.compile(r'\$?([A-Z]{2,5})\b')
STOPWORDS = {"NEWS", "STOCK", "STOCKS", "JUMP", "SURGE", "FOR", "AND", "THE", "BUY", "NEW", "HIGH", "LOW"}

# Streamlit Page Setup for Mobile
st.set_page_config(
    page_title="Stock Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Shared Session for HTTP Calls
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})


# ==============================
# HELPER FUNCTIONS
# ==============================
@st.cache_data(ttl=60)
def fetch_single_quote(symbol):
    """Fetch live quote data for a symbol via Finnhub."""
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        resp = session.get(url, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            c, pc = float(data.get("c", 0)), float(data.get("pc", 0))
            if pc > 0:
                change_pct = ((c - pc) / pc) * 100
                return {"symbol": symbol, "price": c, "change_pct": change_pct}
    except Exception:
        pass
    return None

def fetch_top_gainers():
    """Fetch quotes concurrently for watchlist items."""
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(fetch_single_quote, GAINERS_WATCHLIST))
    
    valid_results = [r for r in results if r is not None]
    valid_results.sort(key=lambda x: x["change_pct"], reverse=True)
    return valid_results[:5]

@st.cache_data(ttl=300)
def fetch_earnings():
    """Fetch earnings calendar via Finnhub."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        url = f"https://finnhub.io/api/v1/calendar/earnings?from={today}&to={future}&token={FINNHUB_API_KEY}"
        resp = session.get(url, timeout=5)
        if resp.status_code == 200:
            calendar = resp.json().get("earningsCalendar", [])
            parsed = []
            for item in calendar[:8]:
                symbol = item.get("symbol", "")
                if symbol:
                    parsed.append({
                        "Symbol": symbol,
                        "Date": item.get("date", "Today"),
                        "Timing": "☀️ BMO" if item.get("hour") == "bmo" else ("🌙 AMC" if item.get("hour") == "amc" else "--"),
                        "Est. EPS": f"${item.get('epsEstimate'):.2f}" if item.get('epsEstimate') is not None else "--",
                        "Est. Rev": f"${item.get('revenueEstimate')/1e6:.1f}M" if item.get('revenueEstimate') is not None else "--"
                    })
            return parsed
    except Exception:
        pass
    return []

@st.cache_data(ttl=120)
def fetch_live_news():
    """Parse web headlines for stock symbols."""
    headlines = []
    try:
        url = "https://www.google.com/search?q=stocks+surge+jump+breaking+news"
        response = session.get(url, timeout=5)
        soup = BeautifulSoup(response.text, "html.parser")

        for h3 in soup.find_all('h3'):
            text = h3.get_text(strip=True)
            raw_matches = TICKER_REGEX.findall(text)
            tickers = [m for m in set(raw_matches) if m not in STOPWORDS]
            if tickers:
                headlines.append({"headline": text, "tickers": ", ".join(tickers)})
    except Exception:
        pass
    return headlines

def get_intraday_chart(symbol):
    """Generate a responsive dark-themed Plotly chart for mobile."""
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period="1d", interval="1m")
        if not df.empty:
            start_p, end_p = df['Close'].iloc[0], df['Close'].iloc[-1]
            color = "#30D158" if end_p >= start_p else "#FF453A"
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df.index, y=df['Close'],
                mode='lines',
                line=dict(color=color, width=2),
                hovertemplate="%{x|%I:%M %p}<br>$%{y:.2f}<extra></extra>"
            ))
            fig.update_layout(
                margin=dict(l=10, r=10, t=25, b=10),
                height=180,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False, visible=False),
                yaxis=dict(showgrid=True, gridcolor="#2C2C2E", font=dict(color="#8E8E93", size=10)),
                title=dict(text=f"{symbol} 1M Intraday (${end_p:.2f})", font=dict(size=12, color="#FFFFFF"))
            )
            return fig
    except Exception:
        pass
    return None


# ==============================
# UI HEADER & AUDIO STREAM
# ==============================
st.title("📈 Market Screener")

# Audio Player (Native HTML5 Works directly on iOS/Android browsers)
with st.expander("📻 NPR Live Audio Stream", expanded=False):
    st.audio(NPR_STREAM_URL, format="audio/mp3")

# Halted Stocks Status Banner
halted_sample = random.choice([["XYZ", "ABC"], ["FFIE", "MULN"], ["NONE"]])
halted_text = "NONE" if halted_sample == ["NONE"] else ", ".join(halted_sample)
st.error(f"🛑 **HALTED / SUSPENDED:** {halted_text}")

st.divider()

# ==============================
# MAIN SCREENER DASHBOARD
# ==============================
top_gainers = fetch_top_gainers()

if top_gainers:
    top_stock = top_gainers[0]
    st.subheader(f"⭐ Spotlight: {top_stock['symbol']}")
    
    col_metric, col_chart = st.columns([1, 2])
    with col_metric:
        st.metric(
            label=f"{top_stock['symbol']} Price", 
            value=f"${top_stock['price']:.2f}", 
            delta=f"+{top_stock['change_pct']:.2f}%"
        )
    with col_chart:
        fig = get_intraday_chart(top_stock['symbol'])
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

st.divider()

# Grid Layout for Mobile (Collapses into clean single column on narrow screens)
col1, col2 = st.columns(2)

with col1:
    st.subheader("🔥 Top Gainers")
    for item in top_gainers:
        st.write(f"**{item['symbol']}**: ${item['price']:.2f} (`+{item['change_pct']:.2f}%`)")
    
    st.subheader("📅 Earnings Calendar")
    earnings = fetch_earnings()
    if earnings:
        st.dataframe(pd.DataFrame(earnings), hide_index=True, use_container_width=True)
    else:
        st.caption("No upcoming earnings found.")

with col2:
    st.subheader("📰 Live News Feed")
    news_items = fetch_live_news()
    if news_items:
        for news in news_items[:5]:
            st.info(f"**{news['tickers']}**: {news['headline']}")
    else:
        st.caption("Searching live market news...")

# Manual Refresh Button
if st.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()