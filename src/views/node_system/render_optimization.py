# render_optimization.py
from typing import List, Set, Optional, Tuple, Dict, Any
from dataclasses import dataclass
from PySide6.QtCore import QRectF, QPointF, QObject, Signal, QTimer, QElapsedTimer
from PySide6.QtGui import QPainter, QTransform, QRegion
import math
import time


@dataclass
class QuadTreeNode:
    """四叉树节点"""
    bounds: QRectF
    level: int
    max_items: int = 10
    max_depth: int = 8

    def __post_init__(self):
        self.items: List[Any] = []
        self.children: List[Optional['QuadTreeNode']] = [None, None, None, None]
        self.is_leaf = True

    def insert(self, item: Any, item_bounds: QRectF) -> bool:
        """插入项目"""
        if not self.bounds.intersects(item_bounds):
            return False

        if self.is_leaf:
            self.items.append((item, item_bounds))

            # 检查是否需要分裂
            if len(self.items) > self.max_items and self.level < self.max_depth:
                self._subdivide()

            return True
        else:
            # 插入到子节点
            for child in self.children:
                if child and child.insert(item, item_bounds):
                    return True

        return False

    def remove(self, item: Any) -> bool:
        """移除项目"""
        if self.is_leaf:
            for i, (stored_item, _) in enumerate(self.items):
                if stored_item == item:
                    self.items.pop(i)
                    return True
        else:
            for child in self.children:
                if child and child.remove(item):
                    self._try_merge()
                    return True

        return False

    def query(self, search_bounds: QRectF) -> List[Any]:
        """查询区域内的项目"""
        results = []

        if not self.bounds.intersects(search_bounds):
            return results

        if self.is_leaf:
            for item, item_bounds in self.items:
                if search_bounds.intersects(item_bounds):
                    results.append(item)
        else:
            for child in self.children:
                if child:
                    results.extend(child.query(search_bounds))

        return results

    def _subdivide(self):
        """分裂节点"""
        self.is_leaf = False
        cx = self.bounds.center().x()
        cy = self.bounds.center().y()
        hw = self.bounds.width() / 2
        hh = self.bounds.height() / 2

        # 创建四个子节点
        self.children[0] = QuadTreeNode(
            QRectF(self.bounds.x(), self.bounds.y(), hw, hh),
            self.level + 1, self.max_items, self.max_depth
        )
        self.children[1] = QuadTreeNode(
            QRectF(cx, self.bounds.y(), hw, hh),
            self.level + 1, self.max_items, self.max_depth
        )
        self.children[2] = QuadTreeNode(
            QRectF(self.bounds.x(), cy, hw, hh),
            self.level + 1, self.max_items, self.max_depth
        )
        self.children[3] = QuadTreeNode(
            QRectF(cx, cy, hw, hh),
            self.level + 1, self.max_items, self.max_depth
        )

        # 重新分配项目
        old_items = self.items
        self.items = []

        for item, bounds in old_items:
            for child in self.children:
                if child.insert(item, bounds):
                    break

    def _try_merge(self):
        """尝试合并子节点"""
        if self.is_leaf:
            return

        total_items = 0
        for child in self.children:
            if child:
                if not child.is_leaf:
                    return  # 有非叶子节点，不能合并
                total_items += len(child.items)

        if total_items <= self.max_items:
            # 合并
            self.items = []
            for child in self.children:
                if child:
                    self.items.extend(child.items)
            self.children = [None, None, None, None]
            self.is_leaf = True


