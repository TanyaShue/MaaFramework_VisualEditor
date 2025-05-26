# port_system.py
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass
from PySide6.QtCore import QObject, Signal, QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QFont
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem


@dataclass
class PortType:
    """端口类型定义"""
    name: str
    color: QColor
    compatible_with: List[str] = None

    def __post_init__(self):
        if self.compatible_with is None:
            self.compatible_with = []

    def can_connect_to(self, other: 'PortType') -> bool:
        """检查是否可以连接到另一个端口类型"""
        if self.name == 'any' or other.name == 'any':
            return True
        if self.name == other.name:
            return True
        if other.name in self.compatible_with:
            return True
        return False


class PortTypeRegistry:
    """端口类型注册器"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._types: Dict[str, PortType] = {}
        self._register_default_types()

    def _register_default_types(self):
        """注册默认端口类型"""
        self.register_type(PortType('any', QColor(150, 150, 150)))
        self.register_type(PortType('flow', QColor(255, 255, 255)))
        self.register_type(PortType('number', QColor(100, 200, 100)))
        self.register_type(PortType('string', QColor(100, 100, 200)))
        self.register_type(PortType('boolean', QColor(200, 100, 100)))
        self.register_type(PortType('vector', QColor(200, 200, 100)))
        self.register_type(PortType('image', QColor(200, 100, 200)))
        self.register_type(PortType('object', QColor(150, 200, 200)))

    def register_type(self, port_type: PortType):
        """注册端口类型"""
        self._types[port_type.name] = port_type

    def get_type(self, name: str) -> Optional[PortType]:
        """获取端口类型"""
        return self._types.get(name)

    def can_connect(self, type1: str, type2: str) -> bool:
        """检查两种类型是否可以连接"""
        t1 = self.get_type(type1)
        t2 = self.get_type(type2)

        if not t1 or not t2:
            return False

        return t1.can_connect_to(t2) or t2.can_connect_to(t1)


class BasePort(QGraphicsItem):
    """端口基类"""

    class Signals(QObject):
        connection_started = Signal(object)  # self
        connection_completed = Signal(object, object)  # self, other_port
        connection_removed = Signal(object)  # connection
        hover_enter = Signal()
        hover_leave = Signal()

    def __init__(self, parent_node: 'BaseNode', config: 'PortConfig', parent=None):
        super().__init__(parent)
        self.parent_node = parent_node
        self.config = config
        self.signals = self.Signals()

        # 端口属性
        self.port_name = config.name
        self.port_type_name = config.data_type
        self.max_connections = config.max_connections

        # 视觉属性
        self.radius = 8
        self.hover_scale = 1.2
        self.is_hovered = False
        self.is_connecting = False

        # 连接列表
        self.connections: List['Connection'] = []

        # 获取端口类型
        self.port_type = PortTypeRegistry().get_type(self.port_type_name)

        # 设置标志
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges)

        # 设置Z值确保端口在节点之上
        self.setZValue(1)

    def boundingRect(self) -> QRectF:
        """获取边界矩形"""
        scale = self.hover_scale if self.is_hovered else 1.0
        r = self.radius * scale
        return QRectF(-r, -r, 2 * r, 2 * r)

    def paint(self, painter: QPainter, option, widget):
        """绘制端口"""
        painter.setRenderHint(QPainter.Antialiasing)

        # 计算当前半径
        scale = self.hover_scale if self.is_hovered else 1.0
        current_radius = self.radius * scale

        # 获取颜色
        color = self.port_type.color if self.port_type else QColor(150, 150, 150)

        # 绘制外圈
        if self.is_hovered or self.is_connecting:
            painter.setPen(QPen(color.lighter(150), 2))
        else:
            painter.setPen(QPen(color.darker(150), 1))

        # 根据连接状态决定填充
        if self.is_connected():
            painter.setBrush(QBrush(color))
        else:
            painter.setBrush(QBrush(color.darker(120)))

        painter.drawEllipse(QPointF(0, 0), current_radius, current_radius)

        # 如果是多连接端口，添加标记
        if self.max_connections != 1:
            painter.setPen(QPen(Qt.white, 1))
            painter.setFont(QFont("Arial", 6))
            painter.drawText(
                QRectF(-current_radius, -current_radius, 2 * current_radius, 2 * current_radius),
                Qt.AlignCenter,
                "+" if self.max_connections == -1 else str(self.max_connections)
            )

    def hoverEnterEvent(self, event):
        """鼠标进入事件"""
        self.is_hovered = True
        self.signals.hover_enter.emit()
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """鼠标离开事件"""
        self.is_hovered = False
        self.signals.hover_leave.emit()
        self.update()
        super().hoverLeaveEvent(event)

    def is_connected(self) -> bool:
        """是否已连接"""
        return len(self.connections) > 0

    def can_accept_connection(self) -> bool:
        """是否可以接受新连接"""
        if self.max_connections == -1:
            return True
        return len(self.connections) < self.max_connections

    def can_connect_to(self, other_port: 'BasePort') -> bool:
        """是否可以连接到另一个端口"""
        # 不能连接到同一节点的端口
        if self.parent_node == other_port.parent_node:
            return False

        # 检查端口类型兼容性
        if not PortTypeRegistry().can_connect(self.port_type_name, other_port.port_type_name):
            return False

        # 检查连接数量限制
        if not self.can_accept_connection() or not other_port.can_accept_connection():
            return False

        # 检查是否已经连接
        for conn in self.connections:
            if conn.get_other_port(self) == other_port:
                return False

        return True

    def add_connection(self, connection: 'Connection'):
        """添加连接"""
        if connection not in self.connections:
            self.connections.append(connection)
            self.update()

    def remove_connection(self, connection: 'Connection'):
        """移除连接"""
        if connection in self.connections:
            self.connections.remove(connection)
            self.signals.connection_removed.emit(connection)
            self.update()

    def get_connections(self) -> List['Connection']:
        """获取所有连接"""
        return self.connections.copy()

    def get_scene_position(self) -> QPointF:
        """获取场景坐标中的位置"""
        return self.mapToScene(QPointF(0, 0))


class InputPort(BasePort):
    """输入端口"""

    def __init__(self, parent_node: 'BaseNode', config: 'PortConfig', parent=None):
        super().__init__(parent_node, config, parent)

    def mousePressEvent(self, event):
        """鼠标按下事件 - 输入端口不能开始连接"""
        event.ignore()


class OutputPort(BasePort):
    """输出端口"""

    def __init__(self, parent_node: 'BaseNode', config: 'PortConfig', parent=None):
        super().__init__(parent_node, config, parent)

    def mousePressEvent(self, event):
        """鼠标按下事件 - 开始连接"""
        if event.button() == Qt.LeftButton:
            self.signals.connection_started.emit(self)
            self.is_connecting = True
            self.update()
            event.accept()
        else:
            super().mousePressEvent(event)


# connection_system.py
class Connection(QGraphicsPathItem):
    """连接线"""

    def __init__(self, source_port: BasePort, target_port: BasePort, parent=None):
        super().__init__(parent)

        self.source_port = source_port
        self.target_port = target_port

        # 视觉属性
        self.normal_width = 3
        self.hover_width = 5
        self.is_hovered = False

        # 动画属性
        self.animation_offset = 0.0

        # 设置标志
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setZValue(-1)  # 在节点下方

        # 更新路径
        self.update_path()

        # 连接端口
        source_port.add_connection(self)
        target_port.add_connection(self)

    def update_path(self):
        """更新连接路径"""
        path = self.calculate_path()
        self.setPath(path)

        # 更新画笔
        self.update_pen()

    def calculate_path(self) -> QPainterPath:
        """计算贝塞尔曲线路径"""
        start = self.source_port.get_scene_position()
        end = self.target_port.get_scene_position()

        path = QPainterPath()
        path.moveTo(start)

        # 计算控制点
        ctrl_distance = abs(end.x() - start.x()) * 0.5
        ctrl_distance = max(ctrl_distance, 50)

        # 根据端口方向确定控制点
        if self.source_port.config.position == 'right':
            ctrl1 = QPointF(start.x() + ctrl_distance, start.y())
        elif self.source_port.config.position == 'left':
            ctrl1 = QPointF(start.x() - ctrl_distance, start.y())
        elif self.source_port.config.position == 'bottom':
            ctrl1 = QPointF(start.x(), start.y() + ctrl_distance)
        else:  # top
            ctrl1 = QPointF(start.x(), start.y() - ctrl_distance)

        if self.target_port.config.position == 'right':
            ctrl2 = QPointF(end.x() + ctrl_distance, end.y())
        elif self.target_port.config.position == 'left':
            ctrl2 = QPointF(end.x() - ctrl_distance, end.y())
        elif self.target_port.config.position == 'bottom':
            ctrl2 = QPointF(end.x(), end.y() + ctrl_distance)
        else:  # top
            ctrl2 = QPointF(end.x(), end.y() - ctrl_distance)

        # 绘制贝塞尔曲线
        path.cubicTo(ctrl1, ctrl2, end)

        return path

    def update_pen(self):
        """更新画笔"""
        # 获取端口类型颜色
        color = self.source_port.port_type.color if self.source_port.port_type else QColor(150, 150, 150)

        # 根据状态调整
        if self.isSelected():
            color = QColor(255, 200, 0)
            width = self.hover_width
        elif self.is_hovered:
            color = color.lighter(120)
            width = self.hover_width
        else:
            width = self.normal_width

        pen = QPen(color, width)
        pen.setCapStyle(Qt.RoundCap)

        # 设置虚线样式用于动画
        if self.source_port.port_type_name == 'flow':
            pen.setStyle(Qt.DashLine)
            pen.setDashPattern([5, 5])
            pen.setDashOffset(self.animation_offset)

        self.setPen(pen)

    def hoverEnterEvent(self, event):
        """鼠标进入事件"""
        self.is_hovered = True
        self.update_pen()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """鼠标离开事件"""
        self.is_hovered = False
        self.update_pen()
        super().hoverLeaveEvent(event)

    def get_other_port(self, port: BasePort) -> Optional[BasePort]:
        """获取连接的另一端端口"""
        if port == self.source_port:
            return self.target_port
        elif port == self.target_port:
            return self.source_port
        return None

    def disconnect(self):
        """断开连接"""
        self.source_port.remove_connection(self)
        self.target_port.remove_connection(self)

        if self.scene():
            self.scene().removeItem(self)


class ConnectionManager:
    """连接管理器"""

    def __init__(self, canvas):
        self.canvas = canvas
        self.connections: List[Connection] = []

        # 临时连接（用于预览）
        self.temp_connection: Optional[QGraphicsPathItem] = None
        self.connecting_port: Optional[OutputPort] = None

        # 连接验证函数
        self.connection_validators: List[Callable] = []

    def start_connection(self, port: OutputPort):
        """开始创建连接"""
        self.connecting_port = port

        # 创建临时连接线
        self.temp_connection = QGraphicsPathItem()
        self.temp_connection.setPen(
            QPen(port.port_type.color if port.port_type else QColor(150, 150, 150), 2, Qt.DashLine)
        )
        self.canvas.scene.addItem(self.temp_connection)

    def update_temp_connection(self, scene_pos: QPointF):
        """更新临时连接线"""
        if not self.temp_connection or not self.connecting_port:
            return

        start = self.connecting_port.get_scene_position()

        path = QPainterPath()
        path.moveTo(start)

        # 简单的直线
        ctrl_distance = abs(scene_pos.x() - start.x()) * 0.5
        ctrl1 = QPointF(start.x() + ctrl_distance, start.y())
        ctrl2 = QPointF(scene_pos.x() - ctrl_distance, scene_pos.y())

        path.cubicTo(ctrl1, ctrl2, scene_pos)

        self.temp_connection.setPath(path)

    def complete_connection(self, target_port: InputPort) -> Optional[Connection]:
        """完成连接"""
        if not self.connecting_port:
            return None

        # 检查是否可以连接
        if not self.connecting_port.can_connect_to(target_port):
            self.cancel_connection()
            return None

        # 运行验证器
        for validator in self.connection_validators:
            if not validator(self.connecting_port, target_port):
                self.cancel_connection()
                return None

        # 创建连接
        connection = Connection(self.connecting_port, target_port)
        self.canvas.scene.addItem(connection)
        self.connections.append(connection)

        # 清理临时连接
        self.cancel_connection()

        # 发送事件
        self.canvas.event_bus.connection_completed.emit(connection)

        return connection

    def cancel_connection(self):
        """取消连接"""
        if self.temp_connection:
            self.canvas.scene.removeItem(self.temp_connection)
            self.temp_connection = None

        if self.connecting_port:
            self.connecting_port.is_connecting = False
            self.connecting_port.update()
            self.connecting_port = None

    def remove_connection(self, connection: Connection):
        """移除连接"""
        if connection in self.connections:
            self.connections.remove(connection)
            connection.disconnect()
            self.canvas.event_bus.connection_removed.emit(connection)

    def remove_connections_for_port(self, port: BasePort):
        """移除端口的所有连接"""
        for conn in port.get_connections():
            self.remove_connection(conn)

    def update_node_connections(self, node: 'BaseNode'):
        """更新节点的所有连接"""
        # 更新输入连接
        for port in node.get_all_input_ports().values():
            for conn in port.get_connections():
                conn.update_path()

        # 更新输出连接
        for port in node.get_all_output_ports().values():
            for conn in port.get_connections():
                conn.update_path()

    def add_connection_validator(self, validator: Callable):
        """添加连接验证器"""
        self.connection_validators.append(validator)

    def clear(self):
        """清空所有连接"""
        for conn in self.connections.copy():
            self.remove_connection(conn)

    def serialize(self) -> List[Dict[str, Any]]:
        """序列化连接数据"""
        data = []
        for conn in self.connections:
            data.append({
                'source_node': conn.source_port.parent_node.node_id,
                'source_port': conn.source_port.port_name,
                'target_node': conn.target_port.parent_node.node_id,
                'target_port': conn.target_port.port_name
            })
        return data

    def deserialize(self, data: List[Dict[str, Any]], node_map: Dict[str, 'BaseNode']):
        """反序列化连接数据"""
        for conn_data in data:
            source_node = node_map.get(conn_data['source_node'])
            target_node = node_map.get(conn_data['target_node'])

            if source_node and target_node:
                source_port = source_node.get_output_port(conn_data['source_port'])
                target_port = target_node.get_input_port(conn_data['target_port'])

                if source_port and target_port:
                    connection = Connection(source_port, target_port)
                    self.canvas.scene.addItem(connection)
                    self.connections.append(connection)