from flask import (Flask, render_template, request, jsonify, redirect, url_for, session, flash)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, login_required, logout_user, current_user)
from werkzeug.security import (generate_password_hash, check_password_hash)
from datetime import datetime, timedelta
from sqlalchemy import func
import random
import hashlib
import smtplib
import os
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "fallback-dev-key-change-this")

# New database name
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///jobpilot.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ============================================================
# EMAIL CONFIGURATION
# ============================================================

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_USE_TLS"] = True

# ============================================================
# FLASK LOGIN
# ============================================================

login_manager = LoginManager(app)

login_manager.login_view = "login"

login_manager.login_message = None


# ============================================================
# DATABASE MODELS
# ============================================================

class User(UserMixin, db.Model):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )

    jobs = db.relationship(
        "Job",
        backref="user",
        cascade="all, delete-orphan"
    )


class Job(db.Model):

    __tablename__ = "jobs"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    company = db.Column(
        db.String(120),
        nullable=False
    )

    title = db.Column(
        db.String(150),
        nullable=False
    )

    location = db.Column(
        db.String(120)
    )

    job_type = db.Column(
        db.String(50)
    )

    applied_date = db.Column(
        db.Date,
        nullable=False
    )

    job_url = db.Column(
        db.String(500)
    )

    salary = db.Column(
        db.String(100)
    )

    status = db.Column(
        db.String(50),
        default="Applied",
        nullable=False
    )

    notes = db.Column(
        db.Text
    )

    interviews = db.relationship(
        "Interview",
        backref="job",
        cascade="all, delete-orphan"
    )


class Interview(db.Model):

    __tablename__ = "interviews"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    job_id = db.Column(
        db.Integer,
        db.ForeignKey("jobs.id"),
        nullable=False
    )

    interview_date = db.Column(
        db.DateTime,
        nullable=False
    )

    round = db.Column(
        db.String(100)
    )

    interview_type = db.Column(
        db.String(50)
    )

    status = db.Column(
        db.String(50),
        default="Scheduled",
        nullable=False
    )

    feedback = db.Column(
        db.Text
    )


# ============================================================
# CREATE DATABASE TABLES
# ============================================================

with app.app_context():
    db.create_all()


# ============================================================
# LOGIN USER LOADER
# ============================================================

@login_manager.user_loader
def load_user(user_id):

    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None


# ============================================================
# SEND OTP EMAIL
# ============================================================

def send_otp_email(receiver_email, otp):

    msg = EmailMessage()

    msg["Subject"] = "JobPilot - Password Reset OTP"
    msg["From"] = app.config["MAIL_USERNAME"]
    msg["To"] = receiver_email

    msg.set_content(
        f"""Hello,

We received a request to reset your JobPilot password.

Your OTP is:

{otp}

This OTP is valid for 5 minutes.

If you did not request a password reset, you can safely ignore this email.

Regards,
JobPilot Team
"""
    )

    try:
        with smtplib.SMTP(
            app.config["MAIL_SERVER"],
            app.config["MAIL_PORT"]
        ) as server:

            server.ehlo()
            server.starttls()
            server.ehlo()

            server.login(
                app.config["MAIL_USERNAME"],
                app.config["MAIL_PASSWORD"]
            )

            server.send_message(msg)

        print("OTP email sent successfully.")

    except Exception as e:
        print("SMTP ERROR:", repr(e))
        raise

# ============================================================
# GENERATE OTP
# ============================================================

def generate_otp():
    return str(random.randint(100000, 999999))

# ============================================================
# HASH OTP
# ============================================================

def hash_otp(otp):
    return hashlib.sha256(
        otp.encode("utf-8")
    ).hexdigest()


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not email or not password:

            return render_template(
                "login.html",
                error="Please enter email and password."
            )

        user = User.query.filter_by(
            email=email
        ).first()

        if user and check_password_hash(
            user.password,
            password
        ):

            login_user(user)

            return redirect(
                url_for("dashboard")
            )

        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    return render_template("login.html")

# ============================================================
# CHECK USERNAME AVAILABILITY (AJAX)
# ============================================================

