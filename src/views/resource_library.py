from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel,
                               QPushButton, QHBoxLayout, QFileDialog,
                               QLineEdit, QMessageBox, QScrollArea)
from PySide6.QtCore import Signal, Slot
import os


class ResourceLibrary(QWidget):
    """A dockable resource library panel that displays JSON files from a resource directory."""

    # Signal to be emitted when a resource is opened
    resource_opened = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Create main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)

        # Create and configure title label
        title_label = QLabel("资源库")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        # Create path selection controls
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("输入资源库路径...")
        browse_button = QPushButton("浏览...")
        browse_button.clicked.connect(self.browse_folder)
        load_button = QPushButton("加载")
        load_button.clicked.connect(self.load_resources)

        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_button)
        path_layout.addWidget(load_button)

        # Resources section
        self.resources_label = QLabel("资源列表")
        self.resources_label.setStyleSheet("font-weight: bold; margin-top: 10px;")

        # Create a scrollable area for resources
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        # Container for resource items
        self.resources_container = QWidget()
        self.resources_layout = QVBoxLayout(self.resources_container)
        self.resources_layout.setContentsMargins(0, 0, 0, 0)
        self.resources_layout.addStretch()

        self.scroll_area.setWidget(self.resources_container)

        # Add components to main layout
        self.main_layout.addWidget(title_label)
        self.main_layout.addLayout(path_layout)
        self.main_layout.addWidget(self.resources_label)
        self.main_layout.addWidget(self.scroll_area)

        # Status label
        self.status_label = QLabel("请选择资源库文件夹")
        self.main_layout.addWidget(self.status_label)

        # Initialize variables
        self.current_path = None
        self.resource_items = []

    @Slot()
    def browse_folder(self):
        """Open a file dialog to browse for a folder."""
        folder_path = QFileDialog.getExistingDirectory(
            self, "选择资源库文件夹", "", QFileDialog.ShowDirsOnly
        )

        if folder_path:
            self.path_input.setText(folder_path)
            self.load_resources()

    @Slot()
    def load_resources(self):
        """Load resources from the specified path."""
        path = self.path_input.text().strip()

        if not path:
            QMessageBox.warning(self, "路径错误", "请输入有效的路径")
            return

        # Check if path exists
        if not os.path.exists(path):
            QMessageBox.warning(self, "路径错误", f"路径不存在: {path}")
            return

        # Check for resource subdirectory
        resource_path = os.path.join(path, "pipeline")
        if not os.path.exists(resource_path) or not os.path.isdir(resource_path):
            QMessageBox.warning(
                self,
                "无效的资源库",
                f"在选择的文件夹中未找到'pipeline'子文件夹: {path}"
            )
            self.status_label.setText("无效的资源库")
            return

        # Clear previous resources
        self.clear_resources()

        # Find all JSON files in the resource directory
        json_files = [f for f in os.listdir(resource_path)
                      if f.lower().endswith('.json') and
                      os.path.isfile(os.path.join(resource_path, f))]

        if not json_files:
            self.status_label.setText("未找到JSON资源文件")
            return

        # Create list items for each JSON file
        for json_file in json_files:
            self.add_resource_item(resource_path, json_file)

        # Update status
        self.status_label.setText(f"已加载 {len(json_files)} 个资源文件")
        self.current_path = resource_path

    def add_resource_item(self, resource_path, filename):
        """Add a resource item to the list with an open button."""
        # Create container for the item
        item_widget = QWidget()
        item_layout = QHBoxLayout(item_widget)
        item_layout.setContentsMargins(0, 0, 0, 0)

        # Create label for filename
        label = QLabel(filename)

        # Create open button
        open_button = QPushButton("打开")
        open_button.setFixedWidth(60)
        file_path = os.path.join(resource_path, filename)
        # Use default parameter to avoid closure issues with the lambda
        open_button.clicked.connect(lambda checked=False, path=file_path: self.open_resource(path))

        # Add to layout
        item_layout.addWidget(label)
        item_layout.addStretch()
        item_layout.addWidget(open_button)

        # Add to resources container
        self.resources_layout.insertWidget(self.resources_layout.count() - 1, item_widget)
        self.resource_items.append(item_widget)

    def clear_resources(self):
        """Clear all resource items from the list."""
        for item in self.resource_items:
            self.resources_layout.removeWidget(item)
            item.deleteLater()

        self.resource_items = []

    @Slot(str)
    def open_resource(self, file_path):
        """Handle opening a resource file."""
        print(file_path)  # Print the JSON file path as requested
        self.resource_opened.emit(file_path)

    # 在ResourceLibrary类中添加以下方法

    def get_state(self):
        """获取资源库的当前状态信息。

        Returns:
            dict: 包含当前目录和加载的资源的状态字典
        """
        state = {
            "current_path": self.current_path,
            "loaded_resources": []
        }

        # 收集已加载的资源
        if self.current_path:
            resource_path = os.path.join(os.path.dirname(self.current_path), "pipeline")
            if os.path.exists(resource_path):
                for resource_item in self.resource_items:
                    # 查找label以获取文件名
                    for child in resource_item.children():
                        if isinstance(child, QLabel):
                            state["loaded_resources"].append(child.text())
                            break

        return state

    def restore_state(self, state):
        """从保存的状态恢复资源库。

        Args:
            state (dict): 包含要恢复的状态信息的字典
        """
        if "current_path" in state and state["current_path"]:
            self.current_path = state["current_path"]
            parent_dir = os.path.dirname(self.current_path)
            self.path_input.setText(parent_dir)
            self.load_resources()

            # 如果需要恢复特定资源的选择状态，可以在这里实现