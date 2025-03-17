from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFormLayout, QLineEdit, QSpinBox, QPushButton


class NodePropertiesEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        # 创建标题标签
        title_label = QLabel("节点属性编辑器")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        # 创建节点属性表单
        self.form_layout = QFormLayout()
        self.node_id_input = QLineEdit()
        self.node_title_input = QLineEdit()

        self.form_layout.addRow("节点ID:", self.node_id_input)
        self.form_layout.addRow("节点标题:", self.node_title_input)

        # 创建按钮
        apply_button = QPushButton("应用更改")
        reset_button = QPushButton("重置")

        # 创建提示标签
        info_label = QLabel("选择节点以编辑其属性")
        info_label.setAlignment(Qt.AlignCenter)

        # 添加到主布局
        layout.addWidget(title_label)
        layout.addLayout(self.form_layout)
        layout.addWidget(apply_button)
        layout.addWidget(reset_button)
        layout.addWidget(info_label)
        layout.addStretch()

        # 当前节点
        self.current_node = None

    def display_node_properties(self, node):
        pass

    def update_property(self, name, value):
        pass

    def apply_changes(self):
        pass