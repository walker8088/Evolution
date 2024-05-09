import os
import sys
import shutil

cmd = "pyinstaller.exe -F .\\Evolution.py -i images\\app.ico --noconsole --exclude-module PyQt5"

ret = os.system(cmd)

if ret != 0:
    sys.exit(ret)

folders = ['Game', 'Engine', 'Sound']
for folder in folders:
    src_folder = f".\\{folder}"
    dest_folder = f".\\dist\\{folder}"
    #os.mkdir(dest_folder) 
    print("*** Copying Folder:", src_folder,"-->", dest_folder)
    shutil.copytree(src_folder, dest_folder)

shutil.rmtree('build')
os.rename('.\\dist', '.\\Evolution')
print('请到.\\Evolution目录下查看exe文件。')
print("Done.")      