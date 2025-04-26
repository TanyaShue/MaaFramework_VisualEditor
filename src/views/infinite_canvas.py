import time
from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QLabel, QVBoxLayout,
                               QWidget, QGraphicsItem, QGraphicsRectItem, QGraphicsSceneMouseEvent,
                               QApplication)
from PySide6.QtCore import Qt, QPointF, QRectF, QByteArray, QDataStream, QIODevice, QBuffer, QEvent, QTime
from PySide6.QtGui import QPen, QColor, QBrush, QTransform, QMouseEvent, QWheelEvent, QPainterPath, QKeyEvent

# 导入命令模式实现
from src.canvas_commands import CommandManager, MoveNodesCommand, AddNodeCommand, DeleteNodesCommand, \
    ConnectNodesCommand
# 导入右键菜单实现
from src.canvas_context_menus import ContextMenus
# 导入自定义网格项
from src.node_system.grid_item import GridItem


class EnhancedInfiniteCanvas(QWidget):
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
        self.view.setRenderHint(self.view.renderHints().Antialiasing)

        # 性能优化：使用自定义网格
        self._create_grid()

        self.zoom_factor = 1.15
        # 使用统一的 ConnectionManager 管理连接状态
        from src.node_system.connection_manager import ConnectionManager
        self.connection_manager = ConnectionManager(self.scene, self)

        # 初始化命令管理器
        self.command_manager = CommandManager()

        # 初始化右键菜单
        self.context_menus = ContextMenus(self)

        # 节点列表（连线由 ConnectionManager 管理）
        self.nodes = []

        # 拖动状态跟踪
        self.is_dragging_canvas = False
        self.last_mouse_pos = None
        self.is_dragging_nodes = False

        # 记录拖动开始时的节点位置，用于撤销/重做
        self.drag_start_positions = []

        # 剪贴板
        self.clipboard = []

        # 性能优化：视图更新控制
        self._last_connection_update_time = QTime.currentTime()
        self._last_wheel_time = 0
        self._last_selection = None

        # 添加到布局
        self.layout.addWidget(self.view)

        # 信息栏
        self.info_label = QLabel("拖拽与缩放: 按住右键拖拽画布，滚轮缩放，左键选择/移动节点，双击空白处取消选择")
        self.info_label.setStyleSheet("background-color: #f0f0f0; padding: 5px;")
        self.layout.addWidget(self.info_label)

        # 连接事件
        self._connect_events()

        # 设置焦点策略，使画布可以接收键盘事件
        self.setFocusPolicy(Qt.StrongFocus)
        self.view.setFocusPolicy(Qt.StrongFocus)

        # 将视图与画布关联起来
        self.view.canvas = self

    def _create_grid(self):
        """创建高效的网格背景"""
        self.grid_item = GridItem()
        self.scene.addItem(self.grid_item)

        # 添加视图变化事件以更新网格
        self.view.viewportEvent = self._viewport_event_with_grid_update

    def _viewport_event_with_grid_update(self, event):
        # 对于可能改变视图可见范围的事件，更新网格
        if event.type() in (QEvent.Wheel, QEvent.GraphicsSceneResize):
            if hasattr(self, 'grid_item'):
                self.grid_item.prepareGeometryChange()

        # 调用原始的 viewportEvent 方法
        return QGraphicsView.viewportEvent(self.view, event)

    def _on_selection_changed(self):
        """优化的选择变化处理"""
        # 使用缓存避免重复计算选中项
        if hasattr(self, '_last_selection') and self._last_selection == self.scene.selectedItems():
            return

        self._last_selection = self.scene.selectedItems()
        selected_nodes = [item for item in self._last_selection if isinstance(item, Node)]

        if not selected_nodes:
            self.info_label.setText("拖拽与缩放: 按住右键拖拽画布，滚轮缩放，左键选择/移动节点，双击空白处取消选择")
            return

        node_count = len(selected_nodes)
        # 设置一个阈值，超过此数量时不显示节点ID
        threshold = 3

        if node_count <= threshold:
            # 显示全部节点ID
            node_ids = [node.id for node in selected_nodes]
            self.info_label.setText(f"已选择 {node_count} 个节点: {', '.join(node_ids)}")
        else:
            # 当节点数量较多时，只显示数量，不显示具体节点ID
            self.info_label.setText(f"已选择 {node_count} 个节点")

    def _wheel_event(self, event: QWheelEvent):
        """优化的滚轮事件处理"""
        # 使用时间戳限制缩放频率
        current_time = time.time()
        if hasattr(self, '_last_wheel_time') and current_time - self._last_wheel_time < 0.05:
            # 如果距离上次缩放不到50毫秒，忽略此次事件
            event.accept()
            return

        self._last_wheel_time = current_time

        # 标准缩放处理
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
        super(CustomGraphicsView, self.view).mouseDoubleClickEvent(event)

    def zoom(self, factor):
        """缩放画布"""
        transform = self.view.transform()
        transform.scale(factor, factor)
        scale = transform.m11()
        if 0.1 <= scale <= 5.0:
            self.view.setTransform(transform)
            self.info_label.setText(f"缩放级别: {scale:.2f}x")

            # 更新网格显示
            if hasattr(self, 'grid_item'):
                self.grid_item.prepareGeometryChange()

    def pan(self, x, y):
        """平移画布"""
        self.view.horizontalScrollBar().setValue(self.view.horizontalScrollBar().value() - x)
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().value() - y)

        # 更新网格显示
        if hasattr(self, 'grid_item'):
            self.grid_item.prepareGeometryChange()

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

        # 添加到连接管理器的节点映射表中
        if hasattr(self.connection_manager, 'node_connection_map'):
            self.connection_manager.node_connection_map[node] = []

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

        # 更新网格
        if hasattr(self, 'grid_item'):
            self.grid_item.prepareGeometryChange()

    def clear(self):
        """清空画布：移除所有连接和节点，并重置视图"""
        for connection in self.connection_manager.connections[:]:
            self.connection_manager.remove_connection(connection)

        for node in self.nodes[:]:
            self.remove_node(node)

        self.view.resetTransform()
        self.view.centerOn(0, 0)

        # 清空撤销/重做栈
        self.command_manager = CommandManager()

        # 重置连接管理器的节点映射表
        if hasattr(self.connection_manager, 'node_connection_map'):
            self.connection_manager.node_connection_map.clear()

    def _cancel_connection(self):
        """取消当前连接操作，委托给 ConnectionManager"""
        self.connection_manager.cancel_connection()
        self.view.setCursor(Qt.ArrowCursor)
        self.info_label.setText("拖拽与缩放: 按住右键拖拽画布，滚轮缩放，左键选择/移动节点，双击空白处取消选择")

    def remove_node(self, node):
        """移除节点及其所有相关连接"""
        # 性能优化：使用连接管理器的节点映射表快速查找连接
        connections_to_remove = []

        # 从节点映射表中查找连接
        if hasattr(self.connection_manager,
                   'node_connection_map') and node in self.connection_manager.node_connection_map:
            connections_to_remove.extend(self.connection_manager.node_connection_map[node])
            # 从映射表中移除节点
            del self.connection_manager.node_connection_map[node]
        else:
            # 兼容旧方法：通过端口查找连接
            input_ports = node.get_input_ports() if hasattr(node, 'get_input_ports') else [node.get_input_port()]
            for port in input_ports:
                if port and port.is_connected():
                    connections_to_remove.extend(port.get_connections())

            output_ports = node.get_output_ports()
            if isinstance(output_ports, dict):
                output_ports = list(output_ports.values())
            for port in output_ports:
                connections_to_remove.extend(port.get_connections())

        # 移除所有连接
        for connection in connections_to_remove:
            self.remove_connection(connection)

        # 从场景中移除节点
        self.scene.removeItem(node)

        # 从节点列表中移除
        if node in self.nodes:
            self.nodes.remove(node)

    def _mouse_press_event(self, event: QMouseEvent):
        """优化的鼠标按下事件处理"""
        self.last_mouse_pos = event.position().toPoint()

        # 使用场景坐标的缓存
        scene_pos = self.view.mapToScene(event.position().toPoint())

        # 使用场景项的缓存
        item = self.scene.itemAt(scene_pos, self.view.transform())

        if event.button() == Qt.RightButton:
            # 处理右键点击 - 如果处于连线状态则取消，否则显示上下文菜单
            if self.connection_manager.connecting_port:
                self.connection_manager.cancel_connection()
                event.accept()
                return

            # 获取全局坐标
            global_pos = event.globalPosition().toPoint()

            # 检查是否点击在节点上
            if item and isinstance(item, Node):
                # 显示节点右键菜单
                self.context_menus.show_node_context_menu(item, scene_pos, global_pos)
            else:
                # 显示画布右键菜单
                self.context_menus.show_canvas_context_menu(scene_pos, global_pos)

            event.accept()
            return

        elif event.button() == Qt.LeftButton:
            # 连线状态处理
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

                    # 使用命令模式创建连接
                    connection = self.command_manager.execute(
                        ConnectNodesCommand(source_port, target_port, self)
                    )

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

            # 优化：节点拖拽处理
            if item and isinstance(item, Node):
                # 优化选择和拖拽开始
                selected_nodes = self.get_selected_nodes()

                if not item.isSelected():
                    if not (event.modifiers() & Qt.ControlModifier):
                        self.scene.clearSelection()
                    item.setSelected(True)
                    # 重新获取选中节点
                    selected_nodes = self.get_selected_nodes()

                # 建立批量位置捕获
                self.drag_start_positions = []
                for node in selected_nodes:
                    self.drag_start_positions.append((node, node.pos()))

                # 优化拖动状态
                self.is_dragging_nodes = True
                self.view.setDragMode(QGraphicsView.NoDrag)
                self.view.setCursor(Qt.ClosedHandCursor)

                # 缓存预期被修改的连接 (性能优化)
                self._connections_to_update = set()
                for node in selected_nodes:
                    if hasattr(self.connection_manager,
                               'node_connection_map') and node in self.connection_manager.node_connection_map:
                        self._connections_to_update.update(self.connection_manager.node_connection_map[node])

                event.accept()
                return
            else:
                self.is_dragging_nodes = False
                self.view.setDragMode(QGraphicsView.RubberBandDrag)

        # 默认处理
        super(CustomGraphicsView, self.view).mousePressEvent(event)

    def _mouse_move_event(self, event: QMouseEvent):
        """优化的鼠标移动事件处理，减少连接更新频率"""
        current_pos = event.position().toPoint()

        # 如果在连接状态，优化临时连接线的更新
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

            # 性能优化：使用连接管理器的优化方法
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

            # 更新网格
            if hasattr(self, 'grid_item'):
                self.grid_item.prepareGeometryChange()

            event.accept()
            return

        elif self.is_dragging_nodes and self.last_mouse_pos:
            old_scene_pos = self.view.mapToScene(self.last_mouse_pos)
            new_scene_pos = self.view.mapToScene(current_pos)
            delta = new_scene_pos - old_scene_pos

            # 移动所有选中的节点
            nodes_to_update = self.get_selected_nodes()
            for node in nodes_to_update:
                node.moveBy(delta.x(), delta.y())

            # 性能优化：只在拖动过程中定期更新连接，而不是每次鼠标移动都更新
            current_time = QTime.currentTime()
            time_since_last_update = self._last_connection_update_time.msecsTo(current_time)

            # 每100毫秒更新一次连接
            if time_since_last_update > 100:
                # 使用批量更新方法，如果可用
                if hasattr(self.connection_manager, 'batch_update_connections'):
                    self.connection_manager.batch_update_connections(nodes_to_update)
                else:
                    # 回退到逐个更新
                    for node in nodes_to_update:
                        self.connection_manager.update_connections_for_node(node)

                self._last_connection_update_time = current_time

            self.last_mouse_pos = current_pos
            event.accept()
            return

        else:
            super(CustomGraphicsView, self.view).mouseMoveEvent(event)
            self.last_mouse_pos = current_pos

    def _mouse_release_event(self, event: QMouseEvent):
        """优化的鼠标释放事件处理"""
        if self.connection_manager.connecting_port and event.button() == Qt.LeftButton:
            event.accept()
            return

        # 如果是节点拖拽操作结束，记录新位置并创建撤销命令
        if self.is_dragging_nodes and event.button() == Qt.LeftButton and self.drag_start_positions:
            nodes = []
            old_positions = []
            new_positions = []

            for node, start_pos in self.drag_start_positions:
                if node in self.nodes:  # 确保节点仍然有效
                    nodes.append(node)
                    old_positions.append(start_pos)

                    # 获取当前位置并对齐到网格
                    current_pos = node.pos()
                    grid_size = 20
                    snapped_x = round(current_pos.x() / grid_size) * grid_size
                    snapped_y = round(current_pos.y() / grid_size) * grid_size

                    # 设置对齐后的位置
                    node.setPos(snapped_x, snapped_y)
                    new_positions.append(QPointF(snapped_x, snapped_y))

            # 性能优化：拖动结束时进行一次全面更新
            if hasattr(self.connection_manager, 'batch_update_connections'):
                self.connection_manager.batch_update_connections(nodes)
            else:
                # 回退到逐个更新
                for node in nodes:
                    self.connection_manager.update_connections_for_node(node)

            # 如果有实际的移动，创建撤销命令
            if nodes and any(op != np for op, np in zip(old_positions, new_positions)):
                self.command_manager.execute(
                    MoveNodesCommand(nodes, old_positions, new_positions, self)
                )

            # 清空拖动相关状态
            self.drag_start_positions = []
            if hasattr(self, '_connections_to_update'):
                delattr(self, '_connections_to_update')

        self.is_dragging_canvas = False
        self.is_dragging_nodes = False
        self.view.setCursor(Qt.ArrowCursor)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        super(CustomGraphicsView, self.view).mouseReleaseEvent(event)

        # 更新视图
        self.view.viewport().update()

        # 重置连接更新计时器
        if hasattr(self, '_last_connection_update_time'):
            self._last_connection_update_time = QTime.currentTime()

        # 更新选择状态显示
        self._on_selection_changed()

    def _key_press_event(self, event: QKeyEvent):
        """处理键盘按键事件"""
        # 处理Ctrl+Z (撤销)
        if event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
            if self.command_manager.undo():
                self.info_label.setText("已撤销上一操作")
            else:
                self.info_label.setText("没有可撤销的操作")
            event.accept()
            return

        # 处理Ctrl+Y (重做)
        elif event.key() == Qt.Key_Y and event.modifiers() & Qt.ControlModifier:
            if self.command_manager.redo():
                self.info_label.setText("已重做操作")
            else:
                self.info_label.setText("没有可重做的操作")
            event.accept()
            return

        # 处理Ctrl+C (复制)
        elif event.key() == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
            selected_nodes = self.get_selected_nodes()
            if selected_nodes:
                self.context_menus._copy_nodes(selected_nodes)
                event.accept()
                return

        # 处理Ctrl+V (粘贴)
        elif event.key() == Qt.Key_V and event.modifiers() & Qt.ControlModifier:
            if hasattr(self, 'clipboard') and self.clipboard:
                # 获取视图中心作为粘贴位置
                center = self.view.mapToScene(self.view.viewport().rect().center())
                self.context_menus._paste_nodes(center)
                event.accept()
                return

        # 处理Delete (删除)
        elif event.key() == Qt.Key_Delete:
            selected_nodes = self.get_selected_nodes()
            if selected_nodes:
                self.context_menus._delete_nodes(selected_nodes)
                event.accept()
                return

        # 处理Ctrl+A (全选)
        elif event.key() == Qt.Key_A and event.modifiers() & Qt.ControlModifier:
            self.context_menus._select_all_nodes()
            event.accept()
            return

        # 处理方向键 (微调选中节点位置)
        elif event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            selected_nodes = self.get_selected_nodes()
            if selected_nodes:
                # 记录原始位置
                old_positions = [node.pos() for node in selected_nodes]

                # 计算移动增量
                dx, dy = 0, 0
                step = 1  # 普通步长

                # 按住Shift时使用更大步长
                if event.modifiers() & Qt.ShiftModifier:
                    step = 10

                # 确定移动方向
                if event.key() == Qt.Key_Left:
                    dx = -step
                elif event.key() == Qt.Key_Right:
                    dx = step
                elif event.key() == Qt.Key_Up:
                    dy = -step
                elif event.key() == Qt.Key_Down:
                    dy = step

                # 执行移动
                new_positions = []
                for node in selected_nodes:
                    current_pos = node.pos()
                    new_pos = QPointF(current_pos.x() + dx, current_pos.y() + dy)
                    node.setPos(new_pos)
                    new_positions.append(new_pos)

                # 性能优化：批量更新连接
                if hasattr(self.connection_manager, 'batch_update_connections'):
                    self.connection_manager.batch_update_connections(selected_nodes)
                else:
                    # 回退到逐个更新
                    for node in selected_nodes:
                        self.connection_manager.update_connections_for_node(node)

                # 创建撤销命令
                self.command_manager.execute(
                    MoveNodesCommand(selected_nodes, old_positions, new_positions, self)
                )

                event.accept()
                return

        # 如果没有处理，则传递给父类
        super().keyPressEvent(event)

    def _connect_events(self):
        """绑定视图和场景事件"""
        self.view.wheelEvent = self._wheel_event
        self.view.mousePressEvent = self._mouse_press_event
        self.view.mouseMoveEvent = self._mouse_move_event
        self.view.mouseReleaseEvent = self._mouse_release_event
        self.view.mouseDoubleClickEvent = self._mouse_double_click_event
        self.keyPressEvent = self._key_press_event  # 添加键盘事件
        self.scene.selectionChanged.connect(self._on_selection_changed)

    def get_state(self):
        """优化的画布状态获取方法"""
        try:
            # 捕获缩放和位置
            transform = self.view.transform()
            center = self.view.mapToScene(self.view.viewport().rect().center())

            # 构建节点映射以便更快地访问
            node_map = {node.id: node for node in self.nodes if hasattr(node, 'id')}

            # 收集所有节点信息 - 使用更直接的方法
            nodes_data = []
            for node in self.nodes:
                if not hasattr(node, 'id') or not hasattr(node, 'title'):
                    continue  # 跳过无效节点

                # 基本节点数据
                node_data = {
                    'id': node.id,
                    'title': node.title,
                    'position': {'x': node.pos().x(), 'y': node.pos().y()}
                }

                # 获取节点属性（如果有）
                if hasattr(node, 'get_properties') and callable(node.get_properties):
                    node_data['properties'] = node.get_properties()

                # 获取节点类型（如果有）
                if hasattr(node, 'node_type'):
                    node_data['node_type'] = node.node_type

                nodes_data.append(node_data)

            # 收集所有连接信息 - 使用更直接的方法
            connections_data = []
            for conn in self.connection_manager.connections:
                # 直接获取源端口和目标端口
                source_port = conn.start_port if hasattr(conn, 'start_port') else None
                target_port = conn.end_port if hasattr(conn, 'end_port') else None

                # 跳过无效连接
                if not source_port or not target_port:
                    continue

                # 获取父节点
                source_node = getattr(source_port, 'parent_node', None)
                target_node = getattr(target_port, 'parent_node', None)

                # 跳过无效节点
                if not source_node or not target_node or not hasattr(source_node, 'id') or not hasattr(target_node,
                                                                                                       'id'):
                    continue

                # 构建连接数据
                conn_data = {
                    'source_node_id': source_node.id,
                    'source_port_type': getattr(source_port, 'port_type', 'output'),
                    'source_port_name': getattr(source_port, 'port_name', ''),
                    'target_node_id': target_node.id,
                    'target_port_type': getattr(target_port, 'port_type', 'input'),
                    'target_port_name': getattr(target_port, 'port_name', '')
                }
                connections_data.append(conn_data)

            # 返回状态数据
            return {
                'transform': {
                    'scale_x': transform.m11(),
                    'scale_y': transform.m22(),
                    'dx': transform.dx(),
                    'dy': transform.dy()
                },
                'center': {'x': center.x(), 'y': center.y()},
                'nodes': nodes_data,
                'connections': connections_data
            }
        except Exception as e:
            print(f"获取画布状态时出错: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return {
                'transform': {'scale_x': 1.0, 'scale_y': 1.0, 'dx': 0, 'dy': 0},
                'center': {'x': 0, 'y': 0},
                'nodes': [],
                'connections': []
            }

    def restore_state(self, state):
        """优化的画布状态恢复方法"""
        # 首先清除当前内容
        self.clear()

        # 从状态数据创建节点工厂函数
        def create_node_from_data(node_data):
            try:
                # 创建基本节点
                node = Node(
                    id=node_data['id'],
                    title=node_data['title']
                )

                # 设置节点位置
                if 'position' in node_data:
                    pos = node_data['position']
                    node.setPos(pos['x'], pos['y'])

                # 设置节点类型（如果有）
                if 'node_type' in node_data and hasattr(node, 'node_type'):
                    node.node_type = node_data['node_type']

                # 设置节点属性（如果有）
                if 'properties' in node_data and hasattr(node, 'set_properties'):
                    node.set_properties(node_data['properties'])

                return node
            except Exception as e:
                print(f"无法创建节点 {node_data.get('id', 'unknown')}: {str(e)}")
                return None

        # 创建所有节点
        node_map = {}  # 映射节点ID到实例

        # 批量创建节点
        for node_data in state.get('nodes', []):
            node = create_node_from_data(node_data)
            if node:
                self.add_node(node)
                node_map[node_data['id']] = node

        # 延迟创建连接，以确保所有节点都已经创建
        def create_connections():
            # 批量创建连接
            for conn_data in state.get('connections', []):
                source_node_id = conn_data.get('source_node_id')
                target_node_id = conn_data.get('target_node_id')

                if source_node_id in node_map and target_node_id in node_map:
                    source_node = node_map[source_node_id]
                    target_node = node_map[target_node_id]

                    # 获取端口
                    source_port = None
                    source_port_name = conn_data.get('source_port_name', '')

                    if source_port_name and hasattr(source_node, 'get_output_port'):
                        source_port = source_node.get_output_port(source_port_name)
                    elif hasattr(source_node, 'get_output_ports'):
                        # 获取默认输出端口
                        output_ports = source_node.get_output_ports()
                        if isinstance(output_ports, dict) and output_ports:
                            source_port = next(iter(output_ports.values()))
                        elif isinstance(output_ports, list) and output_ports:
                            source_port = output_ports[0]

                    target_port = None
                    target_port_name = conn_data.get('target_port_name', '')

                    if target_port_name and hasattr(target_node, 'get_input_port'):
                        target_port = target_node.get_input_port(target_port_name)
                    elif hasattr(target_node, 'get_input_port'):
                        target_port = target_node.get_input_port()

                    # 创建连接
                    if source_port and target_port:
                        self.command_manager.execute(
                            ConnectNodesCommand(source_port, target_port, self)
                        )

        # 恢复变换（缩放和位置）
        if 'transform' in state:
            t = state['transform']
            self.view.resetTransform()
            self.view.scale(t['scale_x'], t['scale_y'])
            self.view.translate(t['dx'], t['dy'])
        elif 'center' in state:
            # 如果没有变换信息但有中心点，使用中心点
            center = state['center']
            self.view.centerOn(center['x'], center['y'])

        # 批量创建连接
        create_connections()

        # 更新网格
        if hasattr(self, 'grid_item'):
            self.grid_item.prepareGeometryChange()


