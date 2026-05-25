"""仿真引擎核心类"""
from typing import Dict, List, Any
from .models import (
    Node, Edge, Vehicle, Task, ChargingStation, Metrics,
    VehicleStatus, TaskStatus
)


class Simulator:
    """物流车队仿真模拟器"""
    
    def __init__(self, graph_data: dict, scale: str, strategy: str):
        """
        初始化仿真器
        
        Args:
            graph_data: 包含 'nodes' 和 'edges' 的字典
            scale: "small" / "medium" / "large"
            strategy: "nearest" / "largest"
        """
        # 存储图数据
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Edge] = {}  # key: "from->to"
        
        # 解析图数据
        for node_data in graph_data.get('nodes', []):
            node = Node(**node_data)
            self.nodes[node.id] = node
            
        for edge_data in graph_data.get('edges', []):
            edge = Edge(**edge_data)
            key = f"{edge.from_node}->{edge.to_node}"
            self.edges[key] = edge
        
        # 车队数据
        self.vehicles: Dict[str, Vehicle] = {}
        self._init_vehicles()  # 初始化车辆
        
        # 任务数据
        self.tasks: Dict[str, Task] = {}
        
        # 充电站数据
        self.charging_stations: Dict[str, ChargingStation] = {}
        self._init_charging_stations()
        
        # 指标数据
        self.metrics = Metrics(
            current_time=0.0,
            scale=scale,
            strategy=strategy,
            total_score=0.0,
            completed_tasks=0,
            timeout_tasks=0,
            total_distance=0.0,
            charging_times=0
        )
        
        # 仿真时间
        self.current_time = 0.0
        
        # 辅助变量
        self.next_vehicle_id = 1
        self.next_task_id = 1
        
        print(f"[Simulator] 初始化完成 | 规模: {scale} | 策略: {strategy}")
        print(f"[Simulator] 节点数: {len(self.nodes)} | 边数: {len(self.edges)} | 车辆数: {len(self.vehicles)}")
        
    def _init_vehicles(self):
        """初始化车队（3辆车，停在仓库）"""
        # 找到仓库节点（type='depot'）
        depot_nodes = [n for n in self.nodes.values() if n.type == 'depot']
        if not depot_nodes:
            raise ValueError("图中没有仓库节点（type='depot'）")
        
        depot_id = depot_nodes[0].id
        
        # 创建3辆车
        for i in range(1, 4):
            vehicle = Vehicle(
                id=f"v{i}",
                current_node=depot_id,
                battery=100.0,      # 满电 100 kWh
                load=0.0,
                status=VehicleStatus.IDLE,
                target_node="",
                path=[]
            )
            self.vehicles[vehicle.id] = vehicle
            print(f"[Simulator] 创建车辆: {vehicle.id}，初始位置: {depot_id}")
    
    def _init_charging_stations(self):
        """初始化充电站"""
        cs_nodes = [n for n in self.nodes.values() if n.type == 'charging_station']
        for node in cs_nodes:
            cs = ChargingStation(
                node_id=node.id,
                queue_length=0,
                charging_count=0
            )
            self.charging_stations[node.id] = cs
            print(f"[Simulator] 创建充电站: {node.id}")
    
    def get_state(self) -> dict:
        """
        获取当前完整状态（供UI和调度器使用）
        
        Returns:
            符合接口约定的状态字典
        """
        # 转换车辆数据
        vehicles_state = []
        for v in self.vehicles.values():
            v_dict = {
                'id': v.id,
                'current_node': v.current_node,
                'battery': v.battery,
                'load': v.load,
                'status': v.status.value,  # Enum -> str
                'target_node': v.target_node,
                'path': v.path.copy() if v.path else []  # 复制列表避免引用问题
            }
            vehicles_state.append(v_dict)
        
        # 转换任务数据
        tasks_state = []
        for t in self.tasks.values():
            t_dict = {
                'id': t.id,
                'node_id': t.node_id,
                'weight': t.weight,
                'release_time': t.release_time,
                'deadline': t.deadline,
                'status': t.status.value
            }
            tasks_state.append(t_dict)
        
        # 转换充电站数据
        charging_stations_state = []
        for cs in self.charging_stations.values():
            cs_dict = {
                'node_id': cs.node_id,
                'queue_length': cs.queue_length,
                'charging_count': cs.charging_count
            }
            charging_stations_state.append(cs_dict)
        
        # 构建完整状态字典
        state = {
            'nodes': [{'id': n.id, 'x': n.x, 'y': n.y, 'type': n.type} 
                      for n in self.nodes.values()],
            'edges': [{'from_node': e.from_node, 'to_node': e.to_node, 'distance': e.distance}
                      for e in self.edges.values()],
            'vehicles': vehicles_state,
            'tasks': tasks_state,
            'charging_stations': charging_stations_state,
            'metrics': {
                'current_time': self.metrics.current_time,
                'scale': self.metrics.scale,
                'strategy': self.metrics.strategy,
                'total_score': self.metrics.total_score,
                'completed_tasks': self.metrics.completed_tasks,
                'timeout_tasks': self.metrics.timeout_tasks,
                'total_distance': self.metrics.total_distance,
                'charging_times': self.metrics.charging_times
            }
        }
        
        return state
    
    def update(self, dt: float, dispatcher) -> None:
        """
        推进仿真（Day 2 实现核心逻辑）
        
        Args:
            dt: 时间步长（分钟）
            dispatcher: 调度器实例，需包含 dispatch(state) 方法
        """
        # TODO: Day 2 实现以下逻辑
        # 1. 推进时间
        # 2. 移动车辆 _move_vehicles(dt)
        # 3. 处理充电 _handle_charging()
        # 4. 检查任务完成 _check_tasks_completion()
        # 5. 生成新任务 _generate_new_tasks()
        # 6. 调用调度器 _apply_dispatch(dispatcher.dispatch(self.get_state()))
        # 7. 更新指标 _update_metrics()
        pass
    
    def _move_vehicles(self, dt: float) -> None:
        """移动车辆（Day 2 实现）"""
        pass
    
    def _handle_charging(self) -> None:
        """处理充电逻辑（Day 2 实现）"""
        pass
    
    def _check_tasks_completion(self) -> None:
        """检查任务完成（Day 2 实现）"""
        pass
    
    def _generate_new_tasks(self) -> None:
        """生成新任务（Day 2 实现）"""
        pass
    
    def _apply_dispatch(self, actions: list) -> None:
        """应用调度指令（Day 2 实现）"""
        pass
    
    def _update_metrics(self) -> None:
        """更新指标（Day 2 实现）"""
        pass
    
    def add_test_task(self, task_id: str, node_id: str, weight: float, 
                      release_time: float, deadline: float) -> None:
        """
        添加测试任务（用于Day 1验证get_state）
        
        Args:
            task_id: 任务ID
            node_id: 节点ID
            weight: 重量(kg)
            release_time: 产生时间
            deadline: 截止时间
        """
        task = Task(
            id=task_id,
            node_id=node_id,
            weight=weight,
            release_time=release_time,
            deadline=deadline,
            status=TaskStatus.WAITING
        )
        self.tasks[task_id] = task
        print(f"[Simulator] 添加测试任务: {task_id} 在节点 {node_id}")