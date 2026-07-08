from dataclasses import dataclass
from typing import overload
from enum import IntEnum, StrEnum
from constants import PUCK_RADIUS, PLAYER_RADIUS
import math









@dataclass
class Pair:
    first : float
    second : float

    @overload
    def __mul__(self, other: "Pair") -> float: ...

    @overload
    def __mul__(self, other: float) -> "Pair": ...

    @overload
    def __mul__(self, other: int) -> "Pair": ...

    def __mul__(self, other):
        if isinstance(other, Pair):
              return self.first * other.first + self.second * other.second
        elif isinstance(other, (int, float)):
             return Pair(
                  self.first * other,
                  self.second * other
             )
        return NotImplemented
    
    def __rmul__(self, other):
         return self.__mul__(other)
    
    
    def __add__(self, other : "Pair") -> "Pair":
         return Pair(
            self.first + other.first,
            self.second + other.second,
        )
    
    def __sub__(self, other : "Pair") -> "Pair":
         return Pair(
            self.first - other.first,
            self.second - other.second,
        )
         
    def length(self) -> float:
         return math.hypot(self.first, self.second)





@dataclass
class Puck:
    position : Pair
    speed : float
    speed_vector : Pair

    RADIUS : int = PUCK_RADIUS

    def __init__(self, position : Pair, speed : float, speed_vector : Pair):
        self.position = position
        self.speed = speed
        self.speed_vector = normalize_vector(speed_vector)

    




@dataclass
class Player:
     position : Pair
     speed : float
     speed_vector : Pair

     RADIUS = PLAYER_RADIUS

     def __init__(self, position : Pair, speed : float, speed_vector : Pair):
          self.position = position
          self.speed = speed
          self.speed_vector = normalize_vector(speed_vector)




class GoalStatus(IntEnum):
     NoGoal = 0
     Player1Scored = 1
     Player2Scored = 2




def normalize_vector(vector : Pair) -> Pair:
        length = math.sqrt(vector.first ** 2 + vector.second ** 2)
        if length == 0:
             return Pair(0, 0)
        new_vector = Pair(vector.first / length, vector.second / length)
        return new_vector