class SpatialIndex:
    """空间索引管理器"""

    def __init__(self, bounds: QRectF):
        self.bounds = bounds
        self.quad_tree = QuadTreeNode(bounds, 0)
        self.item_bounds: Dict[Any, QRectF] = {}

    def add_item(self, item: Any, bounds: QRectF):
        """添加项目"""
        self.item_bounds[item] = bounds
        self.quad_tree.insert(item, bounds)

    def remove_item(self, item: Any):
        """移除项目"""
        if item in self.item_bounds:
            del self.item_bounds[item]
            self.quad_tree.remove(item)

    def update_item(self, item: Any, new_bounds: QRectF):
        """更新项目位置"""
        if item in self.item_bounds:
            self.remove_item(item)
            self.add_item(item, new_bounds)

    def query_items(self, bounds: QRectF) -> List[Any]:
        """查询区域内的项目"""
        return self.quad_tree.query(bounds)

    def clear(self):
        """清空索引"""
        self.item_bounds.clear()
        self.quad_tree = QuadTreeNode(self.bounds, 0)


class DirtyRectManager:
    """脏矩形管理器"""

    def __init__(self):
        self.dirty_rects: List[QRectF] = []
        self.full_update = False

    def mark_dirty(self, rect: QRectF):
        """标记脏矩形"""
        if self.full_update:
            return

        # 合并重叠的矩形
        merged = False
        for i, existing in enumerate(self.dirty_rects):
            if existing.intersects(rect):
                self.dirty_rects[i] = existing.united(rect)
                merged = True
                break

        if not merged:
            self.dirty_rects.append(rect)

        # 如果脏矩形太多，标记全部更新
        if len(self.dirty_rects) > 20:
            self.mark_full_update()

    def mark_full_update(self):
        """标记全部更新"""
        self.full_update = True
        self.dirty_rects.clear()

    def get_dirty_region(self) -> Optional[QRegion]:
        """获取脏区域"""
        if self.full_update:
            return None

        if not self.dirty_rects:
            return QRegion()

        region = QRegion()
        for rect in self.dirty_rects:
            region += QRegion(rect.toRect())

        return region

    def clear(self):
        """清空脏矩形"""
        self.dirty_rects.clear()
        self.full_update = False


class LODManager:
    """细节层次管理器"""

    # LOD级别定义
    LOD_FULL = 0  # 完整细节
    LOD_MEDIUM = 1  # 中等细节
    LOD_LOW = 2  # 低细节
    LOD_MINIMAL = 3  # 最小细节

    def __init__(self):
        self.zoom_thresholds = {
            self.LOD_FULL: 0.5,  # >= 50% 缩放
            self.LOD_MEDIUM: 0.25,  # >= 25% 缩放
            self.LOD_LOW: 0.1,  # >= 10% 缩放
            self.LOD_MINIMAL: 0.0  # < 10% 缩放
        }

    def get_lod_level(self, zoom_factor: float) -> int:
        """根据缩放因子获取LOD级别"""
        for level in [self.LOD_FULL, self.LOD_MEDIUM, self.LOD_LOW]:
            if zoom_factor >= self.zoom_thresholds[level]:
                return level
        return self.LOD_MINIMAL

    def should_render_detail(self, detail_name: str, lod_level: int) -> bool:
        """判断是否应该渲染某个细节"""
        detail_levels = {
            'text': self.LOD_FULL,
            'properties': self.LOD_FULL,
            'ports': self.LOD_MEDIUM,
            'shadows': self.LOD_MEDIUM,
            'gradients': self.LOD_FULL,
            'icons': self.LOD_MEDIUM,
            'connections': self.LOD_LOW
        }

        required_level = detail_levels.get(detail_name, self.LOD_FULL)
        return lod_level <= required_level


