"""测试 Simulator 完整功能 - 整数ID版本"""
import random
from simulator import Simulator

# 使用整数 ID 的测试图
test_graph = {
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

def run_simulation(strategy, duration=30, dt=1):
    print(f"\n{'='*60}")
    print(f"运行仿真 | 策略: {strategy} | 时长: {duration}分钟 | 步长: {dt}分钟")
    print(f"{'='*60}\n")
    
    sim = Simulator(test_graph, "small", strategy)
    
    # 添加初始任务（node_id 是整数）
    print("\n[添加初始任务]")
    sim.add_test_task("t1", 2, 200, 0, 25)
    sim.add_test_task("t2", 3, 150, 0, 30)
    sim.add_test_task("t3", 4, 300, 0, 35)
    
    print("\n[初始调度]")
    sim._dispatch_tasks()
    
    initial_state = sim.get_state()
    print(f"初始车辆状态:")
    for v in initial_state['vehicles']:
        print(f"  {v['id']}: 位置={v['current_node']}, 状态={v['status']}, 目标={v['target_node']}")
    
    time_steps = int(duration / dt)
    for step in range(time_steps):
        sim.update(dt)
        
        if step % 5 == 0 and step > 0:
            state = sim.get_state()
            print(f"\n[时间 {state['metrics']['current_time']:.1f}分钟]")
            print(f"  完成任务: {state['metrics']['completed_tasks']}")
            print(f"  超时任务: {state['metrics']['timeout_tasks']}")
            print(f"  总得分: {state['metrics']['total_score']:.1f}")
            print(f"  总里程: {state['metrics']['total_distance']:.1f}km")
            print(f"  充电次数: {state['metrics']['charging_times']}")
            
            for v in state['vehicles']:
                if v['status'] != 'idle':
                    print(f"    {v['id']}: {v['status']}, 位置={v['current_node']}, 电量={v['battery']}kWh")
    
    final_state = sim.get_state()
    print(f"\n{'='*60}")
    print(f"仿真结束 - {strategy} 策略")
    print(f"{'='*60}")
    print(f"最终得分: {final_state['metrics']['total_score']:.1f}")
    print(f"完成任务: {final_state['metrics']['completed_tasks']}")
    print(f"超时任务: {final_state['metrics']['timeout_tasks']}")
    print(f"总行驶距离: {final_state['metrics']['total_distance']:.1f} km")
    print(f"充电次数: {final_state['metrics']['charging_times']}")
    
    print(f"\n最终车辆状态:")
    for v in final_state['vehicles']:
        print(f"  {v['id']}: 位置={v['current_node']}, 电量={v['battery']}kWh, 载重={v['load']}kg")
    
    return final_state['metrics']

if __name__ == "__main__":
    print("新能源物流车队调度仿真测试（整数ID版本）")
    print("="*60)
    
    results = {}
    for strategy in ['nearest', 'largest']:
        metrics = run_simulation(strategy, duration=30, dt=1)
        results[strategy] = metrics
    
    print(f"\n{'='*60}")
    print("策略对比结果")
    print(f"{'='*60}")
    print(f"{'指标':<15} {'最近任务优先':<20} {'最大任务优先':<20}")
    print("-"*55)
    print(f"{'最终得分':<15} {results['nearest']['total_score']:<20.1f} {results['largest']['total_score']:<20.1f}")
    print(f"{'完成任务':<15} {results['nearest']['completed_tasks']:<20} {results['largest']['completed_tasks']:<20}")
    print(f"{'超时任务':<15} {results['nearest']['timeout_tasks']:<20} {results['largest']['timeout_tasks']:<20}")
    print(f"{'总里程(km)':<15} {results['nearest']['total_distance']:<20.1f} {results['largest']['total_distance']:<20.1f}")
    print(f"{'充电次数':<15} {results['nearest']['charging_times']:<20} {results['largest']['charging_times']:<20}")