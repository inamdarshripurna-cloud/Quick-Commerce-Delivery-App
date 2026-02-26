import json
import uuid
from datetime import datetime
from firebase_functions import https_fn, options
from firebase_admin import firestore, initialize_app, storage
from werkzeug.utils import secure_filename

# ===================== LAZY FIREBASE INIT =====================
_initialized = False
_db = None
_storage_bucket = None

def get_db():
    global _initialized, _db
    if not _initialized:
        initialize_app()
        _db = firestore.client()
        _initialized = True
    return _db

def get_storage_bucket():
    global _storage_bucket
    if _storage_bucket is None:
        _storage_bucket = storage.bucket()
    return _storage_bucket

# ===================== HELPERS =====================
def json_response(data, status=200):
    def serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    return https_fn.Response(
        json.dumps(data, default=serializer),
        status=status,
        headers={
            "Content-Type": "application/json"
        }
    )

# ===================== FUNCTION OPTIONS =====================
options.set_global_options(region="us-central1", max_instances=10)

# ===================== MAIN API =====================
@https_fn.on_request(
    cors=options.CorsOptions(
        cors_origins="*",
        cors_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )
)
def shri_api(req: https_fn.Request) -> https_fn.Response:
    db = get_db()

    if req.method == "OPTIONS":
        return https_fn.Response("", status=204)

    path = req.path.strip("/")
    method = req.method
    data = req.get_json(silent=True) or {}

    try:

        # ================= ROOT =================
        if path == "":
            return json_response({"status": "success", "message": "Shri Backend API running"})

        # ================= ADMIN LOGIN =================
        if path == "shri_admin_login" and method == "POST":
            email = data.get("email")
            password = data.get("password")

            admins = db.collection("shri_admins").where("email", "==", email).limit(1).get()
            if admins and admins[0].to_dict().get("password") == password:
                return json_response({
                    "status": "success",
                    "admin": {"email": email}
                })
            return json_response({"status": "fail", "message": "Invalid credentials"}, 401)

        # ================= ADMIN ADD USER =================
        if path == "shri_admin_add_user" and method == "POST":
            if db.collection("shri_users").where("mobile", "==", data["mobile"]).limit(1).get():
                return json_response({"status": "fail", "message": "Mobile exists"}, 400)

            db.collection("shri_users").add({
                "name": data["name"],
                "mobile": data["mobile"],
                "email": data.get("email"),
                "location": data.get("location"),
                "password": data.get("password", "default123"),
                "role": "user",
                "created_at": datetime.utcnow()
            })
            return json_response({"status": "success", "message": "User added"})

        # ================= ADMIN VIEW USERS =================
        if path == "shri_admin_view_all_users" and method == "GET":
            users = [{**u.to_dict(), "id": u.id} for u in db.collection("shri_users").stream()]
            return json_response({"status": "success", "users": users})

        # ================= ADMIN UPDATE USER =================
        if path.startswith("shri_admin_update_user/") and method == "PUT":
            mobile = path.split("/")[-1]
            docs = db.collection("shri_users").where("mobile", "==", mobile).limit(1).get()
            if not docs:
                return json_response({"status": "fail", "message": "User not found"}, 404)

            db.collection("shri_users").document(docs[0].id).update(data)
            return json_response({"status": "success", "message": "User updated"})

        # ================= ADMIN DELETE USER =================
        if path.startswith("shri_admin_delete_user/") and method == "DELETE":
            mobile = path.split("/")[-1]
            docs = db.collection("shri_users").where("mobile", "==", mobile).limit(1).get()
            if not docs:
                return json_response({"status": "fail", "message": "User not found"}, 404)

            db.collection("shri_users").document(docs[0].id).delete()
            return json_response({"status": "success", "message": "User deleted"})

        # ================= ADMIN VIEW ORDERS =================
        if path == "shri_admin_view_all_orders" and method == "GET":
            orders = [{**o.to_dict(), "id": o.id} for o in db.collection("shri_orders").stream()]
            return json_response({"status": "success", "orders": orders})

        # ================= USER REGISTER =================
        if path == "shri_user_register" and method == "POST":
            if db.collection("shri_users").where("mobile", "==", data["mobile"]).limit(1).get():
                return json_response({"status": "fail", "message": "Mobile exists"}, 400)

            db.collection("shri_users").add({
                "name": data["name"],
                "mobile": data["mobile"],
                "email": data.get("email"),
                "location": data.get("location"),
                "password": data.get("password"),
                "role": "user",
                "created_at": datetime.utcnow()
            })

            return json_response({"status": "success", "message": "Registered"})

        # ================= USER LOGIN =================
        if path == "shri_user_login" and method == "POST":
            docs = db.collection("shri_users").where("mobile", "==", data["mobile"]).limit(1).get()
            if docs and docs[0].to_dict().get("password") == data["password"]:
                return json_response({"status": "success", "user": docs[0].to_dict()})
            return json_response({"status": "fail", "message": "Invalid credentials"}, 401)

        # ================= PRODUCTS =================
        if path == "shri_add_product" and method == "POST":
            db.collection("shri_products").add({
                **data,
                "created_at": datetime.utcnow()
            })
            return json_response({"status": "success", "message": "Product added"})

        if path.startswith("shri_admin_edit_products/") and method == "PUT":
            product_id = path.split("/")[-1]
            db.collection("shri_products").document(product_id).update({
                **data,
                "updated_at": datetime.utcnow()
            })
            return json_response({"status": "success", "message": "Product updated"})

        if path == "shri_view_products" and method == "GET":
            products = [{**p.to_dict(), "id": p.id} for p in db.collection("shri_products").stream()]
            return json_response({"status": "success", "products": products})

        # ================= CART =================
        if path == "shri_add_to_cart" and method == "POST":
            db.collection("shri_cart").add({
                "user_id": data.get("user_id"),
                "product_id": data.get("product_id"),
                "product_name": data.get("product_name"),
                "quantity": data.get("quantity", 1),
                "price": data.get("price")
            })
            return json_response({"status": "success", "message": "Added to cart"})

        if path == "shri_view_cart" and method == "GET":
            user_id = req.args.get("user_id")
            cart = [
                {**c.to_dict(), "id": c.id}
                for c in db.collection("shri_cart").where("user_id", "==", user_id).stream()
            ]
            return json_response({"status": "success", "cart": cart})

        if path.startswith("shri_remove_from_cart/") and method == "DELETE":
            cart_id = path.split("/")[-1]
            db.collection("shri_cart").document(cart_id).delete()
            return json_response({"status": "success", "message": "Removed from cart"})

        # ================= ORDERS =================
        if path == "shri_place_order" and method == "POST":
            ref = db.collection("shri_orders").add({
                "user_id": data.get("user_id"),
                "items": data.get("items", []),
                "total": data.get("total"),
                "address": data.get("address"),
                "payment_mode": data.get("payment_mode"),
                "status": "placed",
                "ordered_at": datetime.utcnow()
            })
            return json_response({"status": "success", "order_id": ref[1].id})

        if path == "shri_view_orders" and method == "GET":
            user_id = req.args.get("user_id")
            orders = [
                {**o.to_dict(), "id": o.id}
                for o in db.collection("shri_orders").where("user_id", "==", user_id).stream()
            ]
            return json_response({"status": "success", "orders": orders})

        if path.startswith("shri_update_order_status/") and method == "PUT":
            order_id = path.split("/")[-1]
            db.collection("shri_orders").document(order_id).update({
                "status": data.get("status"),
                "updated_at": datetime.utcnow()
            })
            return json_response({"status": "success", "message": "Order updated"})

        # ================= FILE UPLOAD IMAGE =================
        if path == "shri_upload_image" and method == "POST":
            if 'file' not in req.files:
                return json_response({"success": False, "message": "No file provided"}, 400)

            file = req.files['file']

            if file.filename == '':
                return json_response({"success": False, "message": "No file selected"}, 400)

            filename, ext = validate_file(file, "image")

            timestamp = int(datetime.now().timestamp() * 1000)
            unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}.{ext}"
            storage_path = f"shri/{unique_filename}"

            bucket = get_storage_bucket()
            blob = bucket.blob(storage_path)

            blob.upload_from_string(file.read(), content_type=file.content_type)
            blob.make_public()

            return json_response({
                "success": True,
                "url": blob.public_url,
                "uploadedAt": datetime.now().isoformat()
            })

        # ================= FILE UPLOAD PDF =================
        if path == "shri_upload_pdf" and method == "POST":
            if 'file' not in req.files:
                return json_response({"success": False, "message": "No file provided"}, 400)

            file = req.files['file']

            if file.filename == '':
                return json_response({"success": False, "message": "No file selected"}, 400)

            filename, ext = validate_file(file, "pdf")

            timestamp = int(datetime.now().timestamp() * 1000)
            unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}.{ext}"
            storage_path = f"documents/{unique_filename}"

            bucket = get_storage_bucket()
            blob = bucket.blob(storage_path)

            blob.upload_from_string(file.read(), content_type=file.content_type)
            blob.make_public()

            return json_response({
                "success": True,
                "url": blob.public_url,
                "uploadedAt": datetime.now().isoformat()
            })

        return json_response({"status": "fail", "message": "Endpoint not found"}, 404)

    except Exception as e:
        return json_response({"status": "error", "message": str(e)}, 500)


# ================= FILE VALIDATION =================
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
ALLOWED_PDF_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 50 * 1024 * 1024

def validate_file(file, file_type: str = 'image'):
    allowed_extensions = ALLOWED_IMAGE_EXTENSIONS if file_type == 'image' else ALLOWED_PDF_EXTENSIONS

    if file.content_length and file.content_length > MAX_FILE_SIZE:
        raise ValueError(f"File size exceeds {MAX_FILE_SIZE / (1024*1024)}MB limit")

    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    if ext not in allowed_extensions:
        raise ValueError(f"File type .{ext} not allowed. Allowed: {', '.join(allowed_extensions)}")

    return filename, ext