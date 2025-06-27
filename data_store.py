# data_store.py
import os
from uuid import uuid4
from supabase import create_client
import streamlit as st
from datetime import date, datetime
from typing import Dict, List

SUPA_URL = os.getenv("SUPABASE_URL", st.secrets["supabase"]["url"])
SUPA_KEY = os.getenv("SUPABASE_KEY", st.secrets["supabase"]["key"])
sb = create_client(SUPA_URL, SUPA_KEY)

def get_user_id() -> str:
    # per ora hard‐coded, poi sostituirai con sb.auth.user().id
    return "942224b5-a311-4408-adfe-91aed81c73370"

def _serialize_dates(obj: Dict) -> Dict:
    """Converti tutti i date/expiry in ISO string."""
    out = obj.copy()
    for k in ("date", "expiry"):
        if k in out and isinstance(out[k], (date, datetime)):
            out[k] = out[k].isoformat()
    return out

def fetch_trades() -> List[Dict]:
    resp = sb.table("trades") \
             .select("*") \
             .eq("user_id", get_user_id()) \
             .order("date", desc=False) \
             .execute()
    return resp.data or []

def upsert_trade(trade: Dict):
    trade = trade.copy()
    trade["user_id"] = get_user_id()
    trade.setdefault("id", str(uuid4()))
    trade = _serialize_dates(trade)
    sb.table("trades").upsert(trade).execute()

def fetch_cashflows() -> List[Dict]:
    resp = sb.table("cashflows") \
             .select("*") \
             .eq("user_id", get_user_id()) \
             .order("date", desc=False) \
             .execute()
    return resp.data or []

def upsert_cashflow(flow: Dict):
    flow = flow.copy()
    flow["user_id"] = get_user_id()
    flow.setdefault("id", str(uuid4()))
    flow = _serialize_dates(flow)
    sb.table("cashflows").upsert(flow).execute()


