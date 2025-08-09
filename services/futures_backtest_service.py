import pandas as pd
import numpy as np
from datetime import datetime

class FuturesBacktestService:
    def __init__(self, tp_sl_params=None):
        self.commission_rate = 0.0004  # 0.04% commission for futures
        
        # Futures TP/SL settings (in percentage) - Unlimited TPs
        if tp_sl_params:
            self.tp_base_percent = tp_sl_params.get('tp_base', 0.75)
            self.sl_percent = tp_sl_params.get('stop_loss', 1.50)
            self.max_tps = tp_sl_params.get('max_tps', 10)
            self.tp_close_percent = tp_sl_params.get('tp_close', 25) / 100  # Convert to decimal
        else:
            self.tp_base_percent = 0.5   # Base TP percentage (50%)
            self.sl_percent = 1.25   # 125% SL
            self.max_tps = 10  # Maximum number of TPs to track
            self.tp_close_percent = 0.25  # Close 25% at each TP
        
        # Position sizing
    
    def run_backtest(self, df, signals, initial_balance, leverage, margin_ratio, tp_sl_params=None):
        """Run futures backtest with TP/SL logic"""
        try:
            # Update TP/SL parameters if provided
            if tp_sl_params:
                self.tp_base_percent = tp_sl_params.get('tp_base', self.tp_base_percent)
                self.sl_percent = tp_sl_params.get('stop_loss', self.sl_percent)
                self.max_tps = tp_sl_params.get('max_tps', self.max_tps)
                self.tp_close_percent = tp_sl_params.get('tp_close', self.tp_close_percent * 100) / 100
            
            results = {
                'trades': [],
                'equity_curve': [],
                'statistics': {},
                'tp_sl_levels': []  # Store TP/SL levels for chart
            }
            
            balance = initial_balance
            position = {
                'size': 0,  # 0: no position, positive: long size, negative: short size
                'entry_price': 0,
                'entry_time': None,
                'direction': 0,  # 1: long, -1: short
                'remaining_size': 0,
                'tps_hit': [],  # List of TP levels hit
                'trailing_stop': 0,
                'tp_levels': [],  # Current TP levels
                'sl_level': 0    # Current SL level
            }
            
            total_trades = 0
            winning_trades = 0
            total_pnl = 0
            max_drawdown = 0
            peak_balance = initial_balance
            
            print(f"Starting backtest with {len(signals)} signal data points")
            print(f"Signal date range: {signals.index.min()} to {signals.index.max()}")
            
            for timestamp, row in signals.iterrows():
                current_price = row['price']
                signal = row['signal']
                
                # Close existing position if opposite signal or TP/SL hit
                if position['size'] != 0:
                    should_close, close_reason, close_percent = self._check_exit_conditions(
                        position, current_price
                    )
                    
                    if should_close:
                        pnl, commission = self._close_position(
                            position, current_price, close_percent, leverage
                        )
                        
                        balance += pnl
                        total_pnl += pnl
                        total_trades += 1
                        
                        if pnl > 0:
                            winning_trades += 1
                        
                        # Record trade
                        results['trades'].append({
                            'entry_time': position['entry_time'],
                            'exit_time': timestamp,
                            'entry_price': position['entry_price'],
                            'exit_price': current_price,
                            'position': 'Long' if position['direction'] == 1 else 'Short',
                            'pnl': pnl,
                            'commission': commission,
                            'exit_reason': close_reason,
                            'size_closed': close_percent
                        })
                        
                        # Debug: Print trade info
                        if total_trades <= 5 or total_trades % 10 == 0:
                            print(f"Trade #{total_trades}: {timestamp.strftime('%Y-%m-%d')} - {'Long' if position['direction'] == 1 else 'Short'} - PnL: ${pnl:.2f}")
                        
                        # Update position after partial close
                        if close_percent < 1.0:
                            position['remaining_size'] *= (1 - close_percent)
                            # Update trailing stop after TP hit
                            if close_reason.startswith('TP'):
                                position['trailing_stop'] = self._calculate_trailing_stop(
                                    position, current_price
                                )
                        else:
                            # Full close - reset position
                            position = {
                                'size': 0, 'entry_price': 0, 'entry_time': None,
                                'direction': 0, 'remaining_size': 0,
                                'tps_hit': [], 'trailing_stop': 0,
                                'tp_levels': [], 'sl_level': 0
                            }
                
                # Open new position if signal and no existing position
                if signal != 0 and position['size'] == 0:
                    # Calculate position size based on margin
                    margin_amount = balance * (margin_ratio / 100)
                    position_value = margin_amount * leverage
                    position_size = position_value / current_price
                    
                    if balance >= margin_amount:
                        # Calculate TP and SL levels
                        tp_levels, sl_level = self._calculate_tp_sl_levels(current_price, signal)
                        
                        position = {
                            'size': position_size,
                            'entry_price': current_price,
                            'entry_time': timestamp,
                            'direction': signal,
                            'remaining_size': position_size,
                            'tps_hit': [],
                            'trailing_stop': 0,
                            'tp_levels': tp_levels,
                            'sl_level': sl_level
                        }
                        
                        # Store TP/SL levels for chart
                        results['tp_sl_levels'].append({
                            'timestamp': timestamp,
                            'entry_price': current_price,
                            'direction': signal,
                            'tp_levels': tp_levels,
                            'sl_level': sl_level
                        })
                        
                        print(f"New position opened: {signal} at {current_price}, TP levels: {[tp['price'] for tp in tp_levels[:3]]}, SL: {sl_level}")
                
                # Calculate unrealized PnL
                unrealized_pnl = 0
                if position['size'] != 0:
                    price_change = current_price - position['entry_price']
                    if position['direction'] == -1:  # Short position
                        price_change = -price_change
                    
                    unrealized_pnl = (price_change / position['entry_price']) * 100 * leverage * (balance * margin_ratio / 100) / 100
                
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
                'leverage_used': leverage,
                'tp_sl_settings': {
                    'tp_base': self.tp_base_percent,
                    'tp_close': self.tp_close_percent * 100,
                    'max_tps': self.max_tps,
                    'sl': self.sl_percent
                }
            }
            
            return results
        except Exception as e:
            raise Exception(f"Error running futures backtest: {str(e)}")
    
    def _calculate_tp_sl_levels(self, entry_price, direction):
        """Calculate TP and SL levels for unlimited TPs"""
        tp_levels = []
        
        # Calculate multiple TP levels (TP1, TP2, TP3, ...)
        for i in range(1, self.max_tps + 1):
            tp_percent = self.tp_base_percent * i
            
            if direction == 1:  # Long position
                tp_price = entry_price * (1 + tp_percent / 100)
            else:  # Short position
                tp_price = entry_price * (1 - tp_percent / 100)
            
            tp_levels.append({
                'level': i,
                'price': tp_price,
                'percent': tp_percent,
                'hit': False
            })
        
        # Calculate SL level
        if direction == 1:  # Long position
            sl_price = entry_price * (1 - self.sl_percent / 100)
        else:  # Short position
            sl_price = entry_price * (1 + self.sl_percent / 100)
        
        return tp_levels, sl_price
    
    def _check_exit_conditions(self, position, current_price):
        """Check if position should be closed based on TP/SL"""
        entry_price = position['entry_price']
        direction = position['direction']
        
        # Check Stop Loss - ALWAYS fixed at -1.5% from entry price
        fixed_sl = self._get_fixed_sl_level(entry_price, direction)
        if ((direction == 1 and current_price <= fixed_sl) or 
            (direction == -1 and current_price >= fixed_sl)):
            return True, "Stop Loss", 1.0
        
        # Check trailing stop (if any TP was hit)
        if position['trailing_stop'] > 0:
            # Trailing stop should never be worse than fixed SL
            effective_trailing_stop = position['trailing_stop']
            if direction == 1:
                effective_trailing_stop = max(effective_trailing_stop, fixed_sl)
                if current_price <= effective_trailing_stop:
                    return True, "Trailing Stop", 1.0
            else:  # Short
                effective_trailing_stop = min(effective_trailing_stop, fixed_sl)
                if current_price >= effective_trailing_stop:
                    return True, "Trailing Stop", 1.0
        
        # Check Take Profits (unlimited)
        for tp in position['tp_levels']:
            if not tp['hit']:
                if ((direction == 1 and current_price >= tp['price']) or 
                    (direction == -1 and current_price <= tp['price'])):
                    tp['hit'] = True
                    position['tps_hit'].append(tp['level'])
                    return True, f"TP{tp['level']}", self.tp_close_percent
        
        return False, "", 0
    
    def _get_fixed_sl_level(self, entry_price, direction):
        """Get fixed SL level at -1.5% from entry price"""
        if direction == 1:  # Long position
            return entry_price * (1 - self.sl_percent / 100)
        else:  # Short position
            return entry_price * (1 + self.sl_percent / 100)
    
    def _calculate_trailing_stop(self, position, current_price):
        """Calculate trailing stop after TP hit"""
        direction = position['direction']
        entry_price = position['entry_price']
        tps_hit_count = len(position['tps_hit'])
        fixed_sl = self._get_fixed_sl_level(entry_price, direction)
        
        if tps_hit_count == 1:
            # After first TP, set trailing stop at breakeven (entry price)
            # But never worse than fixed SL
            breakeven = entry_price
            if direction == 1:
                return max(breakeven, fixed_sl)
            else:
                return min(breakeven, fixed_sl)
        elif tps_hit_count >= 2:
            # After second TP+, set trailing stop at previous TP level
            # But never worse than fixed SL
            prev_tp_level = tps_hit_count - 1
            prev_tp_percent = self.tp_base_percent * prev_tp_level
            
            if direction == 1:  # Long
                prev_tp_price = entry_price * (1 + prev_tp_percent / 100)
                return max(prev_tp_price, fixed_sl)
            else:  # Short
                prev_tp_price = entry_price * (1 - prev_tp_percent / 100)
                return min(prev_tp_price, fixed_sl)
        
        return 0
    
    def _close_position(self, position, exit_price, close_percent, leverage):
        """Calculate PnL and commission for position close"""
        entry_price = position['entry_price']
        direction = position['direction']
        size_to_close = position['remaining_size'] * close_percent
        
        # Calculate price change
        if direction == 1:  # Long position
            price_change_percent = ((exit_price - entry_price) / entry_price) * 100
        else:  # Short position
            price_change_percent = ((entry_price - exit_price) / entry_price) * 100
        
        # Calculate PnL (percentage-based for futures)
        position_value = size_to_close * entry_price
        pnl = (price_change_percent / 100) * position_value * leverage
        
        # Calculate commission (on both entry and exit)
        commission = position_value * self.commission_rate * 2  # Entry + Exit
        
        net_pnl = pnl - commission
        
        return net_pnl, commission
    
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
            print(f"Futures chart data prepared: {buy_count} buy signals, {sell_count} sell signals out of {len(chart_data)} candles")
            
            return chart_data
        except Exception as e:
            raise Exception(f"Error preparing futures chart data: {str(e)}")