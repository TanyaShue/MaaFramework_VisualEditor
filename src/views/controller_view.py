import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QFileDialog)
from PySide6.QtGui import QPixmap, QImage
from qasync import asyncSlot
from PIL import Image

from src.maafw import maafw
from src.views.components.deviceImage_view import DeviceImageView


class ControllerView(QWidget):
    # 节点变更信号
    OpenNodeChanged = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 初始化状态变量
        self.open_node = None
        self.file_name = None
        self.current_node_name = None
        self.is_connected = False
        self.selection_mode = False

        # 设置UI
        self.setup_ui()

    def setup_ui(self):
        """设置UI界面"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # 工具栏布局
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(10, 5, 10, 5)
        toolbar_layout.setSpacing(10)

        # 连接状态标签
        self.connection_status = QLabel("未连接")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        toolbar_layout.addWidget(self.connection_status)

        # 模式状态标签
        self.mode_status_label = QLabel("当前模式: 显示模式")
        self.mode_status_label.setStyleSheet("font-weight: bold;")
        toolbar_layout.addWidget(self.mode_status_label)

        # 截图按钮
        self.screenshot_btn = QPushButton("截图")
        self.screenshot_btn.clicked.connect(self.update_device_img)
        toolbar_layout.addWidget(self.screenshot_btn)

        # 导入图片按钮
        self.import_image_btn = QPushButton("导入图片")
        self.import_image_btn.clicked.connect(self.import_image)
        toolbar_layout.addWidget(self.import_image_btn)

        # 重置视图按钮
        self.reset_view_btn = QPushButton("重置视图")
        self.reset_view_btn.clicked.connect(self.reset_view)
        toolbar_layout.addWidget(self.reset_view_btn)

        # 添加弹性空间，将后面的标签推到最右侧
        toolbar_layout.addStretch()

        # 添加选中节点标签
        self.current_node_label = QLabel("选中节点: 未选择")
        toolbar_layout.addWidget(self.current_node_label)

        # 打开文件标签
        self.task_file_label = QLabel("打开文件: 未选择")
        toolbar_layout.addWidget(self.task_file_label)

        main_layout.addLayout(toolbar_layout)

        # 创建并添加设备图像视图
        self.device_view = DeviceImageView(control=self)
        self.device_view.selectionChanged.connect(self.on_selection_changed)
        self.device_view.selectionCleared.connect(self.on_selection_cleared)
        self.device_view.modeChangedSignal.connect(self.update_mode_status)

        main_layout.addWidget(self.device_view)

    def update_connection_status(self, is_connected):
        """更新连接状态标签"""
        self.is_connected = is_connected

        if is_connected:
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

    def import_image(self):
        """从计算机导入图片并缩放到1280x720"""
        # 创建文件对话框
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("选择图片")
        file_dialog.setNameFilter("图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)")
        file_dialog.setFileMode(QFileDialog.ExistingFile)

        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]

            try:
                # 使用PIL打开并缩放图片
                pil_image = Image.open(file_path)

                # 转换为RGB模式（如果需要）
                if pil_image.mode not in ('RGB', 'RGBA'):
                    pil_image = pil_image.convert('RGB')

                # 缩放到1280x720
                target_size = (1280, 720)
                pil_image = pil_image.resize(target_size, Image.Resampling.LANCZOS)

                # 显示缩放后的图片
                self.display_image(pil_image)

            except Exception as e:
                print(f"导入图片失败: {e}")

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
        # 处理选择区域变化事件
        pass

    def on_selection_cleared(self):
        """当选择区域被清除时"""
        # 处理选择区域清除事件
        pass

    def set_node(self, node):
        """更新已选中节点的标签"""
        try:
            self.current_node_name = node.task_node.name
            self.open_node = node
            label_text = f"选中节点: {self.current_node_name}"
        except (IndexError, AttributeError, TypeError):
            self.current_node_name = None
            label_text = "选中节点: 未选择"

        self.current_node_label.setText(label_text)

    def update_task_file(self, file_path):
        """更新打开文件的标签，只显示文件名"""
        if not file_path:
            self.task_file_label.setText("打开文件: 未选择")
        else:
            # 提取文件路径中的文件名部分
            self.file_name = os.path.basename(file_path)
            self.task_file_label.setText(f"打开文件: {self.file_name}")