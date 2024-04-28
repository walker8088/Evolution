# -*- coding: utf-8 -*-

import sys, time

from PySide6 import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from cchess import *

from .Utils import *
from .Resource import *


#-----------------------------------------------------#
def scaled_image(img, scale):

    if scale == 1.0:
        return img

    new_height = int(img.height() * scale)
    new_img = img.scaledToHeight(new_height, mode=Qt.SmoothTransformation)

    return new_img


#-----------------------------------------------------#
class ChessBoardBase(QWidget):
    def __init__(self, board):

        super().__init__()

        self._board = board

        self.flip_board = False
        self.mirror_board = False

        self.last_pickup = None

        self.base_board_img = QPixmap(':Images/board.png')
        self.base_select_img = QPixmap(':Images/select.png')
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

        self.scale_board(1.0)

    def scale_board(self, scale):

        if scale < 0.7:
            scale = 0.7

        self.paint_scale = int(scale * 7) / 7.0

        self.space = int(self.base_space * self.paint_scale)
        self.boader = int(self.base_boader * self.paint_scale)
        self.piece_size = int(self.base_piece_size * self.paint_scale)
        self.board_width = int(self.base_board_width * self.paint_scale)
        self.board_height = int(self.base_board_height * self.paint_scale)

        self._board_img = scaled_image(self.base_board_img, self.paint_scale)
        self.select_img = scaled_image(self.base_select_img, self.paint_scale)
        self.point_img = scaled_image(self.base_point_img, self.paint_scale)
        self.done_img = scaled_image(self.base_done_img, self.paint_scale)
        self.over_img = scaled_image(self.base_over_img, self.paint_scale)

        self.pieces_img = {}
        for name in ['k', 'a', 'b', 'r', 'n', 'c', 'p']:
            self.pieces_img[name] = scaled_image(self.base_pieces_img[name],
                                                 self.paint_scale)

    def from_fen(self, fen_str=''):
        self._board.from_fen(fen_str)
        self.clear_pickup()

    def to_fen(self):
        return self._board.to_fen()

    def clear_pickup(self):
        self.last_pickup = None
        self.update()

    def logic_to_board(self, x, y):

        if self.flip_board:
            x = 8 - x
            y = 9 - y

        if self.mirror_board:
            x = 8 - x

        board_x = self.boader + x * self.space + self.start_x
        board_y = self.boader + (9 - y) * self.space + self.start_y

        return (board_x, board_y)

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

        self.scale_board(new_scale)

        self.start_x = (new_width - self.board_width) // 2
        if self.start_x < 0:
            self.start_x = 0

        self.start_y = (new_height - self.board_height) // 2
        if self.start_y < 0:
            self.start_y = 0

    def paintEvent(self, ev):
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

    def mousePressEvent(self, mouseEvent):

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
            if self.last_pickup and key != self.last_pickup:
                #app.try_move(self.last_pickup, key)
                self.try_move(self.last_pickup, key)
                #pass

        self.update()

    def mouseMoveEvent(self, mouseEvent):
        pass

    def mouseReleaseEvent(self, mouseEvent):
        pass

    def sizeHint(self):
        return QSize(self.base_board_width + 30, self.base_board_height + 10)


#-----------------------------------------------------#
class ChessBoardView(ChessBoardBase):
    try_move_signal = Signal(tuple, tuple)

    def __init__(self, board):

        super().__init__(board)

        self._board = board
        self.text = ''
        self.view_only = False

        self.last_pickup = None
        self.last_pickup_moves = []
        self.move_steps_show = []

        self.done = []

        self.move_steps_show = []

        self.start_x = 0
        self.start_y = 0

        self.timer = QTimer()
        self.timer.timeout.connect(self.moveShowEvent)

    def set_view_only(self, yes):
        self.view_only = yes

    def show_move(self, p_from, p_to):
        self.last_pickup = None
        self.last_pickup_moves = []
        self.make_log_step_move(p_from, p_to)
        self.last_move = (p_from, p_to)

    def clear_pickup(self):
        self.last_pickup = None
        self.last_pickup_moves = []
        self.update()

    def make_log_step_move(self, p_from, p_to):

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
        if self.text != '':
            painter.setPen(QColor(34, 168, 3))
            painter.setFont(QFont('Decorative', 16))
            er = ev.rect()
            rect = QRect(er.left(), er.top(), er.width(), 30) 
            painter.drawText(rect, Qt.AlignCenter, self.text)
    '''
        for move_it in self.last_pickup_moves:
            board_x, board_y = self.logic_to_board(*move_it[1])
            painter.drawPixmap(
                QPoint(board_x, board_y), self.point_img,
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
            #painter.drawPixmap(
            #    QPoint(step_point[0], step_point[1]), self.select_img,
            #    QRect(offset, 0, 52, 52))

    def mousePressEvent(self, mouseEvent):

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
            if self.last_pickup and key != self.last_pickup:
                #app.try_move(self.last_pickup, key)
                self.try_move(self.last_pickup, key)
                #pass

        self.update()

    def mouseMoveEvent(self, mouseEvent):
        pass

    def mouseReleaseEvent(self, mouseEvent):
        pass

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
            self.clear_pickup()
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

        self.try_move_signal.emit(move_from, move_to)
        return True


#---------------------------------------------------------#
class ChessBoardEditWidget(ChessBoardBase):
    fenChangedSignal = Signal(str)

    def __init__(self):

        super().__init__(ChessBoard())

        self.last_selected = None
        self._new_pos = None

        self.createContextMenu()

    def createContextMenu(self):

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)

    def showContextMenu(self, pos):

        x, y = self.board_to_logic(pos.x(), pos.y())

        fench = self._board.get_fench((x, y))

        if fench:
            self.last_selected = (x, y)
        else:
            self._new_pos = (x, y)

        fen_str = self._board.to_fen()

        self.contextMenu = QMenu(self)

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
