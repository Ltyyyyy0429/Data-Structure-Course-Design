"""批量实验脚本 - 使用 A 同学的真实地图数据（180分钟仿真）"""
import json
import csv
import os
from simulator import Simulator


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


def load_graph_data(scale: str) -> dict:
    """加载 A 同学的真实地图数据"""
    file_path = f"data/{scale}_map.json"
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # 转换节点格式
            nodes = []
            for node in data.get("nodes", []):
                nodes.append({
                    "id": node.get("id"),
                    "x": node.get("x"),
                    "y": node.get("y"),
                    "type": node.get("type", "normal")
                })
            
            # 转换边格式：from -> from_node, to -> to_node
            edges = []
            for edge in data.get("edges", []):
                edges.append({
                    "from_node": edge.get("from"),
                    "to_node": edge.get("to"),
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


def run_single_experiment(scale: str, strategy: str, duration: int = 180) -> dict:
    """运行单次实验（默认180分钟）"""
    print(f"  运行 {scale} / {strategy} ...")
    
    graph_data = load_graph_data(scale)
    sim = Simulator(graph_data, scale, strategy)
    
    # 获取任务点并添加初始任务
    task_nodes = get_task_nodes(graph_data)
    if not task_nodes:
        task_nodes = [2, 3, 4]  # 备用
    
    # 添加初始任务（最多3个），截止时间延长到 120-180 分钟
    for i, node_id in enumerate(task_nodes[:3]):
        deadline = 120 + i * 30  # 120, 150, 180分钟
        sim.add_test_task(f"t{i}", node_id, 100 + i * 50, 0, deadline)
    
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


def run_batch_experiment():
    """运行批量实验"""
    scales = ["small", "medium", "large"]
    strategies = ["nearest", "largest"]
    results = []
    
    print("=" * 60)
    print("批量实验开始（使用 A 同学真实地图）")
    print("仿真时长: 180分钟 (3小时)")
    print("=" * 60)
    
    for scale in scales:
        for strategy in strategies:
            try:
                metrics = run_single_experiment(scale, strategy, duration=180)
                results.append({
                    "scale": scale,
                    "strategy": strategy,
                    "total_score": metrics['total_score'],
                    "completed_tasks": metrics['completed_tasks'],
                    "timeout_tasks": metrics['timeout_tasks'],
                    "total_distance": metrics['total_distance'],
                    "charging_times": metrics['charging_times']
                })
            except Exception as e:
                print(f"  错误: {scale}/{strategy} - {e}")
    
    # 保存结果到 CSV
    os.makedirs("results", exist_ok=True)
    with open('results/experiment_results.csv', 'w', newline='', encoding='utf-8') as f:
        fieldnames = ["scale", "strategy", "total_score", "completed_tasks", 
                      "timeout_tasks", "total_distance", "charging_times"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print("\n" + "=" * 60)
    print("实验结果（真实地图，180分钟仿真）")
    print("=" * 60)
    print(f"{'规模':<10} {'策略':<12} {'得分':<10} {'完成任务':<10} {'总里程':<10} {'充电次数':<8}")
    print("-" * 65)
    for r in results:
        print(f"{r['scale']:<10} {r['strategy']:<12} {r['total_score']:<10.1f} {r['completed_tasks']:<10} {r['total_distance']:<10.1f} {r['charging_times']:<8}")
    
    print(f"\n结果已保存到: results/experiment_results.csv")
    
    # 输出总结
    print("\n" + "=" * 60)
    print("策略对比总结")
    print("=" * 60)
    for scale in scales:
        nearest_score = next(r['total_score'] for r in results if r['scale'] == scale and r['strategy'] == 'nearest')
        largest_score = next(r['total_score'] for r in results if r['scale'] == scale and r['strategy'] == 'largest')
        winner = "nearest" if nearest_score > largest_score else "largest"
        diff = abs(nearest_score - largest_score)
        print(f"{scale}: nearest={nearest_score:.1f}, largest={largest_score:.1f}, 胜者={winner} (相差{diff:.1f}分)")
    
    return results


if __name__ == "__main__":
    run_batch_experiment()