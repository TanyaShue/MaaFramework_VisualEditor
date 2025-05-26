# node_types.py
from typing import Dict, Any, Optional, List
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QFont, QColor, QPen, QPixmap
from src.views.node_system.node_registry import BaseNode, NodeMetadata, PortConfig, NodeRegistry


class DataNode(BaseNode):
    """数据处理节点基类"""

    def initialize(self):
        """初始化数据节点"""
        self.header_height = 30
        self.content_margin = 10

    def _paint_header(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制标题栏"""
        header_rect = QRectF(0, 0, self._bounds.width(), self.header_height)

        # 绘制背景
        painter.setPen(Qt.NoPen)
        painter.setBrush(colors['header'])
        painter.drawRoundedRect(header_rect, 5, 5)

        # 绘制标题
        painter.setPen(colors['header_text'])
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(
            header_rect.adjusted(10, 0, -10, 0),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.metadata.display_name
        )

    def _paint_content(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制内容区域"""
        content_rect = QRectF(
            self.content_margin,
            self.header_height + self.content_margin,
            self._bounds.width() - 2 * self.content_margin,
            self._bounds.height() - self.header_height - 2 * self.content_margin
        )

        # 绘制属性
        painter.setPen(colors['content_text'])
        painter.setFont(QFont("Arial", 9))

        y_offset = 0
        for key, value in self._properties.items():
            if y_offset + 20 > content_rect.height():
                break

            text = f"{key}: {value}"
            text_rect = QRectF(
                content_rect.x(),
                content_rect.y() + y_offset,
                content_rect.width(),
                20
            )
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, text)
            y_offset += 20

    def on_property_changed(self, name: str, old_value: Any, new_value: Any):
        """属性变化时的处理"""
        # 可以在这里添加验证逻辑
        pass


