from datetime import datetime, time, timedelta
from functools import wraps
from pathlib import Path
from secrets import token_urlsafe
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, text
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from .extensions import db
from .face_auth import FaceAuthError, assert_single_face, remove_file_safely, save_face_data_url, verify_face
from .models import Book, Loan, Member, User

main_bp = Blueprint("main", __name__)
ALLOWED_COVER_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


def get_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = token_urlsafe(32)
        session["_csrf_token"] = token
    return token


@main_bp.app_context_processor
def inject_helpers():
    return {"csrf_token": get_csrf_token, "now": datetime.utcnow, "book_cover_url": book_cover_url}


def validate_csrf():
    expected = session.get("_csrf_token")
    submitted = request.form.get("csrf_token")
    if not expected or submitted != expected:
        abort(400, description="Invalid CSRF token.")


def int_from_form(name, default=0):
    try:
        return int(request.form.get(name, default))
    except (TypeError, ValueError):
        return default


def librarian_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("main.login"))
        if not current_user.is_librarian:
            flash("That page is for librarians only.", "warning")
            return redirect(url_for("main.student_dashboard"))
        return view(*args, **kwargs)
    return wrapped


def student_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("main.student_login"))
        if not current_user.is_student:
            flash("That page is for students only.", "warning")
            return redirect(url_for("main.dashboard"))
        return view(*args, **kwargs)
    return wrapped


def dashboard_for(user):
    if user.is_student:
        return redirect(url_for("main.student_dashboard"))
    return redirect(url_for("main.dashboard"))


def allowed_cover(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_COVER_EXTENSIONS


def save_book_cover(file_storage, old_filename=None):
    if not file_storage or not file_storage.filename:
        return old_filename
    if not allowed_cover(file_storage.filename):
        raise ValueError("Book cover must be PNG, JPG, JPEG, WEBP, or GIF.")

    original = secure_filename(file_storage.filename)
    extension = original.rsplit(".", 1)[1].lower()
    filename = f"cover-{uuid4().hex}.{extension}"
    target_dir = Path(current_app.config["BOOK_COVER_UPLOAD_DIR"])
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    file_storage.save(target_path)

    if old_filename and old_filename != filename:
        try:
            (target_dir / old_filename).unlink(missing_ok=True)
        except OSError:
            pass
    return filename


def book_cover_url(book):
    if book.cover_image_path:
        return url_for("main.book_cover", filename=book.cover_image_path)
    return url_for("static", filename="img/book-placeholder.svg")


@main_bp.route("/book-covers/<path:filename>")
def book_cover(filename):
    return send_from_directory(current_app.config["BOOK_COVER_UPLOAD_DIR"], filename)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return dashboard_for(current_user)
    return render_template("index.html")


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return dashboard_for(current_user)

    if request.method == "POST":
        validate_csrf()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        face_data = request.form.get("face_data", "")

        if not username or not email or len(password) < 8:
            flash("Username, email, and an 8+ character password are required.", "danger")
            return render_template("register.html")

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("That username or email is already registered.", "danger")
            return render_template("register.html")

        face_path = None
        try:
            face_path = save_face_data_url(face_data, current_app.config["FACE_UPLOAD_DIR"], prefix=username)
            assert_single_face(face_path, detector_backend=current_app.config["DEEPFACE_DETECTOR_BACKEND"])
        except FaceAuthError as exc:
            remove_file_safely(face_path)
            flash(str(exc), "danger")
            return render_template("register.html")

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            face_image_path=face_path,
            role="librarian",
        )
        db.session.add(user)
        db.session.commit()
        flash("Librarian account created. You can now log in with your face.", "success")
        return redirect(url_for("main.login"))

    return render_template("register.html")


