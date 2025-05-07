import sys
from PySide6.QtWidgets import (QApplication, QWidget, QScrollArea, QGridLayout,
                               QLabel, QPushButton, QFileDialog, QFrame, QVBoxLayout)
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt, QSize, Signal


class ImagePreviewContainer(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 设置滚动区域属性
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 创建容器窗口部件
        self.container_widget = QWidget()
        self.setWidget(self.container_widget)

        # 创建网格布局
        self.grid_layout = QGridLayout(self.container_widget)
        self.grid_layout.setSpacing(10)
        self.container_widget.setLayout(self.grid_layout)

        # 图片容器列表
        self.image_containers = []

        # 添加"+"按钮用于添加新图片
        self.add_add_button()

        # 当前网格位置
        self.current_row = 0
        self.current_col = 0
        self.max_columns = 3

        # 更新布局
        self.update_layout()

    def add_add_button(self):
        """添加"+"按钮容器用于添加新图片"""
        add_container = ImageContainer(is_add_button=True)
        add_container.add_clicked.connect(self.add_image)
        self.image_containers.append(add_container)

    def add_image(self):
        """添加新图片到容器"""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, "选择图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)"
        )

        if file_path:
            # 移除旧的"+"按钮容器
            add_button_container = self.image_containers.pop()

            # 创建新的图片容器
            image_container = ImageContainer(image_path=file_path)
            image_container.delete_clicked.connect(self.delete_image)
            self.image_containers.append(image_container)

            # 添加回"+"按钮容器
            self.image_containers.append(add_button_container)

            # 更新布局
            self.update_layout()

    def delete_image(self, container):
        """删除图片容器"""
        if container in self.image_containers:
            self.image_containers.remove(container)
            container.deleteLater()
            self.update_layout()

    def update_layout(self):
        """更新网格布局"""
        # 清除现有布局中的所有项目
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        # 重新添加所有图片容器到布局
        for i, container in enumerate(self.image_containers):
            row = i // self.max_columns
            col = i % self.max_columns
            self.grid_layout.addWidget(container, row, col)


class ImageContainer(QFrame):
    """图片容器类，用于显示单个图片或添加按钮"""

    # 自定义信号
    delete_clicked = Signal(object)  # 传递自身作为参数
    add_clicked = Signal()

    def __init__(self, image_path=None, is_add_button=False, parent=None):
        super().__init__(parent)

        # 设置固定大小
        self.setFixedSize(200, 200)

        # 设置边框样式
        self.setFrameShape(QFrame.Box)
        self.setFrameShadow(QFrame.Raised)
        self.setStyleSheet("border: 1px solid #cccccc; border-radius: 5px; background-color: #f9f9f9;")

        # 创建布局
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)

        # 创建图片标签
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(180, 180)
        self.layout.addWidget(self.image_label)

        self.is_add_button = is_add_button

        if is_add_button:
            # 创建添加按钮
            self.setup_add_button()
        elif image_path:
            # 显示图片
            self.load_image(image_path)
            # 添加删除按钮
            self.setup_delete_button()

    def setup_delete_button(self):
        """设置删除按钮"""
        delete_button = QPushButton("×", self)
        delete_button.setFixedSize(20, 20)
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #ff6b6b;
                color: white;
                border-radius: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff4747;
            }
        """)
        delete_button.move(self.width() - 25, 5)  # 右上角位置
        delete_button.clicked.connect(self.on_delete_clicked)

    def setup_add_button(self):
        """设置添加按钮样式"""
        self.image_label.setText("+")
        self.image_label.setStyleSheet("""
            QLabel {
                font-size: 50px;
                color: #aaaaaa;
            }
        """)
        self.setCursor(Qt.PointingHandCursor)

    def load_image(self, image_path):
        """加载并显示图片"""
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(pixmap)
        else:
            self.image_label.setText("图片加载失败")

    def on_delete_clicked(self):
        """删除按钮点击事件"""
        self.delete_clicked.emit(self)

    def mousePressEvent(self, event):
        """鼠标点击事件，用于"+"按钮的点击"""
        if self.is_add_button:
            self.add_clicked.emit()
        super().mousePressEvent(event)

