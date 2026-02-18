
# Menu Styles
MENU_STYLE = """
    listings {
        background-color: rgba(0, 0, 0, 150);
        color: #00FF00;
        font-family: monospace;
        font-size: 24px;
    }
    QLabel {
        color: #00FF00;
        font-size: 24px;
        padding: 5px;
    }
    QLabel[selected="true"] {
        background-color: rgba(0, 255, 0, 100);
        color: #000000;
        border: 1px solid #00FF00;
    }
    QLabel[active="false"] {
        color: #555555;
    }
"""

LAUNCHER_STYLE = """
    QFrame {
        background-color: rgba(0, 0, 0, 200);
        border: 2px solid #00FF00;
        border-radius: 10px;
    }
    QLabel {
        color: #FFFFFF;
        font-size: 18px;
    }
"""
