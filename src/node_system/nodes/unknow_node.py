import hashlib

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QFont, QColor, QPen, QBrush, QPainterPath, QPixmap

from src.node_system.node import Node


class UnknownNode(Node):
    """
    特殊的节点类，用于表示未知节点类型。
    显示一个固定的叉叉图像，表示节点无法识别或加载。
    重要特性：未知节点只有输入端口，没有输出端口，无法连接到其他节点。
    """
    # 类级别的静态图像，所有实例共享
    _recognition_image = None

    @classmethod
    def _create_unknown_image(cls):
        """创建一个带有叉叉的图像表示未知节点（类方法）"""
        if cls._recognition_image is None:
            # 创建一个空白图像
            cls._recognition_image = QPixmap(120, 120)
            cls._recognition_image.fill(Qt.transparent)

            # 创建绘制器
            painter = QPainter(cls._recognition_image)
            painter.setRenderHint(QPainter.Antialiasing)

            # 绘制背景区域（浅灰色半透明圆形）
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(200, 200, 200, 160))
            painter.drawEllipse(10, 10, 100, 100)

            # 绘制红色叉叉
            pen = QPen(QColor(220, 50, 50), 8)  # 使用红色粗线
            painter.setPen(pen)
            painter.drawLine(30, 30, 90, 90)
            painter.drawLine(90, 30, 30, 90)

            # 结束绘制
            painter.end()

        return cls._recognition_image

    def __init__(self, title="Unknown Node", task_node=None, parent=None):
        # 调用父类初始化方法
        super().__init__( title=title, task_node=task_node, parent=parent)

        # 未知节点总是显示特定图像，所以标记为有模板
        self.has_template = True

        # 使用类级别的共享图像
        self.recognition_image = self._create_unknown_image()

        # 同时设置默认图像为叉叉图像
        self.default_image = self.recognition_image

        # 设置视觉属性
        self.bounds = QRectF(0, 0, 240, 180)  # 使节点稍小一些
        self.original_height = self.bounds.height()

        # 更新端口位置
        self._update_port_positions()

    def _initialize_output_ports(self):
        """
        重写父类的输出端口初始化方法
        未知节点没有输出端口
        """
        # 创建一个空字典，不添加任何输出端口
        self.output_ports = {}
        # 不调用父类方法，因为我们不需要创建任何输出端口

    def _get_node_colors(self):
        """重写获取节点颜色方法，使未知节点有独特的视觉样式"""
        return {
            'header': QColor(180, 40, 40),  # 红色标题栏表示错误/未知
            'body': QColor(240, 220, 220),  # 带有红色色调的浅色主体
            'border': QColor(140, 30, 30) if not self.isSelected() else QColor(255, 165, 0),  # 深红色边框或橙色（选中时）
            'header_text': QColor(255, 255, 255),  # 标题栏的白色文本
            'shadow': QColor(50, 50, 50, 40),  # 半透明阴影
            'property_title': QColor(150, 30, 30),  # 红色属性标题
            'property_value': QColor(100, 30, 30),  # 红色属性值
            'separator': QColor(130, 50, 50)  # 红色分隔线
        }

    def _paint_template_content(self, painter, colors):
        """重写绘制模板内容的方法，添加警告消息"""
        if self.recognition_image and not self.recognition_image.isNull():
            # 先绘制警告消息
            warning_text = "未知节点类型"
            painter.setPen(QColor(180, 40, 40))
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.drawText(
                QRectF(10, self.content_start - 5, self.bounds.width() - 20, 20),
                Qt.AlignCenter,
                warning_text
            )

            # 计算调整后的图像位置（留出警告文本的空间）
            img_size = min(self.bounds.width() - 30, self.bounds.height() - self.content_start - 40)
            img_rect = QRectF(
                (self.bounds.width() - img_size) / 2,  # 水平居中
                self.content_start + 20,  # 向下偏移，留出警告文本的空间
                img_size,
                img_size
            )

            # 图像周围添加一个虚线边框
            painter.setPen(QPen(QColor(180, 40, 40, 120), 1, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(img_rect)

            # 绘制图像
            painter.drawPixmap(img_rect.toRect(), self.recognition_image)

    def _update_output_port_positions(self):
        """
        重写更新输出端口位置的方法
        未知节点没有输出端口，所以这个方法什么也不做
        """
        pass

    def get_output_port(self, port_type="next"):
        """
        重写获取输出端口的方法
        始终返回None，因为未知节点没有输出端口
        """
        return None

    def get_output_ports(self):
        """
        重写获取所有输出端口的方法
        返回空字典，因为未知节点没有输出端口
        """
        return {}

    def set_task_node(self, task_node):
        """重写设置任务节点的方法，保持未知节点的特性"""
        super().set_task_node(task_node)

        # 无论传入什么task_node，始终保持未知节点的特性
        self.has_template = True
        # 不再每次都创建图像，而是使用类级别的共享图像
        self.recognition_image = self._create_unknown_image()
        self.default_image = self.recognition_image

        self.title = "Unknown Node"  # 始终保持标题为未知节点

        if task_node and hasattr(task_node, 'name'):
            # 可以保留从task_node获取的ID，但标题仍然为"Unknown Node"
            self.id = hashlib.md5(task_node.name.encode()).hexdigest()[:6].upper()
        else:
            self.id = "UNKNOWN"

        # 确保没有输出端口
        self.output_ports = {}

        # 更新端口位置
        self._update_port_positions()

        self.update()  # 强制重绘