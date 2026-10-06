"""Quantitative DAUB suitability scoring for EPB, Slurry Shield and Hybrid Shield.

Primary source:
    DAUB, Recommendations for the Selection of Tunnel Boring Machines,
    January 2022, revised August 2025, Appendix 3.4 (SLS),
    Appendix 3.5 (EPB), Appendix 3.7 (HYS).

The DAUB application symbols are converted to numerical scores:
    +  main field of application     -> 1.0
    o  extended application         -> 0.5
    -  application limited          -> 0.0

Suitability (%) is the arithmetic mean of the scores for all DAUB parameters
that were actually supplied / derivable for the case, multiplied by 100.
Missing parameters are not silently scored as zero.
"""

from __future__ import annotations

from math import log10
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

CLASSES = ("epb", "slurry", "hybrid")
DISPLAY_NAMES = {
    "epb": "EPB",
    "slurry": "Slurry Shield",
    "hybrid": "Mixed/Hybrid Shield",
}
RATING_SCORE = {"main": 1.0, "extended": 0.5, "limited": 0.0}
RATING_SYMBOL = {"main": "+", "extended": "o", "limited": "–"}
RATING_LABEL = {
    "main": "Main application",
    "extended": "Extended application",
    "limited": "Limited application",
}


def _num(value: Any) -> Optional[float]:
    try:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        val = float(value)
        if np.isnan(val):
            return None
        return val
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    s = str(value).strip()
    return s if s else None


def _single_value(df: pd.DataFrame, column: str) -> Any:
    """Read either the new clean one-row format or the legacy flag/value format."""
    if column not in df.columns or len(df.index) == 0:
        return None
    first = df[column].iloc[0]
    second = df[column].iloc[1] if len(df.index) > 1 else None

    # Legacy format: first data row is 0/1 provided flag and second row is value.
    first_num = _num(first)
    if first_num in (0.0, 1.0) and second is not None and not pd.isna(second):
        if first_num == 0.0:
            return None
        return second

    if first is None or pd.isna(first):
        # fall back to first nonblank cell in the column
        for value in df[column].tolist()[1:]:
            if value is not None and not pd.isna(value):
                return value
        return None
    return first


def _legacy_percentage_value(df: pd.DataFrame, column: str) -> Optional[float]:
    """Read percentage values while remaining compatible with old fraction-formatted files."""
    if column not in df.columns or len(df.index) == 0:
        return None
    first = df[column].iloc[0]
    second = df[column].iloc[1] if len(df.index) > 1 else None
    first_num = _num(first)
    if first_num in (0.0, 1.0) and second is not None and not pd.isna(second):
        if first_num == 0.0:
            return None
        val = _num(second)
        return None if val is None else val * 100.0
    val = _num(first)
    return val


def _percentage_finer_at(df: pd.DataFrame, target_mm: float) -> Optional[float]:
    """Return percent passing at target sieve size using log-size interpolation.

    DAUB uses fines <0.06 mm. Existing project spreadsheets may use 0.075 and
    0.01 mm rather than exactly 0.06 mm, so interpolation is used when needed.
    """
    if "Sieve Size (mm)" not in df.columns or "Percentage Finer (%)" not in df.columns:
        return None
    sizes = pd.to_numeric(df["Sieve Size (mm)"], errors="coerce").to_numpy(dtype=float)
    finer = pd.to_numeric(df["Percentage Finer (%)"], errors="coerce").to_numpy(dtype=float)
    mask = np.isfinite(sizes) & np.isfinite(finer) & (sizes > 0)
    sizes, finer = sizes[mask], finer[mask]
    if len(sizes) < 2:
        return None

    # Project spreadsheets store percentage finer either as fractions (0..1)
    # or explicit percentages (0..100).
    if np.nanmax(np.abs(finer)) <= 1.000001:
        finer = finer * 100.0

    exact = np.where(np.isclose(sizes, target_mm, rtol=0, atol=1e-10))[0]
    if len(exact):
        return float(finer[exact[0]])

    order = np.argsort(sizes)
    sizes, finer = sizes[order], finer[order]
    if target_mm < sizes[0] or target_mm > sizes[-1]:
        return None

    idx_hi = int(np.searchsorted(sizes, target_mm, side="right"))
    idx_lo = idx_hi - 1
    x0, x1 = log10(sizes[idx_lo]), log10(sizes[idx_hi])
    y0, y1 = finer[idx_lo], finer[idx_hi]
    xt = log10(target_mm)
    if x1 == x0:
        return float(y0)
    return float(y0 + (y1 - y0) * (xt - x0) / (x1 - x0))


