# Run: python toeatit.py
# Open the website at http://127.0.0.1:5002/login

import json
import random
import socket
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "toeatit_secret_key"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
USERS_FILE = DATA_DIR / "users.json"
PROFILES_FILE = DATA_DIR / "profiles.json"
INVENTORY_FILE = DATA_DIR / "inventory.json"
ORDERS_FILE = DATA_DIR / "orders.json"
CO2_FILE = DATA_DIR / "co2.json"

TEST_EMAIL = "test@usyd.edu.au"
TEST_PASSWORD = "password123"
MYSTERY_BOX_PRICE = 5.00
CO2_PER_PURCHASE = 2.5
PICKUP_DEADLINE = "9:00 PM"
USED_RECEIPT_CODES = set()

QUIZ_DATA = {
    "q1": {
        "type": "choice",
        "title": "Have you ever used a similar anti-waste website?",
        "subtitle": "Like Too Good To Go, Olio, etc.",
        "next_yes": "q3",
        "next_no": "q2",
    },
    "q2": {
        "type": "choice",
        "title": "Would you like a quick introduction to TO EAT IT?",
        "subtitle": "",
        "next_yes": "q2_intro",
        "next_no": "q3",
    },
    "q2_intro": {
        "type": "intro",
        "title": "Welcome to TO EAT IT 🌱",
        "content": (
            "We partner with top retailers in Sydney to rescue premium surplus food. "
            "Everything is sold as a <strong>Mystery Box for a flat rate of $5</strong>! "
            "You save money, stores reduce waste, and the planet wins."
        ),
        "next": "q3",
    },
    "q3": {
        "type": "choice",
        "title": "Do you have any food allergies?",
        "subtitle": "",
        "next_yes": "q4",
        "next_no": "enjoy",
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
            {"id": "other", "label": "Other", "custom": True},
        ],
        "next": "enjoy",
    },
}

ALLERGEN_LABELS = {
    opt["id"]: opt["label"] for opt in QUIZ_DATA["q4"]["options"] if not opt.get("custom")
}


@dataclass
class Order:
    store: str
    price: float
    item: str
    receipt_code: str
    pickup_message: str
    time: str


class UserProfile:
    def __init__(self, email, has_allergies=False, allergens=None, other_allergen="", orders=None):
        self.email = email
        self.has_allergies = has_allergies
        self.allergens = allergens or []
        self.other_allergen = other_allergen
        self.orders = orders or []

    def to_dict(self):
        return {
            "email": self.email,
            "has_allergies": self.has_allergies,
            "allergens": self.allergens,
            "other_allergen": self.other_allergen,
            "orders": self.orders,
        }

    @classmethod
    def from_dict(cls, email, data):
        return cls(
            email=email,
            has_allergies=data.get("has_allergies", False),
            allergens=data.get("allergens", []),
            other_allergen=data.get("other_allergen", ""),
            orders=data.get("orders", []),
        )

    def allergen_display(self):
        if not self.has_allergies:
            return []
        labels = []
        for allergen_id in self.allergens:
            if allergen_id == "other":
                if self.other_allergen.strip():
                    labels.append(f"Other: {self.other_allergen.strip()}")
            elif allergen_id in ALLERGEN_LABELS:
                labels.append(ALLERGEN_LABELS[allergen_id])
        return labels


class Store:
    def __init__(self, name, count, img, pickup_location):
        self.name = name
        self.count = count
        self.img = img
        self.pickup_location = pickup_location

    def to_dict(self):
        return {
            "count": self.count,
            "img": self.img,
            "pickup_location": self.pickup_location,
        }

    @classmethod
    def from_dict(cls, name, data):
        return cls(name, data.get("count", 0), data.get("img", ""), data.get("pickup_location", name))

    def buy_one(self):
        if self.count <= 0:
            return False
        self.count -= 1
        return True

    def is_sold_out(self):
        return self.count <= 0


class DataStore:
    def __init__(self):
        DATA_DIR.mkdir(exist_ok=True)
        self.users = self._load_json(USERS_FILE, {TEST_EMAIL: TEST_PASSWORD})
        self.profiles = self._load_json(PROFILES_FILE, {})
        self.inventory = self._load_json(INVENTORY_FILE, self._default_inventory())
        self.orders = self._load_json(ORDERS_FILE, {})
        self.co2_saved = float(self._load_json(CO2_FILE, {"total_co2_saved": 0.0}).get("total_co2_saved", 0.0))
        self._migrate_receipt_codes()

    def _default_inventory(self):
        return {
            "Coles": {"count": 5, "img": "🛒", "pickup_location": "Coles Broadway"},
            "Woolworths": {"count": 5, "img": "🥦", "pickup_location": "Woolworths Town Hall"},
            "Aldi": {"count": 5, "img": "📐", "pickup_location": "Aldi Haymarket"},
            "Harris Farm": {"count": 5, "img": "🍎", "pickup_location": "Harris Farm Pyrmont"},
            "7-Eleven": {"count": 5, "img": "🏪", "pickup_location": "7-Eleven Central"},
        }

    def _load_json(self, path, default):
        if not path.exists():
            self._save_json(path, default)
            return default
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            self._save_json(path, default)
            return default

    def _save_json(self, path, payload):
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def save_all(self):
        self._save_json(USERS_FILE, self.users)
        self._save_json(PROFILES_FILE, self.profiles)
        self._save_json(INVENTORY_FILE, self.inventory)
        self._save_json(ORDERS_FILE, self.orders)
        self._save_json(CO2_FILE, {"total_co2_saved": self.co2_saved})

    def _migrate_receipt_codes(self):
        for email_orders in self.orders.values():
            for order in email_orders:
                code = order.get("receipt_code")
                if code:
                    USED_RECEIPT_CODES.add(code)

    def get_profile(self, email):
        if email not in self.profiles:
            self.profiles[email] = UserProfile(email).to_dict()
            self.orders.setdefault(email, [])
            self.save_all()
        return UserProfile.from_dict(email, self.profiles[email])

    def set_profile(self, profile):
        self.profiles[profile.email] = profile.to_dict()
        self.orders[profile.email] = profile.orders
        self.save_all()

    def get_store(self, store_name):
        if store_name not in self.inventory:
            return None
        return Store.from_dict(store_name, self.inventory[store_name])

    def set_store(self, store):
        self.inventory[store.name] = store.to_dict()
        self.save_all()

    def record_order(self, email, order):
        self.orders.setdefault(email, [])
        self.orders[email].append(asdict(order))
        profile = self.get_profile(email)
        profile.orders = self.orders[email]
        self.set_profile(profile)

    def next_receipt_code(self):
        for _ in range(100):
            code = f"TEI-{random.randint(1000, 9999)}"
            full_code = f"#{code}"
            if full_code not in USED_RECEIPT_CODES:
                USED_RECEIPT_CODES.add(full_code)
                return full_code
        raise RuntimeError("Unable to generate unique receipt code")


