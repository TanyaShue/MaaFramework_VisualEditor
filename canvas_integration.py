#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
带连接功能的画布系统示例
包含节点、端口和连接的完整实现
"""

import sys
import time
from typing import Dict, Any, List, Optional, Type, Tuple
from dataclasses import dataclass, field
from abc import ABCMeta, abstractmethod

from PySide6.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
                               QVBoxLayout, QWidget, QToolBar, QDockWidget, QListWidget,
                               QPushButton, QLabel, QGraphicsItem, QGraphicsPathItem,
                               QGraphicsEllipseItem)
from PySide6.QtCore import (Qt, QPointF, QRectF, QObject, Signal, QTimer,
                            QElapsedTimer, QLineF)
from PySide6.QtGui import (QPainter, QColor, QPen, QBrush, QFont, QPainterPath,
                           QWheelEvent, QMouseEvent, QKeyEvent, QAction, QTransform)


# ============ 基础数据结构 ============
@dataclass
class PortConfig:
    """端口配置"""
    name: str
    port_type: str  # 'input' or 'output'
    data_type: str = 'any'
    position: str = 'auto'  # 'top', 'bottom', 'left', 'right'
    max_connections: int = -1
    color: Optional[str] = None


@dataclass
class NodeMetadata:
    """节点元数据"""
    type_id: str
    display_name: str
    category: str
    description: str = ""
    color_scheme: Dict[str, str] = field(default_factory=dict)
    default_size: tuple = (240, 200)
    resizable: bool = True
    ports: List[PortConfig] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)


# ============ 节点注册系统 ============
class NodeRegistry:
    """节点类型注册器（单例）"""
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
        self._node_types: Dict[str, Type['BaseNode']] = {}
        self._node_metadata: Dict[str, NodeMetadata] = {}
        self._categories: Dict[str, List[str]] = {}

    def register_node_type(self, node_class: Type['BaseNode'], metadata: NodeMetadata):
        """注册节点类型"""
        type_id = metadata.type_id

        if type_id in self._node_types:
            raise ValueError(f"Node type '{type_id}' already registered")

        self._node_types[type_id] = node_class
        self._node_metadata[type_id] = metadata

        category = metadata.category
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(type_id)

    def create_node(self, type_id: str, node_id: str) -> 'BaseNode':
        """创建节点实例"""
        if type_id not in self._node_types:
            raise ValueError(f"Unknown node type: {type_id}")

        node_class = self._node_types[type_id]
        metadata = self._node_metadata[type_id]
        return node_class(node_id=node_id, metadata=metadata)

    def get_metadata(self, type_id: str) -> Optional[NodeMetadata]:
        """获取节点元数据"""
        return self._node_metadata.get(type_id)

    def get_categories(self) -> Dict[str, List[str]]:
        """获取所有分类"""
        return self._categories.copy()


# ============ 端口类 ============
class Port(QGraphicsEllipseItem):
    """端口基类"""

    def __init__(self, parent_node: 'BaseNode', config: PortConfig, parent=None):
        # 端口大小
        self.radius = 8
        super().__init__(-self.radius, -self.radius, 2 * self.radius, 2 * self.radius, parent)

        self.parent_node = parent_node
        self.config = config
        self.connections = []

        # 设置外观
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CrossCursor)

        # 根据端口类型设置颜色
        color = QColor(config.color) if config.color else self._get_default_color()
        self.setBrush(QBrush(color))
        self.setPen(QPen(color.darker(150), 1))

        # 设置Z值确保端口在节点之上
        self.setZValue(1)

    def _get_default_color(self) -> QColor:
        """获取默认颜色"""
        if self.config.data_type == 'flow':
            return QColor(255, 255, 255)
        elif self.config.data_type == 'number':
            return QColor(100, 200, 100)
        elif self.config.data_type == 'string':
            return QColor(100, 100, 200)
        else:
            return QColor(150, 150, 150)

    def hoverEnterEvent(self, event):
        """鼠标进入事件"""
        self.setPen(QPen(self.brush().color().lighter(150), 2))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """鼠标离开事件"""
        self.setPen(QPen(self.brush().color().darker(150), 1))
        super().hoverLeaveEvent(event)

    def add_connection(self, connection):
        """添加连接"""
        if connection not in self.connections:
            self.connections.append(connection)

    def remove_connection(self, connection):
        """移除连接"""
        if connection in self.connections:
            self.connections.remove(connection)

    def get_scene_pos(self) -> QPointF:
        """获取场景坐标位置"""
        return self.mapToScene(0, 0)


class InputPort(Port):
    """输入端口"""

    def mousePressEvent(self, event):
        """输入端口不能开始连接"""
        event.ignore()


class OutputPort(Port):
    """输出端口"""

    def mousePressEvent(self, event):
        """鼠标按下开始连接"""
        if event.button() == Qt.LeftButton:
            # 通知画布开始连接
            if hasattr(self.parent_node, 'canvas'):
                self.parent_node.canvas.start_connection(self)
            event.accept()
        else:
            super().mousePressEvent(event)


# ============ 连接类 ============
class Connection(QGraphicsPathItem):
    """连接线"""

    def __init__(self, source_port: Port, target_port: Port, parent=None):
        super().__init__(parent)

        self.source_port = source_port
        self.target_port = target_port

        # 设置外观
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setZValue(-1)  # 在节点下方

        # 添加到端口
        source_port.add_connection(self)
        target_port.add_connection(self)

        # 更新路径
        self.update_path()

    def update_path(self):
        """更新连接路径"""
        path = self.calculate_path()
        self.setPath(path)

        # 设置画笔
        color = self.source_port.brush().color()
        pen = QPen(color, 3 if self.isSelected() else 2)
        pen.setCapStyle(Qt.RoundCap)
        self.setPen(pen)

    def calculate_path(self) -> QPainterPath:
        """计算贝塞尔曲线路径"""
        start = self.source_port.get_scene_pos()
        end = self.target_port.get_scene_pos()

        path = QPainterPath()
        path.moveTo(start)

        # 计算控制点
        ctrl_distance = abs(end.x() - start.x()) * 0.5
        ctrl_distance = max(ctrl_distance, 50)

        # 根据端口位置确定控制点
        if self.source_port.config.position == 'right':
            ctrl1 = QPointF(start.x() + ctrl_distance, start.y())
        elif self.source_port.config.position == 'left':
            ctrl1 = QPointF(start.x() - ctrl_distance, start.y())
        elif self.source_port.config.position == 'bottom':
            ctrl1 = QPointF(start.x(), start.y() + ctrl_distance)
        else:  # top
            ctrl1 = QPointF(start.x(), start.y() - ctrl_distance)

        if self.target_port.config.position == 'left':
            ctrl2 = QPointF(end.x() - ctrl_distance, end.y())
        elif self.target_port.config.position == 'right':
            ctrl2 = QPointF(end.x() + ctrl_distance, end.y())
        elif self.target_port.config.position == 'top':
            ctrl2 = QPointF(end.x(), end.y() - ctrl_distance)
        else:  # bottom
            ctrl2 = QPointF(end.x(), end.y() + ctrl_distance)

        # 绘制贝塞尔曲线
        path.cubicTo(ctrl1, ctrl2, end)

        return path

    def disconnect(self):
        """断开连接"""
        self.source_port.remove_connection(self)
        self.target_port.remove_connection(self)

        if self.scene():
            self.scene().removeItem(self)


# ============ 元类解决方案 ============
class NodeMeta(type(QGraphicsItem), ABCMeta):
    """合并Qt和ABC的元类"""
    pass


# ============ 基础节点类 ============
class BaseNode(QGraphicsItem, metaclass=NodeMeta):
    """所有节点的抽象基类"""

    class Signals(QObject):
        property_changed = Signal(str, object)
        position_changed = Signal(QPointF)
        selected_changed = Signal(bool)

    def __init__(self, node_id: str, metadata: NodeMetadata, parent=None):
        super().__init__(parent)
        self.node_id = node_id
        self.metadata = metadata
        self.signals = self.Signals()
        self.canvas = None  # 将被画布设置

        # 节点状态
        self._properties: Dict[str, Any] = metadata.properties.copy()
        self._bounds = QRectF(0, 0, *metadata.default_size)
        self._selected = False

        # 端口
        self.input_ports: Dict[str, InputPort] = {}
        self.output_ports: Dict[str, OutputPort] = {}

        # 设置标志
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

        # 初始化
        self._create_ports()
        self.initialize()

    def _create_ports(self):
        """创建端口"""
        for port_config in self.metadata.ports:
            if port_config.port_type == 'input':
                port = InputPort(self, port_config, self)
                self.input_ports[port_config.name] = port
            else:
                port = OutputPort(self, port_config, self)
                self.output_ports[port_config.name] = port

            # 设置端口位置
            self._position_port(port, port_config.position)

    def _position_port(self, port: Port, position: str):
        """设置端口位置"""
        if position == 'top':
            port.setPos(self._bounds.width() / 2, 0)
        elif position == 'bottom':
            port.setPos(self._bounds.width() / 2, self._bounds.height())
        elif position == 'left':
            port.setPos(0, self._bounds.height() / 2)
        elif position == 'right':
            port.setPos(self._bounds.width(), self._bounds.height() / 2)
        else:  # auto
            if isinstance(port, InputPort):
                port.setPos(self._bounds.width() / 2, 0)
            else:
                port.setPos(self._bounds.width() / 2, self._bounds.height())

    @abstractmethod
    def initialize(self):
        """初始化节点（子类实现）"""
        pass

    def boundingRect(self) -> QRectF:
        """获取边界矩形"""
        return self._bounds

    def paint(self, painter: QPainter, option, widget):
        """绘制节点"""
        painter.setRenderHint(QPainter.Antialiasing)

        colors = self._get_color_scheme()

        # 绘制阴影
        shadow_rect = self._bounds.adjusted(2, 2, 2, 2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 30)))
        painter.drawRoundedRect(shadow_rect, 5, 5)

        # 绘制主体
        painter.setPen(QPen(colors['border'], 2 if self.isSelected() else 1))
        painter.setBrush(QBrush(colors['background']))
        painter.drawRoundedRect(self._bounds, 5, 5)

        # 绘制标题栏
        self._paint_header(painter, colors)

        # 绘制内容
        self._paint_content(painter, colors)

    def _get_color_scheme(self) -> Dict[str, QColor]:
        """获取颜色方案"""
        default_colors = {
            'background': QColor(240, 240, 240),
            'border': QColor(100, 100, 100),
            'header': QColor(60, 120, 180),
            'header_text': QColor(255, 255, 255),
            'content_text': QColor(50, 50, 50)
        }

        # 应用自定义颜色
        for key, value in self.metadata.color_scheme.items():
            if isinstance(value, str):
                default_colors[key] = QColor(value)

        # 选中状态
        if self.isSelected():
            default_colors['border'] = QColor(255, 165, 0)

        return default_colors

    @abstractmethod
    def _paint_header(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制标题栏（子类实现）"""
        pass

    @abstractmethod
    def _paint_content(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制内容区域（子类实现）"""
        pass

    def itemChange(self, change, value):
        """处理项目变化"""
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.signals.position_changed.emit(value)
            # 更新连接
            self._update_connections()
        elif change == QGraphicsItem.ItemSelectedHasChanged:
            self._selected = value
            self.signals.selected_changed.emit(value)

        return super().itemChange(change, value)

    def _update_connections(self):
        """更新所有连接的路径"""
        for port in list(self.input_ports.values()) + list(self.output_ports.values()):
            for connection in port.connections:
                connection.update_path()

    def get_property(self, name: str) -> Any:
        """获取属性值"""
        return self._properties.get(name)

    def set_property(self, name: str, value: Any):
        """设置属性值"""
        old_value = self._properties.get(name)
        self._properties[name] = value
        self.signals.property_changed.emit(name, value)
        self.update()


# ============ 具体节点实现 ============
class DataNode(BaseNode):
    """数据节点"""

    def initialize(self):
        self.header_height = 30

    def _paint_header(self, painter: QPainter, colors: Dict[str, QColor]):
        header_rect = QRectF(0, 0, self._bounds.width(), self.header_height)

        painter.setPen(Qt.NoPen)
        painter.setBrush(colors['header'])
        painter.drawRoundedRect(header_rect, 5, 5)

        painter.setPen(colors['header_text'])
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(
            header_rect,
            Qt.AlignCenter,
            self.metadata.display_name
        )

    def _paint_content(self, painter: QPainter, colors: Dict[str, QColor]):
        content_rect = QRectF(
            10,
            self.header_height + 10,
            self._bounds.width() - 20,
            self._bounds.height() - self.header_height - 20
        )

        painter.setPen(colors['content_text'])
        painter.setFont(QFont("Arial", 9))

        y_offset = 0
        for key, value in self._properties.items():
            if y_offset + 20 > content_rect.height():
                break

            text = f"{key}: {value}"
            painter.drawText(
                QRectF(content_rect.x(), content_rect.y() + y_offset,
                       content_rect.width(), 20),
                Qt.AlignLeft | Qt.AlignVCenter,
                text
            )
            y_offset += 20


class ProcessNode(BaseNode):
    """处理节点"""

    def initialize(self):
        self.header_height = 35

    def _paint_header(self, painter: QPainter, colors: Dict[str, QColor]):
        header_rect = QRectF(0, 0, self._bounds.width(), self.header_height)

        painter.setPen(Qt.NoPen)
        painter.setBrush(colors['header'])
        painter.drawRoundedRect(header_rect, 5, 5)

        # 图标
        painter.setPen(colors['header_text'])
        painter.setFont(QFont("Arial", 12))
        painter.drawText(
            QRectF(10, 0, 30, self.header_height),
            Qt.AlignCenter,
            "⚙"
        )

        # 标题
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(
            header_rect.adjusted(40, 0, -10, 0),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.metadata.display_name
        )

    def _paint_content(self, painter: QPainter, colors: Dict[str, QColor]):
        content_rect = QRectF(
            10,
            self.header_height + 10,
            self._bounds.width() - 20,
            self._bounds.height() - self.header_height - 20
        )

        painter.setPen(colors['content_text'])
        painter.setFont(QFont("Arial", 9))
        painter.drawText(
            content_rect,
            Qt.AlignCenter,
            f"Multiplier: {self.get_property('multiplier')}"
        )


class IfNode(BaseNode):
    """条件节点"""

    def initialize(self):
        self.header_height = 35

    def _paint_header(self, painter: QPainter, colors: Dict[str, QColor]):
        header_rect = QRectF(0, 0, self._bounds.width(), self.header_height)

        painter.setPen(Qt.NoPen)
        painter.setBrush(colors['header'])
        painter.drawRoundedRect(header_rect, 5, 5)

        painter.setPen(colors['header_text'])
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(
            header_rect,
            Qt.AlignCenter,
            self.metadata.display_name
        )

    def _paint_content(self, painter: QPainter, colors: Dict[str, QColor]):
        content_rect = QRectF(
            10,
            self.header_height + 10,
            self._bounds.width() - 20,
            self._bounds.height() - self.header_height - 20
        )

        painter.setPen(colors['content_text'])
        painter.setFont(QFont("Consolas", 9))

        condition = self.get_property('condition') or ""
        painter.drawText(
            content_rect,
            Qt.AlignTop | Qt.AlignLeft | Qt.TextWordWrap,
            f"if {condition}"
        )


# ============ 画布类 ============
class CanvasWithConnections(QWidget):
    """带连接功能的画布"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # 初始化组件
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-2000, -2000, 4000, 4000)

        self.node_registry = NodeRegistry()

        # 容器
        self.nodes: Dict[str, BaseNode] = {}
        self.connections: List[Connection] = []

        # 连接状态
        self.connecting_port = None
        self.temp_connection = None

        # 初始化UI
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建视图
        self.view = CanvasView(self.scene, self)
        layout.addWidget(self.view)

        # 信息栏
        self.info_label = QLabel("就绪")
        self.info_label.setStyleSheet("background-color: #f0f0f0; padding: 5px;")
        layout.addWidget(self.info_label)

    def add_node(self, node_type: str, position: QPointF = None) -> Optional[BaseNode]:
        """添加节点"""
        try:
            # 生成唯一ID
            node_id = f"node_{len(self.nodes)}_{int(time.time() * 1000)}"

            # 创建节点
            node = self.node_registry.create_node(node_type, node_id)
            node.canvas = self  # 设置画布引用

            # 设置位置
            if position:
                node.setPos(position)
            else:
                center = self.view.mapToScene(self.view.viewport().rect().center())
                node.setPos(center)

            # 添加到场景
            self.scene.addItem(node)

            # 添加到容器
            self.nodes[node_id] = node

            self.info_label.setText(f"添加节点: {node.metadata.display_name}")

            return node

        except Exception as e:
            print(f"Failed to add node: {e}")
            return None

    def start_connection(self, port: OutputPort):
        """开始创建连接"""
        self.connecting_port = port

        # 创建临时连接线
        self.temp_connection = QGraphicsPathItem()
        self.temp_connection.setPen(QPen(port.brush().color(), 2, Qt.DashLine))
        self.scene.addItem(self.temp_connection)

        self.info_label.setText("正在连接...")

    def update_temp_connection(self, scene_pos: QPointF):
        """更新临时连接线"""
        if not self.temp_connection or not self.connecting_port:
            return

        start = self.connecting_port.get_scene_pos()

        path = QPainterPath()
        path.moveTo(start)

        # 简单的曲线
        ctrl_distance = abs(scene_pos.x() - start.x()) * 0.5
        ctrl1 = QPointF(start.x() + ctrl_distance, start.y())
        ctrl2 = QPointF(scene_pos.x() - ctrl_distance, scene_pos.y())

        path.cubicTo(ctrl1, ctrl2, scene_pos)

        self.temp_connection.setPath(path)

    def complete_connection(self, target_port: InputPort):
        """完成连接"""
        if not self.connecting_port:
            return

        # 检查是否可以连接
        if self.connecting_port.parent_node == target_port.parent_node:
            self.cancel_connection()
            self.info_label.setText("不能连接到同一节点")
            return

        # 创建连接
        connection = Connection(self.connecting_port, target_port)
        self.scene.addItem(connection)
        self.connections.append(connection)

        # 清理
        self.cancel_connection()

        self.info_label.setText("连接已创建")

    def cancel_connection(self):
        """取消连接"""
        if self.temp_connection:
            self.scene.removeItem(self.temp_connection)
            self.temp_connection = None

        self.connecting_port = None

    def create_connection(self, source_node_id: str, source_port_name: str,
                          target_node_id: str, target_port_name: str) -> Optional[Connection]:
        """创建两个节点之间的连接"""
        source_node = self.nodes.get(source_node_id)
        target_node = self.nodes.get(target_node_id)

        if not source_node or not target_node:
            return None

        source_port = source_node.output_ports.get(source_port_name)
        target_port = target_node.input_ports.get(target_port_name)

        if not source_port or not target_port:
            return None

        # 创建连接
        connection = Connection(source_port, target_port)
        self.scene.addItem(connection)
        self.connections.append(connection)

        return connection


