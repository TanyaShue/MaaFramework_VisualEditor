from typing import Dict, Tuple, Callable, List

from PySide6.QtWidgets import (
    QTabWidget, QLabel
)

from PySide6.QtWidgets import (
    QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal, QMetaObject, Slot, Q_ARG, QObject
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
    data: Dict[int, Tuple[str, bool]] = {}


# 创建一个信号中继器类，用于跨线程发送信号
class SignalRelay(QObject):
    # 定义信号
    add_list_signal = Signal(str, list)
    recognition_signal = Signal(int, str, bool)


class RecognitionRow(QWidget):
    """重写的识别行组件，包含两个按钮和一个滚动容器"""

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

        # 用于记录添加测试按钮点击次数
        self.test_count = 0
        self.current_row_layout = None
        self.containers_per_row = 0

        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 创建标题
        title_label = QLabel("Recognition Debug View")
        title_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #333333;")
        main_layout.addWidget(title_label)

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

        # 创建添加测试按钮
        self.add_test_btn = QPushButton("Add Test")
        self.add_test_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.add_test_btn.clicked.connect(self.add_test)
        button_layout.addWidget(self.add_test_btn)

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

        # 计算一行可以放置的容器数量（滚动区域宽度除以容器宽度）
        # 这个值会在窗口大小调整时动态更新
        self.max_containers_per_row = 3  # 默认值，稍后会更新

        # 创建第一行
        self.create_new_row()

        # 创建带信号中继器的通知处理器
        self.notification_handler = self.MyNotificationHandler(self.signal_relay)

        # 绑定通知处理器
        maafw.notification_handler = self.notification_handler

    def resizeEvent(self, event):
        """窗口大小变化时调整每行容器数量"""
        super().resizeEvent(event)

        # 计算新的每行容器最大数量
        container_width = 200  # 容器宽度
        margin = 10  # 容器之间的间距
        available_width = self.scroll_area.width() - 20  # 减去滚动区域的内边距

        # 计算一行可以放置的容器数量
        self.max_containers_per_row = max(1, int(available_width / (container_width + margin)))
        print(f"Resize: available width={available_width}, containers per row={self.max_containers_per_row}")

    def create_new_row(self):
        """创建新的一行容器"""
        row_widget = QWidget()
        self.current_row_layout = QHBoxLayout(row_widget)
        self.current_row_layout.setAlignment(Qt.AlignLeft)
        self.current_row_layout.setSpacing(10)
        self.current_row_layout.setContentsMargins(0, 0, 0, 0)

        # 将新行添加到滚动区域的布局中
        self.scroll_layout.addWidget(row_widget)

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

        # 重置测试计数和行
        self.test_count = 0
        self.containers_per_row = 0
        self.current_row_layout = None

        # 创建新的第一行
        self.create_new_row()

        print("All test containers cleared")

    def add_test(self):
        """添加一个新的测试容器"""
        try:
            # 增加测试计数
            self.test_count += 1

            # 检查是否需要创建新行
            if self.containers_per_row >= self.max_containers_per_row:
                self.create_new_row()

            # 创建一个新的垂直容器
            container = QWidget()
            container.setObjectName(f"test_container_{self.test_count}")
            container.setStyleSheet("background-color: #f9f9f9; border-radius: 6px; border: 1px solid #dddddd;")

            # 设置固定宽度
            container.setFixedWidth(200)

            # 创建容器的布局
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(10, 10, 10, 10)
            container_layout.setSpacing(8)

            # 添加标签（测试+组号）
            label = QLabel(f"测试 {self.test_count}")
            label.setStyleSheet("font-weight: bold; font-size: 14px; color: #333333;")
            container_layout.addWidget(label)

            # 添加分隔线
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setStyleSheet("background-color: #dddddd;")
            container_layout.addWidget(separator)

            # 根据当前测试计数添加对应数量的按钮
            for i in range(self.test_count):
                button = QPushButton(f"Button {i + 1}")
                button.setStyleSheet("""
                    QPushButton {
                        background-color: #2ecc71;
                        color: white;
                        border: none;
                        padding: 5px;
                        border-radius: 3px;
                    }
                    QPushButton:hover {
                        background-color: #27ae60;
                    }
                """)

                # 使用 lambda 表达式传递索引
                button.clicked.connect(lambda checked, idx=i + 1, group=self.test_count: self.print_number(idx, group))

                container_layout.addWidget(button)
            container_layout.addStretch()
            # 将新容器添加到当前行布局中
            self.current_row_layout.addWidget(container)

            # 增加当前行的容器计数
            self.containers_per_row += 1

            print(f"Added new test container {self.test_count} with {self.test_count} button(s)")
        except Exception as e:
            print(f"Error in add_test: {e}")

    # 使用Slot装饰器表明这是一个槽函数
    @Slot(str, list)
    def add_list_containers_safe(self, current: str, list_to_reco: List[str]):
        """通过信号安全调用的添加容器方法"""
        try:
            print("-----------------111---")
            print(f"Safely adding list container: {current} with {len(list_to_reco)} items")

            # 检查是否需要创建新行
            if self.containers_per_row >= self.max_containers_per_row:
                self.create_new_row()

            # 确保current_row_layout存在
            if self.current_row_layout is None:
                self.create_new_row()

            # 创建一个新的垂直容器
            container = QWidget()
            container.setObjectName(f"list_container_{current}")
            container.setStyleSheet("background-color: #f9f9f9; border-radius: 6px; border: 1px solid #dddddd;")

            # 设置固定宽度
            container.setFixedWidth(200)
            container.setMinimumHeight(100)  # 设置最小高度确保可见

            # 创建容器的布局
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(10, 10, 10, 10)
            container_layout.setSpacing(8)

            # 添加标签（测试+组号）
            label = QLabel(f"{current}")
            label.setStyleSheet("font-weight: bold; font-size: 14px; color: #333333;")
            container_layout.addWidget(label)

            # 添加分隔线
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setStyleSheet("background-color: #dddddd;")
            container_layout.addWidget(separator)

            # 根据当前测试计数添加对应数量的按钮
            for name in list_to_reco:
                button = QPushButton(f"{name}")
                button.setStyleSheet("""
                    QPushButton {
                        background-color: #2ecc71;
                        color: white;
                        border: none;
                        padding: 5px;
                        border-radius: 3px;
                    }
                    QPushButton:hover {
                        background-color: #27ae60;
                    }
                """)

                # 使用 lambda 表达式传递索引
                # 使用更安全的变量捕获方式
                button.clicked.connect(lambda checked, n=name, c=current: self.print_number(n, c))

                container_layout.addWidget(button)

            # 确保有足够的空间显示所有按钮
            container_layout.addStretch()

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
            # 更新数据
            RecoData.data[reco_id] = (name, success)
        except Exception as e:
            print(f"Error in on_recognized: {e}")

    def print_number(self, number, group):
        """打印按钮对应的数字和组号"""
        print(f"Group {group}, Button {number} clicked!")


class RecoDetailView(QWidget):
    """识别详情页面"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # 创建布局
        self.layout = QVBoxLayout(self)

        # 创建标题标签
        self.title_label = QLabel("Recognition Details")
        self.title_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        self.layout.addWidget(self.title_label)

        # 创建详情标签
        self.details_layout = QVBoxLayout()
        self.id_label = QLabel()
        self.name_label = QLabel()
        self.status_label = QLabel()

        self.details_layout.addWidget(self.id_label)
        self.details_layout.addWidget(self.name_label)
        self.details_layout.addWidget(self.status_label)

        # 添加详情部分
        details_container = QWidget()
        details_container.setLayout(self.details_layout)
        self.layout.addWidget(details_container)

        # 添加伸展因子，使内容显示在顶部
        self.layout.addStretch(1)

    def update_details(self, reco_id: int):
        """更新详情内容"""
        name, hit = RecoData.data.get(reco_id, ("Unknown", False))

        self.id_label.setText(f"Recognition ID: {reco_id}")
        self.name_label.setText(f"Name: {name}")
        self.status_label.setText(f"Success: {'Yes' if hit else 'No'}")

        # 设置成功/失败的颜色
        status_color = "#4caf50" if hit else "#f44336"
        self.status_label.setStyleSheet(f"color: {status_color};")


class DebuggerView(QTabWidget):
    """带有标签页的识别容器"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # 创建第一个标签页 - 识别行
        self.recognition_row = RecognitionRow()
        self.addTab(self.recognition_row, "Recognition")

        # 连接识别项点击信号到处理函数
        # self.recognition_row.item_clicked.connect(self.open_details)

        # 创建第二个标签页 - 识别详情页面
        self.detail_view = RecoDetailView()
        self.addTab(self.detail_view, "Details")

    def open_details(self, reco_id: int):
        """打开详情页并显示指定reco_id的信息"""
        # 更新详情页的内容
        self.detail_view.update_details(reco_id)

        # 切换到详情标签页
        self.setCurrentIndex(1)