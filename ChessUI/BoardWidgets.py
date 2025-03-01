# -*- coding: utf-8 -*-

import math
from pathlib import Path
from configparser import ConfigParser

#from PySide6 import qApp
from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QSize, QRect
from PySide6.QtGui import QPixmap, QCursor, QPen, QColor, QPainter, QPolygon
from PySide6.QtWidgets import QDialog, QMenu, QWidget, QApplication
from PySide6.QtSvg import QSvgRenderer

import cchess
from cchess import ChessBoard, iccs2pos

from .Utils import TimerMessageBox
from .Resource import qt_resource_data

DEFAULT_SKIN = '默认'
#piece_names = ['wk', 'wa', 'wb', 'wr', 'wn', 'wc', 'wp', 'bk', 'ba', 'bb', 'br', 'bn', 'bc', 'bp']
piece_names = ['rk', 'ra', 'rb', 'rr', 'rn', 'rc', 'rp', 'bk', 'ba', 'bb', 'br', 'bn', 'bc', 'bp']
piece_base = piece_names[0]

#-----------------------------------------------------#
def scaleImage(img, scale):

    if scale == 1.0:
        return img

    new_height = int(img.height() * scale)
    new_img = img.scaledToHeight(new_height, mode=Qt.SmoothTransformation)

    return new_img

#-----------------------------------------------------#
def SvgToPixmap(svg, width, height):
    pix = QPixmap(QSize(width, height))
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHints(QPainter.Antialiasing)
    svg.render(painter)
    #pix.save('test.png')
    return pix

#-----------------------------------------------------#
def arrowCalc(from_x, from_y, to_x, to_y): 
    
    _arrow_height = 10
    _arrow_width = 4
    
    dx = from_x - to_x
    dy = from_y - to_y

    leng = math.sqrt(dx ** 2 + dy ** 2)
    
    # normalize
    normX = dx / leng   
    normY = dy / leng
    # perpendicular vector
    perpX = -normY
    perpY = normX
    
    leftX = to_x + _arrow_height * normX + _arrow_width * perpX
    leftY = to_y + _arrow_height * normY + _arrow_width * perpY

    rightX = to_x +_arrow_height * normX - _arrow_width * perpX
    rightY = to_y + _arrow_height * normY - _arrow_width * perpY
    
    p_from = QPoint(from_x, from_y)
    p_to = QPoint(to_x, to_y)

    return QPolygon([p_from, p_to, QPoint(leftX, leftY), QPoint(rightX, rightY), p_to])

