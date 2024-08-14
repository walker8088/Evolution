# -*- coding: utf-8 -*-

import os
import time
import logging
import ctypes
import traceback
import platform
import yaml
import configparser
from enum import Enum, auto

from pathlib import Path
from dataclasses import dataclass
from collections import OrderedDict

from PySide6 import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtMultimedia import *

from cchess import *

from .Utils import *
from .BoardWidgets import *
from .Widgets import *
from .Manager import *
from .Storage import *
from .Online import *

from . import Globl

#-----------------------------------------------------#

@dataclass
class Position:
    fen: str
    fen_prev: str
    iccs:str
    score: int
    index: int
    move_color: int
    move: Move

@dataclass
class Position:
    fen: str
    score: int
    diff: int

#-----------------------------------------------------#
# Back up the reference to the exceptionhook
sys._excepthook = sys.excepthook

def my_exception_hook(exctype, value, tb):
    # Print the error and traceback
    msg = ''.join(traceback.format_exception(exctype, value, tb))
    QMessageBox.critical(None, getTitle(), msg)
    logging.error(f'Critical Error: {msg}')

# Set the exception hook to our wrapping function
sys.excepthook = my_exception_hook

#-----------------------------------------------------#
class GameMode(Enum):
    Free = auto()
    Fight = auto()
    EndBook = auto()
    Online = auto()