@app.route("/api/check-username", methods=["GET"])
def check_username():

    username = request.args.get("username", "").strip()

    if not username:
        return jsonify({"available": False, "message": "Username cannot be empty."})

    if len(username) < 3:
        return jsonify({"available": False, "message": "Username must be at least 3 characters."})

    existing = User.query.filter_by(username=username).first()

    if existing:
        return jsonify({"available": False, "message": "Username is already taken."})

    return jsonify({"available": True, "message": "Username is available."})


# ============================================================
# CHECK EMAIL AVAILABILITY (AJAX)
# ============================================================

@app.route("/api/check-email", methods=["GET"])
def check_email():

    email = request.args.get("email", "").strip().lower()

    if not email:
        return jsonify({"available": False, "message": "Email cannot be empty."})

    existing = User.query.filter_by(email=email).first()

    if existing:
        return jsonify({"available": False, "message": "Email is already registered."})

    return jsonify({"available": True, "message": "Email is available."})

# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        # Validation
        if not username or not email or not password:

            return render_template(
                "register.html",
                error="All fields are required."
            )

        if password != confirm_password:

            return render_template(
                "register.html",
                error="Passwords do not match."
            )

        if len(password) < 6:

            return render_template(
                "register.html",
                error="Password must contain at least 6 characters."
            )

        # Check existing user
        existing_user = User.query.filter(
            (User.username == username) |
            (User.email == email)
        ).first()

        if existing_user:

            return render_template(
                "register.html",
                error="Username or email already exists."
            )

        # Create user
        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password)
        )

        db.session.add(user)
        db.session.commit()

        # Automatically login
        login_user(user)

        return redirect(
            url_for("dashboard")
        )

    return render_template("register.html")

# ============================================================
# FORGOT PASSWORD
# ============================================================

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        if not email:
            return render_template(
                "forgot_password.html",
                error="Please enter your email address."
            )

        user = User.query.filter_by(
            email=email
        ).first()

        if not user:
            return render_template(
                "forgot_password.html",
                error="If an account exists with this email, an OTP has been sent."
            )

        otp = generate_otp()

        session["reset_email"] = email
        session["reset_user_id"] = user.id
        session["reset_otp_hash"] = hash_otp(otp)

        session["reset_otp_expires"] = (
            datetime.utcnow() + timedelta(minutes=5)
        ).timestamp()

        session["reset_otp_verified"] = False

        try:

            send_otp_email(
                email,
                otp
            )

        except Exception as e:
            print("====================================")
            print("OTP EMAIL ERROR:", repr(e))
            print("====================================")
            session.pop("reset_email", None)
            session.pop("reset_user_id", None)
            session.pop("reset_otp_hash", None)
            session.pop("reset_otp_expires", None)
            session.pop("reset_otp_verified", None)
            return render_template(
                "forgot_password.html",
                error="Unable to send OTP. Please try again later."
                )

        return redirect(
            url_for("verify_otp")
        )

    return render_template(
        "forgot_password.html"
    )


# ============================================================
# RESET PASSWORD
# ============================================================

@app.route(
    "/reset-password",
    methods=["GET", "POST"]
)
def reset_password():

    # OTP verification complete aayittundo?
    if not session.get("reset_otp_verified"):
        return redirect(
            url_for("forgot_password")
        )

    # Reset email session-il undo?
    email = session.get("reset_email")

    if not email:
        return redirect(
            url_for("forgot_password")
        )

    user = User.query.filter_by(
        email=email
    ).first()

    if not user:
        session.clear()

        return redirect(
            url_for("forgot_password")
        )

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not password or not confirm_password:

            return render_template(
                "reset_password.html",
                error="All fields are required."
            )

        if password != confirm_password:

            return render_template(
                "reset_password.html",
                error="Passwords do not match."
            )

        if len(password) < 6:

            return render_template(
                "reset_password.html",
                error="Password must contain at least 6 characters."
            )

        # Update password
        
        user.password = generate_password_hash(
            password
        )

        db.session.commit()

        # Clear password reset session
        session.pop("reset_email", None)
        session.pop("reset_otp_hash", None)
        session.pop("reset_otp_expires", None)
        session.pop("reset_otp_verified", None)

        flash("Password reset successfully. Please log in with your new password.", "success")

        return redirect(
            url_for("login")
        )
    

    return render_template(
        "reset_password.html"
    )


# ============================================================
# VERIFY OTP
# ============================================================

