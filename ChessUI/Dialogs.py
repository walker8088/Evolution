
import os
import logging
import traceback

from PySide6.QtCore import Qt, Signal, QByteArray, QSize
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from PySide6.QtWidgets import QStyle, QApplication, QMenu, QHBoxLayout, QVBoxLayout, QFormLayout, QDialog, QFileDialog,\
                    QLabel, QSpinBox, QCheckBox, QPushButton, QRadioButton, \
                    QWidget, QDockWidget, QDialogButtonBox, QButtonGroup, QListWidget, QListWidgetItem, QInputDialog, \
                    QAbstractItemView, QComboBox, QTreeWidgetItem, QTreeWidget, QSplitter, QMessageBox

import cchess
from cchess import ChessBoard

from .BoardWidgets import ChessBoardEditWidget
from .SnippingWidget import SnippingWidget

#-----------------------------------------------------#
class SliderWithValue(QSlider):

    def __init__(self, parent=None):
        super(SliderWithValue, self).__init__(parent)

        self.stylesheet = """
        QSlider::groove:vertical {
                background-color: #222;
                width: 30px;
        }
        QSlider::handle:vertical {
            border: 1px #438f99;
            border-style: outset;
            margin: -2px 0;
            width: 30px;
            height: 3px;
            background-color: #438f99;
        }
        QSlider::sub-page:vertical {
            background: #4B4B4B;
        }
        QSlider::groove:horizontal {
                background-color: #222;
                height: 30px;
        }
        QSlider::handle:horizontal {
            border: 1px #438f99;
            border-style: outset;
            margin: -2px 0;
            width: 3px;
            height: 30px;
            background-color: #438f99;
        }
        QSlider::sub-page:horizontal {
            background: #4B4B4B;
        }
        """

        # self.setStyleSheet(self.stylesheet)

    def paintEvent(self, event):
        QSlider.paintEvent(self, event)

        curr_value = str(self.value() / 1000.00)
        round_value = round(float(curr_value), 2)

        painter = QPainter(self)
        painter.setPen(QPen(Qt.white))

        font_metrics = QFontMetrics(self.font())
        font_width = font_metrics.boundingRect(str(round_value)).width()
        font_height = font_metrics.boundingRect(str(round_value)).height()

        rect = self.geometry()
        if self.orientation() == Qt.Horizontal:
            horizontal_x_pos = rect.width() - font_width - 5
            horizontal_y_pos = rect.height() * 0.75

            painter.drawText(QtCore.QPoint(horizontal_x_pos, horizontal_y_pos), str(round_value))

        elif self.orientation() == Qt.Vertical:
            vertical_x_pos = rect.width() - font_width - 5
            vertical_y_pos = rect.height() * 0.75

            painter.drawText(QPoint(rect.width() / 2.0 - font_width / 2.0, rect.height() - 5), str(round_value))
        else:
            pass

        painter.drawRect(rect)

