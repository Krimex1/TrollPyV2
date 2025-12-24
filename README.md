# 🎭 TrollPyV2

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)

**Advanced Remote Administration Tool for Educational Purposes**

*A powerful Python-based remote control system with extensive system manipulation capabilities*

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Commands](#-commands) • [Disclaimer](#%EF%B8%8F-disclaimer)

</div>

---

## 📋 Overview

TrollPyV2 is a sophisticated remote administration toolkit built with Python that allows remote control and monitoring of Windows systems. The project consists of two main components:

- **🖥️ Server (`server.py`)** - Runs on the target machine, listens for commands
- **💻 Client (`client.py`)** - Control interface for sending commands to the server

## ✨ Features

### 🎯 System Control
- **🔊 Audio Manipulation** - Play sounds, TTS, control volume
- **🖱️ Mouse & Keyboard Control** - Remote input simulation
- **📸 Screen Capture** - Take screenshots remotely
- **📹 Webcam Access** - Capture images from camera
- **💬 Message Display** - Show custom messages on screen

### 🛠️ System Operations
- **📂 File Management** - Browse, upload, download files
- **⚙️ Process Management** - List and kill processes
- **🖥️ System Monitoring** - CPU, RAM, disk usage
- **🔒 System Actions** - Shutdown, restart, lock screen
- **📋 Clipboard Access** - Read/write clipboard data

### 🎨 Display Effects
- **🌈 Screen Effects** - Glitch, invert colors, rainbow
- **🖼️ Window Manipulation** - Minimize, maximize, move windows
- **⌨️ Keyboard Lock** - Disable keyboard input
- **🖱️ Mouse Lock** - Disable mouse movement

### 🔐 Stealth Features
- **👻 Hidden Mode** - Run in background
- **🔇 Silent Operation** - No console window
- **🚀 Auto-Start** - System startup integration
- **🔄 Self-Update** - Remote update capability

## 📦 Installation

### Prerequisites
```bash
# Python 3.8 or higher
python --version
```

### 1️⃣ Install Dependencies
```bash
pip install pyinstaller pywin32 opencv-python numpy pyautogui pynput psutil keyboard
```

### 2️⃣ Build Server Executable

Open CMD/PowerShell as **Administrator** in the project directory:

```bash
pyinstaller --onefile --noconsole --name RemoteServer ^
--hidden-import=win32serviceutil ^
--hidden-import=win32service ^
--hidden-import=win32event ^
--hidden-import=servicemanager ^
--hidden-import=ctypes ^
--hidden-import=subprocess ^
--hidden-import=tkinter ^
server.py
```

The compiled `RemoteServer.exe` will be in the `dist/` folder.

### 3️⃣ Deploy Server
Transfer `RemoteServer.exe` to the target machine and run it.

## 🚀 Usage

### Starting the Server
On the target machine:
```bash
python server.py
# or run RemoteServer.exe
```

Server will listen on port `4444` by default.

### Connecting with Client
On your control machine:
```bash
python client.py
```

Enter the target IP address when prompted:
```
Enter server IP: 192.168.1.100
```

## 📝 Commands

### Audio Commands
| Command | Description |
|---------|-------------|
| `play_sound <url>` | Play audio from URL |
| `speak <text>` | Text-to-speech |
| `volume_up` | Increase volume |
| `volume_down` | Decrease volume |
| `volume_max` | Set volume to 100% |
| `volume_mute` | Mute audio |

### Display Commands
| Command | Description |
|---------|-------------|
| `screenshot` | Capture screen |
| `webcam` | Capture from camera |
| `message <text>` | Show message box |
| `glitch` | Screen glitch effect |
| `invert` | Invert screen colors |
| `rainbow` | Rainbow screen effect |

### System Commands
| Command | Description |
|---------|-------------|
| `processes` | List running processes |
| `kill <pid>` | Kill process by ID |
| `sysinfo` | Show system info |
| `shutdown` | Shutdown computer |
| `restart` | Restart computer |
| `lock` | Lock screen |
| `logoff` | Log off user |

### Input Commands
| Command | Description |
|---------|-------------|
| `mouse_move <x> <y>` | Move mouse |
| `mouse_click` | Click mouse |
| `type <text>` | Type text |
| `press <key>` | Press key |
| `lock_keyboard` | Disable keyboard |
| `unlock_keyboard` | Enable keyboard |
| `lock_mouse` | Disable mouse |
| `unlock_mouse` | Enable mouse |

### File Commands
| Command | Description |
|---------|-------------|
| `upload <path>` | Upload file to target |
| `download <path>` | Download file from target |
| `list <dir>` | List directory contents |
| `delete <path>` | Delete file |
| `clipboard_get` | Read clipboard |
| `clipboard_set <text>` | Write to clipboard |

### Control Commands
| Command | Description |
|---------|-------------|
| `help` | Show all commands |
| `exit` | Disconnect from server |
| `kill_server` | Stop server and exit |

## 🏗️ Project Structure

```
TrollPyV2/
├── server.py          # Server-side code (runs on target)
├── client.py          # Client-side control interface
├── README.md          # This file
├── requirements.txt   # Python dependencies (optional)
└── dist/              # Compiled executables (after build)
    └── RemoteServer.exe
```

## 🔧 Configuration

### Change Server Port
Edit `server.py`:
```python
PORT = 4444  # Change to desired port
```

### Enable Logging
Add logging to track activities:
```python
import logging
logging.basicConfig(filename='server.log', level=logging.INFO)
```

### Firewall Configuration
Allow incoming connections on the server port:
```bash
netsh advfirewall firewall add rule name="TrollPyV2" dir=in action=allow protocol=TCP localport=4444
```

## 🛡️ Security Considerations

### ⚠️ Important Notes
- This tool is for **educational purposes only**
- Requires explicit permission from the system owner
- Can be detected by antivirus software
- Network traffic is **not encrypted** by default
- Consider using a VPN or SSH tunnel for secure connections

### 🔐 Recommendations
1. **Encrypt communications** - Implement SSL/TLS
2. **Authentication** - Add password protection
3. **Logging** - Keep audit logs of all actions
4. **Legal compliance** - Ensure proper authorization
5. **Network security** - Use secure network channels

## 🐛 Troubleshooting

### Server Not Starting
- Check if port 4444 is already in use
- Run as Administrator
- Disable antivirus temporarily
- Check firewall settings

### Connection Failed
- Verify IP address is correct
- Ensure server is running
- Check firewall rules on both machines
- Verify network connectivity (`ping <ip>`)

### Commands Not Working
- Check server console for errors
- Verify command syntax
- Ensure required libraries are installed
- Update Python and dependencies

## 📚 Dependencies

Core libraries used:
- `socket` - Network communication
- `pywin32` - Windows API access
- `opencv-python` - Webcam capture
- `numpy` - Image processing
- `pyautogui` - GUI automation
- `pynput` - Input control
- `psutil` - System monitoring
- `keyboard` - Keyboard hooks

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

**EDUCATIONAL PURPOSE ONLY**

This software is provided for educational and research purposes only. The author(s) are not responsible for any misuse or damage caused by this program. Use at your own risk.

By using this software, you agree to:
- Only use it on systems you own or have explicit permission to access
- Comply with all applicable laws and regulations
- Take full responsibility for your actions
- Not use it for malicious purposes

**Unauthorized access to computer systems is illegal and punishable by law.**

## 👤 Author

Created by [Krimex1](https://github.com/Krimex1)

## 🌟 Acknowledgments

- Python community for excellent libraries
- Open-source contributors
- Security researchers and ethical hackers

---

<div align="center">

**⭐ Star this repo if you find it useful! ⭐**

Made with ❤️ by Krimex1

</div>
