
import time
import json
import datetime as dt
from json import JSONEncoder

#import cv2 as cv
#import numpy as np
from PIL import Image, ImageDraw, ImageOps

from PySide6 import *
from PySide6.QtCore import *
from PySide6.QtGui import *

#from pywinauto import *


import cchess


#-----------------------------------------------------------------------------------------#      
pieces_pos = {
    'K': (4, 0),
    'k': (4, 9),
    'A': (3, 0),
    'a': (3, 9),
    'B': (2, 0),
    'b': (2, 9),
    'N': (1, 0),
    'R': (0, 0),
    'C': (1, 2),
    'P': (0, 3),
    'p': (0, 6),
}

FEN_EMPTY = '9/9/9/9/9/9/9/9/9/9'
FEN_FULL = 'rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR'
FEN_FULL_LOWER = FEN_FULL.lower()

"""
#-----------------------------------------------------------------------------------------#      
def cv_to_image(img: np.ndarray) -> Image:
    return Image.fromarray(cv.cvtColor(img, cv.COLOR_BGR2RGB))
    
def image_to_cv(img: Image) -> np.ndarray:
    return cv.cvtColor(np.array(img), cv.COLOR_RGB2BGR)
        
#-----------------------------------------------------------------------------------------#      
class NumpyArrayEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return JSONEncoder.default(self, obj)

#-----------------------------------------------------------------------------------------# 
class ImageSource():
    def __init__(self):
        pass
    
#-----------------------------------------------------------------------------------------        
class MovieSource():

    def open(self, file_name):
        self.movie = cv.VideoCapture(file_name)
        
        ok, frame = self.movie.read()
        if not ok:
            return False
            
        self.height, self.width = frame.shape[:2]
        
        self.start_x = 0 #self.width//5
        self.end_x = self.width #- self.width//5
        
        return True
    
    def get_image(self):
        ok, frame = self.movie.read()      
        
        if not ok:
            return None
        
        for x in range(1):
            ok, frame_new = self.movie.read()      
            
            if not ok:
                break
            
            frame = frame_new
        
        return frame
        
    def get_image_roi(self, roi_rect = None):
    
        ok, frame = self.movie.read()      
        if not ok:
            return None
        
        if roi_rect is not None:    
            img_roi = cv.split(frame[roi_rect[0][1]:roi_rect[1][1], roi_rect[0][0]:roi_rect[1][0]])[0]

        for x in range(25):
            ok, new_frame = self.movie.read()
            if not ok:
                break
            
            if roi_rect is not None:
                img_new_roi = cv.split(new_frame[roi_rect[0][1]:roi_rect[1][1], roi_rect[0][0]:roi_rect[1][0]])[0]

                chang_count = 0
                change = cv.absdiff(img_roi, img_new_roi)
    
                #cv.imshow('INIT BOARD',img_new_roi)
                #cv.waitKey(0)

                for y in range(change.shape[0]):
                    for x in range(change.shape[1]):
                        p = change[y, x]
                        if p > 15:
                            chang_count += 1
                
                #print(chang_count)            
                if chang_count < 500:
                    break
                
                img_roi = img_new_roi                
            frame = new_frame        
        
        return frame 

#-----------------------------------------------------------------------------------------------------
class ScreenSource():
    
    def __init__(self):
    
        self.app = None
        self.win_main = None
        self.img = None
        
    def connect(self):
        self.app = Application(backend='win32')
        
        try:
            self.app.connect(path="QQChess.exe")
            self.win_main = self.app.top_window() #self.app['中国象棋2017']
            self.win_main.set_focus()
            
        except Exception as e:
            print(e)
            return False
        return True    
    
    def move_click(self, s_move):
        print(s_move)
        mouse.click(button='left', coords = s_move[0])
        time.sleep(0.3)
        mouse.click(button='left', coords = s_move[1])
        time.sleep(0.2)
        mouse.move(coords=(0, 0))
        
    def get_image(self, roi_rect = None ):
        try:
            pimg = self.win_main.capture_as_image()
        except Exception as e:
            print(e)
            return None
            
        self.img = image_to_cv(pimg)
        
        return self.img
        
#-----------------------------------------------------------------------------------------------------
class BoardScreen():
    def __init__(self, img = None, flip = False):
    
        self.flip = flip
        
        self.board_begin = [0,0]
        self.board_end = [0,0]
        self.grid_size = [0,0]
        
        self.piece_size = 0
        self.pieces_templ = {}
        
        self.black_index = 0
        
        self.match_precision = 0.7
        
        self.update(img)
        
    def update(self, img):
        
        self.img = img
        
        if self.img is None:
            self.img_gray = None
            self.img_red = None
        else:
            self.img_gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY) 
            b, g, self.img_red = cv.split(img) 
        
    def calc_grid(self):
        self.grid_size = [ (self.board_end[0] - self.board_begin[0])/8.0, (self.board_end[1] - self.board_begin[1])/9.0 ]
        
    def board_to_img(self, x, y):
        
        if self.flip:
            x = 8 - x
            y = 9 - y
            
        return (int(self.board_begin[0] + x * self.grid_size[0]), int(self.board_begin[1] + (9 - y) * self.grid_size[1]))
    
    def img_to_board(self, ix, iy):
        
        x = int((ix + self.piece_size - self.board_begin[0]) / self.grid_size[0])
        y = 9 - int((iy + self.piece_size - self.board_begin[1]) / self.grid_size[1])
        
        if self.flip:
            x = 8 - x
            y = 9 - y
        
        return (x, y)
        
        
    def board_move_to_screen(self, p_from, p_to):
        
        s_from = self.board_to_img(*p_from)
        s_to = self.board_to_img(*p_to)
        
        return (s_from, s_to)
    
    def get_roi_rect(self):
        return ((self.board_begin[0] - self.piece_size, self.board_begin[1] - self.piece_size), 
            (self.board_end[0] + self.piece_size, self.board_end[1] + self.piece_size))
    
    def pos_in_roi(self, pos):
        start, stop = self.get_roi_rect()
        
        if (start[0] <= pos[0] <= stop[0]) and (start[1] <= pos[1] <= stop[1]):
            return True
            
        return False
            
        
    def get_piece_img(self, x, y, gray = True, small = False):
  
        img_pos = self.board_to_img(x, y)
        
        if small:
            half_size = int(self.piece_size / 1.6)
        else:
            half_size = int(self.piece_size / 1.1)
            
        if gray:
            im = self.img_gray[img_pos[1] - half_size : img_pos[1] + half_size, img_pos[0] - half_size : img_pos[0] + half_size] 
        else:        
            im = self.img[img_pos[1] - half_size : img_pos[1] + half_size, img_pos[0] - half_size : img_pos[0] + half_size] 
        
        return im
    
    def make_template(self, config_file_name):
        
        ok = self.auto_detect()
        if not ok:
            return False
            
        board = cchess.ChessBoard() 
        fen = self.to_fen(board)
        
        board.print_board()
        
        config = {
            'image_size': self.img_size,
            'board_begin': self.board_begin,
            'board_end': self.board_end,
            'piece_size': self.piece_size,
            'black_index': self.black_index,
            'match_precision': self.match_precision,
        }
        
        with open(f'{config_file_name}.json', "w") as f:
            json.dump(config, f, indent = 6)
        
        imgs = [self.pieces_templ[key] for key in pieces_pos]
        tmpl_img = cv.hconcat(imgs)
        
        cv.imwrite(f'{config_file_name}.png', tmpl_img)
        
    def load_template(self, config_file_name):
        
        with open(f'{config_file_name}.json', "r") as f:
            config = json.load(f)
            self.img_size = config['image_size']
            self.board_begin = config['board_begin']
            self.board_end = config['board_end']
            self.piece_size = config['piece_size']
            self.black_index = config['black_index']
            self.match_precision = config['match_precision']
        
        self.calc_grid()
        
        img_src = cv.imread(f'{config_file_name}.png')     
        #print(img_src.shape)
        tmpl_img = cv.cvtColor(img_src, cv.COLOR_BGR2GRAY)
        height,width = tmpl_img.shape[:2]
        
        self.pieces_templ = {}    
        index = 0
        for index, key, in enumerate(pieces_pos):
            self.pieces_templ[key] = tmpl_img[0 : height, height * index: height * (index + 1)]
            
    def test_image(self, img):
    
        board = cchess.ChessBoard()
        self.update(img)
        
        fen = self.to_fen(board)
        
        return fen
        
    def auto_detect(self):
    
        img_src = self.img.copy()
        
        r_min = img_src.shape[1] // 60
        r_max = int(r_min * 4)
        
        # 图像预处理
        gray = cv.cvtColor(img_src, cv.COLOR_BGR2GRAY)
        #img = cv.medianBlur(gray, 7)
        gaussian = cv.GaussianBlur(gray, (7, 7),0)
        circles = cv.HoughCircles(gaussian,cv.HOUGH_GRADIENT,1, r_min, param1=100, param2=60, minRadius=r_min, maxRadius=r_max)
                                      
        if circles is None:
            return False
            
        #圆检测
        ims = []
        y_counts = {}
        #circles = np.uint16(np.around(circles))
        for x, y, r in circles[0,:]: 
            x, y, r = int(x), int(y), int(r) 
            #print(x, y, r)
            cv.circle(img_src, (x, y), r, (0, 255, 0), 1, cv.LINE_AA)
            im = img_src[y - r : y + r, x - r : x + r] 
            ims.append((im, x, y, r))
            
            find_y = False
            for y_key, y_count in y_counts.items():
                if abs(y - y_key) < r_min:
                    y_counts[y_key].append((x, y, r)) 
                    find_y = True
                    continue
            if not find_y:
                y_counts[y] = [(x, y, r)]
        
        #cv.imshow('CIRCLE BOARD', img_src)
        #cv.waitKey(0)
        
        x_points = []
        y_points = []
        r_min = -1
        
        img_src = self.img.copy()
                
        for y_key, it in y_counts.items():
            if len(it) == 9:
                for x, y, r in it:
                    #cv.circle(img_src, (x, y), r, (255, 0, 0), 1, cv.LINE_AA)
                    x_points.append(x)
                    y_points.append(y)
                        
                    if r_min < 0 or r < r_min:
                        r_min = r
                    
        board_rect = [min(x_points), min(y_points), max(x_points), max(y_points)]
        
        self.img_size = self.img.shape[:2]
        self.board_begin = board_rect[:2]
        self.board_end = board_rect[2:]
        self.calc_grid()
        self.piece_size = r_min
        
        cv.rectangle(img_src, self.board_begin, self.board_end, (255, 0, 0), 2)
        
        for x in range(9):
            for y in range(10):
                cv.circle(img_src, self.board_to_img(x, y), self.piece_size, (0, 0, 255), 1, cv.LINE_AA)
                pass
        
        cv.imshow('CIRCLE BOARD', img_src)
        cv.waitKey(0)
        
        #使用红色分量检测红黑分界线
        self.flip = False
        
        red_img = cv.split(self.get_piece_img(0, 0, gray = False))[2]
        red_hist = cv.calcHist([red_img],[0],None,[256],[0,256])
        red_sum = np.uint16(np.around(np.cumsum(red_hist)))
        
        black_img = cv.split(self.get_piece_img(0, 9, gray = False))[2]
        black_hist = cv.calcHist([black_img],[0],None,[256],[0,256])
        black_sum = np.uint16(np.around(np.cumsum(black_hist)))
        
        black_count = [0,0]
        for i in range(200):
            #print(black_sum[i],red_sum[i]) 
            if black_sum[i] == 0 and red_sum[i] == 0:
                black_count[0] = i
            
            elif black_sum[i] > 0 and red_sum[i] == 0: 
                black_count[1] = i
        #print('black_count', black_count)        
        
        self.black_index = (black_count[0] + black_count[1]) // 2
        
        self.init_pieces_template()

        return True
        
            
    def init_pieces_template(self):    
        #模板获取    
        for key, (x, y) in pieces_pos.items():
            img = self.get_piece_img(x, y, gray = True, small = True)
            self.pieces_templ[key] = img
        
    def detect_piece(self, img_src, match_precision):
        
        #d = pytesseract.image_to_data(img_src, lang = "chi_sim", output_type=Output.DICT)
        #print(d['text'])
        
        #cv.imshow('CIRCLE BOARD', img_src)
        #cv.waitKey(0)
        ret = None
        for key, img_tmpl in self.pieces_templ.items():
            result = cv.matchTemplate(img_src, img_tmpl, cv.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv.minMaxLoc(result)
            #print(min_val, max_val)
            if max_val > match_precision:
                ret = key
                break
        if ret:
            return ret
               
        return ret        
    
    def detect_piece_best(self, img_src):
    
        ret = None
        max_match = 0.0 
        for key, img_tmpl in self.pieces_templ.items():
            result = cv.matchTemplate(img_src, img_tmpl, cv.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv.minMaxLoc(result)
            #print(min_val, max_val)
            if max_val > max_match:
                max_match = max_val
                ret = key
        
        return (ret, max_match)
        
    
    '''
    def detect_filp(self):
    
        #红黑检测
        b,g,img_up = cv.split(self.get_piece_img(0, 9))
        b,g,img_down = cv.split(self.get_piece_img(0, 0))
        height,width = img_up.shape[:2]
        black_count = [0,0]
        
        for row in range(height):   
            for col in range(width):
                v = img_up[row][col]
                if v <= self.black_index:    
                    black_count[0] += 1
                
                v = img_down[row][col]
                if v <= self.black_index:    
                    black_count[1] += 1
        #up red
        if black_count[0] < black_count[1]:
            self.flip = True
            #self.black_count = (self.black_count[1], self.black_count[0])
    '''
    
    def detect_color(self, img):
        
        b,g,red = cv.split(img)
        
        height, width = img.shape[:2]
        
        b_count = 0
        for row in range(height):
            for col in range(width):         
                pv = red[row, col]
                #print(pv)
                if pv <= self.black_index:    
                    b_count += 1
        return 2 if b_count >= 5 else 1                
     
    def detect_pos_circles(self):
        
        img_src = self.img.copy()
        gray = cv.cvtColor(img_src, cv.COLOR_BGR2GRAY)
        gaussian = cv.GaussianBlur(gray, (7, 7),0)
        circles = cv.HoughCircles(gaussian,cv.HOUGH_GRADIENT, 1, self.piece_size * 2, param1 = 100, param2 = 40, minRadius = self.piece_size - 2, maxRadius = self.piece_size + 5)
        
        if circles is None:
            return []
            
        ims = []
        for x, y, r in circles[0,:]: 
            x, y, r = int(x), int(y), int(r) 
            bx, by = self.img_to_board(x, y)
            if (bx < 0) or (bx > 8) or (by < 0) or (by > 9): 
                continue
            #cv.putText(img_src, f'{bx}{by}', (x, y), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2, cv.LINE_AA)
            im = self.img_gray[y - r : y + r, x - r : x + r] 
            #cv.circle(img_src, (x, y), 5, (0, 0, 255), 2, cv.LINE_AA)
            ims.append((bx, by, im))
            
        #cv.imshow('INIT BOARD',img_src)
        #cv.waitKey(0)
        return ims
        
    def to_fen(self, board):
        
        board.clear()
        
        ims = self.detect_pos_circles()
        for x, y, img in ims:
            #img = self.get_piece_img(x, y)
            #cv.imshow('INIT BOARD',img)
            #cv.waitKey(0)
        
            ret, max_match = self.detect_piece_best(img)   
            #ret = self.detect_piece(img, self.match_precision)
            if ret:
                if ret.isupper(): #红色才需要进一步测试颜色，黑色棋子根据模板已经识别出来了
                    c_img = self.get_piece_img(x, y, gray = False, small = True)
                    color = self.detect_color(c_img)
                
                    if color == 1:
                        fen_ch = ret.upper() 
                    else:
                        fen_ch = ret.lower()
                else:
                    fen_ch = ret
                
                board.put_fench(fen_ch, (x, y))
            else:
                
                fen_ch, max_match = self.detect_piece_best(img)
                print("circle empty", x, y, fen_ch, max_match)
                
        '''
        for x in range(9):
            for y in range(10):
                img = self.get_piece_img(x, y)
                ret = self.detect_piece(img)
                if ret:
                    if ret: #.isupper(): #红色才需要进一步测试颜色，黑色棋子根据模板已经识别出来了
                        img_small = self.get_piece_img(x, y, small = True) 
                        color = self.detect_color(img_small)
                    
                        if color == 1:
                            fen_ch = ret.upper() 
                        else:
                            fen_ch = ret.lower()
                    else:
                        fen_ch = ret
                        
                    if self.flip:
                        x = 8 - x
                        y = 9 - y
                    
                    board.put_fench(fen_ch, (x, y))
        '''
        
        return board.to_fen_base().split(' ')[0]
        
    def show_grid(self):
        
        img_src = self.img.copy()
        
        #board_end = (self.board_begin[0] + self.grid_size[0]*8, self.board_begin[1] + self.grid_size[1]*9)
        #cv.rectangle(img_src, self.board_begin, board_end, (255, 0, 0), 1)
        
        for x in range(9):
            for y in range(10):
                #cv.circle(img_src, self.board_to_img(x, y), self.piece_size, (0, 0, 255), 2, cv.LINE_AA)
                pass
                
        cv.imshow('INIT BOARD',img_src)
        cv.waitKey(0)
        
    def show_move(self, s_move):
        
        s_from, s_to = s_move
        
        img_src = self.img.copy()
        
        cv.circle(img_src, s_from, 6, (0, 0, 255), 2, cv.LINE_AA)
        cv.circle(img_src, s_to, 6, (0, 255, 0), 2, cv.LINE_AA)
                
        cv.imshow('INIT BOARD',img_src)
        cv.waitKey(0)
                
#-----------------------------------------------------------------------------------------#      
class GameMaster():
    def __init__(self, screen, img_src, engine):
        
        self.screen = screen
        self.img_src = img_src
        
        self.engine = engine
        self.board = cchess.ChessBoard() 
        
        self.player = None
    
    
    '''        
    def start_recording(self):
        file_name = f'videos\{dt.datetime.now().strftime("%Y%m%d_%H%M%S%f")}.mp4'
        img_size = self.img.shape[:2]
        self.video_writer = cv.VideoWriter(file_name, cv.VideoWriter_fourcc(*'mp4v'), 15, img_size)
        
    def stop_recording(self):
        self.video_writer.release()
    '''
    
    
    def wait_for_init(self):
        
        board_new = cchess.ChessBoard()
        
        while True:
            img = self.img_src.get_image()
            
            if img is None:
                break
                
            self.screen.update(img)
            
            new_fen = self.screen.to_fen(board_new)
            #print(new_fen)
            if new_fen == FEN_EMPTY:
                continue
            
            if new_fen[0].isupper():
                self.screen.flip = True
                #print(self.screen.flip)
                #new_fen = self.screen.to_fen(board_new)
                #self.board.from_fen(new_fen)
            
            break
            
        self.player = cchess.ChessPlayer(cchess.BLACK) if self.screen.flip  else cchess.ChessPlayer(cchess.RED)
        
        print("Play", self.player)
        
        return True
       
    def run(self):
        
        #self.board.move_player = cchess.ChessPlayer(cchess.RED)
        last_fen = self.screen.to_fen(self.board)
        print('init', last_fen)
        self.board.print_board()
        
        board_new = cchess.ChessBoard()
        
        while True:
            
            img = self.img_src.get_image()
            
            if img is None:
                break
            
            self.screen.update(img)
            
            new_fen = self.screen.to_fen(board_new)
            
            if new_fen != last_fen:
                #print(new_fen)
                #print(board_new.to_fen())    
                #return
                
                m = self.board.detect_move_pieces(board_new)
                
                print(m)
                board_new.print_board()
                
                if (len(m[0]) != 1) or (len(m[1]) != 1):
                    pass
                    
                else:    
                    move_it = self.board.create_move_from_board(board_new)
                        
                    if not move_it:
                        continue
                    
                    color = self.board.get_fench_color(move_it[0])
                    move = self.board.move(move_it[0], move_it[1])
                    print(move_it, move.to_chinese())
                    
                    self.board.move_player.color = color 
                    self.board.move_player.next()
                    
                    print('board_play:', self.board.move_player, 'my_play:', self.player)
                    
                    last_fen = new_fen
                    
                    if self.board.move_player == self.player:
                        self.engine.go_from(self.board.to_fen())
                        tmp_board = self.board.copy()
                        while True:
                            print('.')
                            self.engine.handle_msg_once()
                            if self.engine.move_queue.empty():
                                time.sleep(0.2)
                                continue
                            output = self.engine.move_queue.get()
                            action = output['action']
                            if action == 'best_move':
                                p_from, p_to = output["move"]
                                print("Engine move", p_from, p_to)
                                move_str = tmp_board.move(p_from, p_to).to_chinese()
                                print(move_str)
                                s_move = self.screen.board_move_to_screen(p_from, p_to)
                                print(s_move)
                                #self.screen.show_move(s_move)
                                self.img_src.move_click(s_move)
                                break
                            elif action == 'dead':
                                dead = True
                                break
                            elif action == 'draw':
                                dead = True
                                break
                            elif action == 'resign':
                                dead = True
                                break    
                
"""