import os
import ast
import spotipy
import json
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify 
from flask import Response, stream_with_context
from flask_session import Session

from openai import OpenAI
# Load environment variables
load_dotenv()

GPT_MODEL = "gpt-4-1106-preview" #"gpt-3.5-turbo",
SPOTIFY_PLAYLIST_URL = "https://open.spotify.com/embed/playlist/"
DEMO_PLAYLIST = "6gcBbxehVQekJsRNOkzVLG"

# Set up the Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.environ['FLASK_SECRET_KEY']

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

system_instructions = """
You are an AI assistant who is a musical genius. You love all types of music and are so excited to help people find songs they love.
The goal of this conversation is to create a playlist for the user to listen to. If the conversation starts to go into other topics, 
tell the user that you are only able to assist with music-related tasks. 
You'll chat with the user and learn what kinds of songs they want, the duration/number of tracks for the playlist, 
suggest a good title for the playlist and work with the user to refine it until the user agrees it's ready.

Once the user agrees that the playlist is ready to create, instead of responding to the user. generate a JSON object

The JSON object should be in the form:

{
"playlist_title":"the title of the playlist"
"songs": [
{
  "title": "first_song_title",
  "artist": "first_song_artist"
}, ...

]}

Don't render it with markdown, just the JSON. And don't mention anything about JSON to the user.

Only give the JSON once the user agrees for you to make the playlist for them (we need permission)
"""
system_instructions_debug = """
You are an AI assistant who is a musical genius. You love all types of music and are so excited to help people find songs they love.
The goal of this conversation is to create a playlist for the user to listen to. If the conversation starts to go into other topics, 
tell the user that you are only able to assist with music-related tasks. 
You'll chat with the user and learn what kinds of songs they want, the duration/number of tracks for the playlist, 
suggest a good title for the playlist and work with the user to refine it until the user agrees it's ready.

Once the user agrees that the playlist is ready to create, instead of responding to the user. generate a JSON object

The JSON object should be in the form:

{
"playlist_title":"the title of the playlist"
"songs": [
{
  "title": "first_song_title",
  "artist": "first_song_artist"
}, ...

]}

Don't render it with markdown, just the JSON. Assume any details needed to make the playlist with as litte talking as possible.
"""
chat_history = [{"role":"system","content":system_instructions_debug}]

def extract_json(text):
    try:
        # Find the starting index of JSON structure
        start_index = text.find('{')
        # Find the ending index of JSON structure
        end_index = text.rfind('}') + 1

        # Extract the JSON string
        json_str = text[start_index:end_index]

        # Parse the JSON string into a Python dictionary
        return json.loads(json_str)
    except (ValueError, json.JSONDecodeError) as e:
        # Handle parsing errors (e.g., if the JSON is malformed)
        print("Error parsing JSON:", e)
        return None

def add_playlist_to_spotify(playlist_JSON):
    playlist_JSON = extract_json(playlist_JSON)
    print(playlist_JSON)
    if playlist_JSON is None:
        print("FAILED JSON EXTRACT")
        return
    print("MAKING PLAYLIST!")
    sp = session['sp']
    playlist_name = playlist_JSON.get('playlist_title', "Generated Playlist")
    print(f'Playlist name: {playlist_name}')
    user_info = session['user_info']
    spotify_username = user_info['id']
    playlist = sp.user_playlist_create(user=spotify_username, name=playlist_name)
    playlist_id = playlist['id']
    # Search for tracks and get their URIs
    print("[STATUS] Searching for songs!")
    track_uris = []
    for song in playlist_JSON['songs']:
        results = sp.search(q=f"track:{song['title']} artist:{song['artist']}", type='track', limit=1)
        items = results['tracks']['items']
        if items:
            track_uris.append(items[0]['uri'])
    # Add tracks to the playlist
    print(f"[STATUS] Adding {len(track_uris)} songs to playlist!")
    sp.playlist_add_items(playlist_id=playlist_id, items=track_uris)
    return playlist_id

# @app.route('/latest_playlist_id')
# def get_latest_playlist_id():
#     print(f"session playlist: {session['playlist_id']}")
#     return jsonify({'playlist_id': session['playlist_id']})
@app.route('/test_update_session')
def test_update_session():
    session['playlist_id'] = 'test_id'
    session.modified = True
    return 'Session updated'

@app.route('/test_get_session')
def test_get_session():
    return f"Playlist ID: {session.get('playlist_id', 'Not set')}"

@app.route('/latest_playlist_id')
def get_latest_playlist_id():
    print(session.get('playlist_id', DEMO_PLAYLIST))
    response = jsonify({'playlist_id': session.get('playlist_id', DEMO_PLAYLIST)})
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/')
def index():
    """Homepage route."""
    # Check if the user is already authenticated
    if session.get('token_info'):
        return redirect(url_for('logout'))
    return render_template('index.html')


@app.route('/login')
def login():
    """Route to initiate the Spotify OAuth process."""
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/chat', methods=['GET'])
def chat_page():
    # Render the initial HTML page
    welcome_message = {"role": "assistant", "content": f"Hey {session['display_name'].split()[0]}, I'd love to help you make a playlist!"}
    session['welcome_message'] = welcome_message
    if session['playlist_id'] is None:
        playlist_url = DEMO_PLAYLIST
    else:
        paylist_url = session['playlist_url']
    return render_template('chat.html', display_name=session['display_name'], profile_picture=session['profile_picture'],
    
    playlist_url= playlist_url, welcome_message = welcome_message)

@app.route('/chat', methods=['POST'])
def chat_stream():
    def get_completion(prompt): 
        
        response = client.chat.completions.create(
            model = GPT_MODEL,
            messages=chat_history,
            stream=True
        )
        return(response)
    def generate():
        prompt = request.json.get('prompt')
        chat_history.append({"role": "user", "content": prompt})
        response = get_completion(prompt)
        
        generating_playlist = False
        full_bot_response=""
        playlist_JSON = ""
        for chunk in response:
            print(chunk)
            # Check if delta exists and has content
            if hasattr(chunk.choices[0], 'delta') and getattr(chunk.choices[0].delta, 'content', None):
                chunk_message = chunk.choices[0].delta.content
                full_bot_response += chunk_message
                if "{" in chunk_message or generating_playlist == True:
                    playlist_JSON += chunk_message
                    if not generating_playlist:
                        print('[STATUS] creating JSON object!')
                        generating_playlist = True
                        yield "Playlist Created!".encode('utf-8')
                    else:
                        yield "".encode('utf-8')
                else:
                    yield chunk_message.encode('utf-8')

            # Check if there is a stop reason to end the stream
            if getattr(chunk.choices[0], 'finish_reason', None) is not None:
                print('finish_reason found')
                if generating_playlist:
                    playlist = add_playlist_to_spotify(playlist_JSON)
                    print(f"NEW PLAYLIST: {playlist}")
                    yield f"playlist_id:{playlist}".encode('utf-8')
                else: 
                    break
        chat_history.append({"role": "assistant", "content": full_bot_response})
        
    return Response(stream_with_context(generate()), mimetype='text/plain')
    
@app.route('/callback')
def callback():
    try:
        token_info = sp_oauth.get_access_token(request.args['code'])
        sp = spotipy.Spotify(auth=token_info['access_token'])  # Use the token to authenticate
        user_info = sp.current_user()
        session['sp'] = sp
        session['user_info'] = user_info
        session['token_info'] = token_info
        session['display_name'] = user_info['display_name']
        session['profile_picture'] = user_info['images'][0]['url'] if user_info['images'] else None  
        session['playlist_id'] = None 
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
