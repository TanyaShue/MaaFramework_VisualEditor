from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QToolBar, QHBoxLayout
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt


class SimulatorView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)

        # 创建工具栏
        toolbar = QToolBar()
        toolbar.addAction("截图")
        toolbar.addAction("选择区域")
        toolbar.addAction("放大")
        toolbar.addAction("缩小")
        toolbar.addAction("适应窗口")

        # 创建图像显示区域
        image_layout = QHBoxLayout()
        self.image_label = QLabel("模拟器视图 - 这里将显示模拟器截图")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid gray;")
        self.image_label.setMinimumSize(320, 240)

        image_layout.addWidget(self.image_label)

        # 添加到主布局
        main_layout.addWidget(toolbar)
        main_layout.addLayout(image_layout)

    def display_image(self, image):
        pass

    def capture_roi(self):
        pass

    def mark_region(self, rect):
        pass

    def refresh_image(self):
        pass

    def zoom_in(self):
        pass

    def zoom_out(self):
        pass