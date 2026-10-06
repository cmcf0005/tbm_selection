# Title: Final Year Project - Particle Size Distribution Curve Plot Function
# Name: Jordan Engel
# ID: 32479050
# Start Date: 24/04/24
# Finish Date: 29/04/24

import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter, FormatStrFormatter


def particle_size_distribution_curve_plot(df, output_file):
    plt.figure(figsize = (10, 6))
    plt.semilogx(df['Sieve Size (mm)'], df['Percentage Finer (%)'], linestyle = '-')

    b1_df = {
        "Point 1": [0.0067, 0.00],
        "Point 2": [0.0087, 0.05],
        "Point 3": [0.011, 0.10],
        "Point 4": [0.01425, 0.15],
        "Point 5": [0.0185, 0.20],
        "Point 6": [0.023, 0.25],
        "Point 7": [0.029, 0.30],
        "Point 8": [0.036, 0.35],
        "Point 9": [0.045, 0.40],
        "Point 10": [0.054, 0.45],
        "Point 11": [0.065, 0.50],
        "Point 12": [0.079, 0.55],
        "Point 13": [0.095, 0.60],
        "Point 14": [0.117, 0.65],
        "Point 15": [0.139, 0.70],
        "Point 16": [0.158, 0.75],
        "Point 17": [0.179, 0.80],
        "Point 18": [0.2, 0.85],
        "Point 19": [0.22, 0.90],
        "Point 20": [0.24, 0.95],
        "Point 21": [0.243, 1.00]
    }

    b2_df = {
        "Point 1": [0.0073, 0.00],
        "Point 2": [0.011, 0.05],
        "Point 3": [0.017, 0.10],
        "Point 4": [0.024, 0.15],
        "Point 5": [0.034, 0.20],
        "Point 6": [0.049, 0.25],
        "Point 7": [0.069, 0.30],
        "Point 8": [0.098, 0.35],
        "Point 9": [0.139, 0.40],
        "Point 10": [0.185, 0.45],
        "Point 11": [0.245, 0.50],
        "Point 12": [0.32, 0.55],
        "Point 13": [0.41, 0.60],
        "Point 14": [0.52, 0.65],
        "Point 15": [0.64, 0.70],
        "Point 16": [0.8, 0.75],
        "Point 17": [0.95, 0.80],
        "Point 18": [1.13, 0.85],
        "Point 19": [1.26, 0.90],
        "Point 20": [1.41, 0.95],
        "Point 21": [1.53, 1.00]
    }

    b3_df = {
        "Point 1": [2, 0.00],
        "Point 2": [2.7, 0.05],
        "Point 3": [3.6, 0.10],
        "Point 4": [4.5, 0.15],
        "Point 5": [5.75, 0.20],
        "Point 6": [7.4, 0.25],
        "Point 7": [9.3, 0.30],
        "Point 8": [12, 0.35],
        "Point 9": [15.2, 0.40],
        "Point 10": [19, 0.45],
        "Point 11": [23.5, 0.50],
        "Point 12": [28, 0.55],
        "Point 13": [33, 0.60],
        "Point 14": [39, 0.65],
        "Point 15": [46, 0.70],
        "Point 16": [54, 0.75],
        "Point 17": [64, 0.80],
        "Point 18": [73, 0.85],
        "Point 19": [83, 0.90],
        "Point 20": [91.5, 0.95],
        "Point 21": [100, 1.00]
    }

    b1_x = [p[0] for p in b1_df.values()]
    b1_y = [p[1] for p in b1_df.values()]

    b2_x = [p[0] for p in b2_df.values()]
    b2_y = [p[1] for p in b2_df.values()]

    b3_x = [p[0] for p in b3_df.values()]
    b3_y = [p[1] for p in b3_df.values()]

    plt.fill_betweenx(b1_y, [0] * len(b1_y), b1_x, color='blue', alpha=0.3)
    plt.fill_between(b2_x + b3_x[::-1], b2_y + b3_y[::-1], color='yellow', alpha=0.3)

    plt.xlabel('Sieve Size (mm)')
    plt.ylabel('Percentage Finer Passing')
    plt.title('Particle Size Distribution Curve')
    plt.grid(True, which='both')
    plt.xlim(left=0.001, right=200)
    plt.ylim(bottom=0, top=1)
    plt.yticks([0, 0.2, 0.4, 0.6, 0.8, 1], ['0%', '20%', '40%', '60%', '80%', '100%'])
    plt.gca().xaxis.set_major_formatter(FormatStrFormatter('%.2f'))
    plt.legend(["Sample PSDC", "Suitable for EPB", "Suitable for Mixshield"], loc = 'lower right')
    # plt.show()
    plt.savefig(output_file)
    plt.close()