@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():

    if "reset_email" not in session:
        return redirect(
            url_for("forgot_password")
        )

    if request.method == "POST":

        otp = request.form.get(
            "otp",
            ""
        ).strip()

        if not otp or len(otp) != 6 or not otp.isdigit():

            return render_template(
                "verify_otp.html",
                error="Please enter a valid 6-digit OTP."
            )

        expiry = session.get(
            "reset_otp_expires"
        )

        if not expiry:

            return render_template(
                "verify_otp.html",
                error="OTP has expired. Please request a new OTP."
            )

        if datetime.utcnow().timestamp() > expiry:

            session.pop("reset_otp_hash", None)
            session.pop("reset_otp_expires", None)

            return render_template(
                "verify_otp.html",
                error="OTP has expired. Please request a new OTP."
            )

        entered_hash = hash_otp(otp)

        if entered_hash != session.get(
            "reset_otp_hash"
        ):

            return render_template(
                "verify_otp.html",
                error="Incorrect OTP. Please try again."
            )

        session["reset_otp_verified"] = True
        return redirect(
            url_for(
                "reset_password",
                user_id=session["reset_user_id"]
            )
        )

    return render_template(
        "verify_otp.html"
    )

# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(
        url_for("login")
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/")
@login_required
def dashboard():

    total = Job.query.filter_by(
        user_id=current_user.id
    ).count()

    statuses = [
        "Applied",
        "Shortlisted",
        "Interview",
        "Selected",
        "Rejected"
    ]

    counts = {}

    for status in statuses:

        counts[status] = Job.query.filter_by(
            user_id=current_user.id,
            status=status
        ).count()

    # Monthly applications
    monthly = (
        db.session.query(
            func.strftime(
                "%Y-%m",
                Job.applied_date
            ).label("month"),
            func.count(Job.id).label("count")
        )
        .filter(
            Job.user_id == current_user.id
        )
        .group_by("month")
        .order_by("month")
        .all()
    )

    monthly_data = [
        {
            "month": row.month,
            "count": row.count
        }
        for row in monthly
    ]

    # Applications by company
    company_rows = (
        db.session.query(
            Job.company,
            func.count(Job.id).label("count")
        )
        .filter(
            Job.user_id == current_user.id
        )
        .group_by(Job.company)
        .order_by(
            func.count(Job.id).desc()
        )
        .limit(8)
        .all()
    )

    company_data = [
        [company, count]
        for company, count in company_rows
    ]

    return render_template(
        "dashboard.html",
        total=total,
        counts=counts,
        monthly=monthly_data,
        company_data=company_data
    )


# ============================================================
# JOBS PAGE
# ============================================================

@app.route("/jobs")
@login_required
def jobs_page():

    jobs = (
        Job.query
        .filter_by(user_id=current_user.id)
        .order_by(Job.applied_date.desc())
        .all()
    )

    return render_template(
        "jobs.html",
        jobs=jobs
    )


# ============================================================
# ADD JOB
# ============================================================

@app.route("/jobs/add", methods=["GET", "POST"])
@login_required
def add_job():

    if request.method == "POST":

        company = request.form.get(
            "company",
            ""
        ).strip()

        title = request.form.get(
            "title",
            ""
        ).strip()

        applied_date_value = request.form.get(
            "applied_date",
            ""
        ).strip()

        if not company or not title or not applied_date_value:

            return render_template(
                "job_form.html",
                job=None,
                error="Company, Job Title and Applied Date are required."
            )

        try:

            applied_date = datetime.strptime(
                applied_date_value,
                "%Y-%m-%d"
            ).date()

        except ValueError:

            return render_template(
                "job_form.html",
                job=None,
                error="Invalid date format."
            )

        job = Job(
            user_id=current_user.id,
            company=company,
            title=title,
            location=request.form.get(
                "location",
                ""
            ).strip(),
            job_type=request.form.get(
                "job_type",
                ""
            ).strip(),
            applied_date=applied_date,
            job_url=request.form.get(
                "job_url",
                ""
            ).strip(),
            salary=request.form.get(
                "salary",
                ""
            ).strip(),
            status=request.form.get(
                "status",
                "Applied"
            ).strip(),
            notes=request.form.get(
                "notes",
                ""
            ).strip()
        )

        db.session.add(job)
        db.session.commit()

        return redirect(
            url_for("jobs_page")
        )

    return render_template(
        "job_form.html",
        job=None,
        error=None
    )


