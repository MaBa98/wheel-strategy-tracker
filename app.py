import os, streamlit as st
import asyncio
import pandas as pd

#from ui_components import ui_sidebar, main_view
from ui_components import login_view, ui_sidebar, main_view
from data_store import fetch_trades, fetch_cashflows


def main():
    st.set_page_config(page_title="Wheel Strategy Tracker", layout="wide")

    # 1) Se l'utente non è loggato, mostra la vista di login e ferma l'esecuzione
    if "user_id" not in st.session_state:
        login_view()
        return

    # 2) Se l'utente è loggato ma i suoi dati non sono ancora stati caricati, caricali ora.
    #    Questo blocco viene eseguito solo una volta dopo il login.
    if "trades" not in st.session_state:
        with st.spinner("Caricamento dati utente..."):
            st.session_state.trades = fetch_trades()
            st.session_state.cash_flows = fetch_cashflows()
            # Inizializza le altre variabili di stato necessarie
            st.session_state.last_trade_count = 0
            st.session_state.portfolio_history = pd.DataFrame()
            st.session_state.expired_options_log = pd.DataFrame()

    # 3) Se l'utente è loggato e i dati sono presenti, mostra l'app principale
    ui_sidebar()
    main_view()

if __name__ == "__main__":
    main()

