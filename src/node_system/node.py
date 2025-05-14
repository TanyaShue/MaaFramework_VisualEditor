import hashlib
import os
import math

from PySide6.QtCore import QRectF, Qt, QPointF
from PySide6.QtGui import QPainter, QFont, QColor, QPen, QBrush, QPainterPath, QPixmap
from PySide6.QtWidgets import QGraphicsItem

from src.config_manager import config_manager
from src.node_system.port import InputPort, OutputPort
from src.pipeline import TaskNode


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
        self.title = self._get_node_title(title)

        # Basic configuration
        self.image_dir = self._get_image_directory()
        self.default_image_path = default_image_path

        # Initialize dimensions
        self.header_height = 30
        self.content_start = self.header_height + 10
        self.image_height = 80

        # 使用固定高度初始化所有节点
        self.bounds = QRectF(0, 0, 240, self.FIXED_NODE_HEIGHT)

        # Configure item flags
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

        # Initialize ports
        self.input_port = None
        self.output_ports = {}

        # 加载图像和端口
        self._load_images()
        self._initialize_ports()

        # Initialize collapse state
        self.collapsed = False
        self.original_height = self.FIXED_NODE_HEIGHT

    def _get_node_title(self, default_title=""):
        """Get node title from task_node.name if available, otherwise use default_title"""
        if self.task_node and hasattr(self.task_node, 'name') and self.task_node.name:
            return self.task_node.name
        elif default_title:
            return default_title
        return "Unknown Node"

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
            # 使用列表存储图片
            self.recognition_images = [Node._unknown_image]
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

        # 初始化为包含默认图片的列表
        self.recognition_images = [self.default_image]

        # Try to load specific recognition images if this is a recognition node
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
        """Load recognition images from task_node"""
        if not hasattr(self.task_node, 'template'):
            return

        template = self.task_node.template
        image_paths = []

        # 收集所有图片路径
        if isinstance(template, list):
            image_paths = template
        elif isinstance(template, str):
            image_paths = [template]

        # If no paths found, return
        if not image_paths:
            return

        # Get base path
        base_path = config_manager.config.get("recent_files", {}).get("base_resource_path", "")
        if not base_path:
            return

        # 加载所有图片
        self.recognition_images = []
        for image_path in image_paths:
            full_path = os.path.join(base_path, "image", image_path)
            try:
                pixmap = QPixmap(full_path)
                if not pixmap.isNull():
                    self.recognition_images.append(pixmap)
            except:
                pass

        # 如果没有成功加载任何图片，使用默认图片
        if not self.recognition_images:
            self.recognition_images = [self.default_image]

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
        """Paint recognition node content - show all images"""
        # Skip if no images
        if not self.recognition_images or not any(not img.isNull() for img in self.recognition_images):
            # Show placeholder text if no images are available
            painter.setPen(colors['property_title'])
            painter.setFont(QFont("Arial", 9))
            painter.drawText(
                QRectF(10, self.content_start + 10, self.bounds.width() - 20, 30),
                Qt.AlignCenter,
                "No Template Images"
            )
            return

        # Filter out null images
        valid_images = [img for img in self.recognition_images if not img.isNull()]
        img_count = len(valid_images)

        if img_count == 0:
            return

        # Calculate available space
        available_width = self.bounds.width() - 20
        available_height = self.bounds.height() - self.content_start - 15

        # Determine grid layout based on number of images
        if img_count == 1:
            cols, rows = 1, 1
        elif img_count == 2:
            cols, rows = 2, 1
        elif img_count <= 4:
            cols, rows = 2, 2
        elif img_count <= 6:
            cols, rows = 3, 2
        elif img_count <= 9:
            cols, rows = 3, 3
        else:
            cols = int(math.ceil(math.sqrt(img_count)))
            rows = int(math.ceil(img_count / cols))

        # Calculate image size with padding
        padding = 5
        img_width = (available_width - (cols - 1) * padding) / cols
        img_height = (available_height - (rows - 1) * padding) / rows
        img_size = min(img_width, img_height)

        # Calculate starting position to center the grid
        total_width = cols * img_size + (cols - 1) * padding
        total_height = rows * img_size + (rows - 1) * padding
        start_x = (self.bounds.width() - total_width) / 2
        start_y = self.content_start + (available_height - total_height) / 2

        # Draw each image
        for idx, img in enumerate(valid_images):
            row = idx // cols
            col = idx % cols

            x = start_x + col * (img_size + padding)
            y = start_y + row * (img_size + padding)

            img_rect = QRectF(x, y, img_size, img_size)

            # Draw border around image
            painter.setPen(QPen(QColor(180, 180, 180), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(img_rect)

            # Draw image
            painter.drawPixmap(img_rect.toRect(), img)

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

    def _safe_call_method(self, obj, method_names, *args, **kwargs):
        """安全地调用对象的方法，尝试多个可能的方法名"""
        if not obj:
            return None

        # 如果提供了一个方法名称字符串，转换为列表
        if isinstance(method_names, str):
            method_names = [method_names]

        # 尝试每个方法名
        for name in method_names:
            if hasattr(obj, name):
                method = getattr(obj, name)
                if callable(method):
                    try:
                        return method(*args, **kwargs)
                    except Exception:
                        pass  # 如果失败，尝试下一个方法

        return None  # 如果所有方法都失败了，返回 None

    def _update_connections(self):
        """Update all connections to this node"""
        # Update input connection
        if self.input_port and hasattr(self.input_port, 'is_connected') and self.input_port.is_connected():
            for connection in self.input_port.get_connections():
                if connection:
                    # 安全地调用更新路径方法
                    self._safe_call_method(connection, ['update_path', 'updatePath', 'update'])

        # Update output connections
        for port in self.output_ports.values():
            for connection in port.get_connections():
                if connection:
                    # 安全地调用更新路径方法
                    self._safe_call_method(connection, ['update_path', 'updatePath', 'update'])

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

    def _remove_existing_ports(self):
        """移除所有现有端口，包括从场景中删除它们"""
        scene = self.scene()

        # 处理输入端口
        if self.input_port:
            # 获取所有连接
            connections = []
            try:
                if hasattr(self.input_port, 'get_connections'):
                    connections = list(self.input_port.get_connections())
                elif hasattr(self.input_port, 'connections'):
                    connections = list(self.input_port.connections)
            except Exception:
                # 忽略任何错误，避免中断流程
                pass

            # 断开连接
            for connection in connections:
                try:
                    # 尝试多种可能的方法名称获取源端口
                    source_port = self._safe_call_method(
                        connection,
                        ['get_source_port', 'source', 'getSource', 'sourcePort', 'from_port', 'fromPort']
                    )

                    # 尝试断开连接
                    if source_port:
                        self._safe_call_method(
                            source_port,
                            ['disconnect', 'remove_connection', 'removeConnection'],
                            connection
                        )

                    # 移除连接
                    if scene and connection.scene() == scene:
                        try:
                            scene.removeItem(connection)
                        except Exception:
                            pass
                except Exception:
                    # 忽略错误，继续处理下一个连接
                    pass

            # 从场景中移除端口
            try:
                if scene and self.input_port.scene() == scene:
                    scene.removeItem(self.input_port)
            except Exception:
                pass

            self.input_port = None

        # 处理输出端口
        for port_type, port in list(self.output_ports.items()):
            # 获取所有连接
            connections = []
            try:
                if hasattr(port, 'get_connections'):
                    connections = list(port.get_connections())
                elif hasattr(port, 'connections'):
                    connections = list(port.connections)
            except Exception:
                # 忽略任何错误，避免中断流程
                pass

            # 断开连接
            for connection in connections:
                try:
                    # 尝试多种可能的方法名称获取目标端口
                    target_port = self._safe_call_method(
                        connection,
                        ['get_target_port', 'target', 'getTarget', 'targetPort', 'to_port', 'toPort']
                    )

                    # 尝试断开连接
                    if target_port:
                        # 尝试可能的断开连接方法
                        self._safe_call_method(
                            target_port,
                            ['disconnect', 'remove_connection', 'removeConnection', 'set_connection'],
                            connection if not 'set_connection' in dir(target_port) else None
                        )

                    # 移除连接
                    if scene and connection.scene() == scene:
                        try:
                            scene.removeItem(connection)
                        except Exception:
                            pass
                except Exception:
                    # 忽略错误，继续处理下一个连接
                    pass

            # 从场景中移除端口
            try:
                if scene and port.scene() == scene:
                    scene.removeItem(port)
            except Exception:
                pass

        # 清空端口字典
        self.output_ports = {}

    def set_task_node(self, task_node):
        """Set or update the task node"""
        self.task_node = task_node
        # 更新节点状态
        self.refresh_ui()

    def refresh_ui(self):
        """根据当前task_node刷新UI"""
        if not self.task_node:
            return

        # 保存当前节点的坐标和选择状态
        current_pos = self.pos()
        was_selected = self.isSelected()

        # 确定新的节点类型和标题
        old_type = self.node_type
        self.node_type = self._determine_node_type()
        self.title = self._get_node_title(self.title)

        # 如果节点类型改变，需要重新创建端口
        if old_type != self.node_type:
            # 先尝试安全地移除现有端口
            try:
                self._remove_existing_ports()
            except Exception as e:
                print(f"移除端口时出错: {e}")
                # 如果出错，继续执行，确保能够创建新端口

            # 初始化新端口
            self._initialize_ports()

        # 重新加载图像
        self._load_images()

        # 调整高度（保持固定高度或折叠状态）
        if not self.collapsed:
            self.bounds.setHeight(self.FIXED_NODE_HEIGHT)

        # 更新端口位置和连接
        self._update_port_positions()

        # 安全地更新连接
        try:
            self._update_connections()
        except Exception as e:
            print(f"更新连接时出错: {e}")

        # 恢复位置和选择状态
        self.setPos(current_pos)
        self.setSelected(was_selected)

        # 更新视图
        self.update()

    def toggle_collapse(self):
        """Toggle collapsed state"""
        self.collapsed = not self.collapsed

        if self.collapsed:
            self.bounds.setHeight(self.header_height)
        else:
            self.bounds.setHeight(self.FIXED_NODE_HEIGHT)  # 使用固定高度

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
        # 忽略传入的高度参数，总是使用固定高度
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