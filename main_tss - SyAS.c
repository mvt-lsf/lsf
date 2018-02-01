#include <stdio.h>
#include <windows.h>
#include <stdlib.h>
#include <string.h>
#include "WD-dask64.h"
// renombra algunos parámetros de la placa para usarlos en las funciones. los de la derecha significan algo para la placa
#define TIMEBASE      WD_IntTimeBase
#define ADTRIGSRC     WD_AI_TRGSRC_ExtD
//#define ADTRIGSRC     WD_AI_TRGSRC_SOFT
#define ADTRIGMODE    WD_AI_TRGMOD_DELAY
#define ADTRIGPOL     WD_AI_TrgPositive
#define BUFAUTORESET  1

#define CARDNUM 0
#define CHUNKS 20
#define CONSUMIDORES 1
#define TS_SIZE 13
#define TS_FORMAT "%y%m%d%H%M%S"

HANDLE pipePozoCWrite;
HANDLE pipePozoCRead;
HANDLE pipeDTS;




typedef enum { false, true } bool;


// en la estructura callback estamos juntamos todas las variables externas que utiliza la funciòn AI_CallBack
short* chkBuffer;

bool salir=false;
bool salir2=false;
bool finThreads=false;



struct {
    int nCh;
    int bins;
    int nShotsChk;
    int chkActual;
    bool bufferActual;
    short* ai_buf;
    short* ai_buf2; // este es un puntero short porque los elementos del buffer de la placa son shorts, cuando lo indexemos se va a mover de a un short en memoria, de forma de ir pasando de elemento a elemento.
    bool disponible[CHUNKS];
    bool ovr;
    int contadorPozo; // contador: indica en que chunk estamos para este pozo
    int chunksPorPozo;// cantiad de chunks por Pozo
    int chunks_por_perfil;
    time_t * tss; //timestamps
    int indice_tss;
    int size_tss;
    bool pausa; // este indica si esteamos eperando que se ejecute el cambio de pozo
    HANDLE cambio_pozo; // defini un envento para avisar que se debe cambiar de pozo
    HANDLE semConsumidor[CONSUMIDORES];
}callback;
/* se definen como globales los tipos de datos que utilizan los procesos. Los porcesos no admiten ningún tipo de argumento
 porque es un creador de una función, tiene que ser capaz de poder ejecutar culaquier cosa. Lo que se hace es pasarle un puntero a void y en esa dirección se
 cargan todos los parámetros que necesita el proceso. La única alternativa es tener todas las variables del proceso como globales. Una vez definido el tipo
 cuando se lanza el proceso se crea un estructura particular del tipo correspondiente y se le pasa la dirección de memoria al proceso. dentro del proceso
 se accede a las variables*/

typedef struct th_data{
    int bins;
    int nChkP;
    int nShotsChk;
    int nCh;
    int nRef;
}th_data;

typedef struct th_Matriz{
    int bins;
    int nChkP;
    int nShotsChk;
    int nCh;
    int nRef;
    double **acumula;
    double **acumula2;
	int *nZ1;
	int *nZ2;
    HANDLE  semMatriz;
}th_Matriz;



