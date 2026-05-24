#run python toeatit.py to start the server, then open http://127.0.0.1:5002/login
import random
import socket
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'toeatit_secret_key'

# 1. User mock database
USERS = {"test@usyd.edu.au": "password123"}

# User profile and order history (email -> profile)
USER_PROFILES = {}

# Global CO2 savings statistics (each successful purchase +2.5kg)
TOTAL_CO2_SAVED = 0.0
CO2_PER_PURCHASE = 2.5


def get_user_profile(email):
    if email not in USER_PROFILES:
        USER_PROFILES[email] = {
            "has_allergies": False,
            "allergens": [],
            "other_allergen": "",
            "orders": [],
        }
    return USER_PROFILES[email]

# 2. Store real-time inventory and pickup locations
STORES_INVENTORY = {
    "Coles": {"count": 5, "img": "🛒", "pickup_location": "Coles Broadway"},
    "Woolworths": {"count": 5, "img": "🥦", "pickup_location": "Woolworths Town Hall"},
    "Aldi": {"count": 5, "img": "📐", "pickup_location": "Aldi Haymarket"},
    "Harris Farm": {"count": 5, "img": "🍎", "pickup_location": "Harris Farm Pyrmont"},
    "7-Eleven": {"count": 5, "img": "🏪", "pickup_location": "7-Eleven Central"},
}

USED_RECEIPT_CODES = set()
PICKUP_DEADLINE = "9:00 PM"


def generate_receipt_code():
    """Generate unique 6-digit pickup code, format #TEI-XXXX"""
    for _ in range(100):
        code = f"TEI-{random.randint(1000, 9999)}"
        if code not in USED_RECEIPT_CODES:
            USED_RECEIPT_CODES.add(code)
            return f"#{code}"
    raise RuntimeError("Unable to generate unique receipt code")

# 3. 🔥 Backend-driven onboarding Q&A data for the website
# Control frontend branch jumping through next_yes and next_no
QUIZ_DATA = {
    "q1": {
        "type": "choice",
        "title": "Have you ever used a similar anti-waste app?",
        "subtitle": "Like Too Good To Go, Olio, etc.",
        "next_yes": "q3",  # choose Yes jump to q3
        "next_no": "q2"    # choose No jump to q2
    },
    "q2": {
        "type": "choice",
        "title": "Would you like a quick introduction to TO EAT IT?",
        "subtitle": "",
        "next_yes": "q2_intro",
        "next_no": "q3"
    },
    "q2_intro": {
        "type": "intro",
        "title": "Welcome to TO EAT IT 🌱",
        "content": "We partner with top retailers in Sydney to rescue premium surplus food. Everything is sold as a <strong>Mystery Box for a flat rate of $5</strong>! You save money, stores reduce waste, and planet wins.",
        "next": "q3"
    },
    "q3": {
        "type": "choice",
        "title": "Do you have any food allergies?",
        "subtitle": "",
        "next_yes": "q4",
        "next_no": "enjoy" # choose No directly enter countdown
    },
    "q4": {
        "type": "checkbox",
        "title": "Select your allergen items:",
        "options": [
            {"id": "grains", "label": "Grains / Gluten"},
            {"id": "nuts", "label": "Tree Nuts"},
            {"id": "milk", "label": "Milk / Dairy"},
            {"id": "seafood", "label": "Seafood"},
            {"id": "eggs", "label": "Eggs"},
            {"id": "other", "label": "Other", "custom": True}
        ],
        "next": "enjoy"
    }
}

ALLERGEN_LABELS = {
    opt["id"]: opt["label"]
    for opt in QUIZ_DATA["q4"]["options"]
    if not opt.get("custom")
}


def format_allergen_display(profile):
    if not profile.get("has_allergies"):
        return []
    labels = []
    for aid in profile.get("allergens", []):
        if aid == "other":
            other = profile.get("other_allergen", "").strip()
            if other:
                labels.append(f"Other: {other}")
        elif aid in ALLERGEN_LABELS:
            labels.append(ALLERGEN_LABELS[aid])
    return labels

@app.route('/')
def index():
    # Only allow rendering the main website immediately after a successful login.
    # This forces any subsequent fresh visits to land on the login page
    # even if the browser still had a previous session cookie.
    if session.get('just_logged_in'):
        # consume the one-time flag and show the website
        session.pop('just_logged_in', None)
        return render_template('index.html')

    # Not a fresh login — clear any existing session user and force login page for the website
    session.pop('user', None)
    return redirect(url_for('login'))

