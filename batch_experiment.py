"""批量实验脚本 - 支持多策略 × 多规模 × 多难度"""

import json
import csv
import os
import random
import sys

from simulator import Simulator
from simulator.pathfinder_adapter import RealPathfinder
from core.difficulty import get_difficulty_config
from core.map_generator import generate_all_maps


SCALES = ["small", "medium", "large", "extra_large"]
STRATEGIES = ["nearest", "largest", "energy_aware_hybrid"]
DIFFICULTIES = ["easy", "medium", "hard"]
RESULT_CSV_PATH = "results/experiment_results.csv"
EXPERIMENT_FIELDS = [
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


def get_default_graph():
    """默认测试图"""
    return {
        "nodes": [
            {"id": 1, "x": 0, "y": 0, "type": "depot"},
            {"id": 2, "x": 10, "y": 0, "type": "task_point"},
            {"id": 3, "x": 0, "y": 10, "type": "task_point"},
            {"id": 4, "x": 10, "y": 10, "type": "task_point"},
            {"id": 5, "x": 5, "y": 5, "type": "charging_station"},
        ],
        "edges": [
            {"from_node": 1, "to_node": 2, "distance": 10.0},
            {"from_node": 1, "to_node": 3, "distance": 10.0},
            {"from_node": 1, "to_node": 4, "distance": 14.1},
            {"from_node": 1, "to_node": 5, "distance": 7.0},
            {"from_node": 2, "to_node": 5, "distance": 7.0},
            {"from_node": 3, "to_node": 5, "distance": 7.0},
            {"from_node": 4, "to_node": 5, "distance": 7.0},
        ]
    }


def convert_node_type_to_simulator(node_type: str) -> str:
    """Convert A-map node types to the B Simulator node type names.

    A module stores maps as warehouse / charging / normal. The Simulator
    expects depot / charging_station / task_point. For experiments, normal
    road nodes can be used as candidate task points.
    """

    type_text = str(node_type or "normal").strip().lower()
    type_mapping = {
        "warehouse": "depot",
        "depot": "depot",
        "charging": "charging_station",
        "charging_station": "charging_station",
        "task": "task_point",
        "task_point": "task_point",
        "normal": "task_point",
    }
    return type_mapping.get(type_text, "task_point")


def load_graph_data(scale: str) -> dict:
    """加载 A 同学的真实地图数据，并转换成 B Simulator 可识别的格式"""
    file_path = f"data/{scale}_map.json"
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # 转换节点格式：A 类型 -> B Simulator 类型
            nodes = []
            for node in data.get("nodes", []):
                nodes.append({
                    "id": node.get("id"),
                    "x": node.get("x"),
                    "y": node.get("y"),
                    "type": convert_node_type_to_simulator(node.get("type", "normal"))
                })
            
            # 转换边格式：兼容 A 的 from/to 和 B 的 from_node/to_node
            edges = []
            for edge in data.get("edges", []):
                edges.append({
                    "from_node": edge.get("from", edge.get("from_node")),
                    "to_node": edge.get("to", edge.get("to_node")),
                    "distance": edge.get("distance")
                })
            
            print(f"  加载 {scale} 地图: {len(nodes)} 节点, {len(edges)} 边")
            return {
                "nodes": nodes,
                "edges": edges
            }
    else:
        print(f"  警告: {file_path} 不存在，使用默认小地图")
        return get_default_graph()


def get_task_nodes(graph_data: dict) -> list:
    """获取地图中的所有任务点"""
    task_nodes = []
    for node in graph_data.get("nodes", []):
        node_type = node.get("type", "")
        if node_type == "task_point" or node_type == "task":
            task_nodes.append(node["id"])
    return task_nodes


def get_depot_node(graph_data: dict) -> int:
    """Return the depot node id from converted Simulator graph data."""
    for node in graph_data.get("nodes", []):
        if node.get("type") == "depot":
            return node["id"]
    return graph_data["nodes"][0]["id"]


def get_experiment_seed(scale: str, difficulty: str) -> int:
    """Use the same random task stream for all strategies in one scenario."""
    scale_index = SCALES.index(scale) if scale in SCALES else 0
    difficulty_index = DIFFICULTIES.index(difficulty) if difficulty in DIFFICULTIES else 0
    return 202600 + difficulty_index * 1000 + scale_index * 100


def add_initial_tasks(sim: Simulator, graph_data: dict, pathfinder: RealPathfinder) -> None:
    """Add a fair, distance-varied initial task set for all strategies.

    More waiting tasks than vehicles makes nearest / largest / hybrid choose
    different orders, so the strategy comparison is visible in the CSV.
    """
    task_nodes = get_task_nodes(graph_data)
    if not task_nodes:
        task_nodes = [2, 3, 4]

    depot_id = get_depot_node(graph_data)
    ranked_nodes = []
    for node_id in task_nodes:
        try:
            _, distance = pathfinder.find_path_and_distance(depot_id, node_id)
        except Exception:
            distance = 999.0
        ranked_nodes.append((node_id, distance))

    ranked_nodes.sort(key=lambda item: item[1])
    initial_count = min(len(ranked_nodes), max(sim.vehicle_count * 2, 6))
    near_count = initial_count // 2
    selected = ranked_nodes[:near_count] + ranked_nodes[-(initial_count - near_count):]

    seen = set()
    unique_selected = []
    for node_id, distance in selected:
        if node_id not in seen:
            seen.add(node_id)
            unique_selected.append((node_id, distance))

    for index, (node_id, distance) in enumerate(unique_selected, start=1):
        # Weights rise mildly with task order. The far tasks are still attractive
        # to largest-first, while the hybrid strategy can prefer nearer tasks
        # because its distance and energy penalties now matter.
        weight = round(120 + index * 8, 1)
        deadline = 90 + index * 15
        sim.add_test_task(f"initial_{index}", node_id, weight, 0, deadline)

    # Dynamic tasks use t1/t2/...; keep those ids away from initial_* tasks.
    sim.next_task_id = max(sim.next_task_id, 1000)


def run_single_experiment(scale: str, strategy: str, duration: int = 180,
                         difficulty: str = "easy") -> dict:
    """运行单次实验（默认180分钟）"""
    print(f"  运行 {scale} / {strategy} / {difficulty} ...")

    # Generate map if needed
    map_path = f"data/{scale}_map.json"
    if not os.path.exists(map_path):
        print(f"    生成缺失的地图: {scale}")
        generate_all_maps()

    seed = get_experiment_seed(scale, difficulty)
    random.seed(seed)

    graph_data = load_graph_data(scale)
    pathfinder = RealPathfinder(map_path)
    config = get_difficulty_config(scale, difficulty)
    sim = Simulator(graph_data, scale, strategy, pathfinder=pathfinder, config=config)

    if sim._task_generator is not None:
        sim._task_generator.reset(seed)

    add_initial_tasks(sim, graph_data, pathfinder)
    
    # 立即调度
    sim._dispatch_tasks()
    
    # 运行仿真
    steps = int(duration / 1)  # dt=1分钟
    for step in range(steps):
        sim.update(1)
        # 每30分钟打印一次进度
        if step > 0 and step % 30 == 0:
            state = sim.get_state()
            print(f"    进度: {state['metrics']['current_time']}分钟, 得分={state['metrics']['total_score']:.1f}, 完成任务={state['metrics']['completed_tasks']}")
    
    state = sim.get_state()
    return state['metrics']


def run_batch_experiment(difficulty: str = "easy"):
    """运行批量实验.

    difficulty="all" runs easy / medium / hard and writes one unified CSV.
    Passing "easy", "medium", or "hard" keeps the old single-difficulty usage.
    """
    if difficulty in (None, "", "all"):
        difficulties = DIFFICULTIES
    elif difficulty in DIFFICULTIES:
        difficulties = [difficulty]
    else:
        raise ValueError(f"未知难度: {difficulty}. 可选: all, {DIFFICULTIES}")

    results = []

    print("=" * 60)
    print("批量实验开始")
    print(f"仿真时长: 180分钟 (3小时) | 难度: {difficulties}")
    print(f"规模: {SCALES} | 策略: {STRATEGIES}")
    print("=" * 60)

    # Ensure all maps exist
    ensure_all_maps()

    for current_difficulty in difficulties:
        for scale in SCALES:
            for strategy in STRATEGIES:
                try:
                    metrics = run_single_experiment(
                        scale,
                        strategy,
                        duration=180,
                        difficulty=current_difficulty,
                    )
                    results.append({
                        "difficulty": current_difficulty,
                        "scale": scale,
                        "strategy": strategy,
                        "total_score": metrics['total_score'],
                        "completed_tasks": metrics['completed_tasks'],
                        "timeout_tasks": metrics['timeout_tasks'],
                        "total_distance": metrics['total_distance'],
                        "charging_times": metrics['charging_times'],
                        "low_battery_events": metrics.get('low_battery_events', 0),
                        "charging_requests": metrics.get('charging_requests', 0),
                        "charging_queue_events": metrics.get('charging_queue_events', 0),
                        "total_charging_wait_time": metrics.get('total_charging_wait_time', 0.0),
                        "max_queue_length": metrics.get('max_queue_length', 0),
                    })
                except Exception as e:
                    print(f"  错误: {current_difficulty}/{scale}/{strategy} - {e}")
                    import traceback
                    traceback.print_exc()

    # 保存结果到 CSV
    os.makedirs("results", exist_ok=True)
    with open(RESULT_CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=EXPERIMENT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    print("\n" + "=" * 60)
    print("实验结果（统一 CSV，180分钟仿真）")
    print("=" * 60)
    header = f"{'难度':<8} {'规模':<12} {'策略':<20} {'得分':<10} {'完成任务':<10} {'超时':<8} {'总里程':<10} {'需求':<6} {'充电':<6} {'排队':<6} {'最大队列':<8}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(f"{r['difficulty']:<8} {r['scale']:<12} {r['strategy']:<20} {r['total_score']:<10.1f} "
              f"{r['completed_tasks']:<10} {r['timeout_tasks']:<8} "
              f"{r['total_distance']:<10.1f} {r['charging_requests']:<6} "
              f"{r['charging_times']:<6} {r['charging_queue_events']:<6} "
              f"{r['max_queue_length']:<8}")

    print(f"\n结果已保存到: {RESULT_CSV_PATH}")

    # 输出总结
    print("\n" + "=" * 60)
    print("策略对比总结")
    print("=" * 60)
    for current_difficulty in difficulties:
        for scale in SCALES:
            scale_results = [
                r for r in results
                if r['difficulty'] == current_difficulty and r['scale'] == scale
            ]
            if not scale_results:
                continue
            best = max(scale_results, key=lambda r: r['total_score'])
            print(f"{current_difficulty}/{scale}: 最优={best['strategy']} ({best['total_score']:.1f}分)")

    return results


def ensure_all_maps():
    """确保所有规模的地图 JSON 存在."""
    for scale in SCALES:
        if not os.path.exists(f"data/{scale}_map.json"):
            print(f"  生成缺失地图: {scale}")
            generate_all_maps()
            return  # generate_all_maps 一次性全部生成


if __name__ == "__main__":
    difficulty = sys.argv[1] if len(sys.argv) > 1 else "all"
    run_batch_experiment(difficulty)
