
from PySide6.QtCore import Qt, Signal, QByteArray, QSize
from PySide6.QtGui import *
from PySide6.QtWidgets import *

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
        #self.pixmap = QPixmap.fromImage(cv2qt_image(img)) 
        self.pixmap = QPixmap.fromImage(img) 
        
        #QCoreApplication::setAttribute(Qt::AA_UseHighDpiPixmaps, true); 

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

