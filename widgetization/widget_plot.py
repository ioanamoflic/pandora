import pandas as pd

import matplotlib as mpl
import matplotlib.pyplot as plt
mpl.use('macosx')

from matplotlib.ticker import LinearLocator

import numpy as np

def plot3dsurface():
    # from numpy
    # import genfromtxt
    # my_data = genfromtxt('my_file.csv', delimiter=',')

    fig, ax = plt.subplots(subplot_kw={"projection": "3d"})
    df = pd.read_csv('widget_bench.csv', sep=',', usecols=['record_t', 'record_d', 'widget_count', 'times'])

    # Make data
    x = df['record_d']
    y = df['record_t']

    # x, y = np.meshgrid(x, y)
    # z = np.zeros(x.shape)

    z = df['widget_count']

    # ax.set_zscale('log')



    # for xi, xr in enumerate(x):
    #     yr = y[xi]
    #     zr = z[xi]
    #
    #     # print(xr)
    #     # print(yr)
    #     # print(zr)
    #     # print("----")
    #
    #     for i in range(len(xr)):
    #         cx = xr[i]
    #         cy = yr[i]
    #         r = df[(df['record_t'] == cx) & (df['record_d'] == cy)]['widget_count'].values[0]
    #
    #         # print(cx, cy, r)
    #
    #         zr[i] = r
    #
    #     # z[xi] = np.log(zr)
    #
    # # Plot the surface.

    # x = np.log(x)
    # y = np.log(y)
    # z = np.log(z)

    surf = ax.plot_trisurf(x, y, z, antialiased=False, edgecolor="black", linewidth=0.1,)

    # width = depth = np.zeros(x.shape) + 1
    # bar3d = ax.bar3d(x, y, np.zeros(x.shape), width, depth, z)

    ax.set_xlabel("Depth")
    ax.set_ylabel("T count")



    # Customize the z axis.
    # ax.set_zlim(-1.01, 1.01)
    # ax.zaxis.set_major_locator(LinearLocator(10))
    # A StrMethodFormatter is used automatically
    # ax.zaxis.set_major_formatter('{x:.02f}')

    # Add a color bar which maps values to colors.
    # fig.colorbar(surf, shrink=0.5, aspect=5)

    # print("x", x)
    # print("y", y)
    # print("z", z)


    plt.show()



plot3dsurface()