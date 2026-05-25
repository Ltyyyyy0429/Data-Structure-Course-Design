"""仿真引擎核心类 - 统一整数ID版本（累积距离逐节点移动）"""
from typing import Dict, List, Any, Optional
import random
import math
from .models import (
    Node, Edge, Vehicle, Task, ChargingStation, Metrics,
    VehicleStatus, TaskStatus
)

# 导入 A 模块和 C 模块
from core.graph import CityGraph, Node as ANode
from strategy import Dispatcher


class Simulator:
    VEHICLE_SPEED = 40.0  # km/h
    VEHICLE_BATTERY_CAPACITY = 100.0  # kWh
    VEHICLE_LOAD_CAPACITY = 1000.0  # kg
    ENERGY_PER_KM = 1.2  # kWh/km
    CHARGING_RATE = 50.0  # kWh/h
    CHARGING_PORTS_PER_STATION = 2
    
    def __init__(self, graph_data: dict, scale: str, strategy: str):
        self.nodes: Dict[int, Node] = {}
        self.edges: Dict[str, Edge] = {}
        
        # 解析节点（ID 已经是 int）
        for node_data in graph_data.get('nodes', []):
            node = Node(**node_data)
            self.nodes[node.id] = node
        
        # 解析边
        for edge_data in graph_data.get('edges', []):
            edge = Edge(**edge_data)
            key = f"{edge.from_node}->{edge.to_node}"
            self.edges[key] = edge
        
        # 类型映射（你的类型 -> A模块类型）
        type_mapping = {
            'depot': 'warehouse',
            'task_point': 'task',
            'charging_station': 'charging'
        }
        
        # ========== 创建 A 模块的真实图结构 ==========
        self.city_graph = CityGraph()
        
        for node in self.nodes.values():
            a_type = type_mapping.get(node.type, 'normal')
            self.city_graph.add_node(ANode(id=node.id, x=node.x, y=node.y, type=a_type))
        
        for edge in self.edges.values():
            self.city_graph.add_edge(edge.from_node, edge.to_node, edge.distance, bidirectional=True)
        
        print(f"[Simulator] A模块图已加载: {len(self.nodes)} 节点, {len(self.edges)} 边")
        
        self.vehicles: Dict[str, Vehicle] = {}
        self.vehicle_accumulated_distance: Dict[str, float] = {}  # 累积移动距离
        self._init_vehicles()
        
        self.tasks: Dict[str, Task] = {}
        
        self.charging_stations: Dict[int, ChargingStation] = {}
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
        
        # ========== 使用 C 模块的真实调度器 ==========
        self._dispatcher = Dispatcher(self.city_graph, strategy)
        print(f"[Simulator] 使用 C 模块调度器: {strategy}")
        
        print(f"[Simulator] 初始化完成 | 规模: {scale}")
        print(f"[Simulator] 节点数: {len(self.nodes)} | 车辆数: {len(self.vehicles)}")
    
    def _init_vehicles(self):
        depot_nodes = [n for n in self.nodes.values() if n.type == 'depot']
        depot_id = depot_nodes[0].id if depot_nodes else list(self.nodes.keys())[0]
        for i in range(1, 4):
            vehicle = Vehicle(
                id=f"v{i}", current_node=depot_id, battery=self.VEHICLE_BATTERY_CAPACITY,
                load=0.0, status=VehicleStatus.IDLE, target_node=0, path=[]
            )
            self.vehicles[vehicle.id] = vehicle
            self.vehicle_accumulated_distance[vehicle.id] = 0.0
    
    def _init_charging_stations(self):
        for node in self.nodes.values():
            if node.type == 'charging_station':
                self.charging_stations[node.id] = ChargingStation(
                    node_id=node.id, queue_length=0, charging_count=0
                )
    
    def get_state(self) -> dict:
        vehicles_state = [{
            'id': v.id,
            'current_node': v.current_node,
            'battery': round(v.battery, 1),
            'load': round(v.load, 1),
            'status': v.status.value,
            'target_node': v.target_node,
            'path': v.path.copy()
        } for v in self.vehicles.values()]
        
        tasks_state = [{
            'id': t.id,
            'node_id': t.node_id,
            'weight': t.weight,
            'release_time': round(t.release_time, 1),
            'deadline': round(t.deadline, 1),
            'status': t.status.value
        } for t in self.tasks.values()]
        
        nodes_state = [{
            'id': n.id,
            'x': n.x,
            'y': n.y,
            'type': n.type
        } for n in self.nodes.values()]
        
        edges_state = [{
            'from_node': e.from_node,
            'to_node': e.to_node,
            'distance': e.distance
        } for e in self.edges.values()]
        
        charging_stations_state = [{
            'node_id': cs.node_id,
            'queue_length': cs.queue_length,
            'charging_count': cs.charging_count
        } for cs in self.charging_stations.values()]
        
        return {
            'nodes': nodes_state,
            'edges': edges_state,
            'vehicles': vehicles_state,
            'tasks': tasks_state,
            'charging_stations': charging_stations_state,
            'metrics': {
                'current_time': round(self.metrics.current_time, 1),
                'scale': self.metrics.scale,
                'strategy': self.metrics.strategy,
                'total_score': round(self.metrics.total_score, 1),
                'completed_tasks': self.metrics.completed_tasks,
                'timeout_tasks': self.metrics.timeout_tasks,
                'total_distance': round(self.metrics.total_distance, 1),
                'charging_times': self.metrics.charging_times
            }
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
        """移动车辆 - 使用累积距离逐节点移动"""
        dt_hours = dt / 60.0
        distance_per_step = self.VEHICLE_SPEED * dt_hours
        
        for vehicle in self.vehicles.values():
            if vehicle.status != VehicleStatus.MOVING:
                continue
            
            if not vehicle.path:
                vehicle.status = VehicleStatus.IDLE
                vehicle.target_node = 0
                self.vehicle_accumulated_distance[vehicle.id] = 0.0
                continue
            
            # 累积移动距离
            self.vehicle_accumulated_distance[vehicle.id] += distance_per_step
            
            # 检查是否能到达路径中的下一个节点
            next_node = vehicle.path[0]
            dist_to_next = self._get_distance(vehicle.current_node, next_node)
            
            if self.vehicle_accumulated_distance[vehicle.id] >= dist_to_next:
                # 到达下一个节点
                self.metrics.total_distance += dist_to_next
                vehicle.battery -= dist_to_next * self.ENERGY_PER_KM
                vehicle.current_node = next_node
                vehicle.path.pop(0)
                self.vehicle_accumulated_distance[vehicle.id] -= dist_to_next
                
                print(f"[Simulator] {vehicle.id} 到达 {next_node}，剩余电量 {vehicle.battery:.1f}kWh")
                
                # 检查是否还有更多节点
                if not vehicle.path:
                    vehicle.status = VehicleStatus.IDLE
                    vehicle.target_node = 0
                    print(f"[Simulator] {vehicle.id} 到达最终目标")
            else:
                # 还在路上，消耗电量（按实际移动距离）
                vehicle.battery -= distance_per_step * self.ENERGY_PER_KM
                self.metrics.total_distance += distance_per_step
    
    def _handle_charging(self, dt: float):
        dt_hours = dt / 60.0
        charge_amount = self.CHARGING_RATE * dt_hours
        
        vehicles_to_charge = []
        
        for vehicle in self.vehicles.values():
            if vehicle.status == VehicleStatus.CHARGING:
                vehicle.battery += charge_amount
                if vehicle.battery >= self.VEHICLE_BATTERY_CAPACITY:
                    vehicle.battery = self.VEHICLE_BATTERY_CAPACITY
                    vehicle.status = VehicleStatus.IDLE
                    cs = self.charging_stations.get(vehicle.current_node)
                    if cs:
                        cs.charging_count -= 1
                        print(f"[Simulator] {vehicle.id} 充电完成，释放 {vehicle.current_node} 充电桩")
                    vehicles_to_charge.append(vehicle.current_node)
        
        for cs_node in set(vehicles_to_charge):
            cs = self.charging_stations.get(cs_node)
            if cs and cs.queue_length > 0 and cs.charging_count < self.CHARGING_PORTS_PER_STATION:
                for v in self.vehicles.values():
                    if (v.status == VehicleStatus.IDLE and 
                        hasattr(v, 'charging_target') and
                        v.charging_target == cs_node):
                        v.status = VehicleStatus.CHARGING
                        cs.charging_count += 1
                        cs.queue_length -= 1
                        self.vehicle_accumulated_distance[v.id] = 0.0
                        print(f"[Simulator] {v.id} 从排队开始充电 at {cs_node}")
                        break
    
    def _check_low_battery(self):
        for vehicle in self.vehicles.values():
            if vehicle.battery < 20 and vehicle.status == VehicleStatus.IDLE:
                nearest_cs = self._find_nearest_charging_station(vehicle.current_node)
                if not nearest_cs:
                    continue
                
                if vehicle.current_node == nearest_cs:
                    cs = self.charging_stations[nearest_cs]
                    if cs.charging_count < self.CHARGING_PORTS_PER_STATION:
                        cs.charging_count += 1
                        vehicle.status = VehicleStatus.CHARGING
                        self.metrics.charging_times += 1
                        print(f"[Simulator] {vehicle.id} 已在充电站，开始充电")
                    else:
                        cs.queue_length += 1
                        print(f"[Simulator] {vehicle.id} 在 {nearest_cs} 排队充电")
                    continue
                
                # 获取到充电站的路径
                try:
                    path_int, _ = self.city_graph.shortest_path(vehicle.current_node, nearest_cs)
                    path = path_int[1:]  # 去掉第一个（当前位置）
                except:
                    path = [nearest_cs]
                
                vehicle.target_node = nearest_cs
                vehicle.charging_target = nearest_cs
                vehicle.status = VehicleStatus.MOVING
                vehicle.path = path
                self.vehicle_accumulated_distance[vehicle.id] = 0.0
                
                print(f"[Simulator] {vehicle.id} 电量不足 ({vehicle.battery:.1f}kWh)，前往 {nearest_cs} 充电，路径: {path}")
    
    def _find_nearest_charging_station(self, from_node: int) -> Optional[int]:
        try:
            nearest_int, _ = self.city_graph.nearest_node(from_node, 'charging')
            return nearest_int
        except:
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
        completed_tasks = []
        
        for task in self.tasks.values():
            if task.status != TaskStatus.ASSIGNED:
                continue
            
            for vehicle in self.vehicles.values():
                if vehicle.current_node == task.node_id and vehicle.status == VehicleStatus.IDLE:
                    completed_tasks.append(task)
                    break
        
        for task in completed_tasks:
            task.status = TaskStatus.COMPLETED
            time_early = max(0, task.deadline - self.current_time)
            score = 100 + time_early * 2
            self.metrics.total_score += score
            self.metrics.completed_tasks += 1
            
            for vehicle in self.vehicles.values():
                if vehicle.current_node == task.node_id:
                    vehicle.load += task.weight
                    if vehicle.load > self.VEHICLE_LOAD_CAPACITY:
                        self.metrics.total_score -= 50
                        print(f"[Simulator] 警告: {vehicle.id} 超载！扣50分")
                    break
            
            print(f"[Simulator] 任务 {task.id} 完成！得分: {score:.1f} (提前 {time_early:.1f}分钟)")
        
        for task in self.tasks.values():
            if task.status == TaskStatus.WAITING and self.current_time > task.deadline:
                task.status = TaskStatus.TIMEOUT
                self.metrics.total_score -= 100
                self.metrics.timeout_tasks += 1
                print(f"[Simulator] 任务 {task.id} 超时！扣100分")
    
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
            
            # 使用 A 模块获取真实最短路径
            try:
                path_int, _ = self.city_graph.shortest_path(vehicle.current_node, task.node_id)
                vehicle.path = path_int[1:]  # 去掉第一个（当前位置）
                print(f"[Simulator] 分配任务 {task.id} 给 {vehicle.id}, 从 {vehicle.current_node} 到 {task.node_id}, 路径: {vehicle.path}")
            except Exception as e:
                vehicle.path = [task.node_id]
                print(f"[Simulator] 分配任务 {task.id} 给 {vehicle.id}, 路径计算失败: {e}")
            
            self.vehicle_accumulated_distance[vehicle.id] = 0.0
    
    def _get_path(self, from_node: int, to_node: int) -> List[int]:
        try:
            path, _ = self.city_graph.shortest_path(from_node, to_node)
            return path
        except:
            return [from_node, to_node]
    
    def _get_distance(self, from_node: int, to_node: int) -> float:
        try:
            _, distance = self.city_graph.shortest_path(from_node, to_node)
            return distance
        except:
            n1 = self.nodes.get(from_node)
            n2 = self.nodes.get(to_node)
            if n1 and n2:
                return math.sqrt((n1.x - n2.x)**2 + (n1.y - n2.y)**2)
            return 100.0
    
    def add_test_task(self, task_id: str, node_id: int, weight: float, release_time: float, deadline: float):
        self.tasks[task_id] = Task(
            id=task_id, node_id=node_id, weight=weight, release_time=release_time,
            deadline=deadline, status=TaskStatus.WAITING
        )
        print(f"[Simulator] 添加测试任务: {task_id}")