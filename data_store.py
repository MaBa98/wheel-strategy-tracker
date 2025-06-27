from supabase import create_client
from streamlit import secrets
from uuid import uuid4
from typing import List, Dict

# Inizializza client Supabase
sb = create_client(secrets["supabase"]["url"],
                   secrets["supabase"]["key"])

def get_user_id() -> str:
    # MOCK: in futuro usa sb.auth.user().id
    return "942224b5-a311-4408-adfe-91aed81c7337"

def fetch_trades() -> List[Dict]:
    resp = sb.table("trades") \
             .select("*") \
             .eq("user_id", get_user_id()) \
             .order("date", desc=False) \
             .execute()
    return resp.data or []

def upsert_trade(trade: Dict):
    trade["user_id"] = get_user_id()
    trade.setdefault("id", str(uuid4()))
    sb.table("trades").upsert(trade).execute()

def fetch_cashflows() -> List[Dict]:
    resp = sb.table("cashflows") \
             .select("*") \
             .eq("user_id", get_user_id()) \
             .order("date", desc=False) \
             .execute()
    return resp.data or []

def upsert_cashflow(flow: Dict):
    flow["user_id"] = get_user_id()
    flow.setdefault("id", str(uuid4()))
    sb.table("cashflows").upsert(flow).execute()
