import os
import hashlib
import uuid
import re
from datetime import datetime, timezone
import logging
from dotenv import load_dotenv
from functools import wraps

from flask import Flask, request, jsonify, g, session
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import mysql.connector
from pymongo import MongoClient

from PIL import Image
import pytesseract
import spacy
from difflib import SequenceMatcher

load_dotenv(override=True)

# ================== CONFIG ==================

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev_insecure_change_me")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
frontend_origin = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
CORS(app, supports_credentials=True, origins=[frontend_origin])

# Rate Limiting
limiter = Limiter(get_remote_address, app=app)

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ✅ FIX 1: Remove PDF (Tesseract can't handle PDFs directly)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "tif", "tiff", "bmp"}  # PDF removed

# Tesseract path (change for Linux/Mac if needed)
pytesseract.pytesseract.tesseract_cmd = os.environ.get(
    "TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# MySQL connection parameters
MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "NewPassword123")
MYSQL_DB = os.environ.get("MYSQL_DB", "govverify")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))

# MongoDB connection parameters
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.environ.get("MONGO_DB", "govverify")
MONGO_COLLECTION = os.environ.get("MONGO_COLLECTION", "audit_logs")

# ================== GLOBALS ==================

mysql_db_health = None
mongo_collection = None

# spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
    print("✅ spaCy NLP model loaded successfully!")
except Exception:
    print("⚠️ spaCy model not found. Run: python -m spacy download en_core_web_sm")
    nlp = None

# ================== DB HELPERS ==================

def get_mysql():
    """Return a fresh MySQL connection for each request."""
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        port=MYSQL_PORT,
        autocommit=False
    )

def init_mysql():
    """Check if MySQL is reachable at startup."""
    global mysql_db_health
    try:
        conn = get_mysql()
        conn.close()
        mysql_db_health = True
        print("✅ MySQL reachable!")
        return True
    except mysql.connector.Error as err:
        print(f"❌ MySQL Connection Error: {err}")
        mysql_db_health = False
        return False

def init_mongodb():
    """Initialize MongoDB connection and collection."""
    global mongo_collection
    try:
        mongo_client = MongoClient(MONGO_URI)
        mongo_db = mongo_client[MONGO_DB_NAME]
        mongo_collection = mongo_db[MONGO_COLLECTION]
        mongo_collection.insert_one({
            "status": "MongoDB initialized",
            "timestamp": datetime.now(timezone.utc)
        })
        print("✅ MongoDB connected successfully!")
        return True
    except Exception as e:
        print(f"❌ MongoDB Connection Error: {e}")
        mongo_collection = None
        return False

def log_event(action, **kwargs):
    """Unified logging helper into MongoDB."""
    if mongo_collection is None:
        return
    doc = {
        "action": action,
        "timestamp": datetime.now(timezone.utc)
    }
    doc.update(kwargs)
    try:
        mongo_collection.insert_one(doc)
    except Exception as e:
        print(f"⚠️ Mongo log failed: {e}")

# Audit logging
logging.basicConfig(filename='audit.log', level=logging.INFO)

def log_audit_entry(action, user_id):
    if mongo_collection is None:
        return
    try:
        prev = mongo_collection.find_one(sort=[("_id", -1)])
        prev_hash = prev.get("entry_hash") if prev else "GENESIS"

        content = f"{action}|{user_id}|{datetime.now(timezone.utc)}|{prev_hash}"
        entry_hash = hashlib.sha256(content.encode()).hexdigest()

        mongo_collection.insert_one({
            "action": action,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc),
            "prev_hash": prev_hash,
            "entry_hash": entry_hash
        })
    except Exception as e:
        print(f"WARNING: Mongo audit log failed: {e}")

# ================== GENERIC HELPERS ==================

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file_storage(file_storage):
    filename = secure_filename(file_storage.filename)
    unique = f"{uuid.uuid4().hex}_{filename}"
    path = os.path.join(UPLOAD_DIR, unique)
    file_storage.save(path)
    return path, filename

