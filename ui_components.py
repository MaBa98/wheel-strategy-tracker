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

    # Selettore per la vista: Aggregata vs Per Simbolo
    view_mode = st.selectbox(
        "Scegli la vista:",
        options=['Portafoglio Aggregato'] + calculator.all_symbols,
        index=0
    )

    st.markdown("---")

    if view_mode == 'Portafoglio Aggregato':
        # --- VISTA AGGREGATA (CODICE PRECEDENTE) ---
        # Questa parte rimane quasi identica a prima, ma ricalcoliamo le metriche aggregate
        st.header("Riepilogo Portafoglio Aggregato")
        
        # Calcola le metriche aggregate (potresti voler creare un metodo apposito in WheelMetricsCalculator)
        # Per ora, usiamo i calcoli originali che erano aggregati di default
        from portfolio import PortfolioProcessor # ri-usiamo un processore per le metriche aggregate
        processor = PortfolioProcessor(st.session_state.trades, st.session_state.cash_flows)
        agg_metrics = processor.calculate_performance_metrics(st.session_state.portfolio_history)

        cols = st.columns(4)
        cols[0].metric("P&L Totale", f"${agg_metrics['Total P&L']:,.2f}")
        cols[1].metric("TWR Annualizzato", f"{agg_metrics.get('Annualized TWR',0):.2f}%")
        cols[2].metric("Sharpe (TWR)", f"{agg_metrics.get('TWR Sharpe Ratio',0):.2f}")
        cols[3].metric("Max Drawdown", f"${agg_metrics['Max Drawdown $']:.2f}")

        st.info("Questa è una vista aggregata. Seleziona un simbolo dal menu per l'analisi dettagliata.")

    else:
        # --- VISTA PER SIMBOLO ---
        selected_symbol = view_mode
        st.header(f"🔍 Analisi Dettagliata per: ${selected_symbol}")

        with st.spinner(f"Calcolo metriche per {selected_symbol}..."):
            all_metrics_by_symbol = calculator.calculate_all_metrics_by_symbol()
            metrics = all_metrics_by_symbol.get(selected_symbol, {})

        if not metrics:
            st.error(f"Impossibile calcolare le metriche per {selected_symbol}.")
            return

        # --- GRAFICO RADAR ---
        st.subheader("Radar di Performance")
        
        wes_comps = metrics['wes']['components']
        wcs_comps = metrics['wcs']['components']
        
        # Normalizziamo i valori per il radar (scala 0-100)
        radar_data = {
            'WES': metrics['wes']['WES'] * 10, # Amplificato per visibilità
            'WCS': metrics['wcs']['WCS'],
            'Premium Yield': wes_comps.get('premium_yield', 0),
            'Gestione Assegnazioni': 100 - wes_comps.get('assignment_rate', 100),
            'Score Volatilità': wcs_comps.get('volatility_score', 0)
        }
        
        radar_df = pd.DataFrame(dict(
            r=list(radar_data.values()),
            theta=list(radar_data.keys())
        ))

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=radar_df['r'],
            theta=radar_df['theta'],
            fill='toself',
            name=selected_symbol
        ))
        
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100])
            ),
            showlegend=False,
            title=f"Profilo Strategia per {selected_symbol}",
            height=400
        )
        st.plotly_chart(fig_radar, use_container_width=True)
        st.caption("Il grafico radar mostra i punteggi chiave su una scala normalizzata (0-100). Un'area più ampia indica una performance migliore.")
        
        st.markdown("---")

        # --- DETTAGLIO METRICHE PER SIMBOLO ---
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🎯 Wheel Efficiency (WES)")
            wes_data = metrics['wes']
            st.metric("Score", f"{wes_data.get('WES', 0):.2f}%")
            with st.expander("Dettagli WES"):
                if wes_data.get('components'):
                    comp = wes_data['components']
                    st.write(f"**Premio Incassato:** ${comp.get('premium_income', 0):,.2f}")
                    st.write(f"**Capitale a Rischio:** ${comp.get('capital_at_risk', 0):,.2f}")
                    st.write(f"**Yield Premio:** {comp.get('premium_yield', 0):.2f}%")
                    st.write(f"**Tasso Assegnazione:** {comp.get('assignment_rate', 0):.1f}%")
                    st.write(f"**DTE Medio:** {comp.get('avg_dte', 0):.0f} giorni")
        
        with col2:
            st.subheader("⚡️ Wheel Continuation (WCS)")
            wcs_data = metrics['wcs']
            st.metric("Score", f"{wcs_data.get('WCS', 0):.1f}%", f"Rating: {wcs_data.get('components', {}).get('sustainability_rating', 'N/A')}")
            with st.expander("Dettagli WCS"):
                if wcs_data.get('components'):
                    comp = wcs_data['components']
                    st.write(f"**Frequenza Trading:** {comp.get('trading_frequency', 0):.2f} trades/mese")
                    st.write(f"**Score Volatilità:** {comp.get('volatility_score', 0):.1f}%")
                    st.write(f"**Tasso Assegnazione:** {comp.get('assignment_rate', 0):.1f}%")

