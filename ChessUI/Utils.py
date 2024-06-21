# -*- coding: utf-8 -*-

import os
import sys
import time
from pathlib import Path
import logging
import uuid
import traceback 


import psutil
import requests
import numpy as np
import cv2 as cv
from PIL import Image

from PySide6 import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtNetwork import *

from cchess import *

#-----------------------------------------------------#
def cv2qt_image(image):

    size = image.shape
    step = int(image.size / size[0])
    qformat = QImage.Format_Indexed8

    if len(size) == 3:
        if size[2] == 4:
            qformat = QImage.Format_RGBA8888
        else:
            qformat = QImage.Format_RGB888

    img = QImage(image, size[1], size[0], step, qformat).rgbSwapped()

    return img

def cv2pil_image(cv_img): 
    return Image.fromarray(cv.cvtColor(cv_img, cv.COLOR_BGR2RGB))

def pil2cv_image(pil_img): 
    return cv.cvtColor(np.array(pil_img), cv.COLOR_RGB2BGR)

#-----------------------------------------------------#
def cv_to_image(img: np.ndarray) -> Image:
    return Image.fromarray(cv.cvtColor(img, cv.COLOR_BGR2RGB))
    
def image_to_cv(img: Image) -> np.ndarray:
    return cv.cvtColor(np.array(img), cv.COLOR_RGB2BGR)
    
#-----------------------------------------------------#
def get_mac_address():
    mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
    return ":".join([mac[e:e + 2] for e in range(0, 11, 2)])

def get_free_memory_mb():
    return psutil.virtual_memory().available/1024/1024
        
#-----------------------------------------------------#
def getTitle():
    return QApplication.instance().APP_NAME_TEXT

#-----------------------------------------------------#
class ThreadRunner(QThread):
    def __init__(self, runner):
        super().__init__()
        self.runner = runner

    def run(self):
        self.runner.run()

#-----------------------------------------------------#
def load_eglib(lib_file):
    games = OrderedDict()

    with open(lib_file, 'rb') as f:
        lines = f.readlines()

    for line in lines:
        it = line.strip().decode('utf-8')
        if it.startswith('#') or it == '':
            continue
        its = it.split('|')

        name = its[0]
        if name not in games:
            games[name] = {'name': name, 'fen': its[1]}

        if len(its) == 3:
            games[name]['moves'] = its[2]

    return games.values()


#-----------------------------------------------------#
class TimerMessageBox(QMessageBox):
    def __init__(self, text, timeout = 2):
        super().__init__()
        self.setWindowTitle(getTitle())
        self.time_to_wait = timeout
        self.setText(text)
        self.setStandardButtons(QMessageBox.NoButton)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.changeContent)
        self.timer.start()

    def changeContent(self):
        self.time_to_wait -= 1
        if self.time_to_wait <= 0:
            self.close()

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()

#-----------------------------------------------------#
'''
class CloudDB(QObject):
    query_result_signal = Signal(str, dict)
    
    def __init__(self, parent):
        super().__init__(parent)
        self.url = 'http://www.chessdb.cn/chessdb.php'
        self.net_mgr = QNetworkAccessManager()
        self.reply = None
        self.fen = None
        self.board = ChessBoard()
        
    def startQuery(self, fen, score_limit = 70):
    
        if (self.reply is not None) and (not self.reply.isFinished()):
            self.reply.abort()
        
        self.fen = fen
        self.board.from_fen(fen)
        self.score_limit = score_limit    
        
        url = QUrl(self.url)
        query = QUrlQuery()
        query.addQueryItem('board', fen)
        query.addQueryItem("action", 'queryall')
        url.setQuery(query)
        req = QNetworkRequest(url)
        self.reply = self.net_mgr.get(req)
        self.reply.finished.connect(self.onQueryFinished)
        self.reply.errorOccurred.connect(self.onQueryError)
        
    def onQueryFinished(self):
        
        if not self.reply:
            return
            
        resp = self.reply.readAll().data().decode()
        #print(resp)
        if resp.lower() in ['', 'unknown']:
            return {}

        move_color = self.board.get_move_color()    
        moves = []
    
        #数据分割
        try:
            steps = resp.split('|')
            for it in steps:
                segs = it.strip().split(',')
                items =[x.split(':') for x in segs]
                it_dict = {key:value for key, value in items}
                #print(it_dict)
                moves.append(it_dict)
        except Exception as e:
            #traceback.print_exc()
            traceback.print_exception(*sys.exc_info())
            print('cloud query result:', text, "len:", len(text))
            moves = []
            
        #添加中文走子标记       
        for move in moves:
            move_it = self.board.copy().move_iccs(move['move'])
            if move_it:
                move['text'] = move_it.to_text()
            move['score'] = -int(move['score'])  if move_color == BLACK  else  int(move['score'])
        
        moves_clean = []
        score_base = moves[0]['score']
        for it in moves:
            it['diff'] =  it['score'] - score_base
            if move_color == BLACK :
                it['diff'] = -it['diff']
            if self.score_limit > 0 and abs(it['diff']) >  self.score_limit:
                    continue
            moves_clean.append(it)

        ret = OrderedDict()
        for it in moves_clean:
            ret[it['move']] = it
            
        self.reply = None
        self.query_result_signal.emit(self.fen,  ret)
        
    def onQueryError(self, error):
        print("CLOUD DBQUERY ERROR")
        self.reply = None
        #self.query_result_signal.emit(self.fen,  {})
'''        
#-----------------------------------------------------#
def QueryFromCloudDB(fen, score_limit = 70):
    url = 'http://www.chessdb.cn/chessdb.php'
    param = {"action": 'queryall'}
    param['board'] = fen
    
    #数据获取
    try:
        resp = requests.get(url, params=param,  timeout = 3)
    except Exception as e:
        print(e)
        return []
        
    text = resp.text.rstrip('\0')
    if text.lower() in ['', 'unknown']:
        return []

    board = ChessBoard(fen)
    move_color = board.get_move_color()    
    moves = []
    
    #数据分割
    try:
        steps = text.split('|')
        for it in steps:
            segs = it.strip().split(',')
            items =[x.split(':') for x in segs]
            it_dict = {key:value for key, value in items}
            #print(it_dict)
            moves.append(it_dict)
    except Exception as e:
        #traceback.print_exc()
        traceback.print_exception(*sys.exc_info())
        print('cloud query result:', text, "len:", len(text))
    
    #添加中文走子标记       
    for move in moves:
        move_it = board.copy().move_iccs(move['move'])
        if move_it:
            move['text'] = move_it.to_text()
        move['score'] = -int(move['score'])  if move_color == BLACK  else  int(move['score'])
    
    ret =[]
    score_base = moves[0]['score']
    for it in moves:
        it['diff'] =  it['score'] - score_base
        if move_color == BLACK :
            it['diff'] = -it['diff']
        if  score_limit > 0 and abs(it['diff']) >  score_limit:
                continue
        ret.append(it)       
    return  ret        
