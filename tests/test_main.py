import sys
import asyncio
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QTextEdit
from PySide6.QtCore import Signal
import qasync
from qasync import asyncSlot, asyncClose


class MainWindow(QMainWindow):
    # 定义自定义信号 (PySide6 使用 Signal 而不是 pyqtSignal)
    data_received = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("QAsync AsyncSlot 示例 (PySide6)")
        self.setGeometry(100, 100, 600, 400)

        # 创建中央部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 创建 UI 组件
        self.status_label = QLabel("状态: 就绪")
        layout.addWidget(self.status_label)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)

        # 创建按钮并连接到异步槽
        self.fetch_button = QPushButton("获取数据 (异步)")
        self.fetch_button.clicked.connect(self.on_fetch_clicked)
        layout.addWidget(self.fetch_button)

        self.process_button = QPushButton("处理数据 (异步)")
        self.process_button.clicked.connect(self.on_process_clicked)
        layout.addWidget(self.process_button)

        # 连接自定义信号到异步槽
        self.data_received.connect(self.handle_data_received)

    @asyncSlot()
    async def on_fetch_clicked(self):
        """异步槽：处理获取数据按钮点击事件"""
        self.status_label.setText("状态: 正在获取数据...")
        self.fetch_button.setEnabled(False)

        try:
            # 模拟异步网络请求
            await asyncio.sleep(2)  # 模拟网络延迟

            # 模拟获取到的数据
            data = f"获取到的数据: 当前时间戳 {asyncio.get_event_loop().time()}"

            # 发射信号，传递数据
            self.data_received.emit(data)

            self.status_label.setText("状态: 数据获取完成")
            self.text_edit.append(f"[获取] {data}")

        except Exception as e:
            self.status_label.setText(f"状态: 错误 - {str(e)}")
            self.text_edit.append(f"[错误] {str(e)}")
        finally:
            self.fetch_button.setEnabled(True)

    @asyncSlot()
    async def on_process_clicked(self):
        """异步槽：处理处理数据按钮点击事件"""
        self.status_label.setText("状态: 正在处理数据...")
        self.process_button.setEnabled(False)

        try:
            # 模拟耗时的数据处理
            result = await self.async_process_data()

            self.status_label.setText("状态: 数据处理完成")
            self.text_edit.append(f"[处理] 结果: {result}")

        except Exception as e:
            self.status_label.setText(f"状态: 错误 - {str(e)}")
            self.text_edit.append(f"[错误] {str(e)}")
        finally:
            self.process_button.setEnabled(True)

    async def async_process_data(self):
        """模拟异步数据处理"""
        # 模拟多个异步操作
        tasks = []
        for i in range(3):
            tasks.append(self.simulate_task(i))

        results = await asyncio.gather(*tasks)
        return ", ".join(results)

    async def simulate_task(self, task_id):
        """模拟单个异步任务"""
        await asyncio.sleep(1)  # 模拟处理时间
        return f"任务{task_id}完成"

    @asyncSlot(str)
    async def handle_data_received(self, data):
        """异步槽：处理接收到的数据信号"""
        self.text_edit.append(f"[信号处理] 收到数据: {data}")

        # 在异步槽中执行更多异步操作
        await asyncio.sleep(0.5)  # 模拟处理延迟

        self.text_edit.append(f"[信号处理] 数据处理完成")

    @asyncClose
    async def closeEvent(self, event):
        """异步关闭事件处理"""
        # 可以在这里处理异步清理工作
        self.text_edit.append("[关闭] 正在清理资源...")
        await asyncio.sleep(0.5)
        event.accept()


class AsyncApplication:
    """异步应用程序管理器"""

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.loop = qasync.QEventLoop(self.app)
        asyncio.set_event_loop(self.loop)

        self.window = MainWindow()

    def run(self):
        """运行应用程序"""
        self.window.show()

        with self.loop:
            self.loop.run_forever()