@main_bp.route("/student/register", methods=["GET", "POST"])
def student_register():
    if current_user.is_authenticated:
        return dashboard_for(current_user)

    if request.method == "POST":
        validate_csrf()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        face_data = request.form.get("face_data", "")

        if not username or not email or len(password) < 8:
            flash("Username, email, and an 8+ character password are required.", "danger")
            return render_template("student_register.html")

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("That username or email is already registered.", "danger")
            return render_template("student_register.html")

        face_path = None
        try:
            face_path = save_face_data_url(face_data, current_app.config["FACE_UPLOAD_DIR"], prefix=f"student-{username}")
            assert_single_face(face_path, detector_backend=current_app.config["DEEPFACE_DETECTOR_BACKEND"])
        except FaceAuthError as exc:
            remove_file_safely(face_path)
            flash(str(exc), "danger")
            return render_template("student_register.html")

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            face_image_path=face_path,
            role="student",
        )
        db.session.add(user)
        db.session.commit()
        flash("Student account created. You can now log in and borrow books.", "success")
        return redirect(url_for("main.student_login"))

    return render_template("student_register.html")


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    return handle_login("login.html", student_only=False)


@main_bp.route("/student/login", methods=["GET", "POST"])
def student_login():
    return handle_login("student_login.html", student_only=True)


def handle_login(template_name, student_only=False):
    if current_user.is_authenticated:
        return dashboard_for(current_user)

    if request.method == "POST":
        validate_csrf()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        face_data = request.form.get("face_data", "")
        login_method = request.form.get("login_method", "face")

        user = User.query.filter_by(username=username).first()
        if not user or (student_only and not user.is_student):
            flash("Invalid username or credentials.", "danger")
            return render_template(template_name)

        if login_method == "password":
            if check_password_hash(user.password_hash, password):
                login_user(user)
                flash("Logged in successfully.", "success")
                return dashboard_for(user)
            flash("Invalid username or credentials.", "danger")
            return render_template(template_name)

        temp_path = None
        try:
            temp_path = save_face_data_url(face_data, current_app.config["FACE_UPLOAD_DIR"], prefix=f"login-{username}")
            verified, details = verify_face(
                user.face_image_path,
                temp_path,
                model_name=current_app.config["DEEPFACE_MODEL"],
                detector_backend=current_app.config["DEEPFACE_DETECTOR_BACKEND"],
                distance_metric=current_app.config["DEEPFACE_DISTANCE_METRIC"],
            )
        except FaceAuthError as exc:
            flash(str(exc), "danger")
            return render_template(template_name)
        finally:
            remove_file_safely(temp_path)

        if verified:
            login_user(user)
            distance = details.get("distance")
            if distance is not None:
                flash(f"Face login successful. Distance: {distance:.4f}", "success")
            else:
                flash("Face login successful.", "success")
            return dashboard_for(user)

        flash("Face did not match the enrolled account.", "danger")
        return render_template(template_name)

    return render_template(template_name)


@main_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    validate_csrf()
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("main.index"))


@main_bp.route("/dashboard")
@librarian_required
def dashboard():
    stats = {
        "books": Book.query.count(),
        "students": User.query.filter_by(role="student").count(),
        "members": Member.query.count(),
        "active_loans": Loan.query.filter_by(returned_at=None).count(),
        "available_copies": db.session.query(func.coalesce(func.sum(Book.available_copies), 0)).scalar(),
    }
    recent_loans = Loan.query.order_by(Loan.issued_at.desc()).limit(5).all()
    return render_template("dashboard.html", stats=stats, recent_loans=recent_loans)


@main_bp.route("/books")
@librarian_required
def books():
    query = request.args.get("q", "").strip()
    books_query = Book.query
    if query:
        like = f"%{query}%"
        books_query = books_query.filter((Book.title.ilike(like)) | (Book.author.ilike(like)) | (Book.isbn.ilike(like)))
    all_books = books_query.order_by(Book.title.asc()).all()
    return render_template("books.html", books=all_books, query=query)


