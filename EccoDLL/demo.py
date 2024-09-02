import platform
from ctypes import *

if platform.system() == 'Windows':
    ecco_dll = cdll.LoadLibrary('.\\ECCO64.DLL')
else:
    ecco_dll = cdll.LoadLibrary('./libecco64.so')
ecco_dll.EccoVersion.restype = c_char_p
ecco_dll.EccoOpening.restype = c_char_p
ecco_dll.EccoVariation.restype = c_char_p

ecco_dll.EccoInitOpenVar(0)
print(ecco_dll.EccoVersion().decode())
ecco = ecco_dll.EccoIndex('C2.5N8+7N2+3R9.8R1.2P7+1R2+6N2+3P7+1C8.9R2.3C9-1N8+7A4+5C8.9'.encode())
print(ecco.to_bytes(3, 'little').decode())
print(ecco_dll.EccoOpening(ecco).decode())
print(ecco_dll.EccoVariation(ecco).decode())