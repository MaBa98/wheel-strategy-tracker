import yfinance as yf
import pandas as pd
from datetime import timedelta, date
import streamlit as st
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict

@st.cache_data(ttl=86400)
def fetch_symbol_data(symbol: str, start: date, end: date) -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    hist = ticker.history(start=start - timedelta(days=7),
                          end=end + timedelta(days=1))
    if hist.empty: return pd.DataFrame()
    hist.index = hist.index.tz_localize(None).date
    return hist[['Close']]

async def fetch_all_historical_data(symbols: List[str],
                                    start: date, end: date
                                   ) -> Dict[str, pd.DataFrame]:
    all_data = {}
    progress = st.progress(0)
    status = st.empty()
    with ThreadPoolExecutor(10) as ex:
        loop = asyncio.get_event_loop()
        tasks = [
          loop.run_in_executor(ex, fetch_symbol_data, sym, start, end)
          for sym in symbols
        ]
        for i, fut in enumerate(asyncio.as_completed(tasks)):
            df = await fut
            sym = symbols[i]
            if not df.empty:
                all_data[sym] = df
            progress.progress((i+1)/len(symbols))
            status.text(f"{i+1}/{len(symbols)}: {sym}")
    progress.empty(); status.empty()
    return all_data