@main_bp.route("/books/new", methods=["GET", "POST"])
@librarian_required
def new_book():
    if request.method == "POST":
        validate_csrf()
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        isbn = request.form.get("isbn", "").strip() or None
        total_copies = max(1, int_from_form("total_copies", 1))

        if not title or not author:
            flash("Title and author are required.", "danger")
            return render_template("book_form.html", book=None)

        try:
            cover_filename = save_book_cover(request.files.get("cover_image"))
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template("book_form.html", book=None)

        book = Book(
            title=title,
            author=author,
            isbn=isbn,
            total_copies=total_copies,
            available_copies=total_copies,
            cover_image_path=cover_filename,
        )
        db.session.add(book)
        db.session.commit()
        flash("Book added.", "success")
        return redirect(url_for("main.books"))

    return render_template("book_form.html", book=None)


@main_bp.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
@librarian_required
def edit_book(book_id):
    book = db.get_or_404(Book, book_id)
    if request.method == "POST":
        validate_csrf()
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        isbn = request.form.get("isbn", "").strip() or None
        new_total = max(1, int_from_form("total_copies", book.total_copies))
        checked_out = book.total_copies - book.available_copies

        if not title or not author:
            flash("Title and author are required.", "danger")
            return render_template("book_form.html", book=book)

        if new_total < checked_out:
            flash("Total copies cannot be lower than copies currently checked out.", "danger")
            return render_template("book_form.html", book=book)

        try:
            book.cover_image_path = save_book_cover(request.files.get("cover_image"), old_filename=book.cover_image_path)
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template("book_form.html", book=book)

        book.title = title
        book.author = author
        book.isbn = isbn
        book.total_copies = new_total
        book.available_copies = new_total - checked_out
        db.session.commit()
        flash("Book updated.", "success")
        return redirect(url_for("main.books"))

    return render_template("book_form.html", book=book)


@main_bp.route("/books/<int:book_id>/delete", methods=["POST"])
@librarian_required
def delete_book(book_id):
    validate_csrf()
    book = db.get_or_404(Book, book_id)
    if any(loan.is_active for loan in book.loans):
        flash("Cannot delete a book with active loans.", "danger")
        return redirect(url_for("main.books"))
    if book.cover_image_path:
        try:
            (Path(current_app.config["BOOK_COVER_UPLOAD_DIR"]) / book.cover_image_path).unlink(missing_ok=True)
        except OSError:
            pass
    db.session.delete(book)
    db.session.commit()
    flash("Book deleted.", "info")
    return redirect(url_for("main.books"))


@main_bp.route("/members", methods=["GET", "POST"])
@librarian_required
def members():
    if request.method == "POST":
        validate_csrf()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower() or None
        phone = request.form.get("phone", "").strip() or None
        if not name:
            flash("Member name is required.", "danger")
            return redirect(url_for("main.members"))
        db.session.add(Member(name=name, email=email, phone=phone))
        db.session.commit()
        flash("Member added.", "success")
        return redirect(url_for("main.members"))

    all_members = Member.query.order_by(Member.name.asc()).all()
    students = User.query.filter_by(role="student").order_by(User.username.asc()).all()
    return render_template("members.html", members=all_members, students=students)


@main_bp.route("/members/<int:member_id>/delete", methods=["POST"])
@librarian_required
def delete_member(member_id):
    validate_csrf()
    member = db.get_or_404(Member, member_id)
    if any(loan.is_active for loan in member.loans):
        flash("Cannot delete a member with active loans.", "danger")
        return redirect(url_for("main.members"))
    db.session.delete(member)
    db.session.commit()
    flash("Member deleted.", "info")
    return redirect(url_for("main.members"))


