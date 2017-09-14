# -*- coding: utf-8 -*-
"""
Created on Tue Aug 29 13:28:24 2017

@author: YBL0548
"""

# -*- coding: utf-8 -*-

# en la linea de comandos ejeuctar esta linea para ver donde esta el multiplexor:
#python -m serial.tools.list_ports



import threading
import numpy as np
#import matplotlib as mpl
import matplotlib.pyplot as plt
import win32file, sys, time
import serial
import u3
import pickle
import datetime
import os.path
import msvcrt

#path='D:\\mediciones\\'+datetime.datetime.fromtimestamp(time.time()).strftime('%Y%m%d')+'\\'
#print path
#try:
#    os.makedirs(path)
#except:
#    print 'no pude crear el directorio'
path=''
nPerfilesPorFile=200# es el numero de perfiels que guarda por archivo    
pozos=['GBK980','GBK981','GBK982','GBK983']

def createFileName(path,term,pozo):
    timeStamp=datetime.datetime.fromtimestamp(time.time()).strftime('%Y_%m_%d__%H_%M_%S')
    nombreArchivo=path+pozos[pozo]+'_'+timeStamp+term
    return nombreArchivo

def init_file(filename,params):
    fid=open(filename,'wb')
    pickle.dump(params,fid,pickle.HIGHEST_PROTOCOL)
    return fid
def guardar_perfil(fid,data):#asume fid abierto como wb y data un array de numpy
    fid.write(data.tobytes())

#print "estoy corriendo este 20170815_06 ahora!!!!!!!!!!!"
#time.sleep(0.5)
#----------------

tam=int(sys.argv[1])
perfiles_por_pozo=int(sys.argv[2])
params={'bins':tam,
        'perfiles_por_pozo':perfiles_por_pozo,
        'secuencia_pozos':pozos} #hay que traer todos los parámetros desde C
x = np.arange(0, tam, 1)

rango_tension=0.2
#mpl.interactive(True)

figura1=plt.figure()
ax1=figura1.add_subplot(221)
linea1,=ax1.plot(np.zeros(tam))



ax2=figura1.add_subplot(222)
linea2,=ax2.plot(np.zeros(tam))


ax3=figura1.add_subplot(223)
linea3,=ax3.plot(np.zeros(tam))


ax4=figura1.add_subplot(224)
linea4,=ax4.plot(np.zeros(tam))



#ax1.set_ylim([0.5,2])
#ax2.set_ylim([0.5,2])
#ax3.set_ylim([0.5,2])
#ax4.set_ylim([0.5,2])

Tplotmin = -10
Tplotmax = 70

ax1.set_ylim([Tplotmin,Tplotmax])
ax2.set_ylim([Tplotmin,Tplotmax])
ax3.set_ylim([Tplotmin,Tplotmax])
ax4.set_ylim([Tplotmin,Tplotmax])
graficos={'GBK980':(ax1,linea1),'GBK981':(ax2,linea2),'GBK982':(ax3,linea3),'GBK983':(ax4,linea4)}

t0=58*5# traer el 58 que es el bin de referencia desde C o el script de inicio
T0=-5
dT=-6

#Offset = [12.7,3.83,8.24,26.77]
Offset = [0,0,0,0]
Multi = [0.1,0.009,0.03,0.12]
#Multi = [0,0,0,0]


def blocking():
	
    pipeDTS = win32file.CreateFile("\\\\.\\pipe\\pipeDTS",
                              win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                              0, None,
                              win32file.OPEN_EXISTING,
                              0, None)
    n=1

    ydata_prom=np.zeros(tam)
    Tprom=np.zeros(tam)
    ydata_acum=np.array([])
    pozo=0
    while True:
#        print 'entre en blocking\n'
		#lee un pipe.
        start=time.time()
        try:
            print 'esperando pipe'
            rr,rd = win32file.ReadFile(pipeDTS, tam*8)
            print 'lei un pipe del pozo ', pozo, 'n ',n
        except:
            print 'no pude leer el pipe'
            break

        ydata=np.frombuffer(rd,dtype=np.float64)
        kB=8.617*10**(-5)
        DE=0.05068
        dB=0.8676*10**(-5)
        ydata_prom+=ydata
        rT=ydata
        t=np.arange(tam)*5
        Tref=((T0+0.007)/0.00987)+273.15
        T=(1/Tref-kB/DE*(np.log(rT)+(t-t0)*dB+Multi[pozo]))**(-1)-273.15+Offset[pozo]
#        print T[1500]
        ydata=np.append(ydata,[T0,dT])
        Tprom+=T

        ydata_acum=np.concatenate((ydata_acum,ydata),axis=0)

        eje=graficos[pozos[pozo]]
        update(eje,Tprom,n)
        n+=1
        if n==(perfiles_por_pozo+1):
            n=1
            ydata_prom=np.zeros(tam)
            Tprom=np.zeros(tam)
            
            nombreArchivo=createFileName(path,'.dts',pozo)
            data_file=init_file(nombreArchivo,params)
            guardar_perfil(data_file,ydata_acum)
            print "Guarda ", np.shape(ydata_acum)[0]/(tam+2)," perfiles"