store = DataStore()


def pick_port(preferred=5000):
    """Port 5000 is often occupied on macOS, so try alternates for the website."""
    for port in (preferred, 5001, 5002, 8080):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return preferred


@app.route("/")
def index():
    if session.get("just_logged_in"):
        session.pop("just_logged_in", None)
        return render_template("index.html")
    session.pop("user", None)
    return redirect(url_for("login"))


@app.before_request
def clear_session_on_startup():
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.get_json() or {}
        action = data.get("action")
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        if action == "login":
            if email in store.users and store.users[email] == password:
                session["user"] = email
                session["just_logged_in"] = True
                return jsonify({"status": "success", "message": "Login successful!"})
            return jsonify({"status": "error", "message": "Invalid email or password."})

        if action == "register":
            if email in store.users:
                return jsonify({"status": "error", "message": "Email already registered."})
            store.users[email] = password
            if email not in store.profiles:
                store.profiles[email] = UserProfile(email).to_dict()
                store.orders[email] = []
                store.save_all()
            session["user"] = email
            session["just_logged_in"] = True
            return jsonify({"status": "success", "message": "Registration successful!"})

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("just_logged_in", None)
    return redirect(url_for("login"))


@app.route("/api/quiz-data", methods=["GET"])
def get_quiz_data():
    return jsonify(QUIZ_DATA)


@app.route("/api/inventory", methods=["GET"])
def get_inventory():
    return jsonify({
        "inventory": store.inventory,
        "total_co2_saved": store.co2_saved,
    })


@app.route("/api/allergens", methods=["POST"])
def save_allergens():
    if "user" not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    profile = store.get_profile(session["user"])

    has_allergies = bool(data.get("has_allergies", True))
    profile.has_allergies = has_allergies
    profile.allergens = data.get("allergens", []) if has_allergies else []
    profile.other_allergen = (data.get("other_allergen") or "").strip() if has_allergies else ""

    store.set_profile(profile)
    return jsonify({"status": "success"})


@app.route("/api/profile", methods=["GET"])
def get_profile():
    if "user" not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    email = session["user"]
    profile = store.get_profile(email)
    orders = list(reversed(profile.orders))

    return jsonify({
        "email": email,
        "avatar_letter": email[0].upper() if email else "?",
        "has_allergies": profile.has_allergies,
        "allergens": profile.allergens,
        "other_allergen": profile.other_allergen,
        "allergen_display": profile.allergen_display(),
        "orders": orders,
    })


@app.route("/api/buy", methods=["POST"])
def buy_box():
    if "user" not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    store_name = data.get("store")
    store_obj = store.get_store(store_name)

    if not store_obj:
        return jsonify({"status": "error", "message": "Store not found"})
    if store_obj.is_sold_out():
        return jsonify({"status": "error", "message": "Sold Out!"})

    store_obj.buy_one()
    store.set_store(store_obj)

    receipt_code = store.next_receipt_code()
    pickup_message = f"Please collect from {store_obj.pickup_location} before {PICKUP_DEADLINE}."
    order = Order(
        store=store_name,
        price=MYSTERY_BOX_PRICE,
        item="Mystery Box",
        receipt_code=receipt_code,
        pickup_message=pickup_message,
        time=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    store.record_order(session["user"], order)
    store.co2_saved += CO2_PER_PURCHASE
    store.save_all()

    return jsonify({
        "status": "success",
        "new_count": store_obj.count,
        "total_co2_saved": store.co2_saved,
        "receipt_code": receipt_code,
        "pickup_message": pickup_message,
        "store": store_name,
    })


if __name__ == "__main__":
    port = pick_port(5000)
    base_url = f"http://127.0.0.1:{port}"
    print("\n" + "=" * 56)
    print("  TO EAT IT website started")
    print(f"  Please open the login page in your browser: {base_url}/login")
    print(f"  Or visit the homepage:         {base_url}/")
    print(f"  Test account: {TEST_EMAIL}")
    print(f"  Test password: {TEST_PASSWORD}")
    if port != 5000:
        print(f"  (Port 5000 is occupied, switched to port {port})")
    print("=" * 56 + "\n")
    app.run(debug=True, host="127.0.0.1", port=port, use_reloader=False)
