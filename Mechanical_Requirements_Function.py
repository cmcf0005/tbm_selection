"""Mechanical requirement calculations for the integrated TBM framework.

The boring-force model is selected from the excavation material:

* ``rock``: Colorado School of Mines (CSM) disc-cutter model.
* ``clay``: soft-ground model in which mechanical cutting resistance is
  neglected and thrust is governed by face support plus friction/drag.

The two branches intentionally use different inputs and equations. In hard rock,
CSM cutter penetration force is included as boring force. In soft cohesive clay,
the mechanical cutting/boring component is taken as negligible, while face-
support force is calculated explicitly and included in total thrust.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

GAMMA_W = 9.81  # kN/m^3


def _num(data: Dict[str, Any], key: str) -> Optional[float]:
    value = data.get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: Optional[float], digits: int = 4) -> str:
    if value is None:
        return "?"
    if value == 0:
        return "0"
    if abs(value) >= 10000 or abs(value) < 0.001:
        return f"{value:.4g}"
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def _step(name: str, equation: str, substitution: str, result: Optional[float], unit: str,
          note: str = "", parameters=None) -> Dict[str, Any]:
    return {
        "name": name,
        "equation": equation,
        "substitution": substitution,
        "result": result,
        "result_text": f"{_fmt(result)} {unit}" if result is not None else "Not calculated",
        "note": note,
        "parameters": parameters or [],
    }


def calculate_mechanical_requirements(inputs: Dict[str, Any]) -> Dict[str, Any]:
    d = _num(inputs, "diameter_m")
    depth = _num(inputs, "depth_m")
    water_head = _num(inputs, "water_head_m")
    gamma = _num(inputs, "unit_weight_kN_m3")
    k0 = _num(inputs, "k0")
    mu_shield = _num(inputs, "shield_friction_coefficient")
    mu_backup = _num(inputs, "backup_friction_coefficient")
    shield_length = _num(inputs, "shield_length_m")
    tbm_weight = _num(inputs, "tbm_weight_kN")
    backup_weight = _num(inputs, "backup_weight_kN")
    slope_deg = _num(inputs, "tunnel_slope_deg")
    legacy_pipe_friction_force = _num(inputs, "pipe_friction_force_kN")
    mu_pipe = _num(inputs, "pipe_friction_coefficient")
    pipe_outer_diameter = _num(inputs, "pipe_outer_diameter_m")
    pipe_length = _num(inputs, "pipe_length_m")
    pipe_weight_per_m = _num(inputs, "pipe_weight_per_m_kN")
    rpm = _num(inputs, "rpm")
    clay_torque_requirement_kNm = _num(inputs, "clay_torque_requirement_kNm")

    # Explicit material choice.  Old spreadsheets without this field are
    # auto-detected only for backward compatibility.
    material = str(inputs.get("ground_material") or "").strip().lower()

    # Clay input. Chamber support pressure is still parsed for backward
    # compatibility with older spreadsheets, but it is not used in the current
    # simplified soft-ground thrust model.
    undrained_shear_strength = _num(inputs, "undrained_shear_strength_kpa")
    chamber_support_pressure = _num(inputs, "chamber_support_pressure_kpa")

    # Rock / CSM inputs.
    ucs_mpa = _num(inputs, "rock_ucs_mpa")
    tensile_mpa = _num(inputs, "rock_tensile_strength_mpa")
    cutter_spacing = _num(inputs, "cutter_spacing_m")
    disc_radius = _num(inputs, "disc_cutter_radius_m")
    tip_width = _num(inputs, "cutter_tip_width_m")
    penetration_per_rev = _num(inputs, "penetration_per_rev_m")
    csm_constant = _num(inputs, "csm_constant")
    if csm_constant is None:
        csm_constant = 2.12
    n_cutters = _num(inputs, "number_of_cutters")
    avg_radial_position = _num(inputs, "average_cutter_radial_position_m")

    csm_probe = [ucs_mpa, tensile_mpa, cutter_spacing, disc_radius, tip_width, penetration_per_rev, n_cutters]
    if material not in ("rock", "clay"):
        material = "rock" if all(v is not None for v in csm_probe) else "clay"

    area = math.pi * d**2 / 4 if d is not None and d > 0 else None

    # ------------------------------------------------------------------
    # Common stress / face-pressure quantities.
    # Water is separated from the soil skeleton using effective stress.
    # ------------------------------------------------------------------
    total_vertical_stress_kPa = gamma * max(depth, 0.0) if gamma is not None and depth is not None else None
    groundwater_pressure_kPa = GAMMA_W * max(water_head, 0.0) if water_head is not None else None

    effective_vertical_stress_kPa = None
    if total_vertical_stress_kPa is not None and groundwater_pressure_kPa is not None:
        effective_vertical_stress_kPa = max(total_vertical_stress_kPa - groundwater_pressure_kPa, 0.0)

    effective_horizontal_soil_pressure_kPa = None
    if effective_vertical_stress_kPa is not None and k0 is not None:
        effective_horizontal_soil_pressure_kPa = k0 * effective_vertical_stress_kPa

    # Generic at-rest support pressure, primarily used by the rock branch and
    # as a DAUB confinement-pressure estimate when no clay face equilibrium is available.
    generic_face_support_pressure_kPa = None
    generic_face_support_force_kN = None
    if effective_horizontal_soil_pressure_kPa is not None and groundwater_pressure_kPa is not None:
        generic_face_support_pressure_kPa = effective_horizontal_soil_pressure_kPa + groundwater_pressure_kPa
        if area is not None:
            generic_face_support_force_kN = generic_face_support_pressure_kPa * area

    # ------------------------------------------------------------------
    # CLAY branch: mechanical cutting resistance is neglected.
    # Face-support demand is calculated from the lower-bound active soil force
    # plus groundwater force. For undrained clay phi_u = 0 => Ka = 1.
    # Effective vertical stress is used in the soil term because water force is
    # added separately, avoiding groundwater double counting.
    # ------------------------------------------------------------------
    ka_clay = 1.0
    clay_soil_pressure_lower_kPa = None
    clay_soil_force_kN = None
    water_force_kN = groundwater_pressure_kPa * area if groundwater_pressure_kPa is not None and area is not None else None
    chamber_support_force_kN = chamber_support_pressure * area if chamber_support_pressure is not None and area is not None else None
    clay_face_support_pressure_kPa = None
    clay_face_support_force_kN = None
    # Simplified soft-ground assumption: mechanical cutting/boring resistance
    # is negligible compared with face support and frictional resistances.
    clay_boring_force_kN = 0.0

    if effective_vertical_stress_kPa is not None and undrained_shear_strength is not None:
        raw = ka_clay * effective_vertical_stress_kPa - 2.0 * undrained_shear_strength * math.sqrt(ka_clay)
        clay_soil_pressure_lower_kPa = max(raw, 0.0)
        if area is not None:
            clay_soil_force_kN = clay_soil_pressure_lower_kPa * area

    if clay_soil_pressure_lower_kPa is not None and groundwater_pressure_kPa is not None:
        clay_face_support_pressure_kPa = clay_soil_pressure_lower_kPa + groundwater_pressure_kPa
        if area is not None:
            clay_face_support_force_kN = clay_face_support_pressure_kPa * area

    # ------------------------------------------------------------------
    # ROCK branch: CSM disc-cutter model.
    # ------------------------------------------------------------------
    csm_required = {
        "rock_ucs_mpa": ucs_mpa,
        "rock_tensile_strength_mpa": tensile_mpa,
        "cutter_spacing_m": cutter_spacing,
        "disc_cutter_radius_m": disc_radius,
        "cutter_tip_width_m": tip_width,
        "penetration_per_rev_m": penetration_per_rev,
        "number_of_cutters": n_cutters,
    }
    csm_missing = [k for k, v in csm_required.items() if v is None]

    contact_angle_rad = None
    load_angle_rad = None
    resultant_force_per_cutter_kN = None
    normal_force_per_cutter_kN = None
    rolling_force_per_cutter_kN = None
    cutter_penetration_force_kN = None

    csm_valid = not csm_missing
    if csm_valid:
        if (
            ucs_mpa <= 0 or tensile_mpa <= 0 or cutter_spacing <= 0 or disc_radius <= 0 or
            tip_width <= 0 or penetration_per_rev <= 0 or penetration_per_rev > 2 * disc_radius or
            n_cutters <= 0 or csm_constant <= 0
        ):
            csm_valid = False
        else:
            acos_arg = max(-1.0, min(1.0, (disc_radius - penetration_per_rev) / disc_radius))
            contact_angle_rad = math.acos(acos_arg)
            load_angle_rad = contact_angle_rad / 2.0
            inside = (
                (ucs_mpa**2) * tensile_mpa * cutter_spacing /
                (contact_angle_rad * math.sqrt(disc_radius * tip_width))
            )
            resultant_force_per_cutter_MN = (
                csm_constant * tip_width * disc_radius * contact_angle_rad * inside ** (1.0 / 3.0)
            )
            resultant_force_per_cutter_kN = 1000.0 * resultant_force_per_cutter_MN
            normal_force_per_cutter_kN = resultant_force_per_cutter_kN * math.cos(load_angle_rad)
            rolling_force_per_cutter_kN = resultant_force_per_cutter_kN * math.sin(load_angle_rad)
            cutter_penetration_force_kN = n_cutters * normal_force_per_cutter_kN

    # Branch outputs.
    if material == "rock":
        boring_force_kN = cutter_penetration_force_kN
        face_support_pressure_kPa = generic_face_support_pressure_kPa
        face_support_force_kN = generic_face_support_force_kN
        boring_model = "Hard rock — CSM disc-cutter model"
    else:
        boring_force_kN = clay_boring_force_kN
        face_support_pressure_kPa = clay_face_support_pressure_kPa
        face_support_force_kN = clay_face_support_force_kN
        boring_model = "Soft cohesive clay — mechanical cutting force neglected"

    # ------------------------------------------------------------------
    # Shield friction and trailing drag.
    # ------------------------------------------------------------------
    alpha = math.radians(slope_deg or 0.0)

    shield_friction_force_kN = None
    shield_friction_pressure_kPa = None
    shield_friction_depth_m = None
    # Zhang et al. (2014) F4 shield-friction formulation used in the
    # student hand calculation:
    #     F_friction = mu ( W_TBM + 2*pi*R*L*p_m )
    # where p_m is the average ground pressure acting around the shield.
    # Following the hand calculation, p_m is estimated from total overburden
    # at the shield centre: p_m = gamma (H + R), with R = D/2.
    if mu_shield is not None and shield_length is not None and d is not None and gamma is not None and depth is not None:
        shield_radius_m = d / 2.0
        shield_friction_depth_m = max(depth, 0.0) + shield_radius_m
        shield_friction_pressure_kPa = gamma * shield_friction_depth_m  # p_m
        soil_normal_force_kN = 2.0 * math.pi * shield_radius_m * shield_length * shield_friction_pressure_kPa
        machine_normal_force_kN = tbm_weight or 0.0
        shield_friction_force_kN = mu_shield * (machine_normal_force_kN + soil_normal_force_kN)

    # Pipe-jacking friction. The installed pipe string slides through the ground,
    # so the resistance grows with total jacked pipe length.
    #   F_pipe = mu_pipe (W_pipe + pi D_pipe L_pipe p_m)
    #   W_pipe = w_pipe_per_m L_pipe
    # p_m is the same average ground pressure at the tunnel axis used above.
    pipe_friction_force_kN = None
    pipe_total_weight_kN = None
    pipe_soil_normal_force_kN = None
    pipe_friction_source = None
    if (mu_pipe is not None and pipe_outer_diameter is not None and pipe_length is not None
            and pipe_weight_per_m is not None and shield_friction_pressure_kPa is not None):
        if mu_pipe >= 0 and pipe_outer_diameter > 0 and pipe_length >= 0 and pipe_weight_per_m >= 0:
            pipe_total_weight_kN = pipe_weight_per_m * pipe_length
            pipe_soil_normal_force_kN = math.pi * pipe_outer_diameter * pipe_length * shield_friction_pressure_kPa
            pipe_friction_force_kN = mu_pipe * (pipe_total_weight_kN + pipe_soil_normal_force_kN)
            pipe_friction_source = "Calculated from pipe-jacking inputs"
    elif legacy_pipe_friction_force is not None:
        pipe_friction_force_kN = legacy_pipe_friction_force
        pipe_friction_source = "Legacy manually entered total"

    backup_drag_force_kN = None
    if backup_weight is not None and mu_backup is not None:
        backup_drag_force_kN = backup_weight * math.cos(alpha) * mu_backup + backup_weight * math.sin(alpha)

    # ------------------------------------------------------------------
    # Total thrust is branch-specific.
    # Rock: CSM boring + separate face support + friction/drag/pipe.
    # Clay: mechanical cutting force is neglected; face support + friction/drag/pipe dominate.
    # ------------------------------------------------------------------
    total_operational_thrust_kN = None
    common_drag = [shield_friction_force_kN, backup_drag_force_kN]
    if material == "rock":
        if boring_force_kN is not None and face_support_force_kN is not None and all(v is not None for v in common_drag):
            total_operational_thrust_kN = boring_force_kN + face_support_force_kN + sum(common_drag)
    else:
        if face_support_force_kN is not None and all(v is not None for v in common_drag):
            total_operational_thrust_kN = face_support_force_kN + sum(common_drag)
    if total_operational_thrust_kN is not None and pipe_friction_force_kN is not None:
        total_operational_thrust_kN += pipe_friction_force_kN

    # Torque is branch-specific. Rock torque is calculated from CSM rolling
    # force; soft-ground/clay torque is an empirical/design input because this
    # framework does not assume a single universal clay torque equation.
    torque_requirement_kNm = None
    torque_model = None
    if material == "rock" and rolling_force_per_cutter_kN is not None and n_cutters is not None and avg_radial_position is not None:
        torque_requirement_kNm = n_cutters * rolling_force_per_cutter_kN * avg_radial_position
        torque_model = "Hard rock — CSM rolling-force torque"
    elif material == "clay":
        torque_requirement_kNm = clay_torque_requirement_kNm
        torque_model = "Soft soil / clay — user-entered empirical/design torque"

    power_requirement_kW = None
    if torque_requirement_kNm is not None and rpm is not None:
        power_requirement_kW = torque_requirement_kNm * 2.0 * math.pi * rpm / 60.0

    # ------------------------------------------------------------------
    # Calculation trace.
    # ------------------------------------------------------------------
    steps = []
    steps.append(_step("Excavation area", r"A=\frac{\pi D^2}{4}",
        rf"A=\frac{{\pi({_fmt(d)})^2}}{{4}}" if d is not None else r"D\text{ not provided}", area, "m^2",
        parameters=[(r"D", "Tunnel / cutterhead diameter (m)"), (r"A", "Excavation face area (m²)")]))
    steps.append(_step("Total vertical stress", r"\sigma_v=\gamma H",
        rf"\sigma_v={_fmt(gamma)}\times{_fmt(depth)}" if gamma is not None and depth is not None else r"\gamma\text{ and/or }H\text{ not provided}",
        total_vertical_stress_kPa, "kPa", parameters=[(r"\gamma", "Soil unit weight (kN/m³)"), (r"H", "Tunnel depth / overburden depth used for stress (m)"), (r"\sigma_v", "Total vertical overburden stress (kPa)")]))
    steps.append(_step("Groundwater pressure", r"u=\gamma_w h",
        rf"u=9.81\times{_fmt(water_head)}" if water_head is not None else r"h\text{ not provided}", groundwater_pressure_kPa, "kPa", parameters=[(r"\gamma_w", "Unit weight of water = 9.81 kN/m³"), (r"h", "Groundwater head above the tunnel face (m)"), (r"u", "Groundwater pore pressure (kPa)")]))
    steps.append(_step("Effective vertical stress", r"\sigma'_v=\max(\sigma_v-u,0)",
        rf"\sigma'_v=\max({_fmt(total_vertical_stress_kPa)}-{_fmt(groundwater_pressure_kPa)},0)" if total_vertical_stress_kPa is not None and groundwater_pressure_kPa is not None else r"\sigma_v\text{ and/or }u\text{ not available}",
        effective_vertical_stress_kPa, "kPa", note="Water pressure is removed before applying an effective-stress soil relationship.", parameters=[(r"\sigma_v", "Total vertical overburden stress (kPa)"), (r"u", "Groundwater pore pressure (kPa)"), (r"\sigma'_v", "Effective vertical stress carried by the soil skeleton (kPa)")]))

    if material == "clay":
        steps.append(_step("Clay active soil pressure (lower limit)",
            r"p_{s,lower}=K_a\sigma'_v-2c_u\sqrt{K_a},\quad K_a=1",
            rf"p_{{s,lower}}=1({_fmt(effective_vertical_stress_kPa)})-2({_fmt(undrained_shear_strength)})\sqrt{{1}}" if effective_vertical_stress_kPa is not None and undrained_shear_strength is not None else r"\sigma'_v\text{ and/or }c_u\text{ not provided}",
            clay_soil_pressure_lower_kPa, "kPa", note="For undrained cohesive clay, φu = 0 so Ka = 1. Negative active pressure is clipped to zero.", parameters=[(r"K_a", "Active earth pressure coefficient; taken as 1 for undrained clay"), (r"\sigma'_v", "Effective vertical stress (kPa)"), (r"c_u", "Undrained shear strength of the clay (kPa)"), (r"p_{s,lower}", "Minimum active soil-pressure component required for face stability (kPa)")]))
        steps.append(_step("Clay soil force", r"F_s=A\,p_{s,lower}",
            rf"F_s={_fmt(area)}\times{_fmt(clay_soil_pressure_lower_kPa)}" if area is not None and clay_soil_pressure_lower_kPa is not None else r"A\text{ and/or }p_{s,lower}\text{ not available}",
            clay_soil_force_kN, "kN", parameters=[(r"A", "Excavation face area (m²)"), (r"p_{s,lower}", "Lower-limit clay soil pressure (kPa)"), (r"F_s", "Resulting clay soil force acting on the face (kN)")]))
        steps.append(_step("Water force", r"F_w=uA",
            rf"F_w={_fmt(groundwater_pressure_kPa)}\times{_fmt(area)}" if groundwater_pressure_kPa is not None and area is not None else r"u\text{ and/or }A\text{ not available}",
            water_force_kN, "kN", parameters=[(r"u", "Groundwater pore pressure (kPa)"), (r"A", "Excavation face area (m²)"), (r"F_w", "Hydrostatic water force acting on the face (kN)")]))
        steps.append(_step("Clay face-support force", r"F_{support}=F_s+F_w",
            rf"F_{{support}}={_fmt(clay_soil_force_kN)}+{_fmt(water_force_kN)}" if clay_soil_force_kN is not None and water_force_kN is not None else r"F_s\text{ and/or }F_w\text{ not available}",
            face_support_force_kN, "kN", note="External soil + groundwater load that must be supported at the face.", parameters=[(r"F_s", "Clay soil force (kN)"), (r"F_w", "Groundwater force (kN)"), (r"F_{support}", "Minimum face-support force used in the thrust calculation (kN)")]))
        steps.append(_step("Clay mechanical cutting / boring force", r"F_{boring}\approx 0",
            r"F_{boring}\approx 0\;\text{(soft-ground simplifying assumption)}",
            boring_force_kN, "kN", note="For the soft cohesive clay branch, mechanical cutting resistance is treated as negligible compared with face support and frictional resistances.", parameters=[(r"F_{boring}", "Mechanical tool penetration / cutting force; neglected for the simplified soft-clay branch")]))
    else:
        steps.append(_step("Effective horizontal soil pressure", r"p'_s=K_0\sigma'_v",
            rf"p'_s={_fmt(k0)}\times{_fmt(effective_vertical_stress_kPa)}" if k0 is not None and effective_vertical_stress_kPa is not None else r"K_0\text{ and/or }\sigma'_v\text{ not available}",
            effective_horizontal_soil_pressure_kPa, "kPa", parameters=[(r"K_0", "At-rest earth pressure coefficient"), (r"\sigma'_v", "Effective vertical stress (kPa)"), (r"p'_s", "Effective horizontal soil pressure (kPa)")]))
        steps.append(_step("Face-support pressure", r"p_{support}=p'_s+u",
            rf"p_{{support}}={_fmt(effective_horizontal_soil_pressure_kPa)}+{_fmt(groundwater_pressure_kPa)}" if effective_horizontal_soil_pressure_kPa is not None and groundwater_pressure_kPa is not None else r"p'_s\text{ and/or }u\text{ not available}",
            face_support_pressure_kPa, "kPa", parameters=[(r"p'_s", "Effective horizontal soil pressure (kPa)"), (r"u", "Groundwater pressure (kPa)"), (r"p_{support}", "Total face-support pressure (kPa)")]))
        steps.append(_step("Face-support force", r"F_{support}=p_{support}A",
            rf"F_{{support}}={_fmt(face_support_pressure_kPa)}\times{_fmt(area)}" if face_support_pressure_kPa is not None and area is not None else r"p_{support}\text{ and/or }A\text{ not available}",
            face_support_force_kN, "kN", parameters=[(r"p_{support}", "Face-support pressure (kPa)"), (r"A", "Excavation face area (m²)"), (r"F_{support}", "Face-support force (kN)")]))
        steps.append(_step("CSM cutter contact angle", r"\phi=\arccos\left(\frac{R-p}{R}\right)",
            rf"\phi=\arccos\left(\frac{{{_fmt(disc_radius)}-{_fmt(penetration_per_rev)}}}{{{_fmt(disc_radius)}}}\right)" if disc_radius is not None and penetration_per_rev is not None else r"R\text{ and/or }p\text{ not provided}",
            contact_angle_rad, "rad", parameters=[(r"R", "Disc cutter radius (m)"), (r"p", "Penetration per revolution (m)"), (r"\phi", "Disc cutter contact angle (rad)")]))
        steps.append(_step("CSM resultant force per cutter",
            r"F_t=CTR\phi\left[\frac{\sigma_c^2\sigma_tS}{\phi\sqrt{RT}}\right]^{1/3}",
            r"\text{Complete valid CSM rock inputs required}" if resultant_force_per_cutter_kN is None else rf"F_t={_fmt(resultant_force_per_cutter_kN)}\;\mathrm{{kN}}",
            resultant_force_per_cutter_kN, "kN", parameters=[(r"C", "CSM empirical constant"), (r"T", "Disc cutter tip width (m)"), (r"R", "Disc cutter radius (m)"), (r"\phi", "Contact angle (rad)"), (r"\sigma_c", "Rock unconfined compressive strength / UCS (MPa)"), (r"\sigma_t", "Rock tensile strength (MPa)"), (r"S", "Cutter spacing (m)"), (r"F_t", "Resultant force on one cutter (kN)")]))
        steps.append(_step("CSM normal force per cutter", r"F_0=F_t\cos(\beta),\quad\beta=\phi/2",
            rf"F_0={_fmt(resultant_force_per_cutter_kN)}\cos({_fmt(load_angle_rad)})" if resultant_force_per_cutter_kN is not None and load_angle_rad is not None else r"F_t\text{ and/or }\beta\text{ not available}",
            normal_force_per_cutter_kN, "kN", parameters=[(r"F_t", "Resultant force on one cutter (kN)"), (r"\beta", "Load angle, equal to half the contact angle"), (r"F_0", "Normal force on one disc cutter (kN)")]))
        steps.append(_step("Rock boring force", r"F_{boring}=nF_0",
            rf"F_{{boring}}={_fmt(n_cutters)}\times{_fmt(normal_force_per_cutter_kN)}" if n_cutters is not None and normal_force_per_cutter_kN is not None else r"n\text{ and/or }F_0\text{ not available}",
            boring_force_kN, "kN", note="CSM mechanical chipping force. Face-support force remains a separate thrust component in the rock branch.", parameters=[(r"n", "Number of disc cutters"), (r"F_0", "Normal force per cutter (kN)"), (r"F_{boring}", "Total mechanical rock-boring force (kN)")]))

    steps.append(_step("Average shield ground pressure", r"p_m=\gamma(H+R)",
        (rf"p_m=({_fmt(gamma)})[({_fmt(depth)})+({_fmt(d)}/2)]"
         if shield_friction_pressure_kPa is not None else r"\text{Required friction inputs not available}"),
        shield_friction_pressure_kPa, "kPa",
        note="Average ground pressure used in the Zhang et al. (2014) F4 shield-friction equation, evaluated at the shield centre to match the student hand calculation.", parameters=[(r"\gamma", "Soil unit weight (kN/m³)"), (r"H", "Depth to the top/crown reference used by the input (m)"), (r"R", "Shield radius = D/2 (m)"), (r"p_m", "Average ground pressure acting around the shield (kPa)")]))

    steps.append(_step("Shield friction force", r"F_{friction}=\mu(W_{TBM}+2\pi R L p_m)",
        (rf"F_{{friction}}={_fmt(mu_shield)}[({_fmt(tbm_weight)})+2\pi({_fmt((d / 2.0) if d is not None else None)})({_fmt(shield_length)})({_fmt(shield_friction_pressure_kPa)})]"
         if shield_friction_force_kN is not None else r"\text{Required friction inputs not available}"),
        shield_friction_force_kN, "kN",
        note="Exact Zhang et al. (2014) F4 form used in the student hand calculation. W_TBM is the machine weight, R is shield radius, L is shield length, and p_m is average ground pressure around the shield.", parameters=[(r"\mu", "Shield-ground friction coefficient"), (r"W_{TBM}", "TBM weight (kN)"), (r"R", "Shield radius (m)"), (r"L", "Shield length (m)"), (r"p_m", "Average ground pressure around the shield (kPa)"), (r"F_{friction}", "Shield friction force resisting advance (kN)")]))
    if pipe_friction_source == "Calculated from pipe-jacking inputs":
        steps.append(_step("Total pipe-string weight", r"W_{pipe}=w_{pipe}L_{pipe}",
            rf"W_{{pipe}}={_fmt(pipe_weight_per_m)}\times{_fmt(pipe_length)}" if pipe_weight_per_m is not None and pipe_length is not None else r"w_{pipe}\text{ and/or }L_{pipe}\text{ not provided}",
            pipe_total_weight_kN, "kN", note="Weight of the full pipe string currently being pushed through the ground.", parameters=[(r"w_{pipe}", "Pipe weight per metre (kN/m)"), (r"L_{pipe}", "Total jacked pipe length (m)"), (r"W_{pipe}", "Total weight of the moving pipe string (kN)")]))
        steps.append(_step("Pipe-jacking friction", r"F_{pipe}=\mu_p\left(W_{pipe}+\pi D_{pipe}L_{pipe}p_m\right)",
            rf"F_{{pipe}}={_fmt(mu_pipe)}[({_fmt(pipe_total_weight_kN)})+\pi({_fmt(pipe_outer_diameter)})({_fmt(pipe_length)})({_fmt(shield_friction_pressure_kPa)})]" if all(v is not None for v in (mu_pipe, pipe_total_weight_kN, pipe_outer_diameter, pipe_length, shield_friction_pressure_kPa)) else r"\text{Complete pipe-jacking inputs required}",
            pipe_friction_force_kN, "kN", note="Calculated automatically. Pipe friction rises with the total jacked pipe length.", parameters=[(r"\mu_p", "Pipe-ground friction coefficient"), (r"W_{pipe}", "Total moving pipe-string weight (kN)"), (r"D_{pipe}", "Pipe outside diameter (m)"), (r"L_{pipe}", "Total jacked pipe length (m)"), (r"p_m", "Average ground pressure around the pipe (kPa)"), (r"F_{pipe}", "Pipe-jacking friction added to total operational thrust (kN)")]))
    elif pipe_friction_source:
        steps.append(_step("Pipe / lining friction", r"F_{pipe}=\text{legacy entered total}",
            rf"F_{{pipe}}={_fmt(pipe_friction_force_kN)}", pipe_friction_force_kN, "kN",
            note="Legacy spreadsheet value retained for backward compatibility.", parameters=[(r"F_{pipe}", "Previously entered total pipe / lining friction force (kN)")]))

    steps.append(_step("Back-up drag force", r"F_{pulling}=W_b\cos\alpha\,\mu_b+W_b\sin\alpha",
        rf"F_{{pulling}}={_fmt(backup_drag_force_kN)}" if backup_drag_force_kN is not None else r"\text{Required back-up inputs not available}",
        backup_drag_force_kN, "kN", parameters=[(r"W_b", "Back-up equipment weight (kN)"), (r"\alpha", "Tunnel slope angle"), (r"\mu_b", "Back-up drag friction coefficient"), (r"F_{pulling}", "Force required to pull / drag back-up equipment (kN)")]))

    if material == "rock":
        thrust_eq = r"TH=F_{boring}+F_{support}+F_{friction}+F_{pulling}+F_{pipe}"
        thrust_note = "Rock branch: CSM boring force and face-support force are separate and are both included."
    else:
        thrust_eq = r"TH=F_{support}+F_{friction}+F_{pulling}+F_{pipe}"
        thrust_note = "Clay branch: mechanical cutting/boring force is neglected; required thrust is governed by face support plus shield, back-up and pipe friction."
    steps.append(_step("Total operational thrust", thrust_eq,
        rf"TH={_fmt(total_operational_thrust_kN)}" if total_operational_thrust_kN is not None else r"\text{Required thrust inputs not available}",
        total_operational_thrust_kN, "kN", note=thrust_note, parameters=[(r"F_{support}", "Face-support force (kN)"), (r"F_{boring}", "Mechanical boring force; zero in clay and CSM-calculated in rock"), (r"F_{friction}", "Shield friction force (kN)"), (r"F_{pulling}", "Back-up drag force (kN)"), (r"F_{pipe}", "Pipe-jacking friction force (kN)"), (r"TH", "Total operational thrust requirement (kN)")]))

    if material == "clay":
        steps.append(_step("Soft-ground cutterhead torque", r"T_{req}=T_{input}",
            rf"T_{{req}}={_fmt(clay_torque_requirement_kNm)}" if clay_torque_requirement_kNm is not None else r"T_{input}\text{ not provided}",
            torque_requirement_kNm, "kN·m",
            note="Soft-ground/clay cutterhead torque is entered from manufacturer data, empirical guidance, or another validated soft-ground torque model; no single universal clay torque equation is assumed here.", parameters=[(r"T_{input}", "Estimated / externally determined soft-ground cutterhead torque (kN·m)"), (r"T_{req}", "Torque requirement used for motor power sizing (kN·m)")]))
        steps.append(_step("Required cutterhead power", r"P_{req}=\frac{T_{req}2\pi RPM}{60}",
            rf"P_{{req}}=\frac{{{_fmt(torque_requirement_kNm)}2\pi({_fmt(rpm)})}}{{60}}" if torque_requirement_kNm is not None and rpm is not None else r"T_{req}\text{ and/or RPM not available}",
            power_requirement_kW, "kW", parameters=[(r"T_{req}", "Required cutterhead torque (kN·m)"), (r"RPM", "Cutterhead rotational speed (rev/min)"), (r"P_{req}", "Required cutterhead mechanical power (kW)")]))

    if material == "rock":
        steps.append(_step("CSM rolling force per cutter", r"F_r=F_t\sin(\beta)",
            rf"F_r={_fmt(resultant_force_per_cutter_kN)}\sin({_fmt(load_angle_rad)})" if resultant_force_per_cutter_kN is not None and load_angle_rad is not None else r"F_t\text{ and/or }\beta\text{ not available}",
            rolling_force_per_cutter_kN, "kN", parameters=[(r"F_t", "Resultant force on one cutter (kN)"), (r"\beta", "Load angle"), (r"F_r", "Rolling / tangential cutter force contributing to torque (kN)")]))
        steps.append(_step("Required cutterhead torque", r"T_{req}=nF_r\bar r",
            rf"T_{{req}}={_fmt(n_cutters)}\times{_fmt(rolling_force_per_cutter_kN)}\times{_fmt(avg_radial_position)}" if all(v is not None for v in (n_cutters, rolling_force_per_cutter_kN, avg_radial_position)) else r"n,\;F_r\text{ and/or }\bar r\text{ not available}",
            torque_requirement_kNm, "kN·m", parameters=[(r"n", "Number of disc cutters"), (r"F_r", "Rolling force per cutter (kN)"), (r"\bar r", "Average radial position of cutters on the cutterhead (m)"), (r"T_{req}", "Required cutterhead torque (kN·m)")]))
        steps.append(_step("Required cutterhead power", r"P_{req}=\frac{T_{req}2\pi RPM}{60}",
            rf"P_{{req}}=\frac{{{_fmt(torque_requirement_kNm)}2\pi({_fmt(rpm)})}}{{60}}" if torque_requirement_kNm is not None and rpm is not None else r"T_{req}\text{ and/or RPM not available}",
            power_requirement_kW, "kW", parameters=[(r"T_{req}", "Required cutterhead torque (kN·m)"), (r"RPM", "Cutterhead rotational speed (rev/min)"), (r"P_{req}", "Required cutterhead mechanical power (kW)")]))

    missing = []
    common_required = ["diameter_m", "depth_m", "water_head_m", "unit_weight_kN_m3",
                       "shield_friction_coefficient", "shield_length_m", "backup_weight_kN", "backup_friction_coefficient"]
    for key in common_required:
        if _num(inputs, key) is None:
            missing.append(key)
    if material == "clay":
        if _num(inputs, "undrained_shear_strength_kpa") is None:
            missing.append("undrained_shear_strength_kpa")
        if clay_torque_requirement_kNm is None:
            missing.append("clay_torque_requirement_kNm")
    else:
        missing.extend(csm_missing)
    if rpm is None:
        missing.append("rpm")

    return {
        "ground_material": material,
        "boring_force_model": boring_model,
        "excavation_area_m2": area,
        "total_vertical_stress_kPa": total_vertical_stress_kPa,
        "vertical_stress_kPa": total_vertical_stress_kPa,
        "groundwater_pressure_kPa": groundwater_pressure_kPa,
        "effective_vertical_stress_kPa": effective_vertical_stress_kPa,
        "effective_horizontal_soil_pressure_kPa": effective_horizontal_soil_pressure_kPa,
        "soil_pressure_kPa": effective_horizontal_soil_pressure_kPa,
        "face_support_pressure_kPa": face_support_pressure_kPa,
        "face_support_force_kN": face_support_force_kN,
        "clay_soil_pressure_lower_kPa": clay_soil_pressure_lower_kPa,
        "clay_soil_force_kN": clay_soil_force_kN,
        "water_force_kN": water_force_kN,
        "chamber_support_force_kN": chamber_support_force_kN,
        "csm_contact_angle_rad": contact_angle_rad,
        "csm_load_angle_rad": load_angle_rad,
        "csm_resultant_force_per_cutter_kN": resultant_force_per_cutter_kN,
        "csm_normal_force_per_cutter_kN": normal_force_per_cutter_kN,
        "csm_rolling_force_per_cutter_kN": rolling_force_per_cutter_kN,
        "cutter_penetration_force_kN": cutter_penetration_force_kN,
        "penetration_force_kN": cutter_penetration_force_kN if material == "rock" else None,
        "boring_force_kN": boring_force_kN,
        "penetration_model": boring_model,
        "shield_friction_force_kN": shield_friction_force_kN,
        "shield_friction_pressure_kPa": shield_friction_pressure_kPa,
        "shield_friction_depth_m": shield_friction_depth_m,
        "backup_drag_force_kN": backup_drag_force_kN,
        "pipe_friction_force_kN": pipe_friction_force_kN,
        "pipe_friction_source": pipe_friction_source,
        "pipe_friction_coefficient": mu_pipe,
        "pipe_outer_diameter_m": pipe_outer_diameter,
        "pipe_length_m": pipe_length,
        "pipe_weight_per_m_kN": pipe_weight_per_m,
        "pipe_total_weight_kN": pipe_total_weight_kN,
        "total_operational_thrust_kN": total_operational_thrust_kN,
        "torque_requirement_kNm": torque_requirement_kNm,
        "torque_model": torque_model,
        "power_requirement_kW": power_requirement_kW,
        "mechanical_assessment": "requirements_only",
        "missing_inputs": missing,
        "csm_missing_inputs": csm_missing,
        "permeability_m_s": _num(inputs, "permeability_m_s"),
        "calculation_steps": steps,
    }