#-----------------------------------------------------#
class PositionEditDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle("局面编辑")

        self.boardEdit = ChessBoardEditWidget()
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

        initBtn = QPushButton("初始棋盘", self)
        clearBtn = QPushButton("清空棋盘", self)
        openImgBtn = QPushButton("打开图片", self)
        initBtn.clicked.connect(self.onInitBoard)
        clearBtn.clicked.connect(self.onClearBoard)
        openImgBtn.clicked.connect(self.onOpenImage)
        
        okBtn = QPushButton("确定", self)
        cancelBtn = QPushButton("取消", self)

        vbox = QVBoxLayout()
        vbox.addWidget(self.boardEdit)
        vbox.addWidget(self.fenLabel)
        vbox.addLayout(hbox1)

        hbox = QHBoxLayout()
        hbox.addWidget(self.redMoveBtn)
        hbox.addWidget(self.blackMoveBtn)
        hbox.addWidget(initBtn)
        hbox.addWidget(clearBtn)
        hbox.addWidget(openImgBtn)
        hbox.addWidget(okBtn)
        hbox.addWidget(cancelBtn)

        vbox.addLayout(hbox)
        self.setLayout(vbox)

        self.boardEdit.fenChangedSignal.connect(self.onBoardFenChanged)
        self.redMoveBtn.clicked.connect(self.onRedMoveBtnClicked)
        self.blackMoveBtn.clicked.connect(self.onBlackMoveBtnClicked)

        okBtn.clicked.connect(self.accept)
        cancelBtn.clicked.connect(self.close)
        
        self.snippingWidget = SnippingWidget()
        self.snippingWidget.onSnippingCompleted = self.onSnippingCompleted

    def onInitBoard(self):
        self.boardEdit.from_fen(cchess.FULL_INIT_FEN)

    def onClearBoard(self):
        self.boardEdit.from_fen(cchess.EMPTY_FEN)

    def onRedMoveBtnClicked(self):
        self.boardEdit.set_move_color(cchess.RED)

    def onBlackMoveBtnClicked(self):
        self.boardEdit.set_move_color(cchess.BLACK)
    
    def onOpenImage(self):
        self.snippingWidget.start()

    def onSnippingCompleted(self, img):
        self.setWindowState(Qt.WindowActive)
        
    def onBoardFenChanged(self, fen):

        self.fenLabel.setText(fen)

        color = self.boardEdit.get_move_color()
        if color == cchess.RED:
            self.redMoveBtn.setChecked(True)
        elif color == cchess.BLACK:
            self.blackMoveBtn.setChecked(True)

    def edit(self, fen_str):
        self.boardEdit.from_fen(fen_str)

        if self.exec_() == QDialog.Accepted:
            return self.boardEdit.to_fen()
        else:
            return None


#-----------------------------------------------------#
class PositionHistDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        #self.setFixedSize(200, 120)

        self.setWindowTitle("局面推演")

        vbox = QVBoxLayout()

        self.boardEdit = BoardHistoryWidget()
        vbox.addWidget(self.boardEdit)

        okBtn = QPushButton("完成", self)
        #cancelBtn = QPushButton("取消", self)
        #self.quit.setGeometry(62, 40, 75, 30)

        hbox = QHBoxLayout()
        hbox.addWidget(okBtn)
        vbox.addLayout(hbox)
        self.setLayout(vbox)

        okBtn.clicked.connect(self.accept)
        #cancelBtn.clicked.connect(self.onClose)

    def onInitBoard(self):
        self.boardEdit.from_fen(cchess.FULL_INIT_FEN)
        self.fenLabel.setText(self.boardEdit.to_fen())

