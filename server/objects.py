from dataclasses import dataclass, asdict
from fastapi import WebSocket, WebSocketDisconnect
from enum import IntEnum, StrEnum
from constants import *
from collections import deque
import asyncio

from physics_engine import calculate_player_puck_collision, calculate_player_wall_collision, calculate_puck_wall_collision, checking_goal
from models import Pair, Player, Puck, GoalStatus
from models import normalize_vector


    





@dataclass 
class GameState:
     player1 : Player
     player2 : Player
     puck : Puck
     score : Pair


class Status(IntEnum):
     NO_PLAYERS = 0
     WAITING_FOR_OTHER_PLAYER = 1
     READY = 2


class PacketType(StrEnum):
     GAME_STATE = "GameState"
     MESSAGE = "Message"
     ERROR = "Error"



@dataclass
class Packet:
     type : PacketType
     data : dict | str


class WebSocketHandler:
     player1 : WebSocket | None
     player2 : WebSocket | None
     status : Status
     masterLink : "Master"

     def __init__(self, master : "Master"):
          self.player1 = None
          self.player2 = None
          self.status = Status.NO_PLAYERS
          self.lock = asyncio.Lock()
          self.masterLink = master


     def number_of_connected_players(self) -> int:
          connected_players = 0
          if isinstance(self.player1, WebSocket):
               connected_players += 1
          if isinstance(self.player2, WebSocket):
               connected_players += 1
          return connected_players


     async def connect(self, websocket : WebSocket) -> bool:
          await websocket.accept()

          async with self.lock:
               if self.player1 is None:
                    self.player1 = websocket
               elif self.player2 is None:
                    self.player2 = websocket
               else:
                    await websocket.close()
                    return False
               
          self.status = Status(self.number_of_connected_players())
          if (self.status == Status.READY) and (self.masterLink.gameMaster.game_running is False):
               self.masterLink.gameMaster.StartGame(player1 = Player(Pair(0,0), 0, Pair(0,0)), 
                                                  player2 = Player(Pair(0,0), 0, Pair(0,0)))
               
          print("WebSocket connected")
          return True


     async def disconnect(self, websocket : WebSocket):

          async with self.lock:
               if websocket is self.player1:
                    self.player1 = None
               elif websocket is self.player2:
                    self.player2 = None

          print("WebSocket disconnected")

          self.status = Status(self.number_of_connected_players())
          if (self.status is not Status.READY) and (self.masterLink.gameMaster.game_running is True):
               await self.masterLink.gameMaster.EndGameDisconnect()
          return



     #message data type - dict
     #need to serialize GameState to dict with asdict(game_state)
     async def send_to_player1(self, packet : Packet):
          if isinstance(self.player1, WebSocket):
               await self.player1.send_json(asdict(packet))
          else:
               raise RuntimeError("Player 1 is not connected. Trying to send a message with no connection")          

     async def send_to_player2(self, packet : Packet):
          if isinstance(self.player2, WebSocket):
               #reverse data across the (0,0) coordinate here
               await self.player2.send_json(asdict(packet))
          else:
               raise RuntimeError("Player 2 is not connected. Trying to send a message with no connection")     
     
     async def send_to_both_players(self, packet : Packet):
          successfully_sent = True
          if isinstance(self.player1, WebSocket):
               await self.player1.send_json(asdict(packet))
          else:
               successfully_sent = False
          
          if isinstance(self.player2, WebSocket):
               await self.player2.send_json(asdict(packet))
          else:
               successfully_sent = False
          
          return successfully_sent
     

     async def clear_connections(self):
          if isinstance(self.player1, WebSocket):
               await self.player1.close()
               self.player1 = None
          if isinstance(self.player2, WebSocket):
               await self.player2.close()
               self.player2 = None

          
          

          

     
