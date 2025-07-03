import pytest
import json
from app import User, UserMoviePreference

def test_index_route(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b"Movie Recommender" in response.data

def test_register_user(client, db_session):
    response = client.post('/register', data={'username': 'testuser', 'password': 'testpassword'})
    with client.session_transaction() as sess:
        flashed_messages = sess['_flashes']
    assert ('success', 'Your account has been created! You are now able to log in') in flashed_messages
    assert User.query.filter_by(username='testuser').first() is not None

def test_register_existing_user(client, db_session):
    client.post('/register', data={'username': 'existinguser', 'password': 'password'})
    response = client.post('/register', data={'username': 'existinguser', 'password': 'anotherpassword'})
    with client.session_transaction() as sess:
        flashed_messages = sess['_flashes']
    assert ('danger', 'That username is already taken. Please choose a different one.') in flashed_messages

def test_login_user(client, db_session):
    client.post('/register', data={'username': 'loginuser', 'password': 'loginpassword'})
    response = client.post('/login', data={'username': 'loginuser', 'password': 'loginpassword'})
    with client.session_transaction() as sess:
        flashed_messages = sess['_flashes']
    assert ('success', 'You have been logged in!') in flashed_messages

def test_login_invalid_credentials(client, db_session):
    response = client.post('/login', data={'username': 'nonexistent', 'password': 'wrongpassword'})
    with client.session_transaction() as sess:
        flashed_messages = sess['_flashes']
    assert ('danger', 'Login Unsuccessful. Please check username and password') in flashed_messages

def test_logout_user(auth_client):
    response = auth_client.get('/logout')
    with auth_client.session_transaction() as sess:
        flashed_messages = sess['_flashes']
    assert ('info', 'You have been logged out.') in flashed_messages

def test_status_logged_in(auth_client):
    response = auth_client.get('/status')
    data = json.loads(response.data)
    assert data['isLoggedIn'] == True
    assert data['username'] == 'testuser'

def test_status_logged_out(client):
    response = client.get('/status')
    data = json.loads(response.data)
    assert data['isLoggedIn'] == False
    assert data['username'] == None

def test_random_movie_no_auth(client, mock_tmdb):
    response = client.get('/random-movie')
    data = json.loads(response.data)
    assert response.status_code == 200
    assert "title" in data
    assert data['title'] in ["Movie A", "Movie B"]

def test_random_movie_with_liked_genres(auth_client, mock_tmdb):
    # Add a liked preference for 'Action' genre
    auth_client.post('/movie-preference', json={'title': 'Movie A', 'id': 1, 'genres': 'Action', 'preference': True})
    response = auth_client.get('/random-movie')
    data = json.loads(response.data)
    assert response.status_code == 200
    assert data['title'] == "Movie A" # Should prioritize Action movie

def test_random_movie_with_genre_filter(client, mock_tmdb):
    response = client.get('/random-movie?genres=28') # Filter by Action genre
    data = json.loads(response.data)
    assert response.status_code == 200
    assert data['title'] == "Movie A"

def test_search_movie(client, mock_tmdb):
    response = client.get('/search-movie?query=Search')
    data = json.loads(response.data)
    assert response.status_code == 200
    assert len(data) == 1
    assert data[0]['title'] == "Search Movie C"

def test_search_movie_with_genre_filter(client, mock_tmdb):
    response = client.get('/search-movie?query=Search&genres=28') # Filter by Action genre
    data = json.loads(response.data)
    assert response.status_code == 200
    assert len(data) == 1
    assert data[0]['title'] == "Search Movie C"

def test_movie_preference(auth_client, db_session):
    response = auth_client.post('/movie-preference', json={'title': 'Test Movie', 'id': 123, 'genres': 'Action, Comedy', 'preference': True})
    assert response.status_code == 200
    assert b"Preference saved successfully" in response.data
    pref = UserMoviePreference.query.filter_by(movie_title='Test Movie').first()
    assert pref is not None
    assert pref.preference == True
    assert pref.tmdb_id == 123
    assert pref.genres == 'Action, Comedy'

def test_update_movie_preference(auth_client, db_session):
    # Create initial preference
    auth_client.post('/movie-preference', json={'title': 'Update Movie', 'id': 456, 'genres': 'Drama', 'preference': True})
    # Update preference
    response = auth_client.post('/movie-preference', json={'title': 'Update Movie', 'id': 456, 'genres': 'Drama', 'preference': False})
    assert response.status_code == 200
    pref = UserMoviePreference.query.filter_by(movie_title='Update Movie').first()
    assert pref.preference == False

def test_liked_movies(auth_client, db_session):
    auth_client.post('/movie-preference', json={'title': 'Liked Movie 1', 'id': 1, 'genres': 'Action', 'preference': True})
    auth_client.post('/movie-preference', json={'title': 'Disliked Movie 2', 'id': 2, 'genres': 'Comedy', 'preference': False})
    auth_client.post('/movie-preference', json={'title': 'Liked Movie 3', 'id': 3, 'genres': 'Drama', 'preference': True})

    response = auth_client.get('/liked-movies')
    data = json.loads(response.data)
    assert response.status_code == 200
    assert "Liked Movie 1" in data
    assert "Liked Movie 3" in data
    assert "Disliked Movie 2" not in data

def test_get_genres(client, mock_tmdb):
    response = client.get('/genres')
    data = json.loads(response.data)
    assert response.status_code == 200
    assert len(data) == 2
    assert {'id': 28, 'name': 'Action'} in data
    assert {'id': 35, 'name': 'Comedy'} in data
