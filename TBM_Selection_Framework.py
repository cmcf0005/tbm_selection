"""Integrated TBM selection framework using quantitative DAUB scoring.

DAUB is the primary machine-class selection method. PSDC and USCS are retained
as supporting soil-characterisation outputs. Mechanical equations calculate the
requirements for the selected/candidate machine; they are not used as an
installed-capacity pass/fail check.
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
from scipy import interpolate

from PSDC_Function import particle_size_distribution_curve
from USCS_Function import unified_soil_classification_system
from DAUB_Quantitative_Scoring import score_daub_tbm_options, DISPLAY_NAMES
from Mechanical_Requirements_Function import calculate_mechanical_requirements
from Spreadsheet_Input_Function import mechanical_inputs_from_dataframe


def _safe_float(value):
    try:
        arr = np.asarray(value)
        return float(arr.reshape(-1)[0])
    except Exception:
        return None


def _uscs_calculation_trace(df):
    """Return intermediate USCS values used by the existing classifier."""
    try:
        f = interpolate.interp1d(df['Cumulative Percentage Retained (%)'], df['Sieve Size (mm)'])
        d10 = _safe_float(f(0.1))
        d30 = _safe_float(f(0.3))
        d60 = _safe_float(f(0.6))
        cu = d60 / d10 if d10 not in (None, 0) and d60 is not None else None
        cc = (d30 ** 2) / (d10 * d60) if all(v not in (None, 0) for v in (d10, d60)) and d30 is not None else None
        ll = _safe_float(df['Liquid Limit'].iloc[0]) if 'Liquid Limit' in df.columns else None
        pi = _safe_float(df['Plasticity Index'].iloc[0]) if 'Plasticity Index' in df.columns else None
        a_line = 0.73 * (ll - 20) if ll is not None else None
        u_line = 0.9 * (ll - 8) if ll is not None else None
        return {
            'd10_mm': d10, 'd30_mm': d30, 'd60_mm': d60,
            'cu': cu, 'cc': cc, 'liquid_limit': ll, 'plasticity_index': pi,
            'a_line': a_line, 'u_line': u_line,
        }
    except Exception:
        return {}




def _supporting_classification_cards(recommendation: str):
    """Map the legacy binary PSDC/USCS result onto the three current display classes.

    PSDC and USCS do not contain published criteria that independently separate a
    slurry shield from a multi-mode/hybrid shield.  The Hybrid card therefore
    reports compatibility with the mode indicated by the legacy method rather than
    inventing a third numerical score.
    """
    rec = (recommendation or '').strip().lower()
    if rec == 'epb':
        return {
            'epb': {'label': 'Preferred', 'detail': 'Ground characterisation favours EPB operation.'},
            'slurry': {'label': 'Not preferred', 'detail': 'This supporting method does not favour the slurry-side range.'},
            'hybrid': {'label': 'Compatible', 'detail': 'A Mixed/Hybrid shield could operate in EPB mode; this method cannot rank Hybrid separately.'},
        }
    if rec in ('mixed shield', 'slurry', 'slurry shield'):
        return {
            'epb': {'label': 'Not preferred', 'detail': 'This supporting method does not favour the EPB-side range.'},
            'slurry': {'label': 'Preferred', 'detail': 'Ground characterisation favours the slurry/mixed-shield range.'},
            'hybrid': {'label': 'Compatible', 'detail': 'A Mixed/Hybrid shield could operate in slurry mode; this method cannot rank Hybrid separately.'},
        }
    return {
        'epb': {'label': 'Inconclusive', 'detail': 'No clear preference from this supporting method.'},
        'slurry': {'label': 'Inconclusive', 'detail': 'No clear preference from this supporting method.'},
        'hybrid': {'label': 'Inconclusive', 'detail': 'No clear preference from this supporting method.'},
    }


def integrated_tbm_selection(df, mechanical_inputs: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if mechanical_inputs is None:
        mechanical_inputs = mechanical_inputs_from_dataframe(df)

    # Supporting characterisation methods remain visible, but they no longer
    # participate in a 3/3 voting scheme.
    psdc_text, psdc_rec = particle_size_distribution_curve(df)
    uscs_text, uscs_rec = unified_soil_classification_system(df)

    # Mechanical calculations are performed first so calculated face-support
    # pressure can be used in the DAUB confinement-pressure criterion when a
    # separate confinement-pressure input is not supplied.
    mechanical = calculate_mechanical_requirements(mechanical_inputs)

    daub = score_daub_tbm_options(
        df,
        required_face_pressure_kPa=mechanical.get('face_support_pressure_kPa'),
        water_head_m=mechanical_inputs.get('water_head_m'),
    )

    rec = daub['recommendation']

    def supporting_display_name(value):
        value = (value or '').strip().lower()
        if value == 'epb':
            return 'EPB'
        if value in ('mixed shield', 'slurry', 'slurry shield'):
            return 'Slurry Shield'
        return 'Inconclusive'

    psdc_display = supporting_display_name(psdc_rec)
    uscs_display = supporting_display_name(uscs_rec)

    if rec in DISPLAY_NAMES:
        final_status = 'selection_with_mechanical_requirements'
        daub_display = DISPLAY_NAMES[rec]
        if psdc_display == daub_display and uscs_display == daub_display:
            final_text = (
                f"{daub_display} is the overall recommended TBM type: it has the highest DAUB suitability score, "
                f"with both PSDC and USCS supporting {daub_display}."
            )
        else:
            final_text = (
                f"{daub_display} is the overall recommended TBM type based on the primary DAUB assessment. "
                f"PSDC indicates {psdc_display}, while USCS indicates {uscs_display}."
            )
        geological_recommendation = daub_display
    else:
        final_status = 'inconclusive_selection'
        tied_names = [DISPLAY_NAMES[c] for c in daub.get('tied_classes', [])]
        if tied_names:
            final_text = (
                'The primary DAUB assessment is tied between ' + ', '.join(tied_names) +
                f'. PSDC indicates {psdc_display}, while USCS indicates {uscs_display}; manual review is required.'
            )
        else:
            final_text = (
                'Insufficient DAUB parameters were supplied to calculate a primary TBM class recommendation. '
                f'PSDC indicates {psdc_display}, while USCS indicates {uscs_display}.'
            )
        geological_recommendation = 'Inconclusive / tied'

    return {
        'final_status': final_status,
        'final_text': final_text,
        'geological_recommendation': geological_recommendation,
        'psdc': {'text': psdc_text, 'recommendation': psdc_rec, 'class_support': _supporting_classification_cards(psdc_rec)},
        'uscs': {'text': uscs_text, 'recommendation': uscs_rec, 'class_support': _supporting_classification_cards(uscs_rec)},
        'daub': daub,
        'mechanical': mechanical,
        'selection_trace': {
            'rule': (
                'Primary selection uses the DAUB 2025 application tables. Each provided DAUB parameter is rated '
                'Main = 1.0, Extended = 0.5 or Limited = 0.0 for EPB, Slurry Shield and Mixed/Hybrid Shield. '
                'The mean available-parameter score is reported as a percentage. PSDC and USCS are supporting '
                'characterisation outputs and are not additional votes.'
            ),
            'uscs_values': _uscs_calculation_trace(df),
        },
    }
