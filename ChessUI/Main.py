# -*- coding: utf-8 -*-
import os
import sys
import time
import logging
import ctypes
import traceback
import platform
import threading
from enum import Enum, auto
from pathlib import Path
from collections import OrderedDict
from configparser import ConfigParser

#from PySide6 import 
from PySide6.QtCore import Qt, Signal, QByteArray, QSettings, QUrl
from PySide6.QtGui import QActionGroup, QIcon, QAction
from PySide6.QtWidgets import QApplication,QMainWindow, QStyle, QSizePolicy, QMessageBox, QWidget, QCheckBox, QRadioButton, \
                            QFileDialog, QButtonGroup
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

import cchess
from cchess import ChessBoard, Game

from .Version import release_version
from .Resource import qt_resource_data
from .Manager import EngineManager

from .Storage import EndBookStore #, LocalBookStore
from .CloudDB import CloudDB
from .LocalDB import OpenBookYfk, OpenBookPF, MasterBook, LocalBook

from .Utils import GameMode, ReviewMode, TimerMessageBox, getTitle, getStepsFromFenMoves, trim_fen
from .BoardWidgets import ChessBoardWidget, DEFAULT_SKIN
from .Widgets import ChessEngineWidget, BookmarkWidget, \
                    BoardActionsWidget, EndBookWidget, DockHistoryWidget, GameLibWidget
from .Dialogs import PositionEditDialog, PositionHistDialog, ImageToBoardDialog, EngineConfigDialog

from .SnippingWidget import SnippingWidget
from .Ecco import getBookEcco

#from .Online import OnlineDialog

from . import Globl

#-----------------------------------------------------#
GameTitle = {
    None : '',
    GameMode.Free: '自由练棋', 
    GameMode.Fight: '人机对战', 
    GameMode.EndGame: '杀法挑战', 
    GameMode.Online: '连线分析',          
}

#-----------------------------------------------------#
class ActionType(Enum):
    MOVE = auto()
    CAPTRUE = auto()
    CHECKING = auto()
    MATE = auto()
        
#-----------------------------------------------------#
class QueryMode(Enum):
    CloudFirst = auto()
    EngineFirst = auto()

#-----------------------------------------------------#

GAME_FILE_TYPES = ['.xqf','.pgn', '.cbr']
GAME_LIB_TYPES = ['.cbl']
GAME_TYPES_ALL = GAME_FILE_TYPES + GAME_LIB_TYPES

