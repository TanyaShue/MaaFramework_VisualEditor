import math

from PySide6.QtGui import QPolygonF
from PySide6.QtCore import QPointF, QRectF, QLineF, Qt
from PySide6.QtGui import QPainterPath
from PySide6.QtGui import QPolygonF
from PySide6.QtWidgets import QGraphicsPathItem

from src.node_system.connection import Connection


class ConnectionManager:
    def __init__(self, scene, canvas):
        self.scene = scene
        self.canvas = canvas
        self.temp_connection = None
        self.connecting_port = None
        self.connections = []

    def start_connection(self, output_port):
        """开始从输出端口创建一条连线"""
        self.connecting_port = output_port
        start_pos = output_port.mapToScene(output_port.boundingRect().center())
        end_pos = start_pos  # 初始位置重合
        self.temp_connection = self.create_temp_connection(start_pos, end_pos)
        return self.temp_connection

    def update_temp_connection(self, target_pos):
        """更新临时连线的路径"""
        if not self.temp_connection or not self.connecting_port:
            return

        start_pos = self.connecting_port.mapToScene(self.connecting_port.boundingRect().center())
        start_dir = self._get_direction(self.connecting_port.direction)
        path = self.build_temp_connection_path(start_pos, target_pos, start_dir)
        self.temp_connection.setPath(path)

    def finish_connection(self, target_port):
        """完成连线操作，创建实际的 Connection 对象"""
        if not self.connecting_port or not target_port:
            return None

        if not self.can_connect(self.connecting_port, target_port):
            return None

        connection = Connection(self.connecting_port, target_port, self.scene)
        self.connections.append(connection)
        self.cancel_connection()
        return connection

    def cancel_connection(self):
        """取消当前连线操作"""
        if self.temp_connection:
            self.scene.removeItem(self.temp_connection)
            self.temp_connection = None
        self.connecting_port = None

    def create_temp_connection(self, start_pos, end_pos):
        """创建临时连线路径，供视觉反馈使用"""
        from PySide6.QtGui import QPen, QColor
        from PySide6.QtCore import Qt

        if self.connecting_port.port_type == 'next':
            color = QColor(100, 220, 100)
        elif self.connecting_port.port_type == 'on_error':
            color = QColor(220, 100, 100)
        elif self.connecting_port.port_type == 'interrupt':
            color = QColor(220, 180, 100)
        else:
            color = QColor(100, 100, 100)

        temp_connection = QGraphicsPathItem()
        temp_connection.setPen(QPen(color, 2, Qt.DashLine))
        start_dir = self._get_direction(self.connecting_port.direction)
        path = self.build_temp_connection_path(start_pos, end_pos, start_dir)
        temp_connection.setPath(path)
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
        """移除指定的连线"""
        if not connection:
            return

        source = connection.get_source()
        target = connection.get_target()

        if source and hasattr(source, 'connections') and connection in source.connections:
            source.connections.remove(connection)
        if target and hasattr(target, 'connections') and connection in target.connections:
            target.connections.remove(connection)

        self.scene.removeItem(connection)
        if connection in self.connections:
            self.connections.remove(connection)

    def update_connections_for_node(self, node):
        """更新与指定节点有关的所有连线"""
        input_port = node.get_input_port()
        if input_port and hasattr(input_port, 'connections'):
            for connection in input_port.connections:
                if connection:
                    connection.update_path()

        output_ports = node.get_output_ports()
        if isinstance(output_ports, dict):
            output_ports = list(output_ports.values())

        for output_port in output_ports:
            if output_port and hasattr(output_port, 'connections'):
                for connection in output_port.connections:
                    if connection:
                        connection.update_path()

    def _get_direction(self, direction_str):
        """将字符串方向转换为方向向量"""
        if direction_str == 'top':
            return QPointF(0, -1)
        elif direction_str == 'right':
            return QPointF(1, 0)
        elif direction_str == 'bottom':
            return QPointF(0, 1)
        else:  # 'left'
            return QPointF(-1, 0)

    def build_temp_connection_path(self, start_pos, target_pos, start_dir):
        """构建临时连线的路径（较简单，不含节点避让）"""
        ctrl_length = 20
        path = QPainterPath()
        path.moveTo(start_pos)
        current = start_pos + start_dir * ctrl_length
        path.lineTo(current)

        # 根据起始方向决定中间折点
        if abs(start_dir.x()) > 0:
            mid_point = QPointF(current.x(), target_pos.y())
        else:
            mid_point = QPointF(target_pos.x(), current.y())
        path.lineTo(mid_point)
        path.lineTo(target_pos)
        return path

