# node_registry_fixed.py
"""
修复了元类冲突和导入问题的节点注册系统
"""
from typing import Dict, Type, Any, Callable, Optional, List
from dataclasses import dataclass, field
from abc import ABCMeta, abstractmethod
import json

from src.views.node_system.port_system import InputPort, OutputPort


@dataclass
class PortConfig:
    """端口配置"""
    name: str
    port_type: str  # 'input' or 'output'
    data_type: str = 'any'  # 数据类型
    position: str = 'auto'  # 'top', 'bottom', 'left', 'right', 'auto'
    max_connections: int = -1  # -1表示无限制
    color: Optional[str] = None


@dataclass
class NodeMetadata:
    """节点元数据"""
    type_id: str
    display_name: str
    category: str
    description: str = ""
    icon: Optional[str] = None
    color_scheme: Dict[str, str] = field(default_factory=dict)
    default_size: tuple = (240, 200)
    resizable: bool = True
    ports: List[PortConfig] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)


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

    def register_node_type(
            self,
            node_class: Type['BaseNode'],
            metadata: NodeMetadata
    ) -> None:
        """注册新的节点类型"""
        type_id = metadata.type_id

        # 验证
        if type_id in self._node_types:
            raise ValueError(f"Node type '{type_id}' already registered")

        # 注册
        self._node_types[type_id] = node_class
        self._node_metadata[type_id] = metadata

        # 更新分类
        category = metadata.category
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(type_id)

    def unregister_node_type(self, type_id: str) -> None:
        """注销节点类型"""
        if type_id not in self._node_types:
            return

        # 从分类中移除
        metadata = self._node_metadata[type_id]
        category = metadata.category
        if category in self._categories:
            self._categories[category].remove(type_id)
            if not self._categories[category]:
                del self._categories[category]

        # 移除注册
        del self._node_types[type_id]
        del self._node_metadata[type_id]

    def create_node(self, type_id: str, node_id: str, **kwargs) -> 'BaseNode':
        """创建节点实例"""
        if type_id not in self._node_types:
            raise ValueError(f"Unknown node type: {type_id}")

        node_class = self._node_types[type_id]
        metadata = self._node_metadata[type_id]

        return node_class(node_id=node_id, metadata=metadata, **kwargs)

    def get_metadata(self, type_id: str) -> Optional[NodeMetadata]:
        """获取节点元数据"""
        return self._node_metadata.get(type_id)

    def get_categories(self) -> Dict[str, List[str]]:
        """获取所有分类"""
        return self._categories.copy()

    def get_nodes_by_category(self, category: str) -> List[str]:
        """获取分类下的所有节点类型"""
        return self._categories.get(category, []).copy()


# base_node_fixed.py
from PySide6.QtCore import QObject, Signal, QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtWidgets import QGraphicsItem
from typing import Dict, Any, List, Optional
from abc import ABCMeta, abstractmethod


# 解决元类冲突
class NodeMeta(type(QGraphicsItem), ABCMeta):
    """合并Qt和ABC的元类"""
    pass


