
import time
import json
import datetime as dt
from json import JSONEncoder

import cv2 as cv
import numpy as np

from PIL import Image, ImageDraw, ImageOps, ImageGrab
from PIL.ImageQt import ImageQt

from PyQt5 import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

import pygetwindow as getwindow

import cchess
from cchess import ChessBoard

from .Utils import scaleImage

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


#-----------------------------------------------------------------------------------------#  
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

#-----------------------------------------------------------------------------------------#  
def cv2pil_image(cv_img): 
    return Image.fromarray(cv.cvtColor(cv_img, cv.COLOR_BGR2RGB))

def pil2cv_image(pil_img): 
    return cv.cvtColor(np.array(pil_img), cv.COLOR_RGB2BGR)

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
        self.win = None
        self.img = None
        
    def connect(self, window_title):

        self.win = None
        windows = getwindow.getWindowsWithTitle(window_title)
        if len(windows) == 0:
            return False

        self.win = windows[0]
        
        return True
    
    def isConnected(self):
        return not (self.win is None)

    def move_click(self, s_move):
        mouse.click(button='left', coords = s_move[0])
        time.sleep(0.3)
        mouse.click(button='left', coords = s_move[1])
        time.sleep(0.2)
        mouse.move(coords=(0, 0))
        
    def grab(self, left_marge, top_marge):
        self.win.activate()
        
        box = self.win.box

        bbox = (box.left + left_marge, box.top + top_marge, box.left + box.width - left_marge, box.top + box.height - left_marge) 
        print(box)
        #2433, 1455
        # 330, 120 -> 1405, 1315 
        
        left = int(box.width * 355 / 2625.0)
        top = int(box.height * 60 / 1455.0)
        right = int(box.width * 1515 / 2625.0)
        bottom = int(box.height * 1255 / 1455.0)
        
        img = ImageGrab.grab(bbox)
        #img_board = img.crop((left, top, right, bottom))
        #img.save('tian.jpg')

        return img #img_board
        
