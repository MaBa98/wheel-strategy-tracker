from postgrest import APIError
import requests
from bs4 import BeautifulSoup
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

def fetch_price_series(
    ticker: str,
    start: date,
    end: date
) -> pd.Series:
    """
    Scarica da Yahoo Finance la serie dei prezzi di chiusura 
    adjusted per `ticker` fra start (incluso) ed end (escluso).
    Ritorna pd.Series indexed by date.
    """
    df = yf.Ticker(ticker).history(
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=True
    )
    # se non ci sono dati, ritorna serie vuota
    if df.empty:
        return pd.Series(dtype=float)
    return df["Close"].rename(ticker)

@st.cache_data(ttl=86400) # Mettiamo in cache per 1 giorno
def fetch_risk_free_rate() -> float:
    """
    Recupera l'ultimo tasso €STR dalla pagina della BCE usando requests e BeautifulSoup,
    e lo converte in formato decimale.
    """
    URL = "https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_short-term_rate/html/index.en.html"
    
    # È buona norma usare un User-Agent per sembrare un browser reale
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        # Esegui la richiesta GET per ottenere il contenuto HTML della pagina
        response = requests.get(URL, headers=headers)
        response.raise_for_status()  # Genera un errore se la richiesta fallisce (es. 404, 500)

        # Crea un oggetto BeautifulSoup per parsare l'HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # Trova l'elemento <dd> con la classe 'value' che contiene il tasso.
        # Questa è la parte cruciale che dipende dalla struttura della pagina HTML.
        rate_element = soup.find('dd', class_='value')

        if rate_element:
            rate_str = rate_element.get_text(strip=True)
            rate_float = float(rate_str)
            return rate_float / 100  # Converte in decimale
        else:
            st.warning("Non è stato possibile trovare l'elemento del risk-free rate nella pagina. Verrà usato un valore di default.")
            return 0.05  # Fallback

    except requests.exceptions.RequestException as e:
        st.error(f"Errore di rete durante il recupero del risk-free rate: {e}")
        return 0.05  # Fallback
    except Exception as e:
        st.error(f"Errore imprevisto durante il recupero del risk-free rate: {e}")
        return 0.05  # Fallback
    except Exception as e:
        st.error(f"Errore durante il recupero del risk-free rate: {e}")
        return 0.05 # Valore di fallback in caso di errore
