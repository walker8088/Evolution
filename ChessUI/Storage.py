# -*- coding: utf-8 -*-
import os
import hashlib
import sqlite3
import json
import logging
import time
from collections import OrderedDict
from pathlib import Path

import cchess

from peewee import *
from playhouse.sqlite_ext import *
from tinydb import TinyDB, Query

from PySide6 import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtNetwork import *

from . import Globl

#------------------------------------------------------------------------------
def trim_fen(fen):
    return ' '.join(fen.split(' ')[:2])


#------------------------------------------------------------------------------
def updateFenCache(qResult):
    fen = qResult['fen']
    if fen not in Globl.fenCache:
        Globl.fenCache[fen] = {}
    Globl.fenCache[fen].update({'score': qResult['score']}) 

    best_moves = []
    actions = qResult['actions']
    for act in actions:
        if act['diff'] == 0:
            best_moves.append(act['iccs'])
        m = {'score': act['score'], 'diff': act['diff']}
        new_fen = act['new_fen']
        if new_fen not in Globl.fenCache:
            Globl.fenCache[new_fen] = m
        else:
            Globl.fenCache[new_fen].update(m)    
    
    if len(best_moves) > 0: 
        Globl.fenCache[fen].update({ 'best_moves': best_moves })
        #print(Globl.fenCache[fen])        
        
#------------------------------------------------------------------------------
book_db = SqliteExtDatabase(None)
#'game/openbook.db', pragmas=(
#    ('cache_size', -1024 * 64),  # 64MB page-cache.
#   ('journal_mode', 'wal'),  # Use WAL-mode (you should always use this!).
#   #('foreign_keys', 1),
#    ))  # Enforce foreign-key constraints.

     
#------------------------------------------------------------------------------
class PosMove(Model):
    fen = CharField(unique=True, index=True)
    vkey = BigIntegerField(unique=True)
    step  = IntegerField()
    score = IntegerField()
    mark  = CharField(null=True)
    vmoves = JSONField()
   
    class Meta:
        database = book_db

#------------------------------------------------------------------------------
#勇芳开局库
openBookYfk = SqliteExtDatabase(None)

class YfkBaseModel(Model):
    class Meta:
        database = openBookYfk

class Bhobk(YfkBaseModel):
    vdraw = IntegerField(null=True)
    vindex = IntegerField(null=True)
    vkey = IntegerField(null=True)
    vlost = IntegerField(null=True)
    vmove = IntegerField(null=True)
    vscore = IntegerField(null=True)
    vvalid = IntegerField(null=True)
    vwin = IntegerField(null=True)

    class Meta:
        table_name = 'bhobk'

class Ltext(YfkBaseModel):
    lma = TextField(null=True)

    class Meta:
        table_name = 'ltext'

#------------------------------------------------------------------------------
c90 =   [ 
        0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3a, 0x3b,
        0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0x4a, 0x4b,
        0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5a, 0x5b,
        0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6a, 0x6b,
        0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7a, 0x7b,
        0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8a, 0x8b,
        0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9a, 0x9b,
        0xa3, 0xa4, 0xa5, 0xa6, 0xa7, 0xa8, 0xa9, 0xaa, 0xab,
        0xb3, 0xb4, 0xb5, 0xb6, 0xb7, 0xb8, 0xb9, 0xba, 0xbb,
        0xc3, 0xc4, 0xc5, 0xc6, 0xc7, 0xc8, 0xc9, 0xca, 0xcb
        ]

s90 = [ 
        "a9", "b9", "c9", "d9", "e9", "f9", "g9", "h9", "i9",
        "a8", "b8", "c8", "d8", "e8", "f8", "g8", "h8", "i8",
        "a7", "b7", "c7", "d7", "e7", "f7", "g7", "h7", "i7",
        "a6", "b6", "c6", "d6", "e6", "f6", "g6", "h6", "i6",
        "a5", "b5", "c5", "d5", "e5", "f5", "g5", "h5", "i5",
        "a4", "b4", "c4", "d4", "e4", "f4", "g4", "h4", "i4",
        "a3", "b3", "c3", "d3", "e3", "f3", "g3", "h3", "i3",
        "a2", "b2", "c2", "d2", "e2", "f2", "g2", "h2", "i2",
        "a1", "b1", "c1", "d1", "e1", "f1", "g1", "h1", "i1",
        "a0", "b0", "c0", "d0", "e0", "f0", "g0", "h0", "i0"
        ]

