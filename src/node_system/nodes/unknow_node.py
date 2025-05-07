from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QFont, QColor, QPen, QBrush, QPainterPath, QPixmap

from src.node_system.node import Node


class UnknownNode(Node):
    """
    特殊的节点类，用于表示未知节点类型。
    显示一个固定的叉叉图像，表示节点无法识别或加载。
    """

    def __init__(self, id=None, title="Unknown Node", task_node=None, parent=None):
        # 调用父类初始化方法
        super().__init__(id=id, title=title, task_node=task_node, parent=parent)

        # 未知节点总是显示特定图像，所以标记为有模板
        self.has_template = True

        self.border_color=QColor(240, 240, 240)
        # 创建叉叉图像
        self._create_unknown_image()

        # 设置视觉属性
        self.bounds = QRectF(0, 0, 240, 180)  # 使节点稍小一些
        self.original_height = self.bounds.height()

        # 更新端口位置
        self._update_port_positions()

    def _create_unknown_image(self):
        """创建一个带有叉叉的图像表示未知节点"""
        # 创建一个空白图像
        self.recognition_image = QPixmap(120, 120)
        self.recognition_image.fill(Qt.transparent)

        # 创建绘制器
        painter = QPainter(self.recognition_image)
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

        # 同时设置默认图像为叉叉图像
        self.default_image = self.recognition_image

    def paint(self, painter, option, widget):
        """重写绘制方法，使未知节点有特殊的视觉样式"""
        # 设置渲染提示以获得更平滑的外观
        painter.setRenderHint(QPainter.Antialiasing)

        # 使用特殊颜色方案表示未知节点
        header_color = QColor(180, 40, 40)  # 红色标题栏表示错误/未知
        body_color = QColor(240, 220, 220)  # 带有红色色调的浅色主体
        border_color = QColor(140, 30, 30) if not self.isSelected() else QColor(255, 165, 0)  # 深红色边框或橙色（选中时）
        text_color = QColor(255, 255, 255)  # 标题栏的白色文本
        shadow_color = QColor(50, 50, 50, 40)  # 半透明阴影

        # 添加阴影效果
        painter.save()
        shadow_rect = self.bounds.adjusted(4, 4, 4, 4)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(shadow_color))
        painter.drawRoundedRect(shadow_rect, 5, 5)
        painter.restore()

        # 绘制主体
        painter.setPen(QPen(border_color, 1.5))
        painter.setBrush(QBrush(body_color))

        # 绘制圆角矩形
        path = QPainterPath()
        path.addRoundedRect(self.bounds, 5, 5)
        painter.drawPath(path)

        # 绘制标题栏
        header_rect = QRectF(0, 0, self.bounds.width(), self.header_height)
        header_path = QPainterPath()
        header_path.addRoundedRect(header_rect, 5, 5)

        # 创建一个裁剪区域使只有顶部角为圆形
        painter.save()
        painter.setClipPath(header_path)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(header_color))
        painter.drawRect(header_rect)
        painter.restore()

        # 绘制标题
        painter.setPen(text_color)
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        title_width = self.bounds.width() - 70  # 预留ID徽章的空间
        painter.drawText(
            QRectF(10, 0, title_width, self.header_height),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.title
        )

        # 绘制ID徽章
        id_text = f"{self.id}"
        id_font = QFont("Monospace", 7)
        painter.setFont(id_font)

        # 计算ID文本的宽度
        metrics = painter.fontMetrics()
        id_width = metrics.horizontalAdvance(id_text) + 10  # 添加内边距

        # 绘制ID徽章
        id_rect = QRectF(self.bounds.width() - id_width - 5, 5, id_width, 20)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(30, 30, 30, 150))  # 半透明深色背景
        painter.drawRoundedRect(id_rect, 10, 10)

        # 绘制ID文本
        painter.setPen(QColor(220, 220, 220))  # 浅灰色文本
        painter.drawText(id_rect, Qt.AlignCenter, id_text)

        # 如果未折叠，绘制内容部分
        if not self.collapsed:
            painter.setPen(QPen(QColor(100, 100, 100), 0.5))
            y_pos = self.header_height
            painter.drawLine(0, y_pos, self.bounds.width(), y_pos)

            # 绘制叉叉图像
            if self.recognition_image and not self.recognition_image.isNull():
                img_size = min(self.bounds.width() - 30, self.bounds.height() - self.content_start - 20)
                img_rect = QRectF(
                    (self.bounds.width() - img_size) / 2,  # 水平居中
                    self.content_start,
                    img_size,
                    img_size
                )

                # 绘制警告消息
                warning_text = "未知节点类型"
                painter.setPen(QColor(180, 40, 40))
                painter.setFont(QFont("Arial", 9, QFont.Bold))
                painter.drawText(
                    QRectF(10, self.content_start - 5, self.bounds.width() - 20, 20),
                    Qt.AlignCenter,
                    warning_text
                )

                # 图像周围添加一个微妙的边框
                painter.setPen(QPen(QColor(180, 40, 40, 120), 1, Qt.DashLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(img_rect)

                # 绘制图像
                painter.drawPixmap(img_rect.toRect(), self.recognition_image)

    def set_task_node(self, task_node):
        """重写设置任务节点的方法，保持未知节点的特性"""
        super().set_task_node(task_node)

        # 无论传入什么task_node，始终保持未知节点的特性
        self.has_template = True
        self._create_unknown_image()  # 确保始终使用叉叉图像
        self.title = "Unknown Node"  # 始终保持标题为未知节点

        if task_node and hasattr(task_node, 'name'):
            # 可以保留从task_node获取的ID，但标题仍然为"Unknown Node"
            self.id = task_node.name[:6].upper()
        else:
            self.id = "UNKNOWN"

        self.update()  # 强制重绘