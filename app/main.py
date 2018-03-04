import bottle
import os
import random
import operator
from math import ceil
from copy import copy, deepcopy

@bottle.route('/')
def static():
    return "SERVER IS RUNNING"

@bottle.route('/static/<path:path>')
def static(path):
    return bottle.static_file(path, root='static/')

@bottle.post('/start')
def start():
    #data = bottle.request.json
    #game_id = data.get('game_id')
    #board_width = data.get('width')
    #board_height = data.get('height')

    return {
        'color': '#00FF00',
        'taunt': 'Catch me if you can!',
        'head_url': 'https://i.imgur.com/G8YsaF6.png',
        'name': 'battlesnake-python',
        'head_type': 'fang',
        'tail_type': 'curled'
    }

@bottle.post('/move')
def move():
    request = bottle.request.json
    
    # Extract data from request
    snakeId = request['you']['id']
    snakes = request['snakes']['data']
    foods = request['food']['data']
    boardWidth = request['width']
    boardHeight = request['height']
    area = boardWidth * boardHeight

    # Generate lookup objects 
    board = generateBoard(boardHeight, boardWidth, snakes, foods)
    snakesLookup = generateSnakesLookup(snakes)
    
    mySnake = snakesLookup[snakeId]
    snakeHead = mySnake.coords[0]
    snakeTail = mySnake.coords[len(mySnake.coords) - 1]
    
    move = None
    moveDecided = False
    taunt = "Snakeliness is next to Godliness"
    
    validRoutines = { "left": 0, "right": 0, "down": 0, "up": 0}
    validRoutinesCopy = validRoutines.copy()
    
    # Routine: Verify legal moves
    for direction, value in validRoutinesCopy.items():
        directionValid = directionIsValid(board, snakesLookup, snakeId, direction)
        if not directionValid:
            del validRoutines[direction]
            
    # If no valid moves; kill self
    if not validRoutines:
        return returnMoveResponse("down", "Goodbye cruel world...")
        
    pathToTailRoutines = validRoutines.copy()
    
    # Determine which moves would put us at risk of colliding with other snakes
    largerSnakeCanMoveToSquareValues = []
    for direction, value in validRoutines.items():
        largerSnakeCanMoveToSquare = otherSnakeCanCompeteForSquare(board, snakesLookup, snakeId, direction)
        if largerSnakeCanMoveToSquare:
            largerSnakeCanMoveToSquareValues.append(direction)
    
    # Routine: Verify that each route allows us to get back to our tail (note: disregards spaces around other snake heads)
    # TODO: If the current space we are moving into has enough area for us to move around in such that our tail catches up to us, we should also count that as being a path
    for direction, value in validRoutines.items():
        shortestPathToTail = directionForShortestPathBetweenSnakeHeadAndPoint(board, snakeHead, snakeTail['x'], snakeTail['y'], direction, True, snakeId)
        if shortestPathToTail == None:
            floodFillValue = spaceAvailableForDirection(board, snakesLookup, snakeId, direction)
            if floodFillValue == 0 or (floodFillValue * 1.5) < len(mySnake.coords):
                del pathToTailRoutines[direction]
            else:
                pathToTailRoutines[direction] += (area - (floodFillValue * 1.5))
        else:
            pathToTailRoutines[direction] += (area - shortestPathToTail[0])
    
    # Routine: Verify each route again if no safe path exists but don't treat other snake heads as special
    if not pathToTailRoutines:
        pathToTailRoutines = validRoutines.copy()
        
        for direction, value in validRoutines.items():
            shortestPathToTail = directionForShortestPathBetweenSnakeHeadAndPoint(board, snakeHead, snakeTail['x'], snakeTail['y'], direction)
            if shortestPathToTail == None:
                del pathToTailRoutines[direction]
            else:
                pathToTailRoutines[direction] += (area - shortestPathToTail[0])
            
    # If no viable routes back to our tail, then find the path to maximize the time we can stay alive
    if not pathToTailRoutines:
        # Routine: Determine how many moves we can make if we go in a given direction
        # TODO: Replace with longest path algorithm?
        mostSpaces = 0
        bestDirectionToStayAliveWhenBlocked = None
        currentDirectionCollidesWithSnake = False
        
        for direction, value in validRoutines.items():
            movesAvailable = spaceAvailableForDirection(board, snakesLookup, snakeId, direction)
            if ((movesAvailable > mostSpaces and direction not in largerSnakeCanMoveToSquareValues) 
            or (movesAvailable > mostSpaces and direction in largerSnakeCanMoveToSquareValues and currentDirectionCollidesWithSnake) 
            or (movesAvailable > 10 and direction not in largerSnakeCanMoveToSquareValues and currentDirectionCollidesWithSnake)):
                mostSpaces = movesAvailable
                bestDirectionToStayAliveWhenBlocked = direction
                currentDirectionCollidesWithSnake = direction in largerSnakeCanMoveToSquareValues
                
        return returnMoveResponse(bestDirectionToStayAliveWhenBlocked, "I'm trapped!")
    
    # Determine which of the paths back to our tail are not at risk of colliding with another snake's head
    safePathToTailRoutines = {}
    for direction, value in pathToTailRoutines.items():
        if direction not in largerSnakeCanMoveToSquareValues:
            safePathToTailRoutines[direction] = value
    
    # If only one route exists that does not risk colliding with another snake's head, select it
    if len(safePathToTailRoutines) == 1:
        return returnMoveResponse(safePathToTailRoutines.keys()[0], "That was a close one!")
    
    # If all squares are at risk of collision, choose the one furthest from the nearest food
    if len(safePathToTailRoutines) == 0:
        mostSpacesForFood = -1
        bestDirectionToEscapeSnakeAwayFromFood = None
        
        for direction, value in pathToTailRoutines.items():
            # Determine which snake can collide with us
            snakeIdToCompare = findOtherSnakeIdInProximityToDirection(board, snakeHead, snakeId, direction)
            
            if snakeIdToCompare == None:
                bestDirectionToEscapeSnakeAwayFromFood = direction
                break
            
            moveForFood = directionToReachClosestPieceOfFood(board, snakesLookup, snakeIdToCompare, foods, direction)
            if moveForFood == None:
                bestDirectionToEscapeSnakeAwayFromFood = direction
                break
            
            if moveForFood != None and (mostSpacesForFood == -1 or moveForFood[0] > mostSpacesForFood):
                mostSpacesForFood = moveForFood[0]
                bestDirectionToEscapeSnakeAwayFromFood = direction
        
        if bestDirectionToEscapeSnakeAwayFromFood == None:
            bestDirectionToEscapeSnakeAwayFromFood = pathToTailRoutines.items()[0]
        
        return returnMoveResponse(bestDirectionToEscapeSnakeAwayFromFood, "I'm in trouble...")
    
    # Routine: Get rekt (kill a smaller snake)
    for direction, value in safePathToTailRoutines.items():
        canSmallerSnakeCompete = smallerSnakeCanCompeteForSquare(board, snakesLookup, snakeId, direction)
        if canSmallerSnakeCompete:
            safePathToTailRoutines[direction] += 100
    
    # Routine: Go towards food
    leastSpaces = -1
    bestDirectionToEatFood = None
        
    for direction, value in safePathToTailRoutines.items():
        moveForFood = directionToReachClosestPieceOfFood(board, snakesLookup, snakeId, foods, direction)
        if moveForFood != None:
            safePathToTailRoutines[direction] += (100 - mySnake.health) - moveForFood[0]
            print "Snake ID: " + snakeId + " | Direction: " + direction + " | Food Value: " + str((100 - mySnake.health) - moveForFood[0])
            if bestDirectionToEatFood == None or moveForFood[0] < leastSpaces:
                leastSpaces = moveForFood[0]
                bestDirectionToEatFood = direction
    
    if bestDirectionToEatFood != None:
        if leastSpaces < 3 and mySnake.health < 60:
            return returnMoveResponse(bestDirectionToEatFood, "Nom nom nom")
        # elif leastSpaces < 2:
        #     return returnMoveResponse(bestDirectionToEatFood, "Nom nom nom")
        elif mySnake.health < 40:
            return returnMoveResponse(bestDirectionToEatFood, "Feed me!")
    elif mySnake.health < 50:
        for direction, value in safePathToTailRoutines.items():
            moveForFood = directionToReachClosestPieceOfFood(board, snakesLookup, snakeId, foods, direction, True)
            if moveForFood != None:
                if bestDirectionToEatFood == None or moveForFood[0] < leastSpaces:
                    leastSpaces = moveForFood[0]
                    bestDirectionToEatFood = direction
        
        return returnMoveResponse(bestDirectionToEatFood, "Watch out, because I'm hungry!")

    # Routine: Travel in a straight line
    moveForStraightLine = directionToTravelInAStraightLine(mySnake)
    if moveForStraightLine != None and moveForStraightLine in safePathToTailRoutines:
        safePathToTailRoutines[moveForStraightLine] += 5
            
    # Routine: Follow another snake's tail
    moveForSnakeToFollow = directionToFollowClosestSnake(board, snakesLookup, snakeId)
    if moveForSnakeToFollow != None and moveForSnakeToFollow in safePathToTailRoutines:
        safePathToTailRoutines[moveForSnakeToFollow] += 5
            
    # Routine: Move towards largest empty rectangle
    leastSpaces = -1
    bestDirectionToGetToMaxRectangle = None
    
    largestRectangleCenterPoint = getLocationForMaximumRectangle(board)
    for direction, value in safePathToTailRoutines.items():
        moveToLargestRectangle = directionForShortestPathBetweenSnakeHeadAndPoint(board, snakeHead, largestRectangleCenterPoint[0], largestRectangleCenterPoint[1], direction)
        if moveToLargestRectangle != None:
            safePathToTailRoutines[direction] += (area - moveToLargestRectangle[0]) * 5
            #print "Snake ID: " + snakeId + " | Direction: " + direction + " | Area Value: " + str((area - moveToLargestRectangle[0]) * 3)
            if bestDirectionToGetToMaxRectangle == None or moveToLargestRectangle[0] < leastSpaces:
                leastSpaces = moveToLargestRectangle[0]
                bestDirectionToGetToMaxRectangle = direction

    # Routine: Determine if any move we do will restrict another snake's ability to move
    snakesWithCurrentFlashFloodValues = {}
    for newSnakeId, newSnakeValue in snakesLookup.items():
        if newSnakeId == snakeId:
            continue
        
        otherSnakeHead = newSnakeValue.coords[0]
        movesAvailable = flashFoodAreaFromSpace(board, otherSnakeHead['x'], otherSnakeHead['y'], True)
        snakesWithCurrentFlashFloodValues[newSnakeId] = movesAvailable
        
    for direction, value in safePathToTailRoutines.items():
        headXPosition = snakeHead['x']
        headYPosition = snakeHead['y']
        if direction == "left":
            headXPosition -= 1
        if direction == "right":
            headXPosition += 1
        if direction == "up":
            headYPosition -= 1
        if direction == "down":
            headYPosition += 1
        
        newBoard = moveSnakeInBoard(board, snakesLookup, snakeId, headXPosition, headYPosition)
        
        for newSnakeId, newSnakeValue in snakesLookup.items():
            if newSnakeId == snakeId:
                continue
            
            otherSnakeHead = newSnakeValue.coords[0]
            movesAvailable = flashFoodAreaFromSpace(newBoard, otherSnakeHead['x'], otherSnakeHead['y'], True)
            
            # We are allowing the snake to move MORE FREELY
            if snakesWithCurrentFlashFloodValues[newSnakeId] == 0 and movesAvailable > 0:
                safePathToTailRoutines[direction] -= 50
            # We are decreasing the snake's movement
            elif movesAvailable + 5 < snakesWithCurrentFlashFloodValues[newSnakeId]:
                print "Reduced moves from", snakesWithCurrentFlashFloodValues[newSnakeId], "to", movesAvailable
                safePathToTailRoutines[direction] += 50

    # Pick the routine with the largest value
    return returnMoveResponse(max(safePathToTailRoutines.iteritems(), key=operator.itemgetter(1))[0], taunt)
    
