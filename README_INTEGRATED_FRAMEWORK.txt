INTEGRATED TBM SELECTION FRAMEWORK — DAUB 2025 QUANTITATIVE VERSION

PRIMARY SELECTION METHOD
------------------------
The machine-class recommendation is now based on the latest official DAUB
"Recommendations for the Selection of Tunnel Boring Machines":
January 2022, revised August 2025.

Official DAUB publication page:
https://www.daub-ita.de/en/publikationen/empfehlungen/

Official August 2025 PDF:
https://www.daub-ita.de/fileadmin/documents/daub/gtcrec1/2025-08_Selection_of_Tunnel_Borng_Machines.pdf

The software implements the published selection tables for:
- Appendix 3.4 — Slurry Shield (SLS)
- Appendix 3.5 — Earth Pressure Balanced Shield (EPB)
- Appendix 3.7 — Hybrid-/Multi-mode Shield (HYS)

DAUB symbols are mapped to software scores as follows:
- Main field of application (+) = 1.0
- Extended application (o) = 0.5
- Application limited (–) = 0.0

For each candidate class:
Suitability (%) = 100 × sum(parameter scores) / number of scored parameters

Only supplied/applicable DAUB parameters enter the denominator. Missing inputs
are not treated as failures. If two or more classes have exactly the same top
percentage, the software reports a tie rather than inventing a tie-breaker.

IMPORTANT: DAUB publishes the + / o / – classifications. The 1.0 / 0.5 / 0.0
mapping and percentage normalisation are the project software implementation
requested for quantitative comparison; they are not a percentage formula
prescribed by DAUB itself.

IMPLEMENTED DAUB PARAMETERS
---------------------------
Soft ground / soil:
- fines content < 0.06 mm (calculated from PSD; log-size interpolation if needed)
- permeability k
- consistency index Ic
- relative density
- confinement / face-support pressure
- swelling potential
- equivalent quartz abrasivity

Rock (when rock inputs are supplied):
- unconfined compressive strength (UCS)
- RQD
- RMR
- water inflow per 10 m tunnel
- Cerchar Abrasivity Index (CAI)
- swelling potential
- confinement / face-support pressure

The Results tab reports:
- EPB suitability (%)
- Slurry Shield suitability (%)
- Mixed/Hybrid Shield suitability (%)
- highest-scoring recommendation or tie
- parameters driving the winning margin
- constraints on the leading class

PSDC AND USCS
-------------
PSDC and USCS remain in the application as supporting soil-characterisation
outputs and calculation traces. They no longer cast separate 3/3 votes in the
final machine-class recommendation. This avoids double-counting related soil
classification information once the DAUB tables are scored directly.

MECHANICAL REQUIREMENTS
-----------------------
The mechanical calculations remain separate from the DAUB class score.
They calculate required face-support pressure/force, boring/thrust demand,
rock-cutter torque and cutterhead power when enough inputs are available. They
do not claim an installed-capacity PASS/FAIL before a specific TBM has been
selected.

The face-support calculation now uses effective stress:
    sigma_v = gamma H
    u = gamma_w h
    sigma'_v = sigma_v - u
    p'_s = K0 sigma'_v
    p_support = p'_s + u
This prevents groundwater from being counted twice when K0 is used.

For rock, the penetration branch uses the Colorado School of Mines (CSM)
disc-cutter equations. The normal cutter force is summed over all cutters to
obtain the boring / cutter penetration force. Face-support force remains a
separate component and both are added once in the total thrust calculation.

The old 0.59 torque approximation is no longer used for the CSM rock branch.
Rolling force is resolved from the CSM resultant cutter force and torque is
calculated from n * Fr * average cutter radial position (or, conceptually,
Sum[Fr_i * r_i] for individually located cutters).

For non-rock cases, a separate optional Penetration / Cutting Force input is
available until a separately sourced soil penetration model is selected. Old
spreadsheets containing Boring Force are still accepted for compatibility; that
legacy value is treated as boring / cutting force only; face support remains separate.

If an explicit confinement-pressure value is not entered, the DAUB pressure
criterion can use the calculated required face-support pressure when that
mechanical result is available.

SECONDARY CROSS-CHECKS
----------------------
FHWA and EFNARC are used as non-scoring cross-checks, particularly for
permeability, groundwater conditions and EPB soil conditioning.

FHWA Tunnel Manual library:
https://www.fhwa.dot.gov/bridge/tunnel/library.cfm

EFNARC publications — Specification and Guidelines for the use of specialist
products for Mechanised Tunnelling (TBM), April 2005:
https://efnarc.org/publications

The secondary-reference notes do not change the DAUB percentage. They are shown
separately so the primary DAUB selection logic remains auditable.

SPREADSHEET FORMAT
------------------
Preferred format:
- Row 1 = parameter header
- Row 2 = value
- Blank cell = not provided

The obsolete 0/1 "provided" row is not required. The parser remains backwards
compatible with the older flag/value files.

FILES
-----
server.py
    Flask user interface: manual input OR spreadsheet upload, results and
    calculation breakdown.

TBM_Selection_Framework.py
    Orchestrates PSDC, USCS, quantitative DAUB selection and mechanics.

DAUB_Quantitative_Scoring.py
    Published DAUB table bands, +/o/– scoring, percentage normalisation,
    recommendation, controlling parameters and secondary checks.

Mechanical_Requirements_Function.py
    Effective-stress face support, CSM rock cutter forces, boring/thrust, torque and power equations.

Spreadsheet_Input_Function.py
    Reads mechanical values from the clean spreadsheet format, with legacy
    compatibility.

PSDC_Function.py / USCS_Function.py / PSDC_PlotFunction.py
    Supporting classification / plotting functions.

EXAMPLE SPREADSHEETS
--------------------
- EPB Example.xlsx
- Slurry Shield Example.xlsx
- Mixed Hybrid Shield Example.xlsx
- Conflict Example.xlsx

The first three examples are configured so the quantitative DAUB score has a
clear highest-scoring EPB, Slurry Shield or Mixed/Hybrid Shield respectively.
The Conflict Example intentionally preserves the previous tied case so the
software's inconclusive/tie handling can be demonstrated.

The example sheets include optional rock-criteria columns for UCS, RQD, RMR,
water inflow and CAI, and use a categorical Swelling Potential input.
