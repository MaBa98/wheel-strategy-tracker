# data_store.py

import os
from uuid import uuid4
from datetime import date, datetime
from typing import Dict, List

import streamlit as st
from postgrest import APIError
from supabase import create_client

# ——————————————————————————————————————————————
# 1) Init Supabase client con env vars o st.secrets
# ——————————————————————————————————————————————
def _get_supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        sec = st.secrets.get("supabase", {})
        url = url or sec.get("url")
        key = key or sec.get("key")
    if not url or not key:
        raise RuntimeError(
            "Supabase credentials missing. "
            "Set SUPABASE_URL/KEY env vars or "
            "put them in .streamlit/secrets.toml under [supabase]."
        )
    return create_client(url, key)

sb = _get_supabase_client()


# ——————————————————————————————————————————————
# 2) Helper generici
# ——————————————————————————————————————————————
def get_user_id() -> str:
    # Temporaneo, finché non imposti auth
    return "942224b5-a311-4408-adfe-91aed81c7337"


def _serialize_dates(obj: Dict) -> Dict:
    out = obj.copy()
    for k in ("date", "expiry"):
        if k in out and isinstance(out[k], (date, datetime)):
            out[k] = out[k].isoformat()
    return out


# ——————————————————————————————————————————————
# 3) Fetch
# ——————————————————————————————————————————————

def fetch_trades() -> List[Dict]:
    try:
        resp = (
            sb.table("trades")
              .select("*")
              .order("date", desc=False)
              .execute()
        )
        rows = resp.data or []
        # ----- Aggiungi queste righe -----
        for r in rows:
            if isinstance(r.get("date"), str):
                r["date"] = date.fromisoformat(r["date"])
            if isinstance(r.get("expiry"), str) and r["expiry"]:
                r["expiry"] = date.fromisoformat(r["expiry"])
        return rows
    except APIError as e:
        st.error("❌ Supabase APIError in fetch_trades():")
        st.json(e.args[0])
        return []

def fetch_cashflows() -> List[Dict]:
    try:
        resp = (
            sb.table("cashflows")
              .select("*")
              .order("date", desc=False)
              .execute()
        )
        rows = resp.data or []
        # ----- Aggiungi queste righe -----
        for r in rows:
            # converte 'date'
            if isinstance(r.get("date"), str):
                r["date"] = date.fromisoformat(r["date"])
        return rows
    except APIError as e:
        st.error("❌ Supabase APIError in fetch_cashflows():")
        st.json(e.args[0])
        return []

# ——————————————————————————————————————————————
# 4) Upsert
# ——————————————————————————————————————————————
def upsert_trade(trade: Dict):
    record = trade.copy()
    record["user_id"] = get_user_id()
    record.setdefault("id", str(uuid4()))
    record = _serialize_dates(record)

    # Filtra solo i campi presenti nello schema public.trades
    allowed = {
        "id", "user_id", "date", "symbol", "type", "quantity",
        "strike", "expiry", "premium", "stock_price",
        "commission", "multiplier", "note"
    }
    record = {k: v for k, v in record.items() if k in allowed}

    try:
        sb.table("trades").upsert(record).execute()
    except APIError as e:
        st.error("❌ Supabase APIError in upsert_trade():")
        st.json(e.args[0])


def upsert_cashflow(flow: Dict):
    record = flow.copy()
    record["user_id"] = get_user_id()
    record.setdefault("id", str(uuid4()))
    record = _serialize_dates(record)

    # Filtra solo i campi presenti nello schema public.cashflows
    allowed = {"id", "user_id", "date", "amount", "note"}
    record = {k: v for k, v in record.items() if k in allowed}

    try:
        sb.table("cashflows").upsert(record).execute()
    except APIError as e:
        st.error("❌ Supabase APIError in upsert_cashflow():")
        st.json(e.args[0])


