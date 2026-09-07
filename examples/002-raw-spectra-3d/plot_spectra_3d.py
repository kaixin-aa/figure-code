#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""可复用的原始光谱三维绘图脚本。随附数据为用户提供的模拟数据。

特点
----
1. 只绘制原始光谱，不调用任何预处理方法或项目内模块。
2. 支持 CSV、XLSX 和 XLS 文件。
3. 优先从列名中的 ``Wavelength``/``nm`` 自动识别光谱列及波长。
4. 可直接修改下方“常用配置”，也可通过命令行临时覆盖配置。

最简单的用法
------------
直接运行（使用下方 DEFAULT_DATA_FILE）::

    python plot_spectra_3d.py

临时更换数据文件::

    python plot_spectra_3d.py --input "另一份数据.xlsx"

指定目标列、工作表和波长范围::

    python plot_spectra_3d.py --input "data.xlsx" \
        --sheet Sheet1 --target Moisture_Content --wavelength-min 900 \
        --wavelength-max 1700
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, Normalize


# ============================================================================
# 常用配置：日后通常只需修改 DEFAULT_DATA_FILE（或运行时使用 --input）
# ============================================================================
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_FILE = BASE_DIR / "data" / "simulated_spectra.csv"
DEFAULT_TARGET_COLUMN = "Moisture_Content"
DEFAULT_OUTPUT_DIR = BASE_DIR / "figures"

# auto：目标值绝对值不超过 1.5 时按比例值处理并乘以 100，否则保持原值。
# ratio：始终乘以 100；percent/raw：保持原值。
DEFAULT_TARGET_UNIT = "auto"

# None 表示不裁剪波长，使用输入表内识别到的全部原始光谱波段。
DEFAULT_WAVELENGTH_MIN: float | None = None
DEFAULT_WAVELENGTH_MAX: float | None = None

# rank 会将曲线按目标值排序后等距展开，减少重叠；actual 使用真实目标值位置。
DEFAULT_Y_MODE = "rank"
DEFAULT_CMAP = "paper_like"
DEFAULT_FORMATS = ("png",)
DEFAULT_DPI = 300

ELEV = 14.0
AZIM = 55.0
LINE_WIDTH = 0.90
LINE_ALPHA = 0.32
Y_TICK_COUNT = 6
Z_PAD_RATIO = 0.05


PAPER_LIKE_CMAP = LinearSegmentedColormap.from_list(
    "paper_like",
    ["#002666", "#2c568c", "#5985b2", "#85b5d8", "#b2e5ff"],
    N=256,
)

