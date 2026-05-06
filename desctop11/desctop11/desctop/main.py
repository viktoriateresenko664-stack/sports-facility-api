import sys
import os
import logging
import requests
import html
from datetime import datetime, timezone, timedelta
from PySide6.QtWidgets import (
    QApplication, QListWidget, QListWidgetItem, QStackedWidget,
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialog,
    QLineEdit, QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QTabWidget, QMessageBox, QTextEdit,
    QFileDialog
)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QIcon, QFont, QColor
from styles import *
import tempfile
import webbrowser

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("desktop_polling")

BASE_URL = "https://sports-facility-api.onrender.com"
TOKEN = None
USER_ROLE = None
MSK = timezone(timedelta(hours=3))


def clean_text(text):
    if not text:
        return ""
    return html.escape(str(text))


def format_datetime(date_str):
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.astimezone(MSK).strftime("%d.%m.%Y %H:%M")
    except:
        return clean_text(date_str or "")


def make_table(headers, style=STYLE_TABLE):
    table = QTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    table.verticalHeader().setVisible(False)
    table.setStyleSheet(style)
    return table


def make_combo(items, width=180, height=35, style=STYLE_COMBO):
    combo = QComboBox()
    combo.addItems(items)
    combo.setFixedWidth(width)
    combo.setMinimumHeight(height)
    combo.setStyleSheet(style)
    return combo


def make_label(text, style=FONT_LABEL, align=None):
    label = QLabel(clean_text(str(text)))
    label.setStyleSheet(style)
    if align:
        label.setAlignment(align)
    return label


def make_button(text, style=STYLE_BTN_BLUE, width=None, height=None):
    btn = QPushButton(clean_text(str(text)))
    btn.setStyleSheet(style)
    if width:
        btn.setFixedWidth(width)
    if height:
        btn.setFixedHeight(height)
    return btn


def load_icon(name):
    png_path = os.path.join(os.path.dirname(__file__), "png")
    icon_path = os.path.join(png_path, name)
    if os.path.exists(icon_path):
        return QIcon(icon_path)
    return QIcon()


def add_menu_items(menu_list, items):
    for icon_name, text in items:
        item = QListWidgetItem(load_icon(icon_name), clean_text(text))
        item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        item.setSizeHint(QSize(150, 85))
        menu_list.addItem(item)


