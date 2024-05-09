# -*- coding: utf-8 -*-

from PySide6 import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from cchess import *

from .Utils import *

#-----------------------------------------------------#
class EngineManager(QObject):

    engine_ready_signal = Signal(int, str, list)
    best_move_signal = Signal(int, dict)
    move_probe_signal = Signal(int, dict)
    checkmate_signal = Signal(int, dict)

    def __init__(self, parent):
        super().__init__()

        self.parent = parent
        self.engines = []
        self.engine_fens = []
        self.go_param = []
        self.stoped = True
        #self.score_mode = False
        self.score_moves = []

    def get_config(self, engine_id):
        return self.go_param[engine_id].copy()

    def set_config(self, engine_id, params):
        self.go_param[engine_id] = params
    
    def update_config(self, engine_id, params):
        self.go_param[engine_id].update(params)

    def load_engine(self, engine_path):
        engine = UciEngine('')

        if engine.load(engine_path):
            self.engines.append(engine)
            self.score_moves.append({})
            self.go_param.append({})
            return True
        else:
            return False
    
    def set_engine_option(self, engine_id, name, value):
        if (engine_id < 0) or (engine_id >= len(self.engines)):
            return False
        
        engine = self.engines[engine_id]
        engine.set_option(name, value)
        return True
        
    def go_from(self, engine_id, fen):
        if (engine_id < 0) or (engine_id >= len(self.engines)):
            return False

        #print(fen)
        #跳过不合理的fen,免得引擎误报
        if EMPTY_BOARD in fen:
            return

        self.score_moves[engine_id].clear()

        params = self.go_param[engine_id]
        self.engines[engine_id].go_from(fen, params)

    def stop_thinking(self):
        for engine_id, engine in enumerate(self.engines):
            engine.stop_thinking()
        time.sleep(0.1)
        engine.handle_msg_once()
        time.sleep(0.1)
        engine.handle_msg_once()

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
        for engine_id, engine in enumerate(self.engines):
            engine.stop_thinking()

    def run_once(self):
        for engine_id, engine in enumerate(self.engines):
            engine.handle_msg_once()
            while not engine.move_queue.empty():
                eg_out = engine.move_queue.get()
                #print(eg_out)
                action = eg_out['action']
                score_move = self.score_moves[engine_id]
                if action == 'ready':
                    self.engine_ready_signal.emit(engine_id,
                                                  engine.ids['name'], engine.options)
                elif action == 'bestmove':
                    if 'move' in eg_out:
                        move_iccs = eg_out['move']
                        #print(move_iccs, score_move)
                        if move_iccs in score_move:
                            eg_out['score'] = score_move[move_iccs]
                    eg_out['move_scores'] = self.score_moves[engine_id]
                    self.best_move_signal.emit(engine_id, eg_out)
                elif action == 'dead':  #被将死
                    self.checkmate_signal.emit(engine_id, eg_out)
                elif action == 'info_move':
                    if len(eg_out['move']) == 0:
                        continue
                    move_iccs = eg_out['move'][0]
                    if 'score' in eg_out:
                        score_move[move_iccs] = eg_out['score']
                    self.move_probe_signal.emit(engine_id, eg_out)
                elif action == 'info':
                    #print(eg_out)
                    pass


#-----------------------------------------------------#
