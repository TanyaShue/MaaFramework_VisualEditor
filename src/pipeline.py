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

    def __init__(self, name: str, **kwargs):
        """
        初始化节点对象

        Args:
            name: 节点名称
            **kwargs: 节点的所有属性
        """
        self.name = name

        # 基本属性
        self.recognition = kwargs.get('recognition', 'DirectHit')
        self.action = kwargs.get('action', 'DoNothing')
        self.next = kwargs.get('next', [])
        self.interrupt = kwargs.get('interrupt', [])
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

        # 识别算法通用属性
        self.roi = kwargs.get('roi', None)
        self.roi_offset = kwargs.get('roi_offset', None)
        self.order_by = kwargs.get('order_by', 'Horizontal')
        self.index = kwargs.get('index', 0)

        # 模板匹配相关属性 (TemplateMatch, FeatureMatch)
        self.template = kwargs.get('template', None)
        self.threshold = kwargs.get('threshold', 0.7)
        self.method = kwargs.get('method', 5)
        self.green_mask = kwargs.get('green_mask', False)

        # 特征匹配特有属性 (FeatureMatch)
        self.count = kwargs.get('count', 4)
        self.detector = kwargs.get('detector', 'SIFT')
        self.ratio = kwargs.get('ratio', 0.6)

        # 颜色匹配特有属性 (ColorMatch)
        self.lower = kwargs.get('lower', None)
        self.upper = kwargs.get('upper', None)
        self.connected = kwargs.get('connected', False)

        # OCR特有属性
        self.expected = kwargs.get('expected', None)
        self.replace = kwargs.get('replace', None)
        self.only_rec = kwargs.get('only_rec', False)
        self.model = kwargs.get('model', '')

        # 神经网络特有属性 (NeuralNetworkClassify, NeuralNetworkDetect)
        self.labels = kwargs.get('labels', None)

        # 自定义识别算法属性
        self.custom_recognition = kwargs.get('custom_recognition', None)
        self.custom_recognition_param = kwargs.get('custom_recognition_param', None)

        # 动作相关属性
        self.target = kwargs.get('target', True)
        self.target_offset = kwargs.get('target_offset', None)

        # 滑动特有属性
        self.begin = kwargs.get('begin', True)
        self.end = kwargs.get('end', True)
        self.begin_offset = kwargs.get('begin_offset', None)
        self.end_offset = kwargs.get('end_offset', None)
        self.duration = kwargs.get('duration', 200)

        # 多指滑动属性
        self.swipes = kwargs.get('swipes', None)

        # 按键特有属性
        self.key = kwargs.get('key', None)

        # 输入文本特有属性
        self.input_text = kwargs.get('input_text', None)

        # 应用相关属性
        self.package = kwargs.get('package', None)

        # 命令相关属性
        self.exec = kwargs.get('exec', None)
        self.args = kwargs.get('args', None)
        self.detach = kwargs.get('detach', False)

        # 自定义动作属性
        self.custom_action = kwargs.get('custom_action', None)
        self.custom_action_param = kwargs.get('custom_action_param', None)

        # 保存其他额外属性
        self._extra_properties = {}
        for key, value in kwargs.items():
            if not hasattr(self, key):
                self._extra_properties[key] = value

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

        # 添加算法相关属性（根据算法类型）
        if self.recognition == "TemplateMatch":
            self._add_if_not_none(result, 'template', self.template)
            self._add_if_not_default(result, 'threshold', self.threshold, 0.7)
            self._add_if_not_default(result, 'method', self.method, 5)
            self._add_if_true(result, 'green_mask', self.green_mask)

        elif self.recognition == "FeatureMatch":
            self._add_if_not_none(result, 'template', self.template)
            self._add_if_not_default(result, 'count', self.count, 4)
            self._add_if_not_default(result, 'detector', self.detector, 'SIFT')
            self._add_if_not_default(result, 'ratio', self.ratio, 0.6)
            self._add_if_true(result, 'green_mask', self.green_mask)

        elif self.recognition == "ColorMatch":
            self._add_if_not_none(result, 'lower', self.lower)
            self._add_if_not_none(result, 'upper', self.upper)
            self._add_if_not_default(result, 'method', self.method, 4)
            self._add_if_not_default(result, 'count', self.count, 1)
            self._add_if_true(result, 'connected', self.connected)

        elif self.recognition == "OCR":
            self._add_if_not_none(result, 'expected', self.expected)
            self._add_if_not_default(result, 'threshold', self.threshold, 0.3)
            self._add_if_not_none(result, 'replace', self.replace)
            self._add_if_true(result, 'only_rec', self.only_rec)
            self._add_if_not_empty(result, 'model', self.model)

        elif self.recognition in ["NeuralNetworkClassify", "NeuralNetworkDetect"]:
            self._add_if_not_empty(result, 'model', self.model)
            self._add_if_not_none(result, 'expected', self.expected)
            if self.recognition == "NeuralNetworkDetect":
                self._add_if_not_default(result, 'threshold', self.threshold, 0.3)
            self._add_if_not_none(result, 'labels', self.labels)

        elif self.recognition == "Custom":
            self._add_if_not_none(result, 'custom_recognition', self.custom_recognition)
            self._add_if_not_none(result, 'custom_recognition_param', self.custom_recognition_param)

        # 添加通用识别相关属性
        self._add_if_not_none(result, 'roi', self.roi)
        self._add_if_not_none(result, 'roi_offset', self.roi_offset)
        self._add_if_not_default(result, 'order_by', self.order_by, 'Horizontal')
        self._add_if_not_default(result, 'index', self.index, 0)

        # 添加动作相关属性（根据动作类型）
        if self.action == "Click":
            self._add_if_not_true(result, 'target', self.target)
            self._add_if_not_none(result, 'target_offset', self.target_offset)

        elif self.action == "Swipe":
            self._add_if_not_true(result, 'begin', self.begin)
            self._add_if_not_true(result, 'end', self.end)
            self._add_if_not_none(result, 'begin_offset', self.begin_offset)
            self._add_if_not_none(result, 'end_offset', self.end_offset)
            self._add_if_not_default(result, 'duration', self.duration, 200)

        elif self.action == "MultiSwipe":
            self._add_if_not_none(result, 'swipes', self.swipes)

        elif self.action == "Key":
            self._add_if_not_none(result, 'key', self.key)

        elif self.action == "InputText":
            self._add_if_not_none(result, 'input_text', self.input_text)

        elif self.action in ["StartApp", "StopApp"]:
            self._add_if_not_none(result, 'package', self.package)

        elif self.action == "Command":
            self._add_if_not_none(result, 'exec', self.exec)
            self._add_if_not_none(result, 'args', self.args)
            self._add_if_true(result, 'detach', self.detach)

        elif self.action == "Custom":
            self._add_if_not_none(result, 'custom_action', self.custom_action)
            self._add_if_not_none(result, 'custom_action_param', self.custom_action_param)
            self._add_if_not_true(result, 'target', self.target)
            self._add_if_not_none(result, 'target_offset', self.target_offset)

        # 添加其他额外属性
        result.update(self._extra_properties)

        return result

    def _add_if_not_none(self, dict_obj: Dict[str, Any], key: str, value: Any) -> None:
        """添加非None值到字典"""
        if value is not None:
            dict_obj[key] = value

    def _add_if_not_default(self, dict_obj: Dict[str, Any], key: str, value: Any, default: Any) -> None:
        """添加非默认值到字典"""
        if value != default:
            dict_obj[key] = value

    def _add_if_not_empty(self, dict_obj: Dict[str, Any], key: str, value: str) -> None:
        """添加非空字符串到字典"""
        if value:
            dict_obj[key] = value

    def _add_if_true(self, dict_obj: Dict[str, Any], key: str, value: bool) -> None:
        """添加True值到字典"""
        if value:
            dict_obj[key] = value

    def _add_if_not_true(self, dict_obj: Dict[str, Any], key: str, value: Any) -> None:
        """添加非True值到字典"""
        if value is not True:
            dict_obj[key] = value

    def __str__(self) -> str:
        """
        返回节点的字符串表示

        Returns:
            节点的字符串表示
        """
        parts = [f"TaskNode({self.name})"]
        parts.append(f"recognition={self.recognition}")
        parts.append(f"action={self.action}")

        if self.next:
            if isinstance(self.next, list):
                parts.append(f"next=[{', '.join(self.next)}]")
            else:
                parts.append(f"next={self.next}")

        if self.interrupt:
            if isinstance(self.interrupt, list):
                parts.append(f"interrupt=[{', '.join(self.interrupt)}]")
            else:
                parts.append(f"interrupt={self.interrupt}")

        if self.on_error:
            if isinstance(self.on_error, list):
                parts.append(f"on_error=[{', '.join(self.on_error)}]")
            else:
                parts.append(f"on_error={self.on_error}")

        if self.timeout_next:
            if isinstance(self.timeout_next, list):
                parts.append(f"timeout_next=[{', '.join(self.timeout_next)}]")
            else:
                parts.append(f"timeout_next={self.timeout_next}")

        if self.is_sub:
            parts.append("is_sub=True")

        if self.inverse:
            parts.append("inverse=True")

        if not self.enabled:
            parts.append("enabled=False")

        # 添加主要算法特有属性
        if self.recognition == "TemplateMatch" and self.template:
            if isinstance(self.template, list):
                parts.append(f"template=[{', '.join(self.template)}]")
            else:
                parts.append(f"template={self.template}")

        elif self.recognition == "OCR" and self.expected:
            if isinstance(self.expected, list):
                parts.append(f"expected=[{', '.join(self.expected)}]")
            else:
                parts.append(f"expected={self.expected}")

        # 添加动作相关属性
        if self.action == "Click" and self.target is not True:
            parts.append(f"target={self.target}")

        elif self.action == "Swipe":
            if self.begin is not True:
                parts.append(f"begin={self.begin}")
            if self.end is not True:
                parts.append(f"end={self.end}")

        return ": ".join(parts)

    def validate(self) -> List[str]:
        """
        验证节点配置是否有效

        Returns:
            错误信息列表，空列表表示验证通过
        """
        errors = []

        # 验证基本属性
        if self.recognition not in self.RECOGNITION_TYPES:
            errors.append(f"Invalid recognition type: {self.recognition}")

        if self.action not in self.ACTION_TYPES:
            errors.append(f"Invalid action type: {self.action}")

        # 验证特定算法所需属性
        if self.recognition == "TemplateMatch":
            if self.template is None:
                errors.append("TemplateMatch requires 'template' property")

        elif self.recognition == "FeatureMatch":
            if self.template is None:
                errors.append("FeatureMatch requires 'template' property")

        elif self.recognition == "ColorMatch":
            if self.lower is None:
                errors.append("ColorMatch requires 'lower' property")
            if self.upper is None:
                errors.append("ColorMatch requires 'upper' property")

        elif self.recognition == "OCR":
            if self.expected is None:
                errors.append("OCR requires 'expected' property")

        elif self.recognition == "NeuralNetworkClassify":
            if not self.model:
                errors.append("NeuralNetworkClassify requires 'model' property")
            if self.expected is None:
                errors.append("NeuralNetworkClassify requires 'expected' property")

        elif self.recognition == "NeuralNetworkDetect":
            if not self.model:
                errors.append("NeuralNetworkDetect requires 'model' property")
            if self.expected is None:
                errors.append("NeuralNetworkDetect requires 'expected' property")

        elif self.recognition == "Custom":
            if self.custom_recognition is None:
                errors.append("Custom recognition requires 'custom_recognition' property")

        # 验证特定动作所需属性
        if self.action == "Key":
            if self.key is None:
                errors.append("Key action requires 'key' property")

        elif self.action == "InputText":
            if self.input_text is None:
                errors.append("InputText action requires 'input_text' property")

        elif self.action in ["StartApp", "StopApp"]:
            if self.package is None:
                errors.append(f"{self.action} action requires 'package' property")

        elif self.action == "Command":
            if self.exec is None:
                errors.append("Command action requires 'exec' property")

        elif self.action == "Custom":
            if self.custom_action is None:
                errors.append("Custom action requires 'custom_action' property")

        return errors

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

    def validate(self) -> Dict[str, List[str]]:
        """
        验证所有节点配置是否有效

        Returns:
            节点名到错误信息列表的映射，空字典表示验证全部通过
        """
        errors = {}

        for node in self.nodes:
            node_errors = node.validate()
            if node_errors:
                errors[node.name] = node_errors

        return errors
open_pipeline=Pipeline()