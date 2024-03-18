from http.client import BAD_REQUEST, HTTPException
import os
import sqlite3
import traceback
from flask import Flask, request, session, g, redirect, url_for, abort, \
    render_template, flash
import requests
import werkzeug

app = Flask(__name__)  # create the application instance :)
app.config.from_object(__name__)  # load config from this file , flaskr.py

# Load default config and override config from an environment variable
# TODO use for db path http://flask.pocoo.org/docs/0.12/config/#instance-folders
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'flaskr.db'),
    SECRET_KEY='development key',
    USERNAME='admin',
    PASSWORD='default'
))

# FLASKR_SETTINGS points to a config file
app.config.from_envvar('FLASKR_SETTINGS', silent=True)

def init_db():
    db = get_db()
    # maybe create a migrations flow
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()


@app.cli.command('initdb')
def initdb_command():
    """Initializes the database."""
    init_db()
    print('Initialized the database.')


def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv


def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db


@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


@app.route('/')
def show_entries():
    db = get_db()
    cur = db.execute('SELECT title, text, created_at FROM entries ORDER BY id DESC')
    entries = cur.fetchall()
    return render_template('show_entries.html', entries=entries)


@app.route('/add', methods=['POST'])
def add_entry():
    if not session.get('logged_in'):
        abort(401)

    newTodo  = {
        'id': None,
        'title': request.form['title'],
        'text': request.form['text']
    }

    if not newTodo['title']:
        raise werkzeug.exceptions.BadRequest('Title is required')
        
    if not newTodo['text']:
        raise werkzeug.exceptions.BadRequest('Text is required')

    try:
        db = get_db()
        cur = db.execute('INSERT INTO entries (title, text) VALUES (?, ?)',
                [request.form['title'], request.form['text']])
        newTodo['id'] = cur.lastrowid

        # this could be done in an async way (event, queue, etc)
        res = requests.post('https://postman-echo.com/post', json=newTodo)
        res.raise_for_status()

        db.commit()

    except sqlite3.Error as e:
        traceback.print_exc()
        app.logger.error('Database error', exc_info=e)
        db.rollback()
        # maybe check for specific error codes
        raise werkzeug.exceptions.InternalServerError('Database error')
   
    except requests.exceptions.RequestException as e:
        traceback.print_exc()
        app.logger.error('Postman echo error', exc_info=e)
        db.rollback()
        raise werkzeug.exceptions.InternalServerError('Postman echo error')
    
    flash('New entry was successfully posted')
    return redirect(url_for('show_entries'))

@app.route('/api/search', methods=['GET'])
def search():
    search_param = request.args.get('q') or ''
    filter = '%' + search_param + '%'

    db = get_db()
    cur = db.execute('SELECT title, text, created_at FROM entries WHERE title LIKE ? ORDER BY id DESC', [filter])
    entries = cur.fetchall()

    serializable = [dict(ix) for ix in entries]
    return serializable


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] != app.config['USERNAME']:
            error = 'Invalid username'
        elif request.form['password'] != app.config['PASSWORD']:
            error = 'Invalid password'
        else:
            session['logged_in'] = True
            flash('You were logged in')
            return redirect(url_for('show_entries'))
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You were logged out')
    return redirect(url_for('show_entries'))
