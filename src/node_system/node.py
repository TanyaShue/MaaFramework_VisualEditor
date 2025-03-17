from PySide6.QtCore import QRectF, Qt, QPointF, Signal, QObject
from PySide6.QtGui import QPainter, QFont, QColor, QPen, QBrush, QPainterPath
from PySide6.QtWidgets import QGraphicsItem

from src.node_system.port import InputPort, OutputPort


# Signals need to be in a QObject, so we create a helper class
class NodeSignals(QObject):
    propertyChanged = Signal(str, str, object)  # node_id, property_name, new_value


class Node(QGraphicsItem):
    def __init__(self, id, title, parent=None):
        super().__init__(parent)
        self.id = id
        self.title = title
        self.bounds = QRectF(0, 0, 240, 160)
        self.properties = {}
        self.header_height = 30
        self.content_start = self.header_height + 10
        self.signals = NodeSignals()

        # Node can be selected and moved
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

        # Initialize ports
        self._initialize_ports()

        # Create a collapsed state
        self.collapsed = False
        self.original_height = self.bounds.height()

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

        # If not collapsed, draw properties section
        if not self.collapsed:
            painter.setPen(QPen(QColor(100, 100, 100), 0.5))
            y_pos = self.header_height
            painter.drawLine(0, y_pos, self.bounds.width(), y_pos)

            # Draw properties
            y_pos = self.content_start
            painter.setPen(QColor(30, 30, 30))
            painter.setFont(QFont("Arial", 8))

            for i, (key, value) in enumerate(self.properties.items()):
                if y_pos + 15 > self.bounds.height():
                    # Don't render properties that would go outside the node
                    break

                # Draw property key
                property_text = f"{key}: {value}"
                painter.drawText(
                    QRectF(10, y_pos, self.bounds.width() - 20, 15),
                    Qt.AlignVCenter | Qt.AlignLeft,
                    property_text
                )
                y_pos += 15

        # If selected, add an effect
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

    def update_properties(self, props):
        # Update properties and emit signals
        for key, value in props.items():
            old_value = self.properties.get(key)
            if old_value != value:
                self.properties[key] = value
                self.signals.propertyChanged.emit(self.id, key, value)
        self.update()  # Force redraw

    def add_property(self, key, value):
        self.properties[key] = value
        self.signals.propertyChanged.emit(self.id, key, value)
        self.update()  # Force redraw

    def remove_property(self, key):
        if key in self.properties:
            del self.properties[key]
            self.signals.propertyChanged.emit(self.id, key, None)
            self.update()  # Force redraw

    def get_property(self, key, default=None):
        return self.properties.get(key, default)

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
        """Resize the node to fit all properties"""
        properties_count = len(self.properties)
        min_height = self.header_height + 10  # Header plus padding

        # Calculate needed height
        properties_height = properties_count * 15 + 20  # Each property row plus padding
        new_height = max(min_height, properties_height + self.header_height)

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