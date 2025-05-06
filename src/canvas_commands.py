from abc import ABC, abstractmethod


class Command(ABC):
    """命令抽象基类"""

    @abstractmethod
    def execute(self):
        """执行命令"""
        pass

    @abstractmethod
    def undo(self):
        """撤销命令"""
        pass


class MoveNodesCommand(Command):
    """移动节点命令"""

    def __init__(self, nodes, old_positions, new_positions, canvas):
        self.nodes = nodes
        self.old_positions = old_positions
        self.new_positions = new_positions
        self.canvas = canvas

    def execute(self):
        """执行移动命令"""
        for i, node in enumerate(self.nodes):
            node.setPos(self.new_positions[i])
            self.canvas.connection_manager.update_connections_for_node(node)

    def undo(self):
        """撤销移动命令"""
        for i, node in enumerate(self.nodes):
            node.setPos(self.old_positions[i])
            self.canvas.connection_manager.update_connections_for_node(node)


class AddNodeCommand(Command):
    """添加节点命令"""

    def __init__(self, node, canvas):
        self.node = node
        self.canvas = canvas

    def execute(self):
        """执行添加命令"""
        self.canvas.add_node(self.node)

    def undo(self):
        """撤销添加命令"""
        self.canvas.remove_node(self.node)


class DeleteNodesCommand(Command):
    """删除节点命令"""

    def __init__(self, nodes, canvas):
        self.nodes = nodes
        self.canvas = canvas
        self.node_data = []  # 存储节点数据以便恢复

        for node in nodes:
            # 保存节点数据
            node_info = {
                'id': node.id,
                'title': node.title,
                'properties': node.get_properties(),
                'position': node.pos(),
                'connections': []
            }

            # 保存连接信息
            # 输入端口的连接
            input_port = node.get_input_port()
            if input_port and input_port.is_connected():
                for conn in input_port.get_connections():
                    source_node = conn.source_port.parent_node
                    node_info['connections'].append({
                        'source_node_id': source_node.id,
                        'source_port_type': conn.source_port.port_type,
                        'source_port_name': getattr(conn.source_port, 'port_name', ''),
                        'is_input': True
                    })

            # 输出端口的连接
            output_ports = node.get_output_ports()
            if isinstance(output_ports, dict):
                output_ports = list(output_ports.values())

            for port in output_ports:
                for conn in port.get_connections():
                    target_node = conn.target_port.parent_node
                    node_info['connections'].append({
                        'target_node_id': target_node.id,
                        'target_port_type': conn.target_port.port_type,
                        'target_port_name': getattr(conn.target_port, 'port_name', ''),
                        'is_input': False,
                        'source_port_name': getattr(port, 'port_name', '')
                    })

            self.node_data.append(node_info)

    def execute(self):
        """执行删除命令"""
        for node in self.nodes:
            self.canvas.remove_node(node)

    def undo(self):
        """撤销删除命令 - 重新创建节点及其连接"""
        # 这需要根据具体的节点创建和连接机制来实现
        # 以下是一个示例框架，具体实现需要根据 Node 类和 Connection 类的设计
        from src.node_system.node import Node

        recreated_nodes = {}

        # 首先重新创建所有节点
        for node_info in self.node_data:
            node = Node(node_info['id'], node_info['title'])
            node.update_properties(node_info['properties'])
            node.setPos(node_info['position'])
            self.canvas.add_node(node)
            recreated_nodes[node_info['id']] = node

        # 然后重新创建连接
        for node_info in self.node_data:
            node = recreated_nodes[node_info['id']]

            for conn_info in node_info['connections']:
                if conn_info['is_input']:
                    # 重新连接作为目标的连接
                    source_node = recreated_nodes.get(conn_info['source_node_id'])
                    if source_node:
                        source_port = None
                        if conn_info['source_port_name']:
                            output_ports = source_node.get_output_ports()
                            if isinstance(output_ports, dict):
                                source_port = output_ports.get(conn_info['source_port_name'])
                            else:
                                for port in output_ports:
                                    if getattr(port, 'port_name', '') == conn_info['source_port_name']:
                                        source_port = port
                                        break
                        else:
                            output_ports = source_node.get_output_ports()
                            source_port = output_ports[0] if isinstance(output_ports, list) and output_ports else None

                        if source_port:
                            target_port = node.get_input_port()
                            if target_port and source_port.can_connect(target_port):
                                self.canvas.connection_manager.create_connection(source_port, target_port)
                else:
                    # 对于输出连接，在处理目标节点时已经创建
                    pass


class ConnectNodesCommand(Command):
    """连接节点命令"""

    def __init__(self, source_port, target_port, canvas):
        self.source_port = source_port
        self.target_port = target_port
        self.canvas = canvas
        self.connection = None

    def execute(self):
        """执行连接命令"""
        # 先设置connecting_port，然后调用finish_connection方法
        self.canvas.connection_manager.connecting_port = self.source_port
        self.connection = self.canvas.connection_manager.finish_connection(self.target_port)
        return self.connection is not None

    def undo(self):
        """撤销连接命令"""
        if self.connection:
            self.canvas.connection_manager.remove_connection(self.connection)


class DisconnectNodesCommand(Command):
    """断开连接命令"""

    def __init__(self, connection, canvas):
        self.connection = connection
        self.canvas = canvas
        # 使用get_source()和get_target()方法获取端口
        self.source_port = connection.get_source()
        self.target_port = connection.get_target()

    def execute(self):
        """执行断开命令"""
        self.canvas.connection_manager.remove_connection(self.connection)

    def undo(self):
        """撤销断开命令"""
        # 使用正确的方法恢复连接
        self.canvas.connection_manager.connecting_port = self.source_port
        self.connection = self.canvas.connection_manager.finish_connection(self.target_port)

class CommandManager:
    """命令管理器，用于管理撤销/重做栈"""

    def __init__(self):
        self.undo_stack = []  # 撤销栈
        self.redo_stack = []  # 重做栈

    def execute(self, command):
        """执行命令并添加到撤销栈"""
        result = command.execute()
        self.undo_stack.append(command)
        self.redo_stack.clear()  # 执行新命令后清空重做栈
        return result

    def undo(self):
        """撤销最近的命令"""
        if self.undo_stack:
            command = self.undo_stack.pop()
            command.undo()
            self.redo_stack.append(command)
            return True
        return False

    def redo(self):
        """重做最近撤销的命令"""
        if self.redo_stack:
            command = self.redo_stack.pop()
            command.execute()
            self.undo_stack.append(command)
            return True
        return False

    def can_undo(self):
        """是否可以撤销"""
        return len(self.undo_stack) > 0

    def can_redo(self):
        """是否可以重做"""
        return len(self.redo_stack) > 0