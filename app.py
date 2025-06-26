import streamlit as st
import asyncio


from ui_components import ui_sidebar, main_view
from data_store import fetch_trades, fetch_cashflows
st.write("🔍 CWD:", os.getcwd())
st.write("🔍 files in root:", os.listdir("."))
if os.path.isdir(".streamlit"):
    st.write("🔍 files in .streamlit:", os.listdir(".streamlit"))
else:
    st.error("❌ Non trovo la cartella .streamlit qui!")
st.stop()
def initialize_session_state():
    if 'trades' not in st.session_state:
        st.session_state.trades = fetch_trades()
    if 'cash_flows' not in st.session_state:
        st.session_state.cash_flows = fetch_cashflows()
    if 'last_trade_count' not in st.session_state:
        st.session_state.last_trade_count = 0

def main():
    st.set_page_config(page_title="Wheel Strategy Tracker", layout="wide")
    initialize_session_state()
    ui_sidebar()
    main_view()

if __name__ == "__main__":
    main()