WAVELENGTH_PATTERN = re.compile(
    r"(?:wavelength|wave(?:length)?|nm)[^0-9+-]*([+-]?\d+(?:\.\d+)?)",
    flags=re.IGNORECASE,
)
NUMERIC_HEADER_PATTERN = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
ID_LIKE_PATTERN = re.compile(
    r"(?:^|[_\s-])(id|index|sample|seed|label)(?:$|[_\s-])",
    flags=re.IGNORECASE,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="读取 CSV/Excel 中的原始光谱并生成三维光谱图。"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_DATA_FILE,
        help=f"输入 CSV/XLSX/XLS 文件（默认：{DEFAULT_DATA_FILE}）。",
    )
    parser.add_argument(
        "--sheet",
        default="0",
        help="Excel 工作表名称或从 0 开始的序号；读取 CSV 时忽略（默认：0）。",
    )
    parser.add_argument(
        "--target",
        default=DEFAULT_TARGET_COLUMN,
        help=f"用于排序和着色的目标列（默认：{DEFAULT_TARGET_COLUMN}）。",
    )
    parser.add_argument(
        "--target-label",
        default=None,
        help="图中 y 轴名称；省略时根据目标列与单位自动生成。",
    )
    parser.add_argument(
        "--target-unit",
        choices=("auto", "ratio", "percent", "raw"),
        default=DEFAULT_TARGET_UNIT,
        help="目标值单位。ratio 会乘 100；percent/raw 保持不变（默认：auto）。",
    )
    parser.add_argument(
        "--exclude-columns",
        default="",
        help="额外排除的非光谱列，多个列名用英文逗号分隔。",
    )
    parser.add_argument(
        "--wavelength-min",
        type=float,
        default=DEFAULT_WAVELENGTH_MIN,
        help="可选的最小波长；省略则不裁剪下限。",
    )
    parser.add_argument(
        "--wavelength-max",
        type=float,
        default=DEFAULT_WAVELENGTH_MAX,
        help="可选的最大波长；省略则不裁剪上限。",
    )
    parser.add_argument(
        "--y-mode",
        choices=("rank", "actual"),
        default=DEFAULT_Y_MODE,
        help="rank 等距展开曲线，actual 使用真实目标值位置（默认：rank）。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"输出目录（默认：{DEFAULT_OUTPUT_DIR}）。",
    )
    parser.add_argument(
        "--output-name",
        default=None,
        help="不含扩展名的输出文件名（默认：输入文件名_raw_spectra_3d）。",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=("png", "svg", "pdf", "tiff"),
        default=list(DEFAULT_FORMATS),
        help="输出格式，可同时指定多个（默认：png）。",
    )
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI, help="位图分辨率。")
    parser.add_argument("--cmap", default=DEFAULT_CMAP, help="Matplotlib 色图名称。")
    parser.add_argument("--elev", type=float, default=ELEV, help="三维视角仰角。")
    parser.add_argument("--azim", type=float, default=AZIM, help="三维视角方位角。")
    return parser


def parse_sheet(value: str) -> str | int:
    """将纯整数工作表参数转为序号，其余内容作为工作表名称。"""
    try:
        return int(value)
    except ValueError:
        return value


