# -*- coding: utf-8 -*-

import sys
import time
import logging
import ctypes
import traceback
import platform
import threading
import configparser
from enum import Enum, auto
from pathlib import Path
from collections import OrderedDict

#from PySide6 import 
from PySide6.QtCore import Qt, Signal, QByteArray, QSettings, QUrl
from PySide6.QtGui import QActionGroup, QIcon, QAction
from PySide6.QtWidgets import QMainWindow, QStyle, QSizePolicy, QMessageBox, QWidget, QCheckBox, QRadioButton, \
                            QFileDialog, QButtonGroup
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

import cchess
from cchess import ChessBoard, Game, iccs2pos, pos2iccs, read_from_pgn, read_from_xqf, get_move_color, fench_to_text

from .Version import release_version
from .Resource import qt_resource_data
from .Manager import EngineManager
from .Storage import DataStore, CloudDB, OpenBookYfk
from .Utils import GameMode, TimerMessageBox, getTitle, loadEglib, getStepsFromFenMoves
from .BoardWidgets import ChessBoardWidget
from .Widgets import PositionEditDialog, PositionHistDialog, ChessEngineWidget, EngineConfigDialog, BookmarkWidget, \
                    CloudDbWidget, MoveDbWidget, EndBookWidget, DockHistoryWidget

        
#from .Online import OnlineDialog

from . import Globl

#-----------------------------------------------------#
GameTitle = {
    None : '',
    GameMode.Free: '自由练棋', 
    GameMode.Fight: '人机对战', 
    GameMode.EndGame: '杀局练习', 
    GameMode.Online: '连线分析',          
}

#-----------------------------------------------------#
class ActionType(Enum):
    MOVE = auto()
    CAPTRUE = auto()
    CHECKING = auto()
    MATE = auto()
    
#-----------------------------------------------------#
class ReviewMode(Enum):
    ByCloud = auto()
    ByEngine = auto()
    
#-----------------------------------------------------#
class QueryMode(Enum):
    CloudFirst = auto()
    EngineFirst = auto()

