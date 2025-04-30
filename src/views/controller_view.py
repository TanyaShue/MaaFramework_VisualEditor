from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QFormLayout, QLineEdit, QPushButton, QComboBox,
                               QToolBar, QSplitter, QStackedWidget, QGroupBox)
from PySide6.QtCore import Qt, Signal, QThread
from maa.toolkit import Toolkit

from src.maafw import maafw


class DeviceSearchThread(QThread):
    """用于后台搜索设备的线程"""
    devices_found = Signal(list)
    search_error = Signal(str)

    def __init__(self, search_type):
        super().__init__()
        self.search_type = search_type

    def run(self):
        try:
            # 模拟搜索结果，实际应用中替换为真实设备搜索
            devices = []
            if self.search_type == "ADB":
                devices = Toolkit.find_adb_devices()
            elif self.search_type == "WIN32":
                devices = Toolkit.find_desktop_windows()
                devices = [device for device in devices if device.window_name != '']
            print(devices)
            self.devices_found.emit(devices)
        except Exception as e:
            self.search_error.emit(str(e))


class ControllerView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 搜索到的设备列表
        self.found_devices = []
        self.select_device=None

        # 主布局，使用水平布局包含分割器
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 创建分割器，用于左右可调节区域
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：控制器设置
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(15)

        # 标题
        title_label = QLabel("控制器设置")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        left_layout.addWidget(title_label)

        # 设备类型
        device_type_group = QGroupBox("设备类型")
        dt_layout = QFormLayout(device_type_group)
        dt_layout.setLabelAlignment(Qt.AlignRight)
        self.device_type_combo = QComboBox()
        self.device_type_combo.addItem("ADB设备", "ADB")
        self.device_type_combo.addItem("Win32窗口", "WIN32")
        self.device_type_combo.currentIndexChanged.connect(self.device_type_changed)
        dt_layout.addRow(QLabel("控制器类型:"), self.device_type_combo)
        left_layout.addWidget(device_type_group)

        # 设备搜索
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
        # 将按钮行作为整行添加
        search_layout.addRow(btn_layout)

        # 发现的设备行，标签与"控制器类型"对齐
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(200)
        self.device_combo.currentIndexChanged.connect(self.device_selected)
        search_layout.addRow(QLabel("发现的设备:"), self.device_combo)

        left_layout.addWidget(search_group)

        # 设备配置
        self.config_group = QGroupBox("设备配置")
        cfg_layout = QVBoxLayout(self.config_group)
        cfg_layout.setContentsMargins(5, 5, 5, 5)

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
        left_layout.addWidget(self.config_group)

        # 连接/断开 按钮
        btn_connect = QPushButton("连接设备")
        btn_connect.clicked.connect(self.connect_device)
        btn_disconnect = QPushButton("断开连接")
        btn_disconnect.clicked.connect(self.disconnect_device)
        left_layout.addWidget(btn_connect)
        left_layout.addWidget(btn_disconnect)
        left_layout.addStretch()

        # 右侧：控制器视图
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(10)

        toolbar = QToolBar()
        for action_text in ["截图", "选择区域", "放大", "缩小", "适应窗口"]:
            toolbar.addAction(action_text)
        right_layout.addWidget(toolbar)

        self.image_label = QLabel("控制器视图 - 这里将显示设备截图")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid gray;")
        self.image_label.setMinimumSize(320, 240)
        right_layout.addWidget(self.image_label)

        # 将左右面板添加到分割器
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        # 设置分割器伸缩比例: 左1:右2
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        # 将分割器加入主布局
        main_layout.addWidget(splitter)
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
            self.select_device=device
            # 根据控制器类型填充相应字段
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

    def connect_device(self):
        """连接到指定设备"""
        device_type = self.device_type_combo.currentData()
        if device_type == "ADB":
            address = self.adb_address_edit.text()
            adb_path = self.adb_path_edit.text()
            config = self.config_edit.text()
            maafw.connect_adb(adb_path,address, config)
        else:  # WIN32
            hwnd = self.hwnd_edit.text()
            input_method = self.input_method_combo.currentData()
            screenshot_method = self.screenshot_method_combo.currentData()
            print(f"连接到Win32窗口: {hwnd}, 输入方法: {input_method}, 截图方法: {screenshot_method}")

        # 这里只是演示，实际应用中需要实现真正的连接逻辑
        self.image_label.setText("已连接到设备，等待截图...")

    def disconnect_device(self):
        """断开当前设备连接"""
        # 这里只是演示，实际应用中需要实现真正的断开连接逻辑
        self.image_label.setText("控制器视图 - 这里将显示设备截图")
        print("断开设备连接")

    def get_device_info(self):
        """获取当前连接设备的信息"""
        pass

    def update_settings(self):
        """更新控制器设置"""
        pass

    # Methods from SimulatorView
    def display_image(self, image):
        """在视图中显示图像"""
        pass

    def capture_roi(self):
        """捕获感兴趣区域"""
        pass

    def mark_region(self, rect):
        """在图像上标记区域"""
        pass

    def refresh_image(self):
        """刷新当前图像"""
        pass

    def zoom_in(self):
        """放大图像"""
        pass

    def zoom_out(self):
        """缩小图像"""
        pass