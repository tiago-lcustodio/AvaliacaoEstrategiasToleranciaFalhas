# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import glob
from matplotlib.ticker import FuncFormatter

# ==============================
# Configuração visual
# ==============================

COLOR_BLUE = "#2E6F95"
COLOR_BEIGE = "#E8C07D"

plt.rcParams.update({
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False
})

# ==============================
# FORMATADORES
# ==============================

def formatter_int(x, pos):
    return f"{int(x)}"

def formatter_one_decimal(x, pos):
    return f"{x:.1f}".replace(".", ",")

formatter_int = FuncFormatter(formatter_int)
formatter_one_decimal = FuncFormatter(formatter_one_decimal)

# ==============================
# Carregar CSVs
# ==============================

csv_files = glob.glob("*.csv")

dfs = []
for f in csv_files:
    dfs.append(pd.read_csv(f))

df = pd.concat(dfs, ignore_index=True)

# ==============================
# Funções auxiliares
# ==============================

def mean_se(data):
    mean = data.mean()
    se = data.std(ddof=1) / np.sqrt(len(data))
    return mean, se


def annotate_bars(ax, bars, means, ses, offset_index=0, raise_left=False):

    for i, (bar, mean, se) in enumerate(zip(bars, means, ses)):

        height = bar.get_height()

        x = bar.get_x() + bar.get_width()/2
        x = x + (offset_index * bar.get_width() * 0.25)

        y = height + se

        if raise_left:
            y = y * 1.05

        label = f"{mean:.3f} ± {se:.3f}".replace(".", ",")

        ax.text(
            x,
            y + (y * 0.02 + 0.001),
            label,
            ha='center',
            va='bottom',
            fontsize=8
        )


def adjust_ylim(ax, means, ses, formatter):

    max_value = max([m + s for m, s in zip(means, ses)])
    ax.set_ylim(0, max_value * 1.25)
    ax.yaxis.set_major_formatter(formatter)


# ==============================
# Cenários
# ==============================

scenarios = df["Scenario"].unique()

print("Cenários encontrados:", scenarios)

# ==============================
# Gerar gráficos
# ==============================