# ============================================================
# EDIT JOB
# ============================================================

@app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
def edit_job(job_id):

    job = Job.query.filter_by(
        id=job_id,
        user_id=current_user.id
    ).first_or_404()

     
    if request.method == "POST":

        company = request.form.get(
            "company",
            ""
        ).strip()

        title = request.form.get(
            "title",
            ""
        ).strip()

        applied_date_value = request.form.get(
            "applied_date",
            ""
        ).strip()

        if not company or not title or not applied_date_value:

            return render_template(
                "job_form.html",
                job=job,
                error="Company, Job Title and Applied Date are required."
            )

        try:

            applied_date = datetime.strptime(
                applied_date_value,
                "%Y-%m-%d"
            ).date()

        except ValueError:

            return render_template(
                "job_form.html",
                job=job,
                error="Invalid date format."
            )

        job.company = company
        job.title = title
        job.location = request.form.get(
            "location",
            ""
        ).strip()

        job.job_type = request.form.get(
            "job_type",
            ""
        ).strip()

        job.applied_date = applied_date

        job.job_url = request.form.get(
            "job_url",
            ""
        ).strip()

        job.salary = request.form.get(
            "salary",
            ""
        ).strip()

        job.status = request.form.get(
            "status",
            "Applied"
        ).strip()

        job.notes = request.form.get(
            "notes",
            ""
        ).strip()

        db.session.commit()

        return redirect(
            url_for("jobs_page")
        )

    return render_template(
        "job_form.html",
        job=job,
        error=None
    )


# ============================================================
# INTERVIEWS PAGE
# ============================================================

@app.route("/interviews")
@login_required
def interviews_page():

    interviews = (
        Interview.query
        .join(Job)
        .filter(
            Job.user_id == current_user.id
        )
        .order_by(
            Interview.interview_date.desc()
        )
        .all()
    )

    return render_template(
        "interviews.html",
        interviews=interviews
    )


# ============================================================
# INTERVIEW DATETIME PARSER
# ============================================================

def parse_interview_datetime():

    date_value = request.form.get(
        "interview_date",
        ""
    ).strip()

    hour = request.form.get(
        "hour",
        ""
    ).strip()

    minute = request.form.get(
        "minute",
        ""
    ).strip()

    ampm = request.form.get(
        "ampm",
        ""
    ).strip().upper()

    if not date_value:
        raise ValueError(
            "Interview date is required."
        )

    if not hour:
        raise ValueError(
            "Interview hour is required."
        )

    if not minute:
        raise ValueError(
            "Interview minute is required."
        )

    if ampm not in ["AM", "PM"]:
        raise ValueError(
            "Please select AM or PM."
        )

    try:

        return datetime.strptime(
            f"{date_value} {hour}:{minute} {ampm}",
            "%Y-%m-%d %I:%M %p"
        )

    except ValueError:

        raise ValueError(
            "Invalid interview date or time."
        )


# ============================================================
# API DATETIME PARSER
# ============================================================

def parse_api_interview_datetime(value):

    if not value:
        raise ValueError(
            "Interview date/time is required."
        )

    formats = [
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%I:%M %p",
        "%Y-%m-%d %I:%M %p"
    ]

    for fmt in formats:

        try:

            return datetime.strptime(
                value,
                fmt
            )

        except ValueError:
            continue

    raise ValueError(
        "Invalid interview date/time format."
    )


# ============================================================
# UPDATE JOB STATUS FROM INTERVIEW
# ============================================================

def update_job_status_from_interviews(job):

    interviews = Interview.query.filter_by(
        job_id=job.id
    ).all()

    if not interviews:
        return

    statuses = [
        interview.status
        for interview in interviews
    ]

    # ------------------------------------------------
    # ANY ROUND FAILED → REJECTED
    # ------------------------------------------------
    if "Failed" in statuses:
        job.status = "Rejected"
        return

    # ------------------------------------------------
    # ALL ROUNDS PASSED → SELECTED
    # ------------------------------------------------
    if all(status == "Passed" for status in statuses):
        job.status = "Selected"
        return

    # ------------------------------------------------
    # INTERVIEW STILL IN PROGRESS
    # ------------------------------------------------
    if any(
        status in ["Scheduled", "Completed"]
        for status in statuses
    ):
        job.status = "Interview"
        return


