import pytest
import json
from app import User, UserMoviePreference, Friendship

def test_index_route(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b"Match Movie" in response.data

def test_register_user(client, db_session):
    response = client.post('/register', data={'username': 'testuser', 'password': 'testpassword'})
    with client.session_transaction() as sess:
        flashed_messages = sess.get('_flashes', [])
    assert ('success', 'Your account has been created! You are now able to log in') in flashed_messages
    assert User.query.filter_by(username='testuser').first() is not None

def test_register_existing_user(client, db_session):
    client.post('/register', data={'username': 'existinguser', 'password': 'password'})
    response = client.post('/register', data={'username': 'existinguser', 'password': 'anotherpassword'})
    with client.session_transaction() as sess:
        flashed_messages = sess.get('_flashes', [])
    assert ('danger', 'That username is already taken. Please choose a different one.') in flashed_messages

def test_login_user(client, db_session):
    client.post('/register', data={'username': 'loginuser', 'password': 'loginpassword'})
    response = client.post('/login', data={'username': 'loginuser', 'password': 'loginpassword'})
    with client.session_transaction() as sess:
        flashed_messages = sess.get('_flashes', [])
    assert ('success', 'You have been logged in!') in flashed_messages

def test_login_invalid_credentials(client, db_session):
    response = client.post('/login', data={'username': 'nonexistent', 'password': 'wrongpassword'})
    assert b'Login Unsuccessful. Please check username and password' in response.data

def test_logout_user(auth_client):
    response = auth_client.get('/logout')
    with auth_client.session_transaction() as sess:
        flashed_messages = sess.get('_flashes', [])
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

# New tests for friends functionality
def test_friends_page_access(auth_client):
    response = auth_client.get('/friends')
    assert response.status_code == 200
    assert b"Your Friends" in response.data

def test_add_friend(client, db_session):
    # Register two users
    client.post('/register', data={'username': 'user1', 'password': 'pass1'})
    client.post('/register', data={'username': 'user2', 'password': 'pass2'})

    # Log in user1
    client.post('/login', data={'username': 'user1', 'password': 'pass1'})

    user2 = User.query.filter_by(username='user2').first()
    assert user2 is not None

    response = client.post('/add_friend', data={'friend_id': user2.id}, follow_redirects=True)
    assert f'You are now friends with {user2.username}!'.encode() in response.data
    
    # Verify friendship in DB
    user1 = User.query.filter_by(username='user1').first()
    assert user1 is not None
    friends_of_user1 = user1.get_friends()
    assert user2 in friends_of_user1

def test_add_existing_friend(client, db_session):
    # Register two users
    client.post('/register', data={'username': 'userA', 'password': 'passA'})
    client.post('/register', data={'username': 'userB', 'password': 'passB'})

    # Log in userA
    client.post('/login', data={'username': 'userA', 'password': 'passA'})

    userB = User.query.filter_by(username='userB').first()
    assert userB is not None

    # Add friend first time
    client.post('/add_friend', data={'friend_id': userB.id}, follow_redirects=True)

    # Try adding again
    response = client.post('/add_friend', data={'friend_id': userB.id}, follow_redirects=True)
    assert b'You are already friends with this user.' in response.data

def test_add_self_as_friend(client, db_session):
    client.post('/register', data={'username': 'selfuser', 'password': 'selfpass'})
    client.post('/login', data={'username': 'selfuser', 'password': 'selfpass'})

    self_user = User.query.filter_by(username='selfuser').first()
    assert self_user is not None

    response = client.post('/add_friend', data={'friend_id': self_user.id}, follow_redirects=True)
    assert b'You cannot add yourself as a friend.' in response.data

def test_remove_friend(client, db_session):
    # Register two users
    client.post('/register', data={'username': 'userX', 'password': 'passX'})
    client.post('/register', data={'username': 'userY', 'password': 'passY'})

    # Log in userX
    client.post('/login', data={'username': 'userX', 'password': 'passX'})

    userY = User.query.filter_by(username='userY').first()
    assert userY is not None

    # Add friend
    client.post('/add_friend', data={'friend_id': userY.id}, follow_redirects=True)

    # Remove friend
    response = client.post('/remove_friend', data={'friend_id': userY.id}, follow_redirects=True)
    assert f'You are no longer friends with {userY.username}.'.encode() in response.data

    # Verify friendship removed from DB
    userX = User.query.filter_by(username='userX').first()
    assert userX is not None
    friends_of_userX = userX.get_friends()
    assert userY not in friends_of_userX

def test_remove_non_existent_friend(client, db_session):
    client.post('/register', data={'username': 'userZ', 'password': 'passZ'})
    client.post('/login', data={'username': 'userZ', 'password': 'passZ'})

    response = client.post('/remove_friend', data={'friend_id': 999}, follow_redirects=True) # Non-existent ID
    assert b'User not found.' in response.data

def test_shared_movies_access(auth_client, db_session):
    # Register another user
    auth_client.post('/register', data={'username': 'frienduser', 'password': 'friendpass'})
    friend_user = User.query.filter_by(username='frienduser').first()
    assert friend_user is not None

    # Add friend
    auth_client.post('/add_friend', data={'friend_id': friend_user.id}, follow_redirects=True)

    # Current user likes a movie
    auth_client.post('/movie-preference', json={'title': 'Shared Movie', 'id': 10, 'genres': 'Action', 'preference': True})

    # Friend likes the same movie (log in as friend, set preference, then log back in as current_user)
    auth_client.get('/logout', follow_redirects=True)
    auth_client.post('/login', data={'username': 'frienduser', 'password': 'friendpass'}, follow_redirects=True)
    auth_client.post('/movie-preference', json={'title': 'Shared Movie', 'id': 10, 'genres': 'Action', 'preference': True})
    auth_client.get('/logout', follow_redirects=True)
    auth_client.post('/login', data={'username': 'testuser', 'password': 'testpassword'}, follow_redirects=True)

    response = auth_client.get(f'/friends/shared_movies/{friend_user.id}')
    assert response.status_code == 200
    assert b"Shared Movies with frienduser" in response.data
    assert b"Shared Movie" in response.data

def test_shared_movies_non_friend(client, db_session):
    # Register two users
    client.post('/register', data={'username': 'user_a', 'password': 'pass_a'})
    client.post('/register', data={'username': 'user_b', 'password': 'pass_b'})

    # Log in user_a
    client.post('/login', data={'username': 'user_a', 'password': 'pass_a'})

    user_b = User.query.filter_by(username='user_b').first()
    assert user_b is not None

    response = client.get(f'/friends/shared_movies/{user_b.id}', follow_redirects=True)
    assert b'You are not friends with this user.' in response.data
    assert b"Your Friends" in response.data # Redirects to friends page