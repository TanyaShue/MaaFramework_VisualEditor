import json
import os

from PySide6.QtCore import QByteArray, QSettings


class ConfigManager:
    """管理应用程序配置的持久化存储。"""

    def __init__(self, app_name="MaaFrameworkVisualEditor"):
        """初始化配置管理器。"""
        self.app_name = app_name
        self.settings = QSettings(app_name, "Config")

        # 获取当前根目录
        self.app_dir = os.getcwd()  # 使用当前工作目录作为根目录

        # 在根目录下创建config文件夹
        self.config_dir = os.path.join(self.app_dir, "config")
        self.config_file = os.path.join(self.config_dir, "config.json")

        print(f"配置文件路径: {self.config_file}")

        # 如果配置目录不存在则创建
        if not os.path.exists(self.config_dir):
            try:
                os.makedirs(self.config_dir)
                print(f"已创建配置目录: {self.config_dir}")
            except Exception as e:
                print(f"创建配置目录时出错: {str(e)}")

        # 初始化默认配置
        self.config = self._get_default_config()

        # 如果存在，加载已有配置
        self._load_config()

    def _get_default_config(self):
        """返回默认配置值。"""
        return {
            "window": {
                "geometry": None,
                "state": None,
                "size": [1200, 800],
                "position": [100, 100],
                "maximized": False
            },
            "docks": {
                "node_library": {"visible": True},
                "properties": {"visible": True},
                "resource_library": {"visible": True},
                "controller": {"visible": True}
            },
            "canvas": {
                "zoom": 1.0,
                "position": [0, 0]
                # 移除节点和连接保存
            },
            "recent_files": {
                "base_resource_path": None,  # Base resource directory (without pipeline)
                "pipeline_path": None,  # Full path to pipeline directory
                "current_opened_file": None  # Currently opened resource file path
            },
            "controller": {
                "device_type": "ADB",
                "adb_address": "127.0.0.1:5555",
                "hwnd": "",
                "adb_path": "",
                "input_method": 1,
                "screenshot_method": 1,
                "connected": False
            }
        }

    def _load_config(self):
        """从文件加载配置。"""
        try:
            if os.path.exists(self.config_file):
                print(f"正在加载配置文件: {self.config_file}")
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 使用加载的值更新配置
                    self._update_dict(self.config, loaded_config)
                print("配置文件加载成功")
            else:
                print(f"配置文件不存在，将使用默认配置: {self.config_file}")
        except Exception as e:
            print(f"加载配置时出错: {str(e)}")
            import traceback
            print(traceback.format_exc())

    def _update_dict(self, target, source):
        """递归更新目标字典的值。"""
        for key, value in source.items():
            if key in target:
                if isinstance(value, dict) and isinstance(target[key], dict):
                    self._update_dict(target[key], value)
                else:
                    target[key] = value

    def save_config(self):
        """保存配置到文件。"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置时出错: {str(e)}")
            import traceback
            print(traceback.format_exc())

    def save_window_state(self, main_window):
        """保存窗口状态和几何信息。"""
        self.config["window"]["maximized"] = main_window.isMaximized()
        if not main_window.isMaximized():
            self.config["window"]["size"] = [main_window.width(), main_window.height()]
            self.config["window"]["position"] = [main_window.x(), main_window.y()]

        # 将Qt窗口状态和几何信息保存为base64字符串
        geometry = main_window.saveGeometry()
        state = main_window.saveState()
        self.config["window"]["geometry"] = bytes(geometry.toBase64()).decode()
        self.config["window"]["state"] = bytes(state.toBase64()).decode()

        # 保存停靠窗口可见性
        for name, dock in main_window.dock_widgets.items():
            self.config["docks"][name]["visible"] = dock.isVisible()

        self.save_config()

    def restore_window_state(self, main_window):
        """恢复窗口状态和几何信息。"""
        try:
            # 如果可用，恢复几何和状态
            if self.config["window"]["geometry"] and self.config["window"]["state"]:
                geometry = QByteArray.fromBase64(self.config["window"]["geometry"].encode())
                state = QByteArray.fromBase64(self.config["window"]["state"].encode())
                main_window.restoreGeometry(geometry)
                main_window.restoreState(state)
            else:
                # 使用尺寸和位置
                if self.config["window"]["maximized"]:
                    main_window.showMaximized()
                else:
                    size = self.config["window"]["size"]
                    pos = self.config["window"]["position"]
                    main_window.resize(size[0], size[1])
                    main_window.move(pos[0], pos[1])

            # 恢复停靠窗口可见性
            for name, dock_config in self.config["docks"].items():
                if name in main_window.dock_widgets:
                    main_window.dock_widgets[name].setVisible(dock_config["visible"])

        except Exception as e:
            print(f"恢复窗口状态时出错: {str(e)}")
            import traceback
            print(traceback.format_exc())

    def save_canvas_state(self, canvas):
        """保存画布状态，仅包括缩放和位置。"""
        try:
            # 仅保存基本视图状态（缩放和位置）
            self.config["canvas"]["zoom"] = canvas.view.transform().m11()
            center = canvas.view.mapToScene(canvas.view.viewport().rect().center())
            self.config["canvas"]["position"] = [center.x(), center.y()]
        except Exception as e:
            print(f"保存画布状态时出错: {str(e)}")
            import traceback
            print(traceback.format_exc())

        self.save_config()

    def restore_canvas_state(self, canvas):
        """恢复画布状态，仅包括缩放和位置。"""
        try:
            # 恢复基本的视图状态（缩放和位置）
            zoom = self.config["canvas"]["zoom"]
            pos = self.config["canvas"]["position"]

            # 设置缩放
            canvas.view.resetTransform()
            canvas.view.scale(zoom, zoom)

            # 设置位置
            canvas.view.centerOn(pos[0], pos[1])

        except Exception as e:
            print(f"恢复画布状态时出错: {str(e)}")
            import traceback
            print(traceback.format_exc())

    def save_controller_state(self, controller_view):
        """保存控制器视图状态。"""
        try:
            # 保存设备类型
            device_type = controller_view.device_type_combo.currentData() if hasattr(controller_view,
                                                                                     'device_type_combo') else "ADB"
            self.config["controller"]["device_type"] = device_type

            # 根据设备类型保存不同的地址信息
            if device_type == "ADB" and hasattr(controller_view, 'adb_address_edit') and hasattr(controller_view,
                                                                                                 "adb_path_edit"):
                self.config["controller"]["adb_address"] = controller_view.adb_address_edit.text()
                self.config["controller"]["adb_path"] = controller_view.adb_path_edit.text()
            elif device_type == "WIN32" and hasattr(controller_view, 'hwnd_edit'):
                self.config["controller"]["hwnd"] = controller_view.hwnd_edit.text()

                # 保存Win32特有的配置
                if hasattr(controller_view, 'input_method_combo'):
                    self.config["controller"]["input_method"] = controller_view.input_method_combo.currentData()
                if hasattr(controller_view, 'screenshot_method_combo'):
                    self.config["controller"][
                        "screenshot_method"] = controller_view.screenshot_method_combo.currentData()

            # 保存连接状态
            if hasattr(controller_view, 'is_connected'):
                self.config["controller"]["connected"] = controller_view.is_connected

            # 保存当前任务文件路径
            if hasattr(controller_view, 'current_task_file'):
                self.config["recent_files"]["current_task_file"] = controller_view.current_task_file

            self.save_config()
        except Exception as e:
            print(f"保存控制器状态时出错: {str(e)}")
            import traceback
            print(traceback.format_exc())

    def restore_controller_state(self, controller_view):
        """恢复控制器视图状态。"""
        try:
            # 设置设备类型
            if hasattr(controller_view, 'device_type_combo'):
                device_type = self.config["controller"]["device_type"]
                for i in range(controller_view.device_type_combo.count()):
                    if controller_view.device_type_combo.itemData(i) == device_type:
                        controller_view.device_type_combo.setCurrentIndex(i)
                        break

            # 根据设备类型设置相应的地址信息
            device_type = self.config["controller"]["device_type"]
            if device_type == "ADB" and hasattr(controller_view, 'adb_address_edit'):
                controller_view.adb_address_edit.setText(self.config["controller"]["adb_address"])
                controller_view.adb_path_edit.setText(str(self.config["controller"]["adb_path"]))
            elif device_type == "WIN32" and hasattr(controller_view, 'hwnd_edit'):
                controller_view.hwnd_edit.setText(self.config["controller"]["hwnd"])

                # 设置Win32特有的配置
                if hasattr(controller_view, 'input_method_combo'):
                    input_method = self.config["controller"]["input_method"]
                    for i in range(controller_view.input_method_combo.count()):
                        if controller_view.input_method_combo.itemData(i) == input_method:
                            controller_view.input_method_combo.setCurrentIndex(i)
                            break

                if hasattr(controller_view, 'screenshot_method_combo'):
                    screenshot_method = self.config["controller"]["screenshot_method"]
                    for i in range(controller_view.screenshot_method_combo.count()):
                        if controller_view.screenshot_method_combo.itemData(i) == screenshot_method:
                            controller_view.screenshot_method_combo.setCurrentIndex(i)
                            break

            # 如果需要，重新连接
            if (hasattr(controller_view, 'is_connected') and
                    self.config["controller"]["connected"] and
                    hasattr(controller_view, 'connect_device')):
                controller_view.connect_device()

        except Exception as e:
            print(f"恢复控制器状态时出错: {str(e)}")
            import traceback
            print(traceback.format_exc())

    def save_project_state(self, main_window):
        """保存当前打开的项目。"""
        if main_window.current_file_path:
            self.config["recent_files"]["project"] = main_window.current_file_path
        self.save_config()

    def get_last_project(self):
        """获取上次打开的项目文件路径。"""
        return self.config["recent_files"]["project"]

    def save_task_file_state(self, file_path):
        """保存当前打开的任务文件路径。"""
        self.config["recent_files"]["current_task_file"] = file_path
        self.save_config()

    def save_resource_library_state(self, resource_library):
        """Save resource library state."""
        if resource_library.base_resource_path:
            self.config["recent_files"]["base_resource_path"] = resource_library.base_resource_path

        if resource_library.pipeline_path:
            self.config["recent_files"]["pipeline_path"] = resource_library.pipeline_path

        if resource_library.current_opened_file:
            self.config["recent_files"]["current_opened_file"] = resource_library.current_opened_file

        self.save_config()

    def restore_resource_library_state(self, resource_library):
        """Restore resource library state."""
        try:
            state = {
                "base_resource_path": self.config["recent_files"]["base_resource_path"],
                "pipeline_path": self.config["recent_files"]["pipeline_path"],
                "current_opened_file": self.config["recent_files"]["current_opened_file"]
            }

            resource_library.restore_state(state)
        except Exception as e:
            print(f"Error restoring resource library state: {str(e)}")
            import traceback
            print(traceback.format_exc())

    def get_last_task_file(self):
        """Get the last opened task file path."""
        return self.config["recent_files"]["current_opened_file"]
config_manager = ConfigManager()