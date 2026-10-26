
import os
import re
import sqlite3
import secrets
from functools import wraps
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, g, jsonify
)
from werkzeug.security import (
    generate_password_hash, check_password_hash
)
from predict_model import predict_performance
# =====================================================
# PROJECT CONFIGURATION
# =====================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "mindmap.db"

app = Flask(__name__, static_folder="static", static_url_path="/static")

app.secret_key = os.environ.get("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError(
        "Set the FLASK_SECRET_KEY environment variable first."
    )

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",
    MAX_CONTENT_LENGTH=2 * 1024 * 1024
)

# =====================================================
# QUIZ DATA
# =====================================================

QUIZZES = {
    "Mathematics": [
        {
            "id": "math_1",
            "topic": "Addition",
            "question": "What is 5 + 3?",
            "options": [
                {"id": "a", "text": "6"},
                {"id": "b", "text": "8"},
                {"id": "c", "text": "9"},
                {"id": "d", "text": "10"}
            ],
            "answer": "b"
        },
        {
            "id": "math_2",
            "topic": "Multiplication",
            "question": "What is 4 × 3?",
            "options": [
                {"id": "a", "text": "7"},
                {"id": "b", "text": "10"},
                {"id": "c", "text": "12"},
                {"id": "d", "text": "14"}
            ],
            "answer": "c"
        },
        {
            "id": "math_3",
            "topic": "Fractions",
            "question": "What is half of 10?",
            "options": [
                {"id": "a", "text": "2"},
                {"id": "b", "text": "5"},
                {"id": "c", "text": "8"},
                {"id": "d", "text": "10"}
            ],
            "answer": "b"
        }
    ],

    "Science": [
        {
            "id": "science_1",
            "topic": "Solar System",
            "question": "Which planet is known as the Red Planet?",
            "options": [
                {"id": "a", "text": "Earth"},
                {"id": "b", "text": "Mars"},
                {"id": "c", "text": "Venus"},
                {"id": "d", "text": "Jupiter"}
            ],
            "answer": "b"
        },
        {
            "id": "science_2",
            "topic": "Plants",
            "question": "Which part of a plant absorbs water?",
            "options": [
                {"id": "a", "text": "Flower"},
                {"id": "b", "text": "Leaf"},
                {"id": "c", "text": "Root"},
                {"id": "d", "text": "Fruit"}
            ],
            "answer": "c"
        },
        {
            "id": "science_3",
            "topic": "Human Body",
            "question": "Which organ pumps blood?",
            "options": [
                {"id": "a", "text": "Lungs"},
                {"id": "b", "text": "Heart"},
                {"id": "c", "text": "Brain"},
                {"id": "d", "text": "Stomach"}
            ],
            "answer": "b"
        }
    ],

    "English": [
        {
            "id": "english_1",
            "topic": "Vocabulary",
            "question": "What is the opposite of happy?",
            "options": [
                {"id": "a", "text": "Joyful"},
                {"id": "b", "text": "Sad"},
                {"id": "c", "text": "Excited"},
                {"id": "d", "text": "Cheerful"}
            ],
            "answer": "b"
        },
        {
            "id": "english_2",
            "topic": "Grammar",
            "question": "Choose the correct sentence.",
            "options": [
                {"id": "a", "text": "She go to school."},
                {"id": "b", "text": "She goes to school."},
                {"id": "c", "text": "She going school."},
                {"id": "d", "text": "She gone to school."}
            ],
            "answer": "b"
        },
        {
            "id": "english_3",
            "topic": "Vocabulary",
            "question": "Which word means big?",
            "options": [
                {"id": "a", "text": "Tiny"},
                {"id": "b", "text": "Small"},
                {"id": "c", "text": "Large"},
                {"id": "d", "text": "Short"}
            ],
            "answer": "c"
        }
    ]
}

