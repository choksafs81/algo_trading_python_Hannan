# Algorithmic Trading System

A comprehensive algorithmic trading system built with Python, FastAPI, and IBKR TWS integration.

## Features

- **Web-based Dashboard**: Modern, responsive web interface for monitoring and control
- **IBKR TWS Integration**: Direct connection to Interactive Brokers for live trading
- **Market Data**: Real-time and historical data from Alpha Vantage and Polygon APIs
- **Trading Strategies**: Framework for implementing and managing automated strategies
- **Real-time Updates**: WebSocket-based live updates for orders, positions, and market data
- **Risk Management**: Built-in position sizing and risk controls
- **Order Management**: Complete order lifecycle management
- **Portfolio Tracking**: Real-time portfolio performance monitoring

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
- `GET /api/trading/positions` - Get current positions
- `GET /api/trading/account` - Get account information

### Market Data
- `GET /api/market-data/quotes/{symbol}` - Get real-time quote
- `POST /api/market-data/historical` - Get historical data
- `GET /api/market-data/news/{symbol}` - Get news for symbol
- `GET /api/market-data/watchlist` - Manage watchlist

### Strategies
- `GET /api/strategies/` - Get all strategies
- `POST /api/strategies/` - Create new strategy
- `POST /api/strategies/{id}/start` - Start strategy
- `POST /api/strategies/{id}/stop` - Stop strategy

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
