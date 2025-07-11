import copy
import json
import os
from pathlib import Path

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QMenu
from qasync import asyncSlot

from src.canvas_commands import AddNodeCommand, DeleteNodesCommand, DisconnectNodesCommand
from src.config_manager import config_manager
from src.maafw import maafw
from src.pipeline import TaskNode
from src.views.node_system.node import Node


class ContextMenus:
    """处理画布上的右键菜单"""

    def __init__(self, canvas):
        self.canvas = canvas

    def show_node_context_menu(self, node, global_pos):
        """显示节点右键菜单

        Args:
            node: 被右键点击的节点
            scene_pos: 场景坐标中的点击位置
            global_pos: 全局坐标中的点击位置
        """
        menu = QMenu()

        # 是否有多个节点被选中
        selected_nodes = self.canvas.get_selected_nodes()
        multiple_selection = len(selected_nodes) > 1

        # 复制操作
        copy_action = menu.addAction("复制节点")
        copy_action.triggered.connect(
            lambda: self._copy_nodes(selected_nodes if multiple_selection else [node])
        )

        # 删除操作
        delete_action = menu.addAction("删除节点")
        delete_action.triggered.connect(
            lambda: self._delete_nodes(selected_nodes if multiple_selection else [node])
        )

        # 分隔线
        menu.addSeparator()

        # 连接相关操作（仅针对单个节点）
        if not multiple_selection:
            # 获取与此节点的连接
            connections = self._get_node_connections(node)

            if connections:
                disconnect_menu = QMenu("断开连接", menu)
                # disconnect_menu = QMenu("断开连接", menu)

                for conn in connections:
                    source_node = conn.start_port.parent_node
                    target_node = conn.end_port.parent_node
                    if not source_node.task_node or not target_node.task_node:
                        continue
                    # 根据端口类型获取端口名称
                    source_port_name = source_node.task_node.name
                    target_port_name = target_node.task_node.name
                    # 创建断开连接的动作
                    connection_label = f"{source_port_name} → {target_port_name}"
                    disconnect_menu.addAction(connection_label).triggered.connect(
                        lambda checked=False, c=conn: self._disconnect_nodes(c)
                    )

                menu.addMenu(disconnect_menu)
        menu.addSeparator()
        if not multiple_selection and node.task_node:
            # Create a debug submenu instead of a single action
            debug_menu = QMenu("调试", menu)

            # Add the three debug options to the submenu
            debug_action = debug_menu.addAction("从该节点开始调试")
            debug_action.triggered.connect(
                lambda checked=False, n=node.task_node: self.run_task(n)
            )
            debug_menu.addSeparator()
            debug_only_action = debug_menu.addAction("仅调试该节点")
            debug_only_action.triggered.connect(
                lambda checked=False, n=node.task_node: self.run_task(n, debug_only=True)
            )

            recognize_only_action = debug_menu.addAction("仅识别该节点")
            recognize_only_action.triggered.connect(
                lambda checked=False, n=node.task_node: self.run_task(n, debug_only=True, recognize_only=True)
            )

            # Add the submenu to the main context menu
            menu.addMenu(debug_menu)
        # 显示菜单
        menu.exec(global_pos)

    @asyncSlot()
    async def run_task(self, node, debug_only=False, recognize_only=False):
        if debug_only:
            debug_node = copy.deepcopy(node)
            debug_node.name = f"debug_{node.name}"

            # Set next, interrupt, and on_error attributes to None
            debug_node.next = None
            debug_node.interrupt = None
            debug_node.on_error = None
            if recognize_only:
                debug_node.action = None
            print(f"开始调试节点:{debug_node.name},参数:{debug_node.to_json()}")

            # Run the debug node instead of the original
            maafw.run_task(debug_node.name, json.loads(debug_node.to_json()))
        else:
            print(f"开始运行任务id:{node.name}")
            await self.connect_mfw_res()
            maafw.run_task(node.name)

    @asyncSlot()
    async def connect_mfw_res(self):
        """连接到指定设备"""
        try:
            res_path = Path(config_manager.config["recent_files"]["base_resource_path"])
            self.canvas.save_to_file()

            success, error = await maafw.load_resource([res_path])
            if success:
                print(f"成功连接资源: {res_path}")
            else:
                print(f"连接资源失败: {error}")
            agent_id=await maafw.create_agent("maa-agent-server")
            await maafw.connect_agent()
            if agent_id:
                print(f"agent_id: {agent_id}")
        except Exception as e:
            print(f"连接资源时发生错误: {str(e)}")
            self.is_connected = False

    def show_canvas_context_menu(self, scene_pos, global_pos):
        """显示画布右键菜单

        Args:
            scene_pos: 场景坐标中的点击位置
            global_pos: 全局坐标中的点击位置
        """
        menu = QMenu()

        # 基本画布操作
        menu.addAction("居中视图").triggered.connect(
            lambda: self.canvas.center_on_content()
        )

        menu.addAction("重置视图").triggered.connect(
            lambda: self._reset_view()
        )

        # 分隔线
        menu.addSeparator()

        # 粘贴操作（如果剪贴板中有内容）
        paste_action = menu.addAction("粘贴节点")
        paste_action.setEnabled(hasattr(self.canvas, 'clipboard') and bool(self.canvas.clipboard))
        paste_action.triggered.connect(
            lambda: self._paste_nodes(scene_pos)
        )

        # 添加节点操作
        add_node_menu = QMenu("添加节点", menu)

        # 这里可以根据可用的节点类型动态填充
        node_types = [
            ("通用节点", "通用节点")
        ]

        for node_title, node_type in node_types:
            add_node_menu.addAction(node_title).triggered.connect(
                lambda checked=False, t=node_title, type=node_type:
                self._add_common_node(scene_pos)
            )

        menu.addMenu(add_node_menu)

        # 选择操作
        menu.addSeparator()
        menu.addAction("全选").triggered.connect(
            lambda: self._select_all_nodes()
        )

        select_by_type_menu = QMenu("按名称选择", menu)

        # 根据存在的节点类型填充
        node_types_map = {}
        for node in self.canvas.node_manager.nodes:
            node_type = node.title.split(' ')[0]  # 简单地以空格分隔取第一部分作为类型
            if node_type not in node_types_map:
                node_types_map[node_type] = []
            node_types_map[node_type].append(node)

        for node_type, nodes in node_types_map.items():
            select_by_type_menu.addAction(f"{node_type} ({len(nodes)})").triggered.connect(
                lambda checked=False, nodes=nodes: self._select_nodes(nodes)
            )

        if node_types_map:
            menu.addMenu(select_by_type_menu)

        # 撤销/重做操作（如果已实现）
        if hasattr(self.canvas, 'command_manager'):
            menu.addSeparator()

            undo_action = menu.addAction("撤销")
            undo_action.setEnabled(self.canvas.command_manager.can_undo())
            undo_action.triggered.connect(
                lambda: self.canvas.command_manager.undo()
            )

            redo_action = menu.addAction("重做")
            redo_action.setEnabled(self.canvas.command_manager.can_redo())
            redo_action.triggered.connect(
                lambda: self.canvas.command_manager.redo()
            )

        # 显示菜单
        menu.exec(global_pos)

    def _copy_nodes(self, nodes):
        """将节点复制到剪贴板"""
        if not nodes:
            return

        # 创建节点的数据字典列表
        clipboard_data = []
        for node in nodes:
            # 深拷贝 task_node 并处理
            task_node_copy = None
            if node.task_node:
                task_node_copy = copy.deepcopy(node.task_node)
                # 修改 task_node 的 name，添加 _copy 后缀
                task_node_copy.name = f"{task_node_copy.name}_copy"
                # 移除 next, interrupt, on_error 属性
                task_node_copy.next = None
                task_node_copy.interrupt = None
                task_node_copy.on_error = None

            # 创建包含节点信息的字典
            node_data = {
                'title': node.title,
                'position': node.pos(),  # QPointF position
                'task_node': task_node_copy
            }
            clipboard_data.append(node_data)

        # 保存到画布的剪贴板属性
        self.canvas.clipboard = clipboard_data
        self.canvas.info_label.setText(f"已复制 {len(nodes)} 个节点到剪贴板")

    def _paste_nodes(self, scene_pos):
        """从剪贴板粘贴节点"""
        if not hasattr(self.canvas, 'clipboard') or not self.canvas.clipboard:
            return

        # 清除当前选择
        self.canvas.scene.clearSelection()

        # 计算新位置的偏移量
        if len(self.canvas.clipboard) == 1:
            # 单节点粘贴，直接放在点击位置
            offset_x = scene_pos.x() - self.canvas.clipboard[0]['position'].x()
            offset_y = scene_pos.y() - self.canvas.clipboard[0]['position'].y()
        else:
            # 多节点粘贴，保持相对位置，整体移动到点击位置
            min_x = min(data['position'].x() for data in self.canvas.clipboard)
            min_y = min(data['position'].y() for data in self.canvas.clipboard)
            offset_x = scene_pos.x() - min_x
            offset_y = scene_pos.y() - min_y

        # 获取已存在的所有节点标题
        existing_titles = [node.title for node in self.canvas.node_manager.nodes]

        # 创建新节点
        new_nodes = []
        for node_data in self.canvas.clipboard:
            # 生成唯一的标题
            base_title = node_data['title']
            new_title = base_title
            title_count = 1

            # 如果标题重复，添加数字后缀避免重复
            while new_title in existing_titles:
                new_title = f"{base_title}_copy{title_count}"
                title_count += 1

            existing_titles.append(new_title)  # 添加到列表中避免同批次粘贴的重复

            # 创建新节点
            new_node = Node(title=new_title)

            # 如果有 task_node，复制并更新名称
            if node_data.get('task_node'):
                task_node_copy = copy.deepcopy(node_data['task_node'])
                task_node_copy.name = new_title  # 更新 task_node 的名称
                new_node.set_task_node(task_node_copy)

            # 设置位置
            new_pos = QPointF(
                node_data['position'].x() + offset_x,
                node_data['position'].y() + offset_y
            )
            new_node.setPos(new_pos)

            # 将节点添加到画布并选中
            self.canvas.add_node(new_node)
            new_node.setSelected(True)
            new_nodes.append(new_node)

        # 使用撤销/重做命令添加节点
        if hasattr(self.canvas, 'command_manager') and new_nodes:
            for node in new_nodes:
                self.canvas.command_manager.execute(AddNodeCommand(node, self.canvas))

        self.canvas.info_label.setText(f"已粘贴 {len(new_nodes)} 个节点")
    def _delete_nodes(self, nodes):
        """删除节点"""
        if not nodes:
            return

        # 使用撤销/重做命令删除节点
        if hasattr(self.canvas, 'command_manager'):
            self.canvas.command_manager.execute(DeleteNodesCommand(nodes, self.canvas))
        else:
            # 没有命令管理器时的直接删除
            for node in nodes:
                self.canvas.remove_node(node)

        self.canvas.info_label.setText(f"已删除 {len(nodes)} 个节点")

    def _get_node_connections(self, node):
        """获取与节点相关的所有连接"""
        connections = []

        # 输入端口的连接
        input_port = node.get_input_port()
        if input_port and input_port.is_connected():
            connections.extend(input_port.get_connections())

        # 输出端口的连接
        output_ports = node.get_output_ports()
        if isinstance(output_ports, dict):
            output_ports = list(output_ports.values())

        for port in output_ports:
            connections.extend(port.get_connections())

        return connections

    def _disconnect_nodes(self, connection):
        """断开节点连接"""
        if hasattr(self.canvas, 'command_manager'):
            self.canvas.command_manager.execute(DisconnectNodesCommand(connection, self.canvas))
        else:
            self.canvas.remove_connection(connection)

        source_node = connection.source_port.parent_node
        target_node = connection.target_port.parent_node
        self.canvas.info_label.setText(f"已断开 {source_node.id} 到 {target_node.id} 的连接")

    def _snap_to_grid(self, nodes):
        """将节点对齐到网格"""
        if not nodes:
            return

        # 记录原始位置用于撤销
        old_positions = [node.pos() for node in nodes]

        # 对齐到网格
        grid_size = 20
        new_positions = []

        for node in nodes:
            pos = node.pos()
            snapped_x = round(pos.x() / grid_size) * grid_size
            snapped_y = round(pos.y() / grid_size) * grid_size
            node.setPos(snapped_x, snapped_y)
            new_positions.append(QPointF(snapped_x, snapped_y))
            self.canvas.connection_manager.update_connections_for_node(node)

        # 注册撤销/重做命令
        if hasattr(self.canvas, 'command_manager'):
            from canvas_commands import MoveNodesCommand
            # 使用新创建的命令替换当前命令，而不是添加新命令
            self.canvas.command_manager.execute(
                MoveNodesCommand(nodes, old_positions, new_positions, self.canvas)
            )

        self.canvas.info_label.setText(f"已将 {len(nodes)} 个节点对齐到网格")

    def _reset_view(self):
        """重置视图到默认状态"""
        self.canvas.view.resetTransform()
        self.canvas.view.centerOn(0, 0)
        self.canvas.info_label.setText("视图已重置")

    def _add_common_node(self, scene_pos):
        """
        在指定位置添加新节点

        Args:
            scene_pos: 场景中的位置
        """
        # 获取当前打开的文件路径
        full_path = config_manager.config.get("recent_files", {}).get("current_opened_file")
        default_title = "通用节点"

        # 提取文件名（不含路径和扩展名）
        if full_path:
            base_name = os.path.basename(full_path)
            filename = os.path.splitext(base_name)[0]
            base_title = filename or default_title
        else:
            base_title = default_title

        display_title = base_title
        title_count = 1

        # 获取已存在的所有节点标题
        existing_titles = [node.title for node in self.canvas.node_manager.nodes]

        # 如果标题重复，添加数字后缀避免重复
        while display_title in existing_titles:
            display_title = f"{base_title}{title_count}"
            title_count += 1
        # 创建新节点 - 不再传递ID参数
        new_node = Node(title=display_title)

        task_node = TaskNode(display_title)
        new_node.set_task_node(task_node)

        # 设置节点位置并对齐到网格
        grid_size = 20
        snapped_x = round(scene_pos.x() / grid_size) * grid_size
        snapped_y = round(scene_pos.y() / grid_size) * grid_size
        new_node.setPos(snapped_x, snapped_y)

        # 将节点添加到画布并选中
        self.canvas.add_node(new_node)

        # 清除之前的选择并选中新节点
        self.canvas.scene.clearSelection()
        new_node.setSelected(True)

        # 使用撤销/重做命令添加节点
        if hasattr(self.canvas, 'command_manager'):
            self.canvas.command_manager.execute(AddNodeCommand(new_node, self.canvas))

        self.canvas.info_label.setText(f"已添加新节点: {display_title}")

    def _select_all_nodes(self):
        """选择所有节点"""
        for node in self.canvas.node_manager.nodes:
            node.setSelected(True)

        self.canvas.info_label.setText(f"已选择所有节点 ({len(self.canvas.node_manager.nodes)})")

    def _select_nodes(self, nodes):
        """选择指定的节点组"""
        self.canvas.scene.clearSelection()

        for node in nodes:
            node.setSelected(True)

        self.canvas.info_label.setText(f"已选择 {len(nodes)} 个节点")
