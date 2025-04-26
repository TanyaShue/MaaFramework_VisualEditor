from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPen, QColor, QBrush


class GridItem(QGraphicsItem):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid_size = 20
        self.primary_grid_size = 100  # 5x the normal grid size
        self.grid_pen_primary = QPen(QColor(200, 200, 200), 0.8)
        self.grid_pen_secondary = QPen(QColor(230, 230, 230), 0.5)
        self.setZValue(-2)  # 放置在所有内容下方
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)  # 启用缓存以提高性能

    def boundingRect(self):
        # 使用当前视图的可见区域
        if self.scene() and self.scene().views():
            view = self.scene().views()[0]
            view_rect = view.mapToScene(view.viewport().rect()).boundingRect()
            # 扩大一点以确保覆盖
            view_rect.adjust(-100, -100, 100, 100)
            return view_rect
        return QRectF(-10000, -10000, 20000, 20000)

    def paint(self, painter, option, widget):
        # 获取当前可见区域
        view_rect = self.boundingRect()

        # 计算可见区域中的网格线
        left = int(view_rect.left() // self.grid_size) * self.grid_size
        right = int(view_rect.right() // self.grid_size + 1) * self.grid_size
        top = int(view_rect.top() // self.grid_size) * self.grid_size
        bottom = int(view_rect.bottom() // self.grid_size + 1) * self.grid_size

        # 优化：获取当前视图缩放级别
        view_scale = 1.0
        if self.scene() and self.scene().views():
            view = self.scene().views()[0]
            view_scale = view.transform().m11()  # 获取水平缩放系数

        # 根据缩放级别调整网格显示
        if view_scale < 0.4:
            # 低缩放级别：只显示主网格线
            painter.setPen(self.grid_pen_primary)
            for x in range(left, right, self.primary_grid_size):
                painter.drawLine(x, top, x, bottom)

            for y in range(top, bottom, self.primary_grid_size):
                painter.drawLine(left, y, right, y)
        else:
            # 正常或高缩放级别：显示所有网格线

            # 绘制次要网格线
            painter.setPen(self.grid_pen_secondary)
            for x in range(left, right, self.grid_size):
                if x % self.primary_grid_size != 0:  # 跳过将绘制为主网格线的线
                    painter.drawLine(x, top, x, bottom)

            for y in range(top, bottom, self.grid_size):
                if y % self.primary_grid_size != 0:  # 跳过将绘制为主网格线的线
                    painter.drawLine(left, y, right, y)

            # 绘制主网格线
            painter.setPen(self.grid_pen_primary)
            for x in range(left, right, self.primary_grid_size):
                painter.drawLine(x, top, x, bottom)

            for y in range(top, bottom, self.primary_grid_size):
                painter.drawLine(left, y, right, y)

        # 在原点绘制特殊标记
        if left <= 0 <= right and top <= 0 <= bottom:
            painter.setBrush(QBrush(QColor(255, 0, 0, 100)))
            painter.drawRect(-5, -5, 10, 10)