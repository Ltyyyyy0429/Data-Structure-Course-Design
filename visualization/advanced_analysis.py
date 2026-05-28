"""Generate an advanced analysis dashboard for experiment results.

Run from the project root:
    python3 visualization/advanced_analysis.py

The script reads the official results/experiment_results.csv file and writes
professional report-ready figures to results/analysis/.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"
CSV_PATH = RESULTS_DIR / "experiment_results.csv"
OUTPUT_DIR = RESULTS_DIR / "analysis"
MPL_CACHE_DIR = RESULTS_DIR / ".matplotlib_cache"

MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
import pandas as pd

try:
    from analysis_utils import (
        aggregate_by_strategy,
        ensure_output_dir,
        get_difficulty_order,
        get_scale_order,
        get_strategy_order,
        load_experiment_results,
        normalize_metric,
        save_figure,
        shorten_strategy_name,
        write_html_report,
    )
except ModuleNotFoundError:
    from visualization.analysis_utils import (
        aggregate_by_strategy,
        ensure_output_dir,
        get_difficulty_order,
        get_scale_order,
        get_strategy_order,
        load_experiment_results,
        normalize_metric,
        save_figure,
        shorten_strategy_name,
        write_html_report,
    )


CORE_METRICS = ["total_score", "completed_tasks", "timeout_tasks", "total_distance"]
LOWER_IS_BETTER = {"timeout_tasks", "total_distance", "charging_queue_events", "total_charging_wait_time"}
CHARGING_DASHBOARD_METRICS = [
    "charging_requests",
    "charging_times",
    "charging_queue_events",
    "total_charging_wait_time",
]
FIGURE_DPI = 220


def setup_style() -> None:
    """Use a clean Matplotlib style and a readable system font if available."""

    font_candidates = [
        "PingFang SC",
        "Helvetica Neue",
        "Arial",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    available_fonts = {font.name for font in font_manager.fontManager.ttflist}
    for font_name in font_candidates:
        if font_name in available_fonts:
            plt.rcParams["font.sans-serif"] = [font_name]
            break
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"
    plt.rcParams["axes.edgecolor"] = "#d1d5db"
    plt.rcParams["axes.labelcolor"] = "#374151"
    plt.rcParams["xtick.color"] = "#4b5563"
    plt.rcParams["ytick.color"] = "#4b5563"
    plt.rcParams["grid.color"] = "#e5e7eb"
    plt.rcParams["grid.linestyle"] = "-"
    plt.rcParams["grid.linewidth"] = 0.8


def get_strategy_colors(strategies: list[str]) -> dict[str, str]:
    palette = [
        "#2563eb",
        "#dc2626",
        "#16a34a",
        "#7c3aed",
        "#ea580c",
        "#0891b2",
        "#9333ea",
        "#64748b",
    ]
    return {strategy: palette[index % len(palette)] for index, strategy in enumerate(strategies)}


def clean_output_dir(output_dir: Path) -> None:
    """Remove old generated analysis artifacts."""

    ensure_output_dir(output_dir)
    for pattern in ("*.png", "*.csv", "*.html"):
        for path in output_dir.glob(pattern):
            path.unlink()


def pretty_metric_name(metric: str) -> str:
    names = {
        "total_score": "Total score",
        "completed_tasks": "Completed",
        "timeout_tasks": "Timeout",
        "total_distance": "Distance",
        "charging_times": "Charging",
        "charging_requests": "Requests",
        "charging_queue_events": "Queue events",
        "max_queue_length": "Max queue",
        "total_charging_wait_time": "Wait time",
    }
    return names.get(metric, metric.replace("_", " ").title())


def plot_strategy_kpi_summary(summary: pd.DataFrame, output_dir: Path) -> str:
    """Create a compact KPI overview figure and write the summary CSV."""

    summary_path = output_dir / "summary_table.csv"
    summary.round(3).to_csv(summary_path, index=False)

    display_columns = [
        column
        for column in [
            "strategy_label",
            "total_score",
            "completed_tasks",
            "timeout_tasks",
            "total_distance",
            "charging_times",
            "charging_queue_events",
        ]
        if column in summary.columns
    ]

    table_df = summary[display_columns].copy()
    table_df.columns = [pretty_metric_name(column) if column != "strategy_label" else "Strategy" for column in table_df.columns]
    for column in table_df.columns:
        if column != "Strategy":
            table_df[column] = table_df[column].map(lambda value: f"{value:.1f}")

    fig, (ax_bar, ax_table) = plt.subplots(
        2,
        1,
        figsize=(11.5, 7.2),
        gridspec_kw={"height_ratios": [2.4, 1.7]},
    )

    colors = get_strategy_colors(summary["strategy"].tolist())
    labels = summary["strategy_label"].tolist()
    ax_bar.barh(labels, summary["total_score"], color=[colors[s] for s in summary["strategy"]])
    ax_bar.axvline(0, color="#9ca3af", linewidth=1)
    ax_bar.set_title("Strategy KPI Summary", fontsize=17, weight="bold", pad=14)
    ax_bar.set_xlabel("Average total score")
    ax_bar.grid(axis="x", alpha=0.8)

    ax_table.axis("off")
    table = ax_table.table(
        cellText=table_df.values,
        colLabels=table_df.columns,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9.5)
    table.scale(1.0, 1.35)
    for (row, _column), cell in table.get_celld().items():
        cell.set_edgecolor("#d1d5db")
        if row == 0:
            cell.set_facecolor("#eff6ff")
            cell.set_text_props(weight="bold")
        else:
            cell.set_facecolor("white")

    output_path = output_dir / "strategy_kpi_summary.png"
    save_figure(fig, output_path, FIGURE_DPI)
    return output_path.name


def plot_ranking_heatmap(summary: pd.DataFrame, output_dir: Path) -> str:
    metrics = CORE_METRICS + [metric for metric in ["charging_queue_events"] if metric in summary.columns]
    ranking = pd.DataFrame(index=summary["strategy_label"])
    for metric in metrics:
        ascending = metric in LOWER_IS_BETTER
        ranking[pretty_metric_name(metric)] = summary[metric].rank(method="min", ascending=ascending).astype(int).values

    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    image = ax.imshow(ranking.values, cmap="YlGnBu_r", vmin=1, vmax=max(1, len(summary)))
    ax.set_title("Strategy Ranking Heatmap (1 = best)", fontsize=17, weight="bold", pad=14)
    ax.set_xticks(range(len(ranking.columns)))
    ax.set_xticklabels(ranking.columns, rotation=25, ha="right")
    ax.set_yticks(range(len(ranking.index)))
    ax.set_yticklabels(ranking.index)

    for row in range(ranking.shape[0]):
        for col in range(ranking.shape[1]):
            ax.text(col, row, int(ranking.iloc[row, col]), ha="center", va="center", color="#111827", weight="bold")

    cbar = fig.colorbar(image, ax=ax, fraction=0.035, pad=0.03)
    cbar.set_label("Rank")

    output_path = output_dir / "ranking_heatmap.png"
    save_figure(fig, output_path, FIGURE_DPI)
    return output_path.name


def plot_score_distance_tradeoff(df: pd.DataFrame, output_dir: Path) -> str:
    strategies = get_strategy_order(df)
    difficulties = get_difficulty_order(df)
    colors = get_strategy_colors(strategies)
    markers = ["o", "s", "^", "D", "P", "X"]

    fig, ax = plt.subplots(figsize=(10.5, 6.6))
    max_completed = max(float(df["completed_tasks"].max()), 1.0)
    for strategy in strategies:
        for difficulty_index, difficulty in enumerate(difficulties):
            sub = df[(df["strategy"] == strategy) & (df["difficulty"] == difficulty)]
            if sub.empty:
                continue
            sizes = 45 + 180 * (sub["completed_tasks"] / max_completed)
            ax.scatter(
                sub["total_distance"],
                sub["total_score"],
                s=sizes,
                color=colors[strategy],
                marker=markers[difficulty_index % len(markers)],
                alpha=0.72,
                edgecolor="white",
                linewidth=0.8,
            )

    strategy_handles = [
        Line2D([0], [0], marker="o", linestyle="", color=colors[strategy], label=shorten_strategy_name(strategy))
        for strategy in strategies
    ]
    difficulty_handles = [
        Line2D([0], [0], marker=markers[index % len(markers)], linestyle="", color="#374151", label=difficulty)
        for index, difficulty in enumerate(difficulties)
    ]
    legend1 = ax.legend(handles=strategy_handles, title="Strategy", loc="upper right")
    ax.add_artist(legend1)
    ax.legend(handles=difficulty_handles, title="Difficulty", loc="lower left")
    ax.set_title("Score vs Distance Trade-off", fontsize=17, weight="bold", pad=14)
    ax.set_xlabel("Total distance")
    ax.set_ylabel("Total score")
    ax.grid(True, alpha=0.7)

    output_path = output_dir / "score_distance_tradeoff.png"
    save_figure(fig, output_path, FIGURE_DPI)
    return output_path.name


def plot_trend(
    df: pd.DataFrame,
    output_dir: Path,
    group_column: str,
    group_order: list[str],
    metric: str,
    file_name: str,
    title: str,
) -> str:
    strategies = get_strategy_order(df)
    colors = get_strategy_colors(strategies)
    pivot = (
        df.pivot_table(index=group_column, columns="strategy", values=metric, aggfunc="mean")
        .reindex(group_order)
    )

    fig, ax = plt.subplots(figsize=(10.0, 5.8))
    x_positions = range(len(group_order))
    for strategy in strategies:
        if strategy not in pivot.columns:
            continue
        ax.plot(
            list(x_positions),
            pivot[strategy].tolist(),
            marker="o",
            linewidth=2.4,
            color=colors[strategy],
            label=shorten_strategy_name(strategy),
        )

    ax.set_title(title, fontsize=17, weight="bold", pad=14)
    ax.set_xlabel(group_column)
    ax.set_ylabel(pretty_metric_name(metric))
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(group_order)
    ax.grid(True, axis="y", alpha=0.75)
    ax.legend(loc="best")

    output_path = output_dir / file_name
    save_figure(fig, output_path, FIGURE_DPI)
    return output_path.name


def plot_charging_pressure_dashboard(summary: pd.DataFrame, output_dir: Path) -> str | None:
    metrics = [metric for metric in CHARGING_DASHBOARD_METRICS if metric in summary.columns]
    if not metrics:
        return None

    strategies = summary["strategy"].tolist()
    labels = summary["strategy_label"].tolist()
    colors = get_strategy_colors(strategies)

    fig, axes = plt.subplots(2, 2, figsize=(12, 7.4))
    axes = axes.flatten()
    for index, metric in enumerate(metrics[:4]):
        ax = axes[index]
        ax.bar(labels, summary[metric], color=[colors[strategy] for strategy in strategies])
        ax.set_title(pretty_metric_name(metric), fontsize=13, weight="bold")
        ax.grid(axis="y", alpha=0.7)
        ax.tick_params(axis="x", rotation=20)
    for index in range(len(metrics), len(axes)):
        axes[index].axis("off")

    fig.suptitle("Charging Pressure Dashboard (sum by strategy)", fontsize=17, weight="bold")
    output_path = output_dir / "charging_pressure_dashboard.png"
    save_figure(fig, output_path, FIGURE_DPI)
    return output_path.name


def plot_strategy_radar(summary: pd.DataFrame, output_dir: Path) -> str:
    radar_df = pd.DataFrame({
        "strategy": summary["strategy"],
        "strategy_label": summary["strategy_label"],
        "Score": normalize_metric(summary["total_score"], True),
        "Completed": normalize_metric(summary["completed_tasks"], True),
        "Low Timeout": normalize_metric(summary["timeout_tasks"], False),
        "Low Distance": normalize_metric(summary["total_distance"], False),
    })
    if "charging_queue_events" in summary.columns:
        radar_df["Low Charging Pressure"] = normalize_metric(summary["charging_queue_events"], False)
    elif "total_charging_wait_time" in summary.columns:
        radar_df["Low Charging Pressure"] = normalize_metric(summary["total_charging_wait_time"], False)

    metric_labels = [column for column in radar_df.columns if column not in {"strategy", "strategy_label"}]
    angles = [2 * math.pi * index / len(metric_labels) for index in range(len(metric_labels))]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8.6, 8.0), subplot_kw={"projection": "polar"})
    colors = get_strategy_colors(radar_df["strategy"].tolist())
    for _, row in radar_df.iterrows():
        values = [float(row[label]) for label in metric_labels]
        values += values[:1]
        ax.plot(angles, values, linewidth=2.2, color=colors[row["strategy"]], label=row["strategy_label"])
        ax.fill(angles, values, color=colors[row["strategy"]], alpha=0.09)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metric_labels)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0.25", "0.50", "0.75", "1.00"])
    ax.set_title("Normalized Strategy Radar", fontsize=17, weight="bold", pad=18)
    ax.legend(loc="upper right", bbox_to_anchor=(1.22, 1.12))

    output_path = output_dir / "strategy_radar.png"
    save_figure(fig, output_path, FIGURE_DPI)
    return output_path.name


def find_pareto_frontier(df: pd.DataFrame) -> pd.DataFrame:
    """Return points not dominated by another higher-score and lower-distance run."""

    frontier_rows = []
    for index, row in df.iterrows():
        score = float(row["total_score"])
        distance = float(row["total_distance"])
        dominated = False
        for other_index, other in df.iterrows():
            if index == other_index:
                continue
            other_score = float(other["total_score"])
            other_distance = float(other["total_distance"])
            at_least_as_good = other_score >= score and other_distance <= distance
            strictly_better = other_score > score or other_distance < distance
            if at_least_as_good and strictly_better:
                dominated = True
                break
        if not dominated:
            frontier_rows.append(row)
    if not frontier_rows:
        return pd.DataFrame(columns=df.columns)
    return pd.DataFrame(frontier_rows).sort_values(["total_distance", "total_score"], ascending=[True, False])


def plot_pareto_frontier(df: pd.DataFrame, output_dir: Path) -> str:
    strategies = get_strategy_order(df)
    colors = get_strategy_colors(strategies)
    frontier = find_pareto_frontier(df)
    frontier = frontier.sort_values("total_distance")

    fig, ax = plt.subplots(figsize=(10.3, 6.2))
    for strategy in strategies:
        sub = df[df["strategy"] == strategy]
        ax.scatter(
            sub["total_distance"],
            sub["total_score"],
            s=70,
            color=colors[strategy],
            alpha=0.65,
            edgecolor="white",
            linewidth=0.8,
            label=shorten_strategy_name(strategy),
        )
    if not frontier.empty:
        ax.plot(
            frontier["total_distance"],
            frontier["total_score"],
            color="#111827",
            linewidth=2.4,
            linestyle="--",
            label="Pareto frontier",
        )
        for _, row in frontier.iterrows():
            ax.annotate(
                shorten_strategy_name(row["strategy"]),
                (row["total_distance"], row["total_score"]),
                textcoords="offset points",
                xytext=(6, 6),
                fontsize=8,
            )

    ax.set_title("Pareto Frontier: High Score and Low Distance", fontsize=17, weight="bold", pad=14)
    ax.set_xlabel("Total distance (lower is better)")
    ax.set_ylabel("Total score (higher is better)")
    ax.grid(True, alpha=0.75)
    ax.legend(loc="best")

    output_path = output_dir / "pareto_frontier.png"
    save_figure(fig, output_path, FIGURE_DPI)
    return output_path.name


def main() -> None:
    setup_style()
    df = load_experiment_results(CSV_PATH)
    output_dir = ensure_output_dir(OUTPUT_DIR)
    clean_output_dir(output_dir)

    strategy_order = get_strategy_order(df)
    difficulty_order = get_difficulty_order(df)
    scale_order = get_scale_order(df)
    summary = aggregate_by_strategy(df)

    figures: list[tuple[str, str, str]] = []
    figures.append((
        plot_strategy_kpi_summary(summary, output_dir),
        "KPI summary by strategy",
        "每个策略的核心 KPI 汇总：收益、完成数、超时数和里程使用平均值；充电请求、充电次数、排队事件和等待时间使用合计值；最大队列长度使用该策略所有实验中的最大值。",
    ))
    figures.append((
        plot_ranking_heatmap(summary, output_dir),
        "Ranking heatmap",
        "按策略聚合后的指标排名，1 表示最好。收益和完成数越大越好；超时、里程和排队事件越小越好。",
    ))
    figures.append((
        plot_score_distance_tradeoff(df, output_dir),
        "Score-distance trade-off",
        "每个点代表一组实验；横轴为总里程，纵轴为总得分，颜色表示策略，点形状表示难度，点大小表示完成任务数。",
    ))
    figures.append((
        plot_trend(
            df,
            output_dir,
            "difficulty",
            difficulty_order,
            "total_score",
            "difficulty_trend.png",
            "Average Score by Difficulty",
        ),
        "Difficulty trend",
        "按 easy -> medium -> hard 顺序展示各策略平均总得分随难度变化的趋势。",
    ))
    figures.append((
        plot_trend(
            df,
            output_dir,
            "difficulty",
            difficulty_order,
            "completed_tasks",
            "difficulty_completion_trend.png",
            "Average Completed Tasks by Difficulty",
        ),
        "Difficulty completion trend",
        "按 easy -> medium -> hard 顺序展示各策略平均完成任务数随难度变化的趋势。",
    ))
    figures.append((
        plot_trend(
            df,
            output_dir,
            "scale",
            scale_order,
            "total_score",
            "scale_trend.png",
            "Average Score by Scale",
        ),
        "Scale trend",
        "按 small -> medium -> large -> extra_large 顺序展示各策略平均总得分随规模变化的趋势。",
    ))

    charging_figure = plot_charging_pressure_dashboard(summary, output_dir)
    if charging_figure:
        figures.append((
            charging_figure,
            "Charging pressure dashboard",
            "充电压力指标按策略合计：Requests 来自 charging_requests，Charging 来自 charging_times，Queue events 来自 charging_queue_events，Wait time 来自 total_charging_wait_time。",
        ))

    figures.append((
        plot_strategy_radar(summary, output_dir),
        "Normalized radar chart",
        "所有指标归一化到 0-1，数值越大代表表现越好；Low Timeout、Low Distance 和 Low Charging Pressure 已做反向归一化。",
    ))
    figures.append((
        plot_pareto_frontier(df, output_dir),
        "Pareto frontier",
        "Pareto 前沿表示没有被其他实验同时以更高得分和更低里程支配的结果点。",
    ))

    write_html_report(
        output_dir / "index.html",
        CSV_PATH.relative_to(PROJECT_ROOT),
        df,
        summary,
        figures,
    )

    print(f"Loaded data from: {CSV_PATH}")
    print(f"Rows: {len(df)}")
    print(f"Strategies: {[shorten_strategy_name(s) for s in strategy_order]}")
    print(f"Difficulties: {difficulty_order}")
    print(f"Scales: {scale_order}")
    print(f"Output directory: {output_dir}")
    print("Generated files:")
    for file_name, _caption, _description in figures:
        print(f"- {file_name}")
    print("- summary_table.csv")
    print("- index.html")


if __name__ == "__main__":
    main()