def returnMoveResponse(move, taunt):
    return {
        'move': move,
        'taunt': taunt
    }
    
# https://leetcode.com/problems/maximal-rectangle/discuss/29054/Share-my-DP-solution
# http://i.cs.hku.hk/~hkual/Notes/Greedy/LargestRectangleProblem.html
def getLocationForMaximumRectangle(board):
    m = len(board)
    n = len(board[0]) + 1
    h = w = ret = 0
    height = [0] * n
    
    maxCoords = 0
    
    for i in range(0, m):
        s = []
        
        for j in range(0, n):
            if j < (n - 1):
                if snakeCanMoveToPosition(i, j, board):
                    height[j] += 1
                else:
                    height[j] = 0
            
            while s and height[s[len(s) - 1]] >= height[j]:
                h = height[s[len(s) - 1]]
                s.pop()
                
                prev = 0
                if not s:
                    w = j
                else:
                    w = j - s[len(s) - 1] - 1
                    prev = s[len(s) - 1] + 1
                    
                if (h * w) > ret:
                    ret = h * w
                    maxCoords = (i - h + 1, prev, i, j - 1)
            
            s.append(j)
    
    centerX = ceil((maxCoords[2] + maxCoords[0]) / 2)
    centerY = ceil((maxCoords[3] + maxCoords[1]) / 2)

    return (int(centerX), int(centerY))
    
