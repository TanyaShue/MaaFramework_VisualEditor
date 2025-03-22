from PySide6.QtCore import QRectF, Qt, QPointF, Signal, QObject
from PySide6.QtGui import QPainter, QFont, QColor, QPen, QBrush, QPainterPath, QPixmap
from PySide6.QtWidgets import QGraphicsItem

from src.node_system.port import InputPort, OutputPort


# Signals need to be in a QObject, so we create a helper class
class NodeSignals(QObject):
    propertyChanged = Signal(str, str, object)  # node_id, property_name, new_value


class Node(QGraphicsItem):
    def __init__(self, id, title, task_node=None, parent=None, default_image_path="default_image.png"):
        super().__init__(parent)
        self.id = id
        self.title = title
        self.task_node = task_node  # Store TaskNode object instead of properties dict
        self.bounds = QRectF(0, 0, 240, 200)  # Make slightly taller for image
        self.header_height = 30
        self.content_start = self.header_height + 10
        self.signals = NodeSignals()

        # Image display settings
        self.image_height = 80  # Height for the image display area
        self.default_image_path = default_image_path
        self.default_image = None
        self.recognition_image = None  # Will hold the image to recognize
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
        """Load the default image and recognition image"""
        # Load default image
        try:
            self.default_image = QPixmap(self.default_image_path)
            if self.default_image.isNull():
                # Create a simple default image if file can't be loaded
                self.default_image = QPixmap(self.image_height, self.image_height)
                self.default_image.fill(QColor(200, 200, 200))
        except:
            # Create a simple default image if file can't be loaded
            self.default_image = QPixmap(self.image_height, self.image_height)
            self.default_image.fill(QColor(200, 200, 200))

        # Load recognition image if task_node is provided
        if self.task_node:
            self._load_recognition_image()
        else:
            self.recognition_image = self.default_image

    def _load_recognition_image(self):
        """Load the recognition image from the task_node"""
        image_path = None

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
            try:
                self.recognition_image = QPixmap(image_path)
                if self.recognition_image.isNull():
                    self.recognition_image = self.default_image
            except:
                self.recognition_image = self.default_image
        else:
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

        # Define colors
        header_color = QColor(60, 120, 190)  # Blue header
        body_color = QColor(240, 240, 240)  # Light gray body
        border_color = QColor(30, 60, 90) if not self.isSelected() else QColor(255, 165,
                                                                               0)  # Dark blue border or orange when selected
        text_color = QColor(255, 255, 255)  # White text for header

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
        painter.drawText(
            QRectF(10, 0, self.bounds.width() - 20, self.header_height),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.title
        )

        # Draw ID with smaller font
        painter.setFont(QFont("Arial", 7))
        painter.drawText(
            QRectF(10, 0, self.bounds.width() - 20, self.header_height),
            Qt.AlignVCenter | Qt.AlignRight,
            f"ID: {self.id}"
        )

        # If not collapsed, draw content section
        if not self.collapsed:
            painter.setPen(QPen(QColor(100, 100, 100), 0.5))
            y_pos = self.header_height
            painter.drawLine(0, y_pos, self.bounds.width(), y_pos)

            # Draw the recognition image
            if self.recognition_image and not self.recognition_image.isNull():
                img_rect = QRectF(
                    (self.bounds.width() - self.image_height) / 2,  # Centered horizontally
                    self.content_start,
                    self.image_height,
                    self.image_height
                )
                painter.drawPixmap(img_rect.toRect(), self.recognition_image)

            # Draw TaskNode properties below the image
            if self.task_node:
                y_pos = self.content_start + self.image_height + 10
                painter.setPen(QColor(30, 30, 30))
                painter.setFont(QFont("Arial", 8))

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

                # Draw the properties
                for key, value in properties_to_display:
                    if y_pos + 15 > self.bounds.height():
                        # Don't render properties that would go outside the node
                        break

                    # Draw property text
                    property_text = f"{key}: {value}"
                    painter.drawText(
                        QRectF(10, y_pos, self.bounds.width() - 20, 15),
                        Qt.AlignVCenter | Qt.AlignLeft,
                        property_text
                    )
                    y_pos += 15

        # If selected, add a highlight effect
        if self.isSelected():
            highlight_rect = self.bounds.adjusted(-2, -2, 2, 2)
            painter.setPen(QPen(QColor(255, 165, 0), 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(highlight_rect, 7, 7)

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
        self._load_recognition_image()
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

        # Calculate needed height for image and properties
        property_count = len(self.task_node._algorithm_properties) + 3 if self.task_node else 0
        properties_height = property_count * 15 + 20  # Each property row plus padding

        content_height = self.content_start + self.image_height + properties_height
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