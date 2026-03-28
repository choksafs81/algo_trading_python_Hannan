# Strategies Folder

This folder contains persistent storage for algorithmic trading strategies.

## File Structure

- `strategy_{strategy_id}.json` - Individual strategy files containing:
  - Strategy configuration (name, description, parameters)
  - Symbol list and trading parameters
  - Status (STOPPED, RUNNING, PAUSED, ERROR)
  - Timestamps (created, updated, started, stopped)
  - MACD parameters (fast_period, slow_period, signal_period)

- `strategies.json` - Main strategies index file
- `executions.json` - Strategy execution history

## Current Strategies

### 1. CIGL MACD Persistent Strategy
- **ID**: `150bd228-439e-435d-b1da-e3b38e0a7add`
- **Status**: RUNNING ✅
- **Symbol**: CIGL
- **Parameters**: Fast: 12, Slow: 26, Signal: 9
- **Created**: 2025-10-04 11:12:54
- **Started**: 2025-10-04 11:12:59

### 2. AAPL MACD Strategy
- **ID**: `32538676-41ba-4b79-9919-88f5276568f0`
- **Status**: STOPPED
- **Symbol**: AAPL
- **Parameters**: Fast: 12, Slow: 26, Signal: 9
- **Created**: 2025-10-04 11:13:07

### 3. Multi-Symbol MACD
- **ID**: `2298955b-9282-4f7e-81f6-8c56452144a2`
- **Status**: STOPPED
- **Symbols**: MSFT, GOOGL
- **Parameters**: Fast: 12, Slow: 26, Signal: 9
- **Created**: 2025-10-04 11:13:08

## MACD Strategy Details

### Technical Analysis
- **MACD Line**: EMA(12) - EMA(26)
- **Signal Line**: EMA(9) of MACD Line
- **Histogram**: MACD Line - Signal Line

### Trading Signals
- **BUY**: MACD crosses above Signal + MACD > 0
- **SELL**: MACD crosses below Signal + MACD < 0
- **Additional Filters**: Histogram momentum, zero line position

### Current CIGL Analysis
- **MACD Line**: 0.0107 (positive, above zero)
- **Signal Line**: 0.0113 (positive, above zero)
- **Histogram**: -0.0006 (negative, MACD below signal)
- **Current Signal**: NO_SIGNAL (waiting for crossover)

## Persistence Features

✅ **Automatic Saving**: Strategies saved on creation, start, stop, update
✅ **Automatic Loading**: Strategies restored on application startup
✅ **Status Persistence**: Running strategies resume after restart
✅ **Execution History**: Trading signals saved to disk
✅ **File Management**: Individual strategy files for easy backup

## API Endpoints

- `POST /api/strategies/macd` - Create MACD strategy
- `POST /api/strategies/{id}/start` - Start strategy
- `POST /api/strategies/{id}/stop` - Stop strategy
- `GET /api/strategies/` - List all strategies
- `POST /api/strategies/test-macd/{symbol}` - Test MACD analysis

## File Backup

All strategy files are automatically backed up and can be restored by:
1. Copying strategy files to this folder
2. Restarting the application
3. Strategies will be automatically loaded

## Monitoring

The running CIGL MACD strategy:
- Analyzes CIGL every 5 minutes
- Generates BUY/SELL signals based on MACD crossovers
- Logs all trading decisions
- Saves execution history to disk



