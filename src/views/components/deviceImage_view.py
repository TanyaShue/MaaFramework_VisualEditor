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


class SelectionRect(QGraphicsRectItem):
    """Selection rectangle with info display"""

    def __init__(self):
        super().__init__()
        self.setPen(QPen(QColor(255, 0, 0), 2, Qt.SolidLine))
        self.setBrush(QBrush(QColor(255, 0, 0, 40)))
        self.setZValue(100)  # Ensure it's on top
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        # Add a flag to check if the object is valid
        self.is_valid = True

    def paint(self, painter, option, widget):
        """Customize the paint to add info overlay"""
        # Paint the standard rectangle
        super().paint(painter, option, widget)

        # Get the normalized rectangle
        rect = self.rect().normalized()

        # Calculate the absolute coordinates in scene
        scene_rect = self.sceneTransform().mapRect(rect)

        # Check if we're in a valid view
        if widget and widget.parentWidget():
            view = widget.parentWidget()
            if isinstance(view, DeviceImageView):
                pixmap_item = view.pixmap_item

                if pixmap_item:
                    pixmap_rect = pixmap_item.boundingRect()
                    if not pixmap_rect.isEmpty():
                        # 计算ROI (x, y, w, h)
                        pixmap_scene_pos = pixmap_item.scenePos()
                        roi_x = int(scene_rect.left() - pixmap_scene_pos.x())
                        roi_y = int(scene_rect.top() - pixmap_scene_pos.y())
                        roi_w = int(scene_rect.width())
                        roi_h = int(scene_rect.height())

                        # Get zoom factor directly from view's method for consistency
                        zoom_factor = view.get_zoom_factor()
                        zoom = int(zoom_factor * 100)  # Convert to percentage and ensure integer value

                        # Draw info panel
                        info_width = 180
                        info_height = 80
                        info_margin = 10

                        # Save painter state before any transformations
                        painter.save()

                        # Get the viewport
                        viewport = view.viewport()

                        # Reset all transformations to paint directly in viewport coordinates
                        painter.resetTransform()

                        # Calculate position in the top-right corner of the viewport
                        # This ensures it stays fixed regardless of panning
                        info_x = viewport.width() - info_width - info_margin
                        info_y = info_margin

                        # Use QPainter's device coordinate system
                        device_rect = painter.viewport()
                        painter.setWindow(device_rect)

                        # Translate to viewport coordinates
                        painter.translate(viewport.mapTo(widget, QPoint(0, 0)))

                        # Draw info background
                        painter.setPen(Qt.NoPen)
                        painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
                        painter.drawRoundedRect(info_x, info_y, info_width, info_height, 5, 5)

                        # Draw info text
                        painter.setPen(QPen(QColor(255, 255, 255)))
                        painter.setFont(QFont("Arial", 9))

                        # 更新信息面板，只显示ROI信息
                        text = (f"选择区域信息:\n"
                                f"起点: ({int(scene_rect.x())}, {int(scene_rect.y())})\n"
                                f"终点: ({int(scene_rect.right())}, {int(scene_rect.bottom())})\n"
                                f"ROI: ({roi_x}, {roi_y}, {roi_w}, {roi_h})")

                        painter.drawText(info_x + 10, info_y + 10, info_width - 20, info_height - 20,
                                         Qt.AlignLeft, text)

                        # Restore painter state
                        painter.restore()


class DeviceImageView(QGraphicsView):
    """Enhanced graphics view for device images with intuitive zooming and panning"""

    # Signals
    selectionChanged = Signal(QRectF)
    selectionCleared = Signal()
    # 添加新信号
    NodeChangeSignal = Signal(str, object)
    modeChangedSignal = Signal(bool)  # True = 框选模式, False = 显示模式

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
        self.zoom_info_item = None
        self.original_pixmap = None
        self.is_selecting = False
        self.selection_mode = False
        self.selection_start = None
        self.min_zoom = 0.1
        self.max_zoom = 4.0
        self.zoom_sensitivity = 0.3  # 调整缩放灵敏度为0.15
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

    def get_roi_data(self):
        """获取当前选择区域的ROI数据 (x, y, w, h)"""
        if not self.is_selection_valid() or not self.pixmap_item:
            return None

        try:
            # 获取场景坐标中的选择区域
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
            self.selection_rect = None
            return None

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

        # Left click for selection
        if event.button() == Qt.LeftButton and self.selection_mode:
            # 确保点击位置在图片内
            try:
                pixmap_scene_pos = self.pixmap_item.mapToScene(
                    self.pixmap_item.boundingRect()
                ).boundingRect()

                if pixmap_scene_pos.contains(scene_pos):
                    # Clear any existing selection first
                    self.clear_selection()

                    self.is_selecting = True
                    self.selection_start = scene_pos

                    # Create new selection rectangle
                    self.selection_rect = SelectionRect()
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

        # Selection in progress
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
        # End selection
        if self.is_selecting and event.button() == Qt.LeftButton:
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

        # Different options based on selection state
        if self.is_selection_valid():
            self.context_menu.addAction("编辑选区", self._edit_selection)

            # 创建保存选区子菜单
            save_menu = self.context_menu.addMenu("保存选区")
            save_menu.addAction("保存图片到节点", self._save_image_to_node)
            save_menu.addAction("保存ROI到节点", self._save_roi_to_node)
            save_menu.addAction("保存Target到节点", self._save_target_to_node)

            self.context_menu.addAction("清除选区", self.clear_selection)
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

        # 发射信号（假设信号定义为带参数：str）
        if relative_path:
            self.NodeChangeSignal.emit("template", relative_path)

    def _save_roi_to_node(self):
        """保存选区ROI到节点"""
        if not self.is_selection_valid():
            return

        # 获取ROI数据
        roi_data = self.get_roi_data()
        if not roi_data:
            return

        # 发送信号
        self.NodeChangeSignal.emit("roi", roi_data)

    def _save_target_to_node(self):
        """保存选区为目标到节点"""
        if not self.is_selection_valid() or not self.original_pixmap:
            return

        try:
            target_data = self.get_roi_data()
            if not target_data:
                return
            # 发送信号
            self.NodeChangeSignal.emit("target", target_data)

        except (RuntimeError, AttributeError) as e:
            print(f"保存目标时发生错误: {e}")

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
                    base_filename = self.control.selected_node_name or file_name_without_ext
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