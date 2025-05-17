from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QMainWindow, QDockWidget, QStatusBar, QToolBar,
                               QWidget, QLabel, QPushButton, QHBoxLayout,
                               QMessageBox, QFileDialog, QSizePolicy)

from src.views.node_canvas import NodeCanvas
from src.views.node_library import NodeLibrary
from src.views.node_properties_editor import NodePropertiesEditor
from .config_manager import config_manager
from .views.controller_view import ControllerView
from .views.debug_view import DebuggerView
from .views.resource_library import ResourceLibrary


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MaaFramework Visual Editor")
        self.resize(1200, 800)

        # 创建配置管理器
        self.config_manager = config_manager
        # 创建核心组件 - 使用增强的画布
        self.canvas = NodeCanvas()
        self.controller_view = ControllerView()
        self.resource_library = ResourceLibrary()
        self.property_editor = NodePropertiesEditor()
        self.debugger_view = DebuggerView()

        # 设置中央部件
        self.setCentralWidget(self.canvas)

        # 存储所有停靠窗口的引用
        self.dock_widgets = {}

        # 创建并添加停靠窗口
        self._create_docks()

        # 创建工具栏和状态栏
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

        # 恢复应用程序状态
        self.restore_application_state()

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

        event.accept()

    def _create_docks(self):
        # 创建节点库停靠窗口
        # node_library_dock = QDockWidget("节点库", self)
        # node_library_dock.setWidget(self.node_library)
        # node_library_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        # node_library_dock.setObjectName("node_library_dock")
        # self.dock_widgets["node_library"] = node_library_dock

        # 创建属性编辑器停靠窗口 - 修改允许区域
        properties_dock = QDockWidget("节点属性", self)
        properties_dock.setWidget(self.property_editor)
        properties_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        properties_dock.setObjectName("properties_dock")
        self.dock_widgets["properties"] = properties_dock

        resource_library_dock = QDockWidget("资源库", self)
        resource_library_dock.setWidget(self.resource_library)
        resource_library_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        resource_library_dock.setObjectName("resource_library_dock")
        self.dock_widgets["resource_library"] = resource_library_dock

        # 创建控制器视图停靠窗口
        controller_dock = QDockWidget("控制器", self)
        controller_dock.setWidget(self.controller_view)
        controller_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)
        controller_dock.setObjectName("controller_dock")
        self.dock_widgets["controller"] = controller_dock
        # 创建控制器视图停靠窗口
        debugger_view_dock = QDockWidget("调试器", self)
        debugger_view_dock.setWidget(self.debugger_view)
        debugger_view_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)
        debugger_view_dock.setObjectName("debugger_view_dock")
        self.dock_widgets["debugger_view"] = debugger_view_dock

        # 添加停靠窗口到主窗口 - 修改布局位置
        # self.addDockWidget(Qt.LeftDockWidgetArea, node_library_dock)
        self.addDockWidget(Qt.LeftDockWidgetArea, resource_library_dock)
        self.addDockWidget(Qt.BottomDockWidgetArea, controller_dock)
        self.addDockWidget(Qt.BottomDockWidgetArea, debugger_view_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, properties_dock)  # 将属性编辑器放在右侧

        # 创建标签页配置 - 使属性编辑器可以贴靠到控制器视图右侧
        self.tabifyDockWidget(controller_dock, properties_dock)

        # 确保属性编辑器在前面
        properties_dock.raise_()

    def _create_tool_bar(self):
        tool_bar = QToolBar("主工具栏")
        self.addToolBar(tool_bar)

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

        save_pipeline = tool_bar.addAction("保存")
        save_pipeline.triggered.connect(self._do_save)

        # 添加弹性空间将标签推到最右侧
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tool_bar.addWidget(spacer)

        # 添加标签
        label1 = QLabel("标签1")
        label2 = QLabel("标签2")

        tool_bar.addWidget(label1)
        tool_bar.addWidget(label2)
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
        self.canvas.node_manager.OpenNodeChanged.connect(self.update_open_node)
        self.canvas.node_manager.OpenNodeChanged.connect(self.show_properties_dock)
        self.resource_library.resource_opened.connect(self.on_resource_opened)
        self.property_editor.OpenNodeChanged.connect(self.update_open_node)
        self.property_editor.node_name_change.connect(self.canvas.node_manager.update_node_name)
        self.controller_view.OpenNodeChanged.connect(self.update_open_node)
    @Slot()
    def show_properties_dock(self):
        dock = self.dock_widgets.get("properties")
        if dock:
            dock.setVisible(True)
            dock.raise_()
            self.update_dock_status(dock, True)

    @Slot(str,object)
    def update_open_node(self,come_from,open_node):
        """当节点选择改变时更新属性编辑器"""
        if not come_from:
            return

        if come_from=="canvas":
            self.property_editor.set_node(open_node)
            self.controller_view.set_node(open_node)
        elif come_from=="property_editor":
            self.controller_view.set_node(open_node)
        elif come_from=="controller_view":
            # self.property_editor.set_node(open_node)
            self.property_editor.update_ui_from_node()


    @Slot()
    def on_properties_changed(self):
        """节点属性更改时的处理方法"""
        self.mark_unsaved_changes()

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

    def _do_save(self, file_path):
        """执行实际的保存操作

        Args:
            file_path: 保存的文件路径

        Returns:
            bool: 保存是否成功
        """
        try:
            # 调用项目保存逻辑
            self.canvas.save_to_file()
            return True
        except Exception as e:
            QMessageBox.critical(
                self,
                "保存失败",
                f"保存项目时发生错误：\n{str(e)}"
            )
            return False

    def mark_unsaved_changes(self):
        """标记有未保存的更改"""
        pass

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
    def restore_application_state(self):
        """从配置恢复应用程序状态。"""
        try:
            # 恢复窗口状态（大小、位置、停靠窗口可见性）
            self.config_manager.restore_window_state(self)

            # 恢复画布状态（仅视图缩放和位置）
            self.config_manager.restore_canvas_state(self.canvas)

            # 恢复资源库状态
            self.config_manager.restore_resource_library_state(self.resource_library)

            # 恢复控制器状态
            self.config_manager.restore_controller_state(self.controller_view)



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

            # 保存画布状态（仅视图缩放和位置）
            self.config_manager.save_canvas_state(self.canvas)

            # 保存资源库状态
            self.config_manager.save_resource_library_state(self.resource_library)

            # 保存控制器状态
            self.config_manager.save_controller_state(self.controller_view)

            # 保存自动保存设置
            self.config_manager.save_config()

            self.status_label.setText("已保存应用程序状态到配置")
        except Exception as e:
            import traceback
            print(f"保存应用程序状态时出错: {str(e)}")
            print(traceback.format_exc())
            self.status_label.setText("保存应用程序状态失败")

    @Slot(str)
    def on_resource_opened(self, file_path):
        """处理资源文件打开事件"""
        self.status_label.setText(f"已打开资源: {file_path}")
        self.controller_view.update_task_file(file_path)
        try:
            self.canvas.load_file(file_path)
        except Exception as e:
            self.status_label.setText(f"加载失败: {str(e)}")
            print(f"加载流水线时出错: {str(e)}")
