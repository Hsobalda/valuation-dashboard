"""Segment build: company revenue growth and margin from its business segments.

A single company growth rate hides mix shift. When a fast-growing, high-margin
segment (Apple's Services) becomes a bigger share of revenue, both total growth
and the company margin change over time; summing the segments captures that.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Segment:
    name: str
    revenue: float                  # latest fiscal year
    growth_y1: float
    growth_y5: float                # growth moves in a straight line from year 1 to year 5
    margin: float | None = None     # operating margin, optional


@dataclass
class SegmentBuild:
    revenue: list[list[float]]      # [segment][year 0..n]
    growth: list[float]             # blended company growth, years 1..n
    mix_start: list[float]          # revenue share, year 0
    mix_end: list[float]            # revenue share, final year
    margin_start: float | None      # revenue-weighted margin, year 0 (None unless every segment has one)
    margin_end: float | None


def _growth(seg: Segment, t: int, years: int) -> float:
    return seg.growth_y1 + (seg.growth_y5 - seg.growth_y1) * (t - 1) / (years - 1)


def build(segments: list[Segment], years: int = 5) -> SegmentBuild:
    if not segments:
        raise ValueError("At least one segment is needed")
    revenue = []
    for seg in segments:
        path = [seg.revenue]
        for t in range(1, years + 1):
            path.append(path[-1] * (1.0 + _growth(seg, t, years)))
        revenue.append(path)
    totals = [sum(r[t] for r in revenue) for t in range(years + 1)]
    if totals[0] <= 0:
        raise ValueError("Segment revenues must add up to more than zero")
    growth = [totals[t] / totals[t - 1] - 1.0 for t in range(1, years + 1)]

    def weighted_margin(t: int) -> float | None:
        if any(s.margin is None for s in segments):
            return None
        return sum(r[t] * s.margin for r, s in zip(revenue, segments)) / totals[t]

    return SegmentBuild(
        revenue=revenue,
        growth=growth,
        mix_start=[r[0] / totals[0] for r in revenue],
        mix_end=[r[-1] / totals[-1] for r in revenue],
        margin_start=weighted_margin(0),
        margin_end=weighted_margin(years),
    )
