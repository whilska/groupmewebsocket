import requests
import json
import websocket
import datetime
import time
import threading 

class GroupmeWebSocket:

	FAYE_URL = "https://push.groupme.com/faye"
	WSS_HOST = "wss://push.groupme.com/faye"
	TIMEOUT_SECONDS = 60

	# handler: the function which will handle the message json
	# access_token: token from dev.groupme.com
	# user_id: the groupme user_id associated with the access_token
	# client_id: groupme client_id retrieved from the handshake. Changes every ~10 minutes.
	# ws: the websocket object
	# id: request id, needs to be incremented with every call
	def __init__(self,handler,access_token,user_id):
		self.handler = handler
		self.access_token = access_token
		self.user_id = user_id
		self.client_id = None
		self.ws = None
		self.id = 0

	def __enter__(self):
		self.open_socket()
		return self

	def __exit__(self,exc_type,exc_value,traceback):
		self.close_socket()

	def post_to_faye(self,data):
		return requests.post(url=self.FAYE_URL,
			data=json.dumps(data),headers={"Content-type": "application/json"})

	# Increment id for every call, otherwise websocket connection won't open
	def __get_id(self):
		self.id += 1
		return self.id

	# Returns object for the initial handshake with Faye
	def handshake(self,connection_types=["websocket"]):
		return [
			{
				"channel": "/meta/handshake",
				"version": "1.0",
				"supportedConnectionTypes": connection_types,
				"id": self.__get_id()
			}
		]

	# Returns object for subscribing to user channel
	def subscribe(self):
		return [
		  {
		    "channel": "/meta/subscribe",
		    "clientId": self.client_id,
		    "subscription":"/user/{0}".format(self.user_id),
		    "id": self.__get_id(),
		    "ext": {"access_token": self.access_token}
		  }
		]

	# Object needed for socket request
	def poll(self,connection_type="websocket"):
		return [
		  {
		    "channel": "/meta/connect",
		    "clientId": self.client_id,
		    "connectionType": connection_type,
		    "id": self.__get_id()
		  }
		]

	# Creates & assigns the websocket object
	def open_socket(self):
		self.ws = websocket.create_connection(self.WSS_HOST,self.TIMEOUT_SECONDS)

	def close_socket(self):
		if self.ws is not None: self.ws.close()

	def is_socket_open(self):
		if self.ws is not None:
			return True
		else:
		 	return False

	def connect_to_faye(self):
		handshake = self.post_to_faye(self.handshake()).json()
		# Initial client_id is set here
		self.client_id = handshake[0].get("clientId")
		self.post_to_faye(self.subscribe())

	def listen_to_socket(self):
		if self.ws is None:
			return -1
		while self.ws.connected:
			try:
				recv = self.ws.recv()
				response = json.loads(recv)
			except websocket._exceptions.WebSocketConnectionClosedException as err:
				# Socket is closed, exit with -1
				return -1
			except json.decoder.JSONDecodeError as err:
				return -1
			if response[0].get("channel") == "/meta/connect":
				# Websocket needs to reconnect, client_id is reset
				self.client_id = response[0].get("clientId")
				self.ws.send(json.dumps(self.poll()))
			elif response[0].get("data").get("type") == "line.create":
				# New event, pass message JSON to handler
				self.handler(response)
			else:
				# Ping, do nothing
				pass
		return 0

	def run_1(self,seconds=60):
		end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
		self.connect_to_faye()
		self.ws.send(json.dumps(self.poll()))
		l_thread = threading.Thread(target=self.listen_to_socket)
		l_thread.start()
		while datetime.datetime.now() < end_time:
			# wait 1 second before checking the time again
			time.sleep(1)

	def run(self,seconds=3600):
		end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
		self.connect_to_faye()
		if self.is_socket_open(): 
			self.ws.send(json.dumps(self.poll()))
		else:
			# Method should not proceed if the websocket not been created
			return -1
		while (datetime.datetime.now() < end_time):
			try:
				response = json.loads(self.ws.recv())
			except websocket._exceptions.WebSocketConnectionClosedException as err:
				# Socket is closed, exit with -1
				return -1
			
			if response[0].get("channel") == "/meta/connect":
				# Websocket needs to reconnect, client_id is reset
				self.client_id = response[0].get("clientId")
				self.ws.send(json.dumps(self.poll()))
			elif response[0].get("data").get("type") == "line.create":
				# New event, pass message JSON to handler
				self.handler(response)
			else:
				self.handler(response)
				# pass
		return 0

# Testing purposes only
def test_handler(msg):
	print(str(msg))

if __name__ == '__main__':
	with GroupmeWebSocket(test_handler,"access_token","user_id") as gws:
		gws.run_1()