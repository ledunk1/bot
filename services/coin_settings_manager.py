import json
import os
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional, List

class CoinSettingsManager:
    """Manage individual coin settings and optimization results"""
    
    def __init__(self):
        self.settings_dir = "coin_settings"
        self.settings_file = os.path.join(self.settings_dir, "coin_settings.json")
        self.ensure_settings_dir()
        self.coin_settings = self.load_all_settings()
        
    def ensure_settings_dir(self):
        """Ensure settings directory exists"""
        if not os.path.exists(self.settings_dir):
            os.makedirs(self.settings_dir)
            print(f"Created settings directory: {self.settings_dir}")
    
    def get_default_settings(self) -> Dict[str, Any]:
        """Get default strategy settings"""
        return {
            'strategy_params': {
                'macd_fast': 14,
                'macd_slow': 32,
                'macd_signal': 10,
                'sma_length': 150
            },
            'tp_sl_params': {
                'tp_base': 0.5,
                'stop_loss': 1.25,
                'max_tps': 10,
                'tp_close': 25
            },
            'optimization_score': 0.0,
            'optimization_date': None,
            'backtest_stats': None
        }
    
    def save_coin_settings(self, symbol: str, settings: Dict[str, Any]) -> bool:
        """Save settings for a specific coin"""
        try:
            # Add metadata
            settings['last_updated'] = datetime.now().isoformat()
            settings['symbol'] = symbol
            
            # Update in memory
            self.coin_settings[symbol] = settings
            
            # Save to file
            with open(self.settings_file, 'w') as f:
                json.dump(self.coin_settings, f, indent=2, default=str)
            
            print(f"✅ Settings saved for {symbol}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving settings for {symbol}: {str(e)}")
            return False
    
    def load_coin_settings(self, symbol: str) -> Dict[str, Any]:
        """Load settings for a specific coin"""
        if symbol in self.coin_settings:
            return self.coin_settings[symbol]
        else:
            # Return default settings if not found
            default = self.get_default_settings()
            print(f"⚠️ Using default settings for {symbol}")
            return default
    
    def load_all_settings(self) -> Dict[str, Dict[str, Any]]:
        """Load all coin settings from file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                print(f"📁 Loaded settings for {len(settings)} coins")
                return settings
            else:
                print("📁 No existing settings file found, starting fresh")
                return {}
        except Exception as e:
            print(f"❌ Error loading settings: {str(e)}")
            return {}
    
    def save_optimization_result(self, symbol: str, optimization_result: Dict[str, Any]) -> bool:
        """Save the best optimization result for a coin"""
        try:
            if not optimization_result:
                return False
            
            # Extract best parameters
            best_params = optimization_result['parameters']
            
            settings = {
                'strategy_params': {
                    'macd_fast': best_params['macd_fast'],
                    'macd_slow': best_params['macd_slow'],
                    'macd_signal': best_params['macd_signal'],
                    'sma_length': best_params['sma_length']
                },
                'tp_sl_params': {
                    'tp_base': best_params['tp_base'],
                    'stop_loss': best_params['stop_loss'],
                    'max_tps': 10,  # Fixed
                    'tp_close': 25  # Fixed
                },
                'optimization_score': optimization_result['score'],
                'optimization_date': datetime.now().isoformat(),
                'backtest_stats': {
                    'total_return': optimization_result['total_return'],
                    'win_rate': optimization_result['win_rate'],
                    'total_trades': optimization_result['total_trades'],
                    'max_drawdown': optimization_result['max_drawdown'],
                    'profit_factor': optimization_result.get('profit_factor', 0),
                    'sharpe_ratio': optimization_result.get('sharpe_ratio', 0)
                }
            }
            
            return self.save_coin_settings(symbol, settings)
            
        except Exception as e:
            print(f"❌ Error saving optimization result for {symbol}: {str(e)}")
            return False
    
    def get_coins_with_settings(self) -> List[str]:
        """Get list of coins that have custom settings"""
        return list(self.coin_settings.keys())
    
    def get_settings_summary(self) -> Dict[str, Any]:
        """Get summary of all coin settings"""
        summary = {
            'total_coins': len(self.coin_settings),
            'optimized_coins': 0,
            'default_coins': 0,
            'coins_by_score': []
        }
        
        for symbol, settings in self.coin_settings.items():
            if settings.get('optimization_score', 0) > 0:
                summary['optimized_coins'] += 1
                summary['coins_by_score'].append({
                    'symbol': symbol,
                    'score': settings['optimization_score'],
                    'return': settings.get('backtest_stats', {}).get('total_return', 0),
                    'win_rate': settings.get('backtest_stats', {}).get('win_rate', 0),
                    'optimization_date': settings.get('optimization_date')
                })
            else:
                summary['default_coins'] += 1
        
        # Sort by score
        summary['coins_by_score'].sort(key=lambda x: x['score'], reverse=True)
        
        return summary
    
    def export_settings_csv(self, filepath: str = None) -> str:
        """Export all settings to CSV"""
        try:
            if not filepath:
                filepath = os.path.join(self.settings_dir, f"coin_settings_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            
            data = []
            for symbol, settings in self.coin_settings.items():
                row = {
                    'symbol': symbol,
                    'macd_fast': settings['strategy_params']['macd_fast'],
                    'macd_slow': settings['strategy_params']['macd_slow'],
                    'macd_signal': settings['strategy_params']['macd_signal'],
                    'sma_length': settings['strategy_params']['sma_length'],
                    'tp_base': settings['tp_sl_params']['tp_base'],
                    'stop_loss': settings['tp_sl_params']['stop_loss'],
                    'optimization_score': settings.get('optimization_score', 0),
                    'optimization_date': settings.get('optimization_date'),
                    'total_return': settings.get('backtest_stats', {}).get('total_return', 0),
                    'win_rate': settings.get('backtest_stats', {}).get('win_rate', 0),
                    'total_trades': settings.get('backtest_stats', {}).get('total_trades', 0),
                    'max_drawdown': settings.get('backtest_stats', {}).get('max_drawdown', 0)
                }
                data.append(row)
            
            df = pd.DataFrame(data)
            df.to_csv(filepath, index=False)
            
            print(f"📊 Settings exported to: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"❌ Error exporting settings: {str(e)}")
            return ""
    
    def import_settings_csv(self, filepath: str) -> bool:
        """Import settings from CSV"""
        try:
            df = pd.read_csv(filepath)
            imported_count = 0
            
            for _, row in df.iterrows():
                symbol = row['symbol']
                settings = {
                    'strategy_params': {
                        'macd_fast': int(row['macd_fast']),
                        'macd_slow': int(row['macd_slow']),
                        'macd_signal': int(row['macd_signal']),
                        'sma_length': int(row['sma_length'])
                    },
                    'tp_sl_params': {
                        'tp_base': float(row['tp_base']),
                        'stop_loss': float(row['stop_loss']),
                        'max_tps': 10,
                        'tp_close': 25
                    },
                    'optimization_score': float(row.get('optimization_score', 0)),
                    'optimization_date': row.get('optimization_date'),
                    'backtest_stats': {
                        'total_return': float(row.get('total_return', 0)),
                        'win_rate': float(row.get('win_rate', 0)),
                        'total_trades': int(row.get('total_trades', 0)),
                        'max_drawdown': float(row.get('max_drawdown', 0))
                    }
                }
                
                if self.save_coin_settings(symbol, settings):
                    imported_count += 1
            
            print(f"📥 Imported settings for {imported_count} coins")
            return True
            
        except Exception as e:
            print(f"❌ Error importing settings: {str(e)}")
            return False
    
    def delete_coin_settings(self, symbol: str) -> bool:
        """Delete settings for a specific coin"""
        try:
            if symbol in self.coin_settings:
                del self.coin_settings[symbol]
                
                # Save updated settings
                with open(self.settings_file, 'w') as f:
                    json.dump(self.coin_settings, f, indent=2, default=str)
                
                print(f"🗑️ Settings deleted for {symbol}")
                return True
            else:
                print(f"⚠️ No settings found for {symbol}")
                return False
                
        except Exception as e:
            print(f"❌ Error deleting settings for {symbol}: {str(e)}")
            return False
    
    def reset_all_settings(self) -> bool:
        """Reset all coin settings to default"""
        try:
            self.coin_settings = {}
            
            with open(self.settings_file, 'w') as f:
                json.dump(self.coin_settings, f, indent=2)
            
            print("🔄 All coin settings reset to default")
            return True
            
        except Exception as e:
            print(f"❌ Error resetting settings: {str(e)}")
            return False