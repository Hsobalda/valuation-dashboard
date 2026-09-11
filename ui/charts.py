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
                  annotation_text="reference WACC",
                  annotation_position="top left")
    fig.update_layout(**_base_layout("C. ROIC vs reference cost of capital"),
                      yaxis_tickformat=".0%")
    return fig


def sensitivity_heatmap(df) -> go.Figure:
    fig = go.Figure(data=go.Heatmap(
        z=df.values.tolist(),
        x=[f"{g:.1%}" for g in df.columns],
        y=[f"{w:.1%}" for w in df.index],
        colorscale="RdYlGn",
        colorbar=dict(title="value/share"),
        text=[[("" if v is None else f"{v:,.2f}") for v in row] for row in df.values.tolist()],
        texttemplate="%{text}",
        hovertemplate="WACC %{y} · g %{x}<br>%{z:,.2f}<extra></extra>",
    ))
    fig.update_layout(**_base_layout("Sensitivity: value per share (WACC × terminal growth)",
                                     height=360),
                      xaxis_title="terminal growth", yaxis_title="WACC")
    return fig


def football_field(ranges: dict[str, tuple[float, float]], price: float,
                   mos_price: float, currency: str = "USD") -> go.Figure:
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
    fig.add_vline(x=mos_price, line_color="green", line_dash="dash", line_width=2,
                  annotation_text=f"buy zone ≤ {mos_price:,.2f}",
                  annotation_position="bottom")
    fig.update_layout(**_base_layout("Football field (value ranges vs price)", height=320),
                      xaxis_title=currency)
    return fig
