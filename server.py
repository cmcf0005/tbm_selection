import os
import math
import pandas as pd
from flask import Flask, flash, request, render_template_string, url_for
from werkzeug.utils import secure_filename

from PSDC_PlotFunction import particle_size_distribution_curve_plot
from TBM_Selection_Framework import integrated_tbm_selection

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'supersecretkey'

SIEVE_SIZES = [200, 75.0, 63.0, 37.5, 26.5, 19.0, 13.2, 9.50, 6.70, 4.75, 2.36, 1.18, 0.600, 0.400, 0.300, 0.212, 0.150, 0.075, 0.060, 0.010]

# (key, label, unit, spreadsheet column, input type)
GEO_FIELDS = [
    ('liquid_limit', 'Liquid Limit', '', 'Liquid Limit', 'number'),
    ('plasticity_index', 'Plasticity Index', '', 'Plasticity Index', 'number'),
    ('permeability', 'Permeability', 'm/s', 'Permeability (m/s)', 'number'),
    ('consistency_index', 'Consistency Index', '', 'Consistency Index', 'number'),
    ('relative_density_pct', 'Relative Density', '%', 'Relative Density (%)', 'number'),
    ('confinement_pressure', 'Confinement / Face Pressure', 'kPa', 'Confinement Pressure (kPa)', 'number'),
    ('swelling_potential', 'Swelling Potential', '', 'Swelling Potential', 'select'),
    ('abrasivity_pct', 'Equivalent Quartz Abrasivity', '%', 'Abrasivity (%)', 'number'),
    ('ucs_mpa', 'Unconfined Compressive Strength', 'MPa', 'UCS (MPa)', 'number'),
    ('rqd_pct', 'Rock Quality Designation (RQD)', '%', 'RQD (%)', 'number'),
    ('rmr', 'Rock Mass Rating (RMR)', '', 'RMR', 'number'),
    ('water_inflow', 'Water Inflow per 10 m', 'L/min', 'Water Inflow per 10 m (L/min)', 'number'),
    ('cai', 'Cerchar Abrasivity Index (CAI)', '', 'CAI', 'number'),
]

MECH_FIELDS = [
    ('diameter_m', 'Tunnel Diameter', 'm', 'Tunnel Diameter (m)', 'project'),
    ('depth_m', 'Tunnel Depth', 'm', 'Tunnel Depth (m)', 'project'),
    ('water_head_m', 'Water Head', 'm', 'Water Head (m)', 'project'),
    ('unit_weight_kN_m3', 'Soil Unit Weight', 'kN/m³', 'Soil Unit Weight (kN/m3)', 'project'),
    ('k0', 'K₀', '', 'K0', 'project'),
    ('tunnel_slope_deg', 'Tunnel Slope', '°', 'Tunnel Slope (deg)', 'project'),
    ('shield_friction_coefficient', 'Shield Friction Coefficient', '', 'Shield Friction Coefficient', 'assumption'),
    ('backup_friction_coefficient', 'Back-up Friction Coefficient', '', 'Backup Friction Coefficient', 'assumption'),
    ('shield_length_m', 'Shield Length', 'm', 'Shield Length (m)', 'assumption'),
    ('tbm_weight_kN', 'TBM Weight', 'kN', 'TBM Weight (kN)', 'assumption'),
    ('backup_weight_kN', 'Back-up Weight', 'kN', 'Backup Weight (kN)', 'assumption'),
    ('penetration_force_kN', 'Penetration / Cutting Force', 'kN', 'Penetration / Cutting Force (kN)', 'legacy'),
    ('pipe_friction_coefficient', 'Pipe / Ground Friction Coefficient', '', 'Pipe Friction Coefficient', 'pipe'),
    ('pipe_outer_diameter_m', 'Pipe Outer Diameter', 'm', 'Pipe Outer Diameter (m)', 'pipe'),
    ('pipe_length_m', 'Total Jacked Pipe Length', 'm', 'Pipe Length (m)', 'pipe'),
    ('pipe_weight_per_m_kN', 'Pipe Weight per Metre', 'kN/m', 'Pipe Weight per Metre (kN/m)', 'pipe'),
    ('undrained_shear_strength_kpa', 'Undrained Shear Strength', 'kPa', 'Undrained Shear Strength (kPa)', 'clay'),
    ('chamber_support_pressure_kpa', 'Chamber Support Pressure', 'kPa', 'Chamber Support Pressure (kPa)', 'legacy'),
    ('rock_tensile_strength_mpa', 'Rock Tensile Strength', 'MPa', 'Rock Tensile Strength (MPa)', 'rock'),
    ('cutter_spacing_m', 'Cutter Spacing', 'm', 'Cutter Spacing (m)', 'rock'),
    ('disc_cutter_radius_m', 'Disc Cutter Radius', 'm', 'Disc Cutter Radius (m)', 'rock'),
    ('cutter_tip_width_m', 'Cutter Tip Width', 'm', 'Cutter Tip Width (m)', 'rock'),
    ('penetration_per_rev_m', 'Penetration per Revolution', 'm/rev', 'Penetration per Revolution (m)', 'rock'),
    ('csm_constant', 'CSM Constant', '', 'CSM Constant', 'rock'),
    ('number_of_cutters', 'Number of Cutters', '', 'Number of Cutters', 'rock'),
    ('average_cutter_radial_position_m', 'Average Cutter Radial Position', 'm', 'Average Cutter Radial Position (m)', 'rock'),
    ('clay_torque_requirement_kNm', 'Estimated Cutterhead Torque', 'kN·m', 'Estimated Clay Cutterhead Torque (kN-m)', 'clay'),
    ('rpm', 'Cutterhead RPM', 'rpm', 'Cutterhead RPM', 'assumption'),
]

