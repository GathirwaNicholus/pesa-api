/**
 * finance_engine.cpp
 * ==================
 * High-performance finance calculations compiled into a shared library.
 *
 * Why C++ for this?
 * -----------------
 * Python is fast enough for I/O-bound work (waiting on DB, network), but
 * number crunching over large arrays benefits from compiled code.
 * This pattern — Python for glue + C/C++ for hot loops — is used by NumPy,
 * Pandas, TensorFlow, etc. We're showcasing the same idiom at a smaller scale.
 *
 * Compile to shared library with:
 *   g++ -O2 -shared -fPIC -o libfinance.so finance_engine.cpp
 *
 * -O2         : optimise (unroll loops, inline small functions)
 * -shared     : produce a .so (shared object) rather than an executable
 * -fPIC       : Position-Independent Code — required for shared libraries
 *               because the OS loads .so files at arbitrary memory addresses
 */

#include "finance_engine.h"
#include <cstring>   // memset
#include <cmath>     // isnan, isinf

// ---------------------------------------------------------------------------
// Internal helper: validate a double array for NaN / Inf
// We do NOT want crashes when Python passes garbage data.
// ---------------------------------------------------------------------------
static bool array_is_valid(const double* arr, int len) {
    if (arr == nullptr || len <= 0) return false;
    for (int i = 0; i < len; ++i) {
        if (std::isnan(arr[i]) || std::isinf(arr[i])) return false;
    }
    return true;
}

// ---------------------------------------------------------------------------
// calc_moving_average
// ---------------------------------------------------------------------------
int calc_moving_average(
    const double* values,
    int           length,
    int           window,
    double*       out_result
) {
    // --- Guard clauses first: fail fast with a clear error code ---
    if (!array_is_valid(values, length))  return -1;
    if (out_result == nullptr)            return -1;
    if (window <= 0 || window > length)   return -1;

    int out_len = length - window + 1;
    // WHY this formula?
    // A 3-period MA over [1,2,3,4,5] produces [avg(1,2,3), avg(2,3,4), avg(3,4,5)]
    // That is 5 - 3 + 1 = 3 output values.

    // Sliding-window sum: O(n) not O(n*window).
    // We compute the first window sum once, then slide:
    //   add the new element, subtract the element that fell off the back.
    double window_sum = 0.0;
    for (int i = 0; i < window; ++i) {
        window_sum += values[i];
    }
    out_result[0] = window_sum / window;

    for (int i = 1; i < out_len; ++i) {
        window_sum += values[i + window - 1];  // add new element
        window_sum -= values[i - 1];            // drop oldest element
        out_result[i] = window_sum / window;
    }

    return out_len;
}

// ---------------------------------------------------------------------------
// calc_burn_rate_forecast
// ---------------------------------------------------------------------------
bool calc_burn_rate_forecast(
    const double* daily_expenses,
    int           lookback,
    double        budget_limit,
    double        spent_so_far,
    double*       out_daily_rate,
    double*       out_days_left
) {
    // Validate inputs
    if (!array_is_valid(daily_expenses, lookback)) return false;
    if (out_daily_rate == nullptr || out_days_left == nullptr) return false;
    if (budget_limit <= 0.0) return false;
    if (spent_so_far < 0.0 || spent_so_far > budget_limit) return false;

    // Compute average daily expense over the lookback window
    double total = 0.0;
    for (int i = 0; i < lookback; ++i) {
        total += daily_expenses[i];
    }
    double daily_rate = total / lookback;

    *out_daily_rate = daily_rate;

    // How much budget is left?
    double remaining = budget_limit - spent_so_far;

    if (daily_rate <= 0.0) {
        // No spending — budget effectively lasts forever
        // We use -1.0 as a sentinel for "infinite"
        *out_days_left = -1.0;
    } else {
        *out_days_left = remaining / daily_rate;
    }

    return true;
}
