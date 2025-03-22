import json
from typing import Dict, List, Union, Optional, Any


class TaskNode:
    """任务流水线节点类"""

    def __init__(self, name: str, **kwargs):
        """
        初始化节点对象

        Args:
            name: 节点名称
            **kwargs: 节点的其他属性
        """
        self.name = name

        # 基本属性
        self.recognition = kwargs.get('recognition', 'DirectHit')
        self.action = kwargs.get('action', 'DoNothing')
        self.next = kwargs.get('next', [])
        self.interrupt = kwargs.get('interrupt', [])

        # 扩展属性
        self.is_sub = kwargs.get('is_sub', False)
        self.rate_limit = kwargs.get('rate_limit', 1000)
        self.timeout = kwargs.get('timeout', 20 * 1000)
        self.on_error = kwargs.get('on_error', [])
        self.timeout_next = kwargs.get('timeout_next', [])
        self.inverse = kwargs.get('inverse', False)
        self.enabled = kwargs.get('enabled', True)
        self.pre_delay = kwargs.get('pre_delay', 200)
        self.post_delay = kwargs.get('post_delay', 200)
        self.pre_wait_freezes = kwargs.get('pre_wait_freezes', 0)
        self.post_wait_freezes = kwargs.get('post_wait_freezes', 0)
        self.focus = kwargs.get('focus', False)

        # 算法特有属性
        self._algorithm_properties = {}
        for key, value in kwargs.items():
            if key not in self.__dict__:
                self._algorithm_properties[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """
        将节点转换为字典格式

        Returns:
            包含节点所有属性的字典
        """
        result = {
            'recognition': self.recognition,
            'action': self.action
        }

        # 只有非空的next才添加
        if self.next:
            if isinstance(self.next, list) and len(self.next) == 1:
                result['next'] = self.next[0]
            else:
                result['next'] = self.next

        # 添加其他非默认值的基本属性
        if self.interrupt:
            result['interrupt'] = self.interrupt
        if self.is_sub:
            result['is_sub'] = self.is_sub
        if self.rate_limit != 1000:
            result['rate_limit'] = self.rate_limit
        if self.timeout != 20 * 1000:
            result['timeout'] = self.timeout
        if self.on_error:
            result['on_error'] = self.on_error
        if self.timeout_next:
            result['timeout_next'] = self.timeout_next
        if self.inverse:
            result['inverse'] = self.inverse
        if not self.enabled:
            result['enabled'] = self.enabled
        if self.pre_delay != 200:
            result['pre_delay'] = self.pre_delay
        if self.post_delay != 200:
            result['post_delay'] = self.post_delay
        if self.pre_wait_freezes:
            result['pre_wait_freezes'] = self.pre_wait_freezes
        if self.post_wait_freezes:
            result['post_wait_freezes'] = self.post_wait_freezes
        if self.focus:
            result['focus'] = self.focus

        # 添加算法特有属性
        result.update(self._algorithm_properties)

        return result

    def __str__(self) -> str:
        """
        返回节点的字符串表示

        Returns:
            节点的字符串表示
        """
        return f"TaskNode({self.name}): recognition={self.recognition}, action={self.action}, next={self.next}"

    def add_next_node(self, node_name: Union[str, List[str]]) -> None:
        """
        添加后继节点

        Args:
            node_name: 要添加的节点名称或节点名称列表
        """
        if isinstance(node_name, list):
            if isinstance(self.next, list):
                self.next.extend(node_name)
            else:
                self.next = [self.next] if self.next else []
                self.next.extend(node_name)
        else:
            if isinstance(self.next, list):
                self.next.append(node_name)
            else:
                if self.next:
                    self.next = [self.next, node_name]
                else:
                    self.next = node_name

    def add_algorithm_property(self, key: str, value: Any) -> None:
        """
        添加算法特有属性

        Args:
            key: 属性名
            value: 属性值
        """
        self._algorithm_properties[key] = value

    def get_algorithm_property(self, key: str, default: Any = None) -> Any:
        """
        获取算法特有属性

        Args:
            key: 属性名
            default: 默认值，当属性不存在时返回

        Returns:
            属性值或默认值
        """
        return self._algorithm_properties.get(key, default)


class Pipeline:
    """任务流水线类"""

    def __init__(self):
        """初始化流水线对象"""
        self.nodes: Dict[str, TaskNode] = {}

    def add_node(self, node: TaskNode) -> None:
        """
        添加节点

        Args:
            node: 要添加的节点对象
        """
        self.nodes[node.name] = node

    def get_node(self, name: str) -> Optional[TaskNode]:
        """
        获取指定名称的节点

        Args:
            name: 节点名称

        Returns:
            节点对象，若不存在则返回None
        """
        return self.nodes.get(name)

    def get_nodes_by_recognition(self, recognition_type: str) -> List[TaskNode]:
        """
        获取所有使用指定识别算法的节点

        Args:
            recognition_type: 识别算法类型

        Returns:
            使用该识别算法的节点列表
        """
        return [node for node in self.nodes.values() if node.recognition == recognition_type]

    def get_nodes_by_action(self, action_type: str) -> List[TaskNode]:
        """
        获取所有使用指定执行动作的节点

        Args:
            action_type: 执行动作类型

        Returns:
            使用该执行动作的节点列表
        """
        return [node for node in self.nodes.values() if node.action == action_type]

    def _collect_referenced_nodes(self, attribute_name: str) -> set:
        """
        收集所有被指定属性引用的节点名称

        Args:
            attribute_name: 属性名称

        Returns:
            被引用的节点名称集合
        """
        referenced = set()

        for node in self.nodes.values():
            attr_value = getattr(node, attribute_name)
            if isinstance(attr_value, str):
                referenced.add(attr_value)
            elif isinstance(attr_value, list):
                referenced.update(attr_value)

        return referenced

    def get_entry_nodes(self) -> List[TaskNode]:
        """
        获取所有入口节点（没有被其他节点引用的节点）

        Returns:
            入口节点列表
        """
        all_referenced = set()

        # 收集所有被引用的节点
        for attr in ['next', 'interrupt', 'on_error', 'timeout_next']:
            all_referenced.update(self._collect_referenced_nodes(attr))

        # 找出没有被引用的节点
        return [node for name, node in self.nodes.items() if name not in all_referenced]

    def to_dict(self) -> Dict[str, Dict]:
        """
        将流水线转换为字典格式

        Returns:
            包含所有节点的字典
        """
        return {name: node.to_dict() for name, node in self.nodes.items()}

    def to_json(self, indent: int = 4) -> str:
        """
        将流水线转换为JSON字符串

        Args:
            indent: JSON缩进空格数

        Returns:
            流水线的JSON字符串表示
        """
        return json.dumps(self.to_dict(), indent=indent)

    def save_to_file(self, file_path: str, indent: int = 4) -> None:
        """
        将流水线保存到文件

        Args:
            file_path: 文件路径
            indent: JSON缩进空格数
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Dict]) -> 'Pipeline':
        """
        从字典创建流水线

        Args:
            data: 包含节点数据的字典

        Returns:
            流水线对象
        """
        pipeline = cls()
        for name, node_data in data.items():
            node = TaskNode(name, **node_data)
            pipeline.add_node(node)
        return pipeline

    @classmethod
    def from_json(cls, json_str: str) -> 'Pipeline':
        """
        从JSON字符串创建流水线

        Args:
            json_str: JSON字符串

        Returns:
            流水线对象
        """
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def load_from_file(cls, file_path: str) -> 'Pipeline':
        """
        从文件加载流水线

        Args:
            file_path: 文件路径

        Returns:
            流水线对象
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))

    def __str__(self) -> str:
        """
        返回流水线的字符串表示

        Returns:
            流水线的字符串表示
        """
        return f"Pipeline with {len(self.nodes)} nodes: {', '.join(self.nodes.keys())}"