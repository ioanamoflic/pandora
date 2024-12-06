import csv
import time
from _connection import *
from union_find import UnionFindWidgetization
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.ticker import LinearLocator


def show_data():
    fig, ax = plt.subplots(subplot_kw={"projection": "3d"})
    df = pd.read_csv('widget_bench.csv', sep=',', usecols=['record_t', 'record_d', 'widget_count', 'times'])

    # Extract data
    X = df['record_t']
    Y = df['record_d']
    Z = df['widget_count']

    # Apply colors based on Z values for clarity
    # colors = Z / Z.max()  # Normalizing Z values for coloring
    colors = Z
    scatter = ax.scatter3D(X, Y, Z)

    # Draw a line through the points
    ax.plot3D(X, Y, Z, color='black', linewidth=0.1)

    # Customize the z axis
    ax.set_zlim(Z.min(), Z.max())  # Dynamically set z-axis limits
    ax.zaxis.set_major_locator(LinearLocator(10))
    ax.zaxis.set_major_formatter('{x:.02f}')

    # Add labels
    ax.set_xlabel('Max. T depth')
    ax.set_ylabel('Max. Depth')
    ax.set_zlabel('Widget Count', labelpad=15)

    ax.tick_params(axis='x', labelsize=8)
    ax.tick_params(axis='y', labelsize=8)
    ax.tick_params(axis='z', labelsize=8, pad=8)

    # Add a color bar
    # fig.colorbar(scatter, shrink=0.5, aspect=1)

    # Save the figure
    plt.savefig('plot_3d_widget_with_line.png')


if __name__ == "__main__":
    just_show = True
    if just_show:
        show_data()
    else:
        connection = get_connection()
        cursor = connection.cursor()

        max_node_id = 0
        edges = get_edge_list(connection)
        for tup in edges:
            s, t = tup
            max_node_id = max(max_node_id, max(s, t))

        num_elem = max_node_id + 1
        gate_labels = get_gate_types(connection, num_elem)
        connection.close()

        widget_count = []
        n_overlapping = []
        times = []
        record_t = []
        record_d = []
        t_counts = [1, 5, 10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000, 100000, 500000]
        depths = [1, 5, 10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000, 500000]
        for t_count_i in t_counts:
            for depth_i in depths:
                print(f"Started with {t_count_i} and {depth_i}")
                start_time = time.time()
                uf = UnionFindWidgetization(num_elem,
                                            max_t=t_count_i,
                                            max_d=depth_i,
                                            all_edges=edges,
                                            node_labels=gate_labels)
                for node1, node2 in edges:
                    uf.union(node1, node2)
                end_time = time.time()
                print(f"Time union = {end_time - start_time}")

                record_t.append(t_count_i)
                record_d.append(depth_i)
                widget_count.append(uf.count)
                # start_overlap = time.time()
                # n_overlapping.append(uf.overlap_count())
                # print(f"Time overlap = {time.time() - start_overlap}")
                times.append(end_time - start_time)

        # rows = zip(t_counts, depths, widget_count, n_overlapping, times)
        rows = zip(record_t, record_d, widget_count, times)
        with open('widget_bench.csv', 'w') as f:
            writer = csv.writer(f)
            writer.writerow(['record_t', 'record_d', 'widget_count', 'times'])
            for row in rows:
                writer.writerow(row)

        show_data()