for scenario in scenarios:

    sdf = df[df["Scenario"] == scenario]

    middlewares = sdf["Middleware"].unique()

    # ==============================
    # CPU e Memória
    # ==============================

    cpu_means, cpu_ses = [], []
    mem_means, mem_ses = [], []

    for m in middlewares:

        mdf = sdf[sdf["Middleware"] == m]

        mean, se = mean_se(mdf["CPUPercent"])
        cpu_means.append(mean)
        cpu_ses.append(se)

        mean, se = mean_se(mdf["MemPeakMB"])
        mem_means.append(mean)
        mem_ses.append(se)

    x = np.arange(len(middlewares))

    fig, axes = plt.subplots(1,2, figsize=(12,5))

    bars_cpu = axes[0].bar(
        x,
        cpu_means,
        yerr=cpu_ses,
        capsize=6,
        color=COLOR_BLUE,
        label="CPU (%)"
    )

    axes[0].set_ylabel("CPU (%)")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(middlewares, rotation=20)
    axes[0].legend()
    axes[0].grid(axis='y', linestyle='--', alpha=0.4)

    adjust_ylim(axes[0], cpu_means, cpu_ses, formatter_one_decimal)

    annotate_bars(axes[0], bars_cpu, cpu_means, cpu_ses)

    bars_mem = axes[1].bar(
        x,
        mem_means,
        yerr=mem_ses,
        capsize=6,
        color=COLOR_BEIGE,
        label="Memória (MB)"
    )

    axes[1].set_ylabel("Memória (MB)")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(middlewares, rotation=20)
    axes[1].legend()
    axes[1].grid(axis='y', linestyle='--', alpha=0.4)

    adjust_ylim(axes[1], mem_means, mem_ses, formatter_int)

    annotate_bars(axes[1], bars_mem, mem_means, mem_ses)

    plt.tight_layout()
    plt.savefig(f"graph_{scenario}_cpu_mem.png", dpi=300)
    plt.close()

    # ==============================
    # Perda e Duplicação
    # ==============================

    loss_means, loss_ses = [], []
    dup_means, dup_ses = [], []

    for m in middlewares:

        mdf = sdf[sdf["Middleware"] == m]

        mean, se = mean_se(mdf["LossRate"])
        loss_means.append(mean)
        loss_ses.append(se)

        mean, se = mean_se(mdf["DupRate"])
        dup_means.append(mean)
        dup_ses.append(se)

    width = 0.35
    x = np.arange(len(middlewares))

    fig, ax = plt.subplots(figsize=(8,5))

    bars_loss = ax.bar(
        x - width/2,
        loss_means,
        width,
        yerr=loss_ses,
        capsize=6,
        color=COLOR_BLUE,
        label="Perda"
    )

    bars_dup = ax.bar(
        x + width/2,
        dup_means,
        width,
        yerr=dup_ses,
        capsize=6,
        color=COLOR_BEIGE,
        label="Duplicação"
    )

    ax.set_ylabel("Taxa")
    ax.set_xticks(x)
    ax.set_xticklabels(middlewares, rotation=20)

    ax.legend(loc="upper left")

    ax.grid(axis='y', linestyle='--', alpha=0.4)

    adjust_ylim(ax, loss_means + dup_means, loss_ses + dup_ses, formatter_one_decimal)

    annotate_bars(ax, bars_loss, loss_means, loss_ses, offset_index=-0.3, raise_left=True)
    annotate_bars(ax, bars_dup, dup_means, dup_ses, offset_index=0.3)

    plt.tight_layout()
    plt.savefig(f"graph_{scenario}_loss_dup.png", dpi=300)
    plt.close()

    # ==============================
    # Vazão e Latência
    # ==============================

    thr_means, thr_ses = [], []
    lat_means, lat_ses = [], []

    for m in middlewares:

        mdf = sdf[sdf["Middleware"] == m]

        mean, se = mean_se(mdf["ThroughputMsgS"])
        thr_means.append(mean)
        thr_ses.append(se)

        mean, se = mean_se(mdf["LatencyP95Ms"])
        lat_means.append(mean)
        lat_ses.append(se)

    width = 0.35
    x = np.arange(len(middlewares))

    fig, ax1 = plt.subplots(figsize=(8,5))

    bars_thr = ax1.bar(
        x - width/2,
        thr_means,
        width,
        yerr=thr_ses,
        capsize=6,
        color=COLOR_BLUE,
        label="Vazão (msg/s)"
    )

    ax1.set_ylabel("Vazão (msg/s)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(middlewares, rotation=20)
    ax1.grid(axis='y', linestyle='--', alpha=0.4)
    adjust_ylim(ax1, thr_means, thr_ses, formatter_int)

    ax2 = ax1.twinx()

    bars_lat = ax2.bar(
        x + width/2,
        lat_means,
        width,
        yerr=lat_ses,
        capsize=6,
        color=COLOR_BEIGE,
        label="Latência p95 (ms)"
    )

    ax2.set_ylabel("Latência p95 (ms)")
    adjust_ylim(ax2, lat_means, lat_ses, formatter_int)

    # legenda especial
    if scenario.lower() == "slow":
        ax1.legend([bars_thr, bars_lat], ["Vazão (msg/s)", "Latência p95 (ms)"], loc="upper right")
    elif scenario.lower() in ["flapping", "intermittent", "intermitente"]:
        ax1.legend(
            [bars_thr, bars_lat],
            ["Vazão (msg/s)", "Latência p95 (ms)"],
            loc="upper center",
            bbox_to_anchor=(0.5, 1.15),
            ncol=2
        )
    else:
        ax1.legend([bars_thr, bars_lat], ["Vazão (msg/s)", "Latência p95 (ms)"], loc="upper left")

    annotate_bars(ax1, bars_thr, thr_means, thr_ses, offset_index=-0.3, raise_left=True)
    annotate_bars(ax2, bars_lat, lat_means, lat_ses, offset_index=0.3)

    plt.tight_layout()
    plt.savefig(f"graph_{scenario}_thr_lat.png", dpi=300)
    plt.close()

print("Gráficos gerados com sucesso.")