def spaceAvailableForDirection(board, snakes, snakeId, direction):
    if direction == "left":
        return flashFoodAreaFromSpace(board, snakes[snakeId].coords[0]['x'] - 1, snakes[snakeId].coords[0]['y'])
    elif direction == "right":
        return flashFoodAreaFromSpace(board, snakes[snakeId].coords[0]['x'] + 1, snakes[snakeId].coords[0]['y'])
    elif direction == "up":
        return flashFoodAreaFromSpace(board, snakes[snakeId].coords[0]['x'], snakes[snakeId].coords[0]['y'] - 1)
    elif direction == "down":
        return flashFoodAreaFromSpace(board, snakes[snakeId].coords[0]['x'], snakes[snakeId].coords[0]['y'] + 1)
    
def directionWithMostSpaceAvailable(board, snakes, snakeId):
    leftMoveFlashFlood = flashFoodAreaFromSpace(board, snakes[snakeId].coords[0]['x'] - 1, snakes[snakeId].coords[0]['y'])
    rightMoveFlashFlood = flashFoodAreaFromSpace(board, snakes[snakeId].coords[0]['x'] + 1, snakes[snakeId].coords[0]['y'])
    downMoveFlashFlood = flashFoodAreaFromSpace(board, snakes[snakeId].coords[0]['x'], snakes[snakeId].coords[0]['y'] - 1)
    upMoveFlashFlood = flashFoodAreaFromSpace(board, snakes[snakeId].coords[0]['x'], snakes[snakeId].coords[0]['y'] + 1)
    
    if leftMoveFlashFlood >= rightMoveFlashFlood and leftMoveFlashFlood >= downMoveFlashFlood and leftMoveFlashFlood >= upMoveFlashFlood:
        return "left"
    elif rightMoveFlashFlood >= leftMoveFlashFlood and rightMoveFlashFlood >= downMoveFlashFlood and rightMoveFlashFlood >= upMoveFlashFlood:
        return "right"
    elif downMoveFlashFlood >= rightMoveFlashFlood and downMoveFlashFlood >= leftMoveFlashFlood and downMoveFlashFlood >= upMoveFlashFlood:
        return "down"
    elif upMoveFlashFlood >= rightMoveFlashFlood and upMoveFlashFlood >= leftMoveFlashFlood and upMoveFlashFlood >= downMoveFlashFlood:
        return "up"
    
