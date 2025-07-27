// Mobile menu toggle
document.addEventListener('DOMContentLoaded', function() {
    // Mobile menu toggle
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarNav = document.querySelector('#navbarNav');
    
    navbarToggler.addEventListener('click', function() {
        navbarNav.classList.toggle('show');
    });
    
    // Testimonial slider
    const testimonials = document.querySelectorAll('.testimonial');
    let currentTestimonial = 0;
    
    function showTestimonial(index) {
        testimonials.forEach(testimonial => testimonial.classList.remove('active'));
        testimonials[index].classList.add('active');
    }
    
    if (testimonials.length > 0) {
        setInterval(() => {
            currentTestimonial = (currentTestimonial + 1) % testimonials.length;
            showTestimonial(currentTestimonial);
        }, 5000);
    }
    
    // Age range slider
    const ageMin = document.getElementById('ageMin');
    const ageMax = document.getElementById('ageMax');
    const ageMinValue = document.getElementById('ageMinValue');
    const ageMaxValue = document.getElementById('ageMaxValue');
    
    if (ageMin && ageMax) {
        ageMin.addEventListener('input', function() {
            if (parseInt(ageMin.value) > parseInt(ageMax.value)) {
                ageMax.value = ageMin.value;
                ageMaxValue.textContent = ageMin.value;
            }
            ageMinValue.textContent = ageMin.value;
        });
        
        ageMax.addEventListener('input', function() {
            if (parseInt(ageMax.value) < parseInt(ageMin.value)) {
                ageMin.value = ageMax.value;
                ageMinValue.textContent = ageMax.value;
            }
            ageMaxValue.textContent = ageMax.value;
        });
    }
    
    // Chat functionality
    const conversations = document.querySelectorAll('.conversation');
    const chatAreaCol = document.querySelector('.chat-area-col');
    const closeSidebar = document.querySelector('.btn-close-sidebar');
    const profileSidebar = document.querySelector('.profile-sidebar');
    const btnEmoji = document.querySelector('.btn-emoji');
    const btnAttach = document.querySelector('.btn-attach');
    const emojiPicker = document.querySelector('.emoji-picker');
    const attachmentMenu = document.querySelector('.attachment-menu');
    
    // Show chat area when conversation is clicked (on mobile)
    conversations.forEach(conversation => {
        conversation.addEventListener('click', function() {
            if (window.innerWidth < 992) {
                chatAreaCol.style.display = 'block';
                conversations.forEach(c => c.classList.remove('active'));
                this.classList.add('active');
            }
        });
    });
    
    // Close sidebar
    if (closeSidebar) {
        closeSidebar.addEventListener('click', function() {
            profileSidebar.classList.remove('open');
        });
    }
    
    // Toggle emoji picker
    if (btnEmoji) {
        btnEmoji.addEventListener('click', function(e) {
            e.stopPropagation();
            attachmentMenu.classList.remove('open');
            emojiPicker.classList.toggle('open');
        });
    }
    
    // Toggle attachment menu
    if (btnAttach) {
        btnAttach.addEventListener('click', function(e) {
            e.stopPropagation();
            emojiPicker.classList.remove('open');
            attachmentMenu.classList.toggle('open');
        });
    }
    
    // Close pickers when clicking outside
    document.addEventListener('click', function() {
        emojiPicker.classList.remove('open');
        attachmentMenu.classList.remove('open');
    });
    
    // Prevent pickers from closing when clicking inside
    if (emojiPicker) {
        emojiPicker.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }
    
    if (attachmentMenu) {
        attachmentMenu.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }
    
    // Generate emojis
    if (emojiPicker) {
        const emojiContainer = document.querySelector('.emoji-container');
        const emojis = ['😀', '😃', '😄', '😁', '😆', '😅', '😂', '🤣', '😊', '😇', '🙂', '🙃', '😉', '😌', '😍', '🥰', '😘', '😗', '😙', '😚', '😋', '😛', '😝', '😜', '🤪', '🤨', '🧐', '🤓', '😎', '🤩', '🥳', '😏', '😒', '😞', '😔', '😟', '😕', '🙁', '☹️', '😣', '😖', '😫', '😩', '🥺', '😢', '😭', '😤', '😠', '😡', '🤬', '🤯', '😳', '🥵', '🥶', '😱', '😨', '😰', '😥', '😓', '🤗', '🤔', '🤭', '🤫', '🤥', '😶', '😐', '😑', '😬', '🙄', '😯', '😦', '😧', '😮', '😲', '🥱', '😴', '🤤', '😪', '😵', '🤐', '🥴', '🤢', '🤮', '🤧', '😷', '🤒', '🤕', '🤑', '🤠', '😈', '👿', '👹', '👺', '🤡', '💩', '👻', '💀', '☠️', '👽', '👾', '🤖', '🎃', '😺', '😸', '😹', '😻', '😼', '😽', '🙀', '😿', '😾'];
        
        emojis.forEach(emoji => {
            const span = document.createElement('span');
            span.textContent = emoji;
            span.addEventListener('click', function() {
                const input = document.querySelector('.message-input input');
                input.value += emoji;
                input.focus();
            });
            emojiContainer.appendChild(span);
        });
    }
    
    // Form submission
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            // Here you would typically send the form data to a server
            alert('Form submitted! In a real app, this would send data to your server.');
        });
    });
    
    // Back to chat list on mobile
    const backToChatList = document.createElement('button');
    backToChatList.className = 'btn btn-back d-lg-none';
    backToChatList.innerHTML = '<i class="fas fa-arrow-left"></i> Back to chats';
    backToChatList.style.display = 'none';
    backToChatList.style.margin = '10px';
    
    if (chatAreaCol) {
        chatAreaCol.insertBefore(backToChatList, chatAreaCol.firstChild);
        
        backToChatList.addEventListener('click', function() {
            chatAreaCol.style.display = 'none';
            document.querySelector('.conversation.active').classList.add('active');
        });
        
        // Show back button on mobile when chat is open
        if (window.innerWidth < 992 && chatAreaCol.style.display === 'block') {
            backToChatList.style.display = 'block';
        }
    }
    
    // Responsive adjustments
    window.addEventListener('resize', function() {
        if (window.innerWidth >= 992) {
            if (chatAreaCol) chatAreaCol.style.display = 'block';
            if (backToChatList) backToChatList.style.display = 'none';
        } else {
            if (backToChatList && chatAreaCol.style.display === 'block') {
                backToChatList.style.display = 'block';
            }
        }
    });
    
    // Animation on scroll
    const animateOnScroll = function() {
        const elements = document.querySelectorAll('.animate__animated');
        
        elements.forEach(element => {
            const elementPosition = element.getBoundingClientRect().top;
            const windowHeight = window.innerHeight;
            
            if (elementPosition < windowHeight - 100) {
                const animationClass = element.getAttribute('data-animation');
                element.classList.add(animationClass || 'animate__fadeInUp');
            }
        });
    };
    
    window.addEventListener('scroll', animateOnScroll);
    animateOnScroll(); // Run once on page load
});

