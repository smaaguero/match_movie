# Movie Recommender

This is a Flask-based movie recommendation web application that integrates with The Movie Database (TMDb) API. Users can register, log in, get random movie recommendations, search for movies, and mark movies as liked or disliked.

## Features

*   User authentication (registration, login, logout)
*   Random movie recommendations based on user preferences
*   Movie search functionality
*   Like/dislike movie preferences
*   Asynchronous TMDb API calls for improved performance
*   Movie data persistence using SQLite database

## Setup

### Prerequisites

*   Python 3.10+
*   Poetry (for dependency management)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/movie_recommender.git
    cd movie_recommender
    ```

2.  **Install dependencies using Poetry:**
    ```bash
    poetry install
    ```

3.  **Set up environment variables:**
    Create a `.env` file in the root directory of the project with the following variables:
    ```
    FLASK_SECRET_KEY=your_flask_secret_key
    TMDB_API_KEY=your_tmdb_api_key
    ```
    *   `FLASK_SECRET_KEY`: A strong, random string for Flask session management.
    *   `TMDB_API_KEY`: Your API key from [The Movie Database (TMDb)](https://www.themoviedb.org/documentation/api).

4.  **Run the application:**
    ```bash
    poetry run python app.py
    ```

The application will be accessible at `http://127.0.0.1:5001/`.

## Project Structure

```
movie_recommender/
├── app.py                  # Main Flask application
├── ml-100k.zip             # (Optional) MovieLens 100k dataset - not currently used
├── poetry.lock             # Poetry lock file
├── pyproject.toml          # Poetry project configuration
├── __pycache__/            # Python cache files
├── .venv/                  # Python virtual environment
├── instance/               # SQLite database file (site.db)
├── ml-100k/                # Extracted MovieLens 100k dataset - not currently used
├── static/                 # Static files (CSS, JS)
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── script.js
└── templates/              # HTML templates
    ├── index.html
    ├── login.html
    └── register.html
```

## Future Improvements

*   **Pagination:** Implement proper pagination for movie listings.
*   **Recommendation Engine:** Develop a more sophisticated recommendation engine using the MovieLens dataset or user preferences.
*   **User Interface:** Enhance the UI/UX for a more engaging experience.
*   **Error Handling:** More robust error handling and user feedback.
*   **Testing:** Add comprehensive unit and integration tests.
*   **Deployment:** Containerize the application for easier deployment.
