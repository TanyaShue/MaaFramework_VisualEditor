import json
from typing import Dict, Any, Optional, List, Tuple

from PySide6.QtCore import Signal, QTimer
from PySide6.QtGui import QTextCursor, QFont
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFormLayout,
                               QLineEdit, QSpinBox, QPushButton, QCheckBox,
                               QComboBox, QTextEdit, QDoubleSpinBox, QHBoxLayout,
                               QScrollArea, QFrame, QMessageBox,
                               QTabWidget, QStackedWidget)

from src.config_manager import config_manager
from src.pipeline import TaskNode
from src.views.components.collapsible_box import CollapsibleBox
from src.views.components.list_editor import ListEditor
from src.views.components.image_preview_container import ImagePreviewContainer, ImageContainer


class PropertyConfig:
    """属性配置类"""

    def __init__(self, widget_type: str, label: str = "", **kwargs):
        self.widget_type = widget_type
        self.label = label
        self.kwargs = kwargs


class NodePropertiesEditor(QWidget):
    """节点属性编辑器"""

    node_changed = Signal(object)

    # 样式常量
    STYLES = {
        "button": """
            QPushButton {
                background-color: #4a86e8;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #3a76d8; }
            QPushButton:pressed { background-color: #2a66c8; }
            QPushButton:disabled { background-color: #cccccc; }
        """,
        "reset_button": """
            QPushButton {
                background-color: #f8f8f8;
                color: #333;
                border: 1px solid #ccc;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #e8e8e8; }
            QPushButton:pressed { background-color: #d8d8d8; }
        """,
        "input": """
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                padding: 3px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border: 1px solid #4a86e8;
            }
        """
    }

    # 属性定义
    PROPERTY_DEFAULTS = {
        "recognition": "DirectHit",
        "action": "DoNothing",
        "next": [],
        "interrupt": [],
        "on_error": [],
        "is_sub": False,
        "rate_limit": 1000,
        "timeout": 20000,
        "inverse": False,
        "enabled": True,
        "pre_delay": 200,
        "post_delay": 200,
        "pre_wait_freezes": 0,
        "post_wait_freezes": 0,
        "focus": False,
        "method": 5,
        "green_mask": False,
        "count": 4,
        "detector": "SIFT",
        "ratio": 0.6,
        "connected": False,
        "only_rec": False,
        "order_by": "Horizontal",
        "index": 0,
        "target": True,
        "begin": True,
        "end": True,
        "duration": 200,
        "detach": False
    }

    # 特定算法的属性默认值
    ALGORITHM_DEFAULTS = {
        "TemplateMatch": {
            "threshold": 0.7
        },
        "FeatureMatch":{
            "count":4
        },
        "OCR": {
            "threshold": 0.3
        },
        "NeuralNetworkDetect": {
            "threshold": 0.3
        },
        "ColorMatch":{
            "count":1
        }
        # 可以添加更多算法特定的默认值
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        self.recognition_types = [
            "DirectHit", "TemplateMatch", "FeatureMatch", "ColorMatch",
            "OCR", "NeuralNetworkClassify", "NeuralNetworkDetect", "Custom"
        ]

        self.action_types = [
            "DoNothing", "Click", "Swipe", "MultiSwipe", "Key",
            "InputText", "StartApp", "StopApp", "StopTask", "Command", "Custom"
        ]

        self.current_node = None
        self.is_updating_ui = False
        self.auto_save = False

        # 存储所有widget的字典
        self.widgets = {}
        self.property_widgets = {}

        self.init_ui()
        self.setup_properties()
        self.connect_signals()
        self.set_node()

    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 创建选项卡
        self.tab_widget = QTabWidget()
        self.setup_tabs()
        main_layout.addWidget(self.tab_widget)

    def setup_tabs(self):
        """设置选项卡"""
        # 属性编辑选项卡
        properties_tab = self.create_properties_tab()
        self.tab_widget.addTab(properties_tab, "属性")

        # JSON选项卡
        json_tab = self.create_json_tab()
        self.tab_widget.addTab(json_tab, "json预览")

    def create_properties_tab(self):
        """创建属性编辑选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 标题
        title = QLabel("节点属性编辑器")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #333;")
        layout.addWidget(title)

        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)

        self.scroll_layout = QVBoxLayout(scroll_widget)
        self.scroll_layout.setSpacing(10)

        # 创建各个属性组
        self.create_property_groups()

        self.scroll_layout.addStretch()
        layout.addWidget(scroll_area, 1)

        # 按钮区域
        button_layout = self.create_button_layout()
        layout.addLayout(button_layout)

        return tab

    def create_json_tab(self):
        """创建JSON选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 错误提示
        self.json_error_banner = QLabel()
        self.json_error_banner.setStyleSheet("""
            QLabel {
                background-color: #ffdddd;
                color: #990000;
                padding: 8px;
                border-radius: 3px;
                border: 1px solid #990000;
            }
        """)
        self.json_error_banner.setWordWrap(True)
        self.json_error_banner.hide()
        layout.addWidget(self.json_error_banner)

        # JSON编辑器
        self.json_editor = QTextEdit()
        font = QFont("Consolas, Courier New, monospace", 11)
        self.json_editor.setFont(font)
        layout.addWidget(self.json_editor, 1)

        # 按钮
        button_layout = QHBoxLayout()
        self.json_apply_button = QPushButton("应用JSON")
        self.json_apply_button.setStyleSheet(self.STYLES["button"])
        self.json_reset_button = QPushButton("重置JSON")
        self.json_reset_button.setStyleSheet(self.STYLES["reset_button"])

        button_layout.addStretch()
        button_layout.addWidget(self.json_reset_button)
        button_layout.addWidget(self.json_apply_button)
        layout.addLayout(button_layout)

        return tab

    def create_property_groups(self):
        """创建属性组"""
        self.boxes = {}

        # 基本属性
        self.create_basic_properties()

        # 预览
        self.create_preview_box()

        # 流程控制
        self.create_flow_control()

        # 通用属性
        self.create_common_properties()

        # 算法和动作特定属性
        self.create_algorithm_properties()

    def create_basic_properties(self):
        """创建基本属性"""
        box = self.create_box("基本属性")

        configs = {
            "name": PropertyConfig("QLineEdit", "节点名称:", placeholder="输入节点名称"),
            "recognition": PropertyConfig("QComboBox", "识别算法:",
                                          items=self.recognition_types,
                                          default=self.PROPERTY_DEFAULTS.get("recognition")),
            "action": PropertyConfig("QComboBox", "执行动作:",
                                     items=self.action_types,
                                     default=self.PROPERTY_DEFAULTS.get("action"))
        }

        self.add_properties_to_box(box, configs)

    def create_preview_box(self):
        """创建预览框"""
        box = self.create_box("节点识别预览")

        self.image_preview_container = ImagePreviewContainer()
        self.image_preview_container.setMinimumHeight(150)
        box.content_layout.addWidget(self.image_preview_container)

    def create_flow_control(self):
        """创建流程控制"""
        box = self.create_box("流程控制")

        configs = {
            "next": PropertyConfig("ListEditor", "后继节点:",
                                   default=self.PROPERTY_DEFAULTS.get("next")),
            "interrupt": PropertyConfig("ListEditor", "中断节点:",
                                        default=self.PROPERTY_DEFAULTS.get("interrupt")),
            "on_error": PropertyConfig("ListEditor", "错误节点:",
                                       default=self.PROPERTY_DEFAULTS.get("on_error"))
        }

        self.add_properties_to_box(box, configs)

    def create_common_properties(self):
        """创建通用属性"""
        # 通用属性组
        common_box = self.create_box("通用属性")
        common_configs = {
            "is_sub": PropertyConfig("QCheckBox", "是否子节点:",
                                     default=self.PROPERTY_DEFAULTS.get("is_sub")),
            "rate_limit": PropertyConfig("QSpinBox", "识别速率(ms):",
                                         range=(0, 100000),
                                         step=100,
                                         default=self.PROPERTY_DEFAULTS.get("rate_limit")),
            "timeout": PropertyConfig("QSpinBox", "超时时间(ms):",
                                      range=(0, 300000),
                                      step=1000,
                                      default=self.PROPERTY_DEFAULTS.get("timeout")),
            "inverse": PropertyConfig("QCheckBox", "反转识别结果:",
                                      default=self.PROPERTY_DEFAULTS.get("inverse")),
            "enabled": PropertyConfig("QCheckBox", "是否启用:",
                                      default=self.PROPERTY_DEFAULTS.get("enabled"))
        }
        self.add_properties_to_box(common_box, common_configs)

        # 延迟属性组
        delay_box = self.create_box("延迟属性")
        delay_configs = {
            "pre_delay": PropertyConfig("QSpinBox", "动作前延迟(ms):",
                                        range=(0, 10000),
                                        default=self.PROPERTY_DEFAULTS.get("pre_delay")),
            "post_delay": PropertyConfig("QSpinBox", "动作后延迟(ms):",
                                         range=(0, 10000),
                                         default=self.PROPERTY_DEFAULTS.get("post_delay")),
            "pre_wait_freezes": PropertyConfig("QSpinBox", "动作前等待(ms):",
                                               range=(0, 10000),
                                               default=self.PROPERTY_DEFAULTS.get("pre_wait_freezes")),
            "post_wait_freezes": PropertyConfig("QSpinBox", "动作后等待(ms):",
                                                range=(0, 10000),
                                                default=self.PROPERTY_DEFAULTS.get("post_wait_freezes")),
            "focus": PropertyConfig("QCheckBox", "是否关注节点:",
                                    default=self.PROPERTY_DEFAULTS.get("focus"))
        }
        self.add_properties_to_box(delay_box, delay_configs)

    def create_algorithm_properties(self):
        """创建算法属性"""
        # 识别算法属性
        rec_box = self.create_box("识别算法特有属性")
        self.recognition_stack = QStackedWidget()
        rec_box.content_layout.addWidget(self.recognition_stack)

        # 执行动作属性
        action_box = self.create_box("执行动作特有属性")
        self.action_stack = QStackedWidget()
        action_box.content_layout.addWidget(self.action_stack)

    def create_box(self, title: str) -> CollapsibleBox:
        """创建可折叠框"""
        box = CollapsibleBox(title)
        self.boxes[title] = box
        self.scroll_layout.addWidget(box)
        return box

    def add_properties_to_box(self, box: CollapsibleBox, configs: Dict[str, PropertyConfig]):
        """向框中添加属性"""
        for prop_name, config in configs.items():
            widget = self.create_widget(config)
            self.widgets[prop_name] = widget
            box.add_row(config.label, widget)

    def create_widget(self, config: PropertyConfig) -> QWidget:
        """创建widget"""
        widget_type = config.widget_type
        kwargs = config.kwargs

        widget = None

        if widget_type == "QLineEdit":
            widget = QLineEdit()
            widget.setStyleSheet(self.STYLES["input"])
            widget.textChanged.connect(self.on_widget_changed)
            # If default is provided and it's not a boolean True (used for target, begin, end)
            if "default" in kwargs and kwargs["default"] not in (True, None) and not isinstance(kwargs["default"],
                                                                                                bool):
                if isinstance(kwargs["default"], (list, dict)):
                    widget.setText(json.dumps(kwargs["default"]))
                else:
                    widget.setText(str(kwargs["default"]))

        elif widget_type == "QSpinBox":
            widget = QSpinBox()
            widget.setStyleSheet(self.STYLES["input"])
            widget.valueChanged.connect(self.on_widget_changed)
            if "default" in kwargs and kwargs["default"] is not None:
                widget.setValue(kwargs["default"])

        elif widget_type == "QDoubleSpinBox":
            widget = QDoubleSpinBox()
            widget.setStyleSheet(self.STYLES["input"])
            widget.valueChanged.connect(self.on_widget_changed)
            if "default" in kwargs and kwargs["default"] is not None:
                widget.setValue(kwargs["default"])

        elif widget_type == "QComboBox":
            widget = QComboBox()
            widget.setStyleSheet(self.STYLES["input"])
            widget.currentTextChanged.connect(self.on_widget_changed)
            # Set items first, then default
            if "items" in kwargs:
                widget.addItems(kwargs["items"])
            if "default" in kwargs and kwargs["default"] is not None:
                index = widget.findText(str(kwargs["default"]))
                if index >= 0:
                    widget.setCurrentIndex(index)

        elif widget_type == "QCheckBox":
            widget = QCheckBox()
            widget.toggled.connect(self.on_widget_changed)
            if "default" in kwargs:
                widget.setChecked(bool(kwargs["default"]))

        elif widget_type == "ListEditor":
            widget = ListEditor()
            widget.value_changed.connect(self.on_widget_changed)
            if "default" in kwargs and kwargs["default"] is not None:
                widget.set_value(kwargs["default"])

        elif widget_type == "QTextEdit":
            widget = QTextEdit()
            widget.setStyleSheet("""
                QTextEdit {
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    padding: 2px;
                }
                QTextEdit:focus {
                    border: 1px solid #4a86e8;
                }
            """)
            widget.textChanged.connect(self.on_widget_changed)
            if "default" in kwargs and kwargs["default"] is not None:
                if isinstance(kwargs["default"], (list, dict)):
                    widget.setPlainText(json.dumps(kwargs["default"], indent=2))
                else:
                    widget.setPlainText(str(kwargs["default"]))

        # 应用kwargs中的属性
        if widget:
            for key, value in kwargs.items():
                if key == "placeholder" and hasattr(widget, "setPlaceholderText"):
                    widget.setPlaceholderText(value)
                elif key == "range" and hasattr(widget, "setRange"):
                    widget.setRange(*value)
                elif key == "step" and hasattr(widget, "setSingleStep"):
                    widget.setSingleStep(value)
                elif key == "tooltip":
                    widget.setToolTip(value)
                elif key == "max_height" and hasattr(widget, "setMaximumHeight"):
                    widget.setMaximumHeight(value)

        return widget

    def create_button_layout(self) -> QHBoxLayout:
        """创建按钮布局"""
        layout = QHBoxLayout()

        self.auto_save_check = QCheckBox("自动保存")
        self.auto_save_check.toggled.connect(self.toggle_auto_save)

        self.apply_button = QPushButton("应用更改")
        self.apply_button.setStyleSheet(self.STYLES["button"])
        self.apply_button.clicked.connect(self.apply_changes)

        self.reset_button = QPushButton("重置")
        self.reset_button.setStyleSheet(self.STYLES["reset_button"])
        self.reset_button.clicked.connect(self.reset_form)

        layout.addStretch()
        layout.addWidget(self.auto_save_check)
        layout.addWidget(self.apply_button)
        layout.addWidget(self.reset_button)

        return layout

    def setup_properties(self):
        """设置属性定义"""
        # 通用识别属性（除了DirectHit和Custom外的所有识别算法都需要）
        common_recognition = {
            "roi": PropertyConfig("QLineEdit", "识别区域:", placeholder="节点名或坐标 [x,y,w,h]"),
            "roi_offset": PropertyConfig("QLineEdit", "区域偏移:", placeholder="[x,y,w,h]"),
            "order_by": PropertyConfig("QComboBox", "结果排序:",
                                       items=["Horizontal", "Vertical", "Score", "Area", "Random"],
                                       default=self.PROPERTY_DEFAULTS.get("order_by")),
            "index": PropertyConfig("QSpinBox", "结果索引:", range=(-100, 100),
                                    default=self.PROPERTY_DEFAULTS.get("index"))
        }

        # 识别算法属性
        recognition_props = {
            "DirectHit": {},

            "TemplateMatch": {
                "template": PropertyConfig("QLineEdit", "模板图片:", placeholder="模板图片路径，相对于image文件夹"),
                "threshold": PropertyConfig("QDoubleSpinBox", "匹配阈值:", range=(0, 1), step=0.1,
                                            default=self.ALGORITHM_DEFAULTS["TemplateMatch"]["threshold"]),
                "method": PropertyConfig("QSpinBox", "匹配算法:", range=(1, 5),
                                         default=self.PROPERTY_DEFAULTS.get("method"),
                                         tooltip="1、3、5分别对应不同的模板匹配算法"),
                "green_mask": PropertyConfig("QCheckBox", "绿色掩码:",
                                             default=self.PROPERTY_DEFAULTS.get("green_mask"),
                                             tooltip="是否忽略图片中的绿色部分")
            },

            "FeatureMatch": {
                "template": PropertyConfig("QLineEdit", "模板图片:", placeholder="模板图片路径，相对于image文件夹"),
                "count": PropertyConfig("QSpinBox", "特征点数量:", range=(1, 100),
                                        default=self.ALGORITHM_DEFAULTS["FeatureMatch"]["count"]),
                "detector": PropertyConfig("QComboBox", "特征检测器:", items=["SIFT", "KAZE", "AKAZE", "BRISK", "ORB"],
                                           default=self.PROPERTY_DEFAULTS.get("detector")),
                "ratio": PropertyConfig("QDoubleSpinBox", "距离比值:", range=(0, 1), step=0.1,
                                        default=self.PROPERTY_DEFAULTS.get("ratio")),
                "green_mask": PropertyConfig("QCheckBox", "绿色掩码:",
                                             default=self.PROPERTY_DEFAULTS.get("green_mask"))
            },

            "ColorMatch": {
                "lower": PropertyConfig("QLineEdit", "颜色下限:", placeholder="[R,G,B] 或 [[R,G,B],[R,G,B],...]"),
                "upper": PropertyConfig("QLineEdit", "颜色上限:", placeholder="[R,G,B] 或 [[R,G,B],[R,G,B],...]"),
                "method": PropertyConfig("QSpinBox", "匹配算法:", range=(0, 50),
                                         default=self.PROPERTY_DEFAULTS.get("method"),
                                         tooltip="常用：4(RGB), 40(HSV), 6(灰度)"),
                "count": PropertyConfig("QSpinBox", "特征点数量:", range=(1, 10000),
                                        default=self.ALGORITHM_DEFAULTS["ColorMatch"]["count"]),
                "connected": PropertyConfig("QCheckBox", "要求相连:",
                                            default=self.PROPERTY_DEFAULTS.get("connected"))
            },

            "OCR": {
                "expected": PropertyConfig("QLineEdit", "期望文本:", placeholder="期望文本或正则表达式"),
                "threshold": PropertyConfig("QDoubleSpinBox", "匹配阈值:", range=(0, 1), step=0.1,
                                            default=self.ALGORITHM_DEFAULTS["OCR"]["threshold"]),
                "replace": PropertyConfig("QLineEdit", "文本替换:", placeholder='["原文本", "替换文本"]'),
                "only_rec": PropertyConfig("QCheckBox", "仅识别:",
                                           default=self.PROPERTY_DEFAULTS.get("only_rec"),
                                           tooltip="仅识别，不进行文本检测"),
                "model": PropertyConfig("QLineEdit", "模型路径:", placeholder="模型文件夹，相对于model/ocr")
            },

            "NeuralNetworkClassify": {
                "model": PropertyConfig("QLineEdit", "模型路径:", placeholder="模型文件，相对于model/classify"),
                "expected": PropertyConfig("QLineEdit", "期望文本:", placeholder="0 或 [0, 1, 2]"),
                "labels": PropertyConfig("QLineEdit", "标签列表:", placeholder='["猫", "狗", "鼠"]')
            },

            "NeuralNetworkDetect": {
                "model": PropertyConfig("QLineEdit", "模型路径:", placeholder="模型文件，相对于model/detect"),
                "expected": PropertyConfig("QLineEdit", "期望文本:", placeholder="0 或 [0, 1, 2]"),
                "threshold": PropertyConfig("QDoubleSpinBox", "匹配阈值:", range=(0, 1), step=0.1,
                                            default=self.ALGORITHM_DEFAULTS["NeuralNetworkDetect"]["threshold"]),
                "labels": PropertyConfig("QLineEdit", "标签列表:", placeholder='["猫", "狗", "鼠"]')
            },

            "Custom": {
                "custom_recognition": PropertyConfig("QLineEdit", "自定义识别名:",
                                                     placeholder="注册的自定义识别器名称"),
                "custom_recognition_param": PropertyConfig("QTextEdit", "自定义识别参数:",
                                                           max_height=100, placeholder="JSON格式参数")
            }
        }

        # 为识别算法添加通用属性
        for rec_type in recognition_props:
            if rec_type not in ["DirectHit", "Custom"]:
                recognition_props[rec_type] = {**common_recognition, **recognition_props[rec_type]}
            elif rec_type == "Custom":
                # Custom只需要roi和roi_offset
                recognition_props[rec_type].update({
                    "roi": common_recognition["roi"],
                    "roi_offset": common_recognition["roi_offset"]
                })

        # 为每个识别算法创建容器
        for rec_type in self.recognition_types:
            container = QWidget()
            layout = QFormLayout(container)

            props = recognition_props.get(rec_type, {})
            widgets = {}

            if not props:
                info_label = QLabel(f"{rec_type}无需特殊配置")
                info_label.setStyleSheet("color: #666;")
                layout.addRow("", info_label)
            else:
                for prop_name, config in props.items():
                    widget = self.create_widget(config)
                    widgets[prop_name] = widget
                    layout.addRow(config.label, widget)

            self.property_widgets[rec_type] = widgets
            self.recognition_stack.addWidget(container)

        # 动作属性
        action_props = {
            "DoNothing": {},
            "StopTask": {},

            "Click": {
                "target": PropertyConfig("QLineEdit", "点击目标:",
                                         placeholder="节点名或坐标 [x,y,w,h],不填写则为识别目标",
                                         default=self.PROPERTY_DEFAULTS.get("target")),
                "target_offset": PropertyConfig("QLineEdit", "目标偏移:", placeholder="[x,y,w,h]")
            },

            "Swipe": {
                "begin": PropertyConfig("QLineEdit", "起点:", placeholder="节点名或坐标 [x,y,w,h]",
                                        default=self.PROPERTY_DEFAULTS.get("begin")),
                "begin_offset": PropertyConfig("QLineEdit", "起点偏移:", placeholder="[x,y,w,h]"),
                "end": PropertyConfig("QLineEdit", "终点:", placeholder="节点名或坐标 [x,y,w,h]",
                                      default=self.PROPERTY_DEFAULTS.get("end")),
                "end_offset": PropertyConfig("QLineEdit", "终点偏移:", placeholder="[x,y,w,h]"),
                "duration": PropertyConfig("QSpinBox", "持续时间(ms):", range=(50, 5000),
                                           default=self.PROPERTY_DEFAULTS.get("duration"))
            },

            "MultiSwipe": {
                "swipes": PropertyConfig("QTextEdit", "滑动配置:", max_height=120,
                                         placeholder='多指滑动配置，JSON格式')
            },

            "Key": {
                "key": PropertyConfig("QLineEdit", "按键码:", placeholder="25 或 [25, 26, 27]")
            },

            "InputText": {
                "input_text": PropertyConfig("QLineEdit", "输入文本:", placeholder="要输入的文本")
            },

            "StartApp": {
                "package": PropertyConfig("QLineEdit", "应用包名:", placeholder="包名或Activity，如com.example.app")
            },

            "StopApp": {
                "package": PropertyConfig("QLineEdit", "应用包名:", placeholder="包名，如com.example.app")
            },

            "Command": {
                "exec": PropertyConfig("QLineEdit", "执行程序:", placeholder="执行程序路径"),
                "args": PropertyConfig("QTextEdit", "执行参数:", max_height=80,
                                       placeholder='["arg1", "arg2", "{NODE}", "{BOX}"]'),
                "detach": PropertyConfig("QCheckBox", "分离进程:", tooltip="是否分离子进程，不等待完成继续执行",
                                         default=self.PROPERTY_DEFAULTS.get("detach"))
            },

            "Custom": {
                "custom_action": PropertyConfig("QLineEdit", "自定义动作名:", placeholder="注册的自定义动作名称"),
                "custom_action_param": PropertyConfig("QTextEdit", "自定义动作参数:",
                                                      max_height=100, placeholder="JSON格式参数"),
                "target": PropertyConfig("QLineEdit", "点击目标:",
                                         placeholder="节点名或坐标 [x,y,w,h],不填写则为识别目标",
                                         default=self.PROPERTY_DEFAULTS.get("target")),
                "target_offset": PropertyConfig("QLineEdit", "目标偏移:", placeholder="[x,y,w,h]")
            }
        }

        # 为每个动作创建容器
        for action_type in self.action_types:
            container = QWidget()
            layout = QFormLayout(container)

            props = action_props.get(action_type, {})
            widgets = {}

            if not props:
                info_label = QLabel(f"{action_type}无需特殊配置")
                info_label.setStyleSheet("color: #666;")
                layout.addRow("", info_label)
            else:
                for prop_name, config in props.items():
                    widget = self.create_widget(config)
                    widgets[prop_name] = widget
                    layout.addRow(config.label, widget)

            self.property_widgets[action_type] = widgets
            self.action_stack.addWidget(container)

    def connect_signals(self):
        """连接信号"""
        # 识别算法和动作切换
        self.widgets["recognition"].currentTextChanged.connect(self.on_recognition_changed)
        self.widgets["action"].currentTextChanged.connect(self.on_action_changed)

        # JSON标签页
        self.json_apply_button.clicked.connect(self.apply_json_to_node)
        self.json_reset_button.clicked.connect(self.update_json_preview)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

    def set_node(self, node=None):
        """设置要编辑的节点"""
        # Create a new node or make a clean copy of the provided node
        if node is None:
            self.current_node = TaskNode("New Node")
        else:
            # Use JSON serialization to create a clean copy with only the properties
            # that should be in the node, avoiding any retained state
            node_json = node.to_json()
            self.current_node = TaskNode.from_json(node_json)

        # Reset all widgets to default values first
        self.reset_all_widgets()

        # Then update the UI from the clean node
        self.update_ui_from_node()

    def reset_all_widgets(self):
        """重置所有小部件到默认状态"""
        self.is_updating_ui = True
        try:
            # Reset basic widgets
            for prop_name, widget in self.widgets.items():
                default_value = self.PROPERTY_DEFAULTS.get(prop_name)
                self.set_widget_value(widget, default_value)

            # Reset all algorithm-specific widgets
            for algo_type, widgets in self.property_widgets.items():
                for prop_name, widget in widgets.items():
                    # Get algorithm-specific default if available
                    if algo_type in self.ALGORITHM_DEFAULTS and prop_name in self.ALGORITHM_DEFAULTS[algo_type]:
                        default_value = self.ALGORITHM_DEFAULTS[algo_type][prop_name]
                    else:
                        default_value = self.PROPERTY_DEFAULTS.get(prop_name)
                    self.set_widget_value(widget, default_value)
        finally:
            self.is_updating_ui = False

    def update_ui_from_node(self):
        """从节点更新UI"""
        if not self.current_node:
            return

        self.is_updating_ui = True
        try:
            # 更新基本属性
            if hasattr(self.current_node, "name"):
                self.widgets["name"].setText(self.current_node.name)

            # 更新其他属性
            for prop_name, widget in self.widgets.items():
                value = self.get_node_value(prop_name)
                self.set_widget_value(widget, value)

            # 更新算法特定属性
            self.update_algorithm_properties()

            # 更新预览
            self.update_preview_images()

            self.update_json_preview()

        finally:
            self.is_updating_ui = False

    def update_algorithm_properties(self):
        """更新算法特定属性"""
        rec_type = self.get_node_value("recognition")
        if rec_type in self.recognition_types:
            index = self.recognition_types.index(rec_type)
            self.recognition_stack.setCurrentIndex(index)

            # 更新该算法的属性
            widgets = self.property_widgets.get(rec_type, {})
            for prop_name, widget in widgets.items():
                value = self.get_node_value(prop_name)
                # 检查是否应该使用算法特定的默认值
                if value is None and rec_type in self.ALGORITHM_DEFAULTS and prop_name in self.ALGORITHM_DEFAULTS[
                    rec_type]:
                    value = self.ALGORITHM_DEFAULTS[rec_type][prop_name]
                self.set_widget_value(widget, value)

        action_type = self.get_node_value("action")
        if action_type in self.action_types:
            index = self.action_types.index(action_type)
            self.action_stack.setCurrentIndex(index)

            # 更新该动作的属性
            widgets = self.property_widgets.get(action_type, {})
            for prop_name, widget in widgets.items():
                value = self.get_node_value(prop_name)
                self.set_widget_value(widget, value)

    def get_node_value(self, prop_name: str) -> Any:
        """获取节点属性值"""
        if not self.current_node:
            return self.PROPERTY_DEFAULTS.get(prop_name)

        value = getattr(self.current_node, prop_name, None)

        # 如果属性值为None，返回默认值
        if value is None:
            return self.PROPERTY_DEFAULTS.get(prop_name)

        return value

    def get_property_default(self, prop_name: str, rec_type: str = None) -> Any:
        """获取属性的默认值，考虑识别算法特定的默认值"""
        if rec_type and rec_type in self.ALGORITHM_DEFAULTS and prop_name in self.ALGORITHM_DEFAULTS[rec_type]:
            return self.ALGORITHM_DEFAULTS[rec_type][prop_name]
        return self.PROPERTY_DEFAULTS.get(prop_name)

    def set_widget_value(self, widget: QWidget, value: Any):
        """设置widget值"""
        if isinstance(widget, QLineEdit):
            if isinstance(value, (list, dict)):
                widget.setText(json.dumps(value, ensure_ascii=False))
            elif value is True:
                # 对于target, begin, end等特殊值，True表示使用默认值
                widget.clear()
            else:
                widget.setText(str(value) if value is not None else "")

        elif isinstance(widget, QTextEdit):
            if isinstance(value, (list, dict)):
                widget.setPlainText(json.dumps(value, indent=2, ensure_ascii=False))
            else:
                widget.setPlainText(str(value) if value is not None else "")

        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            if value is not None:
                widget.setValue(value)

        elif isinstance(widget, QComboBox):
            if value:
                index = widget.findText(str(value))
                if index >= 0:
                    widget.setCurrentIndex(index)

        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))

        elif isinstance(widget, ListEditor):
            widget.set_value(value or [])

    def on_widget_changed(self):
        """处理widget变化"""
        if self.is_updating_ui:
            return

        if self.auto_save:
            QTimer.singleShot(300, self.apply_changes_silent)

    def on_recognition_changed(self, rec_type):
        """处理识别算法变化"""
        if rec_type in self.recognition_types:
            index = self.recognition_types.index(rec_type)
            self.recognition_stack.setCurrentIndex(index)
            self.boxes["识别算法特有属性"].set_expanded(rec_type != "DirectHit")

            # 更新阈值等属性的默认值
            widgets = self.property_widgets.get(rec_type, {})
            for prop_name, widget in widgets.items():
                # 只更新未被用户修改过的属性值（即节点中不存在的属性）
                if not hasattr(self.current_node, prop_name) and rec_type in self.ALGORITHM_DEFAULTS and prop_name in \
                        self.ALGORITHM_DEFAULTS[rec_type]:
                    default_value = self.ALGORITHM_DEFAULTS[rec_type][prop_name]
                    self.set_widget_value(widget, default_value)

    def on_action_changed(self, action_type):
        """处理动作类型变化"""
        if action_type in self.action_types:
            index = self.action_types.index(action_type)
            self.action_stack.setCurrentIndex(index)
            self.boxes["执行动作特有属性"].set_expanded(action_type not in ["DoNothing", "StopTask"])

    def apply_changes(self, show_message=True):
        """应用更改"""
        if not self.current_node:
            return

        # 更新所有属性
        for prop_name, widget in self.widgets.items():
            if prop_name == "name":
                self.current_node.name = widget.text()
            else:
                value = self.get_widget_value(widget)
                self.save_node_property(prop_name, value)

        # 更新算法特定属性
        self.save_algorithm_properties()

        self.node_changed.emit(self.current_node)

        if show_message and not self.auto_save:
            QMessageBox.information(self, "提示", "节点属性已更新")

    def apply_changes_silent(self):
        """静默应用更改"""
        self.apply_changes(show_message=False)

    def save_algorithm_properties(self):
        """保存算法特定属性"""
        # 保存识别算法属性
        rec_type = self.get_node_value("recognition")
        widgets = self.property_widgets.get(rec_type, {})
        for prop_name, widget in widgets.items():
            value = self.get_widget_value(widget)
            # 如果属性值与算法特定的默认值相同，就不保存
            if rec_type in self.ALGORITHM_DEFAULTS and prop_name in self.ALGORITHM_DEFAULTS[rec_type]:
                if value == self.ALGORITHM_DEFAULTS[rec_type][prop_name]:
                    # 如果属性值已经存在但等于默认值，则删除该属性
                    if hasattr(self.current_node, prop_name):
                        delattr(self.current_node, prop_name)
                    continue
            self.save_node_property(prop_name, value)

        # 保存动作属性
        action_type = self.get_node_value("action")
        widgets = self.property_widgets.get(action_type, {})
        for prop_name, widget in widgets.items():
            value = self.get_widget_value(widget)
            self.save_node_property(prop_name, value)

    def get_widget_value(self, widget: QWidget) -> Any:
        """获取widget的值"""
        if isinstance(widget, QLineEdit):
            text = widget.text().strip()
            if text:
                # 处理特殊值(target, begin, end)
                if text in ["target", "begin", "end"] and not text.startswith("["):
                    return True

                try:
                    if text.startswith(("[", "{")):
                        return json.loads(text)
                    # 尝试解析为整数
                    return int(text)
                except:
                    return text

        elif isinstance(widget, QTextEdit):
            text = widget.toPlainText().strip()
            if text:
                try:
                    return json.loads(text)
                except:
                    return text  # 如果JSON解析失败，返回原始文本而不是None

        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            return widget.value()

        elif isinstance(widget, QComboBox):
            return widget.currentText()

        elif isinstance(widget, QCheckBox):
            return widget.isChecked()

        elif isinstance(widget, ListEditor):
            return widget.get_value()

        return None

    def save_node_property(self, prop_name: str, value: Any):
        """保存属性到节点"""
        if not self.current_node:
            return

        # 获取该属性的默认值（考虑算法特定默认值）
        rec_type = getattr(self.current_node, "recognition", self.PROPERTY_DEFAULTS["recognition"])
        default = self.get_property_default(prop_name, rec_type)

        if value == default:
            if hasattr(self.current_node, prop_name):
                delattr(self.current_node, prop_name)
        else:
            setattr(self.current_node, prop_name, value)

    def reset_form(self):
        """重置表单"""
        if self.current_node:
            self.update_ui_from_node()
            QMessageBox.information(self, "提示", "表单已重置")

    def on_tab_changed(self, index):
        """标签页切换"""
        if index == 1:  # JSON标签页
            self.update_json_preview()

    def update_json_preview(self):
        """更新JSON预览"""
        if not self.current_node:
            return

        try:
            # 生成JSON时使用ensure_ascii=False以正确显示中文字符
            json_text = self.current_node.to_json(indent=4)
            self.json_editor.setPlainText(json_text)
            self.json_error_banner.hide()
        except Exception as e:
            self.json_error_banner.setText(f"更新预览失败: {str(e)}")
            self.json_error_banner.show()

    def apply_json_to_node(self):
        """应用JSON到节点"""
        if not self.current_node:
            return

        try:
            json_text = self.json_editor.toPlainText()
            new_node = TaskNode.from_json(json_text)

            # 复制属性
            self.current_node.__dict__.clear()
            self.current_node.__dict__.update(new_node.__dict__)

            self.update_ui_from_node()
            self.json_error_banner.hide()
            self.node_changed.emit(self.current_node)

        except Exception as e:
            self.json_error_banner.setText(f"应用失败: {str(e)}")
            self.json_error_banner.show()

    def update_preview_images(self):
        """更新预览图像"""
        # 简化的预览更新逻辑
        if not hasattr(self.current_node, 'template') or not self.current_node.template:
            return

        templates = self.current_node.template if isinstance(self.current_node.template, list) else [
            self.current_node.template]

        for template_path in templates:
            if template_path:
                self.add_template_to_preview(template_path)

    def add_template_to_preview(self, template_path):
        """添加模板到预览"""
        # 简化的预览添加逻辑
        pass

    def toggle_auto_save(self, checked):
        """切换自动保存"""
        self.auto_save = checked
        self.apply_button.setEnabled(not checked)

        if checked:
            self.apply_changes_silent()