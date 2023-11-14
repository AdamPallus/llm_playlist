import os
import ast
import spotipy
import json
import requests
import base64

from PIL import Image
from io import BytesIO
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify 
from flask import Response, stream_with_context
from flask_session import Session
from openai import OpenAI, OpenAIError
from threading import Thread

# Load environment variables from .env file
load_dotenv()

GPT_MODEL = "gpt-4-1106-preview" #"gpt-3.5-turbo",
SPOTIFY_PLAYLIST_URL = "https://open.spotify.com/embed/playlist/"
DEMO_PLAYLIST = "6gcBbxehVQekJsRNOkzVLG"

# Set up the Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY')

# Configure Flask-Session
#app.config['SESSION_TYPE'] = 'filesystem'
#app.config['SESSION_PERMANENT'] = False
#app.config['SESSION_USE_SIGNER'] = True

# Initialize Flask-Session
#Session(app)

sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="playlist-modify-public ugc-image-upload"
)


client = OpenAI()

system_instructions = """
You are an AI assistant who is a musical genius. You love all types of music and are so excited to help people find songs they love.
The goal of this conversation is to create a playlist for the user to listen to. If the conversation starts to go into other topics, 
tell the user that you are only able to assist with music-related tasks. 
You'll chat with the user and learn what kinds of songs they want, the duration/number of tracks for the playlist, 
suggest a good title for the playlist and work with the user to refine it until the user agrees it's ready.

You can also ask the user to describe the kind of album cover art they think will go with the album,
or you can make this up based on what you've learned about the user's preferences through the conversation. 
Try to avoid anything that might be flagged as dangerous or inappropriate by the image generator.

Once the user agrees that the playlist is ready to create, instead of responding to the user. generate a JSON object

The JSON object should be in the form:

{
"task":"CREATE_PLAYLIST",
"playlist_title":"the title of the playlist",
"playlist_description":"a very short description explaining what inspired this playlist"
"playlist_cover_art":"a detailed description of what the album cover should look like",
"songs": [
{
  "title": "first_song_title",
  "artist": "first_song_artist"
}, ...

]}

Don't mention anything about JSON to the user, they don't know what JSON is. Just say you're making the playlist.
If the user does not want cover art, just set it to an empty string.

Only give the JSON once the user agrees for you to make the playlist for them (we need permission).
Don't tell the user you're ready to make a playlist, just start returning the JSON when ready.
"""

def make_album_art(playlist_cover_art,playlist_id,token_info):
    print('requesting image from DALL-E')
    def get_response(prompt):
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
            )
        return(response)
    try:
        response = get_response(playlist_cover_art)
    except OpenAIError as e:
        print(e.error)
        print(e.http_status)
        print(e.error)
        return None

    image_url = response.data[0].url
    print('image genrated successfully')
    print(image_url)
    encoded_jpg = encode_jpg(image_url)
    print('JPG encoded successfully')
    try:
        sp = spotipy.Spotify(auth=token_info['access_token'])
        sp.playlist_upload_cover_image(playlist_id, encoded_jpg)
        print("Cover added successfully!")
    except Exception as e:
        print(e)


def encode_jpg(url):
    try:
        # Download the image
        response = requests.get(url)
        image = Image.open(BytesIO(response.content))

        # Resize the image to 512x512
        image = image.resize((512, 512))

        # Convert the image to JPEG (if not already in this format)
        with BytesIO() as f:
            image.save(f, format='JPEG')
            image_jpeg = f.getvalue()

        # Encode the image in base64
        encoded_string = base64.b64encode(image_jpeg).decode('utf-8')
        return encoded_string
    except Exception as e:
        print(f"Error in encode_jpg: {e}")
        return None

def extract_json(text):
    print(text)
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
    try: 
        token_info = session.get('token_info')
        sp = spotipy.Spotify(auth=token_info['access_token'])  # Use the token to authenticate
        user_info = sp.current_user()
    except:
        print('Failed to get spotify token working')
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
        
    playlist_name = playlist_JSON.get('playlist_title', "Generated Playlist")
    playlist_description = playlist_JSON.get('playlist_description',"")
    print(f'Playlist name: {playlist_name}')
    print(f'Playlist description: {playlist_description}')

    spotify_username = user_info['id']
    playlist = sp.user_playlist_create(user=spotify_username, name=playlist_name, description=playlist_description)
    playlist_id = playlist['id']

    playlist_cover_art = playlist_JSON.get('playlist_cover_art',"")
    
    print(playlist_cover_art)
    if  len(playlist_cover_art)>10:
        yield('Generating Album Art!\n'.encode('utf-8'))
        print('[STATUS] Generating Album Art!')
        playlist_thread = Thread(target = make_album_art, args=(playlist_cover_art,playlist_id, token_info))
        playlist_thread.start()

    # Search for tracks and get their URIs
    yield('Searching for songs!\n'.encode('utf-8'))
    print("[STATUS] Searching for songs!")
    track_uris = []
    for song in playlist_JSON['songs']:
        results = sp.search(q=f"track:{song['title']} artist:{song['artist']}", type='track', limit=1)
        items = results['tracks']['items']
        if items:
            track_uris.append(items[0]['uri'])
    # Add tracks to the playlist
    print(f"[STATUS] Adding {len(track_uris)} songs to playlist!")
    yield(f'Adding {len(track_uris)} songs to playlist!\n'.encode('utf-8'))
    sp.playlist_add_items(playlist_id=playlist_id, items=track_uris)
    
    yield f"playlist_id:{playlist_id}".encode('utf-8')

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
    playlist_url = DEMO_PLAYLIST
    initial_chat_history = [{"role": "system", "content": system_instructions}]
    return render_template('chat.html', display_name=session['display_name'], profile_picture=session['profile_picture'],
                            playlist_url= playlist_url, welcome_message = welcome_message,
                            initial_chat_history=initial_chat_history)

@app.route('/chat', methods=['POST'])
def chat_stream():
    def get_completion(messages): 
        
        response = client.chat.completions.create(
            model = GPT_MODEL,
            messages=messages,
            stream=True
        )
        return(response)
    def generate():
        data = request.json
        chat_history = data['chatHistory']
        print(chat_history)
        response = get_completion(chat_history)
        
        generating_playlist = False #tracks when bot has decided to generate the playlist
        full_bot_response=""
        playlist_JSON = ""
        for chunk in response:
            # Check if delta exists and has content
            if hasattr(chunk.choices[0], 'delta') and getattr(chunk.choices[0].delta, 'content', None):
                chunk_message = chunk.choices[0].delta.content
                full_bot_response += chunk_message
                if "{" in chunk_message or generating_playlist == True:
                    playlist_JSON += chunk_message
                    if not generating_playlist:
                        print('[STATUS] creating JSON object!')
                        generating_playlist = True
                        yield "Generating playlist...\n".encode('utf-8')
                    else:
                        yield "".encode('utf-8')
                else:
                    yield chunk_message.encode('utf-8')

            # Check if there is a stop reason to end the stream
            if getattr(chunk.choices[0], 'finish_reason', None) is not None:
                print('finish_reason found')
                print(full_bot_response)
                if generating_playlist:
                    #print(f"NEW PLAYLIST: {playlist}")
                    yield from add_playlist_to_spotify(playlist_JSON)
                else: 
                    break
    return Response(stream_with_context(generate()), mimetype='text/plain')
    
@app.route('/callback')
def callback():
    try:
        token_info = sp_oauth.get_access_token(request.args['code'], check_cache=False)
        sp = spotipy.Spotify(auth=token_info['access_token'])  # Use the token to authenticate
        user_info = sp.current_user()
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
