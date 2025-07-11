"""
Main backtesting engine for 0DTE bull put spread strategies.

This module contains the ZeroDTEBacktester class that orchestrates data retrieval,
spread selection, trade monitoring, and results aggregation.
"""

import os
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dotenv import load_dotenv

from .data_client import DataClient
from .option_utils import OptionUtils
from .spread_selector import SpreadLegs, SpreadSelector


class ZeroDTEBacktester:
    """Main backtesting engine for 0DTE bull put spread strategies."""
    
    def __init__(
        self,
        underlying_symbol: str = 'SPY',
        start_days_ago: int = 8,
        end_days_ago: int = 2,
        risk_free_rate: float = 0.01,
        short_put_delta_range: tuple = (-0.60, -0.20),
        long_put_delta_range: tuple = (-0.40, -0.20),
        spread_width_range: tuple = (2, 4),
        delta_stop_loss_multiplier: float = 2.5,
        target_profit_percentage: float = 0.5,
        buffer_pct: float = 0.05,
        timezone: str = "America/New_York"
    ):
        """
        Initialize the backtester with strategy parameters.
        
        Args:
            underlying_symbol: Symbol to trade (default 'SPY')
            start_days_ago: Days ago to start backtest (default 8)
            end_days_ago: Days ago to end backtest (default 2)
            risk_free_rate: Risk-free rate for calculations (default 0.01)
            short_put_delta_range: Delta range for short put selection
            long_put_delta_range: Delta range for long put selection
            spread_width_range: Acceptable spread width range
            delta_stop_loss_multiplier: Multiplier for delta stop loss
            target_profit_percentage: Target profit as percentage of credit
            buffer_pct: Buffer percentage for strike price range
            timezone: Timezone for operations
        """
        # Load environment variables
        load_dotenv()
        
        # Strategy parameters
        self.underlying_symbol = underlying_symbol
        self.risk_free_rate = risk_free_rate
        self.delta_stop_loss_multiplier = delta_stop_loss_multiplier
        self.target_profit_percentage = target_profit_percentage
        self.buffer_pct = buffer_pct
        self.timezone = ZoneInfo(timezone)
        
        # Calculate date range
        today = datetime.now(self.timezone).date()
        self.start_date = today - timedelta(days=start_days_ago)
        self.end_date = today - timedelta(days=end_days_ago)
        
        # Initialize data client
        self.data_client = DataClient(
            alpaca_api_key=os.environ.get('ALPACA_API_KEY'),
            alpaca_secret_key=os.environ.get('ALPACA_SECRET_KEY'),
            databento_api_key=os.getenv("DATABENTO_API_KEY"),
            timezone=timezone
        )
        
        # Initialize spread selector
        self.spread_selector = SpreadSelector(
            short_put_delta_range=short_put_delta_range,
            long_put_delta_range=long_put_delta_range,
            spread_width_range=spread_width_range,
            risk_free_rate=risk_free_rate
        )
        
        # Data storage
        self.historical_data = None
        self.results = []
    
    def _load_historical_data(self) -> Dict[datetime, List[Dict]]:
        """Load all historical data needed for backtesting."""
        print(f"Loading historical data for {self.underlying_symbol} from {self.start_date} to {self.end_date}")
        
        # Get daily stock bars
        stock_bars_data = self.data_client.get_daily_bars(
            self.underlying_symbol, self.start_date, self.end_date
        )
        
        # Collect option symbols by expiration
        option_symbols_by_expiration = self.data_client.collect_option_symbols_by_expiration(
            stock_bars_data, self.underlying_symbol, self.buffer_pct
        )
        
        # Get comprehensive historical data
        historical_data = self.data_client.get_comprehensive_historical_data(
            option_symbols_by_expiration, self.underlying_symbol
        )
        
        print(f"Loaded data for {len(historical_data)} timestamps")
        return historical_data
    
    def _execute_single_trade(
        self,
        filtered_data: Dict[datetime, List[Dict]]
    ) -> Optional[Dict]:
        """
        Execute a single trade using the filtered historical data.
        
        Args:
            filtered_data: Historical data filtered from a specific start time
            
        Returns:
            Dictionary with trade results or None if no trade executed
        """
        # Find a valid spread
        spread = self.spread_selector.find_spread(filtered_data)
        
        if not spread:
            return None
        
        # Calculate initial metrics
        initial_total_delta = spread.initial_total_delta
        delta_stop_loss = initial_total_delta * self.delta_stop_loss_multiplier
        target_profit_price = spread.credit_received * self.target_profit_percentage
        
        # Monitor the trade through subsequent timestamps
        for timestamp in filtered_data.keys():
            if timestamp <= spread.entry_timestamp:
                continue  # Skip timestamps up to and including entry time
            
            current_data = filtered_data[timestamp]
            
            # Calculate current spread metrics
            metrics = self.spread_selector.calculate_current_spread_metrics(
                spread, current_data, self.risk_free_rate
            )
            
            if not metrics:
                continue  # Skip if we can't calculate metrics
            
            # Check exit conditions
            exit_result = self._check_exit_conditions(
                spread, metrics, target_profit_price, delta_stop_loss
            )
            
            if exit_result:
                exit_result.update({
                    'short_put_symbol': spread.short_leg.option_symbol,
                    'long_put_symbol': spread.long_leg.option_symbol,
                    'entry_time': spread.entry_timestamp,
                    'exit_time': timestamp,
                    'credit_received': spread.credit_received,
                    'spread_width': spread.spread_width
                })
                return exit_result
        
        # Handle expiration (no exit condition met)
        final_timestamp = max(filtered_data.keys())
        return {
            'status': 'expired',
            'theoretical_pnl': spread.credit_received * 100,  # Convert to dollars
            'short_put_symbol': spread.short_leg.option_symbol,
            'long_put_symbol': spread.long_leg.option_symbol,
            'entry_time': spread.entry_timestamp,
            'exit_time': final_timestamp,
            'credit_received': spread.credit_received,
            'spread_width': spread.spread_width
        }
    
    def _check_exit_conditions(
        self,
        spread: SpreadLegs,
        metrics: Dict,
        target_profit_price: float,
        delta_stop_loss: float
    ) -> Optional[Dict]:
        """
        Check if any exit conditions are met.
        
        Args:
            spread: Current spread position
            metrics: Current market metrics
            target_profit_price: Target profit price level
            delta_stop_loss: Delta stop loss threshold
            
        Returns:
            Dictionary with exit result or None if no exit condition met
        """
        current_spread_price = metrics['current_spread_price']
        current_total_delta = metrics['current_total_delta']
        current_underlying_price = metrics['current_underlying_price']
        
        # Check profit target
        if current_spread_price <= target_profit_price:
            return {
                'status': 'target_profit',
                'theoretical_pnl': (spread.credit_received - current_spread_price) * 100
            }
        
        # Check delta stop loss
        if current_total_delta >= delta_stop_loss:
            return {
                'status': 'delta_stop_loss',
                'theoretical_pnl': (spread.credit_received - current_spread_price) * 100
            }
        
        # Check assignment risk (underlying below short strike)
        if current_underlying_price <= spread.short_leg.strike_price:
            theoretical_loss = (spread.credit_received - 
                              (spread.short_leg.strike_price - current_underlying_price))
            return {
                'status': 'assignment_risk',
                'theoretical_pnl': theoretical_loss * 100
            }
        
        # No exit condition met
        return None
    
    def run(self, max_iterations: int = 5000) -> pd.DataFrame:
        """
        Run the iterative backtest.
        
        Args:
            max_iterations: Maximum number of trades to execute
            
        Returns:
            DataFrame with all trade results
        """
        print(f"Starting backtest for {self.underlying_symbol}")
        print(f"Date range: {self.start_date} to {self.end_date}")
        print(f"Max iterations: {max_iterations}")
        
        # Load historical data once
        if self.historical_data is None:
            self.historical_data = self._load_historical_data()
        
        if not self.historical_data:
            print("No historical data available")
            return pd.DataFrame()
        
        # Initialize iteration variables
        current_start_time = min(self.historical_data.keys())
        iteration = 1
        self.results = []
        
        while iteration <= max_iterations:
            print(f"\n--- Iteration {iteration} ---")
            print(f"Starting from: {current_start_time}")
            
            # Filter data to only include timestamps after current_start_time
            filtered_data = {
                timestamp: data for timestamp, data in self.historical_data.items()
                if timestamp >= current_start_time
            }
            
            if not filtered_data:
                print("No more data available. Ending iterations.")
                break
            
            # Execute a single trade
            result = self._execute_single_trade(filtered_data)
            
            if not result:
                print("Could not execute trade. Ending iterations.")
                break
            
            # Store result
            result['iteration'] = iteration
            self.results.append(result)
            
            print(f"Status: {result['status']} | "
                  f"P&L: ${result['theoretical_pnl']:.2f} | "
                  f"Entry: {result['entry_time']} | "
                  f"Exit: {result['exit_time']}")
            
            # Update start time for next iteration
            current_start_time = result['exit_time'] + pd.Timedelta(minutes=1)
            iteration += 1
        
        # Convert results to DataFrame
        if self.results:
            df = pd.DataFrame(self.results)
            df['cumulative_pnl'] = df['theoretical_pnl'].cumsum()
            df['entry_time'] = pd.to_datetime(df['entry_time'])
            df['exit_time'] = pd.to_datetime(df['exit_time'])
            
            # Print summary
            total_pnl = df['theoretical_pnl'].sum()
            win_rate = (df['theoretical_pnl'] > 0).mean() * 100
            
            print(f"\n--- Final Summary ---")
            print(f"Total trades: {len(df)}")
            print(f"Total P&L: ${total_pnl:.2f}")
            print(f"Win rate: {win_rate:.1f}%")
            print(f"Average P&L per trade: ${total_pnl/len(df):.2f}")
            
            return df
        else:
            print("No trades executed")
            return pd.DataFrame()
    
    def plot_results(self, results_df: Optional[pd.DataFrame] = None) -> None:
        """
        Plot the cumulative P&L over time.
        
        Args:
            results_df: DataFrame with results (uses self.results if None)
        """
        if results_df is None:
            if not self.results:
                print("No results to plot")
                return
            results_df = pd.DataFrame(self.results)
            results_df['cumulative_pnl'] = results_df['theoretical_pnl'].cumsum()
            results_df['entry_time'] = pd.to_datetime(results_df['entry_time'])
        
        if results_df.empty:
            print("No results to plot")
            return
        
        # Create plot
        plt.figure(figsize=(12, 6))
        plt.plot(results_df['entry_time'], results_df['cumulative_pnl'], 
                linewidth=2, marker='o', markersize=4)
        plt.axhline(y=0, color='red', linestyle='--', alpha=0.7)
        plt.title('0DTE Bull Put Spread - Cumulative P&L Over Time', 
                 fontsize=14, fontweight='bold')
        plt.xlabel('Date')
        plt.ylabel('Cumulative P&L ($)')
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        
        # Add final P&L text
        final_pnl = results_df['cumulative_pnl'].iloc[-1]
        plt.text(results_df['entry_time'].iloc[int(len(results_df)*0.7)], 
                final_pnl, f'Final P&L: ${final_pnl:.2f}', 
                fontsize=12, fontweight='bold', 
                bbox=dict(boxstyle="round,pad=0.3", facecolor='yellow', alpha=0.7))
        
        plt.tight_layout()
        plt.show()
    
    def get_trade_statistics(self, results_df: Optional[pd.DataFrame] = None) -> Dict:
        """
        Calculate detailed trade statistics.
        
        Args:
            results_df: DataFrame with results (uses self.results if None)
            
        Returns:
            Dictionary with trade statistics
        """
        if results_df is None:
            if not self.results:
                return {}
            results_df = pd.DataFrame(self.results)
        
        if results_df.empty:
            return {}
        
        total_trades = len(results_df)
        winning_trades = (results_df['theoretical_pnl'] > 0).sum()
        losing_trades = (results_df['theoretical_pnl'] <= 0).sum()
        
        total_pnl = results_df['theoretical_pnl'].sum()
        avg_pnl = results_df['theoretical_pnl'].mean()
        
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        avg_winner = results_df[results_df['theoretical_pnl'] > 0]['theoretical_pnl'].mean() if winning_trades > 0 else 0
        avg_loser = results_df[results_df['theoretical_pnl'] <= 0]['theoretical_pnl'].mean() if losing_trades > 0 else 0
        
        # Status breakdown
        status_counts = results_df['status'].value_counts().to_dict()
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'average_pnl': avg_pnl,
            'average_winner': avg_winner,
            'average_loser': avg_loser,
            'status_breakdown': status_counts,
            'max_pnl': results_df['theoretical_pnl'].max(),
            'min_pnl': results_df['theoretical_pnl'].min(),
        } 