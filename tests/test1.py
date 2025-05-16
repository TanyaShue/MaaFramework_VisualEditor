from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel,
    QScrollArea, QFrame, QHBoxLayout
)
from PySide6.QtCore import Qt
import sys

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("动态添加容器")
        self.resize(400, 500)

        self.main_layout = QVBoxLayout(self)

        # 顶部按钮
        self.add_button = QPushButton("添加容器")
        self.add_button.clicked.connect(self.add_container)
        self.main_layout.addWidget(self.add_button)

        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        self.main_layout.addWidget(self.scroll_area)

        # 容器计数
        self.container_count = 0

    def add_container(self):
        self.container_count += 1

        # 创建一个新的容器（QFrame也可以替代QWidget）
        container = QFrame()
        container.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(container)

        # 添加对应数量的标签
        for i in range(1, self.container_count + 1):
            label = QLabel(f"{i}")
            layout.addWidget(label)

        self.scroll_layout.addWidget(container)