#-----------------------------------------------------#
class MainWindow(QMainWindow):
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
        
        logging.basicConfig(filename = f'{self.app.APP_NAME}.log', filemode = 'w', level = logging.INFO) #logging.DEBUG) 
                
        if platform.system() == "Windows":
            #在Windows状态栏上正确显示图标
            myappid = 'mycompany.myproduct.subproduct.version'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                myappid)
        
        #self.isSearchCloud = True
        
        Globl.engineManager = EngineManager(self)
        self.initGameDB()
        self.board = ChessBoard()
        
        self.boardView = ChessBoardWidget(self.board)
        self.setCentralWidget(self.boardView)
        self.boardView.tryMoveSignal.connect(self.onBoardMove)
        self.boardView.rightMouseSignal.connect(self.onBoardRightMouse)

        self.historyView = DockHistoryWidget(self)
        self.historyView.inner.positionSelSignal.connect(
            self.onSelectHistoryPosition)
        self.historyView.inner.reviewByCloudBtn.clicked.connect(self.onReviewByCloud)
        self.historyView.inner.reviewByEngineBtn.clicked.connect(self.onReviewByEngine)
        #self.historyView.inner.reviewByEngineBtn.setEnabled(False)

        self.endBookView = EndBookWidget(self)
        self.endBookView.setVisible(False)
        self.endBookView.end_game_select_signal.connect(self.onSelectEndGame)

        self.moveDbView = MoveDbWidget(self)
        self.cloudDbView = CloudDbWidget(self)

        self.bookmarkView = BookmarkWidget(self)
        self.bookmarkView.setVisible(False)
        #self.myGameView = MyGameWidget(self)
        #self.myGameView.setVisible(False)

        #self.gameReviewView  = GameReviewWidget(self)
        #self.gameReviewView.setVisible(False)

        self.engineView = ChessEngineWidget(self)
        self.engineView.configBtn.clicked.connect(self.onConfigEngine)
        #self.engineView.reviewBtn.clicked.connect(self.onReviewGame)
        self.engineView.eRedBox.stateChanged.connect(self.onRedBoxChanged)
        self.engineView.eBlackBox.stateChanged.connect(self.onBlackBoxChanged)
        self.engineView.analysisModeBox.stateChanged.connect(
            self.onAnalysisModeBoxChanged)

        self.addDockWidget(Qt.LeftDockWidgetArea, self.moveDbView)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.cloudDbView)
        #self.addDockWidget(Qt.RightDockWidgetArea, self.gameReviewView)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.endBookView)
        self.addDockWidget(Qt.RightDockWidgetArea, self.historyView)
        self.addDockWidget(Qt.RightDockWidgetArea, self.bookmarkView)
        #self.addDockWidget(Qt.LeftDockWidgetArea, self.myGameView)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.engineView)
        
        self.initEngine()
        
        Globl.engineManager.best_move_signal.connect(self.onEngineBestMove)
        Globl.engineManager.move_probe_signal.connect(self.onEngineMoveProbe)
        #Globl.engineManager.checkmate_signal.connect(self.onEngineCheckmate)

        self.initSound()
        self.engine_working = False
        self.bind_engines = [None, None, None, None]

        self.readSettings()

        self.createActions()
        self.createMenus()
        self.createToolBars()

        self.gameMode = None
        self.analyzeMode = ''
        self.reviewMode = ''
        
        self.clearAll()
        
        self.cloud = CloudDB(self)
        self.cloud.query_result_signal.connect(self.onCloudQueryResult)
        
        Globl.engineManager.start()
        
        self.switchGameMode(self.game_mode_saved)
        
        self.loadMemoState()

        #splash.finish()

    #-----------------------------------------------------------------------
    #初始化
    def clearAll(self):
        self.base_fen = None
        self.fenPosDict = OrderedDict()
        self.positionList = []
        self.currPosition = None
        self.historyMode = False
        self.reviewMode = None
        
        self.historyView.inner.clear()
        self.moveDbView.clear()
        self.engineView.clear()
        self.boardView.setViewOnly(False)

    def initEngine(self):
        self.config_file = Path('Evolution.ini')
        
        if not self.config_file.is_file():
            QMessageBox.critical(self, f'{getTitle()}', f'配置文件[{self.config_file}]不存在，请确保该文件存在并配置正确.')
            return False    
       
        self.config = configparser.ConfigParser()
        try:
            ok = self.config.read(self.config_file)
        except Exception as e:
            QMessageBox.critical(self, f'{getTitle()}', f'打开配置文件[{self.config_file}]出错：{e}')
            return False
        
        try:
            engine_type = self.config['MainEngine']['engine_type'].lower()
            engine_exec = Path(self.config['MainEngine']['engine_exec'])
        except Exception as e:
            QMessageBox.critical(self, f'{getTitle()}', f'配置文件[{self.config_file}]格式错误：{e}')
            return False
        
        ok = Globl.engineManager.load_engine(engine_exec, engine_type)
        if not ok:
            QMessageBox.critical(self, f'{getTitle()}', f'加载象棋引擎[{engine_exec.absolute()}]出错，请确认该程序能在您的电脑上正确运行。')
        
        return ok

        '''
        try:
            engine_type = self.config['AssitEngine']['engine_type'].lower()
            engine_exec = Path(self.config['AssitEngine']['engine_exec'])
        except Exception as e:
            QMessageBox.critical(self, f'{getTitle()}', f'配置文件[{self.config_file}]格式错误：{e}')
            return False
        
        ok = Globl.engineManager.load_engine(engine_exec, engine_type)
        if not ok:
            QMessageBox.critical(self, f'{getTitle()}', f'加载象棋引擎[{engine_exec.absolute()}]出错，请确认该程序能在您的电脑上正确运行。')
        
        return ok
 
        '''
        
    def initGameDB(self):

        gamePath = Path('Game')
        gamePath.mkdir(exist_ok=True)
        
        Globl.storage = DataStore()
        Globl.storage.open(Path(gamePath, 'Evolution.jdb'))

        #self.openbook = OpenBook()
        #self.openbook.loadBookFile(Path(gamePath, 'openbook.db'))
        
        self.openbook = OpenBookYfk()
        #self.openbook.loadBookFile(Path(gamePath, 'openbook.yfk'))
        self.openbook.loadBookFile(Path(gamePath, '先锋无敌nn库.yfk'))
        
        #self.openbook_json = OpenBookJson()
        #self.openbook_json.loadBookFile(Path(gamePath, 'openbook.jdb'))
    
    def loadOpenBook(self, file_name):
        self.openBook = OpenBookYfk()
        self.openBook.loadBookFile(file_name)
        self.openBook.getMoves(FULL_INIT_FEN)

    #-----------------------------------------------------------------------
    #声音播放
    def initSound(self):
        self.soundVolume = 0
        self.audioOutput = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audioOutput)
        self.player.errorOccurred.connect(self.onPlayError)

    def playSound(self, s_type):
        #print('playSound', s_type, self.soundVolume) 
        if self.soundVolume > 0:
            self.player.setSource(QUrl.fromLocalFile(f'Sound/{s_type}.wav'))
            self.audioOutput.setVolume(100) #self.soundVolume)
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
            m = it['iccs']
            #print(m.to_iccs(), m.to_text())
            moves.append(m.to_iccs())

        return (fen_base, moves)

    #-----------------------------------------------------------------------
    #Game 相关
    def switchGameMode(self, gameMode):

        #模式未变
        if self.gameMode == gameMode:
            return
        self.lastGameMode = self.gameMode    
        self.gameMode = gameMode

        if self.gameMode == GameMode.EndBook:
            self.myGamesAct.setEnabled(False)
            self.bookmarkAct.setEnabled(False)
            self.endBookView.show()
            self.bookmarkView.hide()
            #self.myGameView.hide()
            self.moveDbView.clear()
            self.moveDbView.hide()
            self.cloudDbView.hide()
            
            self.openFileAct.setEnabled(False)
            self.editBoardAct.setEnabled(False)
            
            self.cloudModeBtn.setEnabled(False)
            self.engineModeBtn.setEnabled(False)
            self.engineModeBtn.setChecked(True)
            
            self.showBestBox.setEnabled(False)
            self.showBestBox.setChecked(False)

            self.engineView.eRedBox.setChecked(False)
            self.engineView.eBlackBox.setChecked(True)
            self.engineView.analysisModeBox.setChecked(False)
            self.cloudModeBtn.setChecked(False)
            #self.initGame(EMPTY_FEN)
            self.endBookView.nextGame()
            
        elif self.gameMode == GameMode.Free:
            self.setWindowTitle(f'{self.app.APP_NAME_TEXT} - 自由练习')
            self.myGamesAct.setEnabled(True)
            self.bookmarkAct.setEnabled(True)
            self.endBookView.hide()
            self.moveDbView.show()
            self.cloudDbView.show()
            
            self.engineView.eRedBox.setChecked(False)
            self.engineView.eBlackBox.setChecked(False)
            self.engineView.analysisModeBox.setChecked(False)
        
            self.cloudModeBtn.setEnabled(True)
            self.engineModeBtn.setEnabled(True)
            #self.engineModeBtn.setChecked(True)
            self.cloudModeBtn.setChecked(True)
            
            self.showBestBox.setEnabled(True)
            self.showBestBox.setChecked(True)
            
            self.openFileAct.setEnabled(True)
            self.editBoardAct.setEnabled(True)
        
            if self.lastGameMode not in [GameMode.Fight, ]:        
                self.initGame(FULL_INIT_FEN)
        
        elif self.gameMode == GameMode.Fight:
            self.setWindowTitle(f'{self.app.APP_NAME_TEXT} - 人机练习')
            self.myGamesAct.setEnabled(True)
            self.bookmarkAct.setEnabled(True)
            self.endBookView.hide()
            self.moveDbView.hide()
            self.cloudDbView.hide()
            
            self.cloudModeBtn.setEnabled(True)
            self.cloudModeBtn.setChecked(False)
            self.engineModeBtn.setEnabled(True)
            self.engineModeBtn.setChecked(True)
            
            self.showBestBox.setEnabled(True)
            self.showBestBox.setChecked(False)
        
            self.openFileAct.setEnabled(False)
            self.editBoardAct.setEnabled(True)
        
            self.engineView.eRedBox.setChecked(False)
            self.engineView.eBlackBox.setChecked(True)
            self.engineView.analysisModeBox.setChecked(False)
            self.cloudModeBtn.setChecked(True)
            
            if self.lastGameMode in [None, GameMode.EndBook]:
                self.initGame(FULL_INIT_FEN)
            
    def initGame(self, fen=None, is_only_once=False):

        if (fen is not None) and (not is_only_once):
            self.init_fen = fen

        Globl.engineManager.stop_thinking()

        self.clearAll()

        if is_only_once:
            init_fen = fen if fen else ''
        else:
            init_fen = self.init_fen

        self.init_fen = init_fen
      
        self.boardView.from_fen(self.init_fen, clear = True)
        
        position = {
            'fen': self.init_fen,
            'index': 0,
            'move_side': self.boardView.get_move_color()
            }
        #print(position)        
        self.onPositionChanged(position, is_new = True)
 
    def onGameOver(self, win_side):
        
        if self.gameMode == GameMode.EndBook:
            if win_side == BLACK:
                msgbox = TimerMessageBox("挑战失败, 重新再来!")
            else:
                msgbox = TimerMessageBox("太棒了！ 挑战成功！！！")
            msgbox.exec()

            if win_side == RED:
                self.currGame['ok'] = True
                Globl.storage.updateEndBook(self.currGame)
                self.endBookView.updateCurrent(self.currGame)
                self.endBookView.nextGame()
            
        else:
            win_msg = '红方被将死!' if win_side == BLACK else '黑方被将死!'
            msgbox = TimerMessageBox(win_msg)
            msgbox.exec()

        #self.engine_working = False
        #self.boardView.setViewOnly(True)

    def onSelectEndGame(self, game):
        self.currGame = game
        self.book_moves = game['moves'].split(' ') if 'moves' in game else []
        
        #print(game)
        fen = game['fen']
        steps = fen_moves_to_step(fen, self.book_moves)
        #print(game["book_name"])
        
        self.initGame(fen)

        for fen_t, iccs in steps:
            Globl.fenCache[fen_t] = {'score': 99999, 'best_next': [iccs, ]}
            
        self.setWindowTitle(f'{self.app.APP_NAME_TEXT} - 杀法挑战 - {game["book_name"]} - {game["name"]}')
    
    
    def onBoardRightMouse(self, is_mouse_pressed):
        
        best_next = []    

        if is_mouse_pressed:

            fen = self.currPosition['fen']
            if (fen not in Globl.fenCache) or ('best_next' not in Globl.fenCache[fen]):
                return

            iccs_list = Globl.fenCache[fen]['best_next']
            best_next = [ iccs2pos(x)  for x in iccs_list]

        self.boardView.showBestMoveNext(best_next)    
        
    def onReviewByCloud(self):    

        if not self.reviewMode:
            self.reviewMode = 'Cloud'
            
            self.cloudModeBtn.setEnabled(False)
            self.engineModeBtn.setEnabled(False)
        
            #self.clearAllScore()
            self.reviewList = list(self.fenPosDict.keys())
            self.historyView.inner.reviewByCloudBtn.setText('停止复盘')
            self.onReviewGameStep()
        else:
            self.onReviewGameEnd(isCanceled=True)
         
    def onReviewByEngine(self):    

        if not self.reviewMode:
            self.reviewMode = 'Engine'
            
            self.cloudModeBtn.setEnabled(False)
            self.engineModeBtn.setEnabled(False)
            
            #self.clearAllScore()
            self.reviewList = list(self.fenPosDict.keys())
            self.engineView.analysisModeBox.setChecked(True)
            self.historyView.inner.reviewByEngineBtn.setText('停止复盘')
            self.onReviewGameStep()
        else:
            self.onReviewGameEnd(isCanceled=True)
            
    def onReviewGameStep(self):
        if len(self.reviewList) > 0:
            fen_step = self.reviewList.pop(0)
            
            if self.reviewMode == 'Cloud':
                self.cloud.startQuery(fen_step)
            elif self.reviewMode == 'Engine':
                posi = self.fenPosDict[fen_step]
                self.runEngine(posi)
        else:
            self.onReviewGameEnd()
            return
        
    def onReviewGameEnd(self, isCanceled=False):
        
        self.historyView.inner.reviewByCloudBtn.setText('云库复盘')
        self.historyView.inner.reviewByEngineBtn.setText('引擎复盘')
        
        self.reviewMode = None
        
        if not isCanceled:
            msgbox = TimerMessageBox("  复盘分析完成。  ", timeout=1)
            msgbox.exec()
        
        self.cloudModeBtn.setEnabled(True)
        self.engineModeBtn.setEnabled(True)
        
        self.engineView.analysisModeBox.setChecked(False)

    def saveGameToDB(self):
        Globl.storage.saveMovesToBook(self.positionList[1:])

    def loadBookGame(self, name, game):
        
        #self.cloudModeBtn.setChecked(False)

        fen = game.init_board.to_fen()
        
        self.initGame(fen, is_only_once = True)
        
        moves = game.dump_iccs_moves()
        if not moves:
            return
        for iccs in moves[0]:
            self.onMoveGo(iccs)

        self.setWindowTitle(f'{self.app.APP_NAME_TEXT} -- {name}')
        
        #self.cloudModeBtn.setChecked(save_search)

    def loadBookmark(self, name, position):
     
        self.cloudModeBtn.setChecked(False)

        fen = position['fen']        
        self.initGame(fen, is_only_once = True)
        #print(position)
        if 'moves' in position:
            moves = position['moves']
            if moves is not None:
                for it in moves:
                    iccs = it['iccs']    
                    self.onMoveGo(iccs)
            
        self.setWindowTitle(f'{self.app.APP_NAME_TEXT} -- {name}')

        self.cloudModeBtn.setChecked(save_search)

    #--------------------------------------------------------------------
    #引擎相关
    def detectRunEngine(self):
        new_working = False

        for it in self.bind_engines:
            if it is not None:
                new_working = True
                break
        if new_working: # and (new_working != self.engine_working):
            self.engine_working = True
            if self.currPosition is not None:
                self.runEngine(self.currPosition)

        self.engine_working = new_working
        
    def runEngine(self, position):
        
        self.engineView.clear()
        
        if not self.engine_working:
            return
        
        fen_engine = fen = position['fen']
        if fen == EMPTY_FEN:
            return 
                
        move_color = get_move_color(fen)
        
        need_go = True if self.bind_engines[3] else False
        if not need_go:
            if move_color == RED and (self.bind_engines[RED] is not None):
                need_go = True
        if not need_go:     
            if move_color == BLACK and (self.bind_engines[BLACK] is not None):
                need_go = True
        
        if not need_go:
            return

        if 'move' in position:
            fen_engine = position['move'].to_engine_fen()
        
        #print('engine_move_test', fen)
        ok = Globl.engineManager.go_from(0, fen_engine, fen)
        if not ok:
            QMessageBox.critical(self, f'{getTitle()}', f'象棋引擎命令出错，请确认该程序能正常运行。')
        
    def enginePlayColor(self, engine_id, side, yes):
        self.bind_engines[side] = engine_id if yes else None
        self.detectRunEngine()

    def setEngineAnalysisMode(self, yes):
        self.bind_engines[3] = 99 if yes else None
        self.detectRunEngine()

    def onConfigEngine(self):
        params = Globl.engineManager.get_config(0)

        dlg = EngineConfigDialog()
        if dlg.config(params):
            Globl.engineManager.update_config(0, params)

    def onRedBoxChanged(self, state):
        self.enginePlayColor(0, RED, Qt.CheckState(state) == Qt.Checked)
        
        if self.gameMode in [GameMode.EndBook, GameMode.Fight]:
            red_checked = self.engineView.eRedBox.isChecked()
            black_checked = self.engineView.eBlackBox.isChecked()
            
            if self.reviewMode:
                return
            
            if red_checked == black_checked:
                self.engineView.eBlackBox.setChecked(not red_checked)
            
    def onBlackBoxChanged(self, state):
        self.enginePlayColor(0, BLACK, Qt.CheckState(state) == Qt.Checked)

        if self.gameMode in [GameMode.EndBook, GameMode.Fight]:
            red_checked = self.engineView.eRedBox.isChecked()
            black_checked = self.engineView.eBlackBox.isChecked()
            
            if self.reviewMode:
                return
            
            if red_checked == black_checked:
                self.engineView.eRedBox.setChecked(not black_checked)
        
    def onAnalysisModeBoxChanged(self, state):
        self.setEngineAnalysisMode(Qt.CheckState(state) == Qt.Checked)
    
    def setAnalyzeMode(self, mode):
        
        if mode == self.analyzeMode:
            return

        self.analyzeMode = mode

        if self.analyzeMode == 'Engine':
            self.historyView.inner.reviewByEngineBtn.setEnabled(True)
            self.historyView.inner.reviewByCloudBtn.setEnabled(False)
        elif self.analyzeMode == 'Cloud':
            self.historyView.inner.reviewByEngineBtn.setEnabled(False)
            self.historyView.inner.reviewByCloudBtn.setEnabled(True)
        
        #self.clearAllScore()
                

    def onViewBranch(self, branch):
        dlg = PositionHistDialog()
        dlg.exec()

    #-----------------------------------------------------------------
    #
    def onSelectHistoryPosition(self, move_index):

        if (move_index < 0) or (move_index >= len(self.positionList)):
            return
        
        if self.reviewMode:
            return

        self.currPosition = self.positionList[move_index]
        is_last = True if move_index >= len(self.positionList) - 1 else False

        if is_last:
            self.historyMode = False
            self.boardView.setViewOnly(False)
        else:
            self.historyMode = True
            self.boardView.setViewOnly(True)
        
        best_show = []     
        fen = self.currPosition['fen']
        if fen in Globl.fenCache:
            fenInfo = Globl.fenCache[fen]
            if 'alter_best' in fenInfo:
                best_show = [iccs2pos(x) for x in fenInfo['alter_best']]     
       
        if 'move' in self.currPosition:
            move = self.currPosition['move']
            self.boardView.from_fen(move.board.to_fen())
            self.boardView.showMove(move.p_from, move.p_to, best_show)
        else:
             self.boardView.clearPickup()    
             
        self.onPositionChanged(self.currPosition, is_new = False)
        
    def deleteHistoryFollow(self, move_step):
        self.positionList = self.positionList[:move_step + 1]

        if len(self.positionList) > 0:
            self.currPosition = self.positionList[-1]
        else:
            self.currPosition = None

        self.historyMode = False
        self.boardView.setViewOnly(False)

    #------------------------------------------------------------------------------
    #None UI Events
    def clearAllScore(self):

        #清理分数但是保持fen链的完整性
        for fen in self.fenPosDict:
            if fen not in Globl.fenCache:
                continue 
            fenInfo = Globl.fenCache[fen]
            newInfo = {}
            if 'fen_prev' in fenInfo :
                newInfo['fen_prev'] = fenInfo['fen_prev']
            Globl.fenCache[fen] = newInfo

        for posi in self.positionList:
            self.historyView.inner.onUpdatePosition(posi)

    def localSearch(self, position):
        #暂时不用本地库
        #return

        fen = position['fen']
        qResult = self.openbook.getMoves(fen)
        if not qResult:
            return
        
        #self.updateFenCache(qResult)

        self.cloudDbView.updateCloudMoves(qResult['actions'])

    def onCloudQueryResult(self, qResult):
        
        if not qResult or not  self.positionList:
            return
        
        fen = qResult['fen']
        if (self.analyzeMode == 'Cloud') or (self.reviewMode == 'Cloud'):
            self.updateFenCache(qResult)
    
            posi = self.fenPosDict[fen]
            if posi == self.currPosition:
                self.cloudDbView.updateCloudMoves(qResult['actions'])
            
            if self.reviewMode == 'Cloud':
                self.onReviewGameStep()
        
    def onEngineBestMove(self, engine_id, fenInfo):
        
        fen = fenInfo['fen']
        #print("engine_best_move", fenInfo)
        if (self.analyzeMode == 'Engine') or (self.reviewMode == 'Engine'):
            self.updateFenCache(fenInfo)

        if self.reviewMode == 'Engine' :
            #print("engine_review_end", fen) 
            self.onReviewGameStep()
            return
            
        if not self.historyMode:

            move_color = self.board.get_move_color()
            if self.bind_engines[move_color] == engine_id:
                self.onMoveGo(fenInfo['iccs'])

    def onEngineMoveProbe(self, engine_id, fenInfo):
        
        #if (self.analyzeMode == 'Engine') or (self.reviewMode == 'Engine'):
        #    self.updateFenCache(fenInfo)
        
        self.engineView.onEngineMoveInfo(fenInfo)

    def updateFenCache(self, fenInfo):

        fen = fenInfo['fen']
        
        if fen not in Globl.fenCache:
            Globl.fenCache[fen] = {}   
        Globl.fenCache[fen].update(fenInfo)
        
        best_next = []

        #此局面的最优下个招法
        if 'actions' not in fenInfo:
            return

        actions = fenInfo['actions']
        for act in actions:
            if act['diff'] > -3:
                best_next.append(act['iccs'])
        if best_next:
            Globl.fenCache[fen]['best_next'] = best_next 

        #本着法的其他更好的招法    
        for act in actions:
            new_fen = act['new_fen']

            info = { 'score': act['score'], 'diff':act['diff'] }
            if (act['diff'] < -50) and best_next:
                info['alter_best'] = best_next

            if new_fen not in Globl.fenCache:
                Globl.fenCache[new_fen] = {'fen_prev': fen}   

            Globl.fenCache[new_fen].update(info)
                    
        if best_next:
            Globl.fenCache[fen]['best_next'] = best_next 

        # 如果这一步的fen不在上个步骤的预测走法里面，需要根据fen_prev的分数建立此步骤的alter_best   
        fenInfo = Globl.fenCache[fen]
        #print(1, fenInfo)
        if ('diff' not in fenInfo) and ('fen_prev' in fenInfo):
            fen_prev = fenInfo['fen_prev']
            if fen_prev in Globl.fenCache :
                prevInfo = Globl.fenCache[fen_prev]
                if 'score' in prevInfo:
                    diff = prevInfo['score'] - fenInfo['score']
                    if get_move_color(fen) == BLACK:
                        diff = -diff 
                    fenInfo['diff'] = diff
                    if (diff < -50) and ('best_next' in prevInfo):
                        fenInfo['alter_best'] = prevInfo['best_next']
        #print(2, fenInfo)
        posi = self.fenPosDict[fen]
        self.historyView.inner.onUpdatePosition(posi)
                    
    #-----------------------------------------------------------
    #走子核心逻辑
    def onMoveGo(self, move_iccs, score = None):

        if not self.board.is_valid_iccs_move(move_iccs):
            return
       
        #self.historyMode = True  #用historyMode保护在此期间引擎输出的move信息被忽略
        
        self.boardView.showIccsMove(move_iccs)
        
        #--------------------------------
        #尝试走棋
        move = self.board.move_iccs(move_iccs)
        if move is None:
            #不能走就返回
            #self.historyMode = False  #结束保护
            return
        #self.board在做了这个move动作后，棋子已经更新到新位置了
        #board是下个走子的position了
        self.board.next_turn()
        #--------------------------------
      
        #这一行必须有,否则引擎不能工作
        hist = [x['move'] for x in self.positionList[1:]]
        move.prepare_for_engine(move.board.move_player.opposite(), hist)

        #self.historyMode = False  #结束保护
        
        fen = self.board.to_fen()

        position = {
            'fen': fen,
            'fen_prev': move.board.to_fen(),
            'iccs':  move_iccs,
            'move': move,
            'index': len(self.positionList),
            'move_side': move.board.move_player.color
        }

        self.onPositionChanged(position, is_new = True)
        
        if move.is_checkmate:
            self.onGameOver(move.board.move_player)
              
    def onPositionChanged(self, position, is_new = True):   
        
        fen = position['fen']
        self.currPosition = position        
     
        if is_new:
            self.fenPosDict[fen] = position
            self.positionList.append(position)      
            
            #在fenCach中把招法连起来
            if fen not in Globl.fenCache:
                Globl.fenCache[fen] = {}
            
            if 'fen_prev' in position:    
                Globl.fenCache[fen].update({ 'fen_prev': position['fen_prev'] })
            
            #if score is not None:
            #    Globl.fenCache[fen].update({ 'score': score })
                
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

        self.engineView.clear()       
        self.boardView.from_fen(fen)    
        self.cloudDbView.clear()
        
        if self.gameMode == GameMode.EndBook:        
            pass
        else:
            self.moveDbView.onPositionChanged(position, is_new)
            if (self.analyzeMode == 'Cloud') or (self.reviewMode == 'Cloud'):
                self.cloud.startQuery(fen)
            else:
                self.localSearch(position)
                
        self.detectRunEngine()
        
    #------------------------------------------------------------------------------
    #UI Events

    def onBoardMove(self,  move_from,  move_to):
        move_iccs = pos2iccs(move_from, move_to)
        self.onMoveGo(move_iccs)
        
    def onBookMove(self, move_info):

        if self.historyMode:
            return
        
        self.onMoveGo(move_info['move']) #, move_info['score'])
            
    def onDoOpenBook(self):
        self.switchGameMode(GameMode.Free)

    def onDoEndBook(self):
        if (self.gameMode != GameMode.EndBook) and (len(self.positionList) > 1):
            steps = len(self.positionList) - 1
            ok = QMessageBox.question(self, getTitle(), f"当前棋谱已经走了 {steps} 步, 您确定要切换到其他模式并丢弃当前棋谱吗?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ok != QMessageBox.Yes:
                return
        self.switchGameMode(GameMode.EndBook)

    def onDoRobot(self):
        self.switchGameMode(GameMode.Fight)
        
    def onDoOnline(self):
        self.switchGameMode(GameMode.Online)
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
   
    def onShowBestMoveChanged(self, state):
        showBestMove = (Qt.CheckState(state) == Qt.Checked)
        self.boardView.setShowBestMove(showBestMove)

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
        #options |= QFileDialog.DontUseNativeDialog

        fileName, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "", "象棋通用格式文件(*.pgn);;象棋演播室文件(*.xqf);;所有文件(*.*)", options=options)

        if not fileName:
            return

        game = None
        fileName = Path(fileName)

        ext = fileName.suffix.lower()
        if ext == '.xqf':
            game = read_from_xqf(fileName)
        elif ext == '.pgn':
            game = read_from_pgn(fileName)
        
        if not game:
            return

        self.loadBookGame(fileName.name, game)

    def onSaveFile(self):
        
        if not self.positionList:
            return

        options = QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog

        fileName, _ = QFileDialog.getSaveFileName(
            self,
            "保存对局文件",
            "",
            "象棋通用格式文件(*.pgn)",
            options=options)
        
        if not fileName:
            return

        #ext = Path(fileName).suffix.lower()
        #print(ext)
        self.saveToFile(fileName)

    def saveToFile(self, file_name):

        board = ChessBoard(self.positionList[0]['fen'])
        game = Game(board)
        for pos in self.positionList[1:]:
            game.append_next_move(pos['move'])
        
        game.save_to(file_name)
    
    def onUseOpenBookFile(self):
        options = QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog

        fileName, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "", "勇芳格式开局库(*.yfk);;所有文件(*.*)", options=options)

        if not fileName:
            return

        fileName = Path(fileName)

        self.loadOpenBook(fileName)

    def onImportEndBook(self):
        options = QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(
            self,
            "打开杀局谱文件",
            "",
            "杀局谱文件(*.eglib);;All Files (*)",
            options=options)
        if not fileName:
            return

        lib_name = Path(fileName).stem
        if Globl.storage.isEndBookExist(lib_name):
            msgbox = TimerMessageBox(f"杀局谱[{lib_name}]系统中已经存在，不能重复导入。",
                                     timeout=2)
            msgbox.exec()
            return

        games = load_eglib(fileName)

        Globl.storage.saveEndBook(lib_name, games)
        
    #------------------------------------------------------------------------------
    #UI Base
    def createActions(self):

        self.openFileAct = QAction(self.style().standardIcon(
            QStyle.SP_FileDialogStart),
                                   "打开对局",
                                   self,
                                   statusTip="打开对局文件",
                                   triggered=self.onOpenFile)
        self.useOpenBookAct = QAction(self.style().standardIcon(
                                    QStyle.SP_FileDialogStart),
                                   "使用开局库",
                                   self,
                                   statusTip="选择开局库文件",
                                   triggered=self.onUseOpenBookFile)

        self.saveFileAct = QAction(self.style().standardIcon(
            QStyle.SP_DialogSaveButton),
                                   "保存对局",
                                   self,
                                   statusTip="保存对局文件",
                                   triggered=self.onSaveFile)

        self.doOpenBookAct = QAction(QIcon(':Images/openbook.png'),
                                     "自由练习",
                                     self,
                                     statusTip="自由练习",
                                     triggered=self.onDoOpenBook)

        self.doEndBookAct = QAction(QIcon(':Images/endbook.png'),
                                    "杀法挑战",
                                    self,
                                    statusTip="入局杀法挑战",
                                    triggered=self.onDoEndBook)

        self.doRobotAct = QAction(QIcon(':Images/robot.png'),
                                   "人机练习",
                                   self,
                                   statusTip="人机练习",
                                   triggered=self.onDoRobot)
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
        self.fileMenu.addAction(self.useOpenBookAct)
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
        #self.helpMenu.addAction(self.upgradeAct)
        self.helpMenu.addAction(self.aboutAct)

    def createToolBars(self):

        self.fileBar = self.addToolBar("File")
        self.fileBar.addAction(self.openFileAct)
        self.fileBar.addAction(self.saveFileAct)
        #self.fileBar.addAction(self.myGamesAct)
        self.fileBar.addAction(self.bookmarkAct)

        ag = QActionGroup(self)
        ag.setExclusive(True)
        ag.addAction(self.doOpenBookAct)
        ag.addAction(self.doEndBookAct)
        ag.addAction(self.doRobotAct)

        self.gameBar = self.addToolBar("Game")

        self.gameBar.addAction(self.doOpenBookAct)
        self.gameBar.addAction(self.doRobotAct)
        self.gameBar.addAction(self.doEndBookAct)
        
        self.gameBar.addAction(self.restartAct)
        self.gameBar.addAction(self.editBoardAct)
        #self.gameBar.addAction(self.searchBoardAct)

        self.flipBoardBox = QCheckBox()  #"翻转")
        self.flipBoardBox.setIcon(QIcon(':Images/up_down.png'))
        self.flipBoardBox.setToolTip('上下翻转')
        self.flipBoardBox.stateChanged.connect(self.onFlipBoardChanged)

        self.mirrorBoardBox = QCheckBox()  #"镜像")
        self.mirrorBoardBox.setIcon(QIcon(':Images/left_right.png'))
        self.mirrorBoardBox.setToolTip('左右镜像')
        self.mirrorBoardBox.stateChanged.connect(self.onMirrorBoardChanged)

        self.cloudModeBtn = QRadioButton()  #"云库")
        self.cloudModeBtn.setIcon(QIcon(':Images/cloud.png'))
        self.cloudModeBtn.setToolTip('云库优先模式')
        self.cloudModeBtn.toggled.connect(lambda: self.setAnalyzeMode("Cloud"))

        self.engineModeBtn = QRadioButton()  #"引擎")
        self.engineModeBtn.setIcon(QIcon(':Images/engine.png'))
        self.engineModeBtn.setToolTip('引擎优先模式')
        self.engineModeBtn.toggled.connect(lambda: self.setAnalyzeMode("Engine"))

        #self.cloudModeBtn.setChecked(self.isSearchCloud)
        
        self.modeBtnGroup = QButtonGroup(self)
        self.modeBtnGroup.addButton(self.cloudModeBtn, 1)      # ID 1
        self.modeBtnGroup.addButton(self.engineModeBtn, 2)      # ID 2
        #self.modeBtnGroup.buttonClicked.connect(self.onAnalysisModeChanged)
        #self.cloudModeBtn.setToolTip('实时搜索云库')
        #self.cloudModeBtn.stateChanged.connect(self.onSearchCloudChanged)
        
        self.showBestBox = QCheckBox()  #"最佳提示")
        self.showBestBox.setIcon(QIcon(':Images/info.png'))
        self.showBestBox.setChecked(True)
        self.showBestBox.setToolTip('提示最佳走法')
        self.showBestBox.stateChanged.connect(self.onShowBestMoveChanged)
    
        self.showBar = self.addToolBar("Show")
        self.showBar.addWidget(self.flipBoardBox)
        self.showBar.addWidget(self.mirrorBoardBox)
        self.showBar.addSeparator()
        self.showBar.addWidget(self.cloudModeBtn)
        self.showBar.addWidget(self.engineModeBtn)
        
        self.showBar.addSeparator()
        self.showBar.addWidget(self.showBestBox)
        
        self.sysBar = self.addToolBar("System")
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.sysBar.addWidget(spacer)
        self.sysBar.addAction(self.exitAct)

        self.statusBar().showMessage("Ready")

    def onShowMoveSound(self, yes):
        self.soundVolume = 30 if yes else 0

  
    def center(self):
        screen = QDesktopWidget().screenGeometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) // 2,
                  (screen.height() - size.height()) // 2)

    def closeEvent(self, event):
        self.writeSettings()
        Globl.engineManager.stop()
        Globl.storage.close()
        self.saveMemoState()

    def loadMemoState(self):
        pass

    def saveMemoState(self):
        pass

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
        
        self.game_mode_saved = self.settings.value("gameMode", GameMode.Free)
        
    def writeSettings(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("historyView", self.historyView.isVisible())
        self.settings.setValue("engineView", self.engineView.isVisible())
        self.settings.setValue("moveDBView", self.moveDbView.isVisible())
        self.settings.setValue("cloudDBView", self.moveDbView.isVisible())
        self.settings.setValue("soundVolume", self.soundVolume)
        self.settings.setValue("gameMode", self.gameMode)
        
    def about(self):
        from .Version import release_version
        
        QMessageBox.about(
            self, f"关于 {self.app.APP_NAME}",
            f"{self.app.APP_NAME_TEXT} Version {release_version}\n个人棋谱管家.\n 云库支持：https://www.chessdb.cn/\n 引擎支持：皮卡鱼(https://pikafish.org/)\n\n 联系作者：1053386709@qq.com\n QQ 进群：101947824\n"
        )

#-----------------------------------------------------#