def _range_index(value: float, edges: List[Tuple[Optional[float], Optional[float]]]) -> Optional[int]:
    for i, (low, high) in enumerate(edges):
        if low is None and high is not None and value < high:
            return i
        if high is None and low is not None and value >= low:
            return i
        if low is not None and high is not None and low <= value < high:
            return i
    return None


def _rating_row(name: str, section: str, value: Any, value_text: str,
                ratings: Dict[str, str], source_range: str, note: str = "") -> Dict[str, Any]:
    return {
        "parameter": name,
        "section": section,
        "value": value,
        "value_text": value_text,
        "ratings": {
            cls: {
                "rating": ratings[cls],
                "symbol": RATING_SYMBOL[ratings[cls]],
                "label": RATING_LABEL[ratings[cls]],
                "score": RATING_SCORE[ratings[cls]],
            }
            for cls in CLASSES
        },
        "source_range": source_range,
        "note": note,
    }


def _soil_rows(df: pd.DataFrame, required_face_pressure_kPa: Optional[float],
               include_confinement: bool = True) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    fines = _percentage_finer_at(df, 0.06)
    if fines is not None:
        idx = _range_index(fines, [(None, 5), (5, 15), (15, 40), (40, None)])
        maps = {
            "epb": ["limited", "extended", "extended", "main"],
            "slurry": ["main", "main", "main", "extended"],
            "hybrid": ["limited", "extended", "extended", "main"],
        }
        ratings = {cls: maps[cls][idx] for cls in CLASSES}
        rows.append(_rating_row(
            "Fines content < 0.06 mm", "Soil", fines, f"{fines:.2f}%", ratings,
            "DAUB 2025 Appendix 3.4/3.5/3.7",
            "Calculated from the particle-size distribution; log-size interpolation is used if 0.06 mm is not an entered sieve."
        ))

    permeability = _num(_single_value(df, "Permeability (m/s)"))
    if permeability is not None and permeability > 0:
        # DAUB order: >1e-2, 1e-2..1e-4, 1e-4..1e-6, <1e-6
        if permeability > 1e-2:
            idx = 0
        elif permeability >= 1e-4:
            idx = 1
        elif permeability >= 1e-6:
            idx = 2
        else:
            idx = 3
        maps = {
            "epb": ["limited", "limited", "extended", "main"],
            "slurry": ["limited", "extended", "main", "extended"],
            "hybrid": ["limited", "limited", "extended", "main"],
        }
        ratings = {cls: maps[cls][idx] for cls in CLASSES}
        labels = ["> 10⁻²", "10⁻² to 10⁻⁴", "10⁻⁴ to 10⁻⁶", "< 10⁻⁶"]
        rows.append(_rating_row("Permeability k", "Soil", permeability,
                                f"{permeability:.3g} m/s ({labels[idx]})", ratings,
                                "DAUB 2025 Appendix 3.4/3.5/3.7"))

    consistency = _num(_single_value(df, "Consistency Index"))
    if consistency is not None:
        idx = _range_index(consistency, [(0, 0.5), (0.5, 0.75), (0.75, 1.0), (1.0, 1.25), (1.25, 1.5000001)])
        if idx is not None:
            maps = {
                "epb": ["extended", "main", "main", "extended", "extended"],
                "slurry": ["limited", "extended", "extended", "extended", "extended"],
                "hybrid": ["extended", "main", "main", "extended", "extended"],
            }
            labels = ["very soft", "soft", "stiff", "very stiff", "hard"]
            ratings = {cls: maps[cls][idx] for cls in CLASSES}
            rows.append(_rating_row("Consistency index Ic", "Soil", consistency,
                                    f"{consistency:.3g} ({labels[idx]})", ratings,
                                    "DAUB 2025 Appendix 3.4/3.5/3.7"))

    rel_category = _text(_single_value(df, "Relative Density Category"))
    rel_numeric = _legacy_percentage_value(df, "Relative Density (%)")
    rel_note = ""
    if rel_category:
        norm = rel_category.lower().replace("_", " ").strip()
        if "medium" in norm:
            rel_category = "medium dense"
        elif "loose" in norm:
            rel_category = "loose"
        elif "dense" in norm:
            rel_category = "dense"
        else:
            rel_category = None
    elif rel_numeric is not None:
        # Auxiliary conversion retained for compatibility with the project's
        # pre-existing numeric relative-density input. The DAUB table itself is categorical.
        if rel_numeric < 35:
            rel_category = "loose"
        elif rel_numeric < 65:
            rel_category = "medium dense"
        else:
            rel_category = "dense"
        rel_note = "Numeric relative density was converted to the DAUB loose / medium-dense / dense category for software compatibility."
    if rel_category:
        idx = {"dense": 0, "medium dense": 1, "loose": 2}[rel_category]
        maps = {
            "epb": ["main", "main", "main"],
            "slurry": ["main", "main", "extended"],
            "hybrid": ["main", "main", "main"],
        }
        ratings = {cls: maps[cls][idx] for cls in CLASSES}
        value_text = rel_category if rel_numeric is None else f"{rel_numeric:.1f}% → {rel_category}"
        rows.append(_rating_row("Relative density", "Soil", rel_numeric or rel_category,
                                value_text, ratings, "DAUB 2025 Appendix 3.4/3.5/3.7", rel_note))

    if include_confinement:
        conf_kpa = _num(_single_value(df, "Confinement Pressure (kPa)"))
        conf_source = "Entered confinement pressure"
        # Use calculated face-support pressure as a SOIL confinement criterion only
        # when at least one other soil criterion is present.  If the case contains
        # only rock-specific DAUB inputs, the same calculated pressure is evaluated
        # later against DAUB's rock confinement table instead.
        if conf_kpa is None and required_face_pressure_kPa is not None and rows:
            conf_kpa = required_face_pressure_kPa
            conf_source = "Calculated required face-support pressure"
        if conf_kpa is not None and conf_kpa >= 0:
            conf_bar = conf_kpa / 100.0
            if conf_bar < 1:
                idx = 0
            elif conf_bar < 4:
                idx = 1
            elif conf_bar < 7:
                idx = 2
            elif conf_bar <= 15:
                idx = 3
            else:
                idx = None
            if idx is not None:
                maps = {
                    "epb": ["main", "main", "extended", "limited"],
                    "slurry": ["extended", "main", "main", "main"],
                    "hybrid": ["main", "main", "extended", "limited"],
                }
                ratings = {cls: maps[cls][idx] for cls in CLASSES}
                rows.append(_rating_row("Confinement / face-support pressure", "Soil", conf_bar,
                                        f"{conf_bar:.3g} bar ({conf_source})", ratings,
                                        "DAUB 2025 Appendix 3.4/3.5/3.7",
                                        "For continuous software input, values from 0 to <1 bar are assigned to DAUB's 0-bar class."))

    swelling = _text(_single_value(df, "Swelling Potential"))
    if swelling:
        norm = swelling.lower().strip()
        aliases = {"none": "none", "no": "none", "little": "little", "low": "little",
                   "fair": "fair", "medium": "fair", "high": "high"}
        swelling = aliases.get(norm)
    if swelling:
        idx = {"none": 0, "little": 1, "fair": 2, "high": 3}[swelling]
        maps = {
            "epb": ["main", "main", "extended", "limited"],
            "slurry": ["main", "main", "extended", "limited"],
            "hybrid": ["main", "main", "extended", "limited"],
        }
        ratings = {cls: maps[cls][idx] for cls in CLASSES}
        rows.append(_rating_row("Swelling potential", "Soil", swelling, swelling, ratings,
                                "DAUB 2025 Appendix 3.4/3.5/3.7"))

    abrasivity = _legacy_percentage_value(df, "Abrasivity (%)")
    if abrasivity is not None:
        idx = _range_index(abrasivity, [(0, 5), (5, 15), (15, 35), (35, 75), (75, 100.000001)])
        if idx is not None:
            maps = {
                "epb": ["main", "main", "extended", "extended", "limited"],
                "slurry": ["main", "main", "main", "extended", "extended"],
                "hybrid": ["main", "main", "extended", "extended", "limited"],
            }
            ratings = {cls: maps[cls][idx] for cls in CLASSES}
            rows.append(_rating_row("Abrasivity (equivalent quartz content)", "Soil", abrasivity,
                                    f"{abrasivity:.2f}%", ratings,
                                    "DAUB 2025 Appendix 3.4/3.5/3.7"))

    return rows


