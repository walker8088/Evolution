
# Refer to https://github.com/harupy/snipping-tool

from PIL import ImageGrab
from PIL.ImageQt import ImageQt

from PySide6.QtCore import Qt,QSize, QPoint, QRectF 
from PySide6.QtGui import QCursor, QPixmap, QPainter,QPen,QColor
from PySide6.QtWidgets import QApplication,QWidget

#--------------------------------------------------------------------------------
class SnippingWidget(QWidget):
    is_snipping = False

    def __init__(self,):
        super().__init__()

        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        self.screen = QApplication.primaryScreen()
        self.setGeometry(0, 0, self.screen.size().width(), self.screen.size().height())
        self.begin = QPoint()
        self.end = QPoint()
        self.onSnippingCompleted = None
    
    def fullscreen(self):
        img = ImageGrab.grab(bbox=(0, 0, self.screen.size().width(), self.screen.size().height()))
            
        if self.onSnippingCompleted is not None:
            self.onSnippingCompleted(img)
            
    def start(self):
        SnippingWidget.is_snipping = True
        self.setWindowOpacity(0.3)
        QApplication.setOverrideCursor(QCursor(Qt.CrossCursor))
        self.show()

    def paintEvent(self, event):
        if SnippingWidget.is_snipping:
            brush_color = (128, 128, 255, 100)
            lw = 3
            opacity = 0.3
        else:
            self.begin = QPoint()
            self.end = QPoint()
            brush_color = (0, 0, 0, 0)
            lw = 0
            opacity = 0

        self.setWindowOpacity(opacity)
        qp = QPainter(self)
        qp.setPen(QPen(QColor('black'), lw))
        qp.setBrush(QColor(*brush_color))
        rect = QRectF(self.begin, self.end)
        qp.drawRect(rect)

    def mousePressEvent(self, event):
        self.begin = event.position()
        self.end = self.begin
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.position()
        self.update()

    def mouseReleaseEvent(self, event):
        SnippingWidget.is_snipping = False
        QApplication.restoreOverrideCursor()
        x1 = min(self.begin.x(), self.end.x())
        y1 = min(self.begin.y(), self.end.y())
        x2 = max(self.begin.x(), self.end.x())
        y2 = max(self.begin.y(), self.end.y())

        self.repaint()
        QApplication.processEvents()
        img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        
        qtImg = ImageQt(img)   
        if self.onSnippingCompleted is not None:
            self.onSnippingCompleted(qtImg)

        self.close()

#--------------------------------------------------------------------------------
