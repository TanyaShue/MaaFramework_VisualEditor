from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QTextEdit, QHBoxLayout)


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