#--------------------------------------------------------------#
class ImageView(QWidget):
    def __init__(self, parent, img=None):
        super().__init__()
        
        self.parent = parent
        
        self.left = 0
        self.top = 0
        self.height = 0
        self.width = 0
        self.view_size = None
        
        self.setImage(img)
        
    def setImage(self, img):
        self.img = img
        if img is None:
            return 
        self.height = img.size().height()
        self.width  = img.size().width()
        self.pixmap = img #QPixmap.fromImage() 
        
        pixelRatio = qApp.devicePixelRatio()
        self.pixmap = self.pixmap.scaled(img.size() * pixelRatio, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.pixmap.setDevicePixelRatio(pixelRatio)
    
        v_size = self.parent.size()
        width = max(self.width, v_size.width())
        height = max(self.height, v_size.height())
        self.setGeometry(0, 0, width, height)

        self.resize()
        self.update()

        
    def resize(self):
       
        if self.view_size is None:
            self.left = 0
            self.top = 0
            return

        self.left = (self.view_size.width() - self.width) // 2
        if self.left < 0:
            self.left = 0

        self.top = (self.view_size.height() - self.height) // 2
        if self.top < 0:
            self.top = 0
        
    def resizeEvent(self, ev):
        self.view_size = ev.size()
        self.resize()
    
    def paintEvent(self, ev):
        painter = QPainter(self)
        if self.pixmap is not None:
            painter.drawPixmap(self.left, self.top, self.pixmap)
    
    def minimumSizeHint(self):
        return QSize(self.width, self.height)
    
    def showValue(self, pos):
        if (pos.x() < self.left) or (pos.x() >= self.left + self.width)\
            or (pos.y() < self.top) or (pos.y() >= self.top + self.height):
            self.setCursor(Qt.ArrowCursor)
            main_win.status('')
        else:    
            x = pos.x() - self.left
            y = pos.y() - self.top
            pixel = self.img[y,x]
            main_win.status('x={} y={} value={}'.format(x, y, str(pixel)))
            self.setCursor(Qt.CrossCursor) 
        
    def mousePressEvent(self, mouseEvent):
        
        if self.img is None:
            return
            
        if (mouseEvent.button() != Qt.LeftButton):
            return
        
        self.showValue(mouseEvent.position())        
        
    def mouseMoveEvent(self, mouseEvent):
        
        if self.img is None:
            return
        
        self.showValue(mouseEvent.position())        
        
        
    def mouseReleaseEvent(self, mouseEvent):
        self.setCursor(Qt.ArrowCursor)
        

#--------------------------------------------------------------#
class ImageToBoardDialog(QDialog):
    
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle("图片棋盘识别")

        self.imageView = ImageView(self)
        
        #self.boardEdit = ChessBoardEditWidget()
        self.redMoveBtn = QRadioButton("红方走", self)
        self.blackMoveBtn = QRadioButton("黑方走", self)
        
        group1 = QButtonGroup(self)
        group1.addButton(self.redMoveBtn)
        group1.addButton(self.blackMoveBtn)

        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.redMoveBtn, 0)
        hbox1.addWidget(self.blackMoveBtn, 0)
        hbox1.addWidget(QLabel(''), 1)

        initBtn = QPushButton("初始棋盘", self)
        clearBtn = QPushButton("清空棋盘", self)
        #openImgBtn = QPushButton("打开图片", self)
        initBtn.clicked.connect(self.onInitBoard)
        clearBtn.clicked.connect(self.onClearBoard)
        #openImgBtn.clicked.connect(self.onOpenImage)
        
        okBtn = QPushButton("确定", self)
        cancelBtn = QPushButton("取消", self)

        vbox = QVBoxLayout()
        vbox.addWidget(self.imageView )
        #vbox.addWidget(self.fenLabel)
        vbox.addLayout(hbox1)

        hbox = QHBoxLayout()
        hbox.addWidget(self.redMoveBtn)
        hbox.addWidget(self.blackMoveBtn)
        hbox.addWidget(initBtn)
        hbox.addWidget(clearBtn)
        #hbox.addWidget(openImgBtn)
        hbox.addWidget(okBtn)
        hbox.addWidget(cancelBtn)

        vbox.addLayout(hbox)
        self.setLayout(vbox)

        #self.boardEdit.fenChangedSignal.connect(self.onBoardFenChanged)
        #self.redMoveBtn.clicked.connect(self.onRedMoveBtnClicked)
        #self.blackMoveBtn.clicked.connect(self.onBlackMoveBtnClicked)

        okBtn.clicked.connect(self.accept)
        cancelBtn.clicked.connect(self.close)
    
    def onInitBoard(self):
        #self.boardEdit.from_fen(cchess.FULL_INIT_FEN)
        pass

    def onClearBoard(self):
        #self.boardEdit.from_fen(cchess.EMPTY_FEN)
        pass

    def onRedMoveBtnClicked(self):
        #self.boardEdit.set_move_color(cchess.RED)
        pass

    def onBlackMoveBtnClicked(self):
        #self.boardEdit.set_move_color(cchess.BLACK)
        pass

    def onBoardFenChanged(self, fen):

        self.fenLabel.setText(fen)

        color = self.boardEdit.get_move_color()
        if color == cchess.RED:
            self.redMoveBtn.setChecked(True)
        elif color == cchess.BLACK:
            self.blackMoveBtn.setChecked(True)

    def edit(self, img):
        self.imageView.setImage(img)
        if self.exec() == QDialog.Accepted:
            return 'ok'
        else:
            return None

#--------------------------------------------------------------#

#UCI_Elo:更细致地限制引擎的棋力水平。
#只有开启UCI_LimitStrength才会生效，设置范围1280~3133，越低越弱。如果不满足Skill Level的21个级别划分，
#想要更加细致地划分引擎棋力水平，使用UCI_Elo即可。和Skill Level的限制棋力方式没有区别，只是更加细分。 
#其中Elo=1280等于Skill Level中的0，最高值3133等于Skill Level中的19，2850=13，2568=10，2268=7，1777=4。

class EngineConfigDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle("引擎设置")
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self.MAX_MEM = 5000
        self.MAX_THREADS = os.cpu_count()
        
        self.enginePath = QLabel()
        self.engineType = QLabel()
        
        #vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        
        self.threadsSpin = QSpinBox(self)
        self.threadsSpin.setSingleStep(1)
        self.threadsSpin.setRange(1, self.MAX_THREADS)
        
        self.memorySpin = QSpinBox(self)
        self.memorySpin.setSingleStep(100)
        self.memorySpin.setRange(500, self.MAX_MEM)
        
        self.multiPVSpin = QSpinBox(self)
        self.multiPVSpin.setSingleStep(1)
        self.multiPVSpin.setRange(1, 10)
        
        self.depthSpin = QSpinBox(self)
        self.depthSpin.setRange(1, 100)
        
        self.moveTimeSpin = QSpinBox(self)
        self.moveTimeSpin.setRange(0, 50)
        
        self.scoreFightSlider = QSlider(Qt.Horizontal)
        self.scoreFightSlider.setTickPosition(QSlider.TicksBelow)
        self.scoreFightSlider.setMinimum(1350)
        self.scoreFightSlider.setSingleStep(100)
        self.scoreFightSlider.setPageStep(300)
        self.scoreFightSlider.setMaximum(2850)
        
        self.depthFightSpin = QSpinBox(self)
        self.depthFightSpin.setRange(0, 50)
        self.moveTimeFightSpin = QSpinBox(self)
        self.moveTimeFightSpin.setRange(0, 50)
        
        engineBox = QGroupBox("引擎路径")
        fbox = QFormLayout()    
        fbox.addRow('引擎路径:', self.enginePath)
        fbox.addRow('引擎类别:', self.engineType)
        fbox.addRow('线程数:', self.threadsSpin)
        fbox.addRow('内存(MB):', self.memorySpin)
        fbox.addRow('分支:', self.multiPVSpin)
        engineBox.setLayout(fbox)
        
        defaultBox = QGroupBox("引擎分析设置")
        
        f1 = QFormLayout()    
        f1.addRow('限定深度:', self.depthSpin)
        f1.addRow('限定步时(秒):', self.moveTimeSpin)
        defaultBox.setLayout(f1)
        hbox.addWidget(defaultBox, 1)
        
        fightBox = QGroupBox("人机挑战设置")
        f2 = QFormLayout()
        f2.addRow('限定级别', self.scoreFightSlider)
        f2.addRow('限定深度', self.depthFightSpin)
        f2.addRow('限定步时（秒）', self.moveTimeFightSpin)
        fightBox.setLayout(f2)
        hbox.addWidget(fightBox, 1)
        
        QBtn = (
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        buttonBox = QDialogButtonBox(QBtn)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        layout.addWidget(engineBox)
        layout.addLayout(hbox)
        layout.addWidget(buttonBox)

        self.params = {}
        
        self.params['EngineThreads'] = self.threadsSpin
        self.params['EngineMemory'] = self.memorySpin
        self.params['EngineMultiPV'] = self.multiPVSpin
        
        self.params["EngineGoDepth"] = self.depthSpin
        self.params["EngineGoMoveTime"] = self.moveTimeSpin

        self.params["EngineGoDepthFight"] = self.depthFightSpin
        self.params['EngineGoMoveTimeFight'] = self.moveTimeFightSpin
        self.params['EngineEloFight'] = self.scoreFightSlider
        
        
    def config(self, params):
        
        self.enginePath.setText(params['EnginePath'])
        self.engineType.setText(params['EngineType'])

        changes = {}
            
        for p_name, widget in self.params.items():
            widget.setValue(params[p_name])
        
        if self.exec() == QDialog.Accepted:
            for p_name, widget in self.params.items():
                if params[p_name] != widget.value():
                    params[p_name] = widget.value()
                    changes[p_name] = widget.value()
                    
            if len(changes) > 0:
                logging.info(f'params changed:{changes}')
        
        return changes
        
#--------------------------------------------------------------#
class QuickBookDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle('快速开局')
        
        layout = QVBoxLayout()
        self.setLayout(layout)

