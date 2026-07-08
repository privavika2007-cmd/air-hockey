from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from objects import WebSocketHandler, InputHandler, Master



@asynccontextmanager
async def lifespan_func(app : FastAPI):
    app.state.master = Master()


    yield



app = FastAPI(lifespan = lifespan_func)







@app.get("/")
def root():
    return {"message" : "server root"}


#need to receive data in this format : 
"""{
    "position": {
        "x": 153.2,
        "y": 421.6
    }
}"""

@app.websocket("/ws_connect")
async def websocket_connect(websocket : WebSocket):

    master : Master =  websocket.app.state.master
    web_handler : WebSocketHandler = master.wsHandler
    input_handler : InputHandler = master.inputHandler

    accepted = await web_handler.connect(websocket)
    if not accepted:
        return 

    try:
        while True:
            data = await websocket.receive_json()
            if websocket is web_handler.player1:
                #process for player 1 here
                input_handler.store_packet(1, data)

            elif websocket is web_handler.player2:
                #process for player 2 here - invert across (0,0)
                data["position"]["x"] *= -1
                data["position"]["y"] *= -1
                input_handler.store_packet(2, data)


    except WebSocketDisconnect:
        await web_handler.disconnect(websocket)




#test endpoints
@app.get("/check_connections")
async def check_connections():
    master : Master = app.state.master
    web_handler : WebSocketHandler = master.wsHandler
    player1_connected = False
    player2_connected = False
    if web_handler.player1 is not None:
        player1_connected = True
    if web_handler.player2 is not None:
        player2_connected = True

    return {
        "number_of_connected_players" : web_handler.number_of_connected_players(),
        "player1_connected" : player1_connected,
        "player2_connected" : player2_connected
    }
        

@app.get("/check_inputHandler")
async def check_inputHandler():
    master : Master = app.state.master
    input_handler : InputHandler = master.inputHandler

    return {
        "get_last_packets(1)" : input_handler.get_last_packets(1),
        "get_last_packets(2)" : input_handler.get_last_packets(2)
    }