from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return "Login Page (Placeholder)"

@app.route('/explore')
def explore():
    return "Explore Page (Placeholder)"

@app.route('/chat')
def chat():
    return "Chat Page (Placeholder)"

@app.route('/profile')
def profile():
    return "Profile Page (Placeholder)"

@app.route('/questions')
def questions():
    return "Questions Page (Placeholder)"

if __name__ == '__main__':
    app.run(debug=True)