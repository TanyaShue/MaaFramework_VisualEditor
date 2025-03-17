from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath, QPolygonF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem

from src.node_system.connection import Connection
from PySide6.QtCore import QPointF, QRectF, QLineF
from PySide6.QtGui import QPainterPath


# from src.node_system.connection import Connection


class ConnectionManager:
    def __init__(self, scene, canvas):
        self.scene = scene
        self.canvas = canvas
        self.temp_connection = None
        self.connecting_port = None
        self.connections = []

    def start_connection(self, output_port):
        """开始从输出端口创建一条连线"""
        self.connecting_port = output_port
        start_pos = output_port.mapToScene(output_port.boundingRect().center())
        end_pos = start_pos  # 初始位置重合
        self.temp_connection = self.create_temp_connection(start_pos, end_pos)
        return self.temp_connection

    def update_temp_connection(self, target_pos):
        """更新临时连线的路径"""
        if not self.temp_connection or not self.connecting_port:
            return

        start_pos = self.connecting_port.mapToScene(self.connecting_port.boundingRect().center())
        start_dir = self._get_direction(self.connecting_port.direction)
        path = self.build_temp_connection_path(start_pos, target_pos, start_dir)
        self.temp_connection.setPath(path)

    def finish_connection(self, target_port):
        """完成连线操作，创建实际的 Connection 对象"""
        if not self.connecting_port or not target_port:
            return None

        if not self.can_connect(self.connecting_port, target_port):
            return None

        connection = Connection(self.connecting_port, target_port, self.scene)
        self.connections.append(connection)
        self.cancel_connection()
        return connection

    def cancel_connection(self):
        """取消当前连线操作"""
        if self.temp_connection:
            self.scene.removeItem(self.temp_connection)
            self.temp_connection = None
        self.connecting_port = None

    def create_temp_connection(self, start_pos, end_pos):
        """创建临时连线路径，供视觉反馈使用"""
        from PySide6.QtGui import QPen, QColor
        from PySide6.QtCore import Qt

        if self.connecting_port.port_type == 'next':
            color = QColor(100, 220, 100)
        elif self.connecting_port.port_type == 'on_error':
            color = QColor(220, 100, 100)
        elif self.connecting_port.port_type == 'interrupt':
            color = QColor(220, 180, 100)
        else:
            color = QColor(100, 100, 100)

        temp_connection = QGraphicsPathItem()
        temp_connection.setPen(QPen(color, 2, Qt.DashLine))
        start_dir = self._get_direction(self.connecting_port.direction)
        path = self.build_temp_connection_path(start_pos, end_pos, start_dir)
        temp_connection.setPath(path)
        self.scene.addItem(temp_connection)
        return temp_connection

    def can_connect(self, source_port, target_port):
        """检查两个端口是否可以连接（例如，不能连接同一节点，且端口类型必须兼容）"""
        if not source_port or not target_port:
            return False

        if source_port.parent_node == target_port.parent_node:
            return False

        if not source_port.can_connect(target_port):
            return False

        return True

    def remove_connection(self, connection):
        """移除指定的连线"""
        if not connection:
            return

        source = connection.get_source()
        target = connection.get_target()

        if source and hasattr(source, 'connections') and connection in source.connections:
            source.connections.remove(connection)
        if target and hasattr(target, 'connections') and connection in target.connections:
            target.connections.remove(connection)

        self.scene.removeItem(connection)
        if connection in self.connections:
            self.connections.remove(connection)

    def update_connections_for_node(self, node):
        """更新与指定节点有关的所有连线"""
        input_port = node.get_input_port()
        if input_port and hasattr(input_port, 'connections'):
            for connection in input_port.connections:
                if connection:
                    connection.update_path()

        output_ports = node.get_output_ports()
        if isinstance(output_ports, dict):
            output_ports = list(output_ports.values())

        for output_port in output_ports:
            if output_port and hasattr(output_port, 'connections'):
                for connection in output_port.connections:
                    if connection:
                        connection.update_path()

    def _get_direction(self, direction_str):
        """将字符串方向转换为方向向量"""
        if direction_str == 'top':
            return QPointF(0, -1)
        elif direction_str == 'right':
            return QPointF(1, 0)
        elif direction_str == 'bottom':
            return QPointF(0, 1)
        else:  # 'left'
            return QPointF(-1, 0)

    def build_temp_connection_path(self, start_pos, target_pos, start_dir):
        """构建临时连线的路径（较简单，不含节点避让）"""
        ctrl_length = 20
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

    @staticmethod
    def build_connection_path(start_port, end_port, scene):
        """
        构建最优连接路径:
        1. 确定所有节点的边界
        2. 连接端口到所在节点边界的中点
        3. 构建两个边界中点之间的连线(尽量少的横线或竖线)
        4. 如果直接连线与其他节点边界相交，则绕过这些节点
        5. 对连线进行优化，移除多余点并平滑拐角
        """
        # 基本配置参数
        node_buffer = 30  # 节点边界扩展距离
        radius = 10  # 拐角曲率半径
        offset = 20  # 节点边界偏移距离

        # 获取端口位置
        start_pos = start_port.mapToScene(QPointF(0, 0))
        end_pos = end_port.mapToScene(QPointF(0, 0))

        # 定义方向向量
        direction_vectors = {
            'top': QPointF(0, -1),
            'right': QPointF(1, 0),
            'bottom': QPointF(0, 1),
            'left': QPointF(-1, 0)
        }
        start_dir = direction_vectors[start_port.direction]
        end_dir = direction_vectors[end_port.direction]

        node_boundaries = []
        start_node_boundary = None
        end_node_boundary = None

        # 遍历场景中的所有节点，获取边界信息，并预计算扩展边界的边缘
        if scene:
            for item in scene.items():
                if hasattr(item, '__class__') and item.__class__.__name__ == 'Node':
                    orig_rect = item.sceneBoundingRect()
                    ext_rect = orig_rect.adjusted(-node_buffer, -node_buffer, node_buffer, node_buffer)
                    # 预计算扩展边界的四条边，避免重复计算
                    edges = [
                        QLineF(ext_rect.topLeft(), ext_rect.topRight()),
                        QLineF(ext_rect.topRight(), ext_rect.bottomRight()),
                        QLineF(ext_rect.bottomRight(), ext_rect.bottomLeft()),
                        QLineF(ext_rect.bottomLeft(), ext_rect.topLeft())
                    ]
                    boundary_info = {
                        'node': item,
                        'original': orig_rect,
                        'extended': ext_rect,
                        'edges': edges,
                        'midpoints': {
                            'top': QPointF((ext_rect.left() + ext_rect.right()) / 2, ext_rect.top()),
                            'right': QPointF(ext_rect.right(), (ext_rect.top() + ext_rect.bottom()) / 2),
                            'bottom': QPointF((ext_rect.left() + ext_rect.right()) / 2, ext_rect.bottom()),
                            'left': QPointF(ext_rect.left(), (ext_rect.top() + ext_rect.bottom()) / 2)
                        }
                    }

                    ports = []
                    if hasattr(item, 'get_input_port'):
                        ip = item.get_input_port()
                        if ip:
                            ports.append(ip)
                    if hasattr(item, 'get_output_ports'):
                        op = item.get_output_ports()
                        if isinstance(op, dict):
                            ports.extend(list(op.values()))
                        elif isinstance(op, list):
                            ports.extend(op)

                    if start_port in ports:
                        start_node_boundary = boundary_info
                    if end_port in ports:
                        end_node_boundary = boundary_info

                    node_boundaries.append(boundary_info)

        # 若未找到对应节点，使用默认边界
        if not start_node_boundary or not end_node_boundary:
            start_rect = QRectF(start_pos.x() - 10, start_pos.y() - 10, 20, 20)
            end_rect = QRectF(end_pos.x() - 10, end_pos.y() - 10, 20, 20)
            start_node_boundary = {
                'original': start_rect,
                'extended': start_rect.adjusted(-node_buffer, -node_buffer, node_buffer, node_buffer),
                'midpoints': {
                    'top': QPointF(start_pos.x(), start_rect.top() - node_buffer),
                    'right': QPointF(start_rect.right() + node_buffer, start_pos.y()),
                    'bottom': QPointF(start_pos.x(), start_rect.bottom() + node_buffer),
                    'left': QPointF(start_rect.left() - node_buffer, start_pos.y())
                }
            }
            end_node_boundary = {
                'original': end_rect,
                'extended': end_rect.adjusted(-node_buffer, -node_buffer, node_buffer, node_buffer),
                'midpoints': {
                    'top': QPointF(end_pos.x(), end_rect.top() - node_buffer),
                    'right': QPointF(end_rect.right() + node_buffer, end_pos.y()),
                    'bottom': QPointF(end_pos.x(), end_rect.bottom() + node_buffer),
                    'left': QPointF(end_rect.left() - node_buffer, end_pos.y())
                }
            }

        # 如果起始和结束是同一个节点，创建简单的回环路径
        if start_node_boundary == end_node_boundary:
            path = QPainterPath()
            path.moveTo(start_pos)
            detour_point = start_pos + start_dir * offset * 2
            mid_point = (start_pos + end_pos) * 0.5 + QPointF(0, offset * 1.5)
            path.lineTo(detour_point)
            path.lineTo(mid_point)
            path.lineTo(end_pos)
            return path

        # 根据端口方向获取节点边界中点
        def get_boundary_point(port_position, port_direction, boundary):
            return boundary['midpoints'][port_direction]

        start_boundary_point = get_boundary_point(start_pos, start_port.direction, start_node_boundary)
        end_boundary_point = get_boundary_point(end_pos, end_port.direction, end_node_boundary)

        # 计算扩展连接点
        start_outside = start_boundary_point + start_dir * offset
        end_outside = end_boundary_point + end_dir * offset

        # 根据端口方向明确计算中间点
        if start_port.direction in ('left', 'right') and end_port.direction in ('top', 'bottom'):
            # 当起始端口水平，结束端口垂直时，先水平再垂直
            mid_point = QPointF(start_outside.x(), end_outside.y())
        elif start_port.direction in ('top', 'bottom') and end_port.direction in ('left', 'right'):
            # 当起始端口垂直，结束端口水平时，先垂直再水平
            mid_point = QPointF(end_outside.x(), start_outside.y())
        else:
            # 当两个端口都在水平方向或都在垂直方向时，
            # 使用简单的差值比较，选取一个折中点
            if abs(start_outside.x() - end_outside.x()) > abs(start_outside.y() - end_outside.y()):
                mid_point = QPointF((start_outside.x() + end_outside.x()) / 2, start_outside.y())
            else:
                mid_point = QPointF(start_outside.x(), (start_outside.y() + end_outside.y()) / 2)

        # 初始路径点
        path_points = [
            start_pos,
            start_boundary_point,
            start_outside,
            mid_point,
            end_outside,
            end_boundary_point,
            end_pos
        ]

        # 检查线段与矩形是否相交（加入快速边界框检测）
        def line_intersects_rect(line_start, line_end, rect, edges):
            if (max(line_start.x(), line_end.x()) < rect.left() or
                    min(line_start.x(), line_end.x()) > rect.right() or
                    max(line_start.y(), line_end.y()) < rect.top() or
                    min(line_start.y(), line_end.y()) > rect.bottom()):
                return False
            line = QLineF(line_start, line_end)
            for edge in edges:
                intersection_type, _ = line.intersects(edge)
                if intersection_type == QLineF.BoundedIntersection:
                    return True
            return False

        # 检查路径段是否与障碍物相交，合并关键点判断
        def find_obstacle(p1, p2):
            # 修改这部分：不要跳过特殊点的检测
            # special_points = [start_pos, end_pos, start_boundary_point, start_outside, end_boundary_point, end_outside]
            for boundary in node_boundaries:
                # 如果是起点或终点节点，需要特殊处理
                if boundary == start_node_boundary or boundary == end_node_boundary:
                    # 如果是连接到节点本身的线段，允许穿过该节点边界
                    if (p1 == start_pos and p2 == start_boundary_point) or \
                            (p1 == start_boundary_point and p2 == start_outside) or \
                            (p1 == end_boundary_point and p2 == end_pos) or \
                            (p1 == end_outside and p2 == end_boundary_point):
                        continue
                # 检查线段是否与节点边界相交
                if line_intersects_rect(p1, p2, boundary['extended'], boundary.get('edges', [])):
                    return boundary
            return None

        # 根据障碍物计算绕行路径（合并水平、垂直分支）

        def calculate_detour(p1, p2, obstacle):
            ext_rect = obstacle['extended']
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()

            # 定义绕行距离常量（将其移到函数开头定义）
            clear_distance = 10

            # 更精确地计算绕行方向
            to_end_vector = QPointF(end_pos.x() - p1.x(), end_pos.y() - p1.y())

            # 考虑与起点或终点的关系
            if obstacle == start_node_boundary:
                # 强制绕行，避免穿过起点节点
                if start_port.direction == 'left':
                    y_detour = ext_rect.top() - clear_distance if to_end_vector.y() < 0 else ext_rect.bottom() + clear_distance
                    return [QPointF(p1.x(), y_detour), QPointF(p2.x(), y_detour)]
                elif start_port.direction == 'right':
                    y_detour = ext_rect.top() - clear_distance if to_end_vector.y() < 0 else ext_rect.bottom() + clear_distance
                    return [QPointF(p1.x(), y_detour), QPointF(p2.x(), y_detour)]

            # 一般情况下的绕行逻辑
            horizontal_dominant = abs(dx) > abs(dy)

            if horizontal_dominant:
                y_detour = ext_rect.top() - clear_distance if to_end_vector.y() < 0 else ext_rect.bottom() + clear_distance
                return [QPointF(p1.x(), y_detour), QPointF(p2.x(), y_detour)]
            else:
                x_detour = ext_rect.left() - clear_distance if to_end_vector.x() < 0 else ext_rect.right() + clear_distance
                return [QPointF(x_detour, p1.y()), QPointF(x_detour, p2.y())]
        # 处理路径中的障碍物，迭代防止无限循环
        max_iterations = 50
        iteration_count = 0
        changed = True

        while changed and iteration_count < max_iterations:
            changed = False
            i = 0
            while i < len(path_points) - 1:
                p1 = path_points[i]
                p2 = path_points[i + 1]
                obstacle = find_obstacle(p1, p2)
                if obstacle:
                    detour_points = calculate_detour(p1, p2, obstacle)
                    if detour_points:
                        path_points = path_points[:i + 1] + detour_points + path_points[i + 1:]
                        changed = True
                        iteration_count += 1
                        break  # 重新检查更新后的路径
                i += 1

        # 简化路径：移除几乎共线的点
        def simplify_path(points, tolerance=1.0):
            if len(points) <= 2:
                return points
            result = [points[0]]
            for i in range(1, len(points) - 1):
                prev = result[-1]
                current = points[i]
                next_pt = points[i + 1]
                if (abs(prev.x() - current.x()) < tolerance and abs(current.x() - next_pt.x()) < tolerance) or \
                        (abs(prev.y() - current.y()) < tolerance and abs(current.y() - next_pt.y()) < tolerance):
                    continue
                result.append(current)
            result.append(points[-1])
            return result

        simplified_points = simplify_path(path_points)

        # 创建平滑的贝塞尔路径
        path = QPainterPath()
        if not simplified_points:
            return path

        path.moveTo(simplified_points[0])
        tolerance = 1.0
        if len(simplified_points) == 2:
            path.lineTo(simplified_points[1])
        else:
            for i in range(1, len(simplified_points)):
                current = simplified_points[i]
                prev = simplified_points[i - 1]
                # 对拐角进行平滑处理
                if i < len(simplified_points) - 1:
                    next_pt = simplified_points[i + 1]
                    v1 = QPointF(current.x() - prev.x(), current.y() - prev.y())
                    v2 = QPointF(next_pt.x() - current.x(), next_pt.y() - current.y())
                    is_corner = (abs(v1.x()) > tolerance and abs(v2.y()) > tolerance) or \
                                (abs(v1.y()) > tolerance and abs(v2.x()) > tolerance)
                    if is_corner:
                        line1 = QLineF(prev, current)
                        line2 = QLineF(current, next_pt)
                        if line1.length() > radius and line2.length() > radius:
                            corner_start = QPointF(
                                prev.x() + v1.x() * (1 - radius / line1.length()),
                                prev.y() + v1.y() * (1 - radius / line1.length())
                            )
                            path.lineTo(corner_start)
                            corner_end = QPointF(
                                current.x() + v2.x() * (radius / line2.length()),
                                current.y() + v2.y() * (radius / line2.length())
                            )
                            path.quadTo(current, corner_end)
                        else:
                            path.lineTo(current)
                    else:
                        path.lineTo(current)
                else:
                    path.lineTo(current)

        # 调试代码：在节点边界中点处绘制三角形，帮助判断路径
        def add_debug_triangle(target_path, center, size=10):
            p1 = QPointF(center.x(), center.y() - size / 2)
            p2 = QPointF(center.x() - size / 2, center.y() + size / 2)
            p3 = QPointF(center.x() + size / 2, center.y() + size / 2)
            triangle = QPolygonF([p1, p2, p3])
            debug_path = QPainterPath()
            debug_path.addPolygon(triangle)
            target_path.addPath(debug_path)

        # 在起始节点和结束节点的边界中点处绘制调试用三角形
        add_debug_triangle(path, start_boundary_point)
        add_debug_triangle(path, end_boundary_point)

        return path