class MainWindow(QMainWindow):
    initGameSignal = Signal(str)
    newBoardSignal = Signal()
    moveBeginSignal = Signal()
    moveEndSignal = Signal()
    #newPositionSignal = Signal()
    changePositionSignal = Signal(bool, bool)

    def __init__(self):
        super().__init__()

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAcceptDrops(True)

        self.setWindowIcon(QIcon(':ImgRes/app.ico'))
                
        if platform.system() == "Windows":
            #在Windows状态栏上正确显示图标
            myappid = 'mycompany.myproduct.subproduct.version'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                myappid)
        
        gamePath = Path('Game')
        gamePath.mkdir(exist_ok=True)
                
        #self.openBook = MasterBook()
        #self.openBook.open(Path('Game', 'openbook.edb'))
        
        book_file = Path('Game', 'openbook.yfk')
        if book_file.is_file():
            self.openBook = OpenBookYfk()
            self.openBook.open(book_file)
            logging.info(f'加载开局库：{book_file}')
        else:
            book_file = Path('Game', 'openbook.pfbook')
            if book_file.is_file():
                self.openBook = OpenBookPF()
                self.openBook.open(book_file)
                logging.info(f'加载开局库：{book_file}')
            else:
                self.openBook = OpenBookPF()
                logging.info('没有开局库被加载')

        Globl.endbookStore = EndBookStore(Path(gamePath, 'endbooks.json'))
        #Globl.localbookStore = LocalBookStore(Path(gamePath, 'localbooks.json'))
       
        Globl.localBook = LocalBook()
        Globl.localBook.open(Path(gamePath, 'localbook.db'))
        
        Globl.engineManager = EngineManager(self, id = 1)
        
        self.board = ChessBoard()
        self.changePositionSignal.connect(self.onChangePosition)

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

        #self.moveDbView = MoveDbWidget(self)
        #self.moveDbView.selectMoveSignal.connect(self.onTryBookMove)
        self.actionsView = BoardActionsWidget(self)
        self.actionsView.selectMoveSignal.connect(self.onTryBookMove)

        self.bookmarkView = BookmarkWidget(self)
        self.bookmarkView.setVisible(False)
        self.gamelibView = GameLibWidget(self)
        self.gamelibView.setVisible(False)
                
        self.engineView = ChessEngineWidget(self, Globl.engineManager)
        
        #self.addDockWidget(Qt.LeftDockWidgetArea, self.moveDbView)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.actionsView)
        #self.addDockWidget(Qt.RightDockWidgetArea, self.gameReviewView)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.endBookView)
        self.addDockWidget(Qt.RightDockWidgetArea, self.historyView)
        self.addDockWidget(Qt.RightDockWidgetArea, self.bookmarkView)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.gamelibView)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.engineView)
        
        self.snippingWidget = SnippingWidget()
        self.snippingWidget.onSnippingCompleted = self.onSnippingCompleted
        
        Globl.engineManager.readySignal.connect(self.onEngineReady)
        Globl.engineManager.moveBestSignal.connect(self.onTryEngineMove)
        Globl.engineManager.moveInfoSignal.connect(self.onEngineMoveInfo)
        #Globl.engineManager.checkmate_signal.connect(self.onEngineCheckmate)

        self.skins = self.loadSkins()
        self.initSound()
        self.createActions()
        self.createMenus()
        self.createToolBars()

        self.gameMode = None
        self.queryMode = None
        self.reviewMode = None
        self.lastOpenFolder = ''
        self.isNeedSave = False
        self.isRunEngine = False
        self.engineRunColor = [0, 0, 0]
        self.boardActions = OrderedDict()

        self.skin = DEFAULT_SKIN 

        self.clearAll()
        
        ok = self.initEngine()
        if not ok:
            sys.exit(-1)

        Globl.engineManager.start()
            
        self.readSettingsBeforeGameInit()
        
        '''
        if self.openBookFile.is_file():
            if not self.openBook.open(self.openBookFile):
                msgbox = TimerMessageBox(f"打开开局库文件【{self.openBookFile}】出错, 请重新配置开局库。")
                msgbox.exec()
        else:
            msgbox = TimerMessageBox(f"开局库文件【{self.openBookFile}】不存在, 请重新配置开局库。")
            msgbox.exec()
        '''

        #self.quickBooks = self.loadQuickBook(Path('Game', 'quick_book.txt'))
        #self.bookmarkView.addQuickBooks(self.quickBooks)
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
        self.reviewMode = None

        self.historyView.inner.clear()
        self.engineView.clear()
        self.boardView.setViewOnly(False)
        self.boardActions = OrderedDict()

    def initEngine(self):
        self.config_file = Path('Evolution.ini')
        
        if not self.config_file.is_file():
            QMessageBox.critical(self, f'{getTitle()}', f'配置文件[{self.config_file}]不存在，请确保该文件存在并配置正确.')
            return False    
       
        self.config = ConfigParser()
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
        self.openBook.close()
        if self.openBook.open(file_name):
            self.openBookFile = Path(file_name)
   
    def loadSkins(self):
        
        skins = {}
        skins['默认'] = {'Folder':None}
        
        skinsFolder = Path("Skins")
        for nm in os.listdir(skinsFolder): 
            name = Path(skinsFolder, nm)
            if name.is_dir():
                skins[nm] = { 'Folder': name }
        return skins

    def loadQuickBook(self, fileName):
        quick_moves = OrderedDict()
        
        with open(fileName, 'r', encoding = 'utf-8') as f:
            for line_it in f.readlines():
                line = line_it.strip()
                if not line or line.startswith('#'):
                    continue
                items = line.split(':')
                #print(len(items), line)
                if len(items) != 2:
                    logging.warning(line)
                    continue
                name, moves = items
                name = name[4:]
                quick_moves[name] = moves
        
        return quick_moves
                    
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
            self.player.setSource(QUrl.fromLocalFile(Path('Sound', f'{s_type}.wav')))
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
        moves = [it['iccs'] for it in self.positionList[1:]]
        return (self.positionList[0]['fen'], moves)

    def saveGameToDB(self):
        Globl.localBook.savePositionList(self.positionList)
        self.isNeedSave = False
    
    #-----------------------------------------------------------------------
    #Game 相关
    def switchGameMode(self, gameMode):

        #模式未变
        if self.gameMode == gameMode:
            if (self.gameMode == GameMode.Free) and self.isNeedSave:
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
            self.actionsView.show()
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
            self.gamelibView.hide()
            self.actionsView.hide()
            
            self.showScoreBox.setChecked(False)

            self.cloudModeBtn.setEnabled(True)
            #self.cloudModeBtn.setChecked(False)
            self.engineModeBtn.setEnabled(True)
            #self.engineModeBtn.setChecked(True)
            
            self.showBestBox.setEnabled(True)
            self.showBestBox.setChecked(False)
        
            self.openFileAct.setEnabled(True)
            self.editBoardAct.setEnabled(True)
        
            if self.lastGameMode in [None, GameMode.EndGame]:
                self.initGame(cchess.FULL_INIT_FEN)
        
        elif self.gameMode == GameMode.EndGame:
            self.myGamesAct.setEnabled(False)
            self.bookmarkAct.setEnabled(False)
            self.endBookView.show()
            self.bookmarkView.hide()
            self.gamelibView.hide()
            self.actionsView.hide()
            
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
                msgbox.exec()
                self.onRestartGame()
            else:
                msgbox = TimerMessageBox("太棒了！ 挑战成功！！！")
                msgbox.exec()
                self.currGame['ok'] = True
                Globl.endbookStore.updateEndBook(self.currGame)
                self.endBookView.updateCurrent(self.currGame)
                self.endBookView.nextGame()            
        else:
            win_msg = '红方被将死!' if win_side == cchess.BLACK else '黑方被将死!'
            msgbox = TimerMessageBox(win_msg)
            msgbox.exec()

    #-----------------------------------------------------------
    #走子核心逻辑
    def initGame(self, fen):
        self.isNeedSave = False
        self.init_fen = fen

        self.moveLock = threading.RLock()
        with self.moveLock:
            Globl.engineManager.stopThinking()
            self.clearAll()
            self.boardView.from_fen(self.init_fen, clear = True)
            position = {
                'fen': self.init_fen,
                'index': 0,
                'move_color': self.boardView.get_move_color()
                }

            if cchess.FULL_INIT_BOARD in self.init_fen:
               position['ecco'] = ''
            
            self.positionList.append(position)
            self.currPosition = position   
        
        self.changePositionSignal.emit(True, False)
        
    def updateEcco(self):
        
        if len(self.positionList) == 0:
            return
        
        if ('ecco' in self.positionList[0]):
            position = self.positionList[-1]
            
            eccos = ''
            index = position['index']
            
            if index >= 25:
                return

            if 8 < index < 25:
                ecco = getBookEcco(self.positionList)
                eccos = '-'.join(ecco[1:])
                self.positionList[0]['ecco'] = eccos
                self.updateTitle(eccos)  
            
    def onMoveGo(self, move_iccs, quickMode = False): #, score = None):

        with self.moveLock:

            if not self.board.is_valid_iccs_move(move_iccs):
                return False
           
            #--------------------------------
            #尝试走棋
            move = self.board.move_iccs(move_iccs)
            if move is None:
                #不能走就返回
                return False
           
            #self.board在做了这个move动作后，棋子已经更新到新位置了
            #board是下个走子的position了
            self.board.next_turn()
            #--------------------------------
          
            #这一行必须有,否则引擎不能正常处理历史走子数据，会走出循环着法
            move_history = [x['move'] for x in self.positionList[1:]]
            move.prepare_for_engine(self.board.move_player, move_history)

            new_fen = self.board.to_fen()

            position = {
                'fen': new_fen,
                'fen_prev': move.board.to_fen(),
                'iccs':  move_iccs,
                'move': move,
                'index': len(self.positionList),
                'move_color': move.board.move_player.color
            }
        
            self.positionList.append(position)      
            self.currPosition = position

        if not quickMode:
            self.isNeedSave = True

        self.fenPosDict[new_fen] = position
        #在fenCach中把招法连起来
        if new_fen not in Globl.fenCache:
            Globl.fenCache[new_fen] = {}
        Globl.fenCache[new_fen].update({ 'fen_prev': position['fen_prev'] })

        self.changePositionSignal.emit(True, quickMode)
        
    def onChangePosition(self, isNew = True, quickMode = False):   
        
        position = self.currPosition
        fen = position['fen']
        move_index = position['index']
            
        #提示最优其他走法
        best_show = []     
        if fen in Globl.fenCache:
            fenInfo = Globl.fenCache[fen]
            if 'alter_best' in fenInfo:
                best_show = [cchess.iccs2pos(x) for x in fenInfo['alter_best']]     
        
        #显示走子移动
        if 'move' in position:
            move = position['move']
            self.boardView.from_fen(move.board.to_fen())
            self.boardView.showMove(move.p_from, move.p_to, best_show)
        else:
             self.boardView.clearPickup()
        self.boardView.from_fen(fen)
        
        self.isRunEngine = False
        
        if isNew:
            self.historyView.inner.onNewPostion(self.currPosition)
            self.updateStatus(quickMode)
            self.updateEcco()         
        else:
            self.historyView.inner.selectIndex(move_index, fireEvent = False)

        #清空显示，同步棋盘状态    
        self.engineView.clear()
        self.actionsView.clear()
        self.boardActions = OrderedDict()

        #确定是否进行云搜索
        if self.gameMode == GameMode.EndGame:        
            pass
        else:
            if not quickMode:
                self.localSearch(position)
                if (self.queryMode == QueryMode.CloudFirst) or (self.reviewMode == ReviewMode.ByCloud):
                    self.cloudQuery.startQuery(position)
                
        #引擎搜索
        if not quickMode:
            self.runEngine(position)
    
    def isEndPosition(self):
        index = self.currPosition['index']
        if index == (len(self.positionList) - 1):
            return True 
        return False

    def updateStatus(self, quickMode):

        position = self.currPosition
    
        if 'move' in position:
            move = position['move']
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
                msg = f"吃{cchess.fench_to_text(move.captured)}"
            else:
                self.playSound('move', quickMode)
                msg = ""

            self.statusBar().showMessage(msg)

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
        
        #开局库        
        query = self.openBook.getMoves(fen)    
        if query:
            openbook_actions = query['actions']
        else:
            openbook_actions = OrderedDict()

        #本地库库        
        query = Globl.localBook.getMoves(fen)
        if query:
            local_actions = query['actions']
        else:
            local_actions = OrderedDict()

        for iccs, act in local_actions.items():
            if iccs in openbook_actions:
                act['score'] = openbook_actions[iccs]['score']
            act['mark'] = "*"
            
        #合并最终的输出  
        final_actions = openbook_actions.copy()
        #合并本地库与开局库
        for iccs, l_act in local_actions.items():
            if iccs in final_actions:
                f_act = final_actions[iccs]
                f_act.update(l_act)
            else:
                final_actions[iccs] = l_act
            
        '''        
        #更新分数 
        for act in final_actions.values():
            if 'new_fen' not in act:
                continue
            new_fen = act['new_fen']
            if new_fen not in Globl.fenCache:
                continue
            info= Globl.fenCache[new_fen]
            if 'score' not in info:
                continue
            act['score'] = info['score']
        '''

        self.boardActions = final_actions
        self.actionsView.updateActions(self.boardActions)
        

    def onCloudQueryResult(self, query):
        
        def sort_key(item):
            if 'score' in item[1]:
                return item[1]['score']
            else:
                return 0

        if not query or not self.positionList:
            return
        
        fen = query['fen']
        if fen not in self.fenPosDict:
            return

        move_color = cchess.get_move_color(fen)
            
        if (self.queryMode == QueryMode.CloudFirst) or (self.reviewMode == ReviewMode.ByCloud):
            self.updateFenCache(query)
            new_actions = {}
            posi = self.fenPosDict[fen]
            if posi == self.currPosition: #查询返回的结果与当前局面一致
                actions = query['actions']
                for iccs, act in actions.items():
                    #print(iccs, act)
                    if iccs in self.boardActions:
                        old_act = self.boardActions.pop(iccs)
                        old_act.update(act)
                        new_actions[iccs] = old_act 
                    else:    
                        new_actions[iccs] = act
                        
            x = OrderedDict(sorted(new_actions.items(), key = sort_key, reverse = (move_color == cchess.RED)))
            for iccs, act in self.boardActions.items():
                 x[iccs] = act
            
            self.boardActions = x     
            self.actionsView.updateActions(self.boardActions)

            if self.reviewMode == ReviewMode.ByCloud:
                self.onReviewGameStep()
    
    def showBestHint(self, fenInfo):
        best = []
        
        move = fenInfo.get('iccs', None)
        if not move:
            return
        best.append(cchess.iccs2pos(move))    
        
        ponder = fenInfo.get('ponder', None)
        if ponder:
            best.append(cchess.iccs2pos(ponder))
        
        self.boardView.showMoveHint(best)

    #-----------------------------------------------------------
    #Engine 输出
    def onTryEngineMove(self, engine_id, fenInfo):
        
        self.isRunEngine = False
        
        fen = trim_fen(fenInfo['fen'])
        logging.debug(f'Engine[{engine_id}] BestMove {fenInfo}' )
        
        if (self.gameMode != GameMode.EndGame) and ((self.queryMode == QueryMode.EngineFirst) or (self.reviewMode == ReviewMode.ByEngine)) :
            self.updateFenCache(fenInfo)

        if self.reviewMode == ReviewMode.ByEngine :
            self.onReviewGameStep()
            return
        
        move_color = self.board.get_move_color()
        
        #只有在最后一行时，引擎才会触发走子
        if self.isEndPosition() and (self.engineRunColor[move_color] == engine_id):
            self.onMoveGo(fenInfo['iccs'])
        else:
            if (self.queryMode == QueryMode.EngineFirst):
                self.showBestHint(fenInfo)
            
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
        currmove = fenInfo.get('currmove', None)
        if currmove:
            self.boardView.showMoveHint([cchess.iccs2pos(currmove)])
            return

        moves = fenInfo.get('moves', None)
        if not moves:
            return
        
        iccs = moves[0]
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
        for act in actions.values():
            if act['diff'] >= -5:
                best_next.append(act['iccs'])
        if best_next:
            Globl.fenCache[fen]['best_next'] = best_next 

        #本着法的其他更好的招法    
        for act in actions.values():
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
            move_color = cchess.get_move_color(fen)    
            fen_prev = fenInfo['fen_prev']
            if fen_prev in Globl.fenCache :
                prevInfo = Globl.fenCache[fen_prev]
                if 'score' in prevInfo:
                    diff = prevInfo['score'] - fenInfo['score']
                    if move_color == cchess.BLACK:
                        diff = -diff 
                    fenInfo['diff'] = diff
                    if (diff < -40) and ('best_next' in prevInfo):
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
                
        move_color = cchess.get_move_color(fen)
        
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
        
 
    #------------------------------------------------------------------------------
    #UI Events
    def onTryBoardMove(self,  move_from,  move_to):
        if not self.isEndPosition():
            step_index = self.currPosition['index']
            self.removeHistoryFollow(step_index)

        move_iccs = cchess.pos2iccs(move_from, move_to)
        self.onMoveGo(move_iccs)
        
    def onTryBookMove(self, moveInfo):
        
        if not self.isEndPosition():
            return

        #判断重复局面次数，大于2次被认为是循环导入
        iccs = moveInfo['iccs']
        fen = moveInfo.get('fen', None)
        if fen: 
            fen = moveInfo['fen']
            board = ChessBoard(fen)
            
            move = board.move_iccs(iccs)
            if move is None:
                return

            board.next_turn()
            new_fen = board.to_fen()
            
            fen_count = 0
            for position in self.positionList:
                if new_fen == position['fen']:
                    fen_count += 1
            
            #重复的局面次数过多，不再导入
            if fen_count >= 2:
                return

        self.onMoveGo(iccs)
                
    def onBoardRightMouse(self, is_mouse_pressed):
        
        best_next = []    

        if is_mouse_pressed:

            fen = self.currPosition['fen']
            if (fen not in Globl.fenCache) or ('best_next' not in Globl.fenCache[fen]):
                return

            iccs_list = Globl.fenCache[fen]['best_next']
            best_next = [cchess.iccs2pos(x)  for x in iccs_list]

        self.boardView.showMoveHint(best_next)    

    def removeHistoryFollow(self, step_index):

        for position in reversed(self.positionList):
            fen = position['fen']
            index = position['index']
            if index <= step_index:
                break
            if fen in self.fenPosDict:    
                del self.fenPosDict[fen]
            self.historyView.inner.onRemovePosition(position)
                
        self.positionList = self.positionList[:step_index + 1]
        self.currPosition = self.positionList[-1]
        
        if len(self.positionList) <= 1:
            self.isNeedSave = False

        self.updateEcco()

    def onSelectHistoryPosition(self, move_index):

        if self.reviewMode:
            return
        
        if (move_index < 0) or (move_index >= len(self.positionList)):
            return

        #重复触发同一个事件，忽略
        if move_index == self.currPosition['index']:
            return

        self.currPosition = self.positionList[move_index]  
        self.changePositionSignal.emit(False, False)
    
    
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
            self.currPosition = position
            self.changePositionSignal.emit(False, True)
            QApplication.processEvents()

            if self.reviewMode == ReviewMode.ByCloud:
                self.cloudQuery.startQuery(position)
            elif self.reviewMode == ReviewMode.ByEngine:
                self.runEngine(position)
        else:
            self.onReviewGameEnd()
        
    def onReviewGameEnd(self, isCanceled=False):
        
        self.historyView.inner.reviewByCloudBtn.setText('云库复盘')
        self.historyView.inner.reviewByEngineBtn.setText('引擎复盘')
        self.engineView.onReviewEnd(self.reviewMode)
        
        if not isCanceled:
            msgbox = TimerMessageBox("  复盘分析完成。  ", timeout=1)
            msgbox.exec()
        
        self.reviewMode = None
        self.cloudModeBtn.setEnabled(True)
        self.engineModeBtn.setEnabled(True)
        
            
    def setQueryMode(self, mode):
        
        if mode == self.queryMode: #模式未变
            return

        self.queryMode = mode

        #极少数情况下棋盘是未初始化的
        if self.currPosition:
                self.localSearch(self.currPosition)

        if self.queryMode == QueryMode.EngineFirst:
            self.historyView.inner.reviewByEngineBtn.setEnabled(True)
            self.historyView.inner.reviewByCloudBtn.setEnabled(False)
        
        elif self.queryMode == QueryMode.CloudFirst:
            self.historyView.inner.reviewByEngineBtn.setEnabled(False)
            self.historyView.inner.reviewByCloudBtn.setEnabled(True)
            #极少数情况下棋盘是未初始化的
            if self.currPosition:
                self.cloudQuery.startQuery(self.currPosition)
        
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
        if (self.gameMode != GameMode.EndGame) and self.isNeedSave:
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

        if (self.gameMode in [GameMode.Free, GameMode.Fight]) and self.isNeedSave:
            steps = len(self.positionList) - 1
            if not self.getConfirm(f"当前棋谱已经走了 {steps} 步, 您确定要从新开始吗?"):
                return
        
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
            Globl.fenCache[fen_t] = {'score': 39999, 'best_next': [iccs, ]}
            
        self.isNeedSave = False
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

        self.isNeedSave = False
        self.updateTitle(name)

    def loadBookmark(self, name, position):
        if self.isNeedSave :
            steps = len(self.positionList) - 1
            if not self.getConfirm(f"当前棋谱已经走了 {steps} 步, 您确定要加载收藏并丢弃当前棋谱吗?"):
                return 
            
        self.bookmarkView.setEnabled(False)

        fen = position['fen']        
        self.initGame(fen)
        
        moves = position.get('moves', [])
        for iccs in moves:
            self.onMoveGo(iccs, quickMode = True)
                    
        self.isNeedSave = False
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
            self.bookmarkView.setFocus(Qt.TabFocusReason)

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

    def onCaptureBoard(self):
        self.hide()
        self.snippingWidget.start()

    def onSnippingCompleted(self, img):
        self.show()
        self.setWindowState(Qt.WindowActive)
        dlg = ImageToBoardDialog(self)
        dlg.edit(img)

    def onSearchBoard(self):
        dlg = PositionEditDialog(self)
        new_fen = dlg.edit('')
        if new_fen:
            self.initGame(new_fen)

    def onSetupEngine(self):
        dlg = EngineConfigDialog(self)
        dlg.exec()
    
    def onQuickStart(self):
        pass

    def onOpenFile(self):
        options = QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog

        fileName, _ = QFileDialog.getOpenFileName(
            self, "打开文件", self.lastOpenFolder, "象棋谱(库)文件(*.pgn;*.xqf;*.cbr;*.cbl);;", options=options)

        if not fileName:
            return

        ext = Path(fileName).suffix.lower()
        
        if ext in GAME_FILE_TYPES:
            self.openFile(fileName)
        elif ext in GAME_LIB_TYPES:
            self.openLibFile(fileName)
        else:
            raise Exception(f'Can not open file {fileName}') 

    def onOpenEndGameFile(self):
        options = QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog

        fileName, _ = QFileDialog.getOpenFileName(
            self, "打开文件", self.lastOpenFolder, "残局挑战库文件(*.csv);;", options=options)

        if not fileName:
            return

            
    def onSaveFile(self):
        
        if not self.positionList:
            return

        fileNameDefault = f"{self.positionList[0].get('ecco', 'Unknown')}.pgn"
       
        options = QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog

        fileName, _ = QFileDialog.getSaveFileName(
            self,
            "保存对局文件",
            fileNameDefault,
            "象棋通用格式文件(*.pgn)",
            options=options)
        
        if not fileName:
            return

        self.saveToFile(fileName)
        self.lastOpenFolder = str(Path(fileName).parent)
        
    def openFile(self, file_name):

        fileName = Path(file_name)
        game = Game.read_from(fileName)
        if not game:
            msg = f"读取棋谱库文件【{fileName}】错误：{fileName}"
            logging.error(msg)
            msgbox = TimerMessageBox(msg)
            msgbox.exec()
            return
        self.gamelibView.hide()
        self.loadBookGame(fileName.name, game)
        self.lastOpenFolder = str(fileName.parent)
        
    def openLibFile(self, file_name):

        fileName = Path(file_name)
        try:
            game_lib = Game.read_from_lib(fileName)
        except Exception as e:
            msg = f"读取棋谱库文件【{fileName}】错误：{e}"
            logging.error(msg)
            msgbox = TimerMessageBox(msg)
            msgbox.exec()
            return

        self.gamelibView.updateGameLib(game_lib)
        self.gamelibView.show()

        self.lastOpenFolder = str(fileName.parent)
    
    def saveToFile(self, file_name):

        try:
            board = ChessBoard(self.positionList[0]['fen'])
            game = Game(board.copy())

            for pos in self.positionList[1:]:
                #print(pos['index'], pos['iccs'])
                move = board.move_iccs(pos['iccs'])
                game.append_next_move(move)
                board.next_turn()

            game.save_to(file_name)
            self.isNeedSave = False
        except Exception as e:
            msg = f"保存文件[{file_name}]出错：{traceback.format_exc()}"
            logging.error(msg)
            msgbox = TimerMessageBox(msg)
            msgbox.exec()
            return False    
        return True

    def onUseOpenBookFile(self):
        options = QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog

        fileName, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "", "YFK格式开局库(*.yfk);;所有文件(*.*)", options=options)

        if not fileName:
            return

        fileName = Path(fileName)

        self.loadOpenBook(fileName)
    
    def onChangedSkin(self, action):
        skin = action.text()
        self.changeSkin(skin)
        
    def changeSkin(self, skin):

        if skin == self.skin:
            return True

        if skin in self.skins:
            skin_folder = self.skins[skin]['Folder']
            if self.boardView.fromSkinFolder(skin_folder):
                self.skins[skin]['action'].setChecked(True)
                self.skin = skin
                return True
                    
        return False            

    #------------------------------------------------------------------------------
    #Drag & Drop
    def dragEnterEvent(self, event):

        if self.gameMode != GameMode.Free:
            return

        #TODO 先询问是否丢弃当前未保存的内容    
        urls = event.mimeData().urls()
        fileName = Path(urls[0].toLocalFile())
        ext = fileName.suffix.lower()
        if ext in GAME_TYPES_ALL: # '.jpg', '.png', '.bmp', '.jpeg']:
            event.acceptProposedAction()

    def dropEvent(self, event):

        if self.gameMode != GameMode.Free:
            return
        
        fileName = Path(event.mimeData().urls()[0].toLocalFile())
        ext = fileName.suffix.lower()
        if ext in GAME_FILE_TYPES:
            self.openFile(fileName)
            event.acceptProposedAction()

        elif ext in GAME_LIB_TYPES:
            self.openLibFile(fileName)
            event.acceptProposedAction()
    
    #------------------------------------------------------------------------------
    #UI Base
    def createActions(self):

        self.openFileAct = QAction(self.style().standardIcon(
                                    QStyle.SP_FileDialogStart),
                                   "打开棋谱",
                                   self,
                                   statusTip="打开棋谱（库）文件",
                                   triggered=self.onOpenFile)
        
        self.openEndGameFileAct = QAction(self.style().standardIcon(
                                    QStyle.SP_FileDialogStart),
                                   "打开残局挑战库",
                                   self,
                                   statusTip="打开残局挑战库文件（.CSV）",
                                   triggered=self.onOpenEndGameFile)

        self.useOpenBookAct = QAction(self.style().standardIcon(
                                    QStyle.SP_FileDialogStart),
                                   "开局库选择",
                                   self,
                                   statusTip="选择开局库文件（yfk格式）",
                                   triggered=self.onUseOpenBookFile)

        self.saveFileAct = QAction(self.style().standardIcon(
            QStyle.SP_DialogSaveButton),
                                   "保存棋谱",
                                   self,
                                   statusTip="保存棋谱文件(PGN 格式)",
        
                                   triggered=self.onSaveFile)
        self.setupEngineAct = QAction( #QIcon(':ImgRes/openbook.png'),
                                     "引擎设置",
                                     self,
                                     statusTip="设置引擎参数",
                                     triggered=self.onSetupEngine)

        
        self.doOpenBookAct = QAction(QIcon(':ImgRes/openbook.png'),
                                     "自由练习",
                                     self,
                                     statusTip="自由练习",
                                     triggered=self.onDoFreeGame)

        self.doEndGameAct = QAction(QIcon(':ImgRes/endbook.png'),
                                    "杀法挑战",
                                    self,
                                    statusTip="入局杀法挑战",
                                    triggered=self.onDoEndGame)

        self.doRobotAct = QAction(QIcon(':ImgRes/robot.png'),
                                   "人机战斗",
                                   self,
                                   statusTip="人机战斗",
                                   triggered=self.onDoRobot)
        self.doOnlineAct = QAction(QIcon(':ImgRes/online.png'),
                                   "连线分析",
                                   self,
                                   statusTip="连线分析",
                                   triggered=self.onDoOnline)

        self.restartAct = QAction(QIcon(':ImgRes/restart.png'),
                                  "重新开始",
                                  self,
                                  statusTip="重新开始",
                                  triggered=self.onRestartGame)

        self.editBoardAct = QAction(QIcon(':ImgRes/edit.png'),
                                    "自定局面",
                                    self,
                                    statusTip="从自定局面开始",
                                    triggered=self.onEditBoard)

        self.searchBoardAct = QAction(QIcon(':ImgRes/search.png'),
                                      "搜索局面",
                                      self,
                                      statusTip="从对局库中搜索局面",
                                      triggered=self.onSearchBoard)
        
        self.quickStartAct = QAction( #QIcon(':ImgRes/search.png'),
                                      "快速开局",
                                      self,
                                      statusTip="快速走到某个开局",
                                      triggered=self.onQuickStart)
    
        self.captureBoardAct = QAction(QIcon(':ImgRes/search.png'),
                                      "屏幕截图",
                                      self,
                                      statusTip="从屏幕截图识别局面",
                                      triggered=self.onCaptureBoard)

        
        self.myGamesAct = QAction(QIcon(':ImgRes/mybook.png'),
                                  "我的对局库",
                                  self,
                                  statusTip="我的对局库",
                                  triggered=self.onShowMyGames)
        
        self.bookmarkAct = QAction(QIcon(':ImgRes/bookmark.png'),
                                   "我的收藏",
                                   self,
                                   statusTip="我的收藏",
                                   triggered=self.onShowBookmark)

        self.exitAct = QAction(QIcon(':ImgRes/exit.png'),
                               "退出程序",
                               self,
                               shortcut="Ctrl+Q",
                               statusTip="退出应用程序",
                               triggered=QApplication.closeAllWindows)

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
        self.fileMenu.addAction(self.openEndGameFileAct)
        self.fileMenu.addSeparator()

        #self.fileMenu.addAction(self.useOpenBookAct)
        #self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.exitAct)

        self.menuBar().addSeparator()

        self.showMoveSoundAct = QAction('走子音效', checkable=True)
        self.showMoveSoundAct.setChecked(
            True if self.soundVolume > 0 else False)
        self.showMoveSoundAct.toggled.connect(self.onShowMoveSound)

        self.winMenu = self.menuBar().addMenu("窗口")
        self.winMenu.addAction(self.historyView.toggleViewAction()) 
        self.winMenu.addAction(self.engineView.toggleViewAction())
        #self.winMenu.addAction(self.moveDbView.toggleViewAction())
        self.winMenu.addAction(self.actionsView.toggleViewAction())
        self.winMenu.addAction(self.showMoveSoundAct)

        self.skinMenu = self.menuBar().addMenu("皮肤")
        self.skinMenu.triggered.connect(self.onChangedSkin)

        skinActionGroup = QActionGroup(self)
        skinActionGroup.setExclusive(True)
        
        for index, skin in enumerate(self.skins.keys()):
            action = QAction(skin, self)
            action.setCheckable(True)
            if index == 0:
                action.setChecked(True)
            skinActionGroup.addAction(action)
            self.skinMenu.addAction(action) 
            self.skins[skin]['action'] = action

        self.helpMenu = self.menuBar().addMenu("帮助")
        #self.helpMenu.addAction(self.upgradeAct)
        self.helpMenu.addAction(self.aboutAct)

    def createToolBars(self):

        self.fileBar = self.addToolBar("File")
        self.fileBar.setObjectName("File")

        self.fileBar.addAction(self.setupEngineAct)
        self.fileBar.addAction(self.openFileAct)
        self.fileBar.addAction(self.saveFileAct)
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
        self.gameBar.addAction(self.captureBoardAct)
        #self.gameBar.addAction(self.searchBoardAct)

        self.flipBox = QCheckBox()  #"翻转")
        self.flipBox.setIcon(QIcon(':ImgRes/up_down.png'))
        self.flipBox.setToolTip('上下翻转')
        self.flipBox.stateChanged.connect(self.onFlipBoardChanged)

        self.mirrorBox = QCheckBox()  #"镜像")
        self.mirrorBox.setIcon(QIcon(':ImgRes/left_right.png'))
        self.mirrorBox.setToolTip('左右镜像')
        self.mirrorBox.stateChanged.connect(self.onMirrorBoardChanged)

        self.cloudModeBtn = QRadioButton("云库优先")
        #self.cloudModeBtn.setIcon(QIcon(':ImgRes/cloud.png'))
        self.cloudModeBtn.setToolTip('云库优先模式')
        self.cloudModeBtn.toggled.connect(lambda: self.setQueryMode(QueryMode.CloudFirst))

        self.engineModeBtn = QRadioButton("引擎优先") 
        #self.engineModeBtn.setIcon(QIcon(':ImgRes/engine.png'))
        self.engineModeBtn.setToolTip('引擎优先模式')
        self.engineModeBtn.toggled.connect(lambda: self.setQueryMode(QueryMode.EngineFirst))
        
        self.modeBtnGroup = QButtonGroup(self)
        self.modeBtnGroup.addButton(self.cloudModeBtn, 1)      # ID 1
        self.modeBtnGroup.addButton(self.engineModeBtn, 2)      # ID 2

        self.showBestBox = QCheckBox('最佳提示')  #"最佳提示")
        self.showBestBox.setIcon(QIcon(':ImgRes/info.png'))
        self.showBestBox.setChecked(True)
        self.showBestBox.setToolTip('提示最佳走法')
        self.showBestBox.stateChanged.connect(self.onShowBestMoveChanged)
    
        self.showScoreBox = QCheckBox('分数')  #"最佳提示")
        #self.showScoreBox.setIcon(QIcon(':ImgRes/info.png'))
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
        #self.showBar.addAction(self.quickStartAct)
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
        if self.isNeedSave and (self.gameMode in [GameMode.Free, GameMode.Fight]):
            if not self.getConfirm(f"当前棋谱已经走了 {steps} 步, 尚未保存，您确定要关闭程序吗?"):
                event.ignore()

        self.writeSettings()
        Globl.engineManager.quit()
        time.sleep(0.6)
        
        self.openBook.close()
        #Globl.bookmarkStore.close()
        Globl.endbookStore.close()
        Globl.localBook.close()

    def readSettingsBeforeGameInit(self):
        self.settings = QSettings('XQSoft', Globl.app.APP_NAME)
        
        if Globl.app.isClean:
            self.settings.clear()

        self.restoreGeometry(self.settings.value("geometry", QByteArray()))
        self.restoreState(self.settings.value("windowState", QByteArray()))
        
        self.soundVolume = self.settings.value("soundVolume", 30)
        self.showMoveSoundAct.setChecked(self.soundVolume > 0)

        skin = self.settings.value("boardSkin", DEFAULT_SKIN)
        if skin != DEFAULT_SKIN:
            self.changeSkin(skin)
                    
        self.savedGameMode = self.settings.value("gameMode", GameMode.Free)
        
        #self.openBookFile = Path(self.settings.value("openBookFile", str(Path('game','openbook.yfk'))))
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
        
        #self.settings.setValue("openBookFile", self.openBookFile)
        self.settings.setValue("lastOpenFolder", self.lastOpenFolder)
        self.settings.setValue("boardSkin", self.skin)
        
        self.engineView.writeSettings(self.settings)
        self.endBookView.writeSettings(self.settings)

    def about(self):
        QMessageBox.about(
            self, f"关于 {Globl.app.APP_NAME}",
            f"{Globl.app.APP_NAME_TEXT} Version {release_version}\n个人棋谱管家.\n 云库支持：https://www.chessdb.cn/\n 引擎支持：皮卡鱼(https://pikafish.org/)\n\n 联系作者：1053386709@qq.com\n QQ 进群：101947824\n"
        )

#-----------------------------------------------------#
