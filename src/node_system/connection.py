import math

from PySide6.QtCore import Qt, QPointF, QRectF, QLineF, QTimer
from PySide6.QtGui import QPainter, QPen, QPainterPath, QColor, QPainterPathStroker, QBrush
from PySide6.QtWidgets import QGraphicsItem


class Connection(QGraphicsItem):
    # 类级别的共享数据和计时器
    all_connections = []
    shared_animation_timer = None

    def __init__(self, start_port, end_port, scene):
        super().__init__()
        self.start_port = start_port
        self.end_port = end_port
        self.scene = scene
        self.dash_offset = 0.0  # 用于虚线动画

        # 性能优化：缓存路径的复杂度级别
        self.current_lod = 0  # 0 = 高细节, 1 = 中等细节, 2 = 低细节
        self.path_is_dirty = True  # 路径是否需要更新

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

        # 性能优化：使用共享计时器
        if Connection.shared_animation_timer is None:
            Connection.shared_animation_timer = QTimer()
            Connection.shared_animation_timer.timeout.connect(Connection.update_all_animations)
            Connection.shared_animation_timer.start(50)  # 每50毫秒更新一次

        Connection.all_connections.append(self)

    @classmethod
    def update_all_animations(cls):
        """更新所有连接的动画状态"""
        for connection in cls.all_connections:
            connection.dash_offset -= 1.0  # 负向偏移使虚线从起点向终点移动
            if connection.dash_offset < -20:  # 防止数值过小
                connection.dash_offset = 0.0
            connection.update()  # 触发重绘

    def update_path(self):
        """更新连接路径"""
        if not self.path_is_dirty:
            return  # 如果路径没有变化，避免不必要的更新

        self.prepareGeometryChange()
        # 性能优化：生成连线路径
        self.path = build_connection_path(self.start_port, self.end_port, self.scene)
        self.path_is_dirty = False  # 标记路径已更新
        self.update()

    def get_source(self):
        return self.start_port

    def get_target(self):
        return self.end_port

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)

        # 获取当前视图缩放比例
        view_scale = 1.0
        if self.scene and self.scene.views():
            view = self.scene.views()[0]
            view_scale = view.transform().m11()  # 获取水平缩放因子

        # 根据缩放级别确定细节等级
        if view_scale < 0.4:
            self.current_lod = 2  # 低细节
        elif view_scale < 0.7:
            self.current_lod = 1  # 中等细节
        else:
            self.current_lod = 0  # 高细节

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

        # 根据选择状态和细节级别调整线宽
        pen_width = 8 if self.isSelected() else (6 if self.current_lod == 0 else (4 if self.current_lod == 1 else 2))

        # 低细节模式下使用简单的绘制方法
        if self.current_lod == 2:
            # 低细节时，只绘制基本的线条
            pen = QPen(color, pen_width, Qt.SolidLine)
            painter.setPen(pen)

            # 获取起点和终点
            start_pos = self.start_port.mapToScene(self.start_port.boundingRect().center())
            end_pos = self.end_port.mapToScene(self.end_port.boundingRect().center())

            # 绘制直线
            simple_path = QPainterPath()
            simple_path.moveTo(start_pos)
            simple_path.lineTo(end_pos)
            painter.drawPath(simple_path)
        else:
            # 正常绘制带虚线的路径
            pen = QPen(color, pen_width, Qt.DashLine)

            # 设置虚线样式
            dash_pattern = [4, 4]  # 4个单位的线，4个单位的空白
            pen.setDashPattern(dash_pattern)
            pen.setDashOffset(self.dash_offset)

            painter.setPen(pen)
            painter.drawPath(self.path)

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

        # 从连接列表中移除
        if self in Connection.all_connections:
            Connection.all_connections.remove(self)

        # 如果没有连接了，停止共享计时器
        if not Connection.all_connections and Connection.shared_animation_timer:
            Connection.shared_animation_timer.stop()

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
    优化的连线路径生成函数
    """
    # 临时连线情况的优化
    if end_port is None:
        target_pos = scene_or_pos  # 此时scene_or_pos是目标位置
        start_pos = start_port.mapToScene(start_port.boundingRect().center())
        start_dir = get_direction(start_port.direction)
        ctrl_length = 50

        # 使用简化的路径生成方法
        path = QPainterPath()
        path.moveTo(start_pos)

        # 根据起始方向创建控制点
        current = start_pos + start_dir * ctrl_length
        path.lineTo(current)

        # 根据起始方向决定中间折点
        if abs(start_dir.x()) > 0:  # 水平方向
            mid_point = QPointF(current.x(), target_pos.y())
        else:  # 垂直方向
            mid_point = QPointF(target_pos.x(), current.y())

        path.lineTo(mid_point)
        path.lineTo(target_pos)
        return path

    # 正式连线情况 - 优化性能
    scene = scene_or_pos
    NODE_BUFFER = 40  # 节点边界缓冲距离

    # 优化：直接获取节点的边界
    start_node = start_port.parent_node
    end_node = end_port.parent_node

    # 直接计算节点边界
    start_node_rect = start_node.sceneBoundingRect().adjusted(-NODE_BUFFER, -NODE_BUFFER, NODE_BUFFER, NODE_BUFFER)
    end_node_rect = end_node.sceneBoundingRect().adjusted(-NODE_BUFFER, -NODE_BUFFER, NODE_BUFFER, NODE_BUFFER)

    # 辅助函数：计算边界中点
    def get_boundary_midpoint(rect, direction):
        cx, cy = (rect.left() + rect.right()) / 2, (rect.top() + rect.bottom()) / 2

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

    # 计算边界中点
    start_mid = get_boundary_midpoint(start_node_rect, start_port.direction)
    end_mid = get_boundary_midpoint(end_node_rect, end_port.direction)

    # 创建路径
    path = QPainterPath()

    # 起始段：从端口到边界中点
    path.moveTo(start_pos)
    path.lineTo(start_mid)

    # 优化：根据节点距离调整曲线复杂度
    dist = QLineF(start_mid, end_mid).length()

    # 短距离使用贝塞尔曲线，更自然
    control_dist = min(80, dist * 0.4)

    # 创建控制点
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

    # 绘制贝塞尔曲线
    path.cubicTo(start_control, end_control, end_mid)

    # 结束段：从边界中点到端口
    path.lineTo(end_pos)

    return path