class RecognitionNode(DataNode):
    """图像识别节点"""

    def __init__(self, node_id: str, metadata: NodeMetadata, **kwargs):
        super().__init__(node_id, metadata, **kwargs)
        self._images: List[QPixmap] = []
        self._current_image_index = 0

    def initialize(self):
        """初始化识别节点"""
        super().initialize()
        self._load_template_images()

    def _load_template_images(self):
        """加载模板图像"""
        template_paths = self.get_property('templates') or []
        if isinstance(template_paths, str):
            template_paths = [template_paths]

        self._images = []
        for path in template_paths:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self._images.append(pixmap)

    def _paint_content(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制内容 - 显示图像"""
        if not self._images:
            super()._paint_content(painter, colors)
            return

        # 计算图像显示区域
        content_rect = QRectF(
            self.content_margin,
            self.header_height + self.content_margin,
            self._bounds.width() - 2 * self.content_margin,
            self._bounds.height() - self.header_height - 2 * self.content_margin
        )

        # 显示当前图像
        if 0 <= self._current_image_index < len(self._images):
            image = self._images[self._current_image_index]

            # 保持宽高比缩放图像
            scaled_pixmap = image.scaled(
                content_rect.size().toSize(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            # 居中绘制
            x = content_rect.x() + (content_rect.width() - scaled_pixmap.width()) / 2
            y = content_rect.y() + (content_rect.height() - scaled_pixmap.height()) / 2

            painter.drawPixmap(x, y, scaled_pixmap)

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """处理识别逻辑"""
        # 这里实现具体的识别逻辑
        return {
            'detected': False,
            'confidence': 0.0
        }


class ControlNode(BaseNode):
    """流程控制节点基类"""

    def initialize(self):
        """初始化控制节点"""
        self.header_height = 35
        self._condition = self.get_property('condition') or ""

    def _paint_header(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制标题栏 - 使用不同的样式"""
        header_rect = QRectF(0, 0, self._bounds.width(), self.header_height)

        # 使用渐变或特殊样式
        painter.setPen(Qt.NoPen)
        painter.setBrush(colors.get('control_header', colors['header']))
        painter.drawRoundedRect(header_rect, 5, 5)

        # 绘制图标和标题
        painter.setPen(colors['header_text'])
        painter.setFont(QFont("Arial", 10, QFont.Bold))

        # 添加控制节点特殊标记
        painter.drawText(
            QRectF(10, 0, 30, self.header_height),
            Qt.AlignCenter,
            "▶"
        )

        painter.drawText(
            header_rect.adjusted(40, 0, -10, 0),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.metadata.display_name
        )

    def _paint_content(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制内容 - 显示条件"""
        content_rect = QRectF(
            10,
            self.header_height + 10,
            self._bounds.width() - 20,
            self._bounds.height() - self.header_height - 20
        )

        painter.setPen(colors['content_text'])
        painter.setFont(QFont("Consolas", 9))

        # 显示条件表达式
        if self._condition:
            painter.drawText(
                content_rect,
                Qt.AlignTop | Qt.AlignLeft | Qt.TextWordWrap,
                f"if {self._condition}"
            )

    def on_property_changed(self, name: str, old_value: Any, new_value: Any):
        """属性变化处理"""
        if name == 'condition':
            self._condition = new_value

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """处理控制逻辑"""
        # 评估条件
        result = self._evaluate_condition(inputs)
        return {
            'result': result,
            'next': 'true' if result else 'false'
        }

    def _evaluate_condition(self, context: Dict[str, Any]) -> bool:
        """评估条件表达式"""
        if not self._condition:
            return True

        try:
            # 简单的表达式评估（实际应该使用更安全的方法）
            return eval(self._condition, {"__builtins__": {}}, context)
        except:
            return False


class CompositeNode(BaseNode):
    """组合节点 - 可以包含子节点"""

    def __init__(self, node_id: str, metadata: NodeMetadata, **kwargs):
        super().__init__(node_id, metadata, **kwargs)
        self._child_nodes: List[BaseNode] = []
        self._internal_connections: List[Any] = []

    def initialize(self):
        """初始化组合节点"""
        self.header_height = 40
        self._expanded = False

    def add_child_node(self, node: BaseNode):
        """添加子节点"""
        if node not in self._child_nodes:
            self._child_nodes.append(node)
            node.setParentItem(self)

    def remove_child_node(self, node: BaseNode):
        """移除子节点"""
        if node in self._child_nodes:
            self._child_nodes.remove(node)
            node.setParentItem(None)

    def _paint_header(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制标题栏 - 带展开/折叠按钮"""
        header_rect = QRectF(0, 0, self._bounds.width(), self.header_height)

        # 背景
        painter.setPen(Qt.NoPen)
        painter.setBrush(colors.get('composite_header', QColor(80, 80, 120)))
        painter.drawRoundedRect(header_rect, 5, 5)

        # 展开/折叠按钮
        button_rect = QRectF(10, 10, 20, 20)
        painter.setPen(QPen(colors['header_text'], 2))
        painter.drawRect(button_rect)

        # 绘制加号或减号
        painter.drawLine(15, 20, 25, 20)  # 横线
        if not self._expanded:
            painter.drawLine(20, 15, 20, 25)  # 竖线

        # 标题
        painter.setPen(colors['header_text'])
        painter.setFont(QFont("Arial", 11, QFont.Bold))
        painter.drawText(
            header_rect.adjusted(40, 0, -10, 0),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.metadata.display_name
        )

    def _paint_content(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制内容"""
        if not self._expanded:
            # 折叠状态显示概要信息
            content_rect = QRectF(
                10,
                self.header_height + 5,
                self._bounds.width() - 20,
                30
            )

            painter.setPen(colors['content_text'])
            painter.setFont(QFont("Arial", 9))
            painter.drawText(
                content_rect,
                Qt.AlignCenter,
                f"Contains {len(self._child_nodes)} nodes"
            )
        else:
            # 展开状态显示内部结构
            # 子节点会自动绘制
            pass

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """处理组合节点逻辑"""
        # 按拓扑顺序执行子节点
        results = {}
        for child in self._child_nodes:
            child_result = child.process(inputs)
            results[child.node_id] = child_result

        return results

    def on_property_changed(self, name: str, old_value: Any, new_value: Any):
        """处理属性变化"""
        pass


# 注册节点类型的辅助函数
def register_default_node_types():
    """注册默认节点类型"""
    registry = NodeRegistry()

    # 注册数据节点
    registry.register_node_type(
        DataNode,
        NodeMetadata(
            type_id="data_node",
            display_name="Data Node",
            category="Data Processing",
            description="Basic data processing node",
            color_scheme={
                'header': '#3498db',
                'background': '#ecf0f1'
            },
            ports=[
                PortConfig("input", "input", "any"),
                PortConfig("output", "output", "any")
            ],
            properties={
                'value': None,
                'data_type': 'string'
            }
        )
    )

    # 注册识别节点
    registry.register_node_type(
        RecognitionNode,
        NodeMetadata(
            type_id="recognition_node",
            display_name="Recognition Node",
            category="Computer Vision",
            description="Image recognition node",
            color_scheme={
                'header': '#27ae60',
                'background': '#e8f5e9'
            },
            ports=[
                PortConfig("image", "input", "image"),
                PortConfig("result", "output", "detection"),
                PortConfig("next", "output", "flow"),
                PortConfig("on_error", "output", "flow")
            ],
            properties={
                'templates': [],
                'threshold': 0.8,
                'method': 'template_matching'
            }
        )
    )

    # 注册控制节点
    registry.register_node_type(
        ControlNode,
        NodeMetadata(
            type_id="if_node",
            display_name="If Node",
            category="Flow Control",
            description="Conditional flow control",
            color_scheme={
                'header': '#e74c3c',
                'control_header': '#c0392b',
                'background': '#fadbd8'
            },
            ports=[
                PortConfig("condition", "input", "any"),
                PortConfig("true", "output", "flow"),
                PortConfig("false", "output", "flow")
            ],
            properties={
                'condition': '',
                'evaluate_mode': 'expression'
            }
        )
    )

    # 注册组合节点
    registry.register_node_type(
        CompositeNode,
        NodeMetadata(
            type_id="group_node",
            display_name="Group Node",
            category="Organization",
            description="Group multiple nodes",
            color_scheme={
                'composite_header': '#9b59b6',
                'background': '#f5f3f7'
            },
            resizable=True,
            default_size=(400, 300),
            ports=[
                PortConfig("group_input", "input", "any"),
                PortConfig("group_output", "output", "any")
            ],
            properties={
                'description': ''
            }
        )
    )