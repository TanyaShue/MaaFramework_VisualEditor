#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单的测试脚本，验证重构后的画布系统
将所有必要的类放在一个文件中，避免导入问题
"""

import sys
from typing import Dict, Any, List, Optional, Type
from dataclasses import dataclass, field
from abc import ABCMeta, abstractmethod

from PySide6.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QVBoxLayout, QWidget, \
    QGraphicsItem
from PySide6.QtCore import Qt, QPointF, QRectF, QObject, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath


# ============ 数据结构 ============
@dataclass
class PortConfig:
    """端口配置"""
    name: str
    port_type: str  # 'input' or 'output'
    data_type: str = 'any'
    position: str = 'auto'
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


# ============ 节点注册器 ============
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
        self._node_types: Dict[str, Type['SimpleNode']] = {}
        self._node_metadata: Dict[str, NodeMetadata] = {}

    def register_node_type(self, node_class: Type['SimpleNode'], metadata: NodeMetadata):
        """注册节点类型"""
        self._node_types[metadata.type_id] = node_class
        self._node_metadata[metadata.type_id] = metadata

    def create_node(self, type_id: str, node_id: str) -> 'SimpleNode':
        """创建节点实例"""
        if type_id not in self._node_types:
            raise ValueError(f"Unknown node type: {type_id}")

        node_class = self._node_types[type_id]
        metadata = self._node_metadata[type_id]
        return node_class(node_id=node_id, metadata=metadata)


# ============ 元类解决方案 ============
class NodeMeta(type(QGraphicsItem), ABCMeta):
    """合并Qt和ABC的元类"""
    pass


# ============ 简化的节点基类 ============
class SimpleNode(QGraphicsItem, metaclass=NodeMeta):
    """简化的节点基类"""

    def __init__(self, node_id: str, metadata: NodeMetadata, parent=None):
        super().__init__(parent)
        self.node_id = node_id
        self.metadata = metadata

        # 基本属性
        self._bounds = QRectF(0, 0, *metadata.default_size)
        self._selected = False
        self._properties = metadata.properties.copy()

        # 设置标志
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

        # 初始化
        self.initialize()

    @abstractmethod
    def initialize(self):
        """初始化节点"""
        pass

    def boundingRect(self) -> QRectF:
        """获取边界矩形"""
        return self._bounds

    def paint(self, painter: QPainter, option, widget):
        """绘制节点"""
        painter.setRenderHint(QPainter.Antialiasing)

        # 颜色
        colors = self._get_colors()

        # 绘制阴影
        shadow_rect = self._bounds.adjusted(2, 2, 2, 2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 30)))
        painter.drawRoundedRect(shadow_rect, 5, 5)

        # 绘制主体
        painter.setPen(QPen(colors['border'], 2 if self.isSelected() else 1))
        painter.setBrush(QBrush(colors['background']))
        painter.drawRoundedRect(self._bounds, 5, 5)

        # 绘制标题
        self._paint_header(painter, colors)

    def _get_colors(self) -> Dict[str, QColor]:
        """获取颜色方案"""
        default_colors = {
            'background': QColor(240, 240, 240),
            'border': QColor(100, 100, 100),
            'header': QColor(60, 120, 180),
            'header_text': QColor(255, 255, 255)
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
        """绘制标题栏"""
        pass


# ============ 具体节点实现 ============
class DataNode(SimpleNode):
    """数据节点"""

    def initialize(self):
        """初始化"""
        self.header_height = 30

    def _paint_header(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制标题栏"""
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


class ProcessNode(SimpleNode):
    """处理节点"""

    def initialize(self):
        """初始化"""
        self.header_height = 35

    def _paint_header(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制标题栏"""
        header_rect = QRectF(0, 0, self._bounds.width(), self.header_height)

        # 渐变效果
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


# ============ 简单的画布 ============
class SimpleCanvas(QGraphicsView):
    """简化的画布"""

    def __init__(self):
        super().__init__()

        # 创建场景
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-1000, -1000, 2000, 2000)
        self.setScene(self.scene)

        # 设置视图属性
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)

        # 节点容器
        self.nodes = []

        # 注册器
        self.registry = NodeRegistry()

    def add_node(self, type_id: str, position: QPointF) -> Optional[SimpleNode]:
        """添加节点"""
        try:
            node_id = f"node_{len(self.nodes)}"
            node = self.registry.create_node(type_id, node_id)
            node.setPos(position)

            self.scene.addItem(node)
            self.nodes.append(node)

            return node
        except Exception as e:
            print(f"Failed to add node: {e}")
            return None

    def wheelEvent(self, event):
        """滚轮缩放"""
        # 缩放因子
        scale_factor = 1.15

        # 设置缩放中心
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        # 缩放
        if event.angleDelta().y() > 0:
            self.scale(scale_factor, scale_factor)
        else:
            self.scale(1 / scale_factor, 1 / scale_factor)


# ============ 主窗口 ============
class TestMainWindow(QMainWindow):
    """测试主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("画布系统测试")
        self.resize(800, 600)

        # 注册节点类型
        self.register_node_types()

        # 创建画布
        self.canvas = SimpleCanvas()
        self.setCentralWidget(self.canvas)

        # 创建测试节点
        self.create_test_nodes()

    def register_node_types(self):
        """注册节点类型"""
        registry = NodeRegistry()

        # 注册数据节点
        registry.register_node_type(
            DataNode,
            NodeMetadata(
                type_id="data_node",
                display_name="数据节点",
                category="数据处理",
                color_scheme={
                    'header': '#3498db',
                    'background': '#ecf0f1'
                }
            )
        )

        # 注册处理节点
        registry.register_node_type(
            ProcessNode,
            NodeMetadata(
                type_id="process_node",
                display_name="处理节点",
                category="数据处理",
                color_scheme={
                    'header': '#e74c3c',
                    'background': '#fadbd8'
                }
            )
        )

    def create_test_nodes(self):
        """创建 100 个测试节点"""
        cols = 10  # 每行 10 个节点
        spacing_x = 150
        spacing_y = 100

        for i in range(100):
            row = i // cols
            col = i % cols
            x = 100 + col * spacing_x
            y = 100 + row * spacing_y

            # 偶数为 data_node，奇数为 process_node
            node_type = "data_node" if i % 2 == 0 else "process_node"
            self.canvas.add_node(node_type, QPointF(x, y))

        print(f"Created {len(self.canvas.nodes)} test nodes")


# ============ 主函数 ============
def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = TestMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()