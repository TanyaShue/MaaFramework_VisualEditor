import hashlib
import os

from PySide6.QtCore import QRectF, Qt, QPointF
from PySide6.QtGui import QPainter, QFont, QColor, QPen, QBrush, QPainterPath, QPixmap
from PySide6.QtWidgets import QGraphicsItem

from src.config_manager import config_manager
from src.node_system.port import InputPort, OutputPort
from src.pipeline import TaskNode


# 在Node类中添加一个类变量作为所有节点的固定高度
class Node(QGraphicsItem):
    # Node type constants
    TYPE_GENERIC = 0
    TYPE_RECOGNITION = 1
    TYPE_UNKNOWN = 2

    # 添加固定高度常量
    FIXED_NODE_HEIGHT = 200  # 设置所有节点统一的高度值

    # Shared unknown image
    _unknown_image = None

    def __init__(self, title="Unknown Node", task_node=None, parent=None, default_image_path="default_image.png",
                 node_type=TYPE_UNKNOWN):
        super().__init__(parent)
        self.task_node = task_node
        self.node_type = node_type if node_type is not None else self._determine_node_type()

        # Set title based on task_node.name if available, otherwise use provided title
        self.title = title

        # Basic configuration
        self.image_dir = self._get_image_directory()
        self.default_image_path = default_image_path

        # Initialize dimensions
        self.header_height = 30
        self.content_start = self.header_height + 10
        self.image_height = 80

        # 修改：使用固定高度初始化所有节点
        self.bounds = QRectF(0, 0, 240, self.FIXED_NODE_HEIGHT)

        # Configure item flags
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

        self._load_images()
        # Initialize ports
        self.input_port = None
        self.output_ports = {}
        self._initialize_ports()

        # Initialize collapse state
        self.collapsed = False
        self.original_height = self.FIXED_NODE_HEIGHT  # 修改：使用固定高度

    def _get_node_title(self, default_title=""):
        """Get node title from task_node.name if available, otherwise use default_title"""
        if self.node_type == self.TYPE_UNKNOWN and self.title:
            return self.title
        elif self.task_node and hasattr(self.task_node, 'name') and self.task_node.name:
            return self.task_node.name
        return default_title

    def _get_image_directory(self):
        """Get image directory path"""
        if not config_manager:
            return None

        resource_dir = config_manager.config.get("recent_files", {}).get("resource_dir", "")
        if not resource_dir:
            return None

        base_dir = os.path.dirname(resource_dir)
        return os.path.join(base_dir, "image")

    def _determine_node_type(self):
        """Determine node type based on task_node properties"""
        if not self.task_node or (hasattr(self.task_node, '_node_type') and self.task_node._node_type == 'unknown'):
            return self.TYPE_UNKNOWN

        if hasattr(self.task_node, 'template') and self.task_node.template:
            return self.TYPE_RECOGNITION

        return self.TYPE_GENERIC

    def _load_images(self):
        """Load images based on node type, with graceful fallbacks"""
        # Handle unknown node type
        if self.node_type == self.TYPE_UNKNOWN:
            if Node._unknown_image is None:
                self._create_unknown_image()
            self.default_image = Node._unknown_image
            self.recognition_image = Node._unknown_image
            return

        # Try to load default image if path is available
        if self.default_image_path:
            default_image_path = self.default_image_path
            if self.image_dir and not os.path.isabs(default_image_path):
                default_image_path = os.path.join(self.image_dir, default_image_path)

            try:
                self.default_image = QPixmap(default_image_path)
                if self.default_image.isNull():
                    self._create_fallback_image()
            except:
                self._create_fallback_image()
        else:
            # No default image path provided
            self._create_fallback_image()

        # Set default image as recognition image initially (could be None)
        self.recognition_image = self.default_image

        # Try to load specific recognition image if this is a recognition node
        if self.node_type == self.TYPE_RECOGNITION:
            self._load_recognition_image()

    def _create_fallback_image(self):
        """Create a simple fallback image"""
        self.default_image = QPixmap(self.image_height, self.image_height)
        self.default_image.fill(QColor(200, 200, 200))

    def _create_unknown_image(self):
        """Create image for unknown node type"""
        # Create image only once for all instances
        Node._unknown_image = QPixmap(120, 120)
        Node._unknown_image.fill(Qt.transparent)

        painter = QPainter(Node._unknown_image)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(200, 200, 200, 160))
        painter.drawEllipse(10, 10, 100, 100)

        # Draw red X
        pen = QPen(QColor(220, 50, 50), 8)
        painter.setPen(pen)
        painter.drawLine(30, 30, 90, 90)
        painter.drawLine(90, 30, 30, 90)

        painter.end()

    def _load_recognition_image(self):
        """Load recognition image from task_node"""
        if not hasattr(self.task_node, 'template'):
            return

        template = self.task_node.template
        image_path = None

        # Handle template as list or string
        if isinstance(template, list) and len(template) > 0:
            image_path = template[0]
        elif isinstance(template, str):
            image_path = template

        # If no path found, return
        if not image_path:
            return

        # Get base path and construct full path
        base_path = config_manager.config.get("recent_files", {}).get("base_resource_path", "")
        if not base_path:
            return

        full_path = os.path.join(base_path, "image", image_path)

        try:
            self.recognition_image = QPixmap(full_path)
            if self.recognition_image.isNull():
                self.recognition_image = self.default_image
        except:
            self.recognition_image = self.default_image

    def _initialize_ports(self):
        """Initialize all ports"""
        # Create input port at top center
        width = self.bounds.width()
        self.input_port = InputPort(self, QPointF(width / 2, 0), self)

        # Create output ports (except for unknown nodes)
        if self.node_type != self.TYPE_UNKNOWN:
            height = self.bounds.height()

            # Standard output ports with positions
            port_configs = {
                "next": QPointF(width / 2, height),  # bottom center
                "on_error": QPointF(0, height / 2),  # left center
                "interrupt": QPointF(width, height / 2)  # right center
            }

            # Create output ports from configuration
            self.output_ports = {
                port_type: OutputPort(self, position, port_type, self)
                for port_type, position in port_configs.items()
            }

    def paint(self, painter, option, widget):
        """Paint the node"""
        painter.setRenderHint(QPainter.Antialiasing)

        # Get color scheme based on node type
        colors = self._get_node_colors()

        # Paint shadow
        shadow_rect = self.bounds.adjusted(4, 4, 4, 4)
        painter.setPen(Qt.NoPen)
        painter.setBrush(colors['shadow'])
        painter.drawRoundedRect(shadow_rect, 5, 5)

        # Paint body
        painter.setPen(QPen(colors['border'], 1.5))
        painter.setBrush(colors['body'])
        painter.drawRoundedRect(self.bounds, 5, 5)

        # Paint header
        header_rect = QRectF(0, 0, self.bounds.width(), self.header_height)
        painter.save()
        path = QPainterPath()
        path.addRoundedRect(header_rect, 5, 5)
        painter.setClipPath(path)
        painter.setPen(Qt.NoPen)
        painter.setBrush(colors['header'])
        painter.drawRect(header_rect)
        painter.restore()

        # Paint title text
        painter.setPen(colors['header_text'])
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        painter.drawText(
            QRectF(10, 0, self.bounds.width() - 10, self.header_height),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.title
        )

        # If not collapsed, paint content
        if not self.collapsed:
            # Paint separator line
            painter.setPen(QPen(colors['separator'], 0.5))
            painter.drawLine(0, self.header_height, self.bounds.width(), self.header_height)

            # Paint content based on node type
            if self.node_type == self.TYPE_RECOGNITION:
                self._paint_recognition_content(painter, colors)
            elif self.node_type == self.TYPE_UNKNOWN:
                self._paint_unknown_content(painter, colors)
            else:
                self._paint_properties(painter, colors)

    def _get_node_colors(self):
        """Get color scheme based on node type"""
        # Base colors that are common
        base_colors = {
            'shadow': QColor(50, 50, 50, 40),
            'header_text': QColor(255, 255, 255),
            'border': QColor(255, 165, 0) if self.isSelected() else None,
        }

        # Colors specific to node type
        if self.node_type == self.TYPE_RECOGNITION:
            colors = {
                'header': QColor(60, 150, 60),
                'body': QColor(240, 248, 240),
                'border': QColor(255, 165, 0) if self.isSelected() else QColor(30, 90, 30),
                'property_title': QColor(60, 100, 60),
                'property_value': QColor(80, 120, 80),
                'separator': QColor(100, 160, 100)
            }
        elif self.node_type == self.TYPE_UNKNOWN:
            colors = {
                'header': QColor(180, 40, 40),
                'body': QColor(240, 220, 220),
                'border': QColor(255, 165, 0) if self.isSelected() else QColor(140, 30, 30),
                'property_title': QColor(150, 30, 30),
                'property_value': QColor(100, 30, 30),
                'separator': QColor(130, 50, 50)
            }
        else:  # Generic node
            colors = {
                'header': QColor(60, 120, 190),
                'body': QColor(240, 245, 250),
                'border': QColor(255, 165, 0) if self.isSelected() else QColor(30, 60, 90),
                'property_title': QColor(60, 60, 90),
                'property_value': QColor(80, 80, 110),
                'separator': QColor(100, 120, 160)
            }

        # Add common colors (except border which we already set specifically)
        for key, value in base_colors.items():
            if key != 'border':  # Don't override border
                colors[key] = value

        return colors

    def _paint_recognition_content(self, painter, colors):
        """Paint recognition node content - show only the image"""
        # Skip if no image or null image
        if not self.recognition_image or self.recognition_image.isNull():
            # Show placeholder text if no image is available
            painter.setPen(colors['property_title'])
            painter.setFont(QFont("Arial", 9))
            painter.drawText(
                QRectF(10, self.content_start + 10, self.bounds.width() - 20, 30),
                Qt.AlignCenter,
                "No Template Image"
            )
            return

        # Calculate image size and position - make it larger for recognition nodes
        # Use more space since we don't need to show properties
        img_size = min(self.bounds.width() - 20, self.bounds.height() - self.content_start - 15)
        img_rect = QRectF(
            (self.bounds.width() - img_size) / 2,
            self.content_start + 5,
            img_size,
            img_size
        )

        # Draw border around image
        painter.setPen(QPen(QColor(180, 180, 180), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(img_rect)

        # Draw image
        painter.drawPixmap(img_rect.toRect(), self.recognition_image)

    def _paint_unknown_content(self, painter, colors):
        """Paint unknown node content"""
        if self._unknown_image and not self._unknown_image.isNull():
            # Draw warning text
            painter.setPen(colors['property_title'])
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.drawText(
                QRectF(10, self.content_start - 5, self.bounds.width() - 20, 20),
                Qt.AlignCenter,
                "未知节点类型"
            )

            # Calculate and draw image
            img_size = min(self.bounds.width() - 30, self.bounds.height() - self.content_start - 40)
            img_rect = QRectF(
                (self.bounds.width() - img_size) / 2,
                self.content_start + 20,
                img_size,
                img_size
            )

            # Draw dashed border
            painter.setPen(QPen(colors['property_title'], 1, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(img_rect)

            # Draw image
            painter.drawPixmap(img_rect.toRect(), self._unknown_image)

    def _paint_properties(self, painter, colors):
        """Paint node properties with emphasis on node type"""
        if not self.task_node:
            return

        y_pos = self.content_start + 5
        properties = self._get_properties_to_display()

        for key, value in properties:
            if y_pos + 25 > self.bounds.height():
                break

            self._draw_property(
                painter,
                key,
                value,
                y_pos,
                colors['property_title'],
                colors['property_value']
            )
            y_pos += 25

    def _draw_property(self, painter, key, value, y_pos, title_color, value_color):
        """Draw a single property (key-value pair)"""
        # Draw property key (bold)
        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.setPen(title_color)
        property_key = f"{key}:"
        painter.drawText(
            QRectF(10, y_pos, self.bounds.width() - 20, 12),
            Qt.AlignLeft,
            property_key
        )

        # Draw property value (regular font)
        painter.setFont(QFont("Arial", 8))
        painter.setPen(value_color)

        # Handle long values with ellipsis
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

    def _get_properties_to_display(self):
        """Get list of properties to display"""
        properties = []

        # Add basic properties
        basic_attrs = [
            ('recognition', "Recognition"),
            ('action', "Action"),
            ('enabled', "Enabled")
        ]

        for attr, label in basic_attrs:
            if hasattr(self.task_node, attr):
                value = getattr(self.task_node, attr)
                properties.append((label, str(value)))

        # Add algorithm properties
        if hasattr(self.task_node, '_algorithm_properties'):
            properties.extend(
                (key, str(value))
                for key, value in self.task_node._algorithm_properties.items()
                if isinstance(value, (str, int, float, bool))
            )

        return properties

    def boundingRect(self):
        """Return the bounding rectangle"""
        return self.bounds

    def set_position(self, x, y):
        """Set node position and update connections"""
        self.setPos(x, y)
        self._update_connections()

    def _update_connections(self):
        """Update all connections to this node"""
        # Update input connection
        if self.input_port and self.input_port.is_connected():
            connection = self.input_port.get_connection()
            if connection:
                connection.update_path()

        # Update output connections
        for port in self.output_ports.values():
            for connection in port.get_connections():
                if connection:
                    connection.update_path()

    def _update_port_positions(self):
        """Update positions of all ports"""
        width = self.bounds.width()
        height = self.bounds.height()

        # Update input port position
        if self.input_port:
            self.input_port.setPos(width / 2, 0)

        # Update output port positions
        if self.node_type != self.TYPE_UNKNOWN:
            port_positions = {
                "next": QPointF(width / 2, height),
                "on_error": QPointF(0, height / 2),
                "interrupt": QPointF(width, height / 2)
            }

            for port_type, position in port_positions.items():
                if port_type in self.output_ports:
                    self.output_ports[port_type].setPos(position)

    def get_input_port(self):
        """Get the input port"""
        return self.input_port

    def get_output_port(self, port_type="next"):
        """Get output port by type"""
        if self.node_type == self.TYPE_UNKNOWN:
            return None
        return self.output_ports.get(port_type)

    def get_output_ports(self):
        """Get all output ports"""
        if self.node_type == self.TYPE_UNKNOWN:
            return {}
        return self.output_ports

    def set_task_node(self, task_node):
        """Set or update the task node"""
        self.task_node = task_node

        # Determine new node type
        old_type = self.node_type
        self.node_type = self._determine_node_type()

        # Update node title based on task_node
        self.title = self._get_node_title(self.title)

        # 关键修复：无论节点类型是否改变，都正确清理旧端口
        self._remove_existing_ports()

        # 初始化新端口
        self._initialize_ports()

        # Reload images
        self._load_images()

        # 保持固定高度
        if not self.collapsed:
            self.bounds.setHeight(self.FIXED_NODE_HEIGHT)

        self._update_port_positions()
        self._update_connections()
        self.update()

    def _remove_existing_ports(self):
        """移除所有现有端口，包括从场景中删除它们"""
        # 处理输入端口
        if self.input_port:
            # 断开所有连接
            if self.input_port.is_connected():
                connection = self.input_port.get_connection()
                if connection:
                    # 从源端口移除连接
                    source_port = connection.get_source_port()
                    if source_port:
                        source_port.remove_connection(connection)
                    # 从场景中移除连接
                    scene = self.scene()
                    if scene and connection.scene() == scene:
                        scene.removeItem(connection)

            # 从场景中移除端口
            scene = self.scene()
            if scene and self.input_port.scene() == scene:
                scene.removeItem(self.input_port)

            # 清空引用
            self.input_port = None

        # 处理输出端口
        for port_type, port in list(self.output_ports.items()):
            # 断开所有连接
            connections = port.get_connections()
            for connection in list(connections):
                # 从目标端口移除连接
                target_port = connection.get_target_port()
                if target_port:
                    target_port.set_connection(None)

                # 从场景中移除连接
                scene = self.scene()
                if scene and connection.scene() == scene:
                    scene.removeItem(connection)

            # 从场景中移除端口
            scene = self.scene()
            if scene and port.scene() == scene:
                scene.removeItem(port)

        # 清空引用
        self.output_ports = {}

    def toggle_collapse(self):
        """Toggle collapsed state"""
        self.collapsed = not self.collapsed

        if self.collapsed:
            self.bounds.setHeight(self.header_height)
        else:
            self.bounds.setHeight(self.FIXED_NODE_HEIGHT)  # 修改：使用固定高度

        self._update_port_positions()
        self._update_connections()
        self.update()

    def mousePressEvent(self, event):
        """Handle mouse press events"""
        if (event.button() == Qt.LeftButton and
                0 <= event.pos().x() <= self.bounds.width() and
                0 <= event.pos().y() <= self.header_height and
                event.type() == event.GraphicsSceneMouseDoubleClick):
            self.toggle_collapse()
            event.accept()
            return

        super().mousePressEvent(event)

    def resize_to_content(self):
        """
        修改后的resize_to_content方法，保持固定高度
        只调整宽度（如果需要）
        """
        if self.collapsed:
            return

        # 保持高度固定，只处理宽度（如果需要）
        # 此处可以添加宽度调整逻辑，但高度保持不变

        # 更新端口和连接
        self._update_port_positions()
        self._update_connections()
        self.update()

    def resize(self, width, height):
        """Manually resize the node"""
        if self.collapsed:
            return

        self.bounds.setWidth(max(100, width))
        # 修改：忽略传入的高度参数，总是使用固定高度
        self.bounds.setHeight(self.FIXED_NODE_HEIGHT)

        self._update_port_positions()
        self._update_connections()
        self.update()

    def get_center_pos(self):
        """Get center position in local coordinates"""
        return QPointF(self.bounds.width() / 2, self.bounds.height() / 2)

    def get_scene_center_pos(self):
        """Get center position in scene coordinates"""
        return self.mapToScene(self.get_center_pos())
