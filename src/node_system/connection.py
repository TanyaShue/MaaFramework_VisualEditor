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
    TOL = 1e-6
    TOL_SQ = TOL * TOL  # 预计算平方容差，用于距离比较

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
        return QRectF(pos.x() - 10, pos.y() - 10, 20, 20).adjusted(-NODE_BUFFER, -NODE_BUFFER, NODE_BUFFER, NODE_BUFFER)

    def get_boundary_midpoint(rect, direction):
        # 预计算中心坐标，避免重复计算
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

    def equal_points(p1, p2):
        # 使用平方距离进行点比较，避免计算平方根
        dx = p1.x() - p2.x()
        dy = p1.y() - p2.y()
        return dx * dx + dy * dy < TOL_SQ

    def intersect_line(line1, line2):
        p1, p2 = line1.p1(), line1.p2()
        p3, p4 = line2.p1(), line2.p2()

        # 预计算增量
        dx1, dy1 = p2.x() - p1.x(), p2.y() - p1.y()
        dx2, dy2 = p4.x() - p3.x(), p4.y() - p3.y()

        denom = dx1 * dy2 - dy1 * dx2
        if abs(denom) < TOL:
            return False, None

        # 计算参数
        p3x_p1x = p3.x() - p1.x()
        p3y_p1y = p3.y() - p1.y()

        t = (p3x_p1x * dy2 - p3y_p1y * dx2) / denom
        u = (p3x_p1x * dy1 - p3y_p1y * dx1) / denom

        if 0 <= t <= 1 and 0 <= u <= 1:
            # 计算交点
            px = p1.x() + t * dx1
            py = p1.y() + t * dy1
            return True, QPointF(px, py)
        return False, None

    def get_cumulative_lengths(pts):
        if not pts:
            return [0]

        # 优化累计长度计算
        result = [0]
        for i in range(1, len(pts)):
            dx = pts[i].x() - pts[i - 1].x()
            dy = pts[i].y() - pts[i - 1].y()
            result.append(result[-1] + (dx * dx + dy * dy) ** 0.5)
        return result

    # --- 计算所有节点扩展边界及对应节点 ---
    rects = []
    start_node_rect = None
    end_node_rect = None

    if scene:
        # 只获取节点类型，避免处理所有场景项
        nodes = [item for item in scene.items()
                 if getattr(item, '__class__', None) and item.__class__.__name__ == 'Node']

        # 更高效地处理节点
        for node in nodes:
            r = create_boundary_rect(node)
            rects.append(r)

            # 每个节点只获取一次端口
            node_ports = get_ports(node)
            for port in node_ports:
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
    # 创建路径
    paths = []
    for r in rects:
        p = QPainterPath()
        p.addRect(r)
        paths.append(p)

    # 预缓存每个合并路径的多边形
    merged_paths = []
    merged_polys = []  # 多边形缓存

    # 更高效地处理路径
    while paths:
        current = paths.pop(0)
        merged = True

        while merged:
            merged = False
            # 使用更高效的方法进行路径合并
            i = 0
            while i < len(paths):
                if current.intersects(paths[i]):
                    current = current.united(paths[i])
                    paths.pop(i)
                    merged = True
                else:
                    i += 1

        merged_paths.append(current)
        merged_polys.append(current.toFillPolygon())  # 预计算多边形

    # --- 计算边界中点及候选路径 ---
    start_mid = get_boundary_midpoint(start_node_rect, start_port.direction)
    end_mid = get_boundary_midpoint(end_node_rect, end_port.direction)

    # 预计算中间点
    mid_x_start_y = QPointF(end_mid.x(), start_mid.y())
    start_x_mid_y = QPointF(start_mid.x(), end_mid.y())

    # 创建候选路径
    candidate1 = [start_mid, mid_x_start_y, end_mid]
    candidate2 = [start_mid, start_x_mid_y, end_mid]

    # --- 交点检测与替换 ---
    def compute_intersections(candidate, poly):
        intersections = []
        cum_lengths = get_cumulative_lengths(candidate)
        poly_count = poly.count()

        # 处理每个线段
        for i in range(len(candidate) - 1):
            seg_start, seg_end = candidate[i], candidate[i + 1]

            # 计算线段属性
            dx = seg_end.x() - seg_start.x()
            dy = seg_end.y() - seg_start.y()
            seg_len = (dx * dx + dy * dy) ** 0.5
            is_horizontal = abs(dy) < TOL
            is_vertical = abs(dx) < TOL

            seg = QLineF(seg_start, seg_end)

            # 检查与多边形所有边的交点
            for j in range(poly_count):
                edge_start = poly.at(j)
                edge_end = poly.at((j + 1) % poly_count)

                # 跳过平行线段
                edge_dx = edge_end.x() - edge_start.x()
                edge_dy = edge_end.y() - edge_start.y()

                if (is_horizontal and abs(edge_dy) < TOL) or (is_vertical and abs(edge_dx) < TOL):
                    continue

                # 计算交点
                found, point = intersect_line(seg, QLineF(edge_start, edge_end))
                if found and point:
                    # 计算路径参数
                    if seg_len > TOL:
                        pt_dx = point.x() - seg_start.x()
                        pt_dy = point.y() - seg_start.y()
                        frac = ((pt_dx * pt_dx + pt_dy * pt_dy) ** 0.5) / seg_len
                    else:
                        frac = 0

                    t_val = cum_lengths[i] + frac * seg_len

                    # 检查重复点
                    is_duplicate = False
                    for _, existing_pt in intersections:
                        if equal_points(point, existing_pt):
                            is_duplicate = True
                            break

                    if not is_duplicate:
                        intersections.append((t_val, point))

        # 按参数排序
        intersections.sort(key=lambda x: x[0])
        return intersections

    def get_shorter_boundary_arc(poly, A, B):
        """
        优化版 get_shorter_boundary_arc 函数
        """
        n = poly.count()

        # 检查点是否与顶点接近
        def point_at_vertex(pt):
            for i in range(n):
                if equal_points(pt, poly.at(i)):
                    return i
            return None

        # 查找点所在的边（或顶点）
        def find_edge(pt):
            # 先检查顶点
            vertex_idx = point_at_vertex(pt)
            if vertex_idx is not None:
                return vertex_idx, "vertex"

            # 再检查边
            for i in range(n):
                p0, p1 = poly.at(i), poly.at((i + 1) % n)

                # 跳过很短的边
                dx = p1.x() - p0.x()
                dy = p1.y() - p0.y()
                seg_len_sq = dx * dx + dy * dy

                if seg_len_sq < TOL_SQ:
                    continue

                # 更高效地检查点是否在线段上
                d1_sq = (pt.x() - p0.x()) ** 2 + (pt.y() - p0.y()) ** 2
                d2_sq = (pt.x() - p1.x()) ** 2 + (pt.y() - p1.y()) ** 2

                # 如果点在线段上，d1 + d2 ≈ 线段长度
                if abs((d1_sq ** 0.5 + d2_sq ** 0.5) - seg_len_sq ** 0.5) < TOL:
                    return i, "edge"

            return None, None

        # 查找两点的边信息
        posA, typeA = find_edge(A)
        posB, typeB = find_edge(B)

        # 处理特殊情况
        if posA is None or posB is None:
            return [A, B]

        if typeA == typeB and posA == posB:
            if typeA == "vertex" or (typeA == "edge" and equal_points(A, B)):
                return [A, B]

        if typeA == "edge" and typeB == "edge" and posA == posB:
            return [A, B]

        # 初始化顺时针和逆时针路径
        path_cw = [A]
        path_ccw = [A]

        # 构建顺时针路径
        i_cw = posA
        if typeA != "vertex":
            path_cw.append(poly.at((posA + 1) % n))
            i_cw = (posA + 1) % n

        # 防止无限循环
        steps = 0
        max_steps = n + 2

        # 构建顺时针路径
        while steps < max_steps:
            next_i = (i_cw + 1) % n
            if (typeB == "vertex" and i_cw == posB) or (typeB == "edge" and i_cw == posB):
                break
            path_cw.append(poly.at(next_i))
            i_cw = next_i
            if i_cw == posA:  # 安全检查
                break
            steps += 1

        if not equal_points(path_cw[-1], B):
            path_cw.append(B)

        # 构建逆时针路径
        i_ccw = posA
        if typeA != "vertex":
            path_ccw.append(poly.at(posA))

        steps = 0
        while steps < max_steps:
            prev_i = (i_ccw - 1 + n) % n
            if (typeB == "vertex" and prev_i == posB) or (typeB == "edge" and prev_i == posB):
                break
            path_ccw.append(poly.at(prev_i))
            i_ccw = prev_i
            if i_ccw == posA:  # 安全检查
                break
            steps += 1

        if not equal_points(path_ccw[-1], B):
            path_ccw.append(B)

        # 清理路径 - 删除连续重复点
        def clean_path(path):
            if not path:
                return []

            result = [path[0]]
            for pt in path[1:]:
                if not equal_points(result[-1], pt):
                    result.append(pt)
            return result

        path_cw = clean_path(path_cw)
        path_ccw = clean_path(path_ccw)

        # 比较路径长度
        def path_length(path):
            if len(path) <= 1:
                return 0

            total = 0
            for i in range(len(path) - 1):
                dx = path[i + 1].x() - path[i].x()
                dy = path[i + 1].y() - path[i].y()
                total += (dx * dx + dy * dy) ** 0.5
            return total

        len_cw = path_length(path_cw)
        len_ccw = path_length(path_ccw)

        return path_cw if len_cw <= len_ccw else path_ccw

    def replace_segment(candidate, t1, pt1, t2, pt2, arc):
        cum_lengths = get_cumulative_lengths(candidate)

        # 根据t值查找线段索引
        i1 = 0
        for i in range(len(cum_lengths) - 1):
            if cum_lengths[i] <= t1 <= cum_lengths[i + 1]:
                i1 = i
                break

        i2 = 0
        for i in range(len(cum_lengths) - 1):
            if cum_lengths[i] <= t2 <= cum_lengths[i + 1]:
                i2 = i
                break

        # 高效构建新路径
        new_candidate = candidate[:i1 + 1]

        # 添加第一个交点（如果需要）
        if not new_candidate or not equal_points(new_candidate[-1], pt1):
            new_candidate.append(pt1)

        # 添加弧线点
        for arc_pt in arc:
            if not new_candidate or not equal_points(new_candidate[-1], arc_pt):
                new_candidate.append(arc_pt)

        # 添加第二个交点（如果需要）
        if not new_candidate or not equal_points(new_candidate[-1], pt2):
            new_candidate.append(pt2)

        # 添加剩余点
        new_candidate.extend(candidate[i2 + 1:])

        return new_candidate

    def process_candidate(candidate):
        # 使用候选路径的副本
        new_candidate = candidate[:]

        # 处理每个边界
        for idx, boundary in enumerate(merged_paths):
            # 使用缓存的多边形
            poly = merged_polys[idx]

            # 查找交点
            intersections = compute_intersections(new_candidate, poly)

            # 只处理恰好有2个交点的情况
            if len(intersections) == 2:
                t1, pt1 = intersections[0]
                t2, pt2 = intersections[1]

                # 查找边界上的较短路径
                arc = get_shorter_boundary_arc(poly, pt1, pt2)

                # 用弧线替换线段
                new_candidate = replace_segment(new_candidate, t1, pt1, t2, pt2, arc)

        return new_candidate

    # 处理两个候选路径
    candidate1_final = process_candidate(candidate1)
    candidate2_final = process_candidate(candidate2)

    # --- 优化候选路径 ---
    def path_length(points):
        total = 0
        for i in range(1, len(points)):
            dx = points[i].x() - points[i - 1].x()
            dy = points[i].y() - points[i - 1].y()
            total += (dx * dx + dy * dy) ** 0.5
        return total

    def count_turns(points):
        if len(points) < 3:
            return 0

        turns = 0
        for i in range(1, len(points) - 1):
            # 计算向量
            v1x = points[i].x() - points[i - 1].x()
            v1y = points[i].y() - points[i - 1].y()
            v2x = points[i + 1].x() - points[i].x()
            v2y = points[i + 1].y() - points[i].y()

            # 计算长度的平方
            len1_sq = v1x * v1x + v1y * v1y
            len2_sq = v2x * v2x + v2y * v2y

            # 只处理有效长度的线段
            if len1_sq > TOL_SQ and len2_sq > TOL_SQ:
                len1 = len1_sq ** 0.5
                len2 = len2_sq ** 0.5

                # 计算向量夹角的余弦值
                cos_angle = (v1x * v2x + v1y * v2y) / (len1 * len2)

                # 如果余弦值小于0.996（约5度），计为一个转折
                if abs(cos_angle) < 0.996:
                    turns += 1

        return turns

    def smooth_path(points):
        if len(points) < 3:
            return points

        result = [points[0]]

        for i in range(1, len(points) - 1):
            prev_pt, curr, nxt = result[-1], points[i], points[i + 1]

            # 计算向量和长度
            dx1, dy1 = curr.x() - prev_pt.x(), curr.y() - prev_pt.y()
            dx2, dy2 = nxt.x() - curr.x(), nxt.y() - curr.y()

            len1_sq = dx1 * dx1 + dy1 * dy1
            len2_sq = dx2 * dx2 + dy2 * dy2

            # 跳过太短的线段
            if len1_sq < TOL_SQ or len2_sq < TOL_SQ:
                continue

            # 计算角度
            len1 = len1_sq ** 0.5
            len2 = len2_sq ** 0.5

            cos_angle = (dx1 * dx2 + dy1 * dy2) / (len1 * len2)

            # 跳过接近180度的角度（回溯）
            if cos_angle < -0.99:
                continue

            result.append(curr)

        result.append(points[-1])
        return result

    # 对两个候选路径应用平滑处理
    smooth1 = smooth_path(candidate1_final)
    smooth2 = smooth_path(candidate2_final)

    # 计算两条路径的指标
    turns1 = count_turns(smooth1)
    turns2 = count_turns(smooth2)

    len1 = path_length(smooth1)
    len2 = path_length(smooth2)

    # 选择最优路径
    optimal = smooth1 if (turns1 < turns2 or (turns1 == turns2 and len1 <= len2)) else smooth2

    # --- 构造最终连接路径 ---
    final_path = QPainterPath()

    # 添加初始段
    final_path.moveTo(start_pos)
    final_path.lineTo(start_mid)

    # 添加最优路径
    final_path.moveTo(start_mid)
    for pt in optimal[1:]:
        final_path.lineTo(pt)

    # 添加最终段
    final_path.moveTo(end_mid)
    final_path.lineTo(end_pos)

    return final_path
# 为了在 Connection 中调用统一的路径构建方法，
# 这里导入 ConnectionManager（也可以将 build_connection_path 方法移到独立模块中）
# from src.node_system.connection_manager import ConnectionManager