def _rock_rows(df: pd.DataFrame, required_face_pressure_kPa: Optional[float],
               include_shared: bool = True, include_confinement: bool = True) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    # Only evaluate the rock section when at least one genuinely rock-specific
    # input is present. This prevents shared pressure/swelling rows from being
    # counted twice in ordinary soft-ground cases.
    rock_specific = [
        _num(_single_value(df, "UCS (MPa)")),
        _num(_single_value(df, "RQD (%)")),
        _num(_single_value(df, "RMR")),
        _num(_single_value(df, "Water Inflow per 10 m (L/min)")),
        _num(_single_value(df, "CAI")),
    ]
    if not any(v is not None for v in rock_specific):
        return rows

    ucs = rock_specific[0]
    if ucs is not None and ucs >= 0:
        idx = _range_index(ucs, [(0, 5), (5, 25), (25, 50), (50, 100), (100, 250), (250, None)])
        if idx is not None:
            maps = {
                "epb": ["extended", "extended", "extended", "limited", "limited", "limited"],
                "slurry": ["extended", "extended", "extended", "extended", "extended", "extended"],
                "hybrid": ["extended", "extended", "extended", "limited", "limited", "limited"],
            }
            ratings = {cls: maps[cls][idx] for cls in CLASSES}
            rows.append(_rating_row("Unconfined compressive strength", "Rock", ucs,
                                    f"{ucs:.2f} MPa", ratings,
                                    "DAUB 2025 Appendix 3.4/3.5/3.7"))

    rqd = _num(_single_value(df, "RQD (%)"))
    if rqd is not None and 0 <= rqd <= 100:
        idx = _range_index(rqd, [(0, 25), (25, 50), (50, 75), (75, 90), (90, 100.000001)])
        maps = {
            "epb": ["main", "extended", "extended", "limited", "limited"],
            "slurry": ["extended", "extended", "extended", "extended", "extended"],
            "hybrid": ["main", "extended", "extended", "limited", "limited"],
        }
        ratings = {cls: maps[cls][idx] for cls in CLASSES}
        rows.append(_rating_row("Rock Quality Designation (RQD)", "Rock", rqd,
                                f"{rqd:.1f}%", ratings,
                                "DAUB 2025 Appendix 3.4/3.5/3.7"))

    rmr = _num(_single_value(df, "RMR"))
    if rmr is not None and 0 <= rmr <= 100:
        if rmr < 20:
            idx = 0
        elif rmr <= 40:
            idx = 1
        elif rmr <= 60:
            idx = 2
        elif rmr <= 80:
            idx = 3
        else:
            idx = 4
        maps = {
            "epb": ["main", "extended", "extended", "limited", "limited"],
            "slurry": ["extended", "extended", "extended", "extended", "extended"],
            "hybrid": ["main", "extended", "extended", "limited", "limited"],
        }
        ratings = {cls: maps[cls][idx] for cls in CLASSES}
        rows.append(_rating_row("Rock Mass Rating (RMR)", "Rock", rmr,
                                f"{rmr:.1f}", ratings,
                                "DAUB 2025 Appendix 3.4/3.5/3.7"))

    inflow = _num(_single_value(df, "Water Inflow per 10 m (L/min)"))
    if inflow is not None and inflow >= 0:
        if inflow == 0:
            idx = 0
        elif inflow < 10:
            idx = 1
        elif inflow < 25:
            idx = 2
        elif inflow <= 125:
            idx = 3
        else:
            idx = 4
        # All three selected closed-face classes are extended application across
        # the water-inflow classes in the DAUB tables.
        ratings = {cls: "extended" for cls in CLASSES}
        rows.append(_rating_row("Water inflow per 10 m tunnel", "Rock", inflow,
                                f"{inflow:.2f} L/min", ratings,
                                "DAUB 2025 Appendix 3.4/3.5/3.7"))

    cai = _num(_single_value(df, "CAI"))
    if cai is not None and cai >= 0:
        idx = _range_index(cai, [(0.1, 0.5), (0.5, 1), (1, 2), (2, 4), (4, 6.000001)])
        if idx is not None:
            maps = {
                "epb": ["main", "main", "extended", "extended", "limited"],
                "slurry": ["main", "main", "extended", "extended", "extended"],
                "hybrid": ["main", "main", "extended", "extended", "extended"],
            }
            ratings = {cls: maps[cls][idx] for cls in CLASSES}
            note = "For HYS at the highest CAI class, DAUB includes a mode-dependent limitation; this implementation uses the table's extended HYS rating for the overall hybrid class."
            rows.append(_rating_row("Cerchar Abrasivity Index (CAI)", "Rock", cai,
                                    f"{cai:.2f}", ratings,
                                    "DAUB 2025 Appendix 3.4/3.5/3.7", note if idx == 4 else ""))

    if include_shared:
        swelling = _text(_single_value(df, "Swelling Potential"))
        if swelling:
            norm = swelling.lower().strip()
            aliases = {"none": "none", "no": "none", "little": "little", "low": "little",
                       "fair": "fair", "medium": "fair", "high": "high"}
            swelling = aliases.get(norm)
        if swelling:
            idx = {"none": 0, "little": 1, "fair": 2, "high": 3}[swelling]
            maps = {
                "epb": ["main", "main", "extended", "limited"],
                "slurry": ["main", "main", "extended", "limited"],
                "hybrid": ["main", "main", "extended", "limited"],
            }
            ratings = {cls: maps[cls][idx] for cls in CLASSES}
            rows.append(_rating_row("Swelling potential", "Rock", swelling, swelling, ratings,
                                    "DAUB 2025 Appendix 3.4/3.5/3.7"))

    if include_confinement:
        conf_kpa = _num(_single_value(df, "Confinement Pressure (kPa)"))
        conf_source = "Entered confinement pressure"
        if conf_kpa is None and required_face_pressure_kPa is not None:
            conf_kpa = required_face_pressure_kPa
            conf_source = "Calculated required face-support pressure"
        if conf_kpa is not None and conf_kpa >= 0:
            conf_bar = conf_kpa / 100.0
            if conf_bar < 1:
                idx = 0
            elif conf_bar < 4:
                idx = 1
            elif conf_bar < 7:
                idx = 2
            elif conf_bar <= 15:
                idx = 3
            else:
                idx = None
            if idx is not None:
                maps = {
                    "epb": ["extended", "main", "extended", "limited"],
                    "slurry": ["extended", "main", "main", "main"],
                    "hybrid": ["extended", "main", "limited", "limited"],
                }
                ratings = {cls: maps[cls][idx] for cls in CLASSES}
                rows.append(_rating_row("Confinement / face-support pressure", "Rock", conf_bar,
                                        f"{conf_bar:.3g} bar ({conf_source})", ratings,
                                        "DAUB 2025 Appendix 3.4/3.5/3.7",
                                        "For continuous software input, values from 0 to <1 bar are assigned to DAUB's 0-bar class."))

    return rows


