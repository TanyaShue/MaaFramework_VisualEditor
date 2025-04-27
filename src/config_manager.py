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
                "position": [0, 0],
                "nodes": [],
                "connections": []
            },
            "recent_files": {
                "project": None,
                "resource_dir": None
            },
            "controller": {
                "device_type": "ADB",
                "device_address": "127.0.0.1:5555",
                "connected": False
            },
            "autosave": {
                "enabled": True,
                "interval": 5  # 分钟
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
        """保存画布状态，包括缩放、位置、节点和连接。"""
        # 获取画布的完整状态
        if hasattr(canvas, 'get_state'):
            canvas_state = canvas.get_state()

            # 更新配置中的画布状态
            self.config["canvas"]["zoom"] = canvas_state["transform"]["scale_x"]
            self.config["canvas"]["position"] = [
                canvas_state["center"]["x"],
                canvas_state["center"]["y"]
            ]

            # 保存节点和连接信息
            self.config["canvas"]["nodes"] = canvas_state["nodes"]
            self.config["canvas"]["connections"] = canvas_state["connections"]
        else:
            # 如果画布没有get_state方法，退回到基本状态保存
            self.config["canvas"]["zoom"] = canvas.view.transform().m11()
            center = canvas.view.mapToScene(canvas.view.viewport().rect().center())
            self.config["canvas"]["position"] = [center.x(), center.y()]

        self.save_config()

    def restore_canvas_state(self, canvas):
        """恢复画布状态，包括节点和连接。"""
        try:
            # 首先恢复基本的视图状态（缩放和位置）
            zoom = self.config["canvas"]["zoom"]
            pos = self.config["canvas"]["position"]

            # 设置缩放
            canvas.view.resetTransform()
            canvas.view.scale(zoom, zoom)

            # 设置位置
            canvas.view.centerOn(pos[0], pos[1])

            # 如果有节点和连接数据，并且画布有restore_state方法，则恢复完整状态
            if ("nodes" in self.config["canvas"] or "connections" in self.config["canvas"]) and hasattr(canvas,
                                                                                                        'restore_state'):
                canvas_state = {
                    'transform': {
                        'scale_x': zoom,
                        'scale_y': zoom,
                        'dx': 0,
                        'dy': 0
                    },
                    'center': {'x': pos[0], 'y': pos[1]},
                    'nodes': self.config["canvas"].get("nodes", []),
                    'connections': self.config["canvas"].get("connections", [])
                }
                canvas.restore_state(canvas_state)

        except Exception as e:
            print(f"恢复画布状态时出错: {str(e)}")
            import traceback
            print(traceback.format_exc())

    def save_resource_library_state(self, resource_library):
        """保存资源库状态。"""
        if resource_library.current_path:
            self.config["recent_files"]["resource_dir"] = resource_library.current_path
        self.save_config()

    def restore_resource_library_state(self, resource_library):
        """恢复资源库状态。"""
        try:
            if self.config["recent_files"]["resource_dir"]:
                parent_dir = os.path.dirname(self.config["recent_files"]["resource_dir"])
                resource_library.path_input.setText(parent_dir)
                resource_library.load_resources()
        except Exception as e:
            print(f"恢复资源库状态时出错: {str(e)}")
            import traceback
            print(traceback.format_exc())

    def save_controller_state(self, controller_view):
        """保存控制器视图状态。"""
        self.config["controller"]["device_type"] = controller_view.device_combo.currentText()
        self.config["controller"]["device_address"] = controller_view.address_input.text()
        # 需要在ControllerView中添加connected标志
        if hasattr(controller_view, 'is_connected'):
            self.config["controller"]["connected"] = controller_view.is_connected
        self.save_config()

    def restore_controller_state(self, controller_view):
        """恢复控制器视图状态。"""
        try:
            # 设置设备类型
            index = controller_view.device_combo.findText(self.config["controller"]["device_type"])
            if index >= 0:
                controller_view.device_combo.setCurrentIndex(index)

            # 设置设备地址
            controller_view.address_input.setText(self.config["controller"]["device_address"])

            # 如果需要，重新连接
            if hasattr(controller_view, 'is_connected') and self.config["controller"]["connected"]:
                if hasattr(controller_view, 'connect_device'):
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

config_manager=ConfigManager()