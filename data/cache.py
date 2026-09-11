"""Caching helpers.

Every network call must go through a cache so slider drags never re-fetch. In
Streamlit we use @st.cache_data; outside Streamlit (tests / CLI) these helpers
degrade gracefully to plain calls.
"""

from __future__ import annotations

try:
    import streamlit as st

    _HAS_STREAMLIT = True
except Exception:  # pragma: no cover - import may fail in headless envs
    _HAS_STREAMLIT = False


def cache_data(ttl: int | None = 86400):
    """Decorator factory: @st.cache_data in Streamlit, passthrough elsewhere."""

    def decorator(fn):
        if _HAS_STREAMLIT:
            return st.cache_data(ttl=ttl)(fn)
        return fn

    return decorator
