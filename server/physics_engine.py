from models import Pair, Player, Puck, GoalStatus
from constants import*
import math


def calculate_player_puck_collision(player : Player, puck : Puck):
    distance = math.hypot(
        player.position.first - puck.position.first,
        player.position.second - puck.position.second
        )

    if distance < PLAYER_RADIUS + PUCK_RADIUS:
        player_speed = player.speed_vector * player.speed
        puck_speed = puck.speed_vector * puck.speed

        #formula : v'' = v' - 2(v' * n)n , где n единичная нормаль к прямой
        #по относительности v' = v(puck) - v(player)

        puck_speed_relative = puck_speed - player_speed
        normal_vector = puck.position - player.position
        if(normal_vector.length() == 0):
            return puck_speed

        normal_vector_unit = normal_vector * (1/normal_vector.length())

        overlap = (PLAYER_RADIUS + PUCK_RADIUS) - distance
        puck.position = puck.position + normal_vector_unit * overlap

        velocity_along_normal = puck_speed_relative * normal_vector_unit
        if velocity_along_normal < 0:
            puck_speed_relative_reflected = (puck_speed_relative - normal_vector_unit * ( 2*(puck_speed_relative * normal_vector_unit) ) )
            puck_speed_reflected = puck_speed_relative_reflected + player_speed
            return puck_speed_reflected
       
            

        
        

    return puck.speed_vector * puck.speed
    




def calculate_puck_wall_collision(puck : Puck):
    puck_speed_vector = puck.speed_vector * puck.speed
    new_puck_speed_vector =  puck_speed_vector

    #левая стенка
    if puck.position.first <= (LEFT_WALL + PUCK_RADIUS):      #проверка на коллизию с левой стенкой
        normal_vector_from_wall = Pair(1, 0)

        velocity_along_normal = puck_speed_vector * normal_vector_from_wall
        if velocity_along_normal < 0:

            puck.position = Pair(LEFT_WALL + PUCK_RADIUS, puck.position.second)
            
            new_puck_speed_vector = puck_speed_vector - normal_vector_from_wall * (puck_speed_vector * normal_vector_from_wall) * 2
            return new_puck_speed_vector

    elif ((puck.position.second >= (TOP_WALL - PUCK_RADIUS) or           #проверка нахождения шайбы в воротах + коллизия с их левой стенкой
          puck.position.second <= (DOWN_WALL + PUCK_RADIUS)) and 
         puck.position.first <= (GOAL_LEFT + PUCK_RADIUS)):
        normal_vector_from_wall = Pair(1, 0)

        velocity_along_normal = puck_speed_vector * normal_vector_from_wall
        if velocity_along_normal < 0:

            puck.position = Pair(GOAL_LEFT + PUCK_RADIUS, puck.position.second)
            
            new_puck_speed_vector = puck_speed_vector - normal_vector_from_wall * (puck_speed_vector * normal_vector_from_wall) * 2
            return new_puck_speed_vector
        
    #правая стенка
    if  puck.position.first >= (RIGHT_WALL - PUCK_RADIUS):     #проверка на коллизию с правой стенкой
          
        normal_vector_from_wall = Pair(-1, 0)

        
        velocity_along_normal = puck_speed_vector * normal_vector_from_wall

        if velocity_along_normal < 0:
            
            puck.position = Pair(RIGHT_WALL - PUCK_RADIUS, puck.position.second)

            
            new_puck_speed_vector = puck_speed_vector - normal_vector_from_wall * (puck_speed_vector * normal_vector_from_wall) * 2
            return new_puck_speed_vector
        
    elif ((puck.position.second >= (TOP_WALL - PUCK_RADIUS) or         #проверка на нахождение шайбы в воротах + коллизия с их правой стенкой
          puck.position.second <= (DOWN_WALL + PUCK_RADIUS)) and 
         puck.position.first >= (GOAL_RIGHT - PUCK_RADIUS)):
        normal_vector_from_wall = Pair(-1, 0)

        
        velocity_along_normal = puck_speed_vector * normal_vector_from_wall

        if velocity_along_normal < 0:
            
            puck.position = Pair(GOAL_RIGHT - PUCK_RADIUS, puck.position.second)

            
            new_puck_speed_vector = puck_speed_vector - normal_vector_from_wall * (puck_speed_vector * normal_vector_from_wall) * 2
            return new_puck_speed_vector



    #верхняя стенка ворот
    if ((puck.position.second >= (TOP_WALL - PUCK_RADIUS)) and   #проверка на коллизию с горизонтальными стенками возле ворот

          (puck.position.first <= (GOAL_LEFT + PUCK_RADIUS) or 
           puck.position.first >= (GOAL_RIGHT - PUCK_RADIUS))):
        
        normal_vector_from_wall = Pair(0, -1)

        velocity_along_normal = puck_speed_vector * normal_vector_from_wall
        if velocity_along_normal < 0:

            puck.position = Pair(puck.position.first, TOP_WALL - PUCK_RADIUS)

            
            new_puck_speed_vector = puck_speed_vector - normal_vector_from_wall * (puck_speed_vector * normal_vector_from_wall) * 2
            return new_puck_speed_vector

    #нижняя стенка ворот
    elif (puck.position.second <= (DOWN_WALL + PUCK_RADIUS)
          and
          (puck.position.first <= (GOAL_LEFT + PUCK_RADIUS)
           or
           puck.position.first >= (GOAL_RIGHT - PUCK_RADIUS))):
        
        normal_vector_from_wall = Pair(0, 1)
        
        velocity_along_normal = puck_speed_vector * normal_vector_from_wall
        if velocity_along_normal < 0:

            puck.position = Pair(puck.position.first, DOWN_WALL + PUCK_RADIUS)

            new_puck_speed_vector = puck_speed_vector - normal_vector_from_wall * (puck_speed_vector * normal_vector_from_wall) * 2
            return new_puck_speed_vector
        

    return puck_speed_vector


