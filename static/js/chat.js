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
    });

    function periodicallyCheckForNewPlaylist() {
    setInterval(function() {
        $.get('/latest_playlist_id', function(data) {
            if (data.playlist_id) {
                var iframeSrc = 'https://open.spotify.com/embed/playlist/' + data.playlist_id;
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
                                }
                                controller.close();
                                return;
                            }

                            let chunkText = new TextDecoder().decode(value, {stream: true});
                            completeChunk += chunkText;

                            // Check for a chunk delimiter (e.g., newline) and process accordingly
                            if (chunkText.endsWith('\n')) {
                                updateChatUI(completeChunk);
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
