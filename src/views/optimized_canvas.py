# optimized_canvas_complete.py
import json
import time
import os
from typing import Dict, List, Optional, Any, Tuple
from PySide6.QtCore import Qt, QPointF, QRectF, Signal, QObject, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QWheelEvent, QMouseEvent, QKeyEvent, QBrush, QFont, QPainterPath
from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QWidget, QVBoxLayout, QLabel,
                               QMenu, QGraphicsItem, QGraphicsRectItem, QMessageBox, QFileDialog)

from src.views.node_system.node_registry import NodeRegistry, NodeMetadata, PortConfig
from src.views.node_system.port_system import Connection, ConnectionManager, InputPort, OutputPort
from src.views.node_system.render_optimization import RenderOptimizer
from src.pipeline import TaskNode
from src.config_manager import config_manager


# ============= BaseNode 定义（修复元类问题） =============

class BaseNode(QGraphicsItem):
    """所有节点的基类 - 不使用ABC元类以避免冲突"""

    # 信号定义
    class Signals(QObject):
        property_changed = Signal(str, object)  # 属性名, 新值
        port_connected = Signal(str, object)  # 端口名, 连接
        port_disconnected = Signal(str, object)  # 端口名, 连接
        position_changed = Signal(QPointF)
        selected_changed = Signal(bool)

    def __init__(self, node_id: str, metadata: 'NodeMetadata', parent=None, **kwargs):
        super().__init__(parent)
        self.node_id = node_id
        self.metadata = metadata
        self.signals = self.Signals()

        # 添加 task_node 支持
        self.task_node = kwargs.get('task_node')

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
        from src.views.node_system.port_system import InputPort, OutputPort

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

    def initialize(self):
        """初始化节点（子类应该重写）"""
        pass

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """处理节点逻辑（子类应该重写）"""
        return {}

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

    def _paint_header(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制标题栏（子类应该实现）"""
        header_rect = QRectF(0, 0, self._bounds.width(), 30)

        painter.setPen(Qt.NoPen)
        painter.setBrush(colors['header'])
        painter.drawRoundedRect(header_rect, 5, 5)

        painter.setPen(colors['header_text'])
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(
            header_rect.adjusted(10, 0, -10, 0),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.metadata.display_name
        )

    def _paint_content(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制内容区域（子类应该实现）"""
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

    def mousePressEvent(self, event):
        """处理鼠标按下事件"""
        if (event.button() == Qt.LeftButton and
                event.type() == event.GraphicsSceneMouseDoubleClick and
                0 <= event.pos().x() <= self._bounds.width() and
                0 <= event.pos().y() <= 30):  # 点击标题栏
            # 切换折叠状态
            self._collapsed = not self._collapsed
            if self._collapsed:
                self._bounds.setHeight(30)
            else:
                self._bounds.setHeight(self._size.y())
            self._update_port_positions()
            self.update()
            event.accept()
            return

        super().mousePressEvent(event)


# ============= 节点类型定义 =============

class GenericNode(BaseNode):
    """通用节点 - 对应 TYPE_GENERIC"""

    def __init__(self, node_id: str, metadata: NodeMetadata, **kwargs):
        super().__init__(node_id, metadata, **kwargs)
        self.task_node = kwargs.get('task_node')
        self._collapsed = False

    def initialize(self):
        """初始化节点"""
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
        painter.setFont(QFont("Arial", 9, QFont.Bold))

        title = self.get_property('display_name') or self.metadata.display_name
        painter.drawText(
            header_rect.adjusted(10, 0, -10, 0),
            Qt.AlignVCenter | Qt.AlignLeft,
            title
        )

    def _paint_content(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制内容区域"""
        if self._collapsed:
            return

        content_rect = QRectF(
            self.content_margin,
            self.header_height + self.content_margin,
            self._bounds.width() - 2 * self.content_margin,
            self._bounds.height() - self.header_height - 2 * self.content_margin
        )

        # 绘制属性
        painter.setPen(colors['content_text'])
        painter.setFont(QFont("Arial", 8))

        y_offset = 0
        properties_to_show = ['recognition', 'action', 'enabled']

        for prop in properties_to_show:
            if y_offset + 20 > content_rect.height():
                break

            value = self.get_property(prop)
            if value is not None:
                text = f"{prop}: {value}"
                text_rect = QRectF(
                    content_rect.x(),
                    content_rect.y() + y_offset,
                    content_rect.width(),
                    20
                )
                painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, text)
                y_offset += 20

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """处理节点逻辑"""
        # 这里可以调用 task_node 的处理逻辑
        return {}

    def on_property_changed(self, name: str, old_value: Any, new_value: Any):
        """属性变化时的处理"""
        if self.task_node and hasattr(self.task_node, name):
            setattr(self.task_node, name, new_value)


class RecognitionNode(BaseNode):
    """识别节点 - 对应 TYPE_RECOGNITION"""

    def __init__(self, node_id: str, metadata: NodeMetadata, **kwargs):
        super().__init__(node_id, metadata, **kwargs)
        self.task_node = kwargs.get('task_node')
        self._images = []
        self._collapsed = False

    def initialize(self):
        """初始化节点"""
        self.header_height = 30
        self.content_margin = 10
        self._load_images()

    def _load_images(self):
        """加载识别图像"""
        if not self.task_node or not hasattr(self.task_node, 'template'):
            return

        template = self.task_node.template
        if isinstance(template, str):
            template = [template]
        elif not isinstance(template, list):
            return

        base_path = config_manager.config.get("recent_files", {}).get("base_resource_path", "")
        if not base_path:
            return

        from PySide6.QtGui import QPixmap
        self._images = []

        for img_path in template:
            full_path = os.path.join(base_path, "image", img_path)
            try:
                pixmap = QPixmap(full_path)
                if not pixmap.isNull():
                    self._images.append(pixmap)
            except:
                pass

    def _paint_header(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制标题栏"""
        header_rect = QRectF(0, 0, self._bounds.width(), self.header_height)

        # 使用绿色系配色
        painter.setPen(Qt.NoPen)
        painter.setBrush(colors.get('recognition_header', QColor(60, 150, 60)))
        painter.drawRoundedRect(header_rect, 5, 5)

        # 绘制标题
        painter.setPen(colors['header_text'])
        painter.setFont(QFont("Arial", 9, QFont.Bold))

        title = self.get_property('display_name') or self.metadata.display_name
        painter.drawText(
            header_rect.adjusted(10, 0, -10, 0),
            Qt.AlignVCenter | Qt.AlignLeft,
            title
        )

    def _paint_content(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制内容 - 显示图像"""
        if self._collapsed:
            return

        content_rect = QRectF(
            self.content_margin,
            self.header_height + self.content_margin,
            self._bounds.width() - 2 * self.content_margin,
            self._bounds.height() - self.header_height - 2 * self.content_margin
        )

        if not self._images:
            # 显示无图像提示
            painter.setPen(colors['content_text'])
            painter.setFont(QFont("Arial", 9))
            painter.drawText(content_rect, Qt.AlignCenter, "No Template Images")
            return

        # 绘制图像网格
        import math
        img_count = len(self._images)

        if img_count == 1:
            cols, rows = 1, 1
        elif img_count == 2:
            cols, rows = 2, 1
        elif img_count <= 4:
            cols, rows = 2, 2
        else:
            cols = int(math.ceil(math.sqrt(img_count)))
            rows = int(math.ceil(img_count / cols))

        padding = 5
        img_width = (content_rect.width() - (cols - 1) * padding) / cols
        img_height = (content_rect.height() - (rows - 1) * padding) / rows
        img_size = min(img_width, img_height, 60)  # 限制最大尺寸

        for idx, img in enumerate(self._images):
            row = idx // cols
            col = idx % cols

            x = content_rect.x() + col * (img_size + padding)
            y = content_rect.y() + row * (img_size + padding)

            img_rect = QRectF(x, y, img_size, img_size)

            # 绘制边框
            painter.setPen(QPen(QColor(180, 180, 180), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(img_rect)

            # 绘制图像
            painter.drawPixmap(img_rect.toRect(), img)

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """处理识别逻辑"""
        return {'detected': False}

    def on_property_changed(self, name: str, old_value: Any, new_value: Any):
        """属性变化时的处理"""
        if self.task_node and hasattr(self.task_node, name):
            setattr(self.task_node, name, new_value)

        if name == 'template':
            self._load_images()
            self.update()


class UnknownNode(BaseNode):
    """未知节点 - 对应 TYPE_UNKNOWN"""

    def __init__(self, node_id: str, metadata: NodeMetadata, **kwargs):
        super().__init__(node_id, metadata, **kwargs)
        self.task_node = kwargs.get('task_node')
        self._collapsed = False

    def initialize(self):
        """初始化节点"""
        self.header_height = 30
        self.content_margin = 10

    def _paint_header(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制标题栏"""
        header_rect = QRectF(0, 0, self._bounds.width(), self.header_height)

        # 使用红色系配色
        painter.setPen(Qt.NoPen)
        painter.setBrush(colors.get('unknown_header', QColor(180, 40, 40)))
        painter.drawRoundedRect(header_rect, 5, 5)

        # 绘制标题
        painter.setPen(colors['header_text'])
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        painter.drawText(
            header_rect.adjusted(10, 0, -10, 0),
            Qt.AlignVCenter | Qt.AlignLeft,
            "Unknown Node"
        )

    def _paint_content(self, painter: QPainter, colors: Dict[str, QColor]):
        """绘制内容"""
        if self._collapsed:
            return

        content_rect = QRectF(
            self.content_margin,
            self.header_height + self.content_margin,
            self._bounds.width() - 2 * self.content_margin,
            self._bounds.height() - self.header_height - 2 * self.content_margin
        )

        # 绘制警告图标和文本
        painter.setPen(colors.get('unknown_text', QColor(150, 30, 30)))
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        painter.drawText(content_rect, Qt.AlignCenter, "未知节点类型\n⚠")

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """处理逻辑 - 未知节点不处理"""
        return {}

    def on_property_changed(self, name: str, old_value: Any, new_value: Any):
        """属性变化时的处理"""
        pass


# ============= 命令系统 =============

class Command:
    """命令基类"""

    def execute(self):
        pass

    def undo(self):
        pass


class AddNodeCommand(Command):
    """添加节点命令"""

    def __init__(self, canvas, node_type: str, position: QPointF, task_node=None):
        self.canvas = canvas
        self.node_type = node_type
        self.position = position
        self.task_node = task_node
        self.node = None

    def execute(self):
        self.node = self.canvas.add_node(self.node_type, self.position, self.task_node)
        return self.node

    def undo(self):
        if self.node:
            self.canvas.remove_node(self.node)


class RemoveNodeCommand(Command):
    """删除节点命令"""

    def __init__(self, canvas, node):
        self.canvas = canvas
        self.node = node
        self.connections = []
        self.position = node.pos()

    def execute(self):
        # 保存连接信息
        for port in self.node.get_all_input_ports().values():
            self.connections.extend([(conn, 'input', port) for conn in port.get_connections()])
        for port in self.node.get_all_output_ports().values():
            self.connections.extend([(conn, 'output', port) for conn in port.get_connections()])

        self.canvas.remove_node(self.node)

    def undo(self):
        # 恢复节点
        self.canvas.scene.addItem(self.node)
        self.canvas.nodes[self.node.node_id] = self.node
        self.node.setPos(self.position)

        # 恢复连接
        for conn, port_type, port in self.connections:
            self.canvas.scene.addItem(conn)
            if port_type == 'input':
                port.add_connection(conn)
            else:
                port.add_connection(conn)


class MoveNodeCommand(Command):
    """移动节点命令"""

    def __init__(self, node, old_pos: QPointF, new_pos: QPointF):
        self.node = node
        self.old_pos = old_pos
        self.new_pos = new_pos

    def execute(self):
        self.node.setPos(self.new_pos)

    def undo(self):
        self.node.setPos(self.old_pos)


class CommandManager:
    """命令管理器"""

    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []

    def execute(self, command):
        result = command.execute()
        self.undo_stack.append(command)
        self.redo_stack.clear()
        return result

    def undo(self):
        if self.undo_stack:
            command = self.undo_stack.pop()
            command.undo()
            self.redo_stack.append(command)
            return True
        return False

    def redo(self):
        if self.redo_stack:
            command = self.redo_stack.pop()
            command.execute()
            self.undo_stack.append(command)
            return True
        return False


# ============= 右键菜单系统 =============

class CanvasContextMenu:
    """画布右键菜单"""

    def __init__(self, canvas):
        self.canvas = canvas

    def show_node_menu(self, node, global_pos):
        """显示节点右键菜单"""
        menu = QMenu()

        # 复制
        copy_action = menu.addAction("复制节点")
        copy_action.triggered.connect(lambda: self._copy_node(node))

        # 删除
        delete_action = menu.addAction("删除节点")
        delete_action.triggered.connect(lambda: self._delete_node(node))

        menu.addSeparator()

        # 调试选项
        if node.task_node:
            debug_menu = QMenu("调试", menu)

            debug_action = debug_menu.addAction("从该节点开始调试")
            debug_action.triggered.connect(lambda: self._debug_node(node))

            debug_only_action = debug_menu.addAction("仅调试该节点")
            debug_only_action.triggered.connect(lambda: self._debug_node_only(node))

            menu.addMenu(debug_menu)

        menu.exec(global_pos)

    def show_canvas_menu(self, scene_pos, global_pos):
        """显示画布右键菜单"""
        menu = QMenu()

        # 添加节点
        add_menu = QMenu("添加节点", menu)

        add_menu.addAction("通用节点").triggered.connect(
            lambda: self._add_node('generic_node', scene_pos)
        )
        add_menu.addAction("识别节点").triggered.connect(
            lambda: self._add_node('recognition_node', scene_pos)
        )
        add_menu.addAction("未知节点").triggered.connect(
            lambda: self._add_node('unknown_node', scene_pos)
        )

        menu.addMenu(add_menu)

        # 粘贴
        if hasattr(self.canvas, '_clipboard') and self.canvas._clipboard:
            menu.addSeparator()
            paste_action = menu.addAction("粘贴节点")
            paste_action.triggered.connect(lambda: self._paste_node(scene_pos))

        menu.exec(global_pos)

    def _copy_node(self, node):
        """复制节点"""
        self.canvas._clipboard = {
            'type': node.metadata.type_id,
            'properties': node.get_properties(),
            'task_node': node.task_node
        }

    def _paste_node(self, position):
        """粘贴节点"""
        if hasattr(self.canvas, '_clipboard') and self.canvas._clipboard:
            data = self.canvas._clipboard
            task_node = data.get('task_node')

            # 创建新的 task_node 副本
            if task_node:
                import copy
                task_node = copy.deepcopy(task_node)

            node = self.canvas.add_node(
                data['type'],
                position,
                task_node
            )

            if node:
                # 设置属性
                for key, value in data['properties'].items():
                    node.set_property(key, value)

    def _delete_node(self, node):
        """删除节点"""
        cmd = RemoveNodeCommand(self.canvas, node)
        self.canvas.command_manager.execute(cmd)

    def _add_node(self, node_type, position):
        """添加节点"""
        cmd = AddNodeCommand(self.canvas, node_type, position)
        self.canvas.command_manager.execute(cmd)

    def _debug_node(self, node):
        """调试节点"""
        print(f"调试节点: {node.node_id}")

    def _debug_node_only(self, node):
        """仅调试该节点"""
        print(f"仅调试节点: {node.node_id}")


# ============= 主画布类 =============

class OptimizedCanvas(QWidget):
    """优化的节点画布"""

    # 信号
    node_selected = Signal(object)  # 节点选中信号

    def __init__(self, parent=None):
        super().__init__(parent)

        # 初始化组件
        self._init_components()

        # 初始化UI
        self._init_ui()

        # 注册节点类型
        self._register_node_types()

        # 连接信号
        self._connect_signals()

        # 初始化交互状态
        self._init_interaction_state()

    def _init_components(self):
        """初始化组件"""
        # 场景
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-10000, -10000, 20000, 20000)

        # 渲染优化器
        self.optimizer = RenderOptimizer(self.scene.sceneRect())

        # 节点注册器
        self.node_registry = NodeRegistry()

        # 连接管理器
        self.connection_manager = ConnectionManager(self)

        # 命令管理器
        self.command_manager = CommandManager()

        # 右键菜单
        self.context_menu = CanvasContextMenu(self)

        # 节点和连接容器
        self.nodes: Dict[str, BaseNode] = {}

        # 剪贴板
        self._clipboard = None

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建视图
        self.view = OptimizedGraphicsView(self.scene, self)
        layout.addWidget(self.view)

        # 信息栏
        self.info_label = QLabel("Ready")
        self.info_label.setStyleSheet("background-color: #f0f0f0; padding: 5px;")
        layout.addWidget(self.info_label)

        # 绘制网格
        self._create_grid()

    def _create_grid(self):
        """创建网格背景"""
        grid_size = 20
        grid_pen_primary = QPen(QColor(200, 200, 200), 0.8)
        grid_pen_secondary = QPen(QColor(230, 230, 230), 0.5)

        for i in range(-1000, 1000, grid_size):
            if i % (grid_size * 5) == 0:
                self.scene.addLine(i, -1000, i, 1000, grid_pen_primary)
                self.scene.addLine(-1000, i, 1000, i, grid_pen_primary)
            else:
                self.scene.addLine(i, -1000, i, 1000, grid_pen_secondary)
                self.scene.addLine(-1000, i, 1000, i, grid_pen_secondary)

    def _register_node_types(self):
        """注册节点类型"""
        # 通用节点
        self.node_registry.register_node_type(
            GenericNode,
            NodeMetadata(
                type_id="generic_node",
                display_name="Generic Node",
                category="General",
                color_scheme={
                    'header': '#3b82f6',
                    'background': '#eff6ff',
                    'border': '#2563eb',
                    'header_text': '#ffffff',
                    'content_text': '#1e3a8a'
                },
                ports=[
                    PortConfig("input", "input", "any", "top"),
                    PortConfig("next", "output", "any", "bottom"),
                    PortConfig("on_error", "output", "any", "left"),
                    PortConfig("interrupt", "output", "any", "right")
                ],
                properties={
                    'recognition': 'DirectHit',
                    'action': 'Click',
                    'enabled': True
                }
            )
        )

        # 识别节点
        self.node_registry.register_node_type(
            RecognitionNode,
            NodeMetadata(
                type_id="recognition_node",
                display_name="Recognition Node",
                category="Recognition",
                color_scheme={
                    'header': '#16a34a',
                    'background': '#f0fdf4',
                    'border': '#15803d',
                    'recognition_header': '#16a34a',
                    'header_text': '#ffffff',
                    'content_text': '#14532d'
                },
                ports=[
                    PortConfig("input", "input", "any", "top"),
                    PortConfig("next", "output", "any", "bottom"),
                    PortConfig("on_error", "output", "any", "left"),
                    PortConfig("interrupt", "output", "any", "right")
                ],
                properties={
                    'recognition': 'TemplateMatch',
                    'action': 'Click',
                    'template': [],
                    'threshold': 0.8,
                    'enabled': True
                }
            )
        )

        # 未知节点
        self.node_registry.register_node_type(
            UnknownNode,
            NodeMetadata(
                type_id="unknown_node",
                display_name="Unknown Node",
                category="Unknown",
                color_scheme={
                    'header': '#dc2626',
                    'background': '#fef2f2',
                    'border': '#b91c1c',
                    'unknown_header': '#dc2626',
                    'unknown_text': '#7f1d1d',
                    'header_text': '#ffffff',
                    'content_text': '#991b1b'
                },
                ports=[
                    PortConfig("input", "input", "any", "top")
                ],
                properties={}
            )
        )

    def _connect_signals(self):
        """连接信号"""
        self.scene.selectionChanged.connect(self._on_selection_changed)

    def _init_interaction_state(self):
        """初始化交互状态"""
        self.is_panning = False
        self.is_connecting = False
        self.last_mouse_pos = None
        self.selected_nodes = []
        self.zoom_factor = 1.15

    def add_node(self, node_type: str, position: QPointF = None, task_node=None) -> Optional[BaseNode]:
        """添加节点"""
        try:
            # 生成唯一ID
            node_id = f"node_{len(self.nodes)}_{int(time.time() * 1000)}"

            # 准备参数
            kwargs = {}
            if task_node:
                kwargs['task_node'] = task_node

            # 创建节点
            node = self.node_registry.create_node(node_type, node_id, **kwargs)

            # 设置显示名称
            if task_node and hasattr(task_node, 'name'):
                node.set_property('display_name', task_node.name)

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

            # 添加到空间索引
            self.optimizer.add_item(node, node.boundingRect())

            return node

        except Exception as e:
            print(f"Failed to add node: {e}")
            return None

    def remove_node(self, node: BaseNode):
        """移除节点"""
        if node.node_id not in self.nodes:
            return

        # 移除连接
        for port in node.get_all_input_ports().values():
            self.connection_manager.remove_connections_for_port(port)
        for port in node.get_all_output_ports().values():
            self.connection_manager.remove_connections_for_port(port)

        # 从空间索引移除
        self.optimizer.remove_item(node)

        # 从场景移除
        self.scene.removeItem(node)

        # 从容器移除
        del self.nodes[node.node_id]

    def _on_selection_changed(self):
        """处理选择变化"""
        selected_items = self.scene.selectedItems()
        self.selected_nodes = [item for item in selected_items if isinstance(item, BaseNode)]

        if self.selected_nodes:
            # 发送选中信号
            if len(self.selected_nodes) == 1:
                self.node_selected.emit(self.selected_nodes[0])

            self.info_label.setText(f"Selected {len(self.selected_nodes)} nodes")
        else:
            self.info_label.setText("Ready")

    def keyPressEvent(self, event: QKeyEvent):
        """处理键盘事件"""
        # Ctrl+Z 撤销
        if event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
            if self.command_manager.undo():
                self.info_label.setText("Undo")

        # Ctrl+Y 重做
        elif event.key() == Qt.Key_Y and event.modifiers() & Qt.ControlModifier:
            if self.command_manager.redo():
                self.info_label.setText("Redo")

        # Delete 删除
        elif event.key() == Qt.Key_Delete:
            for node in self.selected_nodes:
                cmd = RemoveNodeCommand(self, node)
                self.command_manager.execute(cmd)

        # Ctrl+C 复制
        elif event.key() == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
            if self.selected_nodes:
                self.context_menu._copy_node(self.selected_nodes[0])

        # Ctrl+V 粘贴
        elif event.key() == Qt.Key_V and event.modifiers() & Qt.ControlModifier:
            if self._clipboard:
                center = self.view.mapToScene(self.view.viewport().rect().center())
                self.context_menu._paste_node(center)

        super().keyPressEvent(event)

    def save_to_file(self, file_path: str = None) -> bool:
        """保存到文件"""
        if not file_path:
            file_path = config_manager.config.get("recent_files", {}).get("current_opened_file")

        if not file_path:
            return False

        try:
            # 收集所有节点的 task_node 数据
            task_data = {}

            for node in self.nodes.values():
                if hasattr(node, 'task_node') and node.task_node:
                    task_node = node.task_node
                    if hasattr(task_node, 'name'):
                        task_data[task_node.name] = task_node.to_dict()

            # 保存到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)

            self.info_label.setText(f"Saved to {os.path.basename(file_path)}")
            return True

        except Exception as e:
            print(f"Failed to save: {e}")
            return False

    def load_file(self, file_path: str) -> bool:
        """从文件加载"""
        try:
            # 清空当前内容
            self.clear()

            # 加载数据
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 创建节点
            node_positions = {}
            y_offset = 0

            for name, node_data in data.items():
                # 创建 TaskNode
                task_node = TaskNode(name, **node_data)

                # 确定节点类型
                node_type = 'generic_node'
                if hasattr(task_node, 'template') and task_node.template:
                    node_type = 'recognition_node'
                elif hasattr(task_node, '_node_type') and task_node._node_type == 'unknown':
                    node_type = 'unknown_node'

                # 创建节点
                position = QPointF(0, y_offset)
                node = self.add_node(node_type, position, task_node)

                if node:
                    node_positions[name] = node
                    y_offset += 250

            # 创建连接
            for name, node_data in data.items():
                if name not in node_positions:
                    continue

                source_node = node_positions[name]

                # 处理 next 连接
                if 'next' in node_data and node_data['next']:
                    next_names = node_data['next']
                    if isinstance(next_names, str):
                        next_names = [next_names]

                    for next_name in next_names:
                        if next_name in node_positions:
                            target_node = node_positions[next_name]
                            source_port = source_node.get_output_port('next')
                            target_port = target_node.get_input_port('input')

                            if source_port and target_port:
                                self.connection_manager.complete_connection(source_port, target_port)

            self.info_label.setText(f"Loaded {len(node_positions)} nodes")
            return True

        except Exception as e:
            print(f"Failed to load: {e}")
            return False

    def clear(self):
        """清空画布"""
        # 移除所有节点
        for node in list(self.nodes.values()):
            self.remove_node(node)

        # 清空连接
        self.connection_manager.clear()

        # 清空选择
        self.selected_nodes.clear()

        # 清空撤销/重做栈
        self.command_manager = CommandManager()

        # 重置视图
        self.view.resetTransform()
        self.view.centerOn(0, 0)

    def center_on_content(self):
        """居中显示内容"""
        if self.nodes:
            rect = QRectF()
            for node in self.nodes.values():
                rect = rect.united(node.sceneBoundingRect())
            rect.adjust(-100, -100, 100, 100)
            self.view.fitInView(rect, Qt.KeepAspectRatio)
        else:
            self.view.centerOn(0, 0)

    def zoom(self, factor):
        """缩放视图"""
        self.view.scale(factor, factor)


class OptimizedGraphicsView(QGraphicsView):
    """优化的图形视图"""

    def __init__(self, scene: QGraphicsScene, canvas: OptimizedCanvas):
        super().__init__(scene)
        self.canvas = canvas

        # 视图设置
        self.setRenderHint(QPainter.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        self.setOptimizationFlags(
            QGraphicsView.DontAdjustForAntialiasing |
            QGraphicsView.DontSavePainterState
        )

        # 交互状态
        self.connecting_from_port = None
        self.temp_connection_line = None

    def mousePressEvent(self, event: QMouseEvent):
        """处理鼠标按下"""
        scene_pos = self.mapToScene(event.pos())
        item = self.scene().itemAt(scene_pos, self.transform())

        if event.button() == Qt.LeftButton:
            # 检查是否点击了输出端口
            if isinstance(item, OutputPort):
                self.connecting_from_port = item
                # 创建临时连接线
                self.temp_connection_line = self.scene().addLine(
                    item.scenePos().x(), item.scenePos().y(),
                    scene_pos.x(), scene_pos.y(),
                    QPen(QColor(100, 100, 100), 2, Qt.DashLine)
                )
                event.accept()
                return

        elif event.button() == Qt.RightButton:
            # 右键菜单
            if isinstance(item, BaseNode):
                self.canvas.context_menu.show_node_menu(item, event.globalPos())
            else:
                self.canvas.context_menu.show_canvas_menu(scene_pos, event.globalPos())
            event.accept()
            return

        elif event.button() == Qt.MiddleButton:
            # 开始拖动画布
            self.canvas.is_panning = True
            self.canvas.last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """处理鼠标移动"""
        scene_pos = self.mapToScene(event.pos())

        # 更新临时连接线
        if self.temp_connection_line and self.connecting_from_port:
            line = self.temp_connection_line.line()
            line.setP2(scene_pos)
            self.temp_connection_line.setLine(line)
            event.accept()
            return

        # 拖动画布
        if self.canvas.is_panning and self.canvas.last_mouse_pos:
            delta = event.pos() - self.canvas.last_mouse_pos
            self.canvas.last_mouse_pos = event.pos()

            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """处理鼠标释放"""
        scene_pos = self.mapToScene(event.pos())
        item = self.scene().itemAt(scene_pos, self.transform())

        if event.button() == Qt.LeftButton and self.connecting_from_port:
            # 完成连接
            if isinstance(item, InputPort):
                if self.connecting_from_port.can_connect_to(item):
                    self.canvas.connection_manager.complete_connection(
                        self.connecting_from_port, item
                    )

            # 清理临时连接线
            if self.temp_connection_line:
                self.scene().removeItem(self.temp_connection_line)
                self.temp_connection_line = None

            self.connecting_from_port = None
            event.accept()
            return

        elif event.button() == Qt.MiddleButton:
            self.canvas.is_panning = False
            self.setCursor(Qt.ArrowCursor)

        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """处理滚轮缩放"""
        # 设置缩放锚点
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        # 缩放
        scale_factor = 1.15
        if event.angleDelta().y() > 0:
            self.scale(scale_factor, scale_factor)
        else:
            self.scale(1 / scale_factor, 1 / scale_factor)