CoordMap = {}

def buildCoordMap():
    global c90, s90, CoordMap
    for i in range(90):
        CoordMap[c90[i]] = s90[i]
    
#------------------------------------------------------------------------------
def vmove2iccs(vmove):
    global CoordMap
    
    v_from =  vmove & 0xff
    v_to = vmove >> 8
    
    #print(hex(v_from), hex(v_to))
    return CoordMap[v_from] + CoordMap[v_to];

#------------------------------------------------------------------------------
class OpenBookYfk():
    
    def __init__(self):
        buildCoordMap()

    def loadBookFile(self, file_name):
        global openBookYfk
        #create = not Path(file_name).is_file()
        openBookYfk.init(file_name, pragmas={'journal_mode': 'wal'})
        
    def getMoves(self, fen):
        
        board = cchess.ChessBoard(fen)
        
        for b, b_state in [(board, ''), (board.mirror(), 'mirror')]:
            query = Bhobk.select().where(Bhobk.vkey == str(b.zhash()), Bhobk.vvalid == 1).order_by(-Bhobk.vscore)
            query.execute()
            if len(query) > 0:
                break
        
        if len(query) == 0:
            return None

        actions = [] 
        score_best = None
        #move_color = board.get_move_color()        
        
        for it in query:
            #print(b_state, vmove2iccs(it.vmove), it.vscore, )

            ics = vmove2iccs(it.vmove)
            score = it.vscore
            
            if score_best is None:
               score_best = score
                    
            if b_state == 'mirror':
                iccs = cchess.iccs_mirror(ics)
            else:
                iccs = ics

            m = {}  
            m['iccs'] = iccs
            move_it = board.copy().move_iccs(iccs)
            m['text'] = move_it.to_text()
            m['score'] = score
            m['diff'] =  score - score_best
            #if move_color == cchess.BLACK:
            #    m['score'] = -m['score']
            m['new_fen'] = move_it.board_done.to_fen()
            actions.append(m)
        
        ret = {}
        ret['fen'] = fen
        ret['score'] = score_best 
        ret['actions'] = actions

        return ret
        
#------------------------------------------------------------------------------
#OpenBook

class OpenBook():

    def loadBookFile(self, file_name):
        global book_db
        create = not Path(file_name).is_file()
        book_db.init(file_name, pragmas={'journal_mode': 'wal'})
        if create:
            book_db.create_tables([PosMove])

    def getMoves(self, fen):
        
        board = cchess.ChessBoard(fen)
        
        for b, b_state in [(board, ''), (board.mirror(), 'mirror')]:
            try:
                #query = PosMove.get(PosMove.vkey == str(b.zhash()))
                query = PosMove.get(PosMove.fen == b.to_fen())
            except PosMove.DoesNotExist:
                query = None
                print(b.to_fen(), b_state)
                continue
            if query is not None:
                break
                
        if (query is None )or len(query.vmoves) == 0:
            #print("GET:", b_state, query)
            return None
        
        actions = [] #OrderedDict()    
        move_color = board.get_move_color()        
        score_best = query.score

        for ics, move_dict in query.vmoves.items():
            
            if b_state == 'mirror':
                iccs = cchess.iccs_mirror(ics)
            else:
                iccs = ics
            m = {}  
            m['iccs'] = iccs
            
            score = move_dict['score']
            move_it = board.copy().move_iccs(iccs)
            m['text'] = move_it.to_text()
            m['score'] = score
            m['diff'] =  score - score_best
            if move_color == cchess.BLACK:
                m['score'] = -m['score']
            m['new_fen'] = move_it.board_done.to_fen()
            actions.append(m)
            
        ret = {}
        ret['fen'] = fen
        ret['score'] = score_best 
        ret['actions'] = actions

        return ret

