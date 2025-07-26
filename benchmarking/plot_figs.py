import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec

plt.rcParams.update({
    "font.size": 7,
    "axes.titlesize": 7,
    "axes.labelsize": 7,
    "xtick.labelsize": 6,
    "ytick.labelsize": 6,
    "legend.fontsize": 6,
    "lines.markersize": 3,
})


def fig1():
    df_tket = pd.read_csv(f'results/tket_bench_final.csv')
    df_qiskit = pd.read_csv(f'results/qiskit_bench_final.csv')

    tket_cnot_counts = df_tket['n_cx']
    pandora_times = df_tket['Pandora']
    tket_times = df_tket['TKET']

    qiskit_labels = df_qiskit['Category']
    qiskit_x = np.arange(len(qiskit_labels))
    pandora_qiskit = df_qiskit['Pandora']
    qiskit_search = df_qiskit['Qiskit search']
    qiskit_rewrite = df_qiskit['Qiskit rewrite']
    qiskit_total = df_qiskit['Qiskit total']

    fig = plt.figure(figsize=(4.7, 3.2), dpi=600)
    gs = GridSpec(1, 2, height_ratios=[1], hspace=0.5)

    ax1 = fig.add_subplot(gs[0, 0])
    ax1.grid(True, linestyle=':', color='gray', alpha=0.6)

    ax1.loglog(tket_cnot_counts, pandora_times, marker='o', color='cadetblue', label='Pandora')
    ax1.loglog(tket_cnot_counts, tket_times, marker='o', color='brown', label='TKET')

    # for x, y in zip(tket_cnot_counts, pandora_times):
    #     ax1.annotate(f"{y:.2f}", (x, y), color='blue', fontsize=6, ha='right', va='bottom')
    # for x, y in zip(tket_cnot_counts, tket_times):
    #     ax1.annotate(f"{y:.2f}", (x, y), color='black', fontsize=6, ha='right', va='bottom')

    ax1.set_xlabel("TKET: Number of CNOTs")
    ax1.set_ylabel("Seconds")
    ax1.set_title("(a)")
    ax1.legend()

    ax2 = fig.add_subplot(gs[0, 1], sharey=ax1)
    ax2.grid(True, linestyle=':', color='gray', alpha=0.6)

    ax2.semilogy(qiskit_x, qiskit_search, label='Qiskit search', color='red', marker='o', alpha=0.6)
    ax2.semilogy(qiskit_x, qiskit_rewrite, label='Qiskit rewrite', color='darksalmon', marker='o', alpha=0.6)
    ax2.semilogy(qiskit_x, qiskit_total, label='Qiskit total', color='brown', marker='o')
    ax2.semilogy(qiskit_x, pandora_qiskit, label='Pandora', color='cadetblue', marker='o')

    ax2.set_xticks(qiskit_x)
    ax2.set_xticklabels(qiskit_labels, rotation=30, ha='right')
    ax2.set_xlabel("Qiskit: (#Qubits, Ratio)")
    ax2.legend()
    ax2.set_title("(b)")

    plt.savefig("fig1.png", bbox_inches='tight', dpi=600)
    plt.savefig("fig1.pdf", bbox_inches='tight', dpi=600)


def fig2():
    df_fh = pd.read_csv(f'results/fh50_bench_final.csv')
    df_adder = pd.read_csv(f'results/adder_improvement_3600.csv')
    df_pandora = pd.read_csv(f'results/pandora_multi_final.csv')

    threads_fh = df_fh['nprocs']
    threads_pandora = df_pandora['nprocs']

    speedup_fh = df_fh['speedup']
    speedup_pandora = df_pandora['HYBRID speed']

    adders = df_adder['circuit']
    tcount_reduction = df_adder['improvement_3600']

    fig = plt.figure(figsize=(5, 5), dpi=600)
    gs = GridSpec(2, 2, hspace=0.5)

    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(threads_fh, threads_fh, linestyle='--', color='gray', label='Ideal')
    ax1.plot(threads_fh, speedup_fh, marker='o', color='mediumslateblue', label='Observed')
    ax1.set_title("(a)")
    ax1.set_xlabel("Number of Threads")
    ax1.set_ylabel("Speed-up")
    ax1.set_xscale('log', base=10)
    ax1.set_yscale('log', base=10)
    ax1.set_xticks(threads_fh)
    ax1.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax1.grid(True, linestyle=':', color='gray', alpha=0.6)

    ax2 = fig.add_subplot(gs[0, 1])
    ax2.grid(True, linestyle=':', alpha=0.6, zorder=0)

    ax2.plot(threads_pandora, threads_pandora, linestyle='--', color='gray', label='Ideal')
    ax2.plot(threads_pandora, speedup_pandora, marker='o', color='mediumslateblue', label='Observed')
    ax2.set_title("(b)")
    ax2.set_xlabel("Number of Threads")
    ax2.set_xscale('log', base=10)
    ax2.set_yscale('log', base=10)
    ax2.set_xticks(threads_pandora)
    ax2.get_xaxis().set_major_formatter(plt.ScalarFormatter())

    ax3 = fig.add_subplot(gs[1, :])
    ax3.grid(True, linestyle=':', alpha=0.6, zorder=0)
    ax3.bar(adders, tcount_reduction, color='lightsteelblue', zorder=2)
    ax3.set_ylabel("T-count reduced (%)")
    # ax3.set_ylim(0, 16)
    ax3.set_xticklabels(adders, rotation=30, ha='right')
    ax3.set_title("(c)")

    plt.savefig("fig2.png", bbox_inches='tight', dpi=600)
    plt.savefig("fig2.pdf", bbox_inches='tight', dpi=600)