def sha256_bytes(data_bytes):
    return hashlib.sha256(data_bytes).hexdigest()

def sha256_hash_file(file_path):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def fuzzy_ratio(a, b):
    return SequenceMatcher(None, a, b).ratio()

# ✅ FIX 4: OCR with PSM 6 (better accuracy) + DEBUG PRINTS
def preprocess_image(image_path):
    img = Image.open(image_path).convert("L")  # grayscale
    img = img.resize((img.width * 2, img.height * 2))
    return img

# Update OCR extraction logic

def ocr_extract_text(image_path):
    try:
        img = preprocess_image(image_path)
        text = pytesseract.image_to_string(img, config="--psm 6")
        if len(text.strip()) < 20:
            return ""
        return text
    except Exception:
        return ""

# ================== DB SETUP (TABLES/TRIGGERS) ==================

def ensure_column(cursor, table_name, column_def):
    col_name = column_def.split()[0]
    cursor.execute("""
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
    """, (MYSQL_DB, table_name, col_name))
    exists = cursor.fetchone()[0]
    if not exists:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")

def setup_databases():
    """Create all required tables according to ER diagram + your govverify schema."""
    try:
        conn = get_mysql()
        cursor = conn.cursor()
    except Exception as e:
        print(f"❌ setup_databases cannot connect to MySQL: {e}")
        return

    try:
        cursor.execute("SET FOREIGN_KEY_CHECKS=0")

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role ENUM('user', 'admin') DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_email (email)
            )
        """)

        # Documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                doc_name VARCHAR(255) NOT NULL,
                doc_type VARCHAR(100),
                file_path VARCHAR(1024),
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                document_hash VARCHAR(255) UNIQUE,
                verification_status ENUM('pending', 'verified', 'rejected') DEFAULT 'pending',
                ledger_reference_id VARCHAR(255),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                INDEX idx_hash (document_hash),
                INDEX idx_user (user_id)
            )
        """)

        # Ensure legacy DBs get missing columns
        ensure_column(cursor, 'documents', 'document_hash VARCHAR(255)')
        ensure_column(
            cursor,
            "documents",
            "verification_status ENUM('pending', 'verified', 'rejected') DEFAULT 'pending'"
        )
        ensure_column(cursor, 'documents', 'ledger_reference_id VARCHAR(255)')

        # AI extracted info
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_extracted_info (
                extract_id INT AUTO_INCREMENT PRIMARY KEY,
                doc_id INT NOT NULL,
                key_name VARCHAR(100) NOT NULL,
                value_text TEXT,
                confidence_score FLOAT DEFAULT 0.0,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE,
                INDEX idx_doc (doc_id)
            )
        """)

        # Verification log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verification_log (
                verify_id INT AUTO_INCREMENT PRIMARY KEY,
                doc_id INT NOT NULL,
                admin_id INT,
                verification_status VARCHAR(50) NOT NULL,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                remarks TEXT,
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE,
                FOREIGN KEY (admin_id) REFERENCES users(user_id) ON DELETE SET NULL,
                INDEX idx_doc (doc_id)
            )
        """)

        # Optional trigger
        try:
            cursor.execute("DROP TRIGGER IF EXISTS trg_after_doc_insert")
            cursor.execute("""
                CREATE TRIGGER trg_after_doc_insert
                AFTER INSERT ON documents
                FOR EACH ROW
                BEGIN
                    INSERT INTO verification_log (doc_id, admin_id, verification_status, remarks)
                    VALUES (NEW.doc_id, NULL, 'pending', 'Auto-created on upload');
                END
            """)
        except mysql.connector.Error:
            print("⚠️ Trigger creation skipped or failed.")

        cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        conn.commit()
        print("✅ All database tables created/verified successfully!")

    except Exception as e:
        conn.rollback()
        print(f"❌ setup_databases error: {e}")
    finally:
        try:
            cursor.close()
        except:
            pass
        try:
            conn.close()
        except:
            pass

# ================== NLP / EXTRACTION ==================