class RenderOptimizer(QObject):
    """渲染优化器"""

    # 信号
    render_stats_updated = Signal(dict)

    def __init__(self, scene_bounds: QRectF):
        super().__init__()

        # 空间索引
        self.spatial_index = SpatialIndex(scene_bounds)

        # 脏矩形管理
        self.dirty_rect_manager = DirtyRectManager()

        # LOD管理
        self.lod_manager = LODManager()

        # 渲染统计
        self.stats = {
            'items_total': 0,
            'items_visible': 0,
            'items_culled': 0,
            'dirty_rects': 0,
            'fps': 0.0,
            'render_time': 0.0
        }

        # 性能监控
        self.frame_times: List[float] = []
        self.max_frame_samples = 60
        self.frame_timer = QElapsedTimer()
        self.frame_start_time = 0

        # 批处理
        self.batch_updates: List[Tuple[Any, str, Any]] = []
        self.batch_timer = QTimer()
        self.batch_timer.timeout.connect(self._process_batch_updates)
        self.batch_timer.setInterval(16)  # 约60 FPS

    def add_item(self, item: Any, bounds: QRectF):
        """添加项目到优化器"""
        self.spatial_index.add_item(item, bounds)
        self.stats['items_total'] += 1

    def remove_item(self, item: Any):
        """从优化器移除项目"""
        self.spatial_index.remove_item(item)
        self.stats['items_total'] -= 1

    def update_item_bounds(self, item: Any, new_bounds: QRectF):
        """更新项目边界"""
        old_bounds = self.spatial_index.item_bounds.get(item)
        if old_bounds:
            self.dirty_rect_manager.mark_dirty(old_bounds)

        self.spatial_index.update_item(item, new_bounds)
        self.dirty_rect_manager.mark_dirty(new_bounds)

    def get_visible_items(self, view_rect: QRectF, zoom_factor: float) -> List[Tuple[Any, int]]:
        """获取可见项目及其LOD级别"""
        # 扩展视图矩形以包含边缘项目
        expanded_rect = view_rect.adjusted(-50, -50, 50, 50)

        # 查询可见项目
        visible_items = self.spatial_index.query_items(expanded_rect)

        # 确定LOD级别
        lod_level = self.lod_manager.get_lod_level(zoom_factor)

        # 更新统计
        self.stats['items_visible'] = len(visible_items)
        self.stats['items_culled'] = self.stats['items_total'] - len(visible_items)

        return [(item, lod_level) for item in visible_items]

    def batch_update(self, item: Any, property_name: str, value: Any):
        """批量更新（延迟执行）"""
        self.batch_updates.append((item, property_name, value))

        if not self.batch_timer.isActive():
            self.batch_timer.start()

    def _process_batch_updates(self):
        """处理批量更新"""
        if not self.batch_updates:
            self.batch_timer.stop()
            return

        # 处理所有更新
        updates_by_item = {}
        for item, prop, value in self.batch_updates:
            if item not in updates_by_item:
                updates_by_item[item] = {}
            updates_by_item[item][prop] = value

        # 应用更新
        for item, updates in updates_by_item.items():
            for prop, value in updates.items():
                if hasattr(item, f'set_{prop}'):
                    getattr(item, f'set_{prop}')(value)
                elif hasattr(item, prop):
                    setattr(item, prop, value)

            # 标记项目区域为脏
            if item in self.spatial_index.item_bounds:
                self.dirty_rect_manager.mark_dirty(
                    self.spatial_index.item_bounds[item]
                )

        self.batch_updates.clear()
        self.batch_timer.stop()

    def start_frame(self):
        """开始新的渲染帧"""
        self.frame_timer.restart()
        self.frame_start_time = time.perf_counter()

    def end_frame(self):
        """结束渲染帧"""
        frame_time = (time.perf_counter() - self.frame_start_time) * 1000  # 转换为毫秒
        self.frame_times.append(frame_time)

        if len(self.frame_times) > self.max_frame_samples:
            self.frame_times.pop(0)

        # 计算FPS
        if self.frame_times:
            avg_frame_time = sum(self.frame_times) / len(self.frame_times)
            self.stats['fps'] = 1000.0 / avg_frame_time if avg_frame_time > 0 else 0
            self.stats['render_time'] = avg_frame_time

        # 清理脏矩形
        self.dirty_rect_manager.clear()

        # 发送统计信息
        self.render_stats_updated.emit(self.stats.copy())

    def should_render_detail(self, detail_name: str, zoom_factor: float) -> bool:
        """判断是否应该渲染某个细节"""
        lod_level = self.lod_manager.get_lod_level(zoom_factor)
        return self.lod_manager.should_render_detail(detail_name, lod_level)