class ScreenBoardView(QWidget):
    def __init__(self, parent = None):

        super().__init__(parent)
    
        self.setAutoFillBackground(True)

        p = self.palette()
        p.setColor(self.backgroundRole(), QColor(40, 40, 40))
        self.setPalette(p)
    
        self._board = ChessBoard()

        self.flip_board = False
        self.mirror_board = False

        self.last_pickup = None

        self.start_x = 0
        self.start_y = 0
        
        self.base_space = 56
        self.base_boader = 15
        self.base_piece_size = 53
        
        self.img_width = 530
        self.img_height = 586
        
        self.base_img = None
        self.img_src = None

    def to_fen(self):
        return self._board.to_fen()

    def logic_to_board(self, x, y,  bias = 0):

        board_x = self.boader + x * self.space + self.start_x
        board_y = self.boader + (9 - y) * self.space + self.start_y

        return (board_x + bias, board_y + bias)

    def board_to_logic(self, bx, by):

        x = (bx - self.boader - self.start_x) // self.space
        y = 9 - ((by - self.boader - self.start_y) // self.space)

        if self.flip_board:
            x = 8 - x
            y = 9 - y

        if self.mirror_board:
            x = 8 - x

        return (x, y)
    
    def setFlipBoard(self, fliped):

        if fliped != self.flip_board:
            self.flip_board = fliped
            self.update()

    def setMirrorBoard(self, mirrored):

        if mirrored != self.mirror_board:
            self.mirror_board = mirrored
            self.update()

    def resizeEvent(self, ev):
        self.fitImage(ev.size())

    def fitImage(self, size):
        
        new_width = size.width()
        new_height = size.height()
        
        self.start_x = (new_width - self.img_width) // 2
        if self.start_x < 0:
            self.start_x = 0

        self.start_y = (new_height - self.img_height) // 2
        if self.start_y < 0:
            self.start_y = 0
                
    def updateImage(self, img):
        
        self.cv_img = pil2cv_image(img)
        self.img_src = None

        im2 = img.convert("RGBA")
        data = im2.tobytes("raw", "BGRA")
        qimg = QImage(data, img.width, img.height, QImage.Format_ARGB32)
        
        #qimg = ImageQt(img)
        self.base_img = QPixmap.fromImage(qimg)
        
        self.img_width =  self.base_img.width()
        self.img_height =  self.base_img.height()
        
        self.fitImage(self.size())
        
        self.update()
        
    def paintEvent(self, ev):

        painter = QPainter(self)
        
        if self.img_src:
            painter.drawPixmap(self.start_x,  self.start_y, self.img_src)
        elif self.base_img:
            painter.drawPixmap(self.start_x,  self.start_y, self.base_img)

    def detectBoard(self):
        
        self.gause_times = 2

        img_src = self.cv_img.copy()
    
        # 图像预处理
        gray = cv.cvtColor(img_src, cv.COLOR_BGR2GRAY)
        for i in range(self.gause_times):
            gray = cv.GaussianBlur(gray, (5, 5),0)
        
        r_min = img_src.shape[1] // 30
        r_max = int(r_min * 1.5)
        print(r_min, r_max)
        
        circles = cv.HoughCircles(gray,cv.HOUGH_GRADIENT,1, r_min, param1=100, param2=70, minRadius=r_min, maxRadius=r_max)
        
        if circles is None:
            return 
            
        #圆检测
        ims = []
        y_counts = {}
        #circles = np.uint16(np.around(circles))
        for x, y, r in circles[0,:]: 
            x, y, r = int(x), int(y), int(r) 
            print(x, y, r)
            cv.circle(img_src, (x, y), r, (0, 255, 0), 1, cv.LINE_AA)
            #im = img_src[y - r : y + r, x - r : x + r] 
            #ims.append((im, x, y, r))
            
            find_y = False
            for y_key, y_count in y_counts.items():
                if abs(y - y_key) < r_min:
                    y_counts[y_key].append((x, y, r)) 
                    find_y = True
                    continue
            if not find_y:
                y_counts[y] = [(x, y, r)]

     
        qimg = cv2qt_image(img_src)
        self.img_src = QPixmap.fromImage(qimg)

        self.update()
    
    def mousePressEvent(self, mouseEvent):
        pass
        
    def mouseMoveEvent(self, mouseEvent):
        pass

    def mouseReleaseEvent(self, mouseEvent):
        pass
    

#-----------------------------------------------------#
class OnlineDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle("连线分析-窗口截图")
        self.setMinimumSize(600, 800)
        
        self.screen = ScreenBoardView(self)
        self.source = ScreenSource()

        self.redMoveBtn = QRadioButton("红方走", self)
        self.blackMoveBtn = QRadioButton("黑方走", self)
        self.fenLabel = QLabel()

        group1 = QButtonGroup(self)
        group1.addButton(self.redMoveBtn)
        group1.addButton(self.blackMoveBtn)

        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.redMoveBtn, 0)
        hbox1.addWidget(self.blackMoveBtn, 0)
        hbox1.addWidget(QLabel(''), 1)

        captureBtn = QPushButton("截取窗口", self)
        captureBtn.clicked.connect(self.onCapture)
        detectBtn = QPushButton("检测", self)
        detectBtn.clicked.connect(self.onDetect)
        okBtn = QPushButton("确定", self)
        cancelBtn = QPushButton("取消", self)

        vbox = QVBoxLayout()
        vbox.addWidget(self.screen, 2)
        #vbox.addWidget(self.fenLabel)
        vbox.addLayout(hbox1)

        hbox = QHBoxLayout()
        #hbox.addWidget(self.redMoveBtn)
        #hbox.addWidget(self.blackMoveBtn)
        hbox.addWidget(captureBtn)
        hbox.addWidget(detectBtn)
        
        hbox.addWidget(okBtn)
        hbox.addWidget(cancelBtn)

        vbox.addLayout(hbox)
        self.setLayout(vbox)

        #self.boardEdit.fenChangedSignal.connect(self.onBoardFenChanged)
        self.redMoveBtn.clicked.connect(self.onRedMoveBtnClicked)
        self.blackMoveBtn.clicked.connect(self.onBlackMoveBtnClicked)

        okBtn.clicked.connect(self.accept)
        cancelBtn.clicked.connect(self.close)

        self.source.connect('天天象棋')
        
    def showEvent(self, event):
        print(event)
        if self.source.isConnected():
            self.onCapture()
        
    def onCapture(self):
        
        win_rect = self.frameGeometry()
        inner_rect = self.geometry()
        
        left_marge = inner_rect.x() - win_rect.x() 
        top_marge = inner_rect.y() - win_rect.y()
        
        #print(left_marge, top_marge)

        img = self.source.grab(left_marge, top_marge)
        self.screen.updateImage(img)
        
        #img.save('tiantian.jpg')

    def onDetect(self):
        self.screen.detectBoard()
        
    def onRedMoveBtnClicked(self):
        self.boardEdit.set_move_color(RED)

    def onBlackMoveBtnClicked(self):
        self.boardEdit.set_move_color(BLACK)

    def onBoardFenChanged(self, fen):

        self.fenLabel.setText(fen)

        color = self.boardEdit.get_move_color()
        if color == RED:
            self.redMoveBtn.setChecked(True)
        elif color == BLACK:
            self.blackMoveBtn.setChecked(True)

    def edit(self, fen_str):
        self.boardEdit.from_fen(fen_str)

        if self.exec_() == QDialog.Accepted:
            return self.boardEdit.to_fen()
        else:
            return None
            
    def get_image(self):
        pass


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
    
    def sizeHint(self): 
        return QSize(400, 400)
    
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
"""
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
#-----------------------------------------------------#
