# -*- coding: utf-8 -*-
import os
import logging
import traceback
from pathlib import Path
from collections import OrderedDict

from PyQt5.QtCore import QSize, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QStyle, QApplication, QMenu, QHBoxLayout, QVBoxLayout, QFormLayout, QDialog, QFileDialog,\
                    QLabel, QSpinBox, QCheckBox, QPushButton, QRadioButton, \
                    QWidget, QDockWidget, QDialogButtonBox, QButtonGroup, QListWidget, QListWidgetItem, QInputDialog, \
                    QAbstractItemView, QComboBox, QTreeWidgetItem, QTreeWidget, QTextEdit, QSplitter, QMessageBox

import cchess
from cchess import ChessBoard

from .Utils import Stage, GameMode, ReviewMode, getTitle, TimerMessageBox, getFreeMem, getStepsTextFromFenMoves, loadEglib, loadCsvlib
from .BoardWidgets import ChessBoardWidget, ChessBoardEditWidget
from .SnippingWidget import SnippingWidget
from .Dialogs import EngineConfigDialog

from . import Globl

#-----------------------------------------------------#
class DockWidget(QDockWidget):
    def __init__(self, parent, dock_areas):
        super().__init__(parent)
        self.setAllowedAreas(dock_areas)

#-----------------------------------------------------#
class DocksWidget(QDockWidget):
    def __init__(self, name, parent, inner, dock_areas):
        super().__init__(parent)
        self.setObjectName(name)
        self.inner = inner
        self.setWidget(self.inner)
        self.setWindowTitle(self.inner.title)
        self.setAllowedAreas(dock_areas)
        
