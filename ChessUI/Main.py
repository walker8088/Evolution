# -*- coding: utf-8 -*-

import os
import time
import logging
from pathlib import Path
import ctypes
import platform

import yaml

from PySide6 import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtMultimedia import *

from qt_material import apply_stylesheet, QtStyleTools

from cchess import *

from .Utils import *
from .BoardWidgets import *
from .Widgets import *
from .Manager import *
from .Storage import *
from .Online import *

#-----------------------------------------------------#
class MainWindow(QMainWindow, QtStyleTools):
    initGameSignal = Signal(str)
    newBoardSignal = Signal()
    moveBeginSignal = Signal()
    moveEndSignal = Signal()
    newPositionSignal = Signal()

    def __init__(self, app):
        super().__init__()

        self.setAttribute(Qt.WA_DeleteOnClose)

        self.app = app

        self.setWindowIcon(QIcon(':Images/app.ico'))
        self.setWindowTitle(self.app.APP_NAME_TEXT)
        
        logging.basicConfig(filename = f'{self.app.APP_NAME}.log', filemode = 'w', level=logging.DEBUG)
                
        if platform.system() == "Windows":
            #在Windows状态栏上正确显示图标
            myappid = 'mycompany.myproduct.subproduct.version'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                myappid)

        #self.apply_stylesheet(self, 'dark_teal.xml')

        self.engine_manager = EngineManager(self)

        self.initGameDB()

        self.board = ChessBoard()
        self.game_manager = None

        self.boardView = ChessBoardView(self.board)
        self.setCentralWidget(self.boardView)
        self.boardView.try_move_signal.connect(self.onBoardMove)

        self.historyView = DockHistoryWidget(self)
        self.historyView.inner.positionSelSignal.connect(
            self.onSelectHistoryPosition)

        self.endBookView = EndBookWidget(self)
        self.endBookView.setVisible(False)
        self.endBookView.end_game_select_signal.connect(
            self.onSelectEndGameIndex)

        self.moveDbView = MoveDbWidget(self)
        self.cloudDbView = CloudDbWidget(self)

        self.bookmarkView = BookmarkWidget(self)
        self.bookmarkView.setVisible(False)
        self.myGameView = MyGameWidget(self)
        self.myGameView.setVisible(False)

        #self.gameReviewView  = GameReviewWidget(self)
        #self.gameReviewView.setVisible(False)

        self.engineView = ChessEngineWidget(self, self.engine_manager)
        self.engineView.configBtn.clicked.connect(self.onConfigEngine)
        self.engineView.reviewBtn.clicked.connect(self.onReviewGame)
        self.engineView.eRedBox.stateChanged.connect(self.onRedBoxChanged)
        self.engineView.eBlackBox.stateChanged.connect(self.onBlackBoxChanged)
        self.engineView.analysisModeBox.stateChanged.connect(
            self.onAnalysisModeBoxChanged)

        self.addDockWidget(Qt.LeftDockWidgetArea, self.historyView)
        self.addDockWidget(Qt.RightDockWidgetArea, self.moveDbView)
        self.addDockWidget(Qt.RightDockWidgetArea, self.cloudDbView)
        #self.addDockWidget(Qt.RightDockWidgetArea, self.gameReviewView)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.endBookView)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.bookmarkView)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.myGameView)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.engineView)
        
        self.initEngine()
        
        self.engine_manager.best_move_signal.connect(self.onEngineBestMove)
        self.engine_manager.move_probe_signal.connect(self.onEngineMoveProbe)
        self.engine_manager.checkmate_signal.connect(self.onEngineCheckmate)

        self.initSound()
        self.engine_working = False
        self.bind_engines = [None, None, None, None]

        self.readSettings()

        self.createActions()
        self.createMenus()
        self.createToolBars()

        self.game_mode = None
        self.clearAll()

        self.engine_manager.start()
        self.switchGameMode("open_book")

        #splash.finish()

    #-----------------------------------------------------------------------
    #
    def clearAll(self):
        self.base_fen = None
        self.positionList = []
        self.currPosition = None
        self.historyMode = False
        self.reviewMode = False

        self.historyView.inner.clear()
        self.moveDbView.clear()
        self.engineView.clear()
        self.boardView.set_view_only(False)
    
    def initEngine(self):
        with open(Path('Engine', 'engine.conf')) as f:
            try:
                engine_conf = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                print(exc)
                return False
        engine_path = engine_conf['engine']['run']
        ok = self.engine_manager.load_engine(Path('Engine', engine_path))
        return ok
        
    def initGameDB(self):
        self.storage = DataStore()
        self.storage.open(Path('Game', 'localbook.db'))

    #-----------------------------------------------------------------------
    #声音播放
    def initSound(self):
        self.soundVolume = 0
        self.audioOutput = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audioOutput)
        self.player.errorOccurred.connect(self.onPlayError)

    def playSound(self, s_type):
        if self.soundVolume > 0:
            self.player.setSource(QUrl.fromLocalFile(f'Sound/{s_type}.wav'))
            self.audioOutput.setVolume(self.soundVolume)
            self.player.setPosition(0)
            self.player.play()

    def onPlayError(self, error, error_string):
        logging.error(f'Sound PlayError: {error_string}')

    #-----------------------------------------------------------------------
    #基础信息
    def getGameIccsMoves(self):
        fen_base = self.positionList[0]['fen']
        moves = []

        for it in self.positionList[1:]:
            m = it['move']
            #print(m.to_iccs(), m.to_text())
            moves.append(m.to_iccs())

        return (fen_base, moves)

    #-----------------------------------------------------------------------
    #Game 相关
    def switchGameMode(self, game_mode):

        #模式未变
        if self.game_mode == game_mode:
            return

        self.game_mode = game_mode

        if self.game_mode == 'end_book':
            self.myGamesAct.setEnabled(False)
            self.bookmarkAct.setEnabled(False)
            self.endBookView.show()
            self.bookmarkView.hide()
            self.myGameView.hide()
            self.moveDbView.hide()
            self.initGame(EMPTY_FEN)

        elif self.game_mode == 'open_book':
            self.myGamesAct.setEnabled(True)
            self.bookmarkAct.setEnabled(True)
            self.endBookView.hide()
            self.moveDbView.show()
            #self.bookmarkView.show()
            self.initGame(FULL_INIT_FEN)

    def initGame(self, fen=None, is_only_once=False):

        if (fen is not None) and (not is_only_once):
            self.init_fen = fen

        self.engine_manager.stop_thinking()
        self.clearAll()

        if is_only_once:
            init_fen = fen if fen else ''
        else:
            init_fen = self.init_fen

        self.init_fen = init_fen
      
        if self.game_mode == 'end_book':
            self.engineView.eRedBox.setChecked(False)
            self.engineView.eBlackBox.setChecked(True)
            self.engineView.analysisModeBox.setChecked(False)
        else:
            self.engineView.eRedBox.setChecked(False)
            self.engineView.eBlackBox.setChecked(False)
            self.engineView.analysisModeBox.setChecked(False)
        
        self.boardView.from_fen(self.init_fen)
        
        position = {
            'fen': self.init_fen,
            'index': 0,
            'move_side': self.boardView.get_move_color()
            }
        
        self.onPositionChanged(position, is_new = True)
 
    def onGameOver(self, win_side):

        if self.game_mode == 'end_book':
            if win_side == BLACK:
                msgbox = TimerMessageBox("挑战失败, 重新再来!")
            else:
                msgbox = TimerMessageBox("恭喜！ 挑战成功！！！")
            msgbox.exec()
            #self.onRestartGame()

        elif self.game_mode == 'open_book':
            win_msg = '红方被将死!' if win_side == BLACK else '黑方被将死!'
            msgbox = TimerMessageBox(win_msg)
            msgbox.exec()

        #self.engine_working = False
        self.boardView.set_view_only(True)

    def onSelectEndGameIndex(self, index):
        curr_game = self.endBookView.curr_game
        #self.init_fen =  curr_game['fen']
        self.book_moves = curr_game['moves'] if 'moves' in curr_game else None
        self.initGame(curr_game['fen'])

    def onReviewGame(self):

        if len(self.positionList) <= 1:
            return

        if not self.reviewMode:
            self.onReviewGameBegin()
        else:
            self.onReviewGameEnd(isCanceled=True)

    def onReviewGameBegin(self):

        self.reviewMode = True

        self.engineView.eRedBox.setChecked(False)
        self.engineView.eBlackBox.setChecked(False)
        self.engineView.analysisModeBox.setChecked(True)
        self.engineView.reviewBtn.setText('停止分析')
        self.historyView.inner.selectIndex(0)
        self.onReviewGameStep()
        
    def onReviewGameStep(self):
        sel_index = self.historyView.inner.selectionIndex + 1
        while True:
            if sel_index >= (len(self.positionList) - 1):  #已到最后一步
                self.onReviewGameEnd()
                return
            pos = self.positionList[sel_index]
            if 'score' in pos and pos['score'] != '':
                sel_index +=  1
                continue
            else:            
                self.historyView.inner.selectIndex(sel_index)

    def onReviewGameEnd(self, isCanceled=False):
        self.reviewMode = False
        self.engineView.reviewBtn.setText('复盘分析')
        if not isCanceled:
            msgbox = TimerMessageBox("  复盘分析完成。  ", timeout=1)
            msgbox.exec()
            self.engineView.analysisModeBox.setChecked(False)

    def saveGameToDB(self):
        self.storage.saveMovesToBook(self.positionList[1:])

    def loadBookGame(self, name, game_info):
    
        fen = game_info['fen']
        self.initGame(fen, is_only_once = True)
        if 'moves' in game_info:
            iccs_moves = game_info['moves']
            for iccs in iccs_moves:
                self.onMoveGo(iccs)

        self.setWindowTitle(f'{self.app.APP_NAME_TEXT} -- {name}')

    #--------------------------------------------------------------------
    #引擎相关
    def detectRunEngine(self):
        new_working = False

        for it in self.bind_engines:
            if it is not None:
                new_working = True
                break

        if new_working and (new_working != self.engine_working):
            self.engine_working = True
            self.runEngine()

        self.engine_working = new_working

    def runEngine(self):

        if not self.engine_working:
            return

        if 'move' in self.currPosition:
            fen_engine = self.currPosition['move'].to_engine_fen()
        else:
            fen_engine = self.currPosition['fen']

        self.engine_manager.go_from(0, fen_engine)

    def engine_play(self, engine_id, side, yes):

        if yes:
            self.bind_engines[side] = engine_id

        else:
            self.bind_engines[side] = None

        self.detectRunEngine()

    def engine_analyze(self, yes):
        self.bind_engines[3] = 99 if yes else None
        self.detectRunEngine()

    def onConfigEngine(self):
        params = self.engine_manager.get_config(0)

        dlg = EngineConfigDialog()
        if dlg.config(params):
            self.engine_manager.update_config(0, params)

    def onRedBoxChanged(self, state):
        self.engine_play(0, RED, Qt.CheckState(state) == Qt.Checked)

    def onBlackBoxChanged(self, state):
        self.engine_play(0, BLACK, Qt.CheckState(state) == Qt.Checked)

    def onAnalysisModeBoxChanged(self, state):
        self.engine_analyze(Qt.CheckState(state) == Qt.Checked)

    def onViewBranch(self, branch):
        dlg = PositionHistDialog()
        dlg.exec()

    #-----------------------------------------------------------------
    #
    def onSelectHistoryPosition(self, move_index):

        if (move_index < 0) or (move_index >= len(self.positionList)):
            return

        self.currPosition = self.positionList[move_index]
        is_last = True if move_index >= len(self.positionList) - 1 else False

        if is_last:
            self.historyMode = False
            self.boardView.set_view_only(False)
        else:
            self.historyMode = True
            self.boardView.set_view_only(True)

        if 'move' in self.currPosition:
            move = self.currPosition['move']
            self.boardView.from_fen(move.board.to_fen())
            self.boardView.show_move(move.p_from, move.p_to)

        #self.boardView.from_fen(fen)
        
        self.onPositionChanged(self.currPosition, is_new = False)
        
    def deleteHistoryFollow(self, move_step):
        self.positionList = self.positionList[:move_step + 1]

        if len(self.positionList) > 0:
            self.currPosition = self.positionList[-1]
        else:
            self.currPosition = None

        self.historyMode = False
        self.boardView.set_view_only(False)

    #------------------------------------------------------------------------------
    #None UI Events
    def onEngineMoveProbe(self, engine_id, info):
        fen = self.board.to_fen()
        self.engineView.onEngineMoveInfo(fen, info)

    def onEngineCheckmate(self, engine_id, info):
        print('onEngineCheckmate')

        if self.historyMode:
            return

        print(self.board.move_player)
        win_side = self.board.move_player.next()
        print("WIN:", win_side)
        self.onGameOver(win_side)

    def onEngineBestMove(self, engine_id, move_info):

        if not self.board.is_valid_iccs_move(move_info['move']):
            return
            
        move_color = self.board.get_move_color()
        
        if self.currPosition['index'] > 0:
            if 'score' not in move_info:
                print("score not found:", move_info)
            else:
                score = move_info['score']
                self.currPosition[
                    'score'] = score if move_color == BLACK else -score
                self.currPosition['move_scores'] = move_info['move_scores']

        self.historyView.inner.onUpdatePosition(self.currPosition)

        if self.reviewMode:
            self.onReviewGameStep()
            return

        if self.historyMode:
            return

        if self.bind_engines[move_color] != engine_id:
            return

        self.onMoveGo(move_info['move'])

    def onBookMove(self, move_info):

        if self.historyMode:
            return
            
        if not self.board.is_valid_iccs_move( move_info['move']):
            return

        self.onMoveGo( move_info['move'])#, move_info['score'])

    def searchBookMoves(self, fen):
    
        def key_func(it):
            try:
                return int(it['score'])
            except ValueError:
                return 0
            except KeyError:
                return 0

        self.moveDbView.clear()
        board = ChessBoard(fen)
        book_moves = []

        ret = self.storage.getAllBookMoves(fen)
        if len(ret) == 0:
            return
        elif len(ret) > 1:
            print('database error', fen, ret)
            return

        for it in ret:
            if 'actions' not in it:
                continue
            for act in it['actions']:
                act['text'] = board.copy().move_iccs(act['move']).to_text()
                book_moves.append(act)
                
        is_reverse  = True if board.get_move_color() == RED else False        
        book_moves.sort(key=key_func, reverse = is_reverse)
        
        self.moveDbView.updateBookMoves(book_moves)
    
    def searchCloudMoves(self, fen):
    
        self.cloudDbView.clear()
        
        moves = QueryFromCloudDB(fen)
        if  len(moves) == 0:
            return
            
        if self.currPosition['index'] >  0:
            prevPosition = self.positionList[ self.currPosition['index'] - 1]
            curr_iccs = self.currPosition['move'].to_iccs()
            curr_score = moves[0]['score']
            self.currPosition['score'] = curr_score
           
            if 'next_moves' in prevPosition:
                best_moves = prevPosition['next_moves']
            
            if curr_iccs in best_moves:
                self.currPosition['diff'] = best_moves[curr_iccs]['diff']
                #print(self.currPosition['diff'])
            else:
                pass  
        
        #构造着法得分供下一个着法查询    
        move_dict = {}    
        for it in moves:
            move_dict[it['move']] = {'score': it['score'], 'diff': it['diff']}
        self.currPosition['next_moves'] = move_dict
        
        self.historyView.inner.onUpdatePosition(self.currPosition)
   
        self.cloudDbView.updateCloudMoves(moves)

    #-----------------------------------------------------------
    #走子核心逻辑
    def onPositionChanged(self, position, is_new = True):   
        
        self.currPosition = position        
        fen = position['fen']
        
        if is_new:
            self.positionList.append(position)
            self.historyView.inner.onNewPostion(self.currPosition)
            
            if 'move' in position:
                move = position['move']            
                if move.is_checking:
                    if move.is_checkmate:
                        msg = "将死！"
                        self.playSound('mate')
                    else:
                        self.playSound('check')
                        msg = "将军！"
                elif move.captured:
                    self.playSound('capture')
                    msg = f"吃{fench_to_text(move.captured)}"
                else:
                    self.playSound('move')
                    msg = ""
                self.statusBar().showMessage(msg)

        self.boardView.from_fen(fen)    
        self.engineView.clear()
        
        self.searchBookMoves(fen)
        self.searchCloudMoves(fen)
        self.runEngine()
    
    def onBoardMove(self,  move_from,  move_to):
        move_iccs = ChessBoard.pos_to_iccs(move_from, move_to)
        self.onMoveGo(move_iccs)
        
    def onMoveGo(self,  move_iccs, score = ''):

        self.historyMode = True  #用historyMode保护在此期间引擎输出的move信息被忽略
        
        move_from, move_to = Move.from_iccs(move_iccs)
        
        self.boardView.show_move(move_from, move_to)
        
        #--------------------------------
        #self.board在做了这个move动作后，棋子已经更新到新位置了
        move = self.board.move(move_from, move_to)
        #board是下个走子的position了
        self.board.next_turn()
        #--------------------------------
      
        #这一行必须有,否则引擎不能工作
        hist = [x['move'] for x in self.positionList[1:]]
        move.prepare_for_engine(move.board.move_player.opposite(), hist)

        self.historyMode = False  #结束保护
        
        position = {
            'fen': self.board.to_fen(),
            'fen_prev': move.board.to_fen(),
            'move': move,
            'score': score,
            'index': len(self.positionList),
            'move_side': move.board.move_player.color
        }
        
        self.onPositionChanged(position)
      
        if move.is_checkmate:
            self.onGameOver(move.board.move_player)
      
    #------------------------------------------------------------------------------
    #UI Events
    def onDoOpenBook(self):
        self.switchGameMode("open_book")

    def onDoEndBook(self):
        self.switchGameMode("end_book")

    def onDoOnline(self):
        self.switchGameMode("online_game")
        dlg = OnlineDialog(self)
        dlg.show()
        
    def onRestartGame(self):
        self.initGame()

    def onShowMyGames(self):
        if self.myGameView.isVisible():
            self.myGameView.hide()
        else:
            self.myGameView.show()

    def onShowBookmark(self):
        if self.bookmarkView.isVisible():
            self.bookmarkView.hide()
        else:
            self.bookmarkView.show()

    def onFlipBoardChanged(self, state):
        self.boardView.setFlipBoard(state)

    def onMirrorBoardChanged(self, state):
        self.boardView.setMirrorBoard(state)

    def onEditBoard(self):
        dlg = PositionEditDialog(self)
        new_fen = dlg.edit(self.board.to_fen())
        if new_fen:
            self.initGame(new_fen)

    def onSearchBoard(self):
        dlg = PositionEditDialog(self)
        new_fen = dlg.edit('')
        if new_fen:
            self.initGame(new_fen)

    def onOpenFile(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog

        fileName, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "", "象棋演播室文件(*.xqf);;PGN文件(*.pgn)", options=options)

        if not fileName:
            return

        game = None
        fileName = Path(fileName)

        ext = fileName.suffix.lower()
        if ext == '.xqf':
            game = read_from_xqf(fileName)
        elif ext == '.pgn':
            pass

        if game:
            game_info = {
                'fen': game.init_board.to_fen(),
                'moves': game.dump_iccs_moves()[0]
            }
            self.loadBookGame(fileName.name, game_info)

    def onSaveFile(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog

        fileName, _ = QFileDialog.getSaveFileName(
            self,
            "保存对局文件",
            "",
            "象棋演播室文件(*.xqf);;PGN文件(*.pgn)",
            options=options)

        if not fileName:
            return

        ext = Path(fileName).suffix.lower()
        print(ext)

    def onImportEndBook(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(
            self,
            "打开残局文件",
            "",
            "残局文件(*.eglib);;All Files (*)",
            options=options)
        if not fileName:
            return

        lib_name = Path(fileName).stem
        if self.storage.isEndBookExist(lib_name):
            msgbox = TimerMessageBox(f"残局库[{lib_name}]系统中已经存在，不能重复导入。",
                                     timeout=2)
            msgbox.exec()
            return

        games = load_eglib(fileName)

        #for it in games:
        #    print(it['name'])

        self.storage.saveEndBook(lib_name, games)
        #self.endBookView.update_fen()

    #------------------------------------------------------------------------------
    #UI Base
    def createActions(self):

        self.openFileAct = QAction(self.style().standardIcon(
            QStyle.SP_FileDialogStart),
                                   "打开对局",
                                   self,
                                   statusTip="打开对局文件",
                                   triggered=self.onOpenFile)

        self.saveFileAct = QAction(self.style().standardIcon(
            QStyle.SP_DialogSaveButton),
                                   "保存对局",
                                   self,
                                   statusTip="保存对局文件",
                                   triggered=self.onSaveFile)

        self.doOpenBookAct = QAction(QIcon(':Images/openbook.png'),
                                     "打谱练习",
                                     self,
                                     statusTip="打谱练习",
                                     triggered=self.onDoOpenBook)

        self.doEndBookAct = QAction(QIcon(':Images/endbook.png'),
                                    "残局挑战",
                                    self,
                                    statusTip="残局挑战",
                                    triggered=self.onDoEndBook)

        self.doOnlineAct = QAction(QIcon(':Images/online.png'),
                                   "连线分析",
                                   self,
                                   statusTip="连线分析",
                                   triggered=self.onDoOnline)

        self.restartAct = QAction(QIcon(':Images/restart.png'),
                                  "重新开始",
                                  self,
                                  statusTip="重新开始",
                                  triggered=self.onRestartGame)

        self.editBoardAct = QAction(QIcon(':Images/edit.png'),
                                    "自定局面",
                                    self,
                                    statusTip="从自定局面开始",
                                    triggered=self.onEditBoard)

        self.searchBoardAct = QAction(QIcon(':Images/search.png'),
                                      "搜索局面",
                                      self,
                                      statusTip="从对局库中搜索局面",
                                      triggered=self.onSearchBoard)

        self.myGamesAct = QAction(QIcon(':Images/mybook.png'),
                                  "我的对局库",
                                  self,
                                  statusTip="我的对局库",
                                  triggered=self.onShowMyGames)

        self.bookmarkAct = QAction(QIcon(':Images/bookmark.png'),
                                   "我的收藏",
                                   self,
                                   statusTip="我的收藏",
                                   triggered=self.onShowBookmark)

        self.upgradeAct = QAction("升级到专业版",
                                  self,
                                  statusTip="升级到专业版",
                                  triggered=self.onUpgradeToProfessional)

        self.exitAct = QAction(QIcon(':Images/exit.png'),
                               "退出程序",
                               self,
                               shortcut="Ctrl+Q",
                               statusTip="退出应用程序",
                               triggered=qApp.closeAllWindows)

        self.aboutAct = QAction(
            "关于...",
            self,
            #statusTip="Show the application's About box",
            triggered=self.about)

    def createMenus(self):
        self.fileMenu = self.menuBar().addMenu("文件")
        self.fileMenu.addAction(self.openFileAct)
        self.fileMenu.addAction(self.saveFileAct)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.exitAct)

        self.menuBar().addSeparator()

        self.showMoveSoundAct = QAction('走子音效', checkable=True)
        self.showMoveSoundAct.setChecked(
            True if self.soundVolume > 0 else False)
        self.showMoveSoundAct.toggled.connect(self.onShowMoveSound)

        self.winMenu = self.menuBar().addMenu("窗口")
        self.winMenu.addAction(self.historyView.toggleViewAction()) 
        self.winMenu.addAction(self.engineView.toggleViewAction())
        self.winMenu.addAction(self.moveDbView.toggleViewAction())
        self.winMenu.addAction(self.cloudDbView.toggleViewAction())
        self.winMenu.addAction(self.showMoveSoundAct)

        self.helpMenu = self.menuBar().addMenu("帮助")
        self.helpMenu.addAction(self.upgradeAct)
        self.helpMenu.addAction(self.aboutAct)

    def createToolBars(self):

        self.fileBar = self.addToolBar("File")
        self.fileBar.addAction(self.openFileAct)
        self.fileBar.addAction(self.saveFileAct)
        self.fileBar.addAction(self.myGamesAct)
        self.fileBar.addAction(self.bookmarkAct)

        ag = QActionGroup(self)
        ag.setExclusive(True)
        ag.addAction(self.doOpenBookAct)
        ag.addAction(self.doEndBookAct)
        ag.addAction(self.doOnlineAct)

        self.gameBar = self.addToolBar("Game")

        self.gameBar.addAction(self.doEndBookAct)
        self.gameBar.addAction(self.doOpenBookAct)
        self.gameBar.addAction(self.doOnlineAct)
        self.gameBar.addAction(self.restartAct)
        self.gameBar.addAction(self.editBoardAct)
        #self.gameBar.addAction(self.searchBoardAct)

        self.flipBoardBox = QCheckBox()  #"翻转")
        self.flipBoardBox.setIcon(QIcon(':Images/up_down.png'))
        self.flipBoardBox.stateChanged.connect(self.onFlipBoardChanged)

        self.mirrorBoardBox = QCheckBox()  #"镜像")
        self.mirrorBoardBox.setIcon(QIcon(':Images/left_right.png'))
        self.mirrorBoardBox.stateChanged.connect(self.onMirrorBoardChanged)

        self.showBar = self.addToolBar("Show")
        self.showBar.addWidget(self.flipBoardBox)
        self.showBar.addWidget(self.mirrorBoardBox)
        #self.showBar.addSeparator()

        self.sysBar = self.addToolBar("System")
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.sysBar.addWidget(spacer)
        self.sysBar.addAction(self.exitAct)

        self.statusBar().showMessage("Ready")

    def onShowMoveSound(self, yes):
        self.soundVolume = 30 if yes else 0

    def onUpgradeToProfessional(self):
        pass

    def center(self):
        screen = QDesktopWidget().screenGeometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) // 2,
                  (screen.height() - size.height()) // 2)

    def closeEvent(self, event):
        self.writeSettings()
        self.engine_manager.stop()
        self.storage.close()

    def readSettings(self):
        self.settings = QSettings('Company', self.app.APP_NAME)

        self.restoreGeometry(self.settings.value("geometry", QByteArray()))

        yes = bool(self.settings.value("historyView", True))
        self.historyView.setVisible(yes)

        yes = bool(self.settings.value("engineView", True))
        self.engineView.setVisible(yes)

        yes = bool(self.settings.value("moveDBView", True))
        self.moveDbView.setVisible(yes)
        
        yes = bool(self.settings.value("cloudDBView", True))
        self.cloudDbView.setVisible(yes)

        self.soundVolume = self.settings.value("soundVolume", 30)

    def writeSettings(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("historyView", self.historyView.isVisible())
        self.settings.setValue("engineView", self.engineView.isVisible())
        self.settings.setValue("moveDBView", self.moveDbView.isVisible())
        self.settings.setValue("cloudDBView", self.moveDbView.isVisible())
        self.settings.setValue("soundVolume", self.soundVolume)

    def about(self):
        from .Version import release_version
        
        QMessageBox.about(
            self, f"关于 {self.app.APP_NAME}",
            f"{self.app.APP_NAME_TEXT} Version{release_version}\n棋谱管家，\n 云库支持:\n 引擎支持：皮卡鱼(https://pikafish.org/)\n 问题反馈,联系作者：1053386709@qq.com"
        )


#-----------------------------------------------------#
