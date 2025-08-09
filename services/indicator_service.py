import pandas as pd
import numpy as np
import talib
from config.settings import Config
from services.macd_sma_strategy import MACDSMAStrategy

class IndicatorService:
    def __init__(self):
        self.config = Config()
        self.macd_sma_strategy = MACDSMAStrategy()
    
    def calculate_indicators(self, df, strategy_params=None):
        """Calculate technical indicators using MACD + SMA 200 strategy"""
        try:
            if df.empty:
                raise Exception("No data available for indicator calculation")
            
            print(f"Calculating indicators for {len(df)} data points")
            print(f"Data date range: {df.index.min()} to {df.index.max()}")
            
            # Use MACD + SMA 200 strategy for indicator calculation
            result = self.macd_sma_strategy.calculate_indicators(df, strategy_params)
            
            print(f"Indicators calculated successfully for {len(result)} data points")
            return result
        except Exception as e:
            print(f"Error in calculate_indicators: {str(e)}")
            raise Exception(f"Error calculating indicators: {str(e)}")
    
    def generate_signals(self, df, strategy_params=None):
        """Generate buy/sell signals using MACD + SMA 200 strategy"""
        try:
            if df.empty:
                raise Exception("No data available for signal generation")
            
            print(f"Generating signals for {len(df)} data points")
            
            # Use MACD + SMA 200 strategy for signal generation
            result = self.macd_sma_strategy.generate_signals(df, strategy_params)
            
            # Count actual signals
            buy_signals = (result['signal'] == 1).sum()
            sell_signals = (result['signal'] == -1).sum()
            print(f"Generated {buy_signals} buy signals and {sell_signals} sell signals")
            
            return result
        except Exception as e:
            print(f"Error in generate_signals: {str(e)}")
            raise Exception(f"Error generating signals: {str(e)}")
    
    def get_strategy_info(self):
        """Get current strategy information"""
        return self.macd_sma_strategy.get_strategy_info()