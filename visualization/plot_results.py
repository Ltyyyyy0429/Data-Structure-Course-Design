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
STRATEGIES = ["nearest", "largest", "energy_aware_hybrid", "genetic_algorithm"]
DIFFICULTIES = ["easy", "medium", "hard"]
EXPECTED_ROWS = len(SCALES) * len(DIFFICULTIES) * len(STRATEGIES)
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


def load_results() -> pd.DataFrame:
    """Load the official 48-row experiment CSV.

    Final report charts must be based on real batch experiment output.  If the
    CSV is missing or incomplete, stop and ask the user to regenerate it.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        df = pd.read_csv(CSV_PATH)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "results/experiment_results.csv not found. "
            "Please run python3 batch_experiment.py all first."
        ) from exc
    except EmptyDataError as exc:
        raise ValueError(
            "results/experiment_results.csv is empty. "
            "Please run python3 batch_experiment.py all first."
        ) from exc

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(
            f"experiment_results.csv 缺少必要列: {missing_columns}. "
            "Please run python3 batch_experiment.py all first."
        )

    if df.empty:
        raise ValueError(
            "experiment_results.csv 没有任何实验行。"
            "Please run python3 batch_experiment.py all first."
        )

    if len(df) != EXPECTED_ROWS:
        raise ValueError(
            f"实验行数不完整: 当前 {len(df)} 行，期望 {EXPECTED_ROWS} 行 "
            "(4 scales x 3 difficulties x 4 strategies). "
            "Please run python3 batch_experiment.py all first."
        )

    if df[REQUIRED_COLUMNS].isna().any().any():
        bad_columns = df[REQUIRED_COLUMNS].columns[df[REQUIRED_COLUMNS].isna().any()].tolist()
        raise ValueError(f"experiment_results.csv 存在空值/NaN 列: {bad_columns}")

    required_combinations = {
        (difficulty, scale, strategy)
        for difficulty in DIFFICULTIES
        for scale in SCALES
        for strategy in STRATEGIES
    }
    actual_combinations = set(zip(df["difficulty"], df["scale"], df["strategy"]))
    missing_combinations = sorted(required_combinations - actual_combinations)
    if missing_combinations:
        raise ValueError(f"experiment_results.csv 缺少实验组合: {missing_combinations}")

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
    colors = {
        "nearest": "#3182ce",
        "largest": "#dd6b20",
        "energy_aware_hybrid": "#2ca02c",
        "genetic_algorithm": "#805ad5",
    }

    plt.figure(figsize=(9.5, 5.4))
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
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(FIGURE_DIR / file_name, dpi=150)
    plt.close()


def main() -> None:
    df = load_results()
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
    print(f"Strategies: {list(STRATEGIES)}")
    print(f"Figures saved to: {FIGURE_DIR}")


if __name__ == "__main__":
    main()
