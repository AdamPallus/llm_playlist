## Adam's LLM Spotify Playlist Maker

ChatGPT is great at making song and playlist recommendations but there is no easy way to actually listen to the songs it suggests.

To solve this problem, ask chatGPT to give you its song recommendations as a python-style list of tuples in the form:

```
[("song1","artist1"),
 (song2","artist2"),
 ...]

```

This repo contains a flask app that lets you paste this list of tuples and it will automatically search for the songs and add them to a playlist for you. 

The app is deployed on heroku and I'm curerntly experimenting with using redis for session management.

If you want to host this yourself you'll need to register your app for your own spotify API key