import sys, os, ctypes, subprocess
import winreg
import logging
import json, re
from PyQt5.QtWidgets import QApplication, QMainWindow, QAbstractItemView, QMessageBox, QShortcut
from PyQt5.QtCore import QStringListModel, QModelIndex, Qt
from PyQt5.QtGui import QFont
from PyQt5.Qsci import QsciScintilla
from PyQt5DsdtLoaderGUI import Ui_MainWindow
from wal import ACPI_REG_KEY_PATH, REGEDIT_AML_POSTFIX, OUTPUT_ASL_POSTFIX, AML_POSTFIX, GetEnumKeyList

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.qfontSci = QFont()
        self.qfontSci.setPointSize(11)

        self.qscintilla = QsciScintilla()
        self.qscintilla.setWrapMode (QsciScintilla.SC_WRAP_NONE)
        self.ui.verticalLayout.addWidget(self.qscintilla)
        self.qscintilla.textChanged.connect(self.acpiTblCntChanged)
        self.qscintilla.setFont(self.qfontSci)
        self.qscintilla.setEolMode(QsciScintilla.SC_EOL_CRLF)

        # Qsci margin
        qsciMargin = QsciScintilla.MarginType()
        qsciMarginFont = QFont()
        qsciMarginFont.setPointSize(8)
        self.qscintilla.setMarginsFont(qsciMarginFont)
        self.qscintilla.setMarginWidth(1, "xxxxxx")
        self.qscintilla.setMarginType(1, qsciMargin)
        self.qscintilla.setMarginLineNumbers(1, True)

        self.ui.pushButton.clicked.connect(self.compilePushButton)
        self.ui.pushButton.setEnabled(False)
        self.ui.pushButton_2.clicked.connect(self.loadPushButton)
        self.ui.pushButton_2.setEnabled(False)
        self.ui.pushButton_3.clicked.connect(self.debugOnPushButton)
        self.ui.pushButton_4.clicked.connect(self.debugOffPushButton)
        self.ui.pushButton_5.clicked.connect(lambda: self.searchPushButton(True))

        self.wo, self.cs = False, False
        self.searchText, self.selections = self.ui.lineEdit.text(), None
        self.modified = False

        # Add shortcuts
        QShortcut(Qt.ControlModifier | Qt.Key_F, self.qscintilla).activated.connect(self.shortCutCtrlF)
        QShortcut(Qt.Key_Return, self.ui.lineEdit).activated.connect(lambda: self.searchPushButton(True))
        QShortcut(Qt.Key_Enter, self.ui.lineEdit).activated.connect(lambda: self.searchPushButton(True))
        QShortcut(Qt.Key_F3, self.ui.lineEdit).activated.connect(lambda: self.searchPushButton(True))
        QShortcut(Qt.ShiftModifier | Qt.Key_Return, self.ui.lineEdit).activated.connect(lambda: self.searchPushButton(False))
        QShortcut(Qt.ShiftModifier | Qt.Key_Enter, self.ui.lineEdit).activated.connect(lambda: self.searchPushButton(False))
        QShortcut(Qt.ShiftModifier | Qt.Key_F3, self.ui.lineEdit).activated.connect(lambda: self.searchPushButton(False))

        self.msgBox = QMessageBox()

        # Show ACPI tbl in QListView
        self.acpiRegTblList = GetEnumKeyList (winreg.HKEY_LOCAL_MACHINE, ACPI_REG_KEY_PATH)
        self.ctnRegTblList = list()
        # Collect needed external control method AML
        for regTbl in self.acpiRegTblList:
            if re.match(r'SSD.|DSDT', regTbl):
                    self.ctnRegTblList.append (regTbl)

        # Extract AMLs
        for regTbl in self.ctnRegTblList:
            subprocess.run ([aslExePath, '/nologo', '/tab=' + regTbl, '/c'], encoding='utf-8', capture_output=False)

        self.extCtnAmlList = [f for f in cfg['EXT_CTN_AML_DIR'] if os.path.exists(f)]

        acpiSlm = QStringListModel()
        acpiSlm.setStringList(self.ctnRegTblList)
        self.ui.listView.setModel(acpiSlm)
        self.ui.listView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.tblName = str()
        self.acpiModelIndex = QModelIndex()

        self.ui.listView.clicked.connect(self.clickedListView)

    def clickedListView(self, qModelIndex):
        # Select the same table, just to return
        if self.acpiModelIndex == qModelIndex:
            return

        if self.modified:
            rtn = self.popSaveBox()
            if rtn == QMessageBox.StandardButton.Cancel:
                self.ui.listView.setCurrentIndex(self.acpiModelIndex)
                return
            elif rtn == QMessageBox.StandardButton.Yes:
                with open (self.tblName + '.mod' + OUTPUT_ASL_POSTFIX, 'w') as tbl:
                    tbl.write(self.qscintilla.text())

        # Disable Compile pushButton
        self.ui.pushButton.setEnabled(False)
        # Disable Load pushButton
        self.ui.pushButton_2.setEnabled(False)

        self.acpiModelIndex = qModelIndex
        # Run asl.exe to get AML
        self.tblName = self.ctnRegTblList[qModelIndex.row()]

        # Extract needed external control method AML
        subProcArgs = [iAslExePath, '-vs', '-p' + self.tblName, '-e']
        for regTbl in self.ctnRegTblList:
            if regTbl != self.tblName:
                subProcArgs.append(regTbl + REGEDIT_AML_POSTFIX)

        for extTbl in self.extCtnAmlList:
            subProcArgs.append(extTbl)
        subProcArgs.extend (['-d', self.tblName + REGEDIT_AML_POSTFIX])

        tblCnt = str()

        # Use iasl.exe to disassemble AML
        self.ui.statusbar.showMessage('Disassembling ' + self.tblName)
        status = subprocess.run (subProcArgs, encoding='utf-8', capture_output=True)
        if status.returncode:
            self.ui.statusbar.showMessage(self.tblName + ' disassembled failed')
            self.msgBox.setText(self.tblName + ' disassembled failed!')
            self.popErrMsgBox(status.stderr)
        else:
            self.ui.statusbar.clearMessage()
            print(status.stderr)
            with open (self.tblName + OUTPUT_ASL_POSTFIX, 'r') as tbl:
                tblCnt = tbl.read()
        self.qscintilla.setText(tblCnt)

        # Change the table, set self.modified back to False
        self.modified = False

    def acpiTblCntChanged(self):
        self.ui.pushButton.setEnabled(True)
        self.selections = None
        self.modified = True

    def compilePushButton(self):
        with open (self.tblName + OUTPUT_ASL_POSTFIX, 'w') as tbl:
            tbl.write(self.qscintilla.text())
        status = subprocess.run ([iAslExePath, '-ve', self.tblName + OUTPUT_ASL_POSTFIX], encoding='utf-8', capture_output=True)
        if not status.returncode:
            self.ui.pushButton.setEnabled(False)
            self.ui.pushButton_2.setEnabled(True)
            print(status.stdout)
        else:
            self.msgBox.setText(self.tblName + ' compiled error!')
            self.popErrMsgBox(status.stderr)

    def popErrMsgBox(self, errStr):
        self.msgBox.setWindowTitle('ERROR')
        self.msgBox.setInformativeText(errStr)
        self.msgBox.setStandardButtons(QMessageBox.StandardButton.Ok)
        self.msgBox.setDefaultButton(QMessageBox.StandardButton.Ok)
        return self.msgBox.exec()

    def popMsgBox(self):
        self.msgBox.setWindowTitle('LOAD')
        self.msgBox.setText(self.tblName + ' is going load into registry!')
        self.msgBox.setInformativeText('Do you want to apply it?')
        self.msgBox.setStandardButtons(QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Cancel)
        self.msgBox.setDefaultButton(QMessageBox.StandardButton.Apply)
        return self.msgBox.exec()

    def popSaveBox(self):
        self.msgBox.setWindowTitle('File Modified')
        self.msgBox.setText(self.tblName + ' is modified! Do you want to save it?')
        self.msgBox.setInformativeText('Yes to save the ' + self.tblName)
        self.msgBox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
        self.msgBox.setDefaultButton(QMessageBox.StandardButton.Yes)
        return self.msgBox.exec()

    def loadPushButton(self):
        rtn = self.popMsgBox()
        if rtn == QMessageBox.StandardButton.Apply:
            status = subprocess.run ([aslExePath, '/loadtable', self.tblName + AML_POSTFIX], encoding='utf-8', shell=True)
            if status.returncode:
                self.ui.pushButton_2.setEnabled(False)
            else:
                self.popErrMsgBox(status.stderr)
        else:
            pass

    def searchLoop(self, s):
        resSelList = list()
        orgCurPosition = self.qscintilla.getCursorPosition()
        self.qscintilla.setCursorPosition (0, 0)
        if self.qscintilla.findFirst(s, False, False, False, False, forward=True):
            resSelList.append(self.qscintilla.getSelection())
            while (self.qscintilla.findNext()):
                resSelList.append(self.qscintilla.getSelection())
        self.qscintilla.setCursorPosition(*orgCurPosition)
        return resSelList

    def searchPushButton(self, fw):
        if self.searchText != self.ui.lineEdit.text() or not self.selections:
            self.searchText = self.ui.lineEdit.text()
            self.selections = self.searchLoop(self.searchText)
        orgCurPosition = self.qscintilla.getCursorPosition()

        if not fw:
            self.qscintilla.setCursorPosition(orgCurPosition[0], orgCurPosition[1] - 1)

        if not self.qscintilla.findFirst(self.searchText, False, False, False, False, forward=fw):
            self.ui.label.setText("Not Found")
            if not fw:
                self.qscintilla.setSelection(*self.selections[0])
            else:
                self.qscintilla.setSelection(*self.selections[-1])
        else:
            t = str(self.selections.index(self.qscintilla.getSelection()) + 1) + " / " + str(len(self.selections))
            self.ui.label.setText(t)

    def debugOnPushButton(self):
        status = subprocess.run(['bcdedit', '/set', 'testsigning', 'on'], encoding='utf-8', shell=True)
        print ('Return Code:', status.returncode)

    def debugOffPushButton(self):
        status = subprocess.run(['bcdedit', '/set', 'testsigning', 'off'], encoding='utf-8', shell=True)
        print ('Return Code:', status.returncode)

    def shortCutCtrlF(self):
        self.ui.lineEdit.setText(self.qscintilla.selectedText())
        self.ui.lineEdit.setFocus()
        self.ui.lineEdit.selectAll()