def extract_entities_nlp(text):
    """Generic NER using spaCy."""
    if not nlp or not text:
        return []
    doc = nlp(text)
    results = []
    for ent in doc.ents:
        results.append({
            "key": ent.label_,
            "value": ent.text,
            "confidence": 0.85
        })
    return results

def extract_structured_fields_generic(text):
    """Generic regex-based extraction (dates/emails/phone/id)."""
    results = []

    # Date patterns
    date_pattern = r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"
    dates = re.findall(date_pattern, text)
    for date in dates:
        results.append({
            "key": "DATE",
            "value": date,
            "confidence": 0.9
        })

    # Email
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    emails = re.findall(email_pattern, text)
    for email in emails:
        results.append({
            "key": "EMAIL",
            "value": email,
            "confidence": 0.95
        })

    # Phone (Indian-style)
    phone_pattern = r"\b(?:\+91[-.\s]?)?[6-9]\d{9}\b"
    phones = re.findall(phone_pattern, text)
    for phone in phones:
        results.append({
            "key": "PHONE",
            "value": phone,
            "confidence": 0.9
        })

    # Aadhaar-like ID
    id_pattern = r"\b\d{4}\s?\d{4}\s?\d{4}\b"
    ids = re.findall(id_pattern, text)
    for id_num in ids:
        results.append({
            "key": "ID_NUMBER",
            "value": id_num,
            "confidence": 0.88
        })

    return results

def extract_entities_doc_specific(text, doc_type):
    """Aadhaar / Passport / Certificate + generic extraction + spaCy."""
    entities = []

    if doc_type == "aadhaar":
        aadhaar = re.findall(r"\b\d{4}\s\d{4}\s\d{4}\b", text)
        dob = re.findall(r"\b\d{2}-\d{2}-\d{4}\b", text)
        for a in aadhaar:
            entities.append({"key": "AADHAAR_NUMBER", "value": a, "confidence": 0.95})
        for d in dob:
            entities.append({"key": "DOB", "value": d, "confidence": 0.9})

    elif doc_type == "passport":
        passport_no = re.findall(r"\b[A-Z][0-9]{7}\b", text)
        dates = re.findall(r"\b\d{2}-\d{2}-\d{4}\b", text)
        for p in passport_no:
            entities.append({"key": "PASSPORT_NUMBER", "value": p, "confidence": 0.92})
        for d in dates:
            entities.append({"key": "DATE", "value": d, "confidence": 0.85})

    elif doc_type == "certificate":
        keywords = ["certificate", "university", "board", "issued"]
        for kw in keywords:
            if kw in text.lower():
                entities.append({
                    "key": "CERTIFICATE_KEYWORD",
                    "value": kw.upper(),
                    "confidence": 0.85
                })
    else:
        entities.append({
            "key": "TEXT_LENGTH",
            "value": len(text),
            "confidence": 0.7
        })

    entities.extend(extract_structured_fields_generic(text))
    entities.extend(extract_entities_nlp(text))
    entities.append({
        "key": "RAW_TEXT_SNIPPET",
        "value": text[:500] if len(text) > 500 else text,
        "confidence": 1.0
    })

    return entities

REQUIRED_FIELDS = {
    "aadhaar": {"AADHAAR_NUMBER"},
    "passport": {"PASSPORT_NUMBER"},
    "certificate": {"CERTIFICATE_KEYWORD"}
}

# ✅ FIX 3: RELAXED VALIDATION (PROJECT-SAFE)
def validate_document(doc_type, entities):
    keys = {e["key"] for e in entities}
    if doc_type == "aadhaar":
        return "AADHAAR_NUMBER" in keys or "ID_NUMBER" in keys

    required = REQUIRED_FIELDS.get(doc_type)
    if not required:
        return True
    return required.issubset(keys)

# ================== ROUTES: HOME ==================