# 更复杂的示例：带有定时器的异步操作
class AdvancedWindow(QMainWindow):
    # 定义多种类型的信号 (PySide6)
    string_signal = Signal(str)
    int_signal = Signal(int)
    complex_signal = Signal(str, int, float)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("高级 AsyncSlot 示例 (PySide6)")
        self.setGeometry(100, 100, 600, 500)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.info_label = QLabel("高级异步操作示例")
        layout.addWidget(self.info_label)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)

        # 创建定时操作按钮
        self.timer_button = QPushButton("启动定时任务")
        self.timer_button.clicked.connect(self.start_timer_task)
        layout.addWidget(self.timer_button)

        # 创建并发操作按钮
        self.concurrent_button = QPushButton("执行并发任务")
        self.concurrent_button.clicked.connect(self.execute_concurrent_tasks)
        layout.addWidget(self.concurrent_button)

        # 连接信号到异步槽
        self.string_signal.connect(self.handle_string_signal)
        self.int_signal.connect(self.handle_int_signal)
        self.complex_signal.connect(self.handle_complex_signal)

        # 用于控制定时任务
        self.timer_task = None

    @asyncSlot()
    async def start_timer_task(self):
        """启动定时任务"""
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
            self.output_text.append("[定时器] 停止定时任务")
            self.timer_button.setText("启动定时任务")
        else:
            self.timer_button.setText("停止定时任务")
            self.timer_task = asyncio.create_task(self.timer_worker())

    async def timer_worker(self):
        """定时工作任务"""
        count = 0
        try:
            while True:
                await asyncio.sleep(1)
                count += 1
                self.int_signal.emit(count)

                if count % 5 == 0:
                    self.string_signal.emit(f"定时器运行了 {count} 秒")
        except asyncio.CancelledError:
            self.output_text.append(f"[定时器] 任务被取消，共运行 {count} 秒")
            raise

    @asyncSlot()
    async def execute_concurrent_tasks(self):
        """执行并发任务"""
        self.concurrent_button.setEnabled(False)
        self.output_text.append("[并发] 开始执行并发任务...")

        try:
            # 创建多个并发任务
            tasks = [
                self.concurrent_task("任务A", 2.0),
                self.concurrent_task("任务B", 1.5),
                self.concurrent_task("任务C", 3.0)
            ]

            # 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.output_text.append(f"[并发] 任务{i}失败: {result}")
                else:
                    self.output_text.append(f"[并发] 任务{i}结果: {result}")

            # 发送复杂信号
            self.complex_signal.emit("所有任务完成", len(results), 100.0)

        finally:
            self.concurrent_button.setEnabled(True)

    async def concurrent_task(self, name, duration):
        """模拟并发任务"""
        self.output_text.append(f"[并发] {name} 开始执行...")
        await asyncio.sleep(duration)
        return f"{name} 完成 (耗时 {duration}秒)"

    @asyncSlot(str)
    async def handle_string_signal(self, message):
        """处理字符串信号"""
        self.output_text.append(f"[字符串信号] {message}")

    @asyncSlot(int)
    async def handle_int_signal(self, value):
        """处理整数信号"""
        self.info_label.setText(f"计数器: {value}")

    @asyncSlot(str, int, float)
    async def handle_complex_signal(self, message, count, percentage):
        """处理复杂信号"""
        self.output_text.append(f"[复杂信号] {message}, 数量: {count}, 百分比: {percentage}%")


# 实际应用示例：异步 HTTP 请求
import aiohttp


class NetworkExample(QMainWindow):
    # 定义信号
    response_received = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("异步网络请求示例")
        self.setGeometry(100, 100, 600, 400)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.url_label = QLabel("URL: https://httpbin.org/json")
        layout.addWidget(self.url_label)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)

        self.request_button = QPushButton("发送请求")
        self.request_button.clicked.connect(self.send_request)
        layout.addWidget(self.request_button)

        # 连接信号
        self.response_received.connect(self.handle_response)
        self.error_occurred.connect(self.handle_error)

    @asyncSlot()
    async def send_request(self):
        """发送异步 HTTP 请求"""
        self.request_button.setEnabled(False)
        self.result_text.append("发送请求中...")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://httpbin.org/json') as response:
                    data = await response.json()
                    self.response_received.emit(data)
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self.request_button.setEnabled(True)

    @asyncSlot(dict)
    async def handle_response(self, data):
        """处理响应数据"""
        import json
        formatted_data = json.dumps(data, indent=2, ensure_ascii=False)
        self.result_text.append(f"响应数据:\n{formatted_data}")

    @asyncSlot(str)
    async def handle_error(self, error_message):
        """处理错误"""
        self.result_text.append(f"错误: {error_message}")


def main():
    """主函数"""
    app = AsyncApplication()
    app.run()


# 简单的启动示例
def simple_example():
    """简单示例"""

    print("hello")
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()