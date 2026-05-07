import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from .extensions import db, login_manager


def ensure_sqlite_parent(database_url):
    """Create the parent directory for relative/absolute SQLite URLs."""
    if not database_url.startswith("sqlite:///"):
        return
    raw_path = database_url.replace("sqlite:///", "", 1)
    if raw_path == ":memory:":
        return
    db_path = Path(raw_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)


def create_app():
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        database_url = "sqlite:///" + str(Path(app.instance_path) / "library.sqlite3")
    ensure_sqlite_parent(database_url)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
        FACE_UPLOAD_DIR=str(Path(app.instance_path) / "faces"),
        BOOK_COVER_UPLOAD_DIR=str(Path(app.instance_path) / "book_covers"),
        STUDENT_LOAN_DAYS=int(os.environ.get("STUDENT_LOAN_DAYS", "14")),
        DEEPFACE_MODEL=os.environ.get("DEEPFACE_MODEL", "Facenet"),
        DEEPFACE_DETECTOR_BACKEND=os.environ.get("DEEPFACE_DETECTOR_BACKEND", "opencv"),
        DEEPFACE_DISTANCE_METRIC=os.environ.get("DEEPFACE_DISTANCE_METRIC", "cosine"),
    )

    Path(app.config["FACE_UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["BOOK_COVER_UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    login_manager.login_message_category = "warning"

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .routes import main_bp

    app.register_blueprint(main_bp)
    register_cli(app)

    return app


def make_svg_cover(title, author, accent="#3157d5"):
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_author = author.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="720" viewBox="0 0 480 720">
  <rect width="480" height="720" rx="36" fill="{accent}"/>
  <rect x="40" y="40" width="400" height="640" rx="28" fill="#ffffff" opacity="0.12"/>
  <rect x="72" y="84" width="336" height="552" rx="20" fill="#ffffff"/>
  <text x="240" y="250" text-anchor="middle" font-family="Arial, sans-serif" font-size="42" font-weight="700" fill="#182033">{safe_title}</text>
  <line x1="110" y1="330" x2="370" y2="330" stroke="{accent}" stroke-width="8" stroke-linecap="round"/>
  <text x="240" y="400" text-anchor="middle" font-family="Arial, sans-serif" font-size="26" fill="#697386">{safe_author}</text>
  <text x="240" y="570" text-anchor="middle" font-family="Arial, sans-serif" font-size="22" fill="#697386">Library copy</text>
</svg>'''


def seed_cover_file(app, filename, title, author, accent):
    path = Path(app.config["BOOK_COVER_UPLOAD_DIR"]) / filename
    if not path.exists():
        path.write_text(make_svg_cover(title, author, accent), encoding="utf-8")
    return filename


def seed_database(app):
    from werkzeug.security import generate_password_hash

    from .models import Book, Member, User

    db.create_all()

    if not User.query.filter_by(username="admin").first():
        db.session.add(
            User(
                username="admin",
                email="admin@example.com",
                password_hash=generate_password_hash("admin12345"),
                role="admin",
            )
        )

    if not User.query.filter_by(username="student").first():
        db.session.add(
            User(
                username="student",
                email="student@example.com",
                password_hash=generate_password_hash("student12345"),
                role="student",
            )
        )

    if Book.query.count() == 0:
        books = [
            ("Clean Code", "Robert C. Martin", "9780132350884", 3, "clean-code.svg", "#3157d5"),
            ("Fluent Python", "Luciano Ramalho", "9781492056355", 2, "fluent-python.svg", "#067647"),
            ("The Pragmatic Programmer", "Andrew Hunt and David Thomas", "9780135957059", 4, "pragmatic-programmer.svg", "#b54708"),
        ]
        for title, author, isbn, copies, cover, accent in books:
            db.session.add(
                Book(
                    title=title,
                    author=author,
                    isbn=isbn,
                    total_copies=copies,
                    available_copies=copies,
                    cover_image_path=seed_cover_file(app, cover, title, author, accent),
                )
            )

    if Member.query.count() == 0:
        db.session.add_all(
            [
                Member(name="Juan Dela Cruz", email="juan@example.com", phone="09171234567"),
                Member(name="Maria Santos", email="maria@example.com", phone="09181234567"),
            ]
        )

    db.session.commit()


def register_cli(app):
    import click

    @app.cli.command("init-db")
    def init_db_command():
        """Create database tables."""
        db.create_all()
        click.echo("Database initialized.")

    @app.cli.command("seed")
    def seed_command():
        """Create starter data, including sample book covers."""
        seed_database(app)
        click.echo("Seed data inserted.")

    @app.cli.command("reset-db")
    def reset_db_command():
        """Drop all tables, recreate them, and insert starter data."""
        if not click.confirm("This deletes all library data. Continue?"):
            click.echo("Cancelled.")
            return
        db.drop_all()
        db.create_all()
        seed_database(app)
        click.echo("Database reset and seed data inserted.")