@main_bp.route("/loans", methods=["GET", "POST"])
@librarian_required
def loans():
    if request.method == "POST":
        validate_csrf()
        book_id = int_from_form("book_id")
        member_id = int_from_form("member_id")
        due_date_str = request.form.get("due_date", "").strip()

        book = db.session.get(Book, book_id)
        member = db.session.get(Member, member_id)
        if not book or not member:
            flash("Select a valid book and member.", "danger")
            return redirect(url_for("main.loans"))

        if book.available_copies < 1:
            flash("No copies available for that book.", "danger")
            return redirect(url_for("main.loans"))

        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            due_at = datetime.combine(due_date, time(hour=23, minute=59, second=59))
        except ValueError:
            flash("Choose a valid due date.", "danger")
            return redirect(url_for("main.loans"))

        loan = Loan(book=book, member=member, due_at=due_at)
        book.available_copies -= 1
        db.session.add(loan)
        db.session.commit()
        flash("Book issued.", "success")
        return redirect(url_for("main.loans"))

    all_loans = Loan.query.order_by(Loan.issued_at.desc()).all()
    available_books = Book.query.filter(Book.available_copies > 0).order_by(Book.title.asc()).all()
    all_members = Member.query.order_by(Member.name.asc()).all()
    return render_template("loans.html", loans=all_loans, books=available_books, members=all_members)


@main_bp.route("/loans/<int:loan_id>/return", methods=["POST"])
@librarian_required
def return_loan(loan_id):
    validate_csrf()
    loan = db.get_or_404(Loan, loan_id)
    return finish_return(loan, redirect_to=url_for("main.loans"))


@main_bp.route("/student/dashboard")
@student_required
def student_dashboard():
    my_active_loans = Loan.query.filter_by(student_id=current_user.id, returned_at=None).order_by(Loan.issued_at.desc()).all()
    available_books = Book.query.filter(Book.available_copies > 0).order_by(Book.title.asc()).limit(6).all()
    stats = {
        "active_loans": len(my_active_loans),
        "available_books": Book.query.filter(Book.available_copies > 0).count(),
    }
    return render_template("student_dashboard.html", loans=my_active_loans, books=available_books, stats=stats)


@main_bp.route("/student/books")
@student_required
def student_books():
    query = request.args.get("q", "").strip()
    books_query = Book.query
    if query:
        like = f"%{query}%"
        books_query = books_query.filter((Book.title.ilike(like)) | (Book.author.ilike(like)) | (Book.isbn.ilike(like)))
    all_books = books_query.order_by(Book.title.asc()).all()
    active_book_ids = {
        loan.book_id for loan in Loan.query.filter_by(student_id=current_user.id, returned_at=None).all()
    }
    return render_template("student_books.html", books=all_books, query=query, active_book_ids=active_book_ids)


@main_bp.route("/student/books/<int:book_id>/borrow", methods=["POST"])
@student_required
def student_borrow(book_id):
    validate_csrf()
    book = db.get_or_404(Book, book_id)
    if book.available_copies < 1:
        flash("No copies are available right now.", "danger")
        return redirect(url_for("main.student_books"))

    existing = Loan.query.filter_by(student_id=current_user.id, book_id=book.id, returned_at=None).first()
    if existing:
        flash("You already borrowed this book.", "warning")
        return redirect(url_for("main.student_books"))

    due_at = datetime.utcnow() + timedelta(days=current_app.config["STUDENT_LOAN_DAYS"])
    loan = Loan(book=book, student=current_user, due_at=due_at)
    book.available_copies -= 1
    db.session.add(loan)
    db.session.commit()
    flash(f"You borrowed {book.title}. Due date: {due_at.strftime('%Y-%m-%d')}.", "success")
    return redirect(url_for("main.student_dashboard"))


@main_bp.route("/student/loans")
@student_required
def student_loans():
    my_loans = Loan.query.filter_by(student_id=current_user.id).order_by(Loan.issued_at.desc()).all()
    return render_template("student_loans.html", loans=my_loans)


@main_bp.route("/student/loans/<int:loan_id>/return", methods=["POST"])
@student_required
def student_return_loan(loan_id):
    validate_csrf()
    loan = db.get_or_404(Loan, loan_id)
    if loan.student_id != current_user.id:
        abort(403)
    return finish_return(loan, redirect_to=url_for("main.student_loans"))


def finish_return(loan, redirect_to):
    if loan.returned_at:
        flash("Loan was already returned.", "info")
        return redirect(redirect_to)

    loan.returned_at = datetime.utcnow()
    loan.book.available_copies += 1
    db.session.commit()
    flash("Book returned.", "success")
    return redirect(redirect_to)
