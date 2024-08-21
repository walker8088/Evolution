# -*- coding: utf-8 -*-

import os
from collections import OrderedDict

from PySide6.QtCore import Signal, Qt, qApp, QTimer
from PySide6.QtGui import QSize, QStyle, QApplication
from PySide6.QtWidgets import QIcon, QMenu, QHBoxLayout, QVBoxLayout, QFormLayout, QDialog, QLabel, QSpinBox, QCheckBox, QPushButton, QRadioButton, \
                            QWidget, QDockWidget, QDialogButtonBox, QButtonGroup, QListWidget, QListWidgetItem, QInputDialog, QAbstractItemView, \
                            QComboBox, QTreeWidgetItem, QTreeWidget, QSplitter, QMessageBox

from cchess import ChessBoard, RED, BLACK, FULL_INIT_FEN, EMPTY_FEN, iccs2pos

from .Utils import getTitle, TimerMessageBox, get_free_memory_mb
#from .Storage import *
#from .Resource import *
from .BoardWidgets import ChessBoardWidget, ChessBoardEditWidget

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
    positionSelSignal = Signal(int)
    save_book_signal = Signal()

    def __init__(self, parent):
        super().__init__(parent)

        self.title = "棋谱记录"
        self.parent = parent
        self.isShowScore = True 

        self.positionView = QTreeWidget()
        self.positionView.setColumnCount(1)
        self.positionView.setHeaderLabels(["序号", "着法", "红优分", '', "备注"])
        self.positionView.setColumnWidth(0, 50)
        #self.positionView.setTextAlignment(0, Qt.AlignLeft)
        self.positionView.setColumnWidth(1, 80)
        self.positionView.setColumnWidth(2, 50)
        self.positionView.setColumnWidth(3, 10)
        self.positionView.setColumnWidth(4, 20)

        #self.positionView.itemSelectionChanged.connect(self.onSelectStep)
        self.positionView.itemClicked.connect(self.onItemClicked)

        #self.annotationView = QTextEdit()
        #self.annotationView.readOnly = True

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
        #self.reviewByCloudBtn.clicked.connect(self.onReviewByCloudBtnClick)
        self.reviewByEngineBtn = QPushButton("引擎复盘")
        #self.reviewByEngineBtn.clicked.connect(self.onReviewByEngineBtnClick)
        
        
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
        
        #hbox3 = QHBoxLayout()
        #hbox3.addWidget(self.addBookmarkBtn, 0)
        #hbox3.addWidget(self.addBookmarkBookBtn, 0)
        #hbox3.addWidget(self.saveDbBtnBtn, 0)
        
        vbox = QVBoxLayout()
        vbox.addWidget(splitter, 2)
        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)
        #vbox.addLayout(hbox3)

        self.setLayout(vbox)

        self.clear()

    def contextMenuEvent(self, event):

        menu = QMenu(self)

        clearFollowAction = menu.addAction("删除后续着法")
        menu.addSeparator()
        copyFenAction =  menu.addAction("复制(Fen)")
        menu.addSeparator()
        bookmarkPositionAction =  menu.addAction("收藏局面")
        bookmarkBookAction =  menu.addAction("收藏棋谱")
        addToMyLibAction =  menu.addAction("保存到棋谱库")

        action = menu.exec_(self.mapToGlobal(event.pos()))

        if action == clearFollowAction:
            self.onClearFollowBtnClick()
        elif action == copyFenAction:
            pos = self.getCurrPosition()
            #print(pos)
            if pos:
                cb = QApplication.clipboard()
                cb.clear()
                cb.setText(pos['fen'])
        
        elif action == bookmarkPositionAction:
            self.onAddBookmarkBtnClick()
        elif action == bookmarkBookAction:
            self.onAddBookmarkBookBtnClick()
        elif action == addToMyLibAction:
            self.onSaveDbBtnClick()

    def onClearFollowBtnClick(self):

        if self.selectionIndex < 0:
            return

        self.parent.deleteHistoryFollow(self.selectionIndex)
        #TODO 同步更新逻辑
        root = self.positionView.invisibleRootItem()
        while True:
            it = self.items[-1]
            it_num = it.data(0, Qt.UserRole)
            if it_num <= self.selectionIndex:
                break
            root.removeChild(it)
            self.items.pop(-1)

    def onItemClicked(self, item, col):
        self.selectionIndex = item.data(0, Qt.UserRole)
        self.positionSelSignal.emit(self.selectionIndex)

    def selectIndex(self, index, fireEvent = True):
        self.selectionIndex = index
        item = self.items[self.selectionIndex]
        self.positionView.setCurrentItem(item)
        if fireEvent:
            self.positionSelSignal.emit(self.selectionIndex)

    def onFirstBtnClick(self):
        self.selectIndex(0)
       
    def onLastBtnClick(self):
        self.selectIndex(len(self.items) - 1)
       
    def onNextBtnClick(self):
        if (self.selectionIndex < 0) or \
                (self.selectionIndex >= (len(self.items) -1)):
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

        if Globl.storage.isFenInBookmark(fen):
            msgbox = TimerMessageBox("收藏中已经有该局面存在.", timeout = 1)
            msgbox.exec()
            return

        name, ok = QInputDialog.getText(self, getTitle(), '请输入收藏名称:')
        if not ok:
            return

        if Globl.storage.isNameInBookmark(name):
            msgbox = TimerMessageBox(f'收藏中已经有[{name}]存在.', timeout = 1)
            msgbox.exec()
            return

        Globl.storage.saveBookmark(name, fen)
        self.parent.bookmarkView.updateBookmarks()

    def onAddBookmarkBookBtnClick(self):

        fen, moves = self.parent.getGameIccsMoves()

        name, ok = QInputDialog.getText(self, getTitle(), '请输入收藏名称:')
        if not ok:
            return

        if Globl.storage.isNameInBookmark(name):
            QMessageBox.information(None, f'{getTitle()}, 收藏中已经有[{name}]存在.')
            return

        Globl.storage.saveBookmark(name, fen, moves)
        self.parent.bookmarkView.updateBookmarks()
    
    def getCurrPosition(self):
        if self.selectionIndex < 0:
            return None
        item = self.items[self.selectionIndex]
        return item.data(1, Qt.UserRole)
        
    def onNewPostion(self, position):
        item = QTreeWidgetItem(self.positionView)
        item.setTextAlignment(2, Qt.AlignRight)
        self.items.append(item)
        self.updatePositionItem(item, position)

    def onUpdatePosition(self, position):
        for it in self.items:
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
                        item.setIcon(3, QIcon(":Images/star.png"))
                    elif diff > -70:
                        item.setIcon(3, QIcon(":Images/good.png"))
                    elif diff > -100:
                        item.setIcon(3, QIcon(":Images/sad.png"))
                    else:
                        item.setIcon(3, QIcon(":Images/bad.png"))    
                else:
                    item.setIcon(3, QIcon())

        item.setData(0, Qt.UserRole, index)
        item.setData(1, Qt.UserRole, position)

        self.selectionIndex = index
        self.positionView.setCurrentItem(item)
        self.update()
    
    def setShowScore(self, yes):
        self.isShowScore = yes
        for it in self.items:
            position = it.data(1, Qt.UserRole)
            self.updatePositionItem(it, position)

    def clear(self):
        self.items = []
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
class ChessEngineWidget(QDockWidget):

    def __init__(self, parent, engineMgr):

        super().__init__("引擎", parent)    
        self.setObjectName("ChessEngine")
        
        self.parent = parent
        self.engineManager = engineMgr

        self.dockedWidget = QWidget(self)
        self.setWidget(self.dockedWidget)

        hbox = QHBoxLayout()

        self.engineLabel = QLabel()
        self.engineLabel.setAlignment(Qt.AlignCenter)
        
        self.DepthSpin = QSpinBox()
        self.DepthSpin.setRange(0, 100)
        self.DepthSpin.setValue(22)
        self.DepthSpin.valueChanged.connect(self.onDepthChanged)
        
        self.moveTimeSpin = QSpinBox()
        self.moveTimeSpin.setRange(0, 3000)
        self.moveTimeSpin.setValue(20)
        self.moveTimeSpin.valueChanged.connect(self.onMoveTimeChanged)
        
        self.threadsSpin = QSpinBox()
        max_threads =  os.cpu_count()
        self.threadsSpin.setSingleStep(1)
        self.threadsSpin.setValue(max_threads * 3 // 4)
        self.threadsSpin.setRange(1, max_threads)
        self.threadsSpin.valueChanged.connect(self.onThreadsChanged)
        
        MAX_MEM = 5000
        self.memorySpin = QSpinBox()
        self.memorySpin.setSingleStep(100)
        self.memorySpin.setRange(500, MAX_MEM)
        self.memorySpin.valueChanged.connect(self.onMemoryChanged)
        mem = get_free_memory_mb()/2
        m_count = int((mem // 100 ) * 100)
        if m_count > MAX_MEM: 
            m_count = MAX_MEM
        self.memorySpin.setValue(m_count)
        
        self.multiPVSpin = QSpinBox()
        self.multiPVSpin.setSingleStep(1)
        self.multiPVSpin.setValue(1)
        self.multiPVSpin.setRange(1, 10)
        self.multiPVSpin.valueChanged.connect(self.onMultiPVChanged)
        
        self.skillLevelSpin = QSpinBox()
        self.skillLevelSpin.setSingleStep(1)
        self.skillLevelSpin.setValue(20)
        self.skillLevelSpin.setRange(0, 20)
        self.skillLevelSpin.valueChanged.connect(self.onSkillLevelChanged)

        self.eRedBox = QCheckBox("执红")
        self.eBlackBox = QCheckBox("执黑")
        self.analysisModeBox = QCheckBox("分析模式")
        self.configBtn = QPushButton("参数")
        self.reviewBtn = QPushButton("复盘分析")

        #hbox.addWidget(self.configBtn, 0)
        
        hbox.addWidget(QLabel('深度:'), 0)
        hbox.addWidget(self.DepthSpin, 0)
        hbox.addWidget(QLabel(' 步时(秒):'), 0)
        hbox.addWidget(self.moveTimeSpin, 0)
        hbox.addWidget(QLabel(' 级别:'), 0)
        hbox.addWidget(self.skillLevelSpin, 0)
        '''
        hbox.addWidget(QLabel(' 线程:'), 0)
        hbox.addWidget(self.threadsSpin, 0)
        hbox.addWidget(QLabel(' 存储:'), 0)
        hbox.addWidget(self.memorySpin, 0)
        hbox.addWidget(QLabel('MB  分支:'), 0)
        hbox.addWidget(self.multiPVSpin, 0)
        '''

        hbox.addWidget(QLabel('    '), 0)
        hbox.addWidget(self.eRedBox, 0)
        hbox.addWidget(self.eBlackBox, 0)
        hbox.addWidget(self.engineLabel, 2)
        hbox.addWidget(self.analysisModeBox, 0)
        #hbox.addWidget(self.reviewBtn, 0)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        self.dockedWidget.setLayout(vbox)

        self.positionView = QTreeWidget()
        self.positionView.setColumnCount(1)
        self.positionView.setHeaderLabels(["深度", "红优分", "着法"])
        self.positionView.setColumnWidth(0, 80)
        self.positionView.setColumnWidth(1, 100)
        self.positionView.setColumnWidth(2, 380)

        vbox.addWidget(self.positionView)

        self.engineManager.readySignal.connect(self.onEngineReady)
        self.branchs = []
    
    def writeSettings(self, settings):
        settings.setValue("engineDepth", self.DepthSpin.value())
        settings.setValue("engineMoveTime", self.moveTimeSpin.value())
        #settings.setValue("engineThreads", self.threadsSpin.value())
        #settings.setValue("engineMemory", self.memorySpin.value())
        #settings.setValue("engineMultiPV", self.multiPVSpin.value())
        settings.setValue("engineSkillLevel", self.skillLevelSpin.value())
        
        settings.setValue("engineRed", self.eRedBox.isChecked()) 
        settings.setValue("engineBlack", self.eBlackBox.isChecked()) 
        settings.setValue("engineAnalysisMode", self.analysisModeBox.isChecked()) 

    def readSettings(self, settings):
        
        self.DepthSpin.setValue(settings.value("engineDepth", 22))
        self.moveTimeSpin.setValue(settings.value("engineMoveTime", 10))
        #self.threadsSpin.setValue(settings.value("engineThreads", )
        #self.memorySpin.setValue(settings.value("engineMemory", )
        #self.multiPVSpin.setValue(settings.value("engineMultiPV", )
        self.skillLevelSpin.setValue(settings.value("engineSkillLevel", 20))
        
        self.eRedBox.setChecked(settings.value("engineRed", False, type=bool))
        self.eBlackBox.setChecked(settings.value("engineBlack", False, type=bool))
        self.analysisModeBox.setChecked(settings.value("engineAnalysisMode", False, type=bool))
    
    def setTopGameLevel(self):
        self.skillLevelSpin.setValue(20)

    def restoreGameLevel(self, level):
        self.skillLevelSpin.setValue(level)

    def saveGameLevel(self):
        return self.skillLevelSpin.value()

    def setGoParams(self):
        
        moveTime = self.moveTimeSpin.value()
        depth = self.DepthSpin.value()
        
        if depth == 0 and moveTime == 0:
            msgbox = TimerMessageBox("***ERROR*** 分析深度与分析时间不能同时为0。", timeout=1)
            msgbox.exec()
            return
        
        config = {}    
        if moveTime == 0:
            config = {'depth': depth }
        elif depth == 0:
            config = {'movetime': moveTime * 1000 }
        else:
            config =  {'depth': depth, 'movetime': moveTime * 1000 }

        self.engineManager.set_config(config) 
            
        self.saveEngineOptions()
                        
    def contextMenuEvent(self, event):
        return
        menu = QMenu(self)
        viewBranchAction = menu.addAction("分支推演")
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == viewBranchAction:
            self.onViewBranch()
    
    def onDepthChanged(self, num):
        self.setGoParams()
        
    def onMoveTimeChanged(self, num):
        self.setGoParams()
        
    def onThreadsChanged(self, num):
        self.engineManager.set_engine_option('Threads', num)
        self.saveEngineOptions()
        
    def onMemoryChanged(self, num):
        self.engineManager.set_engine_option('Hash', num)
        self.saveEngineOptions()
        
    def onMultiPVChanged(self, num):
        self.engineManager.set_engine_option('MultiPV', num)
        self.saveEngineOptions()
    
    def onSkillLevelChanged(self, num):
        self.engineManager.set_engine_option('Skill Level', num)
        self.saveEngineOptions()
    
    def saveEngineOptions(self): 
        #options = {}
        #Globl.storage.saveEngineOptions(options)
        pass

    def onViewBranch(self):
        self.parent.onViewBranch()

    def onEngineMoveInfo(self, move_info):

        if not self.analysisModeBox.isChecked():
            return

        board = ChessBoard(move_info['fen'])
        #board.from_fen(fen)

        iccs_str = ','.join(move_info["moves"])
        move_info['iccs_str'] = iccs_str

        moves_text = []
        for step_str in move_info["moves"]:
            move_from, move_to = iccs2pos(step_str)
            if board.is_valid_move(move_from, move_to):
                move = board.move(move_from, move_to)
                moves_text.append(move.to_text())
                board.next_turn()
            else:
                #moves_text.append(f'err:{move_info["move"]}')
                return

        move_info['move_text'] = ','.join(moves_text)

        found = False
        for i in range(self.positionView.topLevelItemCount()):
            it = self.positionView.topLevelItem(i)
            iccs_it = it.data(0, Qt.UserRole)
            if iccs_str.find(iccs_it) == 0:  #新的步骤提示比已有的长
                self.update_node(it, move_info, True)
                found = True
                break
            elif iccs_it.find(iccs_str) == 0:  #新的步骤提示比已有的短
                self.update_node(it, move_info, False)
                found = True

        if not found:
            it = QTreeWidgetItem(self.positionView)
            self.update_node(it, move_info, True)

        self.positionView.sortItems(0, Qt.DescendingOrder)  #Qt.AscendingOrder)

    def update_node(self, it, move_info, is_new_text=True):
        if 'depth' in move_info:
            depth = int(move_info['depth'])
            it.setText(0, f'{depth:02d}')
        if 'score' in move_info:
            it.setText(1, str(move_info['score']))
        if is_new_text:
            it.setText(2, move_info['move_text'])

        it.setData(0, Qt.UserRole, move_info['iccs_str'])

    def append_info(self, info):
        self.positionView.addItem(info)

    def onEngineReady(self, engine_id, name, engine_options):
        #print(engine_options)
        
        self.engineLabel.setText(name)
        
        #self.readSettings()

        self.setGoParams()

        self.onThreadsChanged(self.threadsSpin.value())
        self.onMemoryChanged(self.memorySpin.value())
        self.onMultiPVChanged(self.multiPVSpin.value())
        
    def clear(self):
        self.positionView.clear()

    def sizeHint(self):
        return QSize(500, 100)

#------------------------------------------------------------------#
class MoveDbWidget(QDockWidget):
    selectMoveSignal = Signal(dict)

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
        records = Globl.storage.getAllBookMoves()
        for it in records:
            fen = it['fen']
            board = ChessBoard(fen)
            for act in it['actions']:
                m = board.is_valid_iccs_move(act['iccs'])
                if m is None:
                    bad_moves.append((fen, act['iccs']))
        for fen, iccs in bad_moves:
            print(len(records), fen, iccs)
            Globl.storage.delBookMoves(fen, iccs)

    def onDeleteBranch(self):
        item = self.moveListView.currentItem()
        move_info = item.data(0, Qt.UserRole)
        fen = move_info['fen']
        iccs = move_info['iccs']
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
                record = Globl.storage.getAllBookMoves(new_fen)
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
                Globl.storage.delBookMoves(fen, iccs)
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

        ret = Globl.storage.getAllBookMoves(fen)
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
            
        is_reverse  = True if board.get_move_color() == RED else False        
        book_moves.sort(key=key_func, reverse = is_reverse)
        
        self.updateBookMoves(book_moves)
    
        
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
        #self.parent.onTryBookMove(act)
        self.selectMoveSignal.emit(act)

    def sizeHint(self):
        return QSize(150, 500)

#------------------------------------------------------------------#
class CloudDbWidget(QDockWidget):
    selectMoveSignal = Signal(dict)

    def __init__(self, parent):
        super().__init__("开局库", parent)
        self.setObjectName("开局库")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.parent = parent
         
        self.cloudMovesView = QTreeWidget()
        self.cloudMovesView.setColumnCount(1)
        self.cloudMovesView.setHeaderLabels(["备选着法", "红优分", '', '备注'])
        self.cloudMovesView.setColumnWidth(0, 80)
        self.cloudMovesView.setColumnWidth(1, 60)
        self.cloudMovesView.setColumnWidth(2, 1)
        self.cloudMovesView.setColumnWidth(3, 20)
        self.cloudMovesView.clicked.connect(self.onSelectIndex)

        self.importFollowMode = False

        self.setWidget( self.cloudMovesView)

    def clear(self):
        self.cloudMovesView.clear()

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
        
    def updateCloudMoves(self, moves):
        self.cloudMovesView.clear()
        for act in moves:
            item = QTreeWidgetItem(self.cloudMovesView)
            item.setText(0, act['text'])    
            item.setText(1, str(act['score']))
            item.setTextAlignment(1, Qt.AlignRight)
            if 'memo' in act:
                item.setText(2, str(act['memo']))
                item.setTextAlignment(2, Qt.AlignCenter)
            
            item.setData(0, Qt.UserRole, act)
       
    def onSelectIndex(self, index):
        item = self.cloudMovesView.currentItem()
        act = item.data(0, Qt.UserRole)
        self.selectMoveSignal.emit(act)

    def sizeHint(self):
        return QSize(150, 500)

#------------------------------------------------------------------#
class EndBookWidget(QDockWidget):
    selectEndGameSignal = Signal(dict)

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
        
        hbox = QHBoxLayout()
        hbox.addWidget(self.bookCombo, 2)
        hbox.addWidget(self.importBtn, 0)
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
        #super.update()
        self.currBookName = ''
        self.currGame = None

        self.books = Globl.storage.getAllEndBooks()

        self.bookCombo.clear()
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
        self.parent.onImportEndBook()
        self.update()

    def onBookChanged(self, book_name):

        self.bookView.clear()

        if book_name == '':
            return

        self.currBookName = book_name
        self.currBook = self.books[self.currBookName]
        self.currGame = None

        self.updateCurrentBook()

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
        remarkAllAction = menu.addAction("标记未完成（全部）")
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == copyAction:
            qApp.clipboard().setText(self.parent.board.to_fen())
        
        elif action == remarkAction:
            if self.currGame:
                self.currGame['ok'] = False
                Globl.storage.updateEndBook(self.currGame)
            self.updateCurrentBook()
            
        elif action == remarkAllAction:
            for i, game in enumerate(self.books[self.currBookName]):
                if game['ok'] is True:
                    game['ok'] = False
                    Globl.storage.updateEndBook(game)
            self.updateCurrentBook()
                
    def sizeHint(self):
        return QSize(150, 500)

    def readSettings(self, settings):
        
        self.updateBooks()

        endBookName = settings.value("endBookName", '')
        if endBookName:
            self.bookCombo.setCurrentText(endBookName)
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
        self.bookmarks = sorted(Globl.storage.getAllBookmarks(), key = lambda x: x['name'])

        for i, it in enumerate(self.bookmarks):
            item = QListWidgetItem()
            item.setText(it['name'])
            item.setData(Qt.UserRole, it)
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
            Globl.storage.removeBookmark(old_name)
            self.updateBookmarks()
        elif action == renameAction:
            new_name, ok = QInputDialog.getText(self,
                                                getTitle(),
                                                '请输入新名称:',
                                                text=old_name)
            if ok:
                Globl.storage.changeBookmarkName(fen, new_name)
                self.updateBookmarks()

    def onBookmarkChanged(self, book_name):
        pass

    def onDoubleClicked(self):
        item = self.bookmarkView.currentItem()
        position = item.data(Qt.UserRole)
        #position['fen'] = position['fen']
        name = item.text()
        self.parent.loadBookmark(name, position)

    def onSelectIndex(self, index):
        self.curr_item = self.bookmarkView.itemFromIndex(index)

    def sizeHint(self):
        return QSize(150, 500)

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
        #cancelBtn = QPushButton("取消", self)
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

'''
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
'''