def read_table(data_file: Path, sheet: str | int = 0) -> pd.DataFrame:
    """读取 CSV 或 Excel 表格。"""
    data_file = data_file.expanduser().resolve()
    if not data_file.is_file():
        raise FileNotFoundError(f"数据文件不存在：{data_file}")

    suffix = data_file.suffix.lower()
    if suffix == ".csv":
        try:
            return pd.read_csv(data_file, encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(data_file, encoding="gbk")
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(data_file, sheet_name=sheet)
    raise ValueError(f"不支持的文件格式：{suffix}；请使用 CSV、XLSX 或 XLS。")


def wavelength_from_header(column: object) -> float | None:
    """从常见光谱列名中提取波长，不把 Seed_ID 等数字误当成波长。"""
    if isinstance(column, (int, float)) and not isinstance(column, bool):
        return float(column)

    name = str(column).strip()
    if NUMERIC_HEADER_PATTERN.fullmatch(name):
        return float(name)

    match = WAVELENGTH_PATTERN.search(name)
    if match:
        return float(match.group(1))
    return None


def detect_spectral_columns(
    df: pd.DataFrame,
    target_column: str,
    excluded_columns: Sequence[str] = (),
) -> tuple[list[object], np.ndarray, str]:
    """识别光谱列，返回列名、波长和识别方式说明。"""
    excluded = {target_column, *excluded_columns}
    parsed: list[tuple[object, float]] = []

    for column in df.columns:
        if str(column) in excluded or column in excluded:
            continue
        wavelength = wavelength_from_header(column)
        if wavelength is not None:
            parsed.append((column, wavelength))

    if len(parsed) >= 2:
        parsed.sort(key=lambda item: item[1])
        columns = [column for column, _ in parsed]
        wavelengths = np.asarray([wave for _, wave in parsed], dtype=float)
        return columns, wavelengths, "从列名自动提取波长"

    # 对没有波长列名的表，退回到所有数值列，并以波段序号作为横坐标。
    fallback_columns: list[object] = []
    for column in df.columns:
        name = str(column)
        if name in excluded or column in excluded or ID_LIKE_PATTERN.search(name):
            continue
        converted = pd.to_numeric(df[column], errors="coerce")
        if converted.notna().all():
            fallback_columns.append(column)

    if len(fallback_columns) < 2:
        raise ValueError(
            "无法识别至少两个光谱列。建议将光谱列命名为 "
            "'Band_1_Wavelength_900.0' 或直接使用数值波长作为列名。"
        )

    wavelengths = np.arange(1, len(fallback_columns) + 1, dtype=float)
    return fallback_columns, wavelengths, "未找到波长列名，使用波段序号"


def load_raw_spectra(
    data_file: Path,
    sheet: str | int,
    target_column: str,
    excluded_columns: Sequence[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[object], str]:
    """加载原始光谱矩阵、目标值和波长。"""
    df = read_table(data_file, sheet=sheet)
    if target_column not in df.columns:
        preview = ", ".join(map(str, df.columns[:10]))
        raise ValueError(
            f"数据中未找到目标列 '{target_column}'。前 10 个列名为：{preview}"
        )

    spectral_columns, wavelengths, detection_note = detect_spectral_columns(
        df,
        target_column=target_column,
        excluded_columns=excluded_columns,
    )

    spectra_df = df[spectral_columns].apply(pd.to_numeric, errors="coerce")
    target_series = pd.to_numeric(df[target_column], errors="coerce")

    invalid_spectra = ~np.isfinite(spectra_df.to_numpy(dtype=float))
    invalid_target = ~np.isfinite(target_series.to_numpy(dtype=float))
    if invalid_spectra.any() or invalid_target.any():
        bad_spectral_rows = int(np.any(invalid_spectra, axis=1).sum())
        bad_target_rows = int(invalid_target.sum())
        raise ValueError(
            "数据含缺失值或非数值："
            f"光谱异常行 {bad_spectral_rows}，目标列异常行 {bad_target_rows}。"
        )

    return (
        spectra_df.to_numpy(dtype=float),
        target_series.to_numpy(dtype=float),
        wavelengths,
        spectral_columns,
        detection_note,
    )


def crop_wavelengths(
    spectra: np.ndarray,
    wavelengths: np.ndarray,
    wavelength_min: float | None,
    wavelength_max: float | None,
) -> tuple[np.ndarray, np.ndarray]:
    """按可选上下限裁剪原始光谱波段。"""
    lower = -np.inf if wavelength_min is None else wavelength_min
    upper = np.inf if wavelength_max is None else wavelength_max
    if lower > upper:
        raise ValueError("wavelength-min 不能大于 wavelength-max。")

    mask = (wavelengths >= lower) & (wavelengths <= upper)
    if not np.any(mask):
        raise ValueError(
            f"波长范围 [{lower}, {upper}] 内没有数据；"
            f"当前数据范围为 [{wavelengths.min()}, {wavelengths.max()}]。"
        )
    return spectra[:, mask], wavelengths[mask]


def scale_target(values: np.ndarray, unit: str) -> tuple[np.ndarray, bool]:
    """按配置处理目标值单位，返回转换后数值及是否转换成百分数。"""
    if unit == "ratio":
        return values * 100.0, True
    if unit in {"percent", "raw"}:
        return values.copy(), unit == "percent"

    should_scale = float(np.nanmax(np.abs(values))) <= 1.5
    return (values * 100.0, True) if should_scale else (values.copy(), False)


def make_target_label(column: str, requested_label: str | None, is_percent: bool) -> str:
    if requested_label:
        return requested_label
    label = column.replace("_", " ").strip()
    if is_percent:
        label += " (%)"
    return label[:1].upper() + label[1:]


def setup_style() -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    matplotlib.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Arial",
                "Helvetica",
                "DejaVu Sans",
                "Microsoft YaHei",
                "SimHei",
            ],
            "axes.unicode_minus": False,
            "axes.facecolor": "white",
            "figure.facecolor": "white",
            "axes.linewidth": 0.8,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )


def resolve_cmap(cmap_name: str):
    if cmap_name.lower() == "paper_like":
        return PAPER_LIKE_CMAP
    return matplotlib.colormaps.get_cmap(cmap_name)