#-----------------------------------------------------#
class ChessBoardBaseWidget(QWidget):
    
    def __init__(self, board):

        super().__init__()

        self._board = board

        self.flip_board = False
        self.mirror_board = False

        self.last_pickup = None

        self.setAutoFillBackground(True)

        p = self.palette()
        p.setColor(self.backgroundRole(), QColor(40, 40, 40))
        self.setPalette(p)

        self.board_start_x = 0
        self.board_start_y = 0
        self.paint_scale = 1.0

         #self.setMinimumSize(self.base_board_width + 20, self.base_board_height + 10) 
        
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)
        
        self.setDefaultSkin()

    def setDefaultSkin(self):
        
        self.use_svg = False

        self.base_board = QPixmap(':ImgRes/board.png')
        #self.base_select_img = QPixmap(':ImgRes/select.png')
        self.base_select_img = QPixmap(':ImgRes/step.png')
        self.base_step_img = QPixmap(':ImgRes/step.png')
        self.base_point_img = QPixmap(':ImgRes/point.png')

        self.base_pieces = {}
        for name in piece_names:
            self.base_pieces[name] = QPixmap(':ImgRes/{}.png'.format(name))

        self.base_board_width = self.base_board.width()
        self.base_board_height = self.base_board.height()
        self.base_piece_size = self.base_pieces[piece_base].width()
        
        self.base_offset_x = 0
        self.base_offset_y = 0

        self.base_border_x = 15
        self.base_border_y = 15

        self.base_board_width = self.base_board.width()
        self.base_board_height = self.base_board.height()
        self.base_piece_size = self.base_pieces[piece_base].width()
    
        self.base_space_x = (self.base_board_width - self.base_border_x*2) / 9
        self.base_space_y = (self.base_board_height - self.base_border_y*2) / 10 
        
        self.scaleBoard(1.0)
        
    def fromSkinFolder(self, skinFolder):
        if not skinFolder:
            self.setDefaultSkin()
        else:
            self.use_svg = False

            self.base_board = QPixmap(str(Path(skinFolder, 'board.png')))
            for name in piece_names:
                self.base_pieces[name] = QPixmap(str(Path(skinFolder, f'{name}.png')))
            
            pv_offset = 0
            ph_offset = 0

            '''    
            configFile = Path(skinFolder, 'skin.txt')    
            if configFile.is_file():
                config = ConfigParser()
                config.read(configFile)
                piece_scale = config.getfloat('SYS', "piecescale")
                pv_offset = config.getint('SYS', "pv_offset")
                ph_offset = config.getint('SYS', "ph_offset")
                
                print(piece_scale, pv_offset, ph_offset)
            '''

            self.base_board_width = self.base_board.width()
            self.base_board_height = self.base_board.height()
            self.base_piece_size = self.base_pieces[piece_base].width()
        
            self.base_offset_x = ph_offset
            self.base_offset_y = pv_offset
            
            self.base_border_x = 10
            self.base_border_y = 10

            self.base_space_x = (self.base_board_width - self.base_border_x*2) / 9
            self.base_space_y = (self.base_board_height - self.base_border_y*2) / 10 
            
        self.resizeBoard(self.size())
        self.update()
        
        return True

    '''
    def fromSvgSkinFolder(self, skinFolder):
        if not skinFolder:
            self.setDefaultSkin()
        else:
            self.use_svg = True

            self.base_board = QSvgRenderer(str(Path(skinFolder, 'board.svg')))
            self.base_board_width =  self.base_board.defaultSize().width()
            self.base_board_height = self.base_board.defaultSize().height()
            
            self.mask = QSvgRenderer(str(Path(skinFolder, 'mask.svg')))
            
            for name in piece_names:
                self.base_pieces[name] = QSvgRenderer(str(Path(skinFolder, f'{name}.svg')))
                
            self.base_border_x = 0
            self.base_border_y = 0

            self.base_space_x = (self.base_board_width - self.base_border_x * 2) // 9
            self.base_space_y = (self.base_board_height - self.base_border_y * 2) // 10
            
            self.base_piece_size = min(self.base_space_x, self.base_space_y) - 1
         
        self.resizeBoard(self.size())

        self.update()
    '''

    def scaleBoard(self, scale):

        self.paint_scale = scale #int(scale * 9) / 9.0

        self.board_width = int(self.base_board_width * self.paint_scale)
        self.board_height = int(self.base_board_height * self.paint_scale)
        
        self.offset_x = int(self.base_offset_x * self.paint_scale)
        self.offset_y = int(self.base_offset_y * self.paint_scale)   
        self.border_x = int(self.base_border_x * self.paint_scale)
        self.border_y = int(self.base_border_y * self.paint_scale)

        
        self.space_x = self.base_space_x * self.paint_scale
        self.space_y = self.base_space_y * self.paint_scale

        self.border_x = int(self.base_border_x * self.paint_scale)
        self.border_y = int(self.base_border_y * self.paint_scale)

        if not self.use_svg:

            self._board_img = scaleImage(self.base_board, self.paint_scale)
            self.point_img = scaleImage(self.base_point_img, self.paint_scale)
            
            select_scale = (self.space_x) / self.base_select_img.width()
            self.select_img = scaleImage(self.base_select_img, select_scale)
            self.step_img = scaleImage(self.base_step_img, select_scale)
            
            self.pieces_img = {}
            piece_scale = (self.space_x - 1) / self.base_piece_size
            self.piece_size = int(self.base_piece_size * piece_scale)
            for name in piece_names:
                self.pieces_img[name] = scaleImage(self.base_pieces[name], piece_scale)

        else:    
            self._board_img = SvgToPixmap(self.base_board, self.board_width, self.board_height)
            
            self.piece_size = int(self.base_piece_size * self.paint_scale)
            self.pieces_img = {}
            for name in piece_names:
                svg = self.base_pieces[name]
                self.pieces_img[name] = SvgToPixmap(svg, self.piece_size, self.piece_size)
            
            self.select_img = scaleImage(self.base_select_img, self.paint_scale)
            self.step_img = scaleImage(self.base_step_img, self.paint_scale)
            self.point_img = scaleImage(self.base_point_img, self.paint_scale)
            
    def resizeBoard(self, size):
        
        new_width = size.width()
        new_height = size.height()

        new_scale = min((new_width-10) / self.base_board_width,
                        (new_height-10) / self.base_board_height)

        self.scaleBoard(new_scale)

        self.board_start_x =  (new_width - self.board_width) // 2
        if self.board_start_x < 0:
            self.board_start_x = 0

        self.board_start_y =  (new_height - self.board_height) // 2
        if self.board_start_y < 0:
            self.board_start_y = 0
    
    def copyFenToClipboard(self):
        fen = self._board.to_fen()        
        clipboard = QApplication.clipboard()
        clipboard.clear()
        clipboard.setText(fen)

    def copyImageToClipboard(self):
        pixmap = self.grab(self.getBoardRect())
        clipboard = QApplication.clipboard()
        clipboard.clear()
        clipboard.setPixmap(pixmap)

    def getBoardRect(self):
        return QRect(self.board_start_x, self.board_start_y, self.board_width, self.board_height)

    def from_fen(self, fen_str, clear = False):
        self._board.from_fen(fen_str)
        if clear:
            self.clearPickup()
        self.update()
            
    def to_fen(self):
        return self._board.to_fen()
    
    def get_move_color(self):
        return self._board.get_move_color()
        
    def clearPickup(self):
        self.last_pickup = None
        self.update()

    def logic_to_board(self, x, y, bias = 0):

        if self.flip_board:
            x = 8 - x
            y = 9 - y

        if self.mirror_board:
            x = 8 - x

        board_x = int(self.board_start_x + self.offset_x + self.border_x + x * self.space_x) 
        board_y = int(self.board_start_y + self.offset_y + self.border_y + (9 - y) * self.space_y) 

        return (board_x + bias, board_y + bias)

    def board_to_logic(self, bx, by):

        x = (bx - self.border_x - self.board_start_x) // int(self.space_x)
        y = 9 - ((by - self.border_y - self.board_start_y) // int(self.space_y))

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
        self.resizeBoard(ev.size())
    
    def paintGrid(self, painter):
        for x in range(9):
            for y in range(10):
                board_x, board_y = self.logic_to_board(x, y)   
                painter.drawRect(board_x, board_y, self.space_x, self.space_y)        
                
    def paintEvent(self, ev):
        
        painter = QPainter(self)
        painter.drawPixmap(self.board_start_x, self.board_start_y, self._board_img)
        
        #self.paintGrid(painter)
        
        for piece in self._board.get_pieces():
            board_x, board_y = self.logic_to_board(piece.x, piece.y)

            painter.drawPixmap(
                QPoint(board_x, board_y), self.pieces_img[piece.get_color_fench()],
                QRect(0, 0, self.piece_size - 1, self.piece_size - 1))

            if (piece.x, piece.y) == self.last_pickup:
                painter.drawPixmap(
                    QPoint(board_x, board_y), self.select_img,
                    QRect(0, 0, self.select_img.width() - 1, self.select_img.height() - 1))

    def showContextMenu(self, pos):
        pass

    def sizeHint(self):
        return QSize(self.base_board_width + 20, self.base_board_height + 10)
    
    #def sizeHint(self):
    #    return QSize(self.base_board_width + 20, self.base_board_height + 10)


#-----------------------------------------------------#
class ChessBoardWidget(ChessBoardBaseWidget):
    rightMouseSignal = Signal(bool)
    tryMoveSignal = Signal(tuple, tuple)

    def __init__(self, board):

        super().__init__(board)

        self._board = board
        self.text = ''
        self.view_only = False

        self.move_pieces = []
        self.last_pickup = None
        self.last_pickup_moves = []
        self.move_steps_show = []
        self.best_moves = []
        self.best_next_moves = []
        self.is_show_best_move = True
    
        self.done = []

        self.move_steps_show = []

        self.board_start_x = 0
        self.board_start_y = 0

        self.timer = QTimer()
        self.timer.timeout.connect(self.moveShowEvent)

    def setViewOnly(self, yes):
        self.view_only = yes
    
    def setShowBestMove(self, yes):
        self.is_show_best_move = yes
        self.update()    
        
    def showIccsMove(self, iccs):
        self.showMove(*iccs2pos(iccs))
        
    def showMove(self, p_from, p_to, best_moves = []):
    
        self.move_pieces = (p_from, p_to)
        self.last_pickup = None
        self.last_pickup_moves = []
        self.best_moves = best_moves
        self.best_next_moves = []
        self._make_move_steps(p_from, p_to)
  
    def showMoveHint(self, best_next_moves):
        self.best_next_moves = best_next_moves
        self.update()

    def clearPickup(self):
        self.move_pieces = []
        self.last_pickup = None
        self.last_pickup_moves = []
        self.best_moves = []
        self.best_next_moves = []
        
        self.update()

    def _make_move_steps(self, p_from, p_to):

        self.last_pickup = p_from

        self.move_steps_show = self.make_show_steps(p_from, p_to, 10)

        self.timer.start(20)

        #等待的运动绘制完成
        while len(self.move_steps_show) > 0:
            qApp.processEvents()
            
        self.update()

        self.last_pickup = None

    def closeEvent(self, event):
        self.timer.stop()

    def moveShowEvent(self):
        if len(self.move_steps_show) == 0:
            self.timer.stop()
        else:
            self.update()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        
        painter = QPainter(self)

        '''
        for move_it in self.last_pickup_moves:
            board_x, board_y = self.logic_to_board(*move_it[1])
            painter.drawPixmap(
                QPoint(board_x, board_y), self.point_img,
                QRect(0, 0, self.piece_size - 1, self.piece_size - 1))
        '''
        
        for pos in  self.move_pieces:
            board_x, board_y = self.logic_to_board(*pos)
            painter.drawPixmap(
                QPoint(board_x, board_y), self.step_img,
                QRect(0, 0, self.step_img.width() - 1, self.step_img.height() - 1))
    

        if len(self.move_steps_show) > 0:
            piece, step_point = self.move_steps_show.pop(0)
            painter.drawPixmap(
                QPoint(step_point[0], step_point[1]),
                self.pieces_img[piece.get_color_fench()],
                QRect(0, 0, self.piece_size - 1, self.piece_size - 1))
        
        if self.is_show_best_move:
            for p_from, p_to in self.best_moves: 
                
                r = self.space_x//2
                
                from_x, from_y = self.logic_to_board(*p_from,r)   
                to_x, to_y = self.logic_to_board(*p_to, r)   
    
                color = Qt.darkGreen
                
                painter.setPen(QPen(color,3))#,  Qt.DotLine))    
                painter.drawLine(from_x, from_y, to_x, to_y)        
                painter.drawPolyline(arrowCalc(from_x, from_y, to_x,to_y))
        
            for p_from, p_to in self.best_next_moves: 
                r = self.space_x//2
                from_x, from_y = self.logic_to_board(*p_from,r)   
                to_x, to_y = self.logic_to_board(*p_to, r)   
                
                color = Qt.darkGreen
                
                painter.setPen(QPen(color,3))#,  Qt.DotLine))    
                painter.drawLine(from_x, from_y, to_x, to_y)
                painter.drawPolyline(arrowCalc(from_x, from_y, to_x,to_y))
        
    '''            
    def drawLineArrow(self, fromX, fromY, toX, toY):

        headlen = 0.2 * 1.41 * math.sqrt((fromX - toX) * (fromX - toX) + (fromY - toY) * (fromY - toY)) #箭头头部长度

        if headlen > 160 : #40是箭头头部最大值
            headlen = 160

        theta = 30 #自定义箭头线与直线的夹角
        
        #计算各角度和对应的箭头终点坐标

        angle = math.atan2(fromY - toY, fromX - toX) * 180 / math.pi
        angle1 = (angle + theta) * math.pi / 180
        angle2 = (angle - theta) * math.pi / 180

        topX = headlen * math.cos(angle1)
        topY = headlen * math.sin(angle1)
        botX = headlen * math.cos(angle2)
        botY = headlen * math.sin(angle2)

        toLeft = fromX > toX
        toUp = fromY > toY

        #箭头最上点
        arrowX = toX + topX
        arrowY = toY + topY

        #箭头下拐点
        arrowX1 = toX + botX
        arrowY1 = toY + botY

        #箭头上拐点
        arrowX2 = arrowX + 0.25 * abs(arrowX1 - arrowX) if toUp else  arrowX - 0.25 * abs(arrowX1 - arrowX)
        arrowY2 = arrowY - 0.25 * abs(arrowY1 - arrowY) if toLeft else arrowY + 0.25 * abs(arrowY1 - arrowY)

        #箭头最下点
        arrowX3 = arrowX + 0.75 * abs(arrowX1 - arrowX) if toUp else arrowX - 0.75 * abs(arrowX1 - arrowX);
        arrowY3 = arrowY - 0.75 * abs(arrowY1 - arrowY) if toLeft else arrowY + 0.75 * abs(arrowY1 - arrowY);

        return QPolygon([QPoint(fromX, fromY), 
                        QPoint(arrowX2, arrowY2), 
                        QPoint(arrowX, arrowY),
                        QPoint(toX, toY),
                        QPoint(arrowX1, arrowY1),
                        QPoint(arrowX3, arrowY3),
                        QPoint(fromX, fromY),
                        ])

    '''

    def mousePressEvent(self, mouseEvent):
        
        if (mouseEvent.button() == Qt.RightButton):
            self.rightMouseSignal.emit(True)
            
        if self.view_only:
            return

        if (mouseEvent.button() != Qt.LeftButton):
            return

        if len(self.move_steps_show) > 0:
            return

        pos = mouseEvent.pos()
        key = x, y = self.board_to_logic(pos.x(), pos.y())

        #数据合法校验
        if key[0] < 0 or key[0] > 8:
            return
        if key[1] < 0 or key[1] > 9:
            return

        piece = self._board.get_piece(key)

        if piece and piece.color == self._board.move_player.color:
            #pickup and clear last move
            self.last_pickup = key
            self.last_pickup_moves = list(self._board.create_piece_moves(key))

        else:
            # move check
            if self.last_pickup:
                if key != self.last_pickup:
                    self.try_move(self.last_pickup, key)
            else:
                #此处会清空最优步骤提示
                self.clearPickup()

        self.update()

    def mouseMoveEvent(self, mouseEvent):
        pass

    def mouseReleaseEvent(self, mouseEvent):
        if (mouseEvent.button() == Qt.RightButton):
            self.rightMouseSignal.emit(False)
            
    def make_show_steps(self, p_from, p_to, step_diff):

        move_man = self._board.get_piece(p_from)

        board_p_from = self.logic_to_board(p_from[0], p_from[1])
        board_p_to = self.logic_to_board(p_to[0], p_to[1])

        step = ((board_p_to[0] - board_p_from[0]) // step_diff,
                (board_p_to[1] - board_p_from[1]) // step_diff)

        steps = []

        for i in range(step_diff):

            x = board_p_from[0] + step[0] * i
            y = board_p_from[1] + step[1] * i

            steps.append((move_man, (x, y)))

        steps.append((move_man, board_p_to))

        return steps

    def try_move(self, move_from, move_to):

        if not self._board.is_valid_move(move_from, move_to):
            self.clearPickup()
            return False

        checked = self._board.is_checked_move(move_from, move_to)
        if checked:
            #if self.last_checked:
            #    msg = "    必须应将!    "
            #else:
            msg = "    不能送将!    "

            msgbox = TimerMessageBox(msg, timeout=1)
            msgbox.exec_()

            return False

        self.tryMoveSignal.emit(move_from, move_to)
        return True


#---------------------------------------------------------#
class PiecesDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle("局面编辑")
        
        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.redMoveBtn, 0)
        hbox1.addWidget(self.blackMoveBtn, 0)
        hbox1.addWidget(QLabel(''), 1)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox1)

        hbox = QHBoxLayout()
        
        vbox.addLayout(hbox)
        self.setLayout(vbox)