void AI_CallBack(){
// sino está en pausa ejecuta normal, está en pausa mientras espera el cambio de pozo
    if (callback.contadorPozo%100==0)   printf("Callback chunk %d/%d\n",callback.contadorPozo,callback.chunksPorPozo);
    if(!callback.pausa){
        short* bufferPlaca;

    // le pasamos la dirección de memoria del primer elemento del buffer donde escribió la placa
        if (callback.bufferActual){
                bufferPlaca=callback.ai_buf;
        }else{
                bufferPlaca=callback.ai_buf2;
        }


        //WaitForSingleObject(pmut, INFINITE);
        if(!callback.disponible[callback.chkActual] ) {
            //ReleaseMutex(pmut);
            callback.ovr=true;
            WD_AI_ContBufferReset (CARDNUM);
            WD_Buffer_Free (CARDNUM, callback.ai_buf);
            WD_Buffer_Free (CARDNUM, callback.ai_buf2);
            WD_Release_Card(CARDNUM);
            //return;
        }
        else{
			callback.disponible[callback.chkActual]=false;

            memcpy(chkBuffer+callback.bins*(callback.nCh)*callback.chkActual*callback.nShotsChk,bufferPlaca,callback.bins*callback.nCh*callback.nShotsChk*sizeof(I16)); ///copia 2 canales



        }

      //printf("productor pasa un chunk\n");


        callback.chkActual=(callback.chkActual+1)%CHUNKS;
        callback.bufferActual=!callback.bufferActual;
        callback.contadorPozo++;
        if (callback.contadorPozo%callback.chunks_por_perfil==0){

				time(callback.tss[callback.indice_tss]);
				callback.indice_tss= (callback.indice_tss+1) %callback.size_tss;
        }
        
        DWORD semCount;
        ReleaseSemaphore(callback.semConsumidor[0],1,&semCount); ///semaforo para consumidor

       //s printf("Contador pozo %d de chunk por pozo %d \n",callback.contadorPozo,callback.chunksPorPozo);
        if (callback.contadorPozo==callback.chunksPorPozo){
            callback.contadorPozo=0;
            printf("voy a setear el evento\n");
            SetEvent(callback.cambio_pozo); //sucedió el evento
          //  printf("setie el evento\n");
            callback.pausa=true; //se setea en true para esperar que se consuma el cambio de pozo
        }
    }
	return;
}



void* cambio_de_pozo(void* n){

    char* buffer=calloc(3,sizeof(char)); // crea el string y lo inicializa es un malloc inicializado con 0
    char* cambio="CAMBIAME EL POZO"; // string a enviar a python
    //lanzar proceso de cambio de pozo en python
    ConnectNamedPipe(pipePozoCRead,NULL);

    while(true){
        //printf("vivito y coleando\n");
        WaitForSingleObject(callback.cambio_pozo,INFINITE);
        printf("por favor Cambia el pozo\n");
        DWORD leido_pipe,leido_pipe2;
        WriteFile(pipePozoCWrite,cambio,sizeof(char)*17,&leido_pipe,NULL);
        printf("ya escribi en el pipe cambia pozo\n");
        ReadFile(pipePozoCRead,buffer,sizeof(char)*3,&leido_pipe2,NULL);
        printf("ya lei en el pipe cambia pozo\n");
        printf("%s\n",buffer);
        if(strcmp(buffer,"OK")==0){// habia un 0
            callback.pausa=false;
            memset(buffer,0,10);
        }else{
            printf("Falla multiplexer.\n");
        }

    }


}


