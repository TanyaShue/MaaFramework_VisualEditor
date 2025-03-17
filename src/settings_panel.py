from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFormLayout, QLineEdit, QPushButton, QComboBox


class SettingsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        # 添加标签
        title_label = QLabel("设置面板")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        # 创建设备连接部分
        device_layout = QFormLayout()
        self.device_combo = QComboBox()
        self.device_combo.addItem("ADB")
        self.device_combo.addItem("模拟器")
        self.device_combo.addItem("iOS")

        self.address_input = QLineEdit("127.0.0.1:5555")

        device_layout.addRow("设备类型:", self.device_combo)
        device_layout.addRow("设备地址:", self.address_input)

        # 创建按钮
        connect_button = QPushButton("连接设备")
        disconnect_button = QPushButton("断开连接")
        refresh_button = QPushButton("刷新设备列表")

        # 添加到主布局
        layout.addWidget(title_label)
        layout.addLayout(device_layout)
        layout.addWidget(connect_button)
        layout.addWidget(disconnect_button)
        layout.addWidget(refresh_button)
        layout.addStretch()

    def connect_device(self):
        pass

    def disconnect_device(self):
        pass

    def get_device_info(self):
        pass

    def update_settings(self):
        pass