# ============ 视图类 ============
class CanvasView(QGraphicsView):
    """画布视图"""

    def __init__(self, scene: QGraphicsScene, canvas: CanvasWithConnections):
        super().__init__(scene)
        self.canvas = canvas

        # 视图设置
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)

    def mouseMoveEvent(self, event: QMouseEvent):
        """处理鼠标移动"""
        if self.canvas.connecting_port:
            scene_pos = self.mapToScene(event.pos())
            self.canvas.update_temp_connection(scene_pos)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """处理鼠标释放"""
        if self.canvas.connecting_port and event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            item = self.scene().itemAt(scene_pos, self.transform())

            if isinstance(item, InputPort):
                self.canvas.complete_connection(item)
            else:
                self.canvas.cancel_connection()

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """处理键盘事件"""
        if event.key() == Qt.Key_Escape and self.canvas.connecting_port:
            self.canvas.cancel_connection()

        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """处理滚轮缩放"""
        # 缩放因子
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor

        # 设置缩放锚点
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        # 执行缩放
        if event.angleDelta().y() > 0:
            self.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.scale(zoom_out_factor, zoom_out_factor)


# ============ 主窗口 ============
class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("带连接功能的节点画布")
        self.resize(1200, 800)

        # 注册节点类型
        self.register_node_types()

        # 创建画布
        self.canvas = CanvasWithConnections()
        self.setCentralWidget(self.canvas)

        # 创建工具栏
        self.create_toolbar()

        # 状态栏
        self.statusBar().showMessage("就绪")

        # 创建示例
        QTimer.singleShot(100, self.create_example_nodes)

    def register_node_types(self):
        """注册节点类型"""
        registry = NodeRegistry()

        # 数据节点
        registry.register_node_type(
            DataNode,
            NodeMetadata(
                type_id="data_node",
                display_name="数据节点",
                category="基础节点",
                color_scheme={
                    'header': '#3498db',
                    'background': '#ecf0f1'
                },
                ports=[
                    PortConfig("output", "output", "number", "bottom")
                ],
                properties={
                    'value': 42,
                    'type': 'number'
                }
            )
        )

        # 识别节点（作为处理节点的示例）
        registry.register_node_type(
            ProcessNode,
            NodeMetadata(
                type_id="recognition_node",
                display_name="识别节点",
                category="处理节点",
                color_scheme={
                    'header': '#27ae60',
                    'background': '#e8f5e9'
                },
                ports=[
                    PortConfig("input", "input", "any", "top"),
                    PortConfig("result", "output", "any", "bottom"),
                    PortConfig("error", "output", "flow", "right", color="#e74c3c")
                ],
                properties={
                    'threshold': 0.8,
                    'multiplier': 1
                }
            )
        )

        # 条件节点
        registry.register_node_type(
            IfNode,
            NodeMetadata(
                type_id="if_node",
                display_name="条件节点",
                category="控制节点",
                color_scheme={
                    'header': '#e74c3c',
                    'background': '#fadbd8'
                },
                ports=[
                    PortConfig("input", "input", "any", "top"),
                    PortConfig("true", "output", "flow", "left", color="#27ae60"),
                    PortConfig("false", "output", "flow", "right", color="#e74c3c")
                ],
                properties={
                    'condition': 'value > 40'
                }
            )
        )

        # 自定义处理节点
        registry.register_node_type(
            ProcessNode,
            NodeMetadata(
                type_id="custom_process",
                display_name="自定义处理",
                category="自定义节点",
                color_scheme={
                    'header': '#e67e22',
                    'background': '#fef5e7'
                },
                ports=[
                    PortConfig("input", "input", "number", "top"),
                    PortConfig("output", "output", "number", "bottom")
                ],
                properties={
                    'multiplier': 2
                }
            )
        )

    def create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar("主工具栏")
        self.addToolBar(toolbar)

        # 清空画布
        clear_action = QAction("清空", self)
        clear_action.triggered.connect(self.clear_canvas)
        toolbar.addAction(clear_action)

        # 适应视图
        fit_action = QAction("适应视图", self)
        fit_action.triggered.connect(self.fit_view)
        toolbar.addAction(fit_action)

    def create_example_nodes(self):
        """创建示例节点和连接"""
        # 创建节点
        node1 = self.canvas.add_node("data_node", QPointF(100, 100))
        if node1:
            node1.set_property('value', 42)

        node2 = self.canvas.add_node("recognition_node", QPointF(400, 100))

        node3 = self.canvas.add_node("if_node", QPointF(250, 300))
        if node3:
            node3.set_property('condition', 'value > 40')

        node4 = self.canvas.add_node("custom_process", QPointF(550, 300))

        # 创建连接
        if node1 and node2 and node3 and node4:
            # 数据节点 -> 识别节点
            self.canvas.create_connection(node1.node_id, "output",
                                          node2.node_id, "input")

            # 识别节点 -> 条件节点
            self.canvas.create_connection(node2.node_id, "result",
                                          node3.node_id, "input")

            # 条件节点 -> 自定义处理节点
            self.canvas.create_connection(node3.node_id, "true",
                                          node4.node_id, "input")

            self.statusBar().showMessage("已创建示例节点和连接", 2000)

    def clear_canvas(self):
        """清空画布"""
        # 清除连接
        for conn in self.canvas.connections[:]:
            conn.disconnect()
        self.canvas.connections.clear()

        # 清除节点
        for node in list(self.canvas.nodes.values()):
            self.canvas.scene.removeItem(node)
        self.canvas.nodes.clear()

        self.statusBar().showMessage("画布已清空", 2000)

    def fit_view(self):
        """适应视图"""
        if self.canvas.nodes:
            # 计算所有节点的边界
            bounds = QRectF()
            for node in self.canvas.nodes.values():
                node_rect = node.mapRectToScene(node.boundingRect())
                bounds = bounds.united(node_rect)

            # 添加边距
            bounds.adjust(-50, -50, 50, 50)

            # 适应视图
            self.canvas.view.fitInView(bounds, Qt.KeepAspectRatio)


# ============ 主函数 ============
def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()