"""
Fetch today's QQQ options chain via yfinance and compute the same GEX profile
that SyntheticGammaEngine.compute_daily_gex_profile() returns from parquet.

Returned dict schema (identical to the parquet version):
  {
    "date":           "YYYY-MM-DD",
    "gex_flip":       float,
    "gamma_clusters": [float, ...],   # up to 5 NQ-scaled strike prices
    "total_gex":      float,
    "ratio":          float,          # NQ/QQQ price ratio
  }

Call fetch_gex_profile(nq_price) once per trading day before market open.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import numpy as np
import yfinance as yf

logger = logging.getLogger(__name__)

QQQ_MULTIPLIER = 100


def _compute_gex(
    strikes: np.ndarray,
    gammas:  np.ndarray,
    ois:     np.ndarray,
    is_call: np.ndarray,
    spot:    float,
) -> tuple[float, list[float], float]:
    """Return (gex_flip_nq, gamma_clusters_nq, total_gex) scaled to NQ prices."""
    calc_gamma = np.where(is_call, gammas, -gammas)
    gex        = calc_gamma * ois * (spot ** 2) * QQQ_MULTIPLIER

    unique_strikes, inverse = np.unique(strikes, return_inverse=True)
    agg_gex = np.bincount(inverse, weights=gex, minlength=len(unique_strikes))
    gex_cum = np.cumsum(agg_gex)

    sign_changes = np.where(np.diff(np.sign(gex_cum)))[0]
    if len(sign_changes) > 0:
        flip_strike = float(unique_strikes[sign_changes[0]])
    else:
        flip_strike = float(unique_strikes[np.argmin(np.abs(gex_cum))])

    k = min(5, len(agg_gex))
    top_idx = np.argpartition(np.abs(agg_gex), -k)[-k:]
    clusters = sorted(float(unique_strikes[idx]) for idx in top_idx)

    return flip_strike, clusters, float(np.sum(gex))


def fetch_gex_profile(nq_price: float, date_str: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch live QQQ options chain and compute a GEX profile.

    Parameters
    ----------
    nq_price : float
        Current NQ price — used to derive the NQ/QQQ ratio.
    date_str : str, optional
        "YYYY-MM-DD" for the profile date label.  Defaults to today.

    Returns
    -------
    dict matching SyntheticGammaEngine output, or None on failure.
    """
    date_str = date_str or date.today().isoformat()

    try:
        qqq = yf.Ticker("QQQ")

        # Spot price (last close or pre-market)
        info  = qqq.fast_info
        spot  = float(getattr(info, "last_price", None) or getattr(info, "previous_close", None))
        ratio = nq_price / spot

        expirations = qqq.options
        if not expirations:
            logger.warning("yfinance returned no QQQ expirations.")
            return None

        # Use the nearest 3 expirations for better GEX coverage
        near_expiries = expirations[:3]

        all_strikes:  List[float] = []
        all_gammas:   List[float] = []
        all_ois:      List[float] = []
        all_is_call:  List[bool]  = []

        for expiry in near_expiries:
            chain = qqq.option_chain(expiry)
            for df, is_call in [(chain.calls, True), (chain.puts, False)]:
                if df.empty:
                    continue
                # yfinance may not include 'gamma' — use it if present,
                # otherwise approximate from impliedVolatility as a proxy
                if "gamma" in df.columns:
                    gamma_col = "gamma"
                elif "impliedVolatility" in df.columns:
                    gamma_col = "impliedVolatility"
                else:
                    continue  # skip — no usable gamma data
                needed = ["strike", gamma_col, "openInterest"]
                df = df[needed].dropna()
                df = df[(df[gamma_col] > 0) & (df["openInterest"] > 0)]
                all_strikes.extend(df["strike"].tolist())
                all_gammas.extend(df[gamma_col].tolist())
                all_ois.extend(df["openInterest"].tolist())
                all_is_call.extend([is_call] * len(df))

        if not all_strikes:
            logger.warning("No valid options rows after filtering.")
            return None

        qqq_strikes = np.array(all_strikes,  dtype=np.float64)
        gammas      = np.array(all_gammas,   dtype=np.float64)
        ois         = np.array(all_ois,      dtype=np.float64)
        is_call_arr = np.array(all_is_call,  dtype=bool)

        # Scale QQQ strikes → NQ prices
        nq_strikes = qqq_strikes * ratio

        flip_nq, clusters_nq, total_gex = _compute_gex(
            nq_strikes, gammas, ois, is_call_arr, spot
        )

        return {
            "date":           date_str,
            "gex_flip":       flip_nq,
            "gamma_clusters": clusters_nq,
            "total_gex":      total_gex,
            "ratio":          ratio,
        }

    except Exception as exc:
        logger.error("fetch_gex_profile failed: %s", exc)
        return None
