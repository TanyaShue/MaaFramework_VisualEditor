from typing import Dict, Tuple, Callable, List, Optional

from PySide6.QtWidgets import (
    QTabWidget, QLabel, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal, QMetaObject, Slot, Q_ARG, QObject
from PySide6.QtGui import QCursor
from maa.notification_handler import NotificationHandler, NotificationType

from src.maafw import maafw
from src.views.components.status_indicator import Status


class StatusIndicator(QLabel):
    """状态指示器组件，替代原来的StatusIndicator类"""

    STATUS_STYLES = {
        Status.PENDING: "background-color: #f0f0f0; border-radius: 8px; padding: 4px; min-width: 16px; min-height: 16px;",
        Status.SUCCEEDED: "background-color: #4caf50; border-radius: 8px; padding: 4px; min-width: 16px; min-height: 16px;",
        Status.FAILED: "background-color: #f44336; border-radius: 8px; padding: 4px; min-width: 16px; min-height: 16px;"
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)  # 稍微增大一点
        self.setAlignment(Qt.AlignCenter)
        self.setText("")  # 确保没有文本
        self.setStatus(Status.PENDING)

    def setStatus(self, status: Status):
        # 设置更加明显的样式
        if status == Status.SUCCEEDED:
            self.setText("✓")  # 添加一个勾号
            self.setStyleSheet(self.STATUS_STYLES[status] + "color: white; font-weight: bold;")
        elif status == Status.FAILED:
            self.setText("✗")  # 添加一个叉号
            self.setStyleSheet(self.STATUS_STYLES[status] + "color: white; font-weight: bold;")
        else:
            self.setText("")
            self.setStyleSheet(self.STATUS_STYLES[status])

        # 确保状态变化立即可见
        self.update()


class RecoData:
    """存储识别数据的类"""
    data: Dict[int, Tuple[str, bool]] = {}


# 创建一个信号中继器类，用于跨线程发送信号
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
    """优化的识别行组件，具有动态调整的布局和容器大小"""

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
            print(f"Emitted signal for {detail.name} with {len(detail.next_list)} items")

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
            print(f"{detail.reco_id},: {detail.name},{noti_type}")
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

        # 存储容器对象的字典，用于后续高度调整
        self.container_map = {}

        # 用于记录添加测试按钮点击次数
        self.test_count = 0
        self.current_row_layout = None
        self.containers_per_row = 0

        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 创建顶部按钮布局
        button_layout = QHBoxLayout()

        # 创建清除按钮
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.clear_btn.clicked.connect(self.clear)
        button_layout.addWidget(self.clear_btn)

        # 添加按钮布局到主布局
        main_layout.addLayout(button_layout)

        # 创建滚动区域容器
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 禁用水平滚动条
        self.scroll_area.setStyleSheet("background-color: white; border: 1px solid #dddddd;")

        # 创建滚动区域的内容容器
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)  # 从顶部开始排列
        self.scroll_layout.setSpacing(15)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)

        # 设置滚动区域的内容
        self.scroll_area.setWidget(self.scroll_content)

        # 添加滚动区域到主布局
        main_layout.addWidget(self.scroll_area)

        # 设置行容器列表，用于管理行
        self.row_widgets = []

        # 默认一行放置的容器数量
        self.max_containers_per_row = 3  # 默认值，稍后会更新

        # 默认容器宽度和间距
        self.container_width = 200
        self.container_margin = 10
        self.container_min_height = 100

        # 创建第一行
        self.create_new_row()

        # 创建带信号中继器的通知处理器
        self.notification_handler = self.MyNotificationHandler(self.signal_relay)

        # 绑定通知处理器
        maafw.notification_handler = self.notification_handler

        # 安装事件过滤器以捕获大小变化
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        """事件过滤器，用于捕获大小变化事件"""
        if obj == self and event.type() == event.__class__.Resize:
            # 延迟执行布局更新以避免过于频繁的更新
            QMetaObject.invokeMethod(self, "updateLayout", Qt.QueuedConnection)
        return super().eventFilter(obj, event)

    @Slot()
    def updateLayout(self):
        """更新整个布局"""
        # 获取新的可用宽度
        available_width = self.scroll_area.width() - 40  # 滚动区域的宽度减去padding

        # 计算新的每行容器数量
        new_max = max(1, int(available_width / (self.container_width + self.container_margin)))

        # 如果每行容器数量没变，只调整宽度
        if new_max == self.max_containers_per_row:
            # 只更新容器宽度
            self.updateContainerWidths(available_width, new_max)
            return

        # 保存新的最大容器数
        self.max_containers_per_row = new_max

        # 如果没有容器，不需要重新布局
        if not self.container_map:
            return

        # 重新布局所有容器
        self.rebuildLayout()

    def updateContainerWidths(self, available_width, containers_per_row):
        """更新所有容器的宽度"""
        # 计算新的容器宽度
        new_width = int((available_width - (containers_per_row - 1) * self.container_margin) / containers_per_row)
        new_width = max(150, min(300, new_width))  # 限制最小/最大宽度

        # 只有在宽度有显著变化时才更新
        if abs(new_width - self.container_width) > 10:
            self.container_width = new_width

            # 更新所有容器的宽度
            for container in self.container_map.values():
                container.setFixedWidth(self.container_width)

    def rebuildLayout(self):
        """重建整个布局"""
        # 保存所有容器的引用
        containers = list(self.container_map.values())

        # 清除当前布局
        self.clearRows()

        # 重置当前行
        self.containers_per_row = 0
        self.create_new_row()

        # 重新添加所有容器
        for container in containers:
            # 检查是否需要创建新行
            if self.containers_per_row >= self.max_containers_per_row:
                self.create_new_row()

            # 更新容器宽度
            container.setFixedWidth(self.container_width)

            # 将容器添加到当前行
            self.current_row_layout.addWidget(container)

            # 更新计数
            self.containers_per_row += 1

    def clearRows(self):
        """清除所有行，但保留容器"""
        # 从所有行中移除容器，但不删除容器
        for row_widget in self.row_widgets:
            layout = row_widget.layout()
            while layout.count():
                item = layout.takeAt(0)
                # 只移除但不删除控件
                if item.widget():
                    item.widget().setParent(None)

            # 隐藏行控件
            row_widget.hide()
            row_widget.deleteLater()

        # 清空行列表
        self.row_widgets.clear()

    def resizeEvent(self, event):
        """窗口大小变化时调整每行容器数量"""
        super().resizeEvent(event)
        # 实际的布局更新由eventFilter处理

    def create_new_row(self):
        """创建新的一行容器"""
        row_widget = QWidget()
        self.current_row_layout = QHBoxLayout(row_widget)
        self.current_row_layout.setAlignment(Qt.AlignLeft)
        self.current_row_layout.setSpacing(self.container_margin)
        self.current_row_layout.setContentsMargins(0, 0, 0, 0)

        # 将新行添加到滚动区域的布局中
        self.scroll_layout.addWidget(row_widget)

        # 将行添加到行列表中
        self.row_widgets.append(row_widget)

        # 重置当前行的容器计数
        self.containers_per_row = 0

    def clear(self):
        """清除所有测试容器"""
        # 移除滚动区域中的所有内容
        while self.scroll_layout.count():
            # 获取布局中的第一个项目
            item = self.scroll_layout.takeAt(0)
            # 获取项目对应的控件
            widget = item.widget()
            if widget:
                # 隐藏控件
                widget.hide()
                # 删除控件
                widget.deleteLater()

        # 清空按钮映射和容器映射
        self.button_map.clear()
        self.container_map.clear()

        # 清空行列表
        self.row_widgets.clear()

        # 重置测试计数和行
        self.test_count = 0
        self.containers_per_row = 0
        self.current_row_layout = None

        # 创建新的第一行
        self.create_new_row()

        print("All test containers cleared")

    # 使用Slot装饰器表明这是一个槽函数
    @Slot(str, list)
    def add_list_containers_safe(self, current: str, list_to_reco: List[str]):
        """通过信号安全调用的添加容器方法"""
        try:
            print(f"Safely adding list container: {current} with {len(list_to_reco)} items")

            # 检查是否需要创建新行
            if self.containers_per_row >= self.max_containers_per_row:
                self.create_new_row()

            # 确保current_row_layout存在
            if self.current_row_layout is None:
                self.create_new_row()

            # 为当前组创建按钮映射字典
            if current not in self.button_map:
                self.button_map[current] = {}

            # 创建一个新的垂直容器
            container = QWidget()
            container.setObjectName(f"list_container_{current}")
            container.setStyleSheet("background-color: #f9f9f9; border-radius: 6px; border: 1px solid #dddddd;")

            # 设置固定宽度
            container.setFixedWidth(self.container_width)
            container.setMinimumHeight(self.container_min_height)  # 设置最小高度确保可见

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

            # 添加带状态指示器的按钮
            buttons_height = 0
            for name in list_to_reco:
                # 创建自定义按钮
                button = RecognitionButton(name, current)

                # 估算按钮高度 (基本高度 + 内容高度)
                button_height = 30  # 估计的基础按钮高度

                # 连接按钮点击信号
                button.clicked.connect(lambda checked, btn=button: self.on_button_clicked(btn))

                # 将按钮添加到布局
                container_layout.addWidget(button)

                # 累计按钮高度
                buttons_height += button_height

                # 保存按钮引用到映射中
                self.button_map[current][name] = button

            # 计算容器的适应高度 (标题 + 分隔线 + 按钮总高度 + 内边距)
            adapted_height = 30 + 10 + buttons_height + 40
            # 设置最小高度，但不设置固定高度，允许容器自适应
            container.setMinimumHeight(max(self.container_min_height, adapted_height))

            # 确保有足够的空间显示所有按钮
            container_layout.addStretch()

            # 保存容器引用
            self.container_map[current] = container

            # 将新容器添加到当前行布局中
            self.current_row_layout.addWidget(container)

            # 增加当前行的容器计数
            self.containers_per_row += 1

            print(f"Added new list container {current} with {len(list_to_reco)} button(s)")
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

