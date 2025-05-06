from PIL.Image import Image
from PIL.ImageQt import QImage
from PySide6.QtCore import Qt, Signal, QPoint, QRectF, QPointF, QTimer
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtWidgets import (QMenu, QGraphicsView, QGraphicsScene,
                               QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsItem,
                               QApplication)


class SelectionRect(QGraphicsRectItem):
    """Selection rectangle with info display"""

    def __init__(self):
        super().__init__()
        self.setPen(QPen(QColor(255, 0, 0), 2, Qt.SolidLine))
        self.setBrush(QBrush(QColor(255, 0, 0, 40)))
        self.setZValue(100)  # Ensure it's on top
        self.setFlag(QGraphicsItem.ItemIsMovable, False)

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
                        # Calculate relative coordinates (0-1 range)
                        pixmap_scene_pos = pixmap_item.scenePos()
                        rel_x1 = (scene_rect.left() - pixmap_scene_pos.x()) / pixmap_rect.width()
                        rel_y1 = (scene_rect.top() - pixmap_scene_pos.y()) / pixmap_rect.height()
                        rel_x2 = (scene_rect.right() - pixmap_scene_pos.x()) / pixmap_rect.width()
                        rel_y2 = (scene_rect.bottom() - pixmap_scene_pos.y()) / pixmap_rect.height()

                        # Get zoom factor directly from view's method for consistency
                        zoom_factor = view.get_zoom_factor()
                        zoom = int(zoom_factor * 100)  # Convert to percentage and ensure integer value

                        # Draw info panel
                        info_width = 200
                        info_height = 130
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

                        text = (f"选择区域信息:\n"
                                f"起点: ({int(scene_rect.x())}, {int(scene_rect.y())})\n"
                                f"终点: ({int(scene_rect.right())}, {int(scene_rect.bottom())})\n"
                                f"大小: {int(scene_rect.width())} x {int(scene_rect.height())}\n"
                                f"图像坐标:\n"
                                f"({rel_x1:.3f}, {rel_y1:.3f}) - "
                                f"({rel_x2:.3f}, {rel_y2:.3f})\n"
                                f"缩放: {zoom}%")

                        painter.drawText(info_x + 10, info_y + 10, info_width - 20, info_height - 20,
                                         Qt.AlignLeft, text)

                        # Restore painter state
                        painter.restore()


class DeviceImageView(QGraphicsView):
    """Enhanced graphics view for device images with intuitive zooming and panning"""

    # Signals
    selectionChanged = Signal(QRectF)
    selectionCleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

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

    def clear_selection(self):
        """Clear current selection"""
        if self.selection_rect:
            self.scene.removeItem(self.selection_rect)
            self.selection_rect = None
            self.selectionCleared.emit()

    def get_selection(self):
        """Get the current selection in scene coordinates"""
        if not self.selection_rect:
            return None
        rect = self.selection_rect.rect().normalized()
        return self.selection_rect.mapToScene(rect).boundingRect()

    def get_normalized_selection(self):
        """Get the selection as normalized coordinates (0-1 range)"""
        if not self.selection_rect or not self.pixmap_item:
            return None

        # Get selection in scene coordinates
        sel_rect = self.get_selection()

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

        return None

    def constrain_to_pixmap(self, scene_pos):
        """将场景坐标限制在图片范围内"""
        if not self.pixmap_item:
            return scene_pos

        # 获取图片在场景中的边界
        pixmap_rect = self.pixmap_item.mapToScene(
            self.pixmap_item.boundingRect()
        ).boundingRect()

        # 限制坐标到图片边界
        constrained_x = max(pixmap_rect.left(), min(scene_pos.x(), pixmap_rect.right()))
        constrained_y = max(pixmap_rect.top(), min(scene_pos.y(), pixmap_rect.bottom()))

        return QPointF(constrained_x, constrained_y)

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
            pixmap_scene_pos = self.pixmap_item.mapToScene(
                self.pixmap_item.boundingRect()
            ).boundingRect()

            if pixmap_scene_pos.contains(scene_pos):
                self.is_selecting = True
                self.selection_start = scene_pos

                # Create new selection rectangle if it doesn't exist
                if not self.selection_rect:
                    self.selection_rect = SelectionRect()
                    self.scene.addItem(self.selection_rect)

                # Initialize with zero rect at start point
                self.selection_rect.setRect(QRectF(0, 0, 0, 0))
                self.selection_rect.setPos(scene_pos)
                return

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
        if self.is_selecting and self.selection_rect:
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

        # Panning in progress
        if self._panning and self._last_pan_pos:
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

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release events"""
        # End selection
        if self.is_selecting and event.button() == Qt.LeftButton:
            self.is_selecting = False
            if self.selection_rect and not self.selection_rect.rect().isEmpty():
                self.selectionChanged.emit(self.get_selection())

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
        if self.selection_rect:
            self.context_menu.addAction("复制选区", self._copy_selection)
            self.context_menu.addAction("保存选区", self._save_selection)
            self.context_menu.addAction("清除选区", self.clear_selection)
        else:
            self.context_menu.addAction("全选", self._select_all)
            self.context_menu.addAction("重置视图", self.reset_view)

        # Common options
        self.context_menu.addSeparator()
        self.context_menu.addAction(f"选择模式: {'开' if self.selection_mode else '关'}",
                                    lambda: self.toggle_selection_mode(not self.selection_mode))

        # 添加缩放选项
        self.context_menu.addSeparator()
        zoom_menu = self.context_menu.addMenu("缩放")
        for zoom in [25, 50, 75, 100, 125, 150, 200, 300]:
            zoom_menu.addAction(f"{zoom}%", lambda z=zoom / 100: self.zoom_to_factor(z))

        # Show menu
        self.context_menu.exec(self.mapToGlobal(pos))

    # Context menu actions
    def _copy_selection(self):
        """Copy selection to clipboard"""
        if not self.selection_rect or not self.original_pixmap:
            return

        # Get normalized selection
        norm_rect = self.get_normalized_selection()
        if not norm_rect:
            return

        # Extract from original pixmap
        pixmap_rect = self.original_pixmap.rect()
        x = int(norm_rect.x() * pixmap_rect.width())
        y = int(norm_rect.y() * pixmap_rect.height())
        w = int(norm_rect.width() * pixmap_rect.width())
        h = int(norm_rect.height() * pixmap_rect.height())

        # Create cropped pixmap
        cropped = self.original_pixmap.copy(x, y, w, h)

        # Copy to clipboard
        QApplication.clipboard().setPixmap(cropped)

    def _save_selection(self):
        """Save selection to file"""
        # TODO: Implement file save dialog and saving functionality
        pass

    def _select_all(self):
        """Select the entire image"""
        if not self.pixmap_item:
            return

        # Enable selection mode
        self.selection_mode = True

        # Create selection rect if needed
        if not self.selection_rect:
            self.selection_rect = SelectionRect()
            self.scene.addItem(self.selection_rect)

        # Set to full image bounds
        self.selection_rect.setRect(QRectF(self.pixmap_item.boundingRect()))
        self.selection_rect.setPos(self.pixmap_item.pos())

        # Emit signal
        self.selectionChanged.emit(self.get_selection())
