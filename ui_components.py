# ui_components.py

import streamlit as st
import asyncio
import pandas as pd
import plotly.graph_objects as go

from data_store import upsert_trade, upsert_cashflow
from data_store import find_user_by_email, create_user
from portfolio import PortfolioProcessor
from datetime import date
from data_fetcher import fetch_price_series

def classify_pos(x):
    try:
        return 'SHORT' if x < 0 else 'LONG'
    except Exception:
        return None

def login_view():
    st.title("👋 Benvenuto")
    st.write("Per favore inserisci la tua email per continuare.")

    email = st.text_input("Email", placeholder="nome@dominio.com")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔑 Sono un utente esistente"):
            if not email:
                st.error("Inserisci un’email valida.")
            else:
                uid = find_user_by_email(email)
                if uid:
                    st.session_state.user_id = uid
                    #st.experimental_rerun()
                else:
                    st.error("Email non trovata. Prova a registrarti qui sotto.")

    with col2:
        if st.button("🆕 Nuova registrazione"):
            if not email:
                st.error("Inserisci un’email valida.")
            else:
                # se esiste già, avvisa, altrimenti crea
                if find_user_by_email(email):
                    st.warning("Questa email esiste già, prova a loggare.")
                else:
                    uid = create_user(email)
                    st.success("Registrazione avvenuta! Benvenuto 🎉")
                    st.session_state.user_id = uid
                    #st.experimental_rerun()