class RecoDetailView(QWidget):
    """识别详情页面"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # 创建布局
        self.layout = QVBoxLayout(self)

        # 创建标题标签
        # self.title_label = QLabel("Recognition Details")
        # self.title_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        # self.layout.addWidget(self.title_label)

        # 创建详情标签
        self.details_layout = QVBoxLayout()

        # 创建信息显示区
        self.info_frame = QFrame()
        self.info_frame.setStyleSheet("""
            QFrame {
                background-color: #f9f9f9;
                border-radius: 6px;
                border: 1px solid #dddddd;
                padding: 10px;
            }
            QLabel {
                font-size: 14px;
                margin: 5px;
            }
        """)
        self.info_layout = QVBoxLayout(self.info_frame)

        self.id_label = QLabel("Recognition ID: -")
        self.name_label = QLabel("Name: -")
        self.status_indicator = QLabel("Status: -")

        self.info_layout.addWidget(self.id_label)
        self.info_layout.addWidget(self.name_label)
        self.info_layout.addWidget(self.status_indicator)

        # 添加信息区到布局
        self.layout.addWidget(self.info_frame)

        # 添加伸展因子，使内容显示在顶部
        self.layout.addStretch(1)

    def update_details(self, reco_id: int):
        """更新详情内容"""
        name, hit = RecoData.data.get(reco_id, ("Unknown", False))

        self.id_label.setText(f"Recognition ID: {reco_id}")
        self.name_label.setText(f"Name: {name}")

        # 设置成功/失败的状态
        if hit:
            self.status_indicator.setText("Status: Success")
            self.status_indicator.setStyleSheet("color: #4caf50; font-weight: bold;")
        else:
            self.status_indicator.setText("Status: Failed")
            self.status_indicator.setStyleSheet("color: #f44336; font-weight: bold;")


class DebuggerView(QTabWidget):
    """带有标签页的识别容器"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # 创建第一个标签页 - 识别行
        self.recognition_row = RecognitionRow()
        self.addTab(self.recognition_row, "Recognition")

        # 连接识别项点击信号到处理函数
        self.recognition_row.item_clicked.connect(self.open_details)

        # 创建第二个标签页 - 识别详情页面
        self.detail_view = RecoDetailView()
        self.addTab(self.detail_view, "Details")

    def open_details(self, reco_id: int):
        """打开详情页并显示指定reco_id的信息"""
        # 更新详情页的内容
        self.detail_view.update_details(reco_id)

        # 切换到详情标签页
        self.setCurrentIndex(1)