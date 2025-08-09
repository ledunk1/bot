class ResultsManager {
    constructor() {
        this.resultsPanel = document.getElementById('resultsPanel');
        this.statisticsDiv = document.getElementById('statistics');
        this.tradesTableBody = document.getElementById('tradesTableBody');
        this.chartManager = new ChartManager();
    }
    
    displayResults(data, symbolSelect, intervalSelect) {
        this.displayStatistics(data.results.statistics);
        this.chartManager.displayChart(data.chart_data, data.results.tp_sl_levels || [], symbolSelect, intervalSelect);
        this.displayTrades(data.results.trades);
        this.resultsPanel.classList.remove('hidden');
    }
    
    displayStatistics(stats) {
        const formatCurrency = (value) => `$${value.toFixed(2)}`;
        const formatPercent = (value) => `${value.toFixed(2)}%`;
        
        this.statisticsDiv.innerHTML = `
            <div class="bg-blue-50 p-4 rounded-lg">
                <h3 class="text-lg font-semibold text-blue-800">Initial Balance</h3>
                <p class="text-2xl font-bold text-blue-600">${formatCurrency(stats.initial_balance)}</p>
            </div>
            <div class="bg-green-50 p-4 rounded-lg">
                <h3 class="text-lg font-semibold text-green-800">Final Balance</h3>
                <p class="text-2xl font-bold text-green-600">${formatCurrency(stats.final_balance)}</p>
            </div>
            <div class="bg-purple-50 p-4 rounded-lg">
                <h3 class="text-lg font-semibold text-purple-800">Total Return</h3>
                <p class="text-2xl font-bold ${stats.total_return >= 0 ? 'text-green-600' : 'text-red-600'}">${formatPercent(stats.total_return)}</p>
            </div>
            <div class="bg-yellow-50 p-4 rounded-lg">
                <h3 class="text-lg font-semibold text-yellow-800">Win Rate</h3>
                <p class="text-2xl font-bold text-yellow-600">${formatPercent(stats.win_rate)}</p>
            </div>
            <div class="bg-gray-50 p-4 rounded-lg">
                <h3 class="text-lg font-semibold text-gray-800">Total Trades</h3>
                <p class="text-2xl font-bold text-gray-600">${stats.total_trades}</p>
            </div>
            <div class="bg-red-50 p-4 rounded-lg">
                <h3 class="text-lg font-semibold text-red-800">Max Drawdown</h3>
                <p class="text-2xl font-bold text-red-600">${formatPercent(stats.max_drawdown)}</p>
            </div>
            <div class="bg-indigo-50 p-4 rounded-lg">
                <h3 class="text-lg font-semibold text-indigo-800">Leverage Used</h3>
                <p class="text-2xl font-bold text-indigo-600">${stats.leverage_used}x</p>
            </div>
            <div class="bg-teal-50 p-4 rounded-lg">
                <h3 class="text-lg font-semibold text-teal-800">Total PnL</h3>
                <p class="text-2xl font-bold ${stats.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}">${formatCurrency(stats.total_pnl)}</p>
            </div>
            ${stats.tp_sl_settings ? `
            <div class="bg-orange-50 p-4 rounded-lg col-span-2 md:col-span-4">
                <h3 class="text-lg font-semibold text-orange-800 mb-2">TP/SL Settings</h3>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                    <div><span class="font-medium">TP Base:</span> ${stats.tp_sl_settings.tp_base}%</div>
                    <div><span class="font-medium">TP Close:</span> ${stats.tp_sl_settings.tp_close}%</div>
                    <div><span class="font-medium">Max TPs:</span> ${stats.tp_sl_settings.max_tps}</div>
                    <div><span class="font-medium">SL:</span> ${stats.tp_sl_settings.sl}%</div>
                </div>
            </div>
            ` : ''}
        `;
    }
    
    displayTrades(trades) {
        this.tradesTableBody.innerHTML = '';
        
        console.log(`Displaying ${trades.length} trades`);
        
        // Add pagination if there are many trades
        const tradesPerPage = 50;
        const totalPages = Math.ceil(trades.length / tradesPerPage);
        let currentPage = 1;
        
        const displayPage = (page) => {
            this.tradesTableBody.innerHTML = '';
            
            const startIndex = (page - 1) * tradesPerPage;
            const endIndex = Math.min(startIndex + tradesPerPage, trades.length);
            const pageTrades = trades.slice(startIndex, endIndex);
            
            pageTrades.forEach((trade, index) => {
                const globalIndex = startIndex + index + 1;
                this._createTradeRow(trade, globalIndex);
            });
            
            // Update pagination info
            this._updatePaginationInfo(page, totalPages, trades.length);
        };
        
        // Create pagination controls if needed
        if (totalPages > 1) {
            this._createPaginationControls(totalPages, displayPage);
        }
        
        // Display first page
        displayPage(currentPage);
    }
    
    _createTradeRow(trade, index) {
        const row = document.createElement('tr');
        row.className = 'border-b hover:bg-gray-50';
        
        const pnlClass = trade.pnl >= 0 ? 'text-green-600' : 'text-red-600';
        const positionClass = trade.position === 'Long' ? 'text-blue-600' : 'text-purple-600';
        const exitReasonClass = trade.exit_reason?.startsWith('TP') ? 'text-green-600' :
                              trade.exit_reason === 'Stop Loss' ? 'text-red-600' : 
                              trade.exit_reason === 'Trailing Stop' ? 'text-yellow-600' : 'text-gray-600';
        
        row.innerHTML = `
            <td class="px-2 py-1 text-xs">#${index}</td>
            <td class="px-2 py-1 text-xs">${new Date(trade.entry_time).toLocaleString()}</td>
            <td class="px-2 py-1 text-xs">${new Date(trade.exit_time).toLocaleString()}</td>
            <td class="px-2 py-1 text-xs font-medium ${positionClass}">${trade.position}</td>
            <td class="px-2 py-1 text-xs">$${trade.entry_price.toFixed(4)}</td>
            <td class="px-2 py-1 text-xs">$${trade.exit_price.toFixed(4)}</td>
            <td class="px-2 py-1 text-xs font-medium ${exitReasonClass}">${trade.exit_reason || 'Signal'}</td>
            <td class="px-2 py-1 text-xs font-bold ${pnlClass}">$${trade.pnl.toFixed(2)}</td>
        `;
        
        this.tradesTableBody.appendChild(row);
    }
    
    _createPaginationControls(totalPages, displayPageCallback) {
        // Find or create pagination container
        let paginationContainer = document.getElementById('tradesPagination');
        if (!paginationContainer) {
            paginationContainer = document.createElement('div');
            paginationContainer.id = 'tradesPagination';
            paginationContainer.className = 'flex justify-center items-center space-x-2 mt-4';
            
            // Insert after trades table
            const tradesTable = document.getElementById('tradesTable');
            tradesTable.parentNode.insertBefore(paginationContainer, tradesTable.nextSibling);
        }
        
        let currentPage = 1;
        
        const updatePagination = () => {
            paginationContainer.innerHTML = `
                <button id="prevPage" class="px-3 py-1 bg-gray-300 text-gray-700 rounded hover:bg-gray-400 disabled:opacity-50" ${currentPage === 1 ? 'disabled' : ''}>
                    Previous
                </button>
                <span class="px-3 py-1 bg-blue-100 text-blue-800 rounded">
                    Page ${currentPage} of ${totalPages}
                </span>
                <button id="nextPage" class="px-3 py-1 bg-gray-300 text-gray-700 rounded hover:bg-gray-400 disabled:opacity-50" ${currentPage === totalPages ? 'disabled' : ''}>
                    Next
                </button>
            `;
            
            // Add event listeners
            document.getElementById('prevPage').addEventListener('click', () => {
                if (currentPage > 1) {
                    currentPage--;
                    displayPageCallback(currentPage);
                    updatePagination();
                }
            });
            
            document.getElementById('nextPage').addEventListener('click', () => {
                if (currentPage < totalPages) {
                    currentPage++;
                    displayPageCallback(currentPage);
                    updatePagination();
                }
            });
        };
        
        updatePagination();
    }
    
    _updatePaginationInfo(currentPage, totalPages, totalTrades) {
        // Add or update pagination info
        let infoElement = document.getElementById('tradesInfo');
        if (!infoElement) {
            infoElement = document.createElement('div');
            infoElement.id = 'tradesInfo';
            infoElement.className = 'text-sm text-gray-600 mb-2';
            
            const tradesTable = document.getElementById('tradesTable');
            tradesTable.parentNode.insertBefore(infoElement, tradesTable);
        }
        
        infoElement.textContent = `Showing ${totalTrades} total trades`;
    }
}