"""        
#------------------------------------------------------------------------------
#OpenBookJson
class OpenBookJson():
    def __init__(self):
        pass

    def loadBookFile(self, file_name):
        self.db = TinyDB(file_name)

    def getMoves(self, fen):
        
        board = cchess.ChessBoard(fen)
        
        for b, b_state in [(board, ''), (board.mirror(), 'mirror')]:
            fen = b.to_fen()
            result = self.db.search(Query().fen == fen)
            if len(result) > 0:
                break
        
        #print("GET:", b_state, query)
        if len(result) == 0:
            return {}
        
        
        actions = [] #OrderedDict()    
        move_color = board.get_move_color()        
        score_best = None
        
        moves = result[0]
        #print(moves)

        for ics, info in moves['action'].items():
            score = info['score']
            if b_state == 'mirror':
                iccs = cchess.iccs_mirror(ics)
            else:
                iccs = ics
            m = {}  
            m['iccs'] = iccs
            
            if score_best is  None:
                score_best = score

            move_it = board.copy().move_iccs(iccs)
            m['text'] = move_it.to_text()
            m['score'] = score
            m['diff'] =  score - score_best
            if move_color == cchess.BLACK:
                m['score'] = -m['score']
            m['new_fen'] = move_it.board_done.to_fen()
            actions.append(m)
            
        ret = {}
        ret['fen'] = fen
        ret['score'] = score_best 
        ret['actions'] = actions

        return ret
"""
#-----------------------------------------------------#
class CloudDB(QObject):
    query_result_signal = Signal(dict)
    
    def __init__(self, parent):
        super().__init__(parent)
        self.url = 'http://www.chessdb.cn/chessdb.php'
        self.net_mgr = QNetworkAccessManager()
        
        self.reply = None
        self.fen = None
        self.board = cchess.ChessBoard()
        self.tryCount = 0
        
        self.move_cache = {}
        
    def startQuery(self, fen, score_limit = 70):
        
        if fen in self.move_cache:
            ret = self.move_cache[fen]
            self.query_result_signal.emit(ret)
            return 
             
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
        
        self.req = QNetworkRequest(url)
        self.reply = self.net_mgr.get(self.req)
        self.reply.finished.connect(self.onQueryFinished)
        self.reply.errorOccurred.connect(self.onQueryError)
        
    def onQueryFinished(self):
        
        if not self.reply:
            return
            
        resp = self.reply.readAll().data().decode().rstrip('\0')
        if resp.lower() in ['', 'unknown']:
            return {}

        move_color = self.board.get_move_color()    
        moves = []
    
        #数据分割
        try:
            steps = resp.split('|')
            for index, it in enumerate(steps):
                segs = it.strip().split(',')
                items =[x.split(':') for x in segs]
                it_dict = {}
                for name, value in items:
                    if name == 'score':
                        it_dict['score'] = value
                    elif name == 'move':
                        it_dict['iccs'] = value
                #if index > 3:
                #    break        
                moves.append(it_dict)
        except Exception as e:
            print(e)
            #print('cloud query result:', resp, "len:", len(resp))
        
        if not moves: 
            return

        score_best = int(moves[0]['score'])
        for move in moves:
            move_it = self.board.copy().move_iccs(move['iccs'])
            if move_it:
                move['text'] = move_it.to_text()
            move['score'] = int(move['score']) 
            move['diff'] =  move['score'] - score_best
            if move_color == cchess.BLACK:
                move['score'] = -move['score']
            move['new_fen'] = move_it.board_done.to_fen()

            
        #moves = filter(lambda x : is_odd, moves)        

        #for it in moves:
        #   if self. score_limit > 0 and abs(it['diff']) >  self.score_limit:
        #           continue
        
        moves =  sorted(moves, key = lambda x:x['diff'], reverse = True) 
        
        moves_clean = []
        score_best = moves[0]['score']
        for it in moves:
            it['diff'] =  it['score'] - score_best
            if move_color == cchess.BLACK :
                it['diff'] = -it['diff']
            if self.score_limit > 0 and abs(it['diff']) >  self.score_limit:
                    continue
            moves_clean.append(it)
            
        ret = {}
        ret['fen'] = self.fen
        ret['score'] = score_best
        ret['actions'] = moves_clean
            
        self.move_cache[self.fen]  = ret
        
        updateFenCache(ret)

        self.reply = None
        self.query_result_signal.emit(ret)
        
    def onQueryError(self, error):
        self.reply = None
        
        self.tryCount += 1
        if self.tryCount < 5:
            logging.warning(f'Query From CloudDB Error, retry { self.tryCount}')
            time.sleep(2)
            self.reply = self.net_mgr.get(self.req)
            self.reply.finished.connect(self.onQueryFinished)
            self.reply.errorOccurred.connect(self.onQueryError)
        else:
            self.query_result_signal.emit({})
        
