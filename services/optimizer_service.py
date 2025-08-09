import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from services.binance_service import BinanceService
from services.indicator_service import IndicatorService
from services.futures_backtest_service import FuturesBacktestService

class OptimizerService:
    def __init__(self):
        self.binance_service = BinanceService()
        self.indicator_service = IndicatorService()
        self.backtest_service = FuturesBacktestService()
        
        # Data caching
        self.cache_dir = "optimizer_cache"
        self.ensure_cache_dir()
        
        # Optimization state
        self.is_running = False
        self.current_progress = 0
        self.total_combinations = 0
        self.best_results = []
        self.optimization_thread = None
        
        # Results storage
        self.results_lock = threading.Lock()
        
    def ensure_cache_dir(self):
        """Ensure cache directory exists"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            print(f"Created cache directory: {self.cache_dir}")
    
    def get_cache_filename(self, symbol, interval, start_date, end_date):
        """Generate cache filename for data"""
        return f"{symbol}_{interval}_{start_date}_{end_date}.csv"
    
    def get_cache_filepath(self, symbol, interval, start_date, end_date):
        """Get full cache file path"""
        filename = self.get_cache_filename(symbol, interval, start_date, end_date)
        return os.path.join(self.cache_dir, filename)
    
    def load_cached_data(self, symbol, interval, start_date, end_date):
        """Load cached market data if available"""
        try:
            cache_path = self.get_cache_filepath(symbol, interval, start_date, end_date)
            
            if os.path.exists(cache_path):
                # Check if cache is not too old (max 1 day for historical data)
                cache_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_path))
                if cache_age.days <= 1:
                    print(f"Loading cached data for {symbol} from {cache_path}")
                    df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
                    return df
                else:
                    print(f"Cache expired for {symbol}, will fetch fresh data")
                    os.remove(cache_path)  # Remove expired cache
            
            return None
        except Exception as e:
            print(f"Error loading cached data for {symbol}: {str(e)}")
            return None
    
    def save_cached_data(self, df, symbol, interval, start_date, end_date):
        """Save market data to cache"""
        try:
            cache_path = self.get_cache_filepath(symbol, interval, start_date, end_date)
            df.to_csv(cache_path)
            print(f"Saved cached data for {symbol} to {cache_path}")
        except Exception as e:
            print(f"Error saving cached data for {symbol}: {str(e)}")
    
    def get_market_data(self, symbol, interval, start_date, end_date):
        """Get market data with caching"""
        try:
            # Try to load from cache first
            cached_data = self.load_cached_data(symbol, interval, start_date, end_date)
            if cached_data is not None and not cached_data.empty:
                return cached_data
            
            # Fetch fresh data if not cached
            print(f"Fetching fresh data for {symbol}...")
            df = self.binance_service.get_klines(symbol, interval, start_date, end_date)
            
            if not df.empty:
                # Save to cache
                self.save_cached_data(df, symbol, interval, start_date, end_date)
                return df
            else:
                raise Exception(f"No data received for {symbol}")
                
        except Exception as e:
            print(f"Error getting market data for {symbol}: {str(e)}")
            raise e
    
    def generate_parameter_combinations(self, param_ranges):
        """Generate all parameter combinations"""
        try:
            # Extract parameter ranges
            macd_fast_range = range(param_ranges['macd_fast']['min'], 
                                  param_ranges['macd_fast']['max'] + 1, 
                                  param_ranges['macd_fast']['step'])
            
            macd_slow_range = range(param_ranges['macd_slow']['min'], 
                                  param_ranges['macd_slow']['max'] + 1, 
                                  param_ranges['macd_slow']['step'])
            
            macd_signal_range = range(param_ranges['macd_signal']['min'], 
                                    param_ranges['macd_signal']['max'] + 1, 
                                    param_ranges['macd_signal']['step'])
            
            sma_length_range = range(param_ranges['sma_length']['min'], 
                                   param_ranges['sma_length']['max'] + 1, 
                                   param_ranges['sma_length']['step'])
            
            tp_base_values = np.arange(param_ranges['tp_base']['min'], 
                                     param_ranges['tp_base']['max'] + param_ranges['tp_base']['step'], 
                                     param_ranges['tp_base']['step'])
            
            stop_loss_values = np.arange(param_ranges['stop_loss']['min'], 
                                       param_ranges['stop_loss']['max'] + param_ranges['stop_loss']['step'], 
                                       param_ranges['stop_loss']['step'])
            
            # Generate all combinations
            combinations = list(itertools.product(
                macd_fast_range,
                macd_slow_range, 
                macd_signal_range,
                sma_length_range,
                tp_base_values,
                stop_loss_values
            ))
            
            # Filter valid combinations (fast < slow)
            valid_combinations = []
            for combo in combinations:
                macd_fast, macd_slow, macd_signal, sma_length, tp_base, stop_loss = combo
                if macd_fast < macd_slow:  # Valid MACD configuration
                    valid_combinations.append({
                        'macd_fast': macd_fast,
                        'macd_slow': macd_slow,
                        'macd_signal': macd_signal,
                        'sma_length': sma_length,
                        'tp_base': round(tp_base, 2),
                        'stop_loss': round(stop_loss, 2)
                    })
            
            print(f"Generated {len(valid_combinations)} valid parameter combinations")
            return valid_combinations
            
        except Exception as e:
            raise Exception(f"Error generating parameter combinations: {str(e)}")
    
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
    
    def start_optimization(self, optimization_params):
        """Start optimization process"""
        if self.is_running:
            return False, "Optimization is already running"
        
        try:
            self.is_running = True
            self.current_progress = 0
            self.best_results = []
            
            # Start optimization in separate thread
            self.optimization_thread = threading.Thread(
                target=self._run_optimization,
                args=(optimization_params,),
                daemon=True
            )
            self.optimization_thread.start()
            
            return True, "Optimization started successfully"
            
        except Exception as e:
            self.is_running = False
            return False, f"Error starting optimization: {str(e)}"
    
    def _run_optimization(self, optimization_params):
        """Run the optimization process"""
        try:
            print("Starting optimization process...")
            
            # Extract parameters
            symbol = optimization_params['symbol']
            interval = optimization_params['interval']
            start_date = optimization_params['start_date']
            end_date = optimization_params['end_date']
            param_ranges = optimization_params['param_ranges']
            trading_params = optimization_params['trading_params']
            max_workers = optimization_params.get('max_workers', 4)
            
            # Get market data (with caching)
            print(f"Getting market data for {symbol}...")
            df = self.get_market_data(symbol, interval, start_date, end_date)
            
            if df.empty:
                raise Exception("No market data available")
            
            # Generate parameter combinations
            combinations = self.generate_parameter_combinations(param_ranges)
            self.total_combinations = len(combinations)
            
            print(f"Testing {self.total_combinations} parameter combinations...")
            
            # Run optimization with parallel processing
            results = []
            completed = 0
            progress_lock = threading.Lock()  # Thread-safe progress tracking
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_params = {
                    executor.submit(self.run_single_backtest, df, params, trading_params): params
                    for params in combinations
                }
                
                # Process completed tasks
                for future in as_completed(future_to_params):
                    if not self.is_running:  # Check if optimization was stopped
                        break
                        
                    try:
                        result = future.result()
                        if result is not None:
                            results.append(result)
                        
                        # Thread-safe progress update
                        with progress_lock:
                            completed += 1
                            # Fix progress calculation to show actual completed count
                            self.current_progress = completed
                        
                        # Print progress every 10%
                        if completed % max(1, self.total_combinations // 10) == 0:
                            progress_percent = (completed / self.total_combinations) * 100
                            print(f"Progress: {completed}/{self.total_combinations} ({progress_percent:.1f}%)")
                            
                    except Exception as e:
                        print(f"Error in backtest: {str(e)}")
                        # Thread-safe progress update for errors too
                        with progress_lock:
                            completed += 1
                            self.current_progress = completed
            
            # Sort results by optimization score
            results.sort(key=lambda x: x['score'], reverse=True)
            
            # Store best results
            with self.results_lock:
                self.best_results = results[:100]  # Keep top 100 results
            
            # Save results to file
            self._save_optimization_results(results, optimization_params)
            
            print(f"Optimization completed! Found {len(results)} valid results.")
            print(f"Best result: Score {results[0]['score']:.2f}, Return {results[0]['total_return']:.2f}%")
            
        except Exception as e:
            print(f"Error in optimization: {str(e)}")
        finally:
            self.is_running = False
            self.current_progress = self.total_combinations  # Set to total when complete
    
    def _save_optimization_results(self, results, optimization_params):
        """Save optimization results to file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"optimization_results_{optimization_params['symbol']}_{timestamp}.json"
            filepath = os.path.join(self.cache_dir, filename)
            
            # Prepare data for saving
            save_data = {
                'optimization_params': optimization_params,
                'timestamp': timestamp,
                'total_combinations': len(results),
                'results': results[:100]  # Save top 100 results
            }
            
            with open(filepath, 'w') as f:
                json.dump(save_data, f, indent=2, default=str)
            
            print(f"Optimization results saved to {filepath}")
            
        except Exception as e:
            print(f"Error saving optimization results: {str(e)}")
    
    def stop_optimization(self):
        """Stop optimization process"""
        if self.is_running:
            self.is_running = False
            print("Stopping optimization...")
            return True
        return False
    
    def get_optimization_status(self):
        """Get current optimization status"""
        with self.results_lock:
            # Calculate progress percentage for display (ensure it doesn't exceed 100%)
            if self.total_combinations > 0:
                progress_percent = min((self.current_progress / self.total_combinations) * 100, 100.0)
            else:
                progress_percent = 0
            
            return {
                'is_running': self.is_running,
                'progress': round(progress_percent, 2),
                'completed': self.current_progress,
                'total_combinations': self.total_combinations,
                'best_results_count': len(self.best_results),
                'best_results': self.best_results[:20] if self.best_results else []  # Return top 20
            }
    
    def get_cached_files(self):
        """Get list of cached data files"""
        try:
            cached_files = []
            if os.path.exists(self.cache_dir):
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith('.csv'):
                        filepath = os.path.join(self.cache_dir, filename)
                        file_size = os.path.getsize(filepath)
                        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                        
                        cached_files.append({
                            'filename': filename,
                            'size': file_size,
                            'created': file_time.strftime('%Y-%m-%d %H:%M:%S'),
                            'age_hours': (datetime.now() - file_time).total_seconds() / 3600
                        })
            
            return cached_files
        except Exception as e:
            print(f"Error getting cached files: {str(e)}")
            return []
    
    def clear_cache(self, older_than_hours=24):
        """Clear cached files older than specified hours"""
        try:
            cleared_count = 0
            if os.path.exists(self.cache_dir):
                current_time = datetime.now()
                
                for filename in os.listdir(self.cache_dir):
                    filepath = os.path.join(self.cache_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                    age_hours = (current_time - file_time).total_seconds() / 3600
                    
                    if age_hours > older_than_hours:
                        os.remove(filepath)
                        cleared_count += 1
                        print(f"Removed cached file: {filename}")
            
            return cleared_count
        except Exception as e:
            print(f"Error clearing cache: {str(e)}")
            return 0