def ui_sidebar():
    """Disegna la sidebar per l’inserimento dei dati e il reset."""
    with st.sidebar:
        st.header("⚙️ Inserimento Dati")

        tab1, tab2, tab3 = st.tabs(["📈 Azioni", "📊 Opzioni", "💰 Flussi"])

        # ——————————————————————————————
        # TAB 1: Trade Azioni
        # ——————————————————————————————
        with tab1:
            with st.form("stock_trade_form", clear_on_submit=True):
                st.subheader("Trade Azioni")
                symbol = st.text_input("Simbolo (Ticker)", "SPY").upper()
                trade_date = st.date_input("Data Trade", value=pd.Timestamp.today().date())
                op_type = st.radio("Operazione", ["Acquisto", "Vendita"], horizontal=True)
                qty = st.number_input("Quantità Azioni", min_value=1, step=1)
                price = st.number_input("Prezzo per Azione", min_value=0.01, step=0.01, format="%.2f")
                commission = st.number_input("Commissioni ($)", value=1.50, min_value=0.0, step=0.5)

                final_qty = qty if op_type == "Acquisto" else -qty

                submitted = st.form_submit_button("➕ Aggiungi Trade Azioni")
                if submitted:
                    trade = {
                        "date": trade_date,
                        "symbol": symbol,
                        "type": "stock",
                        "quantity": final_qty,
                        "stock_price": price,
                        "commission": commission,
                        "expiry": trade_date,
                        "strike": 0.0,
                        "premium": 0.0,
                        "multiplier": 1,
                        "note": ""
                    }
                    upsert_trade(trade)
                    st.session_state.trades.append(trade)
                    st.success("✅ Trade Azioni salvato!")

        # ——————————————————————————————
        # TAB 2: Trade Opzioni
        # ——————————————————————————————
        with tab2:
            sub1, sub2 = st.tabs(["🔄 Opzioni Attive", "⏰ Opzioni Scadute"])

            # Opzioni Attive
            with sub1:
                with st.form("active_options_form", clear_on_submit=True):
                    st.subheader("Trade Opzioni Attive")
                    symbol = st.text_input("Simbolo (Ticker)", "SPY", key="act_symbol").upper()
                    trade_date = st.date_input("Data Trade", value=pd.Timestamp.today().date(), key="act_date")
                    op_side = st.radio("Operazione", ["Vendita (Short)", "Acquisto (Long)"], horizontal=True, key="act_side")
                    opt_type = st.selectbox("Tipo Opzione", ["put", "call"], key="act_type")
                    contracts = st.number_input("Numero Contratti", min_value=1, step=1, key="act_qty")
                    strike = st.number_input("Strike ($)", min_value=0.01, step=0.01, format="%.2f", key="act_strike")
                    expiry = st.date_input("Scadenza", min_value=pd.Timestamp.today().date() + pd.Timedelta(days=1), key="act_expiry")
                    premium_pp = st.number_input("Premio (per azione)", min_value=0.01, step=0.01, format="%.2f", key="act_prem")
                    multiplier = st.number_input("Moltiplicatore", min_value=1, value=100, key="act_mult")
                    commission = st.number_input("Commissioni ($)", value=1.50, min_value=0.0, step=0.5, key="act_comm")

                    total_prem = premium_pp * contracts * multiplier
                    st.info(f"Premio Totale: ${total_prem:,.2f}")

                    final_qty = -contracts if op_side.startswith("Vendita") else contracts

                    submitted = st.form_submit_button("➕ Aggiungi Opzione Attiva")
                    if submitted:
                        trade = {
                            "date": trade_date,
                            "symbol": symbol,
                            "type": opt_type,
                            "quantity": final_qty,
                            "strike": strike,
                            "expiry": expiry,
                            "premium": total_prem,
                            "commission": commission,
                            "stock_price": 0.0,
                            "multiplier": multiplier,
                            "note": ""
                        }
                        upsert_trade(trade)
                        st.session_state.trades.append(trade)
                        st.success("✅ Opzione Attiva salvata!")

            # Opzioni Scadute
            with sub2:
                with st.form("expired_options_form", clear_on_submit=True):
                    st.subheader("Trade Opzioni Scadute")
                    st.info("⚠️ Per opzioni già scadute: outcome calcolato automaticamente")
                    symbol = st.text_input("Ticker", "SPY", key="exp_symbol").upper()
                    trade_date = st.date_input("Data Apertura", value=pd.Timestamp.today().date() - pd.Timedelta(days=30), key="exp_date")
                    expiry = st.date_input("Data Scadenza", max_value=pd.Timestamp.today().date(), key="exp_expiry")
                    op_side = st.radio("Operazione", ["Vendita (Short)", "Acquisto (Long)"], horizontal=True, key="exp_side")
                    opt_type = st.selectbox("Tipo", ["put", "call"], key="exp_type")
                    contracts = st.number_input("Contratti", min_value=1, step=1, key="exp_qty")
                    strike = st.number_input("Strike", min_value=0.01, step=0.01, format="%.2f", key="exp_strike")
                    premium_pp = st.number_input("Premio Originale", min_value=0.01, step=0.01, format="%.2f", key="exp_prem")
                    multiplier = st.number_input("Moltiplicatore", min_value=1, value=100, key="exp_mult")
                    commission = st.number_input("Commissioni ($)", value=1.50, min_value=0.0, step=0.5, key="exp_comm")
                    was_assigned = st.checkbox("Assegnata?", key="exp_assigned")
                    if was_assigned:
                        st.warning("Ricorda: aggiungi il trade di azioni risultante dall'assegnazione.")
                    total_prem = premium_pp * contracts * multiplier
                    st.info(f"Premio Totale: ${total_prem:,.2f}")

                    final_qty = -contracts if op_side.startswith("Vendita") else contracts

                    submitted = st.form_submit_button("➕ Aggiungi Opzione Scaduta")
                    if submitted:
                        trade = {
                            "date": trade_date,
                            "symbol": symbol,
                            "type": opt_type,
                            "quantity": final_qty,
                            "strike": strike,
                            "expiry": expiry,
                            "premium": total_prem,
                            "commission": commission,
                            "stock_price": 0.0,
                            "multiplier": multiplier,
                            "was_assigned": was_assigned,
                            "note": ""
                        }
                        upsert_trade(trade)
                        st.session_state.trades.append(trade)
                        msg = "✅ Opzione Scaduta salvata!"
                        if was_assigned:
                            msg += " ⚠️ Aggiungi il trade di azioni!"
                        st.success(msg)

        # ——————————————————————————————
        # TAB 3: Flussi di Cassa
        # ——————————————————————————————
        with tab3:
            with st.form("cash_flow_form", clear_on_submit=True):
                st.subheader("Flussi di Cassa")
                flow_type = st.radio("Tipo", ["💰 Deposito", "💸 Prelievo"], horizontal=True)
                amount = st.number_input("Importo ($)", min_value=0.01, format="%.2f")
                flow_date = st.date_input("Data", value=pd.Timestamp.today().date())
                note = st.text_input("Nota (opzionale)")

                submitted = st.form_submit_button("➕ Aggiungi Flusso")
                if submitted:
                    amt = amount if flow_type == "💰 Deposito" else -amount
                    flow = {"date": flow_date, "amount": amt, "note": note or ""}
                    upsert_cashflow(flow)
                    st.session_state.cash_flows.append(flow)
                    st.success("✅ Flusso di cassa salvato!")

        st.markdown("---")
        if st.button("🔄 Resetta Sessione", type="secondary"):
            st.session_state.clear()
            st.experimental_rerun()
        if st.button("Logout"):
            del st.session_state["user_id"]
            st.experimental_rerun()


