
# 📚 RAG Admin Backend API Documentation

Base URL: `http://<YOUR_PUBLIC_IP>/`

This backend manages **administrators, documents, and syllabus mappings** for the RAG-based education platform.

---

## 🔐 Authentication (Admin)

### ➤ Register Admin
**POST** `/admin/register`  
Registers a new admin account.

**Body (JSON):**
```json
{
  "username": "admin1",
  "email": "admin@example.com",
  "password": "123456"
}
```

**Response:**
```json
{
  "message": "Admin registered successfully"
}
```

---

### ➤ Login Admin
**POST** `/admin/login`  
Authenticate admin and get JWT token.

**Body (JSON):**
```json
{
  "email": "admin@example.com",
  "password": "123456"
}
```

**Response:**
```json
{
  "access_token": "<JWT_TOKEN>"
}
```

---

### ➤ Logout Admin
**POST** `/admin/logout`

**Response:**
```json
{
  "message": "Admin logged out successfully"
}
```

---

## 👤 Admin Profile (JWT Required)

### ➤ Get Profile
**GET** `/admin/profile`

**Headers:**
```
Authorization: Bearer <JWT_TOKEN>
```

**Response:**
```json
{
  "username": "admin1",
  "email": "admin@example.com",
  "role": "admin",
  "status": "active"
}
```

---

### ➤ Update Profile
**PUT** `/admin/update-profile`

**Headers:**
```
Authorization: Bearer <JWT_TOKEN>
```

**Body (JSON):**
```json
{
  "username": "new_admin_name"
}
```

**Response:**
```json
{
  "message": "Admin profile updated"
}
```

---

## 📤 Document Upload

### ➤ Upload Document
**POST** `/admin/upload`

**Form Data:**
| Key | Value |
|----|------|
| file | document.pdf |
| class | 10 |
| board | stateboard |
| subject | Science |
| group | Biology (optional) |

**Response:**
```json
{
  "message": "Document uploaded successfully",
  "document_id": "abc123-uuid"
}
```

---

## 📄 Documents Management

### ➤ Get Documents (Filter + Limit)
**GET** `/admin/documents`

**Query Params (Optional):**
- `board`
- `class`
- `subject`
- `limit` (default: 20)

**Example:**
```
/admin/documents?board=stateboard&class=10&limit=5
```

**Response:**
```json
[
  {
    "document_id": "abc123",
    "filename": "science.pdf",
    "class": "10",
    "board": "stateboard",
    "subject": "Science",
    "group": null
  }
]
```

---

### ➤ Update Document
**PUT** `/admin/document/<document_id>`

**Body (JSON):**
```json
{
  "subject": "Biology"
}
```

**Response:**
```json
{
  "message": "Document updated successfully"
}
```

---

### ➤ Delete Document
**DELETE** `/admin/document/<document_id>`

**Response:**
```json
{
  "message": "Document deleted successfully"
}
```

---

## ⚙️ Deployment Summary

- Server: **AWS EC2**
- Web Server: **Nginx**
- App Server: **Gunicorn**
- Vector DB: **Pinecone**
- Database: **MongoDB Atlas**
- Auth: **JWT**
- Embeddings: **Sentence Transformers (CPU)**

---

## 🚀 Auto Start (systemd)

Service: `rag-admin.service`

```bash
sudo systemctl start rag-admin
sudo systemctl enable rag-admin
sudo systemctl status rag-admin
```

---

## 🌐 Nginx Port Mapping

| Port | Purpose |
|------|--------|
| 80 | Public API |
| 6000 | Flask / Gunicorn |

---

## 📌 Notes

- JWT required only for:
  - `/admin/profile`
  - `/admin/update-profile`
- Upload & document management endpoints are public.
- Pinecone stores embeddings; MongoDB stores metadata.
- No student queries handled here.

---

🎉 **Admin backend is production-ready.**
