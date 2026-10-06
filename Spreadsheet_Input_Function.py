"""Read mechanical inputs from the integrated TBM spreadsheet.

Preferred spreadsheet format:
    row 1: column header
    row 2: value
    blank cell: not provided

Legacy files using row 2 = 0/1 provided flag and row 3 = value are still
accepted so older project spreadsheets remain usable.
"""

from __future__ import annotations

from typing import Any, Dict
import pandas as pd

MECHANICAL_COLUMNS = {
    "Ground Material": "ground_material",
    "Tunnel Diameter (m)": "diameter_m",
    "Tunnel Depth (m)": "depth_m",
    "Water Head (m)": "water_head_m",
    "Soil Unit Weight (kN/m3)": "unit_weight_kN_m3",
    "K0": "k0",
    "Shield Friction Coefficient": "shield_friction_coefficient",
    "Backup Friction Coefficient": "backup_friction_coefficient",
    "Shield Length (m)": "shield_length_m",
    "TBM Weight (kN)": "tbm_weight_kN",
    "Backup Weight (kN)": "backup_weight_kN",
    "Tunnel Slope (deg)": "tunnel_slope_deg",
    "Penetration / Cutting Force (kN)": "penetration_force_kN",
    # Preferred pipe-jacking inputs (friction is calculated automatically).
    "Pipe Friction Coefficient": "pipe_friction_coefficient",
    "Pipe Outer Diameter (m)": "pipe_outer_diameter_m",
    "Pipe Length (m)": "pipe_length_m",
    "Pipe Weight per Metre (kN/m)": "pipe_weight_per_m_kN",
    # Legacy manually entered total friction force retained for old files.
    "Pipe / Lining Friction Force (kN)": "pipe_friction_force_kN",
    "Undrained Shear Strength (kPa)": "undrained_shear_strength_kpa",
    "Chamber Support Pressure (kPa)": "chamber_support_pressure_kpa",
    # Backward compatibility only. This is treated as the boring / cutting
    # component; face-support force is calculated and added separately.
    "Boring Force (kN)": "boring_force_kN",
    "Rock Tensile Strength (MPa)": "rock_tensile_strength_mpa",
    "Cutter Spacing (m)": "cutter_spacing_m",
    "Disc Cutter Radius (m)": "disc_cutter_radius_m",
    "Cutter Tip Width (m)": "cutter_tip_width_m",
    "Penetration per Revolution (m)": "penetration_per_rev_m",
    "CSM Constant": "csm_constant",
    "Number of Cutters": "number_of_cutters",
    "Average Cutter Radial Position (m)": "average_cutter_radial_position_m",
    "Estimated Clay Cutterhead Torque (kN-m)": "clay_torque_requirement_kNm",
    "Cutterhead RPM": "rpm",
}


def _provided_value(df: pd.DataFrame, column: str) -> Any:
    if column not in df.columns or len(df.index) == 0:
        return None
    first = df[column].iloc[0]
    second = df[column].iloc[1] if len(df.index) > 1 else None

    # Legacy 0/1 flag + value format.
    try:
        f = float(first)
        if f in (0.0, 1.0) and second is not None and not pd.isna(second):
            return None if f == 0.0 else second
    except (TypeError, ValueError):
        pass

    # Clean format: first data cell is the value.
    if first is not None and not pd.isna(first):
        return first
    return None


def mechanical_inputs_from_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    inputs: Dict[str, Any] = {}
    for excel_column, internal_key in MECHANICAL_COLUMNS.items():
        inputs[internal_key] = _provided_value(df, excel_column)
    inputs["permeability_m_s"] = _provided_value(df, "Permeability (m/s)")
    # Re-use the DAUB rock UCS input in the CSM mechanical model.
    inputs["rock_ucs_mpa"] = _provided_value(df, "UCS (MPa)")
    return inputs
