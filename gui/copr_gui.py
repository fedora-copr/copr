import sys
import random
import string

from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, QThread, QObject, pyqtSignal
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QMenu,
)

from munch import unmunchify
import json

from copr.v3 import Client, exceptions

class FetchChrootWorker(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, client):
        super().__init__()
        self.client = client

    def run(self):
        try:
            # Replace this with the actual API call.
            chroots = None
            try:
                chroots = self.client.available_chroots
            except AttributeError:
                chroots = self.client.mock_chroot_proxy.get_list().keys()
                chroots = list([i for i in chroots if (len(i) > 2 and i[:2] != '__') ])
                chroots.sort()
                self.client.available_chroots = chroots

            self.succeeded.emit(chroots)

        except Exception as e:
            self.failed.emit(str(e))
        finally:
            self.finished.emit()


def FetchChroot(client, chroots_edit):
    thread = QThread(chroots_edit)
    worker = FetchChrootWorker(client)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.succeeded.connect(
        chroots_edit.set_available_chroots
    )
    worker.finished.connect(
        thread.quit
    )
    worker.finished.connect(
        worker.deleteLater
    )
    thread.finished.connect(
        thread.deleteLater
    )
    thread.start()
    add_worker_and_thread(worker, thread)

class ChrootEditor(QWidget):
    def __init__(self, chroots=None, parent=None):
        super().__init__(parent)

        self._chroots = list(chroots or [])
        self._available_chroots = []

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "Enter one chroot per line"
        )

        self.edit_button = QPushButton("...")
        self.edit_button.setFixedSize(28, 28)
        self.edit_button.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        self.edit_button.clicked.connect(
            self.edit_table
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.editor)

        # Put the button in the top-right corner
        # of the QPlainTextEdit.
        self.edit_button.setParent(self.editor)

        self.update_button_position()
        self.set_chroots(self._chroots)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_button_position()

    def update_button_position(self):
        self.edit_button.move(
            self.editor.width()
            - self.edit_button.width()
            - 4,
            4,
        )

    def chroots(self):
        """
        Return the current chroot list.

        This reads directly from the text editor, so
        manually typed changes are always included.
        """
        return [
            line.strip()
            for line in self.editor.toPlainText().splitlines()
            if line.strip()
        ]

    def set_chroots(self, chroots):
        self._chroots = list(chroots)

        self.editor.setPlainText(
            "\n".join(self._chroots)
        )

    def set_available_chroots(self, chroots):
        """
        Called later by FetchChroot().
        """
        self._available_chroots = list(chroots)

    def edit_table(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit chroots")
        dialog.resize(600, 400)

        layout = QVBoxLayout(dialog)

        table = QTableWidget()
        table.setColumnCount(1)
        table.setHorizontalHeaderLabels(
            ["Chroot"]
        )

        table.horizontalHeader().setStretchLastSection(
            True
        )

        table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )

        layout.addWidget(table)

        buttons_layout = QHBoxLayout()

        add_button = QPushButton("Add")
        delete_button = QPushButton("Delete")

        buttons_layout.addWidget(add_button)
        buttons_layout.addWidget(delete_button)
        buttons_layout.addStretch()

        layout.addLayout(buttons_layout)

        dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )

        layout.addWidget(dialog_buttons)

        # Populate table from the current plain text.
        current_chroots = self.chroots()

        for chroot in current_chroots:
            self.add_table_row(table, chroot)

        def add_row():
            self.add_table_row(table)

            row = table.rowCount() - 1
            table.selectRow(row)

            combo = table.cellWidget(row, 0)

            if combo:
                combo.setFocus()
                combo.showPopup()

        def delete_row():
            rows = table.selectionModel().selectedRows()

            if not rows:
                return

            # Delete selected rows from bottom to top.
            for index in sorted(
                rows,
                key=lambda x: x.row(),
                reverse=True,
            ):
                table.removeRow(index.row())

        add_button.clicked.connect(add_row)
        delete_button.clicked.connect(delete_row)

        dialog_buttons.accepted.connect(
            dialog.accept
        )
        dialog_buttons.rejected.connect(
            dialog.reject
        )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        chroots = []

        for row in range(table.rowCount()):
            combo = table.cellWidget(row, 0)

            if combo is None:
                continue

            value = combo.currentText().strip()

            if value:
                chroots.append(value)

        self.set_chroots(chroots)

    def add_table_row(
        self,
        table,
        value=None,
    ):
        row = table.rowCount()
        table.insertRow(row)
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(
            self._available_chroots
        )
        if value:
            if (
                combo.findText(value)
                == -1
            ):
                combo.addItem(value)
            combo.setCurrentText(value)
        table.setCellWidget(
            row,
            0,
            combo,
        )


class ProjectCardsLayout(QVBoxLayout):
    widget_removed = pyqtSignal(QWidget)

    def removeWidget(self, widget):
        super().removeWidget(widget)
        self.widget_removed.emit(widget)

class DeletePackageWorker(QObject):
    finished = pyqtSignal()
    failed = pyqtSignal(str)
    done = pyqtSignal()

    def __init__(self, client, package):
        super().__init__()

        self.client = client
        self.data = package

    def run(self):
        try:
            for package in self.data:
                owner = package.ownername
                project = package.projectname
                name = package.name

                self.client.package_proxy.delete(
                    owner,
                    project,
                    name,
                )

                self.done.emit()

        except Exception as e:
            self.failed.emit(str(e))

        finally:
            self.finished.emit()

class AddPackageWorker(QObject):
    finished = pyqtSignal()
    failed = pyqtSignal(str)
    done = pyqtSignal()

    def __init__(self, client, source_dict):
        super().__init__()

        self.client = client
        self.data = source_dict

    def run(self):
        try:
            NewPackage(self.client, self.data)
            self.done.emit()
        except Exception as e:
            self.failed.emit(str(e))
        finally:
            self.finished.emit()

class AddBuildWorker(QObject):
    finished = pyqtSignal()
    failed = pyqtSignal(str)
    done = pyqtSignal()

    def __init__(self, client, source_dict):
        super().__init__()

        self.client = client
        self.data = source_dict

    def run(self):
        try:
            NewBuild(self.client, self.data)
            self.done.emit()
        except Exception as e:
            self.failed.emit(str(e))
        finally:
            self.finished.emit()

class DeleteBuildWorker(QObject):
    finished = pyqtSignal()
    failed = pyqtSignal(str)
    done = pyqtSignal()

    def __init__(self, client, package):
        super().__init__()

        self.client = client
        self.data = package

    def run(self):
        try:
            for build in self.data:
                try:
                    self.client.build_proxy.cancel(
                        build.id
                    )
                except Exception:
                    pass
                self.client.build_proxy.delete(
                    build.id
                )

                self.done.emit()

        except Exception as e:
            self.failed.emit(str(e))

        finally:
            self.finished.emit()

class DeleteProjectWorker(QObject):
    finished = pyqtSignal()
    failed = pyqtSignal(str)
    done = pyqtSignal()

    def __init__(self, client, project):
        super().__init__()

        self.client = client
        self.project = project

    def run(self):
        try:
            owner, project = self.project.full_name.split('/')
            result = self.client.project_proxy.delete(
                owner, project
            )
            self.done.emit()

        except Exception as e:
            self.failed.emit(str(e))

        finally:
            self.finished.emit()


def show_text_dialog(parent, title, text):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(600, 400)

    layout = QVBoxLayout(dialog)

    text_edit = QPlainTextEdit()
    text_edit.setReadOnly(True)
    text_edit.setPlainText(text)

    layout.addWidget(text_edit)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok
    )

    buttons.accepted.connect(dialog.accept)

    layout.addWidget(buttons)

    dialog.exec()


class ProjectCard(QFrame):
    clicked = pyqtSignal()
    double_clicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
            event.accept()
            return

        super().mouseDoubleClickEvent(event)

    def project_updated(self):
        pass

    def project_update_failed(self, error):
        QMessageBox.critical(
            self,
            "Project update failed",
            error,
        )

    def update_project(
        self,
        description,
        instructions,
        homepage,
        contact,
    ):
        update_thread = QThread(self)
        update_worker = UpdateProjectOverviewWorker(
            self.client,
            self.project,
            description,
            instructions,
            homepage,
            contact,
        )
        update_worker.moveToThread(
            update_thread
        )
        update_thread.started.connect(
            update_worker.run
        )
        update_worker.updated.connect(
            self.project_updated
        )
        update_worker.failed.connect(
            self.project_update_failed
        )
        update_worker.finished.connect(
            update_thread.quit
        )
        update_worker.finished.connect(
            update_worker.deleteLater
        )
        update_thread.finished.connect(
            update_thread.deleteLater
        )
        update_thread.start()
        add_worker_and_thread(update_worker, update_thread)

    def __init__(self, project, client, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.project = project
        self._pre_init = False
        self.selected = False

        self.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        def setup():
            nonlocal self
            pre_init = self._pre_init
            self.setup_ui()
            self.update_style()
            if pre_init:
                self.update_project(
                    self.project.description,
                    self.project.instructions,
                    self.project.homepage,
                    self.project.contact
                )
            self._pre_init = True

        def showProjectWindow():
            nonlocal self, setup
            window = ProjectWindow(self.project, self)
            window.overview.saved.connect(
                setup    
            )
            window.show()
        self.double_clicked.connect(
            showProjectWindow
        )
        self.setMouseTracking(True)
        setup()
        self.client = client

    def remove_self(self):
        project = self.project
        thread = QThread(self)
        worker = DeleteProjectWorker(
            self.client,
            project,
        )
        worker.moveToThread(
            thread
        )
        thread.started.connect(
            worker.run
        )

        def delete_later():
            nonlocal self
            layout = self.parentWidget().layout()
            if layout:
                layout.removeWidget(self)
            self.deleteLater()
            layout.set_project_count()

        worker.done.connect(
            delete_later
        )
        worker.failed.connect(
            lambda error: QMessageBox.critical(
                self,
                "Delete failed",
                error,
            )
        )
        worker.finished.connect(
            thread.quit
        )
        worker.finished.connect(
            worker.deleteLater
        )
        thread.finished.connect(
            thread.deleteLater
        )
        thread.start()
        add_worker_and_thread(worker, thread)

    def contextMenuEvent(self, event):
        self.show_context_menu(event.pos())
        event.accept()


    def show_context_menu(self, pos=None):
        menu = QMenu(self)

        open_action = QAction("Open", self)
        delete_action = QAction("Delete", self)
        view_json = QAction("View Json", self)

        menu.addAction(open_action)
        menu.addAction(delete_action)
        menu.addAction(view_json)

        pos = self.mapToGlobal(pos if pos else self.rect().center())
        action = menu.exec(pos)

        if action == open_action:
            self.double_clicked.emit()
        elif action == delete_action:
            self.remove_self()
        elif action == view_json:
            pretty = json.dumps(
                unmunchify(self.project),
                indent=4,
                sort_keys=True,
            )
            show_text_dialog(self, "Json", pretty)

    def refresh(self):
        self.name_label.setText(
            self.project.full_name
        )

        self.description_label.setText(
            self.project.description
            or "No description"
        )
        chroots = {}
        for chroot in self.project.chroot_repos:
            try:
                release, arch = chroot.rsplit("-", 1)
            except ValueError:
                release = chroot
                arch = ""
            chroots.setdefault(
                release,
                []
            ).append(arch)
        if not chroots:
            self.chroots_label.hide()
            self.chroots_value_label.hide()
            return
        self.chroots_label.show()
        self.chroots_value_label.show()
        lines = []

        for release, architectures in chroots.items():
            architectures = sorted(
                architectures
            )

            lines.append(
                f"{release}: "
                f"{', '.join(architectures)}"
            )
        self.chroots_value_label.setText(
            "\n".join(lines)
        )


    def setup_ui(self):
        if self._pre_init:
            self.refresh()
            return
        self._pre_init = True
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            16, 12, 16, 12
        )
        layout.setSpacing(5)
    # --------------------------------------------------
    # Name
    # --------------------------------------------------
        self.name_label = QLabel()
        self.name_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        font = QFont()
        font.setBold(True)
        self.name_label.setFont(font)
        layout.addWidget(self.name_label)
    # --------------------------------------------------
    # Description
    # --------------------------------------------------
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        layout.addWidget(self.description_label)
    # --------------------------------------------------
    # Chroots
    # --------------------------------------------------
        self.chroots_label = QLabel("Chroots")
        self.chroots_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        font = QFont()
        font.setBold(True)
        self.chroots_label.setFont(font)
        layout.addWidget(self.chroots_label)
        self.chroots_value_label = QLabel()
        self.chroots_value_label.setWordWrap(True)
        self.chroots_value_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        layout.addWidget(
            self.chroots_value_label
        )
        self.refresh()


    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.press_event()
        super().mousePressEvent(event)

    def set_selected(self, selected):
        self.selected = selected
        self.update_style()

    def focusInEvent(self, event):
        self.update_style()
        super().focusInEvent(event)

    def press_event(self):
        self.set_selected(True)
        self.clicked.emit()

        QTimer.singleShot(
            300,
            lambda: self.set_selected(False)
        )

    def keyPressEvent(self, event):
        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            self.press_event()
        if (event.key() == Qt.Key.Key_F10 and (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ) ) or event.key() == Qt.Key.Key_Menu:
            self.show_context_menu()
        super().keyPressEvent(event)


    def focusOutEvent(self, event):
        self.update_style()
        super().focusOutEvent(event)


    def update_style(self):
        if self.selected:
            self.setStyleSheet("""
                ProjectCard {
                    border: 2px solid palette(highlight);
                    border-radius: 8px;
                    background: palette(alternate-base);
                }
            """)
        else:
            self.setStyleSheet("""
                ProjectCard {
                    border: 1px solid palette(mid);
                    border-radius: 8px;
                }

                ProjectCard:hover, 
                ProjectCard:focus {
                    border: 1px solid palette(highlight);
                }
            """)


