package go_priceoptions

import (
	"encoding/json"
	"math"
	"os"
	"strconv"
	"strings"
	"testing"
	"time"
)

// TestIVCalculation reads option snapshots from a JSON file, extracts parameters,
// calculates the implied volatility, and then compares it with the expected value.
func TestIVCalculation(t *testing.T) {
	// Open the JSON file with option data.
	file, err := os.Open("AAPL_20250214.json")
	if err != nil {
		t.Fatalf("failed to open file: %v", err)
	}
	defer file.Close()

	var data map[string]interface{}
	if err := json.NewDecoder(file).Decode(&data); err != nil {
		t.Fatalf("failed to decode JSON: %v", err)
	}

	snapshots, ok := data["snapshots"].(map[string]interface{})
	if !ok {
		t.Fatalf("snapshots not in expected format")
	}

	for key, s := range snapshots {
		snapshot, ok := s.(map[string]interface{})
		if !ok {
			continue
		}

		// Skip options without complete data.
		if snapshot["greeks"] == nil || snapshot["impliedVolatility"] == nil {
			continue
		}

		// Extract parameters.
		// (You can use the greeks if needed; here we're focusing on extracting strike.)
		_ = snapshot["greeks"].(map[string]interface{})
		underlying := 228.00 // Replace with actual underlying price if available.
		strike := parseStrikeFromKey(key)
		expiry, err := parseExpiryFromKey(key)
		if err != nil {
			t.Fatalf("failed to parse expiry date from key: %v", err)
		}
		daysLeft := int(math.Ceil(expiry.Sub(time.Now()).Hours() / 24))
		t.Logf("Key: %s\nUnderlying: %.2f\nStrike: %.2f\nExpiration Date: %s\nDays Left: %d",
			key, underlying, strike, expiry.Format("2006-01-02"), daysLeft)

		dailyBar, ok := snapshot["dailyBar"].(map[string]interface{})
		if !ok {
			continue
		}
		lastPrice, ok := dailyBar["c"].(float64)
		if !ok {
			continue
		}
		tte := float64(daysLeft) / 365.0 // Time to expiration in years
		
		// Compare the calculated IV with the expected IV from the snapshot.
		expectedIV, ok := snapshot["impliedVolatility"].(float64)
		if !ok {
			continue
		}

		// Print the extracted parameters.
		t.Logf("Key: %s\nUnderlying: %.2f\nStrike: %.2f\nLast Price: %.2f\nTime to Expiration: %.4f years",
			key, underlying, strike, lastPrice, tte)

		// Run IV calculation.
		iv := BSImpliedVol(
			false,    // false indicates a put option (set to true for call options)
			lastPrice,
			underlying,
			strike,
			tte,
			0.23,  // initial guess for IV
			0.0432623312, // risk-free rate
			0.0, // dividend yield
		)

		// Print calculated and expected IV.
		t.Logf("For key %s:\nCalculated IV: %.4f\nExpected IV: %.4f", key, iv, expectedIV)

		if math.Abs(iv-expectedIV) > 0.01 {
			t.Errorf("IV mismatch for %s: Got %.4f, Expected %.4f", key, iv, expectedIV)
		}
	}
}

// // parseStrikeFromKey extracts the strike price from an OCC-style option key.
// // It looks for the last occurrence of "P" or "C" and parses the following 8 digits.
// // For example, given the key "AAPL250214P00247500", it extracts "00247500",
// // converts it to an integer (247500), and then divides by 1000 to get 247.50.
// func parseStrikeFromKey(key string) float64 {
// 	// Find the index of the option type letter ("P" or "C").
// 	idx := strings.LastIndexAny(key, "PC")
// 	if idx == -1 {
// 		// Option type letter not found; return 0.0 or handle the error as needed.
// 		return 0.0
// 	}

// 	// The strike portion should follow the option type letter.
// 	strikeStr := key[idx+1:]
// 	if len(strikeStr) != 8 {
// 		// Unexpected format; return 0.0 or handle the error as needed.
// 		return 0.0
// 	}

// 	// Convert the strike string to an integer.
// 	strikeInt, err := strconv.Atoi(strikeStr)
// 	if err != nil {
// 		// Parsing error; return 0.0 or handle the error.
// 		return 0.0
// 	}

// 	// Divide by 1000 to place the decimal correctly.
// 	return float64(strikeInt) / 1000.0
// }

// parseExpiryFromKey extracts the expiration date from an OCC-style option key.
// For example, given "AAPL250214P00247500", it extracts "250214" and parses it as "2025-02-14".
func parseExpiryFromKey(key string) (time.Time, error) {
	if len(key) < 15 {
		return time.Time{}, strconv.ErrSyntax // Invalid key length
    }

	datePart := key[4:10] // Extract "250214"
	layout := "060102"   // Go's magic date layout for YYMMDD
	return time.Parse(layout, datePart)
}

// parseStrikeFromKey extracts the strike price from an OCC-style option key.
// For example, given the key "AAPL250214P00247500", it extracts "00247500",
// converts it to an integer (247500), and then divides by 1000 to get 247.50.
func parseStrikeFromKey(key string) float64 {
	idx := strings.LastIndexAny(key, "PC")
	if idx == -1 || len(key) < idx+9 { // Ensure valid index and length
        return 0.0
    }

	strikeStr := key[idx+1 : idx+9] // Extract the strike portion
	strikeInt, err := strconv.Atoi(strikeStr)
	if err != nil {
        return 0.0
    }

	return float64(strikeInt) / 1000.0
}