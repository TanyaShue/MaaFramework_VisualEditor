from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor
from PySide6.QtWidgets import QGraphicsPathItem

from src.node_system.connection import Connection, build_connection_path


class ConnectionManager:
    def __init__(self, scene, canvas):
        self.scene = scene
        self.canvas = canvas
        self.temp_connection = None
        self.connecting_port = None
        self.connections = []

        # 性能优化：添加节点-连接映射表
        self.node_connection_map = {}  # 节点 -> 连接列表的映射

        # 性能优化：添加临时连接缓存
        self.last_temp_target_pos = None
        self.temp_connection_update_counter = 0

    def start_connection(self, output_port):
        """开始从输出端口创建一条连线"""
        self.connecting_port = output_port
        start_pos = output_port.mapToScene(output_port.boundingRect().center())
        self.temp_connection = self.create_temp_connection(start_pos, start_pos)
        self.last_temp_target_pos = None  # 重置临时目标位置
        return self.temp_connection

    def update_temp_connection(self, target_pos):
        """更新临时连线的路径 - 性能优化版本"""
        if not self.temp_connection or not self.connecting_port:
            return

        # 性能优化：限制更新频率
        self.temp_connection_update_counter += 1
        if self.temp_connection_update_counter % 2 != 0:  # 每两帧更新一次
            return

        # 性能优化：检查目标位置是否有明显变化
        if self.last_temp_target_pos is not None:
            dx = abs(target_pos.x() - self.last_temp_target_pos.x())
            dy = abs(target_pos.y() - self.last_temp_target_pos.y())
            # 如果移动不到5个像素，不更新
            if dx < 5 and dy < 5:
                return

        # 更新临时连接路径
        path = build_connection_path(self.connecting_port, None, target_pos)
        self.temp_connection.setPath(path)
        self.last_temp_target_pos = target_pos

    def finish_connection(self, target_port):
        """完成连线操作，创建实际的 Connection 对象"""
        if not self.connecting_port or not target_port:
            return None

        if not self.can_connect(self.connecting_port, target_port):
            return None

        # 创建连接
        connection = Connection(self.connecting_port, target_port, self.scene)
        self.connections.append(connection)

        # 更新节点-连接映射
        source_node = self.connecting_port.parent_node
        target_node = target_port.parent_node

        # 为源节点添加连接引用
        if source_node not in self.node_connection_map:
            self.node_connection_map[source_node] = []
        self.node_connection_map[source_node].append(connection)

        # 为目标节点添加连接引用
        if target_node not in self.node_connection_map:
            self.node_connection_map[target_node] = []
        self.node_connection_map[target_node].append(connection)

        self.cancel_connection()
        return connection

    def cancel_connection(self):
        """取消当前连线操作"""
        if self.temp_connection:
            self.scene.removeItem(self.temp_connection)
            self.temp_connection = None
        self.connecting_port = None
        self.last_temp_target_pos = None
        self.temp_connection_update_counter = 0

    def create_temp_connection(self, start_pos, end_pos):
        """创建临时连线路径，供视觉反馈使用"""
        if not self.connecting_port:
            return None

        # 根据端口类型确定颜色
        port_type = getattr(self.connecting_port, 'port_type', '')
        if port_type == 'next':
            color = QColor(100, 220, 100)
        elif port_type == 'on_error':
            color = QColor(220, 100, 100)
        elif port_type == 'interrupt':
            color = QColor(220, 180, 100)
        else:
            color = QColor(100, 100, 100)

        temp_connection = QGraphicsPathItem()
        pen = QPen(color, 2, Qt.DashLine)

        # 设置虚线样式
        dash_pattern = [4, 4]  # 4个单位的线，4个单位的空白
        pen.setDashPattern(dash_pattern)

        temp_connection.setPen(pen)

        # 初始路径 - 将在update_temp_connection中更新
        path = build_connection_path(self.connecting_port, None, end_pos)
        temp_connection.setPath(path)
        temp_connection.setZValue(-0.5)  # 确保临时连接显示在其他连接上方
        self.scene.addItem(temp_connection)
        return temp_connection

    def can_connect(self, source_port, target_port):
        """检查两个端口是否可以连接（例如，不能连接同一节点，且端口类型必须兼容）"""
        if not source_port or not target_port:
            return False

        if source_port.parent_node == target_port.parent_node:
            return False

        if not source_port.can_connect(target_port):
            return False

        return True

    def remove_connection(self, connection):
        """移除指定的连线 - 优化版本"""
        if not connection:
            return

        source = connection.get_source()
        target = connection.get_target()

        # 更新端口的连接列表
        if source and hasattr(source, 'connections') and connection in source.connections:
            source.connections.remove(connection)

        if target and hasattr(target, 'connections') and connection in target.connections:
            target.connections.remove(connection)

        # 更新节点-连接映射
        if source and hasattr(source, 'parent_node'):
            source_node = source.parent_node
            if source_node in self.node_connection_map and connection in self.node_connection_map[source_node]:
                self.node_connection_map[source_node].remove(connection)

        if target and hasattr(target, 'parent_node'):
            target_node = target.parent_node
            if target_node in self.node_connection_map and connection in self.node_connection_map[target_node]:
                self.node_connection_map[target_node].remove(connection)

        # 从场景中移除
        self.scene.removeItem(connection)

        # 从连接列表中移除
        if connection in self.connections:
            self.connections.remove(connection)

    def update_connections_for_node(self, node):
        """更新与指定节点有关的所有连线 - 优化版本"""
        # 使用节点-连接映射快速查找相关连接
        if node in self.node_connection_map:
            for connection in self.node_connection_map[node]:
                if connection:
                    # 标记路径为脏，将在下次绘制时更新
                    connection.path_is_dirty = True
                    connection.update_path()

        # 兼容旧版行为（以防节点尚未添加到映射表）
        if node not in self.node_connection_map:
            # 通过端口查找连接
            self._update_connections_via_ports(node)

            # 创建映射表项
            self.node_connection_map[node] = []

            # 收集所有连接
            input_port = node.get_input_port()
            if input_port and hasattr(input_port, 'connections'):
                for conn in input_port.connections:
                    if conn and conn not in self.node_connection_map[node]:
                        self.node_connection_map[node].append(conn)

            output_ports = node.get_output_ports()
            if isinstance(output_ports, dict):
                output_ports = list(output_ports.values())

            for output_port in output_ports:
                if output_port and hasattr(output_port, 'connections'):
                    for conn in output_port.connections:
                        if conn and conn not in self.node_connection_map[node]:
                            self.node_connection_map[node].append(conn)

    def _update_connections_via_ports(self, node):
        """通过节点的端口更新连接 (兼容旧方法)"""
        input_port = node.get_input_port()
        if input_port and hasattr(input_port, 'connections'):
            for connection in input_port.connections:
                if connection:
                    connection.path_is_dirty = True
                    connection.update_path()

        output_ports = node.get_output_ports()
        if isinstance(output_ports, dict):
            output_ports = list(output_ports.values())

        for output_port in output_ports:
            if output_port and hasattr(output_port, 'connections'):
                for connection in output_port.connections:
                    if connection:
                        connection.path_is_dirty = True
                        connection.update_path()

    def batch_update_connections(self, nodes):
        """批量更新多个节点的连接"""
        # 收集所有需要更新的连接
        connections_to_update = set()

        for node in nodes:
            if node in self.node_connection_map:
                connections_to_update.update(self.node_connection_map[node])

        # 批量更新
        for connection in connections_to_update:
            if connection:
                connection.path_is_dirty = True
                connection.update_path()