import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

class TelegramChartGenerator:
    """Generate charts for Telegram notifications"""
    
    @staticmethod
    def create_enhanced_chart_image(signal_data):
        """Create enhanced chart image with TP/SL levels"""
        try:
            print(f"📊 Creating enhanced chart for {signal_data['symbol']}")
            
            chart_data = signal_data['chart_data']
            symbol = signal_data['symbol']
            signal_type = signal_data['signal']
            entry_price = signal_data['entry_price']
            tp_levels = signal_data['tp_levels']
            sl_level = signal_data['sl_level']
            
            if not chart_data:
                print(f"❌ No chart data available for {symbol}")
                return None
            
            print(f"📈 Processing {len(chart_data)} candles for {symbol}")
            
            # Extract data
            timestamps = [d['timestamp'] for d in chart_data]
            opens = [d['open'] for d in chart_data]
            highs = [d['high'] for d in chart_data]
            lows = [d['low'] for d in chart_data]
            closes = [d['close'] for d in chart_data]
            
            # Find signals
            buy_signals = [d for d in chart_data if d['signal'] == 1]
            sell_signals = [d for d in chart_data if d['signal'] == -1]
            
            print(f"📊 Chart signals: {len(buy_signals)} buy, {len(sell_signals)} sell")
            
            # Create subplot with secondary y-axis for volume
            fig = make_subplots(
                rows=2, cols=1,
                subplot_titles=[f"{symbol} - {signal_type} SIGNAL 🚨", "Volume"],
                vertical_spacing=0.1,
                row_heights=[0.8, 0.2]
            )
            
            # Add candlestick
            fig.add_trace(
                go.Candlestick(
                    x=timestamps,
                    open=opens,
                    high=highs,
                    low=lows,
                    close=closes,
                    name='Price',
                    increasing_line_color='#10b981',
                    decreasing_line_color='#ef4444'
                ),
                row=1, col=1
            )
            
            # Add volume bars
            volumes = [d['volume'] for d in chart_data]
            fig.add_trace(
                go.Bar(
                    x=timestamps,
                    y=volumes,
                    name='Volume',
                    marker_color='rgba(158,158,158,0.5)'
                ),
                row=2, col=1
            )
            
            # Add moving averages
            fast_ma = [d['fast_ma'] for d in chart_data if d['fast_ma'] is not None]
            slow_ma = [d['slow_ma'] for d in chart_data if d['slow_ma'] is not None]
            very_slow_ma = [d['very_slow_ma'] for d in chart_data if d['very_slow_ma'] is not None]
            
            if fast_ma:
                fig.add_trace(
                    go.Scatter(
                        x=timestamps[-len(fast_ma):],
                        y=fast_ma,
                        mode='lines',
                        name='MA 12',
                        line=dict(color='#3b82f6', width=1)
                    ),
                    row=1, col=1
                )
            
            if slow_ma:
                fig.add_trace(
                    go.Scatter(
                        x=timestamps[-len(slow_ma):],
                        y=slow_ma,
                        mode='lines',
                        name='MA 26',
                        line=dict(color='#f59e0b', width=1)
                    ),
                    row=1, col=1
                )
            
            if very_slow_ma:
                fig.add_trace(
                    go.Scatter(
                        x=timestamps[-len(very_slow_ma):],
                        y=very_slow_ma,
                        mode='lines',
                        name='SMA 200',
                        line=dict(color='#ef4444', width=2)
                    ),
                    row=1, col=1
                )
            
            # Add entry price line
            fig.add_hline(
                y=entry_price,
                line=dict(color='#3b82f6', width=3, dash='solid'),
                annotation_text=f"Entry: ${entry_price:.4f}",
                annotation_position="top right",
                row=1, col=1
            )
            
            # Add TP levels
            tp_colors = ['#22c55e', '#16a34a', '#15803d', '#166534', '#14532d']
            for i, tp in enumerate(tp_levels[:5]):  # Show first 5 TPs
                fig.add_hline(
                    y=tp['price'],
                    line=dict(color=tp_colors[i], width=2, dash='dot'),
                    annotation_text=f"TP{tp['level']}: ${tp['price']:.4f}",
                    annotation_position="top right" if i % 2 == 0 else "bottom right",
                    row=1, col=1
                )
            
            # Add SL level
            fig.add_hline(
                y=sl_level,
                line=dict(color='#ef4444', width=3, dash='dash'),
                annotation_text=f"SL: ${sl_level:.4f}",
                annotation_position="bottom right",
                row=1, col=1
            )
            
            # Add buy signals
            if buy_signals:
                fig.add_trace(
                    go.Scatter(
                        x=[d['timestamp'] for d in buy_signals],
                        y=[d['low'] * 0.995 for d in buy_signals],
                        mode='markers',
                        name='BUY Signal',
                        marker=dict(
                            symbol='triangle-up',
                            size=15,
                            color='#10b981'
                        )
                    ),
                    row=1, col=1
                )
            
            # Add sell signals
            if sell_signals:
                fig.add_trace(
                    go.Scatter(
                        x=[d['timestamp'] for d in sell_signals],
                        y=[d['high'] * 1.005 for d in sell_signals],
                        mode='markers',
                        name='SELL Signal',
                        marker=dict(
                            symbol='triangle-down',
                            size=15,
                            color='#ef4444'
                        )
                    ),
                    row=1, col=1
                )
            
            # Update layout
            fig.update_layout(
                title=f"🚨 {symbol} - {signal_type} SIGNAL DETECTED 🚨",
                height=800,
                width=1200,
                showlegend=True,
                template="plotly_white",
                font=dict(size=12)
            )
            
            # Update x-axis
            fig.update_xaxes(title_text="Time", row=2, col=1)
            fig.update_yaxes(title_text="Price (USDT)", row=1, col=1)
            fig.update_yaxes(title_text="Volume", row=2, col=1)
            
            # Convert to image
            print(f"🖼️ Converting chart to image for {symbol}")
            img_bytes = pio.to_image(fig, format="png", width=1200, height=800)
            print(f"✅ Chart image created for {symbol} ({len(img_bytes)} bytes)")
            return img_bytes
            
        except Exception as e:
            print(f"Error creating enhanced chart image: {str(e)}")
            return None
    
    @staticmethod
    def create_chart_image(signal_data):
        """Create chart image from signal data"""
        try:
            chart_data = signal_data['chart_data']
            symbol = signal_data['symbol']
            signal_type = signal_data['signal']
            
            if not chart_data:
                return None
            
            # Extract data
            timestamps = [d['timestamp'] for d in chart_data]
            opens = [d['open'] for d in chart_data]
            highs = [d['high'] for d in chart_data]
            lows = [d['low'] for d in chart_data]
            closes = [d['close'] for d in chart_data]
            
            # Find signals
            buy_signals = [d for d in chart_data if d['signal'] == 1]
            sell_signals = [d for d in chart_data if d['signal'] == -1]
            
            # Create subplot
            fig = make_subplots(
                rows=1, cols=1,
                subplot_titles=[f"{symbol} - {signal_type} Signal"],
                vertical_spacing=0.1
            )
            
            # Add candlestick
            fig.add_trace(
                go.Candlestick(
                    x=timestamps,
                    open=opens,
                    high=highs,
                    low=lows,
                    close=closes,
                    name='Price',
                    increasing_line_color='#10b981',
                    decreasing_line_color='#ef4444'
                ),
                row=1, col=1
            )
            
            # Add moving averages
            fast_ma = [d['fast_ma'] for d in chart_data if d['fast_ma'] is not None]
            slow_ma = [d['slow_ma'] for d in chart_data if d['slow_ma'] is not None]
            very_slow_ma = [d['very_slow_ma'] for d in chart_data if d['very_slow_ma'] is not None]
            
            if fast_ma:
                fig.add_trace(
                    go.Scatter(
                        x=timestamps[-len(fast_ma):],
                        y=fast_ma,
                        mode='lines',
                        name='MA 12',
                        line=dict(color='#3b82f6', width=1)
                    ),
                    row=1, col=1
                )
            
            if slow_ma:
                fig.add_trace(
                    go.Scatter(
                        x=timestamps[-len(slow_ma):],
                        y=slow_ma,
                        mode='lines',
                        name='MA 26',
                        line=dict(color='#f59e0b', width=1)
                    ),
                    row=1, col=1
                )
            
            if very_slow_ma:
                fig.add_trace(
                    go.Scatter(
                        x=timestamps[-len(very_slow_ma):],
                        y=very_slow_ma,
                        mode='lines',
                        name='SMA 200',
                        line=dict(color='#ef4444', width=2)
                    ),
                    row=1, col=1
                )
            
            # Add buy signals
            if buy_signals:
                fig.add_trace(
                    go.Scatter(
                        x=[d['timestamp'] for d in buy_signals],
                        y=[d['low'] * 0.99 for d in buy_signals],
                        mode='markers',
                        name='Buy Signal',
                        marker=dict(
                            symbol='triangle-up',
                            size=12,
                            color='#10b981'
                        )
                    ),
                    row=1, col=1
                )
            
            # Add sell signals
            if sell_signals:
                fig.add_trace(
                    go.Scatter(
                        x=[d['timestamp'] for d in sell_signals],
                        y=[d['high'] * 1.01 for d in sell_signals],
                        mode='markers',
                        name='Sell Signal',
                        marker=dict(
                            symbol='triangle-down',
                            size=12,
                            color='#ef4444'
                        )
                    ),
                    row=1, col=1
                )
            
            # Update layout
            fig.update_layout(
                title=f"{symbol} - {signal_type} Signal Detected",
                xaxis_title="Time",
                yaxis_title="Price (USDT)",
                height=600,
                width=1000,
                showlegend=True,
                template="plotly_white"
            )
            
            # Convert to image
            img_bytes = pio.to_image(fig, format="png", width=1000, height=600)
            return img_bytes
            
        except Exception as e:
            print(f"Error creating chart image: {str(e)}")
            return None