GEO_HELP = {
    'liquid_limit': 'Water content at which the soil changes from plastic to liquid behaviour.',
    'plasticity_index': 'Range of water content over which the soil behaves plastically.',
    'permeability': 'Hydraulic conductivity of the ground.',
    'consistency_index': 'Firmness of cohesive soil relative to its Atterberg limits.',
    'relative_density_pct': 'Relative density of granular soil.',
    'confinement_pressure': 'Required confinement or face-support pressure. If blank, the calculated face-support pressure is used when available.',
    'swelling_potential': 'Ground swelling category: none, little, fair or high.',
    'abrasivity_pct': 'Equivalent quartz content used to represent soil abrasivity.',
    'ucs_mpa': 'Unconfined compressive strength of rock.',
    'rqd_pct': 'Rock Quality Designation.',
    'rmr': 'Rock Mass Rating.',
    'water_inflow': 'Estimated water inflow per 10 m of tunnel.',
    'cai': 'Cerchar Abrasivity Index.',
}

GEO_SECTIONS = [
    ('USCS', ['liquid_limit', 'plasticity_index']),
    ('DAUB — Soil criteria', ['permeability', 'consistency_index', 'relative_density_pct', 'confinement_pressure', 'swelling_potential', 'abrasivity_pct']),
    ('DAUB — Rock criteria (optional)', ['ucs_mpa', 'rqd_pct', 'rmr', 'water_inflow', 'cai']),
]

