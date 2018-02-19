import bottle
import os
import random

@bottle.route('/')
def static():
    return "the server is running"

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
        'head_type': 'pixel',
        'tail_type': 'pixel'
    }

@bottle.post('/move')
def move():
    data = bottle.request.json

    # TODO: Do things with data
    
    directions = ['up', 'down', 'left', 'right']
    direction = random.choice(directions)
    print direction
    return {
        'move': direction,
        'taunt': 'TAUNT'
    }

application = bottle.default_app()

if __name__ == '__main__':
    bottle.run(
        application,
        host=os.getenv('IP', '0.0.0.0'),
        port=os.getenv('PORT', '8080'),
        debug = True)