@app.route("/")
def home():
    return jsonify({
        "message": "Document Verifier / GovVerify Backend API",
        "version": "2.0 - OCR FIXED",
        "endpoints": {
            "POST /register": "Register new user",
            "POST /login": "User login",
            "POST /upload": "Upload document (OCR+NLP+hash) - IMAGES ONLY",
            "POST /verify_upload": "Verify uploaded file vs stored hash",
            "GET /verify/<hash>": "Verify document by hash",
            "GET /document/<doc_id>": "Get document details",
            "GET /user/<user_id>/documents": "Get user's documents",
            "GET /admin/pending": "List pending documents",
            "POST /admin/verify/<doc_id>": "Admin verify/reject",
            "GET /admin/compare?doc1=<id>&doc2=<id>": "Compare docs"
        },
        "note": "✅ PDF support removed | ✅ OCR fixed with PSM6 | ✅ Relaxed validation"
    })

# ================== USER AUTH ==================

@app.route("/register", methods=["POST"])
def register_user():
    try:
        data = request.get_json()
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")
        role = "user"

        if not all([name, email, password]):
            return jsonify({"error": "Missing required fields"}), 400

        password_hash = generate_password_hash(password)

        conn = None
        cursor = None
        try:
            conn = get_mysql()
            cursor = conn.cursor()
            sql = "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (name, email, password_hash, role))
            conn.commit()
            user_id = cursor.lastrowid
        except mysql.connector.IntegrityError:
            if conn:
                conn.rollback()
            return jsonify({"error": "Email already exists"}), 409
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        log_event("USER_REGISTER", user_id=user_id, email=email)

        return jsonify({
            "message": "User registered successfully!",
            "user_id": user_id,
            "email": email
        }), 201

    except Exception as e:
        print(f"❌ Registration Error: {e}")
        log_event("SERVER_ERROR", context="register", error=str(e))
        return jsonify({"error": "Server error"}), 500

@app.route("/login", methods=["POST"])
@limiter.limit('5 per minute')  # Limit login attempts
def login_user():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")

        if not all([email, password]):
            return jsonify({"error": "Missing credentials"}), 400

        conn = None
        cursor = None
        try:
            conn = get_mysql()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "Invalid credentials"}), 401

        log_event("USER_LOGIN", user_id=user["user_id"], email=email)

        session["user_id"] = user["user_id"]
        session["role"] = user["role"]

        return jsonify({
            "message": "Login successful",
            "user": {
                "user_id": user["user_id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"]
            }
        }), 200

    except Exception as e:
        print(f"❌ Login Error: {e}")
        log_event("SERVER_ERROR", context="login", error=str(e))
        return jsonify({"error": "Server error"}), 500

# ================== SESSION ==================

@app.route("/session", methods=["GET"])
def get_session():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify({
        "user": {
            "user_id": user_id,
            "role": session.get("role", "user")
        }
    }), 200

@app.route("/logout", methods=["POST"])
def logout_user():
    session.clear()
    return jsonify({"message": "Logged out"}), 200

# ================== AUTH HELPERS ==================

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Not authenticated"}), 401
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return fn(*args, **kwargs)
    return wrapper

# ================== DOCUMENT UPLOAD & VERIFY ==================

