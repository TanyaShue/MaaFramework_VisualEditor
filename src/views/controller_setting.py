import json
import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QFormLayout, QLineEdit, QPushButton, QComboBox,
                               QGroupBox, QScrollArea, QGridLayout, QFrame, QMessageBox)
from maa.toolkit import Toolkit
from qasync import asyncSlot

from src.config_manager import config_manager
from src.maafw import maafw


class DeviceSearchThread(QThread):
    """用于后台搜索设备的线程"""
    devices_found = Signal(list)
    search_error = Signal(str)

    def __init__(self, search_type):
        super().__init__()
        self.search_type = search_type

    def run(self):
        try:
            # 搜索设备
            devices = []
            if self.search_type == "ADB":
                devices = Toolkit.find_adb_devices()
            elif self.search_type == "WIN32":
                devices = Toolkit.find_desktop_windows()
                devices = [device for device in devices if device.window_name != '']
            self.devices_found.emit(devices)
        except Exception as e:
            self.search_error.emit(str(e))


class DeviceSettingsView(QWidget):
    # 信号定义
    connectionStatusChanged = Signal(bool)
    deviceConnected = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # 初始化状态变量
        self.found_devices = []
        self.select_device = None
        self.is_connected = False

        # 创建UI
        self.setupUI()

    def setupUI(self):
        """设置UI界面"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(20)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.NoFrame)  # 移除边框,使界面更加整洁

        # 创建内容小部件
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(20)

        # 合并后的设备类型和搜索组 - 美化边框和间距
        search_group = QGroupBox("设备搜索与类型")
        search_group.setStyleSheet(
            "QGroupBox {border: 1px solid #bdc3c7; border-radius: 5px; margin-top: 10px; font-weight: bold;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 10px; padding: 0 5px;}")
        grid_layout = QGridLayout(search_group)
        grid_layout.setContentsMargins(15, 20, 15, 15)
        grid_layout.setSpacing(12)

        # 第一行: 控制器类型标签和下拉框与搜索按钮和状态在同一行
        type_label = QLabel("控制器类型:")
        type_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid_layout.addWidget(type_label, 0, 0)

        self.device_type_combo = QComboBox()
        self.device_type_combo.setStyleSheet("padding: 5px;")
        self.device_type_combo.addItem("ADB设备", "ADB")
        self.device_type_combo.addItem("Win32窗口", "WIN32")
        self.device_type_combo.currentIndexChanged.connect(self.device_type_changed)
        grid_layout.addWidget(self.device_type_combo, 0, 1)

        # 第一行右侧: 搜索按钮和状态
        self.search_btn = QPushButton("搜索设备")
        self.search_btn.setStyleSheet("padding: 5px; background-color: #3498db; color: white; border-radius: 4px;")
        self.search_btn.clicked.connect(self.search_devices)
        self.search_btn.setCursor(QCursor(Qt.PointingHandCursor))  # 鼠标悬停时显示手型光标
        grid_layout.addWidget(self.search_btn, 0, 2)

        self.search_status = QLabel("未搜索")
        self.search_status.setStyleSheet("color: #7f8c8d; font-style: italic;")
        grid_layout.addWidget(self.search_status, 0, 3)

        # 第二行: 设备标签和下拉框
        device_label = QLabel("发现的设备:")
        device_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid_layout.addWidget(device_label, 1, 0)

        self.device_combo = QComboBox()
        self.device_combo.setStyleSheet("padding: 5px;")
        self.device_combo.setMinimumWidth(200)
        self.device_combo.currentIndexChanged.connect(self.device_selected)
        grid_layout.addWidget(self.device_combo, 1, 1, 1, 3)  # 跨越3列

        content_layout.addWidget(search_group)

        # 设备配置组 - 美化边框和间距
        self.config_group = QGroupBox("设备配置")
        self.config_group.setStyleSheet(
            "QGroupBox {border: 1px solid #bdc3c7; border-radius: 5px; margin-top: 10px; font-weight: bold;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 10px; padding: 0 5px;}")
        cfg_layout = QVBoxLayout(self.config_group)
        cfg_layout.setContentsMargins(15, 20, 15, 15)
        cfg_layout.setSpacing(15)

        # 配置栈
        self.controller_stack = QComboBox()
        self.controller_stack.setVisible(False)  # 我们使用不同的方法代替栈

        # ADB配置页面
        self.adb_widget = QGroupBox("ADB设置")
        self.adb_widget.setStyleSheet("QGroupBox {border: 1px solid #bdc3c7; border-radius: 5px; margin-top: 5px;}")
        self.adb_widget.setVisible(False)
        adb_form = QFormLayout(self.adb_widget)
        adb_form.setLabelAlignment(Qt.AlignRight)
        adb_form.setSpacing(10)
        adb_form.setContentsMargins(10, 15, 10, 10)

        self.adb_path_edit = QLineEdit()
        self.adb_path_edit.setStyleSheet("padding: 5px;")
        self.adb_address_edit = QLineEdit()
        self.adb_address_edit.setStyleSheet("padding: 5px;")
        self.config_edit = QLineEdit()
        self.config_edit.setStyleSheet("padding: 5px;")

        adb_form.addRow("ADB 路径:", self.adb_path_edit)
        adb_form.addRow("ADB 地址:", self.adb_address_edit)
        adb_form.addRow("配置:", self.config_edit)

        # Win32配置页面
        self.win32_widget = QGroupBox("Win32设置")
        self.win32_widget.setStyleSheet("QGroupBox {border: 1px solid #bdc3c7; border-radius: 5px; margin-top: 5px;}")
        self.win32_widget.setVisible(False)
        win32_form = QFormLayout(self.win32_widget)
        win32_form.setLabelAlignment(Qt.AlignRight)
        win32_form.setSpacing(10)
        win32_form.setContentsMargins(10, 15, 10, 10)

        self.hwnd_edit = QLineEdit()
        self.hwnd_edit.setStyleSheet("padding: 5px;")

        self.input_method_combo = QComboBox()
        self.input_method_combo.setStyleSheet("padding: 5px;")
        self.input_method_combo.addItem("Seize", 1)
        self.input_method_combo.addItem("SendMessage", 2)

        self.screenshot_method_combo = QComboBox()
        self.screenshot_method_combo.setStyleSheet("padding: 5px;")
        self.screenshot_method_combo.addItem("GDI", 1)
        self.screenshot_method_combo.addItem("FramePool", 2)
        self.screenshot_method_combo.addItem("DXGI_DesktopDup", 3)

        win32_form.addRow("窗口句柄 (hWnd):", self.hwnd_edit)
        win32_form.addRow("输入方法:", self.input_method_combo)
        win32_form.addRow("截图方法:", self.screenshot_method_combo)

        cfg_layout.addWidget(self.adb_widget)
        cfg_layout.addWidget(self.win32_widget)

        content_layout.addWidget(self.config_group)

        # 资源连接组 - 添加GroupBox使其更加美观
        resource_agent_group = QGroupBox("资源与Agent连接")
        resource_agent_group.setStyleSheet(
            "QGroupBox {border: 1px solid #bdc3c7; border-radius: 5px; margin-top: 10px; font-weight: bold;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 10px; padding: 0 5px;}")
        resource_agent_layout = QVBoxLayout(resource_agent_group)
        resource_agent_layout.setContentsMargins(15, 20, 15, 15)
        resource_agent_layout.setSpacing(15)

        # 创建资源连接组 - 水平布局
        resource_layout = QHBoxLayout()
        resource_layout.setSpacing(10)

        self.resource_path_edit = QLineEdit()
        self.resource_path_edit.setStyleSheet("padding: 5px;")
        self.resource_path_edit.setPlaceholderText("资源路径")

        btn_connect_res = QPushButton("连接资源")
        btn_connect_res.setStyleSheet("padding: 5px; background-color: #2ecc71; color: white; border-radius: 4px;")
        btn_connect_res.setCursor(QCursor(Qt.PointingHandCursor))
        btn_connect_res.clicked.connect(self.connect_mfw_res)

        resource_layout.addWidget(self.resource_path_edit, 3)  # 3:1的比例
        resource_layout.addWidget(btn_connect_res, 1)

        # 创建agent连接组 - 水平布局
        agent_layout = QHBoxLayout()
        agent_layout.setSpacing(10)

        self.agent_id_edit = QLineEdit()
        self.agent_id_edit.setStyleSheet("padding: 5px;")
        self.agent_id_edit.setPlaceholderText("Agent_id")

        btn_connect_agent = QPushButton("连接Agent")
        btn_connect_agent.setStyleSheet("padding: 5px; background-color: #2ecc71; color: white; border-radius: 4px;")
        btn_connect_agent.setCursor(QCursor(Qt.PointingHandCursor))
        btn_connect_agent.clicked.connect(self.connect_mfw_agent)

        agent_layout.addWidget(self.agent_id_edit, 3)  # 3:1的比例
        agent_layout.addWidget(btn_connect_agent, 1)

        # 添加到资源和Agent组
        resource_agent_layout.addLayout(resource_layout)
        resource_agent_layout.addLayout(agent_layout)

        content_layout.addWidget(resource_agent_group)

        # 主要连接按钮组 - 放置在最下方
        btn_group = QGroupBox()
        btn_group.setStyleSheet("QGroupBox {border: none;}")
        btn_layout = QHBoxLayout(btn_group)
        btn_layout.setContentsMargins(0, 10, 0, 0)
        btn_layout.setSpacing(15)

        btn_connect = QPushButton("连接设备")
        btn_connect.setMinimumHeight(40)
        btn_connect.setStyleSheet(
            "background-color: #3498db; color: white; font-weight: bold; border-radius: 5px; font-size: 14px;")
        btn_connect.setCursor(QCursor(Qt.PointingHandCursor))
        btn_connect.clicked.connect(self.connect_device)

        btn_disconnect = QPushButton("断开连接")
        btn_disconnect.setMinimumHeight(40)
        btn_disconnect.setStyleSheet(
            "background-color: #e74c3c; color: white; font-weight: bold; border-radius: 5px; font-size: 14px;")
        btn_disconnect.setCursor(QCursor(Qt.PointingHandCursor))
        btn_disconnect.clicked.connect(self.disconnect_device)

        btn_layout.addWidget(btn_connect)
        btn_layout.addWidget(btn_disconnect)

        content_layout.addWidget(btn_group)
        content_layout.addStretch(1)

        # 设置滚动区域
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        # 默认显示ADB设置
        self.device_type_changed(0)

    def device_type_changed(self, index):
        """当控制器类型变更时的处理函数"""
        device_type = self.device_type_combo.currentData()

        # 根据选择的设备类型显示相应配置页面
        if device_type == "ADB":
            self.adb_widget.setVisible(True)
            self.win32_widget.setVisible(False)
        else:  # WIN32
            self.adb_widget.setVisible(False)
            self.win32_widget.setVisible(True)

        self.device_combo.clear()
        self.search_status.setText("未搜索")
        self.found_devices = []

    def search_devices(self):
        """搜索设备"""
        self.search_btn.setEnabled(False)
        self.search_status.setText("正在搜索...")
        self.device_combo.clear()

        device_type = self.device_type_combo.currentData()
        self.search_thread = DeviceSearchThread(device_type)
        self.search_thread.devices_found.connect(self.on_devices_found)
        self.search_thread.search_error.connect(self.on_search_error)
        self.search_thread.finished.connect(self.on_search_completed)
        self.search_thread.start()

    def on_devices_found(self, devices):
        """处理找到的设备"""
        self.device_combo.clear()
        self.found_devices = devices
        if devices:
            for device in devices:
                if hasattr(device, 'address'):  # ADB设备
                    text = f"{device.name} - {device.address}"
                elif hasattr(device, 'hwnd'):  # WIN32窗口
                    text = f"{device.window_name} - {device.hwnd}"
                else:
                    text = str(device)
                self.device_combo.addItem(text)
            self.search_status.setText(f"找到 {len(devices)} 个设备")
        else:
            self.device_combo.addItem("未找到设备")
            self.search_status.setText("未找到设备")

    def on_search_error(self, error_msg):
        """处理搜索错误"""
        self.device_combo.clear()
        self.device_combo.addItem("搜索出错")
        self.search_status.setText(f"搜索出错: {error_msg}")

    def on_search_completed(self):
        """搜索完成后的处理"""
        self.search_btn.setEnabled(True)
        self.search_thread = None

    def device_selected(self, index):
        """当选择设备时填充相应字段"""
        if 0 <= index < len(self.found_devices):
            device = self.found_devices[index]
            device_type = self.device_type_combo.currentData()
            self.select_device = device

            if device_type == "ADB":
                # 填充ADB设备字段
                if device.address:
                    self.adb_address_edit.setText(str(device.address))
                if device.adb_path:
                    self.adb_path_edit.setText(str(device.adb_path))
                if device.config:
                    self.config_edit.setText(str(device.config))
            elif device_type == "WIN32":
                # 填充Win32设备字段
                if device.hwnd:
                    self.hwnd_edit.setText(str(device.hwnd))

    @asyncSlot()
    async def connect_device(self) ->bool:
        """连接到指定设备"""
        try:
            device_type = self.device_type_combo.currentData()
            if device_type == "ADB":
                address = self.adb_address_edit.text()
                adb_path = self.adb_path_edit.text()
                config_text = str(self.config_edit.text())
                # 将config_text转换为字典
                if config_text == "":
                    config_dict = {}
                else:
                    try:
                        # 尝试解析为JSON格式的字典
                        config_dict = json.loads(config_text)
                        if not isinstance(config_dict, dict):
                            raise ValueError("配置必须是有效的JSON对象格式")
                    except json.JSONDecodeError:
                        print("错误: 配置必须是有效的JSON格式，例如: {\"key\": \"value\"}")
                        QMessageBox.critical(self, "配置错误", "配置必须是有效的JSON格式，例如: {\"key\": \"value\"}")
                        return False
                    except ValueError as e:
                        print(f"错误: {str(e)}")
                        QMessageBox.critical(self, "配置错误", str(e))
                        return False
                # 连接到ADB设备
                connected, error = await maafw.connect_adb(adb_path, address, config_dict)
                if connected:
                    print(f"成功连接到ADB设备: {address}")
                    self.is_connected = True
                else:
                    print(f"连接ADB设备失败: {error}")
                    self.is_connected = False
            else:  # WIN32
                hwnd_text = self.hwnd_edit.text()
                input_method = self.input_method_combo.currentData()
                screenshot_method = self.screenshot_method_combo.currentData()

                # 连接到Win32窗口
                connected, error = await maafw.connect_win32hwnd(hwnd_text, screenshot_method, input_method)
                if connected:
                    print(f"成功连接到Win32窗口: {hwnd_text}")
                    self.is_connected = True
                else:
                    print(f"连接Win32窗口失败: {error}")
                    self.is_connected = False

            # 发送连接状态变化信号
            self.connectionStatusChanged.emit(self.is_connected)

            if self.is_connected:
                self.deviceConnected.emit()
                return True
            return False
        except Exception as e:
            print(f"连接设备时发生错误: {str(e)}")
            self.is_connected = False
            self.connectionStatusChanged.emit(False)
            return False

    @asyncSlot()
    async def connect_mfw_res(self) ->bool:
        """连接MAA资源"""
        try:
            res_path = Path(config_manager.config["recent_files"]["base_resource_path"])
            success, error = await maafw.load_resource([res_path])

            if success:
                print(f"成功连接资源: {res_path}")
                return True
            else:
                print(f"连接资源失败: {error}")
            # agent_id=await maafw.create_agent("maa-agent-server")
            # await maafw.connect_agent("maa-agent-server")
            # if agent_id:
            #     print(f"agent_id: {agent_id}")
            return False
        except Exception as e:
            print(f"连接资源时发生错误: {str(e)}")
        return False

    @asyncSlot()
    async def connect_mfw_agent(self) ->bool:
        """连接MAA资源"""
        try:
            self.agent_id=self.agent_id_edit.text().strip()
            agent_id_input = self.agent_id_edit.text().strip()
            agent_id=await maafw.create_agent(agent_id_input)
            print(f"当前agentID{agent_id}")
            success=await maafw.connect_agent()
            if success:
                print(f"agent连接成功 agent_id: {agent_id}")
                return True
            return False
        except Exception as e:
            print(f"连接agent时发生错误: {str(e)}")
        return False

    @asyncSlot()
    def disconnect_device(self):
        """断开当前设备连接"""
        # 断开连接逻辑
        self.is_connected = False
        self.connectionStatusChanged.emit(False)
        print("断开设备连接")