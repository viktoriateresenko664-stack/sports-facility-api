COLOR_BLUE = "#103A5E"
COLOR_WHITE = "white"
COLOR_BLACK = "#000"
COLOR_GRAY = "#f5f5f5"
COLOR_LIGHT_GRAY = "#e0e0e0"
COLOR_RED = "#cc0000"
COLOR_DARK = "#333"
STATUS_RED = "#FF0000"
STATUS_ORANGE = "#FFA500"
STATUS_GREEN = "#008000"
STATUS_BG_GREEN = "#e6ffe6"
STATUS_BG_ORANGE = "#fff9e6"
STATUS_BG_RED = "#ffe6e6"

FONT_TITLE = "font-size: 22px; font-weight: bold; color: #103A5E;"
FONT_HEADER = "font-size: 24px; font-weight: bold; color: #103A5E;"
FONT_ROLE = "font-size: 24px; font-weight: bold; color: #000;"
FONT_LABEL = "font-size: 14px; font-weight: bold; color: #333;"
FONT_OBJECT_TITLE = "font-size: 28px; font-weight: bold; color: #103A5E;"
FONT_OBJECT_INFO = "font-size: 18px;"
FONT_OBJECT_STATUS = "font-size: 18px; font-weight: bold; padding: 5px 10px; border-radius: 5px;"
FONT_ERROR = "color: #cc0000; font-size: 13px;"
FONT_TABLE = "font-size: 12px;"
FONT_TABLE_HEADER = "font-size: 14px;"
FONT_MENU_ITEM = "font-size: 14px; font-weight: bold;"
FONT_SMALL = "font-size: 11px;"
FONT_OBJECT_LIST = "font-size: 16px;"

STYLE_LOGIN_INPUT = """
    QLineEdit {
        padding: 8px;
        border: 1px solid #ccc;
        border-radius: 5px;
        font-size: 14px;
        background-color: white;
    }
"""

STYLE_LOGIN_BTN = """
    QPushButton {
        background-color: #103A5E;
        color: white;
        padding: 12px;
        border-radius: 8px;
        font-size: 16px;
        font-weight: bold;
    }
"""

STYLE_MENU = """
    QListWidget {
        background-color: #103A5E;
        border: none;
        padding: 10px;
    }
    QListWidget::item {
        color: white;
    }
    QListWidget::item:selected {
        background-color: rgba(255,255,255,0.3);
        border-radius: 8px;
    }
"""
STYLE_LOGOUT_BTN = """
    QPushButton {
        background-color: transparent;
        border: none;
    }
    QPushButton:hover {
        background-color: rgba(255,255,255,0.2);
        border-radius: 5px;
    }
"""

STYLE_TABLE = """
    QTableWidget {
        background-color: white;
        gridline-color: #ccc;
        font-size: 12px;
    }
    QHeaderView::section {
        background-color: #103A5E;
        color: white;
        padding: 10px;
        font-weight: bold;
    }
"""

STYLE_TABLE_SMALL = """
    QTableWidget {
        background-color: white;
        gridline-color: #ccc;
        font-size: 14px;
    }
    QHeaderView::section {
        background-color: #103A5E;
        color: white;
        padding: 10px;
        font-size: 14px;
    }
"""

STYLE_BTN_BLUE = """
    QPushButton {
        background-color: #103A5E;
        color: white;
        padding: 10px;
        border-radius: 5px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #1a4a6e;
    }
"""

STYLE_BTN_CANCEL = """
    QPushButton {
        background-color: #e0e0e0;
        color: #333;
        border-radius: 5px;
        font-size: 13px;
    }
    QPushButton:hover {
        background-color: #d0d0d0;
    }
"""

STYLE_COMBO = """
    QComboBox {
        padding: 8px;
        border: 1px solid #ccc;
        border-radius: 5px;
        font-size: 13px;
    }
"""

STYLE_CREATE_BTN_DISABLED = """
    QPushButton {
        background-color: #ccc;
        color: #666;
        padding: 12px;
        border-radius: 8px;
        font-weight: bold;
        font-size: 16px;
    }
"""

STYLE_CREATE_BTN_ENABLED = """
    QPushButton {
        background-color: #103A5E;
        color: white;
        padding: 12px;
        border-radius: 8px;
        font-weight: bold;
        font-size: 16px;
    }
    QPushButton:hover {
        background-color: #1a4a6e;
    }
"""

STYLE_HEADER_BLUE = """
    font-size: 18px;
    font-weight: bold;
    color: white;
    background-color: #103A5E;
    padding: 15px;
"""

STYLE_TEXT_EDIT = """
    QTextEdit {
        border: 1px solid #ccc;
        border-radius: 5px;
        padding: 8px;
        font-size: 13px;
    }
"""

COLORS = {
    "green": "#e6ffe6",
    "yellow": "#fff9e6",
    "red": "#ffe6e6",
}

def localize_status(status: str) -> str:
    mapping = {
        "CREATED": "Создана",
        "ACTIVE": "В работе",
        "COMPLETED": "Выполнена",
        "CANCELLED": "Отменена",
        "SUCCESS": "Успешно",
        "FAILED": "Ошибка",
        "PENDING": "В обработке",
    }
    return mapping.get((status or "").upper(), status or "")

def localize_action(action: str) -> str:
    mapping = {
        "LOGIN": "Вход в систему",
        "EMPLOYEE_LOGIN": "Вход сотрудника",
        "USER_REGISTER": "Регистрация пользователя",
        "CREATE_REQUEST": "Создание заявки",
        "TASK_STATUS_CHANGE": "Изменение статуса задачи",
        "TASK_START": "Начало задачи",
        "TASK_COMPLETE": "Завершение задачи",
        "ASSIGN_ENGINEER": "Назначение инженера",
    }
    return mapping.get((action or "").upper(), action or "")

def localize_role(role: str) -> str:
    mapping = {
        "ADMIN": "Администратор",
        "OPERATOR": "Оператор",
        "ENGINEER": "Инженер",
        "CHIEF_ENGINEER": "Главный инженер",
        "USER": "Пользователь",
    }
    return mapping.get((role or "").upper(), role or "")

def localize_object_name(obj: str) -> str:
    mapping = {
        "Olympic Pool": "Олимпийский бассейн",
        "Ice Arena": "Ледовая арена",
        "Main Stadium": "Главный стадион",
        "user_requests": "Заявка",
        "engineer_tasks": "Задача",
        "employees": "Сотрудник",
        "users": "Пользователь",
    }
    return mapping.get(obj, obj)