# 自定义视图类，用于自定义橡皮筋选择框和实现视图优化
class CustomGraphicsView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.canvas = None  # 会被EnhancedInfiniteCanvas设置
        self.rubberBandColor = QColor(100, 100, 100, 100)  # 半透明灰色
        self.rubberBandBorderColor = QColor(60, 60, 60, 150)  # 稍深的灰色边框

        # 设置渲染提示
        self.setOptimizationFlags(QGraphicsView.DontAdjustForAntialiasing |
                                  QGraphicsView.DontSavePainterState)
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)

        # 设置缓存模式
        self.setCacheMode(QGraphicsView.CacheBackground)

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

    # 优化：只绘制可见区域内的项目
    def paintEvent(self, event):
        """优化场景绘制，只渲染可见项目"""
        # 获取可见场景矩形
        visible_rect = self.mapToScene(self.viewport().rect()).boundingRect()

        # 稍微扩大一点以包含部分可见的项目
        margin = 100
        culling_rect = visible_rect.adjusted(-margin, -margin, margin, margin)

        # 存储原始场景矩形
        original_rect = self.scene().sceneRect()

        # 临时设置场景矩形为可见区域，以提高渲染效率
        self.scene().setSceneRect(culling_rect)

        # 绘制场景
        super().paintEvent(event)

        # 恢复原始场景矩形
        self.scene().setSceneRect(original_rect)


# 此处需要导入Node类，确保代码能够正确运行
from src.node_system.node import Node
from src.node_system.port import OutputPort, InputPort