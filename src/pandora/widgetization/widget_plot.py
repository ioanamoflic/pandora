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

    x = np.log10(x)
    y = np.log10(y)
    z = np.log10(z)
    
    surf = ax.plot_trisurf(x, y, z, antialiased=False, edgecolor="black", linewidth=0.1,)

    ax.set_xlabel("Log(Depth)")
    ax.set_ylabel("Log(T-count)")
    ax.set_zlabel("Log(Widget-Count)")

    plt.show()
