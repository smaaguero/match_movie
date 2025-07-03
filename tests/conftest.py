import pytest
import os
import requests_mock

# Set environment variables before importing app
os.environ['FLASK_SECRET_KEY'] = 'test_secret_key'
os.environ['TMDB_API_KEY'] = 'test_tmdb_api_key'

from app import app, db, User, UserMoviePreference

@pytest.fixture(scope='module')
def client(mock_tmdb):
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SECRET_KEY'] = 'test_secret_key'
    app.template_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..' , 'templates') # Set template folder for tests
    os.environ['TMDB_API_KEY'] = 'test_tmdb_api_key'

    with app.test_client() as client:
        with app.app_context():
            app.config['GENRES_MAP'] = {28: 'Action', 35: 'Comedy'}
            app.config['MOVIE_DB'] = [
                {'id': 1, 'title': 'Movie A', 'score': 8.0, 'poster_url': '/pathA.jpg', 'overview': 'Overview A', 'release_date': '2023-01-01', 'genres': 'Action', 'genre_ids': [28], 'trailer_url': 'trailerA', 'cast': 'Actor A, Actor B'},
                {'id': 2, 'title': 'Movie B', 'score': 7.5, 'poster_url': '/pathB.jpg', 'overview': 'Overview B', 'release_date': '2023-02-01', 'genres': 'Comedy', 'genre_ids': [35], 'trailer_url': 'trailerB', 'cast': 'Actor C, Actor D'},
            ]
            yield client

@pytest.fixture(scope='function')
def auth_client(client, db_session):
    # Register a test user
    client.post('/register', data={'username': 'testuser', 'password': 'testpassword'}, follow_redirects=True)
    # Log in the test user
    client.post('/login', data={'username': 'testuser', 'password': 'testpassword'}, follow_redirects=True)
    yield client
    # Log out the test user
    client.get('/logout', follow_redirects=True)

@pytest.fixture(scope='function')
def db_session():
    db.create_all()
    yield
    db.session.remove()
    db.drop_all()

@pytest.fixture(scope='module')
def mock_tmdb():
    with requests_mock.Mocker() as m:
        # Mock genre list
        m.get('https://api.themoviedb.org/3/genre/movie/list', json={'genres': [{'id': 28, 'name': 'Action'}, {'id': 35, 'name': 'Comedy'}]})
        
        # Mock top rated movies
        m.get('https://api.themoviedb.org/3/movie/top_rated', json={
            'results': [
                {'id': 1, 'title': 'Movie A', 'vote_average': 8.0, 'vote_count': 100, 'poster_path': '/pathA.jpg', 'overview': 'Overview A', 'release_date': '2023-01-01', 'genre_ids': [28]},
                {'id': 2, 'title': 'Movie B', 'vote_average': 7.5, 'vote_count': 60, 'poster_path': '/pathB.jpg', 'overview': 'Overview B', 'release_date': '2023-02-01', 'genre_ids': [35]},
            ]
        })

        # Mock movie videos (trailer)
        m.get('https://api.themoviedb.org/3/movie/1/videos', json={'results': [{'site': 'YouTube', 'type': 'Trailer', 'key': 'trailerA'}]})
        m.get('https://api.themoviedb.org/3/movie/2/videos', json={'results': [{'site': 'YouTube', 'type': 'Trailer', 'key': 'trailerB'}]})

        # Mock movie credits (cast)
        m.get('https://api.themoviedb.org/3/movie/1/credits', json={'cast': [{'name': 'Actor A'}, {'name': 'Actor B'}]})
        m.get('https://api.themoviedb.org/3/movie/2/credits', json={'cast': [{'name': 'Actor C'}, {'name': 'Actor D'}]})

        # Mock search movie
        m.get('https://api.themoviedb.org/3/search/movie', json={
            'results': [
                {'id': 3, 'title': 'Search Movie C', 'vote_average': 7.0, 'poster_path': '/pathC.jpg', 'overview': 'Overview C', 'release_date': '2023-03-01', 'genre_ids': [28, 35]},
            ]
        })
        m.get('https://api.themoviedb.org/3/movie/3/videos', json={'results': [{'site': 'YouTube', 'type': 'Trailer', 'key': 'trailerC'}]})
        m.get('https://api.themoviedb.org/3/movie/3/credits', json={'cast': [{'name': 'Actor E'}]})

        yield m
        with app.app_context():
            from app import fetch_genres, fetch_top_rated_movies
            fetch_genres()
            fetch_top_rated_movies()
