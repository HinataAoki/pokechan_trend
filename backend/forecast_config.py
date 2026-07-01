"""Tunable parameters for the influence/decay calculation.

Kept isolated from forecaster.py so these can be adjusted (with the user)
once real usage data is available, without touching collection logic.
Re-running forecaster.py alone recomputes pokemon_daily_forecast from the
already-collected raw data.
"""

# Time constant (hours) for the decay curve:
#   decay(d) = 1 - tanh(d / TAU_HOURS)
# At d = TAU_HOURS * 2.33 (~168h / 1 week with TAU=72), decay drops below ~2%.
TAU_HOURS = 72.0

# Channel subscriber weighting: weight = 1 + log10(max(subscribers, 1) / SUBSCRIBER_BASELINE),
# clipped to a minimum of 1.0 so small channels are never penalized below baseline.
SUBSCRIBER_BASELINE = 10_000

# How many days ahead of "today" to (re)compute forecast rows for.
FORECAST_HORIZON_DAYS = 3

# How many days back to look for videos whose influence might still be nonzero.
# Should comfortably exceed MAX_TRACKING_HOURS so no contributing video is missed.
LOOKBACK_DAYS = 10
