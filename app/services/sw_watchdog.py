"""v2.3 Task 2: SW Watchdog 守护进程

后台线程持续监控 SolidWorks 进程健康状态：
1. 通过 PID 检查 SW 进程是否存活（psutil / win32api fallback）
2. 通过 COM RevisionNumber 检查 SW 是否可响应（由外部提供检查函数）
3. 超过 hang_threshold_s 无响应则标记为 hung
4. 通过回调通知上层触发恢复策略

状态机:
    idle → watching → hung → recovering → watching
                     ↓
                  (进程退出) → idle

使用方式:
    from app.services.sw_watchdog import SwWatchdog
    wd = SwWatchdog(sw_pid=12345, hang_threshold_s=60.0)
    wd.set_com_check_func(lambda: sw.RevisionNumber())  # 设置 COM 响应检查函数
    wd.set_hung_callback(lambda status: print("SW hung!", status))
    wd.set_recovery_callback(lambda: recover())
    wd.start()
    # ... 正常运行 ...
    wd.stop()
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional


class WatchdogState(str, Enum):
    """看门狗状态"""
    IDLE = "idle"
    WATCHING = "watching"
    HUNG = "hung"
    RECOVERING = "recovering"


@dataclass
class WatchdogStatus:
    """看门狗状态快照"""
    sw_pid: Optional[int]
    alive: bool
    last_responsive: str  # ISO 时间戳
    hang_duration: float  # 挂起持续时间（秒）
    state: str


class SwWatchdog:
    """SolidWorks 进程健康看门狗

    后台 daemon 线程定期（check_interval_s）检查 SW 进程：
    - 进程是否存活（PID 存在）
    - COM 是否可响应（通过外部提供的检查函数）
    若连续 hang_threshold_s 无响应，触发 hung 回调。
    """

    def __init__(
        self,
        sw_pid: Optional[int] = None,
        check_interval_s: float = 5.0,
        hang_threshold_s: float = 60.0,
    ):
        """
        Args:
            sw_pid: SolidWorks 进程 PID。None 时需在 start() 前设置
            check_interval_s: 检查间隔（秒）
            hang_threshold_s: 判定挂起的阈值（秒）
        """
        self._sw_pid = sw_pid
        self._check_interval_s = check_interval_s
        self._hang_threshold_s = hang_threshold_s

        self._state = WatchdogState.IDLE
        self._lock = threading.RLock()

        # 线程控制
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # 响应追踪
        self._last_responsive_time: float = time.time()
        self._last_alive: bool = False
        self._last_check_time: float = 0.0

        # 回调
        self._hung_callback: Optional[Callable[[dict], Any]] = None
        self._recovery_callback: Optional[Callable[[], Any]] = None

        # COM 响应检查函数（由外部设置，因为 COM 对象不能跨线程调用）
        self._com_check_func: Optional[Callable[[], bool]] = None

        # hung 状态是否已通知（避免重复触发）
        self._hung_notified: bool = False

    # ========== 生命周期 ==========

    def start(self):
        """启动看门狗后台线程"""
        if self._thread is not None and self._thread.is_alive():
            return  # 已在运行

        with self._lock:
            self._state = WatchdogState.WATCHING
            self._last_responsive_time = time.time()
            self._hung_notified = False

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="SwWatchdog",
        )
        self._thread.start()

    def stop(self, timeout_s: float = 5.0):
        """停止看门狗"""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout_s)
            self._thread = None
        with self._lock:
            self._state = WatchdogState.IDLE

    def reset(self):
        """重置看门狗状态"""
        with self._lock:
            self._state = WatchdogState.WATCHING if self._thread and self._thread.is_alive() else WatchdogState.IDLE
            self._last_responsive_time = time.time()
            self._last_alive = False
            self._last_check_time = 0.0
            self._hung_notified = False

    # ========== 回调设置 ==========

    def set_hung_callback(self, callback: Callable[[dict], Any]):
        """设置挂起检测回调

        Args:
            callback: 当 SW 被判定为 hung 时调用，参数为 status dict
        """
        self._hung_callback = callback

    def set_recovery_callback(self, callback: Callable[[], Any]):
        """设置恢复触发回调

        Args:
            callback: 当需要触发恢复时调用（无参数）
        """
        self._recovery_callback = callback

    def set_com_check_func(self, func: Callable[[], bool]):
        """设置 COM 响应检查函数

        由于 COM 对象不能跨线程自由调用，需要由创建 COM 对象的线程
        提供检查函数。看门狗线程会定期调用此函数检查 SW 是否可响应。

        Args:
            func: 无参数函数，返回 True 表示 SW 可响应，False 表示无响应
                  示例: lambda: sw.RevisionNumber() is not None
        """
        self._com_check_func = func

    # ========== 查询 ==========

    def is_alive(self) -> bool:
        """检查 SW 进程是否存活"""
        with self._lock:
            return self._last_alive

    def get_status(self) -> dict:
        """获取当前状态快照"""
        with self._lock:
            now = time.time()
            hang_duration = 0.0
            if self._state == WatchdogState.HUNG:
                hang_duration = now - self._last_responsive_time

            return {
                "sw_pid": self._sw_pid,
                "alive": self._last_alive,
                "last_responsive": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(self._last_responsive_time)
                ),
                "hang_duration": round(hang_duration, 2),
                "state": self._state.value,
                "check_interval_s": self._check_interval_s,
                "hang_threshold_s": self._hang_threshold_s,
                "last_check_time": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(self._last_check_time)
                ) if self._last_check_time > 0 else "",
            }

    @property
    def sw_pid(self) -> Optional[int]:
        return self._sw_pid

    @sw_pid.setter
    def sw_pid(self, value: Optional[int]):
        with self._lock:
            self._sw_pid = value
            # PID 更新时重置响应时间
            self._last_responsive_time = time.time()
            self._hung_notified = False

    @property
    def state(self) -> WatchdogState:
        with self._lock:
            return self._state

    # ========== 监控循环 ==========

    def _monitor_loop(self):
        """后台监控循环"""
        while not self._stop_event.is_set():
            try:
                self._do_check()
            except Exception:
                pass  # 监控线程不应因异常退出

            # 使用 wait 代替 sleep，便于快速响应 stop
            self._stop_event.wait(timeout=self._check_interval_s)

    def _do_check(self):
        """执行单次检查"""
        with self._lock:
            self._last_check_time = time.time()
            pid = self._sw_pid
            current_state = self._state

        # 如果处于 recovering 状态，跳过检查
        if current_state == WatchdogState.RECOVERING:
            return

        # 1. 检查进程是否存活
        alive = self._check_process_alive(pid)

        with self._lock:
            self._last_alive = alive

        if not alive:
            # 进程已退出
            with self._lock:
                if self._state != WatchdogState.IDLE:
                    self._state = WatchdogState.IDLE
            return

        # 2. 检查 COM 是否可响应
        responsive = self._check_com_responsive()

        with self._lock:
            now = time.time()
            if responsive:
                self._last_responsive_time = now
                # 如果之前是 hung 状态，恢复到 watching
                if self._state == WatchdogState.HUNG:
                    self._state = WatchdogState.WATCHING
                    self._hung_notified = False
            else:
                # 不可响应，检查是否超过阈值
                hang_duration = now - self._last_responsive_time
                if hang_duration >= self._hang_threshold_s:
                    if self._state != WatchdogState.HUNG:
                        self._state = WatchdogState.HUNG

                    # 触发 hung 回调（仅一次）
                    if not self._hung_notified and self._hung_callback is not None:
                        self._hung_notified = True
                        try:
                            status = {
                                "sw_pid": pid,
                                "hang_duration": round(hang_duration, 2),
                                "last_responsive": time.strftime(
                                    "%Y-%m-%d %H:%M:%S",
                                    time.localtime(self._last_responsive_time),
                                ),
                            }
                            self._hung_callback(status)
                        except Exception:
                            pass

                    # 触发恢复回调
                    if self._recovery_callback is not None:
                        try:
                            self._recovery_callback()
                        except Exception:
                            pass

    def _check_process_alive(self, pid: Optional[int]) -> bool:
        """检查进程是否存活

        优先使用 psutil，fallback 到 win32api。
        """
        if pid is None:
            return False

        # 方式 1: psutil
        try:
            import psutil
            return psutil.pid_exists(pid)
        except ImportError:
            pass
        except Exception:
            pass

        # 方式 2: win32api / ctypes
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            pass

        # 方式 3: tasklist（最慢但最通用）
        try:
            import subprocess
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=10,
            )
            return str(pid) in result.stdout
        except Exception:
            pass

        return False

    def _check_com_responsive(self) -> bool:
        """检查 SW COM 是否可响应

        通过外部提供的检查函数执行。如果未设置检查函数，
        则仅依赖进程存活检查（乐观策略）。
        """
        if self._com_check_func is None:
            # 未设置 COM 检查函数，仅依赖进程存活
            return self._last_alive

        try:
            return self._com_check_func()
        except Exception:
            # COM 调用失败，视为无响应
            return False

    # ========== 输出 ==========

    def save_status(self, path: Path):
        """保存看门狗状态到 JSON 文件

        Args:
            path: 输出文件路径
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            **self.get_status(),
        }

        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
