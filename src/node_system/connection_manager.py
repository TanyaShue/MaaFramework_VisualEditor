import math

from PySide6.QtGui import QPolygonF
from PySide6.QtCore import QPointF, QRectF, QLineF, Qt
from PySide6.QtGui import QPainterPath
from PySide6.QtGui import QPolygonF
from PySide6.QtWidgets import QGraphicsPathItem

from src.node_system.connection import Connection


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
        NODE_BUFFER = 30  # 边界扩展距离
        tol = 1e-6

        # ------ 基本辅助函数 ------
        def create_boundary_rect(node):
            rect = node.sceneBoundingRect()
            return rect.adjusted(-NODE_BUFFER, -NODE_BUFFER, NODE_BUFFER, NODE_BUFFER)

        def get_ports(node):
            ports = []
            if hasattr(node, 'get_input_port'):
                ip = node.get_input_port()
                if ip:
                    ports.append(ip)
            if hasattr(node, 'get_output_ports'):
                op = node.get_output_ports()
                if isinstance(op, dict):
                    ports.extend(list(op.values()))
                elif isinstance(op, list):
                    ports.extend(op)
            return ports

        def create_default_boundary(pos):
            rect = QRectF(pos.x() - 10, pos.y() - 10, 20, 20)
            return rect.adjusted(-NODE_BUFFER, -NODE_BUFFER, NODE_BUFFER, NODE_BUFFER)

        def get_boundary_midpoint(rect, direction):
            if direction == 'top':
                return QPointF((rect.left() + rect.right()) / 2, rect.top())
            elif direction == 'bottom':
                return QPointF((rect.left() + rect.right()) / 2, rect.bottom())
            elif direction == 'left':
                return QPointF(rect.left(), (rect.top() + rect.bottom()) / 2)
            elif direction == 'right':
                return QPointF(rect.right(), (rect.top() + rect.bottom()) / 2)
            else:
                return QPointF((rect.left() + rect.right()) / 2, (rect.top() + rect.bottom()) / 2)

        def equal_points(p1, p2, tol=tol):
            return abs(p1.x() - p2.x()) < tol and abs(p1.y() - p2.y()) < tol

        def intersect_line(line1, line2):
            # 标准直线交点算法
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
                seg = QLineF(pts[i - 1], pts[i]).length()
                cum.append(cum[-1] + seg)
            return cum

        # ------ 计算所有节点扩展边界及所属节点 ------
        rects = []  # 存储所有扩展边界 (QRectF)
        start_node_rect = None
        end_node_rect = None
        if scene:
            for item in scene.items():
                if hasattr(item, '__class__') and item.__class__.__name__ == 'Node':
                    r = create_boundary_rect(item)
                    rects.append(r)
                    ports = get_ports(item)
                    if start_port in ports:
                        start_node_rect = r
                    if end_port in ports:
                        end_node_rect = r
        start_pos = start_port.mapToScene(QPointF(0, 0))
        end_pos = end_port.mapToScene(QPointF(0, 0))
        if start_node_rect is None:
            start_node_rect = create_default_boundary(start_pos)
        if end_node_rect is None:
            end_node_rect = create_default_boundary(end_pos)

        # ------ 合并重叠边界（用于交点检测）------
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
                remaining = []
                for other in paths:
                    if current.intersects(other):
                        current = current.united(other)
                        merged = True
                    else:
                        remaining.append(other)
                paths = remaining
            merged_paths.append(current)
        # merged_paths 中的每个 QPainterPath 的多边形用于后续交点检测

        # ------ 计算边界中点 ------
        start_mid = get_boundary_midpoint(start_node_rect, start_port.direction)
        end_mid = get_boundary_midpoint(end_node_rect, end_port.direction)

        # ------ 构造候选路径（中间部分）------
        # 候选路径1：先水平，再垂直
        candidate1_pts = [start_mid, QPointF(end_mid.x(), start_mid.y()), end_mid]
        # 候选路径2：先垂直，再水平
        candidate2_pts = [start_mid, QPointF(start_mid.x(), end_mid.y()), end_mid]

        # ------ 交点计算与替换处理 ------
        def compute_intersections_for_boundary(candidate_pts, boundary):
            """
            对 candidate_pts 与 boundary（由 QPainterPath.toFillPolygon() 得到的多边形）
            计算交点，返回列表 [(t, point), ...]，其中 t 为候选路径上累计距离参数。
            注意：如果候选段与边界边共线，则跳过（共线部分不处理）。
            """
            poly = boundary.toFillPolygon()
            intersections = []
            cum = get_cumulative_lengths(candidate_pts)
            for i in range(len(candidate_pts) - 1):
                seg_line = QLineF(candidate_pts[i], candidate_pts[i + 1])
                seg_len = seg_line.length()
                horizontal_seg = abs(candidate_pts[i].y() - candidate_pts[i + 1].y()) < tol
                vertical_seg = abs(candidate_pts[i].x() - candidate_pts[i + 1].x()) < tol
                for j in range(poly.count()):
                    q1 = poly.at(j)
                    q2 = poly.at((j + 1) % poly.count())
                    edge_line = QLineF(q1, q2)
                    if horizontal_seg and abs(q1.y() - q2.y()) < tol:
                        continue
                    if vertical_seg and abs(q1.x() - q2.x()) < tol:
                        continue
                    found, ipt = intersect_line(QLineF(candidate_pts[i], candidate_pts[i + 1]),
                                                QLineF(q1, q2))
                    if found and ipt is not None:
                        frac = QLineF(candidate_pts[i], ipt).length() / seg_len if seg_len > 0 else 0
                        t = cum[i] + frac * seg_len
                        if not any(equal_points(ipt, p) for (_, p) in intersections):
                            intersections.append((t, ipt))
            intersections.sort(key=lambda x: x[0])
            return intersections

        def get_shorter_boundary_arc(poly, A, B, tol=tol):
            """
            对于给定多边形 poly (QPolygonF) 和位于其上的两点 A, B，
            查找连接这两点的最短边界路径。
            修复了处理点在同一边上或接近顶点时的问题。
            """
            n = poly.count()

            # 检查点是否与顶点接近
            def point_at_vertex(pt):
                for i in range(n):
                    if equal_points(pt, poly.at(i), tol):
                        return i
                return None

            # 查找点在哪条边上
            def find_edge(pt):
                # 先检查是否在顶点上
                vertex_idx = point_at_vertex(pt)
                if vertex_idx is not None:
                    return vertex_idx, "vertex"

                # 再检查在哪条边上
                for i in range(n):
                    p0 = poly.at(i)
                    p1 = poly.at((i + 1) % n)
                    seg = QLineF(p0, p1)
                    if seg.length() < tol:
                        continue

                    # 检查点是否在线段上
                    if abs(QLineF(p0, pt).length() + QLineF(pt, p1).length() - seg.length()) < tol:
                        return i, "edge"

                return None, None

            # 查找A和B的位置
            posA, typeA = find_edge(A)
            posB, typeB = find_edge(B)

            if posA is None or posB is None:
                return [A, B]  # 点不在多边形上

            # 特殊情况：点在同一位置
            if typeA == typeB and posA == posB:
                if typeA == "vertex" or (typeA == "edge" and equal_points(A, B, tol)):
                    return [A, B]

            # 特殊情况：点在同一边上
            if typeA == "edge" and typeB == "edge" and posA == posB:
                return [A, B]  # 直接连接，无需绕行

            # 准备构建路径
            path_cw = [A]  # 顺时针路径
            path_ccw = [A]  # 逆时针路径

            # 顺时针路径构建
            if typeA == "vertex":
                i = posA
            else:  # edge
                path_cw.append(poly.at((posA + 1) % n))
                i = (posA + 1) % n

            while True:
                next_i = (i + 1) % n

                # 检查是否到达B所在位置
                if typeB == "vertex" and i == posB:
                    break
                if typeB == "edge" and i == posB:
                    break

                path_cw.append(poly.at(next_i))
                i = next_i

                # 防止无限循环
                if i == posA:
                    break

            # 确保路径末尾是B
            if not equal_points(path_cw[-1], B, tol):
                path_cw.append(B)

            # 逆时针路径构建
            if typeA == "vertex":
                i = posA
            else:  # edge
                path_ccw.append(poly.at(posA))
                i = posA

            while True:
                prev_i = (i - 1 + n) % n

                # 检查是否到达B所在位置
                if typeB == "vertex" and prev_i == posB:
                    break
                if typeB == "edge" and prev_i == posB:
                    break

                path_ccw.append(poly.at(prev_i))
                i = prev_i

                # 防止无限循环
                if i == posA:
                    break

            # 确保路径末尾是B
            if not equal_points(path_ccw[-1], B, tol):
                path_ccw.append(B)

            # 移除路径中的重复点
            def clean_path(path):
                if len(path) <= 1:
                    return path
                result = [path[0]]
                for pt in path[1:]:
                    if not equal_points(result[-1], pt, tol):
                        result.append(pt)
                return result

            path_cw = clean_path(path_cw)
            path_ccw = clean_path(path_ccw)

            # 计算路径长度并选择较短的
            def path_length(path):
                total = 0
                for i in range(len(path) - 1):
                    total += QLineF(path[i], path[i + 1]).length()
                return total

            len_cw = path_length(path_cw)
            len_ccw = path_length(path_ccw)

            return path_cw if len_cw <= len_ccw else path_ccw

        def replace_candidate_segment(candidate_pts, t1, A, t2, B, replacement_arc):
            """
            将 candidate_pts 中累计参数在 [t1, t2] 内的部分替换为 replacement_arc（点列表），
            返回新的候选路径（不改变原始其余部分）。
            """
            cum = get_cumulative_lengths(candidate_pts)
            i1 = 0
            for i in range(len(cum) - 1):
                if cum[i] <= t1 <= cum[i + 1]:
                    i1 = i
                    break
            i2 = 0
            for i in range(len(cum) - 1):
                if cum[i] <= t2 <= cum[i + 1]:
                    i2 = i
                    break
            new_candidate = candidate_pts[:i1 + 1]
            if not equal_points(new_candidate[-1], A):
                new_candidate.append(A)
            for pt in replacement_arc:
                if not equal_points(new_candidate[-1], pt):
                    new_candidate.append(pt)
            if not equal_points(new_candidate[-1], B):
                new_candidate.append(B)
            new_candidate.extend(candidate_pts[i2 + 1:])
            return new_candidate

        def process_candidate_path(candidate_pts, merged_paths):
            new_candidate = candidate_pts[:]  # 初始候选路径
            for mpath in merged_paths:
                inters = compute_intersections_for_boundary(new_candidate, mpath)
                if len(inters) == 2:
                    (t1, pt1), (t2, pt2) = inters
                    # print("候选路径与某边界交点数=2, 交点: ({:.2f}, {:.2f}) 和 ({:.2f}, {:.2f})".format(
                    #     pt1.x(), pt1.y(), pt2.x(), pt2.y()))
                    poly = mpath.toFillPolygon()
                    arc = get_shorter_boundary_arc(poly, pt1, pt2)
                    new_candidate = replace_candidate_segment(new_candidate, t1, pt1, t2, pt2, arc)
            return new_candidate

        # ------ 对候选路径分别处理替换 ------
        candidate1_final = process_candidate_path(candidate1_pts, merged_paths)
        candidate2_final = process_candidate_path(candidate2_pts, merged_paths)
        # print("处理后候选路径1顶点：")
        # for pt in candidate1_final:
        #     print("  ({:.2f}, {:.2f})".format(pt.x(), pt.y()))
        # print("处理后候选路径2顶点：")
        # for pt in candidate2_final:
        #     print("  ({:.2f}, {:.2f})".format(pt.x(), pt.y()))

        # ------ 构造最终连接路径 ------
        final_path = QPainterPath()
        # 从 start_port 到 start_mid
        final_path.moveTo(start_pos)
        final_path.lineTo(start_mid)
        # 添加候选路径1
        final_path.moveTo(start_mid)
        for pt in candidate1_final[1:]:
            final_path.lineTo(pt)
        # 添加候选路径2
        final_path.moveTo(start_mid)
        for pt in candidate2_final[1:]:
            final_path.lineTo(pt)
        # 从 end_mid 到 end_port
        final_path.moveTo(end_mid)
        final_path.lineTo(end_pos)

        # ------ 调试：将所有合并后的边界也添加到最终路径中 ------
        # boundaries_path = QPainterPath()
        # for mpath in merged_paths:
        #     boundaries_path.addPath(mpath)
        # final_path.addPath(boundaries_path)

        return final_path


