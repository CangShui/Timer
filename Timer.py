import sys
import os
import json
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer
import winsound

STATE_FILE = "timer_state.json"

# ------------------ 保存 / 读取持久化状态 --------------------
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

# ------------------ 倒计时窗口 --------------------
class CountdownWindow(QtWidgets.QWidget):
    instances = []

    def __init__(self, state, time_secs):
        super().__init__(None, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.state = state
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)

        # 使用同一份位置大小信息
        default_geom = [200, 200, 200, 100]
        geom = self.state.get("geometry", default_geom)
        self.setGeometry(*geom)

        # 标签
        self.label = QtWidgets.QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color:white; background-color: rgba(0,0,0,0.7);")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.label)

        self.remaining_secs = time_secs
        CountdownWindow.instances.append(self)
        self.update_label()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(1000)

        self.apply_always_on_top()
        self._adjust_font()
        self.show()

    def apply_always_on_top(self):
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.show()

    def keyPressEvent(self, e: QtGui.QKeyEvent):
        step = 10
        changed = False
        if e.key() == Qt.Key_Up:
            self.move(self.x(), self.y() - step)
            changed = True
        elif e.key() == Qt.Key_Down:
            self.move(self.x(), self.y() + step)
            changed = True
        elif e.key() == Qt.Key_Left:
            self.move(self.x() - step, self.y())
            changed = True
        elif e.key() == Qt.Key_Right:
            self.move(self.x() + step, self.y())
            changed = True
        elif e.key() == Qt.Key_Plus and e.modifiers() & Qt.KeypadModifier:
            self._resize_by(1.2)
            changed = True
        elif e.key() == Qt.Key_Minus and e.modifiers() & Qt.KeypadModifier:
            self._resize_by(0.8)
            changed = True
        elif e.key() == Qt.Key_Period and e.modifiers() & Qt.KeypadModifier:
            self.close()
        if changed:
            self.save_geometry()
        else:
            super().keyPressEvent(e)

    def _resize_by(self, factor):
        g = self.geometry()
        new_w = int(g.width() * factor)
        new_h = int(g.height() * factor)
        cx = g.center().x()
        cy = g.center().y()
        self.resize(new_w, new_h)
        self.move(cx - new_w//2, cy - new_h//2)
        self._adjust_font()

    def moveEvent(self, e):
        super().moveEvent(e)
        self.save_geometry()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._adjust_font()
        self.save_geometry()

    def closeEvent(self, e):
        if self in CountdownWindow.instances:
            CountdownWindow.instances.remove(self)
        self.save_geometry()
        return super().closeEvent(e)

    def update_label(self):
        self.label.setText(self.format_time(self.remaining_secs))
        self._adjust_font()

    def update_countdown(self):
        if self.remaining_secs > 0:
            self.remaining_secs -= 1
            self.update_label()
        else:
            self.timer.stop()
            self.remaining_secs = 0
            self.update_label()
            self.play_alarm()

    def format_time(self, secs):
        m = secs // 60
        s = secs % 60
        return f"{m:02}:{s:02}"

    def _adjust_font(self):
        txt = self.label.text() or "00:00"
        w = max(10, self.width() - 20)
        h = max(10, self.height() - 20)
        font = QtGui.QFont("Segoe UI", 10, QtGui.QFont.Bold)
        low, high = 6, 1000
        best = 6
        while low <= high:
            mid = (low + high)//2
            font.setPointSize(mid)
            fm = QtGui.QFontMetrics(font)
            rect = fm.boundingRect(txt)
            if rect.width() <= w and rect.height() <= h:
                best = mid
                low = mid +1
            else:
                high = mid -1
        font.setPointSize(best)
        font.setBold(True)
        self.label.setFont(font)

    def save_geometry(self):
        self.state["geometry"] = [self.x(), self.y(), self.width(), self.height()]
        save_state(self.state)

    def play_alarm(self):
        winsound.MessageBeep(winsound.MB_ICONASTERISK)

# ------------------ 主窗口 --------------------
class MainWindow(QtWidgets.QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.setWindowTitle("计时器")
        self.resize(400, 300)

        layout = QtWidgets.QVBoxLayout(self)

        self.input_edit = QtWidgets.QLineEdit(self)
        self.input_edit.setPlaceholderText("输入倒计时 (例如 0430)")
        layout.addWidget(self.input_edit)

        self.history_list = QtWidgets.QListWidget(self)
        layout.addWidget(self.history_list)

        btn_layout = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("开始倒计时")
        self.reset_btn = QtWidgets.QPushButton("重置历史")
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.reset_btn)
        layout.addLayout(btn_layout)

        self.start_btn.clicked.connect(self.start_timer)
        self.history_list.itemDoubleClicked.connect(self.apply_from_history)
        self.reset_btn.clicked.connect(self.reset_history)
        self.input_edit.returnPressed.connect(self.start_timer)

        self.load_history()

    def load_history(self):
        self.history_list.clear()
        for t in self.state.get("history", []):
            self.history_list.addItem(t)

    def save_history(self):
        items = [self.history_list.item(i).text() for i in range(self.history_list.count())]
        self.state["history"] = items
        save_state(self.state)

    def parse_time_input(self, text):
        text = text.strip()
        if not text:
            return None
        if ":" in text:
            try:
                m,s = map(int,text.split(":"))
                return m*60+s
            except:
                return None
        if text.isdigit():
            num = int(text)
            if num < 60:
                return num
            else:
                s = num % 100
                m = num // 100
                return m*60 + s
        return None

    def start_timer(self):
        raw_text = self.input_edit.text()
        secs = self.parse_time_input(raw_text)
        if secs is None:
            QtWidgets.QMessageBox.warning(self, "格式错误", "请输入正确的时间，例如 0430 或 04:30")
            return

        display_text = f"{secs // 60:02}:{secs % 60:02}"
        self.input_edit.setText(display_text)

        if display_text not in [self.history_list.item(i).text() for i in range(self.history_list.count())]:
            self.history_list.addItem(display_text)
            self.save_history()

        CountdownWindow(self.state, secs)

    def apply_from_history(self, item):
        self.input_edit.setText(item.text())
        self.start_timer()

    def reset_history(self):
        reply = QtWidgets.QMessageBox.question(
            self, "确认重置", "确定要重置历史记录吗？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.state["history"] = []
            save_state(self.state)
            self.load_history()

# ------------------ 主程序入口 --------------------
def main():
    app = QtWidgets.QApplication(sys.argv)
    state = load_state()
    win = MainWindow(state)
    win.show()
    sys.exit(app.exec_())

if __name__=="__main__":
    main()
