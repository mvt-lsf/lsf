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
for eq in equipos_validos:
	last_uptime[eq]=datetime.datetime.now()
	
def alerta_mail():
	print 'empieza monitoreo con mail'
	seg_thresh=10*60
	while(True):
		time.sleep(seg_thresh)
		time_ref=datetime.datetime.now()
		for equipo in equipos_validos:
			if (time_ref-last_uptime[equipo]).seconds>seg_thresh:
				send_alarm(equipo)


		

class Handler(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.end_headers()
    def do_POST(self):
    	global primera_conexion
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


port=8081
server = HTTPServer(('', port), Handler)
server.serve_forever()
