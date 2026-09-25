"""Plotly chart builders. Presentation only -- no valuation logic here."""

from __future__ import annotations

import plotly.graph_objects as go


def _base_layout(title: str, height: int = 320):
    return dict(
        title=title,
        height=height,
        margin=dict(l=40, r=20, t=40, b=40),
        template="plotly_white",
    )


def history_indexed_chart(brief_history: dict) -> go.Figure:
    """Revenue / EBITDA / net income indexed to the first year (=100)."""
    fig = go.Figure()
    for key, label in [("revenue_idx", "Revenue"), ("ebitda_idx", "EBITDA"),
                       ("ni_idx", "Net income")]:
        s = brief_history[key]
        fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines+markers",
                                 name=label))
    fig.update_layout(**_base_layout("B. Operating history (indexed, first year = 100)"),
                      yaxis_title="Index")
    return fig


def margin_chart(brief_history: dict) -> go.Figure:
    fig = go.Figure()
    for key, label in [("gross_margin", "Gross"), ("operating_margin", "Operating"),
                       ("net_margin", "Net")]:
        s = brief_history[key]
        fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines+markers",
                                 name=label))
    fig.update_layout(**_base_layout("Margin trajectory"), yaxis_tickformat=".0%")
    return fig


def roic_chart(brief_quality: dict) -> go.Figure:
    roic = brief_quality["roic"]
    wacc = brief_quality["reference_wacc"]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=roic.index, y=roic.values, name="ROIC"))
    fig.add_hline(y=wacc, line_dash="dash", line_color="red",
                  annotation_text="cost of capital (WACC)",
                  annotation_position="top left")
    fig.update_layout(**_base_layout("C. ROIC vs reference cost of capital"),
                      yaxis_tickformat=".0%")
    return fig


def sensitivity_heatmap(df) -> go.Figure:
    def _is_invalid(v) -> bool:
        return v is None or v != v  # None or NaN (terminal growth >= discount rate)

    text = [[("n/a" if _is_invalid(v) else f"{v:,.2f}") for v in row] for row in df.values.tolist()]
    fig = go.Figure(data=go.Heatmap(
        z=df.values.tolist(),
        x=[f"{g:.1%}" for g in df.columns],
        y=[f"{w:.1%}" for w in df.index],
        colorscale="RdYlGn",
        colorbar=dict(title="value/share"),
        text=text,
        texttemplate="%{text}",
        hovertemplate="rate %{y} · g %{x}<br>%{text}<extra></extra>",
    ))
    fig.update_layout(**_base_layout("Sensitivity: value per share (discount rate × terminal growth)",
                                     height=360),
                      xaxis_title="terminal growth", yaxis_title="discount rate")
    fig.add_annotation(
        text="n/a = terminal growth ≥ discount rate (mathematically invalid, perpetuity diverges)",
        xref="paper", yref="paper", x=0, y=-0.22, showarrow=False,
        font=dict(size=11, color="gray"), align="left",
    )
    return fig


def capital_allocation_chart(brief_cap: dict, currency: str) -> go.Figure:
    """Cash generated (FCF after stock pay + stock pay) beside cash spent on
    dividends + buybacks, per fiscal year."""
    fcf, sbc = brief_cap["fcf"], brief_cap["sbc"]
    div, buy = brief_cap["dividends"], brief_cap["buybacks"]
    scale, unit = (1e9, "bn") if (fcf + sbc).abs().max() >= 1e9 else (1e6, "m")
    years = [str(y) for y in fcf.index]
    hover = "%{x} · %{fullData.name}: %{y:,.1f}" + unit + "<extra></extra>"
    fig = go.Figure()
    fig.add_trace(go.Bar(x=years, y=fcf / scale, name="Free cash flow after stock pay",
                         offsetgroup="fcf", marker_color="#2a78d6", hovertemplate=hover))
    if sbc.abs().sum() > 0:
        fig.add_trace(go.Bar(x=years, y=sbc / scale, name="Stock-based pay", base=fcf / scale,
                             offsetgroup="fcf", marker_color="#eda100", hovertemplate=hover))
    fig.add_trace(go.Bar(x=years, y=div / scale, name="Dividends",
                         offsetgroup="returned", marker_color="#eb6834", hovertemplate=hover))
    fig.add_trace(go.Bar(x=years, y=buy / scale, name="Buybacks", base=div / scale,
                         offsetgroup="returned", marker_color="#1baf7a", hovertemplate=hover))
    fig.update_traces(marker_line_color="white", marker_line_width=2)
    fig.update_layout(**_base_layout("D. Free cash flow vs cash returned to shareholders"),
                      barmode="group", bargap=0.3, yaxis_title=f"{currency} {unit}",
                      legend=dict(orientation="h", y=-0.2))
    return fig


def football_field(ranges: dict[str, tuple[float, float]], price: float,
                   mos_price: float | None, currency: str = "USD") -> go.Figure:
    """Horizontal valuation ranges vs current price and buy-zone line."""
    labels = list(ranges.keys())
    fig = go.Figure()
    for i, label in enumerate(reversed(labels)):
        low, high = ranges[label]
        fig.add_trace(go.Bar(
            x=[high - low], y=[label], orientation="h",
            base=low, width=0.4, marker_color="#4472C4",
            name=label, showlegend=False,
            text=[f"{low:,.2f} – {high:,.2f}"], textposition="outside",
        ))
    fig.add_vline(x=price, line_color="black", line_width=2,
                  annotation_text=f"price {price:,.2f}", annotation_position="top")
    if mos_price is not None:
        fig.add_vline(x=mos_price, line_color="green", line_dash="dash", line_width=2,
                      annotation_text=f"buy zone ≤ {mos_price:,.2f}",
                      annotation_position="bottom")
    fig.update_layout(**_base_layout("Football field (value ranges vs price)", height=320),
                      xaxis_title=currency)
    return fig
