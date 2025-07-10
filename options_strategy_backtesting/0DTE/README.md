# 0DTE Options Strategy Backtesting System

A professional-grade backtesting framework for 0DTE (Zero Days to Expiration) bull put spread options strategies, built with clean object-oriented architecture.

## Quick Start

```python
from backtester import ZeroDTEBacktester

# Run a backtest with default parameters
backtester = ZeroDTEBacktester()
results = backtester.run()
backtester.plot_results()

print(f"Total P&L: ${results['theoretical_pnl'].sum():.2f}")
print(f"Total Trades: {len(results)}")
print(f"Win Rate: {(results['theoretical_pnl'] > 0).mean()*100:.1f}%")
```

That's it! Three lines to run a complete backtest.

## Key Features

- **Easy Option Strategy Testing**: Test 0DTE bull put spreads with just 3 lines of code
- **Flexible Parameter Customization**: Adjust delta ranges, spread widths, profit targets, and risk management settings
- **Historical Market Data**: Uses historical market data from Alpaca (stocks) and Databento (options)
- **Comprehensive Analytics**: Get detailed performance metrics, win rates, and profit/loss analysis
- **Visual Results**: Built-in plotting for strategy performance and trade distribution
- **Command-Line Ready**: Run backtests from terminal for automation and scripting

## Project Structure

```
0DTE/                              # Main project directory
├── backtester/                    # Core backtesting package
│   ├── __init__.py                # Package exports
│   ├── data_client.py             # Data fetching (Alpaca + Databento)
│   ├── option_utils.py            # Mathematical calculations (IV, Delta)
│   ├── spread_selector.py         # Spread selection logic
│   └── backtester.py              # Main backtesting engine
├── zero_dte_backtest_original.ipynb # Original implementation (reference only)
├── run_backtest.py                # CLI interface
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variables template
└── README.md                      # This file
```

## Installation