def flashFoodAreaFromSpace(board, xPosition, yPosition, includeCurrentSpace = False):
    if not includeCurrentSpace and not snakeCanMoveToPosition(xPosition, yPosition, board):
        return 0
        
    moves = 0
    
    openList = []
    openList.append((xPosition, yPosition))
    
    closedList = []
    
    while len(openList) > 0:
        moves += 1
        currentSquare = openList.pop(0)
        closedList.append(currentSquare)
        adjacentSquaresCoords = [(currentSquare[0] - 1, currentSquare[1]), (currentSquare[0] + 1, currentSquare[1]), (currentSquare[0], currentSquare[1] - 1), (currentSquare[0], currentSquare[1] + 1)]
    
        for adjacentSquareCoords in adjacentSquaresCoords:
            coords = (adjacentSquareCoords[0], adjacentSquareCoords[1])
            if coords not in closedList and snakeCanMoveToPosition(adjacentSquareCoords[0], adjacentSquareCoords[1], board):
                if (coords not in openList):
                    openList.append((adjacentSquareCoords[0], adjacentSquareCoords[1]))

    return moves
    
'''
Calculates the direction to go in order to reach the closest piece of food (does not include food that is closer to
other snakes or at an equal distance to other snakes that are larger than us).
Returns a tuple, with the first item being the distance to the food, and the second item being the direction to 
move to get closer to it.
'''
def directionToReachClosestPieceOfFood(board, snakes, snakeId, foods, direction, ignoreOtherSnakes = False):
    bestDirection = None
    shortestDistance = -1
    
    snakeHead = snakes[snakeId].coords[0]
    
    snakeHeadX = snakeHead['x']
    snakeHeadY = snakeHead['y']
    if direction == "left":
        snakeHeadX = snakeHeadX - 1
    if direction == "right":
        snakeHeadX = snakeHeadX + 1
    if direction == "up":
        snakeHeadY = snakeHeadY - 1
    if direction == "down":
        snakeHeadY = snakeHeadY + 1
    
    for i in xrange(len(foods)):
        food = foods[i]
            
        if snakeHeadX == food['x'] and snakeHeadY == food['y']:
            return 0, None
    
        # Calculate shortest path to the food
        shortestPathToFood = directionForShortestPathBetweenTwoPoints(snakeHeadX, snakeHeadY, food['x'], food['y'], board)
        if shortestPathToFood == None:
            continue
        
        distance = shortestPathToFood[0]
        direction = shortestPathToFood[1]
        
        # Check that we haven't already found food that is closer than this
        if distance >= shortestDistance and shortestDistance != -1:
            continue
        
        # Determine whether another snake is closer to the food than us
        if not ignoreOtherSnakes:
            otherSnakeCloser = False
            for otherSnakeId, otherSnake in snakes.items():
                if otherSnakeId != snakeId:
                    otherSnakeShortestPathToFood = directionForShortestPathBetweenTwoPoints(otherSnake.coords[0]['x'], otherSnake.coords[0]['y'], food['x'], food['y'], board)
                    if otherSnakeShortestPathToFood == None:
                        continue
                    
                    otherSnakeDistance = otherSnakeShortestPathToFood[0]
                    if otherSnakeDistance < distance or (otherSnakeDistance == distance and otherSnake.totalLength >= snakes[snakeId].totalLength):
                        otherSnakeCloser = True
                        break
            
            if otherSnakeCloser == True:
                continue
        
        shortestDistance = distance
        bestDirection = direction
    
    if bestDirection == None:
        return None
    
    return shortestDistance, bestDirection
    
