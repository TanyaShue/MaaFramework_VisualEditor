from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QFont
from PySide6.QtWidgets import QGraphicsItem


class Port(QGraphicsItem):
    def __init__(self, parent_node, position, direction, parent=None):
        super().__init__(parent)
        self.parent_node = parent_node
        self.position = position
        self.direction = direction  # 'top', 'right', 'bottom', 'left'
        self.connections = []

        # 你可以根据需要修改这两个尺寸
        self.port_width = 50  # 横向时的"宽度"
        self.port_height = 20  # 横向时的"高度"

        # 端口的文本标签
        self.label = ""

        # Port 可以被选中
        self.setFlag(QGraphicsItem.ItemIsSelectable)

        # 将端口放置到相对于父节点的坐标
        self.setPos(position)

    def paint(self, painter, option, widget):
        # 开启抗锯齿
        painter.setRenderHint(QPainter.Antialiasing)
        painter.save()

        # 创建一个圆角矩形路径
        path = QPainterPath()

        # ----------------------------
        # 关键：根据 direction 来判断形状
        # top/bottom -> 横向胶囊（宽 > 高）
        # left/right -> 纵向胶囊（高 > 宽）
        # ----------------------------
        if self.direction in ['top', 'bottom']:
            # 横向胶囊
            path.addRoundedRect(
                -self.port_width / 2,
                -self.port_height / 2,
                self.port_width,
                self.port_height,
                self.port_height / 2,
                self.port_height / 2
            )
        else:
            # 纵向胶囊
            path.addRoundedRect(
                -self.port_height / 2,
                -self.port_width / 2,
                self.port_height,
                self.port_width,
                self.port_height / 2,
                self.port_height / 2
            )

        # 设置画笔和画刷
        painter.setPen(QPen(Qt.black, 1))
        painter.setBrush(QBrush(self.get_port_color()))

        # 绘制路径
        painter.drawPath(path)

        # 设置字体和颜色绘制文本
        font = QFont()
        font.setPointSize(7)  # 可根据需要调整字体大小
        painter.setFont(font)
        painter.setPen(QPen(Qt.black))

        # 根据方向调整文本位置
        if self.direction in ['top', 'bottom']:
            # 横向胶囊，文本居中
            text_width = painter.fontMetrics().horizontalAdvance(self.label)
            text_height = painter.fontMetrics().height()
            painter.drawText(
                -text_width / 2,
                text_height / 4,  # 微调文本垂直位置
                self.label
            )
        else:
            # 纵向胶囊，文本垂直显示
            painter.rotate(90)  # 旋转文本
            text_width = painter.fontMetrics().horizontalAdvance(self.label)
            text_height = painter.fontMetrics().height()
            painter.drawText(
                -text_width / 2,
                text_height / 4,
                self.label
            )

        painter.restore()

    def boundingRect(self):
        """
        与 paint() 中的路径大小保持一致，用于碰撞检测、鼠标交互等。
        """
        if self.direction in ['top', 'bottom']:
            # 横向胶囊区域
            return QRectF(
                -self.port_width / 2,
                -self.port_height / 2,
                self.port_width,
                self.port_height
            )
        else:
            # 纵向胶囊区域
            return QRectF(
                -self.port_height / 2,
                -self.port_width / 2,
                self.port_height,
                self.port_width
            )

    def get_port_color(self):
        # 基础颜色，可被子类覆盖
        return QColor(200, 200, 200)

    def get_position(self):
        return self.position

    def can_connect(self, other_port):
        # 默认逻辑，子类中重写
        return False

    def connect(self, connection):
        if connection not in self.connections:
            self.connections.append(connection)

    def disconnect(self, connection):
        if connection in self.connections:
            self.connections.remove(connection)


class InputPort(Port):
    def __init__(self, parent_node, position, parent=None):
        # 这里默认设置成 'top'
        super().__init__(parent_node, position, 'top', parent)
        # 设置输入端口的文本标签
        self.label = "输入"

    def get_port_color(self):
        # 蓝色表示输入端口
        return QColor(100, 180, 255)

    def is_connected(self):
        return len(self.connections) > 0

    def get_connections(self):
        # 返回所有连接的输出端口
        return self.connections

    def can_connect(self, other_port):
        # 修改为允许多个输出端口连接，只要是 OutputPort 就可以连接
        return isinstance(other_port, OutputPort)


class OutputPort(Port):
    def __init__(self, parent_node, position, port_type, parent=None):
        self.port_type = port_type  # 'next', 'on_error', or 'interrupt'
        direction = {
            'next': 'bottom',
            'on_error': 'left',
            'interrupt': 'right'
        }.get(port_type, 'bottom')
        super().__init__(parent_node, position, direction, parent)
        # 设置输出端口的文本标签为端口类型
        self.label = port_type

    def get_port_color(self):
        # 根据不同类型设置不同颜色
        if self.port_type == 'next':
            return QColor(100, 220, 100)  # 绿色
        elif self.port_type == 'on_error':
            return QColor(220, 100, 100)  # 红色
        elif self.port_type == 'interrupt':
            return QColor(220, 180, 100)  # 橙黄色
        return QColor(200, 200, 200)

    def get_connections(self):
        return self.connections

    def can_connect(self, other_port):
        # 修改：允许连接到任何 InputPort，无论其是否已有连接
        return isinstance(other_port, InputPort)