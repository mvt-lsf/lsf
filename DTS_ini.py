# -*- coding: utf-8 -*-
"""
Created on Fri Aug 25 17:45:57 2017

@author: MVT
"""
#
from Tkinter import *
import tkFileDialog
from shutil import copyfile
import os
import configparser
import datetime
import glob
import subprocess
import time

path_mediciones='D:/mediciones/'

new_path=path_mediciones+datetime.datetime.fromtimestamp(time.time()).strftime('%Y%m%d')+'/'

try:
    os.makedirs(new_path)
except:
    pass #ya esta creado




try:
    newest = max(glob.iglob(path_mediciones+'*/*/*.ini'), key=os.path.getctime) 
    config = configparser.ConfigParser()
    config.read(newest)
    if 'Adquisicion' not in config.sections():
        prev_params=[]
    else:
        prev_params=config['Adquisicion']
except:
    prev_params=[]
    print "NO INI FILE"
    pass    


root = Tk()

names = ["Puntos", "Shots por Chunks","Chunks por perfil", "Perfiles por pozo","Cociente frecuencia", "Rango CH1","Rango CH2", "Referencia Stokes","Referencia Anti-Stokes","Delay"]
param_order=[names[1],names[0],names[2],names[7],names[8],"nd",names[9],names[4],names[5],names[6],names[3]]
entry = {}
label = {}
i = 0
for name in names:
    e = Entry(root)#font = "Helvetica 44 bold"
    e.grid(sticky=E)

    if prev_params:
        e.insert(INSERT, prev_params[name])
    entry[name] = e

    lb = Label(root, text=name)
    lb.grid(row=i, column=1,sticky=N+S+E+W)
#    lb.pack()
    label[name] = lb
    i += 1
#for archivo in archivos:
    
def CrearIni(entry):#recibir el py y el exe para logear
    config = configparser.ConfigParser()
    cfgfile = open("parametros_iniciales_"+datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')+'.ini','w')
    config.add_section('Adquisicion')
    for key in entry:
         config.set('Adquisicion',key,entry[key].get())
    config.write(cfgfile)
    cfgfile.close()

def ejecutar():
    
    exe = tkFileDialog.askopenfilename(title='Ejecutable DTS')#recomendar path viejo
    
    #guardar codigo
    
    py = tkFileDialog.askopenfilename(title='Python DTS')
    
    os.chdir(new_path)
    new_med=datetime.datetime.fromtimestamp(time.time()).strftime('%H_%M_%S')
    os.makedirs(new_med)
    os.chdir(new_med)
    CrearIni(entry)
    parametros=""
    for names in param_order:
        if names!="nd":
            parametros+=' '+(entry[names].get())
        else:
            parametros+=' 0'
    

   
    copyfile(exe,os.getcwd()+'/dts_exe.exe')
    copyfile(py,os.getcwd()+'/graficar.py')

    process = subprocess.Popen(('cmd /k dts_exe'+parametros).split(),creationflags=subprocess.CREATE_NEW_CONSOLE)
    #ejecutar con parametros redirigiendo salida a logs
    root.destroy()

b = Button(root, text="Ejecutar", command=ejecutar)
b.grid(sticky=N+S+E+W)

mainloop()