#---------------------------------------------------------#
class ChessBoardEditWidget(ChessBoardBaseWidget):
    fenChangedSignal = Signal(str)

    def __init__(self):

        super().__init__(ChessBoard())
        
        self.last_selected = None
        self._new_pos = None
        self.fenChangedSignal.connect(self.onFenChanged)
    
    def selectPiecesDlg(self):
        #dlg = QPoint()
        pass


    def showContextMenu(self, pos):

        x, y = self.board_to_logic(pos.x(), pos.y())
        
        if x < 0 or x > 8:
            return
        
        if y < 0 or y > 9:
            return
            
        fench = self._board.get_fench((x, y))

        if fench:
            self.last_selected = (x, y)
        else:
            self._new_pos = (x, y)

        fen_str = self._board.to_fen()

        self.contextMenu = QMenu(self)
        
        copyAction = self.contextMenu.addAction('复制(Fen)')
        copyAction.triggered.connect(self.onCopy)
        pasteAction = self.contextMenu.addAction('粘贴(Fen)')
        pasteAction.triggered.connect(self.onPaste)
        self.contextMenu.addSeparator()
        actionDel = self.contextMenu.addAction('删除')
        if not self.last_selected:
            actionDel.setEnabled(False)

        readMenu = self.contextMenu.addMenu('添加红方棋子')

        actionAdd_RK = readMenu.addAction("帅")
        if fen_str.count("K") > 0:
            actionAdd_RK.setEnabled(False)

        actionAdd_RA = readMenu.addAction("仕")
        if fen_str.count("A") > 1:
            actionAdd_RA.setEnabled(False)

        actionAdd_RB = readMenu.addAction("相")
        if fen_str.count("B") > 1:
            actionAdd_RB.setEnabled(False)

        actionAdd_RN = readMenu.addAction("马")
        if fen_str.count("N") > 1:
            actionAdd_RN.setEnabled(False)

        actionAdd_RR = readMenu.addAction("车")
        if fen_str.count("R") > 1:
            actionAdd_RR.setEnabled(False)

        actionAdd_RC = readMenu.addAction("炮")
        if fen_str.count("C") > 1:
            actionAdd_RC.setEnabled(False)

        actionAdd_RP = readMenu.addAction("兵")
        if fen_str.count("P") > 4:
            actionAdd_RP.setEnabled(False)

        blackMenu = self.contextMenu.addMenu('添加黑方棋子')

        actionAdd_BK = blackMenu.addAction("将")
        if fen_str.count("k") > 0:
            actionAdd_BK.setEnabled(False)

        actionAdd_BA = blackMenu.addAction("士")
        if fen_str.count("a") > 1:
            actionAdd_BA.setEnabled(False)

        actionAdd_BB = blackMenu.addAction("象")
        if fen_str.count("b") > 1:
            actionAdd_BB.setEnabled(False)

        actionAdd_BN = blackMenu.addAction("马")
        if fen_str.count("n") > 1:
            actionAdd_BN.setEnabled(False)

        actionAdd_BR = blackMenu.addAction("车")
        if fen_str.count("r") > 1:
            actionAdd_BR.setEnabled(False)

        actionAdd_BC = blackMenu.addAction("炮")
        if fen_str.count("c") > 1:
            actionAdd_BC.setEnabled(False)

        actionAdd_BP = blackMenu.addAction("卒")
        if fen_str.count("p") > 4:
            actionAdd_BP.setEnabled(False)

        actionDel.triggered.connect(self.onActionDel)

        actionAdd_RK.triggered.connect(self.onActionAdd_RK)
        actionAdd_RA.triggered.connect(self.onActionAdd_RA)
        actionAdd_RB.triggered.connect(self.onActionAdd_RB)
        actionAdd_RN.triggered.connect(self.onActionAdd_RN)
        actionAdd_RR.triggered.connect(self.onActionAdd_RR)
        actionAdd_RC.triggered.connect(self.onActionAdd_RC)
        actionAdd_RP.triggered.connect(self.onActionAdd_RP)

        actionAdd_BK.triggered.connect(self.onActionAdd_BK)
        actionAdd_BA.triggered.connect(self.onActionAdd_BA)
        actionAdd_BB.triggered.connect(self.onActionAdd_BB)
        actionAdd_BN.triggered.connect(self.onActionAdd_BN)
        actionAdd_BR.triggered.connect(self.onActionAdd_BR)
        actionAdd_BC.triggered.connect(self.onActionAdd_BC)
        actionAdd_BP.triggered.connect(self.onActionAdd_BP)

        self.contextMenu.move(QCursor.pos())
        self.contextMenu.show()
    
    def onCopy(self):
         cb = QApplication.clipboard()
         cb.clear()
         cb.setText(self.to_fen())
                
    def onPaste(self):
         fen = QApplication.clipboard().text()
         self.from_fen(fen)
         
    def onActionDel(self):
        if self.last_selected:
            self.removePiece(self.last_selected)
            self.last_selected = None
            self.update()

    def onActionAdd_RK(self):
        self.onActionAddPiece('K')

    def onActionAdd_BK(self):
        self.onActionAddPiece('k')

    def onActionAdd_RA(self):
        self.onActionAddPiece('A')

    def onActionAdd_BA(self):
        self.onActionAddPiece('a')

    def onActionAdd_RB(self):
        self.onActionAddPiece('B')

    def onActionAdd_BB(self):
        self.onActionAddPiece('b')

    def onActionAdd_RN(self):
        self.onActionAddPiece('N')

    def onActionAdd_BN(self):
        self.onActionAddPiece('n')

    def onActionAdd_RR(self):
        self.onActionAddPiece('R')

    def onActionAdd_BR(self):
        self.onActionAddPiece('r')

    def onActionAdd_RC(self):
        self.onActionAddPiece('C')

    def onActionAdd_BC(self):
        self.onActionAddPiece('c')

    def onActionAdd_RP(self):
        self.onActionAddPiece('P')

    def onActionAdd_BP(self):
        self.onActionAddPiece('p')

    def onActionAddPiece(self, fench):

        if not self._new_pos:
            return False

        self.newPiece(fench, self._new_pos)

        self._new_pos = None
        self.update()

    def from_fen(self, fen):
        super().from_fen(fen)
        self.fenChangedSignal.emit(self.to_fen())
    
    def set_move_color(self, color):
        self._board.set_move_color(color)
        self.fenChangedSignal.emit(self.to_fen())

    def get_move_color(self):
        return self._board.get_move_color()

    def newPiece(self, fench, pos):
        self._board.put_fench(fench, pos)
        self.fenChangedSignal.emit(self.to_fen())

    def removePiece(self, pos):
        self._board.remove_fench(pos)
        self.fenChangedSignal.emit(self.to_fen())
    
    def onFenChanged(self, fen):
        self.update()
        
    def paintEvent(self, ev):
        super().paintEvent(ev)
        #painter = QPainter(self)

    def mousePressEvent(self, mouseEvent):
        if (mouseEvent.button() != Qt.LeftButton):
            return

        pos = mouseEvent.pos()

        x, y = self.board_to_logic(pos.x(), pos.y())
        self.update()

    def mouseMoveEvent(self, mouseEvent):
        pass

    def mouseReleaseEvent(self, mouseEvent):
        pass