def style_3d_axis(ax: plt.Axes) -> None:
    background = (1.0, 1.0, 1.0, 1.0)
    pane_edge = (0.55, 0.55, 0.55, 1.0)
    grid_color = (0.82, 0.82, 0.82, 0.65)
    axis_color = (0.35, 0.35, 0.35, 1.0)
    ax.set_facecolor(background)

    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor(background)
        axis.pane.set_edgecolor(pane_edge)
        axis.pane.fill = True
        axis._axinfo["grid"]["color"] = grid_color

    ax.xaxis.line.set_color(axis_color)
    ax.yaxis.line.set_color(axis_color)
    ax.zaxis.line.set_color(axis_color)
    ax.tick_params(axis="both", which="major", labelsize=8)
    ax.tick_params(axis="z", which="major", labelsize=8)
    ax.set_box_aspect((1.3, 1.3, 1.0))


def dynamic_limits(values: np.ndarray, pad_ratio: float = Z_PAD_RATIO) -> tuple[float, float]:
    vmin = float(np.min(values))
    vmax = float(np.max(values))
    if np.isclose(vmin, vmax):
        pad = max(abs(vmin) * pad_ratio, 1e-6)
    else:
        pad = (vmax - vmin) * pad_ratio
    return vmin - pad, vmax + pad


def linear_ticks(vmin: float, vmax: float, count: int) -> np.ndarray:
    if np.isclose(vmin, vmax):
        return np.asarray([vmin])
    return np.linspace(vmin, vmax, min(count, max(2, count)))


def display_positions(target_sorted: np.ndarray, mode: str) -> np.ndarray:
    if mode == "actual":
        return target_sorted.copy()
    return np.arange(len(target_sorted), dtype=float)


def y_ticks_and_labels(
    display_y: np.ndarray,
    target_sorted: np.ndarray,
    count: int = Y_TICK_COUNT,
) -> tuple[np.ndarray, list[str]]:
    if len(display_y) == 1:
        return display_y.copy(), [f"{target_sorted[0]:.2f}"]
    indices = np.unique(np.linspace(0, len(display_y) - 1, count).round().astype(int))
    return display_y[indices], [f"{target_sorted[i]:.2f}" for i in indices]


def plot_raw_spectra_3d(
    spectra: np.ndarray,
    target: np.ndarray,
    wavelengths: np.ndarray,
    target_label: str,
    y_mode: str,
    cmap_name: str,
    elev: float,
    azim: float,
) -> plt.Figure:
    """创建原始光谱三维图，不修改输入光谱数值。"""
    order = np.argsort(target, kind="stable")
    spectra_sorted = spectra[order]
    target_sorted = target[order]
    display_y = display_positions(target_sorted, y_mode)

    cmap = resolve_cmap(cmap_name).reversed()
    target_min = float(target_sorted.min())
    target_max = float(target_sorted.max())
    if np.isclose(target_min, target_max):
        norm = Normalize(vmin=target_min - 0.5, vmax=target_max + 0.5)
    else:
        norm = Normalize(vmin=target_min, vmax=target_max)

    fig = plt.figure(figsize=(8.4, 5.4), dpi=150)
    ax = fig.add_subplot(1, 1, 1, projection="3d")

    for index in np.argsort(display_y)[::-1]:
        ax.plot(
            wavelengths,
            np.full_like(wavelengths, display_y[index], dtype=float),
            spectra_sorted[index],
            color=cmap(norm(target_sorted[index])),
            linewidth=LINE_WIDTH,
            alpha=LINE_ALPHA,
        )

    x_min, x_max = float(wavelengths.min()), float(wavelengths.max())
    y_min, y_max = float(display_y.min()), float(display_y.max())
    if np.isclose(y_min, y_max):
        y_min, y_max = y_min - 0.5, y_max + 0.5
    z_min, z_max = dynamic_limits(spectra_sorted)

    ax.set_xlabel("Wavelength (nm)", labelpad=8, fontsize=9)
    ax.set_ylabel(target_label, labelpad=10, fontsize=9)
    # 3D z 轴标签在部分 Matplotlib 版本中会被 tight bbox 错误裁切；
    # 使用轴坐标放置等价的二维标签，保证导出图片中完整可见。
    ax.set_zlabel("")
    ax.text2D(
        -0.075,
        0.50,
        "Raw spectral value",
        transform=ax.transAxes,
        rotation=90,
        va="center",
        ha="center",
        fontsize=9,
    )
    ax.set_xlim(x_max, x_min)
    ax.set_ylim(y_max, y_min)
    ax.set_zlim(z_min, z_max)
    ax.set_xticks(linear_ticks(x_min, x_max, 4))

    tick_positions, tick_labels = y_ticks_and_labels(display_y, target_sorted)
    ax.set_yticks(tick_positions)
    ax.set_yticklabels(tick_labels)
    ax.set_zticks(linear_ticks(z_min, z_max, 6))
    ax.view_init(elev=elev, azim=azim)
    style_3d_axis(ax)

    scalar_mappable = cm.ScalarMappable(norm=norm, cmap=cmap)
    scalar_mappable.set_array([])
    colorbar = fig.colorbar(
        scalar_mappable,
        ax=ax,
        fraction=0.015,
        pad=0.01,
        shrink=0.52,
    )
    colorbar.set_label(target_label, fontsize=9)
    colorbar.set_ticks(linear_ticks(target_min, target_max, Y_TICK_COUNT))
    colorbar.ax.invert_yaxis()
    colorbar.ax.tick_params(labelsize=8)
    colorbar.outline.set_linewidth(0.8)
    return fig


