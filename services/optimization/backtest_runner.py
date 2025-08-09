"""
Backtest runner for optimization
"""
import numpy as np
from services.optimization.base_optimizer import BaseOptimizer

class BacktestRunner(BaseOptimizer):
    """Run backtests for optimization"""
    
    def run_single_backtest(self, df, params, trading_params):
        """Run backtest for single parameter combination"""
        try:
            # Strategy parameters
            strategy_params = {
                'macd_fast': params['macd_fast'],
                'macd_slow': params['macd_slow'],
                'macd_signal': params['macd_signal'],
                'sma_length': params['sma_length']
            }
            
            # TP/SL parameters
            tp_sl_params = {
                'tp_base': params['tp_base'],
                'stop_loss': params['stop_loss'],
                'max_tps': trading_params.get('max_tps', 10),
                'tp_close': trading_params.get('tp_close', 25)
            }
            
            # Calculate indicators and signals
            df_with_indicators = self.indicator_service.calculate_indicators(df, strategy_params)
            signals = self.indicator_service.generate_signals(df_with_indicators, strategy_params)
            
            # Run backtest
            backtest_results = self.backtest_service.run_backtest(
                df_with_indicators, 
                signals, 
                trading_params['balance'], 
                trading_params['leverage'], 
                trading_params['margin'], 
                tp_sl_params
            )
            
            # Extract key metrics
            stats = backtest_results['statistics']
            
            result = {
                'parameters': params,
                'total_return': stats['total_return'],
                'win_rate': stats['win_rate'],
                'total_trades': stats['total_trades'],
                'total_pnl': stats['total_pnl'],
                'max_drawdown': stats['max_drawdown'],
                'final_balance': stats['final_balance'],
                'winning_trades': stats['winning_trades'],
                'profit_factor': self._calculate_profit_factor(backtest_results['trades']),
                'sharpe_ratio': self._calculate_sharpe_ratio(backtest_results['equity_curve']),
                'score': self._calculate_optimization_score(stats)
            }
            
            return result
            
        except Exception as e:
            print(f"Error in single backtest: {str(e)}")
            return None
    
    def _calculate_profit_factor(self, trades):
        """Calculate profit factor"""
        try:
            if not trades:
                return 0
            
            winning_trades = [t for t in trades if t['pnl'] > 0]
            losing_trades = [t for t in trades if t['pnl'] < 0]
            
            total_profit = sum(t['pnl'] for t in winning_trades)
            total_loss = abs(sum(t['pnl'] for t in losing_trades))
            
            if total_loss == 0:
                return float('inf') if total_profit > 0 else 0
            
            return total_profit / total_loss
        except:
            return 0
    
    def _calculate_sharpe_ratio(self, equity_curve):
        """Calculate Sharpe ratio"""
        try:
            if len(equity_curve) < 2:
                return 0
            
            returns = []
            for i in range(1, len(equity_curve)):
                prev_equity = equity_curve[i-1]['equity']
                curr_equity = equity_curve[i]['equity']
                if prev_equity > 0:
                    returns.append((curr_equity - prev_equity) / prev_equity)
            
            if not returns:
                return 0
            
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            
            if std_return == 0:
                return 0
            
            # Annualized Sharpe ratio (assuming daily returns)
            sharpe = (mean_return / std_return) * np.sqrt(365)
            return round(sharpe, 4)
        except:
            return 0
    
    def _calculate_optimization_score(self, stats):
        """Calculate optimization score combining multiple metrics"""
        try:
            # Weighted score combining different metrics
            total_return = stats['total_return']
            win_rate = stats['win_rate']
            max_drawdown = stats['max_drawdown']
            total_trades = stats['total_trades']
            
            # Normalize metrics
            return_score = min(total_return / 100, 5)  # Cap at 500% return
            win_rate_score = win_rate / 100
            drawdown_penalty = max(0, 1 - max_drawdown / 50)  # Penalty for high drawdown
            trade_count_bonus = min(total_trades / 100, 1)  # Bonus for more trades
            
            # Combined score (0-10 scale)
            score = (
                return_score * 0.4 +
                win_rate_score * 0.3 +
                drawdown_penalty * 0.2 +
                trade_count_bonus * 0.1
            ) * 10
            
            return round(score, 2)
        except:
            return 0