"""Stage-1 free-cash-flow projection. Pure, deterministic, no I/O."""


def project_fcff(
    base_revenue: float,
    revenue_growth: float,
    ebit_margin: float,
    tax_rate: float,
    da_pct_revenue: float,
    capex_pct_revenue: float,
    nwc_pct_revenue: float,
    years: int = 5,
) -> list[float]:
    """Project unlevered free cash flow to the firm (FCFF) for `years` years.

    FCFF = EBIT * (1 - tax) + D&A - CapEx - change in net working capital.

    Each ratio (margin, D&A, capex, NWC) is applied as a % of revenue, which is
    the standard simplified analyst projection (drivers-as-%-of-revenue). The
    change in NWC is driven by the *change* in revenue, so in a flat year it is
    zero.

    Returns a list of FCFF, one per year (year 1 .. year `years`).
    """
    fcffs = []
    prev_revenue = base_revenue
    revenue = base_revenue
    for _ in range(years):
        revenue = revenue * (1.0 + revenue_growth)
        ebit = revenue * ebit_margin
        nopat = ebit * (1.0 - tax_rate)
        da = revenue * da_pct_revenue
        capex = revenue * capex_pct_revenue
        delta_nwc = (revenue - prev_revenue) * nwc_pct_revenue
        fcff = nopat + da - capex - delta_nwc
        fcffs.append(fcff)
        prev_revenue = revenue
    return fcffs