def fig3():
    df_rsa = pd.read_csv(f'results/rsa_bench_final.csv')

    bits = df_rsa['n_bits']
    time_high = df_rsa['time_high_decomp']
    time_modadd = df_rsa['time_mod_add']
    gate_counts = df_rsa['final_count']
    gates_per_second = df_rsa['gate_rate']

    fig = plt.figure(figsize=(5, 5), dpi=300)
    gs = GridSpec(2, 2, height_ratios=[1, 1], hspace=0.5, wspace=0.4)

    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(bits, time_high, 'o-', color='navy', label="Shor High-Level")
    ax1.plot(bits, time_modadd, 'o-', color='mediumslateblue', label="CtrlScaleModAdd")
    ax1.set_yscale('log')
    ax1.set_xscale('log')
    ax1.set_ylabel("Transpilation Seconds")
    ax1.set_xlabel("Bits Shor's algorithm")
    ax1.legend(loc='upper left')
    ax1.set_title("(a)")
    ax1.grid(True, linestyle=':', alpha=0.6)

    ax2 = fig.add_subplot(gs[1, 0])
    ax2.plot(bits, gate_counts, 'o-', color='mediumslateblue')
    ax2.set_yscale('log')
    ax2.set_xscale('log')
    ax2.set_ylabel("Gate count")
    ax2.set_xlabel("Bits Shor's algorithm")
    ax2.set_title("(b)")
    ax2.grid(True, linestyle=':', alpha=0.6)

    ax3 = fig.add_subplot(gs[1, 1])
    ax3.plot(bits, gates_per_second, 'o-', color='mediumslateblue')
    ax3.set_yscale('log')
    ax3.set_xscale('log')
    ax3.set_title("(c)")
    ax3.set_ylabel("Gates/Second")
    ax3.set_xlabel("Bits Shor's algorithm")
    ax3.grid(True, linestyle=':', alpha=0.6)

    bit_labels = [r"$2^6$", r"$2^7$", r"$2^8$", r"$2^9$", r"$2^{10}$", r"$2^{11}$"]

    for ax in [ax1, ax2, ax3]:
        ax.set_xticks(bits)
        ax.set_xticklabels(bit_labels, rotation=25, ha='right')

    plt.savefig("fig3.png", bbox_inches='tight', dpi=600)
    plt.savefig("fig3.pdf", bbox_inches='tight', dpi=600)


def fig4():
    df_decomp = pd.read_csv(f'results/decomposition_final.csv')
    df_estimates = pd.read_csv(f'results/fh_final.csv')

    x = df_decomp['id']
    decomp_times = df_decomp['decomp_time']
    extract_times = df_decomp['extraction_time']
    insert_times = df_decomp['pandora_insert_time']
    part_times = df_decomp['widgetisation_time']
    pyliqtr_rate = df_decomp['rate_pyliqtr']
    pandora_rate = df_decomp['rate_pandora']
    partition_rate = df_decomp['rate_partitioning']

    x_bar = ['20', '30', '40', '50', '100']
    y_bar = df_estimates['n_gates']

    x_line = df_decomp['id']
    gate_count = df_decomp['pandora_count']
    part_count = df_decomp['widget_count']

    fig = plt.figure(figsize=(5, 5), dpi=300)
    gs = GridSpec(2, 2, height_ratios=[1, 1], hspace=0.5, wspace=0.4)

    ax1 = fig.add_subplot(gs[0, 0])

    ax1.plot(x, decomp_times, 'o-', color='darkgreen', label='Decomposition')
    ax1.plot(x, extract_times, 'o-', color='darkseagreen', label='Extraction')
    ax1.plot(x, insert_times, 'o-', color='olivedrab', label='Insertion')
    ax1.plot(x, part_times, 'o-', color='lightgreen', label='Partitioning')
    ax1.set_yscale('log')
    ax1.set_xlabel('N x N')
    ax1.set_ylabel('Seconds')
    ax1.set_title('(a)')
    ax1.legend()
    ax1.grid(True, linestyle=':', alpha=0.6)

    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(x, partition_rate, 'o-', color='lightsteelblue', label='Partitioning')
    ax2.plot(x, pandora_rate, 'o-', color='mediumslateblue', label='Pandora')
    ax2.plot(x, pyliqtr_rate, 'o-', color='navy', label='pyLIQTR')

    ax2.set_yscale('log')
    ax2.set_xlabel('N x N')
    ax2.set_ylabel('Gates/second')
    ax2.set_title('(b)')
    ax2.legend()
    ax2.grid(True, linestyle=':', alpha=0.6)

    ax3 = fig.add_subplot(gs[1, 0])
    ax3.grid(True, linestyle=':', alpha=0.6, zorder=0)
    ax3.bar(x_bar, y_bar, color='lightsteelblue', zorder=2)

    ax3.set_title('(c)')
    ax3.set_yscale('log')
    ax3.set_xlabel('N x N')
    ax3.set_ylabel('Clifford+T gate count')
    ax3.set_xticklabels(x_bar)

    ax4 = fig.add_subplot(gs[1, 1])
    ax4.plot(x_line, gate_count, 'o-', color='cadetblue', label='Gate count (Clifford+T)')
    ax4.plot(x_line, part_count, 'o-', color='coral', label='Partition count')
    ax4.set_xlabel('N x N')
    ax4.set_title('(d)')
    ax4.legend()
    ax4.grid(True, linestyle=':', alpha=0.6)

    plt.savefig("fig4.pdf", bbox_inches='tight', dpi=600)
    plt.savefig("fig4.png", bbox_inches='tight', dpi=600)


