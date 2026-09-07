"""模拟数据复刻四联图。运行：python replicate_figure.py
依赖：pip install numpy matplotlib
所有数据均为人工模拟，不能用于医学推断；四个面板为独立的视觉示例。
"""
from pathlib import Path
import csv
import warnings
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

OUT = Path(__file__).resolve().parent
DATA = OUT / "data"
FIGURES = OUT / "figures"
SEED = 20260907


def setup_style():
    fonts = {f.name for f in font_manager.fontManager.ttflist}
    candidates = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC", "WenQuanYi Zen Hei"]
    chinese = next((name for name in candidates if name in fonts), None)
    if chinese is None:
        warnings.warn("未找到中文字体，请安装 Noto Sans CJK SC 或黑体后重新运行。")
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ([chinese] if chinese else []) + ["DejaVu Sans"],
        "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
        "axes.labelsize": 10, "axes.linewidth": 1.1,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.unicode_minus": False, "xtick.direction": "out", "ytick.direction": "out",
        "svg.fonttype": "none", "pdf.fonttype": 42,
        "savefig.facecolor": "white",
    })


def write_csv(name, header, rows):
    with (DATA / name).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def kde(samples, grid, bandwidth=0.42):
    """高斯核密度估计，避免额外依赖 scipy。"""
    z = (grid[:, None] - samples[None, :]) / bandwidth
    return np.exp(-0.5 * z**2).mean(axis=1) / (bandwidth * np.sqrt(2 * np.pi))


def joint_axes(fig, spec, title):
    sub = spec.subgridspec(2, 2, height_ratios=[1, 4], width_ratios=[4, 1], hspace=0.015, wspace=0.015)
    ax = fig.add_subplot(sub[1, 0])
    top = fig.add_subplot(sub[0, 0], sharex=ax)
    right = fig.add_subplot(sub[1, 1], sharey=ax)
    top.set_title(title, loc="left", pad=7)
    top.axis("off")
    right.axis("off")
    return ax, top, right


