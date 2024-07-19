# -*- coding: utf-8 -*-
import os
import sys
import yaml
import logging
#import traceback
from pathlib import Path

from PySide6 import *
from PySide6.QtCore import *
from PySide6.QtWidgets import QApplication

from .Main import *

#-----------------------------------------------------#
class ChessApp(QApplication):
    def __init__(self):
        super().__init__([])

        self.config = {}

        self.APP_NAME = 'Evolution'
        self.APP_NAME_TEXT = "神机象棋"
        '''
        splash = QSplashScreen( QPixmap(":images/splash.png"))
        splash.show()
        
        splash.showMessage("Loaded modules")
        QCoreApplication.processEvents()
        splash.showMessage("Established connections")
        QCoreApplication.processEvents()
    '''
    
        self.mainWin = MainWindow(self)
        self.mainWin.show()

        
#-----------------------------------------------------#
def run():
    app = ChessApp()
    sys.exit(app.exec_())
