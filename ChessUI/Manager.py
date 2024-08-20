# -*- coding: utf-8 -*-

from PySide6 import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from cchess import *

from .Utils import *

#-----------------------------------------------------#
class EngineConfig():
    def __init__(self, engine):
        self.engine = engine
        self.fen = None
        self.fen_engine = None
        self.go_param = {}
        self.score_move = {}

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
        self.econf = None
        self.stoped = True
        self.isReady = False

    def get_config(self):
        return self.econf.go_param.copy()

    def set_config(self, params):
        self.econf.go_param = params
    
    def update_config(self, params):
        self.econf.go_param.update(params)

    def load_engine(self, engine_path, engine_type):
        if engine_type == 'uci':
            engine = UciEngine('')
        elif engine_type == 'ucci':
            engine = UcciEngine('')
        else:
            raise Exception('目前只支持[uci, ucci]类型的引擎。') 

        if engine.load(engine_path):
            self.engine = engine
            self.econf = EngineConfig(engine)
            return True 
        else:
            return False   
    def set_engine_option(self, name, value):
        
        if not self.isReady:
            return False

        self.engine.set_option(name, value)
        
        return True
        
    def go_from(self, fen_engine, fen = None):
        
        if not self.isReady:
            return True
        
        if not fen:
            fen = fen_engine

        #print(fen)
        #跳过不合理的fen,免得引擎误报
        if (EMPTY_BOARD in fen_engine) or (EMPTY_BOARD in fen):
            return False

        self.econf.score_move.clear()
        self.econf.fen_engine = fen_engine
        self.econf.fen = fen

        return self.engine.go_from(fen_engine, self.econf.go_param)
    

    def stop_thinking(self):
        self.engine.stop_thinking()
        time.sleep(0.2)
        self.engine.handle_msg_once()

    def start(self):
        self.thread = ThreadRunner(self)
        self.thread.start()

    def stop(self):
        self.stoped = True

    def run(self):
        self.stoped = False
        while not self.stoped:
            self.run_once()
            time.sleep(0.1)
            self.engine.stop_thinking()

    def run_once(self):
        conf = self.econf
        engine = self.engine

        if conf.fen:
            move_color = get_move_color(conf.fen) 
        
        engine.handle_msg_once()
        
        while not engine.move_queue.empty():
            eg_out = engine.move_queue.get()
            #print(eg_out)
            action = eg_out['action']
            if action == 'ready':
                self.isReady = True
                self.readySignal.emit(self.id, engine.ids['name'], engine.options)
            elif action == 'bestmove':
                ret = {'fen': conf.fen, }
                if 'move' in eg_out:
                    iccs = eg_out['move']
                    
                    ret['iccs'] = iccs
                    ret['best_move'] = [iccs, ]
                    
                    if iccs in conf.score_move:
                        score_best = conf.score_move[iccs] 
                        if move_color == BLACK:
                            score_best = -score_best
                        ret['score'] = score_best
                    
                        m = ChessBoard(conf.fen).move_iccs(iccs)
                        if not m:
                            continue

                        new_fen = m.board_done.to_fen()
  
                        ret['actions'] = [{'iccs': iccs, 'score': score_best, 'diff': 0, 'new_fen': new_fen}]
                    #ret['raw_msg'] = eg_out['raw_msg']

                self.moveBestSignal.emit(self.id, ret)
            elif action == 'dead':  #被将死
                eg_out['fen'] = conf.fen
                self.checkmateSignal.emit(self.id, eg_out)
            elif action == 'info_move':
                eg_out['fen'] = conf.fen
                if len(eg_out['move']) == 0:
                    continue
                eg_out['moves'] = eg_out['move']    
                move_iccs = eg_out['move'][0]
                if 'score' in eg_out:
                    conf.score_move[move_iccs] = eg_out['score']
                    eg_out['actions'] = []
                
                    if move_color == BLACK:
                        eg_out['score'] = -eg_out['score']
                            
                self.moveInfoSignal.emit(self.id, eg_out)
            elif action == 'info':
                #print(eg_out)
                pass


#-----------------------------------------------------#
