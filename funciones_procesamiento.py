import matplotlib
matplotlib.use('TKagg')
import numpy as np
import matplotlib.pyplot as plt

import glob,sys,os,datetime,time


def encontrar_alarmas(imagen_std,avg,std,umbrales_porcentaje,ventana_alarma,zonas,ancho_zona):
	res=np.empty((imagen_std.shape[0],zonas))
	res[:ventana_alarma,:]=-1#primeras ventana filas no tienen sentido
	
	ultima_columna_multiplo=ancho_zona*zonas #ignora ultima zona
	
	alarma_block=imagen_std[:ventana_alarma,:ultima_columna_multiplo] #tomo el primer bloque de alarmas
	block_zoneado=np.array([z_binning_vect(alarma_block[i,:],ancho_zona)for i in range(ventana_alarma)]) #zoneo el bloque de alarmas
	z_score_block=(block_zoneado-avg)/std #calculo los z_scores
	
	#filtro con broadcast bool
	
	umbrales_matriz={}
	umbrales_cuenta={}
	matriz_umbrales=np.array([])
	
	for u in umbrales_porcentaje:
	
		umbrales_matriz[u]=np.where(z_score_block>u,1,0)#Matriz de 1 donde supera el umbral, 0 donde no
	
		umbrales_cuenta[u]=np.sum(umbrales_matriz[u],axis=0)#sumo por columna
	
		matriz_umbrales=np.append(matriz_umbrales,np.where(umbrales_cuenta[u]>(umbrales_porcentaje[u]*ventana_alarma),u,0)) #construye matriz con todas las filas por umbral para buscar maximo por filas
		
	matriz_umbrales=matriz_umbrales.reshape((len(umbrales_porcentaje.keys()),zonas))
	res[ventana_alarma,:]=np.max(matriz_umbrales,axis=0)#inicializo la primera fila
	
	filas_restantes=imagen_std.shape[0]-ventana_alarma-1
	for i in range(filas_restantes):
		fila_nueva_zoneada=z_binning_vect(imagen_std[ventana_alarma+i+1,:ultima_columna_multiplo],ancho_zona)
		res[ventana_alarma+i+1,:]=alarma_fila_nueva(fila_nueva_zoneada,umbrales_porcentaje,avg,std,umbrales_matriz,umbrales_cuenta)	
	
	
	return res

def nombre_avg(archivo):
    return '../AVG/'+archivo[:-3]+'avg'

def cargar_archivos(archivos_std,bins,bin_inicio=0,bin_fin=-1,norm=True):
    imagen_std_actual=cargar_archivo(archivos_std[0],bins,bin_inicio,bin_fin,norm)#cargo el primero
    for archivo in archivos_std[1:]:#cargo los restantes
        print os.path.getctime(archivo),os.path.getmtime(archivo)
        std_archivo=cargar_archivo(archivo,bins,bin_inicio,bin_fin,norm)        
        imagen_std_actual=np.vstack((imagen_std_actual,std_archivo))
    return imagen_std_actual

def cargar_archivo(archivo,bins,bin_inicio,bin_fin,norm):
    if norm:
        return np.reshape(np.fromfile(archivo,dtype=np.float32),(-1,bins))[:,bin_inicio:bin_fin]/np.reshape(np.fromfile(nombre_avg(archivo),dtype=np.float32),(-1,bins))[:,bin_inicio:bin_fin]
    else:
        return np.reshape(np.fromfile(archivo,dtype=np.float32),(-1,bins))[:,bin_inicio:bin_fin]

def z_binning_vect(data,window):
    binned_matrix=data.reshape(-1,(data.shape[0]/window),order='F')
    return binned_matrix.mean(0)

def zonear(data,ultima_multiplo,ancho_zona,filas):
    return np.array([z_binning_vect(data[i,:ultima_multiplo],ancho_zona)for i in range (filas)])

def cargar_linea_de_base(filename_base,bins,bin_inicio,bin_fin,ancho_zona,zonas,base_inicio=0,base_fin=-1,norm=True):

    linea_de_base=cargar_archivo(filename_base,bins,bin_inicio,bin_fin,norm)[base_inicio:base_fin,:]
    ultima_multiplo=ancho_zona*zonas
    base_zoneada=zonear(linea_de_base,ultima_multiplo,ancho_zona,linea_de_base.shape[0])
    mean_base=np.mean(base_zoneada,axis=0)
    std_base=np.std(base_zoneada,axis=0)
    return mean_base,std_base

def pantalla_nueva(archivos_std,archivo_actual,archivos_por_grafico,im_std,im_alarmas):
    imagen_std_actual=np.reshape(np.fromfile(archivos_std[archivo_actual],dtype=np.float32),(-1,bins))[:,bin_inicio:bin_fin]
    if norm:
        imagen_std_actual=imagen_std_actual/np.reshape(np.fromfile(nombre_avg(archivos_std[archivo_actual]),dtype=np.float32),(-1,bins))[:,bin_inicio:bin_fin]
    for archivo in archivos_std[archivo_actual+1:archivo_actual+archivos_por_grafico]:
		print 'Procesando archivo ', archivo 
		std_archivo=np.reshape(np.fromfile(archivo,dtype=np.float32),(-1,bins))[:,bin_inicio:bin_fin]      
		if norm:
                 std_archivo=std_archivo/np.reshape(np.fromfile(nombre_avg(archivo),dtype=np.float32),(-1,bins))[:,bin_inicio:bin_fin]
		imagen_std_actual=np.vstack((imagen_std_actual,std_archivo))
    im_std.set_data(imagen_std_actual)
    im_alarmas.set_data(encontrar_alarmas(imagen_std_actual,mean_base,std_base,umbrales_porcentaje,ventana_alarma,zonas,ancho_zona))
