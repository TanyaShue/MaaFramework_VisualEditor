from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPen, QColor, QBrush, QMouseEvent, QWheelEvent, QKeyEvent
from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QLabel, QVBoxLayout,
                               QWidget, QGraphicsRectItem)

# 导入命令模式实现
from src.canvas_commands import CommandManager, MoveNodesCommand, ConnectNodesCommand
# 导入右键菜单实现
from src.canvas_context_menus import ContextMenus
from src.node_system.canvas_node_manager import CanvasNodeManager
# 导入节点系统
from src.node_system.node import Node
from src.node_system.port import OutputPort, InputPort


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
        self.view.setDragMode(QGraphicsView.NoDrag)  # 默认为不拖拽模式，只有按Ctrl时才框选
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setRubberBandSelectionMode(Qt.IntersectsItemShape)  # 交叉选择
        self.view.setRenderHint(self.view.renderHints().Antialiasing)

        # 绘制网格
        self._create_grid()

        self.zoom_factor = 1.15

        # 使用统一的 ConnectionManager 管理连接状态
        from src.node_system.connection_manager import ConnectionManager
        self.connection_manager = ConnectionManager(self.scene, self)

        # 初始化命令管理器
        self.command_manager = CommandManager()

        # 初始化节点管理器 - 这应该在connection_manager初始化之后
        self.node_manager = CanvasNodeManager(self, self.scene)

        # 初始化右键菜单
        self.context_menus = ContextMenus(self)

        # 拖动状态跟踪
        self.is_dragging_canvas = False
        self.last_mouse_pos = None
        self.is_dragging_nodes = False

        # 记录拖动开始时的节点位置，用于撤销/重做
        self.drag_start_positions = []

        # 剪贴板
        self.clipboard = []

        # 添加到布局
        self.layout.addWidget(self.view)

        # 信息栏
        self.info_label = QLabel(
            "拖拽与缩放: 左键拖拽画布或节点，滚轮缩放，按住Ctrl+左键框选，双击空白处取消选择，右键显示菜单")
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
        # 更新节点管理器的选择状态并获取选中的节点信息
        self.node_manager.update_from_scene_selection()
        selected_nodes = self.node_manager.get_selected_nodes()

        # 更新信息标签显示
        if not selected_nodes:
            self.info_label.setText(
                "拖拽与缩放: 左键拖拽画布或节点，滚轮缩放，按住Ctrl+左键框选，双击空白处取消选择，右键显示菜单")
            return

        node_count = len(selected_nodes)
        threshold = 3

        if node_count <= threshold:
            # 显示全部节点ID
            node_ids = [node.id for node in selected_nodes]
            self.info_label.setText(f"已选择 {node_count} 个节点: {', '.join(node_ids)}")
        else:
            # 当节点数量较多时，只显示数量
            self.info_label.setText(f"已选择 {node_count} 个节点")

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

            if item and isinstance(item, Node):
                # 先关闭所有已打开的节点
                self.node_manager.close_all_nodes()
                # 打开当前节点（设置蓝色边框）
                self.node_manager.set_node_open(item, True)
                self.info_label.setText(f"已打开节点: {item.id}")
                event.accept()
                return
            elif not item:
                # 空白区域双击，清除选择
                self.scene.clearSelection()
                self.info_label.setText(
                    "拖拽与缩放: 左键拖拽画布或节点，滚轮缩放，按住Ctrl+左键框选，双击空白处取消选择，右键显示菜单")
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

    def pan(self, x, y):
        """平移画布"""
        self.view.horizontalScrollBar().setValue(self.view.horizontalScrollBar().value() - x)
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().value() - y)

    # 委托给节点管理器的简化方法
    def add_node(self, node):
        """添加节点到场景，委托给节点管理器"""
        return self.node_manager.add_node(node)

    def remove_node(self, node):
        """移除节点，委托给节点管理器"""
        self.node_manager.remove_node(node)

    def get_selected_nodes(self):
        """获取选中的节点，委托给节点管理器"""
        return self.node_manager.get_selected_nodes()
    def get_open_nodes(self):
        """获取选中的节点，委托给节点管理器"""
        return self.node_manager.get_open_nodes()

    def center_on_content(self):
        """将视图居中显示所有内容"""
        if self.node_manager.nodes:
            rect = QRectF()
            for node in self.node_manager.nodes:
                rect = rect.united(node.sceneBoundingRect())
            rect.adjust(-100, -100, 100, 100)
            self.view.fitInView(rect, Qt.KeepAspectRatio)
        else:
            self.view.centerOn(0, 0)

    def clear(self):
        """清空画布：移除所有连接和节点，并重置视图"""
        # 使用节点管理器清除节点
        self.node_manager.clear()

        # 清除连接
        self.connection_manager.clear_all_connections()

        # 重置视图
        self.view.resetTransform()
        self.view.centerOn(0, 0)

        # 清空撤销/重做栈
        self.command_manager = CommandManager()

    def _cancel_connection(self):
        """取消当前连接操作，委托给ConnectionManager"""
        self.connection_manager.cancel_connection()
        self.view.setCursor(Qt.ArrowCursor)
        self.info_label.setText(
            "拖拽与缩放: 左键拖拽画布或节点，滚轮缩放，按住Ctrl+左键框选，双击空白处取消选择，右键显示菜单")

    def _create_node_context_menu(self, node, global_pos):
        """创建节点右键菜单"""
        # 委托给context_menus处理
        self.context_menus.show_node_context_menu(node, global_pos)

    def _mouse_press_event(self, event: QMouseEvent):
        """处理鼠标按下事件，整合节点拖拽与连线操作"""
        self.last_mouse_pos = event.position().toPoint()

        if event.button() == Qt.RightButton:
            # 处理右键点击 - 如果处于连线状态则取消，否则显示上下文菜单
            if self.connection_manager.connecting_port:
                self.connection_manager.cancel_connection()
                event.accept()
                return

            # 获取点击位置的场景坐标和全局坐标
            scene_pos = self.view.mapToScene(event.position().toPoint())
            global_pos = event.globalPosition().toPoint()

            # 检查是否点击在节点上
            item = self.scene.itemAt(scene_pos, self.view.transform())

            if item and isinstance(item, Node):
                # 显示节点右键菜单
                if not item.isSelected():
                    # 如果节点未被选中，先选中它再显示菜单
                    self.scene.clearSelection()
                    item.setSelected(True)
                    self.node_manager.update_from_scene_selection()

                self._create_node_context_menu(item, global_pos)
            else:
                # 显示画布右键菜单
                self.context_menus.show_canvas_context_menu(scene_pos, global_pos)

            event.accept()
            return

        elif event.button() == Qt.LeftButton:
            scene_pos = self.view.mapToScene(event.position().toPoint())
            item = self.scene.itemAt(scene_pos, self.view.transform())

            # 如果按下了Ctrl键，启用框选模式
            if event.modifiers() & Qt.ControlModifier:
                self.view.setDragMode(QGraphicsView.RubberBandDrag)
                super(CustomGraphicsView, self.view).mousePressEvent(event)
                return

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

                # 如果找到了合适的目标端口并且可以连接，则检查是否已存在连接
                if target_port and self.connection_manager.connecting_port.can_connect(target_port):
                    # 保存当前输出端口，避免后续操作后状态被清空
                    source_port = self.connection_manager.connecting_port

                    # 检查是否已存在连接
                    existing_connection = self.connection_manager.find_connection(source_port, target_port)

                    if existing_connection:
                        # 如果存在连接，使用命令管理器执行断开命令
                        from src.canvas_commands import DisconnectNodesCommand

                        self.command_manager.execute(
                            DisconnectNodesCommand(existing_connection, self)
                        )

                        port_name = getattr(target_port, "port_name", "输入")
                        self.info_label.setText(
                            f"已移除从 {source_port.parent_node.id} 到 {target_port.parent_node.id} 的 {port_name} 连接"
                        )
                        # 取消当前连线操作
                        self.connection_manager.cancel_connection()
                    else:
                        # 如果不存在连接，使用命令模式创建
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
                # 存储拖动开始前所有选中节点的位置
                selected_nodes = self.get_selected_nodes()

                if not item.isSelected():
                    if not (event.modifiers() & Qt.ControlModifier):
                        self.scene.clearSelection()
                    item.setSelected(True)
                    self.node_manager.update_from_scene_selection()
                    selected_nodes = self.get_selected_nodes()

                # 记录拖动开始位置
                self.drag_start_positions = [(node, node.pos()) for node in selected_nodes]

                # 设置拖动状态
                self.is_dragging_nodes = True
                self.view.setDragMode(QGraphicsView.NoDrag)
                self.view.setCursor(Qt.ClosedHandCursor)
                event.accept()
                return
            else:
                # 空白处点击，清除选择并开始拖动画布
                self.is_dragging_nodes = False
                self.is_dragging_canvas = True
                self.view.setDragMode(QGraphicsView.NoDrag)
                self.scene.clearSelection()
                self.node_manager.update_from_scene_selection()
                self.view.setCursor(Qt.OpenHandCursor)
                event.accept()
                return
        else:
            super(CustomGraphicsView, self.view).mousePressEvent(event)

    def _mouse_move_event(self, event: QMouseEvent):
        """处理鼠标移动事件，并处理拖拽操作"""
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

        # 处理画布拖动
        if self.is_dragging_canvas and self.last_mouse_pos:
            delta = current_pos - self.last_mouse_pos
            self.view.horizontalScrollBar().setValue(
                self.view.horizontalScrollBar().value() - delta.x()
            )
            self.view.verticalScrollBar().setValue(
                self.view.verticalScrollBar().value() - delta.y()
            )
            self.view.setCursor(Qt.ClosedHandCursor)  # 改变光标为抓取状态
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

        # 如果是节点拖拽操作结束，记录新位置并创建撤销命令
        if self.is_dragging_nodes and event.button() == Qt.LeftButton and self.drag_start_positions:
            nodes = []
            old_positions = []
            new_positions = []

            for node, start_pos in self.drag_start_positions:
                if node in self.node_manager.nodes:  # 确保节点仍然有效
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

                    # 更新连接
                    self.connection_manager.update_connections_for_node(node)

            # 如果有实际的移动，创建撤销命令
            if nodes and any(op != np for op, np in zip(old_positions, new_positions)):
                self.command_manager.execute(
                    MoveNodesCommand(nodes, old_positions, new_positions, self)
                )

            # 清空拖动开始位置记录
            self.drag_start_positions = []

        # 处理画布拖动结束
        if self.is_dragging_canvas and event.button() == Qt.LeftButton:
            self.view.setCursor(Qt.ArrowCursor)

        # 如果是框选操作结束，恢复为默认拖动模式
        if event.modifiers() & Qt.ControlModifier and self.view.dragMode() == QGraphicsView.RubberBandDrag:
            self.view.setDragMode(QGraphicsView.NoDrag)

        self.is_dragging_canvas = False
        self.is_dragging_nodes = False
        self.view.setCursor(Qt.ArrowCursor)
        self.view.setDragMode(QGraphicsView.NoDrag)  # 恢复默认模式
        super(CustomGraphicsView, self.view).mouseReleaseEvent(event)

        self.view.viewport().update()

        # 更新选择状态和信息标签
        self._update_selection_info()

    def _update_selection_info(self):
        """更新信息栏中的选择信息"""
        selected_nodes = self.node_manager.get_selected_nodes()
        if selected_nodes:
            node_count = len(selected_nodes)
            threshold = 3

            if node_count <= threshold:
                # 显示全部节点ID
                node_ids = [node.id for node in selected_nodes]
                self.info_label.setText(f"已选择 {node_count} 个节点: {', '.join(node_ids)}")
            else:
                # 当节点数量较多时，只显示数量
                self.info_label.setText(f"已选择 {node_count} 个节点")
        else:
            self.info_label.setText(
                "拖拽与缩放: 左键拖拽画布或节点，滚轮缩放，按住Ctrl+左键框选，双击空白处取消选择，右键显示菜单")

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
        """获取画布的当前状态，委托给节点管理器处理节点部分"""
        try:
            # 捕获缩放和位置
            transform = self.view.transform()
            center = self.view.mapToScene(self.view.viewport().rect().center())

            # 收集所有节点信息和连接信息 - 委托给各自的管理器
            nodes_data = self.node_manager.get_nodes_state()
            connections_data = self.connection_manager.get_connections_state()

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
        """从保存的状态恢复画布，委托给各管理器处理相应部分"""
        # 首先清除当前内容
        self.clear()

        # 恢复节点 - 委托给节点管理器
        node_map = self.node_manager.restore_nodes_state(state.get('nodes', []))

        # 恢复连接 - 委托给连接管理器
        self.connection_manager.restore_connections_state(state.get('connections', []), node_map)

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

    # 节点打开相关的简化方法
    def open_node(self, node):
        """将节点标记为'打开'状态（蓝色边框）"""
        self.node_manager.set_node_open(node, True)

    def close_node(self, node):
        """将节点标记为'关闭'状态（正常边框）"""
        self.node_manager.set_node_open(node, False)

    def toggle_node_open(self, node):
        """切换节点的打开状态"""
        self.node_manager.toggle_node_open(node)

    # 添加文件操作
    def load_file(self, file_path):
        """从文件加载节点"""
        return self.node_manager.load_file(file_path)

    def save_to_file(self, file_path=None):
        """保存节点到文件"""
        return self.node_manager.save_to_file(file_path)


# 自定义视图类，用于自定义橡皮筋选择框
class CustomGraphicsView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.canvas = None  # 会被EnhancedInfiniteCanvas设置
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