def main_view():
    """Disegna la vista principale con grafici, KPI e tabelle."""
    st.title("📖 Position Keeper")

    # Pulsanti per refresh e ricalcolo
    col1, col2, _ = st.columns([1, 1, 4])
    with col1:
        if st.button("🔄 Refresh Dati", type="secondary"):
            st.session_state.last_trade_count = -1
            #st.experimental_rerun()
    with col2:
        if st.button("📊 Ricalcola Tutto", type="primary"):
            st.session_state.portfolio_history = pd.DataFrame()
            st.session_state.expired_options_log = pd.DataFrame()
            st.session_state.last_trade_count = -1
            #st.experimental_rerun()

    processor = PortfolioProcessor(
        st.session_state.trades,
        st.session_state.cash_flows
    )
    
    # Controllo se serve ricalcolare lo storico
    trade_count = len(st.session_state.trades) + len(st.session_state.cash_flows)
    if trade_count != st.session_state.last_trade_count:
        with st.spinner("Elaborazione… il primo calcolo può richiedere tempo"):
            processor = PortfolioProcessor(
                st.session_state.trades,
                st.session_state.cash_flows
            )
            history, expired_log = asyncio.run(processor.build_full_history())
            st.session_state.portfolio_history = history
            st.session_state.expired_options_log = expired_log
            st.session_state.last_trade_count = trade_count

    history_df = st.session_state.portfolio_history
    expired_log_df = st.session_state.expired_options_log

    if history_df.empty:
        st.info("Aggiungi almeno un trade o un flusso di cassa nella sidebar.")
        return
    

    # — KPI PRINCIPALI —
    st.header("📈 Dashboard Principale")
    metrics = processor.calculate_performance_metrics(history_df)
    latest = history_df.iloc[-1]

    cols = st.columns(8)
    cols[0].metric("Portafoglio", f"${latest['portfolio_value']:,.2f}")
    cols[1].metric("P&L Totale", f"${metrics['Total P&L']:,.2f}") #f"{metrics['Total Return %']:.2f}%"
    cols[2].metric("TWR", f"{metrics.get('TWR',0):.2f}%", f"Ann: {metrics.get('Annualized TWR',0):.2f}%")
    cols[3].metric("Sharpe-TWR", f"{metrics.get('TWR Sharpe Ratio',0):.2f}")
    cols[4].metric("Sortino", f"{metrics['Sortino Ratio']:.2f}")
    cols[5].metric("VaR 95%", f"${metrics['VaR 95% ($)']:.2f}")
    cols[6].metric("Commissioni", f"${metrics['Total Commissions $']:.2f}", f"{metrics['Comm Impact %']:.2f}%")
    cols[7].metric("Max DD", f"${metrics['Max Drawdown $']:.2f}", f"{metrics['Max DD Duration (days)']}d")

    st.markdown("---")

    # ── Benchmark Performance ────────────────────────────────────────────
    st.markdown("### 📈 Benchmark Performance")
    bench_ticker = st.text_input("Simbolo (Ticker)", "SPY").upper()
    
    # Calcolo date
    all_dates = []
    for t in st.session_state.trades:
        all_dates.append(t["date"])
    for cf in st.session_state.cash_flows:
        all_dates.append(cf["date"])
    if all_dates and isinstance(all_dates[0], str):
        all_dates = [pd.to_datetime(d).date() for d in all_dates]
    start_date = min(all_dates) if all_dates else date.today()
    end_date = date.today()
    
    # Fetch benchmark
    with st.spinner(f"Scarico {bench_ticker} da {start_date} a oggi…"):
        prices = fetch_price_series(bench_ticker, start_date, end_date)
    
    if prices.empty:
        st.warning("Nessun dato restituito per il benchmark in questo intervallo.")
    else:
        # Calcolo rendimenti benchmark
        p0 = float(prices.iloc[0])
        p1 = float(prices.iloc[-1])
        bench_ret = (p1 - p0) / p0
        bench_cumret = (prices / p0 - 1) * 100  # in percentuale
        
        # Calcolo TWR del portafoglio normalizzato alle date del benchmark
        if not history_df.empty:
            # Filtra history_df per le date disponibili nel benchmark
            history_subset = history_df[
                (history_df['date'] >= prices.index[0].date()) & 
                (history_df['date'] <= prices.index[-1].date())
            ].copy()
            
            if not history_subset.empty:
                # Usa     lo stesso metodo TWR della dashboard principale
                portfolio_twr_data = processor.calculate_twr_daily_returns(history_subset, st.session_state.cash_flows)
                
                # Calcola TWR cumulativo dalle daily returns
                if portfolio_twr_data:
                    portfolio_twr_cumulative = pd.Series(portfolio_twr_data).add(1).cumprod().sub(1).mul(100)
                    portfolio_twr_cumulative.index = history_subset['date'].iloc[1:len(portfolio_twr_cumulative)+1]
                else:
                    portfolio_twr_cumulative = pd.Series([0], index=[history_subset['date'].iloc[0]])
                
        # Visualizzazione con grafici side-by-side
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.metric(
                label=f"Rendimento {bench_ticker}",
                value=f"{bench_ret*100:.2f}%",
                help=f"Da {start_date} a {end_date}"
            )
            if not history_df.empty and 'portfolio_twr' in locals():
                portfolio_final_twr = portfolio_twr_cumulative.iloc[-1] if len(portfolio_twr_cumulative) > 0 else 0
                st.metric(
                    label="TWR Portafoglio",
                    value=f"{portfolio_final_twr:.2f}%",
                    delta=f"{portfolio_final_twr - bench_ret*100:.2f}% vs {bench_ticker}",
                    help="Time-Weighted Return del portafoglio"
                )
        
        with col2:
            # Grafico combinato
            fig_bench = go.Figure()
            
            # Benchmark
            fig_bench.add_trace(go.Scatter(
                x=prices.index,
                y=bench_cumret,
                name=f"{bench_ticker} Return",
                line=dict(color='blue', width=2)
            ))
            
            # TWR Portafoglio (se disponibile)
            if not history_df.empty and 'portfolio_twr_cumulative' in locals() and len(portfolio_twr_cumulative) > 0:
                fig_bench.add_trace(go.Scatter(
                    x=portfolio_twr_cumulative.index,
                    y=portfolio_twr_cumulative.values,
                    name="Portfolio TWR",
                    line=dict(color='green', width=2)
                ))
            
            fig_bench.update_layout(
                title=f"Confronto Performance: {bench_ticker} vs Portfolio TWR",
                yaxis_title="Rendimento Cumulativo (%)",
                xaxis_title="Data",
                template='plotly_white',
                height=300
            )
            
            st.plotly_chart(fig_bench, use_container_width=True)
    st.markdown("---")
    
    # — GRAFICI DI PERFORMANCE —
    with st.expander("Grafici di Performance", expanded=True):
        st.subheader("Andamento Portafoglio & P&L")
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=history_df['date'], y=history_df['portfolio_value'],
            name="Valore Totale", line=dict(color='royalblue', width=2)))
        fig1.add_trace(go.Scatter(
            x=history_df['date'], y=history_df['cumulative_cash_flow'],
            name="Capitale Investito", line=dict(color='grey', dash='dash')))
        fig1.add_trace(go.Scatter(
            x=history_df['date'], y=history_df['cash_balance'],
            name="Liquidità", line=dict(color='green', width=1)))
        fig1.add_trace(go.Scatter(
            x=history_df['date'], y=history_df['stock_value'],
            name="Azioni", line=dict(color='orange', width=1)))
        fig1.add_trace(go.Scatter(
            x=history_df['date'], y=history_df['options_value'],
            name="Opzioni", line=dict(color='red', width=1)))
        fig1.update_layout(template='plotly_white',
                           title="Composizione Portafoglio nel Tempo",
                           yaxis_title="$")
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=history_df['date'], y=history_df['equity_line_pnl'],
            name="Equity Line", line=dict(color='green'), fill='tozeroy'))
        fig2.update_layout(template='plotly_white',
                           title="Equity Line (P&L Cumulativo)",
                           yaxis_title="$")
        st.plotly_chart(fig2, use_container_width=True)

    # — TWR vs MWR —
    #with st.expander("📊 Analisi Time-Weighted Return (TWR)", expanded=False):
        #st.subheader("TWR vs MWR")
        #c1, c2 = st.columns(2)
        #with c1:
            #st.metric("TWR", f"{metrics.get('TWR',0):.2f}%")
            #st.metric("TWR Ann.", f"{metrics.get('Annualized TWR',0):.2f}%")
        #with c2:
            #st.metric("MWR (Total Return)", f"{metrics['Total Return %']:.2f}%")
            #diff = metrics.get('TWR',0) - metrics['Total Return %']
            #st.metric("Diff TWR-MWR", f"{diff:.2f}%")
        #if len(history_df) > 1:
            #fig_twr = go.Figure()
            #cum_twr = (1 + history_df['portfolio_value'].pct_change().fillna(0)).cumprod() - 1
            #fig_twr.add_trace(go.Scatter(
                #x=history_df['date'], y=cum_twr*100,
                #name="TWR Approssimato", line=dict(color='blue')))
            #fig_twr.add_trace(go.Scatter(
                #x=history_df['date'],
                #y=(history_df['equity_line_pnl']/history_df['cumulative_cash_flow'].abs())*100,
                #name="MWR", line=dict(color='red', dash='dash')))
            #fig_twr.update_layout(template='plotly_white',
                                  #title="Confronto TWR vs MWR",
                                  #yaxis_title="Return %")
            #st.plotly_chart(fig_twr, use_container_width=True)

    # — METRICHE DI RISCHIO —
    with st.expander("🔬 Analisi Quantitativa", expanded=False):
        st.subheader("Rischio & Rendimento")
        m = metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Sharpe", f"{m['TWR Sharpe Ratio']:.2f}") #c1.metric("Sharpe", f"{metrics.get('TWR Sharpe Ratio',0):.2f}")
        c1.metric("Sortino", f"{m['Sortino Ratio']:.2f}")
        c2.metric("VaR 95%", f"${m['VaR 95% ($)']:.2f}")
        c2.metric("Max Drawdown", f"${m['Max Drawdown $']:.2f}")
        c3.metric("Durata DD", f"{m['Max DD Duration (days)']}d")
        c3.metric("Comm Impact", f"{m['Comm Impact %']:.2f}%")

        st.markdown("**Breakdown P&L per Symbol**")
        st.table(pd.DataFrame.from_dict(m['P&L per Symbol'], orient='index', columns=['P&L $']))

        st.markdown("**Breakdown P&L per Strategy**")
        st.table(pd.DataFrame.from_dict(m['P&L per Strategy'], orient='index', columns=['P&L $']))

    #  — CONTRIBUTO PER SIMBOLO —
    #with st.expander("Contibuto per Simbolo", expanded=False):
        #st.subheader("Contributi P&L per sottostante")
        #contrib_df = PortfolioProcessor.compute_contributions(
            #st.session_state.trades
        #)
        # Tabella e bar chart side-by-side
        #col1, col2 = st.columns(2)
        #with col1:
            #st.dataframe(contrib_df, use_container_width=True)
        #with col2:
            #st.bar_chart(
                #data=contrib_df.set_index('symbol')['pct_of_total'],
                #use_container_width=True
            #)
        #st.caption("Percentuale di contributo di ciascun sottostante sul P&L totale.")

    
    # — POSIZIONI CORRENTI —
    with st.expander("Dettaglio Posizioni Aperte", expanded=False):
        st.subheader("Posizioni Attuali")
        from data_store import fetch_trades  # per ricaricare fresh se vuoi
        # Azioni
        pos_df = pd.DataFrame.from_dict(
            PortfolioProcessor.get_current_positions(st.session_state.trades)[0],
            orient='index'
        ).reset_index()
        pos_df.columns = ['Simbolo', 'Quantità']
        st.write("**Azioni:**")
        if not pos_df.empty:
            st.dataframe(pos_df[pos_df['Quantità'] != 0], use_container_width=True)
        else:
            st.info("Nessuna azione in portafoglio.")

        # Opzioni
        opts = PortfolioProcessor.get_current_positions(st.session_state.trades)[1]
        st.write("**Opzioni Aperte:**")
        if opts:
            opts_df = pd.DataFrame(opts)
            # colonne che vorresti mostrare
            cols = ['symbol', 'type', 'posizione', 'quantity', 'strike', 'expiry', 'premium']
            
            # per ogni colonna mancante in opts_df, aggiungila con valori None
            for c in cols:
                if c not in opts_df.columns:
                    opts_df[c] = None
            if 'expiry' in opts_df.columns:
                # solo se esiste, converte la colonna in ISO string
                opts_df['expiry'] = (
                    pd.to_datetime(opts_df['expiry'], errors='coerce')
                      .dt.strftime('%Y-%m-%d')
                )
            else:
                # se manca, creala vuota o con valori NaN a piacere
                opts_df['expiry'] = None
            if 'quantity' in opts_df.columns:
                opts_df['posizione'] = opts_df['quantity'].apply(classify_pos)
            else:
                opts_df['posizione'] = None
            st.dataframe(opts_df[cols], use_container_width=True)
        else:
            st.info("Nessuna opzione aperta.")

    # — LOG OPZIONI SCADUTE —
    with st.expander("Opzioni Scadute & Assegnate", expanded=False):
        st.subheader("Log Opzioni Scadute")
        if not expired_log_df.empty:
            df = expired_log_df.copy()
            df['expiry_date'] = pd.to_datetime(df['expiry_date']).dt.strftime('%Y-%m-%d')
            st.dataframe(df, use_container_width=True)
            total = len(df)
            assigned = df['was_assigned'].sum()
            st.metric("Totale scadute", total)
            st.metric("Assegnate", f"{assigned} ({assigned/total*100:.1f}%)")
            st.metric("P&L Opzioni", f"${df['pnl'].sum():,.2f}")
        else:
            st.info("Nessuna opzione scaduta.")

    # — STORICO TRADE & FLOWS —
    with st.expander("Storico Completo", expanded=False):
        st.subheader("Tutti i Trade")
        if st.session_state.trades:
            tdf = pd.DataFrame(st.session_state.trades)
            tdf['date'] = pd.to_datetime(tdf['date']).dt.strftime('%Y-%m-%d')
            tdf['expiry'] = pd.to_datetime(tdf['expiry']).dt.strftime('%Y-%m-%d')
            st.dataframe(tdf, use_container_width=True)
        else:
            st.info("Nessun trade.")

        st.subheader("Tutti i Flussi")
        if st.session_state.cash_flows:
            cdf = pd.DataFrame(st.session_state.cash_flows)
            cdf['date'] = pd.to_datetime(cdf['date']).dt.strftime('%Y-%m-%d')
            st.dataframe(cdf, use_container_width=True)
        else:
            st.info("Nessun flusso di cassa.")