#------------------------------------------------------------------------------
class DataStore():
    def __init__(self):
        self.db = None

    def open(self, file):

        self.db = TinyDB(file)

        self.mygame_table = self.db.table('mygame')
        self.bookmark_table = self.db.table('bookmark')
        self.endbook_table = self.db.table('endbook')
        self.position_table = self.db.table('position')
        self.engine_option_table = self.db.table('engine')

    def close(self):
        self.db.close()

    #------------------------------------------------------------------------------
    #EngineConfig
    def loadEngineOptions(self, engine_id):
        ret = self.engine_option_table.search(Query().engine_id == engine_id) 
        
        if len(ret) == 0:
            return None
        
        return ret[0]
        
    def saveEngineOptions(self, engine_id, options):
        self.engine_option_table.update({'engine_id': engine_id, 'options': options }) 
          
    #------------------------------------------------------------------------------
    #EndBooks
    def getAllEndBooks(self):
        q = Query()
        books = {}
        ret = self.endbook_table.search(q.book_name.exists())
        for it in ret:
            if 'ok' not in it:
                it['ok'] = False
            book_name = it['book_name']
            if book_name not in books:
                books[book_name] = []
            books[book_name].append(it)
        return books

    def saveEndBook(self, book_name, games):
        q = Query()

        for game in games:
            game['book_name'] = book_name
            ret = self.endbook_table.search((q.book_name == book_name)
                                            & (q.name == game['name']))
            if len(ret) == 0:
                self.endbook_table.insert(game)
                #yield game['name']
    
    def updateEndBook(self, game):
        q = Query()
        
        ret = self.endbook_table.search((q.book_name ==  game['book_name'] )
                                            & (q.name == game['name']))
        if len(ret) != 1:
            raise Exception(f"Game Not Exist：{game}")
        else:    
            self.endbook_table.update({'ok':game['ok']}, ((q.book_name ==  game['book_name'])
                                            & (q.name == game['name'])))
            
    def isEndBookExist(self, book_name):
        q = Query()
        ret = self.endbook_table.search((q.book_name == book_name))
        return len(ret) >= 1

    def deleteEndBook(self, book_name):
        q = Query()
        self.endbook_table.remove((q.book_name == book_name))

    #------------------------------------------------------------------------------
    #Bookmarks
    def getAllBookmarks(self):
        return self.bookmark_table.search(Query().name.exists())

    def saveBookmark(self, name, fen, moves=None):

        if self.isFenInBookmark(fen) or self.isNameInBookmark(name) > 0:
            return False

        item = {'name': name, 'fen': fen, 'moves': moves}

        if moves is not None:
            item['moves'] = moves

        self.bookmark_table.insert(item)

        return True

    def isFenInBookmark(self, fen):
        q = Query()
        return len(self.bookmark_table.search(q.book_fen == fen)) > 0

    def isNameInBookmark(self, name):
        q = Query()
        return len(self.bookmark_table.search(q.bookmark_name == name)) > 0

    def removeBookmark(self, name):
        q = Query()
        return self.bookmark_table.remove(q.bookmark_name == name)

    def changeBookmarkName(self, fen, new_name):
        q = Query()
        ret = self.bookmark_table.update({'bookmark_name': new_name},
                                         (q.book_fen == fen))

        if len(ret) == 1:
            return True
        return False

    #------------------------------------------------------------------------------
    #MyGames
    def getAllMyGames(self):
        return self.mygame_table.search(Query().name.exists())

    def saveMyGame(self, name, fen):

        if self.isNameInMyGames(name) > 0:
            return False

        item = {'name': name, 'fen': fen, 'moves': moves}
        self.mygame_table.insert(item)

        return True

    def isNameInMyGames(self, name):
        return len(self.mygame_table.search(Query().name == name)) > 0

    def removeMyGame(self, name):
        return self.mygame_table.remove(Query().name == name)

    def changeMyGameName(self, old_name, new_name):
        ret = self.mygame_table.update({'name': new_name},
                                       (Query().name == old_name))
        return True

    #------------------------------------------------------------------------------
    #BookMoves
    def getAllBookMoves(self, fen = None):
        if fen :
            ret = self.position_table.search(Query().fen == fen)
        else:
            ret = self.position_table.all()    
        return ret
    
    def delBookMoves(self, fen, iccs):
        q = Query()
        
        if iccs is None: #删除该fen对应的数据记录
            self.position_table.remove(q.fen == fen)
        else: #删除该fen和该iccs对应的数据记录
            ret = self.position_table.search(q.fen == fen)
            if len(ret) == 0:
                return False
            record = ret[0]
            found = False
            new_record = []    
            for act in record['actions']:
                if iccs == act['move']:
                    found = True
                else:
                    new_record.append(act)
            if found:
                if len(new_record) > 0: 
                    #该fen尚有其它actions
                    self.position_table.update({'actions': new_record}, q.fen == fen)
                else:
                    #该fen下的actions已经为空了
                    self.position_table.remove(q.fen == fen)
                    
    def saveMovesToBook(self, positions):
        board = cchess.ChessBoard()
        q = Query()
        for position in positions:
            #print(position)
            move = position['move']
            fen = position['fen_prev']
            move_iccs = position['iccs']
            board.from_fen(fen)
            if not board.is_valid_iccs_move(move_iccs):
                raise Exception(f'**ERROR** {fen} move {move_iccs}')
            ret = self.position_table.search(q.fen == fen)
            
            action_to_save = {'move': move_iccs}
            
            if len(ret) == 0:
                self.position_table.insert({
                    'fen': fen,
                    'actions': [
                        action_to_save,
                    ]
                })
            elif len(ret) == 1:
                db_actions = ret[0]['actions']
                act_found = False
                for act in db_actions:

                    if act['move'] == move_iccs:
                        act_found = True
                        act.update(action_to_save)
                        self.position_table.update({'actions': db_actions},
                                                   q.fen == fen)
                        break
                if not act_found:
                    db_actions.append(action_to_save)
                    self.position_table.update({'actions': db_actions},
                                               q.fen == fen)
            else:
                print('database error', ret)
    
#------------------------------------------------------------------------------

'''
ds = DataStore()
ds.open('../Game/localbook.db')

books = ds.getAllEndBooks()
for name, games in books.items():
    #ds.deleteEndBook(name)
    print(games)
'''
'''
position_table = db1.table('position')
ret = db2.search((q.fen.exists() & q.actions.exists()))
for it in ret:
    if 'name' in it:
        print("errrr")
        continue
    new_fen = ' '.join(it['fen'].split(' ')[:2])
    it['fen'] = new_fen
    ret = position_table.search(Query().fen == new_fen)
    if len(ret) == 0:
        position_table.insert(it)
        print("inserted", it)
    else:
        print("Error", ret)
        break

bookmark_table = db1.table('bookmark')
ret = db2.search(Query().bookmark_name.exists())
for it in ret:
    new = {}
    new['name'] = it['bookmark_name']
    new['fen'] = trim_fen(it['book_fen'])
    if 'moves' in it:
        new['moves'] = []
        for iccs in it['moves']:
            new['moves'] .append({'iccs': iccs})
    bookmark_table.insert(new)
    print(it)
    print(new)
'''
