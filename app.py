import os, streamlit as st
import asyncio
import pandas as pd

#from ui_components import ui_sidebar, main_view
from ui_components import login_view, ui_sidebar, main_view
from data_store import fetch_trades, fetch_cashflows

def initialize_session_state():
    if 'trades' not in st.session_state:
        st.session_state.trades = fetch_trades()
    if 'cash_flows' not in st.session_state:
        st.session_state.cash_flows = fetch_cashflows()
    if 'last_trade_count' not in st.session_state:
        st.session_state.last_trade_count = 0
    if 'portfolio_history' not in st.session_state:
        st.session_state.portfolio_history = pd.DataFrame()
    if 'expired_options_log' not in st.session_state:
        st.session_state.expired_options_log = pd.DataFrame()

def main():
    st.set_page_config(page_title="Wheel Strategy Tracker", layout="wide")

    # 1) Se non ho user_id in sessione, vado su login
    if "user_id" not in st.session_state:
        login_view()
        return  # non carico sidebar o main_view finché non loggata/o

     # 2) Appena fatto login, carico trades e cash_flows
    if "trades" not in st.session_state or "cash_flows" not in st.session_state:
        initialize_session_state()
    
    # 3) Altrimenti proseguo
    ui_sidebar()
    main_view()

if __name__ == "__main__":
    main()
