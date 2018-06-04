# -*- coding: utf-8 -*-
"""
Created on Thu Apr 05 21:09:28 2018

@author: hh_s
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

import glob,sys,os,datetime,time
import threading
import win32pipe, win32file,time,struct
from opcua import ua, Server
import collections

fileHandle = win32file.CreateFile("\\\\.\\pipe\\Pipe",
                              win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                              0, None,
                              win32file.OPEN_EXISTING,
                              0, None)  

zonas=70
qAlarmas=collections.deque()
def server_opc(zonas_cant):
    server = Server()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/Ducto_costero")
    
    
    server.set_server_name("Servidor alarmas ducto costero")
    # setup our own namespace, not really necessary but should as spec
    uri = "Alarmas ducto RA"
    
    idx = server.register_namespace(uri)
    # get Objects node, this is where we should put our nodes
    objects = server.get_objects_node()
    
    # populating our address space
    myobj = objects.add_object(idx, "Alarmas_RA")
    zonass=[]
    for i in range(zonas_cant):
        new_zone=myobj.add_variable(idx, "Zona_"+str(i+1), False)
        new_zone.set_writable()
        zonass.append(new_zone)
    
    
    zonass=np.array(zonass)
    # starting!
    server.start()
    try:
        while True:
            if len(qAlarmas)>0:
                proxima_alarma=qAlarmas.popleft()
                print proxima_alarma                  
                for zona in zonass[proxima_alarma]:
                    zona.set_value(True)
            else:
                time.sleep(1)
    finally:
    #close connection, remove subcsriptions, etc
        server.stop()
th_alarmas=threading.Thread(target=server_opc,args=[zonas])
th_alarmas.start()

def encontrar_alarmas_live(block_alarma_live,avg,std,umbrales_porcentaje,ventana_alarma,zonas):

    z_score_block=(block_alarma_live-avg)/std #calculo los z_scores
    #filtro con broadcast bool
    
    umbrales_matriz={}
    umbrales_cuenta={}
    matriz_umbrales=np.array([])
    
    for u in umbrales_porcentaje:
    
        umbrales_matriz[u]=np.where(z_score_block>u,1,0)#Matriz de 1 donde supera el umbral, 0 donde no
    
        umbrales_cuenta[u]=np.sum(umbrales_matriz[u],axis=0)#sumo por columna
    
        matriz_umbrales=np.append(matriz_umbrales,np.where(umbrales_cuenta[u]>(umbrales_porcentaje[u]*ventana_alarma),u,0)) #construye matriz con todas las filas por umbral para buscar maximo por filas
        
    matriz_umbrales=matriz_umbrales.reshape((len(umbrales_porcentaje.keys()),zonas))
    primera_fila_alarma=np.max(matriz_umbrales,axis=0)#inicializo la primera fila
    
    return umbrales_matriz,umbrales_cuenta,primera_fila_alarma


#base_ra=open('base_ra_test.std','ab')
def plot_update_anim(i):
    global im_std,imagen_std_actual
    global im_alarmas,imagen_alarmas
    global live_base,baseline
    global umbrales_matriz,umbrales_cuenta
    global fileHandle,base_almuerzo
    
    rr,rd = win32file.ReadFile(fileHandle, bins*4) #2 es tamanio de datos   
    new_data = np.frombuffer(rd,dtype=np.float32)[bin_inicio:bin_fin]
#    new_data.tofile(base_almuerzo)
    
    roll=False
    if i>=shots_por_grafico:
        roll=True
    #new_data=np.random.normal(scale=0.5,size=imagen_std_actual.shape[1])
    if roll:
        imagen_std_actual=np.vstack([imagen_std_actual[1:,:],new_data])
    else:
        imagen_std_actual[i,:]=new_data
    
    if i<ventana_alarma:
        imagen_alarmas[i,:]=-1
        baseline[i,:]=z_binning_vect(new_data[:ancho_zona*zonas],ancho_zona)
    elif i==ventana_alarma:
        umbrales_matriz,umbrales_cuenta,primera_fila = encontrar_alarmas_live(baseline,np.mean(baseline,axis=0),np.std(baseline,axis=0),umbrales_porcentaje,ventana_alarma,zonas)
        imagen_alarmas[i,:]=primera_fila
    else:
        data_test=z_binning_vect(new_data[:ancho_zona*zonas],ancho_zona)
        alarma_nueva=alarma_fila_nueva(data_test,umbrales_porcentaje,np.mean(baseline,axis=0),np.std(baseline,axis=0),umbrales_matriz,umbrales_cuenta)
        if roll:
            imagen_alarmas=np.vstack([imagen_alarmas[1:,:],alarma_nueva])
        else:
            imagen_alarmas[i,:]=alarma_nueva
        qAlarmas.append(np.where(alarma_nueva>0))
    
    im_alarmas.set_data(imagen_alarmas)
    im_std.set_data(imagen_std_actual)
    return im_std,im_alarmas,    


def plot_update_th(ax_std,im_std,ax_alarmas,im_alarmas,imagen_std_actual,imagen_alarmas,mean_base,std_base,live_base,ventana_alarma,fig):

    if live_base:
        contador_historico=0
    fila_actual=0
    roll=False
    while not(fin_adq):
        new_data=np.random.normal(size=imagen_std_actual.shape[1])
        if roll:
            imagen_std_actual=np.vstack([imagen_std_actual[1:,:],new_data])
        else:
            imagen_std_actual[fila_actual,:]=new_data
        fila_actual+=1
        if fila_actual==shots_por_grafico:
            roll=True
        im_std.set_data(imagen_std_actual)
        time.sleep(0.2)
        fig.canvas.draw()    

def alarma_fila_nueva(fila_nueva_zoneada,umbrales_porcentaje,avg,std,umbrales_matriz,umbrales_cuenta):
    
    z_score_fila=(fila_nueva_zoneada-avg)/std #calculo los z_scores
    #filtro con broadcast 1,0
    
    matriz_umbrales=np.array([])
    
    for u in umbrales_porcentaje:
        fila_nueva_umbrales=np.where(z_score_fila>u,1,0)
        
        fila_a_borrar=umbrales_matriz[u][0,:]
                
        umbrales_matriz[u]=np.vstack([umbrales_matriz[u][1:,:],fila_nueva_umbrales]) #actualizo matriz
    
        umbrales_cuenta[u]=umbrales_cuenta[u]-fila_a_borrar+fila_nueva_umbrales#actualizo cuenta
    
        matriz_umbrales=np.append(matriz_umbrales,np.where(umbrales_cuenta[u]>(umbrales_porcentaje[u]*ventana_alarma),u,0)) #construye matriz con todas las filas por umbral para buscar maximo por filas
        
    matriz_umbrales=matriz_umbrales.reshape((len(umbrales_porcentaje.keys()),zonas))
    return np.max(matriz_umbrales,axis=0)


def z_binning_vect(data,window):
    binned_matrix=data.reshape(-1,(data.shape[0]/window),order='F')
    return binned_matrix.mean(0)

bins=int(sys.argv[1])-int(sys.argv[2])+1
bin_inicio=1680
bin_fin=5040

ancho_zona=(bin_fin-bin_inicio)/zonas


norm=True

qFreq=int(sys.argv[3])
clockB=int(sys.argv[-2])
clock=int(sys.argv[-1])
c = 299792458.
delta_t = 5e-9;
n = 1.48143176194
c_f = c/n
if clockB: delta_t=delta_t*clock
delta_x = qFreq*c_f*delta_t/2 
print "Delta X: ",delta_x

try:
    filename_base='base_test_1.std'
    filename_base_avg='base_test_1.avg'
 
    base_inicio=0
    base_fin=950
    linea_de_base=(np.fromfile(filename_base,dtype=np.float32).reshape((-1,bins)))
    if norm:
             linea_de_base=linea_de_base/(np.fromfile(filename_base_avg,dtype=np.float32).reshape((-1,bins)))
    plt.imshow(linea_de_base,aspect='auto')
    plt.title('Linea de base. \nSe toma desde '+str(bin_inicio)+' hasta '+str(bin_fin)+ ' entre shots '+str(base_inicio)+' y '+str(base_fin))
    
    linea_de_base=linea_de_base[base_inicio:base_fin,bin_inicio:bin_fin]
    ultima_multiplo=ancho_zona*zonas
    base_zoneada=np.array([z_binning_vect(linea_de_base[i,:ultima_multiplo],ancho_zona)for i in range (base_fin-base_inicio)])    
    mean_base=np.mean(base_zoneada,axis=0)
    std_base=np.std(base_zoneada,axis=0)
    plt.figure()
    plt.plot(mean_base)
    plt.title('media base')
    plt.figure()
    plt.plot(std_base) 
    plt.title('std base')
    live_base=False
except:
    live_base=True
    print "Baseline live mode"

if (bin_fin-bin_inicio)%zonas!=0:
    pass    #ajustar ultima zona

ventana_alarma=80#Cantidad de vectores std a tener en cuenta
umbrales_porcentaje={6:0.75,8:0.65,10:0.6,15:0.55,20:0.5,30:0.45,40:0.33,50:0.325}#8:0.6,

fig, (ax_std, ax_alarmas) = plt.subplots(1,2)

shots_por_grafico=500
imagen_std_actual=np.zeros((shots_por_grafico,bin_fin-bin_inicio))

if not(live_base):
    minimo_colormap_std=np.min(mean_base)-np.max(std_base)*5
    maximo_colormap_std=np.max(mean_base)+np.max(std_base)*5
else:
    minimo_colormap_std=0
    maximo_colormap_std=0.15

minimo_colormap_std=0
maximo_colormap_std=0.15

baseline=np.zeros((ventana_alarma,zonas))
umbrales_matriz={}
umbrales_cuenta={}



im_std=ax_std.imshow(imagen_std_actual,cmap='jet',aspect='auto',vmin=minimo_colormap_std,vmax=maximo_colormap_std)
ax_std.set_title('Dato STD')
ax_std.axvline(x=2291,label="Valv. 2")
ax_std.axvline(x=1130,label="Toledo")

ax_std.legend()
imagen_alarmas=np.zeros((shots_por_grafico,zonas))

im_alarmas=ax_alarmas.imshow(imagen_alarmas,cmap='hot',aspect='auto',vmin=-1,vmax=max(umbrales_porcentaje.keys()))

ax_alarmas.set_xticks(np.arange(zonas))
ax_alarmas.set_title('Alarmas por zonas (cantidad de desvios por encima de la linea de base)')
ax_alarmas.grid(color='g',axis='x',which='major',alpha=0.5)
ax_alarmas.axhline(y=ventana_alarma,color='r')

fig.suptitle('STD - Alarmas')

th=False
if th:
    mean_base=0
    std_base=1
    th_adq=threading.Thread(target=plot_update_th,args=(ax_std,im_std,ax_alarmas,im_alarmas,imagen_std_actual,imagen_alarmas,mean_base,std_base,live_base,ventana_alarma,fig))
    fin_adq=False
    th_adq.start()
else:
    anim=animation.FuncAnimation(fig, plot_update_anim, interval=200, blit=True)
plt.show()

if th:
    fin_adq=True
    th_adq.join()

