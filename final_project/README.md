# TO EAT IT

TO EAT IT is a Flask-based anti-food-waste website that helps users buy surplus grocery items in the form of a **Mystery Box**. The website combines a simple login flow, allergy preferences, live store inventory, pickup details, and sustainability tracking to create a playful but practical shopping experience.

## Features

- **User login and registration** with session-based authentication
- **Personal allergy profile** setup, including custom allergen notes
- **Backend-driven onboarding quiz** with branching questions
- **Live inventory tracking** for multiple Sydney stores
- **Mystery Box purchase flow** with receipt code generation
- **Pickup information** including store-specific pickup locations and deadline reminders
- **CO2 savings tracker** to show the environmental impact of each purchase
- **Order history** stored per user profile

## Tech Stack

- **Python 3**
- **Flask**
- **Jinja2 templates** for the frontend pages
- **JSON APIs** for website interactions
- **In-memory data storage** for users, inventory, and orders

## Project Structure

```text
final_project/
├── toeatit.py
├── templates/
│   ├── index.html
│   └── login.html
└── README.md
```

## Getting Started

### 1. Install Python dependencies

This project only needs Flask.

```bash
pip install flask
```

### 2. Run the website

Start the server from the project folder:

```bash
python toeatit.py
```

The website automatically picks an available local port and prints the login URL in the terminal.

### 3. Open the website

Go to the login page shown in the terminal, for example:

```text
http://127.0.0.1:5002/login
```

## Test Account

You can use the built-in demo account:

- **Email:** `test@usyd.edu.au`
- **Password:** `password123`

## Main Website Flow

1. Register or log in
2. Complete the onboarding questions
3. Set allergy preferences if needed
4. Browse available stores and inventory
5. Purchase a Mystery Box for a flat rate of $5
6. Receive a receipt code and pickup message
7. View your order history and CO2 savings impact

## API Endpoints

The Flask backend exposes the following endpoints:

- `GET /login` - show the login page
- `POST /login` - log in or register
- `GET /logout` - log out and return to login
- `GET /api/quiz-data` - fetch onboarding quiz data
- `GET /api/inventory` - fetch store inventory and total CO2 saved
- `POST /api/allergens` - save allergy preferences
- `GET /api/profile` - fetch the current user profile
- `POST /api/buy` - buy a Mystery Box from a store

## Notes

- User accounts, inventory, and order history are stored **in memory**, so data resets when the server restarts.
- The website is designed for local development and demonstration purposes.
- Port `5000` is avoided automatically on macOS if it is already in use.

## Future Improvements

- Add a real database for persistent storage
- Improve inventory management with stock updates from a backend service
- Add search, filtering, and order management features
- Expand the UI with more detailed sustainability analytics

## License

This project was created for coursework and demo purposes.
