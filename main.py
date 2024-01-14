from flask import Flask, render_template, request, redirect, make_response
from flask_sqlalchemy import SQLAlchemy
import secrets
import datetime
import json
import math
import os
from random import randint

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['DEFAULT_LANGUAGE'] = 'en_EN'
app.config['DEFAULT_RANGE_TO'] = 20
app.config['DEFAULT_HARD_MODE'] = False

db_url = os.getenv("DATABASE_URL")
print(db_url)
db = SQLAlchemy(db_url)

class Sessions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_hex = db.Column(db.String(64), unique=True, nullable = False)
    range_to = db.Column(db.Integer, nullable = False, default = app.config['DEFAULT_RANGE_TO'])
    hard_mode = db.Column(db.Boolean, nullable = False, default = app.config['DEFAULT_HARD_MODE'])
    language = db.Column(db.String, nullable = False, default = app.config['DEFAULT_LANGUAGE'])
    expires = db.Column(db.DateTime, nullable = False, default = datetime.datetime.now() + datetime.timedelta(days=180))
    games = db.relationship('Games', backref='games', lazy=True)
    
class Games(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_hex = db.Column(db.String(64), unique=True, nullable = False)
    session = db.Column(db.String, db.ForeignKey('sessions.id'), nullable = False)
    range_to = db.Column(db.Integer, nullable = False)
    hard_mode = db.Column(db.Boolean, nullable = False)
    secret_number = db.Column(db.Integer, nullable = False)
    guess = db.Column(db.Integer, nullable = False)
    max_guesses = db.Column(db.Integer, nullable = False)
    guessed = db.Column(db.Boolean, nullable = False, default=False)
    created = db.Column(db.DateTime, nullable = False)
    results = db.relationship('Results', backref='result', lazy=True)

class Results(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game = db.Column(db.Integer, db.ForeignKey('games.id'), unique=True, nullable = False)
    player = db.Column(db.String, nullable = False)
    guess = db.Column(db.Integer, nullable = False)
    timestamp = db.Column(db.DateTime, nullable = False)
    hard_mode = db.Column(db.Boolean, nullable = False)

with app.app_context():
    db.create_all()

with open('./static/languages.json', 'r', encoding='utf-8') as f:
    game_texts = json.loads(f.read())

with open('./static/title.txt', 'r') as f:
    big_title = f.readlines()

@app.route("/")
def index():

        screen_text = []
        input_id = 'index'

        # I used 'try' insted of 'if' because might exist client-side, but the DB may have been corrupted or deleted
        # so the code would error. This way if the request doesn't contain a cookie or if DB does't have the session
        # data for this hex, the code would 'except' and create a new hex and session.
        
        try:
            session_hex = request.cookies.get("session")
            session_data = db.session.execute(db.select(Sessions).filter_by(session_hex=session_hex)).scalar_one()
            
            label = game_texts[session_data.language]['hello']['label']
            screen_text.extend(game_texts[session_data.language]['hello']['text'].split('\n'))
            
            response = make_response(render_template('index.html', title=True, big_title=big_title, screen_text=screen_text, input_id=input_id, label=label))
            response.set_cookie("session", session_hex, expires=datetime.datetime.now() + datetime.timedelta(days=180))
            
            # At every GET request of "/" we extended the expiration of the session cookie, write the change to DB
            session_data.expires = datetime.datetime.now() + datetime.timedelta(days=180)
            db.session.commit()
        
        except:
            session_hex = secrets.token_hex(32)
            
            screen_text.extend(game_texts[app.config['DEFAULT_LANGUAGE']]['hello']['text'].split('\n'))
            label = game_texts[app.config['DEFAULT_LANGUAGE']]['hello']['label']

            current_session = Sessions(session_hex=session_hex)
            db.session.add(current_session)
            db.session.commit()
            
            response = make_response(render_template('index.html', title=True, big_title=big_title, screen_text=screen_text, input_id=input_id, label=label))
            response.set_cookie("session", session_hex, expires=datetime.datetime.now() + datetime.timedelta(days=180))
        
        return response

@app.route("/game", methods=["GET", "POST"])
def game():

    session_hex = request.cookies.get("session")
    session_data = db.session.execute(db.select(Sessions).filter_by(session_hex=session_hex)).scalar_one()
    
    screen_text = []
    input_id = 'game'
    
    if request.method == "GET":
        
        game_hex = secrets.token_hex(32)

        new_game = Games(
            session = session_data.id, 
            game_hex = game_hex,
            range_to = session_data.range_to,
            hard_mode = session_data.hard_mode,
            secret_number = randint(1, session_data.range_to),
            guess = 1,
            max_guesses = math.ceil((session_data.range_to)/4),
            created = datetime.datetime.now()
            )
        
        db.session.add(new_game)
        db.session.commit()
        
        screen_text.append(game_texts[session_data.language]['game']['guesses'].replace('%1', str(new_game.guess)).replace('%2', str(new_game.max_guesses)))
        label = game_texts[session_data.language]['game']['label'].replace('%1', str(new_game.range_to))

        response = make_response(render_template('index.html', title=True, big_title=big_title, screen_text=screen_text, input_id=input_id, label=label))
        response.set_cookie("game", game_hex, expires=datetime.datetime.now() + datetime.timedelta(seconds=120))
        
        return response

    else:
        game_hex = request.cookies.get("game")
        game_data = db.session.execute(db.select(Games).filter_by(game_hex=game_hex)).scalar_one()
        user_guess = int(request.form.get('user-input')) if request.form.get('user-input').isnumeric() else 0
        label = game_texts[session_data.language]['game']['label'].replace('%1', str(game_data.range_to))

        if user_guess == game_data.secret_number:
            screen_text.append(game_texts[session_data.language]['game']['success'])
            label = game_texts[session_data.language]['game']['name']
            input_id = 'winner'
            
            game_data.guessed = True
            db.session.commit()

        elif game_data.guess <= game_data.max_guesses:
            screen_text.append(game_texts[session_data.language]['game']['guesses'].replace('%1', str(game_data.guess)).replace('%2', str(game_data.max_guesses)))
            screen_text.append('')
            
            if not game_data.hard_mode and user_guess > 0:
                if user_guess < game_data.secret_number:
                    screen_text.append(game_texts[session_data.language]['game']['hint']['higher'])
                else:
                    screen_text.append(game_texts[session_data.language]['game']['hint']['lower'])
        
        else:
            screen_text.append(game_texts[session_data.language]['game']['fail'].replace('%1', str(game_data.secret_number)))
            label = game_texts[session_data.language]['game']['playagain']
            input_id = 'play-again'
        
            response = make_response(render_template('index.html', title=True, big_title=big_title, screen_text=screen_text, input_id=input_id, label=label))
            response.set_cookie("game", game_hex, expires=1)

            return response
        
        return render_template('index.html', title=True, big_title=big_title, screen_text=screen_text, input_id=input_id, label=label)


@app.route("/highscores")
def highscores():
    
    session_hex = request.cookies.get("session")
    session_data = db.session.execute(db.select(Sessions).filter_by(session_hex=session_hex)).scalar_one()
    
    screen_text = []
    
    input_id = 'highscores'
    label = game_texts[session_data.language]['highscores']['label']
    
    highscores = Results.query.order_by(Results.guess.asc()).order_by(Results.hard_mode.desc()).order_by(Results.timestamp.asc()).limit(10).all()
    
    if highscores == []:
        screen_text = ['No highscores yet.']
        input_id = 'no-highscores'
    else:
        screen_text.append([game_texts[session_data.language]['highscores']['player'], 
                            game_texts[session_data.language]['highscores']['date'],
                            game_texts[session_data.language]['highscores']['guess'],
                            game_texts[session_data.language]['highscores']['mode']])
    
        for highscore in highscores:
            game_mode = 'HARD' if highscore.hard_mode == True else 'EASY'
            screen_text.append(
                [
                    highscore.player,
                    datetime.datetime.strftime(highscore.timestamp, '%d.%m.%Y'),
                    highscore.guess,
                    game_mode
                ]
            )
    
    return render_template('index.html', title=True, big_title=big_title, screen_text=screen_text, input_id=input_id, label=label)

@app.route("/settings", methods=["GET", "POST"])
def settings():
    
    screen_text = []
    input_id = 'settings'
    session_hex = request.cookies.get("session")
    session_data = db.session.execute(db.select(Sessions).filter_by(session_hex=session_hex)).scalar_one()
    
    if request.method == "GET":

        if session_data.hard_mode:
            game_mode = game_texts[session_data.language]['settings']['diff'].replace('%1', 'HARD')
        else:
            game_mode = game_texts[session_data.language]['settings']['diff'].replace('%1', 'EASY')
        
        screen_text.extend(game_texts[session_data.language]['settings']['choices'].split('\n'))
        screen_text.append('')
        screen_text.append(game_mode)

        label = game_texts[session_data.language]['settings']['label']

        return render_template('index.html', title=True, big_title=big_title, screen_text=screen_text, input_id=input_id, label=label)

    else:
        setting = request.args.get('id')
        
        if setting == 'range':
            input_id = 'settings-range'
            label = game_texts[session_data.language]['settings']['ranges']
            return render_template('index.html', title=True, big_title=big_title, screen_text=screen_text, input_id=input_id, label=label)
        
        elif setting == 'lang':
            input_id = 'settings-lang'
            
            for i in range(len(game_texts['languages'])):
                letter = chr(i+97).upper()
                screen_text.append(letter + ') ' + game_texts['languages'][i][0])
            
            label = game_texts[session_data.language]['settings']['label']
            
            return render_template('index.html', title=True, big_title=big_title, screen_text=screen_text, input_id=input_id, label=label)
        
        return render_template('index.html', title=True, big_title=big_title, screen_text=screen_text, input_id=input_id, label=label)

@app.route("/input", methods=["POST"])
def input():
    
    choice = request.form.get('user-input').upper()
    current_page = request.args.get('id')
    
    # If for some reason the user has not a valid session cookie, he will be redirected to the main menu to create a new session.
    try:
        session_hex = request.cookies.get("session")
        session_data = db.session.execute(db.select(Sessions).filter_by(session_hex=session_hex)).scalar_one()
    except:
        return redirect("/")
    
    if current_page == 'index':
        if choice == 'A':
            return redirect("/game")
        elif choice == 'B':
            return redirect("/highscores")
        elif choice == 'C':
            return redirect("/settings")
        else:
            return redirect("/")
    
    elif current_page == 'game':
        
        if choice.isnumeric():
            # We increment the guess of the current game
            game_hex = request.cookies.get("game")
            game_data = db.session.execute(db.select(Games).filter_by(game_hex=game_hex)).scalar_one()
            game_data.guess += 1
            db.session.commit()
        
        return redirect("/game", code=307)
    
    elif current_page == 'play-again':
        if choice == 'Y':
            return redirect("/game")
        else:
            return redirect("/")
    
    elif current_page == 'settings':
        # Option A changes the upper range of the possible secret number
        if choice == 'A':
            return redirect("/settings?id=range", code=307)
        
        # Option B changes game difficulty
        elif choice == 'B':
            
            session_data.hard_mode = not session_data.hard_mode
            db.session.commit()
            
            return redirect("/settings")
        
        # Option C changes the language
        elif choice == 'C':
            return redirect("/settings?id=lang", code=307)
        
        else:
            return redirect("/")
    
    elif current_page == 'settings-range':
        if choice.isnumeric() and int(choice) > 0:
            session_data.range_to = int(choice)
            db.session.commit()
        
            return redirect("/settings")
        else:
            return redirect("/settings?id=range", code=307)
    
    elif current_page == 'settings-lang':
        letter_number = ord(choice) - 65
        
        if letter_number > len(game_texts['languages'])-1:
            return redirect("/settings?id=lang", code=307)
            
        else:
            session_data.language = game_texts['languages'][letter_number][1]
            db.session.commit()
        
            return redirect("/settings")
    
    elif current_page == 'winner':
        screen_text = []

        game_hex = request.cookies.get("game")
        game_data = db.session.execute(db.select(Games).filter_by(game_hex=game_hex)).scalar_one()

        result = Results(
            game = game_data.id,
            player = choice,
            guess = game_data.guess-1,
            timestamp = datetime.datetime.now(),
            hard_mode = game_data.hard_mode
        )

        db.session.add(result)
        db.session.commit()

        highscores = Results.query.order_by(Results.guess.asc()).order_by(Results.hard_mode.desc()).order_by(Results.timestamp.asc()).limit(10).all()
        result = 0
        
        for i in range(len(highscores)):
            if game_data.id == highscores[i].game:
                result = i + 1
                break

        if result == 1:
            screen_text.append(game_texts[session_data.language]['game']['highscore'])
        elif result > 1:
            screen_text.append(game_texts[session_data.language]['game']['highscore_top10'])

        label = game_texts[session_data.language]['game']['playagain']
        input_id = 'play-again'

        return render_template('index.html', title=True, big_title=big_title, screen_text=screen_text, input_id=input_id, label=label)
    
    elif 'highscores' in current_page:
        return redirect("/")


if __name__ == '__main__':
    app.run()
