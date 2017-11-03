import requests
import time

url = 'http://pinierobck.ddns.net:8081'
equipo='GBK_DTS'
payload = {equipo: 'OK'}
headers = {'content-type': 'application/json'}
user=
proxy={'http':'http://'+user+'@proxy-ypf:80'}
seg_update=120
while(True):
	try:
		r = requests.post(url, json=payload,proxies=proxy)
		print 'Status',r.status_code
	except:
		print 'No hay server aun'
		pass
	time.sleep(seg_update)
#response = requests.post(url, data=json.dumps(payload), headers=headers)
