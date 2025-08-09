class ChartManager {
    constructor() {
        this.chartDiv = document.getElementById('chart');
    }
    
    displayChart(chartData, tpSlLevels, symbolSelect, intervalSelect) {
        const timestamps = chartData.map(d => d.timestamp);
        const opens = chartData.map(d => d.open);
        const highs = chartData.map(d => d.high);
        const lows = chartData.map(d => d.low);
        const closes = chartData.map(d => d.close);
        
        // Buy and sell signals
        const buySignals = chartData.filter(d => d.signal === 1 && d.signal !== null && d.signal !== undefined);
        const sellSignals = chartData.filter(d => d.signal === -1 && d.signal !== null && d.signal !== undefined);
        
        console.log(`Found ${buySignals.length} buy signals and ${sellSignals.length} sell signals`);
        console.log('Buy signals:', buySignals.slice(0, 3));
        console.log('Sell signals:', sellSignals.slice(0, 3));
        console.log('TP/SL Levels:', tpSlLevels);
        
        const traces = this._createBasicTraces(timestamps, opens, highs, lows, closes, buySignals, sellSignals);
        
        // Add TP/SL level lines for BOTH long and short
        if (tpSlLevels && tpSlLevels.length > 0) {
            this._addTpSlTraces(traces, tpSlLevels, timestamps, chartData);
        }
        
        // Add EMAs if available
        this._addEmaTraces(traces, chartData, timestamps);
        
        // Store chart data temporarily for layout calculation
        this.chartDiv.data = traces;
        const layout = this._createLayout(symbolSelect, intervalSelect);
        const config = this._createConfig();
        
        Plotly.newPlot(this.chartDiv, traces, layout, config);
    }
    
    _createBasicTraces(timestamps, opens, highs, lows, closes, buySignals, sellSignals) {
        return [
            // Candlestick chart
            {
                x: timestamps,
                open: opens,
                high: highs,
                low: lows,
                close: closes,
                type: 'candlestick',
                name: 'Price',
                increasing: { line: { color: '#10b981' } },
                decreasing: { line: { color: '#ef4444' } }
            },
            // Buy signals
            {
                x: buySignals.map(d => d.timestamp),
                y: buySignals.map(d => d.low * 0.99),
                mode: 'markers',
                type: 'scatter',
                name: 'Buy Signal',
                marker: {
                    symbol: 'triangle-up',
                    size: 15,
                    color: '#10b981',
                    line: {
                        color: '#065f46',
                        width: 2
                    }
                },
                text: buySignals.map(d => `Buy: $${d.close.toFixed(4)}`),
                textposition: 'top center',
                hovertemplate: '<b>BUY SIGNAL</b><br>Time: %{x}<br>Price: $%{y:.4f}<extra></extra>'
            },
            // Sell signals
            {
                x: sellSignals.map(d => d.timestamp),
                y: sellSignals.map(d => d.high * 1.01),
                mode: 'markers',
                type: 'scatter',
                name: 'Sell Signal',
                marker: {
                    symbol: 'triangle-down',
                    size: 15,
                    color: '#ef4444',
                    line: {
                        color: '#991b1b',
                        width: 2
                    }
                },
                text: sellSignals.map(d => `Sell: $${d.close.toFixed(4)}`),
                textposition: 'bottom center',
                hovertemplate: '<b>SELL SIGNAL</b><br>Time: %{x}<br>Price: $%{y:.4f}<extra></extra>'
            }
        ];
    }
    
    _addTpSlTraces(traces, tpSlLevels, timestamps, chartData) {
        const tpColors = ['#22c55e', '#16a34a', '#15803d', '#166534', '#14532d']; // Green shades for TPs
        const slColor = '#ef4444'; // Red for SL
        
        console.log('Adding TP/SL traces for levels:', tpSlLevels);
        
        tpSlLevels.forEach((level, levelIndex) => {
            // Convert timestamp to proper format if needed
            let entryTime = level.timestamp;
            if (typeof entryTime === 'string' && !entryTime.includes('T')) {
                entryTime = new Date(entryTime).toISOString();
            }
            
            const direction = level.direction;
            const entryPrice = level.entry_price;
            
            // Find the end time (next signal or end of data)
            let endTime = timestamps[timestamps.length - 1];
            const entryIndex = timestamps.findIndex(t => {
                const tTime = new Date(t).getTime();
                const eTime = new Date(entryTime).getTime();
                return Math.abs(tTime - eTime) < 60000; // Within 1 minute
            });
            
            console.log(`Entry time: ${entryTime}, Entry index: ${entryIndex}, End time: ${endTime}`);
            
            if (entryIndex >= 0) {
                // Look for next signal after this entry
                for (let i = entryIndex + 1; i < chartData.length; i++) {
                    if (chartData[i].signal !== 0 && chartData[i].signal !== null && chartData[i].signal !== undefined) {
                        endTime = chartData[i].timestamp;
                        break;
                    }
                }
            }
            
            const positionType = direction === 1 ? 'Long' : 'Short';
            const entryColor = direction === 1 ? '#3b82f6' : '#8b5cf6';
            
            console.log(`Processing ${positionType} position with ${level.tp_levels.length} TP levels`);
            
            // Add TP lines (show first 5 TPs to avoid clutter)
            level.tp_levels.slice(0, 5).forEach((tp, tpIndex) => {
                traces.push({
                    x: [entryTime, endTime],
                    y: [tp.price, tp.price],
                    mode: 'lines',
                    type: 'scatter',
                    name: `${positionType} TP${tp.level} (${tp.percent.toFixed(2)}%)`,
                    line: {
                        color: tpColors[tpIndex % tpColors.length],
                        width: 2,
                        dash: 'dot'
                    },
                    showlegend: levelIndex === 0 && tpIndex < 3, // Only show legend for first 3 TPs of first position
                    hovertemplate: `<b>TP${tp.level}</b><br>Price: $%{y:.4f}<br>Target: ${tp.percent.toFixed(2)}%<extra></extra>`
                });
            });
            
            // Add SL line
            traces.push({
                x: [entryTime, endTime],
                y: [level.sl_level, level.sl_level],
                mode: 'lines',
                type: 'scatter',
                name: `${positionType} Stop Loss`,
                line: {
                    color: slColor,
                    width: 3,
                    dash: 'dash'
                },
                showlegend: levelIndex === 0, // Only show legend for first position
                hovertemplate: '<b>STOP LOSS</b><br>Price: $%{y:.4f}<extra></extra>'
            });
            
            // Add entry price line
            traces.push({
                x: [entryTime, endTime],
                y: [entryPrice, entryPrice],
                mode: 'lines',
                type: 'scatter',
                name: `${positionType} Entry`,
                line: {
                    color: entryColor,
                    width: 2,
                    dash: 'solid'
                },
                showlegend: levelIndex === 0, // Only show legend for first position
                hovertemplate: '<b>ENTRY PRICE</b><br>Price: $%{y:.4f}<extra></extra>'
            });
            
            console.log(`Added TP/SL traces for position ${levelIndex + 1}`);
        });
    }
    
    _addEmaTraces(traces, chartData, timestamps) {
        const fastMA = chartData.map(d => d.fast_ma).filter(v => v !== null);
        const slowMA = chartData.map(d => d.slow_ma).filter(v => v !== null);
        const verySlowMA = chartData.map(d => d.very_slow_ma).filter(v => v !== null);
        
        if (fastMA.length > 0) {
            traces.push({
                x: timestamps.slice(-fastMA.length),
                y: fastMA,
                type: 'scatter',
                mode: 'lines',
                name: 'MA Fast (12)',
                line: { color: '#3b82f6', width: 1 }
            });
        }
        
        if (slowMA.length > 0) {
            traces.push({
                x: timestamps.slice(-slowMA.length),
                y: slowMA,
                type: 'scatter',
                mode: 'lines',
                name: 'MA Slow (26)',
                line: { color: '#f59e0b', width: 1 }
            });
        }
        
        if (verySlowMA.length > 0) {
            traces.push({
                x: timestamps.slice(-verySlowMA.length),
                y: verySlowMA,
                type: 'scatter',
                mode: 'lines',
                name: 'SMA 200',
                line: { color: '#ef4444', width: 2 }
            });
        }
    }
    
    _createLayout(symbolSelect, intervalSelect) {
        // Calculate initial range to show last 100 candles
        const totalCandles = this.chartDiv.data ? this.chartDiv.data[0].x.length : 0;
        let xaxis_range = undefined;
        
        if (totalCandles > 100) {
            // Show last 100 candles initially
            const startIndex = Math.max(0, totalCandles - 100);
            const endIndex = totalCandles - 1;
            
            // Get the timestamp range for last 100 candles
            if (this.chartDiv.data && this.chartDiv.data[0].x) {
                const timestamps = this.chartDiv.data[0].x;
                xaxis_range = [timestamps[startIndex], timestamps[endIndex]];
            }
        }
        
        return {
            title: `${symbolSelect.value} - ${intervalSelect.value} Chart with MACD + SMA 200 Signals & TP/SL Levels`,
            xaxis: { 
                title: 'Time', 
                rangeslider: { visible: true },
                type: 'date',
                range: xaxis_range  // Set initial range to show last 100 candles
            },
            yaxis: { title: 'Price (USDT)' },
            showlegend: true,
            height: 1000,
            width: null,
            autosize: true,
            dragmode: 'pan',
            margin: {
                l: 50,
                r: 50,
                t: 50,
                b: 100
            }
        };
    }
    
    _createConfig() {
        return {
            responsive: true,
            useResizeHandler: true,
            scrollZoom: true,
            displayModeBar: true,
            modeBarButtonsToAdd: ['pan2d', 'select2d', 'lasso2d', 'resetScale2d'],
            modeBarButtonsToRemove: ['autoScale2d'],
            displaylogo: false
        };
    }
}