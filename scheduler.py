# A 组员提供的类
class CityGraph:
    def dijkstra(self, start, end):
        return [] 

#  B 组员提供的类
class VehicleManager:
    def get_all_vehicles(self):
        return []

class Dispatcher:
    def __init__(self, city_graph, vehicle_manager):
        self.city_graph = city_graph
        self.vehicles = vehicle_manager

    def nearest_task_strategy(self):
        # 最近任务优先逻辑
        print("正在计算最近任务...")
        pass

    def largest_task_first_strategy(self):
        # 最大任务优先逻辑
        pass