# =====================================================
# DATABASE
# =====================================================

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("PRAGMA foreign_keys = ON")

        db.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                score INTEGER NOT NULL,
                total_questions INTEGER NOT NULL,
                percentage REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id)
                    REFERENCES students(id) ON DELETE CASCADE
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS quiz_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id INTEGER NOT NULL,
                question_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                selected_option TEXT NOT NULL,
                correct_option TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                FOREIGN KEY (attempt_id)
                    REFERENCES quiz_attempts(id) ON DELETE CASCADE
            )
        """)

        db.commit()


# =====================================================
# CSRF TOKEN
# =====================================================

def get_csrf_token():
    # Create the token if the session doesn't have one.
    if not session.get("csrf_token"):
        session["csrf_token"] = secrets.token_hex(32)

    return session["csrf_token"]


def validate_csrf():
    token = session.get("csrf_token")
    supplied = request.headers.get("X-CSRF-Token", "")

    return (
        isinstance(token, str)
        and isinstance(supplied, str)
        and bool(supplied)
        and secrets.compare_digest(token, supplied)
    )


# =====================================================
# AUTHENTICATION
# =====================================================

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "student_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Login required."}), 401

            flash("Please log in first.")
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


def get_current_student():
    student_id = session.get("student_id")

    if student_id is None:
        return None

    return get_db().execute("""
        SELECT id, name, email, created_at
        FROM students
        WHERE id = ?
    """, (student_id,)).fetchone()


# =====================================================
# HOME
# =====================================================

@app.route("/")
def home():
    if session.get("student_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# =====================================================
# REGISTRATION
# =====================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or len(name) > 100:
            flash("Enter a valid name.")
            return render_template("register.html")

        if (
            not email or len(email) > 254
            or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
        ):
            flash("Enter a valid email address.")
            return render_template("register.html")

        if len(password) < 8 or len(password) > 128:
            flash("Password must be between 8 and 128 characters.")
            return render_template("register.html")

        password_hash = generate_password_hash(password)

        try:
            db = get_db()
            db.execute("""
                INSERT INTO students (name, email, password_hash)
                VALUES (?, ?, ?)
            """, (name, email, password_hash))
            db.commit()

        except sqlite3.IntegrityError:
            flash("This email is already registered.")
            return render_template("register.html")

        flash("Account created! Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


# =====================================================
# LOGIN
# =====================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        student = get_db().execute("""
            SELECT id, password_hash
            FROM students
            WHERE email = ?
        """, (email,)).fetchone()

        if student and check_password_hash(
            student["password_hash"], password
        ):
            session.clear()
            session["student_id"] = student["id"]
            session["csrf_token"] = secrets.token_hex(32)

            return redirect(url_for("dashboard"))

        flash("Incorrect email or password.")

    return render_template("login.html")


# =====================================================
# DASHBOARD
# =====================================================

@app.route("/dashboard")
@login_required
def dashboard():
    student = get_current_student()

    if student is None:
        session.clear()
        flash("Please log in again.")
        return redirect(url_for("login"))

    # Ensure CSRF token exists for this logged-in session.
    get_csrf_token()

    return render_template("index.html", student=student)


# =====================================================
# STUDENT PROFILE API
# =====================================================

@app.route("/api/student", methods=["GET"])
@login_required
def student_profile():
    student = get_current_student()

    if student is None:
        session.clear()
        return jsonify({"error": "Please log in again."}), 401

    return jsonify({
        "id": student["id"],
        "name": student["name"],
        "email": student["email"],
        "created_at": student["created_at"]
    })


# =====================================================
# GET QUIZ QUESTIONS
# =====================================================

@app.route("/api/quiz/questions", methods=["GET"])
@login_required
def get_quiz_questions():
    subject = request.args.get("subject", "").strip()
    questions = QUIZZES.get(subject)

    if questions is None:
        return jsonify({"error": "Invalid subject."}), 400

    public_questions = []

    for q in questions:
        public_questions.append({
            "id": q["id"],
            "topic": q["topic"],
            "question": q["question"],
            "options": q["options"]
        })

    # FIX: Never directly access a possibly missing session key.
    return jsonify({
        "subject": subject,
        "csrf_token": get_csrf_token(),
        "questions": public_questions
    })


# =====================================================
# SUBMIT QUIZ
# =====================================================

@app.route("/api/quiz/submit", methods=["POST"])
@login_required
def submit_quiz():
    if not validate_csrf():
        return jsonify({
            "error": "Invalid security token. Refresh the page."
        }), 403

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid request."}), 400

    subject = data.get("subject")
    answers = data.get("answers")

    if subject not in QUIZZES:
        return jsonify({"error": "Invalid subject."}), 400

    questions = QUIZZES[subject]

    if not isinstance(answers, list) or len(answers) != len(questions):
        return jsonify({
            "error": "Please answer every question."
        }), 400

    answer_map = {}

    for item in answers:
        if not isinstance(item, dict):
            return jsonify({"error": "Invalid answer format."}), 400

        question_id = item.get("question_id")
        option_id = item.get("option_id")

        if question_id in answer_map:
            return jsonify({
                "error": "Duplicate question answer."
            }), 400

        answer_map[question_id] = option_id

    expected_ids = {q["id"] for q in questions}

    if set(answer_map.keys()) != expected_ids:
        return jsonify({
            "error": "Quiz questions do not match."
        }), 400

    score = 0
    response_records = []

    for q in questions:
        selected = answer_map[q["id"]]
        valid_options = {o["id"] for o in q["options"]}

        if selected not in valid_options:
            return jsonify({
                "error": "Invalid option selected."
            }), 400

        correct = selected == q["answer"]

        if correct:
            score += 1

        response_records.append((
            q["id"],
            q["topic"],
            selected,
            q["answer"],
            int(correct)
        ))

    total = len(questions)
    percentage = round((score / total) * 100, 2)

    db = get_db()
    student_id = session["student_id"]

    try:
        cursor = db.execute("""
            INSERT INTO quiz_attempts
            (student_id, subject, score, total_questions, percentage)
            VALUES (?, ?, ?, ?, ?)
        """, (student_id, subject, score, total, percentage))

        attempt_id = cursor.lastrowid

        db.executemany("""
            INSERT INTO quiz_responses
            (attempt_id, question_id, topic, selected_option,
             correct_option, is_correct)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            (attempt_id, *record)
            for record in response_records
        ])

        db.commit()

    except sqlite3.Error:
        db.rollback()
        app.logger.exception("Failed to save quiz attempt.")
        return jsonify({
            "error": "Could not save your quiz result."
        }), 500

    return jsonify({
        "message": "Quiz result saved successfully.",
        "attempt_id": attempt_id,
        "subject": subject,
        "score": score,
        "total": total,
        "percentage": percentage
    })


