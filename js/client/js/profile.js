// Profile page JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Check for new user data from signup
    const newUserData = sessionStorage.getItem('newUserData');
    if (newUserData && window.location.pathname.includes('profile.html')) {
        const userData = JSON.parse(newUserData);
        
        // Update profile with the new user data
        document.querySelector('.profile-header h2').textContent = userData.fullname;
        document.querySelector('.profile-details .detail-value:nth-child(1)').textContent = userData.age;
        document.querySelector('.profile-details .detail-value:nth-child(2)').textContent = 
            userData.gender.charAt(0).toUpperCase() + userData.gender.slice(1);
        document.querySelector('.profile-details .detail-value:nth-child(3)').textContent = 
            userData.interestedIn.charAt(0).toUpperCase() + userData.interestedIn.slice(1);
        
        // Clear the session storage
        sessionStorage.removeItem('newUserData');
        
        // Show welcome message and prompt to complete profile
        setTimeout(() => {
            alert(`Welcome to HeartLink, ${userData.fullname}! Please complete your profile to get better matches.`);
            
            // Open the quiz modal
            const quizModal = new bootstrap.Modal(document.getElementById('quizModal'));
            quizModal.show();
        }, 500);
    }
    
    // Initialize profile photo upload
    const dropArea = document.getElementById('dropArea');
    const fileInput = document.getElementById('fileInput');
    const photoPreview = document.getElementById('photoPreview');
    const previewImage = document.getElementById('previewImage');
    
    if (dropArea && fileInput) {
        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, preventDefaults, false);
            document.body.addEventListener(eventName, preventDefaults, false);
        });
        
        // Highlight drop area when item is dragged over it
        ['dragenter', 'dragover'].forEach(eventName => {
            dropArea.addEventListener(eventName, highlight, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, unhighlight, false);
        });
        
        // Handle dropped files
        dropArea.addEventListener('drop', handleDrop, false);
        
        // Handle clicked files
        dropArea.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', handleFiles);
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        function highlight() {
            dropArea.classList.add('highlight');
        }
        
        function unhighlight() {
            dropArea.classList.remove('highlight');
        }
        
        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            handleFiles(files);
        }
        
        function handleFiles(files) {
            const file = files[0] || files;
            if (file.type.match('image.*')) {
                const reader = new FileReader();
                
                reader.onload = function(e) {
                    previewImage.src = e.target.result;
                    dropArea.style.display = 'none';
                    photoPreview.style.display = 'block';
                };
                
                reader.readAsDataURL(file);
            } else {
                alert('Please select an image file.');
            }
        }
        
        // Cancel crop button
        const cancelCropBtn = document.getElementById('cancelCropBtn');
        if (cancelCropBtn) {
            cancelCropBtn.addEventListener('click', function() {
                photoPreview.style.display = 'none';
                dropArea.style.display = 'block';
                fileInput.value = '';
            });
        }
        
        // Save photo button
        const savePhotoBtn = document.getElementById('savePhotoBtn');
        if (savePhotoBtn) {
            savePhotoBtn.addEventListener('click', function() {
                // In a real app, this would upload the photo to the server
                alert('Profile photo updated successfully!');
                bootstrap.Modal.getInstance(document.getElementById('photoModal')).hide();
                
                // Update profile photo (demo)
                document.querySelector('.profile-photo').src = previewImage.src;
                document.querySelector('.profile-pic-nav').src = previewImage.src;
            });
        }
    }
    
    // Edit profile functionality
    const editProfileModal = document.getElementById('editProfileModal');
    if (editProfileModal) {
        const editProfileForm = document.getElementById('editProfileForm');
        const saveProfileBtn = document.getElementById('saveProfileBtn');
        
        // When modal is shown, populate with current data
        editProfileModal.addEventListener('show.bs.modal', function() {
            const currentName = document.querySelector('.profile-header h2').textContent;
            const currentLocation = document.querySelector('.location').textContent.replace('📍 ', '');
            const currentBio = document.querySelector('.profile-section:nth-child(1) .section-content p').textContent;
            const currentRelationship = document.querySelector('.profile-details .detail-value:nth-child(4)').textContent;
            
            // Get current interests
            const interestTags = document.querySelectorAll('.interest-tag');
            const currentInterests = Array.from(interestTags).map(tag => tag.textContent).join(', ');
            
            document.getElementById('editName').value = currentName;
            document.getElementById('editLocation').value = currentLocation;
            document.getElementById('editBio').value = currentBio;
            document.getElementById('editRelationship').value = currentRelationship.toLowerCase();
            document.getElementById('editInterests').value = currentInterests;
        });
        
        // Save profile changes
        if (saveProfileBtn) {
            saveProfileBtn.addEventListener('click', function() {
                const name = document.getElementById('editName').value;
                const location = document.getElementById('editLocation').value;
                const bio = document.getElementById('editBio').value;
                const relationship = document.getElementById('editRelationship').value;
                const interests = document.getElementById('editInterests').value;
                
                // Simple validation
                if (!name || !location || !bio || !relationship || !interests) {
                    alert('Please fill in all fields');
                    return;
                }
                
                // In a real app, this would save to the server
                // For demo, we'll just update the UI
                document.querySelector('.profile-header h2').textContent = name;
                document.querySelector('.location').textContent = '📍 ' + location;
                document.querySelector('.profile-section:nth-child(1) .section-content p').textContent = bio;
                document.querySelector('.profile-details .detail-value:nth-child(4)').textContent = 
                    relationship.charAt(0).toUpperCase() + relationship.slice(1);
                
                // Update interests
                const interestsContainer = document.querySelector('.interests-container');
                interestsContainer.innerHTML = '';
                interests.split(',').forEach(interest => {
                    const trimmedInterest = interest.trim();
                    if (trimmedInterest) {
                        const span = document.createElement('span');
                        span.className = 'interest-tag';
                        span.textContent = trimmedInterest;
                        interestsContainer.appendChild(span);
                    }
                });
                
                // Update nav profile pic alt text
                document.querySelector('.profile-pic-nav').alt = name + "'s Profile";
                
                alert('Profile updated successfully!');
                bootstrap.Modal.getInstance(editProfileModal).hide();
            });
        }
    }
    
    // Personality quiz functionality
    const startQuizBtn = document.getElementById('startQuizBtn');
    const retakeQuizBtn = document.getElementById('retakeQuizBtn');
    
    if (startQuizBtn) {
        startQuizBtn.addEventListener('click', function() {
            const quizModal = new bootstrap.Modal(document.getElementById('quizModal'));
            quizModal.show();
        });
    }
    
    if (retakeQuizBtn) {
        retakeQuizBtn.addEventListener('click', function() {
            const quizModal = new bootstrap.Modal(document.getElementById('quizModal'));
            quizModal.show();
        });
    }
    
    // Quiz navigation
    const prevQuestionBtn = document.getElementById('prevQuestionBtn');
    const nextQuestionBtn = document.getElementById('nextQuestionBtn');
    const currentQuestionEl = document.getElementById('currentQuestion');
    const quizProgressBar = document.getElementById('quizProgressBar');
    
    if (prevQuestionBtn && nextQuestionBtn) {
        let currentQuestion = 1;
        const totalQuestions = 10;
        
        // Quiz questions data
        const questions = [
            "What's your ideal weekend?",
            "How do you handle conflict?",
            "What's your love language?",
            "How important is physical fitness to you?",
            "What's your approach to finances?",
            "How do you feel about pets?",
            "What's your idea of a perfect date?",
            "How important is career ambition in a partner?",
            "What's your stance on having children?",
            "How do you feel about long-distance relationships?"
        ];
        
        // Option icons for each question
        const optionIcons = [
            ['fa-hiking', 'fa-book', 'fa-utensils', 'fa-glass-cheers'],
            ['fa-comments', 'fa-walking-away', 'fa-handshake', 'fa-heart-crack'],
            ['fa-gifts', 'fa-hand-holding-heart', 'fa-comment-dots', 'fa-people-arrows'],
            ['fa-dumbbell', 'fa-walking', 'fa-couch', 'fa-bicycle'],
            ['fa-piggy-bank', 'fa-money-bill-wave', 'fa-credit-card', 'fa-chart-line'],
            ['fa-paw', 'fa-dog', 'fa-cat', 'fa-fish'],
            ['fa-movie', 'fa-hiking', 'fa-wine-glass', 'fa-home'],
            ['fa-briefcase', 'fa-balance-scale', 'fa-heart', 'fa-user-graduate'],
            ['fa-baby', 'fa-child', 'fa-user', 'fa-times'],
            ['fa-plane', 'fa-video', 'fa-heart', 'fa-times-circle']
        ];
        
        // Update quiz display
        function updateQuizDisplay() {
            document.getElementById('questionText').textContent = questions[currentQuestion - 1];
            currentQuestionEl.textContent = currentQuestion;
            quizProgressBar.style.width = `${(currentQuestion / totalQuestions) * 100}%`;
            
            // Update option icons
            const optionCards = document.querySelectorAll('.option-card');
            optionCards.forEach((card, index) => {
                const icon = card.querySelector('.option-icon i');
                icon.className = `fas ${optionIcons[currentQuestion - 1][index]}`;
            });
            
            // Update button states
            prevQuestionBtn.disabled = currentQuestion === 1;
            nextQuestionBtn.textContent = currentQuestion === totalQuestions ? 'Finish Quiz' : 'Next';
            nextQuestionBtn.disabled = true;
            
            // Clear any previous selections
            document.querySelectorAll('.option-card').forEach(card => {
                card.classList.remove('selected');
            });
        }
        
        // Option selection
        document.querySelectorAll('.option-card').forEach(card => {
            card.addEventListener('click', function() {
                // Remove selected class from all options
                document.querySelectorAll('.option-card').forEach(c => {
                    c.classList.remove('selected');
                });
                
                // Add selected class to clicked option
                this.classList.add('selected');
                
                // Enable next button
                nextQuestionBtn.disabled = false;
            });
        });
        
        // Button event listeners
        nextQuestionBtn.addEventListener('click', function() {
            if (currentQuestion < totalQuestions) {
                currentQuestion++;
                updateQuizDisplay();
            } else {
                // Quiz completed
                alert('Quiz completed! Your profile compatibility has been updated.');
                bootstrap.Modal.getInstance(document.getElementById('quizModal')).hide();
                
                // Update profile completion (demo)
                document.querySelector('.profile-compatibility .progress-bar').style.width = '100%';
                document.querySelector('.profile-compatibility p').textContent = 'Your profile is complete!';
                startQuizBtn.textContent = 'View Personality Traits';
                
                // Update personality traits section (demo)
                document.querySelector('.profile-section:last-child').style.display = 'block';
            }
        });
        
        prevQuestionBtn.addEventListener('click', function() {
            if (currentQuestion > 1) {
                currentQuestion--;
                updateQuizDisplay();
            }
        });
        
        // Initialize quiz
        updateQuizDisplay();
    }
    
    // Logout functionality
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            // In a real app, this would call your logout API
            // For demo, just clear rememberMe and redirect
            localStorage.removeItem('rememberMe');
            alert('You have been logged out successfully.');
            window.location.href = 'index.html';
        });
    }
    
    // Upgrade to premium button
    const upgradeBtn = document.querySelector('.btn-upgrade');
    if (upgradeBtn) {
        upgradeBtn.addEventListener('click', function() {
            alert('Premium upgrade would be processed here. In a real app, this would redirect to payment page.');
        });
    }
});