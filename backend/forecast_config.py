"""Tunable parameters for the influence-score calculation.

Kept isolated from forecaster.py so these can be adjusted (with the user)
once real usage data is available, without touching collection logic.
Re-running forecaster.py alone recomputes pokemon_daily_forecast from the
already-collected raw data. See docs/influence_model.md for the full
derivation of this model.

Formula recap (S_p(t) = daily score for pokemon p on date t):

    R_v(t)      = sum of incremental-view bursts convolved with a
                  lognormal view->play lag kernel (LAG_MU_HOURS/LAG_SIGMA)
    R~_v(t)     = R_v(t) ** REACH_SUBLINEAR_ALPHA
    W_c         = channel subscriber weight (log-scaled)
    T_c         = channel skill-tier weight (TIER_WEIGHTS)
    F_v         = SHORTS_WEIGHT if the title is a #shorts, else 1.0
    B_p(t)      = 1 + BANDWAGON_BETA * ln(number of distinct channels
                  that used p on date t)
    S_p(t)      = B_p(t) * sum_{v contains p} R~_v(t) * W_c * T_c * F_v
"""

# Reach model: each snapshot-to-snapshot view increment is treated as a
# burst of "viewing" that converts to "playing" after a lag, modeled as a
# lognormal kernel peaking at LAG_MU_HOURS after the burst.
LAG_MU_HOURS = 24.0
LAG_SIGMA = 1.0

# Extra exponential freshness decay multiplied onto the lag kernel. The
# lognormal's right tail alone leaves a 13-day-old viral video with ~4% of
# its weight - enough for it to squat in the daily top 3 (the "stale
# Raichu" problem). exp(-dt/tau) with tau=5 days cuts a 4-day-old burst to
# ~45% and a 13-day-old one to ~7% of its lognormal weight. Grid-searched
# against pokedb daily-rank GT on 6/8-7/17: cross-sectional Spearman
# 0.232 -> 0.245 vs no freshness term (docs/influence_model.md section 5).
FRESHNESS_TAU_HOURS = 120.0

# A single burst is assumed concentrated within this many hours of when it
# was measured, capped so an old backfilled video's one-off "catch-up"
# snapshot (which reports total views measured possibly weeks after
# publish) doesn't get treated as if all those views just happened - most
# videos' views arrive within the first day or two.
MAX_INCREMENT_CENTER_HOURS = 36.0

# Reach is sublinear in views (a single viral video shouldn't count as much
# as many mid-sized videos reaching the same total audience, since viewers
# overlap) - R~_v = R_v ** REACH_SUBLINEAR_ALPHA.
REACH_SUBLINEAR_ALPHA = 0.7

# Channel subscriber weighting: weight = 1 + log10(max(subscribers, 1) / SUBSCRIBER_BASELINE),
# clipped to a minimum of 1.0 so small channels are never penalized below baseline.
SUBSCRIBER_BASELINE = 10_000

# Skill-tier weighting from channels.category - a top-tier player's build is
# perceived as "the answer" and gets imitated more than the same reach from
# a casual/light streamer.
TIER_WEIGHTS = {"top": 1.5, "high": 1.2, "mid": 1.0, "light": 0.7}
DEFAULT_TIER_WEIGHT = 1.0  # uncategorized channels

# Bandwagon effect: when multiple distinct channels use the same pokemon on
# the same date, that's perceived as "the current answer" and adoption
# accelerates faster than a simple sum of independent videos would predict.
BANDWAGON_BETA = 0.3

# Calendar window: how many days to (re)compute forecast rows for, ending
# at tomorrow (i.e. tomorrow + the previous CALENDAR_TOTAL_DAYS-1 days).
CALENDAR_TOTAL_DAYS = 30

# How many days back to look for videos whose influence might still be nonzero.
LOOKBACK_DAYS = 30

# #shorts tend to be watched more passively / imitated less than full videos,
# so their contribution is scaled down.
SHORTS_WEIGHT = 1 / 3

# Video-type factor (F_type): labels come from data/video_types.json
# (classify_video_types.py) refined by data/counter_targets.json
# (refine_counter_targets.py). Build guides and rental-code videos convert
# viewers into imitators far better than raw battle VODs. Videos without a
# label (i.e. registered after the last classification run) default to
# "battle". True counter videos contribute nothing to their *target*
# pokemon (a counter guide is not a "use" signal - this is what made
# Swampert's decline invisible) but count normally for the other pokemon
# in the video; negative contribution was tested and rejected, since
# counter videos turned out to be a lagging indicator of popularity
# (docs/influence_model.md section 5).
VIDEO_TYPE_WEIGHTS = {"build": 2.0, "rental": 3.0, "counter": 1.0, "battle": 1.0}
DEFAULT_VIDEO_TYPE = "battle"