def directionForShortestPathBetweenSnakeHeadAndPoint(board, snakeHead, endXPosition, endYPosition, direction, treatSquaresAdjacentToSnakeHeadsAsBlocking=False, snakeId=None):
    if direction == "left":
        return directionForShortestPathBetweenTwoPoints(snakeHead['x'] - 1, snakeHead['y'], endXPosition, endYPosition, board, treatSquaresAdjacentToSnakeHeadsAsBlocking, snakeId)
    elif direction == "right":
        return directionForShortestPathBetweenTwoPoints(snakeHead['x'] + 1, snakeHead['y'], endXPosition, endYPosition, board, treatSquaresAdjacentToSnakeHeadsAsBlocking, snakeId)
    elif direction == "up":
        return directionForShortestPathBetweenTwoPoints(snakeHead['x'], snakeHead['y'] - 1, endXPosition, endYPosition, board, treatSquaresAdjacentToSnakeHeadsAsBlocking, snakeId)
    elif direction == "down":
        return directionForShortestPathBetweenTwoPoints(snakeHead['x'], snakeHead['y'] + 1, endXPosition, endYPosition, board, treatSquaresAdjacentToSnakeHeadsAsBlocking, snakeId)
    
'''
Calculates the shortest path in a grid with obstacles in an extremely computationally efficient way.
Returns a tuple, with the first item being the length of the path, and the second item being the
immediate direction to travel in order to follow that path.
https://www.raywenderlich.com/4946/introduction-to-a-pathfinding
'''
def directionForShortestPathBetweenTwoPoints(startXPosition, startYPosition, endXPosition, endYPosition, board, treatSquaresAdjacentToSnakeHeadsAsBlocking=False, snakeId=None):
    if startXPosition == endXPosition and startYPosition == endYPosition:
        return 0, None
        
    boardWidth = len(board)
    boardHeight = len(board[0])
    
    openList = {}
    closedList = {}
    
    endSquareCoords = (endXPosition, endYPosition)
    startSquareCoords = (startXPosition, startYPosition)
    optimalDistanceToEnd = distanceToCoord(startXPosition, startYPosition, endXPosition, endYPosition)
    
    startSquare = PathfinderSegment(startSquareCoords, None, 0, optimalDistanceToEnd, optimalDistanceToEnd)
    openList[startSquareCoords] = startSquare
    
    while openList:
        # Get the square with the lowest F score
        currentSquare = None
        lowestFScore = -1
        for key, segment in openList.items():
            if lowestFScore == -1 or segment.fValue <= lowestFScore:
                currentSquare = segment
                lowestFScore = segment.fValue
        
        closedList[currentSquare.coords] = currentSquare
        del openList[currentSquare.coords]
        
        # We have found a path
        if endSquareCoords in closedList:
            length = 0
            currentSquare = closedList[endSquareCoords]
            previousSquare = None
            
            if currentSquare.parent == None:
                previousSquare = startSquare
                length = 1
            
            while currentSquare.parent != None:
                previousSquare = currentSquare
                currentSquare = closedList[currentSquare.parent]
                length += 1
            
            if currentSquare.coords[0] < previousSquare.coords[0]:
                direction = "right"
            elif currentSquare.coords[0] > previousSquare.coords[0]:
                direction = "left"
            elif currentSquare.coords[1] > previousSquare.coords[1]:
                direction = "up"
            elif currentSquare.coords[1] < previousSquare.coords[1]:
                direction = "down"
            
            return length, direction
        
        adjacentSquaresCoords = [(currentSquare.coords[0] - 1, currentSquare.coords[1]), (currentSquare.coords[0] + 1, currentSquare.coords[1]), (currentSquare.coords[0], currentSquare.coords[1] - 1), (currentSquare.coords[0], currentSquare.coords[1] + 1)]
        for adjacentSquareCoords in adjacentSquaresCoords:
            # Verify this is a valid square
            if (snakeCanMoveToPosition(adjacentSquareCoords[0], adjacentSquareCoords[1], board, treatSquaresAdjacentToSnakeHeadsAsBlocking, snakeId) == False and endSquareCoords != (adjacentSquareCoords[0], adjacentSquareCoords[1])):
                continue
            
            if adjacentSquareCoords in closedList:
                continue
            
            if adjacentSquareCoords not in openList:
                adjacentSquareDistanceToEnd = distanceToCoord(adjacentSquareCoords[0], adjacentSquareCoords[1], endXPosition, endYPosition)
                openList[adjacentSquareCoords] = PathfinderSegment(adjacentSquareCoords, currentSquare.coords, currentSquare.gValue + 1, adjacentSquareDistanceToEnd, currentSquare.gValue + 1 + adjacentSquareDistanceToEnd)
            else:
                if currentSquare.gValue + 1 < openList[adjacentSquareCoords].gValue:
                    openList[adjacentSquareCoords].gValue = currentSquare.gValue + 1
                    openList[adjacentSquareCoords].fValue = openList[adjacentSquareCoords].gValue + openList[adjacentSquareCoords].hValue
    
    return None
    