# =====================================================
# QUIZ HISTORY
# =====================================================

@app.route("/api/quiz/history", methods=["GET"])
@login_required
def quiz_history():
    rows = get_db().execute("""
        SELECT id, subject, score, total_questions,
               percentage, created_at
        FROM quiz_attempts
        WHERE student_id = ?
        ORDER BY id DESC
        LIMIT 50
    """, (session["student_id"],)).fetchall()

    return jsonify({
        "attempts": [dict(row) for row in rows]
    })


# =====================================================
# QUIZ ATTEMPT REVIEW
# =====================================================

@app.route("/api/quiz/attempt/<int:attempt_id>", methods=["GET"])
@login_required
def quiz_attempt_detail(attempt_id):
    db = get_db()
    student_id = session["student_id"]

    attempt = db.execute("""
        SELECT id, subject, score, total_questions,
               percentage, created_at
        FROM quiz_attempts
        WHERE id = ? AND student_id = ?
    """, (attempt_id, student_id)).fetchone()

    if attempt is None:
        return jsonify({
            "error": "Quiz attempt not found."
        }), 404

    responses = db.execute("""
        SELECT question_id, topic, selected_option,
               correct_option, is_correct
        FROM quiz_responses
        WHERE attempt_id = ?
        ORDER BY id
    """, (attempt_id,)).fetchall()

    return jsonify({
        "attempt": dict(attempt),
        "responses": [dict(row) for row in responses]
    })


