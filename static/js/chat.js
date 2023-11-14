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
            addMessageToHistory(userMessage, 'user')
            displayUserMessage(userMessage);
            fetchStream(chatHistory);
            $('#prompt').val('');
        });
        
        if (welcomeMessage && welcomeMessage.role === "assistant") {
                    updateChatUI(welcomeMessage.content);
        }
    });

    function addMessageToHistory(message, role) {
        chatHistory.push({ role: role, content: message });
        // Update the UI or perform other actions as needed
    }
    
    function fetchStream(chatHistory) {
        fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({chatHistory: chatHistory})
        })
        .then(response => {
            const reader = response.body.getReader();
            let completeChunk = '';
            let isPlaylist = false;
            return new ReadableStream({
                start(controller) {
                    function push() {
                        reader.read().then(({ done, value }) => {
                            if (done) {
                                if (completeChunk) {
                                    addMessageToHistory(completeChunk, 'assistant')
                                    isPlaylist = checkForPlaylistCreation(completeChunk)
                                    if (!isPlaylist){
                                        updateChatUI(completeChunk);
                                    }
                                }
                                controller.close();
                                return;
                            }

                            let chunkText = new TextDecoder().decode(value, {stream: true});
                            completeChunk += chunkText;

                            // Check for a chunk delimiter (e.g., newline) and process accordingly
                            if (chunkText.endsWith('\n')) {
                                isPlaylist = checkForPlaylistCreation(completeChunk)
                                    if (!isPlaylist){
                                        updateChatUI(completeChunk);
                                    }
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
        // If the new playlist ID is available in the chunk, update the iframe
        if (chunk.includes("playlist_id")) {
            playlistId=chunk.split(':')[1]
            console.log("we found the ID!!")
            var iframeSrc = 'https://open.spotify.com/embed/playlist/' + playlistId;
            $('#spotify-iframe').attr('src', iframeSrc);
            return true
        }
        return(false)
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



