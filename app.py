import os
import ast
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify 
from flask import Response, stream_with_context
from flask_session import Session

from openai import OpenAI
# Load environment variables
load_dotenv()

# Set up the Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.environ['FLASK_SECRET_KEY']
#app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')


# Configure Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True

# Initialize Flask-Session
Session(app)

sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="playlist-modify-public"
)

client = OpenAI()
chat_history = [{"role":"system","content":"You are an assistant tasked with helping people make a playlist of songs to listen to."}]



def parse_tracks_artists(input_str):
    try:
        parsed_data = ast.literal_eval(input_str)
        if isinstance(parsed_data, list) and all(isinstance(item, tuple) and len(item) == 2 for item in parsed_data):
            return parsed_data
    except (SyntaxError, ValueError):
        pass
    flash("Invalid input format. Please provide a list of tuples for tracks and artists.")
    return None

@app.route('/')
def index():
    """Homepage route."""
    # Check if the user is already authenticated
    if session.get('token_info'):
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login')
def login():
    """Route to initiate the Spotify OAuth process."""
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

# @app.route("/chat", methods=['POST', 'GET']) 
# def chat(): 
#     print("[STATUS] IN CHAT")
#     if request.method == 'POST': 
#         print('step1') 
#         prompt = request.form['prompt'] 
#         response = get_completion(prompt) 
#         print(response) 
  
#         return jsonify({'response': response}) 
#     return render_template('chat.html', display_name=session['display_name'], profile_picture=session['profile_picture']) 

@app.route('/chat', methods=['GET'])
def chat_page():
    # Render the initial HTML page
    return render_template('chat.html')  # Assuming the HTML file is named chat.html


@app.route('/chat', methods=['POST'])
def chat_stream():
    def get_completion(prompt): 
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=chat_history,
            stream=True
        )
        return(response)
    def generate():
        collected_messages=[]
        prompt = request.json.get('prompt')
        chat_history.append({"role":"user","content":prompt})
        full_reply_content = ""
        print(chat_history)
        response = get_completion(prompt)
        for chunk in response:
            if getattr(chunk.choices[0], 'stop_reason', None) is not None:
                break
            if getattr(chunk.choices[0].delta,'content') is None:
                break
            chunk_message = chunk.choices[0].delta
            full_reply_content += chunk_message.content
            yield chunk_message.content.encode('utf-8')

        collected_messages.append(chunk_message)
        print("*****" + full_reply_content + "*******")
        chat_history.append({"role":"assistant","content":full_reply_content})
    return Response(stream_with_context(generate()), mimetype='text/plain')


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    print("[STATUS] Dashboard route hit")
    print("SESSION CONTENT:", session.items())

    if not session.get('token_info'):
        print("[STATUS] No token in session")
        if request.method == 'POST':
            session['form_data'] = request.form.to_dict()
            print("[STATUS] Form data stored in session")
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)

    token_info = session.get('token_info', {})
    try:
        sp = spotipy.Spotify(auth=token_info['access_token'])  # Use the token to authenticate
        user_info = sp.current_user()
    except: 
        auth_url = sp_oauth.get_authorize_url()
        return(redirect(auth_url))

    if 'display_name' not in session or 'profile_picture' not in session:
        print("Token Info:", token_info)
        print("User Info:", user_info)
        session['display_name'] = user_info['display_name']
        session['profile_picture'] = user_info['images'][0]['url'] if user_info['images'] else None     
    
    if session.get('token_info') and request.method == 'POST':
        print("[STATUS] Token found in session and POST request made")

        if 'form_data' not in session:
            print("[STATUS] Getting form data and adding to session")
            session['form_data'] = request.form.to_dict()
        if 'form_data' in session:
            print("[STATUS] Form data present in session")
            form_data = session.pop('form_data')
        if 'playlist_name' not in form_data:
            flash("Must have a playlist name")
            return render_template('index.html')
        playlist_name = form_data['playlist_name']
        print('[STATUS] making playlist')
        
        spotify_username = user_info['id']

        if 'tracks_artists' not in form_data:
            print('getting form data again from the session.. it got lost?')
            form_data = session.pop('form_data')
        
        
        print("[STATUS] Parsing tracks")
        tracks_artists_str = form_data['tracks_artists']
        tracks_artists = parse_tracks_artists(tracks_artists_str)
        
        if tracks_artists is None:
            print('[STATUS] No artists parsed!')
            return render_template('index.html')
        
        # Create a new playlist
        print("[STATUS] Creating Playlist")
        playlist = sp.user_playlist_create(user=spotify_username, name=playlist_name)
        playlist_id = playlist['id']

        # Search for tracks and get their URIs
        print("[STATUS] Searching for songs!")
        track_uris = []
        for track, artist in tracks_artists:
            results = sp.search(q=f'track:{track} artist:{artist}', type='track', limit=1)
            items = results['tracks']['items']
            if items:
                track_uris.append(items[0]['uri'])

        # Add tracks to the playlist
        print(f"[STATUS] Adding {len(track_uris)} songs to playlist!")
        sp.playlist_add_items(playlist_id=playlist_id, items=track_uris)
        
        flash(f"{playlist_name} Playlist created successfully!")
        return redirect(url_for('dashboard'))

    return render_template('dashboard.html', display_name=session['display_name'], profile_picture=session['profile_picture'])

@app.route('/callback')
def callback():
    try:
        token_info = sp_oauth.get_access_token(request.args['code'])
        sp = spotipy.Spotify(auth=token_info['access_token'])  # Use the token to authenticate
        user_info = sp.current_user()
        session['token_info'] = token_info
        session['display_name'] = user_info['display_name']
        session['profile_picture'] = user_info['images'][0]['url'] if user_info['images'] else None   
        return redirect(url_for('chat_page'))
    except Exception as e:
        print(f"Error in callback: {e}")
        return str(e)  # For debugging purpose


@app.route('/logout')
def logout():
    # Clear all session data
    session.clear()

    # Redirect to homepage or login page
    return redirect(url_for("index"))

if __name__ == '__main__':
    app.run(debug=True)
