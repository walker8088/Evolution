# -*- coding: utf-8 -*-

import os
import sys
import time

from PySide6 import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from cchess import *

from .Utils import *
from .Storage import *
from .Resource import *

#-----------------------------------------------------#
class DockWidget(QDockWidget):
    def __init__(self, parent, dock_areas):
        super().__init__(parent)
        self.setAllowedAreas(dock_areas)

#-----------------------------------------------------#
class DocksWidget(DockWidget):
    def __init__(self, parent, inner, dock_areas):
        super().__init__(parent)
        self.setAllowedAreas(dock_areas)
        self.inner = inner
        self.setWidget(self.inner)
        self.setWindowTitle(self.inner.title)
        
#-----------------------------------------------------#
class HistoryWidget(QWidget):
    positionSelSignal = Signal(int)
    save_book_signal = Signal()

    def __init__(self, parent):
        super().__init__(parent)

        self.title = "棋谱记录"
        self.parent = parent
        self.storage = self.parent.storage

        self.positionView = QTreeWidget()
        self.positionView.setColumnCount(1)
        self.positionView.setHeaderLabels(["序号", "着法", "得分", '', "备注"])
        self.positionView.setColumnWidth(0, 50)
        #self.positionView.setTextAlignment(0, Qt.AlignLeft)
        self.positionView.setColumnWidth(1, 80)
        self.positionView.setColumnWidth(2, 50)
        self.positionView.setColumnWidth(3, 10)
        self.positionView.setColumnWidth(4, 80)

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

        self.addBookmarkBtn = QPushButton("收藏局面")
        self.addBookmarkBtn.clicked.connect(self.onAddBookmarkBtnClick)
        self.addBookmarkBookBtn = QPushButton("收藏棋谱")
        self.addBookmarkBookBtn.clicked.connect(self.onAddBookmarkBookBtnClick)
        self.saveDbBtnBtn = QPushButton("保存到对局库")
        self.saveDbBtnBtn.clicked.connect(self.onSaveDbBtnClick)

        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.firstBtn, 0)
        hbox1.addWidget(self.privBtn, 0)
        hbox1.addWidget(self.nextBtn, 0)
        hbox1.addWidget(self.lastBtn, 0)

        hbox2 = QHBoxLayout()
        hbox2.addWidget(self.addBookmarkBtn, 0)
        hbox2.addWidget(self.addBookmarkBookBtn, 0)
        hbox2.addWidget(self.saveDbBtnBtn, 0)

        vbox = QVBoxLayout()
        vbox.addWidget(splitter, 2)
        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)

        self.setLayout(vbox)

        self.clear()

    def contextMenuEvent(self, event):

        menu = QMenu(self)

        clearFollowAction = menu.addAction("删除后续着法")

        action = menu.exec_(self.mapToGlobal(event.pos()))

        if action == clearFollowAction:
            self.onClearFollowBtnClick()

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

    def selectIndex(self, index):
        self.selectionIndex = index
        item = self.items[self.selectionIndex]
        self.positionView.setCurrentItem(item)
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
        msgbox = TimerMessageBox("当前棋谱已成功保存到对局库.", timeout = 0.5)
        msgbox.exec()
        
    def onAddBookmarkBtnClick(self):

        fen = self.parent.board.to_fen()

        if self.storage.isFenInBookmark(fen):
            msgbox = TimerMessageBox("收藏中已经有该局面存在.", timeout = 1)
            msgbox.exec()
            return

        name, ok = QInputDialog.getText(self, getTitle(), '请输入收藏名称:')
        if not ok:
            return

        if self.storage.isNameInBookmark(name):
            msgbox = TimerMessageBox(f'收藏中已经有[{name}]存在.', timeout = 1)
            msgbox.exec()
            return

        self.storage.saveBookmark(name, fen)
        self.parent.bookmarkView.updateBookmarks()

    def onAddBookmarkBookBtnClick(self):

        fen, moves = self.parent.getGameIccsMoves()

        name, ok = QInputDialog.getText(self, getTitle(), '请输入收藏名称:')
        if not ok:
            return

        if self.storage.isNameInBookmark(name):
            QMessageBox.information(None, f'{getTitle()}, 收藏中已经有[{name}]存在.')
            return

        self.storage.saveBookmark(name, fen, moves)
        self.parent.bookmarkView.updateBookmarks()

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
        #print(index)
        if index % 2 == 1:
            item.setText(0, f"{index//2+1}.")

        if 'move' in position:
            move = position['move']
            item.setText(1, move.to_text())
        else:
            item.setText(1, '=开始=')

        if 'score' in position:
            item.setText(2, str(position['score']))

        if 'diff' in position:
            diff = position['diff']
            print(diff)
            if diff > -8:
                item.setIcon(3, QIcon(":Images/star.png"))
            elif diff > -45:
                item.setIcon(3, QIcon(":Images/good.png"))
            elif diff > -90:
                item.setIcon(3, QIcon(":Images/sad.png"))
            else:
                item.setIcon(3, QIcon(":Images/bad.png"))
            
        item.setData(0, Qt.UserRole, index)
        #item.setData(1, Qt.UserRole, move)
        self.selectionIndex = index
        self.positionView.setCurrentItem(item)

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
        #self.storage = self.parent.storage
        
        self.boardView = ChessBoardView(self)
        self.historyView = HistoryWidget(self)

        splitter = QSplitter(self)
        splitter.setOrientation(Qt.Horizontal)
        splitter.addWidget(self.boardView)
        splitter.addWidget(self.historyView)

        splitter.setStretchFactor(0, 90)
        splitter.setStretchFactor(1, 10)

    def showBoardMoves(fen, moves):
        self.boardView.from_fen(fen)
        for it in moves:
            self.historyView.onNewPostion(it)

