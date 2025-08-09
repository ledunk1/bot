import pandas as pd
import numpy as np
import talib

class MACDSMAStrategy:
    def __init__(self, strategy_params=None):
        # Strategy parameters based on Pine Script
        if strategy_params:
            self.fast_length = strategy_params.get('macd_fast', 12)
            self.slow_length = strategy_params.get('macd_slow', 26)
            self.signal_length = strategy_params.get('macd_signal', 9)
            self.very_slow_length = strategy_params.get('sma_length', 200)
        else:
            self.fast_length = 14
            self.slow_length = 32
            self.signal_length = 10
            self.very_slow_length = 150
        self.max_intraday_loss = 50  # 50% max loss
    
    def calculate_indicators(self, df, strategy_params=None):
        """Calculate MACD and SMA indicators"""
        try:
            # Update parameters if provided
            if strategy_params:
                self.fast_length = strategy_params.get('macd_fast', self.fast_length)
                self.slow_length = strategy_params.get('macd_slow', self.slow_length)
                self.signal_length = strategy_params.get('macd_signal', self.signal_length)
                self.very_slow_length = strategy_params.get('sma_length', self.very_slow_length)
            
            if df.empty or len(df) < self.very_slow_length:
                raise Exception(f"Insufficient data points. Need at least {self.very_slow_length} candles")
            
            data = df.copy()
            
            # Calculate Simple Moving Averages for MACD (not EMA like default MACD)
            data['fast_ma'] = talib.SMA(data['close'], timeperiod=self.fast_length)
            data['slow_ma'] = talib.SMA(data['close'], timeperiod=self.slow_length)
            data['very_slow_ma'] = talib.SMA(data['close'], timeperiod=self.very_slow_length)
            
            # Calculate MACD components
            data['macd'] = data['fast_ma'] - data['slow_ma']
            data['macd_signal'] = talib.SMA(data['macd'], timeperiod=self.signal_length)
            data['macd_histogram'] = data['macd'] - data['macd_signal']
            
            # Fill NaN values
            data = data.fillna(method='ffill').fillna(method='bfill')
            
            return data
        except Exception as e:
            raise Exception(f"Error calculating MACD SMA indicators: {str(e)}")
    
    def generate_signals(self, df, strategy_params=None):
        """Generate signals based on MACD + SMA 200 strategy"""
        try:
            # Update parameters if provided
            if strategy_params:
                self.fast_length = strategy_params.get('macd_fast', self.fast_length)
                self.slow_length = strategy_params.get('macd_slow', self.slow_length)
                self.signal_length = strategy_params.get('macd_signal', self.signal_length)
                self.very_slow_length = strategy_params.get('sma_length', self.very_slow_length)
            
            if df.empty:
                raise Exception("No data available for signal generation")
            
            # Calculate indicators first
            data = self.calculate_indicators(df, strategy_params)
            
            signals = pd.DataFrame(index=data.index)
            signals['price'] = data['close']
            signals['signal'] = 0  # 0: hold, 1: buy (long), -1: sell (short)
            signals['signal_strength'] = 0.0
            
            # Get required columns
            hist = data['macd_histogram']
            macd = data['macd']
            fast_ma = data['fast_ma']
            slow_ma = data['slow_ma']
            very_slow_ma = data['very_slow_ma']
            close = data['close']
            
            # Calculate crossovers
            hist_crossover_up = (hist > 0) & (hist.shift(1) <= 0)  # crossover(hist, 0)
            hist_crossunder_down = (hist < 0) & (hist.shift(1) >= 0)  # crossunder(hist, 0)
            
            # Long entry conditions
            long_condition = (
                hist_crossover_up &  # Histogram MACD crossover ke atas 0
                (macd > 0) &  # MACD > 0 (momentum bullish)
                (fast_ma > slow_ma) &  # Fast MA > Slow MA
                (close.shift(self.slow_length) > very_slow_ma)  # Harga N bar lalu > SMA 200
            )
            
            # Short entry conditions
            short_condition = (
                hist_crossunder_down &  # Histogram MACD cross down ke bawah 0
                (macd < 0) &  # MACD < 0 (momentum bearish)
                (fast_ma < slow_ma) &  # Fast MA < Slow MA
                (close.shift(self.slow_length) < very_slow_ma)  # Harga N bar lalu < SMA 200
            )
            
            # Cancel conditions
            cancel_long = slow_ma < very_slow_ma  # Jika MA(26) < SMA(200) → cancel long
            cancel_short = slow_ma > very_slow_ma  # Jika MA(26) > SMA(200) → cancel short
            
            # Apply signals with cancel conditions
            signals.loc[long_condition & ~cancel_long, 'signal'] = 1
            signals.loc[short_condition & ~cancel_short, 'signal'] = -1
            
            # Debug: Print signal counts
            buy_signals = (signals['signal'] == 1).sum()
            sell_signals = (signals['signal'] == -1).sum()
            print(f"Generated signals: {buy_signals} buy, {sell_signals} sell")
            
            # Calculate signal strength based on MACD momentum and histogram strength
            macd_strength = np.abs(macd) / (np.abs(macd).rolling(20).mean() + 1e-8)
            hist_strength = np.abs(hist) / (np.abs(hist).rolling(20).mean() + 1e-8)
            trend_strength = np.where(
                signals['signal'] == 1,
                np.maximum(0, (close - very_slow_ma) / very_slow_ma),  # Long: price above SMA200
                np.where(
                    signals['signal'] == -1,
                    np.maximum(0, (very_slow_ma - close) / very_slow_ma),  # Short: price below SMA200
                    0
                )
            )
            
            signals['signal_strength'] = np.abs(signals['signal']) * np.minimum(1.0, (
                macd_strength * 0.4 +
                hist_strength * 0.4 +
                trend_strength * 0.2
            ))
            
            # Filter weak signals (strength < 0.2)
            weak_signals = signals['signal_strength'] < 0.2
            signals.loc[weak_signals, 'signal'] = 0
            
            # Debug: Print final signal counts after filtering
            final_buy_signals = (signals['signal'] == 1).sum()
            final_sell_signals = (signals['signal'] == -1).sum()
            print(f"Final signals after filtering: {final_buy_signals} buy, {final_sell_signals} sell")
            
            # Remove NaN values
            signals = signals.fillna(0)
            
            # Add strategy metadata
            signals['strategy'] = 'MACD_SMA200'
            signals['fast_ma'] = fast_ma
            signals['slow_ma'] = slow_ma
            signals['very_slow_ma'] = very_slow_ma
            signals['macd'] = macd
            signals['macd_signal'] = data['macd_signal']
            signals['macd_histogram'] = hist
            
            return signals
        except Exception as e:
            raise Exception(f"Error generating MACD SMA signals: {str(e)}")
    
    def get_strategy_info(self):
        """Get strategy information"""
        return {
            'name': 'MACD + SMA 200 Strategy',
            'description': 'Strategy based on MACD histogram crossovers with SMA 200 trend filter',
            'parameters': {
                'fast_length': self.fast_length,
                'slow_length': self.slow_length,
                'signal_length': self.signal_length,
                'very_slow_length': self.very_slow_length,
                'max_intraday_loss': self.max_intraday_loss
            },
            'entry_conditions': {
                'long': [
                    'MACD Histogram crossover above 0',
                    'MACD > 0 (bullish momentum)',
                    'Fast MA (12) > Slow MA (26)',
                    'Price N bars ago > SMA 200 (long-term bullish)'
                ],
                'short': [
                    'MACD Histogram crossunder below 0',
                    'MACD < 0 (bearish momentum)',
                    'Fast MA (12) < Slow MA (26)',
                    'Price N bars ago < SMA 200 (long-term bearish)'
                ]
            },
            'cancel_conditions': {
                'long': 'MA(26) < SMA(200)',
                'short': 'MA(26) > SMA(200)'
            }
        }