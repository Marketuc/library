from datetime import datetime

from flask_login import UserMixin

from .extensions import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    face_image_path = db.Column(db.String(500), nullable=True)
    role = db.Column(db.String(50), nullable=False, default="librarian")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    student_loans = db.relationship("Loan", back_populates="student", foreign_keys="Loan.student_id")

    def has_face(self):
        return bool(self.face_image_path)

    @property
    def is_student(self):
        return self.role == "student"

    @property
    def is_librarian(self):
        return self.role in {"admin", "librarian"}


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    author = db.Column(db.String(200), nullable=False)
    isbn = db.Column(db.String(64), unique=True, nullable=True)
    total_copies = db.Column(db.Integer, nullable=False, default=1)
    available_copies = db.Column(db.Integer, nullable=False, default=1)
    cover_image_path = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    loans = db.relationship("Loan", back_populates="book", cascade="all, delete-orphan")


class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    loans = db.relationship("Loan", back_populates="member")


class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("book.id"), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey("member.id"), nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    issued_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    due_at = db.Column(db.DateTime, nullable=False)
    returned_at = db.Column(db.DateTime, nullable=True)

    book = db.relationship("Book", back_populates="loans")
    member = db.relationship("Member", back_populates="loans")
    student = db.relationship("User", back_populates="student_loans", foreign_keys=[student_id])

    @property
    def is_active(self):
        return self.returned_at is None

    @property
    def borrower_name(self):
        if self.student:
            return f"{self.student.username} (student)"
        if self.member:
            return self.member.name
        return "Unknown borrower"
