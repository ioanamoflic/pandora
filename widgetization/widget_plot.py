import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import LinearLocator

import numpy as np

def plot3dsurface():

    fig, ax = plt.subplots(subplot_kw={"projection": "3d"})
    df = pd.read_csv('widget_bench.csv', sep=',', usecols=['record_t', 'record_d', 'widget_count', 'times'])

    # Make data
    x = df['record_t']
    y = df['record_d']

    x, y = np.meshgrid(x, y)
    z = np.zeros(x.shape)

    print("x", x)
    print("y", y)
    print("z", z)

    for xi, xr in enumerate(x):
        yr = y[xi]
        zr = z[xi]
        for i in range(len(xr)):
            cx = xr[i]
            cy = yr[i]

            zr[i] = 1#df[df['record_t'] == cx & df['record_d'] == cy]['widget_count'].values[0]

    # Plot the surface.
    surf = ax.plot_surface(x, y, z, linewidth=0, antialiased=False)

    # Customize the z axis.
    ax.set_zlim(-1.01, 1.01)
    ax.zaxis.set_major_locator(LinearLocator(10))
    # A StrMethodFormatter is used automatically
    ax.zaxis.set_major_formatter('{x:.02f}')

    # Add a color bar which maps values to colors.
    fig.colorbar(surf, shrink=0.5, aspect=5)

    plt.show()