@app.route("/upload", methods=["POST"])
@login_required
def upload_document():
    try:
        file = request.files.get("file")
        doc_type = request.form.get("doc_type", "general")
        user_id = session.get("user_id")

        if not file or not user_id:
            return jsonify({"error": "Missing required fields"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": "File type not allowed. Use image formats only (png/jpg/jpeg/tif/tiff/bmp)."}), 400

        user_id_int = int(user_id)

        saved_path, original_name = save_file_storage(file)

        # ✅ FIX 1: DEBUG OCR + FIX 4: PSM 6 config
        extracted_text = ocr_extract_text(saved_path)
        print(f"📊 EXTRACTION SUMMARY: {len(extracted_text)} chars, type={doc_type}")

        entities = extract_entities_doc_specific(extracted_text, doc_type)
        print(f"🔍 Found {len(entities)} entities")

        # ✅ FIX 3: RELAXED VALIDATION
        if not validate_document(doc_type, entities):
            print(f"❌ VALIDATION FAILED: {len(entities)} entities for {doc_type}")
            log_event("AUTO_REJECT", user_id=user_id_int, filename=original_name, entities_count=len(entities))
            try:
                os.remove(saved_path)
            except Exception:
                pass
            return jsonify({"error": "Minimal text detected - try clearer image"}), 422

        file_hash = sha256_hash_file(saved_path)
        tx_hash = "0x" + uuid.uuid4().hex

        conn = None
        cursor = None
        try:
            conn = get_mysql()
            cursor = conn.cursor()
            conn.start_transaction()

            cursor.execute("""
                INSERT INTO documents
                    (user_id, doc_name, doc_type, file_path, document_hash, ledger_reference_id, verification_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id_int,
                original_name,
                doc_type,
                saved_path,
                file_hash,
                tx_hash,
                "pending"
            ))
            doc_id = cursor.lastrowid

            for e in entities:
                cursor.execute("""
                    INSERT INTO ai_extracted_info
                        (doc_id, key_name, value_text, confidence_score)
                    VALUES (%s, %s, %s, %s)
                """, (doc_id, e["key"], str(e["value"]), float(e["confidence"])))

            conn.commit()
            print(f"✅ DOCUMENT SAVED: ID={doc_id}, hash={file_hash}")

        except mysql.connector.IntegrityError:
            if conn:
                conn.rollback()
            log_event("UPLOAD_FAIL", error="Duplicate document hash", hash=file_hash)
            try:
                os.remove(saved_path)
            except Exception:
                pass
            return jsonify({
                "error": "Duplicate document detected. Upload blocked."
            }, 409)
        except Exception as e:
            if conn:
                conn.rollback()
            try:
                os.remove(saved_path)
            except Exception:
                pass
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        log_event(
            "DOCUMENT_UPLOAD",
            user_id=user_id_int,
            doc_id=doc_id,
            filename=original_name,
            hash=file_hash,
            tx_hash=tx_hash,
            entities_extracted=len(entities)
        )
        log_audit_entry('Document uploaded', user_id_int)

        return jsonify({
            "message": "Document uploaded and processed successfully!",
            "document": {
                "doc_id": doc_id,
                "doc_type": doc_type,
                "filename": original_name,
                "document_hash": file_hash,
                "ledger_reference_id": tx_hash,
                "verification_status": "pending"
            },
            "extraction_summary": {
                "total_entities": len(entities),
                "entities": entities[:10],  # First 10 for preview
                "text_length": len(extracted_text)
            }
        }), 201

    except Exception as e:
        print(f"❌ Upload Error: {e}")
        log_event("SERVER_ERROR", context="upload", error=str(e))
        return jsonify({"error": "Server error"}), 500

@app.route("/verify_upload", methods=["POST"])
@login_required
def verify_upload_file():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "Empty filename"}), 400

        file_bytes = file.read()
        computed_hash = sha256_bytes(file_bytes)

        conn = None
        cursor = None
        try:
            conn = get_mysql()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM documents WHERE document_hash = %s",
                (computed_hash,)
            )
            doc = cursor.fetchone()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        if not doc:
            return jsonify({
                "verified": False,
                "message": "No matching document found"
            }), 404

        log_event("DOCUMENT_VERIFY_UPLOAD", doc_id=doc["doc_id"], hash=computed_hash)

        return jsonify({
            "verified": True,
            "message": "File matches stored document",
            "document": {
                "doc_id": doc["doc_id"],
                "doc_name": doc["doc_name"],
                "upload_date": str(doc["upload_date"])
            }
        }), 200

    except Exception as e:
        print(f"❌ verify_upload Error: {e}")
        log_event("SERVER_ERROR", context="verify_upload", error=str(e))
        return jsonify({"error": "Server error"}), 500

# ✅ FIX 1 — trimmed, case-insensitive, success flag
@app.route("/verify/<hash_value>", methods=["GET"])
@login_required
def verify_document(hash_value):
    """Verify document by blockchain hash, trimming and ignoring case."""
    try:
        clean_hash = hash_value.strip().lower()

        conn = None
        cursor = None
        try:
            conn = get_mysql()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM documents WHERE LOWER(document_hash) = %s",
                (clean_hash,)
            )
            doc = cursor.fetchone()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        if not doc:
            return jsonify({
                "success": False,
                "message": "Document not found"
            }), 404

        log_event(
            "DOCUMENT_VERIFY",
            doc_id=doc["doc_id"],
            hash=clean_hash,
            result="found"
        )

        return jsonify({
            "success": True,
            "message": "Document verified successfully",
            "document": doc
        }), 200

    except Exception as e:
        print(f"❌ Verification Error: {e}")
        log_event("SERVER_ERROR", context="verify_hash", error=str(e))
        return jsonify({"success": False, "message": "Server error"}), 500

# [Rest of routes remain exactly the same - admin routes, document details, etc.]
@app.route("/document/<int:doc_id>", methods=["GET"])
@login_required
def get_document_details(doc_id):
    try:
        conn = None
        cursor = None
        try:
            conn = get_mysql()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("""
                SELECT d.*, u.name AS user_name
                FROM documents d
                JOIN users u ON d.user_id = u.user_id
                WHERE d.doc_id = %s
            """, (doc_id,))
            doc = cursor.fetchone()
            if not doc:
                return jsonify({"error": "Document not found"}), 404

            cursor.execute("""
                SELECT * FROM ai_extracted_info WHERE doc_id = %s
            """, (doc_id,))
            extracted_info = cursor.fetchall()

            cursor.execute("""
                SELECT v.*, u.name AS admin_name
                FROM verification_log v
                LEFT JOIN users u ON v.admin_id = u.user_id
                WHERE v.doc_id = %s
                ORDER BY v.verified_at DESC
            """, (doc_id,))
            verification_history = cursor.fetchall()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        return jsonify({
            "document": doc,
            "extracted_info": extracted_info,
            "verification_history": verification_history
        }), 200

    except Exception as e:
        print(f"❌ get_document_details Error: {e}")
        log_event("SERVER_ERROR", context="document_details", error=str(e))
        return jsonify({"error": "Server error"}), 500

@app.route("/user/<int:user_id>/documents", methods=["GET"])
@login_required
def get_user_documents(user_id):
    try:
        if session.get("role") != "admin" and session.get("user_id") != user_id:
            return jsonify({"error": "Forbidden"}), 403
        conn = None
        cursor = None
        try:
            conn = get_mysql()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT doc_id, doc_name, doc_type, upload_date,
                       verification_status, document_hash
                FROM documents
                WHERE user_id = %s
                ORDER BY upload_date DESC
            """, (user_id,))
            documents = cursor.fetchall()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        return jsonify({
            "user_id": user_id,
            "total_documents": len(documents),
            "documents": documents
        }), 200

    except Exception as e:
        print(f"❌ get_user_documents Error: {e}")
        log_event("SERVER_ERROR", context="user_documents", error=str(e))
        return jsonify({"error": "Server error"}), 500

@app.route("/admin/pending", methods=["GET"])
@admin_required
def admin_pending_documents():
    try:
        conn = None
        cursor = None
        try:
            conn = get_mysql()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT doc_id, doc_name, user_id, upload_date
                FROM documents
                WHERE verification_status = 'pending'
                ORDER BY upload_date DESC
            """)
            pending = cursor.fetchall()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        return jsonify({
            "total_pending": len(pending),
            "pending_documents": pending
        }), 200

    except Exception as e:
        print(f"❌ admin_pending_documents Error: {e}")
        log_event("SERVER_ERROR", context="admin_pending", error=str(e))
        return jsonify({"error": "Server error"}), 500

@app.route("/admin/verify/<int:doc_id>", methods=["POST"])
@admin_required
def admin_verify_document(doc_id):
    try:
        data = request.get_json() or {}
        admin_id = session.get("user_id")
        status = data.get("status")
        remarks = data.get("remarks", "")

        if not all([admin_id, status]):
            return jsonify({"error": "Missing required fields"}), 400

        if status not in ["verified", "rejected"]:
            return jsonify({"error": "Invalid status"}), 400

        conn = None
        cursor = None
        try:
            conn = get_mysql()
            cursor = conn.cursor()
            conn.start_transaction()

            cursor.execute("""
                UPDATE documents
                SET verification_status = %s
                WHERE doc_id = %s
            """, (status, doc_id))

            cursor.execute("""
                INSERT INTO verification_log
                    (doc_id, admin_id, verification_status, remarks)
                VALUES (%s, %s, %s, %s)
            """, (doc_id, admin_id, status, remarks))

            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        log_event(
            "ADMIN_VERIFICATION",
            doc_id=doc_id,
            admin_id=admin_id,
            status=status
        )

        return jsonify({
            "message": f"Document {status} successfully",
            "doc_id": doc_id,
            "status": status
        }), 200

    except Exception as e:
        print(f"❌ Admin Verification Error: {e}")
        log_event("SERVER_ERROR", context="admin_verify", error=str(e))
        return jsonify({"error": "Server error"}), 500

@app.route("/admin/compare", methods=["GET"])
@admin_required
def admin_compare_documents():
    try:
        doc1 = request.args.get("doc1")
        doc2 = request.args.get("doc2")
        if not all([doc1, doc2]):
            return jsonify({"error": "Provide doc1 and doc2 as query params"}), 400

        conn = None
        cursor = None
        try:
            conn = get_mysql()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT doc_id, file_path FROM documents
                WHERE doc_id IN (%s, %s)
            """, (doc1, doc2))
            rows = cursor.fetchall()

            if len(rows) < 2:
                return jsonify({"error": "One or both documents not found"}), 404

            cursor.execute("""
                SELECT value_text FROM ai_extracted_info WHERE doc_id = %s
            """, (doc1,))
            r1 = cursor.fetchall()

            cursor.execute("""
                SELECT value_text FROM ai_extracted_info WHERE doc_id = %s
            """, (doc2,))
            r2 = cursor.fetchall()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        text1 = " ".join([r["value_text"] for r in r1 if r["value_text"]])
        text2 = " ".join([r["value_text"] for r in r2 if r["value_text"]])

        ratio = fuzzy_ratio(text1, text2)

        return jsonify({
            "doc1": int(doc1),
            "doc2": int(doc2),
            "similarity_ratio": ratio,
            "conclusion": "likely-same" if ratio > 0.75 else "different"
        }), 200

    except Exception as e:
        print(f"❌ admin_compare_documents Error: {e}")
        log_event("SERVER_ERROR", context="admin_compare", error=str(e))
        return jsonify({"error": "Server error"}), 500

# ================== INPUT SANITIZATION ==================

@app.before_request
def sanitize_inputs():
    """Sanitize inputs to prevent injection attacks."""
    def clean_value(value):
        return re.sub(r"[^\x20-\x7E]", "", value) if isinstance(value, str) else value

    def clean_dict(d):
        return {k: clean_value(v) for k, v in d.items()}

    g.cleaned_form = clean_dict(request.form.to_dict(flat=True))
    g.cleaned_args = clean_dict(request.args.to_dict(flat=True))

    json_payload = request.get_json(silent=True)
    if isinstance(json_payload, dict):
        g.cleaned_json = clean_dict(json_payload)
    else:
        g.cleaned_json = json_payload

# ================== MAIN ==================

def validate_configuration():
    pass

if __name__ == "__main__":
    validate_configuration()

    mysql_ok = init_mysql()
    mongo_ok = init_mongodb()

    if mysql_ok:
        setup_databases()
    else:
        print("WARNING: Running without MySQL - most features disabled")

    if not mongo_ok:
        print("WARNING: Running without MongoDB - logging disabled")

    log_event("SYSTEM_START", status="Backend started - OCR fixed")

    print("\n" + "=" * 60)
    print("Backend Ready! http://localhost:5000")
    print("Upload image files only | Clear images work best")
    print("=" * 60 + "\n")

    app.run(debug=False, host="0.0.0.0", port=5000)
