const { createApp } = Vue

createApp({
  data() {
    return {
      movie: null,
      error: null,
      searchQuery: '',
      searchResults: null,
      lastSearchQuery: '',
      isLoggedIn: false,
      username: '',
      flashMessages: [],
      likedMoviesList: null,
      toast: {
        show: false,
        message: '',
        type: 'info' // 'info', 'success', 'error'
      },
      allGenres: [], // New: Store all genres from TMDb
      selectedGenres: [] // New: Store selected genre IDs
    }
  },
  mounted() {
    this.checkLoginStatus();
    this.fetchAllGenres(); // New: Fetch all genres on mount
  },
  methods: {
    showToast(message, type = 'info') {
      this.toast.show = true;
      this.toast.message = message;
      this.toast.type = type;
      setTimeout(() => {
        this.toast.show = false;
        this.toast.message = '';
      }, 3000); // Hide after 3 seconds
    },
    async checkLoginStatus() {
      try {
        const response = await fetch('/status');
        if (response.ok) {
          const data = await response.json();
          this.isLoggedIn = data.isLoggedIn;
          this.username = data.username;
        } else {
          this.isLoggedIn = false;
          this.username = '';
        }
      } catch (error) {
        console.error('Error checking login status:', error);
        this.isLoggedIn = false;
        this.username = '';
      }
    },
    async fetchAllGenres() {
      try {
        const response = await fetch('/genres');
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        const data = await response.json();
        this.allGenres = data;
      } catch (error) {
        console.error('Error fetching genres:', error);
        this.showToast('Could not load genres.', 'error');
      }
    },
    applyGenreFilter() {
      // When filter is applied, re-fetch random movie or re-run search
      if (this.searchResults) {
        this.searchMovies(); // Re-run search with new filter
      } else {
        this.getRandomMovie(); // Get new random movie with filter
      }
    },
    async getRandomMovie() {
      this.error = null;
      this.searchResults = null; // Clear search results when getting a random movie
      this.likedMoviesList = null; // Clear liked movies list

      let url = '/random-movie';
      if (this.selectedGenres.length > 0) {
        url += `?genres=${this.selectedGenres.join(',')}`;
      }

      try {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        const data = await response.json();
        this.movie = data;
      } catch (error) {
        console.error('Error fetching random movie:', error);
        this.error = 'Could not fetch a random movie. Please try again!';
      }
    },
    async searchMovies() {
      if (!this.searchQuery.trim()) {
        this.searchResults = [];
        this.lastSearchQuery = this.searchQuery;
        this.movie = null; // Clear random movie when searching
        this.likedMoviesList = null; // Clear liked movies list
        return;
      }

      this.error = null;
      this.movie = null; // Clear random movie when searching
      this.likedMoviesList = null; // Clear liked movies list
      this.lastSearchQuery = this.searchQuery;

      let url = `/search-movie?query=${encodeURIComponent(this.searchQuery)}`;
      if (this.selectedGenres.length > 0) {
        url += `&genres=${this.selectedGenres.join(',')}`;
      }

      try {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        const data = await response.json();
        this.searchResults = data;
      } catch (error) {
        console.error('Error searching movies:', error);
        this.error = 'Could not perform search. Please try again!';
      }
    },
    async setPreference(movieTitle, tmdbId, genres, preference) {
        if (!this.isLoggedIn) {
            this.showToast('Please log in to set movie preferences.', 'error');
            return;
        }
        console.log('Sending preference:', { title: movieTitle, id: tmdbId, genres: genres, preference: preference });
        try {
            const response = await fetch('/movie-preference', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ title: movieTitle, id: tmdbId, genres: genres, preference: preference }),
            });
            const data = await response.json();
            if (response.ok) {
                this.showToast(data.message, 'success');
                this.getRandomMovie(); // Request a new random movie
            } else {
                this.showToast('Error: ' + data.error, 'error');
            }
        } catch (error) {
            console.error('Error setting preference:', error);
            this.showToast('Could not set preference. Please try again.', 'error');
        }
    },
    async getLikedMovies() {
        if (!this.isLoggedIn) {
            this.showToast('Please log in to view your liked movies.', 'error');
            return;
        }
        this.error = null;
        this.movie = null; // Clear random movie
        this.searchResults = null; // Clear search results
        try {
            const response = await fetch('/liked-movies');
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            const data = await response.json();
            this.likedMoviesList = data;
        } catch (error) {
            console.error('Error fetching liked movies:', error);
            this.error = 'Could not fetch liked movies. Please try again!';
        }
    }
  }
}).mount('#app') {# Mount to body #}