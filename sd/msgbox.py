#!/usr/bin/python3
# Send messages to the user in GUI space

import os
import sys
import time
import shutil
import subprocess
import multiprocessing as mp
from importlib.util import find_spec

from sd.common import play
from sd.columns import indenter
from sd.common import quote, warn
from sd.common import srun, quickrun
from sd.common import spawn

# Import PyQt and fallback on tkinter otherwise
if find_spec("PyQt5"):
    import PyQt5.QtCore as qcore
    import PyQt5.QtWidgets as qwidgets
    import PyQt5.QtGui as qgui

if find_spec("tkinter"):
    import tkinter as tk
else:
    print("Unable to import PyQt5 or tkinter")
    print("pip3 install PyQt5 tkinter")




################################################################################


def notify(*text):
    '''Use notify send to send a transient message
    uid = User ID Example: 1000'''
    return srun('notify-send', quote(' '.join(text)))  # , user=uid)


def popup(*text, question=False, timeout=99999999):
    '''Popup a text or question in userland and return True if click okay.
    True  = Accept
    False = Reject
    Other = Return Code'''
    text = ' '.join(text)
    if question:
        cmd = "zenity --question --timeout=" + str(timeout)
    else:
        cmd = "zenity --info --timeout=" + str(timeout)

    cmd = cmd.split() + ['--text=' + text]
    print(cmd)
    return subprocess.run(cmd, check=False).returncode


def cow_msg(*msg, limit=300):
    "Messages from a cow"
    msg = ' '.join(msg)
    moo = "/usr/lib/libreoffice/share/gallery/sounds/cow.wav"
    if os.path.exists(moo):
        spawn(play, moo)
    for line in indenter(msg, wrap=limit, even=True):
        quickrun("/usr/games/xcowsay", line)


def tk_box(msg, wrap=640, title='Info'):
    "Messagebox with tkinter"
    root = tk.Tk()
    root.title(title)
    lbl = tk.Label(root, font=("Arial", 12), text=msg, wraplength=wrap)
    lbl.pack(padx=10, pady=20)
    button = tk.Button(root, text="Okay", command=root.destroy, width=10, font=("Arial", 12))
    button.pack(pady=10, padx=40)
    root.update()
    root.lift()
    time.sleep(len(msg)/64)
    root.mainloop()


def pqbox(msg, wrap=640, title='Info', margin=20):
    "Messagebox with PyQt"
    if "QT_LOGGING_RULES" not in os.environ:
        os.environ["QT_LOGGING_RULES"] = "qt5ct.debug=false"

    app = qwidgets.QApplication(sys.argv)
    window = qwidgets.QWidget()
    window.resize(wrap + margin * 2, 200)
    window.move(app.desktop().screen().rect().center() - window.rect().center())

    label = qwidgets.QLabel(window)
    font = qgui.QFont()
    font.setFamily("Arial")
    font.setPointSize(14)
    label.setFont(font)

    label.move(margin, margin)
    label.setFixedWidth(wrap)
    label.setWordWrap(True)
    label.setAlignment(qcore.Qt.AlignCenter)
    label.setText(msg)
    label.adjustSize()      # Do this or the .height() will be wrong
    txtsize = label.fontMetrics().boundingRect(label.text())
    # lbl_height = math.ceil(txtsize.width() / wrap) * txtsize.height()
    # print(lbl_height, label.height())

    button = qwidgets.QPushButton(window)
    button.setText("Okay")
    button.clicked.connect(app.quit)

    pos = window.rect().center() - button.rect().center()
    button.move(pos.x(), label.y() + label.height() + margin)
    window.resize(window.width(), button.y() + button.height() + margin)

    window.setWindowTitle(title)
    window.show()
    app.exec_()


def msgbox(*args, wrap=640, wait=False, throwerr=False):
    '''
    Popup message box, requires PyQT, tkinter or zenity.
    Guaranteed not to break, even if third party libraries not installed.
    wait = wait for user to acknowledge before continuing
    returns False if message was not delivered to desktop
    '''
    msg = ' '.join(list(map(str, args)))

    if "PyQt5" in sys.modules:
        if wait:
            pqbox(msg, wrap)
        else:
            # PyQt must be created in a seperate process, a seperate thread creates errors
            proc = mp.Process(target=pqbox, args=(msg,), kwargs={'wrap': wrap})
            proc.start()

    elif "tkinter" in sys.modules:
        if wait:
            tk_box(msg, wrap)
        else:
            spawn(tk_box, msg, wrap)

    elif shutil.which('zenity'):
        cmd = ['zenity', '--width', str(len(msg)*10), '--info', '--timeout=99999999', '--text='+quote(msg)]
        if wait:
            ret = subprocess.run(cmd, check=False)
            return not bool(ret.returncode)
        else:
            subprocess.Popen(cmd)


    else:
        warn("\nInstall PyQt5, tkinter or zenity to get this message on the desktop:")
        print(msg)
        if throwerr:
            raise ValueError("Cannot show msgbox")
        return False

    return True




'''
import threading, queue
if __name__ == "__main__":
    def send_msg(msg):
        proc = mp.Process(target=pqbox, args=(msg,))
        proc.start()

    def my_func():
        send_msg('hello')

    msg='hello'
    send_msg(msg)
    print("The program continues to run.")

    time.sleep(2)
    thread = threading.Thread(target=my_func)
    thread.daemon = False
    thread.start()
'''




################################################################################
if __name__ == "__main__":
    MSG = ' '.join(sys.argv[1:])
    msgbox(MSG, wait=False)
    # print("Message box done, waiting 3 seconds...")
    # time.sleep(3)