void adquirir(short nCh, int qFreqAdq, int rangoDinCh1,int rangoDinCh2, int bins, int nShotsChk, int delay) {
    /* configura la placa pasando el nùmero de canales, el entero por el que se divide la freq de adquisiciòn màxima.
    qFreqAdq 1, 2,3,.......,2^16
     rangoDin 0,1,2 equivale a +-0.2V +-2V y +-10V
     Además configura los buffers de la RAM a la que la placa transfire los datos aibuf1 y aibuf2.
     Configura triggres, bufferes de la placa. WD_AI_ContBufferSetup y WD_Buffer_Alloc
     inicia la adquisiciòn
    */


//variables placa
	I16 Id,Id2, card;//son requeridas por funciones de la placa para almacenar cosas. son de uso exclusivo de las funciones de la placa
	U16 card_type=PCIe_9852;
	U16 card_num=0; //arranca en 0, en esta compu habìa dos placas la 0 y la 1.

	if ((card=WD_Register_Card (card_type, card_num)) <0 ) {
		printf("Register_Card error=%d", card);
		exit(1);
	}
	//----------------------------------
	// ai_buf y ai_buf2
	// configura los buffers de la ram donde se transfieren los datos de la placa
	int puntosChk=nCh*bins*nShotsChk;
	int tamBuffer =puntosChk*sizeof(I16);
  short* ai_buf = WD_Buffer_Alloc (card, tamBuffer);//direcciòn de memoria del buffer de la ram utilizado por la placa para descargar los datos.
   //lo tiene que utilizar el callback que vaya a buscar los datos por lo que tine que ser global. Hay un buffer en la ram por cada buffer en la placa.
   if(!ai_buf)
   {
	   printf("buffer1 allocation failed\n");
	   exit(1);
   }
  short* ai_buf2 = WD_Buffer_Alloc (card, tamBuffer);
   if(!ai_buf2)
   {
	   printf("buffer22 allocation failed\n");
	   WD_Buffer_Free (card, ai_buf);
	   exit(1);
   }
   //-----------------------------
//configura buffer en la placa

  I16 err=WD_AI_ContBufferSetup (card, ai_buf, puntosChk, &Id);
   if (err!=0) {
       printf("P9842_AI_ContBufferSetup 0 error=%d", err);
	   WD_Buffer_Free (card, ai_buf);
	   WD_Buffer_Free (card, ai_buf2);
	   WD_Release_Card(card);
       exit(1);
   }
   err=WD_AI_ContBufferSetup (card, ai_buf2, puntosChk, &Id2);
   if (err!=0) {
       printf("P9842_AI_ContBufferSetup 0 error=%d", err);
	   WD_AI_ContBufferReset (card);
	   WD_Buffer_Free (card, ai_buf);
	   WD_Buffer_Free (card, ai_buf2);
	   WD_Release_Card(card);
       exit(1);
   }
   // seteamos impedancia y rango dinàmico de los canales
   U16 rango1,rango2;
   switch(rangoDinCh1){
   case 0:
      rango1=AD_B_0_2_V;//+-200mV
      break;
   case 1:
       rango1=AD_B_2_V;//+-2V
       break;
   case 2:
        rango1=AD_B_10_V;//+-10V
   }
   switch(rangoDinCh2){
   case 0:
      rango2=AD_B_0_2_V;//+-200mV
      break;
   case 1:
       rango2=AD_B_2_V;//+-2V
       break;
   case 2:
        rango2=AD_B_10_V;//+-10V
   }

	WD_AI_CH_ChangeParam(card,-1,AI_IMPEDANCE,IMPEDANCE_50Ohm);/// card number,channel,channel setting,setting value
	WD_AI_CH_ChangeParam(card,0,AI_RANGE,rango1);/// card number,channel,setting,setting value
    WD_AI_CH_ChangeParam(card,1,AI_RANGE,rango2);
//----------------------------------------------------

//ver en el manual de la placa esta funciòn
   err = WD_AI_Config (card, TIMEBASE, 1, WD_AI_ADCONVSRC_TimePacer, 0, BUFAUTORESET);
   if (err!=0) {
       printf("WD_AI_Config error=%d", err);
	   WD_Buffer_Free (card, ai_buf);
	   WD_Buffer_Free (card, ai_buf2);
	   WD_Release_Card(card);
       exit(1);
   }
   //------------------------------------------
   //configuraciòn del trigger

   err = WD_AI_Trig_Config (card, ADTRIGMODE, ADTRIGSRC, ADTRIGPOL, 0, 0.0, 0, 0, delay, 0);
   if (err!=0) {
       printf("WD_AI_Trig_Config error=%d", err);
	   WD_Buffer_Free (card, ai_buf);
	   WD_Buffer_Free (card, ai_buf2);
	   WD_Release_Card(card);
       exit(1);
   }

//----------------------------------------------------
// Configura el callBack. El evento es que se llenó el buffer de la placa. TrigEvent haría otra cosa según el manual, pero con este funciona y con que sugiere el manual no
//el callback es el productor trae los datos del buffer de la ram reservado para la placa a los chunks. Por eso recibe tambièn los semàforos de los consumidores
    callback.bins=bins;
    callback.nCh=nCh;
    callback.nShotsChk=nShotsChk;
    callback.ai_buf=ai_buf;
    callback.ai_buf2=ai_buf2;
    callback.bufferActual=true;
    callback.chkActual=0;
    callback.cambio_pozo=CreateEvent(NULL,false,false,NULL);
    SetEvent(callback.cambio_pozo);
    callback.pausa=true;
    callback.contadorPozo=0;
    DWORD pozoID;
    _beginthreadex(NULL, 0, (unsigned int(__stdcall *)(void*))cambio_de_pozo,
	0, 0, pozoID);
//inicializa disponible
    int i;
    for(i=0;i<CHUNKS;++i)callback.disponible[i]=true;
//----------------
//reserva memoria para  los chunks: short* chkBuffer

// creamos semáforos
callback.semConsumidor[0]=CreateSemaphore(NULL,0,CHUNKS,NULL);


	err = WD_AI_EventCallBack_x64(card, 1, TrigEvent, (U32) AI_CallBack);
	if (err!=0) {
		printf("WD_AI_EventCallBack error=%d", err);
		WD_AI_ContBufferReset (card);
		WD_Buffer_Free (card, ai_buf);
	   WD_Buffer_Free (card, ai_buf2);
		WD_Release_Card(card);
		exit(1);
	}

//--------------------------------------------
//start adquisition
    err = WD_AI_ContScanChannels (card, nCh-1, 0, bins, qFreqAdq, qFreqAdq, ASYNCH_OP); //aca puede ser read por scan

    if (err!=0) {
        printf("AI_ContScanChannels error=%d", err);
        WD_AI_ContBufferReset (card);
        WD_Buffer_Free (card, ai_buf);
	   WD_Buffer_Free (card, ai_buf2);
        WD_Release_Card(card);
        exit(1);
    }
}


    /*este es un proceso hijo del proceso que procesa los datos.*/
