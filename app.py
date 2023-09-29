import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash

# Load environment variables
load_dotenv()

# Set up the Flask app
app = Flask(__name__)
app.secret_key = 'some_secret_key'  # for flash messages

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        spotify_username = request.form['spotify_username']
        playlist_name = request.form['playlist_name']
        tracks_artists_str = request.form['tracks_artists']
        tracks_artists = eval(tracks_artists_str)
        
        # Set up authentication
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=os.getenv("SPOTIPY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
            scope="playlist-modify-public"
        ))

        # Create a new playlist
        playlist = sp.user_playlist_create(user=spotify_username, name=playlist_name)
        playlist_id = playlist['id']

        # Search for tracks and get their URIs
        track_uris = []
        for track, artist in tracks_artists:
            results = sp.search(q=f'track:{track} artist:{artist}', type='track', limit=1)
            items = results['tracks']['items']
            if items:
                track_uris.append(items[0]['uri'])

        # Add tracks to the playlist
        sp.playlist_add_items(playlist_id=playlist_id, items=track_uris)
        
        flash("Playlist created successfully!")
        return redirect(url_for('index'))

    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
