import os
import sys
import shutil
from pathlib import Path

#cmd = "pyinstaller.exe -F .\\Evolution.py -i images\\app.ico --noconsole --exclude-module PyQt5"
cmd = "pyinstaller.exe .\\Evolution.py -i images\\app.ico --clean --noconsole --exclude-module=PyQt5 \
            --exclude-module=numpy --exclude-module=nacl --exclude-module=psycopg2"

ret = os.system(cmd)

if ret != 0:
    sys.exit(ret)

'''
need_removes = Path('dist', 'Evolution', '_internal').glob(".//mkl_*.dll")
for file in need_removes:
    os.path.unlink(file)
    print(f'Deleted:{file}')
'''

#shutil.rmtree('dist/Evolution/_internal/psycopg2')
for file in [
    'opengl32sw.dll',
    'Qt6Quick.dll',
    'Qt6Pdf.dll',
    'Qt6Qml.dll',
    'Qt6OpenGL.dll',
    ]:
    os.remove(F'dist/Evolution/_internal/PySide6/{file}')

folders = ['Game', 'Engine', 'EndBooks', 'Sound']
for folder in folders:
    src_folder = f".\\{folder}"
    dest_folder = f".\\dist\\Evolution\\{folder}"
    #os.mkdir(dest_folder) 
    print("*** Copying Folder:", src_folder,"-->", dest_folder)
    shutil.copytree(src_folder, dest_folder)

shutil.rmtree('build')

#os.rename('.\\dist', '.\\Evolution')
for file in [
    "Evolution.ini",
    'ReadMe.txt',
    'ReleaseNote.txt'
    ]:
    shutil.copy(file, '.\\dist\\Evolution\\')

print('请到.\\dist\\Evolution目录下查看exe文件。')
print("Done.")      