def isAdmin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if __name__ == "__main__":

    if isAdmin():
        cfgName = 'wal'
        cfgExt = 'json'

        # Check config file exists
        try:
            logging.info ('Load ' + cfgName + '.' + cfgExt)
            with open (cfgName + '.' + cfgExt, 'r') as j:
                cfg = json.load(j)
        except:
            logging.error (cfgName + '.' + cfgExt + " not found!")
            sys.exit()

        # Check whether asl.exe exists
        if os.path.exists(cfg['ASL_EXE_PATH']):
            aslExePath = os.path.realpath(cfg['ASL_EXE_PATH'])
            logging.info ("Found asl.exe - " + aslExePath)
        else:
            logging.error ("asl.exe not found! - " + cfg['ASL_EXE_PATH'])
            sys.exit()

        # Check whether iasl.exe exists
        if os.path.exists(cfg['iASL_EXE_PATH']):
            iAslExePath = os.path.realpath(cfg['iASL_EXE_PATH'])
            logging.info ("Found iasl.exe - " + iAslExePath)
        else:
            logging.error ("iasl.exe not found! - " + cfg['iASL_EXE_PATH'])
            sys.exit()

        app = QApplication(sys.argv)

        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    else:
        if os.path.splitext(sys.argv[0])[1] == '.py':
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        else:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.argv[0], None, None, 1)
        sys.exit()
