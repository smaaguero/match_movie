from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, get_flashed_messages
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import random
import requests
import os

app = Flask(__name__)

# --- Configuración de Claves desde Variables de Entorno ---
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')

# Verificar que las claves estén configuradas
if not app.config['SECRET_KEY']:
    raise RuntimeError("FLASK_SECRET_KEY not set in environment variables. Please set it.")
if not TMDB_API_KEY:
    raise RuntimeError("TMDB_API_KEY not set in environment variables. Please set it.")
# ---------------------------------------------------------

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500/"
TMDB_YOUTUBE_BASE_URL = "https://www.youtube.com/embed/"

# Global variables for movie data and genres
m_db = []
genres_map = {}

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    preferences = db.relationship('UserMoviePreference', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# User Movie Preference Model
class UserMoviePreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_title = db.Column(db.String(255), nullable=False)
    tmdb_id = db.Column(db.Integer, nullable=True) # New: Store TMDb ID
    genres = db.Column(db.String(255), nullable=True) # New: Store genres as string
    preference = db.Column(db.Boolean, nullable=False) # True for liked, False for disliked

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/genres')
def get_genres():
    genres_list = []
    for gid, gname in genres_map.items():
        genres_list.append({'id': gid, 'name': gname})
    return jsonify(genres_list)

def fetch_genres():
    global genres_map
    genres_url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={TMDB_API_KEY}&language=en-US"
    response = requests.get(genres_url)
    data = response.json()
    if data and 'genres' in data:
        genres_map = {genre['id']: genre['name'] for genre in data['genres']}

def get_movie_trailer(movie_id):
    videos_url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={TMDB_API_KEY}&language=en-US"
    response = requests.get(videos_url)
    data = response.json()
    if data['results']:
        for video in data['results']:
            if video['site'] == 'YouTube' and video['type'] == 'Trailer':
                return TMDB_YOUTUBE_BASE_URL + video['key']
    return None

def get_movie_cast(movie_id):
    credits_url = f"https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={TMDB_API_KEY}&language=en-US"
    response = requests.get(credits_url)
    data = response.json()
    cast = []
    if data and 'cast' in data:
        for member in data['cast'][:5]: # Get top 5 cast members
            cast.append(member['name'])
    return ", ".join(cast)

def fetch_top_rated_movies(num_pages=5):
    global m_db
    m_db = [] # Clear existing movies
    for page in range(1, num_pages + 1):
        url = f"https://api.themoviedb.org/3/movie/top_rated?api_key={TMDB_API_KEY}&language=en-US&page={page}"
        response = requests.get(url)
        data = response.json()
        if data['results']:
            for movie in data['results']:
                if movie.get('vote_average') and movie.get('vote_count', 0) > 50: # Filter for reasonable score and votes
                    trailer_url = get_movie_trailer(movie['id'])
                    cast = get_movie_cast(movie['id'])
                    genres_names = [genres_map.get(gid) for gid in movie.get('genre_ids', []) if gid in genres_map]
                    
                    m_db.append({
                        "id": movie['id'], # New: Store TMDb ID
                        "title": movie['title'],
                        "score": movie['vote_average'],
                        "poster_url": TMDB_IMAGE_BASE_URL + movie['poster_path'] if movie.get('poster_path') else None,
                        "trailer_url": trailer_url,
                        "overview": movie.get('overview', 'No overview available.'),
                        "release_date": movie.get('release_date', 'N/A'),
                        "genres": ", ".join(genres_names),
                        "genre_ids": movie.get('genre_ids', []), # Store genre IDs
                        "cast": cast
                    })
    print(f"Fetched {len(m_db)} movies from TMDb.")

# Fetch movies on startup
with app.app_context():
    # db.drop_all() # DANGER: Only for development, drops all tables
    db.create_all()
    fetch_genres()
    fetch_top_rated_movies()

@app.route('/')
def index():
    # Pass flash messages to the template
    flashed_messages = get_flashed_messages(with_categories=True)
    return render_template('index.html', flashed_messages=flashed_messages)

@app.route('/status')
def status():
    if current_user.is_authenticated:
        return jsonify({'isLoggedIn': True, 'username': current_user.username})
    else:
        return jsonify({'isLoggedIn': False, 'username': None})

@app.route('/random-movie')
def random_movie():
    selected_genres_str = request.args.get('genres')
    selected_genre_ids = []
    if selected_genres_str:
        selected_genre_ids = [int(x) for x in selected_genres_str.split(',')]

    selected_movies = []
    if current_user.is_authenticated:
        liked_preferences = UserMoviePreference.query.filter_by(user_id=current_user.id, preference=True).all()
        if liked_preferences:
            liked_genres_names = set()
            for pref in liked_preferences:
                if pref.genres:
                    liked_genres_names.update(pref.genres.split(', '))
            
            if liked_genres_names:
                # Prioritize movies with liked genres
                for movie in m_db:
                    movie_genres_names = set(movie['genres'].split(', '))
                    if any(g in liked_genres_names for g in movie_genres_names):
                        # Apply additional genre filter if selected
                        if not selected_genre_ids or any(gid in selected_genre_ids for gid in movie.get('genre_ids', [])):
                            selected_movies.append(movie)
    
    if not selected_movies:
        # Fallback to all movies if no liked genres or no matches, applying selected genre filter
        if selected_genre_ids:
            for movie in m_db:
                if any(gid in selected_genre_ids for gid in movie.get('genre_ids', [])):
                    selected_movies.append(movie)
        else:
            selected_movies = m_db

    if selected_movies:
        random_movie_data = random.choice(selected_movies)
        movie_data = {
            "id": random_movie_data['id'],
            "title": random_movie_data['title'],
            "score": round(random_movie_data['score'], 2),
            "poster_url": random_movie_data['poster_url'],
            "trailer_url": random_movie_data['trailer_url'],
            "overview": random_movie_data['overview'],
            "release_date": random_movie_data['release_date'],
            "genres": random_movie_data['genres'],
            "genre_ids": random_movie_data.get('genre_ids', []), # Include genre IDs
            "cast": random_movie_data['cast']
        }
    else:
        movie_data = {
            "id": None,
            "title": "No movies available with the selected criteria.",
            "score": 0,
            "poster_url": None,
            "trailer_url": None,
            "overview": "",
            "release_date": "",
            "genres": "",
            "genre_ids": [],
            "cast": ""
        }
    return jsonify(movie_data)

@app.route('/search-movie')
def search_movie():
    query = request.args.get('query')
    selected_genres_str = request.args.get('genres')
    selected_genre_ids = []
    if selected_genres_str:
        selected_genre_ids = [int(x) for x in selected_genres_str.split(',')]

    if not query:
        return jsonify({"error": "Query parameter is missing"}), 400

    search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}&language=en-US"
    response = requests.get(search_url)
    data = response.json()

    results = []
    if data['results']:
        for movie in data['results']:
            genres_names = [genres_map.get(gid) for gid in movie.get('genre_ids', []) if gid in genres_map]
            
            # Apply genre filter to search results
            if not selected_genre_ids or any(gid in selected_genre_ids for gid in movie.get('genre_ids', [])):
                trailer_url = get_movie_trailer(movie['id'])
                cast = get_movie_cast(movie['id'])
                results.append({
                    "id": movie['id'],
                    "title": movie['title'],
                    "score": movie.get('vote_average', 0),
                    "poster_url": TMDB_IMAGE_BASE_URL + movie['poster_path'] if movie.get('poster_path') else None,
                    "trailer_url": trailer_url,
                    "overview": movie.get('overview', 'No overview available.'),
                    "release_date": movie.get('release_date', 'N/A'),
                    "genres": ", ".join(genres_names),
                    "genre_ids": movie.get('genre_ids', []), # Include genre IDs
                    "cast": cast
                })
    return jsonify(results)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('That username is already taken. Please choose a different one.', 'danger')
            return redirect(url_for('register'))

        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('You have been logged in!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/movie-preference', methods=['POST'])