#-----------------------------------------------------#
class HistoryWidget(QWidget):
    positionSelSignal = pyqtSignal(int)
    save_book_signal = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)

        self.title = "棋谱记录"
        self.parent = parent
        self.isShowScore = True 

        self.positionView = QTreeWidget()
        self.positionView.setColumnCount(1)
        self.positionView.setHeaderLabels(["序号", "着法", "红优分", ''])
        self.positionView.setColumnWidth(0, 90)
        #self.positionView.setTextAlignment(0, Qt.AlignLeft)
        self.positionView.setColumnWidth(1, 120)
        self.positionView.setColumnWidth(2, 80)
        self.positionView.setColumnWidth(3, 20)
        #self.positionView.setColumnWidth(4, 20)

        self.positionView.itemSelectionChanged.connect(self.onSelectionChanged)
        #self.positionView.itemActivated.connect(self.onItemActivated)
        #self.positionView.itemClicked.connect(self.onItemClicked)

        self.annotationView = QTextEdit()
        self.annotationView.readOnly = True

        splitter = QSplitter(self)
        splitter.setOrientation(Qt.Vertical)
        splitter.addWidget(self.positionView)
        
        #splitter.addWidget(self.annotationView)
        #splitter.setStretchFactor(0, 90)
        #splitter.setStretchFactor(1, 10)

        self.firstBtn = QPushButton(
            self.style().standardIcon(QStyle.SP_ArrowUp), '')
        self.firstBtn.clicked.connect(self.onFirstBtnClick)
        self.lastBtn = QPushButton(
            self.style().standardIcon(QStyle.SP_ArrowDown), '')
        self.lastBtn.clicked.connect(self.onLastBtnClick)

        self.nextBtn = QPushButton(
            self.style().standardIcon(QStyle.SP_ArrowForward), '')
        self.nextBtn.clicked.connect(self.onNextBtnClick)
        self.privBtn = QPushButton(
            self.style().standardIcon(QStyle.SP_ArrowBack), '')
        self.privBtn.clicked.connect(self.onPrivBtnClick)
        

        self.reviewByCloudBtn = QPushButton("云库复盘")
        self.reviewByCloudBtn.setEnabled(False)
        self.reviewByEngineBtn = QPushButton("引擎复盘")
        
        self.addBookmarkBtn = QPushButton("收藏局面")
        self.addBookmarkBtn.clicked.connect(self.onAddBookmarkBtnClick)
        self.addBookmarkBookBtn = QPushButton("收藏棋谱")
        self.addBookmarkBookBtn.clicked.connect(self.onAddBookmarkBookBtnClick)
        self.saveDbBtnBtn = QPushButton("保存到棋谱库")
        self.saveDbBtnBtn.clicked.connect(self.onSaveDbBtnClick)
        
        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.firstBtn, 0)
        hbox1.addWidget(self.privBtn, 0)
        hbox1.addWidget(self.nextBtn, 0)
        hbox1.addWidget(self.lastBtn, 0)

        hbox2 = QHBoxLayout()
        hbox2.addWidget(self.reviewByCloudBtn, 0)
        hbox2.addWidget(self.reviewByEngineBtn, 0)
        
        hbox3 = QHBoxLayout()
        #hbox3.addWidget(self.addBookmarkBtn, 0)
        #hbox3.addWidget(self.addBookmarkBookBtn, 0)
        hbox3.addWidget(self.saveDbBtnBtn, 0)
        
        vbox = QVBoxLayout()
        vbox.addWidget(splitter, 2)
        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)
        vbox.addLayout(hbox3)

        self.setLayout(vbox)

        self.viewItems = []
        
        self.clear()

    def contextMenuEvent(self, event):

        menu = QMenu(self)

        clearFollowAction = menu.addAction("删除后续着法")
        menu.addSeparator()
        copyFenAction =  menu.addAction("复制-FEN")
        copyEngineFenAction =  menu.addAction("复制-引擎FEN")
        copyImageAction =  menu.addAction("复制-图片")
        saveImageAction =  menu.addAction("保存图片到文件")
        menu.addSeparator()
        bookmarkPositionAction =  menu.addAction("收藏局面")
        bookmarkBookAction =  menu.addAction("收藏棋谱")
        #addToMyLibAction =  menu.addAction("保存到棋谱库")

        action = menu.exec_(self.mapToGlobal(event.pos()))

        if action == clearFollowAction:
            self.onClearFollowBtnClick()
        elif action == copyFenAction:
            Globl.boardView.copyFenToClipboard()
        elif action == copyEngineFenAction:
            self.parent.copyEngineFenToClipboard()
        elif action == copyImageAction:
            Globl.boardView.copyImageToClipboard()
        elif action == saveImageAction:
            #Globl.boardView.copyImageToClipboard()
            self.parent.saveImageToFile()
        elif action == bookmarkPositionAction:
            self.onAddBookmarkBtnClick()
        elif action == bookmarkBookAction:
            self.onAddBookmarkBookBtnClick()
        #elif action == addToMyLibAction:
        #    self.onSaveDbBtnClick()

    def onClearFollowBtnClick(self):
        if self.selectionIndex < 0:
            return

        #self.onRemoveHistoryFollow(self.selectionIndex)
        self.parent.removeHistoryFollow(self.selectionIndex)
        
    def onItemClicked(self, item, col):
        self.selectionIndex = item.data(0, Qt.UserRole)
        self.positionSelSignal.emit(self.selectionIndex)

    def selectIndex(self, index, fireEvent = True):
        if (self.selectionIndex == index) or (index < 0 ) or (index >= len(self.viewItems)):
            return
        
        self.selectionIndex = index
        item = self.viewItems[self.selectionIndex]
        self.positionView.setCurrentItem(item)
        
        if fireEvent:
            self.positionSelSignal.emit(self.selectionIndex)
    
    def onSelectionChanged(self):
        items = self.positionView.selectedItems()
        if len(items) != 1:
            return
        index = items[0].data(0, Qt.UserRole)
        self.selectIndex(index, True)
                      
    def onFirstBtnClick(self):
        self.selectIndex(0)
       
    def onLastBtnClick(self):
        self.selectIndex(len(self.viewItems) - 1)
       
    def onNextBtnClick(self):
        if (self.selectionIndex < 0) or \
                (self.selectionIndex >= (len(self.viewItems) -1)):
            return

        self.selectIndex(self.selectionIndex + 1)
        
    def onPrivBtnClick(self):
        if self.selectionIndex <= 0:
            return
        
        self.selectIndex(self.selectionIndex - 1)
        
    def onSaveDbBtnClick(self):
        self.parent.saveGameToDB()
        msgbox = TimerMessageBox("当前棋谱已成功保存到棋谱库.", timeout = 0.5)
        msgbox.exec()
        
    def onAddBookmarkBtnClick(self):

        fen = self.parent.board.to_fen()

        if Globl.localBook.isFenInBookmark(fen):
            msgbox = TimerMessageBox("收藏中已经有该局面存在.", timeout = 1)
            msgbox.exec()
            return

        name, ok = QInputDialog.getText(self, getTitle(), '请输入收藏名称:', text = self.parent.getDefaultGameName())
        if not ok:
            return

        if Globl.localBook.isNameInBookmark(name):
            msgbox = TimerMessageBox(f'收藏中已经有[{name}]存在.', timeout = 1)
            msgbox.exec()
            return

        Globl.localBook.saveBookmark(name, fen)
        self.parent.bookmarkView.updateBookmarks()

    def onAddBookmarkBookBtnClick(self):

        fen, moves = self.parent.getGameIccsMoves()

        name, ok = QInputDialog.getText(self, getTitle(), '请输入收藏名称:', text = self.parent.getDefaultGameName())
        if not ok:
            return

        if Globl.localBook.isNameInBookmark(name):
            QMessageBox.information(None, f'{getTitle()}, 收藏中已经有[{name}]存在.')
            return

        Globl.localBook.saveBookmark(name, fen, moves)
        self.parent.bookmarkView.updateBookmarks()
    
    def getCurrPosition(self):
        if self.selectionIndex < 0:
            return None
        item = self.viewItems[self.selectionIndex]
        return item.data(1, Qt.UserRole)
        
    def onNewPostion(self, position):
        item = QTreeWidgetItem(self.positionView)
        item.setTextAlignment(2, Qt.AlignRight)
        self.viewItems.append(item)
        self.updatePositionItem(item, position)
        
        self.selectionIndex = position['index']
        self.positionView.setCurrentItem(item)
        
    '''
    def onRemovePosition(self, position):
        root = self.positionView.invisibleRootItem()
        it = self.viewItems[-1]
        index = it.data(0, Qt.UserRole)
        if index == position['index']:
            item = self.viewItems.pop(-1)
            root.removeChild(item)
    '''

    def onRemoveHistoryFollow(self, index):
        root = self.positionView.invisibleRootItem()
        while len(self.viewItems) > (index + 1): 
            item = self.viewItems.pop(-1)    
            root.removeChild(item)
            
    def onUpdatePosition(self, position):
        for it in self.viewItems:
            index = it.data(0, Qt.UserRole)
            if index == position['index']:
                self.updatePositionItem(it, position)

    def updatePositionItem(self, item, position):
        
        index = position['index']
        
        if index % 2 == 1:
            item.setText(0, f"{index//2+1}.")

        if 'move' in position:
            move = position['move']
            item.setText(1, move.to_text())
        else:
            item.setText(1, '=开始=')
        
        fen = position['fen']

        if not self.isShowScore:
            item.setText(2, '')
            item.setIcon(3, QIcon())
        else: 
            if fen not in Globl.fenCache:
                item.setText(2, '')
                item.setIcon(3, QIcon())    
            else:    
                fenInfo = Globl.fenCache[fen] 
                if (index > 0) and ('score' in fenInfo) :
                    item.setText(2, str(fenInfo['score']))
                else:
                    item.setText(2, '')
                
                if 'diff' in fenInfo:    
                    diff = fenInfo['diff']
                    if diff > -30:
                        item.setIcon(3, QIcon(":ImgRes/star.png"))
                    elif diff > -70:
                        item.setIcon(3, QIcon(":ImgRes/good.png"))
                    elif diff > -100:
                        item.setIcon(3, QIcon(":ImgRes/sad.png"))
                    else:
                        item.setIcon(3, QIcon(":ImgRes/bad.png"))    
                else:
                    item.setIcon(3, QIcon())

        item.setData(0, Qt.UserRole, index)
        item.setData(1, Qt.UserRole, position)

        self.update()
    
    def setShowScore(self, yes):
        self.isShowScore = yes
        for it in self.viewItems:
            position = it.data(1, Qt.UserRole)
            self.updatePositionItem(it, position)

    def clear(self):
        self.viewItems = []
        self.positionView.clear()
        self.selectionIndex = -1

    def sizeHint(self):
        return QSize(350, 500)


