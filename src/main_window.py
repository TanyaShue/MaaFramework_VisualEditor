import os

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QMainWindow, QDockWidget, QStatusBar, QToolBar,
                               QWidget, QLabel, QPushButton, QHBoxLayout,
                               QMessageBox, QFileDialog)
from PySide6.QtCore import Qt, Slot, QTimer

from src.views.infinite_canvas import EnhancedInfiniteCanvas
# 导入增强的InfiniteCanvas而不是原始版本
from src.views.node_properties_editor import NodePropertiesEditor
from src.views.node_library import NodeLibrary
from .canvas_commands import ConnectNodesCommand
from .config_manager import ConfigManager, config_manager
from .maafw_interface import MaafwInterface
from .node_system.node import Node
from .pipeline import Pipeline
from .views.controller_view import ControllerView
from .views.resource_library import ResourceLibrary


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MaaFramework Visual Editor")
        self.resize(1200, 800)

        # 创建配置管理器
        self.config_manager = config_manager
        # 创建核心组件 - 使用增强的画布
        self.canvas = EnhancedInfiniteCanvas()
        self.controller_view = ControllerView()
        self.resource_library = ResourceLibrary()
        self.property_editor = NodePropertiesEditor()
        self.node_library = NodeLibrary()
        self.maafw_interface = MaafwInterface()

        # 设置中央部件
        self.setCentralWidget(self.canvas)

        # 存储所有停靠窗口的引用
        self.dock_widgets = {}

        # 创建并添加停靠窗口
        self._create_docks()

        # 创建菜单、工具栏和状态栏
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_status_bar()

        # 连接信号和槽
        self._connect_signals_slots()

        # 保存默认布局
        self.default_state = self.saveState()

        # 设置当前项目文件路径
        self.current_file_path = None

        # 设置未保存更改标记
        self.has_unsaved_changes = False

        # 设置自动保存定时器并根据配置进行设置
        self.autosave_timer = QTimer(self)
        autosave_config = self.config_manager.config["autosave"]
        if autosave_config["enabled"]:
            interval = autosave_config["interval"] * 60000  # 将分钟转换为毫秒
            self.autosave_timer.setInterval(interval)
            self.autosave_timer.timeout.connect(self.auto_save)
            self.autosave_timer.start()

        # 恢复应用程序状态
        self.restore_application_state()

    # 添加到MainWindow类的新方法
    def restore_application_state(self):
        """从配置恢复应用程序状态。"""
        try:
            # 恢复窗口状态（大小、位置、停靠窗口可见性）
            self.config_manager.restore_window_state(self)

            # 恢复画布状态
            self.config_manager.restore_canvas_state(self.canvas)

            # 恢复资源库状态
            self.config_manager.restore_resource_library_state(self.resource_library)

            # 恢复控制器状态
            self.config_manager.restore_controller_state(self.controller_view)

            # 如果可用，加载上次的项目
            last_project = self.config_manager.get_last_project()
            if last_project and os.path.exists(last_project):
                self.load_project(last_project)

            self.status_label.setText("已从配置恢复应用程序状态")
        except Exception as e:
            import traceback
            print(f"恢复应用程序状态时出错: {str(e)}")
            print(traceback.format_exc())
            self.status_label.setText("恢复应用程序状态失败")

    def save_application_state(self):
        """保存当前应用程序状态到配置。"""
        try:
            # 保存窗口状态
            self.config_manager.save_window_state(self)

            # 保存画布状态
            self.config_manager.save_canvas_state(self.canvas)

            # 保存资源库状态
            self.config_manager.save_resource_library_state(self.resource_library)

            # 保存控制器状态
            self.config_manager.save_controller_state(self.controller_view)

            # 保存项目状态
            self.config_manager.save_project_state(self)

            # 保存自动保存设置
            self.config_manager.config["autosave"]["interval"] = self.autosave_timer.interval() // 60000  # 毫秒转分钟
            self.config_manager.save_config()

            self.status_label.setText("已保存应用程序状态到配置")
        except Exception as e:
            import traceback
            print(f"保存应用程序状态时出错: {str(e)}")
            print(traceback.format_exc())
            self.status_label.setText("保存应用程序状态失败")

    # 修改MainWindow.closeEvent方法
    def closeEvent(self, event):
        """处理窗口关闭事件。"""
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "未保存的更改",
                "有未保存的更改，是否保存？",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )

            if reply == QMessageBox.Save:
                if not self.save_project():
                    # 保存失败或取消，则取消关闭
                    event.ignore()
                    return
            elif reply == QMessageBox.Cancel:
                # 取消关闭
                event.ignore()
                return

        # 保存应用程序状态（包括窗口位置、大小、停靠窗口状态等）
        self.save_application_state()

        # 停止自动保存定时器
        self.autosave_timer.stop()
        event.accept()

    def _create_docks(self):
        # 创建节点库停靠窗口
        node_library_dock = QDockWidget("节点库", self)
        node_library_dock.setWidget(self.node_library)
        node_library_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        node_library_dock.setObjectName("node_library_dock")
        self.dock_widgets["node_library"] = node_library_dock
        # 创建属性编辑器停靠窗口
        properties_dock = QDockWidget("节点属性", self)
        properties_dock.setWidget(self.property_editor)
        properties_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        properties_dock.setObjectName("properties_dock")
        self.dock_widgets["properties"] = properties_dock

        resource_library_dock = QDockWidget("资源库", self)
        resource_library_dock.setWidget(self.resource_library)
        resource_library_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        resource_library_dock.setObjectName("resource_library_dock")
        self.dock_widgets["resource_library"] = resource_library_dock

        # 创建控制器视图停靠窗口 (替换原来的设置面板和模拟器视图)
        controller_dock = QDockWidget("控制器", self)
        controller_dock.setWidget(self.controller_view)
        controller_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)
        controller_dock.setObjectName("controller_dock")
        self.dock_widgets["controller"] = controller_dock

        # 添加停靠窗口到主窗口
        self.addDockWidget(Qt.LeftDockWidgetArea, node_library_dock)
        self.addDockWidget(Qt.LeftDockWidgetArea, resource_library_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, properties_dock)
        self.addDockWidget(Qt.BottomDockWidgetArea, controller_dock)

        self.resource_library.resource_opened.connect(self.on_resource_opened)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()

        # 文件菜单
        file_menu = menu_bar.addMenu("文件")

        new_action = file_menu.addAction("新建项目")
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self.new_project)

        open_action = file_menu.addAction("打开项目")
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_project)

        save_action = file_menu.addAction("保存项目")
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_project)

        save_as_action = file_menu.addAction("另存为")
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.triggered.connect(self.save_project_as)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("退出")
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)

        # 编辑菜单
        edit_menu = menu_bar.addMenu("编辑")

        undo_action = edit_menu.addAction("撤销")
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.triggered.connect(self.undo)

        redo_action = edit_menu.addAction("重做")
        redo_action.setShortcut(QKeySequence.Redo)
        redo_action.triggered.connect(self.redo)

        edit_menu.addSeparator()

        cut_action = edit_menu.addAction("剪切")
        cut_action.setShortcut(QKeySequence.Cut)
        cut_action.triggered.connect(self.cut_nodes)

        copy_action = edit_menu.addAction("复制")
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.triggered.connect(self.copy_nodes)

        paste_action = edit_menu.addAction("粘贴")
        paste_action.setShortcut(QKeySequence.Paste)
        paste_action.triggered.connect(self.paste_nodes)

        delete_action = edit_menu.addAction("删除")
        delete_action.setShortcut(QKeySequence.Delete)
        delete_action.triggered.connect(self.delete_nodes)

        edit_menu.addSeparator()

        select_all_action = edit_menu.addAction("全选")
        select_all_action.setShortcut(QKeySequence.SelectAll)
        select_all_action.triggered.connect(self.select_all_nodes)

        # 视图菜单
        view_menu = menu_bar.addMenu("视图")

        zoom_in_action = view_menu.addAction("放大")
        zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        zoom_in_action.triggered.connect(lambda: self.canvas.zoom(self.canvas.zoom_factor))

        zoom_out_action = view_menu.addAction("缩小")
        zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        zoom_out_action.triggered.connect(lambda: self.canvas.zoom(1 / self.canvas.zoom_factor))

        fit_action = view_menu.addAction("适应窗口")
        fit_action.triggered.connect(self.canvas.center_on_content)

        reset_view_action = view_menu.addAction("重置视图")
        reset_view_action.triggered.connect(self.reset_view)

        # 添加视图菜单项
        view_menu.addSeparator()

        # 为每个停靠窗口添加一个切换动作
        for name, dock in self.dock_widgets.items():
            action = view_menu.addAction(f"显示/隐藏{dock.windowTitle()}")
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(lambda checked, d=dock: d.setVisible(checked))

        # 添加重置所有视图的动作
        view_menu.addSeparator()
        reset_action = view_menu.addAction("重置所有视图")
        reset_action.triggered.connect(self.reset_dock_layout)

        # 节点菜单
        node_menu = menu_bar.addMenu("节点")

        align_grid_action = node_menu.addAction("对齐到网格")
        align_grid_action.triggered.connect(self.align_nodes_to_grid)

        # 使用右键菜单中的其他节点操作来扩展这里

        # MAAFW菜单
        maafw_menu = menu_bar.addMenu("MAAFW")
        maafw_menu.addAction("连接控制器")
        maafw_menu.addAction("断开连接")
        maafw_menu.addAction("执行任务")
        maafw_menu.addAction("停止任务")

    def _create_tool_bar(self):
        tool_bar = QToolBar("主工具栏")
        self.addToolBar(tool_bar)

        # 添加工具栏按钮并连接动作
        new_action = tool_bar.addAction("新建")
        new_action.triggered.connect(self.new_project)

        open_action = tool_bar.addAction("打开")
        open_action.triggered.connect(self.open_project)

        save_action = tool_bar.addAction("保存")
        save_action.triggered.connect(self.save_project)

        tool_bar.addSeparator()

        undo_action = tool_bar.addAction("撤销")
        undo_action.triggered.connect(self.undo)

        redo_action = tool_bar.addAction("重做")
        redo_action.triggered.connect(self.redo)

        tool_bar.addSeparator()

        zoom_in_action = tool_bar.addAction("放大")
        zoom_in_action.triggered.connect(lambda: self.canvas.zoom(self.canvas.zoom_factor))

        zoom_out_action = tool_bar.addAction("缩小")
        zoom_out_action.triggered.connect(lambda: self.canvas.zoom(1 / self.canvas.zoom_factor))

        fit_action = tool_bar.addAction("适应")
        fit_action.triggered.connect(self.canvas.center_on_content)

    def _create_status_bar(self):
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        # 添加状态信息标签
        self.status_label = QLabel("就绪")
        status_bar.addWidget(self.status_label, 1)

        # 创建视图按钮容器
        view_widget = QWidget()
        view_layout = QHBoxLayout(view_widget)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(2)

        # 为每个停靠窗口创建一个切换按钮
        for name, dock in self.dock_widgets.items():
            button = QPushButton(dock.windowTitle())
            button.setCheckable(True)
            button.setChecked(True)
            button.setFixedHeight(20)
            button.setFixedWidth(80)
            button.toggled.connect(lambda checked, d=dock: self.toggle_dock_visibility(d, checked))
            view_layout.addWidget(button)

        # 添加重置布局按钮
        reset_button = QPushButton("重置视图")
        reset_button.setFixedHeight(20)
        reset_button.setFixedWidth(80)
        reset_button.clicked.connect(self.reset_dock_layout)
        view_layout.addWidget(reset_button)

        # 将视图按钮容器添加到状态栏
        status_bar.addPermanentWidget(view_widget)

    def _connect_signals_slots(self):
        # 连接停靠窗口的可见性变化信号
        for name, dock in self.dock_widgets.items():
            dock.visibilityChanged.connect(lambda visible, d=dock: self.update_dock_status(d, visible))

        # 连接节点属性编辑器的信号
        if hasattr(self.property_editor, 'properties_changed'):
            self.property_editor.properties_changed.connect(self.on_properties_changed)
        # 连接节点选择变化信号到属性编辑器
        # self.canvas.scene.selectionChanged.connect(self.update_property_editor)
        self.canvas.node_manager.OpenNodeChanged.connect(self.update_property_editor)


    def update_property_editor(self):
        """当节点选择改变时更新属性编辑器"""
        # selected_nodes = self.canvas.get_selected_nodes()
        open_nodes=self.canvas.get_open_nodes()

        if len(open_nodes) == 1:
            # 单个节点选择时，显示其属性
            node = open_nodes[0]
            # 假设属性编辑器有一个 set_node 方法
            if hasattr(self.property_editor, 'set_node'):
                self.property_editor.set_node(node.task_node)
        else:
            # 多个或零个节点选择时，清空属性编辑器
            if hasattr(self.property_editor, 'clear'):
                self.property_editor.clear()

    @Slot()
    def on_properties_changed(self):
        """节点属性更改时的处理方法"""
        self.mark_unsaved_changes()

    @Slot(str)
    def on_resource_opened(self, file_path):
        """处理资源文件打开事件"""
        self.status_label.setText(f"已打开资源: {file_path}")

        try:
            # 从文件加载流水线
            pipeline = Pipeline.load_from_file(file_path)

            # 清除画布上的现有内容
            self.canvas.clear()

            # 创建一个字典来存储任务节点与可视节点的映射关系
            node_mapping = {}

            # 第一步：创建所有节点
            for name, task_node in pipeline.nodes.items():
                # 创建可视化节点
                visual_node = Node(
                    id=name,
                    title=name,
                    task_node=task_node
                )

                # 添加节点到画布
                self.canvas.add_node(visual_node)

                # 存储映射关系
                node_mapping[name] = visual_node

            # 确定节点位置
            self._layout_nodes(pipeline, node_mapping)

            # 第二步：创建所有连接
            for name, task_node in pipeline.nodes.items():
                source_node = node_mapping[name]

                # 连接 "next" 输出
                if task_node.next:
                    next_nodes = task_node.next if isinstance(task_node.next, list) else [task_node.next]
                    for next_node_name in next_nodes:
                        if next_node_name in node_mapping:
                            target_node = node_mapping[next_node_name]
                            source_port = source_node.get_output_port("next")
                            target_port = target_node.get_input_port()

                            if source_port and target_port:
                                self.canvas.command_manager.execute(
                                    ConnectNodesCommand(source_port, target_port, self.canvas)
                                )

                # 连接 "on_error" 输出
                if task_node.on_error:
                    error_nodes = task_node.on_error if isinstance(task_node.on_error, list) else [task_node.on_error]
                    for error_node_name in error_nodes:
                        if error_node_name in node_mapping:
                            target_node = node_mapping[error_node_name]
                            source_port = source_node.get_output_port("on_error")
                            target_port = target_node.get_input_port()

                            if source_port and target_port:
                                self.canvas.command_manager.execute(
                                    ConnectNodesCommand(source_port, target_port, self.canvas)
                                )

                # 连接 "interrupt" 输出
                if task_node.interrupt:
                    interrupt_nodes = task_node.interrupt if isinstance(task_node.interrupt, list) else [
                        task_node.interrupt]
                    for interrupt_node_name in interrupt_nodes:
                        if interrupt_node_name in node_mapping:
                            target_node = node_mapping[interrupt_node_name]
                            source_port = source_node.get_output_port("interrupt")
                            target_port = target_node.get_input_port()

                            if source_port and target_port:
                                self.canvas.command_manager.execute(
                                    ConnectNodesCommand(source_port, target_port, self.canvas)
                                )

            # 居中显示所有节点
            self.canvas.center_on_content()

            self.status_label.setText(f"已加载流水线: {file_path} (共 {len(pipeline.nodes)} 个节点)")

        except Exception as e:
            self.status_label.setText(f"加载失败: {str(e)}")
            print(f"加载流水线时出错: {str(e)}")

    def _layout_nodes(self, pipeline, node_mapping):
        """优化的节点布局算法，按照连接类型放置节点"""
        # 识别入口节点
        entry_nodes = pipeline.get_entry_nodes()

        # 存储节点层级和水平位置
        node_levels = {}  # 垂直位置（层级）
        node_x_positions = {}  # 水平位置

        # 存储节点的入边
        node_incoming_edges = {}

        # 第一步：使用BFS确定节点层级和收集入边信息
        visited = set()
        queue = [(node.name, 0) for node in entry_nodes]

        while queue:
            node_name, level = queue.pop(0)

            if node_name in visited:
                # 更新为最小层级
                if level < node_levels.get(node_name, float('inf')):
                    node_levels[node_name] = level
                    # 需要重新处理后继节点
                    task_node = pipeline.get_node(node_name)
                    if task_node:
                        for next_type in ['next', 'on_error', 'interrupt']:
                            next_nodes = getattr(task_node, next_type, None)
                            if next_nodes:
                                if isinstance(next_nodes, str):
                                    next_nodes = [next_nodes]
                                for next_node in next_nodes:
                                    queue.append((next_node, level + 1))
                continue

            visited.add(node_name)
            node_levels[node_name] = level

            # 获取任务节点
            task_node = pipeline.get_node(node_name)
            if not task_node:
                continue

            # 处理所有类型的后继节点
            for next_type in ['next', 'on_error', 'interrupt']:
                next_nodes = getattr(task_node, next_type, None)
                if next_nodes:
                    if isinstance(next_nodes, str):
                        next_nodes = [next_nodes]
                    for next_node in next_nodes:
                        # 记录入边
                        if next_node not in node_incoming_edges:
                            node_incoming_edges[next_node] = []
                        node_incoming_edges[next_node].append((node_name, next_type))

                        # 加入队列
                        queue.append((next_node, level + 1))

        # 第二步：按层级组织节点
        nodes_by_level = {}
        for node_name, level in node_levels.items():
            if level not in nodes_by_level:
                nodes_by_level[level] = []
            nodes_by_level[level].append(node_name)

        # 第三步：计算水平位置
        # 首先处理入口节点
        for i, node in enumerate(entry_nodes):
            node_x_positions[node.name] = i * 2  # 给入口节点留足空间

        # 处理每一层的节点
        for level in sorted(nodes_by_level.keys())[1:]:  # 跳过第0层（入口节点）
            used_positions = set()  # 记录此层已使用的位置

            # 首先处理有前驱的节点
            for node_name in list(nodes_by_level[level]):
                if node_name in node_incoming_edges:
                    # 根据前驱关系计算位置
                    suggested_x = []

                    for pred_name, relation_type in node_incoming_edges[node_name]:
                        if pred_name in node_x_positions:
                            pred_x = node_x_positions[pred_name]

                            if relation_type == 'next':
                                # next关系：正下方
                                suggested_x.append(pred_x)
                            elif relation_type == 'on_error':
                                # on_error关系：左下方
                                suggested_x.append(pred_x - 1)
                            elif relation_type == 'interrupt':
                                # interrupt关系：右下方
                                suggested_x.append(pred_x + 1)

                    if suggested_x:
                        # 计算平均位置并四舍五入
                        avg_x = sum(suggested_x) / len(suggested_x)
                        target_x = round(avg_x)

                        # 处理位置冲突
                        while target_x in used_positions:
                            # 从目标位置开始，交替向左右寻找空位
                            offset = 1
                            found = False
                            while not found and offset <= 10:  # 限制偏移范围
                                # 尝试右侧
                                if target_x + offset not in used_positions:
                                    target_x += offset
                                    found = True
                                    break
                                # 尝试左侧
                                if target_x - offset not in used_positions:
                                    target_x -= offset
                                    found = True
                                    break
                                offset += 1

                            if not found:
                                # 如果找不到空位，就放在最右边
                                target_x = max(used_positions) + 1 if used_positions else 0

                        node_x_positions[node_name] = target_x
                        used_positions.add(target_x)

            # 处理剩余的节点（无前驱或前驱不在已处理节点中）
            for node_name in nodes_by_level[level]:
                if node_name not in node_x_positions:
                    # 放在最右边
                    target_x = max(used_positions) + 1 if used_positions else 0
                    node_x_positions[node_name] = target_x
                    used_positions.add(target_x)

        # 应用布局
        grid_spacing_x = 500  # 节点之间的水平间距
        grid_spacing_y = 300  # 层级之间的垂直间距

        for node_name in node_mapping:
            if node_name in node_x_positions and node_name in node_levels:
                x = node_x_positions[node_name] * grid_spacing_x
                y = node_levels[node_name] * grid_spacing_y
                node_mapping[node_name].set_position(x, y)

    @Slot(QDockWidget, bool)
    def toggle_dock_visibility(self, dock, visible):
        """切换停靠窗口的可见性"""
        dock.setVisible(visible)
        self.update_dock_status(dock, visible)

    @Slot(QDockWidget, bool)
    def update_dock_status(self, dock, visible):
        """更新状态栏中的窗口状态信息"""
        status = f"{dock.windowTitle()} {'已显示' if visible else '已隐藏'}"
        self.status_label.setText(status)

        # 更新对应的菜单项和状态栏按钮
        for action in self.menuBar().findChildren(QAction):
            if action.text() == f"显示/隐藏{dock.windowTitle()}":
                action.setChecked(visible)
                break

        for button in self.statusBar().findChildren(QPushButton):
            if button.text() == dock.windowTitle():
                button.setChecked(visible)
                break

    @Slot()
    def reset_dock_layout(self):
        """重置所有停靠窗口到默认布局"""
        # 恢复默认布局
        self.restoreState(self.default_state)

        # 确保所有停靠窗口都是可见的
        for dock in self.dock_widgets.values():
            dock.setVisible(True)

        # 更新状态栏和按钮状态
        for button in self.statusBar().findChildren(QPushButton):
            if button.isCheckable():
                button.setChecked(True)

        self.status_label.setText("布局已重置")

    @Slot()
    def reset_view(self):
        """重置画布视图"""
        self.canvas.view.resetTransform()
        self.canvas.view.centerOn(0, 0)
        self.status_label.setText("视图已重置")

    @Slot()
    def new_project(self):
        """创建新项目"""
        # 检查是否有未保存的更改
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "未保存的更改",
                "有未保存的更改，是否保存？",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )

            if reply == QMessageBox.Save:
                if not self.save_project():
                    # 保存失败或取消，则不创建新项目
                    return
            elif reply == QMessageBox.Cancel:
                # 取消操作
                return

        # 清空画布
        self.canvas.clear()

        # 重置当前文件路径和未保存标记
        self.current_file_path = None
        self.has_unsaved_changes = False
        self.update_title()

        self.status_label.setText("已创建新项目")

    @Slot()
    def open_project(self):
        """打开项目文件"""
        # 检查是否有未保存的更改
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "未保存的更改",
                "有未保存的更改，是否保存？",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )

            if reply == QMessageBox.Save:
                if not self.save_project():
                    # 保存失败或取消，则不打开新项目
                    return
            elif reply == QMessageBox.Cancel:
                # 取消操作
                return

        # 打开文件对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开项目",
            "",
            "MaaFramework 项目文件 (*.maa);;所有文件 (*)"
        )

        if file_path:
            self.load_project(file_path)

    @Slot()
    def save_project(self):
        """保存项目"""
        if not self.current_file_path:
            return self.save_project_as()

        # 执行保存操作
        success = self._do_save(self.current_file_path)

        if success:
            self.has_unsaved_changes = False
            self.update_title()
            self.status_label.setText(f"项目已保存至 {self.current_file_path}")

        return success

    @Slot()
    def save_project_as(self):
        """项目另存为"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存项目",
            "",
            "MaaFramework 项目文件 (*.maa);;所有文件 (*)"
        )

        if file_path:
            success = self._do_save(file_path)

            if success:
                self.current_file_path = file_path
                self.has_unsaved_changes = False
                self.update_title()
                self.status_label.setText(f"项目已保存至 {file_path}")

            return success

        return False

    def _do_save(self, file_path):
        """执行实际的保存操作

        Args:
            file_path: 保存的文件路径

        Returns:
            bool: 保存是否成功
        """
        try:
            # 调用项目保存逻辑
            self.save_project_to_file(file_path)
            return True
        except Exception as e:
            QMessageBox.critical(
                self,
                "保存失败",
                f"保存项目时发生错误：\n{str(e)}"
            )
            return False

    @Slot()
    def auto_save(self):
        """自动保存项目"""
        if self.has_unsaved_changes and self.current_file_path:
            try:
                self._do_save(self.current_file_path + ".autosave")
                self.status_label.setText(f"项目已自动保存")
            except Exception as e:
                # 自动保存失败仅记录，不显示错误消息
                print(f"自动保存失败: {str(e)}")

    def mark_unsaved_changes(self):
        """标记有未保存的更改"""
        if not self.has_unsaved_changes:
            self.has_unsaved_changes = True
            self.update_title()

    def update_title(self):
        """更新窗口标题以反映当前文件和保存状态"""
        title = "MaaFramework Visual Editor"

        if self.current_file_path:
            import os
            filename = os.path.basename(self.current_file_path)
            title = f"{filename} - {title}"

        if self.has_unsaved_changes:
            title = f"*{title}"

        self.setWindowTitle(title)

    # 编辑操作
    @Slot()
    def undo(self):
        """撤销操作"""
        if self.canvas.command_manager.undo():
            self.status_label.setText("已撤销上一操作")
        else:
            self.status_label.setText("没有可撤销的操作")

    @Slot()
    def redo(self):
        """重做操作"""
        if self.canvas.command_manager.redo():
            self.status_label.setText("已重做操作")
        else:
            self.status_label.setText("没有可重做的操作")

    @Slot()
    def cut_nodes(self):
        """剪切选中的节点"""
        selected_nodes = self.canvas.get_selected_nodes()
        if not selected_nodes:
            return

        # 首先复制节点到剪贴板
        self.canvas.context_menus._copy_nodes(selected_nodes)

        # 然后删除节点
        self.canvas.context_menus._delete_nodes(selected_nodes)

        self.status_label.setText(f"已剪切 {len(selected_nodes)} 个节点")

    @Slot()
    def copy_nodes(self):
        """复制选中的节点"""
        selected_nodes = self.canvas.get_selected_nodes()
        if selected_nodes:
            self.canvas.context_menus._copy_nodes(selected_nodes)

    @Slot()
    def paste_nodes(self):
        """粘贴节点"""
        if hasattr(self.canvas, 'clipboard') and self.canvas.clipboard:
            # 获取视图中心作为粘贴位置
            center = self.canvas.view.mapToScene(self.canvas.view.viewport().rect().center())
            self.canvas.context_menus._paste_nodes(center)

    @Slot()
    def delete_nodes(self):
        """删除选中的节点"""
        selected_nodes = self.canvas.get_selected_nodes()
        if selected_nodes:
            self.canvas.context_menus._delete_nodes(selected_nodes)

    @Slot()
    def select_all_nodes(self):
        """选择所有节点"""
        self.canvas.context_menus._select_all_nodes()

    @Slot()
    def align_nodes_to_grid(self):
        """将选中的节点对齐到网格"""
        selected_nodes = self.canvas.get_selected_nodes()
        if selected_nodes:
            self.canvas.context_menus._snap_to_grid(selected_nodes)

    # 项目文件操作方法
    def load_project(self, path):
        """从文件加载项目

        Args:
            path: 项目文件路径
        """
        # 实现项目加载逻辑
        # 这是一个示例框架，具体实现需要根据项目文件格式来设计
        try:
            # 清空当前画布
            self.canvas.clear()

            # 从文件加载项目数据
            # 这里需要根据实际的文件格式进行解析
            # ...

            # 更新当前文件路径和未保存标记
            self.current_file_path = path
            self.has_unsaved_changes = False
            self.update_title()

            self.status_label.setText(f"已加载项目：{path}")
            return True
        except Exception as e:
            QMessageBox.critical(
                self,
                "加载失败",
                f"加载项目时发生错误：\n{str(e)}"
            )
            return False

    def save_project_to_file(self, path):
        """保存项目到文件

        Args:
            path: 保存的文件路径
        """
        # 实现项目保存逻辑
        # 这是一个示例框架，具体实现需要根据项目文件格式来设计

        # 1. 收集节点数据
        nodes_data = []
        for node in self.canvas.nodes:
            node_data = {
                'id': node.id,
                'title': node.title,
                'properties': node.get_properties(),
                'position': {'x': node.pos().x(), 'y': node.pos().y()}
            }
            nodes_data.append(node_data)

        # 2. 收集连接数据
        connections_data = []
        for conn in self.canvas.connection_manager.connections:
            source_node = conn.source_port.parent_node
            target_node = conn.target_port.parent_node

            conn_data = {
                'source_node_id': source_node.id,
                'source_port_type': conn.source_port.port_type,
                'source_port_name': getattr(conn.source_port, 'port_name', ''),
                'target_node_id': target_node.id,
                'target_port_type': conn.target_port.port_type,
                'target_port_name': getattr(conn.target_port, 'port_name', '')
            }
            connections_data.append(conn_data)

        # 3. 构建项目数据
        project_data = {
            'version': '1.0',
            'nodes': nodes_data,
            'connections': connections_data,
            # 可以添加其他项目元数据
        }

        # 4. 序列化并保存到文件
        import json
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, ensure_ascii=False, indent=2)
