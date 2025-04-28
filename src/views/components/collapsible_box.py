from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QToolButton, QLabel, QFormLayout


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
