from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QLabel, QVBoxLayout,
                               QWidget, QGraphicsItem, QGraphicsRectItem, QGraphicsSceneMouseEvent)
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPen, QColor, QBrush, QTransform, QMouseEvent, QWheelEvent, QPainterPath

from src.node_system.connection import Connection
from src.node_system.connection_manager import ConnectionManager
from src.node_system.node import Node
from src.node_system.port import OutputPort, InputPort


# 自定义视图类，用于自定义橡皮筋选择框
class CustomGraphicsView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.canvas = None  # 会被InfiniteCanvas设置
        self.rubberBandColor = QColor(100, 100, 100, 100)  # 半透明灰色
        self.rubberBandBorderColor = QColor(60, 60, 60, 150)  # 稍深的灰色边框

    # 重写绘制橡皮筋选择框的方法
    def drawRubberBand(self, painter, rect):
        painter.save()
        # 设置橡皮筋的颜色和样式
        pen = QPen(self.rubberBandBorderColor, 1, Qt.DashLine)
        brush = QBrush(self.rubberBandColor)
        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawRect(rect)
        painter.restore()

class InfiniteCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # 创建场景和视图
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(-10000, -10000, 20000, 20000)  # 大场景区域

        self.view = CustomGraphicsView(self.scene)  # 使用自定义视图
        self.view.setRenderHint(self.view.renderHints().Antialiasing)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)  # 默认为框选模式
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setRubberBandSelectionMode(Qt.IntersectsItemShape)  # 交叉选择

        # 绘制网格
        self._create_grid()

        self.zoom_factor = 1.15
        # 使用统一的 ConnectionManager 管理连接状态
        self.connection_manager = ConnectionManager(self.scene, self)

        # 节点列表（连线由 ConnectionManager 管理）
        self.nodes = []

        # 拖动状态跟踪
        self.is_dragging_canvas = False
        self.last_mouse_pos = None
        self.is_dragging_nodes = False

        # 添加到布局
        self.layout.addWidget(self.view)

        # 信息栏
        self.info_label = QLabel("拖拽与缩放: 按住右键拖拽画布，滚轮缩放，左键选择/移动节点，双击空白处取消选择")
        self.info_label.setStyleSheet("background-color: #f0f0f0; padding: 5px;")
        self.layout.addWidget(self.info_label)

        # 连接事件
        self._connect_events()

        # 添加示例节点
        self._add_example_nodes()

        # 将视图与画布关联起来
        self.view.canvas = self

    def _create_grid(self):
        """创建网格背景"""
        grid_size = 20
        grid_pen_primary = QPen(QColor(200, 200, 200), 0.8)
        grid_pen_secondary = QPen(QColor(230, 230, 230), 0.5)

        for i in range(-10000, 10000, grid_size):
            # 主网格线
            if i % (grid_size * 5) == 0:
                self.scene.addLine(i, -10000, i, 10000, grid_pen_primary)
                self.scene.addLine(-10000, i, 10000, i, grid_pen_primary)
            else:
                self.scene.addLine(i, -10000, i, 10000, grid_pen_secondary)
                self.scene.addLine(-10000, i, 10000, i, grid_pen_secondary)

        # 添加原点标记
        origin_rect = QGraphicsRectItem(-5, -5, 10, 10)
        origin_rect.setPen(QPen(QColor(255, 0, 0), 1))
        origin_rect.setBrush(QBrush(QColor(255, 0, 0, 100)))
        self.scene.addItem(origin_rect)

    def _on_selection_changed(self):
        """处理选择变化事件"""
        selected_items = self.scene.selectedItems()
        selected_nodes = [item for item in selected_items if isinstance(item, Node)]

        if selected_nodes:
            node_ids = [node.id for node in selected_nodes]
            self.info_label.setText(f"已选择 {len(selected_nodes)} 个节点: {', '.join(node_ids)}")
        else:
            self.info_label.setText("拖拽与缩放: 按住右键拖拽画布，滚轮缩放，左键选择/移动节点，双击空白处取消选择")

    def _wheel_event(self, event: QWheelEvent):
        """处理滚轮事件 - 缩放画布"""
        zoom_in = event.angleDelta().y() > 0
        if zoom_in:
            self.zoom(self.zoom_factor)
        else:
            self.zoom(1 / self.zoom_factor)

    def _mouse_double_click_event(self, event: QMouseEvent):
        """处理鼠标双击事件"""
        if event.button() == Qt.LeftButton:
            scene_pos = self.view.mapToScene(event.position().toPoint())
            item = self.scene.itemAt(scene_pos, self.view.transform())
            if not item or not isinstance(item, Node):
                self.scene.clearSelection()
                self.info_label.setText("拖拽与缩放: 按住右键拖拽画布，滚轮缩放，左键选择/移动节点，双击空白处取消选择")
                event.accept()
                return
        super(QGraphicsView, self.view).mouseDoubleClickEvent(event)

    def zoom(self, factor):
        """缩放画布"""
        transform = self.view.transform()
        transform.scale(factor, factor)
        scale = transform.m11()
        if 0.1 <= scale <= 5.0:
            self.view.setTransform(transform)
            self.info_label.setText(f"缩放级别: {scale:.2f}x")

    def pan(self, x, y):
        """平移画布"""
        self.view.horizontalScrollBar().setValue(self.view.horizontalScrollBar().value() - x)
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().value() - y)

    def add_node(self, node):
        """添加节点到场景"""
        self.scene.addItem(node)
        self.nodes.append(node)

        input_port = node.get_input_port()
        if input_port:
            input_port.setParentItem(node)

        output_ports = node.get_output_ports()
        if isinstance(output_ports, dict):
            for output_port in output_ports.values():
                output_port.setParentItem(node)
        else:
            for port in output_ports:
                port.setParentItem(node)

        return node

    def remove_connection(self, connection):
        """移除连接，交由 ConnectionManager 处理"""
        self.connection_manager.remove_connection(connection)

    def get_selected_nodes(self):
        """获取选中的节点"""
        selected_items = self.scene.selectedItems()
        return [item for item in selected_items if isinstance(item, Node)]

    def center_on_content(self):
        """将视图居中显示所有内容"""
        if self.nodes:
            rect = QRectF()
            for node in self.nodes:
                rect = rect.united(node.sceneBoundingRect())
            rect.adjust(-100, -100, 100, 100)
            self.view.fitInView(rect, Qt.KeepAspectRatio)
        else:
            self.view.centerOn(0, 0)

    def _add_example_nodes(self):
        """添加示例节点"""
        recognition_node = Node("recognition_1", "图像识别")
        recognition_node.update_properties({
            "目标图像": "button.png",
            "识别阈值": "0.85",
            "超时时间": "5000ms"
        })
        recognition_node.set_position(-200, -100)
        self.add_node(recognition_node)

        click_node = Node("click_1", "点击操作")
        click_node.update_properties({
            "目标坐标": "(500, 300)",
            "点击类型": "单击",
            "点击次数": "1"
        })
        click_node.set_position(50, -150)
        self.add_node(click_node)

        swipe_node = Node("swipe_1", "滑动操作")
        swipe_node.update_properties({
            "起始坐标": "(200, 500)",
            "结束坐标": "(800, 500)",
            "持续时间": "300ms"
        })
        swipe_node.set_position(-100, 100)
        self.add_node(swipe_node)

        wait_node = Node("wait_1", "等待操作")
        wait_node.update_properties({
            "等待时间": "2000ms",
            "等待类型": "固定时间"
        })
        wait_node.set_position(150, 100)
        self.add_node(wait_node)

        self.center_on_content()

    def clear(self):
        """清空画布：移除所有连接和节点，并重置视图"""
        for connection in self.connection_manager.connections[:]:
            self.connection_manager.remove_connection(connection)

        for node in self.nodes[:]:
            self.remove_node(node)

        self.view.resetTransform()
        self.view.centerOn(0, 0)

    def _cancel_connection(self):
        """取消当前连接操作，委托给 ConnectionManager"""
        self.connection_manager.cancel_connection()
        self.view.setCursor(Qt.ArrowCursor)
        self.info_label.setText("拖拽与缩放: 按住右键拖拽画布，滚轮缩放，左键选择/移动节点，双击空白处取消选择")

    def remove_node(self, node):
        """移除节点及其所有相关连接"""
        connections_to_remove = []

        input_ports = node.get_input_ports() if hasattr(node, 'get_input_ports') else [node.get_input_port()]
        for port in input_ports:
            if port and port.is_connected():
                connections_to_remove.extend(port.get_connections())

        output_ports = node.get_output_ports()
        if isinstance(output_ports, dict):
            output_ports = list(output_ports.values())
        for port in output_ports:
            connections_to_remove.extend(port.get_connections())

        for connection in connections_to_remove:
            self.remove_connection(connection)

        self.scene.removeItem(node)
        if node in self.nodes:
            self.nodes.remove(node)

    def _connect_events(self):
        """绑定视图和场景事件"""
        self.view.wheelEvent = self._wheel_event
        self.view.mousePressEvent = self._mouse_press_event
        self.view.mouseMoveEvent = self._mouse_move_event
        self.view.mouseReleaseEvent = self._mouse_release_event
        self.view.mouseDoubleClickEvent = self._mouse_double_click_event
        self.scene.selectionChanged.connect(self._on_selection_changed)

    def _mouse_press_event(self, event: QMouseEvent):
        """处理鼠标按下事件，整合节点拖拽与连线操作"""
        self.last_mouse_pos = event.position().toPoint()

        if event.button() == Qt.RightButton:
            # 右键：如果处于连线状态则取消，否则拖拽画布
            if self.connection_manager.connecting_port:
                self.connection_manager.cancel_connection()
                event.accept()
                return

            self.is_dragging_canvas = True
            self.view.setDragMode(QGraphicsView.NoDrag)
            self.view.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        elif event.button() == Qt.LeftButton:
            scene_pos = self.view.mapToScene(event.position().toPoint())
            item = self.scene.itemAt(scene_pos, self.view.transform())

            # 如果处于连线状态，则尝试完成连线操作
            if self.connection_manager.connecting_port:
                target_port = None
                target_pos = scene_pos

                # 如果点击的是 Node，则尝试获取其输入端口（支持多输入端口）
                if isinstance(item, Node):
                    input_ports = item.get_input_ports() if hasattr(item, 'get_input_ports') else [
                        item.get_input_port()]
                    for port in input_ports:
                        if port and self.connection_manager.connecting_port.can_connect(port):
                            target_port = port
                            target_pos = target_port.mapToScene(target_port.boundingRect().center())
                            break
                # 如果点击的是 InputPort，则直接使用该端口
                elif isinstance(item, InputPort):
                    target_port = item
                    target_pos = target_port.mapToScene(target_port.boundingRect().center())

                # 更新临时连线路径到目标位置
                self.connection_manager.update_temp_connection(target_pos)

                # 如果找到了合适的目标端口并且可以连接，则完成连线
                if target_port and self.connection_manager.connecting_port.can_connect(target_port):
                    # 保存当前输出端口，避免 finish_connection 后状态被清空
                    source_port = self.connection_manager.connecting_port
                    connection = self.connection_manager.finish_connection(target_port)
                    if connection:
                        port_name = getattr(target_port, "port_name", "输入")
                        self.info_label.setText(
                            f"已创建从 {source_port.parent_node.id} 到 {target_port.parent_node.id} 的 {port_name} 连接"
                        )
                else:
                    # 如果无法连接，则给出提示并取消连线操作
                    self.info_label.setText("无法连接这些端口")
                    self.connection_manager.cancel_connection()

                event.accept()
                return

            # 如果点击的是输出端口，则启动连线操作
            if item and isinstance(item, OutputPort):
                self.connection_manager.start_connection(item)
                port_name = getattr(item, "port_name", item.port_type)
                self.view.setDragMode(QGraphicsView.NoDrag)
                self.view.setCursor(Qt.CrossCursor)
                self.info_label.setText(
                    f"已选择 {item.parent_node.id} 的 {port_name} 输出端口，点击目标节点完成连接"
                )
                event.accept()
                return

            # 否则处理节点的选择与拖拽
            if item and isinstance(item, Node):
                if not item.isSelected():
                    if not (event.modifiers() & Qt.ControlModifier):
                        self.scene.clearSelection()
                    item.setSelected(True)
                else:
                    self.is_dragging_nodes = True
                    self.view.setDragMode(QGraphicsView.NoDrag)
                    self.view.setCursor(Qt.ClosedHandCursor)
                    event.accept()
                    return
                return
            else:
                self.is_dragging_nodes = False
                self.view.setDragMode(QGraphicsView.RubberBandDrag)
                super(CustomGraphicsView, self.view).mousePressEvent(event)
        else:
            super(CustomGraphicsView, self.view).mousePressEvent(event)

    def _mouse_move_event(self, event: QMouseEvent):
        """处理鼠标移动事件，并输出调试信息"""
        current_pos = event.position().toPoint()

        # 如果在连接状态，更新临时连接线
        if self.connection_manager.connecting_port and self.connection_manager.temp_connection:
            scene_pos = self.view.mapToScene(current_pos)

            # 查找鼠标下方的节点或输入端口
            item = self.scene.itemAt(scene_pos, self.view.transform())

            target_port = None
            target_pos = scene_pos

            # 确定目标端口和位置
            if isinstance(item, Node):
                # 获取所有输入端口（要求 Node 类支持多输入端口）
                input_ports = item.get_input_ports() if hasattr(item, 'get_input_ports') else [item.get_input_port()]
                # 找到第一个可连接的输入端口
                for port in input_ports:
                    if port and self.connection_manager.connecting_port.can_connect(port):
                        target_port = port
                        target_pos = target_port.mapToScene(target_port.boundingRect().center())
                        break
            elif isinstance(item, InputPort):
                target_port = item
                target_pos = target_port.mapToScene(target_port.boundingRect().center())

            # 更新临时连线路径到目标位置
            self.connection_manager.update_temp_connection(target_pos)

            # 提供视觉反馈
            if target_port and self.connection_manager.connecting_port.can_connect(target_port):
                node_id = target_port.parent_node.id if hasattr(target_port, 'parent_node') else "未知节点"
                port_name = target_port.port_name if hasattr(target_port, 'port_name') else "输入"
                self.info_label.setText(f"点击连接到 {node_id} 的 {port_name} 端口")
                self.view.setCursor(Qt.DragLinkCursor)
            else:
                if isinstance(item, Node) or isinstance(item, InputPort):
                    self.info_label.setText("无法连接到此节点或端口")
                    self.view.setCursor(Qt.ForbiddenCursor)
                else:
                    self.view.setCursor(Qt.CrossCursor)
                    self.info_label.setText("点击节点完成连接，右键取消")

            event.accept()
            return

        if self.is_dragging_canvas and self.last_mouse_pos:
            delta = current_pos - self.last_mouse_pos
            self.view.horizontalScrollBar().setValue(
                self.view.horizontalScrollBar().value() - delta.x()
            )
            self.view.verticalScrollBar().setValue(
                self.view.verticalScrollBar().value() - delta.y()
            )
            self.last_mouse_pos = current_pos
            event.accept()
            return

        elif self.is_dragging_nodes and self.last_mouse_pos:
            old_scene_pos = self.view.mapToScene(self.last_mouse_pos)
            new_scene_pos = self.view.mapToScene(current_pos)
            delta = new_scene_pos - old_scene_pos

            for node in self.get_selected_nodes():
                node.moveBy(delta.x(), delta.y())
                # 实时更新所有与该节点相关的连接
                self.connection_manager.update_connections_for_node(node)

            self.last_mouse_pos = current_pos
            event.accept()
            return

        else:
            super(CustomGraphicsView, self.view).mouseMoveEvent(event)
            self.last_mouse_pos = current_pos

    def _mouse_release_event(self, event: QMouseEvent):
        """处理鼠标释放事件"""
        if self.connection_manager.connecting_port and event.button() == Qt.LeftButton:
            event.accept()
            return

        self.is_dragging_canvas = False
        self.is_dragging_nodes = False
        self.view.setCursor(Qt.ArrowCursor)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        super(CustomGraphicsView, self.view).mouseReleaseEvent(event)

        # 节点吸附到网格
        grid_size = 20
        for node in self.get_selected_nodes():
            pos = node.pos()
            snapped_x = round(pos.x() / grid_size) * grid_size
            snapped_y = round(pos.y() / grid_size) * grid_size
            node.setPos(snapped_x, snapped_y)
            self.connection_manager.update_connections_for_node(node)

        self.view.viewport().update()
        selected_nodes = [item for item in self.scene.selectedItems() if isinstance(item, Node)]
        if selected_nodes:
            node_ids = [node.id for node in selected_nodes]
            self.info_label.setText(f"已选择 {len(selected_nodes)} 个节点: {', '.join(node_ids)}")
        else:
            self.info_label.setText("拖拽与缩放: 按住右键拖拽画布，滚轮缩放，左键选择/移动节点，双击空白处取消选择")
