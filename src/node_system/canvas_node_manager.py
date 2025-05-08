from PySide6.QtCore import Signal, QObject, QPointF
from PySide6.QtGui import QColor, Qt, QPen

from src.node_system.node import Node
from src.node_system.nodes.unknow_node import UnknownNode
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

            self._layout_nodes(self.pipeline, node_map)
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

    def create_unknown_node(self, id=None, title="Unknown Node", position=None):
        """
        创建一个未知节点

        参数:
            id: 节点ID，如果为None则自动生成
            title: 节点标题
            position: 节点位置

        返回:
            创建的未知节点
        """

        # 如果没有提供ID，生成一个唯一ID
        if id is None:
            id = f"UNK_{len(self.nodes):03d}"

        # 创建未知节点
        unknown_node = UnknownNode(id=id, title=title)

        # 设置位置（如果提供）
        if position:
            unknown_node.setPos(position)

        # 添加到画布并返回
        return self.add_node(unknown_node)

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

    def _create_visual_node_from_task(self, task_node):
        """
        从TaskNode创建可视化节点

        参数:
            task_node: Pipeline中的TaskNode实例

        返回:
            创建的可视化Node实例
        """
        node = Node(
            id=task_node.name,
            title=task_node.name
        )

        node.set_task_node(task_node)

        return node

    def _create_connections_from_tasks(self, node_map):
        """
        根据Pipeline中的任务节点关系创建可视化连接，处理所有类型的连接

        参数:
            node_map: 从任务节点名称到可视化节点的映射
        """
        # 遍历所有任务节点
        for name, task_node in self.pipeline.nodes.items():
            if name not in node_map:
                continue

            source_node = node_map[name]

            # 处理所有类型的连接
            for conn_type in ['next', 'on_error', 'interrupt']:
                conn_nodes = getattr(task_node, conn_type, None)
                if not conn_nodes:
                    continue

                # 统一处理列表和单个值
                if not isinstance(conn_nodes, list):
                    conn_nodes = [conn_nodes]

                for conn_name in conn_nodes:
                    # 检查目标节点是否存在
                    if conn_name in node_map:
                        target_node = node_map[conn_name]
                        # 创建到已存在节点的连接
                        self._create_connection(source_node, target_node, conn_type)
                    else:
                        # 目标节点不存在，创建未知节点
                        # 为未知节点创建一个基于连接类型的位置
                        source_pos = source_node.pos()

                        # 根据连接类型确定未知节点的位置
                        if conn_type == 'next':
                            unknown_pos = QPointF(source_pos.x() + 500, source_pos.y())
                        elif conn_type == 'on_error':
                            unknown_pos = QPointF(source_pos.x() + 500, source_pos.y() -300)
                        else:  # interrupt
                            unknown_pos = QPointF(source_pos.x() + 500, source_pos.y() - 300)

                        # 创建未知节点，保留原始ID
                        unknown_node = self.create_unknown_node(
                            id=conn_name,
                            title=f"Unknown: {conn_name}",
                            position=unknown_pos
                        )
                        # 更新节点映射
                        node_map[conn_name] = unknown_node

                        # 创建连接
                        self._create_connection(source_node, unknown_node, conn_type)

    def _create_connection(self, source_node, target_node, conn_type='next'):
        """
        在两个节点之间创建特定类型的连接

        参数:
            source_node: 源节点
            target_node: 目标节点
            conn_type: 连接类型 ('next', 'on_error', 'interrupt')

        返回:
            创建的连接对象或None
        """
        # 获取源节点的输出端口
        output_ports = source_node.get_output_ports()
        source_port = None

        # 根据连接类型选择正确的输出端口
        if isinstance(output_ports, dict):
            # 从字典中通过类型获取端口
            source_port = output_ports.get(conn_type)

            # 如果没有找到特定类型的端口，使用默认端口
            if not source_port and output_ports:
                source_port = next(iter(output_ports.values()))
        elif isinstance(output_ports, list):
            # 从列表中找到匹配类型的端口
            for port in output_ports:
                if hasattr(port, 'port_type') and port.port_type == conn_type:
                    source_port = port
                    break

            # 如果没有找到匹配的端口，使用第一个端口
            if not source_port and output_ports:
                source_port = output_ports[0]
        else:
            # 如果是单个端口
            source_port = output_ports

        # 获取目标节点的输入端口
        target_port = target_node.get_input_port()

        # 检查端口是否有效
        if source_port and target_port:
            # 使用连接管理器创建连接
            connection = self.connection_manager.create_connection(source_port, target_port)
            return connection

        return None

    def _update_pipeline_connections(self):
        """根据可视化连接更新Pipeline中的节点关系"""
        # 获取所有连接
        connections = self.connection_manager.get_all_connections()

        # 清除所有节点的next, on_error和interrupt属性
        for task_node in self.pipeline.nodes.values():
            task_node.next = []
            if hasattr(task_node, 'on_error'):
                task_node.on_error = []
            if hasattr(task_node, 'interrupt'):
                task_node.interrupt = []

        # 遍历所有连接，更新节点关系
        for connection in connections:
            source_port = connection.source_port
            target_port = connection.target_port

            if source_port and target_port:
                source_node_id = source_port.parent_node.id
                target_node_id = target_port.parent_node.id

                if source_node_id in self.pipeline.nodes and target_node_id in self.pipeline.nodes:
                    source_task = self.pipeline.nodes[source_node_id]

                    # 根据端口类型确定连接类型
                    conn_type = getattr(source_port, 'port_type', 'next')

                    # 根据连接类型更新相应的关系
                    if conn_type == 'next':
                        self._add_next_node(source_task, target_node_id)
                    elif conn_type == 'on_error':
                        self._add_error_node(source_task, target_node_id)
                    elif conn_type == 'interrupt':
                        self._add_interrupt_node(source_task, target_node_id)
                    else:
                        # 默认添加为next节点
                        self._add_next_node(source_task, target_node_id)

    def _add_next_node(self, task_node, node_name):
        """
        添加下一个节点到任务节点

        参数:
            task_node: 任务节点
            node_name: 要添加的节点名称
        """
        if not hasattr(task_node, 'next') or task_node.next is None:
            task_node.next = []

        if isinstance(task_node.next, list):
            if node_name not in task_node.next:
                task_node.next.append(node_name)
        else:
            # 如果next不是列表，先转换为包含当前值的列表
            current = task_node.next
            task_node.next = [current] if current else []
            if node_name not in task_node.next:
                task_node.next.append(node_name)

    def _add_error_node(self, task_node, node_name):
        """
        添加错误处理节点到任务节点

        参数:
            task_node: 任务节点
            node_name: 要添加的节点名称
        """
        if not hasattr(task_node, 'on_error') or task_node.on_error is None:
            task_node.on_error = []

        if isinstance(task_node.on_error, list):
            if node_name not in task_node.on_error:
                task_node.on_error.append(node_name)
        else:
            # 如果on_error不是列表，先转换为包含当前值的列表
            current = task_node.on_error
            task_node.on_error = [current] if current else []
            if node_name not in task_node.on_error:
                task_node.on_error.append(node_name)

    def _add_interrupt_node(self, task_node, node_name):
        """
        添加中断处理节点到任务节点

        参数:
            task_node: 任务节点
            node_name: 要添加的节点名称
        """
        if not hasattr(task_node, 'interrupt') or task_node.interrupt is None:
            task_node.interrupt = []

        if isinstance(task_node.interrupt, list):
            if node_name not in task_node.interrupt:
                task_node.interrupt.append(node_name)
        else:
            # 如果interrupt不是列表，先转换为包含当前值的列表
            current = task_node.interrupt
            task_node.interrupt = [current] if current else []
            if node_name not in task_node.interrupt:
                task_node.interrupt.append(node_name)

    def _update_pipeline_from_visual(self):
        """将可视化节点的状态更新到Pipeline中的逻辑节点"""
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

    def validate(self):
        """
        验证当前Pipeline配置

        返回:
            dict: 验证错误信息
        """
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

    def _layout_nodes(self, pipeline, node_mapping):
        """
        优化的节点布局算法，处理循环依赖问题

        该算法使用拓扑排序的思想，确保即使在图中存在循环时，
        也能保证节点有合理的布局，避免节点重叠问题。
        """
        # 计算每个节点的入度和出度信息
        in_edges = {}  # 节点的入边 {node_name: [(from_node, conn_type), ...]}
        out_edges = {}  # 节点的出边 {node_name: [(to_node, conn_type), ...]}

        # 首先收集所有节点，包括引用但未定义的节点
        all_nodes = set(pipeline.nodes.keys())
        # 初始化边信息
        for node_name in all_nodes:
            in_edges[node_name] = []
            out_edges[node_name] = []

        # 构建边信息
        for node_name, task_node in pipeline.nodes.items():
            # 处理所有类型的连接
            for conn_type in ['next', 'on_error', 'interrupt']:
                next_nodes = getattr(task_node, conn_type, None)
                if not next_nodes:
                    continue

                # 统一处理成列表
                if not isinstance(next_nodes, list):
                    next_nodes = [next_nodes]

                for next_node in next_nodes:
                    # 如果目标节点不在节点列表中，添加它
                    if next_node not in all_nodes:
                        all_nodes.add(next_node)
                        in_edges[next_node] = []
                        out_edges[next_node] = []

                    # 更新边信息
                    out_edges[node_name].append((next_node, conn_type))
                    in_edges[next_node].append((node_name, conn_type))

        # 识别真正的入口节点（没有入边的节点）
        true_entry_nodes = [node for node in all_nodes if not in_edges[node]]

        # 如果没有真正的入口节点（全是循环），则使用pipeline的入口节点
        if not true_entry_nodes:
            true_entry_nodes = [node.name for node in pipeline.get_entry_nodes()]

            # 如果仍然没有入口节点，选择任意节点作为入口
            if not true_entry_nodes and all_nodes:
                true_entry_nodes = [list(all_nodes)[0]]

        # 节点层级分配
        node_levels = {}  # {node_name: level}
        visited = set()

        # 使用修改版的BFS来分配层级，确保循环中的节点有正确的层级
        queue = [(node, 0) for node in true_entry_nodes]

        # 初始化入口节点的层级
        for node in true_entry_nodes:
            node_levels[node] = 0

        while queue:
            current, level = queue.pop(0)

            # 如果节点已访问且已有层级，不再处理它
            if current in visited:
                continue

            visited.add(current)
            node_levels[current] = level  # 设置层级

            # 处理所有出边
            for next_node, _ in out_edges.get(current, []):
                # 如果节点已经被访问过（可能是循环），跳过
                if next_node in visited:
                    continue

                queue.append((next_node, level + 1))

        # 确保所有节点都有层级
        for node in all_nodes:
            if node not in node_levels:
                # 对于未访问的节点（可能是孤立节点或只有入边的节点），
                # 将其放在所有已知节点的下一层
                max_level = max(node_levels.values()) if node_levels else 0
                node_levels[node] = max_level + 1

        # 按层级组织节点
        nodes_by_level = {}
        for node, level in node_levels.items():
            if level not in nodes_by_level:
                nodes_by_level[level] = []
            nodes_by_level[level].append(node)

        # 计算每个节点的水平位置
        node_x_positions = {}

        # 首先处理入口节点
        for i, node in enumerate(true_entry_nodes):
            node_x_positions[node] = i * 2  # 给入口节点留足水平空间

        # 处理每一层的节点
        for level in sorted(nodes_by_level.keys()):
            nodes_at_level = nodes_by_level[level]
            used_positions = set()  # 记录此层已使用的位置

            # 步骤1: 处理有前驱节点的节点
            for node in list(nodes_at_level):
                # 跳过已处理的入口节点
                if node in node_x_positions:
                    used_positions.add(node_x_positions[node])
                    continue

                incoming = in_edges.get(node, [])
                if incoming:
                    suggested_x = []

                    # 收集所有前驱节点的建议位置
                    for from_node, conn_type in incoming:
                        if from_node in node_x_positions:
                            pred_x = node_x_positions[from_node]

                            # 根据连接类型调整建议位置
                            if conn_type == 'next':
                                suggested_x.append(pred_x)  # 正下方
                            elif conn_type == 'on_error':
                                suggested_x.append(pred_x - 1)  # 左下方
                            elif conn_type == 'interrupt':
                                suggested_x.append(pred_x + 1)  # 右下方

                    if suggested_x:
                        # 计算建议位置的平均值
                        avg_x = sum(suggested_x) / len(suggested_x)
                        target_x = round(avg_x)

                        # 处理位置冲突
                        while target_x in used_positions:
                            # 在冲突位置周围寻找最近的可用位置
                            for offset in range(1, 20):  # 允许更大范围的偏移
                                # 尝试右侧
                                if target_x + offset not in used_positions:
                                    target_x += offset
                                    break
                                # 尝试左侧
                                if target_x - offset not in used_positions:
                                    target_x -= offset
                                    break
                            else:
                                # 如果找不到可用位置，放在最右边
                                target_x = max(used_positions) + 2 if used_positions else 0

                        node_x_positions[node] = target_x
                        used_positions.add(target_x)

            # 步骤2: 处理剩余没有前驱的节点
            for node in nodes_at_level:
                if node not in node_x_positions:
                    # 找到一个未使用的水平位置
                    if used_positions:
                        target_x = max(used_positions) + 2
                    else:
                        target_x = 0

                    node_x_positions[node] = target_x
                    used_positions.add(target_x)

        # 应用布局到可视化节点
        grid_spacing_x = 500  # 水平间距
        grid_spacing_y = 300  # 垂直间距

        for node_name, visual_node in node_mapping.items():
            if node_name in node_x_positions and node_name in node_levels:
                x = node_x_positions[node_name] * grid_spacing_x
                y = node_levels[node_name] * grid_spacing_y
                visual_node.setPos(x, y)