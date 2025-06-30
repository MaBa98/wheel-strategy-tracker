# portfolio.py

import pandas as pd
import numpy as np
from datetime import date, timedelta
from typing import List, Dict, Any, Tuple

# import della funzione async di fetch centralizzata
#from data_fetcher import fetch_all_historical_data
from data_fetcher import fetch_all_historical_data, fetch_risk_free_rate

# configurazione globale
CONFIG = {
    'risk_free_rate': 0.05,
    'default_commission': 1.50,
}


class PortfolioProcessor:
    """
    Classe che contiene tutta la logica per processare i trade,
    ricostruire lo storico e calcolare le metriche.
    """
    def __init__(self, trades: List[Dict], cash_flows: List[Dict]):
        self.trades = sorted(trades, key=lambda x: x['date'])
        self.cash_flows = sorted(cash_flows, key=lambda x: x['date'])
        # tutti i simboli coinvolti
        self.all_symbols = list({t['symbol'] for t in self.trades})

    @staticmethod
    def get_price_on_date(historical_data: pd.DataFrame, target_date: date) -> float:
        """Recupera il prezzo di chiusura più vicino a una data specifica."""
        if historical_data is None or historical_data.empty:
            return 0.0
        subset = historical_data[historical_data.index <= target_date]
        if not subset.empty:
            return float(subset.iloc[-1]['Close'])
        return 0.0

    async def build_full_history(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Ricostruisce giorno per giorno:
         - posizioni e cash balance
         - esecuzione trade e cash flows
         - scadenze opzioni e assegnazioni
         - valore portafoglio e P&L cumulativo
        Restituisce: (portfolio_history_df, expired_options_log_df)
        """
        # se non ci sono dati
        if not self.trades and not self.cash_flows:
            return pd.DataFrame(), pd.DataFrame()

        # 1) Determina l'intervallo temporale
        all_actions = self.trades + self.cash_flows
        start_date = min(a['date'] for a in all_actions)
        end_date = date.today()

        # 2) Scarica una volta per tutte le serie storiche dei prezzi
        historical_prices = await fetch_all_historical_data(
            self.all_symbols, start_date, end_date
        )

        # 3) Costruzione dei log
        portfolio_history: List[Dict[str, Any]] = []
        expired_options_log: List[Dict[str, Any]] = []

        # 4) Stato iniziale
        cash_balance = 0.0
        positions: Dict[str, Dict[str, Any]] = {}  # es. {'AAPL': {'shares': 100, 'cost_basis': 150.0}}
        open_options: List[Dict[str, Any]] = []
        processed_trade_ids = set()

        # 5) assegna ID unici ai trade
        for idx, t in enumerate(self.trades):
            t['unique_id'] = idx

        # 6) Loop su ogni giorno
        for single in pd.date_range(start_date, end_date, freq='D'):
            current_date = single.date()
            daily_cash_flow = 0.0

            # a) cash flows
            for flow in self.cash_flows:
                if flow['date'] == current_date:
                    amt = flow['amount']
                    cash_balance += amt
                    daily_cash_flow += amt

            # b) trade di quel giorno
            for trade in self.trades:
                if (trade['date'] == current_date
                        and trade['unique_id'] not in processed_trade_ids):
                    # commissioni
                    cash_balance -= trade.get('commission', 0)

                    if trade['type'] == 'stock':
                        symbol = trade['symbol']
                        qty = trade['quantity']
                        price = trade['stock_price']

                        # paghi o incassi azioni
                        cash_balance -= qty * price

                        if symbol not in positions:
                            positions[symbol] = {'shares': 0, 'cost_basis': 0.0}

                        # aggiornamento costo medio
                        if qty > 0:  # acquisto
                            old_cost = (positions[symbol]['shares']
                                        * positions[symbol]['cost_basis'])
                            new_cost = qty * price
                            total_shares = positions[symbol]['shares'] + qty
                            positions[symbol]['cost_basis'] = (
                                (old_cost + new_cost) / total_shares
                                if total_shares > 0 else 0.0
                            )

                        positions[symbol]['shares'] += qty

                    elif trade['type'] in ['put', 'call']:
                        # premio opzione
                        prem = abs(trade['premium'])
                        if trade['quantity'] < 0:
                            # short -> incassi premio
                            cash_balance += prem
                        else:
                            # long -> paghi premio
                            cash_balance -= prem

                        open_options.append(trade)

                    processed_trade_ids.add(trade['unique_id'])

            # c) gestione scadenze opzioni
            remaining_options = []
            for opt in open_options:
                if opt['expiry'] == current_date:
                    symbol = opt['symbol']
                    strike = opt['strike']
                    premium = opt['premium']
                    qty = opt['quantity']
                    multiplier = opt.get('multiplier', 100)
                    price_on_exp = self.get_price_on_date(
                        historical_prices.get(symbol, pd.DataFrame()), current_date
                    )
                    pnl = 0.0
                    was_assigned = False

                    # determina se assegnata (solo per short)
                    if qty < 0:
                        if (opt['type'] == 'put' and price_on_exp < strike) \
                           or (opt['type'] == 'call' and price_on_exp > strike):
                            was_assigned = True

                    # calcolo P&L e possibili trade di assignment
                    if qty < 0:
                        # short
                        if was_assigned:
                            # premio già incassato -> considerato P&L
                            pnl = abs(premium)
                            # genera trade di azioni
                            contracts = abs(qty)
                            share_qty = contracts * multiplier
                            if opt['type'] == 'put':
                                assign_qty = share_qty
                            else:
                                assign_qty = -share_qty

                            assignment_trade = {
                                'date': current_date,
                                'symbol': symbol,
                                'type': 'stock',
                                'quantity': assign_qty,
                                'stock_price': strike,
                                'commission': 0.0,
                                'note': f"Assegnazione da {opt['type'].title()} strike {strike}",
                                'unique_id': len(self.trades) + len(expired_options_log)
                            }
                            self.trades.append(assignment_trade)
                        else:
                            # scaduta OTM
                            pnl = abs(premium)
                    else:
                        # long
                        intrinsic = 0.0
                        if opt['type'] == 'put' and price_on_exp < strike:
                            intrinsic = (strike - price_on_exp) * abs(qty) * multiplier
                        elif opt['type'] == 'call' and price_on_exp > strike:
                            intrinsic = (price_on_exp - strike) * abs(qty) * multiplier

                        if intrinsic > 0:
                            cash_balance += intrinsic
                            pnl = intrinsic - abs(premium)
                        else:
                            pnl = -abs(premium)

                    expired_options_log.append({
                        'expiry_date': current_date,
                        'symbol': symbol,
                        'type': opt['type'],
                        'strike': strike,
                        'premium': premium,
                        'pnl': pnl,
                        'was_assigned': was_assigned,
                        'price_on_expiry': price_on_exp
                    })
                else:
                    remaining_options.append(opt)
            open_options = remaining_options

            # d) calcola valori di portafoglio
            stock_value = 0.0
            for symbol, pos in positions.items():
                shares = pos['shares']
                if shares != 0:
                    p = self.get_price_on_date(
                        historical_prices.get(symbol, pd.DataFrame()), current_date
                    )
                    stock_value += shares * p

            options_value = 0.0
            for opt in open_options:
                price_now = self.get_price_on_date(
                    historical_prices.get(opt['symbol'], pd.DataFrame()), current_date
                )
                intrinsic = 0.0
                if opt['type'] == 'put':
                    intrinsic = max(0, opt['strike'] - price_now)
                else:
                    intrinsic = max(0, price_now - opt['strike'])
                val = intrinsic * abs(opt['quantity']) * opt.get('multiplier', 100)
                # short è passività
                options_value += (-val if opt['quantity'] < 0 else val)

            portfolio_value = stock_value + cash_balance + options_value

            # P&L netto rispetto ai cash flows
            cumulative_cf = sum(cf['amount']
                                for cf in self.cash_flows
                                if cf['date'] <= current_date)
            equity_line_pnl = portfolio_value - cumulative_cf

            # registra lo snapshot
            portfolio_history.append({
                'date': current_date,
                'portfolio_value': portfolio_value,
                'stock_value': stock_value,
                'options_value': options_value,
                'cash_balance': cash_balance,
                'daily_cash_flow': daily_cash_flow,
                'cumulative_cash_flow': cumulative_cf,
                'equity_line_pnl': equity_line_pnl
            })

        # ritorna due DataFrame
        return pd.DataFrame(portfolio_history), pd.DataFrame(expired_options_log)

    @staticmethod
    def get_current_positions(trades: list[dict]) -> tuple[dict, dict]:
        """
        Restituisce (positions, expired_options) a partire da trades.
        positions: { symbol: net_quantity, … }
        expired_options: { symbol: [list_of_expired_trades], … }
        """
        positions: dict[str,int] = {}
        expired_options: dict[str,list] = {}
        for t in trades:
            # esempio di logica semplice
            sym = t['symbol']
            qty = t['quantity']
            positions[sym] = positions.get(sym, 0) + qty
            if t.get('expiry') and t['expiry'] < date.today():
                expired_options.setdefault(sym, []).append(t)
        return positions, expired_options
    
    @staticmethod
    def calculate_performance_metrics(
        history: pd.DataFrame,
        cash_flows: List[Dict] = None,
        trades: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Calcola metriche estese: VaR, Sortino, TWR, Sharpe-TWR,
        Drawdown-duration, commissioni, breakdown per simbolo/tipo.
        """
        if history.empty:
            return {}
        
        # rendimenti giornalieri
        ret = history['portfolio_value'].pct_change().dropna()
        #rf = CONFIG['risk_free_rate']
        rf = fetch_risk_free_rate()

        # annualizza return e volatilità
        ann_ret = ret.mean() * 252
        ann_vol = ret.std() * np.sqrt(252)

        # total P&L e total return %
        total_pnl = history['equity_line_pnl'].iloc[-1]
        init_cf = history['cumulative_cash_flow'].iloc[0] or 1
        total_ret_pct = total_pnl / abs(init_cf) * 100

        # Sharpe & Sortino
        sharpe = (ann_ret - rf) / ann_vol if ann_vol > 0 else 0
        down_rets = ret[ret < 0]
        dd_std = down_rets.std() * np.sqrt(252)
        sortino = (ann_ret - rf) / dd_std if dd_std > 0 else 0

        # VaR 95% giornaliero ($)
        var95 = -np.percentile(ret, 5) * history['portfolio_value'].iloc[-1]

        # Max Drawdown e durata
        eq = history['equity_line_pnl']
        running_max = eq.cummax()
        drawdown = running_max - eq
        max_dd = drawdown.max()
        durations, cur = [], 0
        for flag in drawdown > 0:
            cur = cur + 1 if flag else (durations.append(cur) or 0)
        durations.append(cur)
        max_dd_duration = max(durations)

        # commissioni totali e impatto
        total_comm = sum(t.get('commission', 0) for t in trades) if trades else 0
        comm_impact_pct = total_comm / abs(init_cf) * 100

        # breakdown P&L per simbolo e tipo
        per_symbol, per_type = {}, {}
        if trades:
            df_t = pd.DataFrame(trades)
            def net_cf(tr):
                if tr['type'] == 'stock':
                    return -tr['quantity'] * tr['stock_price'] - tr.get('commission', 0)
                prem = tr['premium']
                sign = 1 if tr['quantity'] < 0 else -1
                return sign * prem - tr.get('commission', 0)
            df_t['net_cf'] = df_t.apply(net_cf, axis=1)
            per_symbol = df_t.groupby('symbol')['net_cf'].sum().to_dict()
            per_type = df_t.groupby('type')['net_cf'].sum().to_dict()

        # TWR e TWR-Sharpe
        twr_metrics = {}
        if cash_flows:
            # calcola TWR e TWR-sharpe
            from portfolio import PortfolioProcessor  # evita import circolare
            twr_metrics = PortfolioProcessor.calculate_twr(history, cash_flows)
            twr_daily = PortfolioProcessor.calculate_twr_daily_returns(history, cash_flows)
            if len(twr_daily) > 1:
                mu = np.mean(twr_daily) * 252
                sigma = np.std(twr_daily) * np.sqrt(252)
                sr_twr = (mu - rf) / sigma if sigma > 0 else 0
            else:
                sr_twr = 0
            twr_metrics["TWR Sharpe Ratio"] = sr_twr

        # compone il dict finale
        out = {
            "Total P&L": total_pnl,
            "Total Return %": total_ret_pct,
            "Annual Return %": ann_ret * 100,
            "Annual Volatility %": ann_vol * 100,
            "Sharpe Ratio": sharpe,
            "Sortino Ratio": sortino,
            "VaR 95% ($)": var95,
            "Max Drawdown $": max_dd,
            "Max DD Duration (days)": max_dd_duration,
            "Total Commissions $": total_comm,
            "Comm Impact %": comm_impact_pct,
            **{k: v * 100 for k, v in twr_metrics.items() if k in ["TWR", "Annualized TWR"]},
            "TWR Sharpe Ratio": twr_metrics.get("TWR Sharpe Ratio", 0),
            "P&L per Symbol": per_symbol,
            "P&L per Strategy": per_type
        }
        return out

    @staticmethod
    def calculate_twr(history: pd.DataFrame,
                      cash_flows: List[Dict]) -> Dict[str, float]:
        """
        Time-Weighted Return (TWR) senza l’effetto dei flussi di cassa.
        """
        if len(history) < 2:
            return {"TWR": 0.0, "Annualized TWR": 0.0}

        cash_flow_dates = {cf['date']: cf['amount'] for cf in cash_flows}
        period_returns = []
        previous_value = None

        for idx, row in history.iterrows():
            current_date = row['date']
            current_value = row['portfolio_value']

            if previous_value is None:
                previous_value = current_value
                continue

            cash_flow = cash_flow_dates.get(current_date, 0)
            if cash_flow != 0:
                before = current_value - cash_flow
                if previous_value > 0:
                    period_returns.append((before / previous_value) - 1)
                previous_value = current_value
            elif idx == len(history) - 1:
                if previous_value > 0:
                    period_returns.append((current_value / previous_value) - 1)

        twr = 1.0
        for r in period_returns:
            twr *= (1 + r)
        twr -= 1

        # annualizzazione
        days = (history['date'].iloc[-1] - history['date'].iloc[0]).days
        years = days / 365.25
        ann = ((1 + twr) ** (1 / years) - 1) if years > 0 else twr

        return {"TWR": twr, "Annualized TWR": ann}

    @staticmethod
    def calculate_twr_daily_returns(history: pd.DataFrame,
                                    cash_flows: List[Dict]) -> List[float]:
        """
        Ritorna i rendimenti giornalieri time-weighted.
        """
        if len(history) < 2:
            return []

        cf_dates = {cf['date']: cf['amount'] for cf in cash_flows}
        daily = []
        for i in range(1, len(history)):
            prev = history.iloc[i - 1]
            curr = history.iloc[i]
            cf = cf_dates.get(curr['date'], 0)
            adj = curr['portfolio_value'] - cf if cf != 0 else curr['portfolio_value']
            if prev['portfolio_value'] > 0:
                daily.append((adj / prev['portfolio_value']) - 1)
        return daily

    @staticmethod
    def compute_contributions(trades: list[dict]) -> pd.DataFrame:
        """
        Raggruppa per symbol l’impatto P&L totale.
        Ogni trade deve già contenere:
          - symbol, quantity, premium, stock_price, commission, multiplier
        Contribution per trade = quantity*(stock_price*multiplier)
                                 + premium*multiplier
                                 - commission
        """
        records = []
        for t in trades:
            qty = t['quantity']
            mult = t.get('multiplier',100)
            # pnl da sottostante
            stock_pnl = qty * t.get('stock_price', 0) * mult
            opt_pnl   = t.get('premium',0) * mult
            comm      = t.get('commission',0)
            total_pnl = stock_pnl + opt_pnl - comm
            records.append({'symbol': t['symbol'], 'pnl': total_pnl})
        df = pd.DataFrame(records)
        df = df.groupby('symbol')['pnl'].sum().reset_index()
        # aggiunge colonna % sul totale
        total = df['pnl'].sum()
        df['pct_of_total'] = df['pnl'] / total * 100
        return df.sort_values('pct_of_total', ascending=False)
        # aggiunge colonna % sul totale
        total = df['pnl'].sum()
        df['pct_of_total'] = df['pnl'] / total * 100
        return df.sort_values('pct_of_total', ascending=False)