void *procesaMatriz(void* n){
    double **acumuladora;// decia short
    int bins=(*(th_Matriz *)n).bins;
    int nChkP=(*(th_Matriz *)n).nChkP;
    int nShotsChk=(*(th_Matriz *)n).nShotsChk;
	int *nZ;

    double *acumulado=malloc(bins*sizeof(double));


    bool matrizSwitch = true;
    // ver la carga del pipe
    /*HANDLE pipe = CreateNamedPipe(TEXT("\\\\.\\pipe\\pipeDTS"),
                                PIPE_ACCESS_DUPLEX | PIPE_TYPE_BYTE | PIPE_READMODE_BYTE,   // FILE_FLAG_FIRST_PIPE_INSTANCE is not needed but forces CreateNamedPipe(..) to fail if the pipe already exists...
                                PIPE_WAIT,
                                1,
                                bins*sizeof(double)*2,
                                bins*sizeof(double)*2,
                                NMPWAIT_USE_DEFAULT_WAIT,
                                NULL);*/
    DWORD leido_pipe;
 /*   char command[100];
    snprintf(command,100,"start python simple_plot.py %d ",bins);
    printf(command);
    system(command);*/ //lo paso al main
    int j;
    int i;

	int indice_tss=0;
	char buffer_ts[13];
    while(!salir){
        if(matrizSwitch){
                acumuladora=(*(th_Matriz *)n).acumula;
                nZ=(*(th_Matriz *)n).nZ1;
        }
           else  {
                acumuladora=(*(th_Matriz *)n).acumula2;
                nZ=(*(th_Matriz *)n).nZ2;
           }
       // memset(acumulado,0,bins*sizeof(double));
        for(i=0;i<bins;i++)acumulado[i]=0;
        WaitForSingleObject((*(th_Matriz *)n).semMatriz, INFINITE);
        //printf("llego una matriz para colapsar a procesaMatriz\n revisamos acumulado: %d \n",acumulado[20]);
        for(j=0;j<nChkP*bins;j++){
                //acumulado[j%bins]+=acumuladora[j/bins][j%bins];
                int indice01=j%bins;
                //printf("indice01: %d \n",indice01);
                acumulado[indice01]+=acumuladora[j/bins][j%bins];
        }
	for(j=0;j<bins;j++){
		acumulado[j]/=nZ[j];
		//printf("%d\n",nZ[j]);
	}
        //for(j=0;j<bins;j++)acumulado[j]/=(nChkP*nShotsChk);

		strftime (buffer_ts,TS_SIZE,TS_FORMAT,localtime(&callback.tss[indice_tss]));
		printf("NOW: %s\n",buffer_ts);

		indice_tss= (indice_tss+1) %callback.size_tss;

        WriteFile(pipeDTS,&acumulado[0],sizeof(double)*bins,&leido_pipe,NULL);
        WriteFile(pipeDTS,buffer_ts,TS_SIZE,&leido_pipe,NULL);
        //printf("%.8f\t %.8f \t%.8f\n",acumulado[0],acumulado[50],acumulado[100]);
        printf("ESCRIBI EN EL PIPE\n");
        matrizSwitch=!matrizSwitch;
    }
    free(acumulado);CloseHandle(pipeDTS);
    salir2=true;
    return NULL;

}



