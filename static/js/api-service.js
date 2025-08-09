class ApiService {
    static async loadSymbols() {
        try {
            const response = await fetch('/api/symbols');
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Error loading symbols:', error);
            throw error;
        }
    }
    
    static async runBacktest(params) {
        try {
            const response = await fetch('/api/backtest', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(params)
            });
            
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Error running backtest:', error);
            throw error;
        }
    }
}