'''
Returns the direction to move to that would allow the given snake to follow the nearest enemy snake.
'''
def directionToFollowClosestSnake(board, snakes, snakeId):
    snake = snakes[snakeId]
    snakeHead = snake.coords[0]
    boardWidth = len(board)
    boardHeight = len(board[0])
    
    shortestPath = -1
    shortestPathSnakeDirection = None
    
    for otherSnakeId, otherSnake in snakes.items():
        if otherSnakeId == snakeId:
            continue
        
        otherSnakeTail = otherSnake.coords[len(otherSnake.coords) - 1]
        distance = directionForShortestPathBetweenTwoPoints(snakeHead['x'], snakeHead['y'], otherSnakeTail['x'], otherSnakeTail['y'], board)
        
        if distance != None:
            if shortestPath == -1 or distance[0] < shortestPath:
                shortestPath = distance[0]
                shortestPathSnakeDirection = distance[1]
    
    return shortestPathSnakeDirection
    
'''
Returns the direction for the snake to travel in a straight line if it has already moved 2 squares or more in the same direction.
'''
def directionToTravelInAStraightLine(snake):
    move = None;
    
    if snake.coords[0]['x'] == snake.coords[1]['x']:
        if snake.coords[0]['y'] > snake.coords[1]['y']:
            move = "down"
        else:
            move = "up"
    elif snake.coords[0]['y'] == snake.coords[1]['y']:
        if snake.coords[0]['x'] > snake.coords[1]['x']:
            move = "right"
        else:
            move = "left"
            
    return move
    
'''
Given a snake and direction to move, returns whether the snake can get back to its tail from this new position.
'''
def snakeCanGetBackToTail(board, snakes, snakeId, direction):
    snake = snakes[snakeId]
    snakeHead = snake.coords[0]
    snakeTail = snake.coords[len(snake.coords) - 1]
    
    shortestPath = None
    if direction == "left":
        shortestPath = directionForShortestPathBetweenTwoPoints(snakeHead['x'] - 1, snakeHead['y'], snakeTail['x'], snakeTail['y'], board)
    elif direction == "right":
        shortestPath = directionForShortestPathBetweenTwoPoints(snakeHead['x'] + 1, snakeHead['y'], snakeTail['x'], snakeTail['y'], board)
    elif direction == "up":
        shortestPath = directionForShortestPathBetweenTwoPoints(snakeHead['x'], snakeHead['y'] - 1, snakeTail['x'], snakeTail['y'], board)
    elif direction == "down":
        shortestPath = directionForShortestPathBetweenTwoPoints(snakeHead['x'], snakeHead['y'] + 1, snakeTail['x'], snakeTail['y'], board)
    
    if shortestPath != None:
        return True
    
    return False
    
'''
Given a snake and direction to move, determines if another snake can also move into that position and is longer then
our own snake, killing it.
'''
def otherSnakeCanCompeteForSquare(board, snakes, snakeId, direction):
    snake = snakes[snakeId]
    snakeHead = snake.coords[0]
    boardWidth = len(board)
    boardHeight = len(board[0])
    
    if direction == "left":
        xPosition = snakeHead['x'] - 1
        yPosition = snakeHead['y']
    elif direction == "right":
        xPosition = snakeHead['x'] + 1
        yPosition = snakeHead['y']
    elif direction == "up":
        xPosition = snakeHead['x']
        yPosition = snakeHead['y'] - 1
    elif direction == "down":
        xPosition = snakeHead['x']
        yPosition = snakeHead['y'] + 1
    
    adjacentSquaresCoords = [(xPosition - 1, yPosition), (xPosition + 1, yPosition), (xPosition, yPosition - 1), (xPosition, yPosition + 1)]
    for adjacentSquareCoords in adjacentSquaresCoords:
        # Coordinates are outside the board
        if adjacentSquareCoords[0] >= boardWidth or adjacentSquareCoords[0] < 0 or adjacentSquareCoords[1] >= boardHeight or adjacentSquareCoords[1] < 0:
            continue
        
        if isinstance(board[adjacentSquareCoords[0]][adjacentSquareCoords[1]], SnakeSegment):
            snakeSegment = board[adjacentSquareCoords[0]][adjacentSquareCoords[1]]
            if snakeSegment.snakeId == snakeId:
                continue
            
            if snakeSegment.segmentNum == 0 and snakeSegment.totalLength >= snake.totalLength:
                return True
    
    return False
    
