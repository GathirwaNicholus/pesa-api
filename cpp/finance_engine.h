#pragma once
// pragma once is a non-standard but universally supported header guard.
// It prevents this header from being included more than once per compilation unit.

#include <stddef.h>   // for size_t
#include <stdbool.h>  // for bool in C; harmless in C++

#ifdef __cplusplus
extern "C" {
#endif
// WHY extern "C"?
// C++ mangles function names (e.g. calc_moving_avg → _Z16calc_moving_avgPdi)
// so the linker can support function overloading.
// Python's ctypes loads a shared library and looks for EXACT symbol names.
// extern "C" tells the compiler: export these with plain C names — no mangling.
// Without this, ctypes would silently fail to find the functions.

/**
 * calc_moving_average
 * -------------------
 * Computes a simple N-period moving average over an array of doubles.
 *
 * @param values      Pointer to the input array of transaction amounts
 * @param length      Number of elements in `values`
 * @param window      The period N (e.g. 3 for a 3-month moving average)
 * @param out_result  Pointer to output array; caller must allocate (length - window + 1) doubles
 * @return            Number of values written to out_result, or -1 on error
 *
 * WHY C arrays instead of std::vector?
 * ctypes communicates via raw memory pointers. std::vector lives in C++ ABI
 * space and cannot be safely passed across the shared-library boundary.
 * Plain C arrays / pointers are always safe across the boundary.
 */
int calc_moving_average(
    const double* values,
    int           length,
    int           window,
    double*       out_result
);

/**
 * calc_burn_rate_forecast
 * -----------------------
 * Estimates how many days until a budget is exhausted, given recent spending.
 *
 * Algorithm:
 *   daily_rate  = sum(expenses[0..lookback-1]) / lookback
 *   days_left   = remaining_budget / daily_rate
 *   forecast    = current_date + days_left
 *
 * @param daily_expenses  Array of daily expense totals (most recent last)
 * @param lookback        How many days to average over
 * @param budget_limit    Total budget amount for the period
 * @param spent_so_far    Amount already spent in the period
 * @param out_daily_rate  Output: computed average daily spend rate
 * @param out_days_left   Output: projected days until budget exhausted
 * @return                true on success, false if inputs are invalid
 */
bool calc_burn_rate_forecast(
    const double* daily_expenses,
    int           lookback,
    double        budget_limit,
    double        spent_so_far,
    double*       out_daily_rate,
    double*       out_days_left
);

#ifdef __cplusplus
}  // end extern "C"
#endif
