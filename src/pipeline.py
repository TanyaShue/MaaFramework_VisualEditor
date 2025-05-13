import json
from typing import Dict, List, Union, Optional, Any


class TaskNode:
    """任务流水线节点类"""

    # 支持的识别算法类型
    RECOGNITION_TYPES = [
        "DirectHit", "TemplateMatch", "FeatureMatch", "ColorMatch",
        "OCR", "NeuralNetworkClassify", "NeuralNetworkDetect", "Custom"
    ]

    # 支持的动作类型
    ACTION_TYPES = [
        "DoNothing", "Click", "Swipe", "MultiSwipe", "Key",
        "InputText", "StartApp", "StopApp", "StopTask", "Command", "Custom"
    ]

    # 属性默认值
    DEFAULT_VALUES = {
        "recognition": "DirectHit",
        "action": "DoNothing",
        "next": [],
        "interrupt": [],
        "is_sub": False,
        "rate_limit": 1000,
        "timeout": 20000,
        "on_error": [],
        "inverse": False,
        "enabled": True,
        "pre_delay": 200,
        "post_delay": 200,
        "pre_wait_freezes": 0,
        "post_wait_freezes": 0,
        "focus": False,
        "threshold": None,  # 不同算法有不同默认值
        "method": None,  # 不同算法有不同默认值
        "green_mask": False,
        "count": None,  # 不同算法有不同默认值
        "detector": "SIFT",
        "ratio": 0.6,
        "connected": False,
        "only_rec": False,
        "order_by": "Horizontal",
        "index": 0,
        "target": True,
        "begin": True,
        "end": True,
        "duration": 200,
        "detach": False
    }

    def __init__(self, name: str, **kwargs):
        """
        初始化节点对象

        Args:
            name: 节点名称
            **kwargs: 节点的所有属性
        """
        self.name = name

        # 初始化所有属性为None
        # 基本属性
        self.recognition = kwargs.get('recognition')
        self.action = kwargs.get('action')
        self.next = kwargs.get('next')
        self.interrupt = kwargs.get('interrupt')
        self.is_sub = kwargs.get('is_sub')
        self.rate_limit = kwargs.get('rate_limit')
        self.timeout = kwargs.get('timeout')
        self.on_error = kwargs.get('on_error')
        self.inverse = kwargs.get('inverse')
        self.enabled = kwargs.get('enabled')
        self.pre_delay = kwargs.get('pre_delay')
        self.post_delay = kwargs.get('post_delay')
        self.pre_wait_freezes = kwargs.get('pre_wait_freezes')
        self.post_wait_freezes = kwargs.get('post_wait_freezes')
        self.focus = kwargs.get('focus')

        # 识别算法通用属性
        self.roi = kwargs.get('roi')
        self.roi_offset = kwargs.get('roi_offset')
        self.order_by = kwargs.get('order_by')
        self.index = kwargs.get('index')

        # 模板匹配相关属性 (TemplateMatch, FeatureMatch)
        self.template = kwargs.get('template')
        self.threshold = kwargs.get('threshold')
        self.method = kwargs.get('method')
        self.green_mask = kwargs.get('green_mask')

        # 特征匹配特有属性 (FeatureMatch)
        self.count = kwargs.get('count')
        self.detector = kwargs.get('detector')
        self.ratio = kwargs.get('ratio')

        # 颜色匹配特有属性 (ColorMatch)
        self.lower = kwargs.get('lower')
        self.upper = kwargs.get('upper')
        self.connected = kwargs.get('connected')

        # OCR特有属性
        self.expected = kwargs.get('expected')
        self.replace = kwargs.get('replace')
        self.only_rec = kwargs.get('only_rec')
        self.model = kwargs.get('model')

        # 神经网络特有属性 (NeuralNetworkClassify, NeuralNetworkDetect)
        self.labels = kwargs.get('labels')

        # 自定义识别算法属性
        self.custom_recognition = kwargs.get('custom_recognition')
        self.custom_recognition_param = kwargs.get('custom_recognition_param')

        # 动作相关属性
        self.target = kwargs.get('target')
        self.target_offset = kwargs.get('target_offset')

        # 滑动特有属性
        self.begin = kwargs.get('begin')
        self.end = kwargs.get('end')
        self.begin_offset = kwargs.get('begin_offset')
        self.end_offset = kwargs.get('end_offset')
        self.duration = kwargs.get('duration')

        # 多指滑动属性
        self.swipes = kwargs.get('swipes')

        # 按键特有属性
        self.key = kwargs.get('key')

        # 输入文本特有属性
        self.input_text = kwargs.get('input_text')

        # 应用相关属性
        self.package = kwargs.get('package')

        # 命令相关属性
        self.exec = kwargs.get('exec')
        self.args = kwargs.get('args')
        self.detach = kwargs.get('detach')

        # 自定义动作属性
        self.custom_action = kwargs.get('custom_action')
        self.custom_action_param = kwargs.get('custom_action_param')

    def to_dict(self) -> Dict[str, Any]:
        """
        将节点转换为字典格式，只包含非None的属性
        Returns:
            包含节点非None属性的字典
        """
        result = {}
        # 列举所有可能的属性键
        keys = [
            'recognition', 'action', 'interrupt', 'is_sub', 'rate_limit', 'timeout', 'on_error', 'next',
            'inverse', 'enabled', 'pre_delay', 'post_delay', 'pre_wait_freezes', 'post_wait_freezes', 'focus',
            'roi', 'roi_offset', 'order_by', 'index', 'template', 'threshold', 'method', 'green_mask', 'count',
            'detector', 'ratio', 'lower', 'upper', 'connected', 'expected', 'replace', 'only_rec', 'model',
            'labels', 'custom_recognition', 'custom_recognition_param', 'target', 'target_offset', 'begin', 'end',
            'begin_offset', 'end_offset', 'duration', 'swipes', 'key', 'input_text', 'package', 'exec', 'args',
            'detach', 'custom_action', 'custom_action_param'
        ]
        # 对每个键使用 getattr 安全获取属性值
        for key in keys:
            value = getattr(self, key, None)
            self._add_if_not_none(result, key, value)
        return result

    def _add_if_not_none(self, dict_obj: Dict[str, Any], key: str, value: Any) -> None:
        """添加非None值到字典"""
        if value is not None:
            dict_obj[key] = value

    def __str__(self) -> str:
        """
        返回节点的字符串表示

        Returns:
            节点的字符串表示
        """

        return self.to_json()

    def to_json(self, indent=None) -> str:
        """
        将节点转换为JSON格式字符串，格式为 {"节点名称": {节点属性}}

        Args:
            indent: JSON字符串的缩进级别，None表示无缩进的紧凑格式

        Returns:
            表示节点的JSON格式字符串
        """
        # 获取节点属性字典
        node_dict = self.to_dict()

        # 创建以节点名称为键的字典
        result_dict = {self.name: node_dict}

        # 转换为JSON字符串
        return json.dumps(result_dict, ensure_ascii=False, indent=indent)

    @staticmethod
    def from_json(json_str: str) -> 'TaskNode':
        """
        从JSON字符串创建TaskNode对象，JSON格式为 {"节点名称": {节点属性}}

        Args:
            json_str: 表示节点的JSON格式字符串

        Returns:
            根据JSON字符串创建的TaskNode对象

        Raises:
            ValueError: 当JSON字符串无法解析或格式不正确时抛出
        """
        try:
            # 解析JSON字符串为字典
            data = json.loads(json_str)

            # 确认JSON格式为 {"节点名称": {节点属性}}
            if len(data) != 1:
                raise ValueError("JSON must contain exactly one node with format {'node_name': {properties}}")

            # 获取节点名称和属性
            node_name = next(iter(data))
            node_properties = data[node_name]

            # 确保node_properties是字典
            if not isinstance(node_properties, dict):
                raise ValueError("Node properties must be a dictionary")

            # 创建TaskNode对象并返回
            return TaskNode(node_name, **node_properties)

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {e}")
        except Exception as e:
            raise ValueError(f"Failed to create TaskNode from JSON: {e}")


