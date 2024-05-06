# -*- coding: utf-8 -*-

from PySide6 import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from cchess import *

from .BoardWidgets import *
from .Widgets import *


#-----------------------------------------------------#
class PositionEditDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle("局面编辑")

        self.boardEdit = ChessBoardEditWidget()
        self.redMoveBtn = QRadioButton("红方走", self)
        self.blackMoveBtn = QRadioButton("黑方走", self)
        self.fenLabel = QLabel()

        group1 = QButtonGroup(self)
        group1.addButton(self.redMoveBtn)
        group1.addButton(self.blackMoveBtn)

        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.redMoveBtn, 0)
        hbox1.addWidget(self.blackMoveBtn, 0)
        hbox1.addWidget(QLabel(''), 1)

        initBtn = QPushButton("初始棋盘", self)
        clearBtn = QPushButton("清空棋盘", self)
        initBtn.clicked.connect(self.onInitBoard)
        clearBtn.clicked.connect(self.onClearBoard)
        okBtn = QPushButton("确定", self)
        cancelBtn = QPushButton("取消", self)

        vbox = QVBoxLayout()
        vbox.addWidget(self.boardEdit)
        vbox.addWidget(self.fenLabel)
        vbox.addLayout(hbox1)

        hbox = QHBoxLayout()
        hbox.addWidget(self.redMoveBtn)
        hbox.addWidget(self.blackMoveBtn)
        hbox.addWidget(initBtn)
        hbox.addWidget(clearBtn)
        hbox.addWidget(okBtn)
        hbox.addWidget(cancelBtn)

        vbox.addLayout(hbox)
        self.setLayout(vbox)

        self.boardEdit.fenChangedSignal.connect(self.onBoardFenChanged)
        self.redMoveBtn.clicked.connect(self.onRedMoveBtnClicked)
        self.blackMoveBtn.clicked.connect(self.onBlackMoveBtnClicked)

        okBtn.clicked.connect(self.accept)
        cancelBtn.clicked.connect(self.close)

    def onInitBoard(self):
        self.boardEdit.from_fen(FULL_INIT_FEN)

    def onClearBoard(self):
        self.boardEdit.from_fen(EMPTY_FEN)

    def onRedMoveBtnClicked(self):
        self.boardEdit.set_move_color(RED)

    def onBlackMoveBtnClicked(self):
        self.boardEdit.set_move_color(BLACK)

    def onBoardFenChanged(self, fen):

        self.fenLabel.setText(fen)

        color = self.boardEdit.get_move_color()
        if color == RED:
            self.redMoveBtn.setChecked(True)
        elif color == BLACK:
            self.blackMoveBtn.setChecked(True)

    def edit(self, fen_str):
        self.boardEdit.from_fen(fen_str)

        if self.exec_() == QDialog.Accepted:
            return self.boardEdit.to_fen()
        else:
            return None


#-----------------------------------------------------#
class PositionHistDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        #self.setFixedSize(200, 120)

        self.setWindowTitle("局面推演")

        vbox = QVBoxLayout()

        self.boardEdit = BoardHistoryWidget()
        vbox.addWidget(self.boardEdit)

        okBtn = QPushButton("完成", self)
        cancelBtn = QPushButton("取消", self)
        #self.quit.setGeometry(62, 40, 75, 30)

        hbox = QHBoxLayout()
        hbox.addWidget(okBtn)
        vbox.addLayout(hbox)
        self.setLayout(vbox)

        okBtn.clicked.connect(self.accept)
        #cancelBtn.clicked.connect(self.onClose)

    def onInitBoard(self):
        self.boardEdit.from_fen(FULL_INIT_FEN)
        self.fenLabel.setText(self.boardEdit.to_fen())


#-----------------------------------------------------#
class EngineConfigDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("引擎参数配置")

        self.depthEdit = QSpinBox()
        self.depthEdit.setRange(5, 30)

        form_layout = QFormLayout()
        form_layout.addRow(QLabel("分析深度:"), self.depthEdit)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok
                                      | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        main_layout = QVBoxLayout()
        #main_layout.addWidget(QLabel())
        main_layout.addLayout(form_layout)
        main_layout.addWidget(QLabel())
        main_layout.addWidget(button_box)
        self.setLayout(main_layout)

    def config(self, params):
        if 'depth' in params:
            self.depthEdit.setValue(params['depth'])
        else:
            self.depthEdit.setValue(22)
            
        if self.exec_():
            params['depth'] = self.depthEdit.value()
            return True

        return False

#-----------------------------------------------------#
import pygetwindow as gw
#import pyscreenshot as ImageGrab
from PIL import ImageGrab
from PIL.ImageQt import ImageQt

class OnlineDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle("窗口截图")
        
        self.screen = ScreenBoardView(self)
        
        self.redMoveBtn = QRadioButton("红方走", self)
        self.blackMoveBtn = QRadioButton("黑方走", self)
        self.fenLabel = QLabel()

        group1 = QButtonGroup(self)
        group1.addButton(self.redMoveBtn)
        group1.addButton(self.blackMoveBtn)

        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.redMoveBtn, 0)
        hbox1.addWidget(self.blackMoveBtn, 0)
        hbox1.addWidget(QLabel(''), 1)

        captureBtn = QPushButton("截取窗口", self)
        captureBtn.clicked.connect(self.onCapture)
        detectBtn = QPushButton("检测", self)
        detectBtn.clicked.connect(self.onDetect)
        okBtn = QPushButton("确定", self)
        cancelBtn = QPushButton("取消", self)

        vbox = QVBoxLayout()
        vbox.addWidget(self.screen, 2)
        #vbox.addWidget(self.fenLabel)
        vbox.addLayout(hbox1)

        hbox = QHBoxLayout()
        #hbox.addWidget(self.redMoveBtn)
        #hbox.addWidget(self.blackMoveBtn)
        hbox.addWidget(captureBtn)
        hbox.addWidget(detectBtn)
        
        hbox.addWidget(okBtn)
        hbox.addWidget(cancelBtn)

        vbox.addLayout(hbox)
        self.setLayout(vbox)

        #self.boardEdit.fenChangedSignal.connect(self.onBoardFenChanged)
        self.redMoveBtn.clicked.connect(self.onRedMoveBtnClicked)
        self.blackMoveBtn.clicked.connect(self.onBlackMoveBtnClicked)

        okBtn.clicked.connect(self.accept)
        cancelBtn.clicked.connect(self.close)

    def onCapture(self):
        
        #win = gw.getWindowsWithTitle("22081281AC")[0]
        win = gw.getWindowsWithTitle("BLA-AL00")[0]
        
        win.activate()
        
        #print( win.width,  win.height)
        
        x1, y1, x2, y2 = win.left, win.top, win.left + win.width, win.top + win.height

        img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        
        self.screen.update_img(img)
        
    def onDetect(self):
        self.screen.detectBoard()
        
    def onRedMoveBtnClicked(self):
        self.boardEdit.set_move_color(RED)

    def onBlackMoveBtnClicked(self):
        self.boardEdit.set_move_color(BLACK)

    def onBoardFenChanged(self, fen):

        self.fenLabel.setText(fen)

        color = self.boardEdit.get_move_color()
        if color == RED:
            self.redMoveBtn.setChecked(True)
        elif color == BLACK:
            self.blackMoveBtn.setChecked(True)

    def edit(self, fen_str):
        self.boardEdit.from_fen(fen_str)

        if self.exec_() == QDialog.Accepted:
            return self.boardEdit.to_fen()
        else:
            return None
            
    def get_image(self):
        pass
