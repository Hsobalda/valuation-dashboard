"""Three-stage discounted cash flow model with a moat-driven fade period.

The model mirrors the Morningstar structure (see VALUATION-THINKING.md):

  Stage 1 (years 1..n):   explicit FCFF projections (from projection.py).
  Stage 2 (n+1 .. n+f):   the moat fade -- growth decays *linearly* from the
                          Stage-1 exit growth toward the long-run terminal
                          growth. The length of this stage (fade_years) is the
                          moat rating: ~5 no moat, ~10 narrow, ~20 wide.
  Stage 3 (perpetuity):   Gordon Growth on the last fade-year cash flow.

Pure functions, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValuationResult:
    pv_explicit: float          # PV of Stage-1 FCFF
    pv_fade: float              # PV of Stage-2 (fade) FCFF
    pv_terminal: float          # PV of terminal value
    enterprise_value: float     # sum of the three
    equity_value: float         # EV - net debt - minority interest + cash
    equity_value_per_share: float
    terminal_share_of_ev: float  # pv_terminal / EV -- warn when > 0.8


def _derive_exit_growth(fcff: list[float], terminal_growth: float) -> float:
    """Exit growth = last year's growth, or terminal growth if underivable."""
    if len(fcff) >= 2 and fcff[-2] > 0:
        return fcff[-1] / fcff[-2] - 1.0
    return terminal_growth


def dcf_3stage(
    fcff_stage1: list[float],
    wacc: float,
    fade_years: int,
    terminal_growth: float,
    final_ebit_margin: float = 0.0,
    net_debt: float = 0.0,
    minority_interest: float = 0.0,
    cash: float = 0.0,
    shares_diluted: float = 1.0,
    stage1_growth: float | None = None,
) -> ValuationResult:
    """Discount FCFF through the three stages and bridge to per-share equity.

    `final_ebit_margin` is accepted for spec compatibility and reserved for a
    margin-fade extension (v1 implements growth fade only).
    """
    del final_ebit_margin  # reserved

    if wacc <= 0:
        raise ValueError("WACC must be positive")
    if wacc <= terminal_growth:
        raise ValueError(
            "WACC must exceed terminal growth for the Gordon Growth terminal "
            f"value (got wacc={wacc:.4f}, g={terminal_growth:.4f})"
        )
    if shares_diluted <= 0:
        raise ValueError("shares_diluted must be positive")
    fade_years = max(0, int(fade_years))

    n = len(fcff_stage1)
    last_fcf = fcff_stage1[-1] if fcff_stage1 else 0.0

    # Stage 1 -- explicit projection, year-end discounting.
    pv_explicit = sum(f / (1.0 + wacc) ** (t + 1) for t, f in enumerate(fcff_stage1))

    # Stage 2 -- linear growth fade over fade_years.
    if stage1_growth is None:
        stage1_growth = _derive_exit_growth(fcff_stage1, terminal_growth)

    pv_fade = 0.0
    running = last_fcf
    for i in range(1, fade_years + 1):
        g = stage1_growth + (terminal_growth - stage1_growth) * (i / fade_years)
        running = running * (1.0 + g)
        pv_fade += running / (1.0 + wacc) ** (n + i)

    # Stage 3 -- Gordon Growth perpetuity on the last fade-year cash flow.
    terminal_fcf = running * (1.0 + terminal_growth)
    terminal_value = terminal_fcf / (wacc - terminal_growth)
    pv_terminal = terminal_value / (1.0 + wacc) ** (n + fade_years)

    enterprise_value = pv_explicit + pv_fade + pv_terminal
    equity_value = enterprise_value - net_debt - minority_interest + cash
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
