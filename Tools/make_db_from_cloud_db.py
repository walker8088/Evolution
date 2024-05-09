import os, sys
import time
import pickle
from pathlib import Path

import requests

from cchess import *

from peewee import *
from playhouse.sqlite_ext import *

#---------------------------------------------------------
book_db = SqliteExtDatabase('../Game/openbook.db', pragmas=(
    ('cache_size', -1024 * 64),  # 64MB page-cache.
    ('journal_mode', 'wal'),  # Use WAL-mode (you should always use this!).
    ('foreign_keys', 1)))  # Enforce foreign-key constraints.

class PosMove(Model):
    fen = CharField(unique=True, index=True)
    step = IntegerField()
    moves = JSONField()
   
    class Meta:
        database = book_db

#-----------------------------------------------------#

def QueryFromCloudDB(fen):
    url = 'http://www.chessdb.cn/chessdb.php'
    param = {"action": 'queryall'}
    param['board'] = fen
    
    #数据获取
    try:
        resp = requests.get(url, params=param,  timeout = 10)
    except Exception as e:
        print(e)
        return []
        
    text = resp.text.rstrip('\0')
    if len(text) < 20:
        print(text)
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
        return  None
        
    for move in moves:
        move['score'] = int(move['score'])
    
    return moves
    
#---------------------------------------------------------------------------
def get_pos_moves(fen):
    query = PosMove.select().where(PosMove.fen == fen)
    for it in query:
        print(it.fen, it.moves)
        for m in it.moves:  
            print(m)
        
#---------------------------------------------------------------------------
def is_fen_exist(fen):
    query = list(PosMove.select().where(PosMove.fen == fen))
    if len(query) > 0:
        return True
    
    board = ChessBoard(fen)
    
    fen_mirror = board.copy().mirror().to_fen()    
    query = list(PosMove.select().where(PosMove.fen == fen_mirror))
    if len(query) > 0:
        print('mirror found.')
        return True
        
    fen_swap = board.copy().swap().to_fen()    
    query = list(PosMove.select().where(PosMove.fen == fen_swap))
    if len(query) > 0:
        print('swap found.')
        return True
   
    fen_mirror_swap = board.copy().mirror().swap().to_fen()    
    query = list(PosMove.select().where(PosMove.fen == fen_mirror_swap))
    if len(query) > 0:
        print('mirror swap found.')
        return True

    return False
    
#---------------------------------------------------------------------------
def save_pos_move(fen, step, moves): 
    step_limits = [10, 10,  15, 15,  20, 20,  20, 20, 20, 20,  20, 20,  20, 20,  20, 20, 20, 20,  20, 20,  20, 20]
    ret = []
    records = {}
    for m in moves:
        if step >= len(step_limits):
            limit = 30
        else:
            limit = step_limits[step]
        if  m['score'] < -limit or m['score'] > limit:
            continue
        records[m['move']] = m['score']
        ret.append({'fen': fen, 'iccs': m['move'], 'score': m['score']})
        
    if len(records) > 0:    
        PosMove.create(fen = fen, step = step, moves = records)
        
    return ret

#---------------------------------------------------------------------------

#get_pos_moves(FULL_INIT_FEN)

#sys.exit(0)

table_file = 'table.pickle'

if not Path(table_file).is_file():
    PosMove.create_table()
    tables = []
    fen = FULL_INIT_FEN
    step = 1 
    moves = QueryFromCloudDB(fen)
    if len(moves) == 0:
        print("None Moves Found in CloundDB.")
        sys.exit(-1)
    records = save_pos_move(fen, step, moves)
    for it in records:
        board = ChessBoard(it['fen'])
        move = board.move_iccs(it['iccs'])
        board.next_turn()
        tables.append(board.to_fen())
else:
    with open(table_file, 'rb') as f:
        step, tables = pickle.load(f)
        print(f"Step：{step}, Load {len(tables)} Records")

#消费数据
new_tables = []
step += 1
count = len(tables)
for index, fen in enumerate(tables):
    #生产数据
    if is_fen_exist(fen):
        print(f"Step:{step} Inbook:{fen}")
        continue
    try_count = 0        
    while try_count < 5:
        print(f"Step:{step} {index+1}/{count} Query:{fen}")
        moves = QueryFromCloudDB(fen)
        if len(moves) == 0:
            time.sleep(3)
            try_count += 1
        else:
            break
    
    if len(moves) == 0:
        sys.exit(-1)
        
    try_count = 0        
    records = save_pos_move(fen,step, moves)
    board = ChessBoard(fen)
    for it in records:
        b = board.copy()
        move = b.move_iccs(it['iccs'])
        b.next_turn()
        new_tables.append(b.to_fen())
    #time.sleep(0.2)
    
#保存CheckPoint
print("table len:", len(new_tables))
with open(table_file, 'wb') as f:
    pickle.dump((step, new_tables), f)

#交换数据
#tables = new_tables
#mirror
#rnbakabnr/9/7c1/pcp1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR b
