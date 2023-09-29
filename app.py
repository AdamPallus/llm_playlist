import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session

# Load environment variables
load_dotenv()

# Set up the Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)
sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="playlist-modify-public"
)

@app.route('/', methods=['GET', 'POST'])
def index():
    # If token info isn't in the session, redirect to Spotify authentication
    if not session.get('token_info'):
        # Store the form data in the session before redirecting
        if request.method == 'POST':
            session['form_data'] = request.form
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    
    # If this is a POST request or form data is stored in the session
    if request.method == 'POST' or 'form_data' in session:
        if 'form_data' in session:
            form_data = session.pop('form_data')
        else:
            form_data = request.form

        token_info = session.get('token_info', {})
        sp = spotipy.Spotify(auth=token_info['access_token'])  # Use the token to authenticate
        user_info = sp.current_user()
        print("Token Info:", token_info)
        print("User Info:", user_info)
        spotify_username = user_info['id']
        playlist_name = form_data['playlist_name']
        tracks_artists_str = form_data['tracks_artists']
        tracks_artists = eval(tracks_artists_str)
        
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

@app.route('/callback')
def callback():
    token_info = sp_oauth.get_access_token(request.args['code'])
    session['token_info'] = token_info
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=False)
