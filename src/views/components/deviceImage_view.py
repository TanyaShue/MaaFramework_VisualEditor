import os
from datetime import datetime
from PIL.Image import Image
from PIL.ImageQt import QImage
from PySide6.QtCore import Qt, Signal, QPoint, QRectF, QPointF, QTimer
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtWidgets import (QMenu, QGraphicsView, QGraphicsScene,
                               QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsItem,
                               QApplication, QSizePolicy)

from src.config_manager import config_manager
import numpy as np
import cv2
from io import BytesIO

class SelectionRect(QGraphicsRectItem):
    """Selection rectangle with info display"""

    def __init__(self, is_secondary=False):
        super().__init__()
        # 设置不同的颜色，主选择框为红色，次选择框为绿色
        if is_secondary:
            color = QColor(0, 255, 0, 40)  # Green with alpha
            pen_color = QColor(0, 255, 0)  # Green for pen
        else:
            color = QColor(255, 0, 0, 40)  # Red with alpha
            pen_color = QColor(255, 0, 0)  # Red for pen

        self.setPen(QPen(pen_color, 2, Qt.SolidLine))
        self.setBrush(QBrush(color))
        self.setZValue(100)  # Ensure it's on top
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        # Add a flag to check if the object is valid
        self.is_valid = True
        # 标记是否为次选择框
        self.is_secondary = is_secondary

    def paint(self, painter, option, widget):
        """Customize the paint to add info overlay"""
        # Paint the standard rectangle
        super().paint(painter, option, widget)

        # 信息面板在主类中绘制，这里不再绘制信息


