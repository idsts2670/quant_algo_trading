"""
Data client for fetching stock and option data from Alpaca and Databento APIs.

This module isolates all external API calls and data fetching logic,
providing clean interfaces for historical data retrieval.
"""

from datetime import date, datetime
from typing import Dict, List
from zoneinfo import ZoneInfo

import databento as db
import numpy as np
import pandas as pd
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from .option_utils import OptionUtils


class DataClient:
    """Client for fetching historical stock and option data."""
    
    def __init__(
        self,
        alpaca_api_key: str,
        alpaca_secret_key: str,
        databento_api_key: str,
        timezone: str = "America/New_York"
    ):
        """
        Initialize the data client with API credentials.
        
        Args:
            alpaca_api_key: Alpaca API key
            alpaca_secret_key: Alpaca secret key
            databento_api_key: Databento API key
            timezone: Timezone for data operations (default "America/New_York")
        """
        self.timezone = ZoneInfo(timezone)
        
        # Initialize Alpaca stock data client
        self.stock_data_client = StockHistoricalDataClient(
            api_key=alpaca_api_key,
            secret_key=alpaca_secret_key
        )
        
        # Initialize Databento client
        self.databento_client = db.Historical(databento_api_key)
    
    def get_daily_bars(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        """
        Fetch daily stock bars for the given symbol and date range.
        
        Args:
            symbol: Stock symbol (e.g., 'SPY')
            start_date: Start date
            end_date: End date
            
        Returns:
            DataFrame with daily OHLCV data indexed by timestamp
        """
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame(amount=1, unit=TimeFrameUnit.Day),
            start=start_date,
            end=end_date,
        )
        resp = self.stock_data_client.get_stock_bars(req)
        bars = resp.data[symbol]
        
        rows = [bar.model_dump() for bar in bars]
        df = pd.DataFrame(rows).set_index("timestamp").sort_index()
        
        return df
    
    def get_intraday_stock_bars(
        self,
        symbol: str,
        start_datetime: datetime,
        end_datetime: datetime
    ) -> pd.DataFrame:
        """
        Fetch intraday stock bars for the given symbol and datetime range.
        
        Args:
            symbol: Stock symbol (e.g., 'SPY')
            start_datetime: Start datetime
            end_datetime: End datetime
            timeframe: Timeframe (default "1Min")
            
        Returns:
            DataFrame with intraday OHLCV data indexed by timestamp
        """
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame(amount=1, unit=TimeFrameUnit.Minute),
            start=start_datetime,
            end=end_datetime
        )
        resp = self.stock_data_client.get_stock_bars(req)
        
        if symbol not in resp.data:
            return pd.DataFrame()
        
        rows = [bar.model_dump() for bar in resp.data[symbol]]
        df = pd.DataFrame(rows).set_index("timestamp").sort_index()
        
        return df
    
    def get_option_ticks(
        self,
        option_symbols: List[str],
        start_datetime: datetime,
        end_datetime: datetime
    ) -> pd.DataFrame:
        """
        Fetch option tick data using Databento API.
        
        Args:
            option_symbols: List of option symbols
            start_datetime: Start datetime
            end_datetime: End datetime
            
        Returns:
            DataFrame with option tick data
        """
        # Transform options symbols to format required by databento (add spaces)
        formatted_symbols = [f"{symbol[:3]}   {symbol[3:]}" for symbol in option_symbols]
        
        # Convert datetime to ISO string format for databento API request
        start_iso = start_datetime.strftime("%Y-%m-%dT%H:%M:%S")
        end_iso = end_datetime.strftime("%Y-%m-%dT%H:%M:%S")
        
        # Get option tick data using databento client
        try:
            option_df = self.databento_client.timeseries.get_range(
                dataset="OPRA.PILLAR",
                schema="cbbo-1m",
                symbols=formatted_symbols,
                start=start_iso,
                end=end_iso,
            ).to_df()
            
            if option_df.empty:
                return pd.DataFrame()
            
            # Process the DataFrame to match expected format
            processed_data = []
            for idx, row in option_df.iterrows():
                # Extract original symbol by removing spaces
                original_symbol = row['symbol'].replace(' ', '')
                
                tick_data = {
                    'option_symbol': original_symbol,
                    'timestamp': idx,
                    'close': row['price'],
                    'bid': row['bid_px_00'],
                    'ask': row['ask_px_00'],
                    'midpoint': (row['bid_px_00'] + row['ask_px_00']) / 2,
                    'bid_size': row['bid_sz_00'],
                    'ask_size': row['ask_sz_00'],
                    'strike_price': OptionUtils.extract_strike_price(original_symbol)
                }
                processed_data.append(tick_data)
            
            return pd.DataFrame(processed_data)
            
        except Exception as e:
            print(f"Error fetching option data: {e}")
            return pd.DataFrame()
    
    def collect_option_symbols_by_expiration(
        self,
        stock_bars_data: pd.DataFrame,
        underlying_symbol: str,
        buffer_pct: float = 0.05
    ) -> Dict[date, List[str]]:
        """
        Collect option symbols grouped by expiration date based on stock bars data.
        
        Args:
            stock_bars_data: DataFrame with daily stock bars
            underlying_symbol: Underlying symbol
            buffer_pct: Buffer percentage for strike price range
            
        Returns:
            Dictionary with expiration dates as keys and lists of option symbols as values
        """
        option_symbols_by_expiration = {}
        
        for index, row in stock_bars_data.iterrows():
            min_strike, max_strike = OptionUtils.calculate_strike_price_range(
                row['high'], row['low'], buffer_pct=buffer_pct
            )
            
            # Extract date from the timestamp index for 0DTE (same day expiration)
            expiration_date = index.date()
            
            option_symbols = OptionUtils.generate_put_option_symbols(
                underlying_symbol,
                expiration_date=expiration_date,
                min_strike=min_strike,
                max_strike=max_strike,
                strike_increment=1
            )
            
            # Group symbols by expiration date
            if expiration_date not in option_symbols_by_expiration:
                option_symbols_by_expiration[expiration_date] = []
            
            option_symbols_by_expiration[expiration_date].extend(option_symbols)
        
        return option_symbols_by_expiration
    
    def get_comprehensive_historical_data(
        self,
        option_symbols_by_expiration: Dict[date, List[str]],
        underlying_symbol: str
    ) -> Dict[datetime, List[Dict]]:
        """
        Get comprehensive historical data combining stock and option data.
        
        Args:
            option_symbols_by_expiration: Dictionary of option symbols by expiration date
            underlying_symbol: Underlying symbol
            
        Returns:
            Dictionary with timestamp as key and list of combined data dictionaries as value
        """
        combined_data_by_timestamp = {}
        
        for expiration_date, symbols_list in option_symbols_by_expiration.items():
            # Create start and end datetime with specific times
            start_datetime = datetime(expiration_date.year, expiration_date.month, expiration_date.day, 13, 30)
            end_datetime = datetime(expiration_date.year, expiration_date.month, expiration_date.day, 20, 0)
            
            print(f"Processing data for {expiration_date}: {start_datetime} to {end_datetime}")
            
            # Get stock bar data
            stock_df = self.get_intraday_stock_bars(underlying_symbol, start_datetime, end_datetime)
            
            # Create stock close lookup
            stock_close_by_timestamp = {}
            if not stock_df.empty:
                stock_close_by_timestamp = stock_df['close'].to_dict()
                print(f"Retrieved {len(stock_df)} stock bars for {underlying_symbol}")
            
            # Get option tick data
            option_df = self.get_option_ticks(symbols_list, start_datetime, end_datetime)
            
            if not option_df.empty:
                # Convert market close time to UTC for expiry
                market_close_utc = datetime(
                    expiration_date.year, expiration_date.month, expiration_date.day, 
                    16, 0, tzinfo=self.timezone
                ).astimezone(ZoneInfo("UTC"))
                
                # Process option data and combine with stock data
                for _, row in option_df.iterrows():
                    timestamp = row['timestamp']
                    
                    # Create combined tick data
                    tick_data = {
                        'option_symbol': row['option_symbol'],
                        'timestamp': timestamp,
                        'close': row['close'],
                        'bid': row['bid'],
                        'ask': row['ask'],
                        'midpoint': row['midpoint'],
                        'bid_size': row['bid_size'],
                        'ask_size': row['ask_size'],
                        'strike_price': row['strike_price'],
                        'expiry': market_close_utc,
                        'underlying_close': stock_close_by_timestamp.get(timestamp)
                    }
                    
                    # Initialize timestamp key if it doesn't exist
                    if timestamp not in combined_data_by_timestamp:
                        combined_data_by_timestamp[timestamp] = []
                    
                    # Add this tick data to the timestamp group
                    combined_data_by_timestamp[timestamp].append(tick_data)
                
                print(f"Retrieved {len(option_df)} option ticks for {len(symbols_list)} symbols")
            else:
                print(f"No option data found for {len(symbols_list)} symbols")
        
        # Sort timestamps for consistent ordering
        sorted_timestamps = sorted(combined_data_by_timestamp.keys())
        sorted_data = {ts: combined_data_by_timestamp[ts] for ts in sorted_timestamps}
        
        return sorted_data 