# =====================================================
# LOGOUT
# =====================================================

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have logged out successfully.")
    return redirect(url_for("login"))


# =====================================================
# LEARNING GAP DETECTION & REVISION RECOMMENDATIONS
# =====================================================

@app.route("/api/learning-insights", methods=["GET"])
@login_required
def learning_insights():

    student_id = session["student_id"]
    db = get_db()

    # Analyze this student's saved quiz responses
    rows = db.execute("""
        SELECT
            qr.topic,
            COUNT(*) AS total_questions,
            SUM(qr.is_correct) AS correct_answers
        FROM quiz_responses qr
        JOIN quiz_attempts qa
            ON qr.attempt_id = qa.id
        WHERE qa.student_id = ?
        GROUP BY qr.topic
        ORDER BY qr.topic
    """, (student_id,)).fetchall()

    topics = []
    strong_topics = []
    revision_topics = []

    for row in rows:
        total = row["total_questions"]
        correct = row["correct_answers"] or 0

        accuracy = round((correct / total) * 100, 2)

        if accuracy < 60:
            status = "Needs Revision"
            recommendation = (
                f"Revise {row['topic']} and attempt "
                "more practice questions."
            )
            revision_topics.append(row["topic"])

        elif accuracy >= 80:
            status = "Strong"
            recommendation = (
                f"Keep revising {row['topic']} "
                "occasionally."
            )
            strong_topics.append(row["topic"])

        else:
            status = "Practice"
            recommendation = (
                f"Practice more questions on {row['topic']}."
            )

        topics.append({
            "topic": row["topic"],
            "total_questions": total,
            "correct_answers": correct,
            "accuracy": accuracy,
            "status": status,
            "recommendation": recommendation
        })

    # Put topics with the lowest accuracy first
    topics.sort(key=lambda item: item["accuracy"])

    return jsonify({
        "success": True,
        "topics": topics,
        "strong_topics": strong_topics,
        "revision_topics": revision_topics,
        "next_step": (
            f"Start revising {topics[0]['topic']}."
            if topics else
            "Attempt a quiz to generate learning insights."
        )
    })


# =====================================================
# ML PERFORMANCE PREDICTION
# =====================================================

@app.route("/api/ml-prediction", methods=["POST"])
@login_required
def ml_prediction():

    try:
        if not validate_csrf():
            return jsonify({
                "error": "Invalid CSRF token"
            }), 400

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({
                "error": "Invalid request."
            }), 400

        required_features = [
            "raisedhands",
            "VisITedResources",
            "AnnouncementsView",
            "Discussion"
        ]

        student_data = {}

        for feature in required_features:
            value = data.get(feature)

            if value is None or isinstance(value, bool):
                return jsonify({
                    "error": f"Invalid or missing feature: {feature}"
                }), 400

            try:
                number = float(value)
            except (TypeError, ValueError):
                return jsonify({
                    "error": f"Invalid value: {feature}"
                }), 400

            if not number.is_integer() or not 0 <= number <= 100:
                return jsonify({
                    "error": f"{feature} must be an integer from 0 to 100"
                }), 400

            student_data[feature] = int(number)

        prediction = predict_performance(student_data)

        return jsonify({
            "success": True,
            "prediction": prediction
        }), 200

    except Exception:
        app.logger.exception("ML prediction failed")
        return jsonify({
            "error": "Prediction failed. Check the Flask terminal."
        }), 500


# =====================================================
# START APPLICATION
# =====================================================

with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)
