from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, get_flashed_messages
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import random
import requests
import os

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Forbidden: You do not have administrative access.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

app = Flask(__name__)

# --- Configuración de Claves desde Docker Secrets o Archivos ---
def get_secret(secret_name):
    try:
        # La ruta estándar para Docker Secrets
        with open(f'/run/secrets/{secret_name}', 'r') as secret_file:
            return secret_file.read().strip()
    except IOError:
        # Fallback para desarrollo local sin Docker Compose (opcional)
        # o si el secret no se encuentra
        return os.environ.get(secret_name.upper())

app.config['SECRET_KEY'] = get_secret('flask_secret_key')
TMDB_API_KEY = get_secret('tmdb_api_key')

# Verificar que las claves estén configuradas
if not app.config['SECRET_KEY']:
    raise RuntimeError("FLASK_SECRET_KEY could not be found in Docker Secrets or environment variables.")
if not TMDB_API_KEY:
    raise RuntimeError("TMDB_API_KEY could not be found in Docker Secrets or environment variables.")
# ---------------------------------------------------------

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500/"
TMDB_YOUTUBE_BASE_URL = "https://www.youtube.com/embed/"

# Global variables for movie data and genres
# Global variables for movie data and genres
# 

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False) # New: Admin flag
    preferences = db.relationship('UserMoviePreference', backref='user', lazy=True)

    # Friends relationship
    friends_a = db.relationship('Friendship', foreign_keys='Friendship.user_id', backref='user_a', lazy='dynamic')
    friends_b = db.relationship('Friendship', foreign_keys='Friendship.friend_id', backref='user_b', lazy='dynamic')

    def get_friends(self):
        # Get friends where current user is user_id
        as_user_a = Friendship.query.filter_by(user_id=self.id).all()
        # Get friends where current user is friend_id
        as_user_b = Friendship.query.filter_by(friend_id=self.id).all()

        friends = []
        for friendship in as_user_a:
            friends.append(db.session.get(User, friendship.friend_id))
        for friendship in as_user_b:
            friends.append(db.session.get(User, friendship.user_id))
        return friends

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'friend_id', name='_user_friend_uc'),)

# User Movie Preference Model
class UserMoviePreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_title = db.Column(db.String(255), nullable=False)
    tmdb_id = db.Column(db.Integer, nullable=True) # New: Store TMDb ID
    genres = db.Column(db.String(255), nullable=True) # New: Store genres as string
    preference = db.Column(db.Boolean, nullable=False) # True for liked, False for disliked

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True) # Our internal ID
    tmdb_id = db.Column(db.Integer, unique=True, nullable=False) # TMDb ID
    title = db.Column(db.String(255), nullable=False)
    score = db.Column(db.Float, nullable=True)
    poster_url = db.Column(db.String(255), nullable=True)
    trailer_url = db.Column(db.String(255), nullable=True)
    overview = db.Column(db.Text, nullable=True)
    release_date = db.Column(db.String(50), nullable=True)
    genres = db.Column(db.String(255), nullable=True) # Comma-separated genre names
    genre_ids = db.Column(db.String(255), nullable=True) # Comma-separated genre IDs
    cast = db.Column(db.String(500), nullable=True) # Comma-separated cast names

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/genres')
def get_genres():
    genres_list = []
    genres_map = app.config.get('GENRES_MAP', {})
    for gid, gname in genres_map.items():
        genres_list.append({'id': gid, 'name': gname})
    return jsonify(genres_list)

def fetch_genres():
    genres_url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={TMDB_API_KEY}&language=en-US"
    try:
        response = requests.get(genres_url)
        response.raise_for_status() # Raise an exception for HTTP errors
        data = response.json()
        if data and 'genres' in data:
            app.config['GENRES_MAP'] = {genre['id']: genre['name'] for genre in data['genres']}
        else:
            print(f"DEBUG: TMDb genres API response missing 'genres' key or is empty. Response: {data}")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to fetch genres from TMDb. Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"ERROR: TMDb genres API response status: {e.response.status_code}, content: {e.response.text}")
    except ValueError as e: # Handles JSON decoding errors
        print(f"ERROR: Failed to decode JSON from TMDb genres API. Error: {e}")

