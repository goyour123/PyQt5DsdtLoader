import winreg
import sys, os, subprocess
import re
import json
import logging

ACPI_REG_KEY_PATH = r'HARDWARE\ACPI'
AML_POSTFIX = r'.aml'
REGEDIT_AML_POSTFIX = r'0000.bin'
OUTPUT_ASL_POSTFIX = r'.dsl'

def GetEnumKeyList (RegKey, RegSubKey):
    Idx, EnumKeyList = 0, list ()
    RegKeyIns = winreg.OpenKeyEx (RegKey, RegSubKey)

    while True:
        try:
            KeyEnumStr = winreg.EnumKey (RegKeyIns, Idx)
        except:
            break
        else:
            EnumKeyList.append (KeyEnumStr)
            Idx += 1
    return EnumKeyList

def GetAcpiRegValue (RegKey, RegSubKey):
    KeyList = GetEnumKeyList (RegKey, RegSubKey)
    if not len (KeyList):
        KeyIns = winreg.OpenKeyEx (RegKey, RegSubKey)
        return winreg.EnumValue (KeyIns, 0)[1]
    else:
        return GetAcpiRegValue (RegKey, RegSubKey + '\\' + KeyList[0])

if __name__ == '__main__':
    argNames = ['Script', 'Arg1', 'Arg2']
    args = dict (zip (argNames, sys.argv))
    cfgName = re.findall (r'(.+)\.', args['Script'])[0]
    cfgExt = 'json'

    amlArg = None
    aslExePath, iAslExePath = str(), str()
    status = str()
    acpiRegTblList, ctnRegTblList = list(), list()

    logging.basicConfig(level=logging.INFO)

    if len(args) > 1:
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

        # Collect acpi table names in system
        SubKey = ACPI_REG_KEY_PATH
        acpiRegTblList = GetEnumKeyList (winreg.HKEY_LOCAL_MACHINE, SubKey)

        if args['Arg1'] == '-asl':
            amlArg = None
        elif args['Arg1'] == '-aml':
            amlArg = '/c'
        else:
            # Run asl.exe to get AML
            tblName = args['Arg1']
            status = subprocess.run ([aslExePath, '/nologo', '/tab=' + tblName, '/c'], encoding='utf-8', capture_output=True)
            if status.returncode:
                logging.error('Run ' + aslExePath + ' failed - ' + status.stdout)
                sys.exit()

            # Collect needed external control method AML
            for regTbl in acpiRegTblList:
                if re.match(r'SSD.|DSDT', regTbl):
                    if tblName != regTbl:
                        ctnRegTblList.append (regTbl)

            # Extract needed external control method AML
            subProcArgs = [iAslExePath, '-vs', '-p' + tblName, '-e']
            for regTbl in ctnRegTblList:
                status = subprocess.run ([aslExePath, '/nologo', '/tab=' + regTbl, '/c'], encoding='utf-8', capture_output=True)
                if not status.returncode:
                    subProcArgs.append(regTbl + REGEDIT_AML_POSTFIX)
            subProcArgs.extend (['-d', tblName + REGEDIT_AML_POSTFIX])

            # Use iasl.exe to disassemble AML
            subprocess.run (subProcArgs, capture_output=False)

            if os.path.exists (tblName + REGEDIT_AML_POSTFIX):
                os.remove (tblName + REGEDIT_AML_POSTFIX)
            # Clear external control method AMLs
            for regTbl in ctnRegTblList:
                if os.path.exists (regTbl + REGEDIT_AML_POSTFIX):
                    os.remove (regTbl + REGEDIT_AML_POSTFIX)

            try:
                tblDbgSource = args['Arg2']
            except KeyError:
                sys.exit()
            else:
                pass
            offset = 0
            with open (tblDbgSource, 'r') as dbg:
                dbgContent = dbg.readlines()

            # Embed the script
            with open (tblName + '.dsl', 'r+') as tbl:
                tblContent = tbl.readlines()
                for pos, line in enumerate(tblContent):
                    r = re.findall ('^DefinitionBlock.*', line)
                    if r:
                        pos += 2
                        break

                for idx, line in enumerate(dbgContent):
                    tblContent.insert(pos + idx, line)

                tbl.seek(0)
                tbl.truncate(0)
                tbl.writelines(tblContent)

            # Compile updated asl
            status = subprocess.run ([iAslExePath, '-ve', tblName + OUTPUT_ASL_POSTFIX], encoding='utf-8', capture_output=True)
            if status.returncode:
                logging.error('Run ' + aslExePath + ' failed - ' + status.stdout)
            sys.exit()

        if len(args) > 2:
            if args['Arg2'] == 'FACS':
                tblName = 'FACP'
            else:
                tblName = args['Arg2']
            subProcArgs = [aslExePath, '/nologo', '/tab=' + tblName]
            if amlArg:
                subProcArgs.append(amlArg)
            subprocess.run (subProcArgs)
        else:
            # Extract all ACPI Table from HKEY_LOCAL_MACHINE\HARDWARE\ACPI
            for regTbl in acpiRegTblList:
                if regTbl == 'FACS':
                    tblName = 'FACP'
                else:
                    tblName = regTbl
                subProcArgs = [aslExePath, '/nologo', '/tab=' + tblName]
                if amlArg:
                    subProcArgs.append(amlArg)
                subprocess.run (subProcArgs)

    else:
        sys.exit()