# -*- coding: utf-8 -*-
import hashlib
import sqlite3
import json
import logging
import time
from collections import OrderedDict

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
    vmoves = JSONField()
   
    class Meta:
        database = book_db     
#------------------------------------------------------------------------------
#OpenBook

class OpenBook():

    def loadBookFile(self, file_name):
        global book_db
        book_db.init(file_name, pragmas={'journal_mode': 'wal'})

    def getMoves(self, fen):
        
        ret = {}
        
        board = cchess.ChessBoard(fen)
        for b, b_state in [(board, ''), (board.mirror(), 'mirror')]:
            try:
                query = PosMove.get(PosMove.vkey == str(board.zhash()))
            except PosMove.DoesNotExist:
                query = None
                continue
            if query is not None:
                break
                
        if (query is None )or len(query.vmoves) == 0:
            #print("GET:", b_state, query)
            return ret
         
        move_color = board.get_move_color()        
        #print("GET:", b_state, query.moves)

        score_base = None
        for ics, score in query.vmoves.items():
            if b_state == 'mirror':
                iccs = cchess.iccs_mirror(ics)
            else:
                iccs = ics
            m = {}  
            m['move'] = iccs
            if score_base is  None:
                score_base = score
            move_it = board.copy().move_iccs(iccs)
            m['text'] = move_it.to_text()
            m['score'] = score
            m['diff'] =  score - score_base
            if move_color == cchess.BLACK:
                m['score'] = -m['score']
                #m['diff'] =   -m['diff']
            #print(m)
            ret[iccs] = m

        return ret
        
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
    def getAllBookMoves(self, fen):
        ret = self.position_table.search(Query().fen == fen)
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
        q = Query()
        for position in positions:
            #print(position)
            move = position['move']
            fen = move.board.to_fen()
            move_iccs = move.to_iccs()
            ret = self.position_table.search(q.fen == fen)
            move_score = position['score'] if 'score' in position else ''

            action_to_save = {'move': move_iccs}
            action_to_save['score'] = move_score

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
                        #对更新内容中score为空的数据，不会更新原来的score
                        if (action_to_save['score'] == '') and ('score'
                                                                in act):
                            del action_to_save['score']
                        act.update(action_to_save)
                        self.position_table.update({'actions': db_actions},
                                                   q.fen == fen)
                        #print('update', db_actions)
                        break
                if not act_found:
                    db_actions.append(action_to_save)
                    self.position_table.update({'actions': db_actions},
                                               q.fen == fen)
            else:
                print('database eeeor', ret)

#-----------------------------------------------------#
class CloudDB(QObject):
    query_result_signal = Signal(str, OrderedDict)
    
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
            self.query_result_signal.emit(fen,  ret)
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
            for it in steps:
                segs = it.strip().split(',')
                items =[x.split(':') for x in segs]
                it_dict = {}
               
                for key, value in items:
                    if key not in ['score', 'move', 'winrate']:
                        continue
                    it_dict[key] = value
                moves.append(it_dict)
        except Exception as e:
            print('cloud query result:', resp, "len:", len(resp))
            
        score_base = int(moves[0]['score'])
        for move in moves:
            move_it = self.board.copy().move_iccs(move['move'])
            if move_it:
                move['text'] = move_it.to_text()
            move['score'] = int(move['score']) 
            move['diff'] =  move['score'] - score_base
            if move_color == cchess.BLACK:
                move['score'] = -move['score']
                
        #moves = filter(lambda x : is_odd, moves)        
        
        #for it in moves:
        #   if self. score_limit > 0 and abs(it['diff']) >  self.score_limit:
        #           continue
        
        moves =  sorted(moves, key = lambda x:x['diff'], reverse = True) 
        
        moves_clean = []
        score_base = moves[0]['score']
        for it in moves:
            it['diff'] =  it['score'] - score_base
            if move_color == cchess.BLACK :
                it['diff'] = -it['diff']
            if self.score_limit > 0 and abs(it['diff']) >  self.score_limit:
                    continue
            moves_clean.append(it)
            
        
        ret = OrderedDict()
        for it in moves_clean:
            ret[it['move']] = it
            
        self.move_cache[self.fen]  = ret
        
        self.reply = None
        self.query_result_signal.emit(self.fen,  ret)
        
    def onQueryError(self, error):
        print("CLOUD DBQUERY ERROR")
        self.reply = None
        
        self.tryCount += 1
        if self.tryCount < 3:
            logging.warning(f'Query From CloudDB Error, retry { self.tryCount}')
            time.sleep(2)
            self.reply = self.net_mgr.get(self.req)
            self.reply.finished.connect(self.onQueryFinished)
            self.reply.errorOccurred.connect(self.onQueryError)
        else:
            self.query_result_signal.emit(self.fen,  {})
        
    
#------------------------------------------------------------------------------
def trim_fen(fen):
    return ' '.join(fen.split(' ')[:2])

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
            new['moves'] .append({'move': iccs})
    bookmark_table.insert(new)
    print(it)
    print(new)
'''
