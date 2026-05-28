"""仿真引擎核心类 - 完整修复版（卸货+电量预判+统计指标）"""

from typing import Dict, List, Any, Optional, TYPE_CHECKING
import random
import math
import json
from pathlib import Path
from .models import (
    Node, Edge, Vehicle, Task, ChargingStation, Metrics,
    VehicleStatus, TaskStatus
)

from simulator.pathfinder_adapter import RealPathfinder
from strategy import Dispatcher
from simulator.task_generator import TaskGenerator

if TYPE_CHECKING:
    from core.difficulty import DifficultyConfig


class CityGraphAdapter:
    """适配 CityGraph 到 RealPathfinder 接口"""
    def __init__(self, city_graph):
        self.graph = city_graph
    
    def find_path_and_distance(self, start, end):
        return self.graph.shortest_path(start, end)
    
    def nearest_charging_station(self, start):
        return self.graph.nearest_node(start, 'charging')
    
    def get_state_nodes(self):
        return self.graph.to_state_nodes()
    
    def get_state_edges(self):
        return self.graph.to_state_edges()


class Simulator:
    # ========== 车辆参数（默认值，可被 config 覆盖）==========
    VEHICLE_SPEED = 40.0  # km/h
    VEHICLE_BATTERY_CAPACITY = 80.0  # kWh
    VEHICLE_LOAD_CAPACITY = 1000.0  # kg
    ENERGY_PER_KM = 0.6  # kWh/km
    CHARGING_RATE = 50.0  # kWh/h
    CHARGING_PORTS_PER_STATION = 2
    LOW_BATTERY_THRESHOLD = 35.0  # kWh
    INITIAL_BATTERY_MIN_RATIO = 0.90
    INITIAL_BATTERY_MAX_RATIO = 1.00

    def __init__(self, graph_data: dict = None, scale: str = "small", strategy: str = "nearest",
                 map_file: str = None, pathfinder: RealPathfinder = None, config: "DifficultyConfig" = None):
        self.nodes: Dict[int, Node] = {}
        self.edges: Dict[str, Edge] = {}

        # --- Resolve parameters from config (or fall back to class defaults) ---
        if config is not None:
            vc = config.vehicle
            tc = config.task
            cc = config.charging
            self.speed_kmh = vc.speed_kmh
            self.battery_capacity = vc.battery_capacity_kwh
            self.load_capacity = vc.load_capacity_kg
            self.vehicle_count = vc.count_for_scale(scale)
            self.energy_per_km = vc.energy_per_km
            self.charging_rate = cc.charging_rate_kwh_per_hour
            self.ports_per_station = cc.ports_per_station
            self.low_battery_threshold = vc.low_battery_threshold_kwh()
            self.initial_battery_min, self.initial_battery_max = vc.initial_battery_range_kwh()
            self.task_spawn_probability = tc.spawn_probability
            self.task_gen_interval = tc.spawn_interval_minutes
            self.task_deadline_min = tc.deadline_min
            self.task_deadline_max = tc.deadline_max
            self.task_weight_min = tc.weight_min_kg
            self.task_weight_max = tc.weight_max_kg
            self._task_config = tc
        else:
            self.speed_kmh = self.VEHICLE_SPEED
            self.battery_capacity = self.VEHICLE_BATTERY_CAPACITY
            self.load_capacity = self.VEHICLE_LOAD_CAPACITY
            # 无 config 时按规模设置车辆数
            if scale == "small":
                self.vehicle_count = 5
            elif scale == "medium":
                self.vehicle_count = 10
            elif scale == "large":
                self.vehicle_count = 15
            elif scale == "extra_large":
                self.vehicle_count = 20
            else:
                self.vehicle_count = 3
            self.energy_per_km = self.ENERGY_PER_KM
            self.charging_rate = self.CHARGING_RATE
            self.ports_per_station = self.CHARGING_PORTS_PER_STATION
            self.low_battery_threshold = self.LOW_BATTERY_THRESHOLD
            self.initial_battery_min = self.battery_capacity * self.INITIAL_BATTERY_MIN_RATIO
            self.initial_battery_max = self.battery_capacity * self.INITIAL_BATTERY_MAX_RATIO
            self.task_spawn_probability = 0.3
            self.task_gen_interval = 5.0
            self.task_deadline_min = 60.0
            self.task_deadline_max = 120.0
            self.task_weight_min = 50.0
            self.task_weight_max = 500.0
            self._task_config = None

        # ========== 初始化 pathfinder 和 nodes/edges ==========
        if pathfinder is not None:
            # 方式1：直接传入 pathfinder
            self.pathfinder = pathfinder
            # 需要从 pathfinder 获取节点信息
            state_nodes = self.pathfinder.get_state_nodes()
            for node_id, node_data in state_nodes.items():
                self.nodes[node_id] = Node(
                    id=node_id,
                    x=node_data['x'],
                    y=node_data['y'],
                    type=node_data.get('type', 'normal')
                )
            for edge_data in self.pathfinder.get_state_edges():
                edge = Edge(
                    from_node=edge_data['from'],
                    to_node=edge_data['to'],
                    distance=edge_data['distance']
                )
                key = f"{edge.from_node}->{edge.to_node}"
                self.edges[key] = edge

        elif map_file is not None:
            # 方式2：传入地图文件路径
            self.pathfinder = RealPathfinder(map_file)
            # 从文件加载 nodes/edges
            with open(map_file, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
            
            # 类型映射
            type_mapping_reverse = {
                'warehouse': 'depot',
                'task': 'task_point',
                'charging': 'charging_station',
                'normal': 'normal'
            }
            
            for node_data in file_data.get('nodes', []):
                orig_type = node_data.get('type', 'normal')
                node = Node(
                    id=node_data.get('id'),
                    x=node_data.get('x'),
                    y=node_data.get('y'),
                    type=type_mapping_reverse.get(orig_type, orig_type)
                )
                self.nodes[node.id] = node
            
            for edge_data in file_data.get('edges', []):
                edge = Edge(
                    from_node=edge_data.get('from'),
                    to_node=edge_data.get('to'),
                    distance=edge_data.get('distance')
                )
                key = f"{edge.from_node}->{edge.to_node}"
                self.edges[key] = edge

        elif graph_data is not None:
            # 方式3：传入 graph_data 字典（测试用）
            for node_data in graph_data.get('nodes', []):
                node = Node(**node_data)
                self.nodes[node.id] = node
            for edge_data in graph_data.get('edges', []):
                edge = Edge(**edge_data)
                key = f"{edge.from_node}->{edge.to_node}"
                self.edges[key] = edge
            
            # 使用 CityGraph 作为 pathfinder
            from core.graph import CityGraph, Node as ANode
            type_mapping = {
                'depot': 'warehouse',
                'task_point': 'task',
                'charging_station': 'charging'
            }
            self.city_graph = CityGraph()
            for node in self.nodes.values():
                a_type = type_mapping.get(node.type, 'normal')
                self.city_graph.add_node(ANode(id=node.id, x=node.x, y=node.y, type=a_type))
            for edge in self.edges.values():
                self.city_graph.add_edge(edge.from_node, edge.to_node, edge.distance, bidirectional=True)
            
            # 使用适配器包装 CityGraph
            self.pathfinder = CityGraphAdapter(self.city_graph)

        else:
            raise ValueError("必须提供 graph_data、map_file 或 pathfinder 之一")

        print(f"[Simulator] 图已加载: {len(self.nodes)} 节点, {len(self.edges)} 边")

        self.depot_ids = [n.id for n in self.nodes.values() if n.type == 'depot']

        self.vehicles: Dict[str, Vehicle] = {}
        self.vehicle_accumulated_distance: Dict[str, float] = {}
        self.task_travel_distance: Dict[str, float] = {}
        self.saved_tasks: Dict[str, Optional[str]] = {}
        self.vehicle_active_task: Dict[str, Optional[str]] = {}
        self._init_vehicles()

        self.tasks: Dict[str, Task] = {}

        self.charging_stations: Dict[int, ChargingStation] = {}
        self._init_charging_stations()

        self.charging_start_time: Dict[str, float] = {}
        self.charging_wait_start_time: Dict[str, float] = {}
        self.queued_vehicle_ids: set[str] = set()
        self.active_charging_request_vehicle_ids: set[str] = set()

        # 确保 Metrics 包含所有需要的字段
        self.metrics = Metrics(
            current_time=0.0, scale=scale, strategy=strategy,
            total_score=0.0, completed_tasks=0, timeout_tasks=0,
            total_distance=0.0, charging_times=0
        )
        # 添加扩展字段
        if not hasattr(self.metrics, 'low_battery_events'):
            self.metrics.low_battery_events = 0
        if not hasattr(self.metrics, 'charging_requests'):
            self.metrics.charging_requests = 0
        if not hasattr(self.metrics, 'charging_queue_events'):
            self.metrics.charging_queue_events = 0
        if not hasattr(self.metrics, 'total_charging_wait_time'):
            self.metrics.total_charging_wait_time = 0.0
        if not hasattr(self.metrics, 'max_queue_length'):
            self.metrics.max_queue_length = 0

        self.current_time = 0.0
        self.next_task_id = 1
        self.task_gen_timer = 0.0

        # TaskGenerator
        task_points = [n.id for n in self.nodes.values() if n.type == 'task_point']
        self._task_generator = TaskGenerator(task_points, self._task_config) if task_points else None

        # Dispatcher
        self._dispatcher = Dispatcher(
            self.pathfinder,
            strategy,
            consume_rate=self.energy_per_km,
            load_capacity=self.load_capacity,
        )
        print(f"[Simulator] 使用 C 模块调度器: {strategy}")

        print(f"[Simulator] 初始化完成 | 规模: {scale}")
        print(f"[Simulator] 节点数: {len(self.nodes)} | 车辆数: {len(self.vehicles)}")
        print(
            f"[Simulator] 电池容量: {self.battery_capacity}kWh, "
            f"能耗: {self.energy_per_km}kWh/km, "
            f"低电量阈值: {self.low_battery_threshold:.1f}kWh, "
            f"初始电量范围: {self.initial_battery_min:.1f}-{self.initial_battery_max:.1f}kWh"
        )
    
    def _init_vehicles(self):
        depot_nodes = [n for n in self.nodes.values() if n.type == 'depot']
        depot_id = depot_nodes[0].id if depot_nodes else list(self.nodes.keys())[0]
        for i in range(1, self.vehicle_count + 1):
            initial_battery = random.uniform(self.initial_battery_min, self.initial_battery_max)
            vehicle = Vehicle(
                id=f"v{i}", current_node=depot_id, battery=round(initial_battery, 1),
                load=0.0, status=VehicleStatus.IDLE, target_node=0, path=[]
            )
            self.vehicles[vehicle.id] = vehicle
            self.vehicle_accumulated_distance[vehicle.id] = 0.0
            self.saved_tasks[vehicle.id] = None
            self.vehicle_active_task[vehicle.id] = None
    
    def _init_charging_stations(self):
        for node in self.nodes.values():
            if node.type == 'charging_station':
                self.charging_stations[node.id] = ChargingStation(
                    node_id=node.id, queue_length=0, charging_count=0
                )

    def _record_charging_request(self, vehicle: Vehicle) -> None:
        if vehicle.id in self.active_charging_request_vehicle_ids:
            return
        self.active_charging_request_vehicle_ids.add(vehicle.id)
        self.metrics.charging_requests += 1

    def _start_charging(self, vehicle: Vehicle, station: ChargingStation) -> None:
        station.charging_count += 1
        vehicle.status = VehicleStatus.CHARGING
        self.metrics.charging_times += 1

    def _queue_for_charging(self, vehicle: Vehicle, station: ChargingStation) -> None:
        if vehicle.id in self.queued_vehicle_ids and vehicle.status != VehicleStatus.WAITING_FOR_CHARGE:
            self.queued_vehicle_ids.discard(vehicle.id)
            if station.queue_length > 0:
                station.queue_length -= 1
        if vehicle.id not in self.queued_vehicle_ids:
            station.queue_length += 1
            self.queued_vehicle_ids.add(vehicle.id)
            self.charging_wait_start_time[vehicle.id] = self.current_time
            self.metrics.charging_queue_events += 1
            self.metrics.max_queue_length = max(
                self.metrics.max_queue_length,
                station.queue_length,
            )
        vehicle.status = VehicleStatus.WAITING_FOR_CHARGE
        vehicle.charging_target = station.node_id
    
    def get_state(self) -> dict:
        vehicles_state = [{
            'id': v.id,
            'current_node': v.current_node,
            'battery': round(v.battery, 1),
            'max_battery': round(self.battery_capacity, 1),
            'load': round(v.load, 1),
            'max_load': round(self.load_capacity, 1),
            'load_capacity': round(self.load_capacity, 1),
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
                'charging_times': self.metrics.charging_times,
                'low_battery_events': getattr(self.metrics, 'low_battery_events', 0),
                'charging_requests': getattr(self.metrics, 'charging_requests', 0),
                'charging_queue_events': getattr(self.metrics, 'charging_queue_events', 0),
                'total_charging_wait_time': round(getattr(self.metrics, 'total_charging_wait_time', 0), 1),
                'max_queue_length': getattr(self.metrics, 'max_queue_length', 0)
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
        dt_hours = dt / 60.0
        distance_per_step = self.speed_kmh * dt_hours

        for vehicle in self.vehicles.values():
            if vehicle.status != VehicleStatus.MOVING:
                continue

            remaining_to_target = max(
                0.0,
                self._get_distance(vehicle.current_node, vehicle.target_node)
                - self.vehicle_accumulated_distance[vehicle.id],
            )
            nearest_cs, charger_dist = self.pathfinder.nearest_charging_station(
                vehicle.target_node
            )
            if nearest_cs is not None:
                required_energy = (remaining_to_target + charger_dist) * self.energy_per_km
            else:
                required_energy = remaining_to_target * self.energy_per_km * 1.5
            if vehicle.battery < required_energy:
                nearest_cs = self._find_nearest_charging_station(vehicle.current_node)
                if nearest_cs is not None and nearest_cs != vehicle.current_node:
                    already_heading_to_charger = (
                        getattr(vehicle, 'charging_target', None) == nearest_cs
                        and vehicle.target_node == nearest_cs
                    )
                    if not already_heading_to_charger:
                        self.metrics.low_battery_events += 1
                        self._record_charging_request(vehicle)

                        if vehicle.target_node != 0 and vehicle.target_node != nearest_cs:
                            task_id = self.vehicle_active_task.get(vehicle.id)
                            if task_id is None:
                                for task in self.tasks.values():
                                    if task.status == TaskStatus.ASSIGNED and task.node_id == vehicle.target_node:
                                        task_id = task.id
                                        break
                            if task_id:
                                self.saved_tasks[vehicle.id] = task_id
                                print(f"[Simulator] {vehicle.id} 电量不足 ({vehicle.battery:.1f}kWh)，中断任务 {task_id} 前往充电站")

                        path_int, _ = self.pathfinder.find_path_and_distance(vehicle.current_node, nearest_cs)
                        vehicle.path = path_int[1:] if len(path_int) > 1 else []

                        vehicle.charging_target = nearest_cs
                        vehicle.target_node = nearest_cs
                        self.vehicle_accumulated_distance[vehicle.id] = 0.0
                        continue
            
            if not vehicle.path:
                vehicle.status = VehicleStatus.IDLE
                vehicle.target_node = 0
                self.vehicle_accumulated_distance[vehicle.id] = 0.0
                self._resume_saved_task(vehicle)
                continue
            
            next_node = vehicle.path[0]
            dist = self._get_distance(vehicle.current_node, next_node)
            
            if dist <= 0:
                vehicle.path.pop(0)
                continue
            
            self.vehicle_accumulated_distance[vehicle.id] += distance_per_step
            
            if self.vehicle_accumulated_distance[vehicle.id] >= dist:
                self.metrics.total_distance += dist
                vehicle.battery = max(0.0, vehicle.battery - dist * self.energy_per_km)
                old_node = vehicle.current_node
                vehicle.current_node = next_node
                vehicle.path.pop(0)
                self.vehicle_accumulated_distance[vehicle.id] -= dist
                
                print(f"[Simulator] {vehicle.id} 从 {old_node} 到达 {next_node}，剩余电量 {vehicle.battery:.1f}kWh")
                
                if not vehicle.path:
                    vehicle.status = VehicleStatus.IDLE
                    vehicle.target_node = 0
                    print(f"[Simulator] {vehicle.id} 到达最终目标")
            else:
                vehicle.battery = max(0.0, vehicle.battery - distance_per_step * self.energy_per_km)
                self.metrics.total_distance += distance_per_step
    
    def _handle_charging(self, dt: float):
        dt_hours = dt / 60.0
        charge_amount = self.charging_rate * dt_hours

        for vehicle in self.vehicles.values():
            if vehicle.status != VehicleStatus.CHARGING:
                continue

            vehicle.battery += charge_amount
            if vehicle.battery >= self.battery_capacity:
                vehicle.battery = self.battery_capacity
                vehicle.status = VehicleStatus.IDLE
                self.active_charging_request_vehicle_ids.discard(vehicle.id)
                cs = self.charging_stations.get(vehicle.current_node)
                if cs:
                    cs.charging_count = max(0, cs.charging_count - 1)
                    print(f"[Simulator] {vehicle.id} 充电完成，释放 {vehicle.current_node} 充电桩")
                
                if cs and cs.queue_length > 0:
                    for v in self.vehicles.values():
                        if (hasattr(v, 'charging_target') and 
                            v.charging_target == vehicle.current_node and
                            (v.status == VehicleStatus.WAITING_FOR_CHARGE or
                             (v.status == VehicleStatus.IDLE and v.id in self.queued_vehicle_ids))):
                            v.status = VehicleStatus.CHARGING
                            cs.charging_count += 1
                            cs.queue_length = max(0, cs.queue_length - 1)
                            self.metrics.charging_times += 1
                            self.queued_vehicle_ids.discard(v.id)
                            wait_start = self.charging_wait_start_time.pop(v.id, None)
                            if wait_start is not None:
                                self.metrics.total_charging_wait_time += max(
                                    0.0,
                                    self.current_time - wait_start,
                                )
                            print(f"[Simulator] {v.id} 从排队开始充电")
                            break

                self._resume_saved_task(vehicle)
    
    def _check_low_battery(self):
        for vehicle in self.vehicles.values():
            if vehicle.battery < self.low_battery_threshold and vehicle.status == VehicleStatus.IDLE:
                self.metrics.low_battery_events += 1
                nearest_cs = self._find_nearest_charging_station(vehicle.current_node)
                if nearest_cs is None:
                    continue
                
                if vehicle.current_node == nearest_cs:
                    cs = self.charging_stations.get(nearest_cs)
                    if cs is None:
                        continue
                    self._record_charging_request(vehicle)
                    if cs.charging_count < self.ports_per_station:
                        self._start_charging(vehicle, cs)
                        print(f"[Simulator] {vehicle.id} 电量不足 ({vehicle.battery:.1f}kWh)，开始在 {nearest_cs} 充电")
                    else:
                        self._queue_for_charging(vehicle, cs)
                        print(f"[Simulator] {vehicle.id} 电量不足 ({vehicle.battery:.1f}kWh)，在 {nearest_cs} 排队")
                    continue
                
                path_int, _ = self.pathfinder.find_path_and_distance(vehicle.current_node, nearest_cs)
                vehicle.path = path_int[1:] if len(path_int) > 1 else []

                vehicle.charging_target = nearest_cs
                vehicle.target_node = nearest_cs
                vehicle.status = VehicleStatus.MOVING
                self._record_charging_request(vehicle)
                self.vehicle_accumulated_distance[vehicle.id] = 0.0
                print(f"[Simulator] {vehicle.id} 电量不足 ({vehicle.battery:.1f}kWh)，前往 {nearest_cs} 充电")

    def _resume_saved_task(self, vehicle: Vehicle) -> bool:
        saved_task_id = self.saved_tasks.get(vehicle.id)
        if not saved_task_id:
            return False

        saved_task = self.tasks.get(saved_task_id)
        self.saved_tasks[vehicle.id] = None

        if not saved_task or saved_task.status != TaskStatus.ASSIGNED:
            if self.vehicle_active_task.get(vehicle.id) == saved_task_id:
                self.vehicle_active_task[vehicle.id] = None
            return False

        vehicle.target_node = saved_task.node_id
        vehicle.status = VehicleStatus.MOVING
        self.vehicle_active_task[vehicle.id] = saved_task_id
        path_int, _ = self.pathfinder.find_path_and_distance(vehicle.current_node, saved_task.node_id)
        vehicle.path = path_int[1:] if len(path_int) > 1 else []
        self.vehicle_accumulated_distance[vehicle.id] = 0.0
        print(f"[Simulator] {vehicle.id} 继续执行任务 {saved_task_id}")
        return True
    
    def _find_nearest_charging_station(self, from_node: int) -> Optional[int]:
        nearest_int, _ = self.pathfinder.nearest_charging_station(from_node)
        return nearest_int if nearest_int is not None else None
    
    def _can_reach_and_return(self, vehicle, task_node_id: int) -> bool:
        """检查车辆是否有足够电量到达任务节点并安全返回"""
        if self.pathfinder is None:
            return True
        
        try:
            _, d1 = self.pathfinder.find_path_and_distance(vehicle.current_node, task_node_id)
            nearest_cs, d2 = self.pathfinder.nearest_charging_station(task_node_id)
            if self.depot_ids:
                _, d3 = self.pathfinder.find_path_and_distance(task_node_id, self.depot_ids[0])
            else:
                d3 = float("inf")
            recovery_dist = min(d2, d3) if nearest_cs is not None else d3
            return vehicle.battery >= (d1 + recovery_dist) * self.energy_per_km + 5.0
        except Exception as e:
            print(f"[Simulator] 能量检查异常: {e}")
            return True

    def _check_tasks_completion(self):
        completed_tasks = []
        
        for task in self.tasks.values():
            if task.status != TaskStatus.ASSIGNED:
                continue
            
            for vehicle in self.vehicles.values():
                if (vehicle.current_node == task.node_id and
                    vehicle.status == VehicleStatus.IDLE and
                    self.vehicle_active_task.get(vehicle.id) == task.id):
                    completed_tasks.append((task, vehicle))
                    break
        
        for task, vehicle in completed_tasks:
            task.status = TaskStatus.COMPLETED
            time_early = max(0, task.deadline - self.current_time)
            task_dist = self.task_travel_distance.pop(task.id, 0.0)
            score = 100 + time_early * 2 - task_dist * 0.3
            score = max(score, 0)
            self.metrics.total_score += score
            self.metrics.completed_tasks += 1

            if vehicle.load > self.load_capacity:
                self.metrics.total_score -= 50
                print(f"[Simulator] 警告: 调度阶段未拦截 {vehicle.id} 超载任务，已扣50分")
            vehicle.load = max(0.0, vehicle.load - task.weight)
            if self.vehicle_active_task.get(vehicle.id) == task.id:
                self.vehicle_active_task[vehicle.id] = None
            if self.saved_tasks.get(vehicle.id) == task.id:
                self.saved_tasks[vehicle.id] = None
            
            print(f"[Simulator] 任务 {task.id} 完成！得分: {score:.1f}")
        
        for task in self.tasks.values():
            if task.status in (TaskStatus.WAITING, TaskStatus.ASSIGNED) and self.current_time > task.deadline:
                task.status = TaskStatus.TIMEOUT
                self.metrics.total_score -= 100
                self.metrics.timeout_tasks += 1
                self.task_travel_distance.pop(task.id, None)
                unloaded_vehicle_ids = set()
                for vehicle_id, active_task_id in list(self.vehicle_active_task.items()):
                    vehicle = self.vehicles.get(vehicle_id)
                    if active_task_id == task.id:
                        if vehicle and vehicle_id not in unloaded_vehicle_ids:
                            vehicle.load = max(0.0, vehicle.load - task.weight)
                            unloaded_vehicle_ids.add(vehicle_id)
                        self.vehicle_active_task[vehicle_id] = None
                    if self.saved_tasks.get(vehicle_id) == task.id:
                        if vehicle and vehicle_id not in unloaded_vehicle_ids:
                            vehicle.load = max(0.0, vehicle.load - task.weight)
                            unloaded_vehicle_ids.add(vehicle_id)
                        self.saved_tasks[vehicle_id] = None
                print(f"[Simulator] 任务 {task.id} 超时！扣100分")
    
    def _generate_new_tasks(self, dt: float):
        self.task_gen_timer += dt
        if self.task_gen_timer < self.task_gen_interval:
            return
        self.task_gen_timer = 0

        task_points = [n.id for n in self.nodes.values() if n.type == 'task_point']
        if not task_points:
            return

        if self._task_generator is not None and self._task_config is not None:
            new_tasks = self._task_generator.generate_tasks(self.current_time)
            for td in new_tasks:
                task = Task(
                    id=f"t{self.next_task_id}",
                    node_id=td["node_id"],
                    weight=td["weight"],
                    release_time=td["release_time"],
                    deadline=td["deadline"],
                    status=TaskStatus.WAITING,
                )
                self.tasks[task.id] = task
                self.next_task_id += 1
                print(f"[Simulator] 新任务 {task.id}: 重量{task.weight}kg, 截止{task.deadline:.1f}min")
            return

        if random.random() < self.task_spawn_probability:
            task = Task(
                id=f"t{self.next_task_id}",
                node_id=random.choice(task_points),
                weight=random.randint(int(self.task_weight_min), int(self.task_weight_max)),
                release_time=self.current_time,
                deadline=self.current_time + random.randint(int(self.task_deadline_min), int(self.task_deadline_max)),
                status=TaskStatus.WAITING,
            )
            self.tasks[task.id] = task
            self.next_task_id += 1
            print(f"[Simulator] 新任务 {task.id}: 重量{task.weight}kg, 截止{task.deadline:.1f}min")
    
    def _dispatch_tasks(self):
        actions = self._dispatcher.dispatch(self.get_state())
        print(f"[DEBUG] 调度器返回 {len(actions)} 条指令")
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
            if vehicle.load + task.weight > self.load_capacity:
                print(f"[Simulator] 跳过超载分配 {task.id} 给 {vehicle.id}")
                continue
            if not self._can_reach_and_return(vehicle, task.node_id):
                print(f"[Simulator] 跳过电量不足分配 {task.id} 给 {vehicle.id}")
                continue

            task.status = TaskStatus.ASSIGNED
            vehicle.load += task.weight
            vehicle.target_node = task.node_id
            vehicle.status = VehicleStatus.MOVING
            self.vehicle_active_task[vehicle.id] = task.id
            self.saved_tasks[vehicle.id] = None

            # 获取路径
            try:
                path_int, _ = self.pathfinder.find_path_and_distance(vehicle.current_node, task.node_id)
                if path_int and path_int[0] == vehicle.current_node:
                    vehicle.path = path_int[1:]
                else:
                    vehicle.path = path_int
                print(f"[Simulator] 分配任务 {task.id} 给 {vehicle.id}, 从 {vehicle.current_node} 到 {task.node_id}")
            except Exception as e:
                vehicle.path = [task.node_id]
                print(f"[Simulator] 分配任务 {task.id} 给 {vehicle.id}, 路径计算失败: {e}")

            self.vehicle_accumulated_distance[vehicle.id] = 0.0
            _, task_dist = self.pathfinder.find_path_and_distance(vehicle.current_node, task.node_id)
            self.task_travel_distance[task.id] = task_dist

    def _get_path(self, from_node: int, to_node: int) -> List[int]:
        path, _ = self.pathfinder.find_path_and_distance(from_node, to_node)
        return path

    def _get_distance(self, from_node: int, to_node: int) -> float:
        try:
            _, distance = self.pathfinder.find_path_and_distance(from_node, to_node)
            return distance
        except Exception:
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
        self.next_task_id = max(self.next_task_id, len(self.tasks) + 1000)
        print(f"[Simulator] 添加测试任务: {task_id}")
