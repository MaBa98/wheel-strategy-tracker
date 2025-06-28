from postgrest import APIError
import streamlit as st
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

def fetch_trades() -> List[Dict]:
    """
    Fa SELECT * su trades; cattura e mostra in chiaro 
    l’eventuale errore di PostgREST.
    """
    try:
        resp = sb.table("trades") \
                 .select("*") \
                 .eq("user_id", get_user_id()) \
                 .order("date", desc=False) \
                 .execute()
        return resp.data or []
    except APIError as e:
        err = e.args[0]  # questo è il dict JSON di PostgREST
        st.error("❌ Supabase APIError in fetch_trades():")
        st.json(err)     # lo stampi in pagina, così vedi tutto
        return []

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
