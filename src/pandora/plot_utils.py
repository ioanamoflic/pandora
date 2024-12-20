import pandas as pd
from matplotlib import pyplot as plt


def plot3dsurface():
    fig, ax = plt.subplots(subplot_kw={"projection": "3d"})
    df = pd.read_csv('qpe_bench.csv', sep=',', usecols=['n_sites', 'n_bits', 'gate_count', 'time'])

    # Make data
    x = df['n_sites']
    y = df['n_bits']
    z = df['time']

    # x = np.log10(x)
    # y = np.log10(y)
    # z = np.log10(z)

    surf = ax.plot_trisurf(x, y, z, antialiased=False, edgecolor="black", linewidth=0.1, )

    ax.set_xlabel("nr of sites")
    ax.set_ylabel("nr of bits")
    ax.set_zlabel("time (sec)")

    plt.show()
