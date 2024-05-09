# -*- coding: utf-8 -*-
import sqlite3
import json

import cchess

from peewee import *
from playhouse.sqlite_ext import *
from tinydb import TinyDB, Query

#------------------------------------------------------------------------------
book_db = SqliteExtDatabase('game/openbook.db', pragmas=(
    ('cache_size', -1024 * 64),  # 64MB page-cache.
    ('journal_mode', 'wal'),  # Use WAL-mode (you should always use this!).
    #('foreign_keys', 1),
    ))  # Enforce foreign-key constraints.

#------------------------------------------------------------------------------
class PosMove(Model):
    fen = CharField(unique=True, index=True)
    step = IntegerField()
    moves = JSONField()
   
    class Meta:
        database = book_db
        
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

    #------------------------------------------------------------------------------
    #OpenBook
    def getBookMoves(self, fen):
        
        board = cchess.ChessBoard(fen)
        for b in [board, board.mirror()]:
            try:
                query = PosMove.get(PosMove.fen == b.to_fen())
            except PosMove.DoesNotExist:
                query = None
                continue
        
        if (query is None )or len(query.moves) == 0:
            return []
            
        move_color = b.get_move_color()        
        ret = []
        score_base = query.moves[0][1]
        for it in query.moves:
            m = {}
            m['move'] = it[0]
            m['score'] = it[1]
            p_from, p_to = cchess.Move.from_iccs(m['move'])
            move_it = b.copy().move(p_from, p_to)
            m['text'] = move_it.to_text()
            m['diff'] = score_base - m['score'] if move_color == cchess.RED else score_base - m['score']
            ret.append(m)

        return ret
        
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