### Prerequisites
- Python 3.8+
- Alpaca API account (https://app.alpaca.markets/signup)
- Databento API account (https://databento.com/signup)

### Setup
```bash
# Navigate to the project directory
cd 0DTE/

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Environment Variables
Insert your actual API keys in the `.env` file:
```bash
ALPACA_API_KEY=your_alpaca_api_key
ALPACA_SECRET_KEY=your_alpaca_secret_key
DATABENTO_API_KEY=your_databento_api_key
```

## Usage Examples

### Basic Usage
```python
from backtester import ZeroDTEBacktester

# Default configuration (SPY, last 8 days, standard parameters)
backtester = ZeroDTEBacktester()
results = backtester.run()

# View results
print(f"Total P&L: ${results['theoretical_pnl'].sum():.2f}")
backtester.plot_results()
```

### Customizing Strategy Parameters
To modify delta ranges, profit targets, or other strategy settings, edit your Python script or notebook:

```python
# Example: Tighter delta range and higher profit target
backtester = ZeroDTEBacktester(
    short_put_delta_range=(-0.40, -0.25),  # More conservative short puts
    target_profit_percentage=0.6,          # Take 60% profits instead of 50%
    spread_width_range=(2, 3)              # Narrower spreads
)
results = backtester.run()
```

### Custom Configuration
```python
# Customize strategy parameters
backtester = ZeroDTEBacktester(
    underlying_symbol='SPY',
    start_days_ago=10,
    end_days_ago=1,
    short_put_delta_range=(-0.50, -0.25),  # Tighter delta range
    long_put_delta_range=(-0.35, -0.15),
    spread_width_range=(3, 6),             # Wider spreads
    target_profit_percentage=0.4,          # 40% profit target
    delta_stop_loss_multiplier=2.0,        # Conservative stop loss
    risk_free_rate=0.015                   # Current risk-free rate
)

results = backtester.run(max_iterations=200)
stats = backtester.get_trade_statistics()

print(f"Sharpe Ratio: {stats.get('sharpe_ratio', 'N/A')}")
print(f"Max Drawdown: ${stats.get('max_drawdown', 0):.2f}")
```

### CLI Usage
```bash
# Run with default parameters
python run_backtest.py

# Custom parameters
python run_backtest.py \
    --symbol SPY \
    --start-days-ago 10 \
    --max-iterations 2000 \
    --target-profit 0.4 \
    --plot

# See all options
python run_backtest.py --help
```

### Jupyter Notebook
```python
# In Jupyter notebook
%load_ext autoreload
%autoreload 2

from backtester import ZeroDTEBacktester
import matplotlib.pyplot as plt

backtester = ZeroDTEBacktester()
results = backtester.run()

# Custom plotting
plt.figure(figsize=(12, 8))
plt.subplot(2, 1, 1)
plt.plot(results.index, results['cumulative_pnl'])
plt.title('Cumulative P&L')
plt.subplot(2, 1, 2)
plt.hist(results['theoretical_pnl'], bins=20)
plt.title('P&L Distribution')
plt.tight_layout()
plt.show()
```

## Architecture Overview

### Component Responsibilities

#### 1. **DataClient** (`data_client.py`)
**Purpose**: Handles all external data access
- Fetches daily stock bars from Alpaca
- Retrieves intraday stock data (1-minute bars)
- Gets option tick data from Databento
- Combines and organizes historical datasets

```python
from backtester.data_client import DataClient

client = DataClient()
historical_data = client.get_comprehensive_historical_data('SPY', start_date, end_date)
```

#### 2. **OptionUtils** (`option_utils.py`)
**Purpose**: Pure mathematical functions for options pricing
- Black-Scholes delta calculation
- Implied volatility using Brent's method
- Option symbol parsing and generation
- Strike price extraction

```python
from backtester.option_utils import OptionUtils

delta = OptionUtils.calculate_delta(
    option_price=2.5, strike_price=580, expiry_timestamp=expiry,
    underlying_price=585, risk_free_rate=0.01, option_type='put',
    current_timestamp=now
)
```

#### 3. **SpreadSelector** (`spread_selector.py`)
**Purpose**: Identifies optimal spread pairs
- Finds short and long put options meeting delta criteria
- Validates spread width requirements
- Calculates spread metrics for monitoring

```python
from backtester.spread_selector import SpreadSelector

selector = SpreadSelector()
spread = selector.find_spread_pair(
    historical_data, 
    short_delta_range=(-0.60, -0.20),
    long_delta_range=(-0.40, -0.20),
    spread_width_range=(2, 4)
)
```

#### 4. **ZeroDTEBacktester** (`backtester.py`)
**Purpose**: Main orchestration engine
- Coordinates all components
- Executes iterative backtesting
- Monitors exit conditions
- Generates results and statistics

## Strategy Details

### Bull Put Spread Strategy
A **bull put spread** is a credit spread that profits when the underlying asset stays above the short strike price.

**Structure:**
- **Sell** a higher-strike put (collect premium)
- **Buy** a lower-strike put (limit risk)
- **Net result**: Receive credit upfront

### Entry Criteria
- **Short Put Delta**: -0.60 to -0.20 (configurable)
- **Long Put Delta**: -0.40 to -0.20 (configurable)  
- **Spread Width**: $2-$4 (configurable)
- **Expiration**: Same day (0DTE)
- **Time Window**: 13:30-20:00 ET

### Exit Conditions (Priority Order)
1. **Profit Target**: 50% of credit received (configurable)
2. **Delta Stop Loss**: 2.5x initial delta (configurable)
3. **Assignment Risk**: Underlying drops below short strike
4. **Expiration**: End of trading day

### Risk Management
- **Position Sizing**: Single contract spreads
- **Time Limits**: Intraday only
- **Delta Monitoring**: Continuous risk assessment
- **Automatic Stops**: No manual intervention

## Performance Metrics

The backtester provides comprehensive performance analytics:

```python
stats = backtester.get_trade_statistics()

# Key metrics available:
print(f"Total Trades: {stats['total_trades']}")
print(f"Win Rate: {stats['win_rate']:.1%}")
print(f"Average P&L: ${stats['avg_pnl']:.2f}")
print(f"Profit Factor: {stats['profit_factor']:.2f}")
print(f"Max Drawdown: ${stats['max_drawdown']:.2f}")
print(f"Sharpe Ratio: {stats['sharpe_ratio']:.2f}")
```

### Exit Status Breakdown
- **target_profit**: Reached profit target
- **delta_stop_loss**: Hit delta stop loss
- **assignment_risk**: Underlying below short strike
- **expired**: Held to expiration

## Configuration Options

### Core Parameters
```python
ZeroDTEBacktester(
    underlying_symbol='SPY',                    # Underlying asset
    start_days_ago=8,                          # Backtest start (days ago)
    end_days_ago=2,                            # Backtest end (days ago)
    short_put_delta_range=(-0.60, -0.20),     # Short put delta criteria
    long_put_delta_range=(-0.40, -0.20),      # Long put delta criteria
    spread_width_range=(2, 4),                # Spread width ($)
    target_profit_percentage=0.5,             # Profit target (50% of credit)
    delta_stop_loss_multiplier=2.5,           # Delta stop loss multiplier
    risk_free_rate=0.01,                      # Risk-free rate (1%)
    buffer_percentage=0.05                    # Strike range buffer (5%)
)
```

### Advanced Options
```python
# Custom data client
from backtester.data_client import DataClient
custom_client = DataClient(
    alpaca_api_key="custom_key",
    databento_api_key="custom_key"
)

backtester = ZeroDTEBacktester(data_client=custom_client)
```


## Contributing

### Development Setup
```bash
# Clone the repository
git clone <repo-url>
cd 0DTE/

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# You're now ready to use the backtesting system!

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Adding New Features
1. **Follow existing patterns**: Study the current architecture
2. **Update documentation**: Keep README and docstrings current
3. **Validate results**: Ensure new features don't break existing functionality

### Code Standards
- **PEP 8** compliance
- **Type hints** for all public methods
- **Comprehensive docstrings**

## Additional Resources

- **[Workflow Diagram](workflow_diagram.mmd)**: Visual strategy representation
- **[Example Notebook](zero_dte_backtest_refactored.ipynb)**: Interactive examples and tutorials
- **[Original Implementation](zero_dte_backtest_original.ipynb)**: Legacy code for reference and learning

## Risk Disclaimer

This software is for **educational and research purposes only**. Options trading involves substantial risk and is not suitable for all investors. Past performance does not guarantee future results.

- **Paper Trading Only**: System configured for Alpaca paper trading
- **No Financial Advice**: This is not investment advice
- **Use at Your Own Risk**: Authors not responsible for trading losses
- **Validate Thoroughly**: Test extensively before any real trading

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **Alpaca Markets**: Stock market data API
- **Databento**: Options market data provider
- **Open Source Community**: Libraries and tools that made this possible

---

**Happy backtesting!**

For questions, issues, or contributions, please open an issue or submit a pull request.