def wheel_metrics_view():
    """Vista per le metriche avanzate della strategia Wheel."""
    st.title("🎯 Metriche Avanzate Wheel")
    
    # Verifica dati disponibili
    if not st.session_state.get('trades') or st.session_state.get('portfolio_history', pd.DataFrame()).empty:
        st.warning("📊 Dati insufficienti per calcolare le metriche avanzate.")
        st.info("Aggiungi almeno alcuni trade nella pagina principale per visualizzare le metriche.")
        return
    
    # Import qui per evitare errori circolari
    from wheel_metrics import WheelMetricsCalculator
    
    # Inizializza calcolatore
    calculator = WheelMetricsCalculator(
        trades=st.session_state.trades,
        cash_flows=st.session_state.cash_flows,
        portfolio_history=st.session_state.portfolio_history,
        expired_options=st.session_state.get('expired_options_log', pd.DataFrame())
    )
    
    # Calcola tutte le metriche
    with st.spinner("Calcolo metriche avanzate..."):
        metrics = calculator.calculate_all_metrics()
    
    # Layout principale
    col1, col2 = st.columns(2)
    
    # --- METRICHE PRINCIPALI ---
    with col1:
        st.subheader("🎯 Wheel Efficiency Score (WES)")
        wes_data = metrics['wes']
        st.metric("WES", f"{wes_data['WES']:.2f}%")
        
        if wes_data['components']:
            with st.expander("Dettagli WES"):
                comp = wes_data['components']
                st.write(f"**Premio Incassato:** ${comp['premium_income']:,.2f}")
                st.write(f"**Capitale a Rischio:** ${comp['capital_at_risk']:,.2f}")
                st.write(f"**Yield Premio:** {comp['premium_yield']:.2f}%")
                st.write(f"**Tasso Assegnazione:** {comp['assignment_rate']:.1f}%")
                st.write(f"**DTE Medio:** {comp['avg_dte']:.0f} giorni")
        
        st.caption("*WES misura l'efficienza della strategia wheel considerando premium income, assignment rate e fattore temporale.*")
    
    with col2:
        st.subheader("📈 Relative Opportunity Index (ROI)")
        roi_data = metrics['roi']
        st.metric("ROI", f"{roi_data['ROI']:.2f}%")
        
        if roi_data['components']:
            with st.expander("Dettagli ROI"):
                comp = roi_data['components']
                st.write(f"**Rendimento Strategia:** {comp['strategy_return']:.2f}%")
                st.write(f"**Rendimento Benchmark:** {comp['benchmark_return']:.2f}%")
                st.write(f"**Excess Return:** {comp['excess_return']:.2f}%")
                st.write(f"**Simbolo Principale:** {comp['main_symbol']}")
        
        st.caption("*ROI confronta i rendimenti della strategia wheel con il buy-and-hold del sottostante.*")
    
    # --- ANALISI DRAWDOWN ---
    st.subheader("📉 Drawdown Tracker")
    dd_data = metrics['drawdown']
    
    if dd_data['drawdown_metrics']:
        dd_metrics = dd_data['drawdown_metrics']
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Max Drawdown", f"${dd_metrics['max_drawdown_dollar']:.2f}")
        col2.metric("Max DD %", f"{dd_metrics['max_drawdown_pct']:.2f}%")
        col3.metric("DD Corrente", f"${dd_metrics['current_drawdown']:.2f}")
        col4.metric("Recovery Factor", f"{dd_metrics['recovery_factor']:.2f}")
        
        # Grafico drawdown
        if 'drawdown_series' in dd_data:
            import plotly.graph_objects as go
            fig_dd = go.Figure()
            fig_dd.add_trace(go.Scatter(
                x=st.session_state.portfolio_history['date'],
                y=-dd_data['drawdown_series'],  # Negativo per mostrare drawdown verso il basso
                name="Drawdown",
                fill='tozeroy',
                line=dict(color='red', width=1)
            ))
            fig_dd.update_layout(
                title="Analisi Drawdown nel Tempo",
                yaxis_title="Drawdown ($)",
                template='plotly_white',
                height=300
            )
            st.plotly_chart(fig_dd, use_container_width=True)
        
        with st.expander("Statistiche Drawdown Dettagliate"):
            st.write(f"**Durata Media DD:** {dd_metrics['avg_drawdown_duration']:.1f} giorni")
            st.write(f"**Durata Max DD:** {dd_metrics['max_drawdown_duration']:.0f} giorni")
            st.write(f"**Frequenza DD:** {dd_metrics['drawdown_frequency_monthly']:.2f} per mese")
            st.write(f"**Numero DD:** {dd_metrics['num_drawdowns']}")
    
    st.caption("*Drawdown Tracker analizza la profondità, durata e frequenza dei drawdown della strategia.*")
    
    # --- PROBABILITA' RECOVERY ---
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔄 Recovery Probability")
        rec_data = metrics['recovery']
        st.metric("Probabilità Recovery", f"{rec_data['recovery_prob']:.1f}%")
        
        if rec_data['components']:
            with st.expander("Dettagli Recovery"):
                comp = rec_data['components']
                st.write(f"**Tempo Medio Recovery:** {comp['avg_recovery_time_days']:.1f} giorni")
                st.write(f"**Forza Recovery:** {comp['recovery_strength']:.2f}")
                st.write(f"**Confidence Score:** {comp['confidence_score']:.1f}%")
                st.write(f"**Eventi Recovery:** {comp['num_recovery_events']}")
        
        st.caption("*Recovery Probability stima la capacità della strategia di recuperare dai drawdown.*")
    
    with col2:
        st.subheader("⚡ Wheel Continuation Score (WCS)")
        wcs_data = metrics['wcs']
        st.metric("WCS", f"{wcs_data['WCS']:.1f}%")
        
        if wcs_data['components']:
            with st.expander("Dettagli WCS"):
                comp = wcs_data['components']
                st.write(f"**Trend Performance:** {comp['performance_trend']}")
                st.write(f"**Score Volatilità:** {comp['volatility_score']:.1f}%")
                st.write(f"**Frequenza Trading:** {comp['trading_frequency']:.2f} trades/mese")
                st.write(f"**Simboli:** {comp['num_symbols']}")
                st.write(f"**Tasso Assegnazione:** {comp['assignment_rate']:.1f}%")
                st.write(f"**Rating Sostenibilità:** {comp['sustainability_rating']}")
        
        st.caption("*WCS valuta la sostenibilità e continuabilità della strategia wheel.*")
    
    # --- RIEPILOGO GENERALE ---
    st.subheader("📋 Riepilogo Metriche")
    
    # Tabella riassuntiva
    summary_data = {
        "Metrica": ["WES", "ROI", "Recovery Prob", "WCS"],
        "Valore": [
            f"{metrics['wes']['WES']:.2f}%",
            f"{metrics['roi']['ROI']:.2f}%",
            f"{metrics['recovery']['recovery_prob']:.1f}%",
            f"{metrics['wcs']['WCS']:.1f}%"
        ],
        "Valutazione": [
            "Eccellente" if metrics['wes']['WES'] > 5 else "Buona" if metrics['wes']['WES'] > 2 else "Migliorabile",
            "Positiva" if metrics['roi']['ROI'] > 0 else "Negativa",
            "Alta" if metrics['recovery']['recovery_prob'] > 80 else "Media" if metrics['recovery']['recovery_prob'] > 50 else "Bassa",
            metrics['wcs']['components'].get('sustainability_rating', 'N/A') if metrics['wcs']['components'] else 'N/A'
        ]
    }
    
    st.dataframe(pd.DataFrame(summary_data), use_container_width=True)
    
    # Interpretazione
    st.subheader("🎯 Interpretazione Risultati")
    
    interpretations = []
    
    # WES
    wes_val = metrics['wes']['WES']
    if wes_val > 5:
        interpretations.append("✅ **WES Eccellente**: La strategia wheel sta generando un ottimo rendimento risk-adjusted")
    elif wes_val > 2:
        interpretations.append("⚠️ **WES Buono**: Performance discreta ma c'è margine di miglioramento")
    else:
        interpretations.append("❌ **WES Basso**: Considera di ottimizzare la selezione dei trade o i parametri")
    
    # ROI
    roi_val = metrics['roi']['ROI']
    if roi_val > 5:
        interpretations.append("✅ **ROI Superiore**: La strategia wheel sta battendo significativamente il benchmark")
    elif roi_val > 0:
        interpretations.append("⚠️ **ROI Positivo**: Performance migliore del benchmark ma moderata")
    else:
        interpretations.append("❌ **ROI Negativo**: La strategia sta underperformando il benchmark")
    
    # Recovery
    rec_val = metrics['recovery']['recovery_prob']
    if rec_val > 80:
        interpretations.append("✅ **Recovery Alta**: Ottima capacità di recupero dai drawdown")
    elif rec_val > 50:
        interpretations.append("⚠️ **Recovery Media**: Capacità di recupero accettabile")
    else:
        interpretations.append("❌ **Recovery Bassa**: Attenzione alla gestione del rischio")
    
    # WCS
    wcs_val = metrics['wcs']['WCS']
    if wcs_val > 70:
        interpretations.append("✅ **WCS Alto**: Strategia altamente sostenibile nel lungo periodo")
    elif wcs_val > 40:
        interpretations.append("⚠️ **WCS Medio**: Sostenibilità moderata, monitora attentamente")
    else:
        interpretations.append("❌ **WCS Basso**: Rivedi la strategia per migliorare la sostenibilità")
    
    for interp in interpretations:
        st.write(interp)
    
    # Suggerimenti
    st.subheader("💡 Suggerimenti per Ottimizzazione")
    
    suggestions = []
    
    if metrics['wes']['WES'] < 3:
        suggestions.append("📈 **Migliora WES**: Considera strike più vicini al denaro o scadenze più brevi")
    
    if metrics['roi']['ROI'] < 0:
        suggestions.append("🎯 **Migliora ROI**: Valuta una selezione più rigorosa dei sottostanti")
    
    if metrics['recovery']['recovery_prob'] < 60:
        suggestions.append("🛡️ **Migliora Recovery**: Implementa stop-loss o ridimensiona le posizioni")
    
    if metrics['wcs']['WCS'] < 50:
        suggestions.append("⚡ **Migliora WCS**: Aumenta la diversificazione e ottimizza la frequenza dei trade")
    
    if not suggestions:
        suggestions.append("🎉 **Ottimo Lavoro**: Le metriche indicano una strategia wheel ben ottimizzata!")
    
    for sugg in suggestions:
        st.write(sugg)
