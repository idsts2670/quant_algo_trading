"""
Spread selector for identifying optimal bull put spread option pairs.

This module contains the logic for finding short and long put options that meet the specified delta and spread width criteria.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from alpaca.trading.enums import ContractType

from .option_utils import OptionUtils


@dataclass
class OptionLeg:
    """Represents a single option leg in a spread."""
    option_symbol: str
    strike_price: float
    underlying_price: float
    delta: float
    option_price: float
    timestamp: datetime
    expiration_date: datetime


@dataclass
class SpreadLegs:
    """Represents a complete bull put spread with both legs."""
    short_leg: OptionLeg
    long_leg: OptionLeg
    credit_received: float
    entry_timestamp: datetime
    spread_width: float
    
    @property
    def initial_total_delta(self) -> float:
        """Calculate the initial total delta of the spread."""
        return abs(self.short_leg.delta) - abs(self.long_leg.delta)


class SpreadSelector:
    """Selects optimal bull put spread pairs based on delta and spread width criteria."""
    
    def __init__(
        self,
        short_put_delta_range: Tuple[float, float],
        long_put_delta_range: Tuple[float, float],
        spread_width_range: Tuple[float, float],
        risk_free_rate: float
    ):
        """
        Initialize the spread selector with trading criteria.
        
        Args:
            short_put_delta_range: Delta range for short put selection (e.g., (-0.60, -0.20))
            long_put_delta_range: Delta range for long put selection (e.g., (-0.40, -0.20))
            spread_width_range: Acceptable spread width range (e.g., (2, 4))
            risk_free_rate: Risk-free rate for options calculations
        """
        self.short_put_delta_range = short_put_delta_range
        self.long_put_delta_range = long_put_delta_range
        self.spread_width_range = spread_width_range
        self.risk_free_rate = risk_free_rate
    
    def find_spread(
        self,
        historical_data_by_timestamp: Dict[datetime, List[Dict]],
        option_type: str = 'put'
    ) -> Optional[SpreadLegs]:
        """
        Find the first valid bull put spread from historical data.
        
        Args:
            historical_data_by_timestamp: Dictionary with timestamp as key and option data as value
            option_type: Type of option ('put' or 'call')
            
        Returns:
            SpreadLegs object if valid spread found, None otherwise
        """
        short_put = None
        long_put = None
        
        for timestamp, tick_data_list in historical_data_by_timestamp.items():
            print(f"Analyzing timestamp: {timestamp}")
            
            for tick_data in tick_data_list:
                option_symbol = tick_data['option_symbol']
                print(f"Option symbol is: {option_symbol}")
                
                # Get tick data
                underlying_price = tick_data['underlying_close']
                if underlying_price is None:
                    continue
                    
                option_price = tick_data['midpoint']
                strike_price = tick_data['strike_price']
                expiry = tick_data['expiry']
                current_timestamp = tick_data['timestamp']
                
                # Calculate delta
                delta = OptionUtils.calculate_delta(
                    option_price=option_price,
                    strike_price=strike_price,
                    expiry_timestamp=expiry,
                    underlying_price=underlying_price,
                    risk_free_rate=self.risk_free_rate,
                    option_type=option_type,
                    current_timestamp=current_timestamp
                )
                
                print(f"Delta for {option_symbol} is: {delta}")
                
                # Skip this option if delta calculation failed
                if delta is None:
                    print(f"Delta calculation failed for {option_symbol} at timestamp: {timestamp}")
                    continue
                
                # Check if this option meets short put criteria
                if not short_put and self.short_put_delta_range[0] <= delta <= self.short_put_delta_range[1]:
                    short_put = self._create_option_leg(
                        option_symbol, strike_price, underlying_price, 
                        delta, option_price, current_timestamp, expiry
                    )
                
                # Check if this option meets long put criteria
                elif self.long_put_delta_range[0] <= delta <= self.long_put_delta_range[1]:
                    long_put = self._create_option_leg(
                        option_symbol, strike_price, underlying_price,
                        delta, option_price, current_timestamp, expiry
                    )
                
                # Check if we have both legs and validate spread
                if short_put and long_put:
                    spread_width = abs(short_put.strike_price - long_put.strike_price)
                    
                    if not (self.spread_width_range[0] <= spread_width <= self.spread_width_range[1]):
                        print(f"Spread width of {spread_width} is outside the target range of "
                              f"${self.spread_width_range[0]}-${self.spread_width_range[1]}; resetting search.")
                        # Reset both options to continue searching
                        short_put = None
                        long_put = None
                        continue
                    else:
                        # Create and return valid spread
                        credit_received = short_put.option_price - long_put.option_price
                        print(f"Valid spread found with width ${spread_width} at timestamp: {timestamp} "
                              f"for {short_put.option_symbol} and {long_put.option_symbol} "
                              f"at underlying price: {underlying_price}")
                        
                        return SpreadLegs(
                            short_leg=short_put,
                            long_leg=long_put,
                            credit_received=credit_received,
                            entry_timestamp=current_timestamp,
                            spread_width=spread_width
                        )
        
        # No valid spread found
        return None
    
    def _create_option_leg(
        self,
        option_symbol: str,
        strike_price: float,
        underlying_price: float,
        delta: float,
        option_price: float,
        timestamp: datetime,
        expiry: datetime
    ) -> OptionLeg:
        """Create an OptionLeg object from the provided data."""
        return OptionLeg(
            option_symbol=option_symbol,
            strike_price=strike_price,
            underlying_price=underlying_price,
            delta=delta,
            option_price=option_price,
            timestamp=timestamp,
            expiration_date=expiry
        )
    
    def calculate_current_spread_metrics(
        self,
        spread: SpreadLegs,
        current_data: List[Dict],
        risk_free_rate: float
    ) -> Optional[Dict]:
        """
        Calculate current spread metrics for monitoring.
        
        Args:
            spread: The current spread position
            current_data: Current market data for the timestamp
            risk_free_rate: Risk-free rate for calculations
            
        Returns:
            Dictionary with current spread metrics or None if data unavailable
        """
        current_short_price = None
        current_long_price = None
        current_underlying_price = None
        
        # Find current prices for both legs
        for tick_data in current_data:
            if tick_data['option_symbol'] == spread.short_leg.option_symbol:
                current_short_price = tick_data['midpoint']
                current_underlying_price = tick_data.get('underlying_close')
            elif tick_data['option_symbol'] == spread.long_leg.option_symbol:
                current_long_price = tick_data['midpoint']
                if current_underlying_price is None:
                    current_underlying_price = tick_data.get('underlying_close')
        
        # Return None if any prices are missing
        if not all([current_short_price, current_long_price, current_underlying_price]):
            return None
        
        # Calculate current spread price
        current_spread_price = current_short_price - current_long_price
        
        # Calculate current deltas
        current_timestamp = current_data[0]['timestamp']  # Assume all data has same timestamp
        
        current_short_delta = OptionUtils.calculate_delta(
            current_short_price, 
            spread.short_leg.strike_price, 
            spread.short_leg.expiration_date,
            current_underlying_price, 
            risk_free_rate, 
            'put', 
            current_timestamp
        )
        
        current_long_delta = OptionUtils.calculate_delta(
            current_long_price,
            spread.long_leg.strike_price,
            spread.long_leg.expiration_date,
            current_underlying_price,
            risk_free_rate,
            'put',
            current_timestamp
        )
        
        if current_short_delta is None or current_long_delta is None:
            return None
        
        current_total_delta = abs(current_short_delta) - abs(current_long_delta)
        
        return {
            'current_spread_price': current_spread_price,
            'current_short_price': current_short_price,
            'current_long_price': current_long_price,
            'current_underlying_price': current_underlying_price,
            'current_short_delta': current_short_delta,
            'current_long_delta': current_long_delta,
            'current_total_delta': current_total_delta,
            'timestamp': current_timestamp
        } 