@login_required
def movie_preference():
    data = request.get_json()
    movie_title = data.get('title')
    tmdb_id = data.get('id') # New: Get TMDb ID
    genres = data.get('genres') # New: Get genres
    preference = data.get('preference') # True for liked, False for disliked

    if not movie_title or preference is None or tmdb_id is None or genres is None:
        return jsonify({"error": "Missing movie title, ID, genres or preference"}), 400

    # Check if preference already exists for this user and movie
    existing_preference = UserMoviePreference.query.filter_by(
        user_id=current_user.id,
        movie_title=movie_title
    ).first()

    if existing_preference:
        existing_preference.preference = preference
        existing_preference.tmdb_id = tmdb_id
        existing_preference.genres = genres
    else:
        new_preference = UserMoviePreference(
            user_id=current_user.id,
            movie_title=movie_title,
            tmdb_id=tmdb_id,
            genres=genres,
            preference=preference
        )
        db.session.add(new_preference)
    
    db.session.commit()
    return jsonify({"message": "Preference saved successfully"}), 200

@app.route('/liked-movies')
@login_required
def liked_movies():
    liked_movie_titles = [p.movie_title for p in current_user.preferences if p.preference == True]
    # For now, we'll just return the titles. We could fetch more details from TMDb if needed.
    return jsonify(liked_movie_titles)

if __name__ == 'main':
    app.run(debug=True, port=5001)