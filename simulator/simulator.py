"""仿真引擎核心类 - 完整修复版（任务完成得分修复）"""
from typing import Dict, List, Any, Optional
import random
import math
from .models import (
    Node, Edge, Vehicle, Task, ChargingStation, Metrics,
    VehicleStatus, TaskStatus
)


class MockPathfinder:
    """临时假寻路（等A同学完成后替换）"""
    def __init__(self, nodes: Dict[str, Node], edges: Dict[str, Edge]):
        self.nodes = nodes
        self.edges = edges
    
    def get_shortest_path(self, from_node: str, to_node: str) -> List[str]:
        """返回路径列表"""
        if from_node == to_node:
            return [from_node]
        return [from_node, to_node]
    
    def get_distance(self, from_node: str, to_node: str) -> float:
        """计算欧几里得距离"""
        n1 = self.nodes.get(from_node)
        n2 = self.nodes.get(to_node)
        if not n1 or not n2:
            return 100.0
        return math.sqrt((n1.x - n2.x)**2 + (n1.y - n2.y)**2)


class MockDispatcher:
    """临时假调度（等C同学完成后替换）"""
    def __init__(self, strategy: str):
        self.strategy = strategy
    
    def dispatch(self, state: dict) -> list:
        """分配任务"""
        actions = []
        idle_vehicles = [v for v in state['vehicles'] if v['status'] == 'idle']
        waiting_tasks = [t for t in state['tasks'] if t['status'] == 'waiting']
        
        if self.strategy == 'nearest':
            for vehicle in idle_vehicles:
                if not waiting_tasks:
                    break
                actions.append({
                    'vehicle_id': vehicle['id'],
                    'task_id': waiting_tasks[0]['id'],
                    'action': 'assign'
                })
                waiting_tasks.pop(0)
        elif self.strategy == 'largest':
            waiting_tasks.sort(key=lambda t: t['weight'], reverse=True)
            for vehicle in idle_vehicles:
                if not waiting_tasks:
                    break
                actions.append({
                    'vehicle_id': vehicle['id'],
                    'task_id': waiting_tasks[0]['id'],
                    'action': 'assign'
                })
                waiting_tasks.pop(0)
        
        return actions


