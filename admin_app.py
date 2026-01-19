import os
import uuid
from datetime import timedelta, datetime
from flask import Flask, request, jsonify
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from pypdf import PdfReader
import docx
from sentence_transformers import SentenceTransformer
from groq import Groq
from pinecone import Pinecone
from flask_cors import CORS

# -----------------------------
# Load ENV
# -----------------------------
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# -----------------------------
# Flask Init
# -----------------------------
app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=1)
jwt = JWTManager(app)

# Enable CORS for all origins
CORS(app, resources={r"/*": {"origins": "*"}})
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB

# -----------------------------
# MongoDB Init
# -----------------------------
client = MongoClient(MONGO_URI)
db = client["RAG"]

admins_col = db["admins"]           # NEW
documents_col = db["documents"]     # EXISTING
stateboard_col = db["stateboard"]   # EXISTING
cbse_col = db["cbse"]               # EXISTING

# -----------------------------
# Pinecone Init (NEW SDK)
# -----------------------------
pc = Pinecone(api_key=PINECONE_API_KEY)
INDEX_NAME = "rag-documents"

if INDEX_NAME not in pc.list_indexes().names():
    pc.create_index(
        name=INDEX_NAME,
        dimension=384,
        metric="cosine",
        spec={"serverless": {"cloud": "aws", "region": "us-east-1"}}
    )

index = pc.Index(INDEX_NAME)

# -----------------------------
# Embeddings & Groq
# -----------------------------
embedder = SentenceTransformer("all-MiniLM-L6-v2")
groq_client = Groq(api_key=GROQ_API_KEY)

# -----------------------------
# Utilities (RAG - SAME LOGIC)
# -----------------------------
def load_document(file_path):
    text = ""
    if file_path.endswith(".pdf"):
        reader = PdfReader(file_path)
        for page in reader.pages:
            text += page.extract_text() or ""
    elif file_path.endswith(".docx"):
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    elif file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    return text


def chunk_text(text, chunk_size=500, overlap=100):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def get_embedding(text):
    return embedder.encode(text).tolist()


def store_chunks(chunks, document_id):
    vectors = []
    for i, chunk in enumerate(chunks):
        vectors.append({
            "id": f"{document_id}-{i}",
            "values": get_embedding(chunk),
            "metadata": {
                "text": chunk,
                "document_id": document_id
            }
        })
    index.upsert(vectors)
    
@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
    return response

# -----------------------------
# AUTH (ADMIN)
# -----------------------------
@app.route("/admin/register", methods=["POST"])
def admin_register():
    data = request.json

    if admins_col.find_one({"email": data["email"]}):
        return jsonify({"error": "Admin already exists"}), 400

    admin = {
        "username": data["username"],
        "email": data["email"],
        "password": data["password"],   # ⚠ Hash in production
        "role": "admin",
        "status": "active",
        "created_at": datetime.utcnow()
    }

    admins_col.insert_one(admin)
    return jsonify({"message": "Admin registered successfully"}), 201


@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.json
    admin = admins_col.find_one({
        "email": data["email"],
        "password": data["password"]
    })

    if not admin:
        return jsonify({"error": "Invalid admin credentials"}), 401

    token = create_access_token(identity=str(admin["_id"]))
    return jsonify({"access_token": token})


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    return jsonify({"message": "Admin logged out successfully"})

# -----------------------------
# ADMIN PROFILE (JWT ONLY HERE)
# -----------------------------
@app.route("/admin/profile", methods=["GET"])
@jwt_required()
def admin_profile():
    admin_id = get_jwt_identity()
    admin = admins_col.find_one({"_id": ObjectId(admin_id)})

    return jsonify({
        "username": admin["username"],
        "email": admin["email"],
        "role": admin["role"],
        "status": admin["status"]
    })


@app.route("/admin/update-profile", methods=["PUT"])
@jwt_required()
def update_admin_profile():
    admin_id = get_jwt_identity()
    data = request.json

    admins_col.update_one(
        {"_id": ObjectId(admin_id)},
        {"$set": data}
    )

    return jsonify({"message": "Admin profile updated"})

