import bottle
import os
import random

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
        'head_url': 'http://icons.iconarchive.com/icons/blackvariant/button-ui-requests-13/96/Snake-icon.png',
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

    # Generate lookup objects 
    board = generateBoard(boardHeight, boardWidth, snakes, foods)
    snakesLookup = generateSnakesLookup(snakes)
    
    mySnake = snakesLookup[snakeId]
    
    move = None
    moveDecided = False
    
    # TODO: Find path to largest open space?
    
    # TODO: Determine if we can make a move that will mean another snake is not able to return to its tail?
    
    # TODO: What is the safest route to get back to my tail (calculate several turns in the future)
    
    # Routine 1: Go towards food (only if within 3 spaces of health less than 25)
    moveForFood = directionToReachClosestPieceOfFood(board, snakesLookup, snakeId, foods)
    if moveForFood != None and ((mySnake.health < 50 and moveForFood[0] < 3) or mySnake.health < 25):
        # Ensure we are still able to return to our tail
        if snakeCanGetBackToTail(board, snakesLookup, snakeId, moveForFood[1]):
            moveDecided = True
            move = moveForFood[1]
            
    # Routine 2: Follow a snake's tail
    if not moveDecided:
        moveForSnakeToFollow = directionToFollowClosestSnake(board, snakesLookup, snakeId)
        if (moveForSnakeToFollow != None):
            if snakeCanGetBackToTail(board, snakesLookup, snakeId, moveForSnakeToFollow) and directionIsValid(board, snakesLookup, snakeId, moveForSnakeToFollow) and not otherSnakeCanCompeteForSquare(board, snakesLookup, snakeId, moveForSnakeToFollow):
                moveDecided = True
                move = moveForSnakeToFollow
            
    # Routine 3: Select the direction with the shortest path to getting back to our tail
    if not moveDecided and (mySnake.totalLength > 3 or mySnake.coords[len(mySnake.coords) - 1] != mySnake.coords[len(mySnake.coords) - 2]):
        snakeHead = mySnake.coords[0]
        snakeTail = mySnake.coords[len(mySnake.coords) - 1]
        shortestPathToTail = directionForShortestPathBetweenTwoPoints(snakeHead['x'], snakeHead['y'], snakeTail['x'], snakeTail['y'], board)
        
        # Ensure we are still able to return to our tail and that the space is not occupied by anything else
        if shortestPathToTail != None and shortestPathToTail[1] != None and not otherSnakeCanCompeteForSquare(board, snakesLookup, snakeId, shortestPathToTail[1]) and directionIsValid(board, snakesLookup, snakeId, shortestPathToTail[1]):
            moveDecided = True
            move = shortestPathToTail[1]
        
    # Routine 4: Randomly select a direction that does not immediately kill our snake
    if not moveDecided:
        randomValidMove = randomlySelectValidDirection(board, snakesLookup, snakeId)
        if randomValidMove != None:
            moveDecided = True
            move = randomValidMove
        
    # Routine Final: No safe direction; goodbye cruel world
    if not moveDecided:
        move = "down"
    
    #print move
    return {
        'move': move,
        'taunt': 'TAUNT'
    }
    
'''
Calculates the direction to go in order to reach the closest piece of food (does not include food that is closer to
other snakes or at an equal distance to other snakes that are larger than us).
Returns a tuple, with the first item being the distance to the food, and the second item being the direction to 
move to get closer to it.
'''
def directionToReachClosestPieceOfFood(board, snakes, snakeId, foods):
    bestDirection = None
    shortestDistance = -1
    
    snakeHead = snakes[snakeId].coords[0]
    
    test = len(foods)
    
    for i in xrange(len(foods)):
        food = foods[i]
    
        # Calculate shortest path to the food
        shortestPathToFood = directionForShortestPathBetweenTwoPoints(snakeHead['x'], snakeHead['y'], food['x'], food['y'], board)
        if shortestPathToFood == None:
            continue
        
        distance = shortestPathToFood[0]
        direction = shortestPathToFood[1]
        
        # Check that we haven't already found food that is closer than this
        if distance >= shortestDistance and shortestDistance != -1:
            continue
        
        # Determine whether another snake is closer to the food than us
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
    
'''
Calculates the shortest path in a grid with obstacles in an extremely computationally efficient way.
Returns a tuple, with the first item being the length of the path, and the second item being the
immediate direction to travel in order to follow that path.
https://www.raywenderlich.com/4946/introduction-to-a-pathfinding
'''
def directionForShortestPathBetweenTwoPoints(startXPosition, startYPosition, endXPosition, endYPosition, board):
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
            if (snakeCanMoveToPosition(adjacentSquareCoords[0], adjacentSquareCoords[1], board) == False and endSquareCoords != (adjacentSquareCoords[0], adjacentSquareCoords[1])):
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
Given a snake and direction to move, returns whether the snake can get back to its tail from this new position.
'''
def snakeCanGetBackToTail(board, snakes, snakeId, direction):
    snake = snakes[snakeId]
    snakeHead = snake.coords[0]
    snakeTail = snake.coords[len(snake.coords) - 1]
    boardWidth = len(board)
    boardHeight = len(board[0])
    
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
        if adjacentSquareCoords[0] >= boardWidth or adjacentSquareCoords[1] >= boardHeight:
            continue
        
        if isinstance(board[adjacentSquareCoords[0]][adjacentSquareCoords[1]], SnakeSegment):
            snakeSegment = board[adjacentSquareCoords[0]][adjacentSquareCoords[1]]
            if snakeSegment.snakeId == snakeId:
                continue
            
            if snakeSegment.segmentNum == 0 and snakeSegment.totalLength >= snake.totalLength:
                return True
    
    return False

'''
Returns true if the specified position is empty (and inside the board). If the space is currently occupied by a snake's
tail, then it will also return true. For all other scenarios, returns false.
'''
def snakeCanMoveToPosition(xPosition, yPosition, board):
    boardWidth = len(board)
    boardHeight = len(board[0])
    
    # Verify that this position is not outside the board area
    if xPosition < 0 or xPosition >= boardWidth:
        return False
    if yPosition < 0 or yPosition >= boardHeight:
        return False
    
    # Verify that this position is not another snake's body
    currentObjectInPosition = board[xPosition][yPosition]
    if isinstance(currentObjectInPosition, SnakeSegment):
        return currentObjectInPosition.isTailThatWillMoveNextTurn
    
    return True

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