def get_movie_trailer(movie_id):
    videos_url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={TMDB_API_KEY}&language=en-US"
    try:
        response = requests.get(videos_url)
        response.raise_for_status()
        data = response.json()
        if data and 'results' in data:
            for video in data['results']:
                if video['site'] == 'YouTube' and video['type'] == 'Trailer':
                    return TMDB_YOUTUBE_BASE_URL + video['key']
            print(f"DEBUG: No trailer found for movie {movie_id} in TMDb response.")
        else:
            print(f"DEBUG: TMDb videos API response for movie {movie_id} missing 'results' key or is empty. Response: {data}")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to fetch trailer for movie {movie_id}. Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"ERROR: TMDb videos API response status: {e.response.status_code}, content: {e.response.text}")
    except ValueError as e:
        print(f"ERROR: Failed to decode JSON from TMDb videos API for movie {movie_id}. Error: {e}")
    return None

def get_movie_cast(movie_id):
    credits_url = f"https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={TMDB_API_KEY}&language=en-US"
    try:
        response = requests.get(credits_url)
        response.raise_for_status()
        data = response.json()
        cast = []
        if data and 'cast' in data:
            for member in data['cast'][:5]: # Get top 5 cast members
                cast.append(member['name'])
        else:
            print(f"DEBUG: TMDb credits API response for movie {movie_id} missing 'cast' key or is empty. Response: {data}")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to fetch cast for movie {movie_id}. Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"ERROR: TMDb credits API response status: {e.response.status_code}, content: {e.response.text}")
    except ValueError as e:
        print(f"ERROR: Failed to decode JSON from TMDb credits API for movie {movie_id}. Error: {e}")
    return ", ".join(cast)

