import os

from PySide6.QtCore import QRectF, Qt, QPointF, Signal, QObject
from PySide6.QtGui import QPainter, QFont, QColor, QPen, QBrush, QPainterPath, QPixmap
from PySide6.QtWidgets import QGraphicsItem
import hashlib  # 用于MD5哈希计算

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
        # 根据task_node.name计算MD5作为ID - 不再使用传入的id参数，总是计算一个新的
        if self.task_node and hasattr(self.task_node, 'name'):
            self.id = hashlib.md5(self.task_node.name.encode()).hexdigest()[:6].upper()
        else:
            # 仅在task_node不存在或没有name属性时使用传入的id或设置为"UNKNOWN"
            self.id = id if id else "UNKNOWN"

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
        if self.task_node and hasattr(self.task_node, 'template') and self.task_node.template:
            self.has_template = True

        self._load_images()  # Load images

        # Node can be selected and moved
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

        # Initialize ports
        self._initialize_ports()

        # Create a collapsed state
        self.collapsed = False
        self.original_height = self.bounds.height()

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
        if self.task_node and hasattr(self.task_node, 'template') and self.task_node.template:
            self.has_template = True
            # 如果有template属性，加载对应的图像
            self._load_recognition_image()
        else:
            self.has_template = False

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

        # 如果从template没有获取到路径，按照原来的逻辑尝试其他属性
        if not image_path:
            # Try different possible ways the image path might be stored
            if hasattr(self.task_node, 'recognition') and isinstance(self.task_node.recognition, str):
                # If recognition itself is a path or contains path information
                image_path = self.task_node.recognition

            # Check if there's an image_path in algorithm properties
            elif hasattr(self.task_node, 'get_algorithm_property'):
                possible_keys = ['image_path', 'imagePath', 'image', 'recognition_image']
                for key in possible_keys:
                    path = self.task_node.get_algorithm_property(key)
                    if path:
                        image_path = path
                        break

        # Try to load the image if a path was found
        if image_path:
            # Check if the path is relative and needs to be combined with image_dir
            if self.image_dir and not os.path.isabs(image_path):
                full_image_path = os.path.join(self.image_dir, image_path)
            else:
                full_image_path = image_path

            try:
                self.recognition_image = QPixmap(full_image_path)
                if self.recognition_image.isNull():
                    self.recognition_image = self.default_image
            except:
                self.recognition_image = self.default_image

    def _initialize_ports(self):
        # Calculate width and height for positioning
        width = self.bounds.width()
        height = self.bounds.height()

        # Create input port at the top center
        self.input_port = InputPort(
            self,
            QPointF(width / 2, 0),
            self
        )

        # Create output ports
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
        # Set rendering hints for smoother appearance
        painter.setRenderHint(QPainter.Antialiasing)

        # 增强的颜色方案，提高视觉效果
        header_color = QColor(60, 120, 190)  # 蓝色标题栏
        body_color = QColor(240, 240, 240)  # 浅灰色主体
        border_color = QColor(30, 60, 90) if not self.isSelected() else QColor(255, 165, 0)  # 深蓝色边框或橙色（选中时）
        text_color = QColor(255, 255, 255)  # 标题栏的白色文本
        shadow_color = QColor(50, 50, 50, 40)  # 半透明阴影

        # 添加阴影效果
        painter.save()
        shadow_rect = self.bounds.adjusted(4, 4, 4, 4)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(shadow_color))
        painter.drawRoundedRect(shadow_rect, 5, 5)
        painter.restore()

        # Draw the main body
        painter.setPen(QPen(border_color, 1.5))
        painter.setBrush(QBrush(body_color))

        # Draw rounded rectangle
        path = QPainterPath()
        path.addRoundedRect(self.bounds, 5, 5)
        painter.drawPath(path)

        # Draw header
        header_rect = QRectF(0, 0, self.bounds.width(), self.header_height)
        header_path = QPainterPath()
        header_path.addRoundedRect(header_rect, 5, 5)

        # Create a clip to make only the top corners rounded
        painter.save()
        painter.setClipPath(header_path)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(header_color))
        painter.drawRect(header_rect)
        painter.restore()

        # Draw the title
        painter.setPen(text_color)
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        title_width = self.bounds.width() - 70  # 预留ID徽章的空间
        painter.drawText(
            QRectF(10, 0, title_width, self.header_height),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.title
        )

        # 绘制ID，采用徽章样式增强显示效果
        id_text = f"{self.id}"  # 确保使用self.id而不是其他值
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

        # If not collapsed, draw content section
        if not self.collapsed:
            painter.setPen(QPen(QColor(100, 100, 100), 0.5))
            y_pos = self.header_height
            painter.drawLine(0, y_pos, self.bounds.width(), y_pos)

            # 根据是否有template属性选择不同的显示方式
            if self.has_template:
                # 有template属性，显示图像
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
            else:
                # 没有template属性，显示节点详情
                if self.task_node:
                    self._draw_properties(painter)

    def _draw_properties(self, painter):
        """单独的方法来绘制节点属性，仅在没有template属性时使用"""
        y_pos = self.content_start + 15

        # 修改属性显示的样式，使其更易读
        property_title_color = QColor(60, 60, 60)
        property_value_color = QColor(80, 80, 80)

        # Display key TaskNode properties
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
        # Update port positions based on current bounds
        width = self.bounds.width()
        height = self.bounds.height()

        # Update input port position
        self.input_port.setPos(width / 2, 0)

        # Update output port positions
        self.output_ports["next"].setPos(width / 2, height)
        self.output_ports["on_error"].setPos(0, height / 2)
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

        # 强制更新ID，总是使用task_node.name的MD5哈希值前6位
        if task_node and hasattr(task_node, 'name'):
            self.id = hashlib.md5(task_node.name.encode()).hexdigest()[:6].upper()
        else:
            self.id = "UNKNOWN"  # 如果无法计算MD5，使用"UNKNOWN"作为ID

        # 检查是否有template属性
        if task_node and hasattr(task_node, 'template') and task_node.template:
            self.has_template = True
        else:
            self.has_template = False

        self._load_images()  # 重新加载图像
        self.resize_to_content()  # Adjust size to fit content
        self.update()  # Force redraw

        # Emit signals for properties that changed (for compatibility)
        if task_node and hasattr(task_node, 'to_dict'):
            for key, value in task_node.to_dict().items():
                self.signals.propertyChanged.emit(self.id, key, value)

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
            property_count = 0
            if self.task_node:
                # 计算属性数量
                if hasattr(self.task_node, 'recognition'):
                    property_count += 1
                if hasattr(self.task_node, 'action'):
                    property_count += 1
                if hasattr(self.task_node, 'enabled'):
                    property_count += 1
                if hasattr(self.task_node, '_algorithm_properties'):
                    property_count += len([k for k, v in self.task_node._algorithm_properties.items()
                                           if isinstance(v, (str, int, float, bool))])

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