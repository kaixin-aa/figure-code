# 002 · 原始光谱三维曲线图

使用 Matplotlib 绘制多条光谱曲线，以模拟含水率排序并映射为蓝色渐变。随附 CSV 由用户提供，用户已明确说明为模拟数据，仅用于绘图演示，不代表真实实验观测。

[![预览](figures/preview.png)](figures/raw_spectra_3d.png)

[高清 PNG](figures/raw_spectra_3d.png) · [SVG](figures/raw_spectra_3d.svg) · [PDF](figures/raw_spectra_3d.pdf) · [原有成图](figures/original_output.png)

## 运行

建议 Python 3.10 或更高版本。在仓库根目录执行：

```bash
python -m pip install -r examples/002-raw-spectra-3d/requirements.txt
python examples/002-raw-spectra-3d/plot_spectra_3d.py --output-name raw_spectra_3d --formats png svg pdf
```

生成 README 使用的预览：

```bash
python examples/002-raw-spectra-3d/plot_spectra_3d.py --output-name preview --dpi 120
```

直接运行脚本也可，默认输出 `figures/simulated_spectra_raw_spectra_3d.png`。代码使用 Agg 后端，不需要图形界面。默认路径相对于脚本目录；显式传入的相对路径按终端当前目录解析。同名图片会被覆盖，输入 CSV 不会被修改。

## 数据说明

数据文件为 [`data/simulated_spectra.csv`](data/simulated_spectra.csv)，共 640 行、1026 列。

| 字段 | 含义 |
| --- | --- |
| `Seed_ID` | 样本标识，不参与光谱绘制 |
| `Band_*_Wavelength_*` | 1024 个光谱列，列名含波长，范围 887.39–1702.46 nm |
| `Moisture_Content` | 模拟含水率，原值 0.1046–0.2241，默认自动乘 100 显示为 10.46%–22.41% |

纵向光谱值未声明物理单位，图中使用 `Raw spectral value`。脚本直接绘制表内数值，不做平滑、标准化或其他预处理，也不估计统计显著性。

本例提供的是现成模拟数据及其绘图代码，未提供这份 CSV 的生成器或随机种子，因此可从随附数据复现图片，不能重新生成完全相同的 CSV。

## 排序位置与颜色

- 默认 `--y-mode rank`：先按目标值排序，再把每条曲线等距排列；y 轴刻度标注对应的目标值。几何间距表示排序位置，不表示含水率差值。
- `--y-mode actual`：使用目标值作为曲线真实 y 坐标，适合查看数值距离，相近目标值的曲线可能重叠。
- 颜色按目标值连续映射；右侧色条标注模拟含水率。当前图片是三维曲线图，不是拟合曲面。

## 常用参数

| 参数 | 用途 |
| --- | --- |
| `--input` | 替换 CSV / XLSX / XLS 输入 |
| `--target` | 排序和着色列，默认 `Moisture_Content` |
| `--target-unit` | `auto` 自动判断；`ratio` 乘 100；`percent` / `raw` 保持原值 |
| `--target-label` | 自定义目标轴及色条标签 |
| `--y-mode` | `rank` 或 `actual` |
| `--wavelength-min` / `--wavelength-max` | 波长裁剪范围 |
| `--exclude-columns` | 排除其他数值元数据列，以英文逗号分隔 |
| `--elev` / `--azim` | 视角，默认 14° / 55° |
| `--cmap` | 默认 `paper_like`，也可使用 Matplotlib 色图 |
| `--output-dir` / `--output-name` | 输出目录与文件名 |
| `--formats` / `--dpi` | PNG / SVG / PDF / TIFF；位图默认 300 dpi |

使用 Excel 时按格式另外安装 `openpyxl`（XLSX）或 `xlrd`（XLS）。CSV 示例不需要这两项依赖。完整参数可执行 `python examples/002-raw-spectra-3d/plot_spectra_3d.py --help` 查看。

## 整理与验证

上传副本统一了代码、数据和图片的命名，将原脚本中的个人电脑绝对路径改为示例内路径。CSV 内容保持不变；原有成图另存为 `figures/original_output.png`。不收录 Python 缓存。

已使用随附 CSV 运行整理后的脚本，导出 PNG、SVG、PDF 与预览图，并检查标签显示。此处未验证可选 Excel 输入分支。