@app.before_request
def clear_session_on_startup():
    """Clear session on website startup (for development only)"""
    # Keep placeholder — we handle forced-login via index/login logic.
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Always show the login page on GET so opening the website shows login.
    if request.method == 'POST':
        data = request.get_json()
        action = data.get('action')
        email = data.get('email')
        password = data.get('password')

        if action == 'login':
            if email in USERS and USERS[email] == password:
                # mark user and set one-time flag to allow entering the website
                session['user'] = email
                session['just_logged_in'] = True
                return jsonify({"status": "success", "message": "Login successful!"})
            return jsonify({"status": "error", "message": "Invalid email or password."})

        elif action == 'register':
            if email in USERS:
                return jsonify({"status": "error", "message": "Email already registered."})
            USERS[email] = password
            session['user'] = email
            session['just_logged_in'] = True
            return jsonify({"status": "success", "message": "Registration successful!"})

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('just_logged_in', None)
    return redirect(url_for('login'))

# API: Get backend-configured quiz data for the website
@app.route('/api/quiz-data', methods=['GET'])
def get_quiz_data():
    return jsonify(QUIZ_DATA)

# API: Get current store inventory for the website
@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    return jsonify({
        "inventory": STORES_INVENTORY,
        "total_co2_saved": TOTAL_CO2_SAVED,
    })

# API: Save allergen selection for the website
@app.route('/api/allergens', methods=['POST'])
def save_allergens():
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.get_json()
    profile = get_user_profile(session['user'])
    if 'has_allergies' in data:
        profile['has_allergies'] = bool(data['has_allergies'])
    else:
        profile['has_allergies'] = True
    profile['allergens'] = data.get('allergens', [])
    profile['other_allergen'] = (data.get('other_allergen') or '').strip()
    if not profile['has_allergies']:
        profile['allergens'] = []
        profile['other_allergen'] = ''
    return jsonify({"status": "success"})


# API: Get user profile for the website
@app.route('/api/profile', methods=['GET'])
def get_profile():
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    email = session['user']
    profile = get_user_profile(email)
    avatar_letter = email[0].upper() if email else '?'

    return jsonify({
        "email": email,
        "avatar_letter": avatar_letter,
        "has_allergies": profile['has_allergies'],
        "allergens": profile['allergens'],
        "other_allergen": profile['other_allergen'],
        "allergen_display": format_allergen_display(profile),
        "orders": list(reversed(profile['orders'])),
    })


# API: Buy mystery box from the website
@app.route('/api/buy', methods=['POST'])
def buy_box():
    global TOTAL_CO2_SAVED
    if 'user' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.get_json()
    store_name = data.get('store')

    if store_name in STORES_INVENTORY:
        if STORES_INVENTORY[store_name]['count'] > 0:
            store = STORES_INVENTORY[store_name]
            store['count'] -= 1
            receipt_code = generate_receipt_code()
            pickup_location = store.get('pickup_location', store_name)
            pickup_message = (
                f"Please collect from {pickup_location} before {PICKUP_DEADLINE}."
            )
            profile = get_user_profile(session['user'])
            profile['orders'].append({
                "store": store_name,
                "price": 5.00,
                "item": "Mystery Box",
                "receipt_code": receipt_code,
                "pickup_message": pickup_message,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
            TOTAL_CO2_SAVED += CO2_PER_PURCHASE
            return jsonify({
                "status": "success",
                "new_count": store['count'],
                "total_co2_saved": TOTAL_CO2_SAVED,
                "receipt_code": receipt_code,
                "pickup_message": pickup_message,
                "store": store_name,
            })
        return jsonify({"status": "error", "message": "Sold Out!"})
    return jsonify({"status": "error", "message": "Store not found"})

def pick_port(preferred=5000):
    """Port 5000 is often occupied by AirPlay on macOS, automatically try alternate ports for the website"""
    for port in (preferred, 5001, 5002, 8080):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    return preferred


if __name__ == '__main__':
    port = pick_port(5000)
    base_url = f'http://127.0.0.1:{port}'
    print('\n' + '=' * 56)
    print('  TO EAT IT service started')
    print(f'  Please open the login page in your browser: {base_url}/login')
    print(f'  Or visit the homepage:         {base_url}/')
    print('  Test account: test@usyd.edu.au')
    print('  Test password: password123')
    if port != 5000:
        print('  (Port 5000 is occupied, switched to port %d)' % port)
    print('=' * 56 + '\n')
    app.run(debug=True, host='127.0.0.1', port=port, use_reloader=False)