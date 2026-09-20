#!/bin/python3
import sys
import random
import tempfile
import string

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices

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
        view_json = QAction("View JSON", self)

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
            VIEW_JSON_ACTION: "View JSON"
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
VIEW_BUILD_ACTION = NEW_ACTION + int(random.random() * 100) + 1
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
    elif action == VIEW_BUILD_ACTION:
        if len(data) > 0:
            CoprViewBuilds(self, data[0])
            return
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
        
    def press_event(self):
        pass

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
            VIEW_JSON_ACTION: "View JSON",
            VIEW_BUILD_ACTION: "View build"
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
                bool(options.get(name))
            )

        self.delete_after_days.setValue(
            options.get(
                "delete_after_days",
                None
            ) or 0
        )

        self._set_combo(
            self.bootstrap,
            options.get(
                "bootstrap",
                None
            ) or "default"
        )

        self.bootstrap_image.setText(
            options.get(
                "bootstrap_image",
                None,
            ) or ""
        )

        self._set_combo(
            self.isolation,
            options.get(
                "isolation", None
            ) or "default"
        )

        self._set_lines(
            self.runtime_dependencies,
            options.get(
                "runtime_dependencies", None
            ) or []
        )

        self._set_lines(
            self.packit_forge_projects_allowed,
            options.get(
                "packit_forge_projects_allowed", None
            ) or []
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
            chroots = self.chroot_widgets.chroots()
            repos = {}
            chroot_repos = self.project.chroot_repos
            for i in chroots:
                repos[i] = chroot_repos.get(i, "")
            self.project.chroot_repos = repos
            save_project_options({
                "chroots": chroots
            })
        self.chroot_widgets.changed.connect(save_project_chroots)   
        self.project_options.saved.connect(save_project_options)
        self.setCentralWidget(tabs)


# ===========================================================
# Build chroots
# ===========================================================
from PyQt6.QtWidgets import QAbstractItemView
class BuildTableModel(QAbstractTableModel):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)

        self._data = data or []

        self._headers = [
            "Chroot",
            "Started On",
            "BuildTime",
            "Status",
        ]

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0

        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0

        return len(self._headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role != Qt.ItemDataRole.DisplayRole:
            return None

        build = self._data[index.row()]
        column = index.column()

        if column == 0:
            return build.get("name") or ""

        elif column == 1:
            return time_ago(
                build.get("started_on") or ""
            )

        elif column == 2:
            return format_duration(
                build.get("ended_on") or "",
                build.get("started_on") or "",
            )

        elif column == 3:
            return build.get("state") or ""

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
            if 0 <= section < len(self._headers):
                return self._headers[section]

        if orientation == Qt.Orientation.Vertical:
            return str(section + 1)

        return None

    def set_data(self, data):
        self.beginResetModel()
        self._data = data or []
        self.endResetModel()


class BuildWindow(QMainWindow):
    def __init__(self, parent, _id, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.parent = parent
        self.id = _id
        self.client = parent.client

        self.list = QTableView()
        self.list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.list.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.list.customContextMenuRequested.connect(
            self.show_context_menu
        )

        self.model = BuildTableModel(parent=self)
        self.list.setModel(self.model)

        self.list.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self.config_widget = QWidget(self)

        layout = QVBoxLayout(self.config_widget)
        layout.addWidget(self.list)

        self.setCentralWidget(self.config_widget)

        self.resize(800, 600)

        RunAsync(
            self,
            self.refresh,
            finished=self.refresh_finished,
            error=self.refresh_failed,
        )



    def refresh(self):
        return self.client.build_chroot_proxy.get_list(self.id)

    def refresh_finished(self, builds):
        self.model.set_data(builds)

    def refresh_failed(self, error):
        QMessageBox.critical(
            self,
            "Refresh failed",
            str(error),
        )
    def show_context_menu(self, position):
        index = self.list.indexAt(position)
        menu = QMenu(self)
        if index.isValid():
            # If right-clicked row isn't already selected,
            # make it the only selected row.
            if not self.list.selectionModel().isRowSelected(
                index.row(),
                QModelIndex(),
            ):
                self.list.clearSelection()

                self.list.selectRow(index.row())

            view_action = menu.addAction("View JSON")
            log_action = menu.addAction("View result")
            menu.addSeparator()
        else:
            view_action = None
            log_action = None
        refresh_action = menu.addAction("Refresh")
        action = menu.exec(
            self.list.viewport().mapToGlobal(position)
        )
        rows = [
                index.row()
                for index in self.list.selectionModel().selectedRows()
            ]
        builds = [
                self.model._data[row]
                for row in rows
            ]
        if action == refresh_action:
            RunAsync(
                self,
                self.refresh,
                finished=self.refresh_finished,
                error=self.refresh_failed,
            )
        elif action == log_action:
            if len(builds) > 0:
                for i in builds:
                    url = i.get('result_url', '')
                    if url:
                        QDesktopServices.openUrl(QUrl(url))
                        break
       #     GrowingFileDownloader()
        elif action == view_action:
            if len(builds) == 1:
                builds = builds[0]
            ChrootWidget._show_json(self, builds)

def CoprViewBuilds(self, build):
    self.build_window = BuildWindow(self, build.id)
    self.build_window.show()


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
        window.accepted.connect(
            accepted
        )
        keys = list(self.project.chroot_repos.keys())
        keys.sort()
        window.chroots.set_chroots(keys)
        if self.build_options is not None:
            window.set_values(self.build_options)
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
            identifier_split = identifier.split('-')
            identifier = identifier_split[0]
            if len(identifier_split) > 1:
                spl = identifier_split[1]
                if is_package:
                    if not ('P' in spl):
                        continue
                else:
                    if not ('B' in spl):
                        continue
            
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
        data_name = data.get('name', None) or ''
        if self.name is not None:
            self.name.setText(data_name)
        index = self.qml_ids.get(data.source_type, -1000)
        if index == -1000:
            return
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
            method_index = qml_root.metaObject().indexOfMethod(
                "setName(QVariant)")
            if method_index != -1:
                meta_method = qml_root.metaObject().method(
                    method_index)
                meta_method.invoke(
                    qml_root, 
                    Q_ARG(QVariant, data_name)
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
                source_type = qml_root.property("type")
                if source_type is None:
                    source_type = qml_root.property("identifier"
                        ).split("-")[0]
                data_dict = {
                    "data": data_dict.toVariant(),
                    "type": source_type
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

        thread.start
        add_worker_and_thread(worker, thread)

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
            "View JSON"
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


class AsyncWorker(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(object)

    def __init__(self, function):
        super().__init__()
        self.function = function

    @pyqtSlot()
    def run(self):
        try:
            result = self.function()
        except Exception as exception:
            self.error.emit(exception)
        else:
            self.finished.emit(result)


def RunAsync(parent, function, finished=None, error=None):
    thread = QThread()
    worker = AsyncWorker(function)

    worker.moveToThread(thread)

    thread.started.connect(worker.run)

    if finished is not None:
        worker.finished.connect(finished)

    if error is not None:
        worker.error.connect(error)

    worker.finished.connect(thread.quit)
    worker.error.connect(thread.quit)

    thread.finished.connect(worker.deleteLater)

    thread.start()

    add_worker_and_thread(worker, thread)


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
# GrowingFileDownloader
# ============================================================
import time
from pathlib import Path

import requests


class GrowingFileDownloader:
    def __init__(
        self,
        url,
        output,
        check_interval=2.0,
        chunk_size=1024 * 1024,
        timeout=30,
    ):
        self.url = url
        self.output = Path(output)
        self.check_interval = check_interval
        self.chunk_size = chunk_size
        self.timeout = timeout

        self.session = requests.Session()
        self._closed = False

    def remote_size(self):
        response = self.session.head(
            self.url,
            allow_redirects=True,
            timeout=self.timeout,
        )
        response.raise_for_status()

        size = response.headers.get("Content-Length")

        if size is None:
            raise RuntimeError(
                "Server did not provide Content-Length"
            )

        return int(size)

    def local_size(self):
        if not self.output.exists():
            return 0

        return self.output.stat().st_size

    def download_range(self, start, end):
        headers = {
            "Range": f"bytes={start}-{end}",
        }

        with self.session.get(
            self.url,
            headers=headers,
            stream=True,
            timeout=self.timeout,
        ) as response:
            response.raise_for_status()

            if response.status_code != 206:
                raise RuntimeError(
                    f"Server did not honor Range request: "
                    f"HTTP {response.status_code}"
                )

            with self.output.open("ab") as file:
                for chunk in response.iter_content(
                    chunk_size=self.chunk_size
                ):
                    if chunk:
                        file.write(chunk)

    def update(self):
        """
        Download everything that is currently missing.

        Returns:
            Number of bytes downloaded.
        """
        local = self.local_size()
        remote = self.remote_size()

        if remote <= local:
            return 0

        self.download_range(
            local,
            remote - 1,
        )

        return remote - local

    def follow(self):
        """
        Continuously follow the remote growing file.
        """
        NoNewDataCount = 0
        while NoNewDataCount < 40 and not self._closed:
            try:
                local = self.local_size()
                remote = self.remote_size()

                if remote > local:
                    downloaded = self.update()
                    NoNewDataCount = 0

                elif remote < local:
                    # Remote file was truncated or replaced.
                    self.output.unlink(missing_ok=True)
                    NoNewDataCount = 0

                else:
                    NoNewDataCount += 1

            except requests.RequestException as e:
                print(f"Network error: {e}")

            except Exception as e:
                print(f"Error: {e}")

            time.sleep(self.check_interval)

    def close(self):
        self.session.close()
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


# ============================================================
# LargeLogViewerWindow
# ============================================================

import os
import sys

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import (
    QFont,
    QFontMetrics,
    QPainter,
)
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractScrollArea,
    QFileDialog,
    QMainWindow,
    QToolBar,
)


class LargeLogViewer(QAbstractScrollArea):
    """
    Large-file log viewer.

    The complete file is never loaded into memory.

    Features:
        - Very large files
        - Continuously growing files
        - Automatic follow mode
        - Mouse text selection
        - Ctrl+C
        - Ctrl+A
        - Double-click word selection
        - Selection across multiple lines
        - Selection highlighting
        - UTF-8 with replacement for invalid bytes
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # =====================================================
        # File
        # =====================================================

        self._file = None
        self._path = None
        self._file_size = 0

        # =====================================================
        # Font
        # =====================================================

        self._font = QFont("Monospace")
        self._font.setStyleHint(
            QFont.StyleHint.TypeWriter
        )

        self.setFont(self._font)

        self._metrics = QFontMetrics(self._font)

        self._line_height = (
            self._metrics.lineSpacing()
        )

        self._char_width = (
            self._metrics.horizontalAdvance("M")
        )

        # =====================================================
        # Position
        # =====================================================

        self._top_offset = 0

        # Scrollbar value -> byte offset.
        self._scroll_scale = 1

        # =====================================================
        # Visible line cache
        # =====================================================

        # Each entry:
        #
        # {
        #     "start": absolute byte offset,
        #     "end": absolute byte offset,
        #     "text": decoded text,
        # }
        #
        # "end" is the byte offset after the line's content,
        # but before the newline.

        self._lines = []
        self._lines_offset = -1

        # =====================================================
        # Follow mode
        # =====================================================

        self._follow = True

        # =====================================================
        # Selection
        # =====================================================

        # Selection endpoints are absolute byte offsets.
        #
        # None means there is no selection.
        self._selection_start = None
        self._selection_end = None

        self._selection_anchor = None

        self._dragging = False

        # =====================================================
        # Scrollbars
        # =====================================================

        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )

        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.verticalScrollBar().valueChanged.connect(
            self._scrollbar_changed
        )

        # =====================================================
        # File monitoring
        # =====================================================

        self._timer = QTimer(self)

        self._timer.setInterval(250)

        self._timer.timeout.connect(
            self._check_file
        )

        self._timer.start()

        # =====================================================
        # Focus
        # =====================================================

        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )

        self.setMouseTracking(True)

    # =========================================================
    # File
    # =========================================================

    def set_file(self, path):
        self.close_file()

        self._path = os.path.abspath(path)

        self._file = open(
            self._path,
            "rb",
            buffering=1024 * 1024,
        )

        self._file.seek(
            0,
            os.SEEK_END,
        )

        self._file_size = self._file.tell()

        self._top_offset = 0

        self._follow = True

        self.clear_selection()

        self._invalidate_cache()

        self._update_scrollbar()

        self._go_to_end()

        self.viewport().update()

    def close_file(self):
        if self._file is not None:
            try:
                self._file.close()
            except Exception:
                pass

        self._file = None
        self._path = None

        self._file_size = 0
        self._top_offset = 0

        self.clear_selection()

        self._invalidate_cache()

        self._update_scrollbar()

        self.viewport().update()

    # =========================================================
    # File monitoring
    # =========================================================

    def _check_file(self):
        if self._file is None:
            return

        try:
            size = os.path.getsize(
                self._path
            )
        except OSError:
            return

        if size == self._file_size:
            return

        # -----------------------------------------------------
        # File was truncated/replaced.
        # -----------------------------------------------------

        if size < self._file_size:
            self._file.seek(0)

            self._file_size = size

            self._top_offset = 0

            self.clear_selection()

            self._invalidate_cache()

            self._follow = True

            self._update_scrollbar()

            self._go_to_end()

            self.viewport().update()

            return

        # -----------------------------------------------------
        # File grew.
        # -----------------------------------------------------

        self._file_size = size

        was_at_bottom = self._is_at_bottom()

        self._invalidate_cache()

        self._update_scrollbar()

        if self._follow or was_at_bottom:
            self._follow = True
            self._go_to_end()

        self.viewport().update()

    # =========================================================
    # Cache
    # =========================================================

    def _invalidate_cache(self):
        self._lines.clear()
        self._lines_offset = -1

    # =========================================================
    # Reading
    # =========================================================

    def _read_lines(self, offset, count):
        """
        Read visible lines.

        Returns:

            actual_offset, lines

        Each line contains:

            start
            end
            text
        """

        if self._file is None:
            return offset, []

        if self._file_size <= 0:
            return 0, []

        offset = max(
            0,
            min(
                offset,
                self._file_size,
            ),
        )

        self._file.seek(offset)

        # If offset is in the middle of a line,
        # discard that partial line.
        if offset > 0:
            self._file.readline()

        actual_offset = self._file.tell()

        lines = []

        for _ in range(count):
            start = self._file.tell()

            data = self._file.readline()

            if not data:
                break

            # Remove line ending only from the displayed text.
            content = data.rstrip(
                b"\r\n"
            )

            end = start + len(content)

            text = content.decode(
                "utf-8",
                errors="replace",
            )

            lines.append(
                {
                    "start": start,
                    "end": end,
                    "text": text,
                }
            )

        return actual_offset, lines

    def _read_previous_line(self, offset):
        """
        Find the beginning of the line before offset.
        """

        if offset <= 0:
            return 0

        block_size = 4096

        position = max(
            0,
            offset - block_size,
        )

        while True:
            self._file.seek(position)

            data = self._file.read(
                offset - position
            )

            index = data.rfind(b"\n")

            if index >= 0:
                return position + index + 1

            if position == 0:
                return 0

            offset = position

            position = max(
                0,
                position - block_size,
            )

    # =========================================================
    # Scrollbar
    # =========================================================

    def _update_scrollbar(self):
        scrollbar = self.verticalScrollBar()

        if self._file_size <= 0:
            scrollbar.setRange(0, 0)
            return

        viewport_lines = max(
            1,
            self.viewport().height()
            // self._line_height,
        )

        self._scroll_scale = max(
            1,
            self._file_size // 10_000_000,
        )

        maximum = max(
            0,
            self._file_size
            // self._scroll_scale,
        )

        scrollbar.blockSignals(True)

        scrollbar.setRange(
            0,
            maximum,
        )

        scrollbar.setPageStep(
            max(
                1,
                viewport_lines,
            )
        )

        value = (
            self._top_offset
            // self._scroll_scale
        )

        scrollbar.setValue(
            max(
                0,
                min(
                    value,
                    maximum,
                ),
            )
        )

        scrollbar.blockSignals(False)

    def _scrollbar_changed(self, value):
        if self._file is None:
            return

        offset = (
            value
            * self._scroll_scale
        )

        offset = min(
            offset,
            self._file_size,
        )

        self._top_offset = offset

        if offset > 0:
            self._top_offset = (
                self._read_previous_line(
                    offset
                )
            )

        self._follow = self._is_at_bottom()

        self._invalidate_cache()

        self.viewport().update()

    def _is_at_bottom(self):
        scrollbar = self.verticalScrollBar()

        return (
            scrollbar.value()
            >= scrollbar.maximum() - 1
        )

    # =========================================================
    # Go to end
    # =========================================================

    def _go_to_end(self):
        if self._file is None:
            return

        self._file.seek(
            0,
            os.SEEK_END,
        )

        end = self._file.tell()

        if end <= 0:
            self._top_offset = 0
            self._update_scrollbar()
            return

        self._top_offset = (
            self._read_previous_line(end)
        )

        lines_needed = max(
            1,
            self.viewport().height()
            // self._line_height,
        )

        for _ in range(lines_needed - 1):
            previous = (
                self._read_previous_line(
                    self._top_offset
                )
            )

            if previous == self._top_offset:
                break

            self._top_offset = previous

        self._invalidate_cache()

        self._update_scrollbar()

    # =========================================================
    # Selection
    # =========================================================

    def has_selection(self):
        return (
            self._selection_start is not None
            and self._selection_end is not None
            and self._selection_start
            != self._selection_end
        )

    def clear_selection(self):
        self._selection_start = None
        self._selection_end = None
        self._selection_anchor = None

        self.viewport().update()

    def _set_selection(self, start, end):
        start = max(
            0,
            min(
                start,
                self._file_size,
            ),
        )

        end = max(
            0,
            min(
                end,
                self._file_size,
            ),
        )

        self._selection_start = start
        self._selection_end = end

        self.viewport().update()

    def select_all(self):
        if self._file is None:
            return

        self._selection_start = 0
        self._selection_end = self._file_size
        self._selection_anchor = 0

        self.viewport().update()

    # =========================================================
    # Mouse position -> file offset
    # =========================================================

    def _position_to_offset(self, position):
        """
        Convert a viewport mouse position to an absolute
        byte offset in the file.
        """

        if not self._lines:
            return self._top_offset

        y = position.y()

        row = max(
            0,
            y // self._line_height,
        )

        if row >= len(self._lines):
            line = self._lines[-1]
        else:
            line = self._lines[row]

        text = line["text"]

        # -----------------------------------------------------
        # Find character from X coordinate.
        # -----------------------------------------------------

        x = max(
            0,
            position.x() - 4,
        )

        # Since we're using a monospace font this is cheap,
        # but horizontalAdvance also handles the actual font.
        column = min(
            len(text),
            max(
                0,
                int(
                    x / self._char_width
                    + 0.5
                ),
            ),
        )

        # Convert character position into UTF-8 byte offset.
        prefix = text[:column]

        byte_offset = len(
            prefix.encode(
                "utf-8",
                errors="replace",
            )
        )

        return min(
            line["start"] + byte_offset,
            line["end"],
        )

    # =========================================================
    # Find word
    # =========================================================

    def _word_at_position(self, position):
        """
        Return the byte range of the word under the mouse.
        """

        if not self._lines:
            return None

        y = position.y()

        row = max(
            0,
            y // self._line_height,
        )

        if row >= len(self._lines):
            return None

        line = self._lines[row]

        text = line["text"]

        if not text:
            return None

        x = max(
            0,
            position.x() - 4,
        )

        column = min(
            len(text) - 1,
            max(
                0,
                int(
                    x / self._char_width
                ),
            ),
        )

        # -----------------------------------------------------
        # Find word boundaries.
        # -----------------------------------------------------

        if not (
            text[column].isalnum()
            or text[column] == "_"
        ):
            return None

        start = column
        end = column + 1

        while start > 0:
            char = text[start - 1]

            if not (
                char.isalnum()
                or char == "_"
            ):
                break

            start -= 1

        while end < len(text):
            char = text[end]

            if not (
                char.isalnum()
                or char == "_"
            ):
                break

            end += 1

        start_bytes = len(
            text[:start].encode(
                "utf-8",
                errors="replace",
            )
        )

        end_bytes = len(
            text[:end].encode(
                "utf-8",
                errors="replace",
            )
        )

        return (
            line["start"] + start_bytes,
            line["start"] + end_bytes,
        )

    # =========================================================
    # Mouse events
    # =========================================================

    def mousePressEvent(self, event):
        if event.button() != (
            Qt.MouseButton.LeftButton
        ):
            return

        if self._file is None:
            return

        self.setFocus()

        offset = self._position_to_offset(
            event.position().toPoint()
        )

        # -----------------------------------------------------
        # Shift-click extends the existing selection.
        # -----------------------------------------------------

        if (
            event.modifiers()
            & Qt.KeyboardModifier.ShiftModifier
        ):
            if self._selection_anchor is None:
                self._selection_anchor = offset

            self._set_selection(
                self._selection_anchor,
                offset,
            )

        else:
            self._selection_anchor = offset

            self._set_selection(
                offset,
                offset,
            )

        self._dragging = True

        self._follow = False

        event.accept()

    def mouseMoveEvent(self, event):
        if not self._dragging:
            return

        offset = self._position_to_offset(
            event.position().toPoint()
        )

        if self._selection_anchor is None:
            self._selection_anchor = offset

        self._set_selection(
            self._selection_anchor,
            offset,
        )

        self._follow = False

        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == (
            Qt.MouseButton.LeftButton
        ):
            self._dragging = False

            event.accept()

            return

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() != (
            Qt.MouseButton.LeftButton
        ):
            return

        word = self._word_at_position(
            event.position().toPoint()
        )

        if word is not None:
            start, end = word

            self._selection_anchor = start

            self._set_selection(
                start,
                end,
            )

            self._follow = False

        event.accept()

    # =========================================================
    # Copy
    # =========================================================

    def copy_selection(self):
        if self._file is None:
            return

        if not self.has_selection():
            return

        start = min(
            self._selection_start,
            self._selection_end,
        )

        end = max(
            self._selection_start,
            self._selection_end,
        )

        if start == end:
            return

        self._file.seek(start)

        data = self._file.read(
            end - start
        )

        text = data.decode(
            "utf-8",
            errors="replace",
        )

        QApplication.clipboard().setText(
            text
        )

    # =========================================================
    # Painting
    # =========================================================

    def _selection_range_for_line(self, line):
        if not self.has_selection():
            return None

        start = min(
            self._selection_start,
            self._selection_end,
        )

        end = max(
            self._selection_start,
            self._selection_end,
        )

        line_start = line["start"]
        line_end = line["end"]

        if end <= line_start:
            return None

        if start >= line_end:
            return None

        selected_start = max(
            start,
            line_start,
        )

        selected_end = min(
            end,
            line_end,
        )

        return (
            selected_start,
            selected_end,
        )

    def _byte_offset_to_column(
        self,
        text,
        line_start,
        offset,
    ):
        relative = max(
            0,
            offset - line_start,
        )

        if relative <= 0:
            return 0

        encoded = text.encode(
            "utf-8",
            errors="replace",
        )

        relative = min(
            relative,
            len(encoded),
        )

        # Decode the prefix to determine the number
        # of Unicode characters.
        prefix = encoded[:relative]

        decoded = prefix.decode(
            "utf-8",
            errors="ignore",
        )

        return len(decoded)

    def paintEvent(self, event):
        painter = QPainter(
            self.viewport()
        )

        painter.setFont(
            self._font
        )

        rect = self.viewport().rect()

        # -----------------------------------------------------
        # Background
        # -----------------------------------------------------

        painter.fillRect(
            rect,
            self.palette().base(),
        )

        if self._file is None:
            return

        # -----------------------------------------------------
        # Get visible lines
        # -----------------------------------------------------

        lines_needed = max(
            1,
            rect.height()
            // self._line_height
            + 2,
        )

        if (
            self._lines_offset
            != self._top_offset
            or len(self._lines)
            < lines_needed
        ):
            (
                self._lines_offset,
                self._lines,
            ) = self._read_lines(
                self._top_offset,
                lines_needed,
            )

        # -----------------------------------------------------
        # Colors
        # -----------------------------------------------------

        normal_color = (
            self.palette()
            .text()
            .color()
        )

        selection_background = (
            self.palette()
            .highlight()
            .color()
        )

        selection_color = (
            self.palette()
            .highlightedText()
            .color()
        )

        # -----------------------------------------------------
        # Draw lines
        # -----------------------------------------------------

        y = self._line_height

        for line in self._lines:
            text = line["text"]

            selection = (
                self._selection_range_for_line(
                    line
                )
            )

            if selection is None:
                painter.setPen(
                    normal_color
                )

                painter.drawText(
                    4,
                    y,
                    text,
                )

            else:
                selected_start, selected_end = (
                    selection
                )

                start_column = (
                    self._byte_offset_to_column(
                        text,
                        line["start"],
                        selected_start,
                    )
                )

                end_column = (
                    self._byte_offset_to_column(
                        text,
                        line["start"],
                        selected_end,
                    )
                )

                start_column = max(
                    0,
                    min(
                        start_column,
                        len(text),
                    ),
                )

                end_column = max(
                    start_column,
                    min(
                        end_column,
                        len(text),
                    ),
                )

                before = text[
                    :start_column
                ]

                selected = text[
                    start_column:end_column
                ]

                after = text[
                    end_column:
                ]

                x = 4

                # -------------------------------------------------
                # Before selection
                # -------------------------------------------------

                painter.setPen(
                    normal_color
                )

                if before:
                    painter.drawText(
                        x,
                        y,
                        before,
                    )

                    x += (
                        self._metrics
                        .horizontalAdvance(
                            before
                        )
                    )

                # -------------------------------------------------
                # Selection background
                # -------------------------------------------------

                selected_width = (
                    self._metrics
                    .horizontalAdvance(
                        selected
                    )
                )

                painter.fillRect(
                    x,
                    y - self._metrics.ascent(),
                    selected_width,
                    self._line_height,
                    selection_background,
                )

                painter.setPen(
                    selection_color
                )

                painter.drawText(
                    x,
                    y,
                    selected,
                )

                x += selected_width

                # -------------------------------------------------
                # After selection
                # -------------------------------------------------

                painter.setPen(
                    normal_color
                )

                painter.drawText(
                    x,
                    y,
                    after,
                )

            y += self._line_height

            if y > rect.height():
                break

    # =========================================================
    # Resize
    # =========================================================

    def resizeEvent(self, event):
        super().resizeEvent(event)

        self._update_scrollbar()

        if self._follow:
            self._go_to_end()

        self.viewport().update()

    # =========================================================
    # Keyboard
    # =========================================================

    def keyPressEvent(self, event):
        key = event.key()

        modifiers = event.modifiers()

        scrollbar = self.verticalScrollBar()

        # -----------------------------------------------------
        # Ctrl+C
        # -----------------------------------------------------

        if (
            key == Qt.Key.Key_C
            and modifiers
            & Qt.KeyboardModifier.ControlModifier
        ):
            self.copy_selection()
            event.accept()
            return

        # -----------------------------------------------------
        # Ctrl+A
        # -----------------------------------------------------

        if (
            key == Qt.Key.Key_A
            and modifiers
            & Qt.KeyboardModifier.ControlModifier
        ):
            self.select_all()
            event.accept()
            return

        # -----------------------------------------------------
        # Escape
        # -----------------------------------------------------

        if key == Qt.Key.Key_Escape:
            self.clear_selection()
            event.accept()
            return

        # -----------------------------------------------------
        # End
        # -----------------------------------------------------

        if key == Qt.Key.Key_End:
            self._follow = True

            self._go_to_end()

            self.viewport().update()

            event.accept()
            return

        # -----------------------------------------------------
        # Home
        # -----------------------------------------------------

        if key == Qt.Key.Key_Home:
            self._follow = False

            scrollbar.setValue(
                scrollbar.minimum()
            )

            event.accept()
            return

        # -----------------------------------------------------
        # Page Down
        # -----------------------------------------------------

        if key == Qt.Key.Key_PageDown:
            scrollbar.setValue(
                scrollbar.value()
                + scrollbar.pageStep()
            )

            event.accept()
            return

        # -----------------------------------------------------
        # Page Up
        # -----------------------------------------------------

        if key == Qt.Key.Key_PageUp:
            scrollbar.setValue(
                scrollbar.value()
                - scrollbar.pageStep()
            )

            event.accept()
            return

        # -----------------------------------------------------
        # Down
        # -----------------------------------------------------

        if key == Qt.Key.Key_Down:
            scrollbar.setValue(
                scrollbar.value() + 1
            )

            event.accept()
            return

        # -----------------------------------------------------
        # Up
        # -----------------------------------------------------

        if key == Qt.Key.Key_Up:
            scrollbar.setValue(
                scrollbar.value() - 1
            )

            event.accept()
            return

        super().keyPressEvent(event)

    # =========================================================
    # Mouse wheel
    # =========================================================

    def wheelEvent(self, event):
        super().wheelEvent(event)

        self._follow = self._is_at_bottom()


class LargeLogViewerWindow(QMainWindow):
    def __init__(self, path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle(
            "Large Log Viewer"
        )
        self.resize(
            1000,
            700,
        )
        # =====================================================
        # Viewer
        # =====================================================
        self.viewer = LargeLogViewer(
            self
        )
        self.setCentralWidget(
            self.viewer
        )
        # =====================================================
        # Toolbar
        # =====================================================
        if not path:
            toolbar = QToolBar(
                self
            )
            self.addToolBar(
                toolbar
            )
            open_action = toolbar.addAction(
                "Open"
            )
            open_action.triggered.connect(
                self.open_file
            )
        else:
            self.open_file(path)

    def open_file(self, path = ""):
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Open log file",
            )
        if not path:
            return
        self.viewer.set_file(
            path
        )
        self.setWindowTitle(
            f"Large Log Viewer - {path}"
        )

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


