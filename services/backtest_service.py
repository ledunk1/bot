import pandas as pd
import numpy as np
from datetime import datetime

class BacktestService:
    def __init__(self):
        self.commission_rate = 0.0004  # 0.04% commission
    
    def run_backtest(self, df, signals, initial_balance, leverage, margin_ratio):
        """Run backtest simulation"""
        try:
            results = {
                'trades': [],
                'equity_curve': [],
                'statistics': {}
            }
            
            balance = initial_balance
            position = 0  # 0: no position, 1: long, -1: short
            entry_price = 0
            entry_time = None
            total_trades = 0
            winning_trades = 0
            total_pnl = 0
            max_drawdown = 0
            peak_balance = initial_balance
            
            for timestamp, row in signals.iterrows():
                current_price = row['price']
                signal = row['signal']
                
                # Close existing position if opposite signal
                if position != 0 and signal != 0 and signal != position:
                    # Calculate PnL
                    if position == 1:  # Close long
                        pnl = (current_price - entry_price) * leverage
                    else:  # Close short
                        pnl = (entry_price - current_price) * leverage
                    
                    # Apply commission
                    commission = abs(pnl) * self.commission_rate
                    net_pnl = pnl - commission
                    
                    balance += net_pnl
                    total_pnl += net_pnl
                    total_trades += 1
                    
                    if net_pnl > 0:
                        winning_trades += 1
                    
                    # Record trade
                    results['trades'].append({
                        'entry_time': entry_time,
                        'exit_time': timestamp,
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'position': 'Long' if position == 1 else 'Short',
                        'pnl': net_pnl,
                        'commission': commission
                    })
                    
                    position = 0
                
                # Open new position
                if signal != 0 and position == 0:
                    # Check if we have enough margin (margin_ratio is now percentage)
                    required_margin = (balance * margin_ratio / 100)
                    if balance >= required_margin:
                        position = signal
                        entry_price = current_price
                        entry_time = timestamp
                
                # Update equity curve
                unrealized_pnl = 0
                if position != 0:
                    if position == 1:  # Long position
                        unrealized_pnl = (current_price - entry_price) * leverage
                    else:  # Short position
                        unrealized_pnl = (entry_price - current_price) * leverage
                
                current_equity = balance + unrealized_pnl
                results['equity_curve'].append({
                    'timestamp': timestamp,
                    'balance': balance,
                    'unrealized_pnl': unrealized_pnl,
                    'equity': current_equity
                })
                
                # Track drawdown
                if current_equity > peak_balance:
                    peak_balance = current_equity
                else:
                    drawdown = (peak_balance - current_equity) / peak_balance
                    max_drawdown = max(max_drawdown, drawdown)
            
            # Calculate statistics
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            final_balance = balance
            total_return = ((final_balance - initial_balance) / initial_balance) * 100
            
            results['statistics'] = {
                'initial_balance': initial_balance,
                'final_balance': final_balance,
                'total_return': total_return,
                'total_pnl': total_pnl,
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'win_rate': win_rate,
                'max_drawdown': max_drawdown * 100,
                'leverage_used': leverage
            }
            
            return results
        except Exception as e:
            raise Exception(f"Error running backtest: {str(e)}")
    
    def prepare_chart_data(self, df, signals):
        """Prepare data for candlestick chart with signals"""
        try:
            chart_data = []
            
            for timestamp, row in df.iterrows():
                signal_info = signals.loc[timestamp] if timestamp in signals.index else None
                
                candle = {
                    'timestamp': timestamp.isoformat(),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume']),
                    'macd': float(row['macd']) if 'macd' in row and not pd.isna(row['macd']) else None,
                    'macd_signal': float(row['macd_signal']) if 'macd_signal' in row and not pd.isna(row['macd_signal']) else None,
                    'macd_histogram': float(row['macd_histogram']) if 'macd_histogram' in row and not pd.isna(row['macd_histogram']) else None,
                    'fast_ma': float(row['fast_ma']) if 'fast_ma' in row and not pd.isna(row['fast_ma']) else None,
                    'slow_ma': float(row['slow_ma']) if 'slow_ma' in row and not pd.isna(row['slow_ma']) else None,
                    'very_slow_ma': float(row['very_slow_ma']) if 'very_slow_ma' in row and not pd.isna(row['very_slow_ma']) else None
                }
                
                if signal_info is not None:
                    candle['signal'] = int(signal_info['signal'])
                    candle['signal_strength'] = float(signal_info['signal_strength'])
                else:
                    candle['signal'] = 0
                    candle['signal_strength'] = 0
                
                chart_data.append(candle)
            
            # Debug: Count signals in chart data
            buy_count = len([d for d in chart_data if d['signal'] == 1])
            sell_count = len([d for d in chart_data if d['signal'] == -1])
            print(f"Chart data prepared: {buy_count} buy signals, {sell_count} sell signals out of {len(chart_data)} candles")
            
            return chart_data
        except Exception as e:
            raise Exception(f"Error preparing chart data: {str(e)}")