# ============================================================
# Login worker
# ============================================================

class LoginWorker(QObject):
    succeeded = pyqtSignal(object, str)
    failed = pyqtSignal(str)

    def __init__(self, config=None, use_config_file=False):
        super().__init__()

        self.config = config
        self.use_config_file = use_config_file

    def user_exists(self, client, username):
#        project_name = "".join(random.choices(string.ascii_letters, k=25))
#        chroots = ["fedora-rawhide-x86_64"]  # Supported targets
#        description = ""
#        instructions = ""

#        try:
            # Create the project
#            project = client.project_proxy.add(
#                ownername=username,
#                projectname=project_name,
#                chroots=chroots,
#                description=description,
#                instructions=instructions
#            )
#            client.project_proxy.delete(username, project_name)
#        except Exception as e:
#            return False

        return True

    def run(self):
        try:
            if self.use_config_file:
                client = Client.create_from_config_file()
            else:
                client = Client(self.config)

            username = client.base_proxy.auth_username()
            if self.user_exists(client, username):
                self.succeeded.emit(client, username)
            else:
                raise Exception(f"User {username} not exists")

        except Exception as e:
            self.failed.emit(str(e))


# ============================================================
# Project worker
# ============================================================

class ProjectWorker(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, client, username):
        super().__init__()

        self.client = client
        self.username = username

    def run(self):
        try:
            projects = self.client.project_proxy.get_list(
                ownername=self.username
            )

            self.succeeded.emit(projects)

        except Exception as e:
            self.failed.emit(str(e))


# ============================================================
# Credentials dialog
# ============================================================

class CredentialsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Copr Credentials")
        self.resize(400, 180)

        layout = QFormLayout(self)

        self.url = QLineEdit()
        self.url.setText(
            "https://copr.fedorainfracloud.org"
        )
        self.url.setPlaceholderText("Copr URL")

        self.login = QLineEdit()
        self.login.setEchoMode(
            QLineEdit.EchoMode.Password
        )
        self.login.setPlaceholderText("API login")

        self.user = QLineEdit()
        self.user.setPlaceholderText("Copr username")

        self.token = QLineEdit()
        self.token.setEchoMode(
            QLineEdit.EchoMode.Password
        )
        self.token.setPlaceholderText("API token")

        layout.addRow("URL:", self.url)
        layout.addRow("User:", self.user)
        layout.addRow("Login:", self.login)
        layout.addRow("Token:", self.token)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addRow(buttons)

    def credentials(self):
        return (
            self.login.text().strip(),
            self.token.text().strip(),
            self.user.text().strip(),
            self.url.text().strip(),
        )

class UpdateProjectOverviewWorker(QObject):
    updated = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        client,
        project,
        description,
        instructions,
        homepage,
        contact,
    ):
        super().__init__()

        self.client = client
        self.project = project

        self.description = description
        self.instructions = instructions
        self.homepage = homepage
        self.contact = contact

    def run(self):
        try:
            owner, name = self.project.full_name.split("/", 1)

            project = self.client.project_proxy.edit(
                ownername=owner,
                projectname=name,
                description=self.description,
                instructions=self.instructions,
                homepage=self.homepage,
                contact=self.contact,
            )

            self.updated.emit(project)

        except Exception as error:
            self.failed.emit(str(error))

        finally:
            self.finished.emit()


class UpdateProjectOptionsWorker(QObject):
    updated = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        client,
        project,
        data
    ):
        super().__init__()

        self.client = client
        self.project = project

        self.data = data

    def run(self):
        try:
            owner, name = self.project.full_name.split("/", 1)

            project = self.client.project_proxy.edit(
                ownername=owner,
                projectname=name,
                **self.data
            )

            self.updated.emit(project)

        except Exception as error:
            self.failed.emit(str(error))

        finally:
            self.finished.emit()


class NewProjectWorker(QObject):
    created = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        client,
        username,
        name,
        chroots,
    ):
        super().__init__()

        self.client = client
        self.username = username
        self.name = name
        self.chroots = chroots

    def run(self):
        try:
            project = self.client.project_proxy.add(
                ownername=self.username,
                projectname=self.name,
                chroots=self.chroots,
            )

            self.created.emit(project)

        except Exception as error:
            self.failed.emit(str(error))

        finally:
            self.finished.emit()


def add_project_func(self):
    dialog = QDialog(self)
    dialog.setWindowTitle("New project")
    layout = QFormLayout(dialog)
    name_edit = QLineEdit()
    name_edit.setPlaceholderText(
        "Project name"
    )
    chroots_edit = ChrootEditor()
    layout.addRow(
        "Name:",
        name_edit,
    )
    layout.addRow(
        "Chroots:",
        chroots_edit,
    )
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok
        | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(
        dialog.accept
    )
    buttons.rejected.connect(
        dialog.reject
    )
    layout.addRow(buttons)
    FetchChroot(self.client, chroots_edit)

    if (
        dialog.exec()
        != QDialog.DialogCode.Accepted
    ):
        return

    name = name_edit.text().strip()
    chroots = chroots_edit.chroots()
    if not name:
        QMessageBox.warning(
            self,
            "Invalid project",
            "Project name is required.",
        )
        return

    if not chroots:
        QMessageBox.warning(
            self,
            "Invalid project",
            "At least one chroot is required.",
        )
        return

    self.start_new_project(
        name,
        chroots,
    )


def edit_chroots_func(self):
    dialog = QDialog(self)
    dialog.setWindowTitle("Edit project chroots")
    layout = QFormLayout(dialog)
    chroots_edit = ChrootEditor()
    chroots_edit.set_chroots(self.chroots())
    layout.addRow(
        "Chroots:",
        chroots_edit,
    )
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok
        | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(
        dialog.accept
    )
    buttons.rejected.connect(
        dialog.reject
    )
    layout.addRow(buttons)
    FetchChroot(self.client, chroots_edit)

    if (
        dialog.exec()
        != QDialog.DialogCode.Accepted
    ):
        return

    chroots = chroots_edit.chroots()

    if not chroots:
        QMessageBox.warning(
            self,
            "Invalid chroots",
            "At least one chroot is required.",
        )
        return

    self.set_chroots(
        chroots
    )
    self.changed.emit()


def start_new_project_func(self, name, chroots):
    self.add_button.setEnabled(False)
    self.refresh_button.setEnabled(False)
    new_project_thread = QThread(self)
    new_project_worker = NewProjectWorker(
        self.client,
        self.username,
        name,
        chroots,
    )
    new_project_worker.moveToThread(
        new_project_thread
    )
    new_project_thread.started.connect(
        new_project_worker.run
    )
    new_project_worker.created.connect(
        self.project_created
    )
    new_project_worker.failed.connect(
        self.project_creation_failed
    )
    new_project_worker.finished.connect(
        new_project_thread.quit
    )
    new_project_worker.finished.connect(
        new_project_worker.deleteLater
    )
    new_project_thread.finished.connect(
        new_project_thread.deleteLater
    )
    new_project_thread.finished.connect(
        self.project_creation_failed
    )
    new_project_thread.start()
    add_worker_and_thread(new_project_worker, new_project_thread)


# ============================================================
# Main window
# ============================================================

class CoprWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.client = None
        self.username = None
        self.logged_in = False

        # Keep references to threads/workers alive.
        self.login_thread = None
        self.login_worker = None

        self.project_thread = None
        self.project_worker = None

        self.setWindowTitle("Copr Projects")
        self.resize(800, 500)

        self.setup_ui()

    def set_project_enabled(self, enable):
        self.refresh_button.setEnabled(enable)
        self.add_button.setEnabled(enable)

    # ========================================================
    # UI
    # ========================================================

    def setup_ui(self):
        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            24, 24, 24, 24
        )

        layout.setSpacing(16)

        # ----------------------------------------------------
        # Account/status card
        # ----------------------------------------------------

        card = QFrame()
        card.setFrameShape(
            QFrame.Shape.StyledPanel
        )
        card.setFrameShadow(
            QFrame.Shame
            if False
            else QFrame.Shadow.Raised
        )

        card_layout = QHBoxLayout(card)

        card_layout.setContentsMargins(
            16, 12, 16, 12
        )

        self.status = QLabel()

        card_layout.addWidget(self.status)
        card_layout.addStretch()

        self.config_file_checkbox = QCheckBox("Use config file")
        self.config_file_checkbox.setChecked(True)

        self.login_button = QPushButton("Connect")
        self.login_button.setMinimumWidth(100)
        self.login_button.clicked.connect(
            self.login
        )

        card_layout.addWidget(self.config_file_checkbox)
        card_layout.addWidget(self.login_button)

        layout.addWidget(card)

        # ----------------------------------------------------
        # Projects header
        # ----------------------------------------------------

        projects_header = QHBoxLayout()

        projects_label = QLabel("Projects")

        projects_font = QFont()
        projects_font.setPointSize(14)
        projects_font.setBold(True)

        projects_label.setFont(projects_font)

        self.project_count = QLabel("0 projects")

        projects_header.addWidget(
            projects_label
        )
        projects_header.addWidget(
            self.project_count
        )
        projects_header.addStretch()

        self.refresh_button = QPushButton(
            "Refresh"
        )

        self.add_button = QPushButton(
            "Add"
        )

        self.set_project_enabled(False)

        self.refresh_button.clicked.connect(
            self.load_projects
        )
        self.add_button.clicked.connect(
            self.add_project
        )

        projects_header.addWidget(
            self.add_button
        )

        projects_header.addWidget(
            self.refresh_button
        )

        layout.addLayout(projects_header)

        # ----------------------------------------------------
        # Project card list
        # ----------------------------------------------------

        self.scroll = QScrollArea()

        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.cards_widget = QWidget()

        self.cards_layout = ProjectCardsLayout(
            self.cards_widget
        )

        self.cards_layout.set_project_count = self.set_project_count

        self.cards_layout.setContentsMargins(
            0, 0, 0, 0
        )

        self.cards_layout.setSpacing(10)

        self.scroll.setWidget(
            self.cards_widget
        )

        layout.addWidget(self.scroll)

        # Initial state
        self.not_connected()

    # ========================================================
    # Connection state
    # ========================================================

    def connection_succeeded(self):
        self.status.setText(
            f"Connected as {self.username}"
        )

        self.status.setStyleSheet(
            "color: #22863a; font-weight: bold;"
        )

    def connection_failed(self):
        self.status.setText(
            "Connection failed"
        )

        self.status.setStyleSheet(
            "color: #cb2431; font-weight: bold;"
        )

    def not_connected(self):
        self.status.setText(
            "Not connected"
        )

        self.status.setStyleSheet(
            "font-weight: bold;"
        )

    def project_created(self, project):
        card = self.create_project_card(project)

        self.cards_layout.insertWidget(
            self.cards_layout.count() - 1,
            card,
        )

        self.set_project_count()


    # ========================================================
    # Login
    # ========================================================

    def login(self):
        if self.logged_in:
            self.disconnect()
            return

        self.status.setText(
            "Connecting..."
        )

        self.login_button.setEnabled(False)

        # Try configuration file first.
        self.start_login(
            use_config_file=self.config_file_checkbox.isChecked()
        )

    def start_login(
        self,
        config=None,
        use_config_file=False,
    ):
        login_thread = QThread()
        login_worker = LoginWorker(
            config=config,
            use_config_file=use_config_file,
        )

        login_worker.moveToThread(
            login_thread
        )

        login_thread.started.connect(
            login_worker.run
        )

        login_worker.succeeded.connect(
            self.login_succeeded
        )

        login_worker.failed.connect(
            self.login_failed
        )

        login_worker.succeeded.connect(
            login_thread.quit
        )

        login_worker.failed.connect(
            login_thread.quit
        )

        login_thread.finished.connect(
            login_worker.deleteLater
        )

        login_thread.finished.connect(
            login_thread.deleteLater
        )

        login_thread.start()
        add_worker_and_thread(login_worker, login_thread)

    def login_succeeded(
        self,
        client,
        username,
    ):
        self.client = client
        self.username = username
        self.logged_in = True

        self.connection_succeeded()

        self.login_button.setText(
            "Disconnect"
        )
        self.login_button.setEnabled(True)

        self.set_project_enabled(
            True
        )

        self.load_projects()

    def login_failed(self, error):
        self.client = None
        self.username = None

        # Config file failed.
        #
        # Ask the user for credentials.
        dialog = CredentialsDialog(self)

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            self.not_connected()

            self.login_button.setEnabled(
                True
            )

            return

        login, token, user, url = (
            dialog.credentials()
        )

        if not login or not token:
            self.not_connected()

            self.login_button.setEnabled(
                True
            )

            QMessageBox.warning(
                self,
                "Missing credentials",
                "Please enter both your "
                "login and API token.",
            )

            return

        if not url:
            self.not_connected()

            self.login_button.setEnabled(
                True
            )

            QMessageBox.warning(
                self,
                "Missing URL",
                "Please enter a Copr URL.",
            )

            return

        config = {
            "copr_url": url,
            "login": login,
            "token": token,
            "username": user,
        }

        self.status.setText(
            "Connecting..."
        )

        self.login_button.setEnabled(
            False
        )

        self.start_login(
            config=config,
            use_config_file=False,
        )

    # ========================================================
    # Disconnect
    # ========================================================

    def disconnect(self, disconnected=True):
        self.status.setText(
            "Disconnecting..."
        )

        self.client = None
        self.username = None
        self.logged_in = False

        self.login_button.setText(
            "Connect"
        )

        self.set_project_enabled(
            False
        )

        self.clear_project_cards()

        self.set_project_count()

        if disconnected:
            self.not_connected()
        else:
            self.connection_failed()

    # ========================================================
    # Project adding
    # ========================================================
    def add_project(self):
        add_project_func(self)

    def start_new_project(self, name, chroots):
        start_new_project_func(self, name, chroots)

    def new_project(self, name, chroots):
        project = self.client.project_proxy.add(self.client.base_proxy.auth_username(), name, chroots)
        card = self.create_project_card(
            project
        )

        self.cards_layout.addWidget(
            card
        )

        self.set_project_count()


    # ========================================================
    # Project loading
    # ========================================================

    def load_projects(self):

        self.clear_project_cards()

        if not self.client or not self.username:
            self.set_project_count()

            return

        self.set_project_enabled(
            False
        )

        self.project_count.setText(
            "Loading..."
        )

        project_thread = QThread()

        project_worker = ProjectWorker(
            self.client,
            self.username,
        )

        project_worker.moveToThread(
            project_thread
        )

        project_thread.started.connect(
            project_worker.run
        )

        project_worker.succeeded.connect(
            self.projects_loaded
        )

        project_worker.failed.connect(
            self.projects_failed
        )

        project_worker.succeeded.connect(
            project_thread.quit
        )

        project_worker.failed.connect(
            project_thread.quit
        )

        project_thread.finished.connect(
            project_worker.deleteLater
        )

        project_thread.finished.connect(
            project_thread.deleteLater
        )

        project_thread.start()
        add_worker_and_thread(project_worker, project_thread)

    def projects_loaded(self, projects):
        if not self.logged_in:
            self.disconnect()
            return
            
        for project in projects:
            card = self.create_project_card(
                project
            )

            self.cards_layout.addWidget(
                card
            )

        self.set_project_count()

        # Keep cards at the top.
        self.cards_layout.addStretch()

        self.set_project_enabled(
            True
        )

    def project_card_count(self):
        return sum(
            isinstance(
                self.cards_layout.itemAt(i).widget(),
                ProjectCard
            )
            for i in range(self.cards_layout.count())
        )


    def set_project_count(self):
        count = self.project_card_count()

        self.project_count.setText(
            f"{count} project"
            + ("" if count == 1 else "s")
        )

    def projects_failed(self, error):
        self.project_count.setText(
            "Failed to load"
        )

        self.disconnect(False)

        QMessageBox.critical(
            self,
            "Could not load projects",
            error,
        )

    def project_creation_failed(self, error = None):
        if error:
            QMessageBox.critical(
                self,
                "Could not create project",
                error,
            )
        else:
            self.set_project_enabled(True)

    # ========================================================
    # Project cards
    # ========================================================

    def create_project_card(self, project):
        card = ProjectCard(project, self.client)

        card.clicked.connect(
            lambda card=card:
                self.project_card_clicked(card)
        )
        return card

    def project_card_clicked(self, card):
        pass

    def clear_project_cards(self):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()
                
# ============================================================
def format_duration(start, end):
    if start and end:
        start = int(start)
        end = int(end)
        seconds = abs(end - start)
        if not seconds:
            return ''
    else:
        return ''

    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"

    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"

    hours = round(minutes / 60)
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''}"

    days = round(hours / 24)
    if days < 7:
        return f"{days} day{'s' if days != 1 else ''}"

    weeks = round(days / 7)
    if weeks < 5:
        return f"{weeks} week{'s' if weeks != 1 else ''}"

    months = round(days / 30)
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''}"

    years = round(days / 365)
    return f"{years} year{'s' if years != 1 else ''}"

def time_ago(timestamp):
    from datetime import datetime, timezone
    if not timestamp:
        return ''
    else:
        timestamp = int(timestamp)
    now = datetime.now(timezone.utc)
    then = datetime.fromtimestamp(timestamp, timezone.utc)
    seconds = int((now - then).total_seconds())

    if seconds < 60:
        return "just now"

    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

    hours = round(minutes / 60)
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    days = round(hours / 24)
    if days < 7:
        return f"{days} day{'s' if days != 1 else ''} ago"

    weeks = round(days / 7)
    if weeks < 5:
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"

    months = round(days / 30)
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"

    years = round(days / 365)
    return f"{years} year{'s' if years != 1 else ''} ago"

# ============================================================
# ProjectPackagesFrame
# ============================================================
class ProjectPackagesFrame(QFrame):
    def __init__(self, parent):
        super().__init__(parent)

        self.client = parent.client
        self.project = parent.project
        self._skip_setup = False
    #    self.setup_ui()

    def copr_action(self, rows, act):
        return CoprAction(self, rows, act, PACKAGE_SECTION)

    def setup_ui(self):
        if self._skip_setup:
            return
        else:
            self._skip_setup = True
        layout = QVBoxLayout(self)

        def data_fetch(offset, count):
            name = self.project.name
            owner = self.client.base_proxy.auth_username()
            return self.client.package_proxy.get_list(owner, name, 
                pagination={'limit':count,'offset':offset}, with_latest_build=True)

        def data_process(data, column):
            builds = data.builds.get('latest', None) or {}
            srcs = builds.get('source_package', None) or {}
            if column == 0:
                return data.get('id', None) or ''
            elif column == 1:
                return data.get('name', None) or ''
            elif column == 2:
                return srcs.get('version', None) or ''
            elif column == 3:
                return time_ago(builds.get('submitted_on', None) or '')
            elif column == 4:
                return format_duration(
                    builds.get('ended_on', None) or '', 
                    builds.get('submitted_on', None) or '')
            elif column == 5:
                return builds.get('state', None) or ''
            return ""

        self.view = PaginatedTableView(CoprTable(
            data_fetch, data_process, ["ID", "Name", "Version", "Submitted", "BuildTime", "Status"]
        ), menus={
            ADD_ACTION: "New",
            EDIT_ACTION: "Edit",
            BUILD_ACTION: "Build",
            DELETE_ACTION: "Delete",
            VIEW_JSON_ACTION: "View Json"
        }, action = self.copr_action)
        layout.addWidget(self.view, 1)


