import os, streamlit as st
import asyncio
import pandas as pd

#from ui_components import ui_sidebar, main_view
from ui_components import login_view, ui_sidebar, main_view
from data_store import fetch_trades, fetch_cashflows

# ---------- Inject custom CSS ----------
st.markdown("""
<style>
/* Typography */
html, body, [class*="css"]  {
  font-family: 'Inter', sans-serif;
}

/* Card container */
.card {
  background-color: var(--secondary-background-color);
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  margin-bottom: 1.5rem;
}
.card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 20px rgba(0,0,0,0.12);
}

/* Buttons */
.stButton>button {
  background-color: var(--primary-color);
  color: white;
  border-radius: 8px;
  padding: 0.6rem 1.2rem;
  font-weight: 600;
  transition: background-color .2s ease;
}
.stButton>button:hover {
  background-color: darken(var(--primary-color), 10%);
}

/* Tables */
.dataframe, .stDataFrame>div>div>div>table {
  border-radius: 8px;
  overflow: hidden;
}
.dataframe th, .dataframe td {
  padding: 0.5rem 0.8rem;
}
.dataframe tr:nth-child(even) { background: rgba(0,0,0,0.03); }

/* Fixed header */
.header {
  position: fixed;
  top: 0; left: 0; right: 0;
  background-color: var(--secondary-background-color);
  padding: 1rem 2rem;
  z-index: 1000;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.content { margin-top: 5rem; }

/* Responsive tweaks */
@media (max-width: 768px) {
  .card { padding: 1rem; }
  .stButton>button { width: 100%; }
}
</style>
""", unsafe_allow_html=True)

# ---------- Fixed header with logo ----------
st.markdown("""
<div class="header">
  <img src="https://your-cdn.com/logo.png" width="32px" 
       style="vertical-align:middle; margin-right:8px;">
  <span style="font-size:1.5rem; font-weight:600;">Wheel Strategy Tracker</span>
</div>
<div class="content">
""", unsafe_allow_html=True)

# Alla fine di app.py chiudi il div.content:
# st.markdown("</div>", unsafe_allow_html=True)


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

# st.markdown("</div>", unsafe_allow_html=True)
