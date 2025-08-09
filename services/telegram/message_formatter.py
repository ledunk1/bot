from datetime import datetime

class TelegramMessageFormatter:
    """Format messages for Telegram notifications"""
    
    @staticmethod
    def format_enhanced_signal_message(signal_data, historical_stats=None):
        """Format enhanced signal message with TP/SL levels"""
        try:
            print(f"📝 Formatting enhanced message for {signal_data['symbol']}")
            
            symbol = signal_data['symbol']
            signal_type = signal_data['signal']
            entry_price = signal_data['entry_price']
            strength = signal_data['strength']
            timestamp = signal_data['timestamp']
            tp_levels = signal_data['tp_levels']
            sl_level = signal_data['sl_level']
            timeframe = signal_data.get('timeframe', '1H')
            
            # Signal emoji
            emoji = "🟢📈" if signal_type == "BUY" else "🔴📉"
            
            # Format TP levels
            tp_text = ""
            for tp in tp_levels[:5]:  # Show first 5 TPs
                tp_text += f"TP{tp['level']}: ${tp['price']:.4f} (+{tp['percent']:.2f}%)\n"
            
            # Historical performance info
            historical_info = ""
            if historical_stats:
                # Drawdown risk assessment
                drawdown_risk = TelegramMessageFormatter._assess_drawdown_risk(historical_stats.get('max_drawdown', 0))
                drawdown_emoji = TelegramMessageFormatter._get_drawdown_emoji(historical_stats.get('max_drawdown', 0))
                
                historical_info = f"""
**📊 Historical Performance ({historical_stats['start_date']} - {historical_stats['end_date']}):**
• Win Rate: {historical_stats['win_rate']:.1f}%
• Total Trades: {historical_stats['total_trades']}
• Total Return: {historical_stats['total_return']:.1f}%
• Total PnL: ${historical_stats.get('total_pnl', 0):.2f}
• Max Drawdown: {drawdown_emoji} {historical_stats.get('max_drawdown', 0):.1f}% ({drawdown_risk})
• Period: {historical_stats['period_days']} days
"""
            else:
                historical_info = "\n**📊 Historical Performance:** Calculating..."
            
            # Add signal strength indicator
            strength_emoji = "🔥" if strength >= 0.7 else "⚡" if strength >= 0.5 else "📊"
            
            message = f"""
{emoji} **{signal_type} SIGNAL DETECTED** {emoji}

**📊 Symbol:** {symbol}
**🎯 Signal:** {signal_type}
**💰 Entry Price:** ${entry_price:.4f}
**{strength_emoji} Strength:** {strength:.2f}/1.0
**⏰ Time:** {datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')}

**🎯 Take Profit Levels:**
{tp_text.strip()}

**🛑 Stop Loss:** ${sl_level:.4f} (-1.50%)

**⏱️ Timeframe:** {timeframe}
**🔄 Live WebSocket Data**

{historical_info.strip()}

**📱 Click "ENTRY" button below to start TP/SL tracking!**
        """
            
            print(f"✅ Enhanced message formatted for {symbol}")
            return message.strip()
        
        except Exception as e:
            print(f"Error formatting enhanced message: {str(e)}")
            # Return basic message as fallback
            return f"""
🚨 **{signal_data['signal']} SIGNAL - {signal_data['symbol']}** 🚨

**Entry Price:** ${signal_data['entry_price']:.4f}
**Strength:** {signal_data['strength']:.2f}
**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Click ENTRY button to start tracking!**
            """.strip()
    
    @staticmethod
    def format_signal_message(signal_data, historical_stats=None):
        """Format signal message"""
        symbol = signal_data['symbol']
        signal_type = signal_data['signal']
        price = signal_data['price']
        strength = signal_data['strength']
        timestamp = signal_data['timestamp']
        timeframe = signal_data.get('timeframe', '1H')
        
        # Signal emoji
        emoji = "🟢" if signal_type == "BUY" else "🔴"
        
        # Historical performance info
        historical_info = ""
        if historical_stats:
            # Drawdown risk assessment
            drawdown_risk = TelegramMessageFormatter._assess_drawdown_risk(historical_stats.get('max_drawdown', 0))
            drawdown_emoji = TelegramMessageFormatter._get_drawdown_emoji(historical_stats.get('max_drawdown', 0))
            
            historical_info = f"""
**📊 Historical Performance ({historical_stats['start_date']} - {historical_stats['end_date']}):**
• Win Rate: {historical_stats['win_rate']:.1f}%
• Total Trades: {historical_stats['total_trades']}
• Total Return: {historical_stats['total_return']:.1f}%
• Total PnL: ${historical_stats.get('total_pnl', 0):.2f}
• Max Drawdown: {drawdown_emoji} {historical_stats.get('max_drawdown', 0):.1f}% ({drawdown_risk})
• Period: {historical_stats['period_days']} days
"""
        else:
            historical_info = "\n**📊 Historical Performance:** Calculating..."
        
        message = f"""
{emoji} **{signal_type} SIGNAL DETECTED** {emoji}

**Symbol:** {symbol}
**Signal:** {signal_type}
**Price:** ${price:.4f}
**Strength:** {strength:.2f}
**Time:** {datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')}

**Strategy:** MACD + SMA 200
**Timeframe:** {timeframe}

{historical_info.strip()}

**📱 Click "ENTRY" button below to start TP/SL tracking!**

⚠️ *This is an automated signal. Please do your own research before trading.*
        """
        
        return message.strip()
    
    @staticmethod
    def format_drawdown_alert(symbol, current_drawdown, max_historical_drawdown, entry_price, current_price, signal_type):
        """Format drawdown alert notification"""
        try:
            # Calculate PnL percentage
            if signal_type.upper() == "BUY":
                pnl_percent = ((current_price - entry_price) / entry_price) * 100
            else:
                pnl_percent = ((entry_price - current_price) / entry_price) * 100
            
            # Determine alert level
            if current_drawdown >= max_historical_drawdown * 0.8:
                alert_level = "🚨 CRITICAL"
                alert_color = "🔴"
            elif current_drawdown >= max_historical_drawdown * 0.6:
                alert_level = "⚠️ HIGH"
                alert_color = "🟠"
            else:
                alert_level = "📊 MODERATE"
                alert_color = "🟡"
            
            message = f"""
{alert_color} **DRAWDOWN ALERT - {symbol}** {alert_color}

**{alert_level} DRAWDOWN DETECTED**

**📊 Drawdown Analysis:**
• Current Drawdown: {current_drawdown:.2f}%
• Historical Max: {max_historical_drawdown:.2f}%
• Risk Level: {current_drawdown/max_historical_drawdown*100:.1f}% of historical max

**💹 Position Details:**
• Signal: {signal_type}
• Entry Price: ${entry_price:.4f}
• Current Price: ${current_price:.4f}
• Current PnL: {pnl_percent:+.2f}%

**⏰ Alert Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**💡 Risk Management Tips:**
• Consider reducing position size
• Review stop loss levels
• Monitor closely for trend reversal
• Don't panic - drawdowns are normal

**📈 Remember:** Historical max drawdown was {max_historical_drawdown:.2f}%
            """
            
            return message.strip()
            
        except Exception as e:
            print(f"Error formatting drawdown alert: {str(e)}")
            return f"🚨 **DRAWDOWN ALERT - {symbol}**\n\nCurrent drawdown: {current_drawdown:.2f}%\nPlease review your position."
    
    @staticmethod
    def format_drawdown_recovery_notification(symbol, previous_drawdown, current_drawdown, recovery_percent):
        """Format drawdown recovery notification"""
        try:
            recovery_emoji = "🟢📈" if recovery_percent >= 50 else "🟡📊"
            
            message = f"""
{recovery_emoji} **DRAWDOWN RECOVERY - {symbol}** {recovery_emoji}

**📈 RECOVERY DETECTED**

**📊 Recovery Analysis:**
• Previous Drawdown: {previous_drawdown:.2f}%
• Current Drawdown: {current_drawdown:.2f}%
• Recovery: {recovery_percent:.1f}%

**⏰ Recovery Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**💡 Status:** {"Strong recovery trend" if recovery_percent >= 50 else "Moderate recovery"}

**📈 Keep monitoring for continued improvement!**
            """
            
            return message.strip()
            
        except Exception as e:
            print(f"Error formatting recovery notification: {str(e)}")
            return f"📈 **RECOVERY - {symbol}**\n\nDrawdown improved from {previous_drawdown:.2f}% to {current_drawdown:.2f}%"
    
    @staticmethod
    def format_max_drawdown_warning(symbol, new_max_drawdown, previous_max_drawdown):
        """Format new maximum drawdown warning"""
        try:
            message = f"""
🚨🔴 **NEW MAX DRAWDOWN - {symbol}** 🔴🚨

**⚠️ HISTORICAL HIGH DRAWDOWN REACHED**

**📊 Drawdown Milestone:**
• New Max Drawdown: {new_max_drawdown:.2f}%
• Previous Max: {previous_max_drawdown:.2f}%
• Increase: +{new_max_drawdown - previous_max_drawdown:.2f}%

**⏰ Alert Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**🚨 CRITICAL RISK MANAGEMENT:**
• This is a new historical maximum drawdown
• Consider immediate position review
• Evaluate risk management strategy
• Consider reducing exposure

**📊 Historical Context:**
• This drawdown exceeds all previous levels
• Market conditions may have changed
• Strategy performance under stress

**💡 Action Items:**
• Review stop loss settings
• Consider position sizing adjustments
• Monitor market conditions closely
• Document lessons learned
            """
            
            return message.strip()
            
        except Exception as e:
            print(f"Error formatting max drawdown warning: {str(e)}")
            return f"🚨 **NEW MAX DRAWDOWN - {symbol}**\n\nNew maximum drawdown: {new_max_drawdown:.2f}%"
    
    @staticmethod
    def _assess_drawdown_risk(drawdown_percent):
        """Assess drawdown risk level"""
        if drawdown_percent <= 10:
            return "Low Risk"
        elif drawdown_percent <= 20:
            return "Moderate Risk"
        elif drawdown_percent <= 35:
            return "High Risk"
        else:
            return "Very High Risk"
    
    @staticmethod
    def _get_drawdown_emoji(drawdown_percent):
        """Get appropriate emoji for drawdown level"""
        if drawdown_percent <= 10:
            return "🟢"
        elif drawdown_percent <= 20:
            return "🟡"
        elif drawdown_percent <= 35:
            return "🟠"
        else:
            return "🔴"
    
    @staticmethod
    def calculate_tp_sl_levels(entry_price, direction):
        """Calculate TP and SL levels"""
        tp_base_percent = 0.5
        sl_percent = 1.25
        max_tps = 5
        
        tp_levels = []
        
        # Calculate TP levels
        for i in range(1, max_tps + 1):
            tp_percent = tp_base_percent * i
            
            if direction == 1:  # Long
                tp_price = entry_price * (1 + tp_percent / 100)
            else:  # Short
                tp_price = entry_price * (1 - tp_percent / 100)
                
            tp_levels.append({
                'level': i,
                'price': tp_price,
                'percent': tp_percent
            })
        
        # Calculate SL level
        if direction == 1:  # Long
            sl_price = entry_price * (1 - sl_percent / 100)
        else:  # Short
            sl_price = entry_price * (1 + sl_percent / 100)
            
        return tp_levels, sl_price