def _secondary_reference_checks(df: pd.DataFrame, water_head_m: Optional[float]) -> Dict[str, List[str]]:
    fhwa: List[str] = []
    efnarc: List[str] = []
    k = _num(_single_value(df, "Permeability (m/s)"))
    h = _num(water_head_m)

    if k is not None:
        if k > 1e-5:
            fhwa.append("Permeability is above the FHWA general 1×10⁻⁵ m/s transition guide, which tends toward slurry-face machines; FHWA notes EPB can extend above this with conditioning.")
        elif k < 1e-5:
            fhwa.append("Permeability is below the FHWA general 1×10⁻⁵ m/s transition guide, which tends toward EPB conditions.")
        else:
            fhwa.append("Permeability is approximately at the FHWA general 1×10⁻⁵ m/s EPB/slurry transition guide.")

        if h is not None and h > 0 and k > 1e-5:
            fhwa.append("Hydrostatic head combined with high permeability or fissures can make maintaining an EPB screw-conveyor plug difficult, which strengthens the case for a slurry-face machine.")
    else:
        fhwa.append("No permeability value was provided, so the FHWA permeability cross-check could not be applied.")

    efnarc.append("EPB soil conditioning can alter workability and reduce permeability, so DAUB/FHWA permeability ratings should not be interpreted as absolute machine limits without conditioning trials.")

    return {"fhwa": fhwa, "efnarc": efnarc}


