from PIL.Image import Image
from PIL.ImageQt import QImage
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QFont, QTransform, QCursor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QFormLayout, QLineEdit, QPushButton, QComboBox,
                               QToolBar, QSplitter, QStackedWidget, QGroupBox,
                               QScrollArea, QMenu, QGraphicsView, QGraphicsScene,
                               QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsItem,
                               QApplication)
from PySide6.QtCore import Qt, Signal, QThread, QRect, QPoint, QRectF, QPointF, QSize, QMarginsF, QTimer
from maa.toolkit import Toolkit
from qasync import asyncSlot

from src.maafw import maafw


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
        self.zoom_sensitivity = 0.1
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
            # Check if click is on the image
            if self.pixmap_item.contains(self.pixmap_item.mapFromScene(scene_pos)):
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
            scene_pos = self.mapToScene(event.pos())

            # Calculate rectangle from start to current position
            rect = QRectF(self.selection_start, scene_pos).normalized()

            # Adjust to be relative to the rect's position
            local_rect = QRectF(
                0, 0,
                rect.width(),
                rect.height()
            )

            # Position rect and set its bounds
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

        # Get zoom direction
        zoom_in = event.angleDelta().y() > 0

        # Perform zoom
        self.zoom_by_delta(0.2 if zoom_in else -0.2)

        # Prevent default wheel behavior
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


class DeviceSearchThread(QThread):
    """用于后台搜索设备的线程"""
    devices_found = Signal(list)
    search_error = Signal(str)

    def __init__(self, search_type):
        super().__init__()
        self.search_type = search_type

    def run(self):
        try:
            # 搜索设备
            devices = []
            if self.search_type == "ADB":
                devices = Toolkit.find_adb_devices()
            elif self.search_type == "WIN32":
                devices = Toolkit.find_desktop_windows()
                devices = [device for device in devices if device.window_name != '']
            print(devices)
            self.devices_found.emit(devices)
        except Exception as e:
            self.search_error.emit(str(e))


