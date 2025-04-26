import math

from PySide6.QtCore import Qt, QPointF, QRectF, QLineF, QTimer
from PySide6.QtGui import QPainter, QPen, QPainterPath, QColor, QPainterPathStroker, QBrush
from PySide6.QtWidgets import QGraphicsItem


class Connection(QGraphicsItem):
    def __init__(self, start_port, end_port, scene):
        super().__init__()
        self.start_port = start_port
        self.end_port = end_port
        self.scene = scene
        self.dash_offset = 0.0  # 用于虚线动画

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

        # 设置动画计时器
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(50)  # 每50毫秒更新一次

    def update_animation(self):
        """更新虚线动画状态"""
        self.dash_offset -= 1.0  # 负向偏移使虚线从起点向终点移动
        if self.dash_offset < -20:  # 防止数值过小
            self.dash_offset = 0.0
        self.update()  # 触发重绘

    def get_source(self):
        return self.start_port

    def get_target(self):
        return self.end_port

    def update_path(self):
        self.prepareGeometryChange()
        # 生成连线路径
        self.path = build_connection_path(self.start_port, self.end_port, self.scene)
        self.update()

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)

        # 根据输出端口类型确定颜色
        port_type = getattr(self.start_port, 'port_type', None)
        if port_type == 'next':
            color = QColor(100, 220, 100)
        elif port_type == 'on_error':
            color = QColor(220, 100, 100)
        elif port_type == 'interrupt':
            color = QColor(220, 180, 100)
        else:
            color = QColor(100, 100, 100)

        pen_width = 8 if self.isSelected() else 6
        pen = QPen(color, pen_width, Qt.DashLine)

        # 设置虚线样式，并偏移动画
        dash_pattern = [4, 4]  # 4个单位的线，4个单位的空白
        pen.setDashPattern(dash_pattern)
        pen.setDashOffset(self.dash_offset)

        painter.setPen(pen)

        # 绘制连线路径
        painter.drawPath(self.path)

    # 已移除箭头绘制功能

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
        self.animation_timer.stop()  # 停止动画计时器
        if self.scene:
            self.scene.removeItem(self)


def get_direction(direction_str):
    """将字符串方向转换为方向向量"""
    if direction_str == 'top':
        return QPointF(0, -1)
    elif direction_str == 'right':
        return QPointF(1, 0)
    elif direction_str == 'bottom':
        return QPointF(0, 1)
    else:  # 'left'
        return QPointF(-1, 0)


def build_connection_path(start_port, end_port, scene_or_pos):
    """
    统一的连线路径生成函数，既可用于临时连线也可用于正式连线

    参数：
        start_port: 起始端口
        end_port: 结束端口，若为None则表示临时连线
        scene_or_pos: 若end_port为None，则此参数为目标位置；否则为场景对象
    """
    # 临时连线情况
    if end_port is None:
        target_pos = scene_or_pos  # 此时scene_or_pos是目标位置
        start_pos = start_port.mapToScene(start_port.boundingRect().center())

        # 获取起始方向
        start_dir = get_direction(start_port.direction)
        ctrl_length = 50  # 控制点距离

        path = QPainterPath()
        path.moveTo(start_pos)
        current = start_pos + start_dir * ctrl_length
        path.lineTo(current)

        # 根据起始方向决定中间折点
        if abs(start_dir.x()) > 0:
            mid_point = QPointF(current.x(), target_pos.y())
        else:
            mid_point = QPointF(target_pos.x(), current.y())
        path.lineTo(mid_point)
        path.lineTo(target_pos)
        return path

    # 正式连线情况
    scene = scene_or_pos
    NODE_BUFFER = 40  # 节点边界缓冲距离

    # 辅助函数
    def create_boundary_rect(node):
        return node.sceneBoundingRect().adjusted(-NODE_BUFFER, -NODE_BUFFER, NODE_BUFFER, NODE_BUFFER)

    def create_default_boundary(pos):
        return QRectF(pos.x() - 10, pos.y() - 10, 20, 20).adjusted(-NODE_BUFFER, -NODE_BUFFER, NODE_BUFFER, NODE_BUFFER)

    def get_boundary_midpoint(rect, direction):
        # 计算中心点
        cx, cy = (rect.left() + rect.right()) / 2, (rect.top() + rect.bottom()) / 2

        # 根据方向返回边界中点
        if direction == 'top':
            return QPointF(cx, rect.top())
        elif direction == 'bottom':
            return QPointF(cx, rect.bottom())
        elif direction == 'left':
            return QPointF(rect.left(), cy)
        elif direction == 'right':
            return QPointF(rect.right(), cy)
        return QPointF(cx, cy)

    # 获取场景坐标中的端口位置
    start_pos = start_port.mapToScene(start_port.boundingRect().center())
    end_pos = end_port.mapToScene(end_port.boundingRect().center())

    # 查找端口所在节点的边界
    start_node_rect = None
    end_node_rect = None

    if scene:
        # 查找包含端口的节点
        nodes = [item for item in scene.items()
                 if getattr(item, '__class__', None) and item.__class__.__name__ == 'Node']

        for node in nodes:
            r = create_boundary_rect(node)

            # 获取节点的端口
            node_ports = []
            if hasattr(node, 'get_input_port'):
                ip = node.get_input_port()
                if ip:
                    node_ports.append(ip)
            if hasattr(node, 'get_output_ports'):
                op = node.get_output_ports()
                if isinstance(op, dict):
                    node_ports.extend(op.values())
                elif isinstance(op, list):
                    node_ports.extend(op)

            # 检查此节点是否包含我们的端口
            for port in node_ports:
                if port == start_port:
                    start_node_rect = r
                if port == end_port:
                    end_node_rect = r

    # 如果需要，使用默认边界
    if start_node_rect is None:
        start_node_rect = create_default_boundary(start_pos)
    if end_node_rect is None:
        end_node_rect = create_default_boundary(end_pos)

    # 根据端口方向计算边界中点
    start_mid = get_boundary_midpoint(start_node_rect, start_port.direction)
    end_mid = get_boundary_midpoint(end_node_rect, end_port.direction)

    # 创建最终路径
    path = QPainterPath()

    # 起始段：从端口到边界中点
    path.moveTo(start_pos)
    path.lineTo(start_mid)

    # 计算三次贝塞尔曲线的控制点
    dist = QLineF(start_mid, end_mid).length()
    control_dist = min(100, dist * 0.4)  # 限制控制点距离

    # 根据端口方向设置控制点，以获得自然曲线
    start_control = QPointF(start_mid)
    end_control = QPointF(end_mid)

    # 根据端口方向调整控制点
    if start_port.direction == 'right':
        start_control.setX(start_mid.x() + control_dist)
    elif start_port.direction == 'left':
        start_control.setX(start_mid.x() - control_dist)
    elif start_port.direction == 'bottom':
        start_control.setY(start_mid.y() + control_dist)
    elif start_port.direction == 'top':
        start_control.setY(start_mid.y() - control_dist)

    if end_port.direction == 'right':
        end_control.setX(end_mid.x() + control_dist)
    elif end_port.direction == 'left':
        end_control.setX(end_mid.x() - control_dist)
    elif end_port.direction == 'bottom':
        end_control.setY(end_mid.y() + control_dist)
    elif end_port.direction == 'top':
        end_control.setY(end_mid.y() - control_dist)

    # 中间段：边界中点之间的平滑曲线
    path.moveTo(start_mid)
    path.cubicTo(start_control, end_control, end_mid)

    # 结束段：从边界中点到端口
    path.moveTo(end_mid)
    path.lineTo(end_pos)

    return path