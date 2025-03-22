from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFormLayout,
                               QLineEdit, QSpinBox, QPushButton, QCheckBox,
                               QComboBox, QTextEdit, QDoubleSpinBox, QHBoxLayout,
                               QScrollArea, QGroupBox, QFrame, QMessageBox)
from typing import Dict, List, Union, Optional, Any


class ListEditor(QWidget):
    """列表属性编辑器组件"""

    value_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # 列表项显示区域
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("每行输入一个值")

        # 按钮区域
        button_layout = QHBoxLayout()
        self.add_btn = QPushButton("添加项")
        self.clear_btn = QPushButton("清空")
        button_layout.addWidget(self.add_btn)
        button_layout.addWidget(self.clear_btn)

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
    """节点属性编辑器"""

    node_changed = Signal(object)  # 当节点被修改时发送信号

    def __init__(self, parent=None):
        super().__init__(parent)

        self.init_ui()

        # 属性控件字典，键为属性名，值为控件
        self.property_widgets = {}
        self.algo_property_widgets = {}

        # 当前节点
        self.current_node = None

        # 连接信号
        self.apply_button.clicked.connect(self.apply_changes)
        self.reset_button.clicked.connect(self.reset_form)

        # 识别算法和动作类型选项
        self.recognition_types = [
            "DirectHit", "TemplateMatch", "FeatureMatch", "ColorMatch",
            "OCR", "NeuralNetworkClassify", "NeuralNetworkDetect", "Custom"
        ]

        self.action_types = [
            "DoNothing", "Click", "Swipe", "MultiSwipe", "Key",
            "InputText", "StartApp", "StopApp", "StopTask", "Command", "Custom"
        ]

    def init_ui(self):
        """初始化UI界面"""
        main_layout = QVBoxLayout(self)

        # 创建标题标签
        title_label = QLabel("节点属性编辑器")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)

        scroll_layout = QVBoxLayout(scroll_widget)

        # 创建基本属性组
        basic_group = QGroupBox("基本属性")
        self.form_layout = QFormLayout(basic_group)

        self.node_name_input = QLineEdit()
        self.node_name_input.setReadOnly(True)  # 名称不可编辑

        self.recognition_combo = QComboBox()
        self.action_combo = QComboBox()

        self.form_layout.addRow("节点名称:", self.node_name_input)
        self.form_layout.addRow("识别算法:", self.recognition_combo)
        self.form_layout.addRow("执行动作:", self.action_combo)

        # 创建流控制属性组
        flow_group = QGroupBox("流程控制")
        flow_layout = QFormLayout(flow_group)

        self.next_editor = ListEditor()
        self.interrupt_editor = ListEditor()
        self.on_error_editor = ListEditor()
        self.timeout_next_editor = ListEditor()

        flow_layout.addRow("后继节点:", self.next_editor)
        flow_layout.addRow("中断节点:", self.interrupt_editor)
        flow_layout.addRow("错误节点:", self.on_error_editor)
        flow_layout.addRow("超时节点:", self.timeout_next_editor)

        # 创建通用属性组
        common_group = QGroupBox("通用属性")
        common_layout = QFormLayout(common_group)

        self.is_sub_check = QCheckBox()
        self.rate_limit_spin = QSpinBox()
        self.rate_limit_spin.setRange(0, 100000)
        self.rate_limit_spin.setSingleStep(100)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(0, 300000)
        self.timeout_spin.setSingleStep(1000)

        self.inverse_check = QCheckBox()
        self.enabled_check = QCheckBox()
        self.pre_delay_spin = QSpinBox()
        self.pre_delay_spin.setRange(0, 10000)

        self.post_delay_spin = QSpinBox()
        self.post_delay_spin.setRange(0, 10000)

        self.pre_wait_freezes_spin = QSpinBox()
        self.pre_wait_freezes_spin.setRange(0, 10000)

        self.post_wait_freezes_spin = QSpinBox()
        self.post_wait_freezes_spin.setRange(0, 10000)

        self.focus_check = QCheckBox()

        common_layout.addRow("是否子节点:", self.is_sub_check)
        common_layout.addRow("识别速率(ms):", self.rate_limit_spin)
        common_layout.addRow("超时时间(ms):", self.timeout_spin)
        common_layout.addRow("反转识别结果:", self.inverse_check)
        common_layout.addRow("是否启用:", self.enabled_check)
        common_layout.addRow("动作前延迟(ms):", self.pre_delay_spin)
        common_layout.addRow("动作后延迟(ms):", self.post_delay_spin)
        common_layout.addRow("动作前等待(ms):", self.pre_wait_freezes_spin)
        common_layout.addRow("动作后等待(ms):", self.post_wait_freezes_spin)
        common_layout.addRow("是否关注节点:", self.focus_check)

        # 创建算法特有属性组
        self.algo_group = QGroupBox("算法特有属性")
        self.algo_layout = QFormLayout(self.algo_group)

        # 按钮区域
        button_layout = QHBoxLayout()
        self.apply_button = QPushButton("应用更改")
        self.reset_button = QPushButton("重置")
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.reset_button)

        # 添加所有组件到主布局
        scroll_layout.addWidget(basic_group)
        scroll_layout.addWidget(flow_group)
        scroll_layout.addWidget(common_group)
        scroll_layout.addWidget(self.algo_group)
        scroll_layout.addStretch()

        main_layout.addWidget(title_label)
        main_layout.addWidget(scroll_area)
        main_layout.addLayout(button_layout)

        # 保存基本属性控件的引用
        self.property_widgets = {
            "name": self.node_name_input,
            "recognition": self.recognition_combo,
            "action": self.action_combo,
            "next": self.next_editor,
            "interrupt": self.interrupt_editor,
            "on_error": self.on_error_editor,
            "timeout_next": self.timeout_next_editor,
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

    def setup_recognition_action_combos(self):
        """设置识别算法和动作类型下拉框"""
        self.recognition_combo.clear()
        self.action_combo.clear()

        self.recognition_combo.addItems(self.recognition_types)
        self.action_combo.addItems(self.action_types)

        # 连接信号
        self.recognition_combo.currentTextChanged.connect(self.on_recognition_changed)
        self.action_combo.currentTextChanged.connect(self.on_action_changed)

    def on_recognition_changed(self, recognition_type):
        """当识别算法类型改变时更新特有属性"""
        if self.current_node:
            self.clear_algo_properties()
            self.setup_algo_properties(recognition_type)

    def on_action_changed(self, action_type):
        """当动作类型改变时更新特有属性"""
        if self.current_node:
            self.clear_algo_properties()
            self.setup_algo_properties(self.recognition_combo.currentText(), action_type)

    def clear_algo_properties(self):
        """清除算法特有属性控件"""
        # 清除布局中的所有控件
        while self.algo_layout.count():
            item = self.algo_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.algo_property_widgets.clear()

    def setup_algo_properties(self, recognition_type, action_type=None):
        """根据识别算法和动作类型设置特有属性控件"""
        # 清除旧的属性控件
        self.clear_algo_properties()

        if recognition_type == "TemplateMatch":
            # 为TemplateMatch添加特有属性
            self.add_roi_controls()

            template_edit = QLineEdit()
            threshold_spin = QDoubleSpinBox()
            threshold_spin.setRange(0, 1)
            threshold_spin.setSingleStep(0.1)
            threshold_spin.setValue(0.7)

            order_combo = QComboBox()
            order_combo.addItems(["Horizontal", "Vertical", "Score", "Random"])

            index_spin = QSpinBox()
            index_spin.setRange(-100, 100)

            method_spin = QSpinBox()
            method_spin.setRange(1, 5)
            method_spin.setValue(5)

            green_mask_check = QCheckBox()

            self.algo_layout.addRow("模板图片:", template_edit)
            self.algo_layout.addRow("匹配阈值:", threshold_spin)
            self.algo_layout.addRow("结果排序:", order_combo)
            self.algo_layout.addRow("结果索引:", index_spin)
            self.algo_layout.addRow("匹配算法:", method_spin)
            self.algo_layout.addRow("绿色掩码:", green_mask_check)

            self.algo_property_widgets.update({
                "template": template_edit,
                "threshold": threshold_spin,
                "order_by": order_combo,
                "index": index_spin,
                "method": method_spin,
                "green_mask": green_mask_check
            })

        elif recognition_type == "FeatureMatch":
            # 为FeatureMatch添加特有属性
            self.add_roi_controls()

            template_edit = QLineEdit()
            count_spin = QSpinBox()
            count_spin.setRange(1, 100)
            count_spin.setValue(4)

            order_combo = QComboBox()
            order_combo.addItems(["Horizontal", "Vertical", "Score", "Area", "Random"])

            index_spin = QSpinBox()
            index_spin.setRange(-100, 100)

            detector_combo = QComboBox()
            detector_combo.addItems(["SIFT", "KAZE", "AKAZE", "BRISK", "ORB"])

            ratio_spin = QDoubleSpinBox()
            ratio_spin.setRange(0, 1)
            ratio_spin.setSingleStep(0.1)
            ratio_spin.setValue(0.6)

            green_mask_check = QCheckBox()

            self.algo_layout.addRow("模板图片:", template_edit)
            self.algo_layout.addRow("特征点数量:", count_spin)
            self.algo_layout.addRow("结果排序:", order_combo)
            self.algo_layout.addRow("结果索引:", index_spin)
            self.algo_layout.addRow("特征检测器:", detector_combo)
            self.algo_layout.addRow("距离比值:", ratio_spin)
            self.algo_layout.addRow("绿色掩码:", green_mask_check)

            self.algo_property_widgets.update({
                "template": template_edit,
                "count": count_spin,
                "order_by": order_combo,
                "index": index_spin,
                "detector": detector_combo,
                "ratio": ratio_spin,
                "green_mask": green_mask_check
            })

        elif recognition_type == "ColorMatch":
            # 为ColorMatch添加特有属性
            self.add_roi_controls()
            # 更多ColorMatch特有属性...

        elif recognition_type == "OCR":
            # 为OCR添加特有属性
            self.add_roi_controls()

            expected_edit = QLineEdit()
            threshold_spin = QDoubleSpinBox()
            threshold_spin.setRange(0, 1)
            threshold_spin.setSingleStep(0.1)
            threshold_spin.setValue(0.3)

            order_combo = QComboBox()
            order_combo.addItems(["Horizontal", "Vertical", "Area", "Length", "Random"])

            index_spin = QSpinBox()
            index_spin.setRange(-100, 100)

            only_rec_check = QCheckBox()
            model_edit = QLineEdit()

            self.algo_layout.addRow("期望文本:", expected_edit)
            self.algo_layout.addRow("置信度阈值:", threshold_spin)
            self.algo_layout.addRow("结果排序:", order_combo)
            self.algo_layout.addRow("结果索引:", index_spin)
            self.algo_layout.addRow("仅识别:", only_rec_check)
            self.algo_layout.addRow("模型路径:", model_edit)

            self.algo_property_widgets.update({
                "expected": expected_edit,
                "threshold": threshold_spin,
                "order_by": order_combo,
                "index": index_spin,
                "only_rec": only_rec_check,
                "model": model_edit
            })

        elif recognition_type == "Custom":
            # 为Custom添加特有属性
            custom_name_edit = QLineEdit()
            custom_param_edit = QTextEdit()
            custom_param_edit.setPlaceholderText("JSON格式参数")

            self.algo_layout.addRow("自定义识别名:", custom_name_edit)
            self.algo_layout.addRow("自定义参数:", custom_param_edit)

            self.algo_property_widgets.update({
                "custom_recognition": custom_name_edit,
                "custom_recognition_param": custom_param_edit
            })

        # 添加动作特有属性
        if action_type == "Click":
            target_combo = QComboBox()
            target_combo.addItems(["自身", "其他节点", "固定坐标"])
            target_edit = QLineEdit()
            target_edit.setPlaceholderText("节点名或坐标 [x,y,w,h]")

            self.algo_layout.addRow("点击目标类型:", target_combo)
            self.algo_layout.addRow("点击目标:", target_edit)

            self.algo_property_widgets.update({
                "target_type": target_combo,
                "target": target_edit
            })

        elif action_type == "Swipe":
            # 为Swipe添加特有属性
            begin_combo = QComboBox()
            begin_combo.addItems(["自身", "其他节点", "固定坐标"])
            begin_edit = QLineEdit()

            end_combo = QComboBox()
            end_combo.addItems(["自身", "其他节点", "固定坐标"])
            end_edit = QLineEdit()

            duration_spin = QSpinBox()
            duration_spin.setRange(50, 5000)
            duration_spin.setValue(200)

            self.algo_layout.addRow("起点类型:", begin_combo)
            self.algo_layout.addRow("起点:", begin_edit)
            self.algo_layout.addRow("终点类型:", end_combo)
            self.algo_layout.addRow("终点:", end_edit)
            self.algo_layout.addRow("持续时间(ms):", duration_spin)

            self.algo_property_widgets.update({
                "begin_type": begin_combo,
                "begin": begin_edit,
                "end_type": end_combo,
                "end": end_edit,
                "duration": duration_spin
            })

    def add_roi_controls(self):
        """添加ROI相关控件"""
        roi_combo = QComboBox()
        roi_combo.addItems(["全屏", "其他节点", "固定坐标"])

        roi_edit = QLineEdit()
        roi_edit.setPlaceholderText("节点名或坐标 [x,y,w,h]")

        roi_offset_edit = QLineEdit()
        roi_offset_edit.setPlaceholderText("[x,y,w,h]")
        roi_offset_edit.setText("[0,0,0,0]")

        self.algo_layout.addRow("识别区域类型:", roi_combo)
        self.algo_layout.addRow("识别区域:", roi_edit)
        self.algo_layout.addRow("区域偏移:", roi_offset_edit)

        self.algo_property_widgets.update({
            "roi_type": roi_combo,
            "roi": roi_edit,
            "roi_offset": roi_offset_edit
        })

    def display_node_properties(self, node):
        """显示节点的属性"""
        if not node:
            return

        self.current_node = node

        # 设置基本属性
        self.node_name_input.setText(node.name)

        # 设置下拉框选项
        self.setup_recognition_action_combos()

        # 设置识别算法和动作类型
        recognition_index = self.recognition_combo.findText(node.recognition)
        if recognition_index >= 0:
            self.recognition_combo.setCurrentIndex(recognition_index)

        action_index = self.action_combo.findText(node.action)
        if action_index >= 0:
            self.action_combo.setCurrentIndex(action_index)

        # 设置流程控制属性
        self.next_editor.set_value(node.next)
        self.interrupt_editor.set_value(node.interrupt)
        self.on_error_editor.set_value(node.on_error)
        self.timeout_next_editor.set_value(node.timeout_next)

        # 设置通用属性
        self.is_sub_check.setChecked(node.is_sub)
        self.rate_limit_spin.setValue(node.rate_limit)
        self.timeout_spin.setValue(node.timeout)
        self.inverse_check.setChecked(node.inverse)
        self.enabled_check.setChecked(node.enabled)
        self.pre_delay_spin.setValue(node.pre_delay)
        self.post_delay_spin.setValue(node.post_delay)
        self.pre_wait_freezes_spin.setValue(node.pre_wait_freezes)
        self.post_wait_freezes_spin.setValue(node.post_wait_freezes)
        self.focus_check.setChecked(node.focus)

        # 设置算法特有属性
        self.setup_algo_properties(node.recognition, node.action)

        # 填充算法特有属性值
        for key, widget in self.algo_property_widgets.items():
            # 处理特殊情况
            if key == "roi_type":
                roi = node.get_algorithm_property("roi", [0, 0, 0, 0])
                if isinstance(roi, list) and len(roi) == 4:
                    if roi == [0, 0, 0, 0]:
                        widget.setCurrentText("全屏")
                    else:
                        widget.setCurrentText("固定坐标")
                elif isinstance(roi, str):
                    widget.setCurrentText("其他节点")
            elif key == "roi":
                roi = node.get_algorithm_property("roi", [0, 0, 0, 0])
                if isinstance(roi, list):
                    widget.setText(str(roi))
                elif isinstance(roi, str):
                    widget.setText(roi)
            elif key == "target_type":
                target = node.get_algorithm_property("target", True)
                if target is True:
                    widget.setCurrentText("自身")
                elif isinstance(target, str):
                    widget.setCurrentText("其他节点")
                elif isinstance(target, list):
                    widget.setCurrentText("固定坐标")
            elif key == "target":
                target = node.get_algorithm_property("target", True)
                if isinstance(target, str) or isinstance(target, list):
                    widget.setText(str(target))
            elif key == "begin_type" or key == "end_type":
                # 处理滑动起点/终点类型
                point_key = key.replace("_type", "")
                point = node.get_algorithm_property(point_key, True)
                if point is True:
                    widget.setCurrentText("自身")
                elif isinstance(point, str):
                    widget.setCurrentText("其他节点")
                elif isinstance(point, list):
                    widget.setCurrentText("固定坐标")
            elif key == "begin" or key == "end":
                point = node.get_algorithm_property(key, True)
                if isinstance(point, str) or isinstance(point, list):
                    widget.setText(str(point))
            else:
                # 处理一般属性
                value = node.get_algorithm_property(key)
                if value is not None:
                    if isinstance(widget, QLineEdit):
                        widget.setText(str(value))
                    elif isinstance(widget, QTextEdit):
                        widget.setText(str(value))
                    elif isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
                        widget.setValue(value)
                    elif isinstance(widget, QCheckBox):
                        widget.setChecked(value)
                    elif isinstance(widget, QComboBox):
                        index = widget.findText(value)
                        if index >= 0:
                            widget.setCurrentIndex(index)

    def update_property(self, name, value):
        """更新节点属性"""
        if self.current_node:
            if hasattr(self.current_node, name):
                setattr(self.current_node, name, value)
            else:
                # 更新算法特有属性
                self.current_node.add_algorithm_property(name, value)

    def apply_changes(self):
        """应用所有更改到当前节点"""
        if not self.current_node:
            return

        # 更新基本属性
        self.current_node.recognition = self.recognition_combo.currentText()
        self.current_node.action = self.action_combo.currentText()

        # 更新流程控制属性
        self.current_node.next = self.next_editor.get_value()
        self.current_node.interrupt = self.interrupt_editor.get_value()
        self.current_node.on_error = self.on_error_editor.get_value()
        self.current_node.timeout_next = self.timeout_next_editor.get_value()

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
        for key, widget in self.algo_property_widgets.items():
            # 处理特殊情况
            if key == "roi_type":
                continue  # 这是UI控件类型，不是实际属性
            elif key == "target_type":
                continue  # 这是UI控件类型，不是实际属性
            elif key == "begin_type" or key == "end_type":
                continue  # 这是UI控件类型，不是实际属性
            elif key == "roi":
                roi_type = self.algo_property_widgets.get("roi_type")
                if roi_type:
                    type_text = roi_type.currentText()
                    if type_text == "全屏":
                        self.current_node.add_algorithm_property("roi", [0, 0, 0, 0])
                    elif type_text == "其他节点":
                        self.current_node.add_algorithm_property("roi", widget.text())
                    elif type_text == "固定坐标":
                        try:
                            # 尝试解析坐标
                            roi_str = widget.text().strip("[]").split(",")
                            roi = [int(x.strip()) for x in roi_str]
                            if len(roi) == 4:
                                self.current_node.add_algorithm_property("roi", roi)
                        except:
                            QMessageBox.warning(self, "输入错误", "ROI坐标格式不正确")
            elif key == "target":
                target_type = self.algo_property_widgets.get("target_type")
                if target_type:
                    type_text = target_type.currentText()
                    if type_text == "自身":
                        self.current_node.add_algorithm_property("target", True)
                    elif type_text == "其他节点":
                        self.current_node.add_algorithm_property("target", widget.text())
                    elif type_text == "固定坐标":
                        try:
                            # 尝试解析坐标
                            target_str = widget.text().strip("[]").split(",")
                            target = [int(x.strip()) for x in target_str]
                            if len(target) == 4:
                                self.current_node.add_algorithm_property("target", target)
                        except:
                            QMessageBox.warning(self, "输入错误", "目标坐标格式不正确")
            elif key == "begin" or key == "end":
                type_key = f"{key}_type"
                type_widget = self.algo_property_widgets.get(type_key)
                if type_widget:
                    type_text = type_widget.currentText()
                    if type_text == "自身":
                        self.current_node.add_algorithm_property(key, True)
                    elif type_text == "其他节点":
                        self.current_node.add_algorithm_property(key, widget.text())
                    elif type_text == "固定坐标":
                        try:
                            # 尝试解析坐标
                            pos_str = widget.text().strip("[]").split(",")
                            pos = [int(x.strip()) for x in pos_str]
                            if len(pos) == 4:
                                self.current_node.add_algorithm_property(key, pos)
                        except:
                            QMessageBox.warning(self, "输入错误", f"{key}坐标格式不正确")
            else:
                # 处理一般属性
                if isinstance(widget, QLineEdit):
                    self.current_node.add_algorithm_property(key, widget.text())
                elif isinstance(widget, QTextEdit):
                    self.current_node.add_algorithm_property(key, widget.toPlainText())
                elif isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
                    self.current_node.add_algorithm_property(key, widget.value())
                elif isinstance(widget, QCheckBox):
                    self.current_node.add_algorithm_property(key, widget.isChecked())
                elif isinstance(widget, QComboBox):
                    self.current_node.add_algorithm_property(key, widget.currentText())

        # 发送节点已更改信号
        self.node_changed.emit(self.current_node)
        QMessageBox.information(self, "提示", "节点属性已更新")

    def reset_form(self):
        """重置表单到当前节点的原始状态"""
        if self.current_node:
            self.display_node_properties(self.current_node)