class ControllerView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 初始化状态变量
        self.found_devices = []
        self.select_device = None
        self.selection_mode = False
        self.is_connected = False
        self.left_panel_collapsed = False

        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 分割器
        self.splitter = QSplitter(Qt.Horizontal)

        # 左侧控制面板
        self.setup_left_panel()

        # 右侧视图面板
        self.setup_right_panel()

        # 将左右面板添加到分割器
        self.splitter.addWidget(self.left_widget)
        self.splitter.addWidget(self.right_widget)
        # 设置分割器比例
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)

        # 添加到主布局
        main_layout.addWidget(self.splitter)

        # 创建右键菜单
        self.context_menu = QMenu(self)

    def setup_left_panel(self):
        """设置左侧控制面板"""
        self.left_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_widget)
        self.left_layout.setContentsMargins(10, 10, 10, 10)
        self.left_layout.setSpacing(15)

        # 标题
        title_label = QLabel("控制器设置")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.left_layout.addWidget(title_label)

        # 设备类型组
        device_type_group = QGroupBox("设备类型")
        dt_layout = QFormLayout(device_type_group)
        dt_layout.setLabelAlignment(Qt.AlignRight)
        self.device_type_combo = QComboBox()
        self.device_type_combo.addItem("ADB设备", "ADB")
        self.device_type_combo.addItem("Win32窗口", "WIN32")
        self.device_type_combo.currentIndexChanged.connect(self.device_type_changed)
        dt_layout.addRow(QLabel("控制器类型:"), self.device_type_combo)
        self.left_layout.addWidget(device_type_group)

        # 设备搜索组
        search_group = QGroupBox("设备搜索")
        search_layout = QFormLayout(search_group)
        search_layout.setLabelAlignment(Qt.AlignRight)
        search_layout.setContentsMargins(5, 5, 5, 5)
        search_layout.setSpacing(10)

        # 搜索按钮行
        btn_layout = QHBoxLayout()
        self.search_btn = QPushButton("搜索设备")
        self.search_btn.clicked.connect(self.search_devices)
        self.search_status = QLabel("未搜索")
        btn_layout.addWidget(self.search_btn)
        btn_layout.addWidget(self.search_status)
        btn_layout.addStretch()
        search_layout.addRow(btn_layout)

        # 设备下拉框
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(200)
        self.device_combo.currentIndexChanged.connect(self.device_selected)
        search_layout.addRow(QLabel("发现的设备:"), self.device_combo)
        self.left_layout.addWidget(search_group)

        # 设备配置组
        self.config_group = QGroupBox("设备配置")
        cfg_layout = QVBoxLayout(self.config_group)
        cfg_layout.setContentsMargins(5, 5, 5, 5)

        # 配置栈
        self.controller_stack = QStackedWidget()

        # ADB配置页面
        adb_page = QWidget()
        adb_form = QFormLayout(adb_page)
        adb_form.setLabelAlignment(Qt.AlignRight)
        self.adb_path_edit = QLineEdit()
        self.adb_address_edit = QLineEdit()
        self.config_edit = QLineEdit()
        adb_form.addRow("ADB 路径:", self.adb_path_edit)
        adb_form.addRow("ADB 地址:", self.adb_address_edit)
        adb_form.addRow("配置:", self.config_edit)
        self.controller_stack.addWidget(adb_page)

        # Win32配置页面
        win32_page = QWidget()
        win32_form = QFormLayout(win32_page)
        win32_form.setLabelAlignment(Qt.AlignRight)
        self.hwnd_edit = QLineEdit()
        self.input_method_combo = QComboBox()
        self.input_method_combo.addItem("Seize", 1)
        self.input_method_combo.addItem("SendMessage", 2)
        self.screenshot_method_combo = QComboBox()
        self.screenshot_method_combo.addItem("GDI", 1)
        self.screenshot_method_combo.addItem("FramePool", 2)
        self.screenshot_method_combo.addItem("DXGI_DesktopDup", 3)
        win32_form.addRow("窗口句柄 (hWnd):", self.hwnd_edit)
        win32_form.addRow("输入方法:", self.input_method_combo)
        win32_form.addRow("截图方法:", self.screenshot_method_combo)
        self.controller_stack.addWidget(win32_page)

        cfg_layout.addWidget(self.controller_stack)
        self.left_layout.addWidget(self.config_group)

        # 连接/断开按钮
        btn_connect = QPushButton("连接设备")
        btn_connect.clicked.connect(self.connect_device)
        btn_disconnect = QPushButton("断开连接")
        btn_disconnect.clicked.connect(self.disconnect_device)
        self.left_layout.addWidget(btn_connect)
        self.left_layout.addWidget(btn_disconnect)
        self.left_layout.addStretch()

    def setup_right_panel(self):
        """设置右侧视图面板"""
        self.right_widget = QWidget()
        right_layout = QVBoxLayout(self.right_widget)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(10)

        # 工具栏布局
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(10)

        # 切换面板按钮
        self.toggle_panel_btn = QPushButton("<<")
        self.toggle_panel_btn.setFixedWidth(30)
        self.toggle_panel_btn.setToolTip("折叠/展开控制面板")
        self.toggle_panel_btn.clicked.connect(self.toggle_left_panel)
        toolbar_layout.addWidget(self.toggle_panel_btn)

        # 连接状态标签
        self.connection_status = QLabel("未连接")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        toolbar_layout.addWidget(self.connection_status)

        # 工具栏
        toolbar = QToolBar()
        toolbar_layout.addWidget(toolbar)

        # 截图按钮
        self.screenshot_action = toolbar.addAction("截图")
        self.screenshot_action.triggered.connect(self.update_device_img)

        # 选择区域按钮
        self.select_area_action = toolbar.addAction("选择区域:关")
        self.select_area_action.triggered.connect(self.toggle_selection_mode)

        right_layout.addLayout(toolbar_layout)

        # 重置视图按钮
        zoom_layout = QHBoxLayout()
        zoom_layout.setContentsMargins(0, 0, 0, 0)
        zoom_layout.setSpacing(10)

        self.reset_view_btn = QPushButton("重置视图")
        self.reset_view_btn.clicked.connect(self.reset_view)
        zoom_layout.addStretch()
        zoom_layout.addWidget(self.reset_view_btn)

        right_layout.addLayout(zoom_layout)

        # 创建并添加设备图像视图
        self.device_view = DeviceImageView()
        self.device_view.selectionChanged.connect(self.on_selection_changed)
        self.device_view.selectionCleared.connect(self.on_selection_cleared)
        right_layout.addWidget(self.device_view)

    def toggle_left_panel(self):
        """切换左侧面板显示/隐藏"""
        self.left_panel_collapsed = not self.left_panel_collapsed

        if self.left_panel_collapsed:
            self.left_widget.setMaximumWidth(0)
            self.toggle_panel_btn.setText(">>")
        else:
            self.left_widget.setMaximumWidth(16777215)  # 最大值
            self.toggle_panel_btn.setText("<<")

    def device_type_changed(self, index):
        """当控制器类型变更时的处理函数"""
        self.controller_stack.setCurrentIndex(index)
        self.device_combo.clear()
        self.search_status.setText("未搜索")
        self.found_devices = []

    def search_devices(self):
        """搜索设备"""
        self.search_btn.setEnabled(False)
        self.search_status.setText("正在搜索...")
        self.device_combo.clear()

        device_type = self.device_type_combo.currentData()
        self.search_thread = DeviceSearchThread(device_type)
        self.search_thread.devices_found.connect(self.on_devices_found)
        self.search_thread.search_error.connect(self.on_search_error)
        self.search_thread.finished.connect(self.on_search_completed)
        self.search_thread.start()

    def on_devices_found(self, devices):
        """处理找到的设备"""
        self.device_combo.clear()
        self.found_devices = devices
        if devices:
            for device in devices:
                if hasattr(device, 'address'):  # ADB设备
                    text = f"{device.name} - {device.address}"
                elif hasattr(device, 'hwnd'):  # WIN32窗口
                    text = f"{device.window_name} - {device.hwnd}"
                else:
                    text = str(device)
                self.device_combo.addItem(text)
            self.search_status.setText(f"找到 {len(devices)} 个设备")
        else:
            self.device_combo.addItem("未找到设备")
            self.search_status.setText("未找到设备")

    def on_search_error(self, error_msg):
        """处理搜索错误"""
        self.device_combo.clear()
        self.device_combo.addItem("搜索出错")
        self.search_status.setText(f"搜索出错: {error_msg}")

    def on_search_completed(self):
        """搜索完成后的处理"""
        self.search_btn.setEnabled(True)
        self.search_thread = None

    def device_selected(self, index):
        """当选择设备时填充相应字段"""
        if 0 <= index < len(self.found_devices):
            device = self.found_devices[index]
            device_type = self.device_type_combo.currentData()
            self.select_device = device

            if device_type == "ADB":
                # 填充ADB设备字段
                if device.address:
                    self.adb_address_edit.setText(str(device.address))
                if device.adb_path:
                    self.adb_path_edit.setText(str(device.adb_path))
                if device.config:
                    self.config_edit.setText(str(device.config))
            elif device_type == "WIN32":
                # 填充Win32设备字段
                if device.hwnd:
                    self.hwnd_edit.setText(str(device.hwnd))

    @asyncSlot()
    async def connect_device(self):
        """连接到指定设备"""
        try:
            device_type = self.device_type_combo.currentData()
            if device_type == "ADB":
                address = self.adb_address_edit.text()
                adb_path = self.adb_path_edit.text()
                config_text = self.config_edit.text()
                if config_text == "":
                    config_text = {}

                # 连接到ADB设备
                connected, error = await maafw.connect_adb(adb_path, address, config_text)
                if connected:
                    print(f"成功连接到ADB设备: {address}")
                    self.is_connected = True
                else:
                    print(f"连接ADB设备失败: {error}")
                    self.is_connected = False
            else:  # WIN32
                hwnd_text = self.hwnd_edit.text()
                input_method = self.input_method_combo.currentData()
                screenshot_method = self.screenshot_method_combo.currentData()

                # 连接到Win32窗口
                connected, error = await maafw.connect_win32hwnd(hwnd_text, screenshot_method, input_method)
                if connected:
                    print(f"成功连接到Win32窗口: {hwnd_text}")
                    self.is_connected = True
                else:
                    print(f"连接Win32窗口失败: {error}")
                    self.is_connected = False

            self.update_connection_status()

            if self.is_connected:
                await self.update_device_img()
        except Exception as e:
            print(f"连接设备时发生错误: {str(e)}")
            self.is_connected = False
            self.update_connection_status()

    def disconnect_device(self):
        """断开当前设备连接"""
        # 实现断开连接逻辑
        self.is_connected = False
        self.update_connection_status()
        print("断开设备连接")

    def update_connection_status(self):
        """更新连接状态标签"""
        if self.is_connected:
            self.connection_status.setText("已连接")
            self.connection_status.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.connection_status.setText("未连接")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")

    def toggle_selection_mode(self):
        """切换选择区域模式"""
        self.selection_mode = not self.selection_mode
        self.select_area_action.setText(f"选择区域:{'开' if self.selection_mode else '关'}")
        self.device_view.toggle_selection_mode(self.selection_mode)

    @asyncSlot()
    async def update_device_img(self):
        """更新设备截图"""
        img = await maafw.screencap()
        if img:
            self.display_image(img)

    def display_image(self, image):
        """在视图中显示图像"""
        if image is None:
            return

        self.device_view.set_image(image)

    def reset_view(self):
        """重置视图到原始状态"""
        self.device_view.reset_view()

    def on_selection_changed(self, rect):
        """当选择区域变化时"""
        # 可以在这里处理选择区域变化事件
        pass
    def on_selection_cleared(self):
        """当选择区域被清除时"""
        # 可以在这里处理选择区域清除事件
        pass