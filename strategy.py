# strategy.py
from core.graph import CityGraph

class Dispatcher:
    def __init__(self, city_graph: CityGraph, strategy_name: str = "nearest"):
        """
        初始化调度中心
        :param city_graph: A 模块提供的城市地图实例 (用于计算最短路径)
        :param strategy_name: 调度策略，支持 "nearest" (最近优先) 和 "largest" (最大权重优先)
        """
        self.city_graph = city_graph
        self.strategy_name = strategy_name

    def dispatch(self, state: dict) -> list:
        """
        核心调度算法，接收 B 模块的状态字典，返回 B 模块可执行的指令列表
        """
        actions = []
        
        # 1. 完美适配 B 同学的状态判定：使用 lower() 兼容 'idle' 和 'waiting'
        idle_vehicles = [v for v in state.get('vehicles', []) 
                         if str(v.get('status', '')).lower() == 'idle']
        
        unassigned_tasks = [t for t in state.get('tasks', []) 
                            if str(t.get('status', '')).lower() == 'waiting']

        # 如果没有空闲车辆或没有待分配任务，直接返回空指令
        if not idle_vehicles or not unassigned_tasks:
            return actions

        # 2. 最大权重优先策略 (Largest Weight First)
        if self.strategy_name == "largest":
            # 按任务权重降序排列
            unassigned_tasks.sort(key=lambda x: x.get('weight', 0), reverse=True)
            
            for vehicle in idle_vehicles:
                if not unassigned_tasks:
                    break
                task = unassigned_tasks.pop(0)
                
                # 严格按照 B 仿真器引擎要求的字典格式输出
                actions.append({
                    'vehicle_id': vehicle['id'],
                    'task_id': task['id'],
                    'action': 'assign'
                })

        # 3. 最近任务优先策略 (Nearest Task First)
        elif self.strategy_name == "nearest":
            for vehicle in idle_vehicles:
                if not unassigned_tasks:
                    break
                
                best_task = None
                shortest_dist = float('inf')
                
                # 获取小车当前节点，转为 int 以适配 A 同学的图算法
                start_node = int(vehicle.get('current_node', 0))
                
                for task in unassigned_tasks:
                    # 获取任务节点，转为 int 以适配 A 同学
                    target_node = int(task.get('node_id', 0))
                    
                    try:
                        # 调用 A 模块的最短路径算法计算真实路网距离
                        # A 返回的是 (path_list, distance)，我们只需要 distance
                        _, dist = self.city_graph.shortest_path(start_node, target_node)
                        
                        if dist < shortest_dist:
                            shortest_dist = dist
                            best_task = task
                    except Exception:
                        # 容错处理：如果 A 的算法在两个节点间找不到路，跳过该任务
                        pass 
                
                if best_task:
                    # 按照 B 引擎格式输出分配指令
                    actions.append({
                        'vehicle_id': vehicle['id'],
                        'task_id': best_task['id'],
                        'action': 'assign'
                    })
                    unassigned_tasks.remove(best_task)
                    
        return actions