from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QFormLayout, QLineEdit, QPushButton, QComboBox,
                               QToolBar, QSplitter)
from PySide6.QtCore import Qt


class ControllerView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create a splitter to allow resizing between sections
        splitter = QSplitter(Qt.Horizontal)

        # Left side - Controller Settings (from SettingsPanel)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Add settings title
        settings_title = QLabel("控制器设置")
        settings_title.setStyleSheet("font-weight: bold; font-size: 14px;")

        # Create device connection form
        device_layout = QFormLayout()
        self.device_combo = QComboBox()
        self.device_combo.addItem("ADB")
        self.device_combo.addItem("模拟器")
        self.device_combo.addItem("iOS")

        self.address_input = QLineEdit("127.0.0.1:5555")

        device_layout.addRow("设备类型:", self.device_combo)
        device_layout.addRow("设备地址:", self.address_input)

        # Create buttons
        connect_button = QPushButton("连接设备")
        disconnect_button = QPushButton("断开连接")
        refresh_button = QPushButton("刷新设备列表")

        # Add to left layout
        left_layout.addWidget(settings_title)
        left_layout.addLayout(device_layout)
        left_layout.addWidget(connect_button)
        left_layout.addWidget(disconnect_button)
        left_layout.addWidget(refresh_button)
        left_layout.addStretch()

        # Right side - Controller View (from SimulatorView)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Create toolbar
        toolbar = QToolBar()
        toolbar.addAction("截图")
        toolbar.addAction("选择区域")
        toolbar.addAction("放大")
        toolbar.addAction("缩小")
        toolbar.addAction("适应窗口")

        # Create image display area
        self.image_label = QLabel("控制器视图 - 这里将显示设备截图")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid gray;")
        self.image_label.setMinimumSize(320, 240)

        # Add to right layout
        right_layout.addWidget(toolbar)
        right_layout.addWidget(self.image_label)

        # Add widgets to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)

        # Set initial sizes (1:2 ratio)
        splitter.setSizes([100, 200])

        # Add splitter to main layout
        main_layout.addWidget(splitter)

    # Methods from SettingsPanel
    def connect_device(self):
        """连接到指定设备"""
        pass

    def disconnect_device(self):
        """断开当前设备连接"""
        pass

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