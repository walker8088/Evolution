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
        self.fen_last = None
        self.fen_engine = None
        self.go_param = {}
        self.score_move = {}

#-----------------------------------------------------#
class EngineManager(QObject):

    engine_ready_signal = Signal(int, str, list)
    best_move_signal = Signal(int, dict)
    move_probe_signal = Signal(int, dict)
    checkmate_signal = Signal(int, dict)

    def __init__(self, parent):
        super().__init__()

        self.parent = parent
        self.econf = []
        self.stoped = True
        #self.score_mode = False
        
    def get_config(self, engine_id):
        return self.econf[engine_id].go_param.copy()

    def set_config(self, engine_id, params):
        self.econf[engine_id].go_param = params
    
    def update_config(self, engine_id, params):
        self.econf[engine_id].go_param.update(params)

    def load_engine(self, engine_path, engine_type = 'UCI'):
        
        if engine_type == 'UCI':
            engine = UciEngine('')
        elif engine_type == 'UCCI':
            engine = UcciEngine('')
        else:
            raise Exception('Engine Type Must be in [UCI, UCCI]') 

        if engine.load(engine_path):
            self.econf.append(EngineConfig(engine))
            return True
        else:
            return False
    
    def set_engine_option(self, engine_id, name, value):
        if (engine_id < 0) or (engine_id >= len(self.econf)):
            return False
        
        engine = self.econf[engine_id].engine
        engine.set_option(name, value)
        return True
        
    def go_from(self, engine_id, fen_engine, fen):
        if (engine_id < 0) or (engine_id >= len(self.econf)):
            return False

        #print(fen)
        #跳过不合理的fen,免得引擎误报
        if (EMPTY_BOARD in fen_engine) or (EMPTY_BOARD in fen):
            return False

        conf = self.econf[engine_id]    
        conf.score_move.clear()
        conf.fen_engine = fen_engine
        conf.fen = fen

        return self.econf[engine_id].engine.go_from(fen_engine, conf.go_param)
            
    def stop_thinking(self):
        for engine_id, conf in enumerate(self.econf):
            conf.engine.stop_thinking()
        time.sleep(0.1)
        conf.engine.handle_msg_once()
        time.sleep(0.1)
        conf.engine.handle_msg_once()

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
        for engine_id, conf in enumerate(self.econf):
            conf.engine.stop_thinking()

    def run_once(self):
        for engine_id, conf in enumerate(self.econf):
            engine = conf.engine
            engine.handle_msg_once()
            while not engine.move_queue.empty():
                eg_out = engine.move_queue.get()
                #print(eg_out)
                action = eg_out['action']
                if action == 'ready':
                    self.engine_ready_signal.emit(engine_id,
                                                  engine.ids['name'], engine.options)
                elif action == 'bestmove':
                    if 'move' in eg_out:
                        move_iccs = eg_out['move']
                        #print(move_iccs, score_move)
                        if move_iccs in conf.score_move:
                            eg_out['score'] = conf.score_move[move_iccs]
                    eg_out['move_scores'] = conf.score_move
                    eg_out['fen'] = conf.fen
                    self.best_move_signal.emit(engine_id, eg_out)
                elif action == 'dead':  #被将死
                    eg_out['fen'] = conf.fen
                    self.checkmate_signal.emit(engine_id, eg_out)
                elif action == 'info_move':
                    eg_out['fen'] = conf.fen
                    if len(eg_out['move']) == 0:
                        continue
                    move_iccs = eg_out['move'][0]
                    if 'score' in eg_out:
                        conf.score_move[move_iccs] = eg_out['score']
                    self.move_probe_signal.emit(engine_id, eg_out)
                elif action == 'info':
                    #print(eg_out)
                    pass


#-----------------------------------------------------#
