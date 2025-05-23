import os
import json

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel,
                               QPushButton, QHBoxLayout, QFileDialog,
                               QLineEdit, QMessageBox, QScrollArea)

from src.config_manager import config_manager


class ResourceLibrary(QWidget):
    """A dockable resource library panel that displays JSON files from a resource directory."""

    # Signal to be emitted when a resource is opened
    resource_opened = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Create main layout
        self.base_resource_path = None  # Base resource directory (without pipeline)
        self.pipeline_path = None  # Full path to the pipeline subdirectory
        self.current_opened_file = None  # Path to the currently opened file
        self.is_delete_mode = False  # Track if we're in delete mode

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

        # Store references to new file widgets
        self.new_file_row = None
        self.new_file_input = None

        self.scroll_area.setWidget(self.resources_container)

        # Add components to main layout
        self.main_layout.addWidget(title_label)
        self.main_layout.addLayout(path_layout)
        self.main_layout.addWidget(self.resources_label)
        self.main_layout.addWidget(self.scroll_area)

        # Create management buttons row
        management_layout = QHBoxLayout()
        self.new_file_button = QPushButton("新建文件")
        self.new_file_button.clicked.connect(self.show_new_file_input)
        self.delete_mode_button = QPushButton("删除文件")
        self.delete_mode_button.clicked.connect(self.toggle_delete_mode)

        management_layout.addWidget(self.new_file_button)
        management_layout.addWidget(self.delete_mode_button)
        management_layout.addStretch()

        self.main_layout.addLayout(management_layout)

        # Status label
        self.status_label = QLabel("请选择资源库文件夹")
        self.main_layout.addWidget(self.status_label)

        # Initialize variables
        self.resource_items = []
        self.resource_buttons = {}  # Store buttons for each resource

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

        # Store the base resource path (without pipeline)
        self.base_resource_path = path

        # Check for resource subdirectory
        pipeline_path = os.path.join(path, "pipeline")
        if not os.path.exists(pipeline_path) or not os.path.isdir(pipeline_path):
            QMessageBox.warning(
                self,
                "无效的资源库",
                f"在选择的文件夹中未找到'pipeline'子文件夹: {path}"
            )
            self.status_label.setText("无效的资源库")
            return

        # Update the pipeline path
        self.pipeline_path = pipeline_path

        # Clear previous resources
        self.clear_resources()

        # Find all JSON files in the pipeline directory
        json_files = [f for f in os.listdir(pipeline_path)
                      if f.lower().endswith('.json') and
                      os.path.isfile(os.path.join(pipeline_path, f))]

        if not json_files:
            self.status_label.setText("未找到JSON资源文件")
            return

        # Create list items for each JSON file
        for json_file in json_files:
            self.add_resource_item(pipeline_path, json_file)
        config_manager.save_resource_library_state(self)

        # Update status
        self.status_label.setText(f"已加载 {len(json_files)} 个资源文件")

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
        # Store button reference
        self.resource_buttons[file_path] = open_button

        # Use default parameter to avoid closure issues with the lambda
        open_button.clicked.connect(lambda checked=False, path=file_path: self.handle_button_click(path))

        # Add to layout
        item_layout.addWidget(label)
        item_layout.addStretch()
        item_layout.addWidget(open_button)

        # Add to resources container
        self.resources_layout.addWidget(item_widget)
        self.resource_items.append(item_widget)

    def handle_button_click(self, file_path):
        """Handle button click - either open or delete based on mode."""
        if self.is_delete_mode:
            self.delete_resource(file_path)
        else:
            self.open_resource(file_path)

    def clear_resources(self):
        """Clear all resource items from the list."""
        for item in self.resource_items:
            self.resources_layout.removeWidget(item)
            item.deleteLater()

        self.resource_items = []
        self.resource_buttons = {}

    @Slot(str)
    def open_resource(self, file_path):
        """Handle opening a resource file."""
        # Store the currently opened file path
        print(f"打开{file_path}")
        self.current_opened_file = str(file_path)
        config_manager.save_resource_library_state(self)
        # Emit the signal
        self.resource_opened.emit(str(self.current_opened_file))

    @Slot()
    def show_new_file_input(self):
        """Show input field for creating a new file."""
        if self.new_file_row:
            return  # Already showing input

        # Create new file input row
        self.new_file_row = QWidget()
        row_layout = QHBoxLayout(self.new_file_row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        self.new_file_input = QLineEdit()
        self.new_file_input.setPlaceholderText("输入文件名...")

        save_button = QPushButton("保存")
        save_button.clicked.connect(self.save_new_file)
        save_button.setFixedWidth(60)

        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.cancel_new_file)
        cancel_button.setFixedWidth(60)

        row_layout.addWidget(self.new_file_input)
        row_layout.addWidget(save_button)
        row_layout.addWidget(cancel_button)

        # Insert after the last resource item
        self.resources_layout.addWidget(self.new_file_row)

    @Slot()
    def save_new_file(self):
        """Save the new file with empty JSON content."""
        if not self.new_file_input or not self.pipeline_path:
            return

        filename = self.new_file_input.text().strip()
        if not filename:
            QMessageBox.warning(self, "文件名错误", "请输入有效的文件名")
            return

        # Add .json extension if not present
        if not filename.endswith('.json'):
            filename += '.json'

        # Check if file already exists
        file_path = os.path.join(self.pipeline_path, filename)
        if os.path.exists(file_path):
            QMessageBox.warning(self, "文件已存在", f"文件 {filename} 已存在")
            return

        try:
            # Create empty JSON file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)

            # Add the new file to the list
            self.add_resource_item(self.pipeline_path, filename)

            # Clean up input row
            self.cancel_new_file()

            # Open the new file
            self.open_resource(file_path)

            # Save state
            config_manager.save_resource_library_state(self)

            # Update status
            self.status_label.setText(f"已创建新文件: {filename}")

        except Exception as e:
            QMessageBox.critical(self, "创建失败", f"创建文件失败: {str(e)}")

    @Slot()
    def cancel_new_file(self):
        """Cancel the new file creation."""
        if self.new_file_row:
            self.resources_layout.removeWidget(self.new_file_row)
            self.new_file_row.deleteLater()
            self.new_file_row = None
            self.new_file_input = None

    @Slot()
    def toggle_delete_mode(self):
        """Toggle between normal and delete mode."""
        self.is_delete_mode = not self.is_delete_mode

        # Update button text
        for file_path, button in self.resource_buttons.items():
            button.setText("删除" if self.is_delete_mode else "打开")
            button.setStyleSheet("background-color: #ff6b6b; color: white;" if self.is_delete_mode else "")

        # Update delete mode button
        self.delete_mode_button.setText("取消删除" if self.is_delete_mode else "删除文件")
        self.delete_mode_button.setStyleSheet("background-color: #ffd93d; color: black;" if self.is_delete_mode else "")

    def delete_resource(self, file_path):
        """Delete a resource file after confirmation."""
        filename = os.path.basename(file_path)
        result = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除文件 {filename} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if result == QMessageBox.Yes:
            try:
                os.remove(file_path)

                # Remove from UI
                for i, item in enumerate(self.resource_items):
                    # Find the item with matching file path
                    for child in item.children():
                        if isinstance(child, QPushButton) and child in self.resource_buttons.values():
                            if file_path in self.resource_buttons and self.resource_buttons[file_path] == child:
                                self.resources_layout.removeWidget(item)
                                item.deleteLater()
                                self.resource_items.pop(i)
                                del self.resource_buttons[file_path]
                                break

                # If the deleted file was currently open, clear it
                if self.current_opened_file == file_path:
                    self.current_opened_file = None

                # Save state
                config_manager.save_resource_library_state(self)

                # Update status
                self.status_label.setText(f"已删除文件: {filename}")

            except Exception as e:
                QMessageBox.critical(self, "删除失败", f"删除文件失败: {str(e)}")

    def get_state(self):
        """Get the current state of the resource library.

        Returns:
            dict: A dictionary containing the current state
        """
        state = {
            "base_resource_path": self.base_resource_path,
            "pipeline_path": self.pipeline_path,
            "current_opened_file": self.current_opened_file,
            "loaded_resources": []
        }

        # Collect loaded resources
        if self.pipeline_path and os.path.exists(self.pipeline_path):
            for resource_item in self.resource_items:
                # Find the label to get the filename
                for child in resource_item.children():
                    if isinstance(child, QLabel):
                        state["loaded_resources"].append(child.text())
                        break

        return state

    def restore_state(self, state):
        """Restore the resource library from a saved state.

        Args:
            state (dict): Dictionary containing the state to restore
        """
        # Restore base path and pipeline path
        if "base_resource_path" in state and state["base_resource_path"]:
            self.base_resource_path = state["base_resource_path"]
            self.path_input.setText(self.base_resource_path)
            # Load resources from the restored path
            self.load_resources()

            # Restore currently opened file if available
            if "current_opened_file" in state and state["current_opened_file"]:
                if os.path.exists(state["current_opened_file"]):
                    self.open_resource(state["current_opened_file"])