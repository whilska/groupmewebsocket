import requests
import json
import websocket
import datetime
import time
import threading
import sys

__all__ = ["GroupmeWebSocket"]


class GroupmeWebSocket:
	FAYE_URL = "https://push.groupme.com/faye"
	GET_ME_URL = "https://api.groupme.com/v3/users/me"
	WSS_HOST = "wss://push.groupme.com/faye"
	TIMEOUT_SECONDS = 60

	# handler: the function which will handle the message json
	# access_token: token from dev.groupme.com
	# user_id: the groupme user_id associated with the access_token
	# client_id: groupme client_id retrieved from the handshake. Changes every ~10 minutes.
	# ws: the websocket object
	# id: request id, needs to be incremented with every call
	def __init__(self, handler, access_token, debug=False):
		self.handler = handler
		self.user_id = self.get_user_id(access_token)
		self.access_token = access_token
		self.client_id = None
		self.ws = None
		self.id = 0
		self.debug = debug

	def __enter__(self):
		self.open_socket()
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		self.close_socket()

	def post_to_faye(self, data):
		response = requests.post(url=self.FAYE_URL,
								data=json.dumps(data),
								headers={"Content-type": "application/json"})
		self.debug_out(response.json())
		return response

	# Increment id for every call, otherwise websocket connection won't open
	def __get_id(self):
		self.id += 1
		return self.id

	# Gets user_id related to token 
	def get_user_id(self, access_token):
		json_body = requests.get(headers={"Content-type": "application/json", "X-Access-Token": access_token},
								 url=self.GET_ME_URL).json()
		try:
			user_id = json_body.get("response").get("id")
		except AttributeError:
			user_id = None
		return user_id

	def debug_out(self, msg):
		if self.debug: print(self.__class__.__name__ + ": " + str(msg))

	# Returns object for the initial handshake with Faye
	def handshake(self, connection_types=["websocket"]):
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
				"subscription": "/user/{0}".format(self.user_id),
				"id": self.__get_id(),
				"ext": {"access_token": self.access_token}
			}
		]

	# Object needed for socket request
	def poll(self, connection_type="websocket"):
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
		self.debug_out("Opening socket")
		self.ws = websocket.create_connection(self.WSS_HOST, self.TIMEOUT_SECONDS)

	def close_socket(self):
		if self.ws is not None: self.ws.close()
		self.debug_out("Socket closed")

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
			except websocket._exceptions.WebSocketConnectionClosedException:
				# Socket is closed, exit with -1
				self.debug_out("Error! Socket is already closed.")
				return -1
			except json.decoder.JSONDecodeError as err:
				self.debug_out("Error! Could not decode JSON.")
				return -1
			self.debug_out(response)
			if response[0].get("channel") == "/meta/connect":
				# Websocket needs to reconnect, client_id is reset
				self.debug_out("Reconnecting socket")
				self.client_id = response[0].get("clientId")
				self.ws.send(json.dumps(self.poll()))
			elif response[0].get("data").get("type") in ["line.create", "direct_message.create"]:
				# New event, pass message JSON to handler
				self.debug_out("New message: " + str(response))
				self.handler(response)
			else:
				# Ping, do nothing
				pass
		return 0

	def run(self, seconds=3600):
		if self.user_id is None:
			self.debug_out("User ID not found, exiting")
			return
		end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
		self.connect_to_faye()
		self.ws.send(json.dumps(self.poll()))
		l_thread = threading.Thread(target=self.listen_to_socket)
		l_thread.start()
		while datetime.datetime.now() < end_time:
			# wait 1 second before checking the time again
			time.sleep(1)


# Testing purposes only
def test_handler(msg):
	print(str(msg))


if __name__ == '__main__':
	with GroupmeWebSocket(test_handler, sys.argv[1], True) as gws:
		gws.run()