// Auth specific functionality
document.addEventListener('DOMContentLoaded', function() {
    // Toggle between login and signup forms
    const loginLink = document.querySelector('.auth-footer a[href="login.html"]');
    const signupLink = document.querySelector('.auth-footer a[href="signup.html"]');
    
    if (loginLink && window.location.pathname.includes('login.html')) {
        loginLink.addEventListener('click', function(e) {
            e.preventDefault();
            window.location.href = 'signup.html';
        });
    }
    
    if (signupLink && window.location.pathname.includes('signup.html')) {
        signupLink.addEventListener('click', function(e) {
            e.preventDefault();
            window.location.href = 'login.html';
        });
    }
    
    // Form validation for signup
    const signupForm = document.getElementById('signupForm');
    if (signupForm) {
        signupForm.addEventListener('submit', function(e) {
            const age = document.getElementById('age');
            const gender = document.getElementById('gender');
            const interestedIn = document.getElementById('interested-in');
            const terms = document.getElementById('terms');
            
            if (!terms.checked) {
                alert('You must agree to the Terms of Service and Privacy Policy');
                e.preventDefault();
                return;
            }
            
            if (!age.value || !gender.value || !interestedIn.value) {
                alert('Please fill in all required fields');
                e.preventDefault();
                return;
            }
            
            // If all validations pass, redirect to onboarding/questions page
            // In a real app, you would send this data to your server first
            window.location.href = 'profile.html'; // Change to onboarding page when created
        });
    }
});