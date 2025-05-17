from typing import Dict, Tuple

from PIL.Image import Image
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QScrollArea, QFrame,
    QSplitter, QHBoxLayout, QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QSize
from PySide6.QtGui import QPixmap, QImage, QResizeEvent
from qasync import asyncSlot

from src.maafw import maafw, cvmat_to_image


class RecoData:
    """存储识别数据的类"""
    data: Dict[int, Tuple[str, bool]] = {}


class ImageContainer(QFrame):
    """固定宽度的图片容器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet(
            "background-color: white; border: 1px solid #dddddd; padding: 5px; margin: 2px;")

        # 基本布局
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(5)

        # 图片标签
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.image_label.setScaledContents(True)
        self.layout.addWidget(self.image_label)

        # 原始图片和缩放图片
        self._pixmap = None

        # 优化处理大小变化
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._delayed_resize)

    def setPixmap(self, pixmap):
        """设置图片"""
        self._pixmap = pixmap
        self._update_image_size()

    def _update_image_size(self):
        """更新图片尺寸"""
        if self._pixmap:
            # 计算合适的图片尺寸，保持宽高比
            pixmap_ratio = self._pixmap.height() / max(1, self._pixmap.width())
            # 留出一些边距
            container_width = self.width() - 12
            target_height = int(container_width * pixmap_ratio)

            # 限制最大高度，避免图片过大
            max_height = 800  # 设置一个合理的最大高度值
            if target_height > max_height:
                target_height = max_height
                container_width = int(max_height / pixmap_ratio)

            # 设置图片标签大小
            self.image_label.setFixedSize(container_width, target_height)

            # 设置图片
            self.image_label.setPixmap(self._pixmap.scaled(
                container_width,
                target_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))

    def _delayed_resize(self):
        """延迟处理大小变化，避免频繁更新"""
        self._update_image_size()

    def resizeEvent(self, event):
        """处理容器大小变化"""
        super().resizeEvent(event)
        # 使用计时器延迟更新，避免频繁调用
        self._resize_timer.start(100)

    def sizeHint(self):
        """提供合适的大小提示"""
        if self._pixmap:
            # 根据图片比例提供合适的大小提示
            pixmap_ratio = self._pixmap.height() / max(1, self._pixmap.width())
            hint_width = self.width()
            hint_height = int(hint_width * pixmap_ratio) + 20  # 添加边距
            return QSize(hint_width, hint_height)
        return super().sizeHint()

class RecoDetailView(QWidget):
    """识别详情视图，展示图片和识别数据"""

    # 获取详情信号
    fetch_detail_signal = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 主布局（减少边距）
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(3, 3, 3, 3)  # 减少边距
        self.layout.setSpacing(3)  # 减少间距

        # 修改部分: 标题标签设置为固定高度并优化样式
        self.title_label = QLabel("Recognition Details")
        self.title_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        self.title_label.setFixedHeight(30)  # 设置固定高度
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # 垂直居中，左对齐
        self.layout.addWidget(self.title_label)

        # 加载指示器（简化）
        self.loading_frame = QFrame()
        self.loading_frame.setStyleSheet("background-color: #f0f0f0; border-radius: 4px; padding: 10px;")
        loading_layout = QVBoxLayout(self.loading_frame)
        loading_label = QLabel("Getting results...")
        loading_label.setAlignment(Qt.AlignCenter)
        loading_label.setStyleSheet("font-size: 12pt; color: #555555;")
        loading_layout.addWidget(loading_label)
        self.layout.addWidget(self.loading_frame)
        self.loading_frame.hide()

        # 创建直接在主布局中的分隔器
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(6)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #dddddd; border-radius: 3px; }")

        # 左侧：图片滚动区域（直接放在分隔器中）
        self.image_scroll = QScrollArea()
        # 只允许垂直方向调整大小
        self.image_scroll.setWidgetResizable(True)
        self.image_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.image_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #dddddd; background-color: white; border-radius: 4px; }")

        # 图片容器
        self.image_container = QWidget()
        self.image_layout = QVBoxLayout(self.image_container)
        self.image_layout.setAlignment(Qt.AlignTop)
        self.image_layout.setSpacing(10)
        self.image_layout.setContentsMargins(5, 5, 5, 5)
        self.image_scroll.setWidget(self.image_container)

        # 默认"无图片"标签
        self.no_images_label = QLabel("None")
        self.no_images_label.setAlignment(Qt.AlignCenter)
        self.no_images_label.setStyleSheet("font-size: 14pt; color: #888888; padding: 20px;")
        self.image_layout.addWidget(self.no_images_label)

        # 右侧：占位框架（不实现数据显示部分）
        self.right_frame = QFrame()
        self.right_frame.setStyleSheet("background-color: white; border-radius: 4px; border: 1px solid #dddddd;")

        # 将两侧添加到分隔器
        self.splitter.addWidget(self.image_scroll)
        self.splitter.addWidget(self.right_frame)

        # 设置初始大小（1:1比例）
        self.splitter.setSizes([500, 500])

        # 将分隔器添加到主布局
        self.layout.addWidget(self.splitter)

        # 当前识别ID缓存
        self.current_reco_id = None

        # 连接信号到槽
        self.fetch_detail_signal.connect(self.handle_detail_fetch)

        # 连接分隔器的移动信号
        self.splitter.splitterMoved.connect(self._handle_splitter_moved)

        # 缓存图片
        self._image_cache = {}

        # 延迟处理窗口大小变化
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._update_container_widths)

    def _handle_splitter_moved(self, pos, index):
        """处理分隔器移动事件"""
        # 更新容器宽度和图片大小
        self._update_container_widths()


    def resizeEvent(self, event):
        """处理窗口大小变化"""
        super().resizeEvent(event)
        # 使用计时器延迟更新，避免频繁调用
        self._resize_timer.start(200)

    def _update_container_widths(self):
        """更新所有图片容器的宽度"""
        # 计算合适的容器宽度 - 直接使用滚动区域视口宽度
        scroll_width = self.image_scroll.viewport().width()
        container_width = scroll_width - 20  # 减去一些边距

        # 更新所有图片容器
        for i in range(self.image_layout.count()):
            item = self.image_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ImageContainer):
                container = item.widget()
                container.setFixedWidth(container_width)

                # 如果容器有图片，强制重新计算图片大小
                if container._pixmap:
                    container.setPixmap(container._pixmap)

    def clear(self):
        """清除所有显示的数据"""
        self.title_label.setText("Recognition Details")

        # 清除图片
        for i in reversed(range(self.image_layout.count())):
            item = self.image_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()

        # 添加回"无图片"标签
        self.no_images_label = QLabel("None")
        self.no_images_label.setAlignment(Qt.AlignCenter)
        self.no_images_label.setStyleSheet("font-size: 14pt; color: #888888; padding: 20px;")
        self.image_layout.addWidget(self.no_images_label)

        # 隐藏加载指示器
        self.loading_frame.hide()

        # 清除图片缓存
        self._image_cache.clear()

    def update_details(self, reco_id: int):
        """更新特定识别ID的详情"""
        self.current_reco_id = reco_id

        # 从RecoData获取基本信息
        name, hit = RecoData.data.get(reco_id, ("Unknown", False))
        # 更新标题和状态指示器
        title = f"{'✅' if hit else '❌'} {name} ({reco_id})"
        self.title_label.setText(title)

        # 显示加载指示器
        self.loading_frame.show()

        # 清除现有图片显示
        for i in reversed(range(self.image_layout.count())):
            item = self.image_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()

        # 添加临时"加载中"标签
        loading_img_label = QLabel("Loading images...")
        loading_img_label.setAlignment(Qt.AlignCenter)
        loading_img_label.setStyleSheet("font-size: 12pt; color: #888888; padding: 20px;")
        self.image_layout.addWidget(loading_img_label)

        # 发射信号获取详情
        self.fetch_detail_signal.emit(reco_id)

    @asyncSlot(int)
    async def handle_detail_fetch(self, reco_id: int):
        """处理获取详情的槽函数"""
        try:
            # 检查是否与当前请求的ID匹配
            if reco_id != self.current_reco_id:
                return

            # 异步获取识别详情
            details = await maafw.get_reco_detail(reco_id)

            # 检查是否仍然是当前请求的ID
            if reco_id != self.current_reco_id:
                return

            # 更新UI（在主线程上）
            self.update_ui_with_details(details)
        except Exception as e:
            print(f"Error fetching recognition details: {e}")
            # 出错时更新UI
            if reco_id == self.current_reco_id:
                self.update_ui_with_details(None)

    def update_ui_with_details(self, details):
        """使用获取的详情更新UI"""
        # 隐藏加载指示器
        self.loading_frame.hide()

        # 清除图片
        for i in reversed(range(self.image_layout.count())):
            item = self.image_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()

        if details is None:
            # 获取详情失败，显示错误提示
            error_label = QLabel("Failed to load details")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("font-size: 14pt; color: #ff5555; padding: 20px;")
            self.image_layout.addWidget(error_label)
            return
        print(details.raw_detail)

        # 处理 raw_detail 数据
        self._update_detail_table(details.raw_detail)
        # 显示图片
        if hasattr(details, 'draw_images') and details.draw_images and len(details.draw_images) > 0:
            # 使用QTimer延迟加载每张图片，减轻UI线程负担
            self._load_images(details.draw_images)
        else:
            # 添加回"无图片"标签
            self.no_images_label = QLabel("None")
            self.no_images_label.setAlignment(Qt.AlignCenter)
            self.no_images_label.setStyleSheet("font-size: 14pt; color: #888888; padding: 20px;")
            self.image_layout.addWidget(self.no_images_label)

    def _update_detail_table(self, raw_detail):
        """更新详细数据表格"""

        # 创建表格标签区域，用于放置表格说明信息
        if not hasattr(self, 'table_container'):
            self.table_container = QWidget()
            self.table_container_layout = QVBoxLayout(self.table_container)
            self.table_container_layout.setContentsMargins(3, 3, 3, 3)
            self.table_container_layout.setSpacing(2)

            # 创建表格上方的标签，用于显示颜色说明
            self.table_label = QLabel()
            self.table_label.setStyleSheet("""
                font-size: 11pt; 
                padding: 8px 10px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f8f8f8, stop:1 #f0f0f0);
                border-radius: 4px;
                border: 1px solid #dcdcdc;
                color: #444444;
                font-weight: normal;
                margin-bottom: 4px;
            """)
            self.table_container_layout.addWidget(self.table_label)

            # 创建表格实例
            self.detail_table = QTableWidget()
            self.detail_table.setStyleSheet("""
                QTableWidget {
                    border: 1px solid #dddddd;
                    gridline-color: #dddddd;
                    background-color: white;
                    alternate-background-color: #f9f9f9;
                }
                QHeaderView::section {
                    background-color: #f0f0f0;
                    padding: 4px;
                    border: 1px solid #dddddd;
                    font-weight: bold;
                }
            """)
            self.table_container_layout.addWidget(self.detail_table)

            # 替换右侧框架
            if self.right_frame:
                index = self.splitter.indexOf(self.right_frame)
                self.right_frame.hide()
                self.right_frame.deleteLater()
                self.right_frame = self.table_container
                self.splitter.insertWidget(index, self.table_container)

        # 更新表格标签内容，添加颜色说明
        self.table_label.setText("""
            <table style='border-collapse: separate; border-spacing: 10px 0px;'>
                <tr>
                    <td style='text-align: center; font-weight: bold;'>颜色标记说明:</td>
                    <td>
                        <div style='
                            display: inline-block; 
                            width: 16px; 
                            height: 16px; 
                            background-color: #00c853; 
                            border-radius: 3px; 
                            vertical-align: middle; 
                            border: 1px solid #00a040;
                            margin-right: 5px;
                        '></div>
                        <span style='vertical-align: middle; font-weight: bold;'>best</span>
                    </td>
                    <td>
                        <div style='
                            display: inline-block; 
                            width: 16px; 
                            height: 16px; 
                            background-color: #ffd600; 
                            border-radius: 3px; 
                            vertical-align: middle; 
                            border: 1px solid #c7a500;
                            margin-right: 5px;
                        '></div>
                        <span style='vertical-align: middle; font-weight: bold;'>filter</span>
                    </td>
                </tr>
            </table>
        """)

        # 检查是否有有效数据
        if not raw_detail or 'all' not in raw_detail or not raw_detail['all']:
            # 如果没有数据，创建简单表格
            # 清除并设置表格
            self.detail_table.clear()  # 清除所有内容但保留结构
            self.detail_table.setColumnCount(1)
            self.detail_table.setRowCount(1)

            # 确保表头可见
            self.detail_table.horizontalHeader().setVisible(True)
            self.detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

            # 设置无数据消息
            item = QTableWidgetItem("No detail data available")
            item.setTextAlignment(Qt.AlignCenter)
            self.detail_table.setItem(0, 0, item)

            return

        # 获取所有可能的字段（动态收集所有项目的所有字段）
        all_fields = set()
        for item in raw_detail['all']:
            all_fields.update(item.keys())

        fields = sorted(list(all_fields))  # 对字段进行排序，使表头更有序

        # 清除现有内容
        self.detail_table.clear()  # 使用clear()而不是单独设置行列数为0

        # 重新设置表格大小
        self.detail_table.setColumnCount(len(fields) + 1)  # +1 是为了添加序号列
        self.detail_table.setRowCount(len(raw_detail['all']))

        # 设置表头标签 - 添加序号列和字段列
        header_labels = ['序号'] + fields
        self.detail_table.setHorizontalHeaderLabels(header_labels)

        # 确保表头可见
        self.detail_table.horizontalHeader().setVisible(True)

        # 提取 best 和 filtered 信息，用于高亮显示
        best_item = raw_detail.get('best', {})
        filtered_items = raw_detail.get('filtered', [])

        # 用于比较项目的函数
        def items_match(item1, item2):
            """比较两个项目是否匹配（基于关键字段）"""
            if not item1 or not item2:
                return False

            # 比较关键字段（如 box, text 等）
            for key in ['box', 'text']:
                if key in item1 and key in item2 and item1[key] != item2[key]:
                    return False
            return True

        # 填充表格
        from PySide6.QtGui import QBrush

        for row, item in enumerate(raw_detail['all']):
            # 确定状态
            is_filtered = any(items_match(item, f_item) for f_item in filtered_items)
            is_best = items_match(item, best_item)

            # 设置背景色
            if is_best:
                bg_color_alpha = Qt.green
            elif is_filtered:
                bg_color_alpha = Qt.yellow
            else:
                bg_color_alpha = None

            # 添加序号列
            seq_item = QTableWidgetItem(str(row + 1))
            seq_item.setTextAlignment(Qt.AlignCenter)
            if bg_color_alpha:
                seq_item.setBackground(QBrush(bg_color_alpha))
            self.detail_table.setItem(row, 0, seq_item)

            # 填充每一列字段数据
            for col, field in enumerate(fields):
                table_col = col + 1  # 实际列索引 (加1是因为第0列是序号)

                if field in item:
                    value = item[field]
                    item_widget = QTableWidgetItem(str(value))
                else:
                    item_widget = QTableWidgetItem("")

                # 设置文本对齐方式
                item_widget.setTextAlignment(Qt.AlignCenter)

                # 如果需要设置背景色
                if bg_color_alpha:
                    item_widget.setBackground(QBrush(bg_color_alpha))

                # 将项目添加到表格
                self.detail_table.setItem(row, table_col, item_widget)

        # 优化表格显示
        self.detail_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 序号列自适应内容宽度
        for i in range(1, self.detail_table.columnCount()):
            self.detail_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)  # 其他列伸展

        self.detail_table.verticalHeader().setVisible(False)  # 隐藏行标题
        self.detail_table.setAlternatingRowColors(True)  # 交替行颜色
        self.detail_table.setSortingEnabled(True)  # 启用排序

        # 调整行高
        for row in range(self.detail_table.rowCount()):
            self.detail_table.setRowHeight(row, 30)

    def _load_images(self, images):
        """分批加载图片，避免UI卡顿"""
        if not images:
            return

        # 添加信息标签
        info_label = QLabel(f"Showing {len(images)} images")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("font-size: 12pt; color: #555555; padding: 5px;")
        self.image_layout.addWidget(info_label)

        # 创建加载队列
        self._image_queue = list(enumerate(images))
        self._load_next_batch()

    def _load_next_batch(self, batch_size=2):
        """加载下一批图片"""
        if not self._image_queue:
            return

        # 计算容器宽度（滚动区域宽度减去内边距）
        container_width = self.image_scroll.viewport().width() - 20

        # 最多加载batch_size张图片
        for _ in range(min(batch_size, len(self._image_queue))):
            if not self._image_queue:
                break

            idx, img = self._image_queue.pop(0)
            try:
                # 创建新的图片容器
                image_container = ImageContainer()
                image_container.setFixedWidth(container_width)
                self.image_layout.addWidget(image_container)

                # 转换图片并设置
                image = cvmat_to_image(img)
                pixmap = self.cvmat_to_pixmap(image)
                image_container.setPixmap(pixmap)

            except Exception as e:
                print(f"Error loading image {idx}: {e}")
                error_label = QLabel(f"Failed to load image {idx}")
                error_label.setAlignment(Qt.AlignCenter)
                error_label.setStyleSheet("color: #ff5555; padding: 5px;")
                self.image_layout.addWidget(error_label)

        # 如果还有图片，延迟加载下一批
        if self._image_queue:
            QTimer.singleShot(50, self._load_next_batch)

        # 添加一个弹性空间到布局最后，确保图片不会被拉伸
        if not self._image_queue and not self.image_layout.itemAt(self.image_layout.count() - 1).spacerItem():
            self.image_layout.addStretch(1)

    def cvmat_to_pixmap(self, pil_image):
        """将PIL图像转换为QPixmap，带缓存机制"""
        # 生成图片唯一ID（使用内存地址）
        img_id = id(pil_image)

        # 检查缓存
        if img_id in self._image_cache:
            return self._image_cache[img_id]

        # 确保图像不超过合理大小
        MAX_SIZE = 1200  # 设置最大尺寸
        if pil_image.width > MAX_SIZE or pil_image.height > MAX_SIZE:
            # 保持宽高比缩小图片
            ratio = min(MAX_SIZE / pil_image.width, MAX_SIZE / pil_image.height)
            new_width = int(pil_image.width * ratio)
            new_height = int(pil_image.height * ratio)
            pil_image = pil_image.resize((new_width, new_height))

        # 转换为QImage
        if pil_image.mode == "RGB":
            qimage = QImage(pil_image.tobytes(), pil_image.width, pil_image.height,
                            pil_image.width * 3, QImage.Format_RGB888)
        elif pil_image.mode == "RGBA":
            qimage = QImage(pil_image.tobytes(), pil_image.width, pil_image.height,
                            pil_image.width * 4, QImage.Format_RGBA8888)
        else:
            # 转换为RGB模式
            rgb_image = pil_image.convert("RGB")
            qimage = QImage(rgb_image.tobytes(), rgb_image.width, rgb_image.height,
                            rgb_image.width * 3, QImage.Format_RGB888)

        # 创建QPixmap
        pixmap = QPixmap.fromImage(qimage)

        # 缓存结果
        self._image_cache[img_id] = pixmap
        return pixmap