"""
Option utility functions for calculating Greeks, implied volatility, and symbol manipulation.

This module contains pure mathematical functions with no external dependencies except for NumPy and SciPy, making them easily unit-testable.
"""

import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
from datetime import date
from typing import List


class OptionUtils:
    """Static utility methods for option calculations and symbol manipulation."""
    
    @staticmethod
    def extract_strike_price(symbol: str) -> float:
        """
        Extract strike price from option symbol.
        
        Args:
            symbol: Option symbol (e.g., 'SPY250616P00571000')
            
        Returns:
            Strike price as float (e.g., 571.0)
        """
        try:
            # Extract the last 8 digits and convert to strike price
            strike_str = symbol[-8:]
            strike_price = float(strike_str) / 1000.0
            return strike_price
        except (ValueError, IndexError):
            print(f"Warning: Could not extract strike price from symbol {symbol}")
            return 0.0
    
    @staticmethod
    def generate_put_option_symbols(
        underlying: str, 
        expiration_date: date, 
        min_strike: float, 
        max_strike: float, 
        strike_increment: float = 1.0
    ) -> List[str]:
        """
        Generate put option symbols for the given parameters.
        
        Args:
            underlying: Underlying symbol (e.g., 'SPY')
            expiration_date: Option expiration date
            min_strike: Minimum strike price
            max_strike: Maximum strike price
            strike_increment: Strike price increment (default 1.0)
        
        Returns:
            List of option symbols
        """
        option_symbols = []
        
        # Format expiration date as YYMMDD
        exp_str = expiration_date.strftime("%y%m%d")
        
        # Generate strikes in increments
        current_strike = np.ceil(min_strike / strike_increment) * strike_increment
        
        while current_strike <= max_strike:
            # Format strike price as 8-digit integer (multiply by 1000)
            strike_formatted = f"{int(current_strike * 1000):08d}"
            
            # Create option symbol: SPY + YYMMDD + P + 8-digit strike
            option_symbol = f"{underlying}{exp_str}P{strike_formatted}"
            option_symbols.append(option_symbol)
            
            current_strike += strike_increment
        
        return option_symbols
    
    @staticmethod
    def calculate_strike_price_range(high_price: float, low_price: float, buffer_pct: float = 0.05) -> tuple[float, float]:
        """
        Calculate the strike price range based on daily high/low with buffer.
        
        Args:
            high_price: Daily high price
            low_price: Daily low price
            buffer_pct: Buffer percentage (default 0.05)
            
        Returns:
            Tuple of (min_strike, max_strike)
        """
        min_strike = low_price * (1 - buffer_pct)
        max_strike = high_price * (1 + buffer_pct)
        
        return min_strike, max_strike
    
    @staticmethod
    def calculate_implied_volatility(
        option_price: float, 
        S: float, 
        K: float, 
        T: float, 
        r: float, 
        option_type: str
    ) -> float:
        """
        Calculate implied volatility using Brent's method.
        
        Args:
            option_price: Market price of the option
            S: Current stock price
            K: Strike price
            T: Time to expiration (in years)
            r: Risk-free rate
            option_type: 'call' or 'put'
            
        Returns:
            Implied volatility or None if calculation fails
        """
        # Define a reasonable range for sigma
        sigma_lower = 1e-6
        sigma_upper = 5.0
        
        # Check if the option is out-of-the-money and price is close to zero
        intrinsic_value = max(0, (S - K) if option_type == 'call' else (K - S))
        if option_price <= intrinsic_value + 1e-6:
            return 0.0
        
        # Define the function to find the root
        def option_price_diff(sigma):
            d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            if option_type == 'call':
                price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
            elif option_type == 'put':
                price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            return price - option_price
        
        try:
            return brentq(option_price_diff, sigma_lower, sigma_upper)
        except ValueError as e:
            print(f"Failed to find implied volatility: {e}")
            return None
    
    @staticmethod
    def calculate_delta(
        option_price: float,
        strike_price: float,
        expiry_timestamp,
        underlying_price: float,
        risk_free_rate: float,
        option_type: str,
        current_timestamp
    ) -> float:
        """
        Calculate option delta using Black-Scholes model.
        
        Args:
            option_price: Market price of the option
            strike_price: Strike price
            expiry_timestamp: Expiration timestamp
            underlying_price: Current underlying price
            risk_free_rate: Risk-free rate
            option_type: 'call' or 'put'
            current_timestamp: Current timestamp
            
        Returns:
            Delta value or None if calculation fails
        """
        # Calculate the time to expiry in years
        T = (expiry_timestamp - current_timestamp).total_seconds() / (365 * 24 * 60 * 60)
        # Set minimum T to avoid zero
        T = max(T, 1e-6)
        
        if T == 1e-6:
            print("Option has expired or is expiring now; setting delta based on intrinsic value.")
            if option_type == 'put':
                return -1.0 if underlying_price < strike_price else 0.0
            else:
                return 1.0 if underlying_price > strike_price else 0.0
        
        implied_volatility = OptionUtils.calculate_implied_volatility(
            option_price, underlying_price, strike_price, T, risk_free_rate, option_type
        )
        if implied_volatility is None:
            print("Implied volatility could not be determined, skipping delta calculation.")
            return None
        
        d1 = (np.log(underlying_price / strike_price) + (risk_free_rate + 0.5 * implied_volatility ** 2) * T) / (implied_volatility * np.sqrt(T))
        delta = norm.cdf(d1) if option_type == 'call' else -norm.cdf(-d1)
        return delta 