def score_daub_tbm_options(df: pd.DataFrame, required_face_pressure_kPa: Optional[float] = None,
                           water_head_m: Optional[float] = None) -> Dict[str, Any]:
    # DAUB provides separate confinement/face-pressure application rows for
    # soil and rock. When genuinely rock-specific inputs are supplied, route
    # the pressure criterion through the rock table instead of scoring the
    # same pressure using the soil table. Other soil and rock criteria may
    # still be combined for mixed-ground cases.
    rock_specific_values = [
        _num(_single_value(df, "UCS (MPa)")),
        _num(_single_value(df, "RQD (%)")),
        _num(_single_value(df, "RMR")),
        _num(_single_value(df, "Water Inflow per 10 m (L/min)")),
        _num(_single_value(df, "CAI")),
    ]
    has_rock_specific = any(v is not None for v in rock_specific_values)

    soil_rows = _soil_rows(
        df, required_face_pressure_kPa, include_confinement=not has_rock_specific
    )
    rock_rows = _rock_rows(
        df,
        required_face_pressure_kPa,
        include_shared=not bool(soil_rows),
        include_confinement=has_rock_specific,
    )
    rows = soil_rows + rock_rows

    scores: Dict[str, Dict[str, Any]] = {}
    for cls in CLASSES:
        vals = [row["ratings"][cls]["score"] for row in rows]
        total = float(sum(vals))
        count = len(vals)
        pct = (100.0 * total / count) if count else None
        scores[cls] = {
            "display_name": DISPLAY_NAMES[cls],
            "total_score": total,
            "max_score": float(count),
            "criteria_count": count,
            "percentage": pct,
        }

    available = {cls: s["percentage"] for cls, s in scores.items() if s["percentage"] is not None}
    recommendation = "inconclusive"
    tied: List[str] = []
    if available:
        best = max(available.values())
        tied = [cls for cls, pct in available.items() if abs(pct - best) < 1e-9]
        if len(tied) == 1:
            recommendation = tied[0]

    # Parameter influence relative to the second-best alternative.
    drivers: List[Dict[str, Any]] = []
    constraints: List[Dict[str, Any]] = []
    if recommendation in CLASSES:
        ranked = sorted(available.items(), key=lambda kv: kv[1], reverse=True)
        runner = ranked[1][0] if len(ranked) > 1 else None
        for row in rows:
            win = row["ratings"][recommendation]["score"]
            if runner:
                run = row["ratings"][runner]["score"]
                margin = win - run
                if margin > 0:
                    drivers.append({
                        "parameter": row["parameter"],
                        "value_text": row["value_text"],
                        "winner_rating": row["ratings"][recommendation]["label"],
                        "runner_rating": row["ratings"][runner]["label"],
                        "margin": margin,
                    })
            if win < 1.0:
                constraints.append({
                    "parameter": row["parameter"],
                    "value_text": row["value_text"],
                    "rating": row["ratings"][recommendation]["label"],
                    "score": win,
                })
        drivers.sort(key=lambda x: x["margin"], reverse=True)
        constraints.sort(key=lambda x: x["score"])

    return {
        "source": "DAUB Recommendations for the Selection of Tunnel Boring Machines, January 2022, revised August 2025, Appendices 3.4, 3.5 and 3.7.",
        "score_mapping": {
            "main": 1.0,
            "extended": 0.5,
            "limited": 0.0,
        },
        "formula": "Suitability (%) = 100 × Σ(parameter suitability scores) / number of scored DAUB parameters",
        "scores": scores,
        "recommendation": recommendation,
        "recommendation_display": DISPLAY_NAMES.get(recommendation, "Inconclusive / tied"),
        "tied_classes": tied,
        "details": rows,
        "drivers": drivers,
        "constraints": constraints,
        "secondary_checks": _secondary_reference_checks(df, water_head_m),
    }