def checking_goal(puck : Puck) -> GoalStatus:
    if ((puck.position.second < (DOWN_WALL - PUCK_RADIUS) and  #в нижних воротах
        puck.position.first >= (GOAL_LEFT + PUCK_RADIUS) and
        puck.position.first <= (GOAL_RIGHT - PUCK_RADIUS))
        ):
        return GoalStatus.Player2Scored #слать инфу о голе player2

    elif ((puck.position.second > (TOP_WALL + PUCK_RADIUS) and  #в верхних воротах
        puck.position.first >= (GOAL_LEFT + PUCK_RADIUS) and
        puck.position.first <= (GOAL_RIGHT - PUCK_RADIUS))
        ):
        return GoalStatus.Player1Scored #слать инфу о голе player1
    
    return GoalStatus.NoGoal





#если есть коллизия игрока и стенки можно "достать" игрока из этой стенки немного подправив его координату


def calculate_player_wall_collision(player : Player, player_id : int):
    if (player.position.first >= RIGHT_WALL - PLAYER_RADIUS or          #коллизия с боковыми стенками обнуления х-вой координаты
        player.position.first <= LEFT_WALL + PLAYER_RADIUS):

        player.speed_vector.first = 0
    if player_id == 1:          
        if (player.position.second >= -1 * PLAYER_RADIUS or 
            player.position.second <= DOWN_WALL + PLAYER_RADIUS):           #выход за пределы нижней половины по y у player1, обнуление y координаты

            player.speed_vector.second = 0
    else:
        if (player.position.second <= PLAYER_RADIUS or                      #выход за пределы верхней половины по y y player2, обнуление y координаты
            player.position.second >= TOP_WALL - PLAYER_RADIUS):

            player.speed_vector.second = 0

    return player.speed_vector * player.speed