MECH_HELP = {
    'diameter_m': 'Excavation/tunnel diameter used to calculate the face area.',
    'depth_m': 'Tunnel cover depth. For the Zhang et al. shield-friction term, the program estimates average shield pressure at the shield centre using p_m = gamma(H + R).',
    'water_head_m': 'Groundwater head above the same face point. Water pressure is added once after K₀ is applied to effective stress.',
    'unit_weight_kN_m3': 'Total/bulk soil unit weight used to calculate total vertical stress.',
    'k0': 'Ratio of horizontal effective stress to vertical effective stress at rest.',
    'tunnel_slope_deg': 'Tunnel inclination used in shield-weight and back-up drag calculations.',
    'shield_friction_coefficient': 'Coefficient of friction between the TBM shield and surrounding ground, used in the Zhang et al. equation F_friction = mu(W_TBM + 2*pi*R*L*p_m).',
    'backup_friction_coefficient': 'Separate friction coefficient for trailing/back-up equipment.',
    'shield_length_m': 'Length of the TBM shield in contact with surrounding ground.',
    'tbm_weight_kN': 'TBM shield/body weight included in the shield-friction normal force.',
    'backup_weight_kN': 'Weight of trailing back-up equipment used in the drag calculation.',
    'penetration_force_kN': 'Legacy manual cutting-force input retained only for old spreadsheets.',
    'undrained_shear_strength_kpa': 'Undrained shear strength cᵤ used to estimate the lower-bound active soil pressure at the clay face.',
    'chamber_support_pressure_kpa': 'Legacy field retained for older spreadsheets. It is not used in the current simplified clay thrust model.',
    'pipe_friction_coefficient': 'Coefficient of friction between the jacked pipe and surrounding ground.',
    'pipe_outer_diameter_m': 'Outside diameter of the pipe string sliding through the ground.',
    'pipe_length_m': 'Total length of pipe currently being jacked. Pipe friction increases with this length.',
    'pipe_weight_per_m_kN': 'Pipe weight per metre. For example, 100 kg/m is approximately 0.981 kN/m.',
    'rock_tensile_strength_mpa': 'Rock tensile strength used with UCS in the CSM disc-cutter model. Rock UCS is entered in the DAUB rock section above.',
    'cutter_spacing_m': 'Spacing between adjacent disc cutters used in the CSM model.',
    'disc_cutter_radius_m': 'Radius of one disc cutter.',
    'cutter_tip_width_m': 'Width of the disc cutter tip/edge used in the CSM model.',
    'penetration_per_rev_m': 'Target cutter penetration per cutterhead revolution.',
    'csm_constant': 'CSM empirical constant. If left blank, the program uses 2.12.',
    'number_of_cutters': 'Total number of disc cutters represented in the CSM thrust and torque calculations.',
    'average_cutter_radial_position_m': 'Average distance of the cutters from the cutterhead axis. Used for the simplified torque calculation n·Fr·r̄.',
    'clay_torque_requirement_kNm': 'Estimated soft-ground cutterhead torque from manufacturer data, empirical guidance, or a validated soft-ground torque model. No single clay torque equation is assumed by this framework.',
    'rpm': 'Cutterhead rotational speed. Used with either calculated rock torque or entered clay torque to calculate cutterhead power.',
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _clean_num(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value == '':
            return None
    try:
        number = float(value)
        if math.isnan(number):
            return None
        return number
    except (TypeError, ValueError):
        return None


def _display_num(value):
    value = _clean_num(value)
    if value is None:
        return ''
    return f'{value:.12g}'


def _provided_value(df, column):
    """Read clean row-2 values while remaining compatible with legacy 0/1 flag files."""
    if column not in df.columns or len(df.index) == 0:
        return None
    first = df[column].iloc[0]
    second = df[column].iloc[1] if len(df.index) > 1 else None
    try:
        f = float(first)
        if f in (0.0, 1.0) and second is not None and not pd.isna(second):
            return None if f == 0.0 else second
    except (TypeError, ValueError):
        pass
    if first is not None and not pd.isna(first):
        return first
    return None

def blank_form_values():
    return {
        'sieves': [{'size': _display_num(size), 'mass': ''} for size in SIEVE_SIZES],
        'geo': {field[0]: '' for field in GEO_FIELDS},
        'mech': {field[0]: '' for field in MECH_FIELDS},
        'ground_material': 'clay',
    }


def form_values_from_dataframe(df):
    values = blank_form_values()

    if 'Sieve Size (mm)' in df.columns and 'Mass Retained (g)' in df.columns:
        for row in values['sieves']:
            target = _clean_num(row['size'])
            matches = df[pd.to_numeric(df['Sieve Size (mm)'], errors='coerce').sub(target).abs() < 1e-9]
            if not matches.empty:
                row['mass'] = _display_num(matches['Mass Retained (g)'].iloc[0])

    for key, _label, _unit, column, kind in GEO_FIELDS:
        val = _provided_value(df, column)
        if kind == 'select':
            values['geo'][key] = '' if val is None else str(val)
        else:
            # Legacy percentage columns stored fractions after a 0/1 flag.
            if val is not None and column in ('Relative Density (%)', 'Abrasivity (%)'):
                try:
                    first = float(df[column].iloc[0])
                    if first in (0.0, 1.0) and len(df.index) > 1:
                        val = float(val) * 100.0
                except Exception:
                    pass
            values['geo'][key] = _display_num(val)

    for key, _label, _unit, column, _group in MECH_FIELDS:
        values['mech'][key] = _display_num(_provided_value(df, column))
    material = _provided_value(df, 'Ground Material')
    if material is not None and str(material).strip().lower() in ('rock','clay'):
        values['ground_material'] = str(material).strip().lower()
    return values

def _form_num(form, name):
    return _clean_num(form.get(name))


def dataframe_from_form(form):
    masses, sizes = [], []
    for i, default_size in enumerate(SIEVE_SIZES):
        size = _form_num(form, f'sieve_size_{i}')
        mass = _form_num(form, f'mass_retained_{i}')
        sizes.append(default_size if size is None else size)
        masses.append(0.0 if mass is None else mass)

    total_mass = sum(masses)
    cumulative_mass, running = [], 0.0
    for mass in masses:
        running += mass
        cumulative_mass.append(running)
    if total_mass > 0:
        cumulative_fraction = [v / total_mass for v in cumulative_mass]
        percentage_finer = [1.0 - v for v in cumulative_fraction]
    else:
        cumulative_fraction = [0.0] * len(masses)
        percentage_finer = [1.0] * len(masses)

    df = pd.DataFrame({
        'Sieve Size (mm)': sizes,
        'Mass Retained (g)': masses,
        'Cumulative Mass Retained (g)': cumulative_mass,
        'Cumulative Percentage Retained (%)': cumulative_fraction,
        'Percentage Finer (%)': percentage_finer,
    })

    # Clean spreadsheet convention: the first data cell is the value; blank = not provided.
    df['Ground Material'] = None
    material = form.get('ground_material', 'clay').strip().lower()
    df.loc[0, 'Ground Material'] = material if material in ('rock','clay') else 'clay'
    rock_geo_keys = {'ucs_mpa', 'rqd_pct', 'rmr', 'water_inflow', 'cai'}
    for key, _label, _unit, column, kind in GEO_FIELDS:
        df[column] = None
        # Rock-specific DAUB criteria are not applicable/accepted when the
        # selected excavation material is soft soil / clay.
        if material == 'clay' and key in rock_geo_keys:
            continue
        if kind == 'select':
            val = form.get(key, '').strip()
            if val:
                df.loc[0, column] = val
        else:
            val = _form_num(form, key)
            if val is not None:
                df.loc[0, column] = val

    for key, _label, _unit, column, _group in MECH_FIELDS:
        df[column] = None
        val = _form_num(form, key)
        if val is not None:
            df.loc[0, column] = val
    return df

def values_from_request_form(form):
    values = blank_form_values()
    for i, _size in enumerate(SIEVE_SIZES):
        values['sieves'][i]['size'] = form.get(f'sieve_size_{i}', values['sieves'][i]['size'])
        values['sieves'][i]['mass'] = form.get(f'mass_retained_{i}', '')
    for key, *_ in GEO_FIELDS:
        values['geo'][key] = form.get(key, '')
    for key, *_ in MECH_FIELDS:
        values['mech'][key] = form.get(key, '')
    values['ground_material'] = form.get('ground_material', 'clay')
    return values


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    values = blank_form_values()
    loaded_message = None

    if request.method == 'POST':
        action = request.form.get('action', 'run')

        if action == 'load':
            file = request.files.get('file')
            if file is None or file.filename == '':
                flash('Choose an Excel spreadsheet to load.')
                return render_template_string(INPUT_HTML, values=values, loaded_message=None,
                                              geo_fields=GEO_FIELDS, geo_sections=GEO_SECTIONS, mech_fields=MECH_FIELDS, geo_help=GEO_HELP, mech_help=MECH_HELP)
            if not allowed_file(file.filename):
                flash('Please upload a valid Excel file (.xls or .xlsx).')
                return render_template_string(INPUT_HTML, values=values, loaded_message=None,
                                              geo_fields=GEO_FIELDS, geo_sections=GEO_SECTIONS, mech_fields=MECH_FIELDS, geo_help=GEO_HELP, mech_help=MECH_HELP)

            filename = secure_filename(file.filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            try:
                df = pd.read_excel(file_path)
                values = form_values_from_dataframe(df)
                loaded_message = f'Loaded values from {filename}. You can edit any field before running the selection.'
            except Exception as exc:
                flash(f'Could not read the spreadsheet: {exc}')
            return render_template_string(INPUT_HTML, values=values, loaded_message=loaded_message,
                                          geo_fields=GEO_FIELDS, geo_sections=GEO_SECTIONS, mech_fields=MECH_FIELDS, geo_help=GEO_HELP, mech_help=MECH_HELP)

        # Run using the values currently visible in the form. A spreadsheet is
        # not required; loading a spreadsheet simply pre-fills these same fields.
        values = values_from_request_form(request.form)
        try:
            df = dataframe_from_form(request.form)
            result = integrated_tbm_selection(df)

            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            graph_path = os.path.join(app.config['UPLOAD_FOLDER'], 'graph.png')
            particle_size_distribution_curve_plot(df, graph_path)
            graph_url = url_for('static', filename='uploads/graph.png')
            return render_template_string(RESULT_HTML, result=result, graph_url=graph_url)
        except Exception as exc:
            flash(f'Unable to run the selection with the supplied values: {exc}')
            return render_template_string(INPUT_HTML, values=values, loaded_message=None,
                                          geo_fields=GEO_FIELDS, geo_sections=GEO_SECTIONS, mech_fields=MECH_FIELDS, geo_help=GEO_HELP, mech_help=MECH_HELP)

    return render_template_string(INPUT_HTML, values=values, loaded_message=loaded_message,
                                  geo_fields=GEO_FIELDS, geo_sections=GEO_SECTIONS, mech_fields=MECH_FIELDS, geo_help=GEO_HELP, mech_help=MECH_HELP)


@app.route('/uploads/<filename>')
def serve_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


INPUT_HTML = '''
<!doctype html>
<title>Integrated TBM Selection Framework</title>
<script>
window.MathJax = {tex:{inlineMath:[['\\(','\\)']],displayMath:[['\\[','\\]']]},svg:{fontCache:'global'}};
</script>
<style>
body { font-family: Arial, sans-serif; max-width: 1200px; margin: 30px auto; line-height: 1.4; color:#111; padding:0 18px; }
h1 { margin-bottom:8px; }
fieldset { margin: 18px 0; padding: 18px; border:1px solid #bbb; border-radius:8px; }
legend { font-size:18px; padding:0 8px; }
.note { background:#f4f4f4; padding:12px 16px; border-radius:7px; margin:10px 0; }
.loaded { background:#edf7ed; border:1px solid #b7d8b7; padding:10px 14px; border-radius:7px; }
.flash { background:#fff1f0; border:1px solid #e6b8b5; padding:10px 14px; border-radius:7px; margin:10px 0; }
.grid { display:grid; grid-template-columns:repeat(3, minmax(220px, 1fr)); gap:12px 18px; }
.field label { display:block; font-weight:bold; margin-bottom:4px; }
.field-help { color:#555; font-size:12.5px; line-height:1.3; margin-top:5px; min-height:32px; }
.input-wrap { display:flex; align-items:center; gap:7px; }
.input-wrap input { width:100%; box-sizing:border-box; padding:8px; border:1px solid #aaa; border-radius:5px; }
.unit { white-space:nowrap; color:#555; font-size:14px; }
table { border-collapse:collapse; width:100%; max-width:650px; }
th, td { border:1px solid #ccc; padding:6px 8px; text-align:left; }
th { background:#eee; }
td input { width:100%; box-sizing:border-box; padding:6px; border:1px solid #aaa; border-radius:4px; }
.actions { display:flex; gap:10px; margin:18px 0 35px; }
button { padding:10px 18px; font-size:16px; cursor:pointer; }
.subhead { margin:18px 0 8px; font-size:17px; }
@media (max-width:800px) { .grid { grid-template-columns:1fr; } }
</style>
<h1>Integrated TBM Selection Framework</h1>
<p>Enter the parameters below manually, or load an Excel spreadsheet to pre-fill the same fields.</p>

{% with messages = get_flashed_messages() %}
  {% for message in messages %}<div class="flash">{{ message }}</div>{% endfor %}
{% endwith %}
{% if loaded_message %}<div class="loaded">{{ loaded_message }}</div>{% endif %}

<form method="post" enctype="multipart/form-data">
  <fieldset>
    <legend><b>Load Spreadsheet</b></legend>
    <p>Select an existing TBM input spreadsheet. Loading it fills the fields below; you can then edit them before running the selection.</p>
    <input type="file" name="file" accept=".xls,.xlsx">
    <button type="submit" name="action" value="load">Load Spreadsheet Values</button>
  </fieldset>

  <fieldset>
    <legend><b>Excavation Material</b></legend>
    <div class="note">Select the ground material first. This controls the material-specific DAUB inputs and mechanical torque/boring-force model shown below.</div>
    <div class="field" style="max-width:360px">
      <label for="ground_material">Ground Material</label>
      <div class="input-wrap"><select id="ground_material" name="ground_material" onchange="toggleGroundMaterial()" style="width:100%;padding:8px;border:1px solid #aaa;border-radius:5px;">
        <option value="clay" {% if values.ground_material == 'clay' %}selected{% endif %}>Soft Soil / Clay</option>
        <option value="rock" {% if values.ground_material == 'rock' %}selected{% endif %}>Hard Rock</option>
      </select></div>
    </div>
  </fieldset>

  <fieldset>
    <legend><b>Particle Size Distribution</b></legend>
    <p>Enter mass retained for each sieve. Cumulative retained and percentage finer are calculated automatically.</p>
    <table>
      <tr><th>Sieve size (mm)</th><th>Mass retained (g)</th></tr>
      {% for row in values.sieves %}
      <tr>
        <td><input type="number" step="any" name="sieve_size_{{ loop.index0 }}" value="{{ row.size }}"></td>
        <td><input type="number" step="any" name="mass_retained_{{ loop.index0 }}" value="{{ row.mass }}"></td>
      </tr>
      {% endfor %}
    </table>
  </fieldset>

  <fieldset>
    <legend><b>Geological Classification Inputs</b></legend>
    {% for section_title, section_keys in geo_sections %}
      <div {% if 'rock' in section_title|lower %}id="daub-rock-criteria"{% endif %}>
      <h3 class="subhead">{{ section_title }}</h3>
      {% if 'rock' in section_title|lower %}<div class="note">Shown only for Hard Rock. These rock-specific DAUB criteria are excluded when Soft Soil / Clay is selected.</div>{% endif %}
      <div class="grid">
        {% for key, label, unit, column, kind in geo_fields if key in section_keys %}
        <div class="field">
          <label for="{{ key }}">{{ label }}</label>
          {% if kind == 'select' %}
            <div class="input-wrap"><select id="{{ key }}" name="{{ key }}" style="width:100%;padding:8px;border:1px solid #aaa;border-radius:5px;">
              <option value="" {% if not values.geo[key] %}selected{% endif %}>Not provided</option>
              {% for option in ['none','little','fair','high'] %}<option value="{{ option }}" {% if values.geo[key]|lower == option %}selected{% endif %}>{{ option|title }}</option>{% endfor %}
            </select></div>
          {% else %}
            <div class="input-wrap"><input type="number" step="any" id="{{ key }}" name="{{ key }}" value="{{ values.geo[key] }}">{% if unit %}<span class="unit">{{ unit }}</span>{% endif %}</div>
          {% endif %}
          <div class="field-help">{{ geo_help.get(key, "") }}</div>
        </div>
        {% endfor %}
      </div>
      </div>
    {% endfor %}
  </fieldset>

  <fieldset>
    <legend><b>Mechanical Inputs</b></legend>
    <div class="note">Hard Rock uses the CSM disc-cutter model for boring force and torque. Soft Soil / Clay neglects mechanical cutting force; clay cutterhead torque is entered as an empirical/design requirement and power is then calculated from torque and RPM.</div>
    <h3 class="subhead">Project / Geotechnical Inputs</h3>
    <div class="grid">
      {% for key, label, unit, column, group in mech_fields if group == 'project' %}
      <div class="field">
        <label for="{{ key }}">{{ label }}</label>
        <div class="input-wrap"><input type="number" step="any" id="{{ key }}" name="{{ key }}" value="{{ values.mech[key] }}">{% if unit %}<span class="unit">{{ unit }}</span>{% endif %}</div>
        <div class="field-help">{{ mech_help.get(key, "") }}</div>
      </div>
      {% endfor %}
    </div>
    <h3 class="subhead">Common TBM Design / Reference Assumptions</h3>
    <div class="grid">
      {% for key, label, unit, column, group in mech_fields if group == 'assumption' %}
      <div class="field"><label for="{{ key }}">{{ label }}</label><div class="input-wrap"><input type="number" step="any" id="{{ key }}" name="{{ key }}" value="{{ values.mech[key] }}">{% if unit %}<span class="unit">{{ unit }}</span>{% endif %}</div><div class="field-help">{{ mech_help.get(key, "") }}</div></div>
      {% endfor %}
    </div>
    <h3 class="subhead">Pipe-Jacking Inputs</h3>
    <div class="note">Used to calculate pipe friction for total operational thrust.</div>
    <div class="grid">
      {% for key, label, unit, column, group in mech_fields if group == 'pipe' %}
      <div class="field"><label for="{{ key }}">{{ label }}</label><div class="input-wrap"><input type="number" step="any" id="{{ key }}" name="{{ key }}" value="{{ values.mech[key] }}">{% if unit %}<span class="unit">{{ unit }}</span>{% endif %}</div><div class="field-help">{{ mech_help.get(key, "") }}</div></div>
      {% endfor %}
    </div>
    <div id="clay-inputs">
      <h3 class="subhead">Soft Soil / Clay Face-Support Inputs</h3>
      <div class="note">Mechanical cutting / boring resistance is neglected for the soft-clay thrust branch. Face support uses \(F_{support}=F_s+F_w\), with \(K_a=1\) for undrained cohesive clay. Cutterhead torque is entered separately because no single universal clay torque equation is assumed.</div>
      <div class="grid">{% for key, label, unit, column, group in mech_fields if group == 'clay' %}<div class="field"><label for="{{ key }}">{{ label }}</label><div class="input-wrap"><input type="number" step="any" id="{{ key }}" name="{{ key }}" value="{{ values.mech[key] }}">{% if unit %}<span class="unit">{{ unit }}</span>{% endif %}</div><div class="field-help">{{ mech_help.get(key, "") }}</div></div>{% endfor %}</div>
    </div>
    <div id="rock-inputs">
      <h3 class="subhead">Hard Rock CSM boring-force inputs</h3>
      <div class="note">Uses the CSM disc-cutter model and \(F_{boring}=nF_0\).</div>
      <div class="grid">{% for key, label, unit, column, group in mech_fields if group == 'rock' %}<div class="field"><label for="{{ key }}">{{ label }}</label><div class="input-wrap"><input type="number" step="any" id="{{ key }}" name="{{ key }}" value="{{ values.mech[key] }}">{% if unit %}<span class="unit">{{ unit }}</span>{% endif %}</div><div class="field-help">{{ mech_help.get(key, "") }}</div></div>{% endfor %}</div>
    </div>
  </fieldset>

  <div class="actions"><button type="submit" name="action" value="run"><b>Run TBM selection</b></button></div>
</form>
<script>
function setSectionState(el, show){
  if(!el) return;
  el.style.display=show?'block':'none';
  el.querySelectorAll('input,select').forEach(x=>x.disabled=!show);
}
function toggleGroundMaterial(){
  const m=document.getElementById('ground_material').value;
  setSectionState(document.getElementById('clay-inputs'), m==='clay');
  setSectionState(document.getElementById('rock-inputs'), m==='rock');
  setSectionState(document.getElementById('daub-rock-criteria'), m==='rock');
}
toggleGroundMaterial();
</script>
'''


RESULT_HTML = r'''
<!doctype html>
<title>TBM Selection Result</title>
<script>
window.MathJax = {tex:{inlineMath:[['\\(','\\)']],displayMath:[['\\[','\\]']]},svg:{fontCache:'global'}};
</script>
<script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
<style>
body { font-family:Arial,sans-serif; max-width:1150px; margin:35px auto; line-height:1.45; color:#111; padding:0 18px; }
.box { border:1px solid #bbb; border-radius:8px; padding:16px; margin:16px 0; }
table { border-collapse:collapse; width:100%; } th,td { border:1px solid #ccc; padding:8px; text-align:left; vertical-align:top; } th { background:#eee; }
.tabs { display:flex; gap:8px; margin:18px 0 0; border-bottom:1px solid #bbb; }
.tab-button { border:1px solid #bbb; border-bottom:none; background:#eee; padding:10px 16px; border-radius:7px 7px 0 0; cursor:pointer; font-size:16px; }
.tab-button.active { background:white; font-weight:bold; }.tab-panel{display:none;padding-top:8px}.tab-panel.active{display:block}
.calc-step{border:1px solid #ddd;border-radius:7px;padding:14px 16px;margin:10px 0}.calc-layout{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(260px,.85fr);gap:22px;align-items:start}
.parameter-help{border-left:1px solid #ddd;padding-left:20px}.parameter-help h4{margin:0 0 8px}.parameter-help ul{margin:0;padding-left:18px}.parameter-help li{margin:7px 0}.param-symbol{display:inline-block;min-width:62px;font-weight:bold}
.equation{font-size:19px;margin:10px 0;overflow-x:auto}.substitution{background:#f5f5f5;padding:10px 12px;border-radius:5px;margin:8px 0;overflow-x:auto;font-size:17px}.result-line{font-weight:bold;margin-top:5px}
.score-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:12px 0}.score-card{border:1px solid #ccc;border-radius:8px;padding:14px}.score{font-size:30px;font-weight:bold}.support-status{font-size:23px;font-weight:bold;margin:5px 0 6px}.support-card{min-height:112px}.main{background:#eaf5ea}.extended{background:#fff7df}.limited{background:#fdeaea}.muted{color:#555;font-size:13px}
.new-inputs-button{display:inline-block;border:1px solid #777;background:#f3f3f3;color:#111;padding:10px 16px;border-radius:7px;font-size:16px;font-weight:600;cursor:pointer}.new-inputs-button:hover{background:#e7e7e7}
.mechanical-results-table{table-layout:fixed;width:100%;}
@media(max-width:800px){.calc-layout,.score-grid{grid-template-columns:1fr}.parameter-help{border-left:none;border-top:1px solid #ddd;padding-left:0;padding-top:12px}}
</style>
<h1>Final TBM Suitability Output</h1>
<div class="box"><b>{{ result.final_text }}</b></div>
<div class="tabs"><button class="tab-button active" onclick="showTab('results',this)">Results</button><button class="tab-button" onclick="showTab('calculations',this)">Calculation Breakdown</button></div>

<div id="results" class="tab-panel active">
  <div class="box">
    <h2>DAUB Quantitative Suitability</h2>
    <p>{{ result.selection_trace.rule }}</p>
    <div class="score-grid">
      {% for key in ['epb','slurry','hybrid'] %}
      {% set sc = result.daub.scores[key] %}
      <div class="score-card">
        <b>{{ sc.display_name }}</b>
        <div class="score">{{ '%.1f%%'|format(sc.percentage) if sc.percentage is not none else '—' }}</div>
        <div class="muted">{{ '%.1f'|format(sc.total_score) }} / {{ '%.0f'|format(sc.max_score) }} from {{ sc.criteria_count }} scored DAUB criteria</div>
      </div>
      {% endfor %}
    </div>
    <p><b>Recommendation:</b> {{ result.geological_recommendation }}</p>
  </div>

  <div class="box">
    <h2>Particle Size Distribution Curve (PSDC)</h2>
    <p>{{ result.psdc.text }}</p>
    <div class="score-grid support-grid">
      {% for key, name in [('epb','EPB'),('slurry','Slurry Shield'),('hybrid','Mixed/Hybrid Shield')] %}
      {% set sc = result.psdc.class_support[key] %}
      <div class="score-card support-card"><b>{{ name }}</b><div class="support-status">{{ sc.label }}</div><div class="muted">{{ sc.detail }}</div></div>
      {% endfor %}
    </div>
    <p class="muted">PSDC is retained as a supporting particle-size method. It does not contain a published rule that independently separates Slurry Shield from Mixed/Hybrid Shield, so Hybrid is shown as mode-compatible rather than given an invented third score.</p>
    {% if graph_url %}<img src="{{ graph_url }}" alt="Particle size distribution curve" style="max-width:100%;">{% endif %}
  </div>

  <div class="box">
    <h2>Unified Soil Classification System (USCS)</h2>
    <p>{{ result.uscs.text }}</p>
    <div class="score-grid support-grid">
      {% for key, name in [('epb','EPB'),('slurry','Slurry Shield'),('hybrid','Mixed/Hybrid Shield')] %}
      {% set sc = result.uscs.class_support[key] %}
      <div class="score-card support-card"><b>{{ name }}</b><div class="support-status">{{ sc.label }}</div><div class="muted">{{ sc.detail }}</div></div>
      {% endfor %}
    </div>
    <p class="muted">USCS remains a supporting soil-characterisation method. It can indicate EPB-type versus coarse/granular slurry-side conditions, but it does not independently rank a Hybrid shield as a third machine class.</p>
  </div>

  <div class="box">
    <h2>Secondary-Reference Cross-Checks</h2>
    <p class="muted">These cross-checks do not add or subtract suitability points; the numerical score is based on DAUB.</p>

    <h3>FHWA</h3>
    {% for note in result.daub.secondary_checks.fhwa %}
      <p>{{ note }}</p>
    {% endfor %}

    <h3>EFNARC</h3>
    {% for note in result.daub.secondary_checks.efnarc %}
      <p>{{ note }}</p>
    {% endfor %}
  </div>

  <div class="box">
    <h2>Mechanical Requirements</h2>
    <p><b>Mechanical ground model:</b> {{ 'Soft Soil / Clay' if result.mechanical.ground_material == 'clay' else 'Hard Rock' }} — {{ result.mechanical.boring_force_model }}</p>
    <table class="mechanical-results-table"><colgroup><col style="width:46%"><col style="width:54%"></colgroup><tr><th>Quantity</th><th>Calculated value</th></tr>
    <tr><td>Face support pressure</td><td>{{ '%.2f kPa'|format(result.mechanical.face_support_pressure_kPa) if result.mechanical.face_support_pressure_kPa is not none else 'Not calculated' }}</td></tr>
    <tr><td>Face support force</td><td>{{ '%.2f kN'|format(result.mechanical.face_support_force_kN) if result.mechanical.face_support_force_kN is not none else 'Not calculated' }}</td></tr>
    {% if result.mechanical.ground_material == 'clay' %}<tr><td>Clay soil force, F<sub>s</sub></td><td>{{ '%.2f kN'|format(result.mechanical.clay_soil_force_kN) if result.mechanical.clay_soil_force_kN is not none else 'Not calculated' }}</td></tr><tr><td>Water force, F<sub>w</sub></td><td>{{ '%.2f kN'|format(result.mechanical.water_force_kN) if result.mechanical.water_force_kN is not none else 'Not calculated' }}</td></tr><tr><td>Mechanical cutting / boring force</td><td>Neglected (≈ 0 kN)</td></tr>{% else %}<tr><td>CSM cutter penetration / boring force</td><td>{{ '%.2f kN'|format(result.mechanical.cutter_penetration_force_kN) if result.mechanical.cutter_penetration_force_kN is not none else 'Not calculated' }}</td></tr>{% endif %}
    <tr><td>Shield friction force</td><td>{{ '%.2f kN'|format(result.mechanical.shield_friction_force_kN) if result.mechanical.shield_friction_force_kN is not none else 'Not calculated' }}</td></tr>
    <tr><td>Back-up drag force</td><td>{{ '%.2f kN'|format(result.mechanical.backup_drag_force_kN) if result.mechanical.backup_drag_force_kN is not none else 'Not calculated' }}</td></tr>
    <tr><td>Calculated pipe-jacking friction</td><td>{{ '%.2f kN'|format(result.mechanical.pipe_friction_force_kN) if result.mechanical.pipe_friction_force_kN is not none else 'Not included' }}</td></tr>
    <tr><td>Total operational thrust</td><td>{{ '%.2f kN'|format(result.mechanical.total_operational_thrust_kN) if result.mechanical.total_operational_thrust_kN is not none else 'Not calculated' }}</td></tr>
    <tr><td>Torque requirement</td><td>{{ '%.2f kN·m'|format(result.mechanical.torque_requirement_kNm) if result.mechanical.torque_requirement_kNm is not none else ('Not provided' if result.mechanical.ground_material == 'clay' else 'Not calculated') }}</td></tr>
    <tr><td>Power requirement</td><td>{{ '%.2f kW'|format(result.mechanical.power_requirement_kW) if result.mechanical.power_requirement_kW is not none else 'Not calculated' }}</td></tr></table>
    {% if result.mechanical.penetration_model %}<p><b>Penetration model:</b> {{ result.mechanical.penetration_model }}</p>{% endif %}
    {% if result.mechanical.missing_inputs %}<p><b>Optional inputs not supplied for detailed calculations:</b> {{ result.mechanical.missing_inputs|join(', ') }}</p>{% endif %}
  </div>
</div>

<div id="calculations" class="tab-panel">
  <div class="box">
    <h2>Working DAUB selection algorithm</h2>
    <p><b>DAUB class mapping:</b> Main application = 1.0, Extended application = 0.5, Limited application = 0.0.</p>
    <div class="equation">\[ S_j = 100\,\frac{\sum_{i=1}^{n} s_{ij}}{n} \]</div>
    <p>where \(S_j\) is the suitability percentage for TBM class \(j\), \(s_{ij}\) is the DAUB score for parameter \(i\), and only provided/applicable parameters are included in \(n\).</p>
    <p class="muted">The + / o / – classes come from DAUB. Converting those classes to 1 / 0.5 / 0 and averaging them is the software scoring method requested for this project; DAUB itself does not prescribe this percentage formula.</p>
    <table>
      <tr><th>DAUB parameter</th><th>Input / band</th><th>EPB</th><th>Slurry Shield</th><th>Mixed/Hybrid Shield</th></tr>
      {% for row in result.daub.details %}
      <tr><td><b>{{ row.parameter }}</b><br><span class="muted">{{ row.section }}</span></td><td>{{ row.value_text }}{% if row.note %}<br><span class="muted">{{ row.note }}</span>{% endif %}</td>
      {% for key in ['epb','slurry','hybrid'] %}{% set r=row.ratings[key] %}<td class="{{ r.rating }}"><b>{{ r.symbol }} {{ r.label }}</b><br>Score {{ '%.1f'|format(r.score) }}</td>{% endfor %}</tr>
      {% endfor %}
    </table>
    <h3>Totals</h3>
    {% for key in ['epb','slurry','hybrid'] %}{% set sc=result.daub.scores[key] %}<div class="calc-step"><b>{{ sc.display_name }}</b>: {{ '%.1f'|format(sc.total_score) }} / {{ '%.0f'|format(sc.max_score) }} × 100 = <b>{{ '%.1f%%'|format(sc.percentage) if sc.percentage is not none else 'Not enough data' }}</b></div>{% endfor %}
  </div>

  <div class="box">
    <h2>USCS Calculation Details</h2>
    {% set u=result.selection_trace.uscs_values %}
    {% if u and u.cu is not none and u.cc is not none %}
    <div class="calc-step"><div class="calc-layout"><div><b>Coefficient of uniformity</b><div class="equation">\[ C_u=\frac{D_{60}}{D_{10}} \]</div><div class="substitution">\[ C_u=\frac{ {{ '%.4f'|format(u.d60_mm) }} }{ {{ '%.4f'|format(u.d10_mm) }} }={{ '%.4f'|format(u.cu) }} \]</div></div><div class="parameter-help"><h4>Parameters</h4><ul><li><span class="param-symbol">\(C_u\)</span> coefficient of uniformity</li><li><span class="param-symbol">\(D_{60}\)</span> particle size at 60% passing</li><li><span class="param-symbol">\(D_{10}\)</span> particle size at 10% passing</li></ul></div></div></div>
    <div class="calc-step"><div class="calc-layout"><div><b>Coefficient of curvature</b><div class="equation">\[ C_c=\frac{D_{30}^2}{D_{10}D_{60}} \]</div><div class="substitution">\[ C_c=\frac{({{ '%.4f'|format(u.d30_mm) }})^2}{({{ '%.4f'|format(u.d10_mm) }})({{ '%.4f'|format(u.d60_mm) }})}={{ '%.4f'|format(u.cc) }} \]</div></div><div class="parameter-help"><h4>Parameters</h4><ul><li><span class="param-symbol">\(C_c\)</span> coefficient of curvature</li><li><span class="param-symbol">\(D_{30}\)</span> particle size at 30% passing</li><li><span class="param-symbol">\(D_{10}\)</span> particle size at 10% passing</li><li><span class="param-symbol">\(D_{60}\)</span> particle size at 60% passing</li></ul></div></div></div>
    {% endif %}
    <p><b>USCS result:</b> {{ result.uscs.text }}</p>
  </div>

  <div class="box">
    <h2>PSDC Calculation Details</h2>
    <p>{{ result.psdc.text }}</p>
    <p class="muted">The PSDC plot and legacy envelope comparison are shown on the Results tab. Hybrid compatibility follows the operating mode indicated by the PSDC result; no separate Hybrid PSDC envelope is assumed.</p>
  </div>

  <div class="box">
    <h2>Mechanical Calculation Details</h2>
    {% for step in result.mechanical.calculation_steps %}<div class="calc-step"><div class="calc-layout"><div><b>{{ step.name }}</b><div class="equation">\[ {{ step.equation }} \]</div><div class="substitution">\[ {{ step.substitution }} \]</div><div class="result-line">= {{ step.result_text }}</div></div>{% if step.parameters %}<div class="parameter-help"><h4>Parameters</h4><ul>{% for symbol,meaning in step.parameters %}<li><span class="param-symbol">\({{ symbol }}\)</span> {{ meaning }}</li>{% endfor %}</ul></div>{% endif %}</div></div>{% endfor %}
  </div>
</div>
<form action="/" method="get" style="margin:22px 0"><button class="new-inputs-button" type="submit">← Enter new inputs</button></form>
<script>function showTab(id,button){document.querySelectorAll('.tab-panel').forEach(el=>el.classList.remove('active'));document.querySelectorAll('.tab-button').forEach(el=>el.classList.remove('active'));document.getElementById(id).classList.add('active');button.classList.add('active');if(window.MathJax&&MathJax.typesetPromise)MathJax.typesetPromise([document.getElementById(id)]);}</script>
'''
if __name__ == '__main__':
    app.run(debug=True)
