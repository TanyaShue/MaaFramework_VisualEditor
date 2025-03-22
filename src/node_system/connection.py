import math

from PySide6.QtCore import Qt, QPointF, QRectF, QLineF
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
        self.path = build_connection_path(self.start_port, self.end_port, self.scene)
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

def build_connection_path(start_port, end_port, scene):
    """
    构建连接路径：
      1. 计算所有节点扩展后的边界（扩展矩形）并合并（得到多个 merged_paths，用于交点检测）
      2. 根据端口所在节点边界及方向计算中点（start_mid, end_mid）
      3. 利用这两个中点构成轴对齐矩形，生成两条候选路径：
             - 候选路径1：先水平（从 start_mid 到 (end_mid.x, start_mid.y)），再垂直到 end_mid
             - 候选路径2：先垂直（从 start_mid 到 (start_mid.x, end_mid.y)），再水平到 end_mid
      4. 对每条候选路径，遍历每个合并边界（merged_paths），
         计算候选路径与该边界的交点（沿候选路径累计距离 t），但对于候选段与边界完全共线的部分不处理；
         如果（经过过滤后）正好有2个交点，则将候选路径中这两个交点之间的部分替换为该边界上两点间较短的弧段。
      5. 最终返回的路径由：
             - 从 start_port 到 start_mid
             - 两条候选路径（分别经过替换后的结果）
             - 从 end_mid 到 end_port
         并且调试时会将所有合并后的边界也绘制在最终路径中。
    """
    NODE_BUFFER = 30
    tol = 1e-6

    # --- 辅助函数 ---
    def create_boundary_rect(node):
        return node.sceneBoundingRect().adjusted(-NODE_BUFFER, -NODE_BUFFER, NODE_BUFFER, NODE_BUFFER)

    def get_ports(node):
        ports = []
        if hasattr(node, 'get_input_port'):
            ip = node.get_input_port()
            if ip:
                ports.append(ip)
        if hasattr(node, 'get_output_ports'):
            op = node.get_output_ports()
            if isinstance(op, dict):
                ports.extend(op.values())
            elif isinstance(op, list):
                ports.extend(op)
        return ports

    def create_default_boundary(pos):
        return QRectF(pos.x() - 10, pos.y() - 10, 20, 20).adjusted(-NODE_BUFFER, -NODE_BUFFER, NODE_BUFFER,
                                                                   NODE_BUFFER)

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

    def equal_points(p1, p2, tol_value=tol):
        return abs(p1.x() - p2.x()) < tol_value and abs(p1.y() - p2.y()) < tol_value

    def intersect_line(line1, line2):
        p1, p2 = line1.p1(), line1.p2()
        p3, p4 = line2.p1(), line2.p2()
        dx1, dy1 = p2.x() - p1.x(), p2.y() - p1.y()
        dx2, dy2 = p4.x() - p3.x(), p4.y() - p3.y()
        denom = dx1 * dy2 - dy1 * dx2
        if abs(denom) < tol:
            return False, None
        t = ((p3.x() - p1.x()) * dy2 - (p3.y() - p1.y()) * dx2) / denom
        u = ((p3.x() - p1.x()) * dy1 - (p3.y() - p1.y()) * dx1) / denom
        if 0 <= t <= 1 and 0 <= u <= 1:
            return True, QPointF(p1.x() + t * dx1, p1.y() + t * dy1)
        return False, None

    def get_cumulative_lengths(pts):
        cum = [0]
        for i in range(1, len(pts)):
            cum.append(cum[-1] + QLineF(pts[i - 1], pts[i]).length())
        return cum

    # --- 计算所有节点扩展边界及对应节点 ---
    rects = []
    start_node_rect = None
    end_node_rect = None
    if scene:
        for item in scene.items():
            if getattr(item, '__class__', None) and item.__class__.__name__ == 'Node':
                r = create_boundary_rect(item)
                rects.append(r)
                for port in get_ports(item):
                    if port == start_port:
                        start_node_rect = r
                    if port == end_port:
                        end_node_rect = r

    start_pos = start_port.mapToScene(QPointF(0, 0))
    end_pos = end_port.mapToScene(QPointF(0, 0))
    if start_node_rect is None:
        start_node_rect = create_default_boundary(start_pos)
    if end_node_rect is None:
        end_node_rect = create_default_boundary(end_pos)

    # --- 合并重叠边界 ---
    paths = []
    for r in rects:
        p = QPainterPath()
        p.addRect(r)
        paths.append(p)
    merged_paths = []
    while paths:
        current = paths.pop(0)
        merged = True
        while merged:
            merged = False
            new_paths = []
            for other in paths:
                if current.intersects(other):
                    current = current.united(other)
                    merged = True
                else:
                    new_paths.append(other)
            paths = new_paths
        merged_paths.append(current)

    # --- 计算边界中点及候选路径 ---
    start_mid = get_boundary_midpoint(start_node_rect, start_port.direction)
    end_mid = get_boundary_midpoint(end_node_rect, end_port.direction)
    candidate1 = [start_mid, QPointF(end_mid.x(), start_mid.y()), end_mid]
    candidate2 = [start_mid, QPointF(start_mid.x(), end_mid.y()), end_mid]

    # --- 交点检测与替换 ---
    def compute_intersections(candidate, boundary):
        poly = boundary.toFillPolygon()
        intersections = []
        cum = get_cumulative_lengths(candidate)
        for i in range(len(candidate) - 1):
            seg = QLineF(candidate[i], candidate[i + 1])
            seg_len = seg.length()
            horizontal = abs(candidate[i].y() - candidate[i + 1].y()) < tol
            vertical = abs(candidate[i].x() - candidate[i + 1].x()) < tol
            for j in range(poly.count()):
                q1, q2 = poly.at(j), poly.at((j + 1) % poly.count())
                # 如果候选段与边界边共线，则跳过处理
                if (horizontal and abs(q1.y() - q2.y()) < tol) or (vertical and abs(q1.x() - q2.x()) < tol):
                    continue
                found, pt = intersect_line(QLineF(candidate[i], candidate[i + 1]), QLineF(q1, q2))
                if found and pt:
                    frac = QLineF(candidate[i], pt).length() / seg_len if seg_len else 0
                    t_val = cum[i] + frac * seg_len
                    if not any(equal_points(pt, ex_pt) for (_, ex_pt) in intersections):
                        intersections.append((t_val, pt))
        intersections.sort(key=lambda x: x[0])
        return intersections

    def get_shorter_boundary_arc(poly, A, B, tol=tol):
        """
        对于给定多边形 poly (QPolygonF) 和位于其上的两点 A, B，
        查找连接这两点的最短边界路径，逻辑与原版保持一致。
        """
        n = poly.count()

        # 检查点是否与顶点接近
        def point_at_vertex(pt):
            for i in range(n):
                if equal_points(pt, poly.at(i), tol):
                    return i
            return None

        # 查找点所在的边（或顶点）
        def find_edge(pt):
            vertex_idx = point_at_vertex(pt)
            if vertex_idx is not None:
                return vertex_idx, "vertex"
            for i in range(n):
                p0, p1 = poly.at(i), poly.at((i + 1) % n)
                seg = QLineF(p0, p1)
                if seg.length() < tol:
                    continue
                # 判断 pt 是否位于 p0-p1 线段上
                if abs(QLineF(p0, pt).length() + QLineF(pt, p1).length() - seg.length()) < tol:
                    return i, "edge"
            return None, None

        posA, typeA = find_edge(A)
        posB, typeB = find_edge(B)

        if posA is None or posB is None:
            return [A, B]

        # 特殊情况：两点在同一位置
        if typeA == typeB and posA == posB:
            if typeA == "vertex" or (typeA == "edge" and equal_points(A, B, tol)):
                return [A, B]

        # 特殊情况：两点都在同一边上
        if typeA == "edge" and typeB == "edge" and posA == posB:
            return [A, B]

        # 构造顺时针路径
        path_cw = [A]
        if typeA == "vertex":
            i = posA
        else:
            path_cw.append(poly.at((posA + 1) % n))
            i = (posA + 1) % n
        while True:
            next_i = (i + 1) % n
            if (typeB == "vertex" and i == posB) or (typeB == "edge" and i == posB):
                break
            path_cw.append(poly.at(next_i))
            i = next_i
            if i == posA:  # 防止无限循环
                break
        if not equal_points(path_cw[-1], B, tol):
            path_cw.append(B)

        # 构造逆时针路径
        path_ccw = [A]
        if typeA == "vertex":
            i = posA
        else:
            path_ccw.append(poly.at(posA))
            i = posA
        while True:
            prev_i = (i - 1 + n) % n
            if (typeB == "vertex" and prev_i == posB) or (typeB == "edge" and prev_i == posB):
                break
            path_ccw.append(poly.at(prev_i))
            i = prev_i
            if i == posA:
                break
        if not equal_points(path_ccw[-1], B, tol):
            path_ccw.append(B)

        # 移除重复点
        def clean_path(path):
            result = [path[0]] if path else []
            for pt in path[1:]:
                if not equal_points(result[-1], pt, tol):
                    result.append(pt)
            return result

        path_cw = clean_path(path_cw)
        path_ccw = clean_path(path_ccw)

        # 计算路径长度
        def path_length(path):
            total = 0
            for i in range(len(path) - 1):
                total += QLineF(path[i], path[i + 1]).length()
            return total

        len_cw = path_length(path_cw)
        len_ccw = path_length(path_ccw)
        return path_cw if len_cw <= len_ccw else path_ccw

    def replace_segment(candidate, t1, A, t2, B, arc):
        cum = get_cumulative_lengths(candidate)
        i1 = next(i for i in range(len(cum) - 1) if cum[i] <= t1 <= cum[i + 1])
        i2 = next(i for i in range(len(cum) - 1) if cum[i] <= t2 <= cum[i + 1])
        new_candidate = candidate[:i1 + 1]
        if not equal_points(new_candidate[-1], A):
            new_candidate.append(A)
        for pt in arc:
            if not equal_points(new_candidate[-1], pt):
                new_candidate.append(pt)
        if not equal_points(new_candidate[-1], B):
            new_candidate.append(B)
        new_candidate.extend(candidate[i2 + 1:])
        return new_candidate

    def process_candidate(candidate):
        new_candidate = candidate[:]
        for boundary in merged_paths:
            inters = compute_intersections(new_candidate, boundary)
            if len(inters) == 2:
                t1, pt1 = inters[0]
                t2, pt2 = inters[1]
                arc = get_shorter_boundary_arc(boundary.toFillPolygon(), pt1, pt2)
                new_candidate = replace_segment(new_candidate, t1, pt1, t2, pt2, arc)
        return new_candidate

    candidate1_final = process_candidate(candidate1)
    candidate2_final = process_candidate(candidate2)

    # --- 优化候选路径 ---
    def path_length(points):
        return sum(QLineF(points[i - 1], points[i]).length() for i in range(1, len(points)))

    def count_turns(points):
        if len(points) < 3:
            return 0
        turns = 0
        for i in range(1, len(points) - 1):
            v1 = (points[i].x() - points[i - 1].x(), points[i].y() - points[i - 1].y())
            v2 = (points[i + 1].x() - points[i].x(), points[i + 1].y() - points[i].y())
            len1, len2 = math.hypot(*v1), math.hypot(*v2)
            if len1 > tol and len2 > tol:
                cos_angle = (v1[0] * v2[0] + v1[1] * v2[1]) / (len1 * len2)
                if abs(cos_angle) < 0.996:  # 5° 以内认为无转折
                    turns += 1
        return turns

    def smooth_path(points):
        if len(points) < 3:
            return points
        result = [points[0]]
        for i in range(1, len(points) - 1):
            prev_pt, curr, nxt = result[-1], points[i], points[i + 1]
            if QLineF(prev_pt, curr).length() < tol or QLineF(curr, nxt).length() < tol:
                continue
            v1 = (curr.x() - prev_pt.x(), curr.y() - prev_pt.y())
            v2 = (nxt.x() - curr.x(), nxt.y() - curr.y())
            if math.hypot(*v1) > tol and math.hypot(*v2) > tol:
                cos_angle = (v1[0] * v2[0] + v1[1] * v2[1]) / (math.hypot(*v1) * math.hypot(*v2))
                if cos_angle < -0.99:
                    continue
            result.append(curr)
        result.append(points[-1])
        return result

    smooth1 = smooth_path(candidate1_final)
    smooth2 = smooth_path(candidate2_final)
    turns1, turns2 = count_turns(smooth1), count_turns(smooth2)
    len1, len2 = path_length(smooth1), path_length(smooth2)
    optimal = smooth1 if (turns1 < turns2 or (turns1 == turns2 and len1 <= len2)) else smooth2

    # --- 构造最终连接路径 ---
    final_path = QPainterPath()
    final_path.moveTo(start_pos)
    final_path.lineTo(start_mid)
    final_path.moveTo(start_mid)
    for pt in optimal[1:]:
        final_path.lineTo(pt)
    final_path.moveTo(end_mid)
    final_path.lineTo(end_pos)
    return final_path

# 为了在 Connection 中调用统一的路径构建方法，
# 这里导入 ConnectionManager（也可以将 build_connection_path 方法移到独立模块中）
# from src.node_system.connection_manager import ConnectionManager