class Simulator:
    VEHICLE_SPEED = 40.0  # km/h
    VEHICLE_BATTERY_CAPACITY = 100.0  # kWh
    VEHICLE_LOAD_CAPACITY = 1000.0  # kg
    ENERGY_PER_KM = 1.2  # kWh/km
    CHARGING_RATE = 50.0  # kWh/h
    CHARGING_PORTS_PER_STATION = 2
    
    def __init__(self, graph_data: dict, scale: str, strategy: str):
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Edge] = {}
        
        for node_data in graph_data.get('nodes', []):
            node = Node(**node_data)
            self.nodes[node.id] = node
        for edge_data in graph_data.get('edges', []):
            edge = Edge(**edge_data)
            key = f"{edge.from_node}->{edge.to_node}"
            self.edges[key] = edge
        
        self.vehicles: Dict[str, Vehicle] = {}
        self.vehicle_travel_time: Dict[str, float] = {}
        self._init_vehicles()
        
        self.tasks: Dict[str, Task] = {}
        
        self.charging_stations: Dict[str, ChargingStation] = {}
        self._init_charging_stations()
        
        self.charging_start_time: Dict[str, float] = {}
        
        self.metrics = Metrics(
            current_time=0.0, scale=scale, strategy=strategy,
            total_score=0.0, completed_tasks=0, timeout_tasks=0,
            total_distance=0.0, charging_times=0
        )
        
        self.current_time = 0.0
        self.next_task_id = 1
        self.task_gen_timer = 0
        self.task_gen_interval = 5
        
        self._pathfinder = MockPathfinder(self.nodes, self.edges)
        self._dispatcher = MockDispatcher(strategy)
        
        print(f"[Simulator] 初始化完成 | 规模: {scale} | 策略: {strategy}")
        print(f"[Simulator] 节点数: {len(self.nodes)} | 车辆数: {len(self.vehicles)}")
    
    def _init_vehicles(self):
        depot_nodes = [n for n in self.nodes.values() if n.type == 'depot']
        depot_id = depot_nodes[0].id if depot_nodes else list(self.nodes.keys())[0]
        for i in range(1, 4):
            vehicle = Vehicle(
                id=f"v{i}", current_node=depot_id, battery=self.VEHICLE_BATTERY_CAPACITY,
                load=0.0, status=VehicleStatus.IDLE, target_node="", path=[]
            )
            self.vehicles[vehicle.id] = vehicle
            self.vehicle_travel_time[vehicle.id] = 0
    
    def _init_charging_stations(self):
        for node in self.nodes.values():
            if node.type == 'charging_station':
                self.charging_stations[node.id] = ChargingStation(
                    node_id=node.id, queue_length=0, charging_count=0
                )
    
    def get_state(self) -> dict:
        vehicles_state = [{
            'id': v.id, 'current_node': v.current_node, 'battery': round(v.battery, 1),
            'load': round(v.load, 1), 'status': v.status.value,
            'target_node': v.target_node, 'path': v.path.copy()
        } for v in self.vehicles.values()]
        
        tasks_state = [{
            'id': t.id, 'node_id': t.node_id, 'weight': t.weight,
            'release_time': round(t.release_time, 1), 'deadline': round(t.deadline, 1),
            'status': t.status.value
        } for t in self.tasks.values()]
        
        return {
            'nodes': [{'id': n.id, 'x': n.x, 'y': n.y, 'type': n.type} for n in self.nodes.values()],
            'edges': [{'from_node': e.from_node, 'to_node': e.to_node, 'distance': e.distance} for e in self.edges.values()],
            'vehicles': vehicles_state,
            'tasks': tasks_state,
            'charging_stations': [{'node_id': cs.node_id, 'queue_length': cs.queue_length, 'charging_count': cs.charging_count} 
                                  for cs in self.charging_stations.values()],
            'metrics': {'current_time': round(self.metrics.current_time, 1), 'scale': self.metrics.scale,
                       'strategy': self.metrics.strategy, 'total_score': round(self.metrics.total_score, 1),
                       'completed_tasks': self.metrics.completed_tasks, 'timeout_tasks': self.metrics.timeout_tasks,
                       'total_distance': round(self.metrics.total_distance, 1), 'charging_times': self.metrics.charging_times}
        }
    
    def update(self, dt: float, dispatcher=None):
        if dispatcher:
            self._dispatcher = dispatcher
        
        self.current_time += dt
        self.metrics.current_time = self.current_time
        
        self._move_vehicles(dt)
        self._handle_charging(dt)
        self._check_tasks_completion()
        self._check_low_battery()
        self._generate_new_tasks(dt)
        self._dispatch_tasks()
    
    def _move_vehicles(self, dt: float):
        """移动车辆 - 使用时间累积器"""
        for vehicle in self.vehicles.values():
            if vehicle.status != VehicleStatus.MOVING:
                continue
            
            if not vehicle.path:
                vehicle.status = VehicleStatus.IDLE
                vehicle.target_node = ""
                continue
            
            # 获取目标节点
            target_node = vehicle.path[-1]
            dist_to_target = self._get_distance(vehicle.current_node, target_node)
            
            # 计算到达所需时间（分钟）
            time_needed_hours = dist_to_target / self.VEHICLE_SPEED
            time_needed_minutes = time_needed_hours * 60
            
            # 累积行驶时间
            self.vehicle_travel_time[vehicle.id] += dt
            
            if self.vehicle_travel_time[vehicle.id] >= time_needed_minutes:
                # 到达目标
                self.metrics.total_distance += dist_to_target
                vehicle.battery -= dist_to_target * self.ENERGY_PER_KM
                old_node = vehicle.current_node
                vehicle.current_node = target_node
                vehicle.path = []
                vehicle.status = VehicleStatus.IDLE
                vehicle.target_node = ""
                self.vehicle_travel_time[vehicle.id] = 0
                print(f"[Simulator] {vehicle.id} 从 {old_node} 到达 {target_node}，耗时 {time_needed_minutes:.1f}分钟，剩余电量 {vehicle.battery:.1f}kWh")
    
    def _handle_charging(self, dt: float):
        dt_hours = dt / 60.0
        charge_amount = self.CHARGING_RATE * dt_hours
        
        for vehicle in self.vehicles.values():
            if vehicle.status != VehicleStatus.CHARGING:
                continue
            vehicle.battery += charge_amount
            if vehicle.battery >= self.VEHICLE_BATTERY_CAPACITY:
                vehicle.battery = self.VEHICLE_BATTERY_CAPACITY
                vehicle.status = VehicleStatus.IDLE
                cs = self.charging_stations.get(vehicle.current_node)
                if cs:
                    cs.charging_count -= 1
                print(f"[Simulator] {vehicle.id} 充电完成")
    
    def _check_low_battery(self):
        for vehicle in self.vehicles.values():
            if vehicle.battery < 20 and vehicle.status == VehicleStatus.IDLE:
                nearest_cs = self._find_nearest_charging_station(vehicle.current_node)
                if nearest_cs:
                    cs = self.charging_stations[nearest_cs]
                    if cs.charging_count >= self.CHARGING_PORTS_PER_STATION:
                        cs.queue_length += 1
                        print(f"[Simulator] {vehicle.id} 在 {nearest_cs} 排队充电")
                    else:
                        cs.charging_count += 1
                        vehicle.status = VehicleStatus.CHARGING
                        self.metrics.charging_times += 1
                        print(f"[Simulator] {vehicle.id} 开始在 {nearest_cs} 充电")
    
    def _find_nearest_charging_station(self, from_node: str) -> Optional[str]:
        cs_list = [n.id for n in self.nodes.values() if n.type == 'charging_station']
        if not cs_list:
            return None
        best_cs, best_dist = None, float('inf')
        for cs_id in cs_list:
            dist = self._get_distance(from_node, cs_id)
            if dist < best_dist:
                best_dist, best_cs = dist, cs_id
        return best_cs
    
    def _check_tasks_completion(self):
        """检查任务完成 - 修复版"""
        # 收集已完成的任务
        completed_tasks = []
        
        for task in self.tasks.values():
            if task.status != TaskStatus.ASSIGNED:
                continue
            
            # 检查是否有车辆到达任务节点
            for vehicle in self.vehicles.values():
                if vehicle.current_node == task.node_id and vehicle.status == VehicleStatus.IDLE:
                    completed_tasks.append(task)
                    break
        
        # 处理完成的任务
        for task in completed_tasks:
            task.status = TaskStatus.COMPLETED
            time_early = max(0, task.deadline - self.current_time)
            score = 100 + time_early * 2
            self.metrics.total_score += score
            self.metrics.completed_tasks += 1
            
            # 找到执行任务的车辆并更新载重
            for vehicle in self.vehicles.values():
                if vehicle.current_node == task.node_id:
                    vehicle.load += task.weight
                    # 超载扣分
                    if vehicle.load > self.VEHICLE_LOAD_CAPACITY:
                        self.metrics.total_score -= 50
                        print(f"[Simulator] 警告: {vehicle.id} 超载！扣50分")
                    break
            
            print(f"[Simulator] 任务 {task.id} 完成！得分: {score:.1f} (提前 {time_early:.1f}分钟)")
        
        # 检查超时任务
        for task in self.tasks.values():
            if task.status == TaskStatus.WAITING and self.current_time > task.deadline:
                task.status = TaskStatus.TIMEOUT
                self.metrics.total_score -= 100
                self.metrics.timeout_tasks += 1
                print(f"[Simulator] 任务 {task.id} 超时！扣100分 (截止 {task.deadline:.1f}, 当前 {self.current_time:.1f})")
    
    def _generate_new_tasks(self, dt: float):
        self.task_gen_timer += dt
        if self.task_gen_timer >= self.task_gen_interval:
            self.task_gen_timer = 0
            if random.random() < 0.3:
                task_points = [n.id for n in self.nodes.values() if n.type == 'task_point']
                if task_points:
                    task = Task(
                        id=f"t{self.next_task_id}", node_id=random.choice(task_points),
                        weight=random.randint(50, 500), release_time=self.current_time,
                        deadline=self.current_time + random.randint(10, 60),
                        status=TaskStatus.WAITING
                    )
                    self.tasks[task.id] = task
                    self.next_task_id += 1
                    print(f"[Simulator] 新任务 {task.id}: 重量{task.weight}kg, 截止{task.deadline:.1f}min")
    
    def _dispatch_tasks(self):
        actions = self._dispatcher.dispatch(self.get_state())
        self._apply_dispatch(actions)
    
    def _apply_dispatch(self, actions: list):
        for action in actions:
            if action.get('action') != 'assign':
                continue
            vehicle = self.vehicles.get(action.get('vehicle_id'))
            task = self.tasks.get(action.get('task_id'))
            if not vehicle or not task:
                continue
            if vehicle.status != VehicleStatus.IDLE or task.status != TaskStatus.WAITING:
                continue
            
            task.status = TaskStatus.ASSIGNED
            vehicle.target_node = task.node_id
            vehicle.status = VehicleStatus.MOVING
            
            # 设置路径
            vehicle.path = [task.node_id]
            
            # 重置行驶时间
            self.vehicle_travel_time[vehicle.id] = 0
            
            print(f"[Simulator] 分配任务 {task.id} 给 {vehicle.id}, 从 {vehicle.current_node} 到 {task.node_id}")
    
    def _get_path(self, from_node: str, to_node: str) -> List[str]:
        return self._pathfinder.get_shortest_path(from_node, to_node)
    
    def _get_distance(self, from_node: str, to_node: str) -> float:
        return self._pathfinder.get_distance(from_node, to_node)
    
    def add_test_task(self, task_id: str, node_id: str, weight: float, release_time: float, deadline: float):
        self.tasks[task_id] = Task(
            id=task_id, node_id=node_id, weight=weight, release_time=release_time,
            deadline=deadline, status=TaskStatus.WAITING
        )
        print(f"[Simulator] 添加测试任务: {task_id}")