# ============================================================
# ADD INTERVIEW
# ============================================================

@app.route("/interviews/add", methods=["GET", "POST"])
@login_required
def add_interview():

    jobs = (
        Job.query
        .filter_by(
            user_id=current_user.id
        )
        .order_by(Job.company.asc())
        .all()
    )

    preselect_job_id = request.args.get(
        "job_id",
        type=int
    )

    if not jobs:

        return render_template(
            "interview_form.html",
            interview=None,
            job=None,
            jobs=jobs,
            preselect_job_id=None,
            error="Please add a job application first."
        )

    if request.method == "POST":

        try:

            job_id = request.form.get(
                "job_id",
                ""
            ).strip()

            if not job_id:

                return render_template(
                    "interview_form.html",
                    interview=None,
                    job=None,
                    jobs=jobs,
                    preselect_job_id=None,
                    error="Please select a job application."
                )

            job = Job.query.filter_by(
                id=int(job_id),
                user_id=current_user.id
            ).first_or_404()

            interview_date = parse_interview_datetime()

            interview = Interview(
                job_id=job.id,
                interview_date=interview_date,
                round=request.form.get(
                    "round",
                    ""
                ).strip(),
                interview_type=request.form.get(
                    "interview_type",
                    ""
                ).strip(),
                status=request.form.get(
                    "status",
                    "Scheduled"
                ).strip(),
                feedback=request.form.get(
                    "feedback",
                    ""
                ).strip()
            )

            db.session.add(interview)

            db.session.flush()

            update_job_status_from_interviews(job)

            db.session.commit()
            

            return redirect(
                url_for("interviews_page")
            )

        except (
            ValueError,
            TypeError
        ) as error:

            return render_template(
                "interview_form.html",
                interview=None,
                job=None,
                jobs=jobs,
                preselect_job_id=preselect_job_id,
                error=str(error)
            )

    return render_template(
        "interview_form.html",
        interview=None,
        job=None,
        jobs=jobs,
        preselect_job_id=preselect_job_id,
        error=None
    )


# ============================================================
# EDIT INTERVIEW
# ============================================================

@app.route(
    "/interviews/<int:id>/edit",
    methods=["GET", "POST"]
)
@login_required
def edit_interview(id):

    interview = (
        Interview.query
        .join(Job)
        .filter(
            Interview.id == id,
            Job.user_id == current_user.id
        )
    .first_or_404()
    )
    
    jobs = (
        Job.query
        .filter_by(
            user_id=current_user.id
        )
        .order_by(Job.company.asc())
        .all()
    )

    if request.method == "POST":

        try:

            old_job = interview.job
            job_id = request.form.get(
                "job_id",
                ""
            ).strip()

            if not job_id:

                return render_template(
                    "interview_form.html",
                    interview=interview,
                    job=interview.job,
                    jobs=jobs,
                    preselect_job_id=None,
                    error="Please select a job application."
                )

            job = Job.query.filter_by(
                id=int(job_id),
                user_id=current_user.id
            ).first_or_404()

            
            interview.job_id = job.id

            interview.interview_date = (
                parse_interview_datetime()
            )

            interview.round = request.form.get(
                "round",
                ""
            ).strip()

            interview.interview_type = request.form.get(
                "interview_type",
                ""
            ).strip()

            interview.status = request.form.get(
                "status",
                "Scheduled"
            ).strip()

            interview.feedback = request.form.get(
                "feedback",
                ""
            ).strip()

            db.session.add(interview)

            db.session.flush()

            # Recalculate new job status
            update_job_status_from_interviews(job)

            # If interview was moved to another job,
            # recalculate the old job also
            if old_job.id != job.id:
                update_job_status_from_interviews(old_job)

            db.session.commit()

            return redirect(
                url_for("interviews_page")
            )

        except (
            ValueError,
            TypeError
        ) as error:

            return render_template(
                "interview_form.html",
                interview=interview,
                job=interview.job,
                jobs=jobs,
                preselect_job_id=None,
                error=str(error)
            )

    return render_template(
        "interview_form.html",
        interview=interview,
        job=interview.job,
        jobs=jobs,
        preselect_job_id=None,
        error=None
    )


# ============================================================
# JOB API - GET ALL
# ============================================================

