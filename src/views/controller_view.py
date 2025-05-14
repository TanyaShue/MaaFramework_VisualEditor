import os

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QFormLayout, QLineEdit, QPushButton, QComboBox,
                               QSplitter, QStackedWidget, QGroupBox,
                               QMenu, QSizePolicy, QScrollArea)
from maa.toolkit import Toolkit
from qasync import asyncSlot

from src.maafw import maafw
from src.views.components.deviceImage_view import DeviceImageView


class DeviceSearchThread(QThread):
    """用于后台搜索设备的线程"""
    devices_found = Signal(list)
    search_error = Signal(str)

    def __init__(self, search_type):
        super().__init__()
        self.search_type = search_type

    def run(self):
        try:
            # 搜索设备
            devices = []
            if self.search_type == "ADB":
                devices = Toolkit.find_adb_devices()
            elif self.search_type == "WIN32":
                devices = Toolkit.find_desktop_windows()
                devices = [device for device in devices if device.window_name != '']
            self.devices_found.emit(devices)
        except Exception as e:
            self.search_error.emit(str(e))


class ControllerView(QWidget):
    # 添加新信号

    def __init__(self, parent=None):
        super().__init__(parent)

        # 初始化状态变量
        self.selected_node = None
        self.file_name = None
        self.device_view = None
        self.selected_node_name = None
        self.found_devices = []
        self.select_device = None
        self.selection_mode = False
        self.is_connected = False
        self.left_panel_collapsed = False

        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 分割器
        self.splitter = QSplitter(Qt.Horizontal)

        # 左侧控制面板
        self.setup_left_panel()

        # 右侧视图面板
        self.setup_right_panel()

        # 将左右面板添加到分割器
        self.splitter.addWidget(self.left_widget)
        self.splitter.addWidget(self.right_widget)
        # 设置分割器比例
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)

        # 添加到主布局
        main_layout.addWidget(self.splitter)

        # 创建右键菜单
        self.context_menu = QMenu(self)

    def setup_left_panel(self):
        """设置左侧控制面板"""
        self.left_widget = QWidget()
        outer_layout = QVBoxLayout(self.left_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # 创建一个滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)  # 允许内容小部件调整大小
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 创建内容小部件
        content_widget = QWidget()
        self.left_layout = QVBoxLayout(content_widget)
        self.left_layout.setContentsMargins(10, 10, 10, 10)
        self.left_layout.setSpacing(15)

        # 标题
        title_label = QLabel("控制器设置")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.left_layout.addWidget(title_label)

        # 设备类型组
        device_type_group = QGroupBox("设备类型")
        dt_layout = QFormLayout(device_type_group)
        dt_layout.setLabelAlignment(Qt.AlignRight)
        self.device_type_combo = QComboBox()
        self.device_type_combo.addItem("ADB设备", "ADB")
        self.device_type_combo.addItem("Win32窗口", "WIN32")
        self.device_type_combo.currentIndexChanged.connect(self.device_type_changed)
        dt_layout.addRow(QLabel("控制器类型:"), self.device_type_combo)
        self.left_layout.addWidget(device_type_group)

        # 设备搜索组
        search_group = QGroupBox("设备搜索")
        search_layout = QFormLayout(search_group)
        search_layout.setLabelAlignment(Qt.AlignRight)
        search_layout.setContentsMargins(5, 5, 5, 5)
        search_layout.setSpacing(10)

        # 搜索按钮行
        btn_layout = QHBoxLayout()
        self.search_btn = QPushButton("搜索设备")
        self.search_btn.clicked.connect(self.search_devices)
        self.search_status = QLabel("未搜索")
        btn_layout.addWidget(self.search_btn)
        btn_layout.addWidget(self.search_status)
        btn_layout.addStretch()
        search_layout.addRow(btn_layout)

        # 设备下拉框
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(200)
        self.device_combo.currentIndexChanged.connect(self.device_selected)
        search_layout.addRow(QLabel("发现的设备:"), self.device_combo)
        self.left_layout.addWidget(search_group)

        # 设备配置组
        self.config_group = QGroupBox("设备配置")
        cfg_layout = QVBoxLayout(self.config_group)
        cfg_layout.setContentsMargins(5, 5, 5, 5)

        # 配置栈
        self.controller_stack = QStackedWidget()

        # ADB配置页面
        adb_page = QWidget()
        adb_form = QFormLayout(adb_page)
        adb_form.setLabelAlignment(Qt.AlignRight)
        self.adb_path_edit = QLineEdit()
        self.adb_address_edit = QLineEdit()
        self.config_edit = QLineEdit()
        adb_form.addRow("ADB 路径:", self.adb_path_edit)
        adb_form.addRow("ADB 地址:", self.adb_address_edit)
        adb_form.addRow("配置:", self.config_edit)
        self.controller_stack.addWidget(adb_page)

        # Win32配置页面
        win32_page = QWidget()
        win32_form = QFormLayout(win32_page)
        win32_form.setLabelAlignment(Qt.AlignRight)
        self.hwnd_edit = QLineEdit()
        self.input_method_combo = QComboBox()
        self.input_method_combo.addItem("Seize", 1)
        self.input_method_combo.addItem("SendMessage", 2)
        self.screenshot_method_combo = QComboBox()
        self.screenshot_method_combo.addItem("GDI", 1)
        self.screenshot_method_combo.addItem("FramePool", 2)
        self.screenshot_method_combo.addItem("DXGI_DesktopDup", 3)
        win32_form.addRow("窗口句柄 (hWnd):", self.hwnd_edit)
        win32_form.addRow("输入方法:", self.input_method_combo)
        win32_form.addRow("截图方法:", self.screenshot_method_combo)
        self.controller_stack.addWidget(win32_page)

        cfg_layout.addWidget(self.controller_stack)
        self.left_layout.addWidget(self.config_group)

        # 连接/断开按钮
        btn_connect = QPushButton("连接设备")
        btn_connect.clicked.connect(self.connect_device)
        btn_disconnect = QPushButton("断开连接")
        btn_disconnect.clicked.connect(self.disconnect_device)
        self.left_layout.addWidget(btn_connect)
        self.left_layout.addWidget(btn_disconnect)
        self.left_layout.addStretch()

        # 设置内容小部件为滚动区域的小部件
        scroll_area.setWidget(content_widget)

        # 将滚动区域添加到左侧面板
        outer_layout.addWidget(scroll_area)
    def setup_right_panel(self):
        """设置右侧视图面板"""
        self.right_widget = QWidget()
        right_layout = QVBoxLayout(self.right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 工具栏布局
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(10)

        # 切换面板按钮
        self.toggle_panel_btn = QPushButton("<<")
        self.toggle_panel_btn.setFixedWidth(30)
        self.toggle_panel_btn.setToolTip("折叠/展开控制面板")
        self.toggle_panel_btn.clicked.connect(self.toggle_left_panel)
        toolbar_layout.addWidget(self.toggle_panel_btn)

        # 连接状态标签
        self.connection_status = QLabel("未连接")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        toolbar_layout.addWidget(self.connection_status)

        # 添加当前模式标签 (替代之前的选择区域按钮)
        self.mode_status_label = QLabel("当前模式: 显示模式")
        self.mode_status_label.setStyleSheet("font-weight: bold;")
        toolbar_layout.addWidget(self.mode_status_label)

        # 截图按钮 - 直接加入工具栏布局
        self.screenshot_btn = QPushButton("截图")
        self.screenshot_btn.clicked.connect(self.update_device_img)
        toolbar_layout.addWidget(self.screenshot_btn)

        # 重置视图按钮 - 直接加入工具栏布局
        self.reset_view_btn = QPushButton("重置视图")
        self.reset_view_btn.clicked.connect(self.reset_view)
        toolbar_layout.addWidget(self.reset_view_btn)

        # 添加弹性空间，将后面的标签推到最右侧
        toolbar_layout.addStretch()

        # 添加选中节点标签
        self.selected_node_label = QLabel("选中节点: 未选择")
        toolbar_layout.addWidget(self.selected_node_label)

        # 打开文件
        self.task_file_label = QLabel("打开文件: 未选择")
        toolbar_layout.addWidget(self.task_file_label)

        right_layout.addLayout(toolbar_layout)

        # 创建并添加设备图像视图
        self.device_view = DeviceImageView(control=self)
        self.device_view.selectionChanged.connect(self.on_selection_changed)
        self.device_view.selectionCleared.connect(self.on_selection_cleared)
        # 连接新的信号
        self.device_view.modeChangedSignal.connect(self.update_mode_status)
        right_layout.addWidget(self.device_view)

    def toggle_left_panel(self):
        """切换左侧面板显示/隐藏"""
        self.left_panel_collapsed = not self.left_panel_collapsed

        if self.left_panel_collapsed:
            self.left_widget.setMaximumWidth(0)
            self.toggle_panel_btn.setText(">>")
        else:
            self.left_widget.setMaximumWidth(16777215)  # 最大值
            self.toggle_panel_btn.setText("<<")

    def device_type_changed(self, index):
        """当控制器类型变更时的处理函数"""
        self.controller_stack.setCurrentIndex(index)
        self.device_combo.clear()
        self.search_status.setText("未搜索")
        self.found_devices = []

    def search_devices(self):
        """搜索设备"""
        self.search_btn.setEnabled(False)
        self.search_status.setText("正在搜索...")
        self.device_combo.clear()

        device_type = self.device_type_combo.currentData()
        self.search_thread = DeviceSearchThread(device_type)
        self.search_thread.devices_found.connect(self.on_devices_found)
        self.search_thread.search_error.connect(self.on_search_error)
        self.search_thread.finished.connect(self.on_search_completed)
        self.search_thread.start()

    def on_devices_found(self, devices):
        """处理找到的设备"""
        self.device_combo.clear()
        self.found_devices = devices
        if devices:
            for device in devices:
                if hasattr(device, 'address'):  # ADB设备
                    text = f"{device.name} - {device.address}"
                elif hasattr(device, 'hwnd'):  # WIN32窗口
                    text = f"{device.window_name} - {device.hwnd}"
                else:
                    text = str(device)
                self.device_combo.addItem(text)
            self.search_status.setText(f"找到 {len(devices)} 个设备")
        else:
            self.device_combo.addItem("未找到设备")
            self.search_status.setText("未找到设备")

    def on_search_error(self, error_msg):
        """处理搜索错误"""
        self.device_combo.clear()
        self.device_combo.addItem("搜索出错")
        self.search_status.setText(f"搜索出错: {error_msg}")

    def on_search_completed(self):
        """搜索完成后的处理"""
        self.search_btn.setEnabled(True)
        self.search_thread = None

    def device_selected(self, index):
        """当选择设备时填充相应字段"""
        if 0 <= index < len(self.found_devices):
            device = self.found_devices[index]
            device_type = self.device_type_combo.currentData()
            self.select_device = device

            if device_type == "ADB":
                # 填充ADB设备字段
                if device.address:
                    self.adb_address_edit.setText(str(device.address))
                if device.adb_path:
                    self.adb_path_edit.setText(str(device.adb_path))
                if device.config:
                    self.config_edit.setText(str(device.config))
            elif device_type == "WIN32":
                # 填充Win32设备字段
                if device.hwnd:
                    self.hwnd_edit.setText(str(device.hwnd))

    @asyncSlot()
    async def connect_device(self):
        """连接到指定设备"""
        try:
            device_type = self.device_type_combo.currentData()
            if device_type == "ADB":
                address = self.adb_address_edit.text()
                adb_path = self.adb_path_edit.text()
                config_text = self.config_edit.text()
                if config_text == "":
                    config_text = {}

                # 连接到ADB设备
                connected, error = await maafw.connect_adb(adb_path, address, config_text)
                if connected:
                    print(f"成功连接到ADB设备: {address}")
                    self.is_connected = True
                else:
                    print(f"连接ADB设备失败: {error}")
                    self.is_connected = False
            else:  # WIN32
                hwnd_text = self.hwnd_edit.text()
                input_method = self.input_method_combo.currentData()
                screenshot_method = self.screenshot_method_combo.currentData()

                # 连接到Win32窗口
                connected, error = await maafw.connect_win32hwnd(hwnd_text, screenshot_method, input_method)
                if connected:
                    print(f"成功连接到Win32窗口: {hwnd_text}")
                    self.is_connected = True
                else:
                    print(f"连接Win32窗口失败: {error}")
                    self.is_connected = False

            self.update_connection_status()

            if self.is_connected:
                await self.update_device_img()
        except Exception as e:
            print(f"连接设备时发生错误: {str(e)}")
            self.is_connected = False
            self.update_connection_status()

    def disconnect_device(self):
        """断开当前设备连接"""
        # 实现断开连接逻辑
        self.is_connected = False
        self.update_connection_status()
        print("断开设备连接")

    def update_connection_status(self):
        """更新连接状态标签"""
        if self.is_connected:
            self.connection_status.setText("已连接")
            self.connection_status.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.connection_status.setText("未连接")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")

    def update_mode_status(self, is_selection_mode):
        """更新模式状态标签"""
        self.selection_mode = is_selection_mode
        if is_selection_mode:
            self.mode_status_label.setText("当前模式: 框选模式")
        else:
            self.mode_status_label.setText("当前模式: 显示模式")

    @asyncSlot()
    async def update_device_img(self):
        """更新设备截图"""
        img = await maafw.screencap()
        if img:
            self.display_image(img)

    def display_image(self, image):
        """在视图中显示图像"""
        if image is None:
            return

        self.device_view.set_image(image)

    def reset_view(self):
        """重置视图到原始状态"""
        self.device_view.reset_view()

    def on_selection_changed(self, rect):
        """当选择区域变化时"""
        # 可以在这里处理选择区域变化事件
        pass

    def on_selection_cleared(self):
        """当选择区域被清除时"""
        # 可以在这里处理选择区域清除事件
        pass

    def update_selected_node(self, node):
        """更新已选中节点的标签"""
        try:
            self.selected_node_name = node[0].task_node.name
            self.selected_node=node[0].task_node
            label_text = f"选中节点:{self.selected_node_name}"
        except (IndexError, AttributeError, TypeError):
            self.selected_node_name = None
            label_text = "选中节点: 未选择"

        self.selected_node_label.setText(label_text)

    def update_task_file(self, file_path):
        """更新打开文件的标签，只显示文件名"""
        if not file_path:
            self.task_file_label.setText("打开文件: 未选择")
        else:
            # 提取文件路径中的文件名部分
            self.file_name = os.path.basename(file_path)
            self.task_file_label.setText(f"打开文件: { self.file_name}")