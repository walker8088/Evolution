# -*- coding: utf-8 -*-

import os
import time
from pathlib import Path
import logging
import uuid
from collections import OrderedDict

import requests

from PySide6 import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

#-----------------------------------------------------#
def get_mac_address():
    mac=uuid.UUID(int = uuid.getnode()).hex[-12:]
    return ":".join([mac[e:e+2] for e in range(0,11,2)])

#-----------------------------------------------------#
def getTitle():
    return QApplication.instance().APP_NAME_TEXT
       
#-----------------------------------------------------#
class ThreadRunner(QThread):
    def __init__(self, runner):
        super().__init__()
        self.runner = runner
    
    def run(self):
        self.runner.run()

#-----------------------------------------------------#
def load_eglib(lib_file):
        games = OrderedDict()
        
        with open(lib_file, 'rb') as f:
            lines = f.readlines()

        for line in lines:
            it = line.strip().decode('utf-8')
            if it.startswith('#') or  it== '':
                continue
            its = it.split('|')
            
            name = its[0]
            if name not in games:
                games[name] = {'name' : name, 'fen': its[1]}
                
            if len(its) == 3:
                games[name]['moves'] = its[2]
            
        return games.values()
        
#-----------------------------------------------------#
class TimerMessageBox(QMessageBox):
    def __init__(self, text, timeout=2):
        super().__init__()
        self.setWindowTitle(getTitle ())
        self.time_to_wait = timeout
        self.setText(text)
        self.setStandardButtons(QMessageBox.NoButton)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.changeContent)
        self.timer.start()

    def changeContent(self):
        self.time_to_wait -= 1
        if self.time_to_wait <= 0:
            self.close()

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()

#-----------------------------------------------------#
# Uncomment below for terminal log messages
# logging.basicConfig(level=logging.DEBUG, format=' %(asctime)s - %(name)s - %(levelname)s - %(message)s')    

class PlainTextEditLogger(logging.Handler):
    def __init__(self, parent):
        super().__init__()
        self.widget = QPlainTextEdit(parent)
        self.widget.setReadOnly(True)    

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg
        )    
#-----------------------------------------------------#
def QueryFromCloudDB(fen):
    url = 'http://www.chessdb.cn/chessdb.php'
    param = {"action":'queryall'}
    param['board'] = fen
    resp = requests.get(url, params = param)
    moves = resp.text.split('|')
    for it in moves:
        print(it)