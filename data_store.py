# data_store.py
import os
from uuid import uuid4
from supabase import create_client
import streamlit as st
from datetime import date, datetime
from typing import Dict, List
from postgrest import APIError


def _get_supabase_client():
    # 1) prova env vars
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    # 2) se mancano, prova st.secrets
    if not url or not key:
        sec = st.secrets.get("supabase", {})
        url = url or sec.get("url")
        key = key or sec.get("key")
    # 3) se ancora mancanti, fallisci
    if not url or not key:
        raise RuntimeError(
            "Supabase credentials not found. "
            "Set either environment variables SUPABASE_URL / SUPABASE_KEY "
            "or define them in .streamlit/secrets.toml (supabase.url, supabase.key)."
        )
    return create_client(url, key)

# soltanto qui costruiamo il client
sb = _get_supabase_client()


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
    """
    Fa SELECT * su trades; cattura e mostra in chiaro 
    l’eventuale errore di PostgREST.
    """
    try:
        resp = sb.table("trades")\
         .select("*")\
         .order("date", desc=False)\
         .execute()

        return resp.data or []
    except APIError as e:
        err = e.args[0]  # questo è il dict JSON di PostgREST
        st.error("❌ Supabase APIError in fetch_trades():")
        st.json(err)     # lo stampi in pagina, così vedi tutto
        return []

def upsert_trade(trade: Dict):
    # 1) copia e serializza date
    record = trade.copy()
    record["user_id"] = get_user_id()
    record.setdefault("id", str(uuid4()))
    record = _serialize_dates(record)

    # 2) tieni solo i campi che la tabella trades si aspetta
    allowed = {
        "id","user_id","date","symbol","type","quantity",
        "strike","expiry","premium","stock_price",
        "commission","multiplier","note"
    }
    record = {k: v for k, v in record.items() if k in allowed}

    # 3) invia il JSON “pulito” a Supabase
    sb.table("trades").upsert(record).execute()

def fetch_cashflows() -> List[Dict]:
    """
    Fa SELECT * su trades; cattura e mostra in chiaro 
    l’eventuale errore di PostgREST.
    """
    try:
        resp = sb.table("cashflows")\
         .select("*")\
         .order("date", desc=False)\
         .execute()

        return resp.data or []
    except APIError as e:
        err = e.args[0]  # questo è il dict JSON di PostgREST
        st.error("❌ Supabase APIError in fetch_cashflows():")
        st.json(err)     # lo stampi in pagina, così vedi tutto
        return []

def upsert_cashflow(flow: Dict):
    # 1) Copia e serializza le date
    record = flow.copy()
    record["user_id"] = get_user_id()
    record.setdefault("id", str(uuid4()))
    record = _serialize_dates(record)

    # 2) Tieni solo i campi che esistono veramente in public.cashflows
    allowed = {"id", "user_id", "date", "amount", "note"}
    record = {k: v for k, v in record.items() if k in allowed}

    # 3) Esegui l’upsert sul “record” “pulito”
    try:
        sb.table("cashflows").upsert(record).execute()
    except APIError as e:
        st.error("❌ Supabase APIError in upsert_cashflow():")
        st.json(e.args[0])
