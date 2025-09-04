from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask import flash, redirect, url_for, session, request, render_template


app = Flask(__name__)
app.secret_key = "secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///bank.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# --------------------
# Database Models
# --------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    is_admin = db.Column(db.Boolean, default=False)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    type = db.Column(db.String(50))
    amount = db.Column(db.Float)
    balance = db.Column(db.Float)
    date = db.Column(db.DateTime, default=datetime.utcnow)


# --------------------
# Routes
# --------------------
@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        # First user becomes Admin
        is_first_user = User.query.count() == 0
        new_user = User(username=username, password=password, balance=0.0, is_admin=is_first_user)

        db.session.add(new_user)
        db.session.commit()
        flash("Signup successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["is_admin"] = user.is_admin
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "danger")

    return render_template("login.html")

@app.route("/forgot_password")
def forgot_password():
    return "Forgot Password Page - Coming Soon!"


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    return render_template("dashboard.html", user=user)


@app.route("/deposit", methods=["GET", "POST"])
def deposit():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if request.method == "POST":
        amount = float(request.form["amount"])
        if amount > 0:
            user.balance += amount
            txn = Transaction(user_id=user.id, type="Deposit", amount=amount, balance=user.balance)
            db.session.add(txn)
            db.session.commit()
            flash(f"Successfully deposited ₹{amount}!", "success")
            return redirect(url_for("dashboard"))

    return render_template("deposit.html", user=user)

@app.route("/withdraw", methods=["GET", "POST"])
def withdraw():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    if request.method == "POST":
        amount = float(request.form["amount"])
        pin = request.form["pin"]  # PIN from form

        # Step 1: Verify PIN (PIN = login password)
        if not check_password_hash(user.password, pin):
            flash("❌ Incorrect transaction PIN!", "danger")
            return render_template("withdraw.html", user=user)  # <-- Stay on same page to show error

        # Step 2: Check balance
        if user.balance >= amount and amount > 0:
            user.balance -= amount

            # Record transaction
            txn = Transaction(
                user_id=user.id,
                type="Withdraw",
                amount=amount,
                balance=user.balance
            )
            db.session.add(txn)
            db.session.commit()

            flash(f"✅ Withdrew ₹{amount:.2f} successfully!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("⚠️ Insufficient funds or invalid amount!", "warning")
            return render_template("withdraw.html", user=user)  # Stay here for error

    return render_template("withdraw.html", user=user)



@app.route("/transfer", methods=["GET", "POST"])
def transfer():
    if "user_id" not in session:
        flash("Please log in to continue.", "warning")
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    if request.method == "POST":
        to_username = request.form.get("to_username").strip()
        amount = request.form.get("amount")

        print(f"\n[DEBUG] Transfer attempt: From={user.username}, To={to_username}, Amount={amount}")

        # Validate amount
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            print("[DEBUG] Invalid amount entered")
            flash("Invalid amount entered.", "danger")
            return redirect(url_for("transfer"))

        # Check recipient
        recipient = User.query.filter_by(username=to_username).first()
        print(f"[DEBUG] Recipient found: {recipient.username if recipient else 'None'}")

        if not recipient:
            flash("Recipient not found!", "danger")
            return redirect(url_for("transfer"))

        # Check sender balance
        print(f"[DEBUG] Sender balance: {user.balance}")
        if user.balance < amount:
            print("[DEBUG] Insufficient balance")
            flash("Insufficient balance!", "danger")
            return redirect(url_for("transfer"))

        # Perform transfer
        user.balance -= amount
        recipient.balance += amount
        print(f"[DEBUG] Transfer complete: New Sender Balance={user.balance}, New Recipient Balance={recipient.balance}")

        # Record transactions
        txn1 = Transaction(
            user_id=user.id,
            type="Transfer Sent",
            amount=amount,
            balance=user.balance,
            date=datetime.utcnow()
        )
        txn2 = Transaction(
            user_id=recipient.id,
            type="Transfer Received",
            amount=amount,
            balance=recipient.balance,
            date=datetime.utcnow()
        )

        db.session.add_all([txn1, txn2])
        db.session.commit()
        print("[DEBUG] Transaction committed to database")

        flash(f"Transferred ₹{amount:.2f} to {to_username}", "success")
        return redirect(url_for("dashboard"))

    return render_template("transfer.html", user=user)


@app.route("/transactions")
def transactions():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    txns = Transaction.query.filter_by(user_id=user.id).all()
    return render_template("transactions.html", user=user, transactions=txns)


# --------------------
# Initialize DB
# --------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
app.run(host="0.0.0.0", port=3000, debug=True)

