# groupme-websocket

Use the GroupmeWebSocket class to receive JSON messages in real time from groupme. 

GroupmeWebSocket requires the following parameters:
-A method reference to be invoked on all new messages
-A groupme access token which can be retrieved by logging into dev.groupme.com

from groupmewebsocket import GroupmeWebsocket

with GroupmeWebSocket(handler,access_token,debug) as gws: 
	gws.run()
