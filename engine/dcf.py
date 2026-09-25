"""Three-stage discounted cash flow model with a moat-driven fade period.

The model follows the structure Morningstar uses for its fair value estimates:

  Stage 1 (years 1..n):   explicit FCFF projections (from projection.py).
  Stage 2 (n+1 .. n+f):   the moat fade. Growth decays linearly from the Stage-1
                          exit growth to terminal growth, and return on invested
                          capital (ROIC) decays linearly from today's level to
                          the terminal return on new capital. The length of this
                          stage (fade_years) is the moat: ~5 no moat, ~10 narrow,
                          ~20 wide.
  Stage 3 (perpetuity):   value-driver formula, NOPAT * (1 - g/RONIC) / (r - g).

Growth has to be paid for: to grow NOPAT at g with a return of ROIC on new
capital, a company reinvests g/ROIC of NOPAT, so FCF = NOPAT * (1 - g/ROIC).
With the terminal RONIC equal to the discount rate (the default: competition
has eroded excess returns), terminal value collapses to NOPAT / r and terminal
growth adds no value.

Without `nopat_last`, Stage 2-3 grow Stage-1 FCF directly, which is the same
model with an infinite return on new capital (growth needs no reinvestment).

Pure functions, no I/O.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class ValuationResult:
    pv_explicit: float          # PV of Stage-1 FCFF
    pv_fade: float              # PV of Stage-2 (fade) FCFF
    pv_terminal: float          # PV of terminal value
    enterprise_value: float     # sum of the three
    equity_value: float         # EV - net debt - minority interest
    equity_value_per_share: float
    terminal_share_of_ev: float  # pv_terminal / EV -- warn when > 0.8


def _derive_exit_growth(fcff: list[float], terminal_growth: float) -> float:
    """Exit growth = last year's growth, or terminal growth if underivable."""
    if len(fcff) >= 2 and fcff[-2] > 0:
        return fcff[-1] / fcff[-2] - 1.0
    return terminal_growth


def dcf_3stage(
    fcff_stage1: list[float],
    discount_rate: float,
    fade_years: int,
    terminal_growth: float,
    net_debt: float = 0.0,
    minority_interest: float = 0.0,
    shares_diluted: float = 1.0,
    stage1_growth: float | None = None,
    nopat_last: float | None = None,
    roic_start: float = math.inf,
    terminal_roic: float | None = None,
) -> ValuationResult:
    """Discount FCFF through the three stages and bridge to per-share equity.

    `nopat_last` is Stage-1 final-year NOPAT; with it, Stage 2 fades ROIC from
    `roic_start` to `terminal_roic` (default: the discount rate) and deducts the
    reinvestment growth requires.
    """
    if discount_rate <= 0:
        raise ValueError("Discount rate must be positive")
    if discount_rate <= terminal_growth:
        raise ValueError(
            "Discount rate must exceed terminal growth for the Gordon Growth "
            f"terminal value (got discount_rate={discount_rate:.4f}, g={terminal_growth:.4f})"
        )
    if shares_diluted <= 0:
        raise ValueError("shares_diluted must be positive")
    if roic_start <= 0:
        raise ValueError("ROIC must be positive")
    fade_years = max(0, int(fade_years))

    n = len(fcff_stage1)
    last_fcf = fcff_stage1[-1] if fcff_stage1 else 0.0

    # Stage 1 -- explicit projection, year-end discounting.
    pv_explicit = sum(f / (1.0 + discount_rate) ** (t + 1) for t, f in enumerate(fcff_stage1))

    # Stage 2 -- growth and ROIC fade linearly over fade_years.
    if stage1_growth is None:
        stage1_growth = _derive_exit_growth(fcff_stage1, terminal_growth)

    if nopat_last is None:
        nopat_last, roic_start, terminal_roic = last_fcf, math.inf, math.inf
    elif terminal_roic is None:
        terminal_roic = discount_rate

    def roic_at(i: int) -> float:
        if math.isinf(roic_start):
            return math.inf
        return roic_start + (terminal_roic - roic_start) * (i / fade_years)

    pv_fade = 0.0
    nopat = nopat_last
    for i in range(1, fade_years + 1):
        g = stage1_growth + (terminal_growth - stage1_growth) * (i / fade_years)
        nopat = nopat * (1.0 + g)
        fcf = nopat * (1.0 - g / roic_at(i))
        pv_fade += fcf / (1.0 + discount_rate) ** (n + i)

    # Stage 3 -- value-driver perpetuity on the year after the fade.
    terminal_fcf = nopat * (1.0 + terminal_growth) * (1.0 - terminal_growth / terminal_roic)
    terminal_value = terminal_fcf / (discount_rate - terminal_growth)
    pv_terminal = terminal_value / (1.0 + discount_rate) ** (n + fade_years)

    enterprise_value = pv_explicit + pv_fade + pv_terminal
    equity_value = enterprise_value - net_debt - minority_interest
    equity_value_per_share = equity_value / shares_diluted
    terminal_share = pv_terminal / enterprise_value if enterprise_value else 0.0

    return ValuationResult(
        pv_explicit=pv_explicit,
        pv_fade=pv_fade,
        pv_terminal=pv_terminal,
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        equity_value_per_share=equity_value_per_share,
        terminal_share_of_ev=terminal_share,
    )
