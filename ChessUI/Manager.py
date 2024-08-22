# -*- coding: utf-8 -*-

import time
import logging

#import threading

#from PySide6 import *
from PySide6.QtCore import Signal, QObject
#from PySide6.QtGui import *

import cchess
from cchess import ChessBoard, UcciEngine, UciEngine, get_move_color

from .Utils import ThreadRunner

#-----------------------------------------------------#
class EngineManager(QObject):

    readySignal = Signal(int, str, list)
    moveBestSignal = Signal(int, dict)
    moveInfoSignal = Signal(int, dict)
    checkmateSignal = Signal(int, dict)

    def __init__(self, parent, id):
        super().__init__()
        self.id = id
        self.parent = parent

        self.fen = None
        self.fen_engine = None
        self.score_move = {}
        
        self.isRunning = False
        self.isReady = False

    def loadEngine(self, engine_path, engine_type):
        if engine_type == 'uci':
            engine = UciEngine('')
        elif engine_type == 'ucci':
            engine = UcciEngine('')
        else:
            raise Exception('目前只支持[uci, ucci]类型的引擎。') 

        if engine.load(engine_path):
            self.engine = engine
            return True 
        else:
            return False

    def setOption(self, name, value):
        
        if not self.isReady:
            return False

        logging.info(f'Engine[{self.id}] setOption: {name} = {value}')
        self.engine.set_option(name, value)
        return True
        
    def goFrom(self, fen_engine, fen = None, params = {}):
        
        if not self.isReady:
            return True
        
        if not fen:
            fen = fen_engine

        #print(fen)
        #跳过不合理的fen,免得引擎误报
        if (cchess.EMPTY_BOARD in fen_engine) or (cchess.EMPTY_BOARD in fen):
            return False

        self.score_move.clear()
        self.fen_engine = fen_engine
        self.fen = fen
        
        logging.info(f'Engine[{self.id}] goFrom: {fen} {params}')
        
        return self.engine.go_from(fen_engine, params)
    
    def stopThinking(self):
        if not self.isReady:
            return True
            
        self.engine.stop_thinking()
        time.sleep(0.2)
        self.engine.handle_msg_once()
        return True 

    def start(self):
        self.thread = ThreadRunner(self)
        self.thread.start()

    def stop(self):
        self.isRunning = False
    
    def quit(self):
        
        if not self.isReady:
            return 
        
        self.stop()
        time.sleep(0.2)
        self.engine.quit()

    def run(self):
        self.isRunning = True
        while self.isRunning:
            self.runOnce()
            time.sleep(0.1)
        #self.engine.stop_thinking()

    def runOnce(self):

        if self.fen:
            move_color = get_move_color(self.fen) 
        
        self.engine.handle_msg_once()
        
        while not self.engine.move_queue.empty():
            eg_out = self.engine.move_queue.get()
            #print(eg_out)
            action = eg_out['action']
            if action == 'ready':
                self.isReady = True
                self.readySignal.emit(self.id, self.engine.ids['name'], self.engine.options)
            elif action == 'bestmove':
                ret = {'fen': self.fen, }
                if 'move' in eg_out:
                    iccs = eg_out['move']
                    
                    ret['iccs'] = iccs
                    ret['best_move'] = [iccs, ]
                    
                    if iccs in self.score_move:
                        score_best = self.score_move[iccs] 
                        if move_color == cchess.BLACK:
                            score_best = -score_best
                        ret['score'] = score_best
                    
                        m = ChessBoard(self.fen).move_iccs(iccs)
                        if not m:
                            continue

                        new_fen = m.board_done.to_fen()
  
                        ret['actions'] = [{'iccs': iccs, 'score': score_best, 'diff': 0, 'new_fen': new_fen}]
                    #ret['raw_msg'] = eg_out['raw_msg']

                self.moveBestSignal.emit(self.id, ret)
            elif action == 'dead':  #被将死
                eg_out['fen'] = self.fen
                self.checkmateSignal.emit(self.id, eg_out)
            elif action == 'info_move':
                eg_out['fen'] = self.fen
                if len(eg_out['move']) == 0:
                    continue
                eg_out['moves'] = eg_out['move']    
                move_iccs = eg_out['move'][0]
                if 'score' in eg_out:
                    self.score_move[move_iccs] = eg_out['score']
                    eg_out['actions'] = []
                
                    if move_color == cchess.BLACK:
                        eg_out['score'] = -eg_out['score']
                            
                self.moveInfoSignal.emit(self.id, eg_out)
            elif action == 'info':
                #print(eg_out)
                pass


#-----------------------------------------------------#