#            print "TEMP: ",((T0+0.007)/0.00987),'+/-',(dT/0.00987)
            data_file.close()
            
            pozo=(pozo+1)%4
            ydata_acum=np.array([])
            resaltar_nuevo(graficos[pozos[(pozo-1)%4]][0],graficos[pozos[pozo]][0])
        print "Tiempo entre pipes ",(time.time()-start), " seg" 

    plt.close('all')
    print "CHAU BLOCKING"
            
def update((ax,linea),ydata,n):
    linea.set_ydata(ydata/float(n))
#    print np.min(ydata/float(n))
#    ax.set_ylim([np.min(ydata),np.max(ydata)])
    ax.set_title("Perfil nro "+str(n)+"(T: "+str((T0+0.007)/0.00987)+")")
    ax.figure.canvas.draw()

def resaltar_nuevo(ax_old,ax_new):
    posiciones=['bottom','top','right','left']
    for p in posiciones:
        ax_old.spines[p].set_color('black')
        ax_new.spines[p].set_color('red')


def cambio_pozo():
    ser = serial.Serial( 
    	    port='COM3',
    	    baudrate=9600,
    	    parity=serial.PARITY_NONE,
    	    stopbits=serial.STOPBITS_ONE,
    	    timeout=2,
    	    writeTimeout=100,
    	    bytesize=serial.EIGHTBITS
    	)
    time.sleep(2)	
    pipeRead=win32file.CreateFile("\\\\.\\pipe\\pipePozoCWrite",
                    win32file.GENERIC_READ ,#verificar el nombre que tiene este pipe en C
                    0,None,
                    win32file.OPEN_EXISTING,
                    0,None)
    pipeWrite=win32file.CreateFile("\\\\.\\pipe\\pipePozoCRead",
                    win32file.GENERIC_WRITE ,#verificar el nombre que tiene este pipe en C
                    0,None,
                    win32file.OPEN_EXISTING,
                    0,None)
    pozo=0
    while(True):
        try:
            print 'esperando cambio pozo'
            err,data=win32file.ReadFile(pipeRead,17)
        except:
            print 'problemas leyendo el pipe'
            break
        ser.write(bytearray([0x01, 0x12,0x00,0x01+pozo])) #mandar 0x00 en el ultimo valor cuelga el multiplexer
        pozo= (pozo+1)%4
        try:
            win32file.WriteFile(pipeWrite,"OK")
        except:
            break
           
    ser.close()
    print 'CHAU MULTIPLEX '


th=threading.Thread(target=cambio_pozo, args=())
th.setDaemon(True)
th.start()





#T0=0.1
# comento todo lo referido a la labjack
T0=0
dT=0
cerrar_labjack=threading.Event()
def leeTemp():
    global T0
    global dT
    SCAN_FREQUENCY = 1000
    d = u3.U3()
    d.configIO(FIOAnalog = 0b11111111)
    d.streamConfig(NumChannels=1, PChannels=[4], NChannels=[31], Resolution=0, ScanFrequency=SCAN_FREQUENCY)
#    while(not cerrar_labjack.is_set()):        
    try:
        d.streamStart()
    except:
        d.streamStop()
        d.streamStart()
        #start = datetime.now()
    for r in d.streamData():
        if (not cerrar_labjack.is_set()):
            T0=sum(r["AIN4"])/len(r["AIN4"])*1.0123+2.504E-3
            dT=np.std(np.array(r["AIN4"])*1.0123+2.504E-3)
#            print "TEMP: ",((T0+0.007)/0.00987),'+/-',(dT/0.00987)
#            print ((T0+0.007)/0.00987)
#            print (dT/0.00987)
            
        
        
#            print 'apretar ESC para cerrar labjack despues de cerrar c. . . '
        else:
            d.streamStop()
            d.close()
            break
        
th1=threading.Thread(target=leeTemp, args=())
th1.setDaemon(True)
th1.start()
th2=threading.Thread(target=blocking, args=())
th2.setDaemon(True)
th2.start()


#def cerrar_labjack_th():
#    while(1):
#        key=ord(msvcrt.getch())
#        if key==27: #aprieta ESC
#            cerrar_labjack.set()
#            th1.join()
#            print "Liberada la labjack. Cerrar grafico para salir"
#            break
#th3=threading.Thread(target=cerrar_labjack_th, args=())
#th3.setDaemon(True)
#th3.start()    

plt.show()
cerrar_labjack.set()
th1.join()
print "CHAU LABJACK"
th2.join()
th.join()

