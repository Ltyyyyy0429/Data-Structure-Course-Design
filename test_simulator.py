"""测试 Simulator 完整功能"""
import json
import time
from simulator import Simulator

# 创建测试用的图数据
test_graph = {
    "nodes": [
        {"id": "depot_1", "x": 0, "y": 0, "type": "depot"},
        {"id": "task_1", "x": 10, "y": 0, "type": "task_point"},
        {"id": "task_2", "x": 0, "y": 10, "type": "task_point"},
        {"id": "task_3", "x": 10, "y": 10, "type": "task_point"},
        {"id": "cs_1", "x": 5, "y": 5, "type": "charging_station"},
    ],
    "edges": [
        {"from_node": "depot_1", "to_node": "task_1", "distance": 10.0},
        {"from_node": "depot_1", "to_node": "task_2", "distance": 10.0},
        {"from_node": "depot_1", "to_node": "task_3", "distance": 14.1},
        {"from_node": "depot_1", "to_node": "cs_1", "distance": 7.0},
        {"from_node": "task_1", "to_node": "cs_1", "distance": 7.0},
        {"from_node": "task_2", "to_node": "cs_1", "distance": 7.0},
        {"from_node": "task_3", "to_node": "cs_1", "distance": 7.0},
    ]
}

def run_simulation(strategy, duration=30, dt=1):
    """运行仿真"""
    print(f"\n{'='*60}")
    print(f"运行仿真 | 策略: {strategy} | 时长: {duration}分钟 | 步长: {dt}分钟")
    print(f"{'='*60}\n")
    
    # 创建仿真器
    sim = Simulator(
        graph_data=test_graph,
        scale="small",
        strategy=strategy
    )
    
    # 添加初始任务
    print("\n[添加初始任务]")
    sim.add_test_task("t1", "task_1", 200, 0, 25)
    sim.add_test_task("t2", "task_2", 150, 0, 30)
    sim.add_test_task("t3", "task_3", 300, 0, 35)
    
    # 立即调度一次
    print("\n[初始调度]")
    sim._dispatch_tasks()
    
    # 显示初始状态
    initial_state = sim.get_state()
    print(f"初始车辆状态:")
    for v in initial_state['vehicles']:
        print(f"  {v['id']}: 位置={v['current_node']}, 状态={v['status']}, 目标={v['target_node']}")
    
    # 运行仿真
    time_steps = int(duration / dt)
    for step in range(time_steps):
        sim.update(dt)
        
        # 每5步打印一次状态
        if step % 5 == 0 and step > 0:
            state = sim.get_state()
            print(f"\n[时间 {state['metrics']['current_time']:.1f}分钟]")
            print(f"  完成任务: {state['metrics']['completed_tasks']}")
            print(f"  超时任务: {state['metrics']['timeout_tasks']}")
            print(f"  总得分: {state['metrics']['total_score']:.1f}")
            print(f"  总里程: {state['metrics']['total_distance']:.1f}km")
            print(f"  充电次数: {state['metrics']['charging_times']}")
            
            # 打印车辆状态
            for v in state['vehicles']:
                if v['status'] != 'idle':
                    print(f"    {v['id']}: {v['status']}, 位置={v['current_node']}, 电量={v['battery']}kWh")
    
    # 最终结果
    final_state = sim.get_state()
    print(f"\n{'='*60}")
    print(f"仿真结束 - {strategy} 策略")
    print(f"{'='*60}")
    print(f"最终得分: {final_state['metrics']['total_score']:.1f}")
    print(f"完成任务: {final_state['metrics']['completed_tasks']}")
    print(f"超时任务: {final_state['metrics']['timeout_tasks']}")
    print(f"总行驶距离: {final_state['metrics']['total_distance']:.1f} km")
    print(f"充电次数: {final_state['metrics']['charging_times']}")
    
    # 打印所有车辆最终状态
    print(f"\n最终车辆状态:")
    for v in final_state['vehicles']:
        print(f"  {v['id']}: 位置={v['current_node']}, 电量={v['battery']}kWh, 载重={v['load']}kg")
    
    return final_state['metrics']

if __name__ == "__main__":
    print("新能源物流车队调度仿真测试")
    print("="*60)
    
    # 测试两种策略
    results = {}
    for strategy in ['nearest', 'largest']:
        metrics = run_simulation(strategy, duration=30, dt=1)
        results[strategy] = metrics
    
    # 对比结果
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