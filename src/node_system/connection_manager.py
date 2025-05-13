from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor
from PySide6.QtWidgets import QGraphicsPathItem

from src.node_system.connection import Connection, build_connection_path


class ConnectionManager:
    """
    连接管理器，负责管理节点间的所有连接操作

    功能:
    - 创建和移除连接
    - 跟踪临时连接（连线过程中）
    - 存储所有活动连接
    - 序列化和反序列化连接状态
    """

    def __init__(self, scene, canvas):
        """
        初始化连接管理器

        参数:
            scene: 图形场景
            canvas: 画布引用
        """
        self.scene = scene
        self.canvas = canvas
        self.temp_connection = None  # 临时连接线（绘制中）
        self.connecting_port = None  # 当前正在连接的输出端口
        self.connections = []  # 所有活动连接

    def start_connection(self, output_port):
        """
        开始从输出端口创建一条连线

        参数:
            output_port: 连接的源端口

        返回:
            创建的临时连接对象
        """
        self.connecting_port = output_port
        start_pos = output_port.mapToScene(output_port.boundingRect().center())
        self.temp_connection = self.create_temp_connection(start_pos, start_pos)
        return self.temp_connection

    def update_temp_connection(self, target_pos):
        """
        更新临时连线的路径

        参数:
            target_pos: 当前目标位置（场景坐标）
        """
        if not self.temp_connection or not self.connecting_port:
            return

        # 使用统一的路径构建函数，传递 target_pos 作为第三个参数
        path = build_connection_path(self.connecting_port, None, target_pos)
        self.temp_connection.setPath(path)

    def cancel_connection(self):
        """取消当前连线操作"""
        if self.temp_connection:
            self.scene.removeItem(self.temp_connection)
            self.temp_connection = None
        self.connecting_port = None

    def create_temp_connection(self, start_pos, end_pos):
        """
        创建临时连线路径，供视觉反馈使用

        参数:
            start_pos: 起始位置
            end_pos: 结束位置

        返回:
            临时连接对象
        """
        if not self.connecting_port:
            return None

        # 根据端口类型确定颜色
        port_type = getattr(self.connecting_port, 'port_type', '')
        if port_type == 'next':
            color = QColor(100, 220, 100)  # 绿色
        elif port_type == 'on_error':
            color = QColor(220, 100, 100)  # 红色
        elif port_type == 'interrupt':
            color = QColor(220, 180, 100)  # 橙色
        else:
            color = QColor(100, 100, 100)  # 灰色

        temp_connection = QGraphicsPathItem()
        pen = QPen(color, 2, Qt.DashLine)

        # 设置虚线样式
        dash_pattern = [4, 4]  # 4个单位的线，4个单位的空白
        pen.setDashPattern(dash_pattern)

        temp_connection.setPen(pen)

        # 初始路径 - 将在update_temp_connection中更新
        path = build_connection_path(self.connecting_port, None, end_pos)
        temp_connection.setPath(path)
        self.scene.addItem(temp_connection)
        return temp_connection

    def can_connect(self, source_port, target_port):
        """
        检查两个端口是否可以连接

        参数:
            source_port: 源端口
            target_port: 目标端口

        返回:
            bool: 是否可以连接
        """
        if not source_port or not target_port:
            return False

        if source_port.parent_node == target_port.parent_node:
            return False

        if not source_port.can_connect(target_port):
            return False

        return True

    def remove_connection(self, connection):
        """
        移除指定的连线

        参数:
            connection: 要移除的连接对象
        """
        if not connection:
            return

        source = connection.get_source()
        target = connection.get_target()

        if source and hasattr(source, 'connections') and connection in source.connections:
            source.connections.remove(connection)
        if target and hasattr(target, 'connections') and connection in target.connections:
            target.connections.remove(connection)

        def remove_task_name(source_task_node, target_task_node, attr_name):
            if not target_task_node:
                return

            name_to_remove = target_task_node.name
            attr_value = getattr(source_task_node, attr_name, None)

            # 如果是字符串，转换为列表再移除（防止旧结构遗留）
            if isinstance(attr_value, str):
                attr_value = [attr_value]
                setattr(source_task_node, attr_name, attr_value)

            # 从列表中移除
            if isinstance(attr_value, list) and name_to_remove in attr_value:
                attr_value.remove(name_to_remove)

        if source and target and target.parent_node.task_node:
            source_task_node = source.parent_node.task_node
            target_task_node = target.parent_node.task_node

            if source.port_type == "next":
                remove_task_name(source_task_node, target_task_node, "next")
            elif source.port_type == "on_error":
                remove_task_name(source_task_node, target_task_node, "on_error")
            elif source.port_type == "interrupt":
                remove_task_name(source_task_node, target_task_node, "interrupt")

        # 移除连接图形
        self.scene.removeItem(connection)

        if connection in self.connections:
            self.connections.remove(connection)

    def update_connections_for_node(self, node):
        """
        更新与指定节点有关的所有连线

        参数:
            node: 要更新连接的节点
        """
        input_port = node.get_input_port()
        if input_port and hasattr(input_port, 'connections'):
            for connection in input_port.connections:
                if connection:
                    connection.update_path()

        output_ports = node.get_output_ports()
        if isinstance(output_ports, dict):
            output_ports = list(output_ports.values())

        for output_port in output_ports:
            if output_port and hasattr(output_port, 'connections'):
                for connection in output_port.connections:
                    if connection:
                        connection.update_path()

    def clear_all_connections(self):
        """清除所有连接"""
        for connection in self.connections[:]:  # 使用副本遍历，避免在移除过程中修改列表
            self.remove_connection(connection)

    def get_connections_state(self):
        """
        获取所有连接的序列化状态

        返回:
            list: 包含所有连接状态信息的列表
        """
        connections_data = []

        for conn in self.connections:
            try:
                # 获取连接的源端口和目标端口
                source_port = conn.get_source()
                target_port = conn.get_target()

                if not source_port or not target_port:
                    continue

                # 获取对应的节点
                source_node = source_port.parent_node
                target_node = target_port.parent_node

                # 获取连接类型
                conn_type = getattr(source_port, 'port_type', 'next')

                # 构建连接数据
                conn_data = {
                    'source_node_id': source_node.id,
                    'source_port_type': conn_type,
                    'source_port_name': getattr(source_port, 'port_name', ''),
                    'target_node_id': target_node.id,
                    'target_port_type': getattr(target_port, 'port_type', 'input'),
                    'target_port_name': getattr(target_port, 'port_name', '')
                }
                connections_data.append(conn_data)
            except Exception as e:
                print(f"保存连接状态时出错: {str(e)}")
                import traceback
                print(traceback.format_exc())

        return connections_data

    def restore_connections_state(self, connections_data, node_map):
        """
        从序列化状态恢复连接

        参数:
            connections_data: 连接数据列表
            node_map: 节点ID到节点实例的映射
        """
        from src.canvas_commands import ConnectNodesCommand

        for conn_data in connections_data:
            try:
                source_node_id = conn_data['source_node_id']
                target_node_id = conn_data['target_node_id']
                conn_type = conn_data.get('source_port_type', 'next')

                if source_node_id in node_map and target_node_id in node_map:
                    source_node = node_map[source_node_id]
                    target_node = node_map[target_node_id]

                    # 获取源端口
                    source_port = None
                    output_ports = source_node.get_output_ports()

                    if isinstance(output_ports, dict):
                        # 先通过端口类型尝试获取
                        source_port = output_ports.get(conn_type)

                        # 如果没有找到，但有端口名，使用端口名查找
                        if not source_port and 'source_port_name' in conn_data and conn_data['source_port_name']:
                            source_port = output_ports.get(conn_data['source_port_name'])

                        # 如果仍然没有找到，使用第一个可用端口
                        if not source_port and output_ports:
                            source_port = next(iter(output_ports.values()))
                    elif isinstance(output_ports, list):
                        # 遍历所有输出端口查找匹配的类型
                        for port in output_ports:
                            if getattr(port, 'port_type', '') == conn_type:
                                source_port = port
                                break

                        # 如果没有找到类型匹配的，但有端口名，按名称查找
                        if not source_port and 'source_port_name' in conn_data and conn_data['source_port_name']:
                            for port in output_ports:
                                if getattr(port, 'port_name', '') == conn_data['source_port_name']:
                                    source_port = port
                                    break

                        # 如果仍然没有找到，使用第一个端口
                        if not source_port and output_ports:
                            source_port = output_ports[0]
                    else:
                        # 如果是单个端口
                        source_port = output_ports

                    # 获取目标端口
                    target_port = None
                    if 'target_port_name' in conn_data and conn_data['target_port_name'] and hasattr(target_node,
                                                                                                     'get_input_ports'):
                        # 如果有多输入端口，按名称获取
                        input_ports = target_node.get_input_ports()
                        if isinstance(input_ports, dict):
                            target_port = input_ports.get(conn_data['target_port_name'])
                        else:
                            # 遍历所有输入端口查找匹配的
                            for port in input_ports:
                                if getattr(port, 'port_name', '') == conn_data['target_port_name']:
                                    target_port = port
                                    break
                    else:
                        # 没有端口名称，获取默认端口
                        target_port = target_node.get_input_port()

                    # 创建连接
                    if source_port and target_port and self.can_connect(source_port, target_port):
                        # 设置源端口的类型（如果需要）
                        if hasattr(source_port, 'port_type'):
                            source_port.port_type = conn_type

                        self.canvas.command_manager.execute(
                            ConnectNodesCommand(source_port, target_port, self.canvas)
                        )
            except Exception as e:
                print(f"恢复连接状态时出错: {str(e)}")
                import traceback
                print(traceback.format_exc())

    def find_connection(self, source_port, target_port):
        """
        查找两个端口之间是否已存在连接

        参数:
            source_port: 源端口
            target_port: 目标端口

        返回:
            存在的连接对象，如果不存在则返回None
        """
        for connection in self.connections:
            if (connection.get_source() == source_port and
                    connection.get_target() == target_port):
                return connection
        return None

    def create_connection(self, source_port, target_port):
        """
        在两个端口之间创建连接

        参数:
            source_port: 源端口
            target_port: 目标端口

        返回:
            创建的连接对象，如果无法连接则返回None
        """
        # 检查连接是否有效
        if not self.can_connect(source_port, target_port):
            return None

        # 检查是否已经存在连接
        existing_connection = self.find_connection(source_port, target_port)
        if existing_connection:
            return existing_connection

        # 创建新的连接
        connection = Connection(source_port, target_port, self.scene)

        # 添加到连接列表
        self.connections.append(connection)

        def append_task_name(source_task_node, target_task_node, attr_name):
            if not target_task_node:
                return

            name_to_append = target_task_node.name
            attr_value = getattr(source_task_node, attr_name, None)

            # 如果属性不存在或为 None，则初始化为空列表
            if attr_value is None:
                attr_value = []
                setattr(source_task_node, attr_name, attr_value)

            # 如果是字符串，则转换为列表
            elif isinstance(attr_value, str):
                attr_value = [attr_value]
                setattr(source_task_node, attr_name, attr_value)

            # 如果是列表且不重复，则添加
            if isinstance(attr_value, list) and name_to_append not in attr_value:
                attr_value.append(name_to_append)

        if target_port.parent_node.task_node:
            source_task_node = source_port.parent_node.task_node
            target_task_node = target_port.parent_node.task_node
            if source_port.port_type == "next":
                append_task_name(source_task_node, target_task_node, "next")
            elif source_port.port_type == "on_error":
                append_task_name(source_task_node, target_task_node, "on_error")
            elif source_port.port_type == "interrupt":
                append_task_name(source_task_node, target_task_node, "interrupt")
        # 更新连接的路径
        connection.update_path()
        self.cancel_connection()  # 添加这行取消临时连接状态

        return connection

    def get_all_connections(self):
        """
        获取所有连接

        返回:
            list: 所有连接对象的列表
        """
        return self.connections.copy()
