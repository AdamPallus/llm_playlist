import os
import ast
import spotipy
import redis
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_session import Session
# Load environment variables
load_dotenv()

# Set up the Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)
# Configure Flask-Session
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_REDIS'] = redis.StrictRedis.from_url(os.environ['REDIS_URL'])
app.config['SESSION_KEY_PREFIX'] = 'spotify_playlist:'

# Initialize Flask-Session
Session(app)
print("[STATUS] Getting spotify OAuth")
sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="playlist-modify-public"
)

def parse_tracks_artists(input_str):
    try:
        parsed_data = ast.literal_eval(input_str)
        if isinstance(parsed_data, list) and all(isinstance(item, tuple) and len(item) == 2 for item in parsed_data):
            return parsed_data
    except (SyntaxError, ValueError):
        pass
    flash("Invalid input format. Please provide a list of tuples for tracks and artists.")
    return None

@app.route('/', methods=['GET', 'POST'])
def index():
    # If token info isn't in the session, redirect to Spotify authentication
    if not session.get('token_info'):
        print("[STATUS] no token, getting new token")
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

        print("[STATUS] Setting up spotify session")
        token_info = session.get('token_info', {})
        sp = spotipy.Spotify(auth=token_info['access_token'])  # Use the token to authenticate
        user_info = sp.current_user()
        print("Token Info:", token_info)
        print("User Info:", user_info)
        spotify_username = user_info['id']
        playlist_name = form_data['playlist_name']
        
        print("[STATUS] parsing tracks")

        tracks_artists_str = request.form['tracks_artists']
        tracks_artists = parse_tracks_artists(tracks_artists_str)
        if tracks_artists is None:
            print('[STATUS] No artists parsed!')
            if track_artists_str: print(track_artists_str)
            return render_template('index.html')
        
        # Create a new playlist
        print("[STATUS] Creating Playlist")
        playlist = sp.user_playlist_create(user=spotify_username, name=playlist_name)
        playlist_id = playlist['id']

        # Search for tracks and get their URIs
        print("[STATUS] searching for songs!")
        track_uris = []
        for track, artist in tracks_artists:
            results = sp.search(q=f'track:{track} artist:{artist}', type='track', limit=1)
            items = results['tracks']['items']
            if items:
                track_uris.append(items[0]['uri'])

        # Add tracks to the playlist
        print(f"[STATUS] adding {len(track_uris)} songs to playlist!")
        sp.playlist_add_items(playlist_id=playlist_id, items=track_uris)
        
        flash("{playlist_name} Playlist created successfully!")
        return redirect(url_for('index'))

    return render_template('index.html')

@app.route('/callback')
def callback():
    token_info = sp_oauth.get_access_token(request.args['code'])
    session['token_info'] = token_info
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=False)
