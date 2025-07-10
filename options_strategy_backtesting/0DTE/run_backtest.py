#!/usr/bin/env python3
"""
CLI entry point for running 0DTE bull put spread backtests.

This script provides a simple interface for running backtests with customizable parameters.
"""

import argparse
import sys
from datetime import datetime
from backtester import ZeroDTEBacktester


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description='Run 0DTE Bull Put Spread Backtest',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Strategy parameters
    parser.add_argument(
        '--symbol', '-s',
        type=str,
        default='SPY',
        help='Underlying symbol to trade'
    )
    
    parser.add_argument(
        '--start-days-ago',
        type=int,
        default=8,
        help='Number of days ago to start backtest'
    )
    
    parser.add_argument(
        '--end-days-ago',
        type=int,
        default=2,
        help='Number of days ago to end backtest'
    )
    
    parser.add_argument(
        '--max-iterations',
        type=int,
        default=5000,
        help='Maximum number of trades to execute'
    )
    
    parser.add_argument(
        '--risk-free-rate',
        type=float,
        default=0.01,
        help='Risk-free rate for options calculations'
    )
    
    parser.add_argument(
        '--delta-stop-loss',
        type=float,
        default=2.5,
        help='Delta stop loss multiplier'
    )
    
    parser.add_argument(
        '--target-profit',
        type=float,
        default=0.5,
        help='Target profit percentage of credit received'
    )
    
    parser.add_argument(
        '--spread-width-min',
        type=float,
        default=2.0,
        help='Minimum spread width'
    )
    
    parser.add_argument(
        '--spread-width-max',
        type=float,
        default=4.0,
        help='Maximum spread width'
    )
    
    parser.add_argument(
        '--short-delta-min',
        type=float,
        default=-0.60,
        help='Minimum delta for short put'
    )
    
    parser.add_argument(
        '--short-delta-max',
        type=float,
        default=-0.20,
        help='Maximum delta for short put'
    )
    
    parser.add_argument(
        '--long-delta-min',
        type=float,
        default=-0.40,
        help='Minimum delta for long put'
    )
    
    parser.add_argument(
        '--long-delta-max',
        type=float,
        default=-0.20,
        help='Maximum delta for long put'
    )
    
    parser.add_argument(
        '--no-plot',
        action='store_true',
        help='Skip plotting results'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.start_days_ago <= args.end_days_ago:
        print("Error: start-days-ago must be greater than end-days-ago")
        sys.exit(1)
    
    if args.spread_width_min >= args.spread_width_max:
        print("Error: spread-width-min must be less than spread-width-max")
        sys.exit(1)
    
    # Print configuration
    print("=" * 60)
    print("0DTE Bull Put Spread Backtest Configuration")
    print("=" * 60)
    print(f"Symbol: {args.symbol}")
    print(f"Date range: {args.start_days_ago} to {args.end_days_ago} days ago")
    print(f"Max iterations: {args.max_iterations}")
    print(f"Risk-free rate: {args.risk_free_rate:.2%}")
    print(f"Delta stop loss: {args.delta_stop_loss}x")
    print(f"Target profit: {args.target_profit:.1%}")
    print(f"Spread width: ${args.spread_width_min} - ${args.spread_width_max}")
    print(f"Short put delta: {args.short_delta_min} to {args.short_delta_max}")
    print(f"Long put delta: {args.long_delta_min} to {args.long_delta_max}")
    print("=" * 60)
    
    try:
        # Initialize backtester
        backtester = ZeroDTEBacktester(
            underlying_symbol=args.symbol,
            start_days_ago=args.start_days_ago,
            end_days_ago=args.end_days_ago,
            risk_free_rate=args.risk_free_rate,
            short_put_delta_range=(args.short_delta_min, args.short_delta_max),
            long_put_delta_range=(args.long_delta_min, args.long_delta_max),
            spread_width_range=(args.spread_width_min, args.spread_width_max),
            delta_stop_loss_multiplier=args.delta_stop_loss,
            target_profit_percentage=args.target_profit
        )
        
        # Run backtest
        print("\nStarting backtest...")
        results_df = backtester.run(max_iterations=args.max_iterations)
        
        if results_df.empty:
            print("No trades were executed.")
            return
        
        # Display detailed statistics
        stats = backtester.get_trade_statistics(results_df)
        
        print("\n" + "=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)
        print(f"Total Trades: {stats['total_trades']}")
        print(f"Winning Trades: {stats['winning_trades']}")
        print(f"Losing Trades: {stats['losing_trades']}")
        print(f"Win Rate: {stats['win_rate']:.1f}%")
        print(f"Total P&L: ${stats['total_pnl']:.2f}")
        print(f"Average P&L per Trade: ${stats['average_pnl']:.2f}")
        print(f"Average Winner: ${stats['average_winner']:.2f}")
        print(f"Average Loser: ${stats['average_loser']:.2f}")
        print(f"Best Trade: ${stats['max_pnl']:.2f}")
        print(f"Worst Trade: ${stats['min_pnl']:.2f}")
        
        print("\nExit Status Breakdown:")
        for status, count in stats['status_breakdown'].items():
            percentage = (count / stats['total_trades']) * 100
            print(f"  {status}: {count} ({percentage:.1f}%)")
        
        # Plot results if requested
        if not args.no_plot:
            print("\nGenerating plot...")
            backtester.plot_results(results_df)
        
        print("\nBacktest completed successfully!")
        
    except KeyboardInterrupt:
        print("\nBacktest interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError running backtest: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 