def scatter_marginals(ax, top, right, x, y, color, histcolor):
    ax.scatter(x, y, s=13, color=color, alpha=0.28, linewidths=0)
    slope, intercept = np.polyfit(x, y, 1)
    xx = np.linspace(x.min(), x.max(), 200)
    ax.plot(xx, slope * xx + intercept, color=color, lw=1.6)
    top.hist(x, bins=28, color=histcolor, edgecolor="white", linewidth=0.4)
    right.hist(y, bins=28, orientation="horizontal", color=histcolor, edgecolor="white", linewidth=0.4)
    ax.axhline(4, color="#ad8984", ls="--", lw=1.2, alpha=0.85)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(exist_ok=True)
    FIGURES.mkdir(exist_ok=True)
    setup_style()
    rng = np.random.default_rng(SEED)
    fig = plt.figure(figsize=(8.4, 6.96), facecolor="white")
    gs = fig.add_gridspec(2, 2, left=0.074, right=0.992, bottom=0.088,
                          top=0.952, height_ratios=[1, 1.30], wspace=0.255, hspace=0.36)

    # a：混合正态分布产生不同形状；各曲线按自身峰值归一化高度。
    ax = fig.add_subplot(gs[0, 0])
    configs = [
        ([3.0, 5.8, 8.6, 10.7], [1.0, 1.1, 0.9, 0.65], [0.25, 0.35, 0.31, 0.09]),
        ([2.7, 4.3, 6.5, 8.7], [0.40, 0.45, 0.52, 0.65], [0.19, 0.23, 0.25, 0.33]),
        ([2.0, 4.0, 6.1, 8.8], [0.95, 0.7, 0.75, 0.90], [0.18, 0.22, 0.34, 0.26]),
        ([1.0, 3.3, 5.3, 7.6], [0.46, 0.74, 0.9, 0.92], [0.14, 0.25, 0.23, 0.38]),
    ]
    colors = ["#d6e6f1", "#a9cbe2", "#85adcb", "#638eb2"]
    grid = np.linspace(0, 13.3, 600)
    all_rows = []
    for i, (means, sigmas, weights) in enumerate(configs):
        component = rng.choice(4, 1600, p=weights)
        sample = rng.normal(np.array(means)[component], np.array(sigmas)[component])
        sample = sample[(sample >= 0) & (sample <= 13.3)]
        density = kde(sample, grid, bandwidth=0.35)
        base = 3 - i
        curve = base + density / density.max() * 0.57
        ax.fill_between(grid, base, curve, color=colors[i], alpha=0.88)
        ax.plot(grid, curve, color=colors[i], lw=1.5)
        all_rows.extend((i + 1, float(value)) for value in sample)
    ax.axvline(4, color="#ad8984", ls="--", lw=1.3)
    ax.text(4.08, 3.41, "4%", color="#ad8984", fontsize=9)
    ax.set(xlim=(0, 13.3), ylim=(-0.18, 3.72), xticks=np.arange(0, 13, 2),
           yticks=[3.1, 2.1, 1.1, 0.1], yticklabels=["第1组", "第2组", "第3组", "第4组"],
           xlabel="Y 染色体浓度（%）")
    ax.tick_params(axis="y", length=0, pad=7)
    ax.set_title("a  BMI 分组的 Y 浓度分布", loc="left", pad=10)
    write_csv("panel_a.csv", ["bmi_group", "y_percent"], all_rows)

    # b：各孕周独立生成样本，误差棒为均值 ± 1.96 × 标准误（近似 95% CI）。
    ax = fig.add_subplot(gs[0, 1])
    weeks = np.arange(12, 25)
    targets = np.array([2.2, 2.8, 3.75, 3.95, 4.9, 5.35, 6.05, 6.75, 7.1, 7.6, 8.35, 8.9, 9.3])
    values = [rng.normal(mu, 0.72, 55) for mu in targets]
    means = np.array([v.mean() for v in values])
    ci = np.array([1.96 * v.std(ddof=1) / np.sqrt(len(v)) for v in values])
    ax.axhline(4, color="#ad8984", ls="--", lw=1.3)
    ax.plot(weeks, means, color="#6d91ac", lw=1.2, zorder=1)
    for i, (week, mean, error) in enumerate(zip(weeks, means, ci)):
        ax.errorbar(week, mean, yerr=error, fmt="o", ms=5, capsize=0,
                    color=plt.cm.Blues(0.16 + 0.80 * i / 12), ecolor="#8ea9b9", elinewidth=1.15)
    ax.set(xlim=(11.4, 24.6), ylim=(1.5, 10), xticks=np.arange(12, 25, 2),
           yticks=np.arange(2, 11), xlabel="孕周（周）", ylabel="Y 浓度均值（%）")
    ax.set_title("b  孕周分箱均值与 95% CI", loc="left", pad=10)
    write_csv("panel_b_raw.csv", ["week", "y_percent"], ((w, float(v)) for w, vals in zip(weeks, values) for v in vals))
    write_csv("panel_b_summary.csv", ["week", "mean", "ci95_half_width", "n"], zip(weeks, means, ci, [55] * len(weeks)))

    # c：孕周与浓度正相关，并保留随机散布。
    ax, top, right = joint_axes(fig, gs[1, 0], "c  孕周与 Y 浓度")
    x = rng.uniform(11, 25, 900)
    y = 1.6 + 0.60 * (x - 11) + rng.normal(0, 1.12, x.size)
    scatter_marginals(ax, top, right, x, y, "#426f96", "#d4e6f2")
    ax.set(xlim=(10.8, 25.2), ylim=(0, 13.5), xticks=np.arange(12.5, 25.1, 2.5),
           yticks=np.arange(0, 13, 2), xlabel="孕周（周）", ylabel="Y 染色体浓度（%）")
    write_csv("panel_c.csv", ["week", "y_percent"], zip(x, y))

    # d：独立构造孕周校正后的浓度，呈现与 BMI 的负相关。
    ax, top, right = joint_axes(fig, gs[1, 1], "d  BMI 与校正浓度")
    bmi = rng.normal(31, 5.2, 1300)
    bmi = bmi[(bmi >= 20) & (bmi <= 47)][:1000]
    adjusted_y = 7.0 - 0.102 * (bmi - 20) + rng.normal(0, 0.97, bmi.size)
    scatter_marginals(ax, top, right, bmi, adjusted_y, "#448985", "#dfefef")
    ax.set(xlim=(20, 47.5), ylim=(-1.2, 9.5), xticks=np.arange(20, 46, 5),
           yticks=np.arange(0, 9, 2), xlabel="BMI（kg/m²）", ylabel="孕周校正 Y 浓度（%）")
    write_csv("panel_d.csv", ["bmi", "adjusted_y_percent"], zip(bmi, adjusted_y))

    for ext in ["png", "svg", "pdf"]:
        fig.savefig(FIGURES / f"replicated_figure.{ext}", dpi=300)
    fig.savefig(FIGURES / "preview.png", dpi=120)
    plt.close(fig)
    print(f"已保存图片和模拟数据到：{OUT}")


if __name__ == "__main__":
    main()
