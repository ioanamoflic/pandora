import pandas as pd

import numpy as np

import matplotlib as mpl
import matplotlib.pyplot as plt
mpl.use('macosx')


def plot3dsurface():
    fig, ax = plt.subplots(subplot_kw={"projection": "3d"})
    df = pd.read_csv('widget_bench.csv', sep=',', usecols=['record_t', 'record_d', 'widget_count', 'times'])

    # Make data
    x = df['record_d']
    y = df['record_t']
    z = df['widget_count']

    x = np.log(x)
    y = np.log(y)
    z = np.log(z)

    surf = ax.plot_trisurf(x, y, z, antialiased=False, edgecolor="black", linewidth=0.1,)

    ax.set_xlabel("Depth")
    ax.set_ylabel("T-count")
    ax.set_zlabel("Widget-count")

    plt.show()
