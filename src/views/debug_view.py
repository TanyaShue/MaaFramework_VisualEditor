from typing import List

from PySide6.QtWidgets import (
    QTabWidget, QLabel, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QScrollArea, QFrame, QGridLayout
)
from PySide6.QtCore import Qt, Signal, QMetaObject, Slot, Q_ARG, QObject
from PySide6.QtGui import QCursor
from maa.notification_handler import NotificationHandler, NotificationType
from qasync import asyncSlot

from src.maafw import maafw
from src.views.components.reco_detail_view import RecoDetailView, RecoData
from src.views.components.status_indicator import Status


class SignalRelay(QObject):
    # 定义信号
    add_list_signal = Signal(str, list)
    recognition_signal = Signal(int, str, bool)


class RecognitionButton(QPushButton):
    """自定义按钮类，包含识别相关的信息"""

    def __init__(self, name: str, group: str, parent=None):
        super().__init__(name, parent)
        self.name = name
        self.group = group
        self.reco_id = None
        self.success = False
        self.status = Status.PENDING

        # 设置初始状态样式
        self.updateStyle()

        # 初始状态下禁用按钮
        self.setEnabled(False)

    def setRecognitionResult(self, reco_id: int, success: bool):
        """设置识别结果"""
        self.reco_id = reco_id
        self.success = success
        self.status = Status.SUCCEEDED if success else Status.FAILED

        # 更新样式
        self.updateStyle()

        # 启用按钮
        self.setEnabled(True)

    def updateStyle(self):
        """根据状态更新按钮样式"""
        if self.status == Status.PENDING:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    color: #555555;
                    border: none;
                    padding: 5px;
                    border-radius: 3px;
                }
            """)
        elif self.status == Status.SUCCEEDED:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #2ecc71;
                    color: white;
                    border: none;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #27ae60;
                    cursor: pointer;
                }
            """)
        elif self.status == Status.FAILED:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    border: none;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                    cursor: pointer;
                }
            """)


class RecognitionRow(QWidget):
    """优化的识别行组件，使用网格布局实现动态自适应布局"""

    # 定义一个信号，用于在按钮点击时发送识别ID
    item_clicked = Signal(int)

    class MyNotificationHandler(NotificationHandler):
        """通知处理器类，处理识别事件"""

        def __init__(self, signal_relay) -> None:
            super().__init__()
            # 使用信号中继器
            self.signal_relay = signal_relay

        def on_node_next_list(
                self,
                noti_type: NotificationType,
                detail: NotificationHandler.NodeNextListDetail,
        ):
            if noti_type != NotificationType.Starting:
                return

            # 使用信号发送数据，而不是直接调用回调
            self.signal_relay.add_list_signal.emit(detail.name, detail.next_list)

        def on_node_recognition(
                self,
                noti_type: NotificationType,
                detail: NotificationHandler.NodeRecognitionDetail,
        ):
            if (
                    noti_type != NotificationType.Succeeded
                    and noti_type != NotificationType.Failed
            ):
                return

            # 使用信号发送识别结果
            self.signal_relay.recognition_signal.emit(
                detail.reco_id, detail.name, noti_type == NotificationType.Succeeded
            )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # 创建信号中继器
        self.signal_relay = SignalRelay()

        # 连接信号到槽
        self.signal_relay.add_list_signal.connect(self.add_list_containers_safe)
        self.signal_relay.recognition_signal.connect(self.on_recognized)

        # 存储按钮引用的字典，格式为: {group: {name: button}}
        self.button_map = {}

        # 存储容器对象的字典，用于后续调整
        self.containers = []

        # 存储每行容器的字典，用于高度调整: {row_index: [container1, container2, ...]}
        self.row_containers = {}

        # 用于记录添加测试按钮点击次数
        self.test_count = 0

        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 创建顶部按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        # 创建清除按钮
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #5dade2;  /* 浅蓝色 */
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3498db;  /* 深一点的蓝色 */
            }
        """)
        self.clear_btn.clicked.connect(self.clear)
        button_layout.addWidget(self.clear_btn)

        # 创建停止按钮
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1c40f;  /* 黄色 */
                color: black;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d4ac0d;  /* 深一点的黄色 */
            }
        """)
        self.stop_btn.clicked.connect(self.stop_task)  # 确保你定义了 self.stop 方法
        button_layout.addWidget(self.stop_btn)

        # 添加按钮布局到主布局
        main_layout.addLayout(button_layout)

        # 创建滚动区域容器
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 禁用水平滚动条
        self.scroll_area.setStyleSheet("background-color: white; border: 1px solid #dddddd;")

        # 创建滚动区域的内容容器
        self.scroll_content = QWidget()

        # 使用网格布局来替代垂直布局和行布局
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        # 设置网格布局左对齐
        self.grid_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        # 设置滚动区域的内容
        self.scroll_area.setWidget(self.scroll_content)

        # 添加滚动区域到主布局
        main_layout.addWidget(self.scroll_area)

        # 设置容器参数
        self.min_container_width = 180  # 最小容器宽度
        self.max_container_width = 300  # 最大容器宽度
        self.container_spacing = 15  # 容器之间的间距

        # 用于追踪网格布局中的当前位置
        self.current_grid_row = 0
        self.current_grid_col = 0
        self.max_columns = 3  # 初始列数，会在resizeEvent中更新

        # 创建带信号中继器的通知处理器
        self.notification_handler = self.MyNotificationHandler(self.signal_relay)

        # 绑定通知处理器
        maafw.notification_handler = self.notification_handler

    def resizeEvent(self, event):
        """窗口大小变化时调整布局"""
        super().resizeEvent(event)

        # 计算新的最大列数
        available_width = self.scroll_area.width() - 40  # 考虑边距

        # 根据可用宽度和最小容器宽度计算每行可放置的容器数量
        new_max_columns = max(1, int(available_width / (self.min_container_width + self.container_spacing)))

        if new_max_columns != self.max_columns:
            self.max_columns = new_max_columns
            self.reorganize_grid()

        # 更新所有容器的宽度
        self.update_container_widths()

    def update_container_widths(self):
        """更新所有容器的宽度"""
        if not self.containers:
            return

        available_width = self.scroll_area.width() - 40  # 考虑边距

        # 计算适合的宽度
        column_width = (available_width - (self.max_columns - 1) * self.container_spacing) / self.max_columns

        # 限制宽度在合理范围内
        container_width = max(self.min_container_width, min(self.max_container_width, column_width))

        # 更新所有容器的宽度
        for container in self.containers:
            container.setFixedWidth(int(container_width))

    def reorganize_grid(self):
        """根据新的列数重新组织网格布局中的容器"""
        if not self.containers:
            return

        # 暂时从布局中移除所有容器
        for container in self.containers:
            self.grid_layout.removeWidget(container)

        # 重新添加到网格布局，确保从左侧开始排列
        for i, container in enumerate(self.containers):
            row = i // self.max_columns
            col = i % self.max_columns
            self.grid_layout.addWidget(container, row, col)
            # 确保每个容器都是左对齐的
            self.grid_layout.setAlignment(container, Qt.AlignLeft | Qt.AlignTop)

        # 更新当前位置
        self.current_grid_row = len(self.containers) // self.max_columns
        self.current_grid_col = len(self.containers) % self.max_columns

    @asyncSlot()
    async def stop_task(self):
        """停止任务"""
        await maafw.stop_task()

    @asyncSlot()
    async def clear(self):
        """清除所有测试容器"""
        # 移除网格布局中的所有控件
        while self.grid_layout.count():
            # 获取布局中的第一个项目
            item = self.grid_layout.takeAt(0)
            # 获取项目对应的控件
            widget = item.widget()
            if widget:
                # 隐藏控件
                widget.hide()
                # 删除控件
                widget.deleteLater()

        # 清空按钮映射和容器列表
        self.button_map.clear()
        self.containers.clear()
        self.row_containers.clear()

        # 重置网格位置
        self.current_grid_row = 0
        self.current_grid_col = 0

        await maafw.clear_cache()
        print("以清除缓存")
    # 使用Slot装饰器表明这是一个槽函数
    @Slot(str, list)
    def add_list_containers_safe(self, current: str, list_to_reco: List[str]):
        """通过信号安全调用的添加容器方法"""
        try:

            # 为当前组创建按钮映射字典
            if current not in self.button_map:
                self.button_map[current] = {}

            # 计算当前适合的容器宽度
            available_width = self.scroll_area.width() - 40
            container_width = int(
                (available_width - (self.max_columns - 1) * self.container_spacing) / self.max_columns)
            container_width = max(self.min_container_width, min(self.max_container_width, container_width))

            # 创建一个新的垂直容器
            container = QWidget()
            container.setObjectName(f"list_container_{current}")
            container.setStyleSheet("background-color: #f9f9f9; border-radius: 6px; border: 1px solid #dddddd;")

            # 设置固定宽度和最小高度
            container.setFixedWidth(container_width)
            container.setMinimumHeight(100)  # 设置最小高度确保可见

            # 创建容器的布局
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(10, 10, 10, 10)
            container_layout.setSpacing(8)

            # 添加标签（组名）
            label = QLabel(f"{current}")
            label.setStyleSheet("font-weight: bold; font-size: 14px; color: #333333;")
            container_layout.addWidget(label)

            # 添加分隔线
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setStyleSheet("background-color: #dddddd;")
            container_layout.addWidget(separator)

            # 添加按钮
            buttons_height = 0
            for name in list_to_reco:
                # 创建自定义按钮
                button = RecognitionButton(name, current)

                # 连接按钮点击信号
                button.clicked.connect(lambda checked, btn=button: self.on_button_clicked(btn))

                # 将按钮添加到布局
                container_layout.addWidget(button)

                # 按钮预估高度
                buttons_height += 35  # 每个按钮大约35像素高

                # 保存按钮引用到映射中
                self.button_map[current][name] = button

            # 动态设置容器高度
            if len(list_to_reco) > 0:
                # 计算适当的容器高度 (标题 + 分隔线 + 按钮总高度 + 内边距)
                adapted_height = 40 + 2 + buttons_height + 40
                container.setMinimumHeight(max(100, adapted_height))

            # 确保有足够的空间显示所有按钮
            container_layout.addStretch()

            # 将新容器添加到网格布局中的下一个位置
            self.grid_layout.addWidget(container, self.current_grid_row, self.current_grid_col)
            # 确保容器左对齐
            self.grid_layout.setAlignment(container, Qt.AlignLeft | Qt.AlignTop)

            # 添加到容器列表
            self.containers.append(container)

            # 更新网格位置
            self.current_grid_col += 1
            if self.current_grid_col >= self.max_columns:
                self.current_grid_col = 0
                self.current_grid_row += 1

            # 添加容器到对应行记录
            if self.current_grid_row not in self.row_containers:
                self.row_containers[self.current_grid_row] = []

            # 如果是同一行的新容器，需要更新当前行的所有容器高度
            current_row = (len(self.containers) - 1) // self.max_columns
            if current_row in self.row_containers:
                # 将当前容器添加到行容器列表
                self.row_containers[current_row].append(container)

                # 更新这一行的所有容器高度
                max_height = 0
                for row_container in self.row_containers[current_row]:
                    max_height = max(max_height, row_container.minimumHeight())

                # 设置行中所有容器的高度为最大高度
                for row_container in self.row_containers[current_row]:
                    if row_container.minimumHeight() != max_height:
                        row_container.setMinimumHeight(max_height)
                        row_container.updateGeometry()

        except Exception as e:
            print(f"Error in add_list_containers_safe: {e}")

    @Slot(int, str, bool)
    def on_recognized(self, reco_id: int, name: str, success: bool):
        """处理识别事件的槽函数"""
        try:
            print(f"Recognition: ID={reco_id}, Name={name}, Success={success}")

            # 更新数据存储
            RecoData.data[reco_id] = (name, success)

            # 查找并更新对应的按钮状态
            # 需要遍历所有组，查找包含该名称的按钮
            for group, buttons in self.button_map.items():
                if name in buttons:
                    button = buttons[name]
                    button.setRecognitionResult(reco_id, success)
                    print(f"Updated button '{name}' in group '{group}' with ID={reco_id}, Success={success}")
                    break
        except Exception as e:
            print(f"Error in on_recognized: {e}")

    def on_button_clicked(self, button: RecognitionButton):
        """处理按钮点击事件"""
        if button.reco_id is not None:
            print(
                f"Button clicked: Group={button.group}, Name={button.name}, ID={button.reco_id}, Success={button.success}")
            # 发送信号，通知需要显示详情
            self.item_clicked.emit(button.reco_id)
        else:
            print(f"Button clicked but no recognition data available: {button.name}")


class DebuggerView(QTabWidget):
    """带有标签页的识别容器"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Create first tab - Recognition Row
        self.recognition_row = RecognitionRow()
        self.addTab(self.recognition_row, "Recognition")

        # Connect recognition item click signal to handler
        self.recognition_row.item_clicked.connect(self.open_details)

        # Create second tab - Recognition Details
        self.detail_view = RecoDetailView()
        self.addTab(self.detail_view, "Details")

    def open_details(self, reco_id: int):
        """Open details tab and show info for the specified recognition ID"""
        # Update details with the selected ID
        self.detail_view.update_details(reco_id)

        # Switch to details tab
        self.setCurrentIndex(1)