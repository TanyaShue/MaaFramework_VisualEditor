from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget


class NodeLibrary(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        # 创建标题标签
        title_label = QLabel("节点库")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        # 创建节点模板列表
        self.template_list = QListWidget()

        # 添加一些示例节点模板
        self.template_list.addItem("识别节点")
        self.template_list.addItem("点击节点")
        self.template_list.addItem("滑动节点")
        self.template_list.addItem("等待节点")
        self.template_list.addItem("条件节点")

        # 创建提示标签
        info_label = QLabel("拖拽节点到画布")

        # 添加到主布局
        layout.addWidget(title_label)
        layout.addWidget(self.template_list)
        layout.addWidget(info_label)

        # 节点模板列表
        self.templates = []

    def add_template(self, template):
        pass

    def get_templates(self):
        pass

    def create_node_from_template(self, template_id):
        pass