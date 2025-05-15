from PySide6.QtCore import Signal, QObject, QPointF,Slot
from PySide6.QtGui import QColor, Qt, QPen

from src.views.node_system.node import Node
from src.pipeline import TaskNode, open_pipeline


class CanvasNodeManager(QObject):
    """
    节点操作的统一管理器。与Pipeline协作管理节点的UI表示和逻辑关系。
    """
    OpenNodeChanged = Signal(str,object)

    def __init__(self, canvas, scene):
        super().__init__()

        self.canvas = canvas
        self.scene = scene
        self.connection_manager = canvas.connection_manager
        self.command_manager = canvas.command_manager

        # UI节点集合
        self.nodes = []  # 场景中的所有节点
        self.selected_nodes = []  # 当前选中的节点
        self.open_node = None  # 当前打开的节点

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

        # 确保Pipeline中的节点也被完全清除
        if hasattr(self.pipeline, 'nodes'):
            if isinstance(self.pipeline.nodes, dict):
                self.pipeline.nodes.clear()
            elif isinstance(self.pipeline.nodes, list):
                self.pipeline.nodes.clear()  # 如果是列表也可以用clear方法

        try:
            # 使用Pipeline加载文件
            self.pipeline.load_from_file(file_path)

            # 从Pipeline创建可视化节点
            node_map = {}  # 存储名称到节点的映射

            # 使用列表迭代而不是字典项迭代
            for task_node in self.pipeline.nodes:
                # 创建视觉节点
                node = self._create_visual_node_from_task(task_node)
                self.add_node(node)
                # 使用task_node.name作为键
                node_map[task_node.name] = node

            self._layout_nodes(self.pipeline, node_map)
            # 创建节点间的连接
            self._create_connections_from_tasks(node_map)

            return True
        except Exception as e:
            print(f"加载文件时出错: {str(e)}")
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

    def create_unknown_node(self, title="Unknown Node", position=None):
        """
        创建一个未知节点

        参数:
            id: 节点ID，如果为None则自动生成
            title: 节点标题
            position: 节点位置

        返回:
            创建的未知节点
        """

        # 创建未知节点
        unknown_node = Node(title=title, node_type=Node.TYPE_UNKNOWN)

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
        if node ==self.open_node:
            self.open_node=None

        # 如果node有task_node属性，尝试通过task_node.name删除
        elif hasattr(node, 'task_node') and node.task_node:
            task_node = node.task_node
            if hasattr(task_node, 'name') and task_node.name in self.pipeline.nodes:
                del self.pipeline.nodes[task_node.name]

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
            if node:
                self.open_node=node
                self.OpenNodeChanged.emit("canvas",node)
        else:
            if self.open_node:
                self.open_node=None

        self._update_node_appearance(node)

    def toggle_node_open(self, node):
        """切换节点的打开状态"""
        if node in self.open_node:
            self.set_node_open(node, False)
        else:
            self.set_node_open(node, True)

    def close_all_nodes(self):
        """关闭所有已打开的节点"""
        self.open_node = None

    def _update_node_appearance(self, node):
        """
        根据节点状态更新其外观。

        参数:
            node: 要更新的节点
        """
        if not hasattr(node, 'border_color'):
            node.border_color = self.DEFAULT_COLOR
            self._enhance_node(node)

        if node ==self.open_node:
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
        self.open_node=None
        self.OpenNodeChanged.emit("canvas",self.open_node)

    def get_selected_nodes(self):
        """获取所有选中的节点"""
        return self.selected_nodes.copy()

    def get_open_nodes(self):
        """获取所有打开的节点"""
        return self.open_node

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
        for task_node in self.pipeline.nodes:
            name = task_node.name
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
                            unknown_pos = QPointF(source_pos.x() + 500, source_pos.y() - 300)
                        else:  # interrupt
                            unknown_pos = QPointF(source_pos.x() + 500, source_pos.y() + 150)

                        # 创建未知节点，保留原始ID
                        unknown_node = self.create_unknown_node(
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
        all_nodes = set(task_node.name for task_node in pipeline.nodes)

        # 初始化边信息
        for node_name in all_nodes:
            in_edges[node_name] = []
            out_edges[node_name] = []

        # 构建边信息
        for task_node in pipeline.nodes:
            node_name = task_node.name
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

        # 如果没有真正的入口节点（全是循环），选择任意节点作为入口
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

    def save_to_file(self, file_path=None):
        """
        保存当前节点到文件。

        参数:
            file_path: 保存文件的路径。如果为None，则使用之前加载的文件路径。

        返回:
            bool: 成功或失败
        """
        # 确定保存路径
        actual_path = file_path or getattr(self.pipeline, 'current_file', None)
        if not actual_path:
            print("错误: 未指定保存路径，且无之前加载的文件路径")
            return False

        try:
            print(f"正在保存到: {actual_path}")
            # 将可视化节点更新到Pipeline
            self._update_pipeline_from_visual()

            # 保存到文件
            self.pipeline.save_to_file(actual_path)

            # 如果提供了新路径，更新当前文件路径
            if file_path:
                self.pipeline.current_file = file_path

            print(f"保存成功: {actual_path}")
            return True
        except Exception as e:
            print(f"保存文件时出错: {e}")
            import traceback
            print(traceback.format_exc())
            return False

    def _update_pipeline_from_visual(self):
        """
        将可视化节点的状态更新到Pipeline中的逻辑节点

        这个方法会从当前可视化节点重建Pipeline，包括所有连接和属性
        """
        # 创建新的Pipeline实例
        new_pipeline = self.pipeline.__class__()
        # 首先，为每个可视化节点创建TaskNode
        for visual_node in self.nodes:
            if hasattr(visual_node, 'task_node') and visual_node.task_node:
                task_node = visual_node.task_node
                new_pipeline.add_node(task_node)
                continue


        new_pipeline.current_file = getattr(self.pipeline, 'current_file', None)
        # 替换当前Pipeline
        self.pipeline = new_pipeline

        return new_pipeline

    def _process_port_connections(self, pipeline, source_id, port, conn_type):
        """
        处理端口的所有连接，更新Pipeline中的逻辑连接

        参数:
            pipeline: 要更新的Pipeline对象
            source_id: 源节点ID
            port: 要处理的端口
            conn_type: 连接类型 ('next', 'on_error', 'interrupt')
        """
        if not port or not port.is_connected():
            return

        # 获取端口的所有连接
        connections = port.get_connections()

        # 查找源TaskNode
        source_task = None
        for task_node in pipeline.nodes:
            if task_node.name == source_id:
                source_task = task_node
                break

        if not source_task:
            return

        # 获取当前连接的节点列表
        current_connections = getattr(source_task, conn_type, [])
        if current_connections and not isinstance(current_connections, list):
            current_connections = [current_connections]
        else:
            current_connections = current_connections or []

        # 创建新的连接列表
        new_connections = current_connections.copy()

        # 处理所有连接
        for connection in connections:
            target_port = connection.get_target_port()
            if target_port:
                target_node = target_port.get_parent_node()
                if target_node and hasattr(target_node, 'id'):
                    target_id = target_node.id
                    # 确保目标节点ID不重复添加
                    if target_id not in new_connections:
                        new_connections.append(target_id)

        # 更新TaskNode的连接属性
        if len(new_connections) == 1:
            # 如果只有一个连接，可以直接存为字符串而不是列表
            setattr(source_task, conn_type, new_connections[0])
        elif len(new_connections) > 1:
            setattr(source_task, conn_type, new_connections)
        else:
            # 如果没有连接，确保该属性为空列表或None
            setattr(source_task, conn_type, None)

    def update_from_node(self, task_node):
        """
        更新可视化节点，使用提供的TaskNode中的数据。

        此方法查找与输入TaskNode同名的可视化节点，并通过调用其set_task_node()方法进行更新。

        参数:
            task_node: 包含更新数据的TaskNode

        返回:
            bool: 找到并更新节点则返回True，否则返回False
        """
        if not task_node or not hasattr(task_node, 'name'):
            print("错误: 提供了无效的TaskNode - 缺少name属性")
            return False

        # 查找同名的可视化节点
        matching_node = None
        for node in self.nodes:
            if (hasattr(node, 'task_node') and
                    node.task_node and
                    hasattr(node.task_node, 'name') and
                    node.task_node.name == task_node.name):
                matching_node = node
                break

        # 如果找到匹配的节点，更新它
        if matching_node:
            # 使用新的task_node更新可视化节点
            matching_node.set_task_node(task_node)

            # 更新节点外观以反映变更
            self._update_node_appearance(matching_node)

            return True
        else:
            print(f"警告: 未找到与TaskNode名称匹配的可视化节点: {task_node.name}")
            return False

    @Slot(str, str)
    def update_node_name(self, old_name, new_name):
        """
        更新节点名称，并同步更新所有引用该节点的连接。

        参数:
            old_name: 节点的原始名称
            new_name: 节点的新名称

        返回:
            bool: 操作成功返回True，否则返回False
        """
        # 验证新名称不为空
        if not new_name or new_name.strip() == "":
            print("错误: 新名称不能为空")
            return False

        # 检查新名称是否已被其他节点使用
        for task_node in self.pipeline.nodes:
            if hasattr(task_node, 'name') and task_node.name == new_name:
                print(f"错误: 名称 '{new_name}' 已被使用")
                return False

        # 查找对应的可视化节点和任务节点
        target_visual_node = None
        target_task_node = None

        for node in self.nodes:
            if (hasattr(node, 'task_node') and
                    node.task_node and
                    hasattr(node.task_node, 'name') and
                    node.task_node.name == old_name):
                target_visual_node = node
                target_task_node = node.task_node
                break

        if not target_visual_node or not target_task_node:
            print(f"错误: 未找到名称为 '{old_name}' 的节点")
            return False

        # 更新任务节点的名称
        target_task_node.name = new_name

        # 更新可视化节点的标题
        if hasattr(target_visual_node, 'set_title'):
            target_visual_node.set_title(new_name)
        elif hasattr(target_visual_node, 'title'):
            target_visual_node.title = new_name

        # 更新所有引用此节点的连接
        for task_node in self.pipeline.nodes:
            # 跳过目标节点自身
            if task_node == target_task_node:
                continue

            # 更新所有连接类型: next, on_error, interrupt
            for conn_type in ['next', 'on_error', 'interrupt']:
                conn_nodes = getattr(task_node, conn_type, None)
                if not conn_nodes:
                    continue

                # 处理单个值的情况
                if not isinstance(conn_nodes, list):
                    if conn_nodes == old_name:
                        setattr(task_node, conn_type, new_name)
                    continue

                # 处理列表的情况，替换所有匹配项
                for i, conn_name in enumerate(conn_nodes):
                    if conn_name == old_name:
                        conn_nodes[i] = new_name


        # 触发节点视觉更新
        target_visual_node.refresh_ui()

        print(f"节点名称已成功更新: '{old_name}' -> '{new_name}'")

        return True