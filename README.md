# Algorithmic Trading System

A comprehensive algorithmic trading system built with Python, FastAPI, and IBKR TWS integration.

## Features

- **Web-based Dashboard**: Modern, responsive web interface for monitoring and control
- **IBKR TWS Integration**: Direct connection to Interactive Brokers with improved connection resilience and automatic retry logic
- **Market Data**: Real-time and historical data from Alpha Vantage and Polygon APIs
- **Trading Strategies**: Framework for implementing and managing automated strategies
- **Real-time Updates**: WebSocket-based live updates for orders, positions, and market data
- **Risk Management**: Built-in position sizing and risk controls
- **Order Management**: Complete order lifecycle management with automatic retry on connection failures
- **Portfolio Tracking**: Real-time portfolio performance monitoring
- **YouTube Stock Scraper**: Automated YouTube video scraping with stock symbol extraction and Halal status checking
- **Manual Ticker Lookup**: 
  - Query single or multiple stock tickers (comma-separated)
  - Get real-time price, trend analysis, and Halal compliance status
  - Export results to CSV format
  - Auto-extract tickers from YouTube URLs
- **Tools Portal**: Comprehensive tools for market analysis and data management

## Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   ```bash
   cp config.env.example .env
   # Edit .env with your API keys and settings
   ```

3. **Start the Application**:
   ```bash
   python main.py
   ```

4. **Access Dashboard**:
   Open your browser to `http://localhost:8000`

## Configuration

### Required API Keys

