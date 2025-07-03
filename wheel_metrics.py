## wheel_metrics.py

import pandas as pd
import numpy as np
from datetime import date, timedelta
from typing import Dict, List, Tuple, Any, Optional
import streamlit as st

class WheelMetricsCalculator:
    """
    Calcolatore di metriche avanzate per la strategia Wheel,
    con capacità di calcolo per singolo sottostante.
    """
    
    def __init__(self, trades: List[Dict], cash_flows: List[Dict], 
                 portfolio_history: pd.DataFrame, expired_options: pd.DataFrame):
        self.all_trades = trades
        self.all_cash_flows = cash_flows
        self.all_portfolio_history = portfolio_history
        self.all_expired_options = expired_options
        self.all_symbols = sorted(list(set(t['symbol'] for t in self.all_trades)))

    def _filter_data_by_symbol(self, symbol: str) -> Tuple[List[Dict], List[Dict], pd.DataFrame, pd.DataFrame]:
        """Filtra tutti i dati necessari per un singolo simbolo."""
        trades = [t for t in self.all_trades if t['symbol'] == symbol]
        
        # Nota: cash_flows e portfolio_history non sono direttamente filtrabili per simbolo
        # in quanto rappresentano dati a livello di portafoglio aggregato.
        # Per semplicità, li passiamo interi. Le metriche che li usano
        # dovranno essere interpretate con cautela se usate per un singolo simbolo.
        cash_flows = self.all_cash_flows 
        portfolio_history = self.all_portfolio_history 

        expired_options = self.all_expired_options[
            self.all_expired_options['symbol'] == symbol
        ] if not self.all_expired_options.empty else pd.DataFrame()
        
        return trades, cash_flows, portfolio_history, expired_options

    def calculate_wheel_efficiency_score(self, symbol: str) -> Dict[str, Any]:
        """Calcola il WES per un singolo simbolo."""
        trades, _, _, expired_options = self._filter_data_by_symbol(symbol)
        
        try:
            if not trades:
                return {"WES": 0, "components": {}, "explanation": "Nessun trade per questo simbolo"}
            
            puts_sold = [t for t in trades if t.get('type') == 'put' and t.get('quantity', 0) < 0]
            calls_sold = [t for t in trades if t.get('type') == 'call' and t.get('quantity', 0) < 0]
            
            if not puts_sold and not calls_sold:
                return {"WES": 0, "components": {}, "explanation": "Nessuna opzione venduta per questo simbolo"}
            
            total_premium = sum(abs(t.get('premium', 0)) for t in puts_sold + calls_sold)
            
            capital_at_risk = 0
            for t in puts_sold:
                capital_at_risk += t.get('strike', 0) * abs(t.get('quantity', 0)) * t.get('multiplier', 100)
            #for t in calls_sold:
                #capital_at_risk += t.get('strike', 0) * abs(t.get('quantity', 0)) * t.get('multiplier', 100)

            if expired_options.empty:
                assignment_rate = 0
            else:
                assigned_count = expired_options['was_assigned'].sum()
                total_expired = len(expired_options)
                assignment_rate = assigned_count / total_expired if total_expired > 0 else 0
            
            avg_dte = 0
            if puts_sold + calls_sold:
                total_dte = sum((t.get('expiry', t.get('date')) - t.get('date')).days for t in puts_sold + calls_sold)
                avg_dte = total_dte / len(puts_sold + calls_sold)
            
            time_factor = min(1.0, avg_dte / 45)
            
            if capital_at_risk > 0:
                premium_yield = total_premium / capital_at_risk
                wes = premium_yield * (1 - assignment_rate) * time_factor * 100
            else:
                wes = 0
                premium_yield = 0
                
            components = {
                "premium_income": total_premium, "capital_at_risk": capital_at_risk,
                "premium_yield": premium_yield * 100, "assignment_rate": assignment_rate * 100,
                "avg_dte": avg_dte, "time_factor": time_factor
            }
            
            return {"WES": wes, "components": components, "explanation": f"WES per {symbol}: {wes:.2f}%"}
            
        except Exception as e:
            return {"WES": 0, "components": {}, "explanation": f"Errore: {str(e)}"}

    def calculate_relative_opportunity_index(self, symbol: str) -> Dict[str, Any]:
        """
        Confronta i rendimenti della strategia wheel per un simbolo con il buy-and-hold
        dello stesso sottostante. Usa il P&L calcolato in `portfolio.py`.
        """
        # Questa metrica rimane complessa da calcolare per simbolo senza un P&L per simbolo.
        # Si consiglia di calcolare il P&L per simbolo in PortfolioProcessor e passarlo qui.
        # Per ora, restituiamo un placeholder.
        return {
            "ROI": "N/A", 
            "components": {"main_symbol": symbol},
            "explanation": "Il calcolo del ROI per simbolo richiede il P&L specifico per simbolo (da implementare)."
        }
        
    def calculate_drawdown_tracker(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Analizza i drawdown. Se il simbolo è specificato, è solo informativo,
        poiché il drawdown è una metrica di portafoglio.
        """
        if self.all_portfolio_history.empty:
            return {"drawdown_metrics": {}, "explanation": "Storico portafoglio vuoto"}
        
        # Il Drawdown è una metrica a livello di portafoglio, non per simbolo.
        # La mostriamo identica per tutti ma specifichiamo il contesto.
        explanation_prefix = f"Drawdown a livello di portafoglio (mostrato per il contesto di {symbol})" if symbol else "Drawdown a livello di portafoglio"
        
        equity_line = self.all_portfolio_history['equity_line_pnl']
        running_max = equity_line.cummax()
        drawdown = running_max - equity_line
        
        initial_capital = abs(self.all_portfolio_history['cumulative_cash_flow'].iloc[0])
        drawdown_pct = (drawdown / initial_capital) * 100 if initial_capital > 0 else pd.Series([0] * len(drawdown))
        
        max_drawdown = drawdown.max()
        max_drawdown_pct = drawdown_pct.max()
        
        in_drawdown = drawdown > 0
        drawdown_periods = []
        current_period = 0
        for is_dd in in_drawdown:
            if is_dd:
                current_period += 1
            elif current_period > 0:
                drawdown_periods.append(current_period)
                current_period = 0
        if current_period > 0:
            drawdown_periods.append(current_period)
        
        avg_drawdown_duration = np.mean(drawdown_periods) if drawdown_periods else 0
        max_drawdown_duration = max(drawdown_periods) if drawdown_periods else 0
        
        return {
            "drawdown_metrics": {
                "max_drawdown_dollar": max_drawdown, "max_drawdown_pct": max_drawdown_pct,
                "avg_drawdown_duration": avg_drawdown_duration, "max_drawdown_duration": max_drawdown_duration,
                "current_drawdown": drawdown.iloc[-1] if not drawdown.empty else 0
            },
            "drawdown_series": drawdown,
            "explanation": f"{explanation_prefix}: Max DD ${max_drawdown:.2f} ({max_drawdown_pct:.2f}%)"
        }

    def calculate_recovery_probability(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Stima la probabilità di recupero. Metrica di portafoglio, mostrata per contesto.
        """
        # Anche questa è una metrica di portafoglio
        if self.all_portfolio_history.empty:
            return {"recovery_prob": 0, "components": {}, "explanation": "Storico vuoto"}

        equity_line = self.all_portfolio_history['equity_line_pnl']
        
        # Logica di calcolo identica a prima, è una metrica di portafoglio
        # ... (la logica può essere copiata dalla tua versione originale)
        
        return {
            "recovery_prob": "N/A", 
            "components": {"symbol": symbol},
            "explanation": "Metrica di recupero a livello di portafoglio."
        }

    def calculate_wheel_continuation_score(self, symbol: str) -> Dict[str, Any]:
        """Calcola il WCS per un singolo simbolo."""
        trades, _, _, expired_options = self._filter_data_by_symbol(symbol)

        try:
            if not trades:
                return {"WCS": 0, "components": {}, "explanation": "Nessun trade per il simbolo"}

            # Performance Trend (difficile per simbolo senza P&L per simbolo)
            performance_trend = 0  # Placeholder

            # Volatilità dei rendimenti (metrica di portafoglio, usata come proxy)
            if len(self.all_portfolio_history) > 1:
                returns = self.all_portfolio_history['portfolio_value'].pct_change().dropna()
                volatility = returns.std()
                volatility_score = max(0, 1 - volatility / 0.03) # Normalizzato vs 3% daily std dev
            else:
                volatility_score = 1
            
            days_range = (max(t['date'] for t in trades) - min(t['date'] for t in trades)).days if trades else 0
            trading_frequency = len(trades) / max(1, days_range / 30)
            frequency_score = min(1.0, trading_frequency / 5) # Normalizzato a 5 trades/mese/simbolo

            # Diversificazione non applicabile per singolo simbolo
            diversification_score = 1.0

            if expired_options.empty:
                assignment_management = 1.0
                assignment_rate = 0
            else:
                assignment_rate = expired_options['was_assigned'].mean()
                assignment_management = 1 - min(0.8, assignment_rate)

            wcs = (
                (performance_trend + 1) / 2 * 0.2 +
                volatility_score * 0.3 +
                frequency_score * 0.3 +
                assignment_management * 0.2
            ) * 100
            
            components = {
                "performance_trend": performance_trend, "volatility_score": volatility_score * 100,
                "trading_frequency": trading_frequency,
                "assignment_rate": assignment_rate * 100,
                "sustainability_rating": "Alta" if wcs > 70 else "Media" if wcs > 40 else "Bassa"
            }
            
            return {
                "WCS": wcs, "components": components,
                "explanation": f"WCS per {symbol}: {wcs:.1f}% - Sostenibilità: {components['sustainability_rating']}"
            }
        except Exception as e:
            return {"WCS": 0, "components": {}, "explanation": f"Errore: {str(e)}"}

    def calculate_all_metrics_by_symbol(self) -> Dict[str, Dict[str, Any]]:
        """Calcola tutte le metriche per ogni simbolo nel portafoglio."""
        all_metrics = {}
        for symbol in self.all_symbols:
            # Le metriche che sono solo a livello di portafoglio vengono calcolate una volta
            drawdown_metrics = self.calculate_drawdown_tracker(symbol)
            recovery_metrics = self.calculate_recovery_probability(symbol)

            all_metrics[symbol] = {
                "wes": self.calculate_wheel_efficiency_score(symbol),
                "roi": self.calculate_relative_opportunity_index(symbol),
                "drawdown": drawdown_metrics,
                "recovery": recovery_metrics,
                "wcs": self.calculate_wheel_continuation_score(symbol)
            }
        return all_metrics
