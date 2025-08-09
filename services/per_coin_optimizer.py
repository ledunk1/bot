"""
Per-coin optimizer service - Main orchestrator
"""
import json
import os
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.optimization.base_optimizer import BaseOptimizer
from services.optimization.parameter_generator import ParameterGenerator
from services.optimization.backtest_runner import BacktestRunner
from services.coin_settings_manager import CoinSettingsManager
from utils.date_utils import validate_date_range

class PerCoinOptimizer(BaseOptimizer):
    """Per-coin optimization service"""
    
    def __init__(self):
        super().__init__()
        self.backtest_runner = BacktestRunner()
        self.coin_settings_manager = CoinSettingsManager()
        
        # Per-coin optimization state
        self.is_running = False
        self.current_symbol = ""
        self.current_symbol_index = 0
        self.total_symbols = 0
        self.current_symbol_progress = 0
        self.total_combinations = 0
        self.best_results = {}  # Results per symbol
        self.optimization_thread = None
        
        # Queue management
        self.symbols_queue = []
        self.completed_symbols = []
        self.failed_symbols = []
        
        # Pre-calculated combinations cache
        self.combinations_cache = {}
        self.combinations_cache_file = os.path.join(self.cache_dir, "parameter_combinations.json")
        
        # Symbol data cache
        self.symbols_data_cache = {}
        self.symbols_cache_file = os.path.join(self.cache_dir, "symbols_data_cache.json")
        self.bulk_data_cache_dir = os.path.join(self.cache_dir, "bulk_symbol_data")
        self.ensure_bulk_cache_dir()
    
    def ensure_bulk_cache_dir(self):
        """Ensure bulk cache directory exists"""
        if not os.path.exists(self.bulk_data_cache_dir):
            os.makedirs(self.bulk_data_cache_dir)
            print(f"Created bulk cache directory: {self.bulk_data_cache_dir}")
        
    def get_all_available_symbols(self):
        """Get all available symbols"""
        try:
            symbols_data = self.binance_service.get_futures_symbols()
            return [s['symbol'] for s in symbols_data]
        except Exception as e:
            print(f"Error getting all symbols: {str(e)}")
            return []
    
    def get_bulk_cache_key(self, symbols, interval, start_date, end_date):
        """Generate cache key for bulk symbol data"""
        symbols_hash = str(hash(tuple(sorted(symbols))))
        return f"bulk_{symbols_hash}_{interval}_{start_date}_{end_date}"
    
    def save_bulk_symbol_data(self, symbols_data, cache_key):
        """Save bulk symbol data to cache"""
        try:
            cache_file = os.path.join(self.bulk_data_cache_dir, f"{cache_key}.json")
            
            # Convert DataFrames to dict for JSON serialization
            serializable_data = {}
            for symbol, df in symbols_data.items():
                if df is not None and not df.empty:
                    # Convert DataFrame to dict with timestamp as string
                    df_dict = df.reset_index().to_dict('records')
                    # Convert timestamps to string
                    for record in df_dict:
                        if 'timestamp' in record:
                            record['timestamp'] = record['timestamp'].isoformat()
                    serializable_data[symbol] = df_dict
            
            with open(cache_file, 'w') as f:
                json.dump({
                    'data': serializable_data,
                    'timestamp': datetime.now().isoformat(),
                    'symbols_count': len(serializable_data)
                }, f, indent=2)
            
            print(f"💾 Saved bulk data for {len(serializable_data)} symbols to cache")
            return True
            
        except Exception as e:
            print(f"Error saving bulk symbol data: {str(e)}")
            return False
    
    def load_bulk_symbol_data(self, cache_key):
        """Load bulk symbol data from cache"""
        try:
            cache_file = os.path.join(self.bulk_data_cache_dir, f"{cache_key}.json")
            
            if not os.path.exists(cache_file):
                return None
            
            # Check cache age (max 1 day)
            cache_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))
            if cache_age.days > 1:
                print(f"Bulk cache expired, removing: {cache_file}")
                os.remove(cache_file)
                return None
            
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Convert back to DataFrames
            symbols_data = {}
            for symbol, records in cache_data['data'].items():
                if records:
                    import pandas as pd
                    df = pd.DataFrame(records)
                    # Convert timestamp back to datetime
                    if 'timestamp' in df.columns:
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        df.set_index('timestamp', inplace=True)
                    symbols_data[symbol] = df
            
            print(f"📁 Loaded bulk data for {len(symbols_data)} symbols from cache")
            return symbols_data
            
        except Exception as e:
            print(f"Error loading bulk symbol data: {str(e)}")
            return None
    
    def fetch_all_symbols_data_bulk(self, symbols, interval, start_date, end_date, max_workers=8):
        """Fetch market data for all symbols in parallel with caching"""
        try:
            # Check cache first
            cache_key = self.get_bulk_cache_key(symbols, interval, start_date, end_date)
            cached_data = self.load_bulk_symbol_data(cache_key)
            
            if cached_data:
                print(f"🚀 Using cached bulk data for {len(cached_data)} symbols")
                return cached_data
            
            print(f"🔄 Fetching market data for {len(symbols)} symbols in parallel with {max_workers} workers...")
            symbols_data = {}
            completed = 0
            
            # Use ThreadPoolExecutor for parallel data fetching
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all data fetching tasks
                future_to_symbol = {
                    executor.submit(self._fetch_single_symbol_data_with_retry, symbol, interval, start_date, end_date): symbol
                    for symbol in symbols
                }
                
                # Process completed tasks
                for future in as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    try:
                        df = future.result()
                        symbols_data[symbol] = df
                        completed += 1
                        
                        # Progress indicator
                        if completed % 10 == 0 or completed == len(symbols):
                            progress = (completed / len(symbols)) * 100
                            print(f"  Progress: {completed}/{len(symbols)} ({progress:.1f}%)")
                            
                    except Exception as e:
                        print(f"  ❌ Failed to fetch {symbol}: {str(e)}")
                        symbols_data[symbol] = None
                        completed += 1
            
            # Save to cache
            self.save_bulk_symbol_data(symbols_data, cache_key)
            
            # Filter out failed symbols
            valid_symbols_data = {k: v for k, v in symbols_data.items() if v is not None and not v.empty}
            
            print(f"✅ Successfully fetched data for {len(valid_symbols_data)}/{len(symbols)} symbols")
            return valid_symbols_data
            
        except Exception as e:
            print(f"Error in bulk symbol data fetch: {str(e)}")
            return {}
    
    def _fetch_single_symbol_data_with_retry(self, symbol, interval, start_date, end_date, max_retries=3):
        """Fetch data for a single symbol with retry logic"""
        for attempt in range(max_retries):
            try:
                # Add small delay to avoid rate limiting
                time.sleep(0.5 * attempt)  # Progressive delay
                
                df = self.get_market_data(symbol, interval, start_date, end_date)
                if df is not None and not df.empty:
                    return df
                else:
                    raise Exception(f"Empty data received for {symbol}")
                    
            except Exception as e:
                if attempt == max_retries - 1:  # Last attempt
                    print(f"❌ Failed to fetch {symbol} after {max_retries} attempts: {str(e)}")
                    raise e
                else:
                    print(f"⚠️ Retry {attempt + 1}/{max_retries} for {symbol}: {str(e)}")
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        return None
    
    def _fetch_single_symbol_data(self, symbol, interval, start_date, end_date):
        """Fetch data for a single symbol (legacy method)"""
        try:
            return self.get_market_data(symbol, interval, start_date, end_date)
        except Exception as e:
            print(f"Error fetching {symbol}: {str(e)}")
            return None
    
    def get_popular_symbols(self, count=50):
        """Get popular symbols (top by volume/market cap)"""
        try:
            # Popular symbols list (you can enhance this with real-time volume data)
            popular_symbols = [
                'BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT',
                'LINKUSDT', 'AVAXUSDT', 'MATICUSDT', 'ATOMUSDT', 'NEARUSDT',
                'UNIUSDT', 'LTCUSDT', 'BCHUSDT', 'XLMUSDT', 'VETUSDT',
                'FILUSDT', 'TRXUSDT', 'ETCUSDT', 'XMRUSDT', 'EOSUSDT',
                'AAVEUSDT', 'MKRUSDT', 'COMPUSDT', 'YFIUSDT', 'SUSHIUSDT',
                'SNXUSDT', 'CRVUSDT', 'BALUSDT', '1INCHUSDT', 'ENJUSDT',
                'MANAUSDT', 'SANDUSDT', 'CHZUSDT', 'GALAUSDT', 'AXSUSDT',
                'FLOWUSDT', 'FTMUSDT', 'HBARUSDT', 'ICPUSDT', 'THETAUSDT',
                'ALGOUSDT', 'EGLDUSDT', 'ZILUSDT', 'KSMUSDT', 'WAVESUSDT',
                'OMGUSDT', 'QTUMUSDT', 'BATUSDT', 'ZRXUSDT', 'STORJUSDT',
                'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'SHIBUSDT', 'PEPEUSDT',
                'WIFUSDT', 'BONKUSDT', 'FLOKIUSDT', 'ORDIUSDT', 'INJUSDT',
                'TIAUSDT', 'SUIUSDT', 'APTUSDT', 'ARBUSDT', 'OPUSDT',
                'STXUSDT', 'RNDRUSDT', 'FETUSDT', 'AGIXUSDT', 'OCEANUSDT',
                'GRTUSDT', 'BANDUSDT', 'RLCUSDT', 'NUUSDT', 'CTSIUSDT',
                'STORJUSDT', 'SKLUSDT', 'ANKRUSDT', 'CHRUSDT', 'LITUSDT',
                'MTLUSDT', 'OGNUSDT', 'NKNUSDT', 'SCUSDT', 'DGBUSDT',
                'BTTUSDT', 'HOTUSDT', 'IOTXUSDT', 'ONEUSDT', 'ZILUSDT',
                'ICXUSDT', 'QTUMAUSDT', 'ONTUSDT', 'ZECUSDT', 'DASHUSDT',
                'XTZUSDT', 'RVNUSDT', 'DCRUSDT', 'BATUSDT', 'ENJUSDT'
            ]
            
            # Get available symbols
            all_symbols = self.get_all_available_symbols()
            available_symbols = set(all_symbols)
            
            # Filter popular symbols that are available
            filtered_symbols = [s for s in popular_symbols if s in available_symbols]
            
            # If we need more symbols, add from available symbols
            if len(filtered_symbols) < count:
                remaining_symbols = [s for s in all_symbols if s not in filtered_symbols]
                filtered_symbols.extend(remaining_symbols[:count - len(filtered_symbols)])
            
            return filtered_symbols[:count]
            
        except Exception as e:
            print(f"Error getting popular symbols: {str(e)}")
            return ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT']
    
    def _get_combinations_cache_key(self, param_ranges):
        """Generate cache key for parameter combinations"""
        return str(sorted(param_ranges.items()))
    
    def _load_combinations_cache(self):
        """Load pre-calculated combinations from cache"""
        try:
            if os.path.exists(self.combinations_cache_file):
                with open(self.combinations_cache_file, 'r') as f:
                    self.combinations_cache = json.load(f)
                print(f"📁 Loaded {len(self.combinations_cache)} cached parameter combinations")
            else:
                self.combinations_cache = {}
        except Exception as e:
            print(f"Error loading combinations cache: {str(e)}")
            self.combinations_cache = {}
    
    def _save_combinations_cache(self):
        """Save parameter combinations to cache"""
        try:
            with open(self.combinations_cache_file, 'w') as f:
                json.dump(self.combinations_cache, f, indent=2)
            print(f"💾 Saved parameter combinations cache with {len(self.combinations_cache)} entries")
        except Exception as e:
            print(f"Error saving combinations cache: {str(e)}")
    
    def _get_or_generate_combinations(self, param_ranges):
        """Get combinations from cache or generate new ones"""
        cache_key = self._get_combinations_cache_key(param_ranges)
        
        # Load cache if not already loaded
        if not hasattr(self, 'combinations_cache') or not self.combinations_cache:
            self._load_combinations_cache()
        
        # Check if combinations exist in cache
        if cache_key in self.combinations_cache:
            print(f"📋 Using cached parameter combinations ({len(self.combinations_cache[cache_key])} combinations)")
            return self.combinations_cache[cache_key]
        
        # Generate new combinations
        print("🔄 Generating new parameter combinations...")
        combinations = ParameterGenerator.generate_parameter_combinations(param_ranges)
        
        # Save to cache
        self.combinations_cache[cache_key] = combinations
        self._save_combinations_cache()
        
        return combinations
    
    def get_optimization_queue_estimate(self, symbols, optimization_params):
        """Get optimization time estimate"""
        try:
            # Get or generate combinations
            combinations = self._get_or_generate_combinations(optimization_params['param_ranges'])
            
            # Use the actual combinations count
            optimization_params_copy = optimization_params.copy()
            optimization_params_copy['combinations_count'] = len(combinations)
            
            return ParameterGenerator.get_optimization_queue_estimate(symbols, optimization_params_copy)
        except Exception as e:
            print(f"Error getting optimization estimate: {str(e)}")
            return {'error': str(e), 'total_symbols': len(symbols) if symbols else 0}
    
    def start_per_coin_optimization(self, symbols, optimization_params):
        """Start per-coin optimization"""
        if self.is_running:
            return False, "Per-coin optimization is already running"
        
        try:
            # Validate parameters
            if not symbols:
                return False, "No symbols provided for optimization"
            
            # Filter out symbols that already have optimization results
            original_count = len(symbols)
            symbols = self._filter_unoptimized_symbols(symbols)
            skipped_count = original_count - len(symbols)
            
            if skipped_count > 0:
                print(f"⏭️ Skipped {skipped_count} symbols that already have optimization results")
                print(f"📊 Remaining symbols to optimize: {len(symbols)}")
            
            if len(symbols) == 0:
                return False, "All symbols already have optimization results. Use 'Force Re-optimize' to override."
            
            # Ensure minimum 10 symbols for per-coin optimization
            if len(symbols) < 10:
                print(f"⚠️ Warning: Only {len(symbols)} symbols provided. Minimum recommended: 10")
            
            if not validate_date_range(optimization_params['start_date'], optimization_params['end_date']):
                return False, "Invalid date range"
            
            # Initialize state
            self.is_running = True
            self.symbols_queue = symbols.copy()
            self.completed_symbols = []
            self.failed_symbols = []
            self.best_results = {}
            self.total_symbols = len(symbols)
            self.current_symbol_index = 0
            self.current_symbol_progress = 0
            
            # Get or generate parameter combinations (with caching)
            combinations = self._get_or_generate_combinations(optimization_params['param_ranges'])
            self.total_combinations = len(combinations)
            
            print(f"🚀 Starting per-coin optimization for {self.total_symbols} symbols")
            print(f"📊 Testing {self.total_combinations} parameter combinations per symbol")
            print(f"⚡ Total combinations: {self.total_symbols * self.total_combinations:,}")
            
            # Start optimization in separate thread
            self.optimization_thread = threading.Thread(
                target=self._run_per_coin_optimization,
                args=(symbols, optimization_params, combinations),
                daemon=True
            )
            self.optimization_thread.start()
            
            return True, f"Per-coin optimization started for {self.total_symbols} symbols"
            
        except Exception as e:
            self.is_running = False
            return False, f"Error starting per-coin optimization: {str(e)}"
    
    def _filter_unoptimized_symbols(self, symbols):
        """Filter out symbols that already have optimization results"""
        try:
            unoptimized_symbols = []
            
            for symbol in symbols:
                coin_settings = self.coin_settings_manager.load_coin_settings(symbol)
                
                # Check if symbol has optimization results (score > 0)
                if coin_settings.get('optimization_score', 0) <= 0:
                    unoptimized_symbols.append(symbol)
                else:
                    optimization_date = coin_settings.get('optimization_date', 'Unknown')
                    score = coin_settings.get('optimization_score', 0)
                    print(f"⏭️ Skipping {symbol} (Score: {score:.2f}, Date: {optimization_date})")
            
            return unoptimized_symbols
            
        except Exception as e:
            print(f"Error filtering symbols: {str(e)}")
            return symbols  # Return original list if error
    
    def start_per_coin_optimization_force(self, symbols, optimization_params):
        """Start per-coin optimization with force re-optimize (skip filtering)"""
        if self.is_running:
            return False, "Per-coin optimization is already running"
        
        try:
            # Validate parameters
            if not symbols:
                return False, "No symbols provided for optimization"
            
            print(f"🔄 Force re-optimization mode: Processing all {len(symbols)} symbols")
            
            # Ensure minimum 10 symbols for per-coin optimization
            if len(symbols) < 10:
                print(f"⚠️ Warning: Only {len(symbols)} symbols provided. Minimum recommended: 10")
            
            if not validate_date_range(optimization_params['start_date'], optimization_params['end_date']):
                return False, "Invalid date range"
            
            # Initialize state
            self.is_running = True
            self.symbols_queue = symbols.copy()
            self.completed_symbols = []
            self.failed_symbols = []
            self.best_results = {}
            self.total_symbols = len(symbols)
            self.current_symbol_index = 0
            self.current_symbol_progress = 0
            
            # Get or generate parameter combinations (with caching)
            combinations = self._get_or_generate_combinations(optimization_params['param_ranges'])
            self.total_combinations = len(combinations)
            
            print(f"🚀 Starting FORCE per-coin optimization for {self.total_symbols} symbols")
            print(f"📊 Testing {self.total_combinations} parameter combinations per symbol")
            print(f"⚡ Total combinations: {self.total_symbols * self.total_combinations:,}")
            
            # Start optimization in separate thread
            self.optimization_thread = threading.Thread(
                target=self._run_per_coin_optimization,
                args=(symbols, optimization_params, combinations),
                daemon=True
            )
            self.optimization_thread.start()
            
            return True, f"Force per-coin optimization started for {self.total_symbols} symbols"
            
        except Exception as e:
            self.is_running = False
            return False, f"Error starting force per-coin optimization: {str(e)}"
    
    def _run_per_coin_optimization(self, symbols, optimization_params, combinations):
        """Run the per-coin optimization process"""
        try:
            print("🔄 Starting per-coin optimization process...")
            
            # Extract parameters
            interval = optimization_params['interval']
            start_date = optimization_params['start_date']
            end_date = optimization_params['end_date']
            trading_params = optimization_params['trading_params']
            max_workers = optimization_params.get('max_workers', 4)
            
            # Fetch all symbols data in bulk (parallel)
            print("📊 Fetching market data for all symbols in parallel...")
            bulk_symbols_data = self.fetch_all_symbols_data_bulk(
                symbols, interval, start_date, end_date, max_workers=1  # Sequential processing
            )
            
            if not bulk_symbols_data:
                print("❌ No market data available for any symbols")
                return
            
            # Filter symbols to only those with valid data
            valid_symbols = [s for s in symbols if s in bulk_symbols_data and bulk_symbols_data[s] is not None]
            print(f"✅ Valid symbols with data: {len(valid_symbols)}/{len(symbols)}")
            
            # Update total symbols count
            self.total_symbols = len(valid_symbols)
            
            # Process symbols in batches of 10 for optimization
            self._process_symbols_in_batches(valid_symbols, bulk_symbols_data, combinations, trading_params, max_workers)
            
            # Save summary results
            self._save_per_coin_results(valid_symbols, optimization_params)
            
            print(f"\n🎉 Per-coin optimization completed!")
            print(f"✅ Successful: {len(self.completed_symbols)}")
            print(f"❌ Failed: {len(self.failed_symbols)}")
            
        except Exception as e:
            print(f"❌ Error in per-coin optimization: {str(e)}")
        finally:
            self.is_running = False
            self.current_symbol = ""
    
    def _process_symbols_in_batches(self, valid_symbols, bulk_symbols_data, combinations, trading_params, max_workers=8):
        """Process symbols in batches with enhanced concurrent optimization"""
        try:
            # Dynamic batch size based on available workers and symbols
            batch_size = min(max_workers * 2, 20)  # Process up to 20 symbols simultaneously
            total_batches = (len(valid_symbols) + batch_size - 1) // batch_size
            
            print(f"🔄 Processing {len(valid_symbols)} symbols in {total_batches} batches of {batch_size}")
            print(f"⚡ Using {max_workers} workers per batch for parallel optimization")
            
            for batch_index in range(0, len(valid_symbols), batch_size):
                if not self.is_running:  # Check if optimization was stopped
                    break
                
                batch_symbols = valid_symbols[batch_index:batch_index + batch_size]
                current_batch = (batch_index // batch_size) + 1
                
                print(f"\n📦 Processing batch {current_batch}/{total_batches}: {batch_symbols}")
                
                # Process batch with enhanced ThreadPoolExecutor
                actual_workers = min(len(batch_symbols), max_workers)
                with ThreadPoolExecutor(max_workers=actual_workers) as executor:
                    # Submit optimization tasks for current batch
                    future_to_symbol = {}
                    for symbol in batch_symbols:
                        if symbol in bulk_symbols_data and bulk_symbols_data[symbol] is not None:
                            future = executor.submit(
                                self._optimize_symbol_with_tracking,
                                symbol, bulk_symbols_data[symbol], combinations, trading_params, 
                                min(4, max_workers)  # Nested parallelism with limited workers
                            )
                            future_to_symbol[future] = symbol
                    
                    print(f"  📊 Submitted {len(future_to_symbol)} optimization tasks with {actual_workers} workers")
                    
                    # Process completed optimizations as they finish
                    for future in as_completed(future_to_symbol):
                        if not self.is_running:  # Check if optimization was stopped
                            break
                            
                        symbol = future_to_symbol[future]
                        try:
                            success, result = future.result()
                            
                            if success and result:
                                # Store best result
                                self.best_results[symbol] = result
                                
                                # Save to coin settings
                                save_success = self.coin_settings_manager.save_optimization_result(symbol, result)
                                
                                if save_success:
                                    print(f"✅ {symbol} optimization completed - Score: {result['score']:.2f}, Return: {result['total_return']:.2f}%")
                                    self.completed_symbols.append(symbol)
                                else:
                                    print(f"⚠️ {symbol} optimization completed but failed to save settings")
                                    self.failed_symbols.append(symbol)
                            else:
                                print(f"❌ {symbol} optimization failed")
                                self.failed_symbols.append(symbol)
                                
                        except Exception as e:
                            print(f"❌ Error in {symbol} optimization: {str(e)}")
                            self.failed_symbols.append(symbol)
                
                # Progress update after batch completion
                completed_count = len(self.completed_symbols) + len(self.failed_symbols)
                progress = (completed_count / len(valid_symbols)) * 100
                print(f"📊 Batch {current_batch} completed. Overall progress: {completed_count}/{len(valid_symbols)} ({progress:.1f}%)")
                
                # Small delay between batches to prevent system overload
                if current_batch < total_batches:
                    time.sleep(2)
                
        except Exception as e:
            print(f"❌ Error processing symbol batches: {str(e)}")
    
    def _optimize_symbol_with_tracking(self, symbol, df, combinations, trading_params, max_workers=4):
        """Optimize single symbol with progress tracking"""
        try:
            # Update current symbol for status tracking
            symbol_index = len(self.completed_symbols) + len(self.failed_symbols)
            self.current_symbol = symbol
            self.current_symbol_index = symbol_index
            self.current_symbol_progress = 0
            
            print(f"📈 Optimizing {symbol} ({symbol_index + 1}/{self.total_symbols})")
            
            if df.empty:
                print(f"❌ No data available for {symbol}")
                return False, None
            
            # Run optimization for this symbol
            symbol_results = self._optimize_single_symbol(
                symbol, df, combinations, trading_params, max_workers
            )
            
            if symbol_results:
                best_result = symbol_results[0]  # Already sorted by score
                print(f"  🎯 Best result for {symbol}: Score {best_result['score']:.2f}, Return {best_result['total_return']:.2f}%")
                return True, best_result
            else:
                return False, None
                
        except Exception as e:
            print(f"❌ Error optimizing {symbol}: {str(e)}")
            return False, None
    
    def _optimize_single_symbol(self, symbol, df, combinations, trading_params, max_workers=4):
        """Optimize single symbol"""
        try:
            results = []
            completed = 0
            total_combinations = len(combinations)
            
            print(f"  🔄 Testing {total_combinations} parameter combinations for {symbol}")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks for this symbol
                future_to_params = {
                    executor.submit(self.backtest_runner.run_single_backtest, df, params, trading_params): params
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
                        
                        completed += 1
                        self.current_symbol_progress = completed
                        
                        # Print progress every 10%
                        if completed % max(1, total_combinations // 5) == 0:
                            progress_percent = (completed / total_combinations) * 100
                            print(f"  Progress: {completed}/{len(combinations)} ({progress_percent:.1f}%)")
                            
                    except Exception as e:
                        print(f"  Error in backtest: {str(e)}")
                        completed += 1
                        self.current_symbol_progress = completed
            
            # Sort results by optimization score
            results.sort(key=lambda x: x['score'], reverse=True)
            
            if results:
                print(f"  ✅ {symbol} optimization completed: {len(results)} valid results")
            
            return results
            
        except Exception as e:
            print(f"Error optimizing {symbol}: {str(e)}")
            return []
    
    def _save_per_coin_results(self, symbols, optimization_params):
        """Save per-coin optimization results"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"per_coin_optimization_results_{timestamp}.json"
            filepath = os.path.join(self.cache_dir, filename)
            
            # Prepare summary data
            summary_data = {
                'optimization_params': optimization_params,
                'timestamp': timestamp,
                'total_symbols': len(symbols),
                'completed_symbols': len(self.completed_symbols),
                'failed_symbols': len(self.failed_symbols),
                'symbols_processed': symbols,
                'completed_list': self.completed_symbols,
                'failed_list': self.failed_symbols,
                'best_results_summary': {}
            }
            
            # Add best results summary
            for symbol, result in self.best_results.items():
                summary_data['best_results_summary'][symbol] = {
                    'score': result['score'],
                    'total_return': result['total_return'],
                    'win_rate': result['win_rate'],
                    'total_trades': result['total_trades'],
                    'parameters': result['parameters']
                }
            
            with open(filepath, 'w') as f:
                json.dump(summary_data, f, indent=2, default=str)
            
            print(f"📁 Per-coin optimization results saved to {filepath}")
            
        except Exception as e:
            print(f"Error saving per-coin optimization results: {str(e)}")
    
    def stop_optimization(self):
        """Stop per-coin optimization"""
        if self.is_running:
            self.is_running = False
            print("🛑 Stopping per-coin optimization...")
            return True
        return False
    
    def get_status(self):
        """Get per-coin optimization status"""
        with self.results_lock:
            # Calculate overall progress (fixed calculation)
            overall_progress = 0
            if self.total_symbols > 0:
                # Progress from completed symbols
                completed_symbols_progress = (len(self.completed_symbols) / self.total_symbols) * 100
                
                # Progress from current symbol
                current_symbol_contribution = 0
                if self.total_combinations > 0:
                    current_symbol_progress_percent = (self.current_symbol_progress / self.total_combinations) * 100
                    current_symbol_contribution = (current_symbol_progress_percent / self.total_symbols)
                
                overall_progress = completed_symbols_progress + current_symbol_contribution
                
                # Ensure progress never exceeds 100%
                overall_progress = min(overall_progress, 100.0)
            
            return {
                'is_running': self.is_running,
                'current_symbol': self.current_symbol,
                'current_symbol_index': self.current_symbol_index,
                'total_symbols': self.total_symbols,
                'current_symbol_progress': self.current_symbol_progress,
                'total_combinations': self.total_combinations,
                'overall_progress': round(overall_progress, 2),
                'completed_symbols': len(self.completed_symbols),
                'failed_symbols': len(self.failed_symbols),
                'completed_list': self.completed_symbols[-10:],  # Last 10 completed
                'failed_list': self.failed_symbols[-10:],  # Last 10 failed
                'best_results_count': len(self.best_results),
                'recent_results': list(self.best_results.items())[-5:] if self.best_results else []  # Last 5 results
            }