void *procesaDTS_01(void* n){
    //Esta función sólo sirve para la adquisicióln de 2Chns
    /* Esto es lo que hay en el main.
    th_data DatosThread; // crea una estructura del tipo th_data
    DatosThread.bins=bins;
    DatosThread.nChkP=nChkP;
    DatosThread.nRef=norm1;
    DatosThread.nShotsChk=nShotsChk;

        DWORD dtsID;
        _beginthreadex(NULL, 0, (unsigned int(__stdcall *)(void*))procesaDTS_01,
        (void*)&DatosThread, 0, (unsigned int *)&dtsID);*/


    int i;

    int bins=(*(th_data *)n).bins;
    int nChkP=(*(th_data *)n).nChkP;
    int nShotsChk=(*(th_data *)n).nShotsChk;
    int nCh=(*(th_data *)n).nCh;
    int nRef=(*(th_data *)n).nRef;
    short *chkActual=chkBuffer;
    printf("Params: bins:%d nChkP:%d nShots:%d nCh:%d nRef:%d \n",bins,nChkP,nShotsChk,nCh,nRef);

    /* reserva memoria para las matrices en las que vamos a acumular los chunks. Se procesan bloques de nChP
    chunks que se van guardando en las filas de la matriz acumula o acumula 2. Usamos dos matrices para que mientras se escribe en una se pueda procesar la otra
    Como el procesamiento final se hace al final del ciclo esto desbalancea el loop y puede hacer que el proceso se retrace y se acumulen chunks. Para evitar eso
    el procesamiento final lo va a hacer otro proceso. procesaDTS_01 baja los chunks hace el acumulado de ese chk y lo guarda en una fila de acumula o acumula 2.
    Cuando la matrir1z se completa mediante un semáforo, le avisa al proceso hijo que tiene una matriz para procesar y sigue consumiendo chk.*/
    double **acumula=malloc(nChkP*sizeof(double*)); //reserba un arreglo de punteros, cada uno de ellos va a tener bins punteros (ver la asignaciòn de acumuladora)
    double **acumula2=malloc(nChkP*sizeof(double*));
	int *nZ1=malloc(bins*sizeof(int));
	int *nZ2=malloc(bins*sizeof(int));
    double **acumuladora;
    int *nZ;
    bool matriz=true;
    for(i=0;i<nChkP;i++)acumula[i]=malloc(bins*sizeof(double));
    for(i=0;i<nChkP;i++)acumula2[i]=malloc(bins*sizeof(double));
    int j;
    int nChk=0;
    int k;
    DWORD ccount;
    HANDLE semMatriz=CreateSemaphore(NULL,0,2,NULL);//este semàforo le va a avisar al proceso hijo procesaMatriz que tiene una matriza para procesar.


    th_Matriz datosMatriz; // crea una estructura del tipo th_Matriz

    datosMatriz.bins=bins;
    datosMatriz.nChkP=nChkP;
    datosMatriz.nRef=nRef;
    datosMatriz.nShotsChk=nShotsChk;
    datosMatriz.nCh=nCh;
    datosMatriz.acumula=acumula;
    datosMatriz.acumula2=acumula2;
    datosMatriz.semMatriz=semMatriz;
	datosMatriz.nZ1=nZ1;
	datosMatriz.nZ2=nZ2;

	DWORD dtsID;
	_beginthreadex(NULL, 0, (unsigned int(__stdcall *)(void*))procesaMatriz,
	(void*)&datosMatriz, 0, (unsigned int *)&dtsID);
    for(i=0;i<nChk;i++){
            for(j=0;j<bins;j++)acumula[i][j]=0;
    }
    for(i=0;i<nChk;i++){
            for(j=0;j<bins;j++)acumula2[i][j]=0;
    }
    while(!salir2){
        if(matriz){acumuladora=acumula;
        nZ=nZ1;
        }
           else {acumuladora=acumula2;
           nZ=nZ2;
           }
        for(i=0;i<nChkP;i++){
            for(j=0;j<bins;j++)acumuladora[i][j]=0;
        }
        //printf("revisamos acumuladora: %d \t %d \n",acumuladora[1][10],acumuladora[3][30]);
		for(j=0; j<bins;j++)nZ[j]=0;
		for(i=0;i<nChkP;i++){
    /*para el i-esimo chunk*/
            WaitForSingleObject(callback.semConsumidor[0], INFINITE);//epsera un chunk para procesar.
            /*recorre el chunk shot por shot para hacer la normalizaciòn. */
            //printf("\n llego el chunk i: %d\n ",i);
                    for(k=0;k<nShotsChk;++k){
                        int indice=k*bins*2; //inicio del k-esimo shot en chunkActual nCh es el nùmero de canales

                        short refAs=chkActual[indice+nRef*nCh];//chkActual apunto al inicio dle Chk
                        short refS=chkActual[indice+nRef*nCh+1];
                        for(j=0;j<bins*nCh;j+=2){
                           //acumuladora[i][j/2]+=(double)(chkActual[indice+j+1]);
                        //if(chkActual[indice+j+1]) acumuladora[i][j/2]+=(double)(chkActual[indice+j])/(double)(chkActual[indice+j+1]);
                          // if(chkActual[indice+j+1]) acumuladora[i][j/2]+=(double)(chkActual[indice+j]*refS)/(double)(chkActual[indice+j+1]*refAs);
						  //acumuladora[i][j/2]+=(double)(chkActual[indice+j+1]);
						  if((chkActual[indice+j+1]*refAs)!=0){
                            acumuladora[i][j/2]+=(double)(chkActual[indice+j]*refS)/(double)(chkActual[indice+j+1]*refAs);

                           ///if((refAs)!=0){
                            //acumuladora[i][j/2]+=(double)(chkActual[indice+j+1]);
                           ///acumuladora[i][j/2]+=(double)(chkActual[indice+j])/(double)(refAs);
                           nZ[j/2]++;
						   }
						}
                    }
                    /*acà actualizamos chunkActual. nCh es el nùmero del chunk actual. Calculamos el mòdulo de dividir por el nùmero de chunks (CHUNKS) y multimplicamos eso por el nùmero de elementos
                    en un chunk el resultado se lo sumamos a chkbuffer. Asì nos ahorramos un if ver comentario màs abajo*/
                    callback.disponible[nChk]=true;// avisa que al productor que ya puede escribir en el nChk-esimo chk
                    nChk=(nChk+1)%CHUNKS;
                    chkActual=chkBuffer+bins*nShotsChk*nCh*nChk;
                    //chkActual=chkBuffer+bins*nShotsChk*nCh*nChk;

           // if (chActual==chkBuffer+bins*nShotsChk*nCh*CHUNKS)chkActual=chkBuffer;
        }
        matriz=!matriz; //niego matriz para que el pròximo chunk se procese en la matriz disponible
        printf("paso una matriz para colapsar\n");
        ReleaseSemaphore(semMatriz,1,&ccount);// le avisamos al proceso que colapsa la matriz que tiene una matriz disponible

    }

    for(i=0;i<nChkP;i++)free(acumula[i]);
    for(i=0;i<nChkP;i++)free(acumula2[i]);
    free(acumula);free(acumula2);
	free(datosMatriz.nZ1);
	free(datosMatriz.nZ2);
    finThreads=true; CloseHandle(dtsID);
    return NULL;
}

