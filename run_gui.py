import sys
from PyQt5.QtWidgets import QApplication
from gui.gui_qt import RayTracerGUI

def main():
    app = QApplication(sys.argv)
    window = RayTracerGUI()
    window.showFullScreen()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
