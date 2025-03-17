from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QMainWindow, QDockWidget, QMenuBar, QStatusBar, QToolBar,
                               QVBoxLayout, QWidget, QLabel, QPushButton, QHBoxLayout)
from PySide6.QtCore import Qt, Signal, Slot

from .infinite_canvas import InfiniteCanvas
from .settings_panel import SettingsPanel
from .simulator_view import SimulatorView
from .node_properties_editor import NodePropertiesEditor
from .node_library import NodeLibrary
from .maafw_interface import MaafwInterface


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MaaFramework Visual Editor")
        self.resize(1200, 800)

        # 创建核心组件
        self.canvas = InfiniteCanvas()
        self.settings_panel = SettingsPanel()
        self.simulator_view = SimulatorView()
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

    def _create_docks(self):
        # 创建节点库停靠窗口
        node_library_dock = QDockWidget("节点库", self)
        node_library_dock.setWidget(self.node_library)
        node_library_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        node_library_dock.setObjectName("node_library_dock")
        self.dock_widgets["node_library"] = node_library_dock

        # 创建设置面板停靠窗口
        settings_dock = QDockWidget("设置面板", self)
        settings_dock.setWidget(self.settings_panel)
        settings_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        settings_dock.setObjectName("settings_dock")
        self.dock_widgets["settings"] = settings_dock

        # 创建属性编辑器停靠窗口
        properties_dock = QDockWidget("节点属性", self)
        properties_dock.setWidget(self.property_editor)
        properties_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        properties_dock.setObjectName("properties_dock")
        self.dock_widgets["properties"] = properties_dock

        # 创建模拟器视图停靠窗口
        simulator_dock = QDockWidget("模拟器视图", self)
        simulator_dock.setWidget(self.simulator_view)
        simulator_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)
        simulator_dock.setObjectName("simulator_dock")
        self.dock_widgets["simulator"] = simulator_dock

        # 添加停靠窗口到主窗口
        self.addDockWidget(Qt.LeftDockWidgetArea, node_library_dock)
        self.addDockWidget(Qt.LeftDockWidgetArea, settings_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, properties_dock)
        self.addDockWidget(Qt.BottomDockWidgetArea, simulator_dock)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()

        # 文件菜单
        file_menu = menu_bar.addMenu("文件")
        file_menu.addAction("新建项目")
        file_menu.addAction("打开项目")
        file_menu.addAction("保存项目")
        file_menu.addAction("另存为")
        file_menu.addSeparator()
        file_menu.addAction("退出")

        # 编辑菜单
        edit_menu = menu_bar.addMenu("编辑")
        edit_menu.addAction("撤销")
        edit_menu.addAction("重做")
        edit_menu.addSeparator()
        edit_menu.addAction("剪切")
        edit_menu.addAction("复制")
        edit_menu.addAction("粘贴")
        edit_menu.addAction("删除")

        # 视图菜单
        view_menu = menu_bar.addMenu("视图")
        view_menu.addAction("放大")
        view_menu.addAction("缩小")
        view_menu.addAction("适应窗口")
        view_menu.addAction("重置视图")

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

        # MAAFW菜单
        maafw_menu = menu_bar.addMenu("MAAFW")
        maafw_menu.addAction("连接控制器")
        maafw_menu.addAction("断开连接")
        maafw_menu.addAction("执行任务")
        maafw_menu.addAction("停止任务")

    def _create_tool_bar(self):
        tool_bar = QToolBar("主工具栏")
        self.addToolBar(tool_bar)

        tool_bar.addAction("新建")
        tool_bar.addAction("打开")
        tool_bar.addAction("保存")
        tool_bar.addSeparator()
        tool_bar.addAction("撤销")
        tool_bar.addAction("重做")
        tool_bar.addSeparator()
        tool_bar.addAction("放大")
        tool_bar.addAction("缩小")

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

    def load_project(self, path):
        pass

    def save_project(self, path):
        pass