import multiprocessing as mp
import time
import signal
import sys
import os
from typing import List, Callable


class SchedulerManager:
    def __init__(self):
        self.scheduler_processes: List[mp.Process] = []
        self.running = True

    def start_scheduler_process(self, target_func: Callable):
        """启动调度器进程"""
        process = mp.Process(target=target_func)
        process.daemon = False  # 非守护进程，需要手动管理
        process.start()
        self.scheduler_processes.append(process)
        print(f"已启动调度器进程 PID: {process.pid}")
        return process

    def cleanup_resources(self):
        """清理所有调度器进程资源"""
        print("开始清理调度器进程资源...")

        # 1. 优雅关闭所有进程
        for process in self.scheduler_processes:
            if process.is_alive():
                print(f"终止进程 PID: {process.pid}")
                process.terminate()  # 发送终止信号

        # 2. 等待所有进程结束
        for process in self.scheduler_processes:
            process.join(timeout=5)  # 等待最多5秒
            if process.is_alive():
                print(f"强制杀死进程 PID: {process.pid}")
                process.kill()  # 强制杀死仍未结束的进程

        # 3. 清空进程列表
        self.scheduler_processes.clear()
        print("所有调度器进程资源已清理完毕")

    def signal_handler(self, signum, frame):
        """信号处理函数"""
        print(f"\n接收到信号 {signum}，开始清理资源...")
        self.running = False
        self.cleanup_resources()
        sys.exit(0)

    def setup_signal_handlers(self):
        """设置信号处理器"""
        signal.signal(signal.SIGINT, self.signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, self.signal_handler)  # 终止信号


def start_scheduler_sync_weights():
    """模拟权重同步调度器"""
    print(f"权重同步调度器启动 PID: {str(os.getpid())}")
    while True:
        time.sleep(2)
        print(f"权重同步任务执行中... PID: {str(os.getpid())}")





def start_scheduler_sync_week():
    """模拟周同步调度器"""
    print(f"周同步调度器启动 PID: {str(os.getpid())}")
    while True:
        time.sleep(5)
        print(f"周同步任务执行中... PID: {str(os.getpid())}")


def main():
    # 创建调度器管理器
    manager = SchedulerManager()

    # 设置信号处理器
    manager.setup_signal_handlers()

    try:
        # 启动多个调度器进程
        manager.start_scheduler_process(start_scheduler_sync_weights)
        manager.start_scheduler_process(start_scheduler_sync_day)
        manager.start_scheduler_process(start_scheduler_sync_week)
        print(f"已启动 {len(manager.scheduler_processes)} 个调度器进程")

        # 主进程保持运行
        while manager.running:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n接收到键盘中断信号")
    finally:
        # 确保资源被清理
        manager.cleanup_resources()


if __name__ == "__main__":
    main()
