# -*- coding: utf-8 -*-

import os
import time
import logging
from pathlib import Path
import ctypes
import traceback
import platform
import yaml
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
        
        self.isSearchCloud = True
        self.isShowBestMove = True

        Globl.engineManager = EngineManager(self)
        self.initGameDB()
        self.board = ChessBoard()
        
        self.boardView = ChessBoardWidget(self.board)
        self.setCentralWidget(self.boardView)
        self.boardView.try_move_signal.connect(self.onBoardMove)

        self.historyView = DockHistoryWidget(self)
        self.historyView.inner.positionSelSignal.connect(
            self.onSelectHistoryPosition)
        self.historyView.inner.reviewByCloudBtn.clicked.connect(self.onReviewByCloud)
        self.historyView.inner.reviewByEngineBtn.clicked.connect(self.onReviewByEngine)
        self.historyView.inner.reviewByEngineBtn.setEnabled(False)

        self.endBookView = EndBookWidget(self)
        self.endBookView.setVisible(False)
        self.endBookView.end_game_select_signal.connect(
            self.onSelectEndGame)

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

        self.gameMode = ''
        self.clearAll()
        
        self.cloud = CloudDB(self)
        self.cloud.query_result_signal.connect(self.onCloudQueryResult)
        
        Globl.engineManager.start()
        
        self.switchGameMode(self.game_mode_saved)

        #splash.finish()

    #-----------------------------------------------------------------------
    #初始化
    def clearAll(self):
        self.base_fen = None
        self.positionList = []
        self.currPosition = None
        self.historyMode = False
        self.reviewMode = None

        self.historyView.inner.clear()
        self.moveDbView.clear()
        self.engineView.clear()
        self.boardView.set_view_only(False)

    def initEngine(self):
        engine_conf_file = Path('Engine', 'engine.conf')
        if not engine_conf_file.is_file():
            QMessageBox.critical(self, f'{getTitle()}', f'象棋引擎配置文件[{engine_conf_file}]不存在，请确保该文件存在并配置正确.')
            return False    
        with open(engine_conf_file) as f:
            try:
                engine_conf = yaml.safe_load(f)
            except Exception as e:
                QMessageBox.critical(self, f'{getTitle()}', f'打开象棋引擎配置文件[{engine_conf_file}]出错：{e}')
                return False
        if ('engine' not in engine_conf) or  ('run' not in engine_conf['engine']):
            QMessageBox.critical(self, f'{getTitle()}', f'象棋引擎配置文件格式不正确.')
            return False     
        engine_path = Path('Engine', engine_conf['engine']['run'])
        ok = Globl.engineManager.load_engine(engine_path)
        if not ok:
            QMessageBox.critical(self, f'{getTitle()}', f'加载象棋引擎[{engine_path.absolute()}]出错，请确认该程序能在您的电脑上正确运行。')
        return ok
        
    def initGameDB(self):

        gamePath = Path('Game')
        gamePath.mkdir(exist_ok=True)
        
        Globl.storage = DataStore()
        Globl.storage.open(Path(gamePath, 'Evolution.jdb'))
        self.openbook = OpenBook()
        self.openbook.loadBookFile(Path(gamePath, 'openbook.db'))
        
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
    def switchGameMode(self, gameMode):

        #模式未变
        if self.gameMode == gameMode:
            return
        self.lastGameMode = self.gameMode    
        self.gameMode = gameMode

        if self.gameMode == 'end_book':
            self.myGamesAct.setEnabled(False)
            self.bookmarkAct.setEnabled(False)
            self.endBookView.show()
            self.bookmarkView.hide()
            #self.myGameView.hide()
            self.moveDbView.clear()
            self.moveDbView.hide()
            self.cloudDbView.hide()
            
            self.engineView.eRedBox.setChecked(False)
            self.engineView.eBlackBox.setChecked(True)
            self.engineView.analysisModeBox.setChecked(False)
            self.searchCloudBox.setChecked(False)
            #self.initGame(EMPTY_FEN)
            self.endBookView.nextGame()
            
        elif self.gameMode == 'open_book':
            self.setWindowTitle(f'{self.app.APP_NAME_TEXT} - 自由练习')
            self.myGamesAct.setEnabled(True)
            self.bookmarkAct.setEnabled(True)
            self.endBookView.hide()
            self.moveDbView.show()
            self.cloudDbView.show()
            
            self.engineView.eRedBox.setChecked(False)
            self.engineView.eBlackBox.setChecked(False)
            self.engineView.analysisModeBox.setChecked(False)
            self.searchCloudBox.setChecked(True)
        
            if self.lastGameMode not in ['fight_robot', ]:        
                self.initGame(FULL_INIT_FEN)
        
        elif self.gameMode == 'fight_robot':
            self.setWindowTitle(f'{self.app.APP_NAME_TEXT} - 人机练习')
            self.myGamesAct.setEnabled(True)
            self.bookmarkAct.setEnabled(True)
            self.endBookView.hide()
            self.moveDbView.hide()
            self.cloudDbView.hide()
            #self.bookmarkView.show()
            
            self.engineView.eRedBox.setChecked(False)
            self.engineView.eBlackBox.setChecked(True)
            self.engineView.analysisModeBox.setChecked(False)
            self.searchCloudBox.setChecked(False)
            
            if self.lastGameMode in ['', 'end_book']:
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
        
        if self.gameMode == 'end_book':
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
        #self.boardView.set_view_only(True)

    def onSelectEndGame(self, game):
        self.currGame = game
        self.book_moves = game['moves'] if 'moves' in game else None
        self.initGame(game['fen'])
        self.setWindowTitle(f'{self.app.APP_NAME_TEXT} - 残局挑战 - {game["book_name"]} - {game["name"]}')
    
    def clearAllScore(self):

        for posi in self.positionList:
            posi['score'] = ''
            if 'diff' in posi:
                del posi['diff']
                
            self.historyView.inner.onUpdatePosition(posi)
                
    def onReviewByCloud(self):    
        
        if len(self.positionList) <= 1:
            return

        if not self.reviewMode:
            self.reviewMode = 'Cloud'
            self.clearAllScore()
            self.engineView.eRedBox.setChecked(False)
            self.engineView.eBlackBox.setChecked(False)
            self.engineView.analysisModeBox.setChecked(False)            
            self.historyView.inner.reviewByCloudBtn.setText('停止复盘')
            self.historyView.inner.reviewByEngineBtn.setEnabled(False)
            self.historyView.inner.selectIndex(0)
        else:
            self.onReviewGameEnd(isCanceled=True)
         
    def onReviewByEngine(self):    
        
        if len(self.positionList) <= 1:
            return

        if not self.reviewMode:
            self.reviewMode = 'Engine'
            self.clearAllScore()
            self.engineView.eRedBox.setChecked(False)
            self.engineView.eBlackBox.setChecked(False)
            self.engineView.analysisModeBox.setChecked(True)
            #self.historyView.inner.reviewByEngineBtn.setText('停止复盘')
            #self.historyView.inner.reviewByCloudBtn.setEnabled(False)
            self.historyView.inner.selectIndex(0)
        else:
            self.onReviewGameEnd(isCanceled=True)
            
    def onReviewGameStep(self):
        sel_index = self.historyView.inner.selectionIndex + 1
        print('onReviewGameStep', sel_index)
        if sel_index >= len(self.positionList):  #已到最后一步
            self.onReviewGameEnd()
            return
        self.historyView.inner.selectIndex(sel_index)

    def onReviewGameEnd(self, isCanceled=False):
        self.reviewMode = None
        
        self.historyView.inner.reviewByCloudBtn.setText('云库复盘')
        self.historyView.inner.reviewByCloudBtn.setEnabled(True)
        #self.historyView.inner.reviewByEngineBtn.setText('引擎复盘')
        #self.historyView.inner.reviewByEngineBtn.setEnabled(True)
        
        if not isCanceled:
            msgbox = TimerMessageBox("  复盘分析完成。  ", timeout=1)
            msgbox.exec()
        
        self.engineView.analysisModeBox.setChecked(False)

    def saveGameToDB(self):
        Globl.storage.saveMovesToBook(self.positionList[1:])

    def loadBookGame(self, name, game):
        
        save_search = self.isSearchCloud
        self.searchCloudBox.setChecked(False)

        fen = game.init_board.to_fen()
        
        self.initGame(fen, is_only_once = True)
        
        moves = game.dump_iccs_moves()
        if not moves:
            return
        for iccs in moves[0]:
            self.onMoveGo(iccs)

        self.setWindowTitle(f'{self.app.APP_NAME_TEXT} -- {name}')
        
        self.searchCloudBox.setChecked(save_search)

    def loadBookmark(self, name, position):
     
        save_search = self.isSearchCloud
        self.searchCloudBox.setChecked(False)

        fen = position['fen']        
        self.initGame(fen, is_only_once = True)
        #print(position)
        if 'moves' in position:
            moves = position['moves']
            if moves is not None:
                for it in moves:
                    iccs = it['move']    
                    self.onMoveGo(iccs)
            
        self.setWindowTitle(f'{self.app.APP_NAME_TEXT} -- {name}')

        self.searchCloudBox.setChecked(save_search)

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
            self.runEngine()

        self.engine_working = new_working
        
    def runEngine(self):
        
        self.engineView.clear()
        
        if not self.engine_working:
            return
        
        if self.currPosition is None:
            return
        
        move_color = self.board.get_move_color()
        
        need_go = True if self.bind_engines[3] else False
        if not need_go:
            if move_color == RED and (self.bind_engines[RED] is not None):
                need_go = True
        if not need_go:     
            if move_color == BLACK and (self.bind_engines[BLACK] is not None):
                need_go = True
        
        #print('need_go', need_go)
        
        if not need_go:
            return

        fen_engine = fen = self.currPosition['fen']
        
        if fen == EMPTY_FEN:
            return 

        if 'move' in self.currPosition:
            fen_engine = self.currPosition['move'].to_engine_fen()
        
        ok = Globl.engineManager.go_from(0, fen_engine, fen)
        if not ok:
            QMessageBox.critical(self, f'{getTitle()}', f'象棋引擎命令出错，请确认该程序能正常运行。')
        
    def engine_play(self, engine_id, side, yes):
        self.bind_engines[side] = engine_id if yes else None
        self.detectRunEngine()

    def engine_analyze(self, yes):
        self.bind_engines[3] = 99 if yes else None
        self.detectRunEngine()

    def onConfigEngine(self):
        params = Globl.engineManager.get_config(0)

        dlg = EngineConfigDialog()
        if dlg.config(params):
            Globl.engineManager.update_config(0, params)

    def onRedBoxChanged(self, state):
        self.engine_play(0, RED, Qt.CheckState(state) == Qt.Checked)
        
        if self.gameMode in ['end_book', 'fight_robot']:
            red_checked = self.engineView.eRedBox.isChecked()
            black_checked = self.engineView.eBlackBox.isChecked()
            if red_checked == black_checked:
                self.engineView.eBlackBox.setChecked(not red_checked)
            
    def onBlackBoxChanged(self, state):
        self.engine_play(0, BLACK, Qt.CheckState(state) == Qt.Checked)

        if self.gameMode in ['end_book', 'fight_robot']:
            red_checked = self.engineView.eRedBox.isChecked()
            black_checked = self.engineView.eBlackBox.isChecked()
            if red_checked == black_checked:
                self.engineView.eRedBox.setChecked(not black_checked)
        
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
            best_show = []
            if 'best_show' in  self.currPosition:
                best_show = self.currPosition['best_show']
            self.boardView.from_fen(move.board.to_fen())
            self.boardView.show_move(move.p_from, move.p_to, best_show)
        else:
             self.boardView.clear_pickup()    
             
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
    def updateScore(self, score):
        pass


    def onEngineMoveProbe(self, engine_id, move_info):
        self.engineView.onEngineMoveInfo(move_info)


    def onEngineBestMove(self, engine_id, move_info):
        
        #Globl.fenCache[fen] = {'score': score_best, 'actions': cloud_moves}
        #print(move_info)
        
        if not self.board.is_valid_iccs_move(move_info['move']):
            return
            
        move_color = self.board.get_move_color()
        
        if (self.reviewMode == 'Engine') and self.currPosition['index'] > 0:
            if 'score' not in move_info:
                #print("score not found:", move_info)
                pass
            else:
                score = move_info['score']
                self.currPosition[
                    'score'] = score if move_color == RED else -score
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

        self.onMoveGo( move_info['move'], move_info['score'])
    
       
    def onCloudQueryResult(self, qResult):
        
        if (not qResult) or len(qResult['actions']) == 0:
            return
            
        fen = qResult['fen'] 
        
        if len(self.positionList) == 0:
            return
        
        for posi in reversed(self.positionList):
            if posi['fen'] == fen:
                break

        if posi['fen'] == fen:
            #融合本地跟云库结果    
            #l_moves = self.openbook.getMoves(fen)
            
            score_best = qResult['score']
            move_color = get_move_color(fen)
            actions = qResult['actions']
            self.cloudDbView.updateCloudMoves(actions)
            
            posi['score'] = qResult['score']      
            
            if fen in Globl.fenCache:
                fenMemo = Globl.fenCache[fen] 
                if 'diff' in fenMemo:
                    #print(fenMemo['diff'])
                    posi['diff'] = fenMemo['diff']
                elif 'score_base' in posi:
                    posi['diff'] = posi['score'] - posi['score_base'] 
                    if move_color == RED:
                        posi['diff'] = -posi['diff']
                    fenMemo.update({'diff': posi['diff']})
                        
            #TODO: 优化成多个候选步骤
            if ('diff' in posi) and (posi['diff'] < -30) and (len(actions) > 0) and ('fen_prev' in posi):
                prevMemo = Globl.fenCache[posi['fen_prev']]
                if 'best_moves' in prevMemo:
                    best_moves = prevMemo['best_moves']      
                    iccs = best_moves[0]
                    posi['best_show'] = [(*iccs2pos(iccs), move_color, iccs)]
        
            self.historyView.inner.onUpdatePosition(posi)

        if self.reviewMode == 'Cloud':
            self.onReviewGameStep()

    #-----------------------------------------------------------
    #走子核心逻辑
    def onPositionChanged(self, position, is_new = True):   
        
        self.currPosition = position        
        fen = position['fen']
        
        if fen in Globl.fenCache:
            memo = Globl.fenCache[fen]
            #print("memo", memo)
            position['score'] = memo['score'] 
            if 'diff' in memo:
                position['diff'] = memo['diff']
        else:
            if 'fen_prev' in position and position['fen_prev'] in Globl.fenCache:
                fenMemo = Globl.fenCache[position['fen_prev']] 
                position['score_base'] = fenMemo['score']
        
        if is_new:
            '''    
            if fen in Globl.fenCache:
                memo = Globl.fenCache[fen]
                #print("memo", memo)
                position['score'] = memo['score'] 
                if 'diff' in memo:
                    position['diff'] = memo['diff']
            else:
                if 'fen_prev' in position and position['fen_prev'] in Globl.fenCache:
                    fenMemo = Globl.fenCache[position['fen_prev']] 
                    position['score_base'] = fenMemo['score']
            '''    
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

        self.engineView.clear()       
        self.boardView.from_fen(fen)    
        self.cloudDbView.clear()
        
        if self.gameMode == 'end_book':        
            pass
        else:
            self.moveDbView.onPositionChanged(position, is_new)
            if self.isSearchCloud or (self.reviewMode == 'Cloud'):
                self.cloud.startQuery(fen)
            
        self.detectRunEngine()
        
    def onBoardMove(self,  move_from,  move_to):
        move_iccs = pos2iccs(move_from, move_to)
        self.onMoveGo(move_iccs)
        
    def onMoveGo(self,  move_iccs, score = None):

        self.historyMode = True  #用historyMode保护在此期间引擎输出的move信息被忽略
        
        self.boardView.show_move_iccs(move_iccs)
        
        #--------------------------------
        move = self.board.move_iccs(move_iccs)
        if move is None:
            #不能走就算了
            self.historyMode = False  #结束保护
            return
        #self.board在做了这个move动作后，棋子已经更新到新位置了
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
            'move_iccs':  move_iccs,
            'move': move,
            'score': score,
            'index': len(self.positionList),
            'move_side': move.board.move_player.color
        }
        
        self.onPositionChanged(position)
        #print(move.is_checking, move.is_checkmate)
        if move.is_checkmate:
            self.onGameOver(move.board.move_player)
      
    #------------------------------------------------------------------------------
    #UI Events
    def onDoOpenBook(self):
        self.switchGameMode("open_book")

    def onDoEndBook(self):
        self.switchGameMode("end_book")

    def onDoRobot(self):
        self.switchGameMode("fight_robot")
        
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
    
    def onSearchCloudChanged(self, state):
        self.isSearchCloud = (Qt.CheckState(state) == Qt.Checked)

    def onShowBestMoveChanged(self, state):
        self.isShowBestMove = (Qt.CheckState(state) == Qt.Checked)
        self.boardView.is_show_best_move = self.isShowBestMove

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
        if not game:
            return

        self.loadBookGame(fileName.name, game)

    def onSaveFile(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog

        fileName, _ = QFileDialog.getSaveFileName(
            self,
            "保存对局文件",
            "",
            "PGN文件(*.pgn)",
            options=options)

        if not fileName:
            return

        ext = Path(fileName).suffix.lower()
        #print(ext)

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
        if Globl.storage.isEndBookExist(lib_name):
            msgbox = TimerMessageBox(f"残局库[{lib_name}]系统中已经存在，不能重复导入。",
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
                                    "残局挑战",
                                    self,
                                    statusTip="残局挑战",
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

        self.gameBar.addAction(self.doEndBookAct)
        self.gameBar.addAction(self.doOpenBookAct)
        self.gameBar.addAction(self.doRobotAct)
        
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

        self.searchCloudBox = QCheckBox()  #"云库")
        self.searchCloudBox.setIcon(QIcon(':Images/cloud_search.png'))
        self.searchCloudBox.setChecked(self.isSearchCloud)
        self.searchCloudBox.setToolTip('实时搜索云库')
        self.searchCloudBox.stateChanged.connect(self.onSearchCloudChanged)
        
        self.infoBox = QCheckBox()  #"最佳提示")
        self.infoBox.setIcon(QIcon(':Images/info.png'))
        self.infoBox.setChecked(self.isShowBestMove)
        self.infoBox.setToolTip('提示最佳走法')
        self.infoBox.stateChanged.connect(self.onShowBestMoveChanged)
    
        self.showBar = self.addToolBar("Show")
        self.showBar.addWidget(self.flipBoardBox)
        self.showBar.addWidget(self.mirrorBoardBox)
        self.showBar.addSeparator()
        self.showBar.addWidget(self.searchCloudBox)
        
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
        
        self.game_mode_saved = self.settings.value("gameMode", 'open_book')
        
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
