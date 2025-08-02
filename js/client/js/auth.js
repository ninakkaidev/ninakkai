document.addEventListener('DOMContentLoaded', function() {
    // Social login buttons
    const googleLogin = document.querySelector('.btn-social.google');
    const appleLogin = document.querySelector('.btn-social.apple');
    
    if (googleLogin) {
        googleLogin.addEventListener('click', function(e) {
            e.preventDefault();
            alert('In a real app, this would redirect to Google OAuth login.');
            // window.location.href = '/auth/google';
        });
    }
    
    if (appleLogin) {
        appleLogin.addEventListener('click', function(e) {
            e.preventDefault();
            alert('In a real app, this would redirect to Apple OAuth login.');
            // window.location.href = '/auth/apple';
        });
    }
    
    // Form validation for login
    const loginForm = document.querySelector('.auth-form');
    if (loginForm && !document.getElementById('signupForm')) {
        loginForm.addEventListener('submit', function(e) {
            const email = document.getElementById('email');
            const password = document.getElementById('password');
            
            if (!email.value || !password.value) {
                alert('Please fill in all fields');
                e.preventDefault();
                return;
            }
            
            // In a real app, you would validate the email format
            if (!email.value.includes('@')) {
                alert('Please enter a valid email address');
                e.preventDefault();
                return;
            }
            
            // Simulate successful login
            // In a real app, you would send this to your server
            alert('Login successful! Redirecting to your profile...');
            window.location.href = 'profile.html';
            e.preventDefault();
        });
    }
    
    // Password visibility toggle
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    passwordInputs.forEach(input => {
        const toggle = document.createElement('span');
        toggle.className = 'password-toggle';
        toggle.innerHTML = '<i class="far fa-eye"></i>';
        toggle.style.position = 'absolute';
        toggle.style.right = '15px';
        toggle.style.top = '50%';
        toggle.style.transform = 'translateY(-50%)';
        toggle.style.cursor = 'pointer';
        toggle.style.color = '#777';
        
        input.style.paddingRight = '40px';
        input.parentElement.style.position = 'relative';
        input.parentElement.appendChild(toggle);
        
        toggle.addEventListener('click', function() {
            if (input.type === 'password') {
                input.type = 'text';
                toggle.innerHTML = '<i class="far fa-eye-slash"></i>';
            } else {
                input.type = 'password';
                toggle.innerHTML = '<i class="far fa-eye"></i>';
            }
        });
    });
    
    // Age validation
    const ageInput = document.getElementById('age');
    if (ageInput) {
        ageInput.addEventListener('change', function() {
            if (parseInt(this.value) < 18) {
                alert('You must be at least 18 years old to use this service');
                this.value = 18;
            }
        });
    }
    
    // Forgot password
    const forgotPassword = document.querySelector('.forgot-password');
    if (forgotPassword) {
        forgotPassword.addEventListener('click', function(e) {
            e.preventDefault();
            const email = prompt('Please enter your email address to reset your password:');
            if (email) {
                alert(`Password reset link has been sent to ${email} (simulated)`);
            }
        });
    }
    
    // Gender and interested in validation
    const signupForm = document.getElementById('signupForm');
    if (signupForm) {
        signupForm.addEventListener('submit', function(e) {
            const gender = document.getElementById('gender');
            const interestedIn = document.getElementById('interested-in');
            
            if (!gender.value || !interestedIn.value) {
                alert('Please select your gender and who you are interested in');
                e.preventDefault();
                return;
            }
            
            // In a real app, you would send this data to your server
            alert('Account created successfully! Redirecting to personality quiz...');
            window.location.href = 'profile.html'; // Change to quiz page when created
            e.preventDefault();
        });
    }
    
    // Simulate OTP verification
    if (window.location.search.includes('verify')) {
        setTimeout(() => {
            const otp = prompt('Simulating OTP verification. Enter any 6-digit code:');
            if (otp) {
                alert('Account verified successfully! Redirecting to your profile...');
                window.location.href = 'profile.html';
            }
        }, 1000);
    }
});