from PySide6.QtCore import Qt, Signal, QSize, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFormLayout,
                               QLineEdit, QSpinBox, QPushButton, QCheckBox,
                               QComboBox, QTextEdit, QDoubleSpinBox, QHBoxLayout,
                               QScrollArea, QGroupBox, QFrame, QMessageBox,
                               QToolButton, QSizePolicy, QTabWidget, QStackedWidget,
                               QApplication, QStyle)
from PySide6.QtGui import QFont, QColor, QPalette
import json

from src.pipeline import TaskNode


# Performance-optimized collapsible box
class CollapsibleBox(QWidget):
    """可折叠的属性分组组件 - 性能优化版"""

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setObjectName("collapsible_box")

        # Create main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Create header
        header = QWidget()
        header.setCursor(Qt.PointingHandCursor)
        header.setMinimumHeight(30)
        header.setStyleSheet("background-color: #f0f0f0; border-radius: 3px;")

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(5, 2, 5, 2)

        self.toggle_button = QToolButton()
        self.toggle_button.setStyleSheet("QToolButton { border: none; background: transparent; }")
        self.toggle_button.setArrowType(Qt.RightArrow)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold;")

        header_layout.addWidget(self.toggle_button)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # Content area
        self.content_area = QWidget()
        self.content_area.setVisible(False)
        self.content_layout = QFormLayout(self.content_area)
        self.content_layout.setContentsMargins(20, 5, 5, 5)
        self.content_layout.setSpacing(7)

        # Add to main layout
        self.main_layout.addWidget(header)
        self.main_layout.addWidget(self.content_area)

        # Connect signals
        header.mousePressEvent = self.header_clicked
        self.toggle_button.clicked.connect(self.toggle_content)

        # Animation setup
        self.animation = None

    def header_clicked(self, event):
        self.toggle_button.setChecked(not self.toggle_button.isChecked())
        self.toggle_content()

    def toggle_content(self):
        # Use QTimer to defer layout update for better performance
        self.toggle_button.setArrowType(Qt.DownArrow if self.toggle_button.isChecked() else Qt.RightArrow)
        QTimer.singleShot(10, lambda: self.content_area.setVisible(self.toggle_button.isChecked()))

    def set_expanded(self, expanded):
        """设置是否展开此区域"""
        if self.toggle_button.isChecked() != expanded:
            self.toggle_button.setChecked(expanded)
            self.toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
            self.content_area.setVisible(expanded)

    def has_content(self):
        """检查是否有内容"""
        return self.content_layout.count() > 0

    def add_row(self, label: str, widget: QWidget):
        """添加表单行"""
        label_widget = QLabel(label)
        label_widget.setStyleSheet("padding-left: 5px;")
        self.content_layout.addRow(label_widget, widget)

    def clear_content(self):
        """清除所有内容"""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class ListEditor(QWidget):
    """列表属性编辑器组件 - 优化版"""

    value_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(3)

        # 列表项显示区域
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("每行输入一个值")
        self.text_edit.setMaximumHeight(80)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 2px;
            }
        """)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)

        self.add_btn = QPushButton("添加项")
        self.add_btn.setStyleSheet("""
            QPushButton {
                padding: 3px 10px;
                background-color: #f8f8f8;
                border-radius: 3px;
                border: 1px solid #ccc;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
        """)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                padding: 3px 10px;
                background-color: #f8f8f8;
                border-radius: 3px;
                border: 1px solid #ccc;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
        """)

        button_layout.addWidget(self.add_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addStretch()

        self.layout.addWidget(self.text_edit)
        self.layout.addLayout(button_layout)

        # 连接信号
        self.add_btn.clicked.connect(self.add_item)
        self.clear_btn.clicked.connect(self.clear_items)
        self.text_edit.textChanged.connect(self.on_text_changed)

        self._value = []

    def add_item(self):
        """添加新项"""
        self.text_edit.append("")
        self.text_edit.setFocus()

    def clear_items(self):
        """清空所有项"""
        self.text_edit.clear()
        self._value = []
        self.value_changed.emit(self._value)

    def on_text_changed(self):
        """文本内容变化时更新值"""
        text = self.text_edit.toPlainText()
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        self._value = lines
        self.value_changed.emit(self._value)

    def set_value(self, value):
        """设置编辑器的值"""
        if isinstance(value, list):
            self._value = value
            self.text_edit.setText('\n'.join([str(item) for item in value]))
        elif isinstance(value, str):
            self._value = [value]
            self.text_edit.setText(value)
        else:
            self._value = []
            self.text_edit.clear()

    def get_value(self):
        """获取编辑器的值"""
        return self._value


class NodePropertiesEditor(QWidget):
    """节点属性编辑器 - 性能优化版"""

    node_changed = Signal(object)  # 当节点被修改时发送信号

    # 保存对象的通用样式
    BUTTON_STYLE = """
        QPushButton {
            background-color: #4a86e8;
            color: white;
            border: none;
            padding: 5px 15px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #3a76d8;
        }
        QPushButton:pressed {
            background-color: #2a66c8;
        }
        QPushButton:disabled {
            background-color: #cccccc;
        }
    """

    RESET_BUTTON_STYLE = """
        QPushButton {
            background-color: #f8f8f8;
            color: #333;
            border: 1px solid #ccc;
            padding: 5px 15px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #e8e8e8;
        }
        QPushButton:pressed {
            background-color: #d8d8d8;
        }
    """

    GROUP_BOX_STYLE = """
        QGroupBox {
            font-weight: bold;
            border: 1px solid #cccccc;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 15px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 5px;
        }
    """

    INPUT_STYLE = """
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            padding: 3px;
            border: 1px solid #ccc;
            border-radius: 3px;
        }
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
            border: 1px solid #4a86e8;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 识别算法和动作类型选项
        self.recognition_types = [
            "DirectHit", "TemplateMatch", "FeatureMatch", "ColorMatch",
            "OCR", "NeuralNetworkClassify", "NeuralNetworkDetect", "Custom"
        ]

        self.action_types = [
            "DoNothing", "Click", "Swipe", "MultiSwipe", "Key",
            "InputText", "StartApp", "StopApp", "StopTask", "Command", "Custom"
        ]

        # 初始化UI
        self.init_ui()

        # 当前节点
        self.current_node = None

        # 是否自动保存
        self.auto_save = False

        # 是否正在批量更新控件，避免触发更改事件
        self.is_updating_ui = False

        # 创建所有识别算法和动作的容器
        self.create_recognition_containers()
        self.create_action_containers()

        # 连接信号
        self.connect_signals()

        # 设置默认的TaskNode
        self.set_node()

    def init_ui(self):
        """初始化UI界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 创建标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 5px;
            }
            QTabBar::tab {
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
                border-bottom: none;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                padding: 5px 10px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 1px solid white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #e0e0e0;
            }
        """)

        # 创建属性编辑标签页
        properties_tab = QWidget()
        props_layout = QVBoxLayout(properties_tab)
        props_layout.setSpacing(10)

        # 创建标题标签
        title_label = QLabel("节点属性编辑器")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #333; margin-bottom: 5px;")
        props_layout.addWidget(title_label)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)

        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(10)

        # === 基本属性组 ===
        self.basic_group = QGroupBox("基本属性")
        self.basic_group.setStyleSheet(self.GROUP_BOX_STYLE)
        basic_layout = QFormLayout(self.basic_group)
        basic_layout.setSpacing(8)
        basic_layout.setContentsMargins(10, 15, 10, 10)

        self.node_name_input = QLineEdit()
        self.node_name_input.setStyleSheet(self.INPUT_STYLE)

        self.recognition_combo = QComboBox()
        self.recognition_combo.setStyleSheet(self.INPUT_STYLE)

        self.action_combo = QComboBox()
        self.action_combo.setStyleSheet(self.INPUT_STYLE)

        basic_layout.addRow("节点名称:", self.node_name_input)
        basic_layout.addRow("识别算法:", self.recognition_combo)
        basic_layout.addRow("执行动作:", self.action_combo)

        # === 可折叠的流程控制属性组 ===
        self.flow_box = CollapsibleBox("流程控制")

        self.next_editor = ListEditor()
        self.interrupt_editor = ListEditor()
        self.on_error_editor = ListEditor()

        self.flow_box.add_row("后继节点:", self.next_editor)
        self.flow_box.add_row("中断节点:", self.interrupt_editor)
        self.flow_box.add_row("错误节点:", self.on_error_editor)

        # === 可折叠的通用属性组 ===
        self.common_box = CollapsibleBox("通用属性")

        self.is_sub_check = QCheckBox()
        self.is_sub_check.setStyleSheet("QCheckBox::indicator { width: 16px; height: 16px; }")

        self.rate_limit_spin = QSpinBox()
        self.rate_limit_spin.setRange(0, 100000)
        self.rate_limit_spin.setSingleStep(100)
        self.rate_limit_spin.setValue(1000)
        self.rate_limit_spin.setStyleSheet(self.INPUT_STYLE)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(0, 300000)
        self.timeout_spin.setSingleStep(1000)
        self.timeout_spin.setValue(20000)
        self.timeout_spin.setStyleSheet(self.INPUT_STYLE)

        self.inverse_check = QCheckBox()
        self.inverse_check.setStyleSheet("QCheckBox::indicator { width: 16px; height: 16px; }")

        self.enabled_check = QCheckBox()
        self.enabled_check.setChecked(True)
        self.enabled_check.setStyleSheet("QCheckBox::indicator { width: 16px; height: 16px; }")

        self.common_box.add_row("是否子节点:", self.is_sub_check)
        self.common_box.add_row("识别速率(ms):", self.rate_limit_spin)
        self.common_box.add_row("超时时间(ms):", self.timeout_spin)
        self.common_box.add_row("反转识别结果:", self.inverse_check)
        self.common_box.add_row("是否启用:", self.enabled_check)

        # === 可折叠的延迟属性组 ===
        self.delay_box = CollapsibleBox("延迟属性")

        self.pre_delay_spin = QSpinBox()
        self.pre_delay_spin.setRange(0, 10000)
        self.pre_delay_spin.setValue(200)
        self.pre_delay_spin.setStyleSheet(self.INPUT_STYLE)

        self.post_delay_spin = QSpinBox()
        self.post_delay_spin.setRange(0, 10000)
        self.post_delay_spin.setValue(200)
        self.post_delay_spin.setStyleSheet(self.INPUT_STYLE)

        self.pre_wait_freezes_spin = QSpinBox()
        self.pre_wait_freezes_spin.setRange(0, 10000)
        self.pre_wait_freezes_spin.setStyleSheet(self.INPUT_STYLE)

        self.post_wait_freezes_spin = QSpinBox()
        self.post_wait_freezes_spin.setRange(0, 10000)
        self.post_wait_freezes_spin.setStyleSheet(self.INPUT_STYLE)

        self.focus_check = QCheckBox()
        self.focus_check.setStyleSheet("QCheckBox::indicator { width: 16px; height: 16px; }")

        self.delay_box.add_row("动作前延迟(ms):", self.pre_delay_spin)
        self.delay_box.add_row("动作后延迟(ms):", self.post_delay_spin)
        self.delay_box.add_row("动作前等待(ms):", self.pre_wait_freezes_spin)
        self.delay_box.add_row("动作后等待(ms):", self.post_wait_freezes_spin)
        self.delay_box.add_row("是否关注节点:", self.focus_check)

        # === 可折叠的算法特有属性组 ===
        self.recognition_box = CollapsibleBox("识别算法特有属性")
        # 容器将在create_recognition_containers中创建

        # === 可折叠的动作特有属性组 ===
        self.action_box = CollapsibleBox("执行动作特有属性")
        # 容器将在create_action_containers中创建

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.apply_button = QPushButton("应用更改")
        self.apply_button.setMinimumWidth(100)
        self.apply_button.setStyleSheet(self.BUTTON_STYLE)

        self.reset_button = QPushButton("重置")
        self.reset_button.setMinimumWidth(100)
        self.reset_button.setStyleSheet(self.RESET_BUTTON_STYLE)

        self.auto_save_check = QCheckBox("自动保存")
        self.auto_save_check.setStyleSheet("""
            QCheckBox {
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
        """)

        button_layout.addStretch()
        button_layout.addWidget(self.auto_save_check)
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.reset_button)

        # 添加所有组件到滚动布局
        scroll_layout.addWidget(self.basic_group)
        scroll_layout.addWidget(self.flow_box)
        scroll_layout.addWidget(self.common_box)
        scroll_layout.addWidget(self.delay_box)
        scroll_layout.addWidget(self.recognition_box)
        scroll_layout.addWidget(self.action_box)
        scroll_layout.addStretch()

        # 添加滚动区域和按钮到属性标签页
        props_layout.addWidget(scroll_area, 1)
        props_layout.addLayout(button_layout)

        # 添加属性标签页到标签页窗口
        self.tab_widget.addTab(properties_tab, "属性")

        # 添加未实现的标签页
        placeholder_tab = QWidget()
        placeholder_layout = QVBoxLayout(placeholder_tab)
        placeholder_label = QLabel("待实现的标签页")
        placeholder_label.setAlignment(Qt.AlignCenter)
        placeholder_layout.addWidget(placeholder_label)
        self.tab_widget.addTab(placeholder_tab, "未实现标签页")

        # 添加标签页窗口到主布局
        main_layout.addWidget(self.tab_widget)

        # 设置下拉框内容
        self.recognition_combo.addItems(self.recognition_types)
        self.action_combo.addItems(self.action_types)

        # 保存基本属性控件的引用
        self.property_widgets = {
            "name": self.node_name_input,
            "recognition": self.recognition_combo,
            "action": self.action_combo,
            "next": self.next_editor,
            "interrupt": self.interrupt_editor,
            "on_error": self.on_error_editor,
            "is_sub": self.is_sub_check,
            "rate_limit": self.rate_limit_spin,
            "timeout": self.timeout_spin,
            "inverse": self.inverse_check,
            "enabled": self.enabled_check,
            "pre_delay": self.pre_delay_spin,
            "post_delay": self.post_delay_spin,
            "pre_wait_freezes": self.pre_wait_freezes_spin,
            "post_wait_freezes": self.post_wait_freezes_spin,
            "focus": self.focus_check
        }

    def create_recognition_containers(self):
        """为每种识别算法创建容器 - 优化版"""
        # 创建堆叠部件，用于存放所有不同算法的容器
        self.recognition_stack = QStackedWidget()

        # 为每种识别算法创建独立的容器和控件
        self.recognition_containers = {}
        self.recognition_property_widgets = {}

        # 遍历所有识别算法类型，为每一种创建一个容器
        for rec_type in self.recognition_types:
            container = QWidget()
            layout = QFormLayout(container)
            layout.setSpacing(8)
            layout.setContentsMargins(5, 5, 5, 5)

            # 创建特定算法的属性控件
            widgets = self.create_recognition_property_widgets(rec_type)

            # 将控件添加到容器中
            for label, widget in widgets.items():
                layout.addRow(label, widget)

            # 保存容器和控件引用
            self.recognition_containers[rec_type] = container
            self.recognition_property_widgets[rec_type] = widgets

            # 添加容器到堆叠部件
            self.recognition_stack.addWidget(container)

        # 将堆叠部件添加到识别算法属性组
        self.recognition_box.content_layout.addWidget(self.recognition_stack)

    def create_recognition_property_widgets(self, recognition_type):
        """为特定识别算法类型创建属性控件 - 优化版"""
        widgets = {}

        # 对于DirectHit，没有特殊属性
        if recognition_type == "DirectHit":
            info_label = QLabel("DirectHit无需特殊配置")
            info_label.setStyleSheet("color: #666;")
            widgets[""] = info_label
            return widgets

        # 添加通用ROI控件(对于非DirectHit和非Custom类型)
        if recognition_type != "Custom":
            roi_edit = QLineEdit()
            roi_edit.setPlaceholderText("节点名或坐标 [x,y,w,h]")
            roi_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["识别区域:"] = roi_edit

            roi_offset_edit = QLineEdit()
            roi_offset_edit.setPlaceholderText("[x,y,w,h]")
            roi_offset_edit.setText("[0,0,0,0]")
            roi_offset_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["区域偏移:"] = roi_offset_edit

            order_combo = QComboBox()
            order_combo.addItems(["Horizontal", "Vertical", "Score", "Area", "Random"])
            order_combo.setStyleSheet(self.INPUT_STYLE)
            widgets["结果排序:"] = order_combo

            index_spin = QSpinBox()
            index_spin.setRange(-100, 100)
            index_spin.setStyleSheet(self.INPUT_STYLE)
            widgets["结果索引:"] = index_spin

        # 为不同算法类型添加特有属性
        if recognition_type == "TemplateMatch":
            template_edit = QLineEdit()
            template_edit.setPlaceholderText("模板图片路径，相对于image文件夹")
            template_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["模板图片:"] = template_edit

            threshold_spin = QDoubleSpinBox()
            threshold_spin.setRange(0, 1)
            threshold_spin.setSingleStep(0.1)
            threshold_spin.setValue(0.7)
            threshold_spin.setStyleSheet(self.INPUT_STYLE)
            widgets["匹配阈值:"] = threshold_spin

            method_spin = QSpinBox()
            method_spin.setRange(1, 5)
            method_spin.setValue(5)
            method_spin.setToolTip("1、3、5分别对应不同的模板匹配算法")
            method_spin.setStyleSheet(self.INPUT_STYLE)
            widgets["匹配算法:"] = method_spin

            green_mask_check = QCheckBox()
            green_mask_check.setToolTip("是否忽略图片中的绿色部分")
            green_mask_check.setStyleSheet("QCheckBox::indicator { width: 16px; height: 16px; }")
            widgets["绿色掩码:"] = green_mask_check

        elif recognition_type == "FeatureMatch":
            # FeatureMatch特有属性
            template_edit = QLineEdit()
            template_edit.setPlaceholderText("模板图片路径，相对于image文件夹")
            template_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["模板图片:"] = template_edit

            count_spin = QSpinBox()
            count_spin.setRange(1, 100)
            count_spin.setValue(4)
            count_spin.setStyleSheet(self.INPUT_STYLE)
            widgets["特征点数量:"] = count_spin

            detector_combo = QComboBox()
            detector_combo.addItems(["SIFT", "KAZE", "AKAZE", "BRISK", "ORB"])
            detector_combo.setStyleSheet(self.INPUT_STYLE)
            widgets["特征检测器:"] = detector_combo

            ratio_spin = QDoubleSpinBox()
            ratio_spin.setRange(0, 1)
            ratio_spin.setSingleStep(0.1)
            ratio_spin.setValue(0.6)
            ratio_spin.setStyleSheet(self.INPUT_STYLE)
            widgets["距离比值:"] = ratio_spin

            green_mask_check = QCheckBox()
            green_mask_check.setStyleSheet("QCheckBox::indicator { width: 16px; height: 16px; }")
            widgets["绿色掩码:"] = green_mask_check

        elif recognition_type == "ColorMatch":
            # ColorMatch特有属性
            lower_edit = QLineEdit()
            lower_edit.setPlaceholderText("[R,G,B] 或 [[R,G,B],[R,G,B],...]")
            lower_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["颜色下限:"] = lower_edit

            upper_edit = QLineEdit()
            upper_edit.setPlaceholderText("[R,G,B] 或 [[R,G,B],[R,G,B],...]")
            upper_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["颜色上限:"] = upper_edit

            method_spin = QSpinBox()
            method_spin.setRange(0, 50)
            method_spin.setValue(4)
            method_spin.setToolTip("常用：4(RGB), 40(HSV), 6(灰度)")
            method_spin.setStyleSheet(self.INPUT_STYLE)
            widgets["颜色空间:"] = method_spin

            count_spin = QSpinBox()
            count_spin.setRange(1, 10000)
            count_spin.setValue(1)
            count_spin.setStyleSheet(self.INPUT_STYLE)
            widgets["点数阈值:"] = count_spin

            connected_check = QCheckBox()
            connected_check.setStyleSheet("QCheckBox::indicator { width: 16px; height: 16px; }")
            widgets["要求相连:"] = connected_check

        elif recognition_type == "OCR":
            # OCR特有属性
            expected_edit = QLineEdit()
            expected_edit.setPlaceholderText("期望文本或正则表达式")
            expected_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["期望文本:"] = expected_edit

            threshold_spin = QDoubleSpinBox()
            threshold_spin.setRange(0, 1)
            threshold_spin.setSingleStep(0.1)
            threshold_spin.setValue(0.3)
            threshold_spin.setStyleSheet(self.INPUT_STYLE)
            widgets["置信度阈值:"] = threshold_spin

            replace_edit = QLineEdit()
            replace_edit.setPlaceholderText('["原文本", "替换文本"]')
            replace_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["文本替换:"] = replace_edit

            only_rec_check = QCheckBox()
            only_rec_check.setToolTip("仅识别，不进行文本检测")
            only_rec_check.setStyleSheet("QCheckBox::indicator { width: 16px; height: 16px; }")
            widgets["仅识别:"] = only_rec_check

            model_edit = QLineEdit()
            model_edit.setPlaceholderText("模型文件夹，相对于model/ocr")
            model_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["模型路径:"] = model_edit

        elif recognition_type.startswith("NeuralNetwork"):
            # 神经网络特有属性
            model_edit = QLineEdit()
            if recognition_type == "NeuralNetworkClassify":
                model_edit.setPlaceholderText("模型文件，相对于model/classify")
            else:  # NeuralNetworkDetect
                model_edit.setPlaceholderText("模型文件，相对于model/detect")
            model_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["模型路径:"] = model_edit

            expected_edit = QLineEdit()
            expected_edit.setPlaceholderText("0 或 [0, 1, 2]")
            expected_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["期望类别:"] = expected_edit

            if recognition_type == "NeuralNetworkDetect":
                threshold_spin = QDoubleSpinBox()
                threshold_spin.setRange(0, 1)
                threshold_spin.setSingleStep(0.1)
                threshold_spin.setValue(0.3)
                threshold_spin.setStyleSheet(self.INPUT_STYLE)
                widgets["置信度阈值:"] = threshold_spin

            labels_edit = QLineEdit()
            labels_edit.setPlaceholderText('["猫", "狗", "鼠"]')
            labels_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["标签列表:"] = labels_edit

        elif recognition_type == "Custom":
            # Custom特有属性
            custom_name_edit = QLineEdit()
            custom_name_edit.setPlaceholderText("注册的自定义识别器名称")
            custom_name_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["自定义识别名:"] = custom_name_edit

            custom_param_edit = QTextEdit()
            custom_param_edit.setPlaceholderText("JSON格式参数")
            custom_param_edit.setMaximumHeight(100)
            custom_param_edit.setStyleSheet("""
                QTextEdit {
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    padding: 2px;
                }
                QTextEdit:focus {
                    border: 1px solid #4a86e8;
                }
            """)
            widgets["自定义参数:"] = custom_param_edit

            roi_edit = QLineEdit()
            roi_edit.setPlaceholderText("节点名或坐标 [x,y,w,h]")
            roi_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["识别区域:"] = roi_edit

            roi_offset_edit = QLineEdit()
            roi_offset_edit.setPlaceholderText("[x,y,w,h]")
            roi_offset_edit.setText("[0,0,0,0]")
            roi_offset_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["区域偏移:"] = roi_offset_edit

        return widgets

    def create_action_containers(self):
        """为每种动作类型创建容器 - 优化版"""
        # 创建堆叠部件，用于存放所有不同动作的容器
        self.action_stack = QStackedWidget()

        # 为每种动作类型创建独立的容器和控件
        self.action_containers = {}
        self.action_property_widgets = {}

        # 遍历所有动作类型，为每一种创建一个容器
        for action_type in self.action_types:
            container = QWidget()
            layout = QFormLayout(container)
            layout.setSpacing(8)
            layout.setContentsMargins(5, 5, 5, 5)

            # 创建特定动作的属性控件
            widgets = self.create_action_property_widgets(action_type)

            # 将控件添加到容器中
            for label, widget in widgets.items():
                layout.addRow(label, widget)

            # 保存容器和控件引用
            self.action_containers[action_type] = container
            self.action_property_widgets[action_type] = widgets

            # 添加容器到堆叠部件
            self.action_stack.addWidget(container)

        # 将堆叠部件添加到动作属性组
        self.action_box.content_layout.addWidget(self.action_stack)

    def create_action_property_widgets(self, action_type):
        """为特定动作类型创建属性控件 - 优化版"""
        widgets = {}

        # 对于简单动作类型，没有特殊属性
        if action_type == "DoNothing":
            info_label = QLabel("DoNothing无需特殊配置")
            info_label.setStyleSheet("color: #666;")
            widgets[""] = info_label
            return widgets

        elif action_type == "StopTask":
            info_label = QLabel("该动作将停止当前任务链，无需配置特有属性。")
            info_label.setStyleSheet("color: #666;")
            widgets[""] = info_label
            return widgets

        elif action_type == "Click":

            target_edit = QLineEdit()
            target_edit.setPlaceholderText("节点名或坐标 [x,y,w,h]")
            target_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["点击目标:"] = target_edit

            target_offset_edit = QLineEdit()
            target_offset_edit.setPlaceholderText("[x,y,w,h]")
            target_offset_edit.setText("[0,0,0,0]")
            target_offset_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["目标偏移:"] = target_offset_edit

        elif action_type == "Swipe":
            # Swipe特有属性
            begin_edit = QLineEdit()
            begin_edit.setPlaceholderText("节点名或坐标 [x,y,w,h]")
            begin_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["起点:"] = begin_edit

            begin_offset_edit = QLineEdit()
            begin_offset_edit.setPlaceholderText("[x,y,w,h]")
            begin_offset_edit.setText("[0,0,0,0]")
            begin_offset_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["起点偏移:"] = begin_offset_edit

            end_edit = QLineEdit()
            end_edit.setPlaceholderText("节点名或坐标 [x,y,w,h]")
            end_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["终点:"] = end_edit

            end_offset_edit = QLineEdit()
            end_offset_edit.setPlaceholderText("[x,y,w,h]")
            end_offset_edit.setText("[0,0,0,0]")
            end_offset_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["终点偏移:"] = end_offset_edit

            duration_spin = QSpinBox()
            duration_spin.setRange(50, 5000)
            duration_spin.setValue(200)
            duration_spin.setStyleSheet(self.INPUT_STYLE)
            widgets["持续时间(ms):"] = duration_spin

        elif action_type == "MultiSwipe":
            # MultiSwipe特有属性
            swipes_edit = QTextEdit()
            swipes_edit.setPlaceholderText(
                '多指滑动配置，JSON格式，如:\n[\n  {"starting": 0, "begin": [100,200,10,10], "end": [300,400,10,10], "duration": 200},\n  {"starting": 500, "begin": [500,600,10,10], "end": [700,800,10,10], "duration": 300}\n]')
            swipes_edit.setMaximumHeight(120)
            swipes_edit.setStyleSheet("""
                QTextEdit {
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    padding: 2px;
                }
                QTextEdit:focus {
                    border: 1px solid #4a86e8;
                }
            """)
            widgets["滑动配置:"] = swipes_edit

        elif action_type == "Key":
            # Key特有属性
            key_edit = QLineEdit()
            key_edit.setPlaceholderText("25 或 [25, 26, 27]")
            key_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["按键码:"] = key_edit

        elif action_type == "InputText":
            # InputText特有属性
            input_text_edit = QLineEdit()
            input_text_edit.setPlaceholderText("要输入的文本")
            input_text_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["输入文本:"] = input_text_edit

        elif action_type in ["StartApp", "StopApp"]:
            # StartApp和StopApp特有属性
            package_edit = QLineEdit()
            if action_type == "StartApp":
                package_edit.setPlaceholderText("包名或Activity，如com.example.app")
            else:
                package_edit.setPlaceholderText("包名，如com.example.app")
            package_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["应用包名:"] = package_edit

        elif action_type == "Command":
            # Command特有属性
            exec_edit = QLineEdit()
            exec_edit.setPlaceholderText("执行程序路径")
            exec_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["执行程序:"] = exec_edit

            args_edit = QTextEdit()
            args_edit.setPlaceholderText('["arg1", "arg2", "{NODE}", "{BOX}"]')
            args_edit.setMaximumHeight(80)
            args_edit.setStyleSheet("""
                QTextEdit {
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    padding: 2px;
                }
                QTextEdit:focus {
                    border: 1px solid #4a86e8;
                }
            """)
            widgets["执行参数:"] = args_edit

            detach_check = QCheckBox()
            detach_check.setToolTip("是否分离子进程，不等待完成继续执行")
            detach_check.setStyleSheet("QCheckBox::indicator { width: 16px; height: 16px; }")
            widgets["分离进程:"] = detach_check

        elif action_type == "Custom":
            # Custom特有属性
            custom_action_edit = QLineEdit()
            custom_action_edit.setPlaceholderText("注册的自定义动作名称")
            custom_action_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["自定义动作名:"] = custom_action_edit

            custom_param_edit = QTextEdit()
            custom_param_edit.setPlaceholderText("JSON格式参数")
            custom_param_edit.setMaximumHeight(100)
            custom_param_edit.setStyleSheet("""
                QTextEdit {
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    padding: 2px;
                }
                QTextEdit:focus {
                    border: 1px solid #4a86e8;
                }
            """)
            widgets["自定义参数:"] = custom_param_edit

            target_edit = QLineEdit()
            target_edit.setPlaceholderText("节点名或坐标 [x,y,w,h]")
            target_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["目标:"] = target_edit

            target_offset_edit = QLineEdit()
            target_offset_edit.setPlaceholderText("[x,y,w,h]")
            target_offset_edit.setText("[0,0,0,0]")
            target_offset_edit.setStyleSheet(self.INPUT_STYLE)
            widgets["目标偏移:"] = target_offset_edit

        return widgets

    def connect_signals(self):
        """连接信号 - 优化版"""
        # 识别算法和动作类型变化时切换对应的属性容器
        self.recognition_combo.currentTextChanged.connect(self.on_recognition_changed)
        self.action_combo.currentTextChanged.connect(self.on_action_changed)

        # 应用和重置按钮
        self.apply_button.clicked.connect(self.apply_changes)
        self.reset_button.clicked.connect(self.reset_form)

        # 自动保存复选框
        self.auto_save_check.toggled.connect(self.toggle_auto_save)

        # 连接基本属性的修改信号
        self.node_name_input.textChanged.connect(self.on_widget_changed)
        self.recognition_combo.currentTextChanged.connect(self.on_widget_changed)
        self.action_combo.currentTextChanged.connect(self.on_widget_changed)
        self.next_editor.value_changed.connect(self.on_widget_changed)
        self.interrupt_editor.value_changed.connect(self.on_widget_changed)
        self.on_error_editor.value_changed.connect(self.on_widget_changed)
        self.is_sub_check.toggled.connect(self.on_widget_changed)
        self.rate_limit_spin.valueChanged.connect(self.on_widget_changed)
        self.timeout_spin.valueChanged.connect(self.on_widget_changed)
        self.inverse_check.toggled.connect(self.on_widget_changed)
        self.enabled_check.toggled.connect(self.on_widget_changed)
        self.pre_delay_spin.valueChanged.connect(self.on_widget_changed)
        self.post_delay_spin.valueChanged.connect(self.on_widget_changed)
        self.pre_wait_freezes_spin.valueChanged.connect(self.on_widget_changed)
        self.post_wait_freezes_spin.valueChanged.connect(self.on_widget_changed)
        self.focus_check.toggled.connect(self.on_widget_changed)

    def toggle_auto_save(self, checked):
        """切换自动保存模式"""
        self.auto_save = checked
        self.apply_button.setEnabled(not checked)

    def on_widget_changed(self, *args):
        """当任何控件更改时触发"""
        # 如果正在批量更新UI，不触发自动保存
        if self.is_updating_ui:
            return

        # 如果启用了自动保存，则自动应用更改
        if self.auto_save:
            # 使用QTimer延时一点点再保存，避免频繁保存导致性能问题
            QTimer.singleShot(300, self.apply_changes_silent)

    def apply_changes_silent(self):
        """静默应用更改，不显示消息框"""
        if not self.current_node or not self.auto_save:
            return

        # 更新节点名称
        self.current_node.name = self.node_name_input.text()

        # 更新基本属性
        self.current_node.recognition = self.recognition_combo.currentText()
        self.current_node.action = self.action_combo.currentText()

        # 更新流程控制属性
        self.current_node.next = self.next_editor.get_value()
        self.current_node.interrupt = self.interrupt_editor.get_value()
        self.current_node.on_error = self.on_error_editor.get_value()

        # 更新通用属性
        self.current_node.is_sub = self.is_sub_check.isChecked()
        self.current_node.rate_limit = self.rate_limit_spin.value()
        self.current_node.timeout = self.timeout_spin.value()
        self.current_node.inverse = self.inverse_check.isChecked()
        self.current_node.enabled = self.enabled_check.isChecked()
        self.current_node.pre_delay = self.pre_delay_spin.value()
        self.current_node.post_delay = self.post_delay_spin.value()
        self.current_node.pre_wait_freezes = self.pre_wait_freezes_spin.value()
        self.current_node.post_wait_freezes = self.post_wait_freezes_spin.value()
        self.current_node.focus = self.focus_check.isChecked()

        # 更新算法特有属性
        self.apply_recognition_properties(silent=True)

        # 更新动作特有属性
        self.apply_action_properties(silent=True)

        # 发送节点已更改信号
        self.node_changed.emit(self.current_node)

    def on_recognition_changed(self, recognition_type):
        """当识别算法类型改变时切换到对应的容器 - 优化版"""
        # 切换到对应算法的控件容器
        if recognition_type in self.recognition_types:
            index = self.recognition_types.index(recognition_type)
            self.recognition_stack.setCurrentIndex(index)

            # 如果有特有属性，自动展开折叠框
            if recognition_type != "DirectHit":
                self.recognition_box.set_expanded(True)
            else:
                self.recognition_box.set_expanded(False)

    def on_action_changed(self, action_type):
        """当动作类型改变时切换到对应的容器 - 优化版"""
        # 切换到对应动作的控件容器
        if action_type in self.action_types:
            index = self.action_types.index(action_type)
            self.action_stack.setCurrentIndex(index)

            # 如果有特有属性，自动展开折叠框
            if action_type not in ["DoNothing", "StopTask"]:
                self.action_box.set_expanded(True)
            else:
                self.action_box.set_expanded(False)

    def set_node(self, node=None):
        """设置要编辑的节点，如果为None则创建一个默认节点 - 优化版"""
        try:
            self.is_updating_ui = True

            if node is None:
                # 创建一个默认节点
                self.current_node = TaskNode("New Node")
            else:
                # 判断传入的是什么类型的节点
                if hasattr(node, 'name'):
                    # 如果是TaskNode类型或已有name属性，直接使用
                    self.current_node = node
                else:
                    # 如果是其他类型的节点（如Scene Graph中的Node），需要转换或适配
                    try:
                        # 尝试从node.id或其他属性获取名称
                        name = getattr(node, 'id', f"Node_{id(node)}")
                        # 尝试从node.data获取属性配置
                        data = getattr(node, 'data', {})
                        # 创建一个TaskNode
                        self.current_node = TaskNode(name, **data)
                    except Exception as e:
                        # 如果转换失败，创建一个空节点
                        print(f"Error converting node: {e}")
                        self.current_node = TaskNode(f"Node_{id(node)}")

            # 更新界面
            self.update_ui_from_node()
        finally:
            # 确保标志被重置，即使发生异常
            self.is_updating_ui = False

    def update_ui_from_node(self):
        """根据当前节点更新UI控件 - 优化版"""
        if not self.current_node:
            return

        self.is_updating_ui = True

        try:
            # 设置基本属性
            self.node_name_input.setText(self.current_node.name)

            # 设置识别算法和动作类型
            recognition_index = self.recognition_combo.findText(self.current_node.recognition)
            if recognition_index >= 0:
                self.recognition_combo.setCurrentIndex(recognition_index)

            action_index = self.action_combo.findText(self.current_node.action)
            if action_index >= 0:
                self.action_combo.setCurrentIndex(action_index)

            # 设置流程控制属性
            self.next_editor.set_value(self.current_node.next)
            self.interrupt_editor.set_value(self.current_node.interrupt)
            self.on_error_editor.set_value(self.current_node.on_error)

            # 设置通用属性
            self.is_sub_check.setChecked(self.current_node.is_sub)
            self.rate_limit_spin.setValue(self.current_node.rate_limit)
            self.timeout_spin.setValue(self.current_node.timeout)
            self.inverse_check.setChecked(self.current_node.inverse)
            self.enabled_check.setChecked(self.current_node.enabled)
            self.pre_delay_spin.setValue(self.current_node.pre_delay)
            self.post_delay_spin.setValue(self.current_node.post_delay)
            self.pre_wait_freezes_spin.setValue(self.current_node.pre_wait_freezes)
            self.post_wait_freezes_spin.setValue(self.current_node.post_wait_freezes)
            self.focus_check.setChecked(self.current_node.focus)

            # 更新识别算法特有属性
            self.update_recognition_properties()

            # 更新动作特有属性
            self.update_action_properties()

            # 根据属性是否存在来自动展开或折叠区域
            if self.current_node.recognition != "DirectHit":
                self.recognition_box.set_expanded(True)
            else:
                self.recognition_box.set_expanded(False)

            if self.current_node.action not in ["DoNothing", "StopTask"]:
                self.action_box.set_expanded(True)
            else:
                self.action_box.set_expanded(False)

            # 如果有后继节点或中断节点，展开流程控制区域
            if (self.current_node.next or self.current_node.interrupt or
                    self.current_node.on_error):
                self.flow_box.set_expanded(True)
        finally:
            self.is_updating_ui = False

    def update_recognition_properties(self):
        """更新识别算法特有属性控件 - 优化版"""
        if not self.current_node:
            return

        rec_type = self.current_node.recognition
        widgets = self.recognition_property_widgets.get(rec_type, {})

        if "识别区域:" in widgets:
            roi_edit = widgets["识别区域:"]
            roi = getattr(self.current_node, "roi", [0, 0, 0, 0])
            if isinstance(roi, list):
                roi_edit.setText(str(roi))
            elif isinstance(roi, str):
                roi_edit.setText(roi)

        if "区域偏移:" in widgets:
            roi_offset_edit = widgets["区域偏移:"]
            roi_offset = getattr(self.current_node, "roi_offset", [0, 0, 0, 0])
            if isinstance(roi_offset, list):
                roi_offset_edit.setText(str(roi_offset))

        if "结果排序:" in widgets:
            order_combo = widgets["结果排序:"]
            order_by = getattr(self.current_node, "order_by", "Horizontal")
            order_combo.setCurrentText(order_by)

        if "结果索引:" in widgets:
            index_spin = widgets["结果索引:"]
            index = getattr(self.current_node, "index", 0)
            index_spin.setValue(index)

        # 处理其他算法特有属性
        for widget_label, widget in widgets.items():
            if widget_label in ["识别区域:", "区域偏移:", "结果排序:", "结果索引:", ""]:
                continue  # 这些已经处理过了

            # Template Match
            if widget_label == "模板图片:":
                template = getattr(self.current_node, "template", "")
                if isinstance(template, list):
                    widget.setText(str(template))
                else:
                    widget.setText(str(template))

            elif widget_label == "匹配阈值:" or widget_label == "置信度阈值:":
                threshold = getattr(self.current_node, "threshold", 0.7 if widget_label == "匹配阈值:" else 0.3)
                widget.setValue(threshold)

            elif widget_label == "匹配算法:" or widget_label == "颜色空间:":
                method = getattr(self.current_node, "method", 5 if widget_label == "匹配算法:" else 4)
                widget.setValue(method)

            elif widget_label == "绿色掩码:":
                green_mask = getattr(self.current_node, "green_mask", False)
                widget.setChecked(green_mask)

            # Feature Match
            elif widget_label == "特征点数量:" or widget_label == "点数阈值:":
                count = getattr(self.current_node, "count", 4 if widget_label == "特征点数量:" else 1)
                widget.setValue(count)

            elif widget_label == "特征检测器:":
                detector = getattr(self.current_node, "detector", "SIFT")
                widget.setCurrentText(detector)

            elif widget_label == "距离比值:":
                ratio = getattr(self.current_node, "ratio", 0.6)
                widget.setValue(ratio)

            # Color Match
            elif widget_label == "颜色下限:" or widget_label == "颜色上限:":
                attr_name = "lower" if widget_label == "颜色下限:" else "upper"
                value = getattr(self.current_node, attr_name, [])
                if value:
                    widget.setText(json.dumps(value))

            elif widget_label == "要求相连:":
                connected = getattr(self.current_node, "connected", False)
                widget.setChecked(connected)

            # OCR
            elif widget_label == "期望文本:":
                expected = getattr(self.current_node, "expected", "")
                if isinstance(expected, list):
                    widget.setText(json.dumps(expected))
                else:
                    widget.setText(str(expected))

            elif widget_label == "文本替换:":
                replace = getattr(self.current_node, "replace", "")
                if replace:
                    widget.setText(json.dumps(replace))

            elif widget_label == "仅识别:":
                only_rec = getattr(self.current_node, "only_rec", False)
                widget.setChecked(only_rec)

            elif widget_label == "模型路径:":
                model = getattr(self.current_node, "model", "")
                widget.setText(model)

            # Neural Network
            elif widget_label == "期望类别:":
                expected = getattr(self.current_node, "expected", "")
                if isinstance(expected, list):
                    widget.setText(json.dumps(expected))
                else:
                    widget.setText(str(expected))

            elif widget_label == "标签列表:":
                labels = getattr(self.current_node, "labels", [])
                if labels:
                    widget.setText(json.dumps(labels))

            # Custom
            elif widget_label == "自定义识别名:":
                custom_recognition = getattr(self.current_node, "custom_recognition", "")
                widget.setText(custom_recognition)

            elif widget_label == "自定义参数:":
                custom_param = getattr(self.current_node, "custom_recognition_param", {})
                if custom_param:
                    widget.setText(json.dumps(custom_param, indent=2))

            elif widget_label == "识别区域类型:":
                roi = getattr(self.current_node, "roi", [0, 0, 0, 0])
                if roi == [0, 0, 0, 0]:
                    widget.setCurrentText("全屏")
                elif isinstance(roi, str):
                    widget.setCurrentText("其他节点")
                else:
                    widget.setCurrentText("固定坐标")

    def update_action_properties(self):
        """更新动作特有属性控件 - 优化版"""
        if not self.current_node:
            return

        action_type = self.current_node.action
        widgets = self.action_property_widgets.get(action_type, {})

        if "点击目标:" in widgets:
            target_edit = widgets["点击目标:"]
            target = getattr(self.current_node, "target", True)
            if isinstance(target, str) or isinstance(target, list):
                target_edit.setText(str(target))

        if "目标偏移:" in widgets:
            target_offset_edit = widgets["目标偏移:"]
            target_offset = getattr(self.current_node, "target_offset", [0, 0, 0, 0])
            if isinstance(target_offset, list):
                target_offset_edit.setText(str(target_offset))

        # 处理滑动起点终点控件
        for point_type in ["起点", "终点"]:
            if f"{point_type}类型:" in widgets:
                type_combo = widgets[f"{point_type}类型:"]
                point_key = "begin" if point_type == "起点" else "end"
                point = getattr(self.current_node, point_key, True)
                if point is True:
                    type_combo.setCurrentText("自身")
                elif isinstance(point, str):
                    type_combo.setCurrentText("其他节点")
                elif isinstance(point, list):
                    type_combo.setCurrentText("固定坐标")

            if f"{point_type}:" in widgets:
                point_edit = widgets[f"{point_type}:"]
                point_key = "begin" if point_type == "起点" else "end"
                point = getattr(self.current_node, point_key, True)
                if isinstance(point, str) or isinstance(point, list):
                    point_edit.setText(str(point))

            if f"{point_type}偏移:" in widgets:
                offset_edit = widgets[f"{point_type}偏移:"]
                offset_key = f"{point_key}_offset"
                offset = getattr(self.current_node, offset_key, [0, 0, 0, 0])
                if isinstance(offset, list):
                    offset_edit.setText(str(offset))

        # 处理其他特有属性
        for widget_label, widget in widgets.items():
            if (widget_label.startswith("点击目标") or
                    widget_label.startswith("起点") or
                    widget_label.startswith("终点") or
                    widget_label.startswith("目标") or
                    widget_label == ""):
                continue  # 这些已经处理过了

            # 处理特殊属性
            if widget_label == "持续时间(ms):":
                duration = getattr(self.current_node, "duration", 200)
                widget.setValue(duration)

            elif widget_label == "滑动配置:":
                swipes = getattr(self.current_node, "swipes", [])
                if isinstance(swipes, list):
                    widget.setText(json.dumps(swipes, indent=2))

            elif widget_label == "按键码:":
                key_value = getattr(self.current_node, "key", None)
                if key_value is not None:
                    widget.setText(str(key_value))

            elif widget_label == "输入文本:":
                input_text = getattr(self.current_node, "input_text", "")
                widget.setText(input_text)

            elif widget_label == "应用包名:":
                package = getattr(self.current_node, "package", "")
                widget.setText(package)

            elif widget_label == "执行程序:":
                exec_path = getattr(self.current_node, "exec", "")
                widget.setText(exec_path)

            elif widget_label == "执行参数:":
                args = getattr(self.current_node, "args", [])
                if isinstance(args, list):
                    widget.setText(json.dumps(args, indent=2))

            elif widget_label == "分离进程:":
                detach = getattr(self.current_node, "detach", False)
                widget.setChecked(detach)

            elif widget_label == "自定义动作名:":
                custom_action = getattr(self.current_node, "custom_action", "")
                widget.setText(custom_action)

            elif widget_label == "自定义参数:":
                custom_param = getattr(self.current_node, "custom_action_param", {})
                widget.setText(json.dumps(custom_param, indent=2))

    def apply_changes(self):
        """应用所有更改到当前节点 - 优化版"""
        if not self.current_node:
            return

        # 如果不是自动保存模式，显示确认对话框
        if not self.auto_save:
            reply = QMessageBox.question(
                self, "确认更改",
                "确定要应用这些更改到节点吗?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

        # 更新节点名称
        self.current_node.name = self.node_name_input.text()

        # 更新基本属性
        self.current_node.recognition = self.recognition_combo.currentText()
        self.current_node.action = self.action_combo.currentText()

        # 更新流程控制属性
        self.current_node.next = self.next_editor.get_value()
        self.current_node.interrupt = self.interrupt_editor.get_value()
        self.current_node.on_error = self.on_error_editor.get_value()

        # 更新通用属性
        self.current_node.is_sub = self.is_sub_check.isChecked()
        self.current_node.rate_limit = self.rate_limit_spin.value()
        self.current_node.timeout = self.timeout_spin.value()
        self.current_node.inverse = self.inverse_check.isChecked()
        self.current_node.enabled = self.enabled_check.isChecked()
        self.current_node.pre_delay = self.pre_delay_spin.value()
        self.current_node.post_delay = self.post_delay_spin.value()
        self.current_node.pre_wait_freezes = self.pre_wait_freezes_spin.value()
        self.current_node.post_wait_freezes = self.post_wait_freezes_spin.value()
        self.current_node.focus = self.focus_check.isChecked()

        # 更新算法特有属性
        self.apply_recognition_properties()

        # 更新动作特有属性
        self.apply_action_properties()

        # 发送节点已更改信号
        self.node_changed.emit(self.current_node)

        # 如果不是自动保存模式，显示提示
        if not self.auto_save:
            QMessageBox.information(self, "提示", "节点属性已更新")

    def apply_recognition_properties(self, silent=False):
        """应用识别算法特有属性到节点 - 优化版"""
        if not self.current_node:
            return

        rec_type = self.current_node.recognition
        widgets = self.recognition_property_widgets.get(rec_type, {})

        # 处理ROI相关属性
        if "识别区域:" in widgets:
            roi_edit = widgets["识别区域:"]
            roi_text = roi_edit.text()

            # 判断是节点名称还是坐标
            if roi_text.startswith("[") and roi_text.endswith("]"):
                try:
                    # 尝试解析为坐标
                    roi_str = roi_text.strip("[]").split(",")
                    roi = [int(x.strip()) for x in roi_str]
                    if len(roi) == 4:
                        self.current_node.roi = roi
                    elif not silent:
                        QMessageBox.warning(self, "输入错误", "ROI坐标格式不正确，应为[x,y,w,h]")
                except Exception as e:
                    if not silent:
                        QMessageBox.warning(self, "输入错误", f"ROI坐标格式不正确: {str(e)}")
            elif roi_text == "":
                # 空值默认为全屏
                self.current_node.roi = [0, 0, 0, 0]
            else:
                # 否则为节点名称
                self.current_node.roi = roi_text

        # 处理区域偏移
        if "区域偏移:" in widgets:
            try:
                offset_edit = widgets["区域偏移:"]
                if offset_edit.text():
                    offset_str = offset_edit.text().strip("[]").split(",")
                    offset = [int(x.strip()) for x in offset_str]
                    if len(offset) == 4:
                        self.current_node.roi_offset = offset
                    elif not silent:
                        QMessageBox.warning(self, "输入错误", "ROI偏移坐标格式不正确，应为[x,y,w,h]")
            except Exception as e:
                if not silent:
                    QMessageBox.warning(self, "输入错误", f"ROI偏移坐标格式不正确: {str(e)}")

        # 处理结果排序和索引
        if "结果排序:" in widgets:
            self.current_node.order_by = widgets["结果排序:"].currentText()

        if "结果索引:" in widgets:
            self.current_node.index = widgets["结果索引:"].value()

        # 处理特定算法属性
        for widget_label, widget in widgets.items():
            if widget_label in ["识别区域:", "区域偏移:", "结果排序:", "结果索引:", ""]:
                continue  # 这些已经处理过了

            # 针对不同算法的特殊处理
            if widget_label == "模板图片:":
                text = widget.text()
                if "[" in text and "]" in text:  # 可能是数组
                    try:
                        # 尝试解析为数组
                        import ast
                        templates = ast.literal_eval(text)
                        if isinstance(templates, list):
                            self.current_node.template = templates
                        else:
                            self.current_node.template = text
                    except:
                        # 如果解析失败，就当作字符串
                        self.current_node.template = text
                else:
                    self.current_node.template = text

            elif widget_label == "匹配阈值:" or widget_label == "置信度阈值:":
                self.current_node.threshold = widget.value()

            elif widget_label == "匹配算法:" or widget_label == "颜色空间:":
                self.current_node.method = widget.value()

            elif widget_label == "绿色掩码:":
                self.current_node.green_mask = widget.isChecked()

            elif widget_label == "特征点数量:" or widget_label == "点数阈值:":
                self.current_node.count = widget.value()

            elif widget_label == "特征检测器:":
                self.current_node.detector = widget.currentText()

            elif widget_label == "距离比值:":
                self.current_node.ratio = widget.value()

            elif widget_label == "颜色下限:" or widget_label == "颜色上限:":
                attr_name = "lower" if widget_label == "颜色下限:" else "upper"
                try:
                    if widget.text():
                        value = json.loads(widget.text())
                        setattr(self.current_node, attr_name, value)
                except:
                    if not silent:
                        QMessageBox.warning(self, "输入错误", f"{widget_label}格式不正确，应为JSON格式")

            elif widget_label == "要求相连:":
                self.current_node.connected = widget.isChecked()

            elif widget_label == "期望文本:":
                try:
                    text = widget.text()
                    if text.startswith("[") and text.endswith("]"):
                        # 尝试解析为JSON数组
                        expected = json.loads(text)
                        self.current_node.expected = expected
                    else:
                        # 当作普通文本
                        self.current_node.expected = text
                except:
                    # 如果解析失败，就当作普通文本
                    self.current_node.expected = widget.text()

            elif widget_label == "文本替换:":
                try:
                    if widget.text():
                        replace = json.loads(widget.text())
                        self.current_node.replace = replace
                except:
                    if not silent:
                        QMessageBox.warning(self, "输入错误", "文本替换格式不正确，应为JSON格式")

            elif widget_label == "仅识别:":
                self.current_node.only_rec = widget.isChecked()

            elif widget_label == "模型路径:":
                self.current_node.model = widget.text()

            elif widget_label == "标签列表:":
                try:
                    if widget.text():
                        labels = json.loads(widget.text())
                        self.current_node.labels = labels
                except:
                    if not silent:
                        QMessageBox.warning(self, "输入错误", "标签列表格式不正确，应为JSON格式")

            elif widget_label == "自定义识别名:":
                self.current_node.custom_recognition = widget.text()

            elif widget_label == "自定义参数:":
                try:
                    if widget.toPlainText():
                        param = json.loads(widget.toPlainText())
                        self.current_node.custom_recognition_param = param
                except:
                    if not silent:
                        QMessageBox.warning(self, "输入错误", "自定义参数格式不正确，应为JSON格式")

    def apply_action_properties(self, silent=False):
        """应用动作特有属性到节点 - 优化版"""
        if not self.current_node:
            return

        action_type = self.current_node.action
        widgets = self.action_property_widgets.get(action_type, {})

        # 处理点击目标相关属性
        if "点击目标类型:" in widgets and "点击目标:" in widgets:
            target_type = widgets["点击目标类型:"].currentText()
            target_edit = widgets["点击目标:"]

            if target_type == "自身":
                self.current_node.target = True
            elif target_type == "其他节点":
                self.current_node.target = target_edit.text()
            elif target_type == "固定坐标":
                try:
                    target_str = target_edit.text().strip("[]").split(",")
                    target = [int(x.strip()) for x in target_str]
                    if len(target) == 4:
                        self.current_node.target = target
                    elif not silent:
                        QMessageBox.warning(self, "输入错误", "目标坐标格式不正确，应为[x,y,w,h]")
                except Exception as e:
                    if not silent:
                        QMessageBox.warning(self, "输入错误", f"目标坐标格式不正确: {str(e)}")

        # 处理目标偏移
        if "目标偏移:" in widgets:
            try:
                offset_edit = widgets["目标偏移:"]
                if offset_edit.text():
                    offset_str = offset_edit.text().strip("[]").split(",")
                    offset = [int(x.strip()) for x in offset_str]
                    if len(offset) == 4:
                        self.current_node.target_offset = offset
                    elif not silent:
                        QMessageBox.warning(self, "输入错误", "目标偏移坐标格式不正确，应为[x,y,w,h]")
            except Exception as e:
                if not silent:
                    QMessageBox.warning(self, "输入错误", f"目标偏移坐标格式不正确: {str(e)}")

        # 处理滑动起点和终点相关属性
        for point_type, attr_name in [("起点", "begin"), ("终点", "end")]:
            type_key = f"{point_type}类型:"
            point_key = f"{point_type}:"
            offset_key = f"{point_type}偏移:"

            if type_key in widgets and point_key in widgets:
                point_type_combo = widgets[type_key]
                point_edit = widgets[point_key]
                point_type_value = point_type_combo.currentText()

                if point_type_value == "自身":
                    setattr(self.current_node, attr_name, True)
                elif point_type_value == "其他节点":
                    setattr(self.current_node, attr_name, point_edit.text())
                elif point_type_value == "固定坐标":
                    try:
                        point_str = point_edit.text().strip("[]").split(",")
                        point = [int(x.strip()) for x in point_str]
                        if len(point) == 4:
                            setattr(self.current_node, attr_name, point)
                        elif not silent:
                            QMessageBox.warning(self, "输入错误", f"{point_type}坐标格式不正确，应为[x,y,w,h]")
                    except Exception as e:
                        if not silent:
                            QMessageBox.warning(self, "输入错误", f"{point_type}坐标格式不正确: {str(e)}")

            # 处理偏移
            if offset_key in widgets:
                try:
                    offset_edit = widgets[offset_key]
                    if offset_edit.text():
                        offset_str = offset_edit.text().strip("[]").split(",")
                        offset = [int(x.strip()) for x in offset_str]
                        if len(offset) == 4:
                            setattr(self.current_node, f"{attr_name}_offset", offset)
                        elif not silent:
                            QMessageBox.warning(self, "输入错误", f"{point_type}偏移坐标格式不正确，应为[x,y,w,h]")
                except Exception as e:
                    if not silent:
                        QMessageBox.warning(self, "输入错误", f"{point_type}偏移坐标格式不正确: {str(e)}")

        # 处理其他特有属性
        for widget_label, widget in widgets.items():
            # 跳过已处理的属性
            if (widget_label.startswith("点击目标") or
                    widget_label.startswith("起点") or
                    widget_label.startswith("终点") or
                    widget_label.startswith("目标") or
                    widget_label == ""):
                continue

            # 针对不同动作类型的特殊处理
            if widget_label == "持续时间(ms):":
                self.current_node.duration = widget.value()

            elif widget_label == "滑动配置:":
                try:
                    if widget.toPlainText():
                        swipes = json.loads(widget.toPlainText())
                        self.current_node.swipes = swipes
                except:
                    if not silent:
                        QMessageBox.warning(self, "输入错误", "滑动配置格式不正确，应为JSON格式")

            elif widget_label == "按键码:":
                try:
                    key_text = widget.text()
                    if key_text.startswith("[") and key_text.endswith("]"):
                        # 尝试解析为数组
                        key_value = json.loads(key_text)
                        self.current_node.key = key_value
                    elif key_text:
                        # 解析为数字
                        self.current_node.key = int(key_text)
                    else:
                        self.current_node.key = None
                except:
                    if not silent:
                        QMessageBox.warning(self, "输入错误", "按键码格式不正确，应为数字或数组")

            elif widget_label == "输入文本:":
                self.current_node.input_text = widget.text()

            elif widget_label == "应用包名:":
                self.current_node.package = widget.text()

            elif widget_label == "执行程序:":
                self.current_node.exec = widget.text()

            elif widget_label == "执行参数:":
                try:
                    if widget.toPlainText():
                        args = json.loads(widget.toPlainText())
                        self.current_node.args = args
                except:
                    if not silent:
                        QMessageBox.warning(self, "输入错误", "执行参数格式不正确，应为JSON格式")

            elif widget_label == "分离进程:":
                self.current_node.detach = widget.isChecked()

            elif widget_label == "自定义动作名:":
                self.current_node.custom_action = widget.text()

            elif widget_label == "自定义参数:":
                try:
                    if widget.toPlainText():
                        param = json.loads(widget.toPlainText())
                        self.current_node.custom_action_param = param
                except:
                    if not silent:
                        QMessageBox.warning(self, "输入错误", "自定义参数格式不正确，应为JSON格式")

    def reset_form(self):
        """重置表单到当前节点的原始状态 - 优化版"""
        if self.current_node:
            self.update_ui_from_node()
            QMessageBox.information(self, "提示", "表单已重置为当前节点状态")