- **Alpha Vantage**: Get free API key from [Alpha Vantage](https://www.alphavantage.co/support/#api-key)
- **Polygon**: Get API key from [Polygon.io](https://polygon.io/)

### IBKR TWS Setup

1. Install Interactive Brokers TWS or IB Gateway
2. Enable API connections in TWS settings
3. Configure the connection settings in `.env`

## Project Structure

```
algo_trading_python_Hannan/
├── app/
│   ├── api/                 # FastAPI route handlers
│   ├── core/               # Core configuration and utilities
│   ├── models/             # Pydantic data models
│   ├── services/           # Business logic services
│   └── strategies/         # Trading strategy implementations
├── static/                 # Static web assets
├── templates/              # HTML templates
├── config/                 # Configuration files
├── logs/                   # Application logs
├── tests/                  # Test files
├── main.py                 # Application entry point
└── requirements.txt        # Python dependencies
```

## API Endpoints

### Trading
- `POST /api/trading/orders` - Place new order
- `GET /api/trading/orders` - Get all orders
- `GET /api/trading/orders/{order_id}` - Get specific order
- `DELETE /api/trading/orders/{order_id}` - Cancel order
- `GET /api/trading/positions` - Get current positions
- `GET /api/trading/account` - Get account information
- `GET /api/trading/ib/status` - Check IBKR connection status
- `POST /api/trading/orders/preview` - Preview order details

### Market Data
- `GET /api/market-data/quotes/{symbol}` - Get real-time quote
- `POST /api/market-data/historical` - Get historical data
- `GET /api/market-data/news/{symbol}` - Get news for symbol
- `GET /api/market-data/watchlist` - Manage watchlist
- `POST /api/market-data/watchlist/{symbol}` - Add to watchlist
- `DELETE /api/market-data/watchlist/{symbol}` - Remove from watchlist

### Strategies
- `GET /api/strategies/` - Get all strategies
- `POST /api/strategies/` - Create new strategy
- `GET /api/strategies/{id}` - Get strategy details
- `POST /api/strategies/{id}/start` - Start strategy
- `POST /api/strategies/{id}/stop` - Stop strategy
- `DELETE /api/strategies/{id}` - Delete strategy

### Tools
- `GET /tools/scraper` - YouTube scraper tool page
- `POST /api/tools/scraper/run` - Run scraper manually
- `GET /api/tools/scraper/status` - Get scraper status
- `POST /api/tools/scraper/auto` - Enable/disable auto-run with interval
- `GET /api/tools/scraper/last` - Get last scraper results
- `GET /api/tools/scraper/csv` - Download last scraper results as CSV
- `POST /api/tools/ticker-lookup` - Manual ticker lookup (single or multiple)
- `GET /api/tools/manual-ticker/csv` - Export manual ticker results to CSV

## Tools Portal

### YouTube Stock Scraper
Automatically extract stock information from YouTube video titles:
- **Features**:
  - Scrape latest stock-related YouTube videos from configured channels
  - Auto-extract stock symbols from video titles
  - Check Halal compliance status for each stock
  - Analyze market trends using yfinance
  - Export results to CSV
  - Schedule automated scraping with configurable intervals
  - Real-time updates via web interface

- **Usage**:
  1. Navigate to `/tools/scraper`
  2. Click "Run Now" for immediate scrape
  3. Enable "Auto Run" to schedule periodic scraping
  4. Download results as CSV

### Manual Ticker Lookup
Query stock information for one or multiple tickers:
- **Input Options**:
  - Single or multiple tickers (comma-separated): `AAPL,MSFT,TSLA`
  - YouTube URL with stock symbols for auto-extraction
  
- **Output Data**:
  - Company name
  - Halal status (Yes/No/Unknown)
  - Current price
  - Price change percentage
  - Market trend (Uptrend/Downtrend/Sideways)
  
- **Export**: Download tabular results as CSV file

- **Usage**:
  1. Go to `/tools/scraper` (Manual Ticker Lookup section)
  2. Enter tickers separated by commas or paste a YouTube URL
  3. Click "Lookup Tickers"
  4. View results in table format
  5. Click "Download CSV" to export

## WebSocket Events

Connect to `/ws` for real-time updates:
- `order_update` - Order status changes
- `position_update` - Position changes
- `quote_update` - Real-time price updates

## Development

### Running in Development Mode
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Run tests (when implemented)
pytest tests/
```

## Troubleshooting

### IBKR Connection Issues

The system includes automatic connection resilience features:

1. **Connection Failures**: If the app can't connect to TWS on the first attempt:
   - Automatically retries with delay
   - Attempts up to 3 different client IDs (if 326 error: client ID in use)
   - Recovers gracefully when next order ID is delayed

2. **Order Placement Failures**: 
   - If initial order placement fails due to connection issues
   - System automatically reconnects and retries once
   - Returns detailed error messages in API response

3. **Check IBKR Status**:
   - Call `GET /api/trading/ib/status` endpoint
   - Check `connected: true`, `next_order_id` is populated
   - Verify `client_id` and `port` match your configuration

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `502: Couldn't connect to TWS` | TWS not running or port misconfigured | Verify TWS is running, check port in `.env` (usually 7497 for paper) |
| `326: client id already in use` | Client ID conflict | System auto-retries with alternate IDs; restart TWS if persists |
| Order placement fails | No connection/invalid state | Check `/api/trading/ib/status`, restart app if needed |
| Scraper returns no results | No videos found or API issues | Check YouTube channel URL in code, verify network access |
| Missing Halal status | API unreachable | Check internet connection, verify website is accessible |

## Recent Improvements (Latest Release)

- ✅ **Enhanced IBKR Connection Resilience**: Automatic retry logic for transient connection failures
- ✅ **Order Placement Robustness**: Automatic reconnection and retry on initial failure
- ✅ **Multi-Ticker Lookup**: Support for batch ticker queries with tabular results
- ✅ **CSV Export**: Download lookup and scraper results as CSV files
- ✅ **Manual Lookup with Auto-Extract**: Use YouTube URLs to auto-extract and lookup tickers
- ✅ **Better Error Reporting**: Detailed error messages for debugging connection issues

## Security Notes

- Never commit API keys to version control
- Use environment variables for sensitive configuration
- Implement proper authentication for production use
- Always test with paper trading accounts first

## License

This project is for educational purposes. Use at your own risk when trading with real money.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Disclaimer

This software is for educational purposes only. Trading involves substantial risk of loss and is not suitable for all investors. Past performance is not indicative of future results.