int main(int argc, char* argv[])
{

    int nShotsChk=atoi(argv[1]); //numreo de shots por chunk
    int bins=atoi(argv[2]);// numero de bines por shot màs de 80 y m`yltiplo de 8
    int nChkP=atoi(argv[3]);//numero de chunk a procesar
    int norm1=atoi(argv[4]);
    int norm2=atoi(argv[5]);//rango para normalizar
    long nShots=atol(argv[6]);//shots a adquirir
    int delay=atoi(argv[7]);
    short qFreq=atoi(argv[8]);
    int r1=atoi(argv[9]);
    int r2=atoi(argv[10]);
    int perfiles_por_pozo=atoi(argv[11]);

    callback.chunks_por_perfil=nChkP; //para timestamp
    callback.chunksPorPozo=perfiles_por_pozo*nChkP;
    int size_tss;
    if(nChkP<CHUNKS){
		size_tss=(int)ceil((double)CHUNKS/nChkP);//demostrar que esto no se rompe i.e que si el perfil se pudo crear, el timestamp correspondiente se puede pisar. Vale cuando CHUNKS es multiplo de nchkp(cambiar nombre urgente)
	}else{
		size_tss=2;
    }
    callback.size_tss=size_tss;
    callback.tss=malloc(sizeof(time_t)*size_tss);
    callback.indice_tss=0;

    //define los pipe para hablar con python respecto del cambio de pozo
    pipePozoCWrite = CreateNamedPipe(TEXT("\\\\.\\pipe\\pipePozoCWrite"),
                                PIPE_ACCESS_OUTBOUND | PIPE_TYPE_BYTE | PIPE_READMODE_BYTE,   // FILE_FLAG_FIRST_PIPE_INSTANCE is not needed but forces CreateNamedPipe(..) to fail if the pipe already exists...
                                PIPE_WAIT,
                                1,
                                100,
                                100,
                                NMPWAIT_USE_DEFAULT_WAIT,
                                NULL);
     pipePozoCRead = CreateNamedPipe(TEXT("\\\\.\\pipe\\pipePozoCRead"),
                                PIPE_ACCESS_INBOUND | PIPE_TYPE_BYTE | PIPE_READMODE_BYTE,   // FILE_FLAG_FIRST_PIPE_INSTANCE is not needed but forces CreateNamedPipe(..) to fail if the pipe already exists...
                                PIPE_WAIT,
                                1,
                                100,
                                100,
                                NMPWAIT_USE_DEFAULT_WAIT,
                                NULL);
    pipeDTS = CreateNamedPipe(TEXT("\\\\.\\pipe\\pipeDTS"),
                                PIPE_ACCESS_DUPLEX | PIPE_TYPE_BYTE | PIPE_READMODE_BYTE,   // FILE_FLAG_FIRST_PIPE_INSTANCE is not needed but forces CreateNamedPipe(..) to fail if the pipe already exists...
                                PIPE_WAIT,
                                1,
                                (bins*sizeof(double)+TS_SIZE)*20,
                                (bins*sizeof(double)+TS_SIZE)*20,
                                NMPWAIT_USE_DEFAULT_WAIT,
                                NULL);

	char command[100];
    snprintf(command,100,"start cmd /k python graficar.py %d %d",bins,perfiles_por_pozo);
    system(command);

    chkBuffer=malloc(bins*nShotsChk*2*CHUNKS*sizeof(short));

    th_data DatosThread; // crea una estructura del tipo th_data

    DatosThread.bins=bins;
    DatosThread.nCh=2;
    DatosThread.nChkP=nChkP;
    DatosThread.nRef=norm1;
    DatosThread.nShotsChk=nShotsChk;

    /*llama la funciòn adquirir desde donde se lanzan el productor y se setea el resto del callback*/
    adquirir(2,qFreq,r1,r2,bins,nShotsChk,delay);
    /*lanza el proceso procesaDTS_01 (el consumidor)*/
        DWORD dtsID;
        _beginthreadex(NULL, 0, (unsigned int(__stdcall *)(void*))procesaDTS_01,
        (void*)&DatosThread, 0, (unsigned int *)&dtsID);
    /*--------------------------*/


    while(!kbhit() || getch() != 's'){
            Sleep(500);
    }

    while(!finThreads) Sleep(500);

    free(chkBuffer);
    WD_Release_Card(0);
    CloseHandle(dtsID);

    return 0;
}
