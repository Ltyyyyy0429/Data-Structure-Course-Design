from simulator import Simulator

def run_simulation(strategy_name, sim_time):
    # ===================== 全新10节点扩容路网（直接替换原有路网） =====================
    graph_data = {
        "nodes": [
            {"id": 1, "x": 0, "y": 0, "type": "depot"},
            {"id": 2, "x": 10, "y": 0, "type": "task_point"},
            {"id": 3, "x": 0, "y": 10, "type": "task_point"},
            {"id": 4, "x": 20, "y": 0, "type": "task_point"},
            {"id": 5, "x": 0, "y": 20, "type": "task_point"},
            {"id": 6, "x": 30, "y": 0, "type": "task_point"},
            {"id": 7, "x": 0, "y": 30, "type": "task_point"},
            {"id": 8, "x": 15, "y": 15, "type": "charging_station"},
            {"id": 9, "x": 25, "y": 10, "type": "charging_station"},
            {"id": 10, "x": 10, "y": 25, "type": "charging_station"}
        ],
        "edges": [
            {"from_node": 1, "to_node": 2, "distance": 10},
            {"from_node": 2, "to_node": 1, "distance": 10},
            {"from_node": 1, "to_node": 3, "distance": 10},
            {"from_node": 3, "to_node": 1, "distance": 10},
            {"from_node": 1, "to_node": 8, "distance": 21},
            {"from_node": 8, "to_node": 1, "distance": 21},

            {"from_node": 2, "to_node": 4, "distance": 10},
            {"from_node": 4, "to_node": 2, "distance": 10},
            {"from_node": 2, "to_node": 9, "distance": 11},
            {"from_node": 9, "to_node": 2, "distance": 11},

            {"from_node": 3, "to_node": 5, "distance": 10},
            {"from_node": 5, "to_node": 3, "distance": 10},
            {"from_node": 3, "to_node": 10, "distance": 11},
            {"from_node": 10, "to_node": 3, "distance": 11},

            {"from_node": 4, "to_node": 6, "distance": 10},
            {"from_node": 6, "to_node": 4, "distance": 10},
            {"from_node": 5, "to_node": 7, "distance": 10},
            {"from_node": 7, "to_node": 5, "distance": 10},

            {"from_node": 6, "to_node": 9, "distance": 11},
            {"from_node": 9, "to_node": 6, "distance": 11},
            {"from_node": 7, "to_node": 10, "distance": 11},
            {"from_node": 10, "to_node": 7, "distance": 11},

            {"from_node": 8, "to_node": 9, "distance": 14},
            {"from_node": 9, "to_node": 8, "distance": 14},
            {"from_node": 8, "to_node": 10, "distance": 14},
            {"from_node": 10, "to_node": 8, "distance": 14}
        ]
    }

    sim = Simulator(graph_data, scale="small", strategy=strategy_name)
    # ===================== 初始任务：分配至远端节点，拉长行驶里程 =====================
    print("\n[添加初始任务]")
    sim.add_test_task("t1", 6, 200, 0, 300)
    sim.add_test_task("t2", 7, 150, 0, 300)
    sim.add_test_task("t3", 4, 300, 0, 300)

    state = sim.get_state()
    print("[初始车辆状态]")
    for v in state["vehicles"]:
        print(f"  {v['id']}: 位置={v['current_node']}, 状态={v['status']}, 目标={v['target_node']}")

    # 逐分钟仿真
    for t in range(6, sim_time + 1, 5):
        for _ in range(5):
            sim.update(dt=1)
        state = sim.get_state()
        print(f"\n[时间 {t}.0分钟]")
        print(f"  完成任务: {state['metrics']['completed_tasks']}")
        print(f"  超时任务: {state['metrics']['timeout_tasks']}")
        print(f"  总得分: {state['metrics']['total_score']}")
        print(f"  总里程: {state['metrics']['total_distance']}")
        print(f"  充电次数: {state['metrics']['charging_times']}")
        for v in state["vehicles"]:
            print(f"    {v['id']}: {v['status']}, 位置={v['current_node']}, 电量={v['battery']}kWh")

    # 仿真结束汇总
    final = sim.get_state()
    print("\n" + "="*60)
    print(f"仿真结束 - {strategy_name} 策略")
    print("="*60)
    print(f"最终得分: {final['metrics']['total_score']}")
    print(f"完成任务: {final['metrics']['completed_tasks']}")
    print(f"超时任务: {final['metrics']['timeout_tasks']}")
    print(f"总行驶距离: {final['metrics']['total_distance']} km")
    print(f"充电次数: {final['metrics']['charging_times']}")
    print("最终车辆状态:")
    for v in final["vehicles"]:
        print(f"  {v['id']}: 位置={v['current_node']}, 电量={v['battery']}kWh, 载重={v['load']}kg")
    print("="*60)
    return final["metrics"]


if __name__ == "__main__":
    print("新能源物流车队调度仿真（扩容路网版）")
    print("="*60)

    # 建议仿真时长：90 ~ 120 分钟，稳定触发充电
    SIMULATION_TIME = 90

    # 运行 nearest 策略
    res1 = run_simulation("nearest", SIMULATION_TIME)
    # 运行 largest 策略
    res2 = run_simulation("largest", SIMULATION_TIME)

    # 对比报表
    print("\n策略对比结果")
    print("-"*60)
    print(f"{'指标':<15} {'最近任务优先':<20} {'最大任务优先'}")
    print("-"*60)
    print(f"{'最终得分':<15} {res1['total_score']:<20} {res2['total_score']}")
    print(f"{'完成任务':<15} {res1['completed_tasks']:<20} {res2['completed_tasks']}")
    print(f"{'超时任务':<15} {res1['timeout_tasks']:<20} {res2['timeout_tasks']}")
    print(f"{'总里程(km)':<15} {res1['total_distance']:<20} {res2['total_distance']}")
    print(f"{'充电次数':<15} {res1['charging_times']:<20} {res2['charging_times']}")