class BaseNode(QGraphicsItem, metaclass=NodeMeta):
    """所有节点的抽象基类"""

    # 信号定义
    class Signals(QObject):
        property_changed = Signal(str, object)  # 属性名, 新值
        port_connected = Signal(str, object)  # 端口名, 连接
        port_disconnected = Signal(str, object)  # 端口名, 连接
        position_changed = Signal(QPointF)
        selected_changed = Signal(bool)

    def __init__(self, node_id: str, metadata: NodeMetadata, parent=None):
        super().__init__(parent)
        self.node_id = node_id
        self.metadata = metadata
        self.signals = self.Signals()

        # 节点状态
        self._properties: Dict[str, Any] = metadata.properties.copy()
        self._position = QPointF(0, 0)
        self._size = QPointF(*metadata.default_size)
        self._selected = False

        # 端口管理
        self._input_ports: Dict[str, 'BasePort'] = {}
        self._output_ports: Dict[str, 'BasePort'] = {}

        # 视觉状态
        self._bounds = QRectF(0, 0, self._size.x(), self._size.y())
        self._collapsed = False

        # 设置标志
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

        # 初始化
        self._initialize_ports()
        self.initialize()

    def _initialize_ports(self):
        """根据元数据初始化端口"""

        for port_config in self.metadata.ports:
            if port_config.port_type == 'input':
                port = InputPort(self, port_config, self)
                self._input_ports[port_config.name] = port

                # 设置端口位置
                if port_config.position == 'top' or port_config.position == 'auto':
                    port.setPos(self._bounds.width() / 2, 0)
                elif port_config.position == 'bottom':
                    port.setPos(self._bounds.width() / 2, self._bounds.height())
                elif port_config.position == 'left':
                    port.setPos(0, self._bounds.height() / 2)
                elif port_config.position == 'right':
                    port.setPos(self._bounds.width(), self._bounds.height() / 2)

            else:  # output
                port = OutputPort(self, port_config, self)
                self._output_ports[port_config.name] = port

                # 设置端口位置
                if port_config.position == 'bottom' or port_config.position == 'auto':
                    port.setPos(self._bounds.width() / 2, self._bounds.height())
                elif port_config.position == 'top':
                    port.setPos(self._bounds.width() / 2, 0)
                elif port_config.position == 'left':
                    port.setPos(0, self._bounds.height() / 2)
                elif port_config.position == 'right':
                    port.setPos(self._bounds.width(), self._bounds.height() / 2)

    @abstractmethod
    def initialize(self):
        """初始化节点（子类实现）"""
        pass

    @abstractmethod
    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """处理节点逻辑（子类实现）"""
        pass

    # 属性管理
    def get_property(self, name: str) -> Any:
        """获取属性值"""
        return self._properties.get(name)

    def set_property(self, name: str, value: Any):
        """设置属性值"""
        old_value = self._properties.get(name)
        self._properties[name] = value
        self.signals.property_changed.emit(name, value)
        self.on_property_changed(name, old_value, value)
        self.update()

    def get_properties(self) -> Dict[str, Any]:
        """获取所有属性"""
        return self._properties.copy()

    def set_properties(self, properties: Dict[str, Any]):
        """批量设置属性"""
        for name, value in properties.items():
            self.set_property(name, value)

    @abstractmethod
    def on_property_changed(self, name: str, old_value: Any, new_value: Any):
        """属性变化回调（子类可重写）"""
        pass

    # 端口管理
    def get_input_port(self, name: str) -> Optional['BasePort']:
        """获取输入端口"""
        return self._input_ports.get(name)

    def get_output_port(self, name: str) -> Optional['BasePort']:
        """获取输出端口"""
        return self._output_ports.get(name)

    def get_all_input_ports(self) -> Dict[str, 'BasePort']:
        """获取所有输入端口"""
        return self._input_ports.copy()

    def get_all_output_ports(self) -> Dict[str, 'BasePort']:
        """获取所有输出端口"""
        return self._output_ports.copy()

    # 绘制相关
    def boundingRect(self) -> QRectF:
        """获取边界矩形"""
        return self._bounds

    def paint(self, painter: QPainter, option, widget):
        """绘制节点"""
        painter.setRenderHint(QPainter.Antialiasing)

        # 获取颜色方案
        colors = self._get_color_scheme()

        # 绘制阴影
        shadow_rect = self._bounds.adjusted(2, 2, 2, 2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 30)))
        painter.drawRoundedRect(shadow_rect, 5, 5)

        # 绘制主体
        painter.setPen(QPen(colors['border'], 2 if self._selected else 1))
        painter.setBrush(QBrush(colors['background']))
        painter.drawRoundedRect(self._bounds, 5, 5)

        # 绘制标题栏
        self._paint_header(painter, colors)

        # 绘制内容
        if not self._collapsed:
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
        if self._selected:
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

    # 交互处理
    def itemChange(self, change, value):
        """处理项目变化"""
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.signals.position_changed.emit(value)
        elif change == QGraphicsItem.ItemSelectedHasChanged:
            self._selected = value
            self.signals.selected_changed.emit(value)

        return super().itemChange(change, value)

    # 序列化
    def serialize(self) -> Dict[str, Any]:
        """序列化节点数据"""
        return {
            'node_id': self.node_id,
            'type_id': self.metadata.type_id,
            'position': {'x': self.x(), 'y': self.y()},
            'properties': self._properties.copy(),
            'size': {'width': self._size.x(), 'height': self._size.y()},
            'collapsed': self._collapsed
        }

    def deserialize(self, data: Dict[str, Any]):
        """反序列化节点数据"""
        if 'position' in data:
            pos = data['position']
            self.setPos(pos['x'], pos['y'])

        if 'properties' in data:
            self.set_properties(data['properties'])

        if 'size' in data:
            size = data['size']
            self.resize(size['width'], size['height'])

        if 'collapsed' in data:
            self._collapsed = data['collapsed']

        self.update()

    def resize(self, width: float, height: float):
        """调整节点大小"""
        if not self.metadata.resizable:
            return

        self._size = QPointF(max(100, width), max(50, height))
        self._bounds = QRectF(0, 0, self._size.x(), self._size.y())
        self._update_port_positions()
        self.update()

    def _update_port_positions(self):
        """更新端口位置"""
        # 更新输入端口
        for name, port in self._input_ports.items():
            config = port.config
            if config.position == 'top' or config.position == 'auto':
                port.setPos(self._bounds.width() / 2, 0)
            elif config.position == 'bottom':
                port.setPos(self._bounds.width() / 2, self._bounds.height())
            elif config.position == 'left':
                port.setPos(0, self._bounds.height() / 2)
            elif config.position == 'right':
                port.setPos(self._bounds.width(), self._bounds.height() / 2)

        # 更新输出端口
        for name, port in self._output_ports.items():
            config = port.config
            if config.position == 'bottom' or config.position == 'auto':
                port.setPos(self._bounds.width() / 2, self._bounds.height())
            elif config.position == 'top':
                port.setPos(self._bounds.width() / 2, 0)
            elif config.position == 'left':
                port.setPos(0, self._bounds.height() / 2)
            elif config.position == 'right':
                port.setPos(self._bounds.width(), self._bounds.height() / 2)