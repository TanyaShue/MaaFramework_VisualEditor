import sys
from PySide6.QtWidgets import (QApplication, QWidget, QScrollArea, QGridLayout,
                               QLabel, QPushButton, QFileDialog, QFrame, QVBoxLayout)
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt, QSize, Signal, QTimer


class ImagePreviewContainer(QScrollArea):
    image_deleted = Signal(str)  # 传递被删除图片的路径

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
        self.grid_layout.setSpacing(4)
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

        # 添加一个定时器，用于窗口大小变化时调整图片容器大小
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.handle_resize)

        # 初始调整大小
        QTimer.singleShot(0, self.handle_resize)

    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        super().resizeEvent(event)
        # 使用定时器减少频繁调整
        self.resize_timer.start(100)

    def handle_resize(self):
        """处理容器大小变化，调整所有图片容器的大小"""
        container_width = self.viewport().width()
        cell_width = max(50, (container_width - (self.max_columns - 1) * 4) // self.max_columns)

        for container in self.image_containers:
            container.set_container_size(cell_width)

    def add_add_button(self):
        """添加"+"按钮容器用于添加新图片"""
        add_container = ImageContainer(is_add_button=True)
        add_container.add_clicked.connect(self.add_image)
        self.image_containers.append(add_container)

    def add_image(self, image_path=None, relative_path=None):
        """添加新图片到容器，可以指定图片路径或通过对话框选择"""
        if not image_path:
            file_dialog = QFileDialog()
            file_path, _ = file_dialog.getOpenFileName(
                self, "选择图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)"
            )
            image_path = file_path

        if image_path:
            # 移除旧的"+"按钮容器
            add_button_container = self.image_containers.pop()

            # 创建新的图片容器
            container_width = max(50, (self.viewport().width() - (self.max_columns - 1) * 4) // self.max_columns)
            image_container = ImageContainer(image_path=image_path, initial_width=container_width)

            # 保存相对路径信息
            if relative_path:
                image_container.relative_path = relative_path

            image_container.delete_clicked.connect(self.delete_image)
            self.image_containers.append(image_container)

            # 添加回"+"按钮容器
            self.image_containers.append(add_button_container)
            add_button_container.set_container_size(container_width)

            # 更新布局
            self.update_layout()

            return image_container
        return None

    def delete_image(self, container):
        """删除图片容器"""
        if container in self.image_containers:
            # 发出删除信号，传递相对路径
            if hasattr(container, 'relative_path') and container.relative_path:
                self.image_deleted.emit(container.relative_path)

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

    def clear_images(self):
        """清除所有图片，但保留添加按钮"""
        if len(self.image_containers) > 1:
            add_button_container = self.image_containers[-1] if self.image_containers[-1].is_add_button else None

            # 删除所有图片容器
            for container in self.image_containers[:]:
                if not container.is_add_button:
                    self.image_containers.remove(container)
                    container.deleteLater()

            # 如果没有添加按钮了，重新添加一个
            if not add_button_container:
                self.add_add_button()

            # 更新布局
            self.update_layout()


class ImageContainer(QFrame):
    """图片容器类，用于显示单个图片或添加按钮"""

    # 自定义信号
    delete_clicked = Signal(object)  # 传递自身作为参数
    add_clicked = Signal()

    def __init__(self, image_path=None, is_add_button=False, initial_width=200, parent=None):
        super().__init__(parent)

        # 设置最小大小
        self.setMinimumSize(50, 50)

        # 初始宽度
        self.current_width = initial_width
        self.setFixedSize(self.current_width, self.current_width)

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
        self.image_label.setMinimumSize(40, 40)
        self.layout.addWidget(self.image_label)

        self.is_add_button = is_add_button
        self.image_path = image_path

        if is_add_button:
            # 创建添加按钮
            self.setup_add_button()
        elif image_path:
            # 显示图片
            self.load_image(image_path)
            # 添加删除按钮
            self.setup_delete_button()

    def set_container_size(self, width):
        """设置容器大小"""
        self.current_width = max(50, width)
        self.setFixedSize(self.current_width, self.current_width)

        # 如果有图片，重新加载以正确缩放
        if hasattr(self, 'image_path') and self.image_path:
            self.load_image(self.image_path)

        # 如果有删除按钮，调整其位置
        delete_button = self.findChild(QPushButton)
        if delete_button:
            delete_button.move(self.width() - 15, 5)

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
        delete_button.move(self.width() - 15, 5)  # 右上角位置
        delete_button.clicked.connect(self.on_delete_clicked)

    def setup_add_button(self):
        """设置添加按钮样式"""
        self.image_label.setText("+")
        self.image_label.setStyleSheet("""
            QLabel {
                font-size: 40px;
                color: #aaaaaa;
            }
        """)
        self.setCursor(Qt.PointingHandCursor)

    def load_image(self, image_path):
        """加载并显示图片"""
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            # 计算适合容器的尺寸，减去边距
            content_width = self.current_width - 10  # 减去左右边距
            pixmap = pixmap.scaled(
                content_width,
                content_width,
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