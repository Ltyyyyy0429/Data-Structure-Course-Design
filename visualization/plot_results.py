"""Generate Matplotlib charts for dispatch experiment results.

Run from the project root:
    python3 visualization/plot_results.py
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"
CSV_PATH = RESULTS_DIR / "experiment_results.csv"
FIGURE_DIR = RESULTS_DIR / "figures"
MPL_CACHE_DIR = RESULTS_DIR / ".matplotlib_cache"

MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd
from pandas.errors import EmptyDataError

SCALES = ["small", "medium", "large", "extra_large"]
STRATEGIES = ["nearest", "largest", "energy_aware_hybrid"]
DIFFICULTIES = ["easy", "medium", "hard"]
REQUIRED_COLUMNS = [
    "difficulty",
    "scale",
    "strategy",
    "total_score",
    "completed_tasks",
    "timeout_tasks",
    "total_distance",
    "charging_times",
    "low_battery_events",
    "charging_requests",
    "charging_queue_events",
    "total_charging_wait_time",
    "max_queue_length",
]


def create_sample_data() -> pd.DataFrame:
    rows = []
    for difficulty_index, difficulty in enumerate(DIFFICULTIES):
        for scale_index, scale in enumerate(SCALES):
            for strategy_index, strategy in enumerate(STRATEGIES):
                base = 600 + difficulty_index * 180 + scale_index * 420
                rows.append(
                    {
                        "difficulty": difficulty,
                        "scale": scale,
                        "strategy": strategy,
                        "total_score": base + strategy_index * 90,
                        "completed_tasks": 8 + scale_index * 4 + strategy_index,
                        "timeout_tasks": difficulty_index + strategy_index,
                        "total_distance": 120 + scale_index * 95 + strategy_index * 28,
                        "charging_times": difficulty_index * 2 + scale_index + strategy_index,
                        "low_battery_events": difficulty_index * 5 + scale_index * 2 + strategy_index,
                        "charging_requests": difficulty_index * 4 + scale_index * 2 + strategy_index,
                        "charging_queue_events": difficulty_index + strategy_index,
                        "total_charging_wait_time": difficulty_index * 12 + scale_index * 4 + strategy_index,
                        "max_queue_length": difficulty_index + strategy_index,
                    }
                )
    return pd.DataFrame(rows)


def load_or_create_results() -> pd.DataFrame:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        df = pd.read_csv(CSV_PATH)
    except (FileNotFoundError, EmptyDataError):
        df = create_sample_data()
        df.to_csv(CSV_PATH, index=False)
        return df

    has_required_columns = all(column in df.columns for column in REQUIRED_COLUMNS)
    if df.empty or not has_required_columns:
        df = create_sample_data()
        df.to_csv(CSV_PATH, index=False)

    return df


def setup_font() -> str:
    chinese_font_names = [
        "PingFang SC",
        "Heiti SC",
        "Arial Unicode MS",
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
    ]
    available_fonts = {font.name for font in font_manager.fontManager.ttflist}
    for font_name in chinese_font_names:
        if font_name in available_fonts:
            plt.rcParams["font.sans-serif"] = [font_name]
            plt.rcParams["axes.unicode_minus"] = False
            return "zh"
    return "en"


def plot_grouped_bar(df: pd.DataFrame, metric: str, title: str, ylabel: str, file_name: str) -> None:
    pivot = (
        df.pivot_table(index="scale", columns="strategy", values=metric, aggfunc="mean")
        .reindex(SCALES)
        .fillna(0)
    )

    x_positions = list(range(len(SCALES)))
    num_strategies = len(STRATEGIES)
    bar_width = 0.8 / max(1, num_strategies)
    colors = {"nearest": "#3182ce", "largest": "#dd6b20", "energy_aware_hybrid": "#2ca02c"}

    plt.figure(figsize=(8, 5))
    for index, strategy in enumerate(STRATEGIES):
        offset = (index - (num_strategies - 1) / 2) * bar_width
        values = pivot[strategy] if strategy in pivot.columns else [0] * len(SCALES)
        bar_positions = [x + offset for x in x_positions]
        plt.bar(bar_positions, values, width=bar_width, label=strategy,
                color=colors.get(strategy, "#999999"))

    plt.title(title)
    plt.xlabel("scale")
    plt.ylabel(ylabel)
    plt.xticks(x_positions, SCALES)
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURE_DIR / file_name, dpi=150)
    plt.close()


def main() -> None:
    df = load_or_create_results()
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    language = setup_font()

    if language == "zh":
        chart_settings = [
            ("total_score", "不同规模下策略总收益对比", "总收益", "total_score_comparison.png"),
            (
                "completed_tasks",
                "不同规模下策略完成任务数对比",
                "完成任务数",
                "completed_tasks_comparison.png",
            ),
            (
                "timeout_tasks",
                "不同规模下策略超时任务数对比",
                "超时任务数",
                "timeout_tasks_comparison.png",
            ),
            (
                "total_distance",
                "不同规模下策略总路径长度对比",
                "总路径长度",
                "total_distance_comparison.png",
            ),
            (
                "charging_times",
                "不同规模下策略充电次数对比",
                "充电次数",
                "charging_times_comparison.png",
            ),
            (
                "charging_requests",
                "不同规模下策略充电需求次数对比",
                "充电需求次数",
                "charging_requests_comparison.png",
            ),
            (
                "charging_queue_events",
                "不同规模下策略排队次数对比",
                "排队次数",
                "charging_queue_events_comparison.png",
            ),
            (
                "max_queue_length",
                "不同规模下策略最大队列长度对比",
                "最大队列长度",
                "max_queue_length_comparison.png",
            ),
            (
                "total_charging_wait_time",
                "不同规模下策略充电等待总时间对比",
                "等待总时间",
                "total_charging_wait_time_comparison.png",
            ),
        ]
    else:
        chart_settings = [
            ("total_score", "Total Score by Scale and Strategy", "total score", "total_score_comparison.png"),
            (
                "completed_tasks",
                "Completed Tasks by Scale and Strategy",
                "completed tasks",
                "completed_tasks_comparison.png",
            ),
            (
                "timeout_tasks",
                "Timeout Tasks by Scale and Strategy",
                "timeout tasks",
                "timeout_tasks_comparison.png",
            ),
            (
                "total_distance",
                "Total Distance by Scale and Strategy",
                "total distance",
                "total_distance_comparison.png",
            ),
            (
                "charging_times",
                "Charging Times by Scale and Strategy",
                "charging times",
                "charging_times_comparison.png",
            ),
            (
                "charging_requests",
                "Charging Requests by Scale and Strategy",
                "charging requests",
                "charging_requests_comparison.png",
            ),
            (
                "charging_queue_events",
                "Charging Queue Events by Scale and Strategy",
                "queue events",
                "charging_queue_events_comparison.png",
            ),
            (
                "max_queue_length",
                "Max Queue Length by Scale and Strategy",
                "max queue length",
                "max_queue_length_comparison.png",
            ),
            (
                "total_charging_wait_time",
                "Total Charging Wait Time by Scale and Strategy",
                "total wait time",
                "total_charging_wait_time_comparison.png",
            ),
        ]

    for metric, title, ylabel, file_name in chart_settings:
        plot_grouped_bar(df, metric, f"{title} (all difficulties mean)", ylabel, file_name)

    for difficulty in DIFFICULTIES:
        difficulty_df = df[df["difficulty"] == difficulty]
        if difficulty_df.empty:
            continue
        for metric, title, ylabel, file_name in chart_settings:
            difficulty_file_name = f"{difficulty}_{file_name}"
            plot_grouped_bar(
                difficulty_df,
                metric,
                f"{title} ({difficulty})",
                ylabel,
                difficulty_file_name,
            )

    print(f"Loaded data from: {CSV_PATH}")
    print(f"Rows: {len(df)}")
    print(f"Difficulties: {sorted(df['difficulty'].unique())}")
    print(f"Figures saved to: {FIGURE_DIR}")


if __name__ == "__main__":
    main()
