import hashlib  # 用于MD5哈希计算
import os

from PySide6.QtCore import QRectF, Qt, QPointF, Signal, QObject
from PySide6.QtGui import QPainter, QFont, QColor, QPen, QBrush, QPainterPath, QPixmap
from PySide6.QtWidgets import QGraphicsItem

from src.config_manager import config_manager
from src.node_system.port import InputPort, OutputPort


# Signals need to be in a QObject, so we create a helper class
class NodeSignals(QObject):
    propertyChanged = Signal(str, str, object)  # node_id, property_name, new_value


class Node(QGraphicsItem):
    def __init__(self, id=None, title="", task_node=None, parent=None, default_image_path="default_image.png"):
        super().__init__(parent)
        self.task_node = task_node

        # Store config_manager
        self.config_manager = config_manager

        # Calculate image directory path from resource directory
        self.image_dir = None
        if self.config_manager:
            resource_dir = self.config_manager.config.get("recent_files", {}).get("resource_dir", "")
            if resource_dir:
                # Get the parent directory by removing the last component
                base_dir = os.path.dirname(resource_dir)
                # Append "image" directory (not "images")
                self.image_dir = os.path.join(base_dir, "image")

        # 初始化节点ID
        self._initialize_id(id)

        self.title = title
        self.bounds = QRectF(0, 0, 240, 200)  # Make slightly taller for image
        self.header_height = 30
        self.content_start = self.header_height + 10
        self.signals = NodeSignals()

        # Image display settings
        self.image_height = 80  # Height for the image display area
        self.default_image_path = default_image_path
        self.default_image = None
        self.recognition_image = None  # Will hold the image to recognize
        self.has_template = False  # 标记是否有template属性

        # 检查是否有template属性
        self._check_template()

        self._load_images()  # Load images

        # Node can be selected and moved
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

        # 初始化端口 - 抽象为单独方法便于子类重写
        self.input_port = None
        self.output_ports = {}
        self._initialize_ports()

        # Create a collapsed state
        self.collapsed = False
        self.original_height = self.bounds.height()

    def _initialize_id(self, id=None):
        """初始化节点ID，子类可重写此方法自定义ID生成逻辑"""
        if self.task_node and hasattr(self.task_node, 'name'):
            self.id = hashlib.md5(self.task_node.name.encode()).hexdigest()[:6].upper()
        else:
            # 仅在task_node不存在或没有name属性时使用传入的id或设置为"UNKNOWN"
            self.id = id if id else "UNKNOWN"

    def _check_template(self):
        """检查是否有template属性，子类可重写以自定义template检测逻辑"""
        if self.task_node and hasattr(self.task_node, 'template') and self.task_node.template:
            self.has_template = True
        else:
            self.has_template = False

    def _load_images(self):
        """Load the default image and check for template attribute"""
        # Construct full path for default image
        default_image_path = self.default_image_path
        if self.image_dir and not os.path.isabs(self.default_image_path):
            default_image_path = os.path.join(self.image_dir, self.default_image_path)

        # Load default image
        try:
            self.default_image = QPixmap(default_image_path)
            if self.default_image.isNull():
                # Create a simple default image if file can't be loaded
                self.default_image = QPixmap(self.image_height, self.image_height)
                self.default_image.fill(QColor(200, 200, 200))
        except:
            # Create a simple default image if file can't be loaded
            self.default_image = QPixmap(self.image_height, self.image_height)
            self.default_image.fill(QColor(200, 200, 200))

        self.recognition_image = self.default_image

        # 检查task_node是否有template属性，并且属性有值
        if self.has_template:
            # 如果有template属性，加载对应的图像
            self._load_recognition_image()

    def _load_recognition_image(self):
        """Load the recognition image from the task_node"""
        image_path = None

        # 首先尝试从template属性获取图像路径
        if hasattr(self.task_node, 'template'):
            template = self.task_node.template
            # 处理template是列表的情况，取第一个元素
            if isinstance(template, list) and len(template) > 0:
                image_path = template[0]
            # 处理template是字符串的情况
            elif isinstance(template, str):
                image_path = template
        base_path = config_manager.config["recent_files"]["base_resource_path"]
        full_path = os.path.join(base_path, "image", image_path)
        # Try to load the image if a path was
        if full_path:

            try:
                self.recognition_image = QPixmap(full_path)
                if self.recognition_image.isNull():
                    self.recognition_image = self.default_image
            except:
                self.recognition_image = self.default_image

    def _initialize_ports(self):
        """
        初始化节点的所有端口
        将过程拆分为创建输入和输出端口两个方法，方便子类重写
        """
        # 初始化输入端口
        self._initialize_input_ports()

        # 初始化输出端口
        self._initialize_output_ports()

    def _initialize_input_ports(self):
        """初始化输入端口，子类可重写此方法自定义输入端口逻辑"""
        width = self.bounds.width()

        # 创建输入端口（顶部中心）
        self.input_port = InputPort(
            self,
            QPointF(width / 2, 0),
            self
        )

    def _initialize_output_ports(self):
        """初始化输出端口，子类可重写此方法自定义输出端口逻辑"""
        width = self.bounds.width()
        height = self.bounds.height()

        # 创建输出端口字典
        self.output_ports = {}

        # "next" output port at bottom center
        self.output_ports["next"] = OutputPort(
            self,
            QPointF(width / 2, height),
            "next",
            self
        )

        # "on_error" output port at left center
        self.output_ports["on_error"] = OutputPort(
            self,
            QPointF(0, height / 2),
            "on_error",
            self
        )

        # "interrupt" output port at right center
        self.output_ports["interrupt"] = OutputPort(
            self,
            QPointF(width, height / 2),
            "interrupt",
            self
        )

    def paint(self, painter, option, widget):
        """
        绘制节点的界面。将绘制过程分为几个逻辑组件以便子类重写
        """
        # 设置渲染提示以获取更平滑的外观
        painter.setRenderHint(QPainter.Antialiasing)

        # 定义颜色 - 子类可重写这些颜色
        colors = self._get_node_colors()

        # 绘制节点阴影
        self._paint_shadow(painter, colors)

        # 绘制节点主体
        self._paint_body(painter, colors)

        # 绘制节点标题栏
        self._paint_header(painter, colors)

        # 绘制节点ID徽章
        self._paint_id_badge(painter, colors)

        # 如果未折叠，绘制内容
        if not self.collapsed:
            # 绘制分隔线
            self._paint_separator(painter, colors)

            # 根据是否有template属性选择不同的显示方式
            if self.has_template:
                self._paint_template_content(painter, colors)
            else:
                self._paint_properties_content(painter, colors)

    def _get_node_colors(self):
        """获取节点的颜色方案，子类可重写以更改颜色"""
        return {
            'header': QColor(60, 120, 190),  # 蓝色标题栏
            'body': QColor(240, 240, 240),  # 浅灰色主体
            'border': QColor(30, 60, 90) if not self.isSelected() else QColor(255, 165, 0),  # 深蓝色边框或橙色（选中时）
            'header_text': QColor(255, 255, 255),  # 标题栏的白色文本
            'shadow': QColor(50, 50, 50, 40),  # 半透明阴影
            'property_title': QColor(60, 60, 60),  # 属性标题颜色
            'property_value': QColor(80, 80, 80),  # 属性值颜色
            'separator': QColor(100, 100, 100)  # 分隔线颜色
        }

    def _paint_shadow(self, painter, colors):
        """绘制节点阴影"""
        painter.save()
        shadow_rect = self.bounds.adjusted(4, 4, 4, 4)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(colors['shadow']))
        painter.drawRoundedRect(shadow_rect, 5, 5)
        painter.restore()

    def _paint_body(self, painter, colors):
        """绘制节点主体"""
        painter.setPen(QPen(colors['border'], 1.5))
        painter.setBrush(QBrush(colors['body']))

        # 绘制圆角矩形
        path = QPainterPath()
        path.addRoundedRect(self.bounds, 5, 5)
        painter.drawPath(path)

    def _paint_header(self, painter, colors):
        """绘制节点标题栏"""
        header_rect = QRectF(0, 0, self.bounds.width(), self.header_height)
        header_path = QPainterPath()
        header_path.addRoundedRect(header_rect, 5, 5)

        # 创建裁剪区域使只有顶部角为圆形
        painter.save()
        painter.setClipPath(header_path)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(colors['header']))
        painter.drawRect(header_rect)
        painter.restore()

        # 绘制标题文本
        painter.setPen(colors['header_text'])
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        title_width = self.bounds.width() - 70  # 预留ID徽章的空间
        painter.drawText(
            QRectF(10, 0, title_width, self.header_height),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.title
        )

    def _paint_id_badge(self, painter, colors):
        """绘制ID徽章"""
        id_text = f"{self.id}"
        id_font = QFont("Monospace", 7)
        painter.setFont(id_font)

        # 计算ID文本的宽度
        metrics = painter.fontMetrics()
        id_width = metrics.horizontalAdvance(id_text) + 10  # 添加内边距

        # 绘制ID徽章
        id_rect = QRectF(self.bounds.width() - id_width - 5, 5, id_width, 20)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(30, 30, 30, 150))  # 半透明深色背景
        painter.drawRoundedRect(id_rect, 10, 10)

        # 绘制ID文本
        painter.setPen(QColor(220, 220, 220))  # 浅灰色文本
        painter.drawText(id_rect, Qt.AlignCenter, id_text)

    def _paint_separator(self, painter, colors):
        """绘制标题栏和内容区域之间的分隔线"""
        painter.setPen(QPen(colors['separator'], 0.5))
        y_pos = self.header_height
        painter.drawLine(0, y_pos, self.bounds.width(), y_pos)

    def _paint_template_content(self, painter, colors):
        """绘制包含模板图像的内容"""
        if self.recognition_image and not self.recognition_image.isNull():
            img_size = min(self.bounds.width() - 30, self.bounds.height() - self.content_start - 20)
            img_rect = QRectF(
                (self.bounds.width() - img_size) / 2,  # 水平居中
                self.content_start,
                img_size,
                img_size
            )

            # 图像周围添加一个微妙的框
            painter.setPen(QPen(QColor(180, 180, 180), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(img_rect)

            # 绘制图像
            painter.drawPixmap(img_rect.toRect(), self.recognition_image)

    def _paint_properties_content(self, painter, colors):
        """绘制节点属性内容"""
        if self.task_node:
            self._draw_properties(painter)

    def _draw_properties(self, painter):
        """单独的方法来绘制节点属性，仅在没有template属性时使用"""
        y_pos = self.content_start + 15

        # 修改属性显示的样式，使其更易读
        property_title_color = QColor(60, 60, 60)
        property_value_color = QColor(80, 80, 80)

        # Display key TaskNode properties
        properties_to_display = self._get_properties_to_display()

        # Draw the properties with enhanced styling
        for key, value in properties_to_display:
            if y_pos + 25 > self.bounds.height():
                # Don't render properties that would go outside the node
                break

            # 绘制属性键（粗体）
            painter.setFont(QFont("Arial", 8, QFont.Bold))
            painter.setPen(property_title_color)
            property_key = f"{key}:"
            painter.drawText(
                QRectF(10, y_pos, self.bounds.width() - 20, 12),
                Qt.AlignLeft,
                property_key
            )

            # 绘制属性值（常规字体）
            painter.setFont(QFont("Arial", 8))
            painter.setPen(property_value_color)

            # 处理长值的截断并添加省略号
            property_value = str(value)
            metrics = painter.fontMetrics()
            available_width = self.bounds.width() - 25
            if metrics.horizontalAdvance(property_value) > available_width:
                property_value = metrics.elidedText(property_value, Qt.ElideRight, available_width)

            painter.drawText(
                QRectF(15, y_pos + 13, self.bounds.width() - 25, 12),
                Qt.AlignLeft,
                property_value
            )

            y_pos += 30  # 增加属性之间的间距

    def _get_properties_to_display(self):
        """获取要显示的属性列表，子类可重写此方法自定义属性显示"""
        properties_to_display = []

        # Add essential properties
        if hasattr(self.task_node, 'recognition'):
            properties_to_display.append(("Recognition", self.task_node.recognition))

        if hasattr(self.task_node, 'action'):
            properties_to_display.append(("Action", self.task_node.action))

        if hasattr(self.task_node, 'enabled'):
            properties_to_display.append(("Enabled", str(self.task_node.enabled)))

        # Add important algorithm properties
        if hasattr(self.task_node, '_algorithm_properties'):
            for key, value in self.task_node._algorithm_properties.items():
                if isinstance(value, (str, int, float, bool)):
                    properties_to_display.append((key, str(value)))

        return properties_to_display

    def boundingRect(self):
        return self.bounds

    def set_position(self, x, y):
        self.setPos(x, y)
        # Update the connections when node is moved
        self._update_connections()

    def _update_connections(self):
        # Update all connections attached to this node
        if self.input_port and self.input_port.is_connected():
            connection = self.input_port.get_connection()
            if connection:
                connection.update_path()

        for port_type, port in self.output_ports.items():
            for connection in port.get_connections():
                if connection:
                    connection.update_path()

    def _update_port_positions(self):
        """
        更新所有端口位置
        将这个方法拆分为更新输入和输出端口两部分，方便子类重写
        """
        # 更新输入端口位置
        self._update_input_port_positions()

        # 更新输出端口位置
        self._update_output_port_positions()

    def _update_input_port_positions(self):
        """更新输入端口位置，子类可重写"""
        if self.input_port:
            width = self.bounds.width()
            self.input_port.setPos(width / 2, 0)

    def _update_output_port_positions(self):
        """更新输出端口位置，子类可重写"""
        width = self.bounds.width()
        height = self.bounds.height()

        # 更新输出端口位置
        if "next" in self.output_ports:
            self.output_ports["next"].setPos(width / 2, height)
        if "on_error" in self.output_ports:
            self.output_ports["on_error"].setPos(0, height / 2)
        if "interrupt" in self.output_ports:
            self.output_ports["interrupt"].setPos(width, height / 2)

    def itemChange(self, change, value):
        """Handle item change events"""
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            # The ports move with the node as they are children
            pass
        elif change == QGraphicsItem.ItemSelectedChange:
            # Can adjust selection effects here
            pass
        return super().itemChange(change, value)

    def get_input_port(self):
        return self.input_port

    def get_output_port(self, port_type="next"):
        """Get output port by type"""
        return self.output_ports.get(port_type)

    def get_output_ports(self):
        """Return all output ports as a dictionary"""
        return self.output_ports

    def set_task_node(self, task_node):
        """Set or update the TaskNode associated with this Node"""
        self.task_node = task_node
        original_height = self.bounds.height()

        # 更新ID
        self._initialize_id()

        # 检查template属性
        self._check_template()

        self._load_images()  # 重新加载图像
        self.resize_to_content()  # Adjust size to fit content
        self.update()  # Force redraw

        # Emit signals for properties that changed (for compatibility)
        if task_node and hasattr(task_node, 'to_dict'):
            for key, value in task_node.to_dict().items():
                self.signals.propertyChanged.emit(self.id, key, value)
        self.bounds.setHeight(max(original_height, self.bounds.height()))
        self._update_port_positions()
        self._update_connections()
        self.update()

    def get_task_node(self):
        """Return the TaskNode object"""
        return self.task_node

    def toggle_collapse(self):
        """Toggle between collapsed (header only) and expanded state"""
        self.collapsed = not self.collapsed

        if self.collapsed:
            self.original_height = self.bounds.height()
            self.bounds.setHeight(self.header_height)
        else:
            self.bounds.setHeight(self.original_height)

        # Update port positions
        self._update_port_positions()

        # Update connections
        self._update_connections()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if 0 <= event.pos().x() <= self.bounds.width() and 0 <= event.pos().y() <= self.header_height:
                # If user clicks on the header, handle double-click for collapse
                if event.type() == event.GraphicsSceneMouseDoubleClick:
                    self.toggle_collapse()
                    event.accept()
                    return
        super().mousePressEvent(event)

    def resize_to_content(self):
        """Resize the node to fit content"""
        min_height = self.header_height + 10  # Header plus padding

        # 针对有无template属性的情况进行不同的大小调整策略
        if self.has_template:
            # 如果有template属性，留出更多空间显示图像
            img_size = min(self.bounds.width() - 30, 160)  # 最大图像大小
            content_height = self.content_start + img_size + 20  # 图像加一些内边距
        else:
            # 如果没有template属性，则需要更多的空间来显示属性
            property_count = len(self._get_properties_to_display())
            properties_height = property_count * 30 + 20  # 每个属性行加内边距
            content_height = self.content_start + properties_height

        new_height = max(min_height, content_height)

        # Update bounds
        if not self.collapsed:
            self.bounds.setHeight(new_height)
            self.original_height = new_height

            # Update port positions
            self._update_port_positions()

            # Update connections
            self._update_connections()
            self.update()

    def resize(self, width, height):
        """Manually resize the node"""
        if not self.collapsed:
            self.bounds.setWidth(max(100, width))  # Minimum width of 100
            self.bounds.setHeight(max(self.header_height + 10, height))  # Minimum height
            self.original_height = self.bounds.height()

            # Update port positions
            self._update_port_positions()

            # Update connections
            self._update_connections()
            self.update()

    def get_center_pos(self):
        """Get the center position of the node in its local coordinates"""
        return QPointF(self.bounds.width() / 2, self.bounds.height() / 2)

    def get_scene_center_pos(self):
        """Get the center position of the node in scene coordinates"""
        return self.mapToScene(self.get_center_pos())