'''
Given a snake and direction to move, determines if another snake can also move into that position and is longer then
our own snake, killing it.
'''
def smallerSnakeCanCompeteForSquare(board, snakes, snakeId, direction):
    snake = snakes[snakeId]
    snakeHead = snake.coords[0]
    boardWidth = len(board)
    boardHeight = len(board[0])
    
    if direction == "left":
        xPosition = snakeHead['x'] - 1
        yPosition = snakeHead['y']
    elif direction == "right":
        xPosition = snakeHead['x'] + 1
        yPosition = snakeHead['y']
    elif direction == "up":
        xPosition = snakeHead['x']
        yPosition = snakeHead['y'] - 1
    elif direction == "down":
        xPosition = snakeHead['x']
        yPosition = snakeHead['y'] + 1
    
    adjacentSquaresCoords = [(xPosition - 1, yPosition), (xPosition + 1, yPosition), (xPosition, yPosition - 1), (xPosition, yPosition + 1)]
    for adjacentSquareCoords in adjacentSquaresCoords:
        # Coordinates are outside the board
        if adjacentSquareCoords[0] >= boardWidth or adjacentSquareCoords[0] < 0 or adjacentSquareCoords[1] >= boardHeight or adjacentSquareCoords[1] < 0:
            continue
        
        if isinstance(board[adjacentSquareCoords[0]][adjacentSquareCoords[1]], SnakeSegment):
            snakeSegment = board[adjacentSquareCoords[0]][adjacentSquareCoords[1]]
            if snakeSegment.snakeId == snakeId:
                continue
            
            if snakeSegment.segmentNum == 0 and snakeSegment.totalLength < snake.totalLength:
                return True
    
    return False

'''
Returns true if the specified position is empty (and inside the board). If the space is currently occupied by a snake's
tail, then it will also return true. For all other scenarios, returns false.
'''
def snakeCanMoveToPosition(xPosition, yPosition, board, treatSquaresAdjacentToSnakeHeadsAsBlocking=False, snakeId=None):
    boardWidth = len(board)
    boardHeight = len(board[0])
    
    # Verify that this position is not outside the board area
    if xPosition < 0 or xPosition >= boardWidth:
        return False
    if yPosition < 0 or yPosition >= boardHeight:
        return False
    
    # Verify that this position is not another snake's body
    currentObjectInPosition = board[xPosition][yPosition]
    if isinstance(currentObjectInPosition, SnakeSegment) and not currentObjectInPosition.isTailThatWillMoveNextTurn:
        return False
    
    # Treat squares adjacent to other snake heads as blocked
    if treatSquaresAdjacentToSnakeHeadsAsBlocking:
        adjacentSquaresCoords = [(xPosition - 1, yPosition), (xPosition + 1, yPosition), (xPosition, yPosition - 1), (xPosition, yPosition + 1)]
        for adjacentSquareCoords in adjacentSquaresCoords:
            if adjacentSquareCoords[0] >= boardWidth or adjacentSquareCoords[0] < 0 or adjacentSquareCoords[1] >= boardHeight or adjacentSquareCoords[1] < 0:
                continue
            
            if isinstance(board[adjacentSquareCoords[0]][adjacentSquareCoords[1]], SnakeSegment):
                snakeSegment = board[adjacentSquareCoords[0]][adjacentSquareCoords[1]]
                if snakeSegment.segmentNum == 0 and snakeSegment.snakeId != snakeId:
                    return False
    
    return True

def findOtherSnakeIdInProximityToDirection(board, snakeHead, mySnakeId, direction):
    boardWidth = len(board)
    boardHeight = len(board[0])
    
    xPosition = snakeHead['x']
    yPosition = snakeHead['y']
    
    if direction == "left":
        xPosition -= 1
    elif direction == "right":
        xPosition += 1
    elif direction == "up":
        yPosition -= 1
    elif direction == "down":
        yPosition += 1
        
    adjacentSquaresCoords = [(xPosition - 1, yPosition), (xPosition + 1, yPosition), (xPosition, yPosition - 1), (xPosition, yPosition + 1)]
    for adjacentSquareCoords in adjacentSquaresCoords:
        if adjacentSquareCoords[0] < 0 or adjacentSquareCoords[0] >= boardWidth:
            continue
        if adjacentSquareCoords[1] < 0 or adjacentSquareCoords[1] >= boardHeight:
            continue
        
        currentObjectInPosition = board[adjacentSquareCoords[0]][adjacentSquareCoords[1]]
        if isinstance(currentObjectInPosition, SnakeSegment):
            if currentObjectInPosition.snakeId != mySnakeId:
                return currentObjectInPosition.snakeId
                
    return None

'''
Returns a random direction (in order of left, right, up, and down) that does not kill the given snake.
'''
def randomlySelectValidDirection(board, snakes, snakeId):
    snake = snakes[snakeId]
    snakeHead = snake.coords[0]
    boardWidth = len(board)
    boardHeight = len(board[0])
    
    if snakeCanMoveToPosition(snakeHead['x'] - 1, snakeHead['y'], board) and not otherSnakeCanCompeteForSquare(board, snakes, snakeId, "left"):
        return "left"
    elif snakeCanMoveToPosition(snakeHead['x'] + 1, snakeHead['y'], board) and not otherSnakeCanCompeteForSquare(board, snakes, snakeId, "right"):
        return "right"
    elif snakeCanMoveToPosition(snakeHead['x'], snakeHead['y'] - 1, board) and not otherSnakeCanCompeteForSquare(board, snakes, snakeId, "up"):
        return "up"
    elif snakeCanMoveToPosition(snakeHead['x'], snakeHead['y'] + 1, board) and not otherSnakeCanCompeteForSquare(board, snakes, snakeId, "down"):
        return "down"
    
    return None
    
