# wheel_metrics.py

import pandas as pd
import numpy as np
from datetime import date, timedelta
from typing import Dict, List, Tuple, Any
import streamlit as st

class WheelMetricsCalculator:
    """
    Calcolatore di metriche avanzate per la strategia Wheel.
    """
    
    def __init__(self, trades: List[Dict], cash_flows: List[Dict], 
                 portfolio_history: pd.DataFrame, expired_options: pd.DataFrame):
        self.trades = trades
        self.cash_flows = cash_flows
        self.portfolio_history = portfolio_history
        self.expired_options = expired_options
        
    def calculate_wheel_efficiency_score(self) -> Dict[str, Any]:
        """
        Wheel Efficiency Score (WES): Misura l'efficienza della strategia wheel
        considerando premium income, assignment rate e holding period.
        
        WES = (Premium Income / Capital At Risk) * (1 - Assignment Rate) * Time Factor
        """
        try:
            if not self.trades:
                return {"WES": 0, "components": {}, "explanation": "Nessun trade disponibile"}
            
            puts_sold = [t for t in self.trades if t.get('type') == 'put' and t.get('quantity', 0) < 0]
            calls_sold = [t for t in self.trades if t.get('type') == 'call' and t.get('quantity', 0) < 0]
            
            if not puts_sold and not calls_sold:
                return {"WES": 0, "components": {}, "explanation": "Nessuna opzione venduta trovata"}
            
            # Calcolo premium income
            total_premium = sum(abs(t.get('premium', 0)) for t in puts_sold + calls_sold)
            
            # Calcolo capital at risk (strike * contracts * multiplier)
            capital_at_risk = 0
            for t in puts_sold:
                # Per PUT vendute: capital at risk = strike * contracts * multiplier
                capital_at_risk += t.get('strike', 0) * abs(t.get('quantity', 0)) * t.get('multiplier', 100)
            
            # Per CALL vendute, il capital at risk è il valore delle azioni sottostanti
            for t in calls_sold:
                # Stima valore azioni = strike * contracts * multiplier (approssimazione)
                capital_at_risk += t.get('strike', 0) * abs(t.get('quantity', 0)) * t.get('multiplier', 100)

            
            # Assignment rate
            if self.expired_options.empty:
                assignment_rate = 0
            else:
                assigned_count = self.expired_options['was_assigned'].sum()
                total_expired = len(self.expired_options)
                assignment_rate = assigned_count / total_expired if total_expired > 0 else 0
            
            # Time factor (giorni medi alla scadenza)
            avg_dte = 0
            if puts_sold + calls_sold:
                total_dte = 0
                for t in puts_sold + calls_sold:
                    dte = (t.get('expiry', t.get('date')) - t.get('date')).days
                    total_dte += dte
                avg_dte = total_dte / len(puts_sold + calls_sold)
            
            time_factor = min(1.0, avg_dte / 45)  # Normalizzato a 45 giorni
            
            # Calcolo WES
            if capital_at_risk > 0:
                premium_yield = total_premium / capital_at_risk
                wes = premium_yield * (1 - assignment_rate) * time_factor * 100
            else:
                wes = 0
                
            components = {
                "premium_income": total_premium,
                "capital_at_risk": capital_at_risk,
                "premium_yield": premium_yield * 100 if capital_at_risk > 0 else 0,
                "assignment_rate": assignment_rate * 100,
                "avg_dte": avg_dte,
                "time_factor": time_factor
            }
            
            return {
                "WES": wes,
                "components": components,
                "explanation": f"WES del {wes:.2f}% indica l'efficienza della strategia wheel"
            }
            
        except Exception as e:
            return {"WES": 0, "components": {}, "explanation": f"Errore nel calcolo: {str(e)}"}
    
    def calculate_relative_opportunity_index(self) -> Dict[str, Any]:
        """
        Relative Opportunity Index (ROI): Confronta i rendimenti della strategia wheel
        con il semplice buy-and-hold del sottostante.
        """
        try:
            if self.portfolio_history.empty:
                return {"ROI": 0, "components": {}, "explanation": "Storico portafoglio vuoto"}
            
            # Calcolo rendimento strategia
            initial_value = self.portfolio_history['cumulative_cash_flow'].iloc[0]
            final_pnl = self.portfolio_history['equity_line_pnl'].iloc[-1]
            
            if abs(initial_value) < 1:
                return {"ROI": 0, "components": {}, "explanation": "Capitale iniziale insufficiente"}
            
            strategy_return = final_pnl / abs(initial_value)
            
            # Stima rendimento buy-and-hold (usando il simbolo più tradato)
            symbol_counts = {}
            for t in self.trades:
                symbol = t.get('symbol', '')
                symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
            
            if not symbol_counts:
                return {"ROI": 0, "components": {}, "explanation": "Nessun simbolo trovato"}
            
            main_symbol = max(symbol_counts, key=symbol_counts.get)
            
            # Approssimazione: assumiamo 10% annuo per il sottostante
            days_trading = (self.portfolio_history['date'].iloc[-1] - 
                          self.portfolio_history['date'].iloc[0]).days
            years_trading = days_trading / 365.25
            
            benchmark_return = 0.10 * years_trading  # 10% annuo
            
            # Calcolo ROI
            roi = (strategy_return - benchmark_return) * 100
            
            components = {
                "strategy_return": strategy_return * 100,
                "benchmark_return": benchmark_return * 100,
                "excess_return": roi,
                "main_symbol": main_symbol,
                "trading_days": days_trading
            }
            
            return {
                "ROI": roi,
                "components": components,
                "explanation": f"ROI del {roi:.2f}% vs benchmark {main_symbol}"
            }
            
        except Exception as e:
            return {"ROI": 0, "components": {}, "explanation": f"Errore nel calcolo: {str(e)}"}
    
    def calculate_drawdown_tracker(self) -> Dict[str, Any]:
        """
        Drawdown Tracker: Analizza i drawdown della strategia wheel.
        """
        try:
            if self.portfolio_history.empty:
                return {"drawdown_metrics": {}, "explanation": "Storico portafoglio vuoto"}
            
            equity_line = self.portfolio_history['equity_line_pnl']
            running_max = equity_line.cummax()
            drawdown = running_max - equity_line
            
            initial_capital = abs(self.portfolio_history['cumulative_cash_flow'].iloc[0])
            if initial_capital > 0:
                drawdown_pct = (drawdown / initial_capital) * 100
            else:
                drawdown_pct = pd.Series([0] * len(drawdown))
            
            # Metriche drawdown
            max_drawdown = drawdown.max()
            max_drawdown_pct = drawdown_pct.max()
            
            # Durata drawdown
            in_drawdown = drawdown > 0
            drawdown_periods = []
            current_period = 0
            
            for is_dd in in_drawdown:
                if is_dd:
                    current_period += 1
                else:
                    if current_period > 0:
                        drawdown_periods.append(current_period)
                    current_period = 0
            
            if current_period > 0:
                drawdown_periods.append(current_period)
            
            avg_drawdown_duration = np.mean(drawdown_periods) if drawdown_periods else 0
            max_drawdown_duration = max(drawdown_periods) if drawdown_periods else 0
            
            # Frequenza drawdown
            num_drawdowns = len(drawdown_periods)
            total_days = len(equity_line)
            drawdown_frequency = num_drawdowns / (total_days / 30) if total_days > 0 else 0  # per mese
            
            return {
                "drawdown_metrics": {
                    "max_drawdown_dollar": max_drawdown,
                    "max_drawdown_pct": max_drawdown_pct,
                    "avg_drawdown_duration": avg_drawdown_duration,
                    "max_drawdown_duration": max_drawdown_duration,
                    "drawdown_frequency_monthly": drawdown_frequency,
                    "num_drawdowns": num_drawdowns,
                    "current_drawdown": drawdown.iloc[-1],
                    "recovery_factor": abs(equity_line.iloc[-1]) / max_drawdown if max_drawdown > 0 else 0
                },
                "drawdown_series": drawdown,
                "explanation": f"Max DD: ${max_drawdown:.2f} ({max_drawdown_pct:.2f}%)"
            }
            
        except Exception as e:
            return {"drawdown_metrics": {}, "explanation": f"Errore nel calcolo: {str(e)}"}
    
    def calculate_recovery_probability(self) -> Dict[str, Any]:
        """
        Recovery Probability: Stima la probabilità di recupero dai drawdown.
        """
        try:
            if self.portfolio_history.empty:
                return {"recovery_prob": 0, "components": {}, "explanation": "Storico portafoglio vuoto"}
            
            equity_line = self.portfolio_history['equity_line_pnl']
            running_max = equity_line.cummax()
            drawdown = running_max - equity_line
            
            # Identifica periodi di drawdown e recovery
            in_drawdown = drawdown > 0
            recovery_events = []
            
            i = 0
            while i < len(in_drawdown):
                if in_drawdown.iloc[i]:
                    # Inizio drawdown
                    start_dd = i
                    while i < len(in_drawdown) and in_drawdown.iloc[i]:
                        i += 1
                    
                    # Fine drawdown, inizio recovery
                    if i < len(in_drawdown):
                        max_dd_in_period = drawdown.iloc[start_dd:i].max()
                        recovery_events.append({
                            'start': start_dd,
                            'end': i,
                            'max_dd': max_dd_in_period,
                            'recovered': True
                        })
                else:
                    i += 1
            
            # Calcolo probabilità
            if recovery_events:
                total_recoveries = len(recovery_events)
                successful_recoveries = sum(1 for r in recovery_events if r['recovered'])
                recovery_probability = successful_recoveries / total_recoveries
                
                # Tempo medio di recovery
                recovery_times = [r['end'] - r['start'] for r in recovery_events]
                avg_recovery_time = np.mean(recovery_times)
                
                # Recovery strength
                recovery_strength = np.mean([
                    abs(equity_line.iloc[r['end']]) / r['max_dd'] 
                    for r in recovery_events if r['max_dd'] > 0
                ])
            else:
                recovery_probability = 1.0  # Nessun drawdown = 100% recovery
                avg_recovery_time = 0
                recovery_strength = 1.0
            
            # Confidence score basato su diversi fattori
            confidence_score = (
                recovery_probability * 0.4 +
                min(1.0, recovery_strength / 2) * 0.3 +
                min(1.0, 30 / max(1, avg_recovery_time)) * 0.3
            )
            
            components = {
                "recovery_probability": recovery_probability * 100,
                "avg_recovery_time_days": avg_recovery_time,
                "recovery_strength": recovery_strength,
                "confidence_score": confidence_score * 100,
                "num_recovery_events": len(recovery_events)
            }
            
            return {
                "recovery_prob": recovery_probability * 100,
                "components": components,
                "explanation": f"Probabilità di recupero: {recovery_probability*100:.1f}%"
            }
            
        except Exception as e:
            return {"recovery_prob": 0, "components": {}, "explanation": f"Errore nel calcolo: {str(e)}"}
    
    def calculate_wheel_continuation_score(self) -> Dict[str, Any]:
        """
        Wheel Continuation Score (WCS): Valuta la sostenibilità della strategia wheel.
        """
        try:
            if not self.trades:
                return {"WCS": 0, "components": {}, "explanation": "Nessun trade disponibile"}
            
            # Analisi trend performance
            if self.portfolio_history.empty:
                performance_trend = 0
            else:
                recent_days = min(30, len(self.portfolio_history) // 2)
                recent_pnl = self.portfolio_history['equity_line_pnl'].iloc[-recent_days:].mean()
                early_pnl = self.portfolio_history['equity_line_pnl'].iloc[:recent_days].mean()
                performance_trend = 1 if recent_pnl > early_pnl else -1
            
            # Volatilità dei rendimenti
            if len(self.portfolio_history) > 1:
                returns = self.portfolio_history['portfolio_value'].pct_change().dropna()
                volatility = returns.std() * np.sqrt(252)  # Annualizzata
                volatility_score = max(0, 1 - volatility / 0.5)  # Normalizzato
            else:
                volatility_score = 1
            
            # Frequenza trading
            days_range = (max(t['date'] for t in self.trades) - 
                         min(t['date'] for t in self.trades)).days
            trading_frequency = len(self.trades) / max(1, days_range / 30)  # trades per mese
            frequency_score = min(1.0, trading_frequency / 10)  # Normalizzato a 10 trades/mese
            
            # Diversificazione
            symbols = set(t.get('symbol', '') for t in self.trades)
            diversification_score = min(1.0, len(symbols) / 5)  # Normalizzato a 5 simboli
            
            # Assignment management
            if self.expired_options.empty:
                assignment_management = 1.0
            else:
                assignment_rate = self.expired_options['was_assigned'].mean()
                assignment_management = 1 - min(0.8, assignment_rate)  # Penalizza assignment > 80%
            
            # Calcolo WCS
            wcs = (
                (performance_trend + 1) / 2 * 0.3 +  # Normalizza -1,1 a 0,1
                volatility_score * 0.25 +
                frequency_score * 0.2 +
                diversification_score * 0.15 +
                assignment_management * 0.1
            ) * 100
            
            components = {
                "performance_trend": performance_trend,
                "volatility_score": volatility_score * 100,
                "trading_frequency": trading_frequency,
                "num_symbols": len(symbols),
                "assignment_rate": (self.expired_options['was_assigned'].mean() * 100) if not self.expired_options.empty else 0,
                "sustainability_rating": "Alta" if wcs > 70 else "Media" if wcs > 40 else "Bassa"
            }
            
            return {
                "WCS": wcs,
                "components": components,
                "explanation": f"WCS del {wcs:.1f}% - Sostenibilità: {components['sustainability_rating']}"
            }
            
        except Exception as e:
            return {"WCS": 0, "components": {}, "explanation": f"Errore nel calcolo: {str(e)}"}
    
    def calculate_all_metrics(self) -> Dict[str, Any]:
        """Calcola tutte le metriche avanzate."""
        return {
            "wes": self.calculate_wheel_efficiency_score(),
            "roi": self.calculate_relative_opportunity_index(),
            "drawdown": self.calculate_drawdown_tracker(),
            "recovery": self.calculate_recovery_probability(),
            "wcs": self.calculate_wheel_continuation_score()
        }