class GameMaster():
     gamestate : GameState
     masterLink : "Master"
     game_running : bool = False
     time_delta : float = 1/120
     max_score : float = 5

     def __init__(self, master : "Master"):
          self.gamestate = GameState(
               player1 = Player(Pair(0,0), 0, Pair(0,0)),
               player2 = Player(Pair(0,0), 0, Pair(0,0)),
               puck = Puck(Pair(0,0), 0, Pair(0,0)),
               score = Pair(0,0)
          )
          self.masterLink = master
          self.game_running = False

     def StartGame(self, player1 : Player, player2 : Player):
          self.gamestate.player1 = player1
          self.gamestate.player1.position = Pair(0, DOWN_WALL + PLAYER_RADIUS)

          self.gamestate.player2 = player2
          self.gamestate.player2.position = Pair(0, TOP_WALL - PLAYER_RADIUS)

          puck = Puck(Pair(0,0), 0, Pair(0,0))
          self.gamestate.puck = puck

          self.gamestate.score = Pair(0,0)
          
          self.game_running = True
          asyncio.create_task(self.gameLoop())

     
     async def EndGameDisconnect(self):
          self.game_running = False          #the game stops at the next iteration

          self.gamestate.puck.speed = 0

          self.masterLink.inputHandler.clear_inputs()
          await self.masterLink.wsHandler.clear_connections()

          await self.masterLink.wsHandler.send_to_both_players(
               Packet(
                    type= PacketType.MESSAGE,
                    data = "one of the players disconnected. the game stops now"
                    )
          )
          #отправляем сам месседж


     async def EndGameScore(self):
          self.game_running = False

          self.gamestate.puck.speed = 0

          self.masterLink.inputHandler.clear_inputs()
          await self.masterLink.wsHandler.clear_connections()
          
          await self.masterLink.wsHandler.send_to_both_players(
               Packet(
                    type= PacketType.MESSAGE,
                    data= "max_score reached. the game stops now"
               )
          )#отправляем месседж




     def update_data_for_player1(self):
          last_two_packets_for_player1 = self.masterLink.inputHandler.get_last_packets(1)

          #если еще нет двух пакетов ничего не происходит
          if last_two_packets_for_player1 is None:
               return 
          
          self.gamestate.player1.speed_vector = Pair(last_two_packets_for_player1[1].first - last_two_packets_for_player1[0].first,
                                        last_two_packets_for_player1[1].second - last_two_packets_for_player1[0].second)       #считаем вектор скорости по последним двум пакетам данных (за 1/60 секунды!!)
          self.gamestate.player1.speed = self.gamestate.player1.speed_vector.length() 
          self.gamestate.player1.speed_vector = normalize_vector(self.gamestate.player1.speed_vector)

          #проверка на превышение скорости перед рассчетом позиции
          if self.gamestate.player1.speed <= PLAYER_SPEED_LIMIT:
               self.gamestate.player1.position = Pair(last_two_packets_for_player1[1].first, last_two_packets_for_player1[1].second)
                  #обновляем позицию player1
          else:
               self.gamestate.player1.position = self.gamestate.player1.position + (self.gamestate.player1.speed_vector * PLAYER_SPEED_LIMIT)
               self.gamestate.player1.speed = PLAYER_SPEED_LIMIT


          self.gamestate.player1.speed_vector = calculate_player_wall_collision(self.gamestate.player1, 1)                      #чекаем коллизию player1 и стен
          self.gamestate.player1.speed = self.gamestate.player1.speed_vector.length()
          self.gamestate.player1.speed_vector = normalize_vector(self.gamestate.player1.speed_vector)

          if self.gamestate.player1.speed > PLAYER_SPEED_LIMIT:
               self.gamestate.player1.speed = PLAYER_SPEED_LIMIT



     def update_data_for_player2(self):
          last_two_packets_for_player2 = self.masterLink.inputHandler.get_last_packets(2)

          #если нет двух пакетов
          if last_two_packets_for_player2 is None:
               return
          
          self.gamestate.player2.speed_vector = Pair(last_two_packets_for_player2[1].first - last_two_packets_for_player2[0].first,
                                                     last_two_packets_for_player2[1].second - last_two_packets_for_player2[0].second)       #считаем вектор скорости по последним двум пакетам данных
          self.gamestate.player2.speed = self.gamestate.player2.speed_vector.length() 
          self.gamestate.player2.speed_vector = normalize_vector(self.gamestate.player2.speed_vector)

          #проверка на превышение скорости перед рассчетом позиции
          if self.gamestate.player2.speed <= PLAYER_SPEED_LIMIT:
               self.gamestate.player2.position = Pair(last_two_packets_for_player2[1].first, last_two_packets_for_player2[1].second)
                    #обновляем позицию player2
          else:
               self.gamestate.player2.position = self.gamestate.player2.position + (self.gamestate.player2.speed_vector * PLAYER_SPEED_LIMIT)
               self.gamestate.player2.speed = PLAYER_SPEED_LIMIT


          self.gamestate.player2.speed_vector = calculate_player_wall_collision(self.gamestate.player2, 2)                      #чекаем коллизию player2 и стен
          self.gamestate.player2.speed = self.gamestate.player2.speed_vector.length() 
          self.gamestate.player2.speed_vector = normalize_vector(self.gamestate.player2.speed_vector)


          if self.gamestate.player2.speed > PLAYER_SPEED_LIMIT:
               self.gamestate.player2.speed = PLAYER_SPEED_LIMIT

          



     def update_puck_data(self):
          
          self.gamestate.puck.position = self.gamestate.puck.position + self.gamestate.puck.speed_vector * self.gamestate.puck.speed  #обновляем позицию шайбы


          self.gamestate.puck.speed_vector = calculate_puck_wall_collision(self.gamestate.puck)                                                                      #чекаем коллизию шайбы и стены и обновляем вектор скорости
          self.gamestate.puck.speed = self.gamestate.puck.speed_vector.length() 
          self.gamestate.puck.speed_vector = normalize_vector(self.gamestate.puck.speed_vector)

          self.gamestate.puck.speed_vector = calculate_player_puck_collision(self.gamestate.player1, self.gamestate.puck)                                  #чекаем коллизию шайбы и player1 и обновляем вектор скорости
          self.gamestate.puck.speed = self.gamestate.puck.speed_vector.length() 
          self.gamestate.puck.speed_vector = normalize_vector(self.gamestate.puck.speed_vector)

          self.gamestate.puck.speed_vector = calculate_player_puck_collision(self.gamestate.player2, self.gamestate.puck)                        #чекаем коллизию шайбы и player2 и обновляем вектор скорости
          self.gamestate.puck.speed = self.gamestate.puck.speed_vector.length() 
          self.gamestate.puck.speed_vector = normalize_vector(self.gamestate.puck.speed_vector)


          if (self.gamestate.puck.speed - PUCK_FRICTION) > 0:
               self.gamestate.puck.speed = self.gamestate.puck.speed - PUCK_FRICTION
          else:
               self.gamestate.puck.speed = 0



          if self.gamestate.puck.speed > PUCK_SPEED_LIMIT:
               self.gamestate.puck.speed = PUCK_SPEED_LIMIT


     def reset_after_goal(self):
          #reset players and puck
          self.gamestate.player1 = Player(Pair(0, DOWN_WALL + PLAYER_RADIUS), 0, Pair(0,0))
          self.gamestate.player2 = Player(Pair(0, TOP_WALL - PLAYER_RADIUS), 0, Pair(0,0))
          self.gamestate.puck = Puck(Pair(0,0), 0, Pair(0,0))

          self.masterLink.inputHandler.clear_inputs()





     async def gameLoop(self):

          while self.game_running:
               self.update_data_for_player1()     #player1 обновляем
               self.update_data_for_player2()     #player2 обновляем
               self.update_puck_data()        #puck обновляем

               goal_status : GoalStatus = checking_goal(self.gamestate.puck)

               if goal_status == GoalStatus.Player1Scored:
                    self.gamestate.score.first =  self.gamestate.score.first + 1
                    self.reset_after_goal()

               elif goal_status == GoalStatus.Player2Scored:
                    self.gamestate.score.second =  self.gamestate.score.second + 1
                    self.reset_after_goal()

                    #в идеале, можно разделить сообщения на типы, чтобы клиенту было легче их обрабатывать
                    #например - message, error, GameState, GoalStatus

               #send packets here
               await self.masterLink.wsHandler.send_to_player1(
                    Packet(
                         type= PacketType.GAME_STATE,
                         data= asdict(self.gamestate)
                    )
                    ) #player 1

               #reversing the data for player2
               gamestate_copy_reversed = GameState(
                    player1= Player(
                         position= self.gamestate.player2.position * -1,
                         speed= self.gamestate.player2.speed,
                         speed_vector= self.gamestate.player2.speed_vector * -1
                    ),
                    player2= Player(
                         position= self.gamestate.player1.position * -1,
                         speed = self.gamestate.player1.speed,
                         speed_vector= self.gamestate.player1.speed_vector * -1
                    ),
                    puck = Puck(
                         position= self.gamestate.puck.position * -1,
                         speed= self.gamestate.puck.speed,
                         speed_vector= self.gamestate.puck.speed_vector * -1
                    ),
                    score = Pair(
                         first= self.gamestate.score.second,
                         second= self.gamestate.score.first
                    )
               )

               await self.masterLink.wsHandler.send_to_player2(
                    Packet(
                         type= PacketType.GAME_STATE,
                         data= asdict(gamestate_copy_reversed)
                    )
                    )
          

               if self.gamestate.score.first >= self.max_score or self.gamestate.score.second >= self.max_score:
                    await self.EndGameScore()
               

               await asyncio.sleep(self.time_delta)



               
               

class Master():
     gameMaster : GameMaster
     wsHandler : WebSocketHandler
     inputHandler : "InputHandler"


     def __init__(self):
          self.gameMaster = GameMaster(self)
          self.wsHandler = WebSocketHandler(self)
          self.inputHandler = InputHandler()




class InputHandler:

     def __init__(self):
          self._history = {
               1 : deque(maxlen = 2),
               2 : deque(maxlen = 2)
          }
          



#packet_data MUST look like 
#{
# "position": {
#     "x": 153.2,
#     "y": 421.6
# }
#}

     def store_packet(self, player_id : int, packet_data : dict):
          self._history[player_id].append(
               Pair(first = packet_data["position"]["x"],
                    second = packet_data["position"]["y"])
               )



     def get_last_packets(self, player_id : int):
          if len(self._history[player_id]) < 2:
               return None
               
          return tuple(self._history[player_id])
     
     
     def clear_inputs(self):
          self._history[1].clear()
          self._history[2].clear()