@app.route("/api/jobs", methods=["GET"])
@login_required
def api_get_jobs():

    company = request.args.get("company")
    location = request.args.get("location")
    status = request.args.get("status")
    job_type = request.args.get("job_type")

    query = Job.query.filter_by(
    user_id=current_user.id
)
    if company:

        query = query.filter(
            Job.company.ilike(
                f"%{company}%"
            )
        )

    if location:

        query = query.filter(
            Job.location.ilike(
                f"%{location}%"
            )
        )

    if status:

        query = query.filter_by(
            status=status
        )

    if job_type:

        query = query.filter_by(
            job_type=job_type
        )

    jobs = (
        query
        .order_by(
            Job.applied_date.desc()
        )
        .all()
    )

    return jsonify([
        job_to_dict(job)
        for job in jobs
    ])


# ============================================================
# JOB API - GET SINGLE
# ============================================================

@app.route(
    "/api/jobs/<int:job_id>",
    methods=["GET"]
)
@login_required
def api_get_job(job_id):

    job = Job.query.filter_by(
        id=job_id,
        user_id=current_user.id
    ).first_or_404()

    
    return jsonify(
        job_to_dict(job)
    )


# ============================================================
# JOB API - CREATE
# ============================================================

@app.route(
    "/api/jobs",
    methods=["POST"]
)
@login_required
def api_create_job():

    data = request.get_json(
        silent=True
    ) or {}

    required_fields = [
        "company",
        "title",
        "applied_date"
    ]

    missing = [
        field
        for field in required_fields
        if not data.get(field)
    ]

    if missing:

        return jsonify({
            "error":
                "Missing fields: "
                + ", ".join(missing)
        }), 400

    try:

        applied_date = datetime.strptime(
            data["applied_date"],
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return jsonify({
            "error":
                "applied_date must be YYYY-MM-DD"
        }), 400
    job = Job(
        user_id=current_user.id,
        company=str(data["company"]).strip(),
        title=str(data["title"]).strip(),
        location=str(
            data.get("location", "")
        ).strip(),
        job_type=str(
            data.get("job_type", "")
        ).strip(),
        applied_date=applied_date,
        job_url=str(
            data.get("job_url", "")
        ).strip(),
        salary=str(
            data.get("salary", "")
        ).strip(),
        status=str(
            data.get("status", "Applied")
        ).strip(),
        notes=str(
            data.get("notes", "")
        ).strip()
    )

    db.session.add(job)
    db.session.commit()

    return jsonify(
        job_to_dict(job)
    ), 201


# ============================================================
# JOB API - UPDATE
# ============================================================

@app.route(
    "/api/jobs/<int:job_id>",
    methods=["PUT"]
)
@login_required
def api_update_job(job_id):

    job = Job.query.filter_by(
        id=job_id,
        user_id=current_user.id
    ).first_or_404()
    
    data = request.get_json(
        silent=True
    ) or {}

    editable_fields = [
        "company",
        "title",
        "location",
        "job_type",
        "job_url",
        "salary",
        "status",
        "notes"
    ]

    for field in editable_fields:

        if field in data:

            setattr(
                job,
                field,
                data[field]
            )

    if "applied_date" in data:

        try:

            job.applied_date = datetime.strptime(
                data["applied_date"],
                "%Y-%m-%d"
            ).date()

        except ValueError:

            return jsonify({
                "error":
                    "applied_date must be YYYY-MM-DD"
            }), 400

    db.session.commit()

    return jsonify(
        job_to_dict(job)
    )


# ============================================================
# JOB API - DELETE
# ============================================================

@app.route(
    "/api/jobs/<int:job_id>",
    methods=["DELETE"]
)
@login_required
def api_delete_job(job_id):

    job = Job.query.filter_by(
        id=job_id,
        user_id=current_user.id
    ).first_or_404()

    db.session.delete(job)
    db.session.commit()

    return jsonify({
        "message":
            "Job deleted successfully"
    })


# ============================================================
# INTERVIEW API - GET ALL
# ============================================================

@app.route(
    "/api/interviews",
    methods=["GET"]
)
@login_required
def api_get_interviews():

    interviews = (
        Interview.query
        .join(Job)
        .filter(
            Job.user_id == current_user.id
        )
        .order_by(
            Interview.interview_date.desc()
        )
        .all()
    )

    return jsonify([
        interview_to_dict(interview)
        for interview in interviews
    ])


# ============================================================
# INTERVIEW API - GET SINGLE
# ============================================================

@app.route(
    "/api/interviews/<int:id>",
    methods=["GET"]
)
@login_required
def api_get_interview(id):

    interview = (
        Interview.query
        .join(Job)
        .filter(
            Interview.id == id,
            Job.user_id == current_user.id
        )
        .first_or_404()
    )

    
    return jsonify(
        interview_to_dict(interview)
    )


# ============================================================
# INTERVIEW API - CREATE
# ============================================================

@app.route(
    "/api/interviews",
    methods=["POST"]
)
@login_required
def api_create_interview():

    data = request.get_json(
        silent=True
    ) or {}

    required = [
        "job_id",
        "interview_date"
    ]

    missing = [
        field
        for field in required
        if not data.get(field)
    ]

    if missing:

        return jsonify({
            "error":
                "Missing fields: "
                + ", ".join(missing)
        }), 400

    try:

        job = Job.query.filter_by(
            id = int(data["job_id"]),
            user_id = current_user.id
        ).first_or_404()

    except (
        ValueError,
        TypeError
    ):

        return jsonify({
            "error":
                "Invalid job_id"
        }), 400

    try:

        interview_date = (
            parse_api_interview_datetime(
                data["interview_date"]
            )
        )

    except ValueError as error:

        return jsonify({
            "error": str(error)
        }), 400

    interview = Interview(
        job_id=job.id,
        interview_date=interview_date,
        round=str(
            data.get("round", "")
        ).strip(),
        interview_type=str(
            data.get("interview_type", "")
        ).strip(),
        status=str(
            data.get("status", "Scheduled")
        ).strip(),
        feedback=str(
            data.get("feedback", "")
        ).strip()
    )

    db.session.add(interview)

    # Make the new interview visible to the status calculation
    db.session.flush()

    update_job_status_from_interviews(job)

    db.session.commit()

    return jsonify(
        interview_to_dict(interview)
    ), 201


# ============================================================
# INTERVIEW API - UPDATE
# ============================================================

@app.route(
    "/api/interviews/<int:id>",
    methods=["PUT"]
)
@login_required
def api_update_interview(id):

    interview = (
        Interview.query
        .join(Job)
        .filter(Interview.id == id,
        Job.user_id == current_user.id
        )
        .first_or_404()
    )


    data = request.get_json(
        silent=True
    )

    if data is None:

        return jsonify({
            "error":
                "Invalid or missing JSON data."
        }), 400

    if "job_id" in data:

        try:

            job = Job.query.filter_by(
                id=int(data["job_id"]),
                user_id=current_user.id
            ).first_or_404()

            interview.job_id = job.id

        except (
            ValueError,
            TypeError
        ):

            return jsonify({
                "error":
                    "Invalid job_id"
            }), 400

    if "interview_date" in data:

        try:

            interview.interview_date = (
                parse_api_interview_datetime(
                    data["interview_date"]
                )
            )

        except ValueError as error:

            return jsonify({
                "error": str(error)
            }), 400

    if "round" in data:

        interview.round = (
            data["round"] or ""
        )

    if "interview_type" in data:

        interview.interview_type = (
            data["interview_type"] or ""
        )

    if "status" in data:

        interview.status = (
            data["status"] or "Scheduled"
        )

    if "feedback" in data:

        interview.feedback = (
            data["feedback"] or ""
        )

    job = interview.job

    update_job_status_from_interviews(job)

    db.session.commit()

    return jsonify(
        interview_to_dict(interview)
    )


# ============================================================
# INTERVIEW API - DELETE
# ============================================================

@app.route(
    "/api/interviews/<int:id>",
    methods=["DELETE"]
)
@login_required
def api_delete_interview(id):

    interview = (
        Interview.query
        .join(Job)
        .filter(
            Interview.id == id,
            Job.user_id == current_user.id
        )
        .first_or_404()
    )

    job = interview.job

    db.session.delete(interview)

    db.session.flush()

    update_job_status_from_interviews(job)

    db.session.commit()

    return jsonify({
        "message":
            "Interview deleted successfully"
})


# ============================================================
# RESUME MATCH PAGE
# ============================================================

@app.route("/resume-match")
@login_required
def resume_match():

    return render_template(
        "resume_match.html"
    )


# ============================================================
# RESUME MATCH API
# ============================================================

@app.route(
    "/api/resume-match",
    methods=["POST"]
)
@login_required
def api_resume_match():

    data = request.get_json(
        silent=True
    ) or {}

    resume_skills_text = data.get(
        "resume_skills",
        ""
    ).strip()

    job_description = data.get(
        "job_description",
        ""
    ).strip()

    if not resume_skills_text:

        return jsonify({
            "error":
                "Please enter your skills."
        }), 400

    if not job_description:

        return jsonify({
            "error":
                "Please enter the job description."
        }), 400

    # Skill dictionary
    skill_aliases = {

        "python": "Python",

        "flask": "Flask",

        "django": "Django",

        "fastapi": "FastAPI",

        "sql": "SQL",

        "mysql": "MySQL",

        "postgresql": "PostgreSQL",

        "postgres": "PostgreSQL",

        "sqlite": "SQLite",

        "mongodb": "MongoDB",

        "rest api": "REST API",

        "rest apis": "REST API",

        "api": "REST API",

        "git": "Git",

        "github": "GitHub",

        "html": "HTML",

        "css": "CSS",

        "javascript": "JavaScript",

        "js": "JavaScript",

        "react": "React",

        "reactjs": "React",

        "node": "Node.js",

        "nodejs": "Node.js",

        "docker": "Docker",

        "aws": "AWS",

        "gcp": "GCP",

        "selenium": "Selenium",

        "scrapy": "Scrapy",

        "bootstrap": "Bootstrap",

        "power bi": "Power BI",

        "excel": "Excel",

        "machine learning": "Machine Learning",

        "deep learning": "Deep Learning",

        "pandas": "Pandas",

        "numpy": "NumPy",

        "scikit learn": "Scikit-learn",

        "scikit-learn": "Scikit-learn"
    }

    resume_lower = resume_skills_text.lower()
    jd_lower = job_description.lower()

    resume_found = set()
    jd_found = set()

    for keyword, display_name in skill_aliases.items():

        if keyword in resume_lower:
            resume_found.add(display_name)

        if keyword in jd_lower:
            jd_found.add(display_name)

    matched_skills = sorted(
        resume_found.intersection(jd_found)
    )

    missing_skills = sorted(
        jd_found.difference(resume_found)
    )

    if jd_found:

        match_score = round(
            (
                len(matched_skills)
                /
                len(jd_found)
            ) * 100
        )

    else:

        match_score = 0

    suggested_learning = [
        f"Learn {skill}"
        for skill in missing_skills
    ]

    return jsonify({

        "match_score":
            match_score,

        "matched_skills":
            matched_skills,

        "missing_skills":
            missing_skills,

        "suggested_learning":
            suggested_learning
    })


# ============================================================
# HELPER - JOB TO DICTIONARY
# ============================================================

def job_to_dict(job):

    return {

        "id": job.id,

        "company": job.company,

        "title": job.title,

        "location": job.location,

        "job_type": job.job_type,

        "applied_date":
            job.applied_date.isoformat()
            if job.applied_date
            else None,

        "job_url": job.job_url,

        "salary": job.salary,

        "status": job.status,

        "notes": job.notes
    }


# ============================================================
# HELPER - INTERVIEW TO DICTIONARY
# ============================================================

def interview_to_dict(interview):

    return {

        "id": interview.id,

        "job_id": interview.job_id,

        "company":
            interview.job.company
            if interview.job
            else "",

        "title":
            interview.job.title
            if interview.job
            else "",

        "interview_date":
            interview.interview_date.isoformat()
            if interview.interview_date
            else None,

        "round": interview.round,

        "interview_type":
            interview.interview_type,

        "status": interview.status,

        "feedback": interview.feedback
    }


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    if request.path.startswith("/api/"):

        return jsonify({
            "error": "Resource not found"
        }), 404

    return render_template(
        "404.html"
    ), 404


@app.errorhandler(500)
def internal_server_error(error):

    db.session.rollback()

    if request.path.startswith("/api/"):

        return jsonify({
            "error": "Internal server error"
        }), 500

    return render_template(
        "500.html"
    ), 500


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )