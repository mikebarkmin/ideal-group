import sys
import os
from PySide6.QtWidgets import QApplication
from src.ideal_group.ui.main_window import MainWindow
from src.ideal_group.translations import set_language

try:
    from ctypes import windll  # Only exists on Windows.
    myappid = 'eu.barkmin.idealgroup'
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass

def get_system_language() -> str:
    """Detect system language from environment."""
    # Check common locale environment variables
    for var in ('LC_ALL', 'LC_MESSAGES', 'LANG', 'LANGUAGE'):
        value = os.environ.get(var, '')
        if value.startswith('de'):
            return 'de'
    return 'en'


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Ideal Group")
    app.setOrganizationName("IdealGroup")
    scheme = app.styleHints().colorScheme()
    print(f"Color scheme: {scheme}")
    
    # Auto-detect language from environment
    lang = os.environ.get("IDEAL_GROUP_LANG")
    if not lang:
        lang = get_system_language()

    # Allow --lang argument
    if "--lang" in sys.argv:
        idx = sys.argv.index("--lang")
        if idx + 1 < len(sys.argv):
            lang = sys.argv[idx + 1]
    
    set_language(lang)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
