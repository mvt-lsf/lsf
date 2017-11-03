from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import cgi
import requests
import simplejson
import threading
import datetime
import yagmail
import time

def send_alarm(equipo):
	print 'se rompio: ', equipo
	yag=yagmail.SMTP('alarmatodoestabien','milanesa')
	destinatarios=['dkunik@gmail.com','edomene@gmail.com','mvargastelles@undav.edu.ar']
	contents = equipo + ' OFF'
	yag.send(to=destinatarios, subject='Alertas GBK y demases', contents=[contents])	

equipos_validos=['GBK_DTS']
last_uptime={}
primera_conexion=True
sent_mail=False
for eq in equipos_validos:
	last_uptime[eq]=datetime.datetime.now()
	
def alerta_mail():
	global sent_mail
	print 'empieza monitoreo con mail'
	min_thresh_interval=[10,20,30,60,180]
	current_th=0
	while(True):
		time.sleep(min_thresh_interval[current_th]*60)
		time_ref=datetime.datetime.now()
		for equipo in equipos_validos:
			if (time_ref-last_uptime[equipo]).seconds>min_thresh_interval[0]*60:
				if not sent_mail:
					sent_mail=True
					current_th=0
				send_alarm(equipo)
				if current_th<len(min_thresh_interval)-1:
					current_th+=1


		

class Handler(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.end_headers()
    def do_POST(self):
    	global primera_conexion,sent_mail
        self._set_headers()
        print "in post method"
        self.data_string = self.rfile.read(int(self.headers['Content-Length']))
        data = simplejson.loads(self.data_string)
        for key in data:
			if key in equipos_validos:
				if primera_conexion:
					primera_conexion=False
					th=threading.Thread(target=alerta_mail)
					th.start()	
				last_uptime[key]=datetime.datetime.now()
				if sent_mail:
					sent_mail=False


port=8081
server = HTTPServer(('', port), Handler)
server.serve_forever()