class DeviceImageView(QGraphicsView):
    """Enhanced graphics view for device images with intuitive zooming and panning"""

    # Signals
    selectionChanged = Signal(QRectF)
    selectionCleared = Signal()
    # 添加新信号
    NodeChangeSignal = Signal(str, object)
    modeChangedSignal = Signal(bool)  # True = 框选模式, False = 显示模式
    # 添加多选区变更信号
    multiSelectionChangedSignal = Signal(list)

    def __init__(self, parent=None, control=None):
        super().__init__(parent)
        self.control = control
        # Setup the view
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, True)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Create scene
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # Initialize members
        self.pixmap_item = None
        self.selection_rect = None
        self.secondary_selection_rect = None  # 新增次选择框
        self.zoom_info_item = None
        self.original_pixmap = None
        self.is_selecting = False
        self.is_selecting_secondary = False  # 标记是否正在创建次选择框
        self.selection_mode = False
        self.selection_start = None
        self.secondary_selection_start = None  # 次选择框起始点
        self.min_zoom = 0.1
        self.max_zoom = 4.0
        self.zoom_sensitivity = 0.3  # 调整缩放灵敏度
        self._panning = False
        self._last_pan_pos = None

        # Context menu
        self.context_menu = QMenu(self)

    def set_image(self, image):
        """Set and display a new image"""
        self.scene.clear()
        self.pixmap_item = None
        self.original_pixmap = None
        self.selection_rect = None  # Reset selection rect when changing image
        self.secondary_selection_rect = None  # 重置次选择框

        if image is None:
            return

        # Convert to QPixmap based on type
        if isinstance(image, QPixmap):
            pixmap = image
        elif isinstance(image, Image):
            # Convert PIL Image to QPixmap
            img = image.convert("RGB")
            w, h = img.size
            data = img.tobytes("raw", "RGB")
            qimg = QImage(data, w, h, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
        else:
            # Assume it's a QImage
            pixmap = QPixmap.fromImage(image)

        # Store original
        self.original_pixmap = pixmap

        # Create and add pixmap item
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)

        # Add zoom info item (hidden initially)
        self.zoom_info_item = self.scene.addText("")
        self.zoom_info_item.setDefaultTextColor(QColor(255, 255, 255))
        self.zoom_info_item.setZValue(100)
        self.zoom_info_item.setVisible(False)

        # Reset view and center
        self.reset_view()

    def reset_view(self):
        """Reset view to fit image with proper centering"""
        if self.pixmap_item:
            # Clear selection if any
            self.clear_selection()

            # Reset transform
            self.resetTransform()

            # Calculate the proper scaling to fit view
            view_rect = self.viewport().rect()
            pixmap_rect = self.pixmap_item.boundingRect()

            # Fit contents in view
            self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

            # Center the scene
            self.centerOn(self.pixmap_item)

            # Update scene rect
            margin = 50  # Extra margin for panning
            scene_rect = pixmap_rect.adjusted(
                -margin, -margin, margin, margin
            )
            self.scene.setSceneRect(scene_rect)

    def toggle_selection_mode(self, enabled):
        """Enable/disable selection mode"""
        self.selection_mode = enabled
        if not enabled:
            self.clear_selection()
        self.setCursor(Qt.CrossCursor if enabled else Qt.ArrowCursor)
        # 发送模式变更信号
        self.modeChangedSignal.emit(enabled)

    def clear_selection(self):
        """Clear current selection"""
        # 清除主选择框
        if self.selection_rect:
            try:
                # Check if the object is still valid before attempting to remove it
                if hasattr(self.selection_rect, 'scene') and self.selection_rect.scene():
                    self.scene.removeItem(self.selection_rect)
            except RuntimeError:
                # The object may have been deleted already
                pass
            finally:
                self.selection_rect = None

        # 清除次选择框
        if self.secondary_selection_rect:
            try:
                if hasattr(self.secondary_selection_rect, 'scene') and self.secondary_selection_rect.scene():
                    self.scene.removeItem(self.secondary_selection_rect)
            except RuntimeError:
                pass
            finally:
                self.secondary_selection_rect = None

        # 发出信号
        self.selectionCleared.emit()

    def is_selection_valid(self):
        """Check if the selection rectangle is still valid"""
        if not self.selection_rect:
            return False
        try:
            # Try to access a property to see if the object is valid
            _ = self.selection_rect.rect()
            return True
        except (RuntimeError, AttributeError):
            # Object has been deleted or is invalid
            self.selection_rect = None
            return False

    def is_secondary_selection_valid(self):
        """检查次选择框是否有效"""
        if not self.secondary_selection_rect:
            return False
        try:
            _ = self.secondary_selection_rect.rect()
            return True
        except (RuntimeError, AttributeError):
            self.secondary_selection_rect = None
            return False

    def has_both_selections(self):
        """检查是否同时有主选择框和次选择框"""
        return self.is_selection_valid() and self.is_secondary_selection_valid()

    def get_selection(self):
        """Get the current selection in scene coordinates"""
        if not self.is_selection_valid():
            return None
        try:
            rect = self.selection_rect.rect().normalized()
            return self.selection_rect.mapToScene(rect).boundingRect()
        except (RuntimeError, AttributeError):
            # Handle potential errors if the object becomes invalid
            self.selection_rect = None
            return None

    def get_secondary_selection(self):
        """获取次选择框在场景坐标中的区域"""
        if not self.is_secondary_selection_valid():
            return None
        try:
            rect = self.secondary_selection_rect.rect().normalized()
            return self.secondary_selection_rect.mapToScene(rect).boundingRect()
        except (RuntimeError, AttributeError):
            self.secondary_selection_rect = None
            return None

    def get_normalized_selection(self):
        """Get the selection as normalized coordinates (0-1 range)"""
        if not self.is_selection_valid() or not self.pixmap_item:
            return None

        try:
            # Get selection in scene coordinates
            sel_rect = self.get_selection()
            if not sel_rect:
                return None

            # Get pixmap rect in scene coordinates
            pixmap_rect = self.pixmap_item.mapToScene(
                self.pixmap_item.boundingRect()
            ).boundingRect()

            # Normalize coordinates
            if not pixmap_rect.isEmpty():
                x1 = (sel_rect.left() - pixmap_rect.left()) / pixmap_rect.width()
                y1 = (sel_rect.top() - pixmap_rect.top()) / pixmap_rect.height()
                x2 = (sel_rect.right() - pixmap_rect.left()) / pixmap_rect.width()
                y2 = (sel_rect.bottom() - pixmap_rect.top()) / pixmap_rect.height()

                return QRectF(x1, y1, x2 - x1, y2 - y1)
        except (RuntimeError, AttributeError):
            # Handle potential errors if objects become invalid
            self.selection_rect = None

        return None

    def get_roi_data(self, is_secondary=False):
        """获取选择区域的ROI数据 (x, y, w, h)"""
        selection_rect = self.secondary_selection_rect if is_secondary else self.selection_rect

        if (not selection_rect) or not self.pixmap_item:
            return None

        try:
            # 获取场景坐标中的选择区域
            if is_secondary:
                sel_rect = self.get_secondary_selection()
            else:
                sel_rect = self.get_selection()

            if not sel_rect:
                return None

            # 获取pixmap在场景中的位置
            pixmap_scene_pos = self.pixmap_item.scenePos()

            # 计算相对于图像的ROI坐标
            roi_x = int(sel_rect.left() - pixmap_scene_pos.x())
            roi_y = int(sel_rect.top() - pixmap_scene_pos.y())
            roi_w = int(sel_rect.width())
            roi_h = int(sel_rect.height())

            return [roi_x, roi_y, roi_w, roi_h]

        except (RuntimeError, AttributeError):
            # 处理潜在错误
            if is_secondary:
                self.secondary_selection_rect = None
            else:
                self.selection_rect = None
            return None

    def get_offset_data(self):
        """计算两个选区之间的偏移量"""
        if not self.has_both_selections():
            return None

        roi_1 = self.get_roi_data(is_secondary=False)
        roi_2 = self.get_roi_data(is_secondary=True)

        if not roi_1 or not roi_2:
            return None

        # 计算偏移量 (x差值, y差值, w差值, h差值)
        offset_x = roi_2[0] - roi_1[0]
        offset_y = roi_2[1] - roi_1[1]
        offset_w = roi_2[2] - roi_1[2]
        offset_h = roi_2[3] - roi_1[3]

        return [offset_x, offset_y, offset_w, offset_h]

    def constrain_to_pixmap(self, scene_pos):
        """将场景坐标限制在图片范围内"""
        if not self.pixmap_item:
            return scene_pos

        try:
            # 获取图片在场景中的边界
            pixmap_rect = self.pixmap_item.mapToScene(
                self.pixmap_item.boundingRect()
            ).boundingRect()

            # 限制坐标到图片边界
            constrained_x = max(pixmap_rect.left(), min(scene_pos.x(), pixmap_rect.right()))
            constrained_y = max(pixmap_rect.top(), min(scene_pos.y(), pixmap_rect.bottom()))

            return QPointF(constrained_x, constrained_y)
        except (RuntimeError, AttributeError):
            # If there's an error, return the original position
            return scene_pos

    def zoom_to_factor(self, factor):
        """Zoom to specified factor"""
        # Constrain zoom factor
        factor = max(self.min_zoom, min(self.max_zoom, factor))

        # Get current transform
        current_zoom = self.transform().m11()

        # Calculate zoom change
        zoom_delta = factor / current_zoom

        # Apply zoom
        self.scale(zoom_delta, zoom_delta)

    def zoom_by_delta(self, delta):
        """Zoom by delta amount"""
        zoom_factor = 1 + (delta * self.zoom_sensitivity)

        # Get current zoom
        current_zoom = self.transform().m11()

        # Calculate new zoom
        new_zoom = current_zoom * zoom_factor

        # Apply constrained zoom
        self.zoom_to_factor(new_zoom)

    def get_zoom_factor(self):
        """Get current zoom factor"""
        return self.transform().m11()

    def paintEvent(self, event):
        """重写绘制事件，添加信息面板"""
        super().paintEvent(event)

        # 绘制信息面板
        if self.pixmap_item and (self.is_selection_valid() or self.is_secondary_selection_valid()):
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.Antialiasing)

            # 设置信息面板位置和大小
            info_width = 220  # 增加宽度以适应更多信息
            info_height = 120 if self.has_both_selections() else 80  # 当有两个选区时增加高度
            info_margin = 10

            info_x = self.viewport().width() - info_width - info_margin
            info_y = info_margin

            # 绘制信息面板背景
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
            painter.drawRoundedRect(info_x, info_y, info_width, info_height, 5, 5)

            # 绘制信息文本
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.setFont(QFont("Arial", 9))

            text = "选择区域信息:\n"

            # 添加主选区信息
            if self.is_selection_valid():
                roi_1 = self.get_roi_data(is_secondary=False)
                if roi_1:
                    sel_rect = self.get_selection()
                    text += (f"ROI_1: ({roi_1[0]}, {roi_1[1]}, {roi_1[2]}, {roi_1[3]})\n"
                             f"起点: ({int(sel_rect.x())}, {int(sel_rect.y())})\n")

            # 添加次选区信息
            if self.is_secondary_selection_valid():
                roi_2 = self.get_roi_data(is_secondary=True)
                if roi_2:
                    sel_rect = self.get_secondary_selection()
                    text += (f"ROI_2: ({roi_2[0]}, {roi_2[1]}, {roi_2[2]}, {roi_2[3]})\n"
                             f"起点: ({int(sel_rect.x())}, {int(sel_rect.y())})\n")

            # 添加偏移量信息
            if self.has_both_selections():
                offset = self.get_offset_data()
                if offset:
                    text += f"偏移量: ({offset[0]}, {offset[1]}, {offset[2]}, {offset[3]})"

            painter.drawText(info_x + 10, info_y + 10, info_width - 20, info_height - 20,
                             Qt.AlignLeft, text)

            painter.end()

    # Event handlers
    def mousePressEvent(self, event):
        """Handle mouse press events"""
        if not self.pixmap_item:
            return super().mousePressEvent(event)

        # Get scene position
        scene_pos = self.mapToScene(event.pos())

        # Right click context menu
        if event.button() == Qt.RightButton and not (event.modifiers() & Qt.ControlModifier):
            self._show_context_menu(event.pos())
            return

        # Middle button or Ctrl+Right for panning
        if (event.button() == Qt.MiddleButton or
                (event.button() == Qt.RightButton and event.modifiers() & Qt.ControlModifier)):
            self._panning = True
            self._last_pan_pos = event.pos()
            self.setCursor(Qt.OpenHandCursor)
            return

        # 创建新的次选择框 (Ctrl+左键)
        if (event.button() == Qt.LeftButton and
                self.selection_mode and
                event.modifiers() & Qt.ControlModifier and
                self.is_selection_valid()):
            # 确保点击位置在图片内
            try:
                pixmap_scene_pos = self.pixmap_item.mapToScene(
                    self.pixmap_item.boundingRect()
                ).boundingRect()

                if pixmap_scene_pos.contains(scene_pos):
                    # 清除已有的次选择框
                    if self.secondary_selection_rect:
                        try:
                            if hasattr(self.secondary_selection_rect,
                                       'scene') and self.secondary_selection_rect.scene():
                                self.scene.removeItem(self.secondary_selection_rect)
                        except RuntimeError:
                            pass

                    self.is_selecting_secondary = True
                    self.secondary_selection_start = scene_pos

                    # 创建新的次选择框 (绿色)
                    self.secondary_selection_rect = SelectionRect(is_secondary=True)
                    self.scene.addItem(self.secondary_selection_rect)

                    # 初始化为零矩形
                    self.secondary_selection_rect.setRect(QRectF(0, 0, 0, 0))
                    self.secondary_selection_rect.setPos(scene_pos)
                    return
            except (RuntimeError, AttributeError):
                self.is_selecting_secondary = False
                return super().mousePressEvent(event)

        # Left click for selection
        if event.button() == Qt.LeftButton and self.selection_mode and not (event.modifiers() & Qt.ControlModifier):
            # 确保点击位置在图片内
            try:
                pixmap_scene_pos = self.pixmap_item.mapToScene(
                    self.pixmap_item.boundingRect()
                ).boundingRect()

                if pixmap_scene_pos.contains(scene_pos):
                    # Clear any existing selections
                    self.clear_selection()

                    self.is_selecting = True
                    self.selection_start = scene_pos

                    # Create new selection rectangle (red)
                    self.selection_rect = SelectionRect(is_secondary=False)
                    self.scene.addItem(self.selection_rect)

                    # Initialize with zero rect at start point
                    self.selection_rect.setRect(QRectF(0, 0, 0, 0))
                    self.selection_rect.setPos(scene_pos)
                    return
            except (RuntimeError, AttributeError):
                # Handle potential errors
                self.pixmap_item = None
                return super().mousePressEvent(event)

        # Left click not in selection mode - use for panning
        if event.button() == Qt.LeftButton and not self.selection_mode:
            self._panning = True
            self._last_pan_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move events"""
        if not self.pixmap_item:
            return super().mouseMoveEvent(event)

        # 次选择框选择进行中
        if self.is_selecting_secondary and self.is_secondary_selection_valid():
            try:
                current_scene_pos = self.mapToScene(event.pos())
                constrained_pos = self.constrain_to_pixmap(current_scene_pos)

                rect = QRectF(self.secondary_selection_start, constrained_pos).normalized()
                local_rect = QRectF(0, 0, rect.width(), rect.height())

                self.secondary_selection_rect.setRect(local_rect)
                self.secondary_selection_rect.setPos(rect.topLeft())

                # 触发重绘以更新信息面板
                self.viewport().update()

                return
            except (RuntimeError, AttributeError):
                self.is_selecting_secondary = False
                self.secondary_selection_rect = None

        # 主选择框选择进行中
        if self.is_selecting and self.is_selection_valid():
            try:
                # 获取当前鼠标位置对应的场景坐标
                current_scene_pos = self.mapToScene(event.pos())

                # 限制当前坐标在图片范围内
                constrained_pos = self.constrain_to_pixmap(current_scene_pos)

                # 计算从起始点到当前位置的矩形
                rect = QRectF(self.selection_start, constrained_pos).normalized()

                # 调整为相对于rect位置的坐标
                local_rect = QRectF(
                    0, 0,
                    rect.width(),
                    rect.height()
                )

                # 设置矩形位置和大小
                self.selection_rect.setRect(local_rect)
                self.selection_rect.setPos(rect.topLeft())

                # 触发重绘以更新信息面板
                self.viewport().update()

                return
            except (RuntimeError, AttributeError):
                # Selection rect may have been deleted
                self.is_selecting = False
                self.selection_rect = None

        # Panning in progress
        if self._panning and self._last_pan_pos:
            try:
                # Calculate the delta in view coordinates
                delta = event.pos() - self._last_pan_pos
                self._last_pan_pos = event.pos()

                # Use scrolling to implement natural panning
                self.horizontalScrollBar().setValue(
                    self.horizontalScrollBar().value() - delta.x()
                )
                self.verticalScrollBar().setValue(
                    self.verticalScrollBar().value() - delta.y()
                )

                # Update cursor
                if event.buttons() & Qt.RightButton and event.modifiers() & Qt.ControlModifier:
                    self.setCursor(Qt.ClosedHandCursor)
                return
            except (RuntimeError, AttributeError):
                # Handle potential errors
                self._panning = False

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release events"""
        # 结束次选择框选择
        if self.is_selecting_secondary and event.button() == Qt.LeftButton:
            self.is_selecting_secondary = False

            if self.is_secondary_selection_valid():
                try:
                    if not self.secondary_selection_rect.rect().isEmpty():
                        # 发出双选择框变更信号
                        self.multiSelectionChangedSignal.emit([
                            self.get_selection(),
                            self.get_secondary_selection()
                        ])
                except (RuntimeError, AttributeError):
                    self.secondary_selection_rect = None

        # 结束主选择框选择
        elif self.is_selecting and event.button() == Qt.LeftButton:
            self.is_selecting = False

            # Check if selection rect is valid before accessing
            if self.is_selection_valid():
                try:
                    if not self.selection_rect.rect().isEmpty():
                        selection = self.get_selection()
                        if selection:
                            self.selectionChanged.emit(selection)
                except (RuntimeError, AttributeError):
                    # Handle potential errors
                    self.selection_rect = None

        # End panning
        if self._panning and (event.button() == Qt.MiddleButton or
                              event.button() == Qt.LeftButton or
                              (event.button() == Qt.RightButton and event.modifiers() & Qt.ControlModifier)):
            self._panning = False
            self.setCursor(Qt.ArrowCursor if not self.selection_mode else Qt.CrossCursor)

        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """Handle wheel events for zooming"""
        if not self.pixmap_item:
            return super().wheelEvent(event)

        # 获取滚轮方向和角度大小
        delta = event.angleDelta().y()

        # 根据角度大小计算缩放量，角度越大缩放越明显
        # 将标准的120角度单位映射到0.2的缩放变化
        zoom_delta = delta / 600.0  # 120 * 5 = 600，将标准滚动单位映射到合适缩放比例

        # 执行缩放
        self.zoom_by_delta(zoom_delta)

        # 阻止默认的滚轮行为
        event.accept()

    def resizeEvent(self, event):
        """Handle resize events"""
        super().resizeEvent(event)

        # On first resize after setting image, fit to view
        if self.pixmap_item and event.oldSize().isEmpty():
            QTimer.singleShot(0, self.reset_view)

    def _show_context_menu(self, pos):
        """Show context menu"""
        self.context_menu.clear()

        # 根据选择框状态提供不同选项
        if self.has_both_selections():
            # 当有两个选择框时，显示保存偏移量选项
            save_offset_menu = self.context_menu.addMenu("保存偏移")
            save_offset_menu.addAction("保存偏移到节点roi", self._save_offset_to_node_roi)
            save_offset_menu.addAction("保存偏移到节点target", self._save_offset_to_node_target)

            # 添加清除全部选区选项
            self.context_menu.addAction("清除全部选区", self.clear_selection)

            # 添加仅清除次选区选项
            self.context_menu.addAction("清除次选区", self._clear_secondary_selection)

        elif self.is_selection_valid():
            # 只有主选择框时显示正常选项
            self.context_menu.addAction("编辑选区", self._edit_selection)

            # 创建保存选区子菜单
            save_menu = self.context_menu.addMenu("保存选区")
            save_menu.addAction("保存图片到节点", self._save_image_to_node)
            save_menu.addAction("保存ROI到节点", self._save_roi_to_node)
            save_menu.addAction("保存Target到节点", self._save_target_to_node)
            save_menu.addAction("保存所需颜色到节点", self._save_color_to_node)  # 新增此行

            self.context_menu.addAction("清除选区", self.clear_selection)

            # 添加提示创建次选择框的选项
            self.context_menu.addAction("按Ctrl+左键添加次选择框", lambda: None)

        else:
            self.context_menu.addAction("全选", self._select_all)
            self.context_menu.addAction("重置视图", self.reset_view)

        # Common options
        self.context_menu.addSeparator()
        mode_action = self.context_menu.addAction(f"切换到{'显示' if self.selection_mode else '框选'}模式",
                                                  lambda: self.toggle_selection_mode(not self.selection_mode))

        # 添加缩放选项
        self.context_menu.addSeparator()
        zoom_menu = self.context_menu.addMenu("缩放")
        for zoom in [25, 50, 75, 100, 125, 150, 200, 300]:
            # Create a lambda that captures the value properly
            action = zoom_menu.addAction(f"{zoom}%")
            # Use a separate function to avoid lambda capture issues
            zoom_value = zoom / 100  # Calculate the zoom value
            action.triggered.connect(lambda checked=False, z=zoom_value: self.zoom_to_factor(z))

        # Show menu
        self.context_menu.exec(self.mapToGlobal(pos))

    def _clear_secondary_selection(self):
        """仅清除次选择框"""
        if self.secondary_selection_rect:
            try:
                if hasattr(self.secondary_selection_rect, 'scene') and self.secondary_selection_rect.scene():
                    self.scene.removeItem(self.secondary_selection_rect)
            except RuntimeError:
                pass
            finally:
                self.secondary_selection_rect = None
                self.viewport().update()  # 更新视图以刷新信息面板

    def _save_offset_to_node_roi(self):
        """保存两个选区之间的偏移量到节点"""
        offset_data = self.get_offset_data()
        if not offset_data:
            return

        if self.control and self.control.open_node:
            node = self.control.open_node
            node.task_node.roi_offset = offset_data
            node.refresh_ui()

            # 发送节点变更信号
            self.control.OpenNodeChanged.emit("controller_view", self.control.open_node)

    def _save_offset_to_node_target(self):
        """保存两个选区之间的偏移量到节点"""
        offset_data = self.get_offset_data()
        if not offset_data:
            return

        if self.control and self.control.open_node:
            node = self.control.open_node
            node.task_node.target_offset = offset_data
            node.refresh_ui()

            # 发送节点变更信号
            self.control.OpenNodeChanged.emit("controller_view", self.control.open_node)

    def _save_color_to_node(self):
        """保存选区颜色范围到节点"""
        if not self.is_selection_valid() or not self.original_pixmap:
            return

        try:
            # 获取标准化的选区坐标
            norm_rect = self.get_normalized_selection()
            if not norm_rect:
                return

            # 从原始图像中提取选区
            pixmap_rect = self.original_pixmap.rect()
            x = int(norm_rect.x() * pixmap_rect.width())
            y = int(norm_rect.y() * pixmap_rect.height())
            w = int(norm_rect.width() * pixmap_rect.width())
            h = int(norm_rect.height() * pixmap_rect.height())

            # 创建裁剪后的图像
            cropped = self.original_pixmap.copy(x, y, w, h)

            # 转换QPixmap为numpy数组以便进行颜色分析
            from PySide6.QtCore import QBuffer
            img_buffer = QBuffer()
            img_buffer.open(QBuffer.ReadWrite)
            cropped.save(img_buffer, "PNG")
            img_data = img_buffer.data().data()
            img_buffer.close()

            # 转换为numpy数组
            from PIL import Image
            pil_image = Image.open(BytesIO(img_data))
            np_image = np.array(pil_image)

            # 计算RGB颜色范围
            rgb_lower = np.min(np_image, axis=(0, 1)).tolist()
            rgb_upper = np.max(np_image, axis=(0, 1)).tolist()

            # 转换为HSV并计算颜色范围
            bgr_image = cv2.cvtColor(np_image, cv2.COLOR_RGB2BGR)  # 转换RGB到BGR
            hsv_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
            hsv_lower = np.min(hsv_image, axis=(0, 1)).tolist()
            hsv_upper = np.max(hsv_image, axis=(0, 1)).tolist()

            # 转换为灰度并计算颜色范围
            gray_image = cv2.cvtColor(np_image, cv2.COLOR_RGB2GRAY)
            gray_lower = [int(np.min(gray_image))]
            gray_upper = [int(np.max(gray_image))]

            # 获取当前节点的颜色匹配方法
            method = 4  # 默认RGB
            if self.control and self.control.open_node:
                node = self.control.open_node
                if hasattr(node.task_node, 'method'):
                    method = node.task_node.method

            # 根据method选择适当的颜色范围
            if method == 40:  # HSV
                lower = hsv_lower
                upper = hsv_upper
            elif method == 6:  # Grayscale
                lower = gray_lower
                upper = gray_upper
            else:  # RGB and others
                lower = rgb_lower
                upper = rgb_upper

            # 保存到节点
            if self.control and self.control.open_node:
                node = self.control.open_node
                node.task_node.lower = lower
                node.task_node.upper = upper
                node.refresh_ui()

                # 发送节点变更信号
                self.control.OpenNodeChanged.emit("controller_view", self.control.open_node)

                print(f"已保存颜色范围 - method: {method}, lower: {lower}, upper: {upper}")

        except Exception as e:
            print(f"保存颜色范围时出错: {e}")
    # Context menu actions
    def _edit_selection(self):
        """将选区截取并更新为当前视图"""
        if not self.is_selection_valid() or not self.original_pixmap:
            return

        try:
            # 获取标准化的选区坐标
            norm_rect = self.get_normalized_selection()
            if not norm_rect:
                return

            # 从原始图像中提取选区
            pixmap_rect = self.original_pixmap.rect()
            x = int(norm_rect.x() * pixmap_rect.width())
            y = int(norm_rect.y() * pixmap_rect.height())
            w = int(norm_rect.width() * pixmap_rect.width())
            h = int(norm_rect.height() * pixmap_rect.height())

            # 创建裁剪后的图像
            cropped = self.original_pixmap.copy(x, y, w, h)

            # 更新当前视图，显示裁剪后的图像
            self.set_image(cropped)

            # 清除选区，因为我们已经裁剪并更新了图像
            self.clear_selection()

            # 如果有控制器引用，更新状态信息
            if self.control:
                print(f"已编辑选区：{w}x{h}")

        except (RuntimeError, AttributeError) as e:
            # 处理潜在错误
            print(f"编辑选区时发生错误: {e}")

    def _save_image_to_node(self):
        """保存原始图片到节点"""
        if not self.original_pixmap:
            return

        # 保存并获取相对路径
        relative_path = self._save_selection()

        if not relative_path:
            return

        if self.control.open_node:
            node = self.control.open_node
            template = getattr(node.task_node, 'template', None)

            if template is None:
                node.task_node.template = [relative_path]
            elif isinstance(template, list):
                if relative_path not in template:
                    template.append(relative_path)
            elif isinstance(template, str):
                if template != relative_path:
                    node.task_node.template = [template, relative_path]

            node.refresh_ui()
            self.control.OpenNodeChanged.emit("controller_view", self.control.open_node)

            # self.NodeChangeSignal.emit("template", relative_path)

    def _save_roi_to_node(self):
        """保存选区ROI到节点"""
        if not self.is_selection_valid():
            return

        # 获取ROI数据
        roi_data = self.get_roi_data()
        if not roi_data:
            return
        if self.control.open_node:
            node = self.control.open_node
            node.task_node.roi = roi_data
            node.refresh_ui()
        # 发送信号
        self.control.OpenNodeChanged.emit("controller_view", self.control.open_node)

    def _save_target_to_node(self):
        """保存选区为目标到节点"""
        if not self.is_selection_valid() or not self.original_pixmap:
            return

        target_data = self.get_roi_data()
        if not target_data:
            return
        # 发送信号
        if self.control.open_node:
            node = self.control.open_node
            node.task_node.target = target_data
            node.refresh_ui()
        # 发送信号
        self.control.OpenNodeChanged.emit("controller_view", self.control.open_node)

    def _save_selection(self):
        """Save selection to file and return relative path"""
        if not self.is_selection_valid() or not self.original_pixmap:
            return None

        try:
            norm_rect = self.get_normalized_selection()
            if not norm_rect:
                return None

            pixmap_rect = self.original_pixmap.rect()
            x = int(norm_rect.x() * pixmap_rect.width())
            y = int(norm_rect.y() * pixmap_rect.height())
            w = int(norm_rect.width() * pixmap_rect.width())
            h = int(norm_rect.height() * pixmap_rect.height())
            cropped = self.original_pixmap.copy(x, y, w, h)

            base_path = config_manager.config["recent_files"]["base_resource_path"]

            if self.control:
                file_name = self.control.file_name
                file_name_without_ext = os.path.splitext(os.path.basename(file_name))[0] if file_name else None

                if file_name_without_ext:
                    save_dir = os.path.join(base_path, "image", file_name_without_ext)
                    base_filename = self.control.current_node_name or file_name_without_ext
                else:
                    save_dir = os.path.join(base_path, "image")
                    base_filename = f"selection_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            else:
                save_dir = os.path.join(base_path, "image")
                base_filename = f"selection_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            os.makedirs(save_dir, exist_ok=True)

            def get_unique_filename(directory, base_name, ext='.png'):
                file_path = os.path.join(directory, f"{base_name}{ext}")
                if not os.path.exists(file_path):
                    return f"{base_name}{ext}"
                counter = 1
                while True:
                    new_filename = f"{base_name}_{counter}{ext}"
                    file_path = os.path.join(directory, new_filename)
                    if not os.path.exists(file_path):
                        return new_filename
                    counter += 1

            filename = get_unique_filename(save_dir, base_filename)
            save_path = os.path.join(save_dir, filename)

            try:
                cropped.save(save_path)
                print(f"Selection saved to {save_path}")
            except Exception as e:
                print(f"Error saving selection: {e}")
                return None

            # Return path relative to base_path/image/
            relative_path = os.path.relpath(save_path, os.path.join(base_path, "image"))
            return relative_path

        except Exception as e:
            print(f"Exception in _save_selection: {e}")
            return None

    def _select_all(self):
        """Select the entire image"""
        if not self.pixmap_item:
            return

        try:
            # Enable selection mode
            self.selection_mode = True
            # 发送模式变更信号
            self.modeChangedSignal.emit(True)

            # Clear any existing selection first
            self.clear_selection()

            # Create new selection rectangle
            self.selection_rect = SelectionRect()
            self.scene.addItem(self.selection_rect)

            # Set to full image bounds
            self.selection_rect.setRect(QRectF(self.pixmap_item.boundingRect()))
            self.selection_rect.setPos(self.pixmap_item.pos())

            # Emit signal
            selection = self.get_selection()
            if selection:
                self.selectionChanged.emit(selection)
        except (RuntimeError, AttributeError):
            # Handle potential errors
            self.selection_rect = None