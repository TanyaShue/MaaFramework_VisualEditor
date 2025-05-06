from PySide6.QtCore import Signal, QObject
from PySide6.QtGui import QColor, Qt, QPen

from src.node_system.node import Node
from src.pipeline import TaskNode, open_pipeline


class CanvasNodeManager(QObject):
    """
    节点操作的统一管理器。与Pipeline协作管理节点的UI表示和逻辑关系。
    """
    OpenNodeChanged = Signal(list)

    def __init__(self, canvas, scene):
        super().__init__()

        self.canvas = canvas
        self.scene = scene
        self.connection_manager = canvas.connection_manager
        self.command_manager = canvas.command_manager

        # UI节点集合
        self.nodes = []  # 场景中的所有节点
        self.selected_nodes = []  # 当前选中的节点
        self.open_nodes = []  # 当前打开的节点

        # 节点显示状态的颜色
        self.SELECTED_COLOR = QColor(255, 255, 0)
        self.OPEN_COLOR = QColor(0, 200, 0)
        self.DEFAULT_COLOR = QColor(100, 100, 100)

        # 创建Pipeline实例用于逻辑管理
        self.pipeline = open_pipeline

    def load_file(self, file_path):
        """
        从文件加载节点。

        参数:
            file_path: 包含节点数据的文件路径
        """
        # 清除当前节点
        self.clear()

        try:
            # 使用Pipeline加载文件
            self.pipeline = self.pipeline.__class__.load_from_file(file_path)

            # 从Pipeline创建可视化节点
            node_map = {}  # 存储名称到节点的映射

            for name, task_node in self.pipeline.nodes.items():
                # 创建视觉节点
                node = self._create_visual_node_from_task(task_node)
                self.add_node(node)
                node_map[name] = node

            # 创建节点间的连接
            self._create_connections_from_tasks(node_map)

            return True
        except Exception as e:
            print(f"加载文件时出错: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return False

    def save_to_file(self, file_path=None):
        """
        保存当前节点到文件。

        参数:
            file_path: 保存文件的路径

        返回:
            bool: 成功或失败
        """
        if not file_path and not hasattr(self.pipeline, 'current_file'):
            return False

        try:
            # 更新Pipeline中的节点数据
            self._update_pipeline_from_visual()

            # 使用Pipeline保存数据
            self.pipeline.save_to_file(file_path)

            # 更新当前文件路径
            if file_path:
                self.pipeline.current_file = file_path

            return True
        except Exception as e:
            print(f"保存文件时出错: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return False

    def add_node(self, node):
        """
        添加节点到画布。

        参数:
            node: 要添加的节点

        返回:
            添加的节点
        """
        # 添加到场景
        self.scene.addItem(node)
        self.nodes.append(node)

        # 设置端口
        input_port = node.get_input_port()
        if input_port:
            input_port.setParentItem(node)

        output_ports = node.get_output_ports()
        if isinstance(output_ports, dict):
            for output_port in output_ports.values():
                output_port.setParentItem(node)
        else:
            for port in output_ports:
                port.setParentItem(node)

        # 添加border_color属性到节点
        node.border_color = self.DEFAULT_COLOR

        # 确保节点的paint方法使用此属性
        self._enhance_node(node)

        # 同步到Pipeline中的逻辑节点
        if hasattr(node, 'task_data'):
            task_node = TaskNode(node.id, **node.task_data)
            self.pipeline.add_node(task_node)

        return node

    def remove_node(self, node):
        """
        从画布移除节点。

        参数:
            node: 要移除的节点
        """
        # 移除所有连接
        connections_to_remove = []

        input_ports = node.get_input_ports() if hasattr(node, 'get_input_ports') else [node.get_input_port()]
        for port in input_ports:
            if port and port.is_connected():
                connections_to_remove.extend(port.get_connections())

        output_ports = node.get_output_ports()
        if isinstance(output_ports, dict):
            output_ports = list(output_ports.values())
        for port in output_ports:
            connections_to_remove.extend(port.get_connections())

        for connection in connections_to_remove:
            self.connection_manager.remove_connection(connection)

        # 从场景和列表中移除
        self.scene.removeItem(node)
        if node in self.nodes:
            self.nodes.remove(node)
        if node in self.selected_nodes:
            self.selected_nodes.remove(node)
        if node in self.open_nodes:
            self.open_nodes.remove(node)

        # 从Pipeline中移除节点
        if hasattr(node, 'id') and node.id in self.pipeline.nodes:
            del self.pipeline.nodes[node.id]

    def select_node(self, node, selected=True):
        """
        选择或取消选择节点。

        参数:
            node: 要选择/取消选择的节点
            selected: True选择，False取消选择
        """
        if selected:
            if node not in self.selected_nodes:
                self.selected_nodes.append(node)
                # 会触发场景的selectionChanged信号
                node.setSelected(True)
        else:
            if node in self.selected_nodes:
                self.selected_nodes.remove(node)
                node.setSelected(False)

        self._update_node_appearance(node)

    def set_node_open(self, node, open_state=True):
        """
        设置节点为打开或关闭状态。

        参数:
            node: 要打开/关闭的节点
            open_state: True打开，False关闭
        """
        if open_state:
            if node not in self.open_nodes:
                self.open_nodes.append(node)
                self.OpenNodeChanged.emit([node])
        else:
            if node in self.open_nodes:
                self.open_nodes.remove(node)

        self._update_node_appearance(node)

    def toggle_node_open(self, node):
        """切换节点的打开状态"""
        if node in self.open_nodes:
            self.set_node_open(node, False)
        else:
            self.set_node_open(node, True)

    def close_all_nodes(self):
        """关闭所有已打开的节点"""
        for node in self.open_nodes[:]:
            self.set_node_open(node, False)

    def _update_node_appearance(self, node):
        """
        根据节点状态更新其外观。

        参数:
            node: 要更新的节点
        """
        if not hasattr(node, 'border_color'):
            node.border_color = self.DEFAULT_COLOR
            self._enhance_node(node)

        if node in self.open_nodes:
            node.border_color = self.OPEN_COLOR  # 绿色
        elif node in self.selected_nodes:
            node.border_color = self.SELECTED_COLOR  # 黄色
        else:
            node.border_color = self.DEFAULT_COLOR  # 默认

        node.update()  # 触发重绘

    def _enhance_node(self, node):
        """
        增强节点，只为特殊状态节点添加边框。

        参数:
            node: 要增强的节点
        """
        # 存储原始paint方法
        if not hasattr(node, 'original_paint'):
            node.original_paint = node.paint

            # 定义新的paint方法
            def enhanced_paint(painter, option, widget):
                # 暂存选中状态
                was_selected = node.isSelected()

                # 临时取消选中状态，避免QGraphicsItem绘制默认选中边框
                if was_selected:
                    node.setSelected(False)

                # 调用原始绘制方法（现在不会绘制默认选中边框）
                node.original_paint(painter, option, widget)

                # 恢复选中状态（不会触发重绘）
                if was_selected:
                    node.setSelected(True)

                # 只为选中或打开的节点绘制自定义彩色边框
                if node.border_color != self.DEFAULT_COLOR:
                    pen = QPen(node.border_color, 2)
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)  # 确保不填充矩形
                    painter.drawRect(node.boundingRect().adjusted(1, 1, -1, -1))

            # 替换paint方法
            node.paint = enhanced_paint

    def clear(self):
        """清除所有节点"""
        for node in self.nodes[:]:
            self.remove_node(node)

        self.selected_nodes.clear()
        self.open_nodes.clear()

        # 清空Pipeline
        self.pipeline = self.pipeline.__class__()

    def get_selected_nodes(self):
        """获取所有选中的节点"""
        return self.selected_nodes.copy()

    def get_open_nodes(self):
        """获取所有打开的节点"""
        return self.open_nodes.copy()

    def update_from_scene_selection(self):
        """
        根据场景选择更新selected_nodes列表。
        当场景的selectionChanged信号发出时调用。
        """
        # 从场景获取选中的项
        selected_items = self.scene.selectedItems()

        # 过滤出节点
        selected_nodes = [item for item in selected_items if isinstance(item, Node)]

        # 更新内部选择列表
        self.selected_nodes = selected_nodes

        # 更新所有节点的外观
        for node in self.nodes:
            self._update_node_appearance(node)

    def get_nodes_state(self):
        """
        获取所有节点的序列化状态

        返回:
            list: 包含所有节点状态信息的列表
        """
        # 先更新Pipeline
        self._update_pipeline_from_visual()

        # 使用原始的可视化节点属性
        nodes_data = []

        for node in self.nodes:
            try:
                # 获取节点属性，如果节点有get_properties方法
                properties = node.get_properties() if hasattr(node, 'get_properties') else {}

                node_data = {
                    'id': node.id,
                    'title': node.title,
                    'properties': properties,
                    'position': {'x': node.pos().x(), 'y': node.pos().y()}
                }

                # 如果节点有类型属性，也保存它
                if hasattr(node, 'node_type'):
                    node_data['node_type'] = node.node_type

                nodes_data.append(node_data)
            except Exception as e:
                print(f"保存节点状态时出错: {str(e)}")

        return nodes_data

    def restore_nodes_state(self, nodes_data):
        """
        从序列化状态恢复节点

        参数:
            nodes_data: 节点数据列表

        返回:
            dict: 节点ID到节点实例的映射
        """
        node_map = {}  # 映射节点ID到实例

        for node_data in nodes_data:
            # 创建节点 - 这里需要根据实际的Node类实现进行调整
            node = Node(
                id=node_data['id'],
                title=node_data['title']
            )

            # 设置节点属性
            if 'properties' in node_data and hasattr(node, 'set_properties'):
                node.set_properties(node_data['properties'])

            # 设置节点位置
            if 'position' in node_data:
                pos = node_data['position']
                node.setPos(pos['x'], pos['y'])

            # 添加到画布
            self.add_node(node)

            # 存储到映射中
            node_map[node_data['id']] = node

        return node_map

    def select_all_nodes(self):
        """选择所有节点"""
        for node in self.nodes:
            node.setSelected(True)
        self.update_from_scene_selection()

    def deselect_all_nodes(self):
        """取消选择所有节点"""
        self.scene.clearSelection()
        self.update_from_scene_selection()

    # 新增的方法用于与Pipeline交互
    def _create_visual_node_from_task(self, task_node):
        """
        从TaskNode创建可视化节点

        参数:
            task_node: Pipeline中的TaskNode实例

        返回:
            创建的可视化Node实例
        """
        # 假设Node类的构造函数支持id和title参数
        node = Node(
            id=task_node.name,
            title=task_node.name
        )

        # 存储任务节点数据，便于后续同步
        node.task_data = task_node.to_dict()

        # 可以根据任务节点类型设置不同的外观
        if hasattr(task_node, 'recognition'):
            # 可以根据不同算法类型设置不同的外观
            pass

        if hasattr(task_node, 'action'):
            # 可以根据不同动作类型设置不同的外观
            pass

        return node

    def _create_connections_from_tasks(self, node_map):
        """
        根据Pipeline中的任务节点关系创建可视化连接

        参数:
            node_map: 从任务节点名称到可视化节点的映射
        """
        # 遍历所有任务节点
        for name, task_node in self.pipeline.nodes.items():
            if name not in node_map:
                continue

            source_node = node_map[name]

            # 处理next连接
            next_nodes = []
            if isinstance(task_node.next, list):
                next_nodes = task_node.next
            elif task_node.next:
                next_nodes = [task_node.next]

            for next_name in next_nodes:
                if next_name in node_map:
                    target_node = node_map[next_name]

                    # 创建连接 - 这里需要根据实际的连接管理器实现调整
                    self._create_connection(source_node, target_node)

    def _create_connection(self, source_node, target_node):
        """
        在两个节点之间创建连接

        参数:
            source_node: 源节点
            target_node: 目标节点
        """
        # 获取输出和输入端口
        source_port = source_node.get_output_ports()[0]  # 假设使用第一个输出端口
        target_port = target_node.get_input_port()

        # 检查端口是否有效
        if source_port and target_port:
            # 使用连接管理器创建连接
            self.connection_manager.create_connection(source_port, target_port)

    def _update_pipeline_from_visual(self):
        """将可视化节点的状态更新到Pipeline中的逻辑节点"""
        # 清空当前Pipeline
        self.pipeline = self.pipeline.__class__()

        # 从可视化节点重建Pipeline中的任务节点
        for node in self.nodes:
            if hasattr(node, 'task_data'):
                task_node = TaskNode(node.id, **node.task_data)
                self.pipeline.add_node(task_node)
            else:
                # 如果节点没有关联任务数据，创建基本任务节点
                task_node = TaskNode(
                    name=node.id,
                    recognition="DirectHit",
                    action="DoNothing"
                )
                self.pipeline.add_node(task_node)

        # 更新节点间的连接关系
        self._update_pipeline_connections()

    def _update_pipeline_connections(self):
        """根据可视化连接更新Pipeline中的节点关系"""
        # 获取所有连接
        connections = self.connection_manager.get_all_connections()

        # 清除所有节点的next属性
        for task_node in self.pipeline.nodes.values():
            task_node.next = []

        # 遍历所有连接，更新next关系
        for connection in connections:
            source_port = connection.source_port
            target_port = connection.target_port

            if source_port and target_port:
                source_node_id = source_port.parent_node.id
                target_node_id = target_port.parent_node.id

                if source_node_id in self.pipeline.nodes and target_node_id in self.pipeline.nodes:
                    source_task = self.pipeline.nodes[source_node_id]
                    source_task.add_next_node(target_node_id)

    def validate(self):
        """
        验证当前Pipeline配置

        返回:
            dict: 验证错误信息
        """
        # 先更新Pipeline
        self._update_pipeline_from_visual()

        # 执行Pipeline验证
        config_errors = self.pipeline.validate()
        reference_errors = self.pipeline.check_references()

        # 合并错误信息
        errors = {}
        for name, node_errors in config_errors.items():
            errors[name] = node_errors

        for name, node_errors in reference_errors.items():
            if name in errors:
                errors[name].extend(node_errors)
            else:
                errors[name] = node_errors

        return errors