#-----------------------------------------------------#
class MainWindow(QMainWindow):
    initGameSignal = Signal(str)
    newBoardSignal = Signal()
    moveBeginSignal = Signal()
    moveEndSignal = Signal()
    newPositionSignal = Signal()

    def __init__(self):
        super().__init__()

        self.setAttribute(Qt.WA_DeleteOnClose)

        #self.app = app

        self.setWindowIcon(QIcon(':Images/app.ico'))
                
        if platform.system() == "Windows":
            #在Windows状态栏上正确显示图标
            myappid = 'mycompany.myproduct.subproduct.version'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                myappid)
        
        gamePath = Path('Game')
        gamePath.mkdir(exist_ok=True)
        
        Globl.storage = DataStore()
        Globl.storage.open(Path(gamePath, 'Evolution.jdb'))

        Globl.engineManager = EngineManager(self, id = 1)
        
        self.board = ChessBoard()
        
        self.boardView = ChessBoardWidget(self.board)
        self.setCentralWidget(self.boardView)
        self.boardView.tryMoveSignal.connect(self.onTryBoardMove)
        self.boardView.rightMouseSignal.connect(self.onBoardRightMouse)

        self.historyView = DockHistoryWidget(self)
        self.historyView.inner.positionSelSignal.connect(
            self.onSelectHistoryPosition)
        self.historyView.inner.reviewByCloudBtn.clicked.connect(self.onReviewByCloud)
        self.historyView.inner.reviewByEngineBtn.clicked.connect(self.onReviewByEngine)
        #self.historyView.inner.reviewByEngineBtn.setEnabled(False)

        self.endBookView = EndBookWidget(self)
        self.endBookView.setVisible(False)
        self.endBookView.selectEndGameSignal.connect(self.onSelectEndGame)

        self.moveDbView = MoveDbWidget(self)
        self.moveDbView.selectMoveSignal.connect(self.onTryBookMove)
        self.cloudDbView = CloudDbWidget(self)
        self.cloudDbView.selectMoveSignal.connect(self.onTryBookMove)
        
        self.bookmarkView = BookmarkWidget(self)
        self.bookmarkView.setVisible(False)
        
        self.engineView = ChessEngineWidget(self, Globl.engineManager)
        
        self.addDockWidget(Qt.LeftDockWidgetArea, self.moveDbView)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.cloudDbView)
        #self.addDockWidget(Qt.RightDockWidgetArea, self.gameReviewView)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.endBookView)
        self.addDockWidget(Qt.RightDockWidgetArea, self.historyView)
        self.addDockWidget(Qt.RightDockWidgetArea, self.bookmarkView)
        #self.addDockWidget(Qt.LeftDockWidgetArea, self.myGameView)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.engineView)
        
        self.isRunEngine = False
        self.engineRunColor = [0, 0, 0]
        self.initEngine()
        
        Globl.engineManager.readySignal.connect(self.onEngineReady)
        Globl.engineManager.moveBestSignal.connect(self.onTryEngineMove)
        Globl.engineManager.moveInfoSignal.connect(self.onEngineMoveInfo)
        #Globl.engineManager.checkmate_signal.connect(self.onEngineCheckmate)

        self.initSound()
        self.createActions()
        self.createMenus()
        self.createToolBars()

        self.gameMode = None
        self.queryMode = None
        self.reviewMode = None
        self.lastOpenFolder = ''
        self.hasNewMove = False

        self.clearAll()
        
        self.openBook = OpenBookYfk()
        
        self.readSettingsBeforeGameInit()
        
        if self.openBookFile.is_file():
            if not self.openBook.loadBookFile(self.openBookFile):
                msgbox = TimerMessageBox(f"打开开局库文件【{self.openBookFile}】出错, 请重新配置开局库。")
                msgbox.exec()
        else:
            msgbox = TimerMessageBox(f"开局库文件【{self.openBookFile}】不存在, 请重新配置开局库。")
            msgbox.exec()

        Globl.engineManager.start()
        self.cloudQuery = CloudDB(self)
        self.cloudQuery.query_result_signal.connect(self.onCloudQueryResult)
        
        self.switchGameMode(self.savedGameMode)
        
        self.readSettingsAfterGameInit()

        #splash.finish()

    #-----------------------------------------------------------------------
    #初始化
    def clearAll(self):
        self.fenPosDict = OrderedDict()
        self.positionList = []
        self.currPosition = None
        self.isHistoryMode = False
        self.reviewMode = None

        #防止同一个局面下多次走子重入
        self.isInMoveMode = False

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
        
        ok = Globl.engineManager.loadEngine(engine_exec, engine_type)
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
        
        ok = Globl.engineManager.loadEngine(engine_exec, engine_type)
        if not ok:
            QMessageBox.critical(self, f'{getTitle()}', f'加载象棋引擎[{engine_exec.absolute()}]出错，请确认该程序能在您的电脑上正确运行。')
        
        return ok
        '''

    def loadOpenBook(self, file_name):
        if self.openBook.loadBookFile(file_name):
            self.openBookFile = Path(file_name)
        
    #-----------------------------------------------------------------------
    #声音播放
    def initSound(self):
        self.soundVolume = 0
        self.audioOutput = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audioOutput)
        self.player.errorOccurred.connect(self.onPlayError)

    def playSound(self, s_type, quickMode = False):
        
        if quickMode:
            return

        if self.soundVolume > 0:
            self.player.setSource(QUrl.fromLocalFile(f'Sound/{s_type}.wav'))
            self.audioOutput.setVolume(100) #self.soundVolume)
            self.player.setPosition(0)
            self.player.play()

    def onPlayError(self, error, error_string):
        logging.error(f'Sound PlayError: {error_string}')

    #-----------------------------------------------------------------------
    #基础信息
    def updateTitle(self, subText = ''):
       
        title = f'{Globl.app.APP_NAME_TEXT} - {GameTitle[self.gameMode]}'
        if subText:
            title = f'{title} - {subText}'

        self.setWindowTitle(title)
        
    def getGameIccsMoves(self):
        moves = [{'iccs': it['iccs']}for it in self.positionList[1:]]
        return (self.positionList[0]['fen'], moves)

    def saveGameToDB(self):
        Globl.storage.saveMovesToBook(self.positionList[1:])
        self.hasNewMove = False

    #-----------------------------------------------------------------------
    #Game 相关
    def switchGameMode(self, gameMode):

        #模式未变
        if self.gameMode == gameMode:
            if (self.gameMode == GameMode.Free) and self.hasNewMove:
                steps = len(self.positionList) - 1
                if self.getConfirm(f"当前棋谱已经走了 {steps} 步, 您确定要从新开始吗?"):
                    self.initGame(cchess.FULL_INIT_FEN)
            return
        
        self.lastGameMode = self.gameMode    
        self.gameMode = gameMode
        self.updateTitle()
        self.engineView.onSwitchGameMode(gameMode)

        if self.gameMode == GameMode.Free:
            self.myGamesAct.setEnabled(True)
            self.bookmarkAct.setEnabled(True)
            self.endBookView.hide()
            self.moveDbView.show()
            self.cloudDbView.show()
            self.showScoreBox.setChecked(True)
            
            self.cloudModeBtn.setEnabled(True)
            self.engineModeBtn.setEnabled(True)
            
            self.showBestBox.setEnabled(True)
            self.showBestBox.setChecked(True)
            self.showScoreBox.setChecked(True)
            
            self.openFileAct.setEnabled(True)
            self.editBoardAct.setEnabled(True)
    
            if self.lastGameMode not in [GameMode.Fight, ]:        
                self.initGame(cchess.FULL_INIT_FEN)
        
        elif self.gameMode == GameMode.Fight:
            self.myGamesAct.setEnabled(True)
            self.bookmarkAct.setEnabled(False)
            self.bookmarkView.hide()
            self.endBookView.hide()
            self.moveDbView.hide()
            self.cloudDbView.hide()
            
            self.showScoreBox.setChecked(False)

            self.cloudModeBtn.setEnabled(True)
            #self.cloudModeBtn.setChecked(False)
            self.engineModeBtn.setEnabled(True)
            #self.engineModeBtn.setChecked(True)
            
            self.showBestBox.setEnabled(True)
            self.showBestBox.setChecked(False)
        
            self.openFileAct.setEnabled(False)
            self.editBoardAct.setEnabled(True)
        
            if self.lastGameMode in [None, GameMode.EndGame]:
                self.initGame(cchess.FULL_INIT_FEN)
        
        elif self.gameMode == GameMode.EndGame:
            self.myGamesAct.setEnabled(False)
            self.bookmarkAct.setEnabled(False)
            self.endBookView.show()
            self.bookmarkView.hide()
            #self.myGameView.hide()
            self.moveDbView.clear()
            self.moveDbView.hide()
            self.cloudDbView.hide()
            
            self.showScoreBox.setChecked(False)

            self.openFileAct.setEnabled(False)
            self.editBoardAct.setEnabled(False)
            
            self.cloudModeBtn.setEnabled(False)
            #self.cloudModeBtn.setChecked(False)
            self.engineModeBtn.setEnabled(False)
            self.engineModeBtn.setChecked(True)
            
            self.showBestBox.setEnabled(False)
            self.showBestBox.setChecked(False)

            self.endBookView.nextGame()
        
        
    def onGameOver(self, win_side):
        
        if self.gameMode == GameMode.EndGame:
            if win_side == cchess.BLACK:
                msgbox = TimerMessageBox("挑战失败, 重新再来!")
            else:
                msgbox = TimerMessageBox("太棒了！ 挑战成功！！！")
            msgbox.exec()

            if win_side == cchess.RED:
                self.currGame['ok'] = True
                Globl.storage.updateEndBook(self.currGame)
                self.endBookView.updateCurrent(self.currGame)
                self.endBookView.nextGame()
            
        else:
            win_msg = '红方被将死!' if win_side == cchess.BLACK else '黑方被将死!'
            msgbox = TimerMessageBox(win_msg)
            msgbox.exec()

        #self.isRunEngine = False
        #self.boardView.setViewOnly(True)

    #-----------------------------------------------------------
    #走子核心逻辑
    def initGame(self, fen):
        self.init_fen = fen

        self.moveLock = threading.RLock()
        
        with self.moveLock:
            Globl.engineManager.stopThinking()
            self.clearAll()
            self.boardView.from_fen(self.init_fen, clear = True)
            position = {
                'fen': self.init_fen,
                'index': 0,
                'move_side': self.boardView.get_move_color()
                }
            self.onPositionChanged(position, isNew = True)
        self.hasNewMove = False

    def onMoveGo(self, move_iccs, quickMode = False): #, score = None):

        with self.moveLock:

            self.isInMoveMode = True  #用historyMode保护在此期间引擎输出的move信息被忽略
            if not self.board.is_valid_iccs_move(move_iccs):
                self.isInMoveMode = False
                return False
           
            #--------------------------------
            #尝试走棋
            move = self.board.move_iccs(move_iccs)
            if move is None:
                #不能走就返回
                self.isInMoveMode = False  #结束保护
                return False
            #self.board在做了这个move动作后，棋子已经更新到新位置了
            #board是下个走子的position了
            self.board.next_turn()
            #--------------------------------
          
            #这一行必须有,否则引擎不能工作
            hist = [x['move'] for x in self.positionList[1:]]
            move.prepare_for_engine(move.board.move_player.opposite(), hist)

            
            fen = self.board.to_fen()

            position = {
                'fen': fen,
                'fen_prev': move.board.to_fen(),
                'iccs':  move_iccs,
                'move': move,
                'index': len(self.positionList),
                'move_side': move.board.move_player.color
            }

            self.onPositionChanged(position, isNew = True, quickMode = quickMode)

            if move.is_checking:
                if move.is_checkmate:
                    msg = "将死！"
                    self.playSound('mate', quickMode)
                    self.onGameOver(move.board.move_player)
                else:
                    self.playSound('check', quickMode)
                    msg = "将军！"
            elif move.captured:
                self.playSound('capture', quickMode)
                msg = f"吃{fench_to_text(move.captured)}"
            else:
                self.playSound('move', quickMode)
                msg = ""

            self.statusBar().showMessage(msg)
            self.isInMoveMode = False  #结束保护
            return True 

    def onPositionChanged(self, position, isNew = True, quickMode = False):   
        
        fen = position['fen']
        self.currPosition = position
        self.isRunEngine = False
        
        if isNew:
            self.fenPosDict[fen] = position
            self.positionList.append(position)      
            #print(position['index'], fen)

            #在fenCach中把招法连起来
            if fen not in Globl.fenCache:
                Globl.fenCache[fen] = {}
            
            if 'fen_prev' in position:    
                Globl.fenCache[fen].update({ 'fen_prev': position['fen_prev'] })
            
            self.historyView.inner.onNewPostion(self.currPosition)
        else:
            move_index = position['index']
            is_last = True if move_index >= len(self.positionList) - 1 else False

            self.isHistoryMode = not is_last
            self.boardView.setViewOnly(self.isHistoryMode)
            self.historyView.inner.selectIndex(move_index, fireEvent = False)

        #提示最优其他走法
        best_show = []     
        if fen in Globl.fenCache:
            fenInfo = Globl.fenCache[fen]
            if 'alter_best' in fenInfo:
                best_show = [iccs2pos(x) for x in fenInfo['alter_best']]     
       
        #显示走子移动
        if 'move' in position:
            move = position['move']
            self.boardView.from_fen(move.board.to_fen())
            self.boardView.showMove(move.p_from, move.p_to, best_show)
        else:
             self.boardView.clearPickup()
        
        #清空显示，同步棋盘状态    
        self.engineView.clear()       
        self.cloudDbView.clear()
        self.boardView.from_fen(fen)
        
        #确定是否进行云搜索
        if self.gameMode == GameMode.EndGame:        
            pass
        else:
            if not quickMode:
                self.moveDbView.onPositionChanged(position, isNew)
                if (self.queryMode == QueryMode.CloudFirst) or (self.reviewMode == ReviewMode.ByCloud):
                    self.cloudQuery.startQuery(position)
                if self.queryMode == QueryMode.EngineFirst:
                    self.localSearch(position)
        
        #引擎搜索
        if not quickMode:
            self.runEngine(position)
        
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
        
        fen = position['fen']
        qResult = self.openBook.getMoves(fen)
        if not qResult:
            self.cloudDbView.updateActions([])
        else:    
            #self.updateFenCache(qResult)
            self.cloudDbView.updateActions(qResult['actions'])

    def onCloudQueryResult(self, qResult):
        
        if not qResult or not self.positionList:
            return
        
        fen = qResult['fen']
        if (self.queryMode == QueryMode.CloudFirst) or (self.reviewMode == ReviewMode.ByCloud):
            self.updateFenCache(qResult)
    
            posi = self.fenPosDict[fen]
            if posi == self.currPosition:
                self.cloudDbView.updateActions(qResult['actions'])
            
            if self.reviewMode == ReviewMode.ByCloud:
                self.onReviewGameStep()
        
    #-----------------------------------------------------------
    #Engine 输出
    def onTryEngineMove(self, engine_id, fenInfo):
        
        self.isRunEngine = False
        
        fen = fenInfo['fen']
        logging.debug(f'Engine[{engine_id}] BestMove {fenInfo}' )
        
        #print('onEngineMoveBest', fenInfo)

        if (self.gameMode != GameMode.EndGame) and ((self.queryMode == QueryMode.EngineFirst) or (self.reviewMode == ReviewMode.ByEngine)) :
            self.updateFenCache(fenInfo)

        if self.reviewMode == ReviewMode.ByEngine :
            self.onReviewGameStep()
            return
            
        if self.isHistoryMode or self.isInMoveMode or (fen != self.board.to_fen()):
            return

        move_color = self.board.get_move_color()
        if self.engineRunColor[move_color] != engine_id:
            return
        
        ok = self.onMoveGo(fenInfo['iccs'])
        if ok:
            self.hasNewMove = True

    def onEngineMoveInfo(self, engine_id, fenInfo):
        
        #if (self.queryMode == QueryMode.EngineFirst) or (self.reviewMode == ReviewMode.ByEngine):
        #    self.updateFenCache(fenInfo)
        if not self.currPosition:
            return

        fen = fenInfo['fen']

        #引擎输出的历史数据,不处理
        if fen != self.currPosition['fen']:
            return

        board = ChessBoard(fen)
        iccs = fenInfo['moves'][0]
        #引擎输出的历史数据,不处理
        if not board.is_valid_iccs_move(iccs):
            return

        self.engineView.onEngineMoveInfo(fenInfo)

    def onEngineReady(self, engine_id, name, engine_options):
        logging.info(f'Engine[{engine_id}] {name} Ready.' )
        self.engineView.readSettings(self.settings)
        self.engineView.onEngineReady(engine_id, name, engine_options)

    #-----------------------------------------------------------
    #fenCache 核心逻辑
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
        
        if ('diff' not in fenInfo) and ('fen_prev' in fenInfo):
            fen_prev = fenInfo['fen_prev']
            if fen_prev in Globl.fenCache :
                prevInfo = Globl.fenCache[fen_prev]
                if 'score' in prevInfo:
                    diff = prevInfo['score'] - fenInfo['score']
                    if get_move_color(fen) == cchess.BLACK:
                        diff = -diff 
                    fenInfo['diff'] = diff
                    if (diff < -50) and ('best_next' in prevInfo):
                        fenInfo['alter_best'] = prevInfo['best_next']
        
        if fen in self.fenPosDict:
            self.historyView.inner.onUpdatePosition(self.fenPosDict[fen])
                    
    #--------------------------------------------------------------------
    #引擎相关
    def enginePlayColor(self, engine_id, color, yes):

        if yes:
            self.engineRunColor[color] = engine_id
        else:
            self.engineRunColor[color] = 0
        
        needRun = (sum(self.engineRunColor) > 0)
        
        if needRun and (not self.isRunEngine) and (not self.reviewMode):
            if self.currPosition:
                self.runEngine(self.currPosition)
        
    def runEngine(self, position):

        fen_engine = fen = position['fen']
        
        if cchess.EMPTY_BOARD in fen:
            return 
                
        move_color = get_move_color(fen)
        
        if (self.engineRunColor[0] > 0) or (self.engineRunColor[move_color] > 0):
            #首行会没有move项
            if 'move' in position:
                fen_engine = position['move'].to_engine_fen()
            
            params = self.engineView.getGoParams()
            
            ok = Globl.engineManager.goFrom(fen_engine, fen, params)
            if ok:
                self.isRunEngine = True
            else:
                QMessageBox.critical(self, f'{getTitle()}', '象棋引擎命令出错，请确认该程序能正常运行。')
        
        #print('isRunEngine', self.isRunEngine)

    '''    
    #---------------------------------------------------------------------------
    #Engine config
    def onConfigEngine(self):
        params = {} # Globl.engineManager.get_config()

        dlg = EngineConfigDialog()
        if dlg.config(params):
            #Globl.engineManager.update_config(params)
            pass

    def onRedBoxChanged(self, state):
        e_id = Globl.engineManager.id
        red_checked = self.engineView.redBox.isChecked()
        #print('onRedBoxChanged', red_checked)
        self.enginePlayColor(e_id, cchess.RED, red_checked)
        
        if self.gameMode in [GameMode.EndGame, GameMode.Fight]:
            black_checked = self.engineView.blackBox.isChecked()
            if red_checked == black_checked:
                self.engineView.blackBox.setChecked(not red_checked)
            
    def onBlackBoxChanged(self, state):
        e_id = Globl.engineManager.id
        black_checked = self.engineView.blackBox.isChecked()
        #print('onBlackBoxChanged', black_checked)
        
        self.enginePlayColor(e_id, cchess.BLACK, black_checked)

        if self.gameMode in [GameMode.EndGame, GameMode.Fight]:
            red_checked = self.engineView.redBox.isChecked()
            if red_checked == black_checked:
                self.engineView.redBox.setChecked(not black_checked)
        
    def onAnalysisBoxChanged(self, state):
        e_id = Globl.engineManager.id
        yes = (Qt.CheckState(state) == Qt.Checked)
        #print('onAnalysisBoxChanged', yes)
        self.enginePlayColor(e_id, 0, yes)
    '''

    #------------------------------------------------------------------------------
    #UI Events
    def onTryBoardMove(self,  move_from,  move_to):
        
        if self.isInMoveMode:
            return
        
        move_iccs = pos2iccs(move_from, move_to)
        ok = self.onMoveGo(move_iccs)
        if ok:
            self.hasNewMove = True

    def onTryBookMove(self, moveInfo):
        
        if self.isInMoveMode or  self.isHistoryMode:
            return
        
        ok = self.onMoveGo(moveInfo['iccs'])
        if ok:
            self.hasNewMove = True
                
    def onBoardRightMouse(self, is_mouse_pressed):
        
        best_next = []    

        if is_mouse_pressed:

            fen = self.currPosition['fen']
            if (fen not in Globl.fenCache) or ('best_next' not in Globl.fenCache[fen]):
                return

            iccs_list = Globl.fenCache[fen]['best_next']
            best_next = [ iccs2pos(x)  for x in iccs_list]

        self.boardView.showBestMoveNext(best_next)    

    def deleteHistoryFollow(self, move_step):

        for position in reversed(self.positionList):
            fen = position['fen']
            index = position['index']
            if index <= move_step:
                break
            if fen in self.fenPosDict:    
                del self.fenPosDict[fen]

        self.positionList = self.positionList[:move_step + 1]
        self.currPosition = self.positionList[-1]
        
        self.isHistoryMode = False
        self.boardView.setViewOnly(False)
    
    def onSelectHistoryPosition(self, move_index):
        
        #print("onSelectHistoryPosition", move_index)

        if (move_index < 0) or (move_index >= len(self.positionList)):
            return
        
        if self.reviewMode:
            return

        position = self.positionList[move_index]
             
        self.onPositionChanged(position, isNew = False)
    
    
    #-------------------------------------------------------------------        
    #Game Review 
    def onReviewByCloud(self):    

        if not self.reviewMode:
            self.reviewMode = ReviewMode.ByCloud
            self.cloudModeBtn.setEnabled(False)
            self.engineModeBtn.setEnabled(False)
        
            self.clearAllScore()
            self.showScoreBox.setChecked(True)
            self.reviewList = list(self.fenPosDict.keys())
            self.historyView.inner.reviewByCloudBtn.setText('停止复盘')
            self.engineView.onReviewBegin(self.reviewMode)
            self.onReviewGameStep()
        else:
            self.onReviewGameEnd(isCanceled=True)
         
    def onReviewByEngine(self):    

        if not self.reviewMode:
            self.reviewMode = ReviewMode.ByEngine
            
            self.cloudModeBtn.setEnabled(False)
            self.engineModeBtn.setEnabled(False)
            
            self.clearAllScore()
            self.showScoreBox.setChecked(True)
            self.reviewList = list(self.fenPosDict.keys())
            
            self.engineView.onReviewBegin(self.reviewMode)
            self.historyView.inner.reviewByEngineBtn.setText('停止复盘')
            self.onReviewGameStep()
        else:
            self.onReviewGameEnd(isCanceled=True)
            
    def onReviewGameStep(self):
        if len(self.reviewList) > 0:
            fen_step = self.reviewList.pop(0)
            position = self.fenPosDict[fen_step]
            
            #print("OnReview", position['index'])

            self.onPositionChanged(position, isNew = False)
            qApp.processEvents()

            if self.reviewMode == ReviewMode.ByCloud:
                self.cloudQuery.startQuery(position)
            elif self.reviewMode == ReviewMode.ByEngine:
                self.runEngine(position)
        else:
            self.onReviewGameEnd()
        
    def onReviewGameEnd(self, isCanceled=False):
        
        self.historyView.inner.reviewByCloudBtn.setText('云库复盘')
        self.historyView.inner.reviewByEngineBtn.setText('引擎复盘')
        
        self.reviewMode = None
        
        if not isCanceled:
            msgbox = TimerMessageBox("  复盘分析完成。  ", timeout=1)
            msgbox.exec()
        
        self.cloudModeBtn.setEnabled(True)
        self.engineModeBtn.setEnabled(True)
        
        self.engineView.onReviewEnd()
            
    def setQueryMode(self, mode):
        
        if mode == self.queryMode: #模式未变
            return

        self.queryMode = mode
        
        if self.queryMode == QueryMode.EngineFirst:
            self.historyView.inner.reviewByEngineBtn.setEnabled(True)
            self.historyView.inner.reviewByCloudBtn.setEnabled(False)
            #极少数情况下棋盘是未初始化的
            if self.currPosition:
                self.localSearch(self.currPosition)

        elif self.queryMode == QueryMode.CloudFirst:
            self.historyView.inner.reviewByEngineBtn.setEnabled(False)
            self.historyView.inner.reviewByCloudBtn.setEnabled(True)
            #极少数情况下棋盘是未初始化的
            if self.currPosition:
                self.cloudQuery.startQuery(self.currPosition)
        #self.clearAllScore()

    #------------------------------------------------------------------------------
    #UI Event Handler
    def getConfirm(self, msg):
        ok = QMessageBox.question(self, getTitle(), msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if (ok == QMessageBox.Yes):
            return True 
        return False

    def onDoFreeGame(self):
        self.switchGameMode(GameMode.Free)

    def onDoRobot(self):
        self.switchGameMode(GameMode.Fight)
        
    def onDoEndGame(self):
        if (self.gameMode != GameMode.EndGame) and self.hasNewMove:
            steps = len(self.positionList) - 1
            if not self.getConfirm(f"当前棋谱已经走了 {steps} 步, 您确定要切换到 [残局挑战] 模式并丢弃当前棋谱吗?"):
                return
        self.switchGameMode(GameMode.EndGame)

    def onDoOnline(self):
        #self.switchGameMode(GameMode.Online)
        #dlg = OnlineDialog(self)
        #dlg.show()
        pass

    def onRestartGame(self):
        self.initGame(self.init_fen)
    
    def onSelectEndGame(self, game):
        
        if self.gameMode != GameMode.EndGame:
            return
        
        self.currGame = game
        self.book_moves = game['moves'].split(' ') if 'moves' in game else []
        
        fen = game['fen']
        steps = getStepsFromFenMoves(fen, self.book_moves)
        
        self.initGame(fen)

        for fen_t, iccs in steps:
            Globl.fenCache[fen_t] = {'score': 99999, 'best_next': [iccs, ]}
            
        self.hasNewMove = False
        self.updateTitle(f'{game["book_name"]} - {game["name"]}')

    def loadBookGame(self, name, game):
        
        fen = game.init_board.to_fen()
        
        self.initGame(fen)
        
        moves = game.dump_iccs_moves()
        if not moves:
            return
        for iccs in moves[0]:
            self.onMoveGo(iccs, quickMode = True)
            #qApp.processEvents()

        self.hasNewMove = False
        self.updateTitle(name)

    def loadBookmark(self, name, position):
        if self.hasNewMove :
            steps = len(self.positionList) - 1
            if not self.getConfirm(f"当前棋谱已经走了 {steps} 步, 您确定要加载收藏并丢弃当前棋谱吗?"):
                return 
            
        self.bookmarkView.setEnabled(False)

        fen = position['fen']        
        self.initGame(fen)
        
        if 'moves' in position:
            moves = position['moves']
            if moves is not None:
                for it in moves:
                    iccs = it['iccs']    
                    self.onMoveGo(iccs, quickMode = True)
                    #qApp.processEvents()
            
        self.hasNewMove = False
        self.updateTitle(name)
        self.bookmarkView.setEnabled(True)
        
    def onViewBranch(self, branch):
        dlg = PositionHistDialog()
        dlg.exec()

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
    
    def onShowScoreChanged(self, state):
        self.historyView.inner.setShowScore((Qt.CheckState(state) == Qt.Checked))

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
            self, "打开文件", self.lastOpenFolder, "象棋演播室文件(*.xqf);;象棋通用格式文件(*.pgn);;所有文件(*.*)", options=options)

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
        self.lastOpenFolder = str(fileName.parent)
       
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

        self.saveToFile(fileName)
        self.lastOpenFolder = str(Path(fileName).parent)
        
    def saveToFile(self, file_name):

        board = ChessBoard(self.positionList[0]['fen'])
        game = Game(board)
        for pos in self.positionList[1:]:
            game.append_next_move(pos['move'])
        
        game.save_to(file_name)
        self.hasNewMove = False

    def onUseOpenBookFile(self):
        options = QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog

        fileName, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "", "YFK格式开局库(*.yfk);;所有文件(*.*)", options=options)

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

        games = loadEglib(fileName)

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
                                   "开局库选择",
                                   self,
                                   statusTip="选择开局库文件（yfk格式）",
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
                                     triggered=self.onDoFreeGame)

        self.doEndGameAct = QAction(QIcon(':Images/endbook.png'),
                                    "杀法挑战",
                                    self,
                                    statusTip="入局杀法挑战",
                                    triggered=self.onDoEndGame)

        self.doRobotAct = QAction(QIcon(':Images/robot.png'),
                                   "人机战斗",
                                   self,
                                   statusTip="人机战斗",
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
        self.fileBar.setObjectName("File")

        self.fileBar.addAction(self.openFileAct)
        self.fileBar.addAction(self.saveFileAct)
        #self.fileBar.addAction(self.myGamesAct)
        self.fileBar.addAction(self.bookmarkAct)

        ag = QActionGroup(self)
        ag.setExclusive(True)
        ag.addAction(self.doOpenBookAct)
        ag.addAction(self.doEndGameAct)
        ag.addAction(self.doRobotAct)

        self.gameBar = self.addToolBar("Game")
        self.gameBar.setObjectName("Game")

        self.gameBar.addAction(self.doOpenBookAct)
        self.gameBar.addAction(self.doRobotAct)
        self.gameBar.addAction(self.doEndGameAct)
        
        self.gameBar.addAction(self.restartAct)
        self.gameBar.addAction(self.editBoardAct)
        #self.gameBar.addAction(self.searchBoardAct)

        self.flipBox = QCheckBox()  #"翻转")
        self.flipBox.setIcon(QIcon(':Images/up_down.png'))
        self.flipBox.setToolTip('上下翻转')
        self.flipBox.stateChanged.connect(self.onFlipBoardChanged)

        self.mirrorBox = QCheckBox()  #"镜像")
        self.mirrorBox.setIcon(QIcon(':Images/left_right.png'))
        self.mirrorBox.setToolTip('左右镜像')
        self.mirrorBox.stateChanged.connect(self.onMirrorBoardChanged)

        self.cloudModeBtn = QRadioButton("云库优先")
        #self.cloudModeBtn.setIcon(QIcon(':Images/cloud.png'))
        self.cloudModeBtn.setToolTip('云库优先模式')
        self.cloudModeBtn.toggled.connect(lambda: self.setQueryMode(QueryMode.CloudFirst))

        self.engineModeBtn = QRadioButton("引擎优先") 
        #self.engineModeBtn.setIcon(QIcon(':Images/engine.png'))
        self.engineModeBtn.setToolTip('引擎优先模式')
        self.engineModeBtn.toggled.connect(lambda: self.setQueryMode(QueryMode.EngineFirst))
        
        self.modeBtnGroup = QButtonGroup(self)
        self.modeBtnGroup.addButton(self.cloudModeBtn, 1)      # ID 1
        self.modeBtnGroup.addButton(self.engineModeBtn, 2)      # ID 2

        self.showBestBox = QCheckBox('最佳提示')  #"最佳提示")
        self.showBestBox.setIcon(QIcon(':Images/info.png'))
        self.showBestBox.setChecked(True)
        self.showBestBox.setToolTip('提示最佳走法')
        self.showBestBox.stateChanged.connect(self.onShowBestMoveChanged)
    
        self.showScoreBox = QCheckBox('分数')  #"最佳提示")
        #self.showScoreBox.setIcon(QIcon(':Images/info.png'))
        self.showScoreBox.setChecked(True)
        self.showScoreBox.setToolTip('显示走子得分（红优分）')
        self.showScoreBox.stateChanged.connect(self.onShowScoreChanged)
        
        self.showBar = self.addToolBar("Show")
        self.showBar.setObjectName("Show")

        self.showBar.addWidget(self.flipBox)
        self.showBar.addWidget(self.mirrorBox)
        self.showBar.addSeparator()
        self.showBar.addWidget(self.cloudModeBtn)
        self.showBar.addWidget(self.engineModeBtn)
        
        self.showBar.addSeparator()
        self.showBar.addWidget(self.showBestBox)
        self.showBar.addWidget(self.showScoreBox)
        
        self.sysBar = self.addToolBar("System")
        self.sysBar.setObjectName("System")

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.sysBar.addWidget(spacer)
        self.sysBar.addAction(self.exitAct)

        self.statusBar().showMessage("Ready")

    def onShowMoveSound(self, yes):
        self.soundVolume = 30 if yes else 0

  
    def center(self):
        screen = QWidget.screen().screenGeometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) // 2,
                  (screen.height() - size.height()) // 2)

    def closeEvent(self, event):
        steps = len(self.positionList) - 1
        if self.hasNewMove and (self.gameMode in [GameMode.Free, GameMode.Fight]):
            if not self.getConfirm(f"当前棋谱已经走了 {steps} 步, 尚未保存，您确定要关闭程序吗?"):
                event.ignore()

        self.writeSettings()
        Globl.engineManager.quit()
        time.sleep(0.6)
        self.openBook.close()
        Globl.storage.close()
        

    def readSettingsBeforeGameInit(self):
        self.settings = QSettings('XQSoft', Globl.app.APP_NAME)
        
        #Test Only Code
        #self.settings.clear()

        self.restoreGeometry(self.settings.value("geometry", QByteArray()))
        self.restoreState(self.settings.value("windowState", QByteArray()))
        
        self.soundVolume = self.settings.value("soundVolume", 30)
        self.showMoveSoundAct.setChecked(self.soundVolume > 0)
        
        self.savedGameMode = self.settings.value("gameMode", GameMode.Free)
        
        self.openBookFile = Path(self.settings.value("openBookFile", str(Path('game','openbook.yfk'))))
        self.lastOpenFolder = self.settings.value("lastOpenFolder", '')

        self.endBookView.readSettings(self.settings)
        
    def readSettingsAfterGameInit(self):
        flip = self.settings.value("flip", False, type=bool)
        self.flipBox.setChecked(flip)
        
        mirror = self.settings.value("mirror", False, type=bool)
        self.mirrorBox.setChecked(mirror)
        
        showBest = self.settings.value("showBest", True, type=bool)
        self.showBestBox.setChecked(showBest)
        
        showScore = self.settings.value("showScore", True, type=bool)
        self.showScoreBox.setChecked(showScore)

        cloudMode = self.settings.value("cloudMode", True, type=bool)
        if cloudMode:
            self.cloudModeBtn.setChecked(True)
        
        engineMode = self.settings.value("engineMode", False, type=bool)
        if engineMode:
            self.engineModeBtn.setChecked(True)
        
    #    self.engineView.readSettings(self.settings)

    def writeSettings(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        
        self.settings.setValue("soundVolume", self.soundVolume)
        self.settings.setValue("gameMode", self.gameMode)
        
        self.settings.setValue("flip", self.flipBox.isChecked())
        self.settings.setValue("mirror", self.mirrorBox.isChecked())
        self.settings.setValue("showBest", self.showBestBox.isChecked())
        self.settings.setValue("showScore", self.showScoreBox.isChecked())

        self.settings.setValue("cloudMode", self.cloudModeBtn.isChecked())
        self.settings.setValue("engineMode", self.engineModeBtn.isChecked())
        
        self.settings.setValue("openBookFile", self.openBookFile)
        self.settings.setValue("lastOpenFolder", self.lastOpenFolder)
        
        self.engineView.writeSettings(self.settings)
        self.endBookView.writeSettings(self.settings)

    def about(self):
        QMessageBox.about(
            self, f"关于 {Globl.app.APP_NAME}",
            f"{Globl.app.APP_NAME_TEXT} Version {release_version}\n个人棋谱管家.\n 云库支持：https://www.chessdb.cn/\n 引擎支持：皮卡鱼(https://pikafish.org/)\n\n 联系作者：1053386709@qq.com\n QQ 进群：101947824\n"
        )

#-----------------------------------------------------#