'''
Determines whether the given direction is a valid move for the given snake (ie. is not a wall or other snake).
'''
def directionIsValid(board, snakes, snakeId, direction):
    snake = snakes[snakeId]
    snakeHead = snake.coords[0]
    boardWidth = len(board)
    boardHeight = len(board[0])
    
    if direction == "left":
        xPosition = snakeHead['x'] - 1
        yPosition = snakeHead['y']
    elif direction == "right":
        xPosition = snakeHead['x'] + 1
        yPosition = snakeHead['y']
    elif direction == "up":
        xPosition = snakeHead['x']
        yPosition = snakeHead['y'] - 1
    elif direction == "down":
        xPosition = snakeHead['x']
        yPosition = snakeHead['y'] + 1
    
    return snakeCanMoveToPosition(xPosition, yPosition, board)

'''
Returns the exact distance to the selected space in squares.
'''
def distanceToCoord(startXPosition, startYPosition, endXPosition, endYPosition):
    if startXPosition == endXPosition and startYPosition == endYPosition:
        return 0
    
    return abs(startXPosition - endXPosition) + abs(startYPosition - endYPosition)

'''
Generates a two dimensional board.
Each square with a snake in it contains a SnakeSegment object (containing the snake ID, segment number, length and 
health of the snake it is a part of).
Each square with food in it contains a food value (F).
Each blank square contains an empty value (0).
'''
def generateBoard(height, width, snakes, foods):
    board = [[0 for x in range(height)] for y in range(width)]
    
    for food in foods:
        board[food['x']][food['y']] = "F"
        
    for snake in snakes:
        i = 0
        segments = snake['body']['data']
        
        for coords in segments:
            # Check that this isn't already the head (when the snake starts, all body segments are on top of its head)
            if board[coords['x']][coords['y']]:
                continue;
                
            # Determine whether this segment will move next turn (only valid for a tail and not at the start of the game)
            isTailThatWillMoveNextTurn = False
            if i == len(segments)-1 and segments[i] != segments[i-1]:
                isTailThatWillMoveNextTurn = True
            
            snakeSegment = SnakeSegment(snake['id'], i, len(segments), snake['health'], isTailThatWillMoveNextTurn)
            board[coords['x']][coords['y']] = snakeSegment
            i += 1
    
    return board
    
'''
Returns a clone board object, with the selected snake moved to the given coordinates
'''
def moveSnakeInBoard(board, snakes, snakeId, headXPosition, headYPosition):
    snake = snakes[snakeId]
    
    # Perform a deep clone
    boardClone = deepcopy(board)
    
    boardClone[headXPosition][headYPosition] = SnakeSegment(snakeId, 0, snake.totalLength, snake.health, False)
    for i in range(0, snake.totalLength - 2):
        boardClone[snake.coords[i]['x']][snake.coords[i]['y']].segmentNum += 1
    
    if snake.coords[snake.totalLength - 2] != snake.coords[snake.totalLength - 1]:
        boardClone[snake.coords[snake.totalLength-1]['x']][snake.coords[snake.totalLength-1]['y']] = None
    
    return boardClone
    
'''
Generates a dictionary, with the key being the snake ID and the value being an object containing information about
the snake.
'''
def generateSnakesLookup(snakes):
    snakesLookup = {}
    
    # Process each of the snakes
    for snake in snakes:
        id = snake['id']
        health = snake['health']
        coords = snake['body']['data']
        
        snakeLookup = Snake(len(coords), health, coords)
        snakesLookup[id] = snakeLookup
    
    return snakesLookup
    
class PathfinderSegment:
    def __init__(self, coords, parent, gValue, hValue, fValue):
        self.coords = coords
        self.parent = parent
        self.gValue = gValue
        self.hValue = hValue
        self.fValue = fValue
    
class Snake:
    def __init__(self, totalLength, health, coords):
        self.totalLength = totalLength
        self.health = health
        self.coords = coords

class SnakeSegment:
    def __init__(self, snakeId, segmentNum, totalLength, health, isTailThatWillMoveNextTurn):
        self.snakeId = snakeId
        self.segmentNum = segmentNum
        self.totalLength = totalLength
        self.health = health
        self.isTailThatWillMoveNextTurn = isTailThatWillMoveNextTurn

application = bottle.default_app()

if __name__ == '__main__':
    bottle.run(
        application,
        host=os.getenv('IP', '0.0.0.0'),
        port=os.getenv('PORT', '8080'),
        debug = True)
