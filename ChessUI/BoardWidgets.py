# -*- coding: utf-8 -*-

import math

#from PySide6 import qApp
from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QSize, QRect
from PySide6.QtGui import QPixmap, QCursor, QPen, QColor, QPainter, QPolygon
from PySide6.QtWidgets import QMenu, QWidget, QApplication

from cchess import ChessBoard, RED, iccs2pos

from .Utils import TimerMessageBox
from .Resource import qt_resource_data

#-----------------------------------------------------#
def scaleImage(img, scale):

    if scale == 1.0:
        return img

    new_height = int(img.height() * scale)
    new_img = img.scaledToHeight(new_height, mode=Qt.SmoothTransformation)

    return new_img

#-----------------------------------------------------#
class ChessBoardBaseWidget(QWidget):
    
    def __init__(self, board):

        super().__init__()

        self._board = board

        self.flip_board = False
        self.mirror_board = False

        self.last_pickup = None

        self.base_board_img = QPixmap(':Images/board.png')
        self.base_select_img = QPixmap(':Images/select.png')
        self.base_step_img = QPixmap(':Images/step.png')
        self.base_point_img = QPixmap(':Images/point.png')
        self.base_done_img = QPixmap(':Images/done.png')
        self.base_over_img = QPixmap(':Images/over.png')

        self.base_pieces_img = {}
        for name in ['k', 'a', 'b', 'r', 'n', 'c', 'p']:
            self.base_pieces_img[name] = QPixmap(':Images/{}.png'.format(name))

        self.setAutoFillBackground(True)

        p = self.palette()
        p.setColor(self.backgroundRole(), QColor(40, 40, 40))
        self.setPalette(p)

        self.start_x = 0
        self.start_y = 0
        self.paint_scale = 1.0

        self.base_space = 56
        self.base_boader = 15
        self.base_piece_size = 53
        self.base_board_width = 530
        self.base_board_height = 586

        self.scaleBoard(1.0)
        
        #self.setMinimumSize(self.base_board_width + 20, self.base_board_height + 10) 
        
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)

    def scaleBoard(self, scale):

        if scale < 0.5:
            scale = 0.5

        self.paint_scale = int(scale * 7) / 7.0

        self.space = int(self.base_space * self.paint_scale)
        self.boader = int(self.base_boader * self.paint_scale)
        self.piece_size = int(self.base_piece_size * self.paint_scale)
        self.board_width = int(self.base_board_width * self.paint_scale)
        self.board_height = int(self.base_board_height * self.paint_scale)

        self._board_img = scaleImage(self.base_board_img, self.paint_scale)
        self.select_img = scaleImage(self.base_select_img, self.paint_scale)
        self.step_img = scaleImage(self.base_step_img, self.paint_scale)
        self.point_img = scaleImage(self.base_point_img, self.paint_scale)
        self.done_img = scaleImage(self.base_done_img, self.paint_scale)
        self.over_img = scaleImage(self.base_over_img, self.paint_scale)

        self.pieces_img = {}
        for name in ['k', 'a', 'b', 'r', 'n', 'c', 'p']:
            self.pieces_img[name] = scaleImage(self.base_pieces_img[name],
                                                 self.paint_scale)

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

        new_width = ev.size().width()
        new_height = ev.size().height()
        new_scale = min(new_width / self.base_board_width,
                        new_height / self.base_board_height)

        self.scaleBoard(new_scale)

        self.start_x = (new_width - self.board_width) // 2
        if self.start_x < 0:
            self.start_x = 0

        self.start_y = (new_height - self.board_height) // 2
        if self.start_y < 0:
            self.start_y = 0

    def paintEvent(self, ev):
        #return
        painter = QPainter(self)
        painter.drawPixmap(self.start_x, self.start_y, self._board_img)

        for piece in self._board.get_pieces():
            board_x, board_y = self.logic_to_board(piece.x, piece.y)

            if piece.color == RED:
                offset = 0
            else:
                offset = self.piece_size

            painter.drawPixmap(
                QPoint(board_x, board_y), self.pieces_img[piece.fench.lower()],
                QRect(offset, 0, self.piece_size - 1, self.piece_size - 1))

            if (piece.x, piece.y) == self.last_pickup:
                painter.drawPixmap(
                    QPoint(board_x, board_y), self.select_img,
                    QRect(0, 0, self.piece_size - 1, self.piece_size - 1))

    def showContextMenu(self, pos):
        #print('height')
        pass

    def sizeHint(self):
        return QSize(self.base_board_width + 20, self.base_board_height + 10)


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

        self.start_x = 0
        self.start_y = 0

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
  
    def showBestMoveNext(self, best_next_moves):
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

        for move_it in self.last_pickup_moves:
            board_x, board_y = self.logic_to_board(*move_it[1])
            painter.drawPixmap(
                QPoint(board_x, board_y), self.point_img,
                QRect(0, 0, self.piece_size - 1, self.piece_size - 1))
        
        for pos in  self.move_pieces:
            board_x, board_y = self.logic_to_board(*pos)
            painter.drawPixmap(
                QPoint(board_x, board_y), self.step_img,
                QRect(0, 0, self.piece_size - 1, self.piece_size - 1))
        
        if len(self.move_steps_show) > 0:
            piece, step_point = self.move_steps_show.pop(0)

            if piece.color == RED:
                offset = 0
            else:
                offset = self.piece_size

            painter.drawPixmap(
                QPoint(step_point[0], step_point[1]),
                self.pieces_img[piece.fench.lower()],
                QRect(offset, 0, self.piece_size - 1, self.piece_size - 1))
        
        if self.is_show_best_move:
            for p_from, p_to in self.best_moves: 
                
                r = self.piece_size//2
                from_x, from_y = self.logic_to_board(*p_from,r)   
                to_x, to_y = self.logic_to_board(*p_to, r)   
                
                '''
                if p_color == RED:
                    color = Qt.darkGreen
                else:
                    color = Qt.darkRed
                '''
                
                color = Qt.darkGreen
                
                painter.setPen(QPen(color,3))#,  Qt.DotLine))    
                painter.drawLine(from_x, from_y, to_x, to_y)
                painter.drawEllipse(QPoint(from_x, from_y), r, r)
                #painter.setBrush(QBrush(color, Qt.CrossPattern))
                painter.drawEllipse(QPoint(to_x, to_y), r//4, r//4)
                
                #arrow = self.arrowCalc(QPoint(from_x,from_y), QPoint(to_x,to_x))
                #if arrow:
                #    print(arrow)
                #    painter.drawPolyline(arrow)
        
        for p_from, p_to in self.best_next_moves: 
                r = self.piece_size//2
                from_x, from_y = self.logic_to_board(*p_from,r)   
                to_x, to_y = self.logic_to_board(*p_to, r)   
                
                color = Qt.darkGreen
                
                painter.setPen(QPen(color,3))#,  Qt.DotLine))    
                painter.drawLine(from_x, from_y, to_x, to_y)
                painter.drawEllipse(QPoint(from_x, from_y), r, r)
                #painter.setBrush(QBrush(color, Qt.CrossPattern))
                painter.drawEllipse(QPoint(to_x, to_y), r//4, r//4)
                
    def arrowCalc(self, startPoint, endPoint): 

        dx, dy = startPoint.x() - endPoint.x(), startPoint.y() - endPoint.y()

        leng = math.sqrt(dx ** 2 + dy ** 2)
        normX, normY = dx / leng, dy / leng  # normalize

        # perpendicular vector
        perpX = -normY
        perpY = normX
        
        _arrow_height = 10
        _arrow_width = 10
        
        leftX = endPoint.x() + _arrow_height * normX + _arrow_width * perpX
        leftY = endPoint.y() + _arrow_height * normY + _arrow_width * perpY

        rightX = endPoint.x() +_arrow_height * normX - _arrow_width * perpX
        rightY = endPoint.y() + _arrow_height * normY - _arrow_width * perpY

        point2 = QPoint(leftX, leftY)
        point3 = QPoint(rightX, rightY)

        return QPolygon([point2, endPoint, point3])
        
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
class ChessBoardEditWidget(ChessBoardBaseWidget):
    fenChangedSignal = Signal(str)

    def __init__(self):

        super().__init__(ChessBoard())

        self.last_selected = None
        self._new_pos = None
        self.fenChangedSignal.connect(self.onFenChanged)
        
    def showContextMenu(self, pos):

        x, y = self.board_to_logic(pos.x(), pos.y())

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

#-----------------------------------------------------#
"""
from PIL.ImageQt import ImageQt

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
        self.paint_scale = 1.0

        self.base_space = 56
        self.base_boader = 15
        self.base_piece_size = 53
        
        self.base_win_width = 530
        self.win_width = 530
        
        self.base_win_height = 586
        self.win_height = 586
    
        self.base_win_img = None
        self.win_img = None

    def scaleBoard(self, scale):

        if scale < 0.5:
            scale = 0.5

        self.paint_scale = int(scale * 9) / 9.0
        if self.base_win_img:
            self.win_img = scaleImage(self.base_win_img, self.paint_scale)
            self.win_width = self.win_img.width()
            self.win_height = self.win_img.height()
            
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

        new_width = ev.size().width()
        new_height = ev.size().height()
        
        new_scale = min(new_width / self.base_win_width,
                        new_height / self.base_win_height)

        self.scaleBoard(new_scale)

        self.start_x = (new_width - self.win_width) // 2
        if self.start_x < 0:
            self.start_x = 0

        self.start_y = (new_height - self.win_height) // 2
        if self.start_y < 0:
            self.start_y = 0

    def updateImage(self, img):
        
        self.cv_img = pil2cv_image(img)
        
        self.base_win_img =  QPixmap.fromImage(ImageQt(img))
        
        self.base_win_width =  self.base_win_img.width()
        self.base_win_height =  self.base_win_img.height()
        
        self.scaleBoard( self.paint_scale)

        self.update()
        
    def paintEvent(self, ev):
        painter = QPainter(self)
        if self.win_img:
            painter.drawPixmap(self.start_x,  self.start_y, self.win_img)

    def detectBoard(self):
        img_src = self.cv_img.copy()
        
        gray_img = cv.cvtColor(img_src, cv.COLOR_BGR2GRAY)
        dst = cv.equalizeHist(gray_img)
        # 高斯滤波降噪
        gaussian = cv.GaussianBlur(dst, (5, 5), 0)
        # 边缘检测
        edges = cv.Canny(gaussian, 70, 150)
        
        # Hough 直线检测
        # 重点注意第四个参数 阈值，只有累加后的值高于阈值时才被认为是一条直线，也可以把它看成能检测到的直线的最短长度（以像素点为单位）
        # 在霍夫空间理解为：至少有多少条正弦曲线交于一点才被认为是直线
        #lines = cv.HoughLines(edges, 1.0, np.pi/180, 150)
        lines = cv.HoughLinesP(edges, 1.0, np.pi/180, 350)
        
        #for line in lines: # line[0]存储的是点到直线的极径和极角，其中极角是弧度表示的，theta是弧度 rho, theta = line[0] # 下述代码为获取 (x0,y0) 具体值 a = np.cos(theta) b = np.sin(theta) x0 = a*rho y0 = b*rho # 下图 1000 的目的是为了将线段延长 # 以 (x0,y0) 为基础，进行延长 x1 = int(x0+1000*(-b)) y1 = int(y0+1000*a) x2 = int(x0-1000*(-b)) y2 = int(y0-1000*a) cv.line(src, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        
        r_min = img_src.shape[1] // 60
        r_max = int(r_min * 4)
        print(r_min, r_max)
        # 图像预处理
        gray = cv.cvtColor(img_src, cv.COLOR_BGR2GRAY)
        #img = cv.medianBlur(gray, 7)
        gaussian = cv.GaussianBlur(gray, (7, 7),0)
        circles = cv.HoughCircles(gaussian,cv.HOUGH_GRADIENT,1, r_min, param1=100, param2=50, minRadius=r_min, maxRadius=r_max)
        
        if circles is None:
            return False
            
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

       # for line in lines: 
       #    x1, y1, x2, y2 = line[0] 
       #    cv.line(img_src, (x1, y1), (x2, y2), (0, 255, 0), 2)

        #cv.imshow('CIRCLE BOARD', img_src)
        #cv.waitKey(0)
        '''
        x_points = []
        y_points = []
        r_min = -1
        
        img_src = self.cv_img.copy()
                
        for y_key, it in y_counts.items():
            if len(it) == 9:
                for x, y, r in it:
                    cv.circle(img_src, (x, y), r, (255, 0, 0), 1, cv.LINE_AA)
                    x_points.append(x)
                    y_points.append(y)
                        
                    if r_min < 0 or r < r_min:
                        r_min = r
    '''
        #self.updateImage(cv2pil_image(edges))
        self.updateImage(cv2pil_image(img_src))
        return
        
        board_rect = [min(x_points), min(y_points), max(x_points), max(y_points)]
        
        self.img_size = self.cv_img.shape[:2]
        self.board_begin = board_rect[:2]
        self.board_end = board_rect[2:]
        #self.calc_grid()
        #self.piece_size = r_min
        
        #cv.rectangle(img_src, self.board_begin, self.board_end, (255, 0, 0), 2)
        
        
        return
        for x in range(9):
            for y in range(10):
                cv.circle(img_src, self.board_to_img(x, y), self.piece_size, (0, 0, 255), 1, cv.LINE_AA)
                pass
                
        '''
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
    ''' 

    def mousePressEvent(self, mouseEvent):
        pass
        
    def mouseMoveEvent(self, mouseEvent):
        pass

    def mouseReleaseEvent(self, mouseEvent):
        pass
    
 """    