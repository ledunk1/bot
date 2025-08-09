"""
Parameter combination generator for optimization
"""
import itertools
import numpy as np

class ParameterGenerator:
    """Generate parameter combinations for optimization"""
    
    @staticmethod
    def generate_parameter_combinations(param_ranges):
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
    
    @staticmethod
    def get_optimization_queue_estimate(symbols, optimization_params):
        """Get optimization time estimate"""
        try:
            param_ranges = optimization_params.get('param_ranges', {})
            max_workers = optimization_params.get('max_workers', 4)
            
            # Use pre-calculated combinations count if available
            if 'combinations_count' in optimization_params:
                combinations_per_symbol = optimization_params['combinations_count']
            else:
                # Generate combinations to get count
                combinations = ParameterGenerator.generate_parameter_combinations(param_ranges)
                combinations_per_symbol = len(combinations)
            
            total_combinations = len(symbols) * combinations_per_symbol
            
            # Estimate time (rough calculation)
            # Assume ~0.1 seconds per backtest on average
            estimated_seconds_per_combination = 0.1
            total_estimated_seconds = total_combinations * estimated_seconds_per_combination / max_workers
            
            # Convert to human readable format
            hours = int(total_estimated_seconds // 3600)
            minutes = int((total_estimated_seconds % 3600) // 60)
            seconds = int(total_estimated_seconds % 60)
            
            return {
                'total_symbols': len(symbols),
                'combinations_per_symbol': combinations_per_symbol,
                'total_combinations': total_combinations,
                'max_workers': max_workers,
                'estimated_time': {
                    'total_seconds': int(total_estimated_seconds),
                    'hours': hours,
                    'minutes': minutes,
                    'seconds': seconds,
                    'formatted': f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"
                },
                'symbols_preview': symbols[:10]  # Show first 10 symbols
            }
            
        except Exception as e:
            print(f"Error calculating optimization estimate: {str(e)}")
            return {
                'error': str(e),
                'total_symbols': len(symbols) if symbols else 0,
                'total_combinations': 0,
                'estimated_time': {'formatted': 'Unknown'}
            }