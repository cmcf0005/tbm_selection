# Title: Final Year Project - Unified Soil Classification System Function
# Name: Jordan Engel
# ID: 32479050
# Start Date: 28/04/24
# Finish Date: 09/05/24

from scipy import interpolate

# Note that an extension of this code can be applied to determine grade of the ground material.

def unified_soil_classification_system(df1):

    percentages_to_find = [0.1, 0.3, 0.6]
    interpolated_function = interpolate.interp1d(df1['Cumulative Percentage Retained (%)'], df1['Sieve Size (mm)'])

    sieve_sizes = {percent: interpolated_function(percent) for percent in percentages_to_find}
    d10 = sieve_sizes.get(0.1)
    d30 = sieve_sizes.get(0.3)
    d60 = sieve_sizes.get(0.6)

    cu = d60 / d10
    cc = (d30 ** 2) / (d10 * d60)

    # print(cu)
    # print(cc)

    # for percent, size in sieve_sizes.items():
    #    print(f"Sieve size for {percent*100}% passing: {size} mm")

    ll_val = df1['Liquid Limit'].iloc[0]
    pi_val = df1['Plasticity Index'].iloc[0]

    index_for_percentage_finer_on_size_0_075 = df1[df1['Sieve Size (mm)'] == 0.075]
    total_percentage_finer_on_size_0_075 = index_for_percentage_finer_on_size_0_075["Percentage Finer (%)"] * 100

    gravel_val = 0
    sand_val = 0
    silt_val = 0
    clay_val = 0

    A_line_ll = 0.73 * (ll_val - 20)
    U_line_ll = 0.9 * (ll_val - 8)
    A_line_pi = (pi_val / 0.73) + 20

    # print(total_percentage_finer_on_size_0_075)

    if total_percentage_finer_on_size_0_075.item() < 50:
        # print("Ok, so we have coarse grained")
        # Gravel or Sand (Coarse Grained Conditions)
        if cu > 4 or 1 < cc < 3:
            # print("1")
            gravel_val = 1
            # return "Gravel"
        elif cu > 6 or 1 < cc < 3:
            # print("2")
            sand_val = 1
            # return "Sand"
    elif total_percentage_finer_on_size_0_075.item() > 50:
        # print("Ok, so we have fine grained")
        # Silt of Clay (Fine Grained Conditions)
        if ll_val < 50 and 0 < pi_val < A_line_ll:
            # print("3")
            silt_val = 1
            # return "MH - High Plasticity Silt"
        elif ll_val > 50 and A_line_ll < pi_val < U_line_ll:
            # print("4")
            clay_val = 1
            # return "CH - High Plasticity Clay"
        elif 16 < ll_val < 50 and A_line_ll < pi_val < U_line_ll:
            # print("5")
            clay_val = 1
            # return "CL - Low Plasticity Clay"
        elif 4 < pi_val < 7 and 10 < ll_val < A_line_pi:
            # print("6")
            clay_val = 1
            # return "CL - Low Plasticity Clay"
        elif 20 < ll_val < 50 and 0 < pi_val < A_line_ll:
            # print("7")
            silt_val = 1
            # return "ML - Low Plasticity Silt"
        elif 4 < pi_val < 7 and 10 < ll_val < A_line_pi:
            # print("8")
            silt_val = 1
            # return "ML - Low Plasticity Silt"

    # print(silt_val)
    # print(clay_val)
    # print(sand_val)
    # print(gravel_val)

    # Determine classification based on the updated values
    if silt_val == 1:
        uscs_text = "From the Unified Soil Classification System, the TBM Type is EPB."
        uscs_rec = "epb"

    elif clay_val == 1:
        uscs_text = "From the Unified Soil Classification System, the TBM Type is EPB."
        uscs_rec = "epb"

    elif sand_val == 1:
        uscs_text = "From the Uniform Soil Classification System, the ground profile favours the Slurry/Mixed-Shield range."
        uscs_rec = "mixed shield"

    elif gravel_val == 1:
        uscs_text = "From the Unified Soil Classification System, the ground profile favours the Slurry/Mixed-Shield range."
        uscs_rec = "mixed shield"

    else:
        uscs_text = "Sorry, the TBM type cannot be determined from the Unified Soil Classification System.\nManual selection is required."
        uscs_rec = "inconclusive"

    return uscs_text, uscs_rec