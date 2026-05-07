# Library Face Login System

A Flask library management system using DeepFace face recognition. It now has two account types:

- **Librarians/Admins**: manage books, upload book cover pictures, manage walk-in members, and view all loans.
- **Students**: log in with face recognition or password, browse book pictures, borrow available books, and return their own loans.

## Main features

- Flask + SQLite database
- DeepFace face enrollment and face login
- Separate student login/register pages
- Student book borrowing page with book cover pictures
- Book cover image upload from the librarian book form
- Admin/librarian dashboard, book catalog, members, and all-loans page
- Student dashboard, borrow-books page, and my-loans page

## Windows Conda setup

From PowerShell:

```powershell
cd C:\Users\PC\OneDrive\Documents\library_face_flask
conda create -n library-face python=3.11 -y
conda activate library-face
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
Copy-Item .env.example .env -Force
```

## First run after downloading this version

This version changes the database schema to support student borrowers and book cover pictures. If you already created an older database, reset it once:

```powershell
python -m flask --app run.py reset-db
```

Type `y` when it asks for confirmation.

If you do not have any database yet, you can run:

```powershell
python -m flask --app run.py init-db
python -m flask --app run.py seed
```

## Start the app

```powershell
python -m flask --app run.py run --debug --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

## Default test accounts

These are created by `seed` or `reset-db`:

```text
Librarian/Admin:
username: admin
password: admin12345

Student:
username: student
password: student12345
```

The default accounts do not have enrolled face images, so use password login for them. New registered accounts can use face login.

## Student borrowing flow

1. Student logs in from **Student Login**.
2. Student opens **Borrow Books**.
3. The catalog shows each book with a cover picture.
4. Student clicks **Borrow this book**.
5. The app creates a loan, reduces the available copies by 1, and sets the due date using `STUDENT_LOAN_DAYS` from `.env`.
6. Student can return the book from **My Loans**.

## Adding book pictures

1. Login as librarian/admin.
2. Go to **Books**.
3. Click **Add book** or **Edit**.
4. Upload a cover image in **Book cover picture**.
5. Students will see that picture on the borrow page.

Supported cover formats: PNG, JPG, JPEG, WEBP, GIF.

## Fixing common errors

### Request Entity Too Large

The app is set to allow up to 16 MB requests and the camera capture uses JPEG to keep face captures small. If this still appears, use a smaller cover image.

### Unable to open database file

Make sure the `instance` folder exists:

```powershell
New-Item -ItemType Directory -Force instance
```

The default database URL is:

```env
DATABASE_URL=sqlite:///instance/library.sqlite3
```

### Socket permission error on Flask run

Use port 8000:

```powershell
python -m flask --app run.py run --debug --host 127.0.0.1 --port 8000
```
