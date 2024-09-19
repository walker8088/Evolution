# -*- coding: utf-8 -*-
import sys
import logging
import traceback

from PySide6.QtCore import QCommandLineOption, QCommandLineParser
from PySide6.QtWidgets import QApplication, QMessageBox

from .Version import release_version
from .Main import MainWindow
from .Utils import getTitle

from . import Globl

#-----------------------------------------------------#
# Back up the reference to the exceptionhook
sys._excepthook = sys.excepthook

def my_exception_hook(exctype, value, tb):
    # Print the error and traceback
    msg = ''.join(traceback.format_exception(exctype, value, tb))
    #QMessageBox.critical(None, getTitle(), msg)
    logging.error(f'Critical Error: {msg}')

# Set the exception hook to our wrapping function
sys.excepthook = my_exception_hook

#-----------------------------------------------------#
class ChessApp(QApplication):
    def __init__(self, *argv):
        super().__init__(*argv)

        self.config = {}

        self.APP_NAME = 'Evolution'
        self.APP_NAME_TEXT = "神机象棋"
        
        self.setApplicationName(self.APP_NAME)
        self.setApplicationVersion(release_version)
        
        parser = QCommandLineParser()

        parser.addHelpOption()
        parser.addVersionOption()

        debug_option = QCommandLineOption( ["d", "debug"], "Debug app.")
        parser.addOption(debug_option)
        clean_option = QCommandLineOption( ["c", "clean"], "Clean app setttings.")
        parser.addOption(clean_option)
        
        parser.process(self)
        
        self.isDebug = parser.isSet(debug_option)
        self.isClean = parser.isSet(clean_option)

        if self.isDebug:
            logging.basicConfig(filename = f'{self.APP_NAME}.log', filemode = 'w', level = logging.DEBUG)
        else:
            logging.basicConfig(filename = f'{self.APP_NAME}.log', filemode = 'w', level = logging.INFO) 
        

    def showWin(self):
        self.mainWin = MainWindow()
        self.mainWin.show()

        '''
        splash = QSplashScreen( QPixmap(":images/splash.png"))
        splash.show()
        
        splash.showMessage("Loaded modules")
        QCoreApplication.processEvents()
        splash.showMessage("Established connections")
        QCoreApplication.processEvents()
        '''
        
#-----------------------------------------------------#
def run():
    Globl.app = ChessApp(sys.argv)
    Globl.app.showWin()
    sys.exit(Globl.app.exec())