def save_figure(
    fig: plt.Figure,
    output_dir: Path,
    output_name: str,
    formats: Sequence[str],
    dpi: int,
) -> list[Path]:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for file_format in dict.fromkeys(formats):
        path = output_dir / f"{output_name}.{file_format}"
        save_kwargs = {"bbox_inches": "tight"}
        if file_format in {"png", "tiff"}:
            save_kwargs["dpi"] = dpi
        fig.savefig(path, **save_kwargs)
        saved.append(path)
    return saved


def main() -> None:
    args = build_parser().parse_args()
    input_file = args.input.expanduser().resolve()
    excluded_columns = [
        item.strip() for item in args.exclude_columns.split(",") if item.strip()
    ]

    spectra, target, wavelengths, spectral_columns, detection_note = load_raw_spectra(
        data_file=input_file,
        sheet=parse_sheet(args.sheet),
        target_column=args.target,
        excluded_columns=excluded_columns,
    )
    spectra, wavelengths = crop_wavelengths(
        spectra,
        wavelengths,
        wavelength_min=args.wavelength_min,
        wavelength_max=args.wavelength_max,
    )
    target_for_plot, is_percent = scale_target(target, args.target_unit)
    target_label = make_target_label(args.target, args.target_label, is_percent)

    setup_style()
    fig = plot_raw_spectra_3d(
        spectra=spectra,
        target=target_for_plot,
        wavelengths=wavelengths,
        target_label=target_label,
        y_mode=args.y_mode,
        cmap_name=args.cmap,
        elev=args.elev,
        azim=args.azim,
    )
    output_name = args.output_name or f"{input_file.stem}_raw_spectra_3d"
    saved_files = save_figure(
        fig,
        output_dir=args.output_dir,
        output_name=output_name,
        formats=args.formats,
        dpi=args.dpi,
    )
    plt.close(fig)

    print("=== 原始光谱绘图完成 ===")
    print(f"输入文件：{input_file}")
    print(f"目标列：{args.target}")
    print(f"样本数：{spectra.shape[0]}")
    print(f"光谱列数：{len(spectral_columns)}；绘图波段数：{spectra.shape[1]}")
    print(f"波长范围：{wavelengths.min():.2f}–{wavelengths.max():.2f}")
    print(f"光谱列识别：{detection_note}")
    print("预处理：无（直接使用输入表中的原始光谱值）")
    print("输出文件：")
    for path in saved_files:
        print(f"  - {path}")


if __name__ == "__main__":
    main()