# ============================================================
# ProjectOverviewFrame
# ============================================================
class ProjectOverviewFrame(QFrame):
    saved = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)

        self.project = parent.project
        self.editing = False

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        # --------------------------------------------------
        # Header
        # --------------------------------------------------

        owner, _, name = self.project.full_name.partition("/")

        owner_label = QLabel(f"{owner} /")

        name_label = QLabel(name)

        font = QFont()
        font.setBold(True)
        name_label.setFont(font)

        header = QHBoxLayout()
        header.setSpacing(6)

        header.addWidget(owner_label)
        header.addWidget(name_label)
        header.addStretch()

        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self.toggle_edit)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.hide()

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save)
        self.save_button.hide()

        header.addWidget(self.edit_button)
        header.addWidget(self.save_button)
        header.addWidget(self.cancel_button)

        layout.addLayout(header)

        # --------------------------------------------------
        # Fields
        # --------------------------------------------------

        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlainText(
            self.project.description or ""
        )

        self.instructions_edit = QPlainTextEdit()
        self.instructions_edit.setPlainText(
            self.project.instructions or ""
        )

        self.homepage_edit = QLineEdit()
        self.homepage_edit.setText(
            self.project.homepage or ""
        )

        self.contact_edit = QLineEdit()
        self.contact_edit.setText(
            self.project.contact or ""
        )

        self.description_edit.setMaximumHeight(140)
        self.instructions_edit.setMaximumHeight(140)

        layout.addWidget(
            self.create_section(
                "Description",
                self.description_edit,
            )
        )

        layout.addWidget(
            self.create_section(
                "Instructions",
                self.instructions_edit,
            )
        )

        layout.addWidget(
            self.create_section(
                "Homepage",
                self.homepage_edit,
            )
        )

        layout.addWidget(
            self.create_section(
                "Contact",
                self.contact_edit,
            )
        )

        layout.addStretch()

        # Start read-only.
        self.set_editing(False)

    def create_section(self, title, widget):
        frame = QFrame()
        frame.setFrameShape(
            QFrame.Shape.StyledPanel
        )

        frame.setStyleSheet("""
            QFrame {
                border: 1px solid palette(mid);
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(frame)

        layout.setContentsMargins(
            14, 10, 14, 10
        )

        layout.setSpacing(6)

        title_label = QLabel(title)

        font = QFont()
        font.setBold(True)

        title_label.setFont(font)

        title_label.setStyleSheet(
            "border: none;"
        )

        layout.addWidget(title_label)

        # Don't remove the widget's text/background styling.
        widget.setStyleSheet("""
            QPlainTextEdit,
            QLineEdit {
                border: none;
                background: transparent;
            }
        """)

        layout.addWidget(widget)

        return frame

    def set_editing(self, editing):
        self.editing = editing
        self.description_edit.setReadOnly(
            not editing
        )
        self.instructions_edit.setReadOnly(
            not editing
        )
        self.homepage_edit.setReadOnly(
            not editing
        )
        self.contact_edit.setReadOnly(
            not editing
        )
        self.edit_button.setVisible(
            not editing
        )
        self.cancel_button.setVisible(
            editing
        )
        self.save_button.setVisible(
            editing
        )

    def toggle_edit(self):
        self.set_editing(True)

    def save(self):
        self.project.description = (
            self.description_edit
            .toPlainText()
            .strip()
        )
        self.project.instructions = (
            self.instructions_edit
            .toPlainText()
            .strip()
        )
        self.project.homepage = (
            self.homepage_edit
            .text()
            .strip()
            or None
        )
        self.project.contact = (
            self.contact_edit
            .text()
            .strip()
            or None
        )
        self.set_editing(False)
        self.saved.emit()

    def cancel(self):
        self.description_edit.setPlainText(
            self.project.description or ""
        )
        self.instructions_edit.setPlainText(
            self.project.instructions or ""
        )
        self.homepage_edit.setText(
            self.project.homepage or ""
        )
        self.contact_edit.setText(
            self.project.contact or ""
        )
        self.set_editing(False)

# ============================================================
# PaginatedTableModel
# ============================================================
from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableView,
    QLabel,
    QVBoxLayout,
)

class PaginatedTableModel(QAbstractTableModel):
    row_count_changed = pyqtSignal(int)
    def __init__(self, data_source, parent=None):
        super().__init__(parent) 

        self.data_source = data_source

        self.data_source.dataReady.connect(
            self._data_ready
        )

        self.data_source.fetchFailed.connect(
            self._fetch_failed
        )

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0

        return self.data_source.rowSize()

    def columnCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0

        return self.data_source.columnSize()

    def data(
        self,
        index,
        role=Qt.ItemDataRole.DisplayRole,
    ):
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            return self.data_source.getStr(
                index.row(),
                index.column(),
            )
        elif role == DATA_ROLE:
            return self.data_source.getData(index.row())

        return None

    def headerData(
        self,
        section,
        orientation,
        role=Qt.ItemDataRole.DisplayRole,
    ):
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Horizontal:
            return self.data_source.getHeader(section)

        return section + 1

    def setPage(self, page):
        self.data_source.setPage(page)

    def setPageSize(self, size):
        self.data_source.setPageSize(size)

    def refresh(self):
        self.beginResetModel()
        self.endResetModel()

    def _data_ready(self):
        # This slot runs in the GUI thread because the model
        # lives in the GUI thread.
        self.refresh()
        self.row_count_changed.emit(
            self.rowCount()
        )

    def _fetch_failed(self, error):
        print("Table fetch failed:", error)


# ============================================================
# PaginatedTableView
# ============================================================
DEFAULT_PAGE_SIZE=25
DELETE_ACTION = int(random.random() * 100) + 1
OPEN_ACTION = DELETE_ACTION + int(random.random() * 100) + 1
VIEW_JSON_ACTION = OPEN_ACTION + int(random.random() * 100) + 1
NONE_ACTION = VIEW_JSON_ACTION + int(random.random() * 100) + 1
BUILD_ACTION = NONE_ACTION + int(random.random() * 100) + 1
EDIT_ACTION = BUILD_ACTION + int(random.random() * 100) + 1
ADD_ACTION = EDIT_ACTION + int(random.random() * 100) + 1
NEW_ACTION = ADD_ACTION + int(random.random() * 100) + 1
DATA_ROLE = int(random.random() * 100) + Qt.ItemDataRole.UserRole + 1
BUILD_SECTION = int(random.random() * 100) + 1
PACKAGE_SECTION = int(random.random() * 100) + BUILD_SECTION + 1

from dataclasses import dataclass

@dataclass(eq=False)
class WorkerThread:
    worker: object
    thread: object

    def __hash__(self):
        return id(self)

class WorkerManager:
    def __init__(self):
        self._threads = set()

    def add(self, worker, thread):
        thrd = WorkerThread(worker, thread)
    
        self._threads.add(thrd)
        def discard():
            self._threads.discard(thrd)

        thread.finished.connect(
            discard
        )

worker_manager = WorkerManager()
add_worker_and_thread = worker_manager.add

def CoprAction(self, data, action, section, finish_job = None):
    Worker = None
    if action == VIEW_JSON_ACTION:
        pretty = json.dumps(
            unmunchify(data[0] if len(data) == 1 else data),
            indent=4,
            sort_keys=True,
        )
        show_text_dialog(
            self,
            "Json",
            pretty,
        )
    elif action == NEW_ACTION:
        if section == BUILD_SECTION:
            Worker = AddBuildWorker
        elif section == PACKAGE_SECTION:
            Worker = AddPackageWorker
        else:
            return
    elif action == ADD_ACTION or action == EDIT_ACTION:
        if section == BUILD_SECTION:
            window = BuildType(self, is_package=False)
            def accept():
                nonlocal self, window
                username = self.client.build_proxy.auth_username()
                projectname = self.project.name
                source_dict = window.fetch_qml_data(username, projectname)
                CoprAction(self, source_dict, NEW_ACTION, BUILD_SECTION, 
                    finish_job=window.close)
            window.buttons.accepted.connect(accept)
            window.buttons.rejected.connect(window.close)
            window.show()
        elif section == PACKAGE_SECTION:
            window = BuildType(self, is_package=True)
            def accept():
                nonlocal self, window
                username = self.client.build_proxy.auth_username()
                projectname = self.project.name
                source_dict = window.fetch_qml_data(username, projectname)
                CoprAction(self, source_dict, NEW_ACTION, PACKAGE_SECTION, 
                    finish_job=window.close)
            window.buttons.accepted.connect(accept)
            window.buttons.rejected.connect(window.close)
            if action == EDIT_ACTION:
                if len(data) > 0:
                    data = data[0]
                    window.fill_package_data(data)
            window.show()
    elif action == BUILD_ACTION:
        if section == PACKAGE_SECTION:
            window = BuildType(self, is_package=False)
            def accept():
                nonlocal self, window
                username = self.client.build_proxy.auth_username()
                projectname = self.project.name
                source_dict = window.fetch_qml_data(username, projectname)
                CoprAction(self, source_dict, NEW_ACTION, BUILD_SECTION, 
                    finish_job=window.close)
            window.buttons.accepted.connect(accept)
            window.buttons.rejected.connect(window.close)
            if len(data) > 0:
                data = data[0]
                window.fill_package_data(data)
            window.show()
        else:
            return
    elif action == DELETE_ACTION:
        if section == PACKAGE_SECTION:
            Worker = DeletePackageWorker
        elif section == BUILD_SECTION:
            Worker = DeleteBuildWorker
        else:
            return
    if None != Worker:
        thread = QThread(self)
        worker = Worker(
            self.client,
            data,
        )
        if finish_job:
            worker.done.connect(
                finish_job
            )
        worker.moveToThread(
            thread
        )
        thread.started.connect(
            worker.run
        )
        worker.failed.connect(
            lambda error: QMessageBox.critical(
                self,
                "Job failed",
                error,
            )
        )
        worker.finished.connect(
            thread.quit
        )
        worker.finished.connect(
            worker.deleteLater
        )
        thread.finished.connect(
            thread.deleteLater
        )
        worker.finished.connect(
            self.view.refresh
        )
        thread.start()
        add_worker_and_thread(worker, thread)

class CoprTableView(QTableView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actions = {}

    def keyPressEvent(self, event):
        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            self.press_event()
        if (event.key() == Qt.Key.Key_F10 and (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ) ) or event.key() == Qt.Key.Key_Menu:
            self.show_context_menu()
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        self.show_context_menu(event.pos())
        event.accept()

    click_row = pyqtSignal(list, int)

    def show_context_menu(self, pos=None):
        menu = QMenu(self)

        action_dict = {}
        for value, key in self.actions.items():
            action = QAction(key, self)
            menu.addAction(action)
            action_dict[id(action)] = value

        pos = self.mapToGlobal(pos if pos else self.rect().center())
        action = menu.exec(pos)

        datamodel = self.model()
        model = self.selectionModel()
        indexes = model.selectedIndexes()
        rows = dict()
        for i in indexes:
            rows[i.row()] = i
        rows = [datamodel.data(i, DATA_ROLE) for i in rows.values()]
        
        self.click_row.emit(rows, action_dict.get(id(action), NONE_ACTION))

class PaginatedTableView(QFrame):
    def __init__(self, data_source, parent=None, menus = {}, action = None):
        super().__init__(parent)

        self.data_source = data_source
        self.page = 0
        self.menus = menus
        self.page_size = DEFAULT_PAGE_SIZE

        self.setup_ui()

        self.data_source.setPageSize(
            DEFAULT_PAGE_SIZE
        )

        self.table.click_row.connect(action or (lambda *a: None))

        self.data_source.fetchStarted.connect(
            self.updatePagination
        )

        self.data_source.dataReady.connect(
            self.updatePagination
        )

        self.loadPage(0, force=True)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.model = PaginatedTableModel(
            self.data_source,
            self,
        )
        self.model.row_count_changed.connect(
            self.updatePagination
        )


        self.table = CoprTableView()
        self.table.actions = self.menus
        self.table.setModel(self.model)

        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        header = self.table.horizontalHeader()

        header.setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )


        header.setResizeContentsPrecision(
            DEFAULT_PAGE_SIZE
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        layout.addWidget(
            self.table,
            1,
        )

        pagination = QHBoxLayout()

        self.previous_button = QPushButton(
            "Previous"
        )

        self.page_label = QLabel()

        self.next_button = QPushButton(
            "Next"
        )

        self.refresh_button = QPushButton(
            "Reload"
        )

        pagination.addStretch()
        pagination.addWidget(
            self.previous_button
        )
        pagination.addWidget(
            self.page_label
        )
        pagination.addWidget(
            self.next_button
        )
        pagination.addWidget(
            self.refresh_button
        )
        pagination.addStretch()
        layout.addLayout(pagination)

        self.previous_button.clicked.connect(
            self.previousPage
        )
        self.next_button.clicked.connect(
            self.nextPage
        )
        self.refresh_button.clicked.connect(
            self.refresh
        )
        self.updatePagination()

    def loadPage(self, page, force=False):
        if page < 0:
            return
        if self.data_source.loading:
            return
        if not force and page == self.page:
            return
        self.page = page
        self.model.setPage(page)
        self.updatePagination()

    def refresh(self):
        return self.loadPage(self.page, True)

    def setPageSize(self, size):
        if size <= 0:
            return
        if size == self.page_size:
            return
        self.page_size = size
        self.data_source.setPageSize(size)
        self.loadPage(
            0,
            force=True,
        )

    def previousPage(self):
        if self.data_source.loading:
            return
        if self.page > 0:
            self.loadPage(
                self.page - 1
            )

    def nextPage(self):
        if self.data_source.loading:
            return
        if self.data_source.rowSize() > 0:
            self.loadPage(
                self.page + 1
            )

    def updatePagination(self, count=0):
        self.page_label.setText(
            f"Page {self.page}"
        )
        self.previous_button.setEnabled(
            self.page > 0
        )
        self.next_button.setEnabled(
            self.data_source.rowSize() > 0 or int(count) > 0
        ) 


# ============================================================
class CoprTableFetchWorker(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, data_fetch, offset, count):
        super().__init__()

        self.data_fetch = data_fetch
        self.offset = offset
        self.count = count

    def run(self):
        try:
            data = self.data_fetch(
                self.offset,
                self.count,
            )

            self.succeeded.emit(data)

        except Exception as error:
            self.failed.emit(str(error))

        finally:
            self.finished.emit()


class CoprTable(QObject):
    dataReady = pyqtSignal()
    fetchStarted = pyqtSignal()
    fetchFailed = pyqtSignal(str)

    def __init__(
        self,
        data_fetch,
        data_process,
        headers,
        parent=None,
    ):
        super().__init__(parent)

        self.data_fetch = data_fetch
        self.data_process = data_process
        self.headers = headers

        self.data = []
        self.page = 0
        self.page_size = 25

        self.loading = False

    # --------------------------------------------------------
    # Basic data access
    # --------------------------------------------------------

    def columnSize(self):
        return len(self.headers)

    def rowSize(self):
        return len(self.data)

    def getHeader(self, column):
        if 0 <= column < len(self.headers):
            return self.headers[column]
        return ""

    def getData(self, row):
        if 0 <= row < len(self.data):
            return self.data[row]
        return None

    def getStr(self, row, column):
        data = self.getData(row)
        if None == data:
            return ""
        if (
            0 <= column < self.columnSize()
        ):
            return self.data_process(
                data,
                column,
            )
        return ""

    # --------------------------------------------------------
    # Pagination
    # --------------------------------------------------------

    def setPage(self, page):
        if page < 0:
            return
        self.page = page
        self.data = []
        self.fetch()

    def setPageSize(self, size):
        if size <= 0:
            return
        self.page_size = size
        self.data = []
        self.fetch()

    # --------------------------------------------------------
    # Background fetching
    # --------------------------------------------------------

    def fetch(self):
        if self.loading:
            return
        self.loading = True
        self.fetchStarted.emit()
        thread = QThread(self)
        worker = CoprTableFetchWorker(
            self.data_fetch,
            self.page * self.page_size,
            self.page_size,
        )
        worker.moveToThread(thread)
        thread.started.connect(
            worker.run
        )
        worker.succeeded.connect(
            self._fetch_succeeded
        )
        worker.failed.connect(
            self._fetch_failed
        )
        worker.finished.connect(
            thread.quit
        )
        worker.finished.connect(
            worker.deleteLater
        )
        thread.finished.connect(
            thread.deleteLater
        )
        thread.finished.connect(
            self._thread_finished
        )
        thread.start()
        add_worker_and_thread(worker, thread)

    def _fetch_succeeded(self, data):
        self.data = list(data)
        self.dataReady.emit()

    def _fetch_failed(self, error):
        self.data = []

        self.fetchFailed.emit(error)

    def _thread_finished(self):
        self.loading = False

        self.thread = None
        self.worker = None


# ============================================================
# ProjectBuildsFrame
# ============================================================
class ProjectBuildsFrame(QFrame):
    def __init__(self, parent):
        super().__init__(parent)

        self.client = parent.client
        self.project = parent.project
        self._skip_setup = False

    def copr_action(self, rows, act):
        return CoprAction(self, rows, act, BUILD_SECTION)

    def setup_ui(self):
        if self._skip_setup:
            return
        else:
            self._skip_setup = True
        layout = QVBoxLayout(self)

        def data_fetch(offset, count):
            name = self.project.name
            owner = self.client.base_proxy.auth_username()
            return self.client.build_proxy.get_list(owner, name, 
                pagination={'limit':count,'offset':offset})

        def data_process(data, column):
            src = data.get('source_package', None) or {}
            if column == 0:
                return data.get('id', None) or ''
            elif column == 1:
                return src.get('name', None) or ''
            elif column == 2:
                return src.get('version', None) or ''
            elif column == 3:
                return time_ago(data.get('submitted_on', None) or '')
            elif column == 4:
                return format_duration(
                    data.get('ended_on', None) or '', 
                    data.get('submitted_on', None) or '')
            elif column == 5:
                return data.get('state', None) or ''
            return ""

        self.view = PaginatedTableView(CoprTable(
            data_fetch, data_process, ["ID", "Name", "Version", "Submitted", "BuildTime", "Status"]
        ), menus={
            ADD_ACTION: "Add build",
            DELETE_ACTION: "Delete",
            VIEW_JSON_ACTION: "View Json"
        }, action = self.copr_action)
        layout.addWidget(self.view, 1)

# ============================================================
# Project options
# ============================================================

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QGridLayout,
    QCheckBox,
    QSpinBox,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QLabel,
    QPushButton,
)


class ProjectOptionsWidget(QWidget):
    saved = pyqtSignal(dict)
    editing = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)

        self.project = parent.project
        self._editing = False

        layout = QGridLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(4)

        # Make the two right-hand columns expandable.
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 0)

        # ---------------------------------------------------------
        # Boolean options
        # ---------------------------------------------------------

        self.unlisted_on_hp = QCheckBox(
            "Unlisted on homepage"
        )
        self.enable_net = QCheckBox(
            "Enable network"
        )
        self.auto_prune = QCheckBox(
            "Auto prune"
        )
        self.devel_mode = QCheckBox(
            "Development mode"
        )
        self.module_hotfixes = QCheckBox(
            "Module hotfixes"
        )
        self.follow_fedora_branching = QCheckBox(
            "Follow Fedora branching"
        )
        self.fedora_review = QCheckBox(
            "Fedora review"
        )
        self.appstream = QCheckBox(
            "AppStream"
        )

        checks = [
            self.unlisted_on_hp,
            self.enable_net,
            self.auto_prune,
            self.devel_mode,
            self.module_hotfixes,
            self.follow_fedora_branching,
            self.fedora_review,
            self.appstream,
        ]

        for i, checkbox in enumerate(checks):
            row = i // 2
            column = i % 2
            layout.addWidget(
                checkbox,
                row,
                column,
            )

        # ---------------------------------------------------------
        # Edit / Save
        # ---------------------------------------------------------

        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(
            self._toggle_edit
        )
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(
            self._toggle_cancel
        )
        self.cancel_button.hide()

        # Third column, alongside the checkbox area.
        layout.addWidget(
            self.edit_button,
            0,
            2,
            5,
            1,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
        )        
        # Third column, alongside the checkbox area.
        layout.addWidget(
            self.cancel_button,
            1,
            2,
            5,
            1,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
        )
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )

        row = (len(checks) + 1) // 2

        # ---------------------------------------------------------
        # Delete after days
        # ---------------------------------------------------------

        layout.addWidget(
            QLabel("Delete after:"),
            row,
            0,
        )

        self.delete_after_days = QSpinBox()
        self.delete_after_days.setRange(
            0,
            36500,
        )
        self.delete_after_days.setSpecialValueText(
            "Disabled"
        )
        self.delete_after_days.setSuffix(
            " days"
        )

        # Columns 1 + 2
        layout.addWidget(
            self.delete_after_days,
            row,
            1,
            1,
            2,
        )

        row += 1

        # ---------------------------------------------------------
        # Bootstrap
        # ---------------------------------------------------------

        layout.addWidget(
            QLabel("Bootstrap:"),
            row,
            0,
        )

        self.bootstrap = QComboBox()
        self.bootstrap.addItems([
            "default",
            "on",
            "off",
            "image",
        ])

        layout.addWidget(
            self.bootstrap,
            row,
            1,
            1,
            2,
        )

        row += 1

        # ---------------------------------------------------------
        # Bootstrap image
        # ---------------------------------------------------------

        layout.addWidget(
            QLabel("Bootstrap image:"),
            row,
            0,
        )

        self.bootstrap_image = QLineEdit()
        self.bootstrap_image.setPlaceholderText(
            "Container image"
        )

        layout.addWidget(
            self.bootstrap_image,
            row,
            1,
            1,
            2,
        )

        row += 1

        # ---------------------------------------------------------
        # Isolation
        # ---------------------------------------------------------

        layout.addWidget(
            QLabel("Isolation:"),
            row,
            0,
        )

        self.isolation = QComboBox()
        self.isolation.addItems([
            "default",
            "simple",
            "nspawn",
        ])

        layout.addWidget(
            self.isolation,
            row,
            1,
            1,
            2,
        )

        row += 1

        # ---------------------------------------------------------
        # Runtime dependencies
        # ---------------------------------------------------------

        layout.addWidget(
            QLabel("Runtime dependencies:"),
            row,
            0,
            1,
            3,
        )

        row += 1

        self.runtime_dependencies = QPlainTextEdit()
        self.runtime_dependencies.setPlaceholderText(
            "One repository URL per line"
        )

        # All 3 columns
        layout.addWidget(
            self.runtime_dependencies,
            row,
            0,
            1,
            3,
        )

        layout.setRowStretch(
            row,
            1,
        )

        row += 1

        # ---------------------------------------------------------
        # Packit forge projects
        # ---------------------------------------------------------

        layout.addWidget(
            QLabel("Packit forge projects:"),
            row,
            0,
            1,
            3,
        )

        row += 1

        self.packit_forge_projects_allowed = QPlainTextEdit()
        self.packit_forge_projects_allowed.setPlaceholderText(
            "One project per line"
        )

        # All 3 columns
        layout.addWidget(
            self.packit_forge_projects_allowed,
            row,
            0,
            1,
            3,
        )

        layout.setRowStretch(
            row,
            1,
        )

        # ---------------------------------------------------------
        # Initial state
        # ---------------------------------------------------------

        self.set_options(self.project)
        self._set_editing(False)

    # -------------------------------------------------------------
    # Options
    # -------------------------------------------------------------

    def get_options(self):
        return {
            "unlisted_on_hp":
                self.unlisted_on_hp.isChecked(),

            "enable_net":
                self.enable_net.isChecked(),

            "auto_prune":
                self.auto_prune.isChecked(),

            "devel_mode":
                self.devel_mode.isChecked(),

            "delete_after_days":
                self.delete_after_days.value(),

            "module_hotfixes":
                self.module_hotfixes.isChecked(),

            "bootstrap":
                self.bootstrap.currentText(),

            "bootstrap_image":
                self.bootstrap_image.text(),

            "isolation":
                self.isolation.currentText(),

            "follow_fedora_branching":
                self.follow_fedora_branching.isChecked(),

            "fedora_review":
                self.fedora_review.isChecked(),

            "appstream":
                self.appstream.isChecked(),

            "runtime_dependencies":
                self._lines(
                    self.runtime_dependencies
                ),

            "packit_forge_projects_allowed":
                self._lines(
                    self.packit_forge_projects_allowed
                ),
        }

    def set_options(self, options):
        for name in (
            "unlisted_on_hp",
            "enable_net",
            "auto_prune",
            "devel_mode",
            "module_hotfixes",
            "follow_fedora_branching",
            "fedora_review",
            "appstream",
        ):
            getattr(self, name).setChecked(
                options.get(name, False)
            )

        self.delete_after_days.setValue(
            options.get(
                "delete_after_days",
                0,
            )
        )

        self._set_combo(
            self.bootstrap,
            options.get(
                "bootstrap",
                "default",
            ),
        )

        self.bootstrap_image.setText(
            options.get(
                "bootstrap_image",
                "",
            )
        )

        self._set_combo(
            self.isolation,
            options.get(
                "isolation",
                "default",
            ),
        )

        self._set_lines(
            self.runtime_dependencies,
            options.get(
                "runtime_dependencies",
                [],
            ),
        )

        self._set_lines(
            self.packit_forge_projects_allowed,
            options.get(
                "packit_forge_projects_allowed",
                [],
            ),
        )

    # -------------------------------------------------------------
    # Editing
    # -------------------------------------------------------------

    def _toggle_edit(self):
        if self._editing:
            self._save()
            self._backup_options = None
        else:
            self._set_editing(True)
            self._backup_options = self.get_options()
            self.editing.emit()

    def _toggle_cancel(self):
        self._set_editing(False)
        self.set_options(self._backup_options)
        self.cancelled.emit()

    def _save(self):
        options = self.get_options()

        self._set_editing(False)
        self.saved.emit(options)

    def _set_editing(self, value):
        self._editing = value
        self.cancel_button.setHidden(not value)
        widgets = (
            self.unlisted_on_hp,
            self.enable_net,
            self.auto_prune,
            self.devel_mode,
            self.module_hotfixes,
            self.follow_fedora_branching,
            self.fedora_review,
            self.appstream,
            self.delete_after_days,
            self.bootstrap,
            self.bootstrap_image,
            self.isolation,
            self.runtime_dependencies,
            self.packit_forge_projects_allowed,
        )

        for widget in widgets:
            widget.setEnabled(value)

        self.edit_button.setText(
            "Save" if value else "Edit"
        )

    # -------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------

    @staticmethod
    def _lines(widget):
        return [
            line.strip()
            for line in widget.toPlainText().splitlines()
            if line.strip()
        ]

    @staticmethod
    def _set_lines(widget, values):
        widget.setPlainText(
            "\n".join(values or [])
        )

    @staticmethod
    def _set_combo(combo, value):
        index = combo.findText(value)

        if index >= 0:
            combo.setCurrentIndex(index)

# ============================================================
# ProjectWindow
# ============================================================
from PyQt6.QtWidgets import (
    QMainWindow,
    QTabWidget,
)

class ProjectWindow(QMainWindow):

    def __init__(self, project, parent):
        super().__init__(parent)
        
        self.client = parent.client
        self.project = project

        self.setWindowTitle(
            f"Project — {project.full_name}"
        )

        self.resize(900, 600)

        self.setup_ui()
    
    def tab_changed(self, index):
        if index == 1:
            self.packages.setup_ui()
        elif index == 2:
            self.builds.setup_ui()

    def setup_ui(self):
        tabs = QTabWidget()
        tabs.currentChanged.connect(self.tab_changed)
        self.overview = ProjectOverviewFrame(self)
        self.packages = ProjectPackagesFrame(self)
        self.builds = ProjectBuildsFrame(self)
        tabs.addTab(
            self.overview,
            "Overview",
        )
        tabs.addTab(
            self.packages,
            "Packages",
        )
        tabs.addTab(
            self.builds,
            "Builds",
        )
        self.project_options = ProjectOptionsWidget(self)
        tabs.addTab(
            self.project_options,
            "Options"
        )
        self.chroot_widgets = ChrootWidget(self)
        tabs.addTab(
            self.chroot_widgets,
            "Chroots"
        )	
        def save_project_options(opts):
            nonlocal self
            self.project.update(opts)
            worker = UpdateProjectOptionsWorker(self.client, self.project, opts)
            thread = QThread(self)

            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.finished.connect(
                thread.quit
            )
            worker.finished.connect(
                worker.deleteLater
            )
            thread.finished.connect(
                thread.deleteLater
            )
            worker.failed.connect(
                lambda error: QMessageBox.critical(
                    self,
                    "Update project failed",
                    error,
                )
            )
            thread.start()
            add_worker_and_thread(worker, thread)
        def save_project_chroots():
            nonlocal self, save_project_options
            save_project_options({
				"chroots": self.chroot_widgets.chroots()
			})
        self.chroot_widgets.changed.connect(save_project_chroots)   
        self.project_options.saved.connect(save_project_options)
        self.setCentralWidget(tabs)

# ============================================================
# Create build and package
# ============================================================
def NewBuild(client, source):
    t = source["type"]
    j = source["data"]
    o = source["owner"]
    p = source["project"]
    s = source.get("buildopts", None)
    b = client.build_proxy
    if t == "custom":
        t = b.create_from_custom
        j = {
            "script": j.get("script", None) or '',
            "script_chroot": j.get("chroot", None) or '',
            "script_builddeps": j.get("builddeps", None) or '',
            "script_resultdir": j.get("resultdir", None) or '',
            "script_repos": j.get("repos", None) or ''
        }
    elif t == "pypi":
        t = b.create_from_pypi
    elif t == "rubygems":
        t = b.create_from_rubygems
    elif t == "scm":
        t = b.create_from_scm
    elif t == "distgit":
        t = b.create_from_distgit
    elif t == "url":
        t = b.create_from_url
    elif t == "urls":
        t = b.create_from_urls
    elif t == "file":
        t = b.create_from_file
    elif t == "rpm_upload":
        t = b.create_from_rpm_upload
    else:
        t = None
    if t:
        return t(o, p, buildopts=s, **j)
    else:
        return None

def NewPackage(client, source):
    b = client.package_proxy
    owner = source["owner"]
    project = source["project"] 
    name = source["name"] 
    type = source["type"] 
    data = source["data"]
    if not name:
        raise exceptions.CoprRequestException("Name must not be empty")
    try:
        return b.add(
            owner, project, name, type, data
        )
    except exceptions.CoprRequestException as jf:
        if jf.result.__response__.status_code == 409:
            return b.edit(
                owner, project, name, type, data
            )
        else:
            raise jf

# ============================================================
# Build type
# ============================================================
import os

from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QComboBox,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtQuickWidgets import QQuickWidget
from PyQt6.QtCore import QMetaObject, Q_RETURN_ARG, QVariant, QUrl, Q_ARG


class BuildType(QMainWindow):
    def get_build_options(self):
        window = BuildOptions(self.client, self)
        def accepted():
            nonlocal window, self
            self.build_options = window.values()
        if self.build_options is not None:
            window.set_values(self.build_options)
        window.accepted.connect(
            accepted
        )
        keys = list(self.project.chroot_repos.keys())
        keys.sort()
        window.chroots.set_chroots(keys)
        window.show()

    def __init__(self, parent, *args, is_package=False, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.widgets = {}
        
        self.combo = QComboBox()
        self.stack = QStackedWidget()

        palette = self.palette()

        window_color = palette.color(
            QPalette.ColorRole.Window
        )

        text_color = palette.color(
            QPalette.ColorRole.WindowText
        )
        self.qml_ids = {}
        qml_current_id = 0
        
        directory = Path(__file__).resolve().parent / "copr_gui_source_types"

        for filename in os.listdir(directory):
            if not filename.endswith(".qml"):
                continue

            path = os.path.abspath(
                os.path.join(directory, filename)
            )
            qml = QQuickWidget()
            qml.setResizeMode(
                QQuickWidget.ResizeMode.SizeRootObjectToView
            )

            context = qml.rootContext()
            context.setContextProperty(
                "windowColor",
                window_color,
            )
            context.setContextProperty(
                "textColor",
                text_color,
            )
            qml.setSource(QUrl.fromLocalFile(path))

            identifier = qml.rootObject().property("identifier")
            name = qml.rootObject().property("name") or identifier
            self.qml_ids[identifier] = qml_current_id
            qml_current_id = qml_current_id + 1

            self.combo.addItem(name)
            self.stack.addWidget(qml)

        self.chroots_label = QLabel("Build type")
        self.chroots_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        font = QFont()
        font.setBold(True)
        self.chroots_label.setFont(font)

        self.central = QWidget()
        self.layout = QVBoxLayout(self.central)

        self.build_options = None
        self.is_package = is_package
        if is_package:
            self.name_label = QLabel("Name")
            self.layout.addWidget(self.name_label)
            self.name = QLineEdit()
            self.layout.addWidget(self.name)
        else:
            self.name = None
            self.client = parent.client
            self.project = parent.project
            self.build_options_button = QPushButton("Build options")
            self.build_options_button.clicked.connect(self.get_build_options)
            self.layout.addWidget(self.build_options_button)


        self.layout.addWidget(self.chroots_label)
        self.layout.addWidget(self.combo)
        self.layout.addWidget(self.stack, 1)

        self.setCentralWidget(self.central)

        self.combo.currentIndexChanged.connect(
            self.stack.setCurrentIndex
        )

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.layout.addWidget(self.buttons)

        self.resize(800, 600)

    def fill_package_data(self, data):
        if self.name is not None:
            self.name.setText(data.name)
        index = self.qml_ids[data.source_type]
        self.combo.setCurrentIndex(index)

        current_widget = self.stack.currentWidget()
        if not isinstance(current_widget, QQuickWidget):
            return
            
        qml_root = current_widget.rootObject()
        if qml_root:
            success = QMetaObject.invokeMethod(
                qml_root, 
                "setDict", 
                Q_ARG(QVariant, data.source_dict)
            )
            return not not success

    def fetch_qml_data(self, owner="", project=""):
        current_widget = self.stack.currentWidget()
        if not isinstance(current_widget, QQuickWidget):
            return
        qml_root = current_widget.rootObject()
        if qml_root:
            data_dict = QMetaObject.invokeMethod(
                qml_root, 
                "getDict", 
                Q_RETURN_ARG(QVariant)
            )
            
            if data_dict is not None:
                data_dict = {
                    "data": data_dict.toVariant(),
                    "type": qml_root.property("identifier")
                }
                if self.name is not None:
                    data_dict["name"] = self.name.text()
                data_dict["owner"] = owner
                data_dict["project"] = project
                if self.build_options is not None: 
                    data_dict["buildopts"] = self.build_options
                return data_dict
            else:
                pass
        return None

# ============================================================
# Build options
# ============================================================
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QCheckBox,
    QComboBox,
    QVBoxLayout,
)


class BuildOptions(QDialog):
    def __init__(self, client, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Create Build")
        self.resize(550, 300)
        self.client = client

        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        # timeout
        self.timeout = QSpinBox()
        self.timeout.setRange(0, 2**31 - 1)
        self.timeout.setSpecialValueText("Default")
        self.timeout.setSuffix(" s")

        form.addRow("Timeout:", self.timeout)

        # chroots
        self.chroots = ChrootEditor()

        FetchChroot(self.client, self.chroots)

        form.addRow("Chroots:", self.chroots)

        # background
        self.background = QCheckBox(
            "Mark the build as a background job"
        )

        form.addRow("Background:", self.background)

        # bootstrap
        self.bootstrap = QComboBox()
        self.bootstrap.addItems([
            "untouched",
            "default",
            "image",
            "on",
            "off",
        ])

        form.addRow("Bootstrap:", self.bootstrap)

        # with_build_id
        self.with_build_id = QSpinBox()
        self.with_build_id.setRange(0, 2**31 - 1)
        self.with_build_id.setSpecialValueText("None")

        form.addRow("With build ID:", self.with_build_id)

        # after_build_id
        self.after_build_id = QSpinBox()
        self.after_build_id.setRange(0, 2**31 - 1)
        self.after_build_id.setSpecialValueText("None")

        form.addRow("After build ID:", self.after_build_id)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

    def set_values(self, values):
        self.timeout.setValue(int(values["timeout"]))
        self.chroots.set_chroots(values["chroots"])
        self.background.setChecked(values["background"])
        self.bootstrap.setCurrentText(values["bootstrap"])
        self.with_build_id.setValue(values["with_build_id"])
        self.after_build_id.setValue(values["after_build_id"])

    def values(self):
        chroots = self.chroots.chroots()

        return {
            "timeout": self.timeout.value(),
            "chroots": chroots,
            "background": self.background.isChecked(),
            "bootstrap": self.bootstrap.currentText(),
            "with_build_id": (
                None
                if self.with_build_id.value() == 0
                else self.with_build_id.value()
            ),
            "after_build_id": (
                None
                if self.after_build_id.value() == 0
                else self.after_build_id.value()
            ),
        }

# ============================================================
# Chroot options
# ============================================================
import json

from PyQt6.QtCore import (
    QObject,
    QThread,
    Qt,
    pyqtSignal,
    pyqtSlot,
)

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListWidget,
    QMenu,
    QMessageBox,
)


# ============================================================
# Generic worker
# ============================================================

class Worker(QObject):
    """
    Execute a function in a QThread.

    The function and its arguments are supplied when the worker
    is created.
    """

    finished = pyqtSignal(object)
    error = pyqtSignal(Exception)

    def __init__(self, function, *args, **kwargs):
        super().__init__()

        self.function = function
        self.args = args
        self.kwargs = kwargs

    @pyqtSlot()
    def run(self):
        try:
            result = self.function(
                *self.args,
                **self.kwargs,
            )
        except Exception as exc:
            self.error.emit(exc)
        else:
            self.finished.emit(result)


# ============================================================
# Chroot widget
# ============================================================

class ChrootWidget(QWidget):

    refreshed = pyqtSignal()
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.json_dict = {}

        self.client = parent.client
        self.project = parent.project

        # Keep references to running threads/workers.
        #
        # This is important because otherwise Python could
        # garbage-collect them while they are still running.
        self._workers = []

        # ----------------------------------------------------
        # List
        # ----------------------------------------------------

        self.list = QListWidget()

        self.list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self.list)

        # ----------------------------------------------------
        # Signals
        # ----------------------------------------------------

        self.list.itemDoubleClicked.connect(
            lambda _: self.edit()
        )

        self.list.customContextMenuRequested.connect(
            self.context_menu
        )

        self.list.currentItemChanged.connect(
            lambda *_: self.update_buttons()
        )

        # ----------------------------------------------------
        # Initial data
        # ----------------------------------------------------

        self.set_chroots(
            self.project.chroot_repos.keys()
        )

    # ========================================================
    # List handling
    # ========================================================

    def set_chroots(self, chroots):
        self.list.clear()

        chroots = list(chroots)
        chroots.sort()

        self.list.addItems(chroots)

        self.update_buttons()

    def chroots(self):
        return [
            self.list.item(i).text()
            for i in range(self.list.count())
        ]

    def get_current_name(self):
        item = self.list.currentItem()

        if item is None:
            return ""

        return item.text()

    def update_buttons(self):
        """
        Update buttons/actions depending on selection.

        Implement your actual button handling here if needed.
        """
        pass

    # ========================================================
    # Generic asynchronous operation
    # ========================================================

    def run_async(
        self,
        function,
        *args,
        finished=None,
        error=None,
        **kwargs,
    ):
        """
        Run `function(*args, **kwargs)` in a worker thread.

        `finished(result)` and `error(exception)` are executed
        in the GUI thread.
        """

        thread = QThread()
        worker = Worker(
            function,
            *args,
            **kwargs,
        )

        worker.moveToThread(thread)

        # Start worker when the thread starts.
        thread.started.connect(
            worker.run
        )

        # Result callback.
        if finished is not None:
            worker.finished.connect(
                finished
            )

        # Error callback.
        if error is not None:
            worker.error.connect(
                error
            )

        # Stop thread when operation finishes.
        worker.finished.connect(
            thread.quit
        )

        worker.error.connect(
            thread.quit
        )

        # Delete worker after it finishes.
        worker.finished.connect(
            worker.deleteLater
        )

        worker.error.connect(
            worker.deleteLater
        )

        # Delete QThread after it stops.
        thread.finished.connect(
            thread.deleteLater
        )

        # Keep references alive.
        self._workers.append(
            (thread, worker)
        )

        # Remove references after the thread finishes.
        def cleanup():
            self._workers[:] = [
                pair
                for pair in self._workers
                if pair[0] is not thread
            ]

        thread.finished.connect(
            cleanup
        )

        thread.start()

    # ========================================================
    # Get JSON
    # ========================================================

    def get_current_json_async(self, callback):
        """
        Get the current chroot JSON asynchronously.

        If it is already cached, callback() is called directly.
        Otherwise the API request runs in a worker thread.
        """

        name = self.get_current_name()

        if not name:
            return

        # ----------------------------------------------------
        # Cache
        # ----------------------------------------------------

        cached = self.json_dict.get(name)

        if cached is not None:
            callback(cached)
            return

        # ----------------------------------------------------
        # Expensive operation
        # ----------------------------------------------------
        self.run_async(
            self.client.project_chroot_proxy.get,

            self.client.base_proxy.auth_username(),
            self.project.name,
            name,

            finished=lambda data: (
                self._json_loaded(
                    name,
                    data,
                    callback,
                )
            ),

            error=self._operation_error,
        )

    def _json_loaded(
        self,
        name,
        data,
        callback,
    ):
        """
        Called in the GUI thread after proxy.get() finishes.
        """
        self.json_dict[name] = data

        callback(data)

    # ========================================================
    # View JSON
    # ========================================================

    def view_json_action(self):
        """
        Start asynchronous JSON retrieval.

        The function returns immediately if the data is not
        cached.
        """

        self.get_current_json_async(
            self._show_json
        )

    def _show_json(self, data):
        """
        Called after get_current_json_async() completes.
        """

        pretty = json.dumps(
            data,
            indent=4,
            sort_keys=True,
            default=lambda o: f"<<non-serializable: {type(o).__qualname__}>>"
        )

        show_text_dialog(
            self,
            "Json",
            pretty,
        )

    # ========================================================
    # Edit
    # ========================================================

    def edit(self):
        """
        Start loading the current chroot configuration.

        We don't wait here.

        Once get() finishes, _open_editor() is called.
        """

        name = self.get_current_name()

        if not name:
            return

        # Optionally prevent another operation while loading.
        self.list.setEnabled(False)

        self.get_current_json_async(
            lambda data: (
                self._open_editor(
                    name,
                    data,
                )
            )
        )

    def _open_editor(self, name, data):
        """
        Called in the GUI thread after get() finishes.
        """

        self.list.setEnabled(True)

        window = ChrootConfig(self)

        window.set_config(data)

        # ----------------------------------------------------
        # Editor changed
        # ----------------------------------------------------

        def changed():
            config = window.get_config()

            # Update local cache.
            self.json_dict[name] = config

            # Disable list while saving.
            self.list.setEnabled(False)

            # ------------------------------------------------
            # Expensive edit operation
            # ------------------------------------------------

            self.run_async(
                self.client.project_chroot_proxy.edit,

                self.client.base_proxy.auth_username(),
                self.project.name,
                name,

                finished=self._edit_finished,

                error=self._operation_error,
                **config
            )
            window.close()

        window.changed.connect(
            changed
        )

        window.show()

    def _edit_finished(self, result):
        """
        Called in the GUI thread after edit() finishes.
        """

        self.list.setEnabled(True)

        self.changed.emit()

    # ========================================================
    # Error handling
    # ========================================================

    def _operation_error(self, exc):
        """
        Called in the GUI thread when a worker raises an
        exception.
        """

        self.list.setEnabled(True)

        QMessageBox.critical(
            self,
            "Operation failed",
            str(exc),
        )

    # ========================================================
    # Add
    # ========================================================

    def add(self):
        edit_chroots_func(self)

    # ========================================================
    # Context menu
    # ========================================================

    def context_menu(self, position):
        menu = QMenu(self)

        edit_action = menu.addAction(
            "Edit"
        )

        view_json_action = menu.addAction(
            "View Json"
        )

        menu.addSeparator()

        add_action = menu.addAction(
            "Pick"
        )

        # Find item under mouse.
        item = self.list.itemAt(position)

        edit_action.setEnabled(
            item is not None
        )

        view_json_action.setEnabled(
            item is not None
        )

        # Show menu.
        action = menu.exec(
            self.list.viewport().mapToGlobal(
                position
            )
        )

        # ----------------------------------------------------
        # Pick
        # ----------------------------------------------------

        if action == add_action:
            self.add()

        # ----------------------------------------------------
        # View JSON
        # ----------------------------------------------------

        elif action == view_json_action:

            self.list.setCurrentItem(
                item
            )

            self.view_json_action()

        # ----------------------------------------------------
        # Edit
        # ----------------------------------------------------

        elif action == edit_action:

            self.list.setCurrentItem(
                item
            )

            self.edit()

# ============================================================
# Project Chroot 
# ============================================================
import sys

from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class ListEditor(QWidget):
    """Simple editable list widget with Add/Remove/Clear controls."""

    def __init__(self, title="", placeholder="", parent=None):
        super().__init__(parent)

        self.placeholder = placeholder

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection
        )

        self.add_button = QPushButton("Add")
        self.remove_button = QPushButton("Remove")
        self.clear_button = QPushButton("Clear")

        self.add_button.clicked.connect(self.add_item)
        self.remove_button.clicked.connect(self.remove_items)
        self.clear_button.clicked.connect(self.clear)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if title:
            label = QLabel(title)
            label.setStyleSheet("font-weight: bold;")
            layout.addWidget(label)

        layout.addWidget(self.list_widget)
        layout.addLayout(button_layout)

    def add_item(self):
        value, ok = QInputDialog.getText(
            self,
            "Add item",
            self.placeholder or "Value:",
        )

        if ok and value.strip():
            self.list_widget.addItem(value.strip())

    def remove_items(self):
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(
                self.list_widget.row(item)
            )

    def clear(self):
        self.list_widget.clear()

    def values(self):
        return [
            self.list_widget.item(i).text()
            for i in range(self.list_widget.count())
        ]

    def set_values(self, values):
        self.list_widget.clear()
        self.list_widget.addItems(values)


class ChrootConfigWidget(QWidget):
    """UI for chroot configuration."""
    changed = pyqtSignal()

    BOOTSTRAP_VALUES = [
        "on",
        "off",
        "image",
        "default",
        "untouched",
    ]

    ISOLATION_VALUES = [
        "default",
        "simple",
        "nspawn",
    ]

    RESET_FIELDS = [
        "additional_packages",
        "additional_repos",
        "with_opts",
        "without_opts",
        "bootstrap",
        "bootstrap_image",
        "isolation",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self._build_ui()
        self._connect_signals()
        self._old_config = None

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # ---------------------------------------------------------
        # Additional packages
        # ---------------------------------------------------------
        packages_group = QGroupBox("Additional packages")
        packages_layout = QVBoxLayout(packages_group)

        self.additional_packages = ListEditor(
            placeholder="Package name, e.g. gcc",
        )

        packages_layout.addWidget(
            self.additional_packages
        )

        # ---------------------------------------------------------
        # Additional repositories
        # ---------------------------------------------------------
        repos_group = QGroupBox("Additional repositories")
        repos_layout = QVBoxLayout(repos_group)

        self.additional_repos = ListEditor(
            placeholder="Repository URL or definition",
        )

        repos_layout.addWidget(
            self.additional_repos
        )

        # ---------------------------------------------------------
        # Mock options
        # ---------------------------------------------------------
        options_group = QGroupBox("Mock options")
        options_layout = QHBoxLayout(options_group)

        self.with_opts = ListEditor(
            title="--with",
            placeholder="Option, e.g. network",
        )

        self.without_opts = ListEditor(
            title="--without",
            placeholder="Option, e.g. docs",
        )

        options_layout.addWidget(self.with_opts)
        options_layout.addWidget(self.without_opts)

        # ---------------------------------------------------------
        # Chroot configuration
        # ---------------------------------------------------------
        config_group = QGroupBox("Chroot configuration")
        form = QFormLayout(config_group)

        self.bootstrap = QComboBox()
        self.bootstrap.addItems(
            self.BOOTSTRAP_VALUES
        )

        # bootstrap_image is just a QLineEdit.
        self.bootstrap_image = QLineEdit()
        self.bootstrap_image.setPlaceholderText(
            "bootstrap image"
        )

        self.isolation = QComboBox()
        self.isolation.addItems(
            self.ISOLATION_VALUES
        )

        form.addRow(
            "Bootstrap:",
            self.bootstrap,
        )

        form.addRow(
            "Bootstrap image:",
            self.bootstrap_image,
        )

        form.addRow(
            "Isolation:",
            self.isolation,
        )

        # ---------------------------------------------------------
        # Reset fields - two columns
        # ---------------------------------------------------------
        reset_group = QGroupBox("Reset fields")
        reset_layout = QGridLayout(reset_group)

        self.reset_checks = {}

        for index, field in enumerate(
            self.RESET_FIELDS
        ):
            checkbox = QCheckBox(field)

            self.reset_checks[field] = checkbox

            row = index // 2
            column = index % 2

            reset_layout.addWidget(
                checkbox,
                row,
                column,
            )

        reset_layout.setColumnStretch(0, 1)
        reset_layout.setColumnStretch(1, 1)

        # ---------------------------------------------------------
        # Buttons
        # ---------------------------------------------------------
        buttons_layout = QHBoxLayout()

        self.reset_button = QPushButton(
            "Reset form"
        )

        self.apply_button = QPushButton(
            "Apply"
        )

        self.apply_button.setDefault(True)

        buttons_layout.addStretch()
        buttons_layout.addWidget(
            self.reset_button
        )
        buttons_layout.addWidget(
            self.apply_button
        )

        # ---------------------------------------------------------
        # Assemble
        # ---------------------------------------------------------
        main_layout.addWidget(
            packages_group
        )

        main_layout.addWidget(
            repos_group
        )

        main_layout.addWidget(
            options_group
        )

        main_layout.addWidget(
            config_group
        )

        main_layout.addWidget(
            reset_group
        )

        main_layout.addLayout(
            buttons_layout
        )

    def _connect_signals(self):
        self.reset_button.clicked.connect(
            self.reset_form
        )

        self.apply_button.clicked.connect(
            self.apply
        )

    def get_config(self):
        """Return the current UI state as a dictionary."""

        reset_fields = [
            field
            for field, checkbox
            in self.reset_checks.items()
            if checkbox.isChecked()
        ]

        bootstrap_image = (
            self.bootstrap_image.text().strip()
        )

        return {
            "additional_packages":
                self.additional_packages.values(),

            "additional_repos":
                self.additional_repos.values(),

            "with_opts":
                self.with_opts.values(),

            "without_opts":
                self.without_opts.values(),

            "bootstrap":
                self.bootstrap.currentText(),

            "bootstrap_image":
                bootstrap_image or None,

            "isolation":
                self.isolation.currentText(),

            "reset_fields":
                reset_fields,
        }

    def set_config(self, config):
        """Populate the UI from a configuration dictionary."""
        self._old_config = dict(config)

        self.additional_packages.set_values(
            config.get(
                "additional_packages",
                [],
            )
        )

        self.additional_repos.set_values(
            config.get(
                "additional_repos",
                [],
            )
        )

        self.with_opts.set_values(
            config.get(
                "with_opts",
                [],
            )
        )

        self.without_opts.set_values(
            config.get(
                "without_opts",
                [],
            )
        )

        bootstrap = config.get(
            "bootstrap",
            "default",
        )

        if bootstrap in self.BOOTSTRAP_VALUES:
            self.bootstrap.setCurrentText(
                bootstrap
            )

        self.bootstrap_image.setText(
            config.get(
                "bootstrap_image",
                "",
            ) or ""
        )

        isolation = config.get(
            "isolation",
            "default",
        )

        if isolation in self.ISOLATION_VALUES:
            self.isolation.setCurrentText(
                isolation
            )

        reset_fields = set(
            config.get(
                "reset_fields",
                [],
            )
        )

        for field, checkbox in (
            self.reset_checks.items()
        ):
            checkbox.setChecked(
                field in reset_fields
            )

    def reset_form(self):
        """Reset everything to its default state."""

        self.additional_packages.clear()
        self.additional_repos.clear()
        self.with_opts.clear()
        self.without_opts.clear()

        self.bootstrap.setCurrentText(
            "default"
        )

        self.bootstrap_image.clear()

        self.isolation.setCurrentText(
            "default"
        )

        for checkbox in (
            self.reset_checks.values()
        ):
            checkbox.setChecked(False)
        if type(self._old_config) == dict:
            self.set_config(self._old_config)

    def apply(self):
        """Handle the Apply button."""
        self.changed.emit()


class ChrootConfig(QMainWindow):
    def __getattr__(self, name):
        return getattr(self.config_widget, name)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(
            "Chroot Configuration"
        )

        self.resize(850, 800)

        self.config_widget = config_widget = ChrootConfigWidget()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(config_widget)

        self.setCentralWidget(scroll)

# ============================================================
# Main
# ============================================================
def main():
    app = QApplication(sys.argv)

    window = CoprWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
