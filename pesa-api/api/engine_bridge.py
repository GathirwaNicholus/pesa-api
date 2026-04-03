"""
engine_bridge.py — Python ↔ C++ Bridge via ctypes
====================================================

ctypes is Python's built-in FFI (Foreign Function Interface).
It loads shared libraries (.so / .dll) and calls their functions
without needing to compile any Python extension code.

The workflow:
  1. Load libfinance.so into the Python process
  2. Declare the argument and return types of each C function
  3. Allocate C-compatible arrays for input/output
  4. Call the function
  5. Convert results back to Python types

WHY ctypes over alternatives (cffi, Cython, pybind11)?
-------------------------------------------------------
  ctypes:   stdlib, no compilation step, good for a few functions
  cffi:     pip install, cleaner API, still no compilation
  Cython:   requires .pyx files, compilation, best for heavy extension
  pybind11: C++ only, best for OOP/complex types
For our use case (2 functions, simple arrays), ctypes is perfect.
"""

import ctypes
import os
import logging
from pathlib import Path
from typing import Optional

from api.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Library loader (singleton)
# ---------------------------------------------------------------------------
_lib: Optional[ctypes.CDLL] = None


def _get_lib() -> Optional[ctypes.CDLL]:
    """
    Load libfinance.so once and cache it.
    Returns None if the library isn't available (graceful degradation —
    the API still works, analytics just skips the C++ results).
    """
    global _lib
    if _lib is not None:
        return _lib

    lib_path = Path(settings.lib_path).resolve()

    if not lib_path.exists():
        logger.warning(
            "libfinance.so not found at %s. "
            "Run `make` in the cpp/ directory to build it. "
            "Analytics will return None for C++ fields.",
            lib_path,
        )
        return None

    try:
        _lib = ctypes.CDLL(str(lib_path))
        _configure_signatures(_lib)
        logger.info("Loaded C++ finance engine from %s", lib_path)
        return _lib
    except OSError as e:
        logger.error("Failed to load libfinance.so: %s", e)
        return None


def _configure_signatures(lib: ctypes.CDLL) -> None:
    """
    Tell ctypes the exact argument and return types for each C function.

    WHY is this necessary?
    ctypes defaults to assuming all arguments are C ints and all return
    values are C ints. If you pass a double* without declaring it, ctypes
    will silently truncate or corrupt the value. Explicit signatures prevent
    this class of subtle bugs.
    """
    # --- calc_moving_average ---
    lib.calc_moving_average.restype  = ctypes.c_int
    lib.calc_moving_average.argtypes = [
        ctypes.POINTER(ctypes.c_double),   # const double* values
        ctypes.c_int,                       # int length
        ctypes.c_int,                       # int window
        ctypes.POINTER(ctypes.c_double),   # double* out_result
    ]

    # --- calc_burn_rate_forecast ---
    lib.calc_burn_rate_forecast.restype  = ctypes.c_bool
    lib.calc_burn_rate_forecast.argtypes = [
        ctypes.POINTER(ctypes.c_double),   # const double* daily_expenses
        ctypes.c_int,                       # int lookback
        ctypes.c_double,                    # double budget_limit
        ctypes.c_double,                    # double spent_so_far
        ctypes.POINTER(ctypes.c_double),   # double* out_daily_rate
        ctypes.POINTER(ctypes.c_double),   # double* out_days_left
    ]


# ---------------------------------------------------------------------------
# Public Python functions
# ---------------------------------------------------------------------------

def moving_average(values: list[float], window: int) -> Optional[list[float]]:
    """
    Compute a simple moving average using the C++ engine.

    Args:
        values: list of monthly expense totals (oldest → newest)
        window: number of periods in the moving average

    Returns:
        List of moving average values, or None if library unavailable / error.
    """
    lib = _get_lib()
    if lib is None:
        return None

    n = len(values)
    if n == 0 or window <= 0 or window > n:
        return None

    # Convert Python list → C double array
    c_values = (ctypes.c_double * n)(*values)
    # (ctypes.c_double * n) creates a C array type of n doubles.
    # (*values) unpacks the Python list into the array.

    out_len = n - window + 1
    c_out = (ctypes.c_double * out_len)()
    # () with no args = zero-initialised output array

    result = lib.calc_moving_average(c_values, n, window, c_out)
    if result < 0:
        logger.error("calc_moving_average returned error code %d", result)
        return None

    # Convert C array back to Python list
    return list(c_out[:result])


def burn_rate_forecast(
    daily_expenses: list[float],
    budget_limit: float,
    spent_so_far: float,
) -> Optional[dict]:
    """
    Compute burn rate forecast using the C++ engine.

    Args:
        daily_expenses: recent daily expense amounts (chronological order)
        budget_limit:   total budget for the period
        spent_so_far:   amount already spent

    Returns:
        dict with keys: daily_rate, days_left
        or None if library unavailable / calculation failed.
    """
    lib = _get_lib()
    if lib is None:
        return None

    lookback = len(daily_expenses)
    if lookback == 0:
        return None

    c_expenses = (ctypes.c_double * lookback)(*daily_expenses)
    c_daily_rate = ctypes.c_double(0.0)
    c_days_left  = ctypes.c_double(0.0)

    success = lib.calc_burn_rate_forecast(
        c_expenses,
        lookback,
        ctypes.c_double(budget_limit),
        ctypes.c_double(spent_so_far),
        ctypes.byref(c_daily_rate),
        ctypes.byref(c_days_left),
        # ctypes.byref() passes a pointer to the variable.
        # The C function writes its output through this pointer.
        # This is the ctypes equivalent of passing &variable in C.
    )

    if not success:
        logger.error("calc_burn_rate_forecast returned false")
        return None

    return {
        "daily_rate": c_daily_rate.value,
        "days_left":  c_days_left.value,
    }