# -----------------------------
# DOCUMENT UPLOAD (PUBLIC)
# -----------------------------
@app.route("/admin/upload", methods=["POST"])
def admin_upload():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    class_ = request.form.get("class")
    board = request.form.get("board")
    subject = request.form.get("subject")
    group = request.form.get("group")

    os.makedirs("uploads", exist_ok=True)
    path = os.path.join("uploads", file.filename)
    file.save(path)

    text = load_document(path)
    chunks = chunk_text(text)

    document_id = str(uuid.uuid4())
    store_chunks(chunks, document_id)

    documents_col.insert_one({
        "document_id": document_id,
        "filename": file.filename,
        "class": class_,
        "board": board,
        "subject": subject,
        "group": group,
        "uploaded_at": datetime.utcnow()
    })

    target_col = stateboard_col if board == "stateboard" else cbse_col
    target_col.insert_one({
        "class": class_,
        "subject": subject,
        "group": group,
        "document_id": document_id
    })

    return jsonify({
        "message": "Document uploaded successfully",
        "document_id": document_id
    })

# -----------------------------
# GET DOCUMENTS (PUBLIC)
# -----------------------------
@app.route("/admin/documents", methods=["GET"])
def get_documents():
    board = request.args.get("board")
    class_ = request.args.get("class")
    subject = request.args.get("subject")
    limit = int(request.args.get("limit", 20))

    query = {}
    if board:
        query["board"] = board
    if class_:
        query["class"] = class_
    if subject:
        query["subject"] = subject

    docs = documents_col.find(query, {"_id": 0}).limit(limit)
    return jsonify(list(docs))

# -----------------------------
# UPDATE DOCUMENT (PUBLIC)
# -----------------------------
@app.route("/admin/document/<document_id>", methods=["PUT"])
def update_document(document_id):
    data = request.json

    documents_col.update_one(
        {"document_id": document_id},
        {"$set": data}
    )

    return jsonify({"message": "Document updated successfully"})

# -----------------------------
# DELETE DOCUMENT (PUBLIC)
# -----------------------------
@app.route("/admin/document/<document_id>", methods=["DELETE"])
def delete_document(document_id):
    documents_col.delete_one({"document_id": document_id})
    stateboard_col.delete_many({"document_id": document_id})
    cbse_col.delete_many({"document_id": document_id})

    index.delete(filter={"document_id": {"$eq": document_id}})

    return jsonify({"message": "Document deleted successfully"})

# -----------------------------
# GET STATEBOARD DOCUMENTS
# -----------------------------
@app.route("/admin/stateboard/documents", methods=["GET"])
def get_stateboard_documents():
    class_ = request.args.get("class")
    subject = request.args.get("subject")
    group = request.args.get("group")
    limit = int(request.args.get("limit", 20))

    query = {}
    if class_:
        query["class"] = class_
    if subject:
        query["subject"] = subject
    if group:
        query["group"] = group

    state_docs = list(stateboard_col.find(query, {"_id": 0}).limit(limit))

    # Fetch full document details
    document_ids = [doc["document_id"] for doc in state_docs]
    documents = list(documents_col.find(
        {"document_id": {"$in": document_ids}},
        {"_id": 0}
    ))

    return jsonify(documents)

# -----------------------------
# GET CBSE DOCUMENTS
# -----------------------------
@app.route("/admin/cbse/documents", methods=["GET"])
def get_cbse_documents():
    class_ = request.args.get("class")
    subject = request.args.get("subject")
    group = request.args.get("group")
    limit = int(request.args.get("limit", 20))

    query = {}
    if class_:
        query["class"] = class_
    if subject:
        query["subject"] = subject
    if group:
        query["group"] = group

    cbse_docs = list(cbse_col.find(query, {"_id": 0}).limit(limit))

    # Fetch full document details
    document_ids = [doc["document_id"] for doc in cbse_docs]
    documents = list(documents_col.find(
        {"document_id": {"$in": document_ids}},
        {"_id": 0}
    ))

    return jsonify(documents)

# -----------------------------
# RUN SERVER
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6000)