class Pipeline:
    """任务流水线类"""

    def __init__(self):
        """初始化流水线对象"""
        self.nodes: List[TaskNode] = []
        self.current_file = None

    def add_node(self, node: TaskNode) -> None:
        """
        添加节点

        Args:
            node: 要添加的节点对象
        """
        self.nodes.append(node)

    def get_nodes_by_recognition(self, recognition_type: str) -> List[TaskNode]:
        """
        获取所有使用指定识别算法的节点

        Args:
            recognition_type: 识别算法类型

        Returns:
            使用该识别算法的节点列表
        """
        return [node for node in self.nodes if node.recognition == recognition_type]

    def get_nodes_by_action(self, action_type: str) -> List[TaskNode]:
        """
        获取所有使用指定执行动作的节点

        Args:
            action_type: 执行动作类型

        Returns:
            使用该执行动作的节点列表
        """
        return [node for node in self.nodes if node.action == action_type]

    def to_dict(self) -> Dict[str, Dict]:
        """
        将流水线转换为字典格式

        Returns:
            包含所有节点的字典
        """
        return {node.name: node.to_dict() for node in self.nodes}

    def to_json(self, indent: int = 4) -> str:
        """
        将流水线转换为JSON字符串

        Args:
            indent: JSON缩进空格数

        Returns:
            流水线的JSON字符串表示
        """
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save_to_file(self, file_path: str, indent: int = 4) -> None:
        """
        将流水线保存到文件

        Args:
            file_path: 文件路径
            indent: JSON缩进空格数
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=indent)

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

    def load_from_file(self, file_path: str) -> 'Pipeline':
        """
        从文件加载节点到当前流水线实例中

        Args:
            file_path: 文件路径

        Returns:
            当前流水线对象（用于方法链式调用）
        """
        self.current_file = file_path
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for name, node_data in data.items():
                    node = TaskNode(name, **node_data)
                    self.add_node(node)
            return self
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON file: {e}")
        except Exception as e:
            raise IOError(f"Failed to load pipeline from file: {e}")

    def __str__(self) -> str:
        """
        返回流水线的字符串表示

        Returns:
            包含所有节点内容的字典的字符串表示
        """
        nodes_dict = {node.name: node.to_dict() for node in self.nodes}
        return json.dumps(nodes_dict, ensure_ascii=False, indent=2)



open_pipeline = Pipeline()