def api_request(method, endpoint, data=None):
    if not TOKEN:
        return None
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=15)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=15)
        else:
            logger.error("Unsupported HTTP method: %s", method)
            return None

        if response.status_code in (200, 201):
            return response.json()
        else:
            logger.error("API %s %s failed: %s", method, endpoint, response.status_code)
            return None
    except:
        logger.error("API %s %s request error", method, endpoint)
        return None


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Мониторинг объектов")
        self.setFixedSize(500, 400)
        self.setStyleSheet(f"background-color: {COLOR_GRAY};")

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        layout.addWidget(make_label("МОНИТОРИНГ ОБЪЕКТОВ", FONT_TITLE, Qt.AlignCenter))
        layout.addSpacing(20)

        form = QFormLayout()
        form.setSpacing(15)

        self.key_input = QLineEdit()
        self.key_input.setMinimumHeight(40)
        self.key_input.setStyleSheet(STYLE_LOGIN_INPUT)
        form.addRow(make_label("Ключ:"), self.key_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(40)
        self.password_input.setStyleSheet(STYLE_LOGIN_INPUT)
        form.addRow(make_label("Пароль:"), self.password_input)
        layout.addLayout(form)

        self.login_btn = make_button("ВОЙТИ", STYLE_LOGIN_BTN, height=50)
        self.login_btn.clicked.connect(self.do_login)
        layout.addWidget(self.login_btn)

        self.error_label = make_label("", FONT_ERROR, Qt.AlignCenter)
        layout.addWidget(self.error_label)

        self.setLayout(layout)

    def do_login(self):
        global TOKEN, USER_ROLE
        key = self.key_input.text().strip()
        password = self.password_input.text()

        if not key or not password:
            self.error_label.setText("Заполните все поля")
            return

        try:
            response = requests.post(
                f"{BASE_URL}/auth/employee-login",
                json={"employee_key": key, "password": password},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                TOKEN = data.get("access_token")
                if TOKEN:
                    if key == "OP001":
                        USER_ROLE = "operator"
                    elif key == "CH001":
                        USER_ROLE = "engineer"
                    else:
                        self.error_label.setText("Неверный ключ или пароль")
                        return
                    self.accept()
                else:
                    self.error_label.setText("Ошибка: токен не получен")
            elif response.status_code == 401:
                self.error_label.setText("Неверный ключ или пароль")
            else:
                self.error_label.setText(f"Ошибка сервера: {response.status_code}")
        except requests.exceptions.ConnectionError:
            self.error_label.setText("Нет связи с сервером")
        except Exception as e:
            self.error_label.setText(f"Ошибка: {str(e)[:50]}")


class OperatorWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.all_requests = []
        self.all_facilities = []
        self.all_employees = []
        self.all_logs = []
        self.employee_options = []
        self.setWindowTitle("Оператор")
        self.showMaximized()
        self.setup_ui()
        self.start_polling()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.create_menu())
        layout.addWidget(self.create_right_panel())

    def start_polling(self):
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.load_current_page)
        self.poll_timer.start(10000)

    def load_current_page(self):
        current = self.pages.currentIndex()
        if current == 0:
            self.load_dashboard_data()
        elif current == 1:
            self.load_requests_data()
        elif current == 2:
            self.load_employees_data()
        elif current == 3:
            self.load_logs_data()

    def create_menu(self):
        menu = QWidget()
        menu.setFixedWidth(180)
        menu.setStyleSheet(f"background-color: {COLOR_BLUE};")
        menu_layout = QVBoxLayout(menu)
        menu_layout.setContentsMargins(0, 20, 0, 10)
        menu_layout.setSpacing(0)

        self.menu_list = QListWidget()
        self.menu_list.setViewMode(QListWidget.IconMode)
        self.menu_list.setIconSize(QSize(80, 80))
        self.menu_list.setGridSize(QSize(160, 100))
        self.menu_list.setMovement(QListWidget.Static)
        self.menu_list.setFlow(QListWidget.TopToBottom)
        self.menu_list.setWrapping(False)
        self.menu_list.setSpacing(15)
        self.menu_list.setStyleSheet(STYLE_MENU)
        self.menu_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.menu_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.menu_list.setFont(font)

        add_menu_items(self.menu_list, [
            ("domik.png", "Главная"),
            ("golova.png", "Заявки"),
            ("kaska.png", "Сотрудники"),
            ("book.png", "Журнал"),
        ])

        self.menu_list.itemClicked.connect(self.on_menu)
        menu_layout.addWidget(self.menu_list)
        return menu

    def create_right_panel(self):
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(20, 15, 20, 15)
        right_layout.setSpacing(10)

        header = QHBoxLayout()
        self.page_title = make_label("Главная", FONT_HEADER)
        header.addWidget(self.page_title)
        header.addStretch()
        header.addSpacing(20)
        header.addWidget(make_label("Оператор", FONT_ROLE))
        header.addSpacing(15)

        logout_btn = QPushButton()
        logout_btn.setIcon(load_icon("exit.png"))
        logout_btn.setIconSize(QSize(32, 32))
        logout_btn.setFixedSize(40, 40)
        logout_btn.setToolTip("Выйти из системы")
        logout_btn.setStyleSheet(STYLE_LOGOUT_BTN)
        logout_btn.clicked.connect(self.on_menu_exit)
        header.addWidget(logout_btn)

        right_layout.addLayout(header)

        self.pages = QStackedWidget()
        self.pages.addWidget(self.create_dashboard_page())
        self.pages.addWidget(self.create_requests_page())
        self.pages.addWidget(self.create_employees_page())
        self.pages.addWidget(self.create_logs_page())
        right_layout.addWidget(self.pages)
        return right

    def create_dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        filter_row = QHBoxLayout()
        self.dash_filter = make_combo(["Все", "ACTIVE", "MAINTENANCE", "INACTIVE"])
        self.dash_filter.currentTextChanged.connect(self.filter_dashboard)
        filter_row.addWidget(self.dash_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self.facility_table = make_table(["№", "Название", "Тип", "Адрес", "Статус"])
        layout.addWidget(self.facility_table)

        refresh_btn = make_button("Обновить")
        refresh_btn.clicked.connect(self.load_dashboard_data)
        layout.addWidget(refresh_btn)

        return page

    def create_requests_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        filter_row = QHBoxLayout()
        self.req_filter = make_combo(["Все", "CREATED", "ASSIGNED", "IN_WORK", "COMPLETED", "CANCELLED"])
        self.req_filter.currentTextChanged.connect(self.filter_requests)
        filter_row.addWidget(self.req_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self.requests_table = make_table(["№", "Объект", "Описание", "Дата", "Статус", "Инженер"])
        layout.addWidget(self.requests_table)

        btn_layout = QHBoxLayout()
        refresh_btn = make_button("Обновить")
        refresh_btn.clicked.connect(self.load_requests_data)
        assign_btn = make_button("Назначить")
        assign_btn.clicked.connect(self.assign_engineer)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(assign_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return page

    def create_employees_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        self.employees_table = make_table(["№", "ФИО", "Телефон", "Email", "Должность"])
        layout.addWidget(self.employees_table)

        refresh_btn = make_button("Обновить")
        refresh_btn.clicked.connect(self.load_employees_data)
        layout.addWidget(refresh_btn)

        return page

    def create_logs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        filter_row = QHBoxLayout()
        self.log_filter = make_combo(["Все", "SUCCESS", "FAILED"])
        self.log_filter.currentTextChanged.connect(self.filter_logs)
        filter_row.addWidget(self.log_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self.logs_table = make_table(["№", "Пользователь", "Роль", "Действие", "Объект", "Дата", "Статус"])
        layout.addWidget(self.logs_table)

        refresh_btn = make_button("Обновить")
        refresh_btn.clicked.connect(self.load_logs_data)
        layout.addWidget(refresh_btn)

        return page

    def load_dashboard_data(self):
        self.all_facilities = api_request("GET", "/bff/desktop/dashboard") or []
        self.filter_dashboard()

    def filter_dashboard(self):
        text = self.dash_filter.currentText()
        facilities = self.all_facilities.get("facilities", []) if isinstance(self.all_facilities, dict) else self.all_facilities
        if text != "Все":
            facilities = [f for f in facilities if (f.get("status") or "").upper() == text.upper()]
        self.facility_table.setRowCount(len(facilities))
        for row, fac in enumerate(facilities):
            self.facility_table.setItem(row, 0, QTableWidgetItem(str(fac.get("id", ""))))
            self.facility_table.setItem(row, 1, QTableWidgetItem(fac.get("name", "")))
            self.facility_table.setItem(row, 2, QTableWidgetItem(fac.get("type", "")))
            self.facility_table.setItem(row, 3, QTableWidgetItem(fac.get("address", "")))
            self.facility_table.setItem(row, 4, QTableWidgetItem(fac.get("status", "")))

    def load_requests_data(self):
        if not self.employee_options:
            self.load_employees_data()
        self.all_requests = api_request("GET", "/bff/desktop/requests/all") or []
        self.filter_requests()

    def filter_requests(self):
        text = self.req_filter.currentText()
        rows = self.all_requests if isinstance(self.all_requests, list) else []
        if text != "Все":
            rows = [r for r in rows if (r.get("status") or "").upper() == text.upper()]
        self.requests_table.setRowCount(len(rows))
        for row, req in enumerate(rows):
            self.requests_table.setItem(row, 0, QTableWidgetItem(str(req.get("id", ""))))
            self.requests_table.setItem(row, 1, QTableWidgetItem(req.get("facility", "")))

            desc_item = QTableWidgetItem(req.get("description", ""))
            desc_item.setToolTip(req.get("description", ""))
            self.requests_table.setItem(row, 2, desc_item)

            self.requests_table.setItem(row, 3, QTableWidgetItem(format_datetime(req.get("date", ""))))
            self.requests_table.setItem(row, 4, QTableWidgetItem(req.get("status", "")))
            self.requests_table.setItem(row, 5, QTableWidgetItem(req.get("engineer", "") or "Не назначен"))

    def load_employees_data(self):
        self.all_employees = api_request("GET", "/bff/desktop/employees") or []
        rows = self.all_employees if isinstance(self.all_employees, list) else []

        allowed = ["operator", "engineer"]

        filtered = []
        for emp in rows:
            pos = (emp.get("position") or "").lower()
            if pos in allowed:
                filtered.append(emp)

        self.employee_options = [
            {"id": emp.get("id"), "name": emp.get("name", "")}
            for emp in filtered
            if emp.get("id") and (emp.get("position") or "").lower() == "engineer"
        ]

        self.employees_table.setRowCount(len(filtered))
        for row, emp in enumerate(filtered):
            self.employees_table.setItem(row, 0, QTableWidgetItem(str(emp.get("id", ""))))
            self.employees_table.setItem(row, 1, QTableWidgetItem(emp.get("name", "")))
            self.employees_table.setItem(row, 2, QTableWidgetItem(emp.get("phone", "")))
            self.employees_table.setItem(row, 3, QTableWidgetItem(emp.get("email", "")))
            self.employees_table.setItem(row, 4, QTableWidgetItem(emp.get("position", "")))

    def load_logs_data(self):
        self.all_logs = api_request("GET", "/bff/desktop/logs") or []
        self.filter_logs()

    def filter_logs(self):
        text = self.log_filter.currentText()
        rows = self.all_logs if isinstance(self.all_logs, list) else []
        if text != "Все":
            rows = [r for r in rows if (r.get("status") or "").upper() == text.upper()]
        self.logs_table.setRowCount(len(rows))
        for row, log in enumerate(rows):
            self.logs_table.setItem(row, 0, QTableWidgetItem(str(log.get("id", ""))))
            self.logs_table.setItem(row, 1, QTableWidgetItem(log.get("user", "")))
            self.logs_table.setItem(row, 2, QTableWidgetItem(log.get("role", "")))
            self.logs_table.setItem(row, 3, QTableWidgetItem(log.get("action", "")))
            self.logs_table.setItem(row, 4, QTableWidgetItem(log.get("object", "")))
            self.logs_table.setItem(row, 5, QTableWidgetItem(format_datetime(log.get("date", ""))))
            self.logs_table.setItem(row, 6, QTableWidgetItem(log.get("status", "")))

    def assign_engineer(self):
        row = self.requests_table.currentRow()
        if row < 0:
            return

        request_id = self.requests_table.item(row, 0).text()

        dialog = QDialog(self)
        dialog.setWindowTitle("Назначить инженера")
        dialog.setFixedSize(300, 150)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Выберите инженера:"))

        combo = QComboBox()
        for emp in self.employee_options:
            combo.addItem(emp["name"], emp["id"])
        layout.addWidget(combo)

        btn = make_button("Назначить")
        btn.clicked.connect(lambda: dialog.accept())
        layout.addWidget(btn)

        if dialog.exec() == QDialog.Accepted:
            assigned_engineer_id = combo.currentData()
            if not assigned_engineer_id:
                return

            api_request(
                "POST",
                f"/bff/desktop/requests/{request_id}/assign",
                {"assigned_engineer_id": int(assigned_engineer_id), "operator_comment": ""},
            )
            self.load_requests_data()

    def on_menu(self, item):
        row = self.menu_list.row(item)
        if row < 4:
            names = ["Главная", "Заявки пользователей", "Сотрудники", "Журнал действий"]
            self.page_title.setText(names[row])
            self.pages.setCurrentIndex(row)
            self.load_current_page()

    def on_menu_exit(self):
        self.poll_timer.stop()
        self.close()
        self.open_login()

    def open_login(self):
        global TOKEN, USER_ROLE
        TOKEN = USER_ROLE = None
        self.login = LoginDialog()
        if self.login.exec() == QDialog.Accepted:
            if USER_ROLE == "operator":
                self.new_window = OperatorWindow()
            else:
                self.new_window = EngineerWindow()
            self.new_window.show()
            self.new_window.showMaximized()


class EngineerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.all_requests = []
        self.all_facilities = []
        self.all_logs = []
        self.employee_options = []
        self.all_reports = []
        self.selected_object = None
        self.facility_cache = {}
        self.setWindowTitle("Инженер")
        self.setup_ui()
        self.showMaximized()
        self.start_polling()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.create_menu())
        layout.addWidget(self.create_right_panel())

    def start_polling(self):
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.load_current_page)
        self.poll_timer.start(10000)

    def load_current_page(self):
        current = self.pages.currentIndex()
        if current == 0 or current == 1:
            self.load_dashboard_data()
            if current == 1:
                self.update_object_colors()
        elif current == 2:
            self.load_my_requests()
        elif current == 3:
            self.load_reports()
        elif current == 4:
            self.load_logs_data()

    def create_menu(self):
        menu = QWidget()
        menu.setFixedWidth(180)
        menu.setStyleSheet(f"background-color: {COLOR_BLUE};")
        menu_layout = QVBoxLayout(menu)
        menu_layout.setContentsMargins(0, 20, 0, 10)
        menu_layout.setSpacing(0)

        self.menu_list = QListWidget()
        self.menu_list.setViewMode(QListWidget.IconMode)
        self.menu_list.setIconSize(QSize(64, 64))
        self.menu_list.setGridSize(QSize(160, 94))
        self.menu_list.setMovement(QListWidget.Static)
        self.menu_list.setFlow(QListWidget.TopToBottom)
        self.menu_list.setWrapping(False)
        self.menu_list.setSpacing(15)
        self.menu_list.setStyleSheet(STYLE_MENU)
        self.menu_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.menu_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.menu_list.setFont(font)

        add_menu_items(self.menu_list, [
            ("domik.png", "Главная"),
            ("obj.png", "Объекты"),
            ("kaska.png", "Мои заявки"),
            ("report.png", "Отчёты"),
            ("book.png", "Журнал"),
        ])

        self.menu_list.itemClicked.connect(self.on_menu)
        menu_layout.addWidget(self.menu_list)
        return menu

    def create_right_panel(self):
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(20, 15, 20, 15)
        right_layout.setSpacing(10)

        header = QHBoxLayout()
        self.page_title = make_label("Главная", FONT_HEADER)
        header.addWidget(self.page_title)
        header.addStretch()
        header.addSpacing(20)
        header.addWidget(make_label("Инженер", FONT_ROLE))
        header.addSpacing(15)

        logout_btn = QPushButton()
        logout_btn.setIcon(load_icon("exit.png"))
        logout_btn.setIconSize(QSize(32, 32))
        logout_btn.setFixedSize(40, 40)
        logout_btn.setToolTip("Выйти из системы")
        logout_btn.setStyleSheet(STYLE_LOGOUT_BTN)
        logout_btn.clicked.connect(self.on_menu_exit)
        header.addWidget(logout_btn)

        right_layout.addLayout(header)

        self.pages = QStackedWidget()
        self.pages.addWidget(self.create_dashboard_page())
        self.pages.addWidget(self.create_objects_page())
        self.pages.addWidget(self.create_my_requests_page())
        self.pages.addWidget(self.create_reports_page())
        self.pages.addWidget(self.create_logs_page())
        right_layout.addWidget(self.pages)
        return right

    def create_dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.engineer_facility_table = make_table(["№", "Название", "Тип", "Адрес", "Статус"])
        layout.addWidget(self.engineer_facility_table)

        refresh_btn = make_button("Обновить")
        refresh_btn.clicked.connect(self.load_dashboard_data)
        layout.addWidget(refresh_btn)
        return page

    def create_objects_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.obj_list = QListWidget()
        self.obj_list.setFixedWidth(350)
        self.obj_list.setStyleSheet(f"background-color: #e8e8e8; padding: 10px; {FONT_OBJECT_LIST}")
        self.obj_list.itemClicked.connect(self.on_object_click)
        layout.addWidget(self.obj_list)

        self.detail = QWidget()
        detail_layout = QVBoxLayout(self.detail)
        detail_layout.setContentsMargins(20, 0, 0, 0)
        detail_layout.setSpacing(10)

        self.obj_title = make_label("Выберите объект", FONT_OBJECT_TITLE)
        detail_layout.addWidget(self.obj_title)

        self.obj_status = make_label("", FONT_OBJECT_STATUS)
        detail_layout.addWidget(self.obj_status)

        self.obj_info = make_label("", FONT_OBJECT_INFO)
        detail_layout.addWidget(self.obj_info)

        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.create_table_tab(["Название", "Тип", "Статус"]), "Оборудование")
        self.tab_widget.addTab(self.create_table_tab(["Название", "Тип", "Значение", "Состояние"]), "Датчики")
        detail_layout.addWidget(self.tab_widget)

        self.create_btn = make_button("Создать заявку", STYLE_CREATE_BTN_DISABLED)
        self.create_btn.clicked.connect(self.open_create_dialog)
        self.create_btn.setEnabled(False)
        detail_layout.addWidget(self.create_btn)

        layout.addWidget(self.detail)
        return page

    def create_table_tab(self, headers):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(make_table(headers, STYLE_TABLE_SMALL))
        return w

    def create_my_requests_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        filter_row = QHBoxLayout()
        self.eng_req_filter = make_combo(["Все", "CREATED", "ASSIGNED", "ACTIVE", "COMPLETED", "CANCELLED"])
        self.eng_req_filter.currentTextChanged.connect(self.filter_my_requests)
        filter_row.addWidget(self.eng_req_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self.my_requests_table = make_table(["№", "Объект", "Описание", "Комментарий", "Дата", "Статус", "Исполнитель"])
        layout.addWidget(self.my_requests_table)

        refresh_btn = make_button("Обновить")
        refresh_btn.clicked.connect(self.load_my_requests)
        layout.addWidget(refresh_btn)
        return page

    def create_reports_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.reports_table = make_table(["№", "Объект", "Инженер", "Дата", "Файл", "Размер"])
        layout.addWidget(self.reports_table)

        btn_row = QHBoxLayout()
        refresh_btn = make_button("Обновить")
        refresh_btn.clicked.connect(self.load_reports)
        download_btn = make_button("Скачать")
        download_btn.clicked.connect(self.download_report)
        preview_btn = make_button("Просмотр")
        preview_btn.clicked.connect(self.preview_report)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(download_btn)
        btn_row.addWidget(preview_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return page

    def create_logs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        filter_row = QHBoxLayout()
        self.eng_log_filter = make_combo(["Все", "SUCCESS", "FAILED"])
        self.eng_log_filter.currentTextChanged.connect(self.filter_engineer_logs)
        filter_row.addWidget(self.eng_log_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self.engineer_logs_table = make_table(["№", "Пользователь", "Роль", "Действие", "Объект", "Дата", "Статус"])
        layout.addWidget(self.engineer_logs_table)

        refresh_btn = make_button("Обновить")
        refresh_btn.clicked.connect(self.load_logs_data)
        layout.addWidget(refresh_btn)
        return page

    def load_dashboard_data(self):
        self.all_facilities = api_request("GET", "/bff/desktop/dashboard") or []
        facilities = self.all_facilities.get("facilities", []) if isinstance(self.all_facilities, dict) else self.all_facilities

        if isinstance(facilities, list):
            self.engineer_facility_table.setRowCount(len(facilities))
            self.obj_list.clear()
            self.facility_cache = {}
            for row, fac in enumerate(facilities):
                self.engineer_facility_table.setItem(row, 0, QTableWidgetItem(str(fac.get("id", ""))))
                self.engineer_facility_table.setItem(row, 1, QTableWidgetItem(fac.get("name", "")))
                self.engineer_facility_table.setItem(row, 2, QTableWidgetItem(fac.get("type", "")))
                self.engineer_facility_table.setItem(row, 3, QTableWidgetItem(fac.get("address", "")))
                self.engineer_facility_table.setItem(row, 4, QTableWidgetItem(fac.get("status", "")))

                self.facility_cache[fac.get("name", "")] = fac

                item = QListWidgetItem(fac.get("name", ""))
                item.setForeground(QColor(COLOR_BLACK))
                self.obj_list.addItem(item)

            self.update_object_colors()

    def update_object_colors(self):
        data = api_request("GET", "/dev/fake-sensor-data?randomize=true")
        if not data:
            return

        facilities = data.get("facilities", [])

        for i in range(self.obj_list.count()):
            item = self.obj_list.item(i)
            name = item.text()

            has_critical = False
            has_warning = False

            for f in facilities:
                if f.get("name") == name:
                    sensors = f.get("sensors", [])
                    for sens in sensors:
                        state = (sens.get("state") or sens.get("status") or "").upper()
                        if state in ["CRITICAL", "ERROR"]:
                            has_critical = True
                        elif state in ["WARNING", "MAINTENANCE"]:
                            has_warning = True

                    equipment = f.get("equipment", [])
                    for eq in equipment:
                        eq_status = (eq.get("status") or "").upper()
                        if eq_status in ["CRITICAL", "ERROR"]:
                            has_critical = True
                        elif eq_status in ["WARNING", "MAINTENANCE"]:
                            has_warning = True
                    break

            if has_critical:
                item.setBackground(QColor(STATUS_BG_RED))
            elif has_warning:
                item.setBackground(QColor(STATUS_BG_ORANGE))
            else:
                item.setBackground(QColor(STATUS_BG_GREEN))

    def load_employees_data(self):
        data = api_request("GET", "/bff/desktop/employees") or []
        rows = data if isinstance(data, list) else []

        allowed = ["operator", "engineer", "chief engineer"]
        engineers = ["engineer"]

        filtered = []
        for emp in rows:
            pos = (emp.get("position") or "").lower()
            if pos in allowed:
                filtered.append(emp)

        self.employee_options = []
        for emp in filtered:
            eid = emp.get("id")
            pos = (emp.get("position") or "").lower()
            if eid and pos in engineers:
                self.employee_options.append({"id": eid, "name": emp.get("name", "")})

    def load_my_requests(self):
        if not self.facility_cache:
            self.load_dashboard_data()
        data = api_request("GET", "/engineer-tasks") or []
        self.all_requests = data if isinstance(data, list) else []
        self.filter_my_requests()

    def filter_my_requests(self):
        if not self.employee_options:
            self.load_employees_data()

        text = self.eng_req_filter.currentText()
        rows = self.all_requests
        rows = [r for r in rows if r.get("request_id") is None]

        if text != "Все":
            rows = [r for r in rows if (r.get("status") or "").upper() == text.upper()]

        self.my_requests_table.setRowCount(len(rows))
        for row, req in enumerate(rows):
            self.my_requests_table.setItem(row, 0, QTableWidgetItem(str(req.get("task_id", ""))))

            facility_id = req.get("facility_id")
            facility_name = str(facility_id)
            for name, fac in self.facility_cache.items():
                if fac.get("id") == facility_id:
                    facility_name = name
                    break

            self.my_requests_table.setItem(row, 1, QTableWidgetItem(facility_name))
            
            desc_item = QTableWidgetItem(req.get("description", ""))
            desc_item.setToolTip(req.get("description", ""))
            self.my_requests_table.setItem(row, 2, desc_item)
            
            comm_item = QTableWidgetItem(req.get("operator_comment", ""))
            comm_item.setToolTip(req.get("operator_comment", ""))
            self.my_requests_table.setItem(row, 3, comm_item)
            
            self.my_requests_table.setItem(row, 4, QTableWidgetItem(format_datetime(req.get("created_at", ""))))
            self.my_requests_table.setItem(row, 5, QTableWidgetItem(req.get("status", "")))

            eng_name = "Не назначен"
            for emp in self.employee_options:
                if emp["id"] == req.get("assigned_engineer_id"):
                    eng_name = emp["name"]
                    break
            self.my_requests_table.setItem(row, 6, QTableWidgetItem(eng_name))

    def load_reports(self):
        if not self.facility_cache:
            self.load_dashboard_data()
        if not self.employee_options:
            self.load_employees_data()

        data = api_request("GET", "/bff/desktop/reports") or {}
        rows = data.get("items", []) if isinstance(data, dict) else []

        self.reports_table.setRowCount(len(rows))
        for row, rep in enumerate(rows):
            self.reports_table.setItem(row, 0, QTableWidgetItem(str(rep.get("report_id", ""))))
            self.reports_table.setItem(row, 1, QTableWidgetItem(rep.get("facility_name", "")))
            self.reports_table.setItem(row, 2, QTableWidgetItem(rep.get("engineer_name", "")))
            self.reports_table.setItem(row, 3, QTableWidgetItem(format_datetime(rep.get("created_at", ""))))
            self.reports_table.setItem(row, 4, QTableWidgetItem(rep.get("original_filename", "")))

            size = rep.get("size_bytes", 0)
            self.reports_table.setItem(row, 5, QTableWidgetItem(f"{size / 1024:.1f} KB" if size else ""))

    def download_report(self):
        row = self.reports_table.currentRow()
        if row < 0:
            return

        report_id = self.reports_table.item(row, 0).text()
        filename_item = self.reports_table.item(row, 4)
        original_name = filename_item.text() if filename_item else f"report_{report_id}"

        if not TOKEN:
            return

        headers = {
            "Authorization": f"Bearer {TOKEN}"
        }

        try:
            response = requests.get(
                f"{BASE_URL}/reports/{report_id}/download",
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                save_path, _ = QFileDialog.getSaveFileName(self, "Сохранить отчёт", original_name)
                if save_path:
                    with open(save_path, "wb") as f:
                        f.write(response.content)
        except:
            pass

    def preview_report(self):
        row = self.reports_table.currentRow()
        if row < 0:
            return

        report_id = self.reports_table.item(row, 0).text()

        if not TOKEN:
            return

        headers = {
            "Authorization": f"Bearer {TOKEN}"
        }

        try:
            response = requests.get(
                f"{BASE_URL}/reports/{report_id}/download",
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")

                if "pdf" in content_type:
                    suffix = ".pdf"
                elif "word" in content_type or "document" in content_type:
                    suffix = ".docx"
                elif "image" in content_type:
                    suffix = ".png"
                else:
                    suffix = ".txt"

                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(response.content)
                    tmp_path = tmp.name

                os.startfile(tmp_path)
        except:
            pass

    def load_logs_data(self):
        self.all_logs = api_request("GET", "/bff/desktop/logs") or []
        self.filter_engineer_logs()

    def filter_engineer_logs(self):
        text = self.eng_log_filter.currentText()
        rows = self.all_logs if isinstance(self.all_logs, list) else []
        if text != "Все":
            rows = [r for r in rows if (r.get("status") or "").upper() == text.upper()]
        self.engineer_logs_table.setRowCount(len(rows))
        for row, log in enumerate(rows):
            self.engineer_logs_table.setItem(row, 0, QTableWidgetItem(str(log.get("id", ""))))
            self.engineer_logs_table.setItem(row, 1, QTableWidgetItem(log.get("user", "")))
            self.engineer_logs_table.setItem(row, 2, QTableWidgetItem(log.get("role", "")))
            self.engineer_logs_table.setItem(row, 3, QTableWidgetItem(log.get("action", "")))
            self.engineer_logs_table.setItem(row, 4, QTableWidgetItem(log.get("object", "")))
            self.engineer_logs_table.setItem(row, 5, QTableWidgetItem(format_datetime(log.get("date", ""))))
            self.engineer_logs_table.setItem(row, 6, QTableWidgetItem(log.get("status", "")))

    def on_object_click(self, item):
        name = item.text()
        self.selected_object = name
        self.obj_title.setText(name)
        self.create_btn.setEnabled(True)
        self.create_btn.setStyleSheet(STYLE_CREATE_BTN_ENABLED)

        fac = self.facility_cache.get(name, {})
        if fac:
            self.obj_status.setText(fac.get("status", ""))
            self.obj_info.setText(f"Адрес: {fac.get('address', '')}\nТип: {fac.get('type', '')}")

        data = api_request("GET", "/dev/fake-sensor-data?randomize=true")
        if data:
            facilities = data.get("facilities", [])
            for f in facilities:
                if f.get("name") == name:
                    equipment = f.get("equipment", [])
                    eq_table = self.tab_widget.widget(0).findChild(QTableWidget)
                    if eq_table:
                        eq_table.setRowCount(len(equipment))
                        for row, eq in enumerate(equipment):
                            eq_table.setItem(row, 0, QTableWidgetItem(eq.get("name", "")))
                            eq_table.setItem(row, 1, QTableWidgetItem(eq.get("type", "")))
                            eq_table.setItem(row, 2, QTableWidgetItem(eq.get("status", "")))

                    sensors = f.get("sensors", [])
                    sens_table = self.tab_widget.widget(1).findChild(QTableWidget)
                    if sens_table:
                        sens_table.setRowCount(len(sensors))
                        for row, sens in enumerate(sensors):
                            sens_table.setItem(row, 0, QTableWidgetItem(sens.get("name", "")))
                            sens_table.setItem(row, 1, QTableWidgetItem(sens.get("type", "")))
                            sens_table.setItem(row, 2, QTableWidgetItem(str(sens.get("value", ""))))
                            sens_table.setItem(row, 3, QTableWidgetItem(sens.get("state", "")))
                    break

    def open_create_dialog(self):
        if not self.employee_options:
            self.load_employees_data()

        sensor_data = api_request("GET", "/dev/fake-sensor-data?randomize=true")
        equipment_list = []
        sensors_list = []

        if sensor_data:
            facilities = sensor_data.get("facilities", [])
            for f in facilities:
                if f.get("name") == self.selected_object:
                    equipment_list = f.get("equipment", [])
                    sensors_list = f.get("sensors", [])
                    break

        dialog = QDialog(self)
        dialog.setWindowTitle("Создать заявку")
        dialog.setFixedSize(620, 460)
        dialog.setStyleSheet("background-color: white;")

        layout = QVBoxLayout(dialog)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(make_label("Создать заявку", STYLE_HEADER_BLUE, Qt.AlignCenter))

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        content_layout.addWidget(make_label(f"Объект: {self.selected_object}", "font-size: 20px; font-weight: bold; color: #103A5E;"))

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setSpacing(20)

        eq_widget = QWidget()
        eq_layout = QVBoxLayout(eq_widget)
        eq_layout.setSpacing(5)
        eq_layout.addWidget(make_label("Оборудование"))
        eq_combo = QComboBox()
        eq_combo.addItem("—")
        for eq in equipment_list:
            eq_combo.addItem(eq["name"])
        eq_combo.setMinimumHeight(35)
        eq_combo.setStyleSheet(STYLE_COMBO)
        eq_layout.addWidget(eq_combo)
        row_layout.addWidget(eq_widget)

        sens_widget = QWidget()
        sens_layout = QVBoxLayout(sens_widget)
        sens_layout.setSpacing(5)
        sens_layout.addWidget(make_label("Датчики"))
        sens_combo = QComboBox()
        sens_combo.addItem("—")
        for sens in sensors_list:
            sens_combo.addItem(sens["name"])
        sens_combo.setMinimumHeight(35)
        sens_combo.setStyleSheet(STYLE_COMBO)
        sens_layout.addWidget(sens_combo)
        row_layout.addWidget(sens_widget)

        content_layout.addWidget(row)

        content_layout.addWidget(make_label("Описание проблемы"))
        desc_text = QTextEdit()
        desc_text.setMaximumHeight(100)
        desc_text.setStyleSheet(STYLE_TEXT_EDIT)
        content_layout.addWidget(desc_text)

        bottom = QWidget()
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setSpacing(15)

        eng_widget = QWidget()
        eng_layout = QVBoxLayout(eng_widget)
        eng_layout.setSpacing(5)
        eng_layout.addWidget(make_label("Исполнитель"))
        eng_combo = QComboBox()
        eng_combo.addItem("Не назначен")
        for emp in self.employee_options:
            eng_combo.addItem(emp["name"])
        eng_combo.setFixedWidth(200)
        eng_combo.setMinimumHeight(35)
        eng_combo.setStyleSheet(STYLE_COMBO)
        eng_layout.addWidget(eng_combo)
        bottom_layout.addWidget(eng_widget)

        bottom_layout.addStretch()

        cancel_btn = make_button("Отмена", STYLE_BTN_CANCEL, 110, 35)
        cancel_btn.clicked.connect(dialog.reject)
        bottom_layout.addWidget(cancel_btn)

        create_btn = make_button("Создать", STYLE_BTN_BLUE, 110, 35)
        create_btn.clicked.connect(lambda: self.do_create(dialog, eq_combo, sens_combo, desc_text, eng_combo))
        bottom_layout.addWidget(create_btn)

        content_layout.addWidget(bottom)
        layout.addWidget(content)

        dialog.exec()

    def do_create(self, dialog, eq_combo, sens_combo, desc_text, eng_combo):
        fac = self.facility_cache.get(self.selected_object, {})
        eng_name = eng_combo.currentText()
        eng_id = None
        for emp in self.employee_options:
            if emp["name"] == eng_name:
                eng_id = emp["id"]
                break

        equipment_id = None
        sensor_id = None
        
        sensor_data = api_request("GET", "/dev/fake-sensor-data?randomize=true")
        if sensor_data:
            for f in sensor_data.get("facilities", []):
                if f.get("name") == self.selected_object:
                    for eq in f.get("equipment", []):
                        if eq["name"] == eq_combo.currentText():
                            equipment_id = eq.get("id")
                    for sens in f.get("sensors", []):
                        if sens["name"] == sens_combo.currentText():
                            sensor_id = sens.get("id")
                    break

        description = desc_text.toPlainText().strip() or "Без описания"

        data = {
            "facility_id": fac.get("id"),
            "assigned_engineer_id": eng_id,
            "title": "",
            "description": description,
            "equipment_id": equipment_id,
            "sensor_id": sensor_id,
            "operator_comment": f"Оборудование: {eq_combo.currentText()}, Датчик: {sens_combo.currentText()}"
        }

        api_request("POST", "/bff/desktop/tasks/create-from-sensor", data)
        dialog.accept()
        self.load_my_requests()

    def on_menu(self, item):
        row = self.menu_list.row(item)
        if row < 5:
            names = ["Главная", "Объекты", "Мои заявки", "Отчёты", "Журнал действий"]
            self.page_title.setText(names[row])
            self.pages.setCurrentIndex(row)
            self.load_current_page()

    def on_menu_exit(self):
        self.poll_timer.stop()
        self.close()
        self.open_login()
        
    def open_login(self):
        global TOKEN, USER_ROLE
        TOKEN = USER_ROLE = None
        self.login = LoginDialog()
        if self.login.exec() == QDialog.Accepted:
            if USER_ROLE == "operator":
                self.new_window = OperatorWindow()
            else:
                self.new_window = EngineerWindow()
            self.new_window.show()
            self.new_window.showMaximized()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    login = LoginDialog()
    if login.exec() == QDialog.Accepted:
        if USER_ROLE == "operator":
            w = OperatorWindow()
        else:
            w = EngineerWindow()
        w.show()
        w.showMaximized()
        sys.exit(app.exec())