# Title: Final Year Project - Particle Size Distribution Curve Function
# Name: Jordan Engel
# ID: 32479050
# Start Date: 24/04/24
# Finish Date: 07/05/24

import pandas as pd

def particle_size_distribution_curve(df1):

        #Sieve Sizes, Max Values, and Min Values for Mixed Shield and EPB
        sieve_sizes = [200, 75.0, 63.0, 37.5, 26.5, 19.0, 13.2, 9.50, 6.70, 4.75, 2.36, 1.18, 0.600, 0.400, 0.300, 0.212, 0.150, 0.075]
        mixed_min = [100, 85, 81, 65, 55, 48, 37, 32, 24, 17, 3, 0, 0, 0, 0, 0, 0, 0]
        mixed_max = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 90, 69, 60, 54, 48, 40, 31]
        epb_min = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 90, 74, 55]
        epb_max = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]

        #Making the ranges for Mixed Shield and EPB as dataframes for later use
        mixed_shield_ranges = {
            "Sieve Size": sieve_sizes,
            "Min Vals": mixed_min,
            "Max Vals": mixed_max
        }
        mixed_vals = pd.DataFrame(mixed_shield_ranges)
        epb_shield_ranges = {
            "Sieve Size": sieve_sizes,
            "Min Vals": epb_min,
            "Max Vals": epb_max
        }
        epb_vals = pd.DataFrame(epb_shield_ranges)

        #Initialising counts that will be updated by the for loop
        mixed_shield_match_val = 0
        epb_match_val = 0
        percentage_finer_soft = 0
        percentage_finer_heterogeneous = 0
        not_suitable_region = 0

        for index, (df_row, mixed_row, epb_row) in enumerate(zip(df1.iterrows(), mixed_vals.iterrows(), epb_vals.iterrows()), start=1):
            # Extract percentage finer and sieve sizes from df1
            percentage_finer_check_1 = df_row[1]["Percentage Finer (%)"]*100

            # Extract min and max values from mixed_vals
            min_val_for_mixed = mixed_row[1]["Min Vals"]
            max_val_for_mixed = mixed_row[1]["Max Vals"]

            # Extract min and max values from epb_vals
            min_val_for_epb = epb_row[1]["Min Vals"]
            max_val_for_epb = epb_row[1]["Max Vals"]

            # Finding the percentage finer above sieve size 0.212
            above_0_212 = df1[df1['Sieve Size (mm)'] > 0.212]
            total_percentage_finer_above_0_212 = above_0_212["Percentage Finer (%)"].sum()*100

            # Check to see if percentage finer lies in mixed ranges
            if min_val_for_mixed <= percentage_finer_check_1 <= max_val_for_mixed:
                mixed_shield_match_val += 1
                #print(f"Case 1 for {sieve_size_check_1}")

            # Check to see if percentage finer lies in epb ranges
            elif min_val_for_epb <= percentage_finer_check_1 <= max_val_for_epb:
                epb_match_val += 1
                #print(f"Case 2 for {sieve_size_check_1}")

            # Check to see if percentage finer is smaller than the mixed shield ranges or larger than the mixed shield ranges
            elif ((min_val_for_mixed > percentage_finer_check_1 and percentage_finer_check_1 > max_val_for_mixed) or
                  (min_val_for_mixed < percentage_finer_check_1 and percentage_finer_check_1 < max_val_for_mixed)):
                # Check to see if the percentage retained on the sieve of size 0.212 is less than 50%. If it is, then majority
                # of sample is coarse grained and therefore we pick mixed shield
                if total_percentage_finer_above_0_212 > 50:
                    mixed_shield_match_val += 1
                    #print(f"Case 3 for {sieve_size_check_1}")

            # Check to see if percentage finer is smaller than the epb ranges or larger than the epb ranges
            elif ((min_val_for_mixed > percentage_finer_check_1 and percentage_finer_check_1 > max_val_for_mixed) or
                  (min_val_for_mixed < percentage_finer_check_1 and percentage_finer_check_1 < max_val_for_mixed)):
                # Check to see if the percentage retained on the sieve of size 0.212 is greater than 50%. If it is,
                # then majority of sample is fine grained and therefore we pick epb
                if total_percentage_finer_above_0_212 < 50:
                    epb_match_val += 1
                    #print(f"Case 4 for {sieve_size_check_1}")


        index_for_percentage_finer_on_size_0_075 = df1[df1['Sieve Size (mm)'] == 0.075]
        total_percentage_finer_on_size_0_075 = index_for_percentage_finer_on_size_0_075["Percentage Finer (%)"] * 100

        # Percentage of fine grains passing through no. 200 sieve check
        if (total_percentage_finer_on_size_0_075 > 50).any():
            percentage_finer_soft += 1
        elif (total_percentage_finer_on_size_0_075 < 50).any():
            percentage_finer_heterogeneous += 1


        #print(f"epb_match_val = {epb_match_val}")
        #print(f"mixed_shield_match_val = {mixed_shield_match_val}")
        #print(f"percentage_finer_soft = {percentage_finer_soft}")
        #print(f"percentage_finer_heterogeneous = {percentage_finer_heterogeneous}")



        # Need to revise the final deciding "If" statement and what conditions must be met
        # If more than 9 vals are determined to work for mixed shield
        if mixed_shield_match_val > 9:

            # If ground type is found to be heterogeneous from percentage finer on no. 200 sieve
            if percentage_finer_heterogeneous == 1:
                #(Case 1)
                psdc_text = "From the Particle Size Distribution Curve, the ground profile favours the Slurry/Mixed-Shield range."
                #print("\nFrom the Particle Size Distribution Curve, the ground profile favours the Slurry/Mixed-Shield range (Case 1).")
                psdc_rec = "mixed shield"

            # If ground type is found to be soft from percentage finer on no. 200 sieve
            elif percentage_finer_heterogeneous == 0:

                # Check if percentage finer above sieve size 0.212 is less than 50%. If yes, means predominantely is coarse grained
                if df1.iloc[15]['Percentage Finer (%)']*100 < 50:
                    #(Case 2)
                    psdc_text = "From the Particle Size Distribution Curve, the ground profile favours the Slurry/Mixed-Shield range."
                    #print("\nFrom the Particle Size Distribution Curve, the ground profile favours the Slurry/Mixed-Shield range (Case 2).")
                    psdc_rec = "mixed shield"

                elif df1.iloc[15]['Percentage Finer (%)']*100 > 50:
                    #(Case 3)
                    psdc_text = "From the Particle Size Distribution Curve, the TBM Type is EPB."
                    #print("\nFrom the Particle Size Distribution Curve, the TBM Type is EPB (Case 3).")
                    psdc_rec = "epb"

        elif epb_match_val > 9:
            if percentage_finer_soft == 1:
                #(Case 4)
                psdc_text = "From the Particle Size Distribution Curve, the TBM Type is EPB."
                #print("\nFrom the Particle Size Distribution Curve, the TBM Type is EPB (Case 4).")
                psdc_rec = "epb"

            elif percentage_finer_soft == 0:
                if df1.iloc[15]['Percentage Finer (%)']*100 > 50:
                    #(Case 5)
                    psdc_text = "From the Particle Size Distribution Curve, the TBM Type is EPB."
                    #print("\nFrom the Particle Size Distribution Curve, the TBM Type is EPB (Case 5).")
                    psdc_rec = "epb"

                elif df1.iloc[15]['Percentage Finer (%)']*100 < 50:
                    #(Case 6)
                    psdc_text = "From the Particle Size Distribution Curve, the ground profile favours the Slurry/Mixed-Shield range."
                    #print("\nFrom the Particle Size Distribution Curve, the ground profile favours the Slurry/Mixed-Shield range (Case 6).")
                    psdc_rec = "mixed shield"

        elif not_suitable_region > 9:
            #(Case 7)
            psdc_text = "Sorry, the TBM type cannot be determined from the Particle Size Distribution Curve.\nManual selection is required."
            #print("\nSorry, the TBM type cannot be determined from the Particle Size Distribution Curve.\nManual selection is required (Case 7).")
            psdc_rec = "inconclusive"

        return psdc_text, psdc_rec