       $(document).ready(function() {
        $('#prompt').keypress(function(event) {
            if (event.keyCode === 13 && !event.shiftKey) {
                event.preventDefault();
                $('form').submit();
            }
        });

        $('form').on('submit', function(event) {
            event.preventDefault();
            var userMessage = $('#prompt').val();
            displayUserMessage(userMessage);
            fetchStream(userMessage);
            $('#prompt').val('');
        });
        
        if (welcomeMessage && welcomeMessage.role === "assistant") {
                    updateChatUI(welcomeMessage.content);
        }
        //periodicallyCheckForNewPlaylist()
    });

    function periodicallyCheckForNewPlaylist() {
        var currentPlaylistId = null; // Variable to store the current playlist ID
    
        setInterval(function() {
            $.get('/latest_playlist_id', function(data) {
                if (data.playlist_id && data.playlist_id !== currentPlaylistId) {
                    // Update the currentPlaylistId
                    currentPlaylistId = data.playlist_id;
    
                    // Build the new iframe src URL
                    var iframeSrc = 'https://open.spotify.com/embed/playlist/' + data.playlist_id;
    
                    // Update the iframe src only if it's different
                    $('#spotify-iframe').attr('src', iframeSrc);
                }
            });
        }, 5000); // Check every 5 seconds, adjust timing as appropriate
    }
    

    function fetchStream(prompt) {
        fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({prompt: prompt})
        })
        .then(response => {
            const reader = response.body.getReader();
            let completeChunk = '';

            return new ReadableStream({
                start(controller) {
                    function push() {
                        reader.read().then(({ done, value }) => {
                            if (done) {
                                if (completeChunk) {
                                    updateChatUI(completeChunk);
                                    checkForPlaylistCreation(completeChunk);
                                }
                                controller.close();
                                return;
                            }

                            let chunkText = new TextDecoder().decode(value, {stream: true});
                            completeChunk += chunkText;

                            // Check for a chunk delimiter (e.g., newline) and process accordingly
                            if (chunkText.endsWith('\n')) {
                                updateChatUI(completeChunk);
                                checkForPlaylistCreation(completeChunk);
                                completeChunk = ''; // Reset for the next chunk
                            }

                            controller.enqueue(value);
                            push();
                        });
                    }
                    push();
                }
            });
        })
        .catch(err => console.error(err));
    }

    function checkForPlaylistCreation(chunk) {
        // Example: Check if the chunk contains the specific token/pattern
        console.log(chunk)

        if (chunk.includes("playlist_id")) {
            playlistId=chunk.split(':')[1]
            console.log("we found the ID!!")
            var iframeSrc = 'https://open.spotify.com/embed/playlist/' + playlistId;
            $('#spotify-iframe').attr('src', iframeSrc);
            // If the new playlist ID is available in the chunk, update the iframe
            // var newPlaylistId = extractPlaylistId(chunk);
            // updatePlaylistIframe(newPlaylistId);
        }
    }
    var currentBotMessageId = null;

    function displayUserMessage(message) {
        var dateTime = new Date();
        var time = dateTime.toLocaleTimeString();
        var messageId = 'user-msg-' + dateTime.getTime(); // Unique ID for user message

        $('#response').append('<div id="' + messageId + '" class="user-message"> <i class="bi bi-person"></i>: ' + message + '</div>');
        currentBotMessageId = null; // Reset bot message ID for new response
    }

    function updateChatUI(chunk) {
        var dateTime = new Date();
        var time = dateTime.toLocaleTimeString();

        if (!currentBotMessageId) {
            currentBotMessageId = 'bot-msg-' + dateTime.getTime(); // Unique ID for bot message
            $('#response').append('<div id="' + currentBotMessageId + '" class="bot-message"><i class="bi bi-robot"></i>: </div>');
        }

        var converter = new showdown.Converter();
        var html = converter.makeHtml(chunk);
        $('#' + currentBotMessageId).append(html); // Append chunk as HTML
    }



