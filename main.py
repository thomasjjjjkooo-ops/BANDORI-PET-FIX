import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LIVE2D_PACKAGE = os.path.join(BASE_DIR, "third_party", "live2d-py", "package")
if LIVE2D_PACKAGE not in sys.path:
    sys.path.insert(0, LIVE2D_PACKAGE)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from qfluentwidgets import setTheme, Theme

import live2d.v2 as live2d
from platform_patch import PatchedPlatformManager


def main():
    live2d.init()

    live2d.Live2DFramework.setPlatformManager(
        PatchedPlatformManager(live2d.Live2DFramework.getPlatformManager())
    )

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL)

    app = QApplication(sys.argv)
    app.setApplicationName("BandoriPet")
    app.setOrganizationName("BandoriPet")

    setTheme(Theme.LIGHT)

    from pet_window import PetWindow
    window = PetWindow(live2d)
    window.show()

    ret = app.exec()

    live2d.dispose()
    return ret


if __name__ == "__main__":
    sys.exit(main())
