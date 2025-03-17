from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QPainterPath, QColor, QPainterPathStroker, QBrush
from PySide6.QtWidgets import QGraphicsItem

from src.node_system.port import OutputPort


class Connection(QGraphicsItem):
    def __init__(self, start_port, end_port, scene):
        super().__init__()
        self.start_port = start_port
        self.end_port = end_port
        self.scene = scene

        # 允许选择，且层级低于节点
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setZValue(-1)

        # 初始化绘制路径
        self.path = QPainterPath()

        # 连接端口（端口内部可记录已连接的 Connection 对象）
        self.start_port.connect(self)
        self.end_port.connect(self)

        # 使用统一逻辑生成连线路径
        self.update_path()

        # 添加到场景中
        if self.scene:
            self.scene.addItem(self)

    def get_source(self):
        return self.start_port

    def get_target(self):
        return self.end_port

    def update_path(self):
        self.prepareGeometryChange()
        # 调用 ConnectionManager 提供的静态方法生成连线路径
        self.path = ConnectionManager.build_connection_path(self.start_port, self.end_port, self.scene)
        self.update()

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)

        # 根据输出端口类型确定颜色
        if isinstance(self.start_port, OutputPort):
            port_type = self.start_port.port_type
            if port_type == 'next':
                color = QColor(100, 220, 100)
            elif port_type == 'on_error':
                color = QColor(220, 100, 100)
            elif port_type == 'interrupt':
                color = QColor(220, 180, 100)
            else:
                color = QColor(100, 100, 100)
        else:
            color = QColor(100, 100, 100)

        pen_width = 2.5 if self.isSelected() else 2
        pen = QPen(color, pen_width, Qt.SolidLine)
        painter.setPen(pen)

        # 绘制连线路径
        painter.drawPath(self.path)
        # 绘制方向箭头
        self.draw_arrow(painter, color)

    def draw_arrow(self, painter, color):
        # 获取路径中点用于绘制箭头
        path_length = self.path.length()
        if path_length <= 0:
            return

        mid_percent = 0.5
        pos_mid = self.path.pointAtPercent(mid_percent)
        # 取中点前一点用于计算方向
        pos_before_mid = self.path.pointAtPercent(mid_percent - 0.02)
        dir_vec = pos_mid - pos_before_mid
        if dir_vec.manhattanLength() <= 0:
            return

        # 归一化方向向量
        dir_vec_length = (dir_vec.x() ** 2 + dir_vec.y() ** 2) ** 0.5
        if dir_vec_length > 0:
            dir_vec = QPointF(dir_vec.x() / dir_vec_length, dir_vec.y() / dir_vec_length)

        # 求垂直向量
        perp_vec = QPointF(-dir_vec.y(), dir_vec.x())
        arrow_size = 32  # 将箭头大小设置为原来的 4 倍

        # 箭头三个顶点（以中点为起点）
        arrow_p1 = pos_mid - dir_vec * arrow_size + perp_vec * (arrow_size * 0.5)
        arrow_p2 = pos_mid - dir_vec * arrow_size - perp_vec * (arrow_size * 0.5)

        arrow_path = QPainterPath()
        arrow_path.moveTo(pos_mid)
        arrow_path.lineTo(arrow_p1)
        arrow_path.lineTo(arrow_p2)
        arrow_path.lineTo(pos_mid)
        painter.fillPath(arrow_path, QBrush(color))

    def boundingRect(self):
        return self.path.boundingRect().adjusted(-5, -5, 5, 5)

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(10)  # 方便选择
        return stroker.createStroke(self.path)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setSelected(True)
            event.accept()
        super().mousePressEvent(event)

    def disconnect(self):
        # 与端口断开连接并从场景中移除
        self.start_port.disconnect(self)
        self.end_port.disconnect(self)
        if self.scene:
            self.scene.removeItem(self)


# 为了在 Connection 中调用统一的路径构建方法，
# 这里导入 ConnectionManager（也可以将 build_connection_path 方法移到独立模块中）
from src.node_system.connection_manager import ConnectionManager