def fig5():
    df_mqt = pd.read_csv(f'results/mqt_bench_final.csv')

    circuits = df_mqt['Circuit']

    mqt_eq_total_32 = df_mqt['mqt_eq_total_32']
    pandora_eq_total_32 = df_mqt['pandora_eq_total_32']

    mqt_eq_total_20 = df_mqt['mqt_eq_total_20']
    mqt_neq_total_20 = df_mqt['mqt_neq_total_20']
    mqt_eq_check_20 = df_mqt['mqt_eq_check_20']
    mqt_neq_check_20 = df_mqt['mqt_neq_check_20']
    pandora_eq_total_20 = df_mqt['pandora_eq_total_20']
    pandora_neq_total_20 = df_mqt['pandora_neq_total_20']

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(5, 5), gridspec_kw={'height_ratios': [1, 1.5]})
    bar_width = 0.35
    x = circuits

    ax1.grid(True, linestyle=':', alpha=0.6, zorder=0)
    ax1.bar(x - bar_width / 2, mqt_eq_total_32, width=bar_width, label='MQT 32q eq', color='peachpuff', zorder=2)
    ax1.plot(circuits, pandora_eq_total_32, marker='^', label='Pandora 32q eq', color='maroon', zorder=3)
    ax1.set_ylabel("Seconds")
    ax1.set_xlabel("Circuit")
    ax1.legend()

    ax2.grid(True, linestyle=':', alpha=0.6, zorder=0)
    ax2.bar(x - bar_width / 2, mqt_eq_total_20, width=bar_width, label='MQT 20q eq', color='peachpuff',
            zorder=2)
    ax2.bar(x + bar_width / 2, mqt_neq_total_20, width=bar_width, label='MQT 20q neq', color='lightsteelblue', zorder=2)

    ax2.plot(x, mqt_eq_check_20, marker='o', linestyle='--', color='coral', label='MQT 20q eq check', zorder=3)
    ax2.plot(x, mqt_neq_check_20, marker='o', linestyle='--', color='mediumslateblue', label='MQT 20q neq check', zorder=3)
    ax2.plot(x, pandora_neq_total_20, marker='D', linestyle='-', color='red', label='Pandora 20q neq', zorder=3)
    ax2.plot(x, pandora_eq_total_20, marker='^', linestyle='-', color='maroon', label='Pandora 20q eq', zorder=3)

    ax2.set_yscale('log')
    ax2.set_ylabel("Seconds")
    ax2.set_xlabel("Circuit")
    ax2.legend(fontsize="x-small")

    plt.savefig("fig5.pdf", bbox_inches='tight', dpi=600)
    plt.savefig("fig5.png", bbox_inches='tight', dpi=600)


def fig_adders():
    bit_widths = [16, 32, 64, 128, 256, 512, 1024, 2048]

    fig, axes = plt.subplots(nrows=2, ncols=4, figsize=(8, 4), dpi=300, constrained_layout=True)
    axes = axes.flatten()

    plot_columns = {
        't_count': ('m-', 'T count'),
        's_count': ('y-', 'S count'),
        'h_count': ('b-', 'H count'),
        # 'x_count': ('c-', 'X count'),
        'cx_count': ('r-', 'CX count'),
    }

    for i, n_bits in enumerate(bit_widths):
        df = pd.read_csv(f'results/adders_60min/adder_{n_bits}.csv')
        ax = axes[i]

        for col, (style, label) in plot_columns.items():
            x = np.array(df['id'])[1:]
            y = np.array(df[col])[1:]
            ax.loglog(x, y, style, label=label)

        ax.set_title(f'{n_bits}-bit Adder')
        ax.set_xlabel('Step')
        ax.set_ylabel('Gate Count')
        ax.legend(fontsize='x-small')

    plt.savefig("adders_all.png", bbox_inches='tight', dpi=600)
    plt.savefig("adders_all.pdf", bbox_inches='tight', dpi=600)

    plt.close()


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
    fig5()
    fig_adders()
