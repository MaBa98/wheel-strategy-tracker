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


from Browse import browse # Assicurati di importare lo strumento

@st.cache_data(ttl=86400) #  in cache per 1 giorno per non interrogare  BCE a ogni refresh
def fetch_risk_free_rate() -> float:
    """
    Recupera l'ultimo tasso €STR dalla pagina della BCE e lo converte in formato decimale.
    Esempio: "1.928" -> 0.01928
    """
    URL = "https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_short-term_rate/html/index.en.html"
    try:
        # Usa lo strumento di Browse per estrarre il dato testuale "Rate"
        rate_str = browse(query="Rate", url=URL)
        
        if rate_str:
            # Converte la stringa in un numero (float)
            rate_float = float(rate_str)
            # Converte la percentuale in formato decimale (es. 1.928 -> 0.01928)
            return rate_float / 100
        else:
            st.warning("Non è stato possibile recuperare il risk-free rate. Verrà usato un valore di default.")
            return 0.05 # Valore di fallback
            
    except Exception as e:
        st.error(f"Errore durante il recupero del risk-free rate: {e}")
        return 0.05 # Valore di fallback in caso di errore