#-----------------------------------------------------#
class DockHistoryWidget(DockWidget):
    def __init__(self, parent):
        super().__init__(parent,
                         Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.inner = HistoryWidget(parent)
        self.setWidget(self.inner)
        self.setWindowTitle(self.inner.title)

#-----------------------------------------------------#
class ChessEngineWidget(QDockWidget):
    def __init__(self, parent, engine_mgr):

        super().__init__("引擎", parent)

        self.parent = parent
        self.engine_mgr = engine_mgr
        self.storage = parent.storage
        
        self.dockedWidget = QWidget(self)
        self.setWidget(self.dockedWidget)

        hbox = QHBoxLayout()

        self.engineLabel = QLabel()
        self.engineLabel.setAlignment(Qt.AlignCenter)

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

        self.eRedBox = QCheckBox("执红")
        self.eBlackBox = QCheckBox("执黑")
        self.analysisModeBox = QCheckBox("分析模式")
        self.configBtn = QPushButton("参数")
        self.reviewBtn = QPushButton("复盘分析")

        hbox.addWidget(self.configBtn, 0)
        hbox.addWidget(QLabel(' 线程数:'), 0)
        hbox.addWidget(self.threadsSpin, 0)
        hbox.addWidget(QLabel(' 存储:'), 0)
        hbox.addWidget(self.memorySpin, 0)
        hbox.addWidget(QLabel('MB  分支:'), 0)
        hbox.addWidget(self.multiPVSpin, 0)
        
        hbox.addWidget(self.eRedBox, 0)
        hbox.addWidget(self.eBlackBox, 0)
        hbox.addWidget(self.analysisModeBox, 0)
        hbox.addWidget(self.engineLabel, 2)
        hbox.addWidget(self.reviewBtn, 0)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        self.dockedWidget.setLayout(vbox)

        self.positionView = QTreeWidget()
        self.positionView.setColumnCount(1)
        self.positionView.setHeaderLabels(["深度", "得分", "着法"])
        self.positionView.setColumnWidth(0, 80)
        self.positionView.setColumnWidth(1, 100)
        self.positionView.setColumnWidth(2, 380)

        vbox.addWidget(self.positionView)

        self.engine_mgr.engine_ready_signal.connect(self.onEngineReady)
        self.branchs = []
                
    def contextMenuEvent(self, event):

        menu = QMenu(self)
        viewBranchAction = menu.addAction("分支推演")
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == viewBranchAction:
            self.onViewBranch()

    def onThreadsChanged(self, num):
        self.engine_mgr.set_engine_option(0, 'Threads', num)
        self.saveEngineOptions()
        
    def onMemoryChanged(self, num):
        self.engine_mgr.set_engine_option(0, 'Hash', num)
        self.saveEngineOptions()
        
    def onMultiPVChanged(self, num):
        self.engine_mgr.set_engine_option(0, 'MultiPV', num)
        self.saveEngineOptions()
        
    def saveEngineOptions(self): 
        options = {}
        self.storage.saveEngineOptions(0, options)
     
    def onViewBranch(self):
        self.parent.onViewBranch()

    def onEngineMoveInfo(self, fen, move_info):

        if not self.analysisModeBox.isChecked():
            return

        board = ChessBoard()
        board.from_fen(fen)

        iccs_str = ','.join(move_info["move"])
        move_info['iccs_str'] = iccs_str

        moves_text = []
        for step_str in move_info["move"]:
            move_from, move_to = Move.from_iccs(step_str)
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
        
        #for it in engine_options:
        #    print(it)

        self.engineLabel.setText(name)
        
        self.engine_mgr.set_config(engine_id, {'depth': 24})
        
        self.onThreadsChanged(self.threadsSpin.value())
        self.onMemoryChanged(self.memorySpin.value())
        self.onMultiPVChanged(self.multiPVSpin.value())
        
    def clear(self):
        self.positionView.clear()

    def sizeHint(self):
        return QSize(500, 150)

#------------------------------------------------------------------#
class MoveDbWidget(QDockWidget):
    #move_select_signal = Signal(int)

    def __init__(self, parent):
        super().__init__("我的棋谱库", parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.parent = parent
        self.storage = parent.storage
        
        self.moveListView = QTreeWidget()
        self.moveListView.setColumnCount(1)
        self.moveListView.setHeaderLabels(["备选着法", "得分", '', '备注'])
        self.moveListView.setColumnWidth(0, 80)
        self.moveListView.setColumnWidth(1, 60)
        self.moveListView.setColumnWidth(2, 1)
        self.moveListView.setColumnWidth(3, 100)

        self.moveListView.clicked.connect(self.onSelectIndex)
        
        self.importFollowMode = False

        self.setWidget( self.moveListView)

    def clear(self):
        self.moveListView.clear()
        
    def contextMenuEvent(self, event):

        menu = QMenu(self)
        importFollowAction = menu.addAction("导入分支(单选)")
        #importAllFollowAction = menu.addAction("导入分支(全部)")
        delFollowAction = menu.addAction("删除该分支")
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == importFollowAction:
            self.onImportFollow()
        elif action == delFollowAction:
            self.onDeleteFollow()

    def onImportFollow(self):
        self.importFollowMode = True
        self.onSelectIndex(0)
    
    def onDeleteFollow(self):
        pass
        
    def onImportFollowContinue(self):
        if self.moveListView.topLevelItemCount() != 1:
            self.importFollowMode = False
            return
        item = self.moveListView.topLevelItem(0)
        self.moveListView.setCurrentItem(item, 0)
        self.onSelectIndex(0)

    def updateBookMoves(self, book_moves):
        self.moveListView.clear()
        self.position_len = len(book_moves)
        for move_info in book_moves:
            item = QTreeWidgetItem(self.moveListView)

            item.setText(0, move_info['text'])

            if 'score' in move_info:
                item.setText(1, str(move_info['score']))
                item.setTextAlignment(1, Qt.AlignRight)

            #item.setText(2, str(move_info['count']))
            if 'memo' in move_info:
                item.setText(3, move_info['memo'])

            item.setData(0, Qt.UserRole, move_info)

        if self.importFollowMode:
            if self.position_len == 1:
                QTimer.singleShot(500, self.onImportFollowContinue)
            else:
                self.importFollowMode = False
       
    def onSelectIndex(self, index):
        item = self.moveListView.currentItem()
        move_info = item.data(0, Qt.UserRole)
        self.parent.onBookMove(move_info)

    def sizeHint(self):
        return QSize(150, 500)

#------------------------------------------------------------------#
class CloudDbWidget(QDockWidget):
    #move_select_signal = Signal(int)

    def __init__(self, parent):
        super().__init__("云库", parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.parent = parent
        self.storage = parent.storage
        
        
        self.cloudMovesView = QTreeWidget()
        self.cloudMovesView.setColumnCount(1)
        self.cloudMovesView.setHeaderLabels(["备选着法", "得分", '', '备注'])
        self.cloudMovesView.setColumnWidth(0, 80)
        self.cloudMovesView.setColumnWidth(1, 60)
        self.cloudMovesView.setColumnWidth(2, 1)
        self.cloudMovesView.setColumnWidth(3, 100)
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
        for move_info in moves:
            item = QTreeWidgetItem(self.cloudMovesView)
            item.setText(0, move_info['text'])    
            item.setText(1, str(move_info['score']))
            item.setTextAlignment(1, Qt.AlignRight)

            item.setData(0, Qt.UserRole, move_info)
       
    def onSelectIndex(self, index):
        item = self.cloudMovesView.currentItem()
        move_info = item.data(0, Qt.UserRole)
        self.parent.onBookMove(move_info)
        
    def sizeHint(self):
        return QSize(150, 500)

#------------------------------------------------------------------#
class EndBookWidget(QDockWidget):
    end_game_select_signal = Signal(int)

    def __init__(self, parent):
        super().__init__("残局库", parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.parent = parent
        self.storage = parent.storage

        self.dockedWidget = QWidget(self)
        self.setWidget(self.dockedWidget)

        self.bookView = QListWidget()

        hbox = QHBoxLayout()
        # Add widgets to the layout
        self.libCombo = QComboBox(self)
        self.libCombo.currentTextChanged.connect(self.onBookChanged)

        self.importBtn = QPushButton("导入")
        self.importBtn.clicked.connect(self.onImportBtnClick)

        hbox.addWidget(self.libCombo, 2)
        hbox.addWidget(self.importBtn, 0)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(self.bookView)
        self.dockedWidget.setLayout(vbox)

        self.bookView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.bookView.setAlternatingRowColors(True)
        self.bookView.doubleClicked.connect(self.onItemDoubleClicked)
        #self.bookView.clicked.connect(self.onItemClicked)

        self.update()

    def update(self):

        self.curr_book_name = ''
        self.curr_game = None

        self.books = self.storage.getAllEndBooks()
        self.libCombo.clear()
        self.libCombo.addItems(self.books.keys())

        self.libCombo.setCurrentIndex(0)

    def onImportBtnClick(self):
        self.parent.onImportEndBook()
        self.update()

    def onBookChanged(self, book_name):

        self.bookView.clear()

        if book_name == '':
            return

        self.curr_book_name = book_name
        self.curr_books = self.books[self.curr_book_name]
        self.curr_game = None

        for i, game in enumerate(self.books[self.curr_book_name]):
            item = QListWidgetItem()
            item.setText(game['name'])
            item.setData(Qt.UserRole, game)
            self.bookView.addItem(item)

    def onItemDoubleClicked(self, index):
        index_row = index.row()
        self.curr_game = self.books[self.curr_book_name][index_row]
        self.end_game_select_signal.emit(index_row)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        copyAction = menu.addAction("Copy Fen String")
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == copyAction:
            qApp.clipboard().setText(self.parent.board.to_fen())

    def sizeHint(self):
        return QSize(150, 500)


#------------------------------------------------------------------#
class GameReviewWidget(QDockWidget):
    #move_select_signal = Signal(int)

    def __init__(self, parent):
        super().__init__("复盘分析", parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.parent = parent

        self.moveListView = QTreeWidget()
        self.moveListView.setColumnCount(1)
        self.moveListView.setHeaderLabels(["着法", "得分", '备注'])
        self.moveListView.setColumnWidth(0, 80)
        self.moveListView.setColumnWidth(1, 80)
        self.moveListView.setColumnWidth(3, 100)

        self.moveListView.clicked.connect(self.onSelectIndex)

        self.setWidget(self.moveListView)

    def clear(self):
        self.moveListView.clear()

    def setData(self, book_moves):

        self.clear()
        for move_info in book_moves:
            item = QTreeWidgetItem(self.moveListView)

            item.setText(0, move_info['text'])

            if 'score' in move_info:
                item.setText(1, str(move_info['score']))

            #item.setText(2, str(move_info['count']))
            if 'memo' in move_info:
                item.setText(3, move_info['memo'])

            item.setData(0, Qt.UserRole, move_info)

    def onSelectIndex(self, index):
        item = self.moveListView.currentItem()
        move_info = item.data(0, Qt.UserRole)
        self.parent.onBookMove(move_info)

    def sizeHint(self):
        return QSize(150, 500)


#------------------------------------------------------------------#
class BookmarkWidget(QDockWidget):
    #end_game_select_signal = Signal(int)
    bookmark_type = ('局面收藏', '棋谱收藏')

    def __init__(self, parent):
        super().__init__("我的收藏", parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.parent = parent
        self.storage = parent.storage

        self.bookmarks = []
        self.curr_bookmark_type = self.bookmark_type[0]

        self.dockedWidget = QWidget(self)
        self.setWidget(self.dockedWidget)

        self.bookmarkView = QListWidget()
        self.bookmarkView.doubleClicked.connect(self.onDoubleClicked)

        self.bookmarkTypeCombo = QComboBox(self)
        self.bookmarkTypeCombo.currentTextChanged.connect(
            self.onBookTypeChanged)
        self.bookmarkTypeCombo.addItems(self.bookmark_type)

        hbox = QHBoxLayout()
        hbox.addWidget(self.bookmarkTypeCombo)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(self.bookmarkView)
        self.dockedWidget.setLayout(vbox)

        #self.bookmarkModel = QStandardItemModel(self.bookmarkView)
        #self.bookmarkView.setModel(self.bookmarkModel)
        self.bookmarkView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        #self.bookmarkView.setAlternatingRowColors(True)
        #self.bookmarkView.clicked.connect(self.onSelectIndex)

        self.curr_item = None

        self.updateBookmarks()

    def onBookTypeChanged(self, bookmark_tpye):
        self.curr_bookmark_type = bookmark_tpye
        self.updateBookmarks()

    def updateBookmarks(self):

        self.bookmarkView.clear()
        self.bookmarks = self.storage.getAllBookmarks()

        if self.curr_bookmark_type == self.bookmark_type[0]:
            filtered = filter(lambda x: 'moves' not in x, self.bookmarks)
        else:
            filtered = filter(lambda x: 'moves' in x, self.bookmarks)

        for i, it in enumerate(filtered):
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
            self.storage.removeBookmark(old_name)
            self.updateBookmarks()
        elif action == renameAction:
            new_name, ok = QInputDialog.getText(self,
                                                getTitle(),
                                                '请输入新名称:',
                                                text=old_name)
            if ok:
                self.storage.changeBookmarkName(fen, new_name)
                self.updateBookmarks()

    def onBookmarkChanged(self, book_name):
        pass

    def onDoubleClicked(self):
        item = self.bookmarkView.currentItem()
        position = item.data(Qt.UserRole)
        position['fen'] = position['fen']
        name = item.text()
        self.parent.loadBookGame(name, position)

    def onSelectIndex(self, index):
        self.curr_item = self.bookmarkView.itemFromIndex(index)

    def sizeHint(self):
        return QSize(150, 500)


#------------------------------------------------------------------#
class MyGameWidget(QDockWidget):
    def __init__(self, parent):
        super().__init__("我的对局", parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.parent = parent
        self.storage = parent.storage

        self.dockedWidget = QWidget(self)
        self.setWidget(self.dockedWidget)

        self.bookView = QListWidget()
        self.bookView.doubleClicked.connect(self.onDoubleClicked)

        vbox = QVBoxLayout()
        #vbox.addLayout(hbox)
        vbox.addWidget(self.bookView)
        self.dockedWidget.setLayout(vbox)
        self.bookView.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.curr_item = None

        self.updateMyGames()

    def updateMyGames(self):

        self.bookView.clear()
        self.games = self.storage.getAllMyGames()
        for i, it in enumerate(self.games):
            item = QListWidgetItem()
            item.setText(it['name'])
            item.setData(Qt.UserRole, it)
            self.bookView.addItem(item)

    def contextMenuEvent(self, event):

        menu = QMenu(self)

        removeAction = menu.addAction("删除")
        renameAction = menu.addAction("改名")
        action = menu.exec_(self.mapToGlobal(event.pos()))

        item = self.bookView.currentItem()
        old_name = item.text()
        fen = item.data(Qt.UserRole)['fen']

        if action == removeAction:
            self.storage.removeMyBook(old_name)
            self.updateMyGames()
        elif action == renameAction:
            new_name, ok = QInputDialog.getText(self,
                                                getTitle(),
                                                '请输入新名称:',
                                                text=old_name)
            if ok:
                self.storage.changeMyBookName(old_name, new_name)
                self.updateMyGames()

    def onDoubleClicked(self):
        item = self.bookView.currentItem()
        position = item.data(Qt.UserRole)
        position['fen'] = position['fen']
        name = item.text()
        self.parent.applyBook(name, position)

    def onSelectIndex(self, index):
        self.curr_item = self.bookView.itemFromIndex(index)

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
