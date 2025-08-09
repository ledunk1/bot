class CryptoBacktestApp {
    constructor() {
        this.initializeElements();
        this.loadSymbols();
        this.setDefaultDates();
        this.bindEvents();
        this.resultsManager = new ResultsManager();
        
        // Bulk backtest state
        this.isBulkBacktest = false;
        this.bulkResults = [];
        this.currentPage = 1;
        this.resultsPerPage = 20;
        this.isRunning = false;
        this.shouldStop = false;
    }
    
    initializeElements() {
        this.symbolSelect = document.getElementById('symbol');
        this.fetchAllSymbolsCheckbox = document.getElementById('fetchAllSymbols');
        this.intervalSelect = document.getElementById('interval');
        this.startDateInput = document.getElementById('start_date');
        this.endDateInput = document.getElementById('end_date');
        this.leverageInput = document.getElementById('leverage');
        this.marginInput = document.getElementById('margin');
        this.balanceInput = document.getElementById('balance');
        
        // Strategy settings
        this.macdFastInput = document.getElementById('macd_fast');
        this.macdSlowInput = document.getElementById('macd_slow');
        this.macdSignalInput = document.getElementById('macd_signal');
        this.smaLengthInput = document.getElementById('sma_length');
        
        // TP/SL settings
        this.tpBaseInput = document.getElementById('tp_base');
        this.stopLossInput = document.getElementById('stop_loss');
        this.maxTpsInput = document.getElementById('max_tps');
        this.tpCloseInput = document.getElementById('tp_close');
        
        this.runBacktestBtn = document.getElementById('runBacktest');
        this.stopBacktestBtn = document.getElementById('stopBacktest');
        this.loadingDiv = document.getElementById('loading');
        this.loadingText = document.getElementById('loadingText');
        this.progressInfo = document.getElementById('progressInfo');
        this.progressBar = document.getElementById('progressBar');
        this.progressText = document.getElementById('progressText');
    }
    
    setDefaultDates() {
        const endDate = new Date();
        const startDate = new Date();
        startDate.setMonth(startDate.getMonth() - 1);
        
        this.startDateInput.value = startDate.toISOString().split('T')[0];
        this.endDateInput.value = endDate.toISOString().split('T')[0];
    }
    
    bindEvents() {
        this.runBacktestBtn.addEventListener('click', () => this.runBacktest());
        this.stopBacktestBtn.addEventListener('click', () => this.stopBacktest());
        
        // Bulk backtest controls
        document.getElementById('sortBy').addEventListener('change', () => this.sortAndDisplayResults());
        document.getElementById('sortOrder').addEventListener('change', () => this.sortAndDisplayResults());
        document.getElementById('symbolFilter').addEventListener('input', () => this.filterAndDisplayResults());
        document.getElementById('exportResults').addEventListener('click', () => this.exportResults());
        
        // Checkbox change handler
        this.fetchAllSymbolsCheckbox.addEventListener('change', (e) => {
            this.symbolSelect.disabled = e.target.checked;
        });
    }
    
    async loadSymbols() {
        try {
            this.symbolSelect.innerHTML = '<option value="">Loading symbols...</option>';
            
            const data = await ApiService.loadSymbols();
            
            if (data.success) {
                this.symbolSelect.innerHTML = '<option value="">Select a symbol</option>';
                
                const symbols = data.data;
                console.log(`Loaded ${symbols.length} symbols`);
                
                symbols.forEach(symbol => {
                    const option = document.createElement('option');
                    option.value = symbol.symbol;
                    option.textContent = `${symbol.symbol} (${symbol.baseAsset}/${symbol.quoteAsset})`;
                    this.symbolSelect.appendChild(option);
                });
                
                // Set default symbol
                if (symbols.length > 0) {
                    const btcSymbol = symbols.find(s => s.symbol === 'BTCUSDT');
                    this.symbolSelect.value = btcSymbol ? btcSymbol.symbol : symbols[0].symbol;
                }
            } else {
                this.symbolSelect.innerHTML = '<option value="">Error loading symbols</option>';
                console.error('Error loading symbols:', data.error);
            }
        } catch (error) {
            console.error('Error loading symbols:', error);
            this.symbolSelect.innerHTML = '<option value="">Failed to load symbols</option>';
        }
    }
    
    async runBacktest() {
        if (this.isRunning) {
            return;
        }
        
        this.isBulkBacktest = this.fetchAllSymbolsCheckbox.checked;
        
        if (this.isBulkBacktest) {
            await this.runBulkBacktest();
        } else {
            await this.runSingleBacktest();
        }
    }
    
    async runSingleBacktest() {
        if (!this.validateInputs()) {
            return;
        }
        
        this.showLoading(true);
        this.resultsManager.resultsPanel.classList.add('hidden');
        
        this.loadingText.textContent = 'Running backtest...';
        try {
            const params = {
                symbol: this.symbolSelect.value,
                interval: this.intervalSelect.value,
                start_date: this.startDateInput.value,
                end_date: this.endDateInput.value,
                leverage: parseFloat(this.leverageInput.value),
                margin: parseFloat(this.marginInput.value),
                balance: parseFloat(this.balanceInput.value),
                
                // Strategy settings
                macd_fast: parseInt(this.macdFastInput.value),
                macd_slow: parseInt(this.macdSlowInput.value),
                macd_signal: parseInt(this.macdSignalInput.value),
                sma_length: parseInt(this.smaLengthInput.value),
                
                // TP/SL settings
                tp_base: parseFloat(this.tpBaseInput.value),
                stop_loss: parseFloat(this.stopLossInput.value),
                max_tps: parseInt(this.maxTpsInput.value),
                tp_close: parseFloat(this.tpCloseInput.value)
            };
            
            const data = await ApiService.runBacktest(params);
            
            if (data.success) {
                this.showSingleResults();
                this.resultsManager.displayResults(data.data, this.symbolSelect, this.intervalSelect);
            } else {
                this.showError(data.error);
            }
        } catch (error) {
            console.error('Error running backtest:', error);
            this.showError('Failed to run backtest');
        } finally {
            this.showLoading(false);
        }
    }
    
    async runBulkBacktest() {
        if (!this.validateBulkInputs()) {
            return;
        }
        
        this.isRunning = true;
        this.shouldStop = false;
        this.bulkResults = [];
        
        this.showLoading(true, true);
        this.resultsManager.resultsPanel.classList.add('hidden');
        
        try {
            // Get all symbols
            const symbolsData = await ApiService.loadSymbols();
            if (!symbolsData.success) {
                throw new Error('Failed to load symbols');
            }
            
            const allSymbols = symbolsData.data.map(s => s.symbol);
            console.log(`Starting bulk backtest for ${allSymbols.length} symbols`);
            
            this.loadingText.textContent = 'Running bulk backtest...';
            this.progressInfo.classList.remove('hidden');
            this.updateProgress(0, allSymbols.length);
            
            // Process symbols one by one with delay
            for (let i = 0; i < allSymbols.length; i++) {
                if (this.shouldStop) {
                    console.log('Bulk backtest stopped by user');
                    break;
                }
                
                const symbol = allSymbols[i];
                this.loadingText.textContent = `Processing ${symbol}... (${i + 1}/${allSymbols.length})`;
                
                try {
                    const params = this.getBulkBacktestParams(symbol);
                    const data = await ApiService.runBacktest(params);
                    
                    if (data.success) {
                        this.bulkResults.push({
                            symbol: symbol,
                            ...data.data.results.statistics,
                            status: 'Success'
                        });
                    } else {
                        this.bulkResults.push({
                            symbol: symbol,
                            total_return: 0,
                            win_rate: 0,
                            total_trades: 0,
                            final_balance: 0,
                            max_drawdown: 0,
                            status: 'Failed: ' + data.error
                        });
                    }
                } catch (error) {
                    console.error(`Error processing ${symbol}:`, error);
                    this.bulkResults.push({
                        symbol: symbol,
                        total_return: 0,
                        win_rate: 0,
                        total_trades: 0,
                        final_balance: 0,
                        max_drawdown: 0,
                        status: 'Error: ' + error.message
                    });
                }
                
                this.updateProgress(i + 1, allSymbols.length);
                
                // Show results one by one as they complete
                if (this.bulkResults.length > 0) {
                    // Update the results display in real-time
                    this.showBulkResults();
                    this.displayBulkResults();
                    
                    // Log progress
                    console.log(`Completed ${i + 1}/${allSymbols.length}: ${symbol} - ${this.bulkResults[this.bulkResults.length - 1].status}`);
                }
                
                // Add 1 second delay to avoid rate limiting
                if (i < allSymbols.length - 1) {
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }
            
            if (!this.shouldStop) {
                this.loadingText.textContent = 'Bulk backtest completed!';
                this.showBulkResults();
                
                // Add small delay to ensure UI is ready, then display results
                setTimeout(() => {
                    this.displayBulkResults();
                    console.log(`Displaying ${this.bulkResults.length} bulk backtest results`);
                }, 100);
            }
            
        } catch (error) {
            console.error('Error in bulk backtest:', error);
            this.showError('Failed to run bulk backtest: ' + error.message);
        } finally {
            this.showLoading(false);
            this.isRunning = false;
        }
    }
    
    stopBacktest() {
        this.shouldStop = true;
        this.isRunning = false;
        this.showLoading(false);
        console.log('Backtest stop requested');
    }
    
    getBulkBacktestParams(symbol) {
        return {
            symbol: symbol,
            interval: this.intervalSelect.value,
            start_date: this.startDateInput.value,
            end_date: this.endDateInput.value,
            leverage: parseFloat(this.leverageInput.value),
            margin: parseFloat(this.marginInput.value),
            balance: parseFloat(this.balanceInput.value),
            
            // Strategy settings
            macd_fast: parseInt(this.macdFastInput.value),
            macd_slow: parseInt(this.macdSlowInput.value),
            macd_signal: parseInt(this.macdSignalInput.value),
            sma_length: parseInt(this.smaLengthInput.value),
            
            // TP/SL settings
            tp_base: parseFloat(this.tpBaseInput.value),
            stop_loss: parseFloat(this.stopLossInput.value),
            max_tps: parseInt(this.maxTpsInput.value),
            tp_close: parseFloat(this.tpCloseInput.value)
        };
    }
    
    updateProgress(current, total) {
        const percentage = (current / total) * 100;
        this.progressBar.style.width = `${percentage}%`;
        this.progressText.textContent = `${current} / ${total} symbols processed`;
    }
    
    showSingleResults() {
        document.getElementById('singleResultSection').classList.remove('hidden');
        document.getElementById('chartSection').classList.remove('hidden');
        document.getElementById('tradesSection').classList.remove('hidden');
        document.getElementById('bulkResultsSection').classList.add('hidden');
    }
    
    showBulkResults() {
        document.getElementById('singleResultSection').classList.add('hidden');
        document.getElementById('chartSection').classList.add('hidden');
        document.getElementById('tradesSection').classList.add('hidden');
        document.getElementById('bulkResultsSection').classList.remove('hidden');
        document.getElementById('resultsPanel').classList.remove('hidden');
        
        // Update total results count
        document.getElementById('totalResultsCount').textContent = `${this.bulkResults.length} results`;
        
        console.log(`Showing bulk results section with ${this.bulkResults.length} results`);
    }
    
    sortAndDisplayResults() {
        this.displayBulkResults();
    }
    
    filterAndDisplayResults() {
        this.currentPage = 1; // Reset to first page when filtering
        this.displayBulkResults();
    }
    
    displayBulkResults() {
        const sortBy = document.getElementById('sortBy').value;
        const sortOrder = document.getElementById('sortOrder').value;
        const filterText = document.getElementById('symbolFilter').value.toLowerCase();
        
        console.log(`Displaying bulk results: ${this.bulkResults.length} total results`);
        
        if (this.bulkResults.length === 0) {
            console.log('No bulk results to display');
            return;
        }
        
        // Filter results
        let filteredResults = this.bulkResults.filter(result => 
            result.symbol.toLowerCase().includes(filterText)
        );
        
        console.log(`Filtered results: ${filteredResults.length} results`);
        
        // Sort results
        filteredResults.sort((a, b) => {
            let aVal = a[sortBy];
            let bVal = b[sortBy];
            
            if (typeof aVal === 'string') {
                aVal = aVal.toLowerCase();
                bVal = bVal.toLowerCase();
            }
            
            if (sortOrder === 'asc') {
                return aVal > bVal ? 1 : -1;
            } else {
                return aVal < bVal ? 1 : -1;
            }
        });
        
        // Pagination
        const totalResults = filteredResults.length;
        const totalPages = Math.ceil(totalResults / this.resultsPerPage);
        const startIndex = (this.currentPage - 1) * this.resultsPerPage;
        const endIndex = Math.min(startIndex + this.resultsPerPage, totalResults);
        const pageResults = filteredResults.slice(startIndex, endIndex);
        
        // Display results
        const tbody = document.getElementById('bulkResultsTableBody');
        tbody.innerHTML = '';
        
        console.log(`Displaying page results: ${pageResults.length} results for page ${this.currentPage}`);
        
        pageResults.forEach((result, index) => {
            const globalIndex = startIndex + index + 1;
            const row = this.createBulkResultRow(result, globalIndex);
            tbody.appendChild(row);
        });
        
        // Update pagination
        this.updatePagination(totalPages, totalResults);
        
        // Ensure the bulk results section is visible
        document.getElementById('bulkResultsSection').classList.remove('hidden');
        document.getElementById('resultsPanel').classList.remove('hidden');
    }
    
    createBulkResultRow(result, index) {
        const row = document.createElement('tr');
        row.className = 'border-b hover:bg-gray-50';
        
        const returnClass = result.total_return >= 0 ? 'text-green-600' : 'text-red-600';
        const statusClass = result.status === 'Success' ? 'text-green-600' : 'text-red-600';
        
        // Add console log for debugging
        if (index <= 5) {
            console.log(`Creating row ${index} for ${result.symbol}: Return ${result.total_return}%, Status: ${result.status}`);
        }
        
        row.innerHTML = `
            <td class="px-4 py-2 text-sm">${index}</td>
            <td class="px-4 py-2 text-sm font-medium">${result.symbol}</td>
            <td class="px-4 py-2 text-sm font-bold ${returnClass}">${result.total_return.toFixed(2)}%</td>
            <td class="px-4 py-2 text-sm">${result.win_rate.toFixed(2)}%</td>
            <td class="px-4 py-2 text-sm">${result.total_trades}</td>
            <td class="px-4 py-2 text-sm">$${result.final_balance.toFixed(2)}</td>
            <td class="px-4 py-2 text-sm">${result.max_drawdown.toFixed(2)}%</td>
            <td class="px-4 py-2 text-sm ${statusClass}">${result.status}</td>
        `;
        
        return row;
    }
    
    updatePagination(totalPages, totalResults) {
        const container = document.getElementById('paginationContainer');
        
        if (totalPages <= 1) {
            container.innerHTML = '';
            return;
        }
        
        let paginationHTML = `
            <button id="prevPage" class="px-3 py-1 bg-gray-300 text-gray-700 rounded hover:bg-gray-400 disabled:opacity-50" ${this.currentPage === 1 ? 'disabled' : ''}>
                Previous
            </button>
            <span class="px-3 py-1 bg-blue-100 text-blue-800 rounded">
                Page ${this.currentPage} of ${totalPages} (${totalResults} results)
            </span>
            <button id="nextPage" class="px-3 py-1 bg-gray-300 text-gray-700 rounded hover:bg-gray-400 disabled:opacity-50" ${this.currentPage === totalPages ? 'disabled' : ''}>
                Next
            </button>
        `;
        
        container.innerHTML = paginationHTML;
        
        // Add event listeners
        document.getElementById('prevPage').addEventListener('click', () => {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.displayBulkResults();
            }
        });
        
        document.getElementById('nextPage').addEventListener('click', () => {
            if (this.currentPage < totalPages) {
                this.currentPage++;
                this.displayBulkResults();
            }
        });
    }
    
    exportResults() {
        if (this.bulkResults.length === 0) {
            alert('No results to export');
            return;
        }
        
        // Create CSV content
        const headers = ['Symbol', 'Total Return (%)', 'Win Rate (%)', 'Total Trades', 'Final Balance', 'Max Drawdown (%)', 'Status'];
        const csvContent = [
            headers.join(','),
            ...this.bulkResults.map(result => [
                result.symbol,
                result.total_return.toFixed(2),
                result.win_rate.toFixed(2),
                result.total_trades,
                result.final_balance.toFixed(2),
                result.max_drawdown.toFixed(2),
                `"${result.status}"`
            ].join(','))
        ].join('\n');
        
        // Download CSV
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `bulk_backtest_results_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }
    
    validateInputs() {
        if (!this.isBulkBacktest && !this.symbolSelect.value) {
            this.showError('Please select a trading symbol');
            return false;
        }
        
        if (!this.startDateInput.value || !this.endDateInput.value) {
            this.showError('Please select both start and end dates');
            return false;
        }
        
        const startDate = new Date(this.startDateInput.value);
        const endDate = new Date(this.endDateInput.value);
        
        if (startDate >= endDate) {
            this.showError('Start date must be before end date');
            return false;
        }
        
        if (this.leverageInput.value < 1 || this.leverageInput.value > 125) {
            this.showError('Leverage must be between 1 and 125');
            return false;
        }
        
        if (this.marginInput.value < 1 || this.marginInput.value > 100) {
            this.showError('Margin percentage must be between 1% and 100%');
            return false;
        }
        
        return true;
    }
    
    validateBulkInputs() {
        if (!this.startDateInput.value || !this.endDateInput.value) {
            this.showError('Please select both start and end dates');
            return false;
        }
        
        const startDate = new Date(this.startDateInput.value);
        const endDate = new Date(this.endDateInput.value);
        
        if (startDate >= endDate) {
            this.showError('Start date must be before end date');
            return false;
        }
        
        return true;
    }
    
    showLoading(show, isBulk = false) {
        if (show) {
            this.loadingDiv.classList.add('active');
            this.runBacktestBtn.disabled = true;
            this.runBacktestBtn.textContent = isBulk ? 'Running Bulk...' : 'Running...';
            this.runBacktestBtn.classList.add('hidden');
            this.stopBacktestBtn.classList.remove('hidden');
        } else {
            this.loadingDiv.classList.remove('active');
            this.progressInfo.classList.add('hidden');
            this.runBacktestBtn.disabled = false;
            this.runBacktestBtn.textContent = 'Run Backtest';
            this.runBacktestBtn.classList.remove('hidden');
            this.stopBacktestBtn.classList.add('hidden');
        }
    }
    
    showError(message) {
        alert(`Error: ${message}`);
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new CryptoBacktestApp();
});