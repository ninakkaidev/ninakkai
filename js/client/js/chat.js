document.addEventListener('DOMContentLoaded', function() {
    // Initialize chat functionality
    const messageInput = document.querySelector('.message-input input');
    const sendButton = document.querySelector('.btn-send');
    const messagesContainer = document.querySelector('.messages-container');
    
    // Function to add a new message to the chat
    function addMessage(text, isReceived = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isReceived ? 'received' : 'sent'}`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        const messageText = document.createElement('p');
        messageText.textContent = text;
        
        const messageTime = document.createElement('span');
        messageTime.className = 'message-time';
        const now = new Date();
        messageTime.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        messageContent.appendChild(messageText);
        messageContent.appendChild(messageTime);
        messageDiv.appendChild(messageContent);
        
        messagesContainer.appendChild(messageDiv);
        
        // Scroll to the bottom of the messages
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    // Send message when clicking send button
    if (sendButton) {
        sendButton.addEventListener('click', function() {
            const message = messageInput.value.trim();
            if (message) {
                addMessage(message);
                messageInput.value = '';
                
                // Simulate received message after a delay
                setTimeout(() => {
                    const replies = [
                        "That's interesting! Tell me more.",
                        "I'd love to hear more about that.",
                        "Sounds great!",
                        "What else have you been up to?",
                        "That's awesome!",
                        "I feel the same way."
                    ];
                    const randomReply = replies[Math.floor(Math.random() * replies.length)];
                    addMessage(randomReply, true);
                }, 1000 + Math.random() * 2000);
            }
        });
    }
    
    // Send message when pressing Enter
    if (messageInput) {
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendButton.click();
            }
        });
    }
    
    // Toggle profile sidebar
    const profileSidebar = document.querySelector('.profile-sidebar');
    const chatPartner = document.querySelector('.chat-partner');
    
    if (chatPartner && profileSidebar) {
        chatPartner.addEventListener('click', function() {
            profileSidebar.classList.toggle('open');
        });
    }
    
    // Simulate typing indicator
    function showTypingIndicator() {
        const typingIndicator = document.createElement('div');
        typingIndicator.className = 'message received typing-indicator';
        
        const typingContent = document.createElement('div');
        typingContent.className = 'message-content';
        
        const typingDots = document.createElement('div');
        typingDots.className = 'typing-dots';
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('span');
            typingDots.appendChild(dot);
        }
        
        typingContent.appendChild(typingDots);
        typingIndicator.appendChild(typingContent);
        messagesContainer.appendChild(typingIndicator);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        return typingIndicator;
    }
    
    function hideTypingIndicator(indicator) {
        if (indicator && indicator.parentNode) {
            indicator.parentNode.removeChild(indicator);
        }
    }
    
    // Simulate receiving messages randomly
    setInterval(() => {
        if (Math.random() > 0.7) { // 30% chance of receiving a message
            const typingIndicator = showTypingIndicator();
            
            setTimeout(() => {
                hideTypingIndicator(typingIndicator);
                
                const messages = [
                    "Hey, how's your day going?",
                    "I was thinking about you today!",
                    "What are your plans for the weekend?",
                    "Have you seen any good movies lately?",
                    "I just tried this amazing new restaurant.",
                    "What's your favorite type of music?",
                    "Do you enjoy traveling?",
                    "I'm really enjoying our conversations."
                ];
                
                const randomMessage = messages[Math.floor(Math.random() * messages.length)];
                addMessage(randomMessage, true);
            }, 1000 + Math.random() * 3000);
        }
    }, 10000); // Check every 10 seconds
    
    // Handle image upload
    const attachButton = document.querySelector('.btn-attach');
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/*';
    fileInput.style.display = 'none';
    
    if (attachButton) {
        attachButton.addEventListener('click', function() {
            fileInput.click();
        });
    }
    
    fileInput.addEventListener('change', function(e) {
        if (e.target.files && e.target.files[0]) {
            const reader = new FileReader();
            
            reader.onload = function(event) {
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message sent';
                
                const messageContent = document.createElement('div');
                messageContent.className = 'message-content';
                
                const messageImage = document.createElement('div');
                messageImage.className = 'message-image';
                
                const img = document.createElement('img');
                img.src = event.target.result;
                
                const messageTime = document.createElement('span');
                messageTime.className = 'message-time';
                const now = new Date();
                messageTime.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                
                messageImage.appendChild(img);
                messageContent.appendChild(messageImage);
                messageContent.appendChild(document.createElement('p')).textContent = 'Check this out!';
                messageContent.appendChild(messageTime);
                messageDiv.appendChild(messageContent);
                
                messagesContainer.appendChild(messageDiv);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            };
            
            reader.readAsDataURL(e.target.files[0]);
        }
    });
    
    // Handle emoji selection
    document.querySelectorAll('.emoji-container span').forEach(emoji => {
        emoji.addEventListener('click', function() {
            messageInput.value += this.textContent;
            messageInput.focus();
        });
    });
    
    // Mark messages as read when opening chat
    const activeConversation = document.querySelector('.conversation.active');
    if (activeConversation) {
        const unreadCount = activeConversation.querySelector('.unread-count');
        if (unreadCount) {
            unreadCount.style.display = 'none';
        }
    }
    
    // Video call button
    const videoCallButton = document.querySelector('.btn-video');
    if (videoCallButton) {
        videoCallButton.addEventListener('click', function() {
            alert('Video call functionality would be enabled with a premium subscription.');
        });
    }
    
    // Voice call button
    const voiceCallButton = document.querySelector('.btn-call');
    if (voiceCallButton) {
        voiceCallButton.addEventListener('click', function() {
            alert('Voice call functionality would be enabled with a premium subscription.');
        });
    }
});