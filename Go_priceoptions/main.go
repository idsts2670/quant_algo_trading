package go_priceoptions

import (
	"math"
)

// Global constants
var sqtwopi float64 = math.Sqrt(2 * math.Pi)
var IVPrecision float64 = 1e-6 // tolerance for the bisection method

// NormCdf computes the cumulative distribution function for a standard normal distribution.
func NormCdf(x float64) float64 {
	return 0.5 * (1 + math.Erf(x/math.Sqrt2))
}

// PriceBlackScholes calculates the Black–Scholes price of an option.
func PriceBlackScholes(callType bool, underlying float64, strike float64, timeToExpiration float64, volatility float64, riskFreeInterest float64, dividend float64) float64 {
	var sign float64
	if callType {
		if timeToExpiration <= 0 {
			return math.Max(0, underlying-strike)
		}
		sign = 1
	} else {
		if timeToExpiration <= 0 {
			return math.Max(0, strike-underlying)
		}
		sign = -1
	}

	re := math.Exp(-riskFreeInterest * timeToExpiration)
	qe := math.Exp(-dividend * timeToExpiration)
	vt := volatility * math.Sqrt(timeToExpiration)
	d1 := d1f(underlying, strike, timeToExpiration, volatility, riskFreeInterest, dividend, vt)
	d2 := d2f(d1, vt)
	d1 = sign * d1
	d2 = sign * d2
	nd1 := NormCdf(d1)
	nd2 := NormCdf(d2)

	bsprice := sign * ((underlying * qe * nd1) - (strike * re * nd2))
	return bsprice
}

// d1f computes d1 in the Black–Scholes formula.
func d1f(underlying float64, strike float64, timeToExpiration float64, volatility float64, riskFreeInterest float64, dividend float64, volatilityWithExpiration float64) float64 {
	d1 := math.Log(underlying/strike) + timeToExpiration*(riskFreeInterest-dividend+0.5*volatility*volatility)
	return d1 / volatilityWithExpiration
}

// d2f computes d2 in the Black–Scholes formula.
func d2f(d1 float64, volatilityWithExpiration float64) float64 {
	return d1 - volatilityWithExpiration
}

// d1pdff computes the probability density function for d1.
func d1pdff(underlying float64, strike float64, timeToExpiration float64, volatility float64, riskFreeInterest float64, dividend float64) float64 {
	vt := volatility * math.Sqrt(timeToExpiration)
	d1 := d1f(underlying, strike, timeToExpiration, volatility, riskFreeInterest, dividend, vt)
	d1pdf := math.Exp(-0.5 * d1 * d1)
	return d1pdf / sqtwopi
}

// BSDelta computes the option delta.
func BSDelta(callType bool, underlying float64, strike float64, timeToExpiration float64, volatility float64, riskFreeInterest float64, dividend float64) float64 {
	var zo float64
	if !callType {
		zo = -1
	} else {
		zo = 0
	}
	drq := math.Exp(-dividend * timeToExpiration)
	vt := volatility * math.Sqrt(timeToExpiration)
	d1 := d1f(underlying, strike, timeToExpiration, volatility, riskFreeInterest, dividend, vt)
	cdfd1 := NormCdf(d1)
	delta := drq * (cdfd1 + zo)
	return delta
}

// BSVega computes the option vega.
func BSVega(underlying float64, strike float64, timeToExpiration float64, volatility float64, riskFreeInterest float64, dividend float64) float64 {
	d1pdf := d1pdff(underlying, strike, timeToExpiration, volatility, riskFreeInterest, dividend)
	drq := math.Exp(-dividend * timeToExpiration)
	sqt := math.Sqrt(timeToExpiration)
	vega := d1pdf * drq * underlying * sqt * 0.01
	return vega
}

// BSGamma computes the option gamma.
func BSGamma(underlying float64, strike float64, timeToExpiration float64, volatility float64, riskFreeInterest float64, dividend float64) float64 {
	drq := math.Exp(-dividend * timeToExpiration)
	drd := underlying * volatility * math.Sqrt(timeToExpiration)
	d1pdf := d1pdff(underlying, strike, timeToExpiration, volatility, riskFreeInterest, dividend)
	gamma := (drq / drd) * d1pdf
	return gamma
}

// BSTheta computes the option theta.
func BSTheta(callType bool, underlying float64, strike float64, timeToExpiration float64, volatility float64, riskFreeInterest float64, dividend float64) float64 {
	var sign float64
	if !callType {
		sign = -1
	} else {
		sign = 1
	}

	sqt := math.Sqrt(timeToExpiration)
	drq := math.Exp(-dividend * timeToExpiration)
	dr := math.Exp(-riskFreeInterest * timeToExpiration)
	d1pdf := d1pdff(underlying, strike, timeToExpiration, volatility, riskFreeInterest, dividend)
	twosqt := 2 * sqt
	p1 := -1 * ((underlying * volatility * drq) / twosqt) * d1pdf

	vt := volatility * sqt
	d1 := d1f(underlying, strike, timeToExpiration, volatility, riskFreeInterest, dividend, vt)
	d2 := d2f(d1, vt)
	d1 = sign * d1
	d2 = sign * d2
	nd1 := NormCdf(d1)
	nd2 := NormCdf(d2)

	p2 := -sign * riskFreeInterest * strike * dr * nd2
	p3 := sign * dividend * underlying * drq * nd1
	theta := (p1 + p2 + p3) / 365
	return theta
}

// BSRho computes the option rho.
func BSRho(callType bool, underlying float64, strike float64, timeToExpiration float64, volatility float64, riskFreeInterest float64, dividend float64) float64 {
	var sign float64
	if !callType {
		sign = -1
	} else {
		sign = 1
	}

	dr := math.Exp(-riskFreeInterest * timeToExpiration)
	p1 := sign * (strike * timeToExpiration * dr) / 100

	vt := volatility * math.Sqrt(timeToExpiration)
	d1 := d1f(underlying, strike, timeToExpiration, volatility, riskFreeInterest, dividend, vt)
	d2 := sign * d2f(d1, vt)
	nd2 := NormCdf(d2)
	rho := p1 * nd2
	return rho
}

// BSImpliedVol computes the implied volatility using a bracketed solver (bisection method).
// It brackets the volatility between lowVol and highVol and then finds the root of
// f(vol) = PriceBlackScholes(vol) - lastTradedPrice.
func BSImpliedVol(callType bool, lastTradedPrice float64, underlying float64, strike float64, timeToExpiration float64, startAnchorVolatility float64, riskFreeInterest float64, dividend float64) float64 {
	// --- Intrinsic check removed to allow solving even if market price is below the typical lower bound ---

	// Set volatility bracket.
	lowVol := 1e-6
	highVol := 5.0

	// f(vol) is the difference between the theoretical price and the market price.
	f := func(vol float64) float64 {
		return PriceBlackScholes(callType, underlying, strike, timeToExpiration, vol, riskFreeInterest, dividend) - lastTradedPrice
	}

	fLow := f(lowVol)
	fHigh := f(highVol)
	if fLow*fHigh > 0 {
		// If no sign change exists in the bracket, we cannot reliably find a root.
		return math.NaN()
	}

	// Use the bisection method to find the root.
	midVol := 0.0
	for i := 0; i < 100; i++ {
		midVol = (lowVol + highVol) / 2
		fMid := f(midVol)
		if math.Abs(fMid) < IVPrecision {
			return midVol
		}
		if fLow*fMid < 0 {
			highVol = midVol
			fHigh = fMid
		} else {
			lowVol = midVol
			fLow = fMid
		}
	}

	return midVol
}