def fetch_top_rated_movies(start_page=1, end_page=1):
    new_movies_count = 0
    for page in range(start_page, end_page + 1):
        url = f"https://api.themoviedb.org/3/movie/top_rated?api_key={TMDB_API_KEY}&language=en-US&page={page}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            if data and 'results' in data:
                for movie_data in data['results']:
                    if movie_data.get('vote_average') and movie_data.get('vote_count', 0) > 50:
                        # Check if movie already exists in DB
                        existing_movie = Movie.query.filter_by(tmdb_id=movie_data['id']).first()
                        if not existing_movie:
                            trailer_url = get_movie_trailer(movie_data['id'])
                            cast = get_movie_cast(movie_data['id'])
                            genres_map = app.config.get('GENRES_MAP', {})
                            genres_names = [genres_map.get(gid) for gid in movie_data.get('genre_ids', []) if gid in genres_map]
                            
                            new_movie = Movie(
                                tmdb_id=movie_data['id'],
                                title=movie_data['title'],
                                score=movie_data['vote_average'],
                                poster_url=TMDB_IMAGE_BASE_URL + movie_data['poster_path'] if movie_data.get('poster_path') else None,
                                trailer_url=trailer_url,
                                overview=movie_data.get('overview', 'No overview available.'),
                                release_date=movie_data.get('release_date', 'N/A'),
                                genres=", ".join(genres_names),
                                genre_ids=", ".join(map(str, movie_data.get('genre_ids', []))),
                                cast=cast
                            )
                            db.session.add(new_movie)
                            new_movies_count += 1
                db.session.commit()
            else:
                print(f"DEBUG: TMDb top rated movies API response for page {page} missing 'results' key or is empty. Response: {data}")
        except requests.exceptions.RequestException as e:
            print(f"ERROR: Failed to fetch top rated movies from TMDb (page {page}). Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"ERROR: TMDb top rated movies API response status: {e.response.status_code}, content: {e.response.text}")
        except ValueError as e:
            print(f"ERROR: Failed to decode JSON from TMDb top rated movies API (page {page}). Error: {e}")
    print(f"DEBUG: Fetched and added {new_movies_count} new movies to the database.")
    return new_movies_count

with app.app_context():
    db.create_all()
    fetch_genres()

if __name__ == '__main__':
    app.run(debug=True, port=5001)

@app.route('/api/movies')
def api_movies():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    offset = (page - 1) * per_page

    movies_query = Movie.query.offset(offset).limit(per_page)
    movies_from_db = movies_query.all()

    if not movies_from_db:
        # If no movies in DB for this page, try to fetch from TMDb
        # We'll fetch one page at a time from TMDb, corresponding to the requested page number
        # This assumes TMDb pages align roughly with our internal pagination
        print(f"DEBUG: No movies found in DB for page {page}. Attempting to fetch from TMDb (page {page}).")
        fetch_top_rated_movies(start_page=page, end_page=page)
        movies_from_db = movies_query.all() # Try fetching again after potential new data

    movies_data = []
    for movie in movies_from_db:
        movies_data.append({
            "id": movie.tmdb_id,
            "title": movie.title,
            "score": movie.score,
            "poster_url": movie.poster_url,
            "trailer_url": movie.trailer_url,
            "overview": movie.overview,
            "release_date": movie.release_date,
            "genres": movie.genres,
            "genre_ids": [int(gid) for gid in movie.genre_ids.split(',')] if movie.genre_ids else [],
            "cast": movie.cast
        })
    return jsonify(movies_data)

@app.route('/api/fetch_new_movies', methods=['POST'])
def api_fetch_new_movies():
    num_pages = int(request.json.get('num_pages', 1))
    start_page = int(request.json.get('start_page', 1))
    
    # Fetch movies from TMDb and save to DB
    new_movies_count = fetch_top_rated_movies(start_page=start_page, end_page=start_page + num_pages - 1)
    
    return jsonify({"message": f"Fetched and added {new_movies_count} new movies to the database.", "new_movies_count": new_movies_count})

@app.route('/')
def index():
    # Pass flash messages to the template
    flashed_messages = get_flashed_messages(with_categories=True)
    
    # Get genres from app.config
    genres_map = app.config.get('GENRES_MAP', {})
    
    # Convert genres_map to a list of dictionaries for easier iteration in Jinja2
    genres = [{'id': gid, 'name': gname} for gid, gname in genres_map.items()]

    return render_template('index.html', 
                           flashed_messages=flashed_messages, 
                           genres=genres)

with app.app_context():
    db.create_all()
    fetch_genres()

if __name__ == '__main__':
    app.run(debug=True, port=5001)

@app.route('/random-movie')
def random_movie():
    selected_genres_str = request.args.get('genres')
    selected_genre_ids = []
    if selected_genres_str:
        selected_genre_ids = [int(x) for x in selected_genres_str.split(',')]

    selected_movies = []
    movie_db = app.config.get('MOVIE_DB', [])

    if current_user.is_authenticated:
        liked_preferences = UserMoviePreference.query.filter_by(user_id=current_user.id, preference=True).all()
        if liked_preferences:
            liked_genres_names = set()
            for pref in liked_preferences:
                if pref.genres:
                    liked_genres_names.update(pref.genres.split(', '))
            
            if liked_genres_names:
                # Prioritize movies with liked genres
                for movie in movie_db:
                    movie_genres_names = set(movie['genres'].split(', '))
                    if any(g in liked_genres_names for g in movie_genres_names):
                        # Apply additional genre filter if selected
                        if not selected_genre_ids or any(gid in selected_genre_ids for gid in movie.get('genre_ids', [])):
                            selected_movies.append(movie)
    
    if not selected_movies:
        # Fallback to all movies if no liked genres or no matches, applying selected genre filter
        if selected_genre_ids:
            for movie in movie_db:
                if any(gid in selected_genre_ids for gid in movie.get('genre_ids', [])):
                    selected_movies.append(movie)
        else:
            selected_movies = movie_db

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
    if data and 'results' in data:
        for movie in data['results']:
            genres_map = app.config.get('GENRES_MAP', {})
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

@app.route('/friends')
@login_required
def friends():
    all_users = User.query.filter(User.id != current_user.id).all()
    friends = current_user.get_friends()
    non_friends = [user for user in all_users if user not in friends]
    return render_template('friends.html', friends=friends, non_friends=non_friends)

@app.route('/add_friend', methods=['POST'])
@login_required
def add_friend():
    friend_id = request.form.get('friend_id')
    friend = User.query.get(friend_id)

    if not friend:
        flash('User not found.', 'danger')
        return redirect(url_for('friends'))

    if friend.id == current_user.id:
        flash('You cannot add yourself as a friend.', 'danger')
        return redirect(url_for('friends'))

    # Check if friendship already exists (either way)
    existing_friendship = Friendship.query.filter(
        ((Friendship.user_id == current_user.id) & (Friendship.friend_id == friend.id)) |
        ((Friendship.user_id == friend.id) & (Friendship.friend_id == current_user.id))
    ).first()

    if existing_friendship:
        flash('You are already friends with this user.', 'warning')
        return redirect(url_for('friends'))

    new_friendship = Friendship(user_id=current_user.id, friend_id=friend.id)
    db.session.add(new_friendship)
    db.session.commit()
    flash(f'You are now friends with {friend.username}!', 'success')
    return redirect(url_for('friends'))

@app.route('/remove_friend', methods=['POST'])
@login_required
def remove_friend():
    friend_id = request.form.get('friend_id')
    friend = User.query.get(friend_id)

    if not friend:
        flash('User not found.', 'danger')
        return redirect(url_for('friends'))

    friendship = Friendship.query.filter(
        ((Friendship.user_id == current_user.id) & (Friendship.friend_id == friend.id)) |
        ((Friendship.user_id == friend.id) & (Friendship.friend_id == current_user.id))
    ).first()

    if friendship:
        db.session.delete(friendship)
        db.session.commit()
        flash(f'You are no longer friends with {friend.username}.', 'info')
    else:
        flash('You are not friends with this user.', 'warning')
    
    return redirect(url_for('friends'))

@app.route('/friends/shared_movies/<int:friend_id>')
@login_required
def shared_movies(friend_id):
    friend = User.query.get_or_404(friend_id)

    if not friend:
        flash('Friend not found.', 'danger')
        return redirect(url_for('friends'))

    # Check if they are actually friends
    is_friend = Friendship.query.filter(
        ((Friendship.user_id == current_user.id) & (Friendship.friend_id == friend.id)) |
        ((Friendship.user_id == friend.id) & (Friendship.friend_id == current_user.id))
    ).first()

    if not is_friend:
        flash('You are not friends with this user.', 'danger')
        return redirect(url_for('friends'))

    current_user_liked_movies = {p.movie_title for p in current_user.preferences if p.preference == True}
    friend_liked_movies = {p.movie_title for p in friend.preferences if p.preference == True}

    shared_liked_movie_titles = list(current_user_liked_movies.intersection(friend_liked_movies))

    # Optionally, fetch more details for these movies from TMDb if needed
    # For now, just returning titles
    return render_template('shared_movies.html', friend=friend, shared_liked_movie_titles=shared_liked_movie_titles)

@app.route('/load_movies', methods=['GET', 'POST'])
@login_required
@admin_required
def load_movies():
    total_movies = Movie.query.count()
    if request.method == 'POST':
        num_pages = request.form.get('num_pages', type=int)
        if num_pages and num_pages > 0:
            new_movies_count = fetch_top_rated_movies(start_page=1, end_page=num_pages) # Start from page 1 for simplicity
            flash(f'Successfully fetched and added {new_movies_count} new movies.', 'success')
        else:
            flash('Please enter a valid number of pages.', 'danger')
        return redirect(url_for('load_movies'))
    return render_template('load_movies.html', total_movies=total_movies)