#-----------------------------------------------------#
class BoardHistoryWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        #self.title = "棋谱记录"
        #self.parent = parent
        
        self.boardView = ChessBoardWidget(self)
        self.historyView = HistoryWidget(self)

        splitter = QSplitter(self)
        splitter.setOrientation(Qt.Horizontal)
        splitter.addWidget(self.boardView)
        splitter.addWidget(self.historyView)

        splitter.setStretchFactor(0, 90)
        splitter.setStretchFactor(1, 10)

    def showBoardMoves(self, fen, moves):
        self.boardView.from_fen(fen)
        for it in moves:
            self.historyView.onNewPostion(it)

#-----------------------------------------------------#
class DockHistoryWidget(QDockWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setObjectName("History")
        self.inner = HistoryWidget(parent)
        self.setWidget(self.inner)
        self.setWindowTitle(self.inner.title)

#-----------------------------------------------------#
class EngineWidget(QDockWidget):

    def __init__(self, parent, engineMgr):

        super().__init__("引擎", parent)    
        self.setObjectName("ChessEngine")
        
        self.dockedWidget = QWidget(self)
        self.setWidget(self.dockedWidget)
        
        self.parent = parent
        self.engineManager = engineMgr

        Globl.gameManager.game_mode_changed_signal.connect(self.onGameModeChanged)
        Globl.gameManager.review_mode_changed_signal.connect(self.onReviewModeChanged)

        self.gameMode = None
        self.engineFightLevel = 20
        
        self.MAX_MEM = 5000
        self.MAX_THREADS = os.cpu_count()
        
        self.params = {}
        
        self.params['EngineRule'] = 'ChineseRule'
        self.params['EnginePonder'] = 'false'

        self.params["EngineThreads"] = self.getDefaultThreads()
        self.params["EngineMemory"] = self.getDefaultMem()
        self.params["EngineMultiPV"] = 1
        
        self.params["EngineElo"] = 2850
        self.params["EngineGoDepth"] = 25
        self.params["EngineGoMoveTime"] = 0
        
        self.params["EngineEloFight"] = 1350
        self.params["EngineGoDepthFight"] = 25
        self.params["EngineGoMoveTimeFight"] = 0
        
        self.engineGoDepth = self.params["EngineGoDepth"]
        self.engineGoMoveTime = self.params["EngineGoMoveTime"]

        hbox = QHBoxLayout()

        self.engineLabel = QLabel()
        self.engineLabel.setAlignment(Qt.AlignCenter)
        
        '''
        self.DepthSpin = QSpinBox()
        self.DepthSpin.setRange(0, 100)
        self.DepthSpin.setValue(22)
        self.moveTimeSpin = QSpinBox()
        self.moveTimeSpin.setRange(0, 100)
        self.moveTimeSpin.setValue(0)
        '''
        '''
        self.threadsSpin = QSpinBox()
        self.threadsSpin.setSingleStep(1)
        self.threadsSpin.setRange(1, self.MAX_THREADS)
        self.threadsSpin.setValue(self.getDefaultThreads())
        self.threadsSpin.valueChanged.connect(self.onThreadsChanged)
        
        self.memorySpin = QSpinBox()
        self.memorySpin.setSingleStep(100)
        self.memorySpin.setRange(500, self.MAX_MEM)
        self.memorySpin.setValue(self.getDefaultMem())
        self.memorySpin.valueChanged.connect(self.onMemoryChanged)
        
        self.multiPVSpin = QSpinBox()
        self.multiPVSpin.setSingleStep(1)
        self.multiPVSpin.setRange(1, 10)
        self.multiPVSpin.setValue(1)
        self.multiPVSpin.valueChanged.connect(self.onMultiPVChanged)

        self.skillLevelSpin = QSpinBox()
        self.skillLevelSpin.setSingleStep(1)
        self.skillLevelSpin.setRange(1, 20)
        self.skillLevelSpin.setValue(20)
        self.skillLevelSpin.valueChanged.connect(self.onSkillLevelChanged)
        '''

        self.multiPVSpin = QSpinBox()
        self.multiPVSpin.setSingleStep(1)
        self.multiPVSpin.setRange(1, 7)
        self.multiPVSpin.setValue(1)
        self.multiPVSpin.valueChanged.connect(self.onMultiPVChanged)

        self.redBox = QCheckBox("执红")
        self.blackBox = QCheckBox("执黑")
        self.analysisBox = QCheckBox("局面分析")
        self.configBtn = QPushButton("设置")
        #self.reviewBtn = QPushButton("复盘分析")
        
        self.configBtn.clicked.connect(self.onConfigEngine)
        self.redBox.stateChanged.connect(self.onRedBoxChanged)
        self.blackBox.stateChanged.connect(self.onBlackBoxChanged)
        self.analysisBox.stateChanged.connect(self.onAnalysisBoxChanged)

        hbox.addWidget(self.configBtn, 0)

        '''
        hbox.addWidget(QLabel('深度:'), 0)
        hbox.addWidget(self.DepthSpin, 0)
        hbox.addWidget(QLabel(' 步时(秒):'), 0)
        hbox.addWidget(self.moveTimeSpin, 0)
        hbox.addWidget(QLabel(' 级别:'), 0)
        hbox.addWidget(self.skillLevelSpin, 0)
        '''
        #hbox.addWidget(QLabel(' 线程:'), 0)
        #hbox.addWidget(self.threadsSpin, 0)
        
        hbox.addWidget(QLabel('分支:'), 0)
        hbox.addWidget(self.multiPVSpin, 0)
        
        hbox.addWidget(QLabel('   '), 0)
        hbox.addWidget(self.redBox, 0)
        hbox.addWidget(self.blackBox, 0)
        hbox.addWidget(self.engineLabel, 2)
        hbox.addWidget(self.analysisBox, 0)
        #hbox.addWidget(self.reviewBtn, 0)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        self.dockedWidget.setLayout(vbox)

        self.positionView = QTreeWidget()
        self.positionView.setColumnCount(1)
        self.positionView.setHeaderLabels(["深度", "分支", "红优分", "着法", "后续"])
        self.positionView.setColumnWidth(0, 80)
        self.positionView.setColumnWidth(1, 40)
        self.positionView.setColumnWidth(2, 70)
        self.positionView.setColumnWidth(3, 220)
        self.positionView.setColumnWidth(4, 380)

        vbox.addWidget(self.positionView)

        self.branchs = []
    
    def getDefaultMem(self):
        mem = getFreeMem()/2
        m_count = int((mem // 100 ) * 100)
        if m_count > self.MAX_MEM: 
            m_count = self.MAX_MEM
        
        return m_count

    def getDefaultThreads(self):
        return self.MAX_THREADS // 2

    def writeSettings(self, settings):
        for key, value in self.params.items():
            settings.setValue(key, value)
        
        settings.setValue("engineRed", self.redBox.isChecked()) 
        settings.setValue("engineBlack", self.blackBox.isChecked()) 
        settings.setValue("engineAnalysis", self.analysisBox.isChecked()) 

    def readSettings(self, settings):
        for key, old_value in self.params.items():
            new_value = settings.value(key, old_value)
            self.params[key] = new_value

        self.redBox.setChecked(settings.value("engineRed", False, type=bool))
        self.blackBox.setChecked(settings.value("engineBlack", False, type=bool))
        self.analysisBox.setChecked(settings.value("engineAnalysis", False, type=bool))
    
    def getGoParams(self):

        params = {}
        
        if self.engineGoDepth > 0:
            params['depth'] = self.engineGoDepth
        if self.engineGoMoveTime > 0: 
            params['movetime'] = self.engineGoMoveTime * 1000
        
        return params 

    def contextMenuEvent(self, event):
        return
        menu = QMenu(self)
        viewBranchAction = menu.addAction("分支推演")
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == viewBranchAction:
            self.onViewBranch()
    
    def onViewBranch(self):
        self.parent.onViewBranch()

    def onEngineReady(self, engine_id, name, engine_options):
        self.setWindowTitle(f'引擎 {name}')
        
        self.engineManager.setOption('ScoreType','PawnValueNormalized')
        self.engineManager.setOption('Threads', self.params['EngineThreads'])
        self.engineManager.setOption('Hash', self.params['EngineMemory'])
        self.engineManager.setOption('Repetition Rule', self.params['EngineRule'])
        self.engineManager.setOption('Ponder', self.params['EnginePonder'])
        

    def onGameModeChanged(self, gameMode, oldMode):
        
        #保存在人机模式下的engineSkillLevel
        #if self.gameMode == GameMode.Fight:
            #self.engineFightLevel = self.skillLevelSpin.value()
        
        self.gameMode = gameMode
        
        #引擎尚未就绪则不发送命令
        if not self.engineManager.isReady:
            return

        if gameMode == GameMode.Free:
            self.analysisBox.setChecked(True)
            self.engineElo = self.params['EngineElo']
            self.engineGoDepth = self.params['EngineGoDepth']
            self.engineGoMoveTime = self.params['EngineGoMoveTime']
            self.engineManager.setOption('UCI_LimitStrength', False)
            self.engineManager.setOption('MultiPV', self.params['EngineMultiPV'])
            
            self.multiPVSpin.setValue(self.params['EngineMultiPV'])

        elif gameMode == gameMode.Fight:
            self.analysisBox.setChecked(False)
            
            self.engineElo = self.params['EngineEloFight']
            self.engineGoDepth = self.params['EngineGoDepthFight']
            self.engineGoMoveTime = self.params['EngineGoMoveTimeFight']
            self.engineManager.setOption('UCI_LimitStrength', True)
            self.engineManager.setOption('UCI_Elo', self.engineElo)
            self.engineManager.setOption('MultiPV', 1)
            self.multiPVSpin.setValue(1)
            
        elif gameMode == gameMode.Online:
            #self.redBox.setChecked(False)
            #self.blackBox.setChecked(True)
            self.analysisBox.setChecked(True)
            
            self.engineElo = self.params['EngineElo']
            self.engineGoDepth = self.params['EngineGoDepth']
            self.engineGoMoveTime = self.params['EngineGoMoveTime']
            self.engineManager.setOption('UCI_LimitStrength', False)
            self.engineManager.setOption('MultiPV', 1)
            self.multiPVSpin.setValue(1)
            
        elif gameMode == GameMode.EndGame:
            self.redBox.setChecked(False)
            self.blackBox.setChecked(True)
            self.analysisBox.setChecked(False)
            
            self.engineElo = self.params['EngineElo']
            self.engineGoDepth = self.params['EngineGoDepth']
            self.engineGoMoveTime = self.params['EngineGoMoveTime']
            self.engineManager.setOption('UCI_LimitStrength', False)
            self.engineManager.setOption('MultiPV', 1)
            self.multiPVSpin.setValue(1)
        else: 
            self.multiPVSpin.setValue(0)
               
    def onReviewBegin(self, mode):
        self.onReviewModeChanged(mode, Stage.Begin)
    
    def onReviewEnd(self, mode):
        self.onReviewModeChanged(mode, Stage.End)

    def onReviewModeChanged(self, mode, stage):        
        
        if stage == Stage.Begin:
            self.savedCheckState = self.analysisBox.isChecked()
            self.redBox.setEnabled(False)
            self.blackBox.setEnabled(False)
            self.analysisBox.setEnabled(False)
            
            if mode == ReviewMode.ByEngine:
                self.analysisBox.setChecked(True)
                self.engineManager.setOption('UCI_LimitStrength', False)
                self.engineManager.setOption('UCI_LimitStrength', False)
                
            elif mode == ReviewMode.ByCloud:
                self.analysisBox.setChecked(False)
        
        elif stage == Stage.End:
            self.redBox.setEnabled(True)
            self.blackBox.setEnabled(True)
            self.analysisBox.setEnabled(True)
            
            if mode == ReviewMode.ByEngine:
                if self.gameMode == GameMode.Fight:
                    self.engineManager.setOption('UCI_LimitStrength', True)
                    self.engineManager.setOption('Threads', 1)
            elif mode == ReviewMode.ByCloud:
                pass

            self.analysisBox.setChecked(self.savedCheckState)
            
    def onConfigEngine(self):

        self.params['EnginePath'] = self.parent.config['MainEngine']['engine_exec']
        self.params['EngineType'] = self.parent.config['MainEngine']['engine_type']
        
        dlg = EngineConfigDialog(self.parent)
        change_params = dlg.config(self.params)
        if len(change_params) > 0:
            if 'EngineThreads' in change_params:
                self.engineManager.setOption('Threads', self.params['EngineThreads'])
            if 'EngineMemory' in change_params:
                self.engineManager.setOption('Hash', self.params['EngineMemory'])
            if 'EngineRule' in change_params:
               self.engineManager.setOption('Repetition Rule', self.params['EngineRule'])
            if 'EnginePonder' in change_params:
                self.engineManager.setOption('Ponder', self.params['EnginePonder'])
     
            self.onGameModeChanged(self.gameMode, self.gameMode)
    
    def onMultiPVChanged(self, state):
        v = self.multiPVSpin.value()
        self.engineManager.setOption('MultiPV', v)
        if self.gameMode == GameMode.Free:
            self.params['EngineMultiPV'] = v

    def onRedBoxChanged(self, state):
        
        red_checked = self.redBox.isChecked()
        self.parent.enginePlayColor(self.engineManager.id, cchess.RED, red_checked)
        
        if self.gameMode in [GameMode.Fight,]:
            self.blackBox.setChecked(not red_checked)
        elif self.gameMode in [GameMode.Free,]:
            self.analysisBox.setChecked(True)

    def onBlackBoxChanged(self, state):

        black_checked = self.blackBox.isChecked()
        self.parent.enginePlayColor(self.engineManager.id, cchess.BLACK, black_checked)
        
        if self.gameMode in [GameMode.Fight, ]:
            red_checked = self.redBox.isChecked()
            if red_checked == black_checked:
                self.redBox.setChecked(not black_checked)
        elif self.gameMode in [GameMode.Free,]:
            self.analysisBox.setChecked(True)
        
    def onAnalysisBoxChanged(self, state):
        self.parent.enginePlayColor(self.engineManager.id, 0, (Qt.CheckState(state) == Qt.Checked))
        
    def onEngineMoveInfo(self, fenInfo):
        
        if "moves" not in fenInfo:
            return

        iccs_str = ','.join(fenInfo["moves"])
        fenInfo['iccs_str'] = iccs_str

        fen = fenInfo['fen']
        
        ok, moves_text = getStepsTextFromFenMoves(fen, fenInfo["moves"])
        if not ok:
            #logging.warning(f'{fen}, moves {fenInfo["moves"]}')
            return
        
        fenInfo['move_1'] = ','.join(moves_text[:2])
        fenInfo['move_2'] = ','.join(moves_text[2:])

        pv_index = fenInfo['multipv']
        found = False
        for i in range(self.positionView.topLevelItemCount()):
            it = self.positionView.topLevelItem(i)
            it_pv = it.data(0, Qt.UserRole)
            if pv_index == it_pv:
                found = True
                break   

        if not found:
            it = QTreeWidgetItem(self.positionView)
        
        self.updateNode(it, fenInfo)
        self.positionView.sortItems(1, Qt.AscendingOrder)
        
    def updateNode(self, it, fenInfo):

        depth = int(fenInfo['depth'])
        it.setText(0, f'{depth:02d}')
        pv_index = fenInfo['multipv']
        it.setText(1, str(pv_index))
        it.setData(0, Qt.UserRole, pv_index)
        
        #print(depth, pv_index, fenInfo['move_text'])

        #着法及分数显示只受analysisBox控制，这样在fight模式下也不会看到分数，减少分心        
        if self.analysisBox.isChecked():
            move_color = fenInfo['color']
            mate = fenInfo.get('mate', None)
            if mate is not None:
                if mate == 0:
                    it.setText(2, '杀死')
                else:
                    red_killer = True if move_color == cchess.RED else False
                    if mate < 0:
                        red_killer = not red_killer
                    killer = '红优' if red_killer else '黑优'
                        
                    it.setText(2, f'{killer}{abs(mate)}步杀')
                
            else: 
                score = fenInfo['score']
                #换算到红方分
                if move_color == cchess.BLACK:     
                    score = -score
                it.setText(2, str(score))

            it.setText(3, fenInfo['move_1'])
            it.setText(4, fenInfo['move_2'])

        #it.setData(0, Qt.UserRole, fenInfo['iccs_str'])

    def clear(self):
        self.positionView.clear()

    def sizeHint(self):
        return QSize(400, 100)

#------------------------------------------------------------------#
"""
class MoveDbWidget(QDockWidget):
    selectMoveSignal = pyqtSignal(dict)

    def __init__(self, parent):
        super().__init__("我的棋谱库", parent)
        
        self.setObjectName("我的棋谱库")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.parent = parent
        
        self.moveListView = QTreeWidget()
        self.moveListView.setColumnCount(1)
        self.moveListView.setHeaderLabels(["备选着法", "红优分", '', '备注'])
        self.moveListView.setColumnWidth(0, 80)
        self.moveListView.setColumnWidth(1, 60)
        self.moveListView.setColumnWidth(2, 1)
        self.moveListView.setColumnWidth(3, 20)

        self.moveListView.clicked.connect(self.onSelectIndex)
        
        self.importFollowMode = False

        self.setWidget( self.moveListView)

    def clear(self):
        self.moveListView.clear()
        
    def contextMenuEvent(self, event):

        menu = QMenu(self)
        importFollowAction = menu.addAction("导入分支(单选)")
        #importAllFollowAction = menu.addAction("导入分支(全部)")
        menu.addSeparator()
        delBranchAction = menu.addAction("!删除该分支!")
        #cleanAction = menu.addAction("***清理非法招数***")

        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == importFollowAction:
            self.onImportFollow()
        elif action == delBranchAction:
            self.onDeleteBranch()
        #elif action == cleanAction:
        #    self.onCleanMoves()

    def onImportFollow(self):
        self.importFollowMode = True
        self.onSelectIndex()
    
    def onCleanMoves(self):
        bad_moves = []
        records = Globl.localbookStore.getAllBookMoves()
        for it in records:
            fen = it['fen']
            board = ChessBoard(fen)
            for act in it['actions']:
                m = board.is_valid_iccs_move(act['iccs'])
                if m is None:
                    bad_moves.append((fen, act['iccs']))
        for fen, iccs in bad_moves:
            print(len(records), fen, iccs)
            Globl.localbookStore.delBookMoves(fen, iccs)

    def onDeleteBranch(self):
        item = self.moveListView.currentItem()
        fenInfo = item.data(0, Qt.UserRole)
        fen = fenInfo['fen']
        iccs = fenInfo['iccs']
        board = ChessBoard()
        todoList = [(fen, iccs)]
        todoListNew = []
        branchs = 1
        delFens = OrderedDict()
        if self.moveListView.topLevelItemCount() == 1:
            delFens[fen] = None
        else:
             delFens[fen] = iccs
            
        while len(todoList) > 0:
            for fen, iccs in todoList:
                board.from_fen(fen)
                move = board.move_iccs(iccs)
                if move is None:
                    raise Exception('invalid move')
                board.next_turn()
                
                new_fen = board.to_fen()
                record = Globl.localbookStore.getAllBookMoves(new_fen)
                if len(record) > 0:
                    #只删除有后续着法记录
                    if new_fen not in delFens:
                        delFens[new_fen] = None
                for it in record:
                    #assert it['fen'] == new_fen
                    actions = it['actions']
                    if len(actions) > 1:
                        branchs = branchs + len(actions) - 1
                    for act in actions:
                        #print(act)
                        todoListNew.append((new_fen, act['iccs']))
                        
            if (len(todoListNew) == 0):
                break
            todoList = todoListNew
            todoListNew = []
                  
        ok = QMessageBox.question(self, getTitle(), f"此局面后续有{branchs}个分支，{len(delFens)}个局面, 您确定要全部删除吗?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ok == QMessageBox.Yes:
            for fen, iccs in delFens.items():
                Globl.localbookStore.delBookMoves(fen, iccs)
            QMessageBox.information(self, getTitle(), "已删除。")
            self.onPositionChanged(self.curr_pos, is_new = False)
            
    def onImportFollowContinue(self):
        if self.moveListView.topLevelItemCount() != 1:
            self.importFollowMode = False
            return
        item = self.moveListView.topLevelItem(0)
        self.moveListView.setCurrentItem(item, 0)
        self.onSelectIndex()
    
    def onPositionChanged(self, position, is_new):  

        def key_func(it):
            try:
                return int(it['score'])
            except ValueError:
                return 0
            except KeyError:
                return 0
            except  TypeError:
                return 0

        self.curr_pos = position
        fen = position['fen']
        
        self.clear()
        board = ChessBoard(fen)
        book_moves = []

        ret = Globl.localbook.getMoves(fen)
        '''
        if len(ret) == 0:
            return
        elif len(ret) > 1:
            raise Exception(f'database error: {fen}, {ret}')

        it = ret[0]
        for act in it['actions']:
            act['fen'] = fen
            m = board.copy().move_iccs(act['iccs'])
            if m is None:
                continue
            act['text'] = m.to_text()   
            new_fen = m.board_done.to_fen()

            #if 'score' in act:
            #    del act['score']
            
            if new_fen in Globl.fenCache:
                fenInfo = Globl.fenCache[new_fen]
                if 'score' in fenInfo:
                    act['score'] = fenInfo['score']
            book_moves.append(act)
            
        is_reverse  = True if board.get_move_color() == cchess.RED else False        
        book_moves.sort(key=key_func, reverse = is_reverse)
        
        self.updateBookMoves(book_moves)
        '''
        
    def updateBookMoves(self, book_moves):
        self.moveListView.clear()
        self.position_len = len(book_moves)
        for act in book_moves:
            item = QTreeWidgetItem(self.moveListView)

            item.setText(0, act['text'])

            if 'score' in act:
                item.setText(1, str(act['score']))
                item.setTextAlignment(1, Qt.AlignRight)

            #item.setText(2, str(act['count']))
            if 'memo' in act:
                item.setText(3, act['memo'])

            item.setData(0, Qt.UserRole, act)

        if self.importFollowMode:
            if self.position_len == 1:
                QTimer.singleShot(500, self.onImportFollowContinue)
            else:
                self.importFollowMode = False
       
    def onSelectIndex(self):
        item = self.moveListView.currentItem()
        if not item:
            return
        act = item.data(0, Qt.UserRole)
        self.selectMoveSignal.emit(act)

    def sizeHint(self):
        return QSize(150, 500)
"""

#------------------------------------------------------------------#
class BoardActionsWidget(QDockWidget):
    selectMoveSignal = pyqtSignal(dict)

    def __init__(self, parent):
        super().__init__("棋谱库", parent)
        self.setObjectName("棋谱库")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.importFollowMode = False
        self.parent = parent         
        self.actionsView = QTreeWidget()

        self.actionsView.setColumnCount(1)
        self.actionsView.setHeaderLabels(['MK', "备选着法", "得分", ''])
        self.actionsView.setColumnWidth(0, 40)
        self.actionsView.setColumnWidth(1, 120)
        self.actionsView.setColumnWidth(2, 80)
        self.actionsView.setColumnWidth(3, 10)
        
        self.actionsView.clicked.connect(self.onSelectIndex)
        
        self.setWidget( self.actionsView)

    def clear(self):
        self.actionsView.clear()
        self.update()
        
    def contextMenuEvent(self, event):
        return
        menu = QMenu(self)
        importBestAction = menu.addAction("导入最优分支")
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == importBestAction:
            self.onImportBest()

    def onImportBest(self):
        #self.importFollowMode = True
        #self.onSelectIndex(0)
        pass
        
    def updateActions(self, actions):
        self.actionsView.clear()
        for act in actions.values():
            item = QTreeWidgetItem(self.actionsView)
            
            if 'mark' in act:
                item.setText(0, act['mark'])
                item.setTextAlignment(0, Qt.AlignLeft)
            
            item.setText(1, act['text'])

            if 'score' in act:
                item.setText(2, str(act['score']))
            item.setTextAlignment(2, Qt.AlignRight)
            
            item.setData(0, Qt.UserRole, act)
        self.update()

    def onSelectIndex(self, index):
        item = self.actionsView.currentItem()
        act = item.data(0, Qt.UserRole)
        self.selectMoveSignal.emit(act)

    def sizeHint(self):
        return QSize(110, 500)

#------------------------------------------------------------------#
class EndBookWidget(QDockWidget):
    selectEndGameSignal = pyqtSignal(dict)

    def __init__(self, parent):
        super().__init__("残局库", parent)
        self.setObjectName("EndBook")
        
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.parent = parent
        
        self.dockedWidget = QWidget(self)
        self.setWidget(self.dockedWidget)

        self.bookView = QListWidget()

        # Add widgets to the layout
        self.bookCombo = QComboBox(self)
        self.bookCombo.currentTextChanged.connect(self.onBookChanged)
        self.importBtn = QPushButton("导入")
        self.importBtn.clicked.connect(self.onImportBtnClick)
        self.openBtn = QPushButton("打开")
        self.openBtn.clicked.connect(self.onOpenBtnClick)
        
        hbox = QHBoxLayout()
        hbox.addWidget(self.bookCombo, 2)
        hbox.addWidget(self.importBtn, 0)
        hbox.addWidget(self.openBtn, 0)
        
        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(self.bookView)
        self.dockedWidget.setLayout(vbox)

        self.bookView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.bookView.setAlternatingRowColors(True)
        #self.bookView.doubleClicked.connect(self.onItemDoubleClicked)
        #self.bookView.clicked.connect(self.onItemClicked)
        self.bookView.currentItemChanged.connect(self.onCurrentItemChanged)
    
    def updateBooks(self):
      
        self.currBookName = ''
        self.currBook = []
        self.currGame = None

        self.books = Globl.endbookStore.getAllEndBooks()
        self.bookCombo.clear()
        if len(self.books) > 0:
            self.bookCombo.addItems(self.books.keys())
            self.bookCombo.setCurrentIndex(0)
    
    def nextGame(self):

        if len(self.currBook) == 0:
            return
            
        if self.currGame is None :
           self.currGame = self.currBook[0]
           
        if self.currGame['ok'] is False:
            self.selectEndGameSignal.emit(self.currGame)

        index = self.currGame['index']
        while self.currGame['ok'] is True:
            if index < len(self.currBook)-1:
                index += 1
            else:
                break
            self.currGame = self.currBook[index]
        
        if self.currGame['ok'] is False:
            self.bookView.setCurrentItem(self.currGame['widget'])
            
    def updateCurrent(self, game):
        if self.currGame['fen'] != game['fen']:
            return
        self.currGame['ok'] = game['ok']
        self.updateCurrentBook()
     
    def updateCurrentBook(self):
        self.bookView.clear()
        for i, game in enumerate(self.books[self.currBookName]):
            item = QListWidgetItem()
            item.setText(game['name'])
            if game['ok'] is True:
                item.setForeground(Qt.gray)
            item.setData(Qt.UserRole, game)
            game['index'] = i
            game['widget'] = item
            self.bookView.addItem(item)
        
    def onImportBtnClick(self):
        options = QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(
            self,
            "打开杀局谱文件",
            "",
            "杀局谱文件(*.eglib);;CSV格式文件(*.csv);;All Files (*)",
            options=options)

        if not fileName:
            return

        lib_name = Path(fileName).stem
        if Globl.endbookStore.isEndBookExist(lib_name):
            msgbox = TimerMessageBox(f"杀局谱[{lib_name}]系统中已经存在，不能重复导入。",
                                     timeout=2)
            msgbox.exec()
            return
        ext = Path(fileName).suffix.lower()
        if ext =='.eglib': 
            games = loadEglib(fileName)
            Globl.endbookStore.saveEndBook(lib_name, games)
        if ext =='.csv':  
            games = loadCsvlib(fileName)
            Globl.endbookStore.saveEndBook(lib_name, games)
                
        self.updateBooks()
        self.bookCombo.setCurrentText(lib_name)
    
    def onOpenBtnClick(self):
        pass
            
    def onBookChanged(self, book_name):

        self.bookView.clear()

        if book_name == '':
            return

        if book_name not in self.books:
            return

        self.currBookName = book_name
        self.bookCombo.setCurrentText(self.currBookName)
        self.currBook = self.books[self.currBookName]
        self.currGame = None

        self.updateCurrentBook()
        self.nextGame()

    def onCurrentItemChanged(self, current, previous):
        if current is None:
            return
        self.currGame = current.data(Qt.UserRole)
        self.selectEndGameSignal.emit(self.currGame)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        copyAction = menu.addAction("复制Fen到剪贴板")
        menu.addSeparator()
        remarkAction = menu.addAction("标记未完成")
        remarkAllAction = menu.addAction("标记全部未完成")
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == copyAction:
            QApplication.clipboard().setText(self.parent.board.to_fen())
        
        elif action == remarkAction:
            if self.currGame:
                self.currGame['ok'] = False
                Globl.endbookStore.updateEndBook(self.currGame)
            self.updateCurrentBook()
            
        elif action == remarkAllAction:
            for i, game in enumerate(self.books[self.currBookName]):
                if game['ok'] is True:
                    game['ok'] = False
                    Globl.endbookStore.updateEndBook(game)
            self.updateCurrentBook()
                
    def sizeHint(self):
        return QSize(150, 500)

    def readSettings(self, settings):
        
        self.updateBooks()

        endBookName = settings.value("endBookName", '')
        if endBookName:
            self.onBookChanged(endBookName)

        index = settings.value("endBookIndex", -1)
        if index < 0:
            self.currGame = None
        else:    
            self.bookView.setCurrentRow(index)
        
    def writeSettings(self, settings):
        settings.setValue("endBookName", self.currBookName)
        if self.currGame:
            settings.setValue("endBookIndex", self.currGame['index'])
        else:
            settings.setValue("endBookIndex", -1)
            
#------------------------------------------------------------------#
class BookmarkWidget(QDockWidget):
    
    def __init__(self, parent):
        super().__init__("我的收藏", parent)
        self.setObjectName("我的收藏")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.parent = parent        
        self.bookmarks = []

        self.dockedWidget = QWidget(self)
        self.setWidget(self.dockedWidget)

        self.bookmarkView = QListWidget()
        self.bookmarkView.doubleClicked.connect(self.onDoubleClicked)

        #self.bookmarkTypeCombo = QComboBox(self)
        #self.bookmarkTypeCombo.currentTextChanged.connect(
        #    self.onBookTypeChanged)
        #self.bookmarkTypeCombo.addItems(self.bookmark_type)

        #hbox = QHBoxLayout()
        #hbox.addWidget(self.bookmarkTypeCombo)

        vbox = QVBoxLayout()
        #vbox.addLayout(hbox)
        vbox.addWidget(self.bookmarkView)
        self.dockedWidget.setLayout(vbox)

        #self.bookmarkModel = QStandardItemModel(self.bookmarkView)
        #self.bookmarkView.setModel(self.bookmarkModel)
        self.bookmarkView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        #self.bookmarkView.setAlternatingRowColors(True)
        #self.bookmarkView.clicked.connect(self.onSelectIndex)

        self.curr_item = None

        self.updateBookmarks()

    def updateBookmarks(self):
        
        self.bookmarkView.clear()
        self.bookmarks = sorted(Globl.localBook.getAllBookmarks(), key = lambda x: x['name'])

        for i, it in enumerate(self.bookmarks):
            item = QListWidgetItem()
            item.setText(it['name'])
            item.setData(Qt.UserRole, it)
            self.bookmarkView.addItem(item)
    
    def addQuickBooks(self, books):    
        for i,(name, moves_str) in enumerate(books.items()):
            item = QListWidgetItem()
            item.setText(name)
            position = {}
            position['name'] = name
            position['fen'] = cchess.FULL_INIT_FEN
            position['moves'] = moves_str.split(',')
            item.setData(Qt.UserRole, position)
            self.bookmarkView.addItem(item)
        
    def contextMenuEvent(self, event):

        menu = QMenu(self)

        removeAction = menu.addAction("删除")
        renameAction = menu.addAction("改名")
        action = menu.exec_(self.mapToGlobal(event.pos()))

        item = self.bookmarkView.currentItem()
        old_name = item.text()
        fen = item.data(Qt.UserRole)['fen']

        if action == removeAction:
            Globl.LocalBookmarks.removeBookmark(old_name)
            self.updateBookmarks()
        elif action == renameAction:
            new_name, ok = QInputDialog.getText(self,
                                                getTitle(),
                                                '请输入新名称:',
                                                text=old_name)
            if ok:
                if Globl.localBook.isNameInBookmark(new_name):
                    msgbox = TimerMessageBox(f'收藏中已经有[{new_name}]存在.', timeout = 1)
                    msgbox.exec()
                else:
                    if not Globl.localBook.changeBookmarkName(old_name, new_name):
                        msgbox = TimerMessageBox(f'[{old_name}] -> [{new_name}] 改名失败.', timeout = 2)
                        msgbox.exec()    
                    else:
                        self.updateBookmarks()

    def onBookmarkChanged(self, book_name):
        pass

    def onDoubleClicked(self):
        item = self.bookmarkView.currentItem()
        position = item.data(Qt.UserRole)
        name = item.text()
        #print(position)
        self.parent.loadBookmark(name, position)

    def onSelectIndex(self, index):
        self.curr_item = self.bookmarkView.itemFromIndex(index)

    def sizeHint(self):
        return QSize(150, 500)

#------------------------------------------------------------------#
class GameLibWidget(QDockWidget):
    
    def __init__(self, parent):
        super().__init__("棋库", parent)
        self.setObjectName("GameLibWidget")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.parent = parent        
        self.gameLib = []
        
        self.dockedWidget = QWidget(self)
        self.setWidget(self.dockedWidget)

        self.gamesView = QListWidget()
        self.gamesView.doubleClicked.connect(self.onDoubleClicked)

        vbox = QVBoxLayout()
        #vbox.addLayout(hbox)
        vbox.addWidget(self.gamesView)
        self.dockedWidget.setLayout(vbox)

        #self.gamesModel = QStandardItemModel(self.gamesView)
        #self.gamesView.setModel(self.gamesModel)
        self.gamesView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        #self.gamesView.clicked.connect(self.onSelectIndex)

        #self.curr_item = None


    def updateGameLib(self, gamelib):
        #self.
        self.gamelib = gamelib
        games = gamelib['games']   

        self.gamesView.clear()
        
        for i, it in enumerate(games):
            item = QListWidgetItem()
            item.setText(it.info['title'])
            item.setData(Qt.UserRole, it)
            self.gamesView.addItem(item)
    
    def onDoubleClicked(self):
        item = self.gamesView.currentItem()
        game = item.data(Qt.UserRole)
        name = f'{self.gamelib["name"]}-{game.info["title"]}'
        self.parent.loadBookGame(name, game)

    def onSelectIndex(self, index):
        self.curr_item = self.gamesView.itemFromIndex(index)

    def sizeHint(self):
        return QSize(150, 500)



