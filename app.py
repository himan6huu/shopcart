from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
import os, uuid, secrets

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

with app.app_context():
    db.create_all()

# ── Config ─────────────────────────────────────────────────────────────────────
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///shopcart.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Mail config (set these as env vars on Render)
app.config["MAIL_SERVER"]   = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"]     = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"]  = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME", "noreply@shopcart.com")

db   = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"

# ── Models ─────────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(255), nullable=False)
    is_admin   = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders     = db.relationship("Order", backref="user", lazy=True)
    wishlist   = db.relationship("Wishlist", backref="user", lazy=True)
    reset_tokens = db.relationship("PasswordResetToken", backref="user", lazy=True)

class Product(db.Model):
    __tablename__ = "products"
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(120), nullable=False)
    price        = db.Column(db.Float, nullable=False)
    category     = db.Column(db.String(60), nullable=False)
    image        = db.Column(db.String(512), nullable=True)
    stock        = db.Column(db.Integer, default=0)
    description  = db.Column(db.Text, default="")
    rating       = db.Column(db.Float, default=4.0)
    rating_count = db.Column(db.Integer, default=0)
    featured     = db.Column(db.Boolean, default=False)
    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class Order(db.Model):
    __tablename__ = "orders"
    id          = db.Column(db.Integer, primary_key=True)
    order_ref   = db.Column(db.String(20), unique=True, nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    email       = db.Column(db.String(120), nullable=False)
    full_name   = db.Column(db.String(120), nullable=False)
    address     = db.Column(db.String(255), nullable=False)
    city        = db.Column(db.String(80), nullable=False)
    pincode     = db.Column(db.String(20), nullable=False)
    subtotal    = db.Column(db.Float, nullable=False)
    shipping    = db.Column(db.Float, default=0)
    discount    = db.Column(db.Float, default=0)
    coupon_code = db.Column(db.String(30), nullable=True)
    total       = db.Column(db.Float, nullable=False)
    status      = db.Column(db.String(30), default="Confirmed")
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    items       = db.relationship("OrderItem", backref="order", lazy=True)

    def get_timeline(self):
        statuses = ["Confirmed", "Processing", "Shipped", "Delivered"]
        current_idx = statuses.index(self.status) if self.status in statuses else 0
        return [(s, i <= current_idx) for i, s in enumerate(statuses)]

class OrderItem(db.Model):
    __tablename__ = "order_items"
    id            = db.Column(db.Integer, primary_key=True)
    order_id      = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id    = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    product_name  = db.Column(db.String(120), nullable=False)
    product_image = db.Column(db.String(512), nullable=True)
    price         = db.Column(db.Float, nullable=False)
    qty           = db.Column(db.Integer, nullable=False)
    subtotal      = db.Column(db.Float, nullable=False)

class Wishlist(db.Model):
    __tablename__ = "wishlist"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    added_at   = db.Column(db.DateTime, default=datetime.utcnow)
    product    = db.relationship("Product")
    __table_args__ = (db.UniqueConstraint("user_id", "product_id"),)

class Coupon(db.Model):
    __tablename__ = "coupons"
    id           = db.Column(db.Integer, primary_key=True)
    code         = db.Column(db.String(30), unique=True, nullable=False)
    discount_pct = db.Column(db.Float, nullable=False)   # e.g. 10 = 10% off
    min_order    = db.Column(db.Float, default=0)         # minimum cart value
    max_uses     = db.Column(db.Integer, default=100)
    used_count   = db.Column(db.Integer, default=0)
    active       = db.Column(db.Boolean, default=True)
    expires_at   = db.Column(db.DateTime, nullable=True)

class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token      = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used       = db.Column(db.Boolean, default=False)

    def is_valid(self):
        return not self.used and datetime.utcnow() < self.created_at + timedelta(hours=1)

@login_manager.user_loader
def load_user(uid): return User.query.get(int(uid))

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin: abort(403)
        return f(*args, **kwargs)
    return decorated

# ── Seed ──────────────────────────────────────────────────────────────────────
SEED = [
    dict(name="Wireless Headphones",      price=5999,  category="Electronics", rating=4.7, rating_count=342, featured=True,  stock=15, image="https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600", description="Premium ANC, 40-hr battery, foldable design."),
    dict(name="Mechanical Keyboard",      price=9999,  category="Electronics", rating=4.6, rating_count=218, featured=True,  stock=8,  image="https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=600", description="Tactile switches, per-key RGB, TKL layout."),
    dict(name="Ergonomic Mouse",          price=3499,  category="Electronics", rating=4.5, rating_count=189, featured=False, stock=20, image="https://images.unsplash.com/photo-1527814050087-3793815479db?w=600", description="Sculpted grip, silent scroll, 6 DPI levels."),
    dict(name="Webcam 1080p",             price=4999,  category="Electronics", rating=4.4, rating_count=97,  featured=False, stock=10, image="https://images.unsplash.com/photo-1616763355548-1b606f439f86?w=600", description="Auto-focus, dual stereo mic, plug-and-play."),
    dict(name="USB-C Hub 7-in-1",         price=2799,  category="Electronics", rating=4.3, rating_count=154, featured=False, stock=25, image="https://images.unsplash.com/photo-1625895197185-efcec01cffe0?w=600", description="HDMI 4K, 3xUSB-A, SD/microSD, 100W PD."),
    dict(name="Smartwatch Pro",           price=14999, category="Electronics", rating=4.8, rating_count=412, featured=True,  stock=12, image="https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600", description="AMOLED, GPS, heart-rate, 7-day battery."),
    dict(name="Portable SSD 1TB",         price=7499,  category="Electronics", rating=4.6, rating_count=276, featured=False, stock=30, image="https://images.unsplash.com/photo-1597848212624-a19eb35e2651?w=600", description="540 MB/s, USB 3.2, shock-resistant shell."),
    dict(name="Noise-Cancelling Earbuds", price=4299,  category="Electronics", rating=4.5, rating_count=203, featured=False, stock=14, image="https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=600", description="ANC, 28-hr playback, IPX4, transparency mode."),
    dict(name='LED Monitor 24"',          price=13499, category="Electronics", rating=4.7, rating_count=178, featured=True,  stock=7,  image="https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=600", description="Full HD IPS, 75Hz, HDMI + VGA, eye-care."),
    dict(name="Laptop Stand Aluminium",   price=1999,  category="Electronics", rating=4.4, rating_count=143, featured=False, stock=22, image="https://images.unsplash.com/photo-1593642632559-0c6d3fc62b89?w=600", description="Foldable, adjustable 15-50cm, heat dissipation."),
    dict(name="Gaming Headset 7.1",       price=6999,  category="Gaming",      rating=4.6, rating_count=267, featured=True,  stock=10, image="https://images.unsplash.com/photo-1612198188060-c7c2a3b66eae?w=600", description="Virtual 7.1 surround, noise-cancelling mic, RGB."),
    dict(name="Gamepad Controller",       price=4499,  category="Gaming",      rating=4.5, rating_count=198, featured=False, stock=18, image="https://images.unsplash.com/photo-1592840496694-26d035b52b48?w=600", description="Wireless, 20-hr battery, PC & mobile compatible."),
    dict(name="Gaming Chair",             price=22999, category="Gaming",      rating=4.3, rating_count=87,  featured=True,  stock=4,  image="https://images.unsplash.com/photo-1598550476439-6847785fcea6?w=600", description="Lumbar pillow, 4D armrests, 160-degree recline."),
    dict(name="Gaming Mouse Pad XL",      price=1299,  category="Gaming",      rating=4.4, rating_count=132, featured=False, stock=35, image="https://images.unsplash.com/photo-1616588589676-62b3bd4ff6d2?w=600", description="900x400mm, stitched edges, micro-weave surface."),
    dict(name="Mesh Office Chair",        price=17999, category="Office",      rating=4.6, rating_count=156, featured=True,  stock=5,  image="https://images.unsplash.com/photo-1505843513577-22bb7d21e455?w=600", description="Adjustable lumbar, breathable mesh back."),
    dict(name="Desk Lamp LED",            price=1999,  category="Office",      rating=4.3, rating_count=109, featured=False, stock=12, image="https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=600", description="Touch dimmer, 5 colour temps, USB-A charging."),
    dict(name="Standing Desk Mat",        price=2799,  category="Office",      rating=4.4, rating_count=88,  featured=False, stock=30, image="https://images.unsplash.com/photo-1586281380349-632531db7ed4?w=600", description="Anti-fatigue foam, non-slip base, 90x60cm."),
    dict(name="Monitor Arm Single",       price=3299,  category="Office",      rating=4.5, rating_count=121, featured=False, stock=9,  image="https://images.unsplash.com/photo-1593640408182-31c70c8268f5?w=600", description="VESA 75/100, clamp mount, full motion."),
    dict(name="Studio Monitor Speakers",  price=12999, category="Audio",       rating=4.8, rating_count=89,  featured=True,  stock=7,  image="https://images.unsplash.com/photo-1545454675-3531b543be5d?w=600", description="5-inch woofer, studio-grade flat response, pair."),
    dict(name="USB Condenser Mic",        price=5499,  category="Audio",       rating=4.7, rating_count=234, featured=True,  stock=11, image="https://images.unsplash.com/photo-1605405748313-a416a1b84491?w=600", description="Cardioid pattern, 192kHz/24-bit, shock mount."),
    dict(name="Bluetooth Speaker 360",    price=3299,  category="Audio",       rating=4.5, rating_count=178, featured=False, stock=18, image="https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=600", description="IPX5, 12-hr playtime, 360-degree sound."),
    dict(name="Over-Ear Headphones",      price=3999,  category="Audio",       rating=4.4, rating_count=156, featured=False, stock=16, image="https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=600", description="40mm drivers, foldable, 3.5mm + USB-C."),
    dict(name="Phone Tripod Flexible",    price=999,   category="Accessories", rating=4.3, rating_count=145, featured=False, stock=25, image="https://images.unsplash.com/photo-1617575521317-d2974f3b56d2?w=600", description="360-degree ball head, universal clip, 50cm."),
    dict(name="HDMI 2.1 Cable 2m",        price=599,   category="Accessories", rating=4.2, rating_count=88,  featured=False, stock=60, image="https://images.unsplash.com/photo-1555664424-778a1e5e1b48?w=600", description="8K@60Hz, 4K@120Hz, nylon braid, gold tips."),
    dict(name='Laptop Sleeve 15"',        price=1099,  category="Accessories", rating=4.4, rating_count=167, featured=False, stock=22, image="https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=600", description="Water-resistant neoprene, two pockets."),
]

SEED_COUPONS = [
    dict(code="WELCOME10", discount_pct=10, min_order=500,  max_uses=1000),
    dict(code="SAVE20",    discount_pct=20, min_order=2000, max_uses=500),
    dict(code="FLAT15",    discount_pct=15, min_order=1000, max_uses=200),
]

def seed_db():
    if Product.query.count() == 0:
        for p in SEED: db.session.add(Product(**p))
    if User.query.count() == 0:
        db.session.add(User(name="Admin", email="admin@shopcart.com",
                            password=generate_password_hash("admin123"), is_admin=True))
    if Coupon.query.count() == 0:
        for c in SEED_COUPONS: db.session.add(Coupon(**c))
    db.session.commit()

# ── Jinja filters ──────────────────────────────────────────────────────────────
def fmt_inr(amount):
    major = int(amount); paise = f"{amount:.2f}".split(".")[1]; s = str(major)
    if len(s) > 3:
        last3, rest = s[-3:], s[:-3]; groups = []
        while len(rest) > 2: groups.append(rest[-2:]); rest = rest[:-2]
        if rest: groups.append(rest)
        groups.reverse(); s = ",".join(groups) + "," + last3
    return f"₹{s}.{paise}"

def stars(rating):
    full = int(rating); half = 1 if (rating - full) >= 0.5 else 0
    return "★" * full + "½" * half + "☆" * (5 - full - half)

app.jinja_env.filters["inr"]   = fmt_inr
app.jinja_env.filters["stars"] = stars

# ── Cart helpers ───────────────────────────────────────────────────────────────
def get_cart():    return session.setdefault("cart", {})
def cart_count(c): return sum(c.values())
def cart_total(c):
    return round(sum(Product.query.get(int(pid)).price * qty
                     for pid, qty in c.items() if Product.query.get(int(pid))), 2)
def build_items(cart):
    items = []
    for pid, qty in cart.items():
        p = Product.query.get(int(pid))
        if p: items.append({**p.to_dict(), "qty": qty, "subtotal": round(p.price * qty, 2)})
    return items

def get_wishlist_ids():
    if current_user.is_authenticated:
        return {w.product_id for w in current_user.wishlist}
    return set()

# ── Password Reset ─────────────────────────────────────────────────────────────
@app.route("/forgot-password", methods=["GET","POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        user  = User.query.filter_by(email=email).first()
        if user:
            token = secrets.token_urlsafe(48)
            db.session.add(PasswordResetToken(user_id=user.id, token=token))
            db.session.commit()
            reset_url = url_for("reset_password", token=token, _external=True)
            try:
                msg = Message("Reset your ShopCart password", recipients=[email])
                msg.body = f"Hi {user.name},\n\nClick the link below to reset your password (valid 1 hour):\n{reset_url}\n\nIf you didn't request this, ignore this email."
                msg.html = f"""<h2>Reset your ShopCart password</h2>
                <p>Hi {user.name},</p>
                <p>Click the button below to reset your password. The link expires in 1 hour.</p>
                <a href="{reset_url}" style="display:inline-block;padding:12px 24px;background:#2d6a4f;color:#fff;border-radius:8px;text-decoration:none;font-weight:700;">Reset Password</a>
                <p style="color:#888;font-size:12px;margin-top:16px;">If you didn't request this, ignore this email.</p>"""
                mail.send(msg)
            except Exception:
                pass  # silently fail if mail not configured
        flash("If that email exists, a reset link has been sent.", "info")
        return redirect(url_for("login"))
    return render_template("forgot_password.html", cart_count=cart_count(get_cart()))

@app.route("/reset-password/<token>", methods=["GET","POST"])
def reset_password(token):
    record = PasswordResetToken.query.filter_by(token=token).first()
    if not record or not record.is_valid():
        flash("This reset link is invalid or has expired.", "error")
        return redirect(url_for("forgot_password"))
    if request.method == "POST":
        pw  = request.form.get("password","")
        pw2 = request.form.get("password2","")
        if len(pw) < 6:  flash("Password must be at least 6 characters.", "error"); return redirect(request.url)
        if pw != pw2:    flash("Passwords do not match.", "error"); return redirect(request.url)
        record.user.password = generate_password_hash(pw)
        record.used = True
        db.session.commit()
        flash("Password reset! Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("reset_password.html", token=token, cart_count=cart_count(get_cart()))

# ── Wishlist ───────────────────────────────────────────────────────────────────
@app.route("/wishlist")
@login_required
def wishlist():
    items = Wishlist.query.filter_by(user_id=current_user.id).order_by(Wishlist.added_at.desc()).all()
    return render_template("wishlist.html", items=items, cart_count=cart_count(get_cart()))

@app.route("/wishlist/toggle/<int:pid>", methods=["POST"])
@login_required
def toggle_wishlist(pid):
    existing = Wishlist.query.filter_by(user_id=current_user.id, product_id=pid).first()
    if existing:
        db.session.delete(existing); db.session.commit()
        return jsonify({"status": "removed"})
    db.session.add(Wishlist(user_id=current_user.id, product_id=pid))
    db.session.commit()
    return jsonify({"status": "added"})

@app.route("/wishlist/remove/<int:pid>")
@login_required
def remove_wishlist(pid):
    w = Wishlist.query.filter_by(user_id=current_user.id, product_id=pid).first()
    if w: db.session.delete(w); db.session.commit()
    flash("Removed from wishlist.", "info")
    return redirect(url_for("wishlist"))

@app.route("/wishlist/move-to-cart/<int:pid>")
@login_required
def move_to_cart(pid):
    cart = get_cart(); cart[str(pid)] = cart.get(str(pid), 0) + 1; session.modified = True
    w = Wishlist.query.filter_by(user_id=current_user.id, product_id=pid).first()
    if w: db.session.delete(w); db.session.commit()
    flash("Moved to cart!", "success"); return redirect(url_for("wishlist"))

# ── Coupon ─────────────────────────────────────────────────────────────────────
@app.route("/coupon/apply", methods=["POST"])
def apply_coupon():
    code   = request.form.get("coupon_code","").strip().upper()
    total  = cart_total(get_cart())
    coupon = Coupon.query.filter_by(code=code, active=True).first()
    if not coupon:
        return jsonify({"ok": False, "msg": "Invalid coupon code."})
    if coupon.expires_at and datetime.utcnow() > coupon.expires_at:
        return jsonify({"ok": False, "msg": "This coupon has expired."})
    if coupon.used_count >= coupon.max_uses:
        return jsonify({"ok": False, "msg": "This coupon has reached its usage limit."})
    if total < coupon.min_order:
        return jsonify({"ok": False, "msg": f"Minimum order of {fmt_inr(coupon.min_order)} required."})
    discount = round(total * coupon.discount_pct / 100, 2)
    session["coupon"] = {"code": code, "pct": coupon.discount_pct, "discount": discount}
    session.modified = True
    return jsonify({"ok": True, "msg": f"{int(coupon.discount_pct)}% off applied! You save {fmt_inr(discount)}.",
                    "discount": discount, "discount_fmt": fmt_inr(discount),
                    "new_total": fmt_inr(max(0, total - discount))})

@app.route("/coupon/remove")
def remove_coupon():
    session.pop("coupon", None); session.modified = True
    flash("Coupon removed.", "info"); return redirect(url_for("cart"))

# ── Order detail / tracking ────────────────────────────────────────────────────
@app.route("/order/<order_ref>")
@login_required
def order_detail(order_ref):
    order = Order.query.filter_by(order_ref=order_ref).first_or_404()
    if order.user_id != current_user.id and not current_user.is_admin: abort(403)
    return render_template("order_detail.html", order=order, cart_count=cart_count(get_cart()))

# ── Auth ───────────────────────────────────────────────────────────────────────
@app.route("/register", methods=["GET","POST"])
def register():
    if current_user.is_authenticated: return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form.get("name","").strip(); email = request.form.get("email","").strip().lower()
        pw   = request.form.get("password","");     pw2   = request.form.get("password2","")
        if not name or not email or not pw: flash("All fields required.","error"); return redirect(url_for("register"))
        if pw != pw2: flash("Passwords don't match.","error"); return redirect(url_for("register"))
        if User.query.filter_by(email=email).first(): flash("Email already registered.","error"); return redirect(url_for("register"))
        u = User(name=name, email=email, password=generate_password_hash(pw))
        db.session.add(u); db.session.commit(); login_user(u)
        flash(f"Welcome, {name}!","success"); return redirect(url_for("index"))
    return render_template("register.html", cart_count=cart_count(get_cart()))

@app.route("/login", methods=["GET","POST"])
def login():
    if current_user.is_authenticated: return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email","").strip().lower(); pw = request.form.get("password","")
        u = User.query.filter_by(email=email).first()
        if u and check_password_hash(u.password, pw):
            login_user(u, remember=request.form.get("remember"))
            flash(f"Welcome back, {u.name}!","success")
            return redirect(request.args.get("next") or url_for("index"))
        flash("Invalid email or password.","error")
    return render_template("login.html", cart_count=cart_count(get_cart()))

@app.route("/logout")
@login_required
def logout():
    logout_user(); flash("Logged out.","info"); return redirect(url_for("index"))

@app.route("/account")
@login_required
def account():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("account.html", orders=orders, cart_count=cart_count(get_cart()))

# ── Shop ───────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    category=request.args.get("category","All"); search=request.args.get("search","").strip()
    sort=request.args.get("sort","featured");    min_price=request.args.get("min_price","")
    max_price=request.args.get("max_price","");  min_rating=request.args.get("min_rating","")
    q = Product.query
    if category != "All": q = q.filter_by(category=category)
    if search: q = q.filter(db.or_(Product.name.ilike(f"%{search}%"), Product.description.ilike(f"%{search}%")))
    if min_price:
        try: q = q.filter(Product.price >= float(min_price))
        except: pass
    if max_price:
        try: q = q.filter(Product.price <= float(max_price))
        except: pass
    if min_rating:
        try: q = q.filter(Product.rating >= float(min_rating))
        except: pass
    sort_map = {"price_asc":Product.price.asc(),"price_desc":Product.price.desc(),
                "rating":Product.rating.desc(),"name":Product.name.asc(),"featured":Product.featured.desc()}
    products   = q.order_by(sort_map.get(sort, Product.featured.desc())).all()
    categories = ["All"] + sorted({p.category for p in Product.query.all()})
    cart       = get_cart()
    wishlist_ids = get_wishlist_ids()
    return render_template("index.html", products=products, categories=categories,
                           selected_category=category, search=search, sort=sort,
                           min_price=min_price, max_price=max_price, min_rating=min_rating,
                           cart_count=cart_count(cart), wishlist_ids=wishlist_ids)

@app.route("/product/<int:pid>")
def product(pid):
    p = Product.query.get_or_404(pid)
    related = Product.query.filter(Product.category==p.category, Product.id!=pid).limit(4).all()
    in_wishlist = pid in get_wishlist_ids()
    return render_template("product.html", product=p, related=related,
                           in_wishlist=in_wishlist, cart_count=cart_count(get_cart()))

@app.route("/cart/add", methods=["POST"])
def add_to_cart():
    pid=str(request.form.get("product_id")); qty=int(request.form.get("quantity",1))
    p=Product.query.get(int(pid))
    if not p: flash("Not found.","error"); return redirect(url_for("index"))
    cart=get_cart(); new_qty=cart.get(pid,0)+qty
    if new_qty>p.stock: flash(f"Only {p.stock} units available.","error")
    else: cart[pid]=new_qty; session.modified=True; flash(f"'{p.name}' added to cart!","success")
    return redirect(request.referrer or url_for("index"))

@app.route("/cart")
def cart():
    raw=get_cart(); coupon=session.get("coupon",{})
    subtotal=cart_total(raw); discount=coupon.get("discount",0)
    return render_template("cart.html", items=build_items(raw), subtotal=subtotal,
                           discount=discount, coupon=coupon, total=subtotal,
                           cart_count=cart_count(raw))

@app.route("/cart/update", methods=["POST"])
def update_cart():
    pid=str(request.form.get("product_id")); qty=int(request.form.get("quantity",0)); cart=get_cart()
    if qty<=0: cart.pop(pid,None); flash("Item removed.","info")
    else:
        p=Product.query.get(int(pid))
        if p and qty<=p.stock: cart[pid]=qty
        else: flash("Quantity exceeds stock.","error")
    session.modified=True; return redirect(url_for("cart"))

@app.route("/cart/remove/<pid>")
def remove_from_cart(pid):
    cart=get_cart(); cart.pop(str(pid),None); session.modified=True
    flash("Item removed.","info"); return redirect(url_for("cart"))

@app.route("/checkout", methods=["GET","POST"])
def checkout():
    cart=get_cart()
    if not cart: flash("Cart is empty.","info"); return redirect(url_for("index"))
    coupon_data=session.get("coupon",{})
    if request.method=="POST":
        name=request.form.get("name","").strip(); email=request.form.get("email","").strip()
        address=request.form.get("address","").strip(); city=request.form.get("city","").strip()
        pincode=request.form.get("pincode","").strip()
        card=request.form.get("card_number","").replace(" ",""); expiry=request.form.get("expiry","").strip(); cvv=request.form.get("cvv","").strip()
        errors=[]
        if not name: errors.append("Full name required.")
        if "@" not in email: errors.append("Valid email required.")
        if not address: errors.append("Address required.")
        if not city: errors.append("City required.")
        if not pincode: errors.append("PIN code required.")
        if len(card)!=16 or not card.isdigit(): errors.append("Card must be 16 digits.")
        if len(expiry)!=5: errors.append("Expiry must be MM/YY.")
        if len(cvv) not in (3,4): errors.append("CVV must be 3-4 digits.")
        if errors:
            for e in errors: flash(e,"error")
            return render_template("checkout.html", items=build_items(cart), total=cart_total(cart), cart_count=cart_count(cart), coupon=coupon_data)
        subtotal=cart_total(cart); discount=coupon_data.get("discount",0)
        shipping=0 if subtotal>=2000 else 99; total=round(subtotal+shipping-discount,2)
        ref=str(uuid.uuid4())[:8].upper()
        order=Order(order_ref=ref, email=email, full_name=name, address=address, city=city, pincode=pincode,
                    subtotal=subtotal, shipping=shipping, discount=discount,
                    coupon_code=coupon_data.get("code"), total=max(0,total),
                    user_id=current_user.id if current_user.is_authenticated else None)
        db.session.add(order); db.session.flush()
        for pid2,qty2 in cart.items():
            p2=Product.query.get(int(pid2))
            if p2:
                db.session.add(OrderItem(order_id=order.id, product_id=p2.id, product_name=p2.name,
                                         product_image=p2.image, price=p2.price, qty=qty2, subtotal=round(p2.price*qty2,2)))
                p2.stock=max(0,p2.stock-qty2)
        if coupon_data:
            c=Coupon.query.filter_by(code=coupon_data.get("code")).first()
            if c: c.used_count+=1
        db.session.commit()
        session.pop("cart",None); session.pop("coupon",None)
        session["last_order_id"]=order.id
        flash(f"Order #{ref} placed!","success")
        return redirect(url_for("order_success"))
    subtotal=cart_total(cart); discount=coupon_data.get("discount",0); shipping=0 if subtotal>=2000 else 99
    return render_template("checkout.html", items=build_items(cart), subtotal=subtotal,
                           discount=discount, shipping=shipping,
                           total=round(subtotal+shipping-discount,2),
                           cart_count=cart_count(cart), coupon=coupon_data)

@app.route("/order/success")
def order_success():
    oid=session.get("last_order_id"); order=Order.query.get(oid) if oid else None
    if not order: return redirect(url_for("index"))
    return render_template("success.html", order=order, cart_count=0)

# ── Admin ──────────────────────────────────────────────────────────────────────
@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    return render_template("admin/dashboard.html",
                           total_products=Product.query.count(),
                           total_orders=Order.query.count(),
                           total_users=User.query.count(),
                           recent_orders=Order.query.order_by(Order.created_at.desc()).limit(5).all(),
                           cart_count=0)

@app.route("/admin/analytics")
@login_required
@admin_required
def admin_analytics():
    from sqlalchemy import func
    orders = Order.query.all()
    total_revenue = sum(o.total for o in orders)
    total_orders  = len(orders)
    avg_order     = round(total_revenue / total_orders, 2) if total_orders else 0

    # Revenue last 7 days
    daily = {}
    for i in range(6, -1, -1):
        day = (datetime.utcnow() - timedelta(days=i)).strftime("%d %b")
        daily[day] = 0
    for o in orders:
        day = o.created_at.strftime("%d %b")
        if day in daily: daily[day] += o.total

    # Orders by status
    status_counts = {}
    for o in orders:
        status_counts[o.status] = status_counts.get(o.status, 0) + 1

    # Top products by revenue
    product_rev = {}
    for o in orders:
        for item in o.items:
            product_rev[item.product_name] = product_rev.get(item.product_name, 0) + item.subtotal
    top_products = sorted(product_rev.items(), key=lambda x: x[1], reverse=True)[:8]

    # Category revenue
    cat_rev = {}
    for o in orders:
        for item in o.items:
            p = Product.query.get(item.product_id) if item.product_id else None
            cat = p.category if p else "Other"
            cat_rev[cat] = cat_rev.get(cat, 0) + item.subtotal
    cat_revenue = sorted(cat_rev.items(), key=lambda x: x[1], reverse=True)

    # Coupon usage
    coupons = Coupon.query.all()

    return render_template("admin/analytics.html",
                           total_revenue=total_revenue, total_orders=total_orders, avg_order=avg_order,
                           total_users=User.query.count(),
                           daily_labels=list(daily.keys()), daily_values=list(daily.values()),
                           status_labels=list(status_counts.keys()), status_values=list(status_counts.values()),
                           top_products=top_products, cat_revenue=cat_revenue,
                           coupons=coupons, cart_count=0)

@app.route("/admin/products")
@login_required
@admin_required
def admin_products():
    q=request.args.get("q","")
    products=Product.query.filter(Product.name.ilike(f"%{q}%")).order_by(Product.id.desc()).all() if q else Product.query.order_by(Product.id.desc()).all()
    return render_template("admin/products.html", products=products, q=q, cart_count=0)

@app.route("/admin/products/add", methods=["GET","POST"])
@login_required
@admin_required
def admin_add_product():
    categories=sorted({p.category for p in Product.query.all()})
    if request.method=="POST":
        p=Product(name=request.form["name"],price=float(request.form["price"]),
                  category=request.form["category"],image=request.form.get("image",""),
                  stock=int(request.form.get("stock",0)),description=request.form.get("description",""),
                  rating=float(request.form.get("rating",4.0)),rating_count=int(request.form.get("rating_count",0)),
                  featured="featured" in request.form)
        db.session.add(p); db.session.commit(); flash(f"'{p.name}' added!","success")
        return redirect(url_for("admin_products"))
    return render_template("admin/add_product.html", categories=categories, cart_count=0)

@app.route("/admin/products/edit/<int:pid>", methods=["GET","POST"])
@login_required
@admin_required
def admin_edit_product(pid):
    p=Product.query.get_or_404(pid); categories=sorted({pr.category for pr in Product.query.all()})
    if request.method=="POST":
        p.name=request.form["name"]; p.price=float(request.form["price"]); p.category=request.form["category"]
        p.image=request.form.get("image",""); p.stock=int(request.form.get("stock",0))
        p.description=request.form.get("description",""); p.rating=float(request.form.get("rating",4.0))
        p.rating_count=int(request.form.get("rating_count",0)); p.featured="featured" in request.form
        db.session.commit(); flash(f"'{p.name}' updated!","success"); return redirect(url_for("admin_products"))
    return render_template("admin/edit_product.html", product=p, categories=categories, cart_count=0)

@app.route("/admin/products/delete/<int:pid>", methods=["POST"])
@login_required
@admin_required
def admin_delete_product(pid):
    p=Product.query.get_or_404(pid); db.session.delete(p); db.session.commit()
    flash(f"'{p.name}' deleted.","info"); return redirect(url_for("admin_products"))

@app.route("/admin/orders")
@login_required
@admin_required
def admin_orders():
    orders=Order.query.order_by(Order.created_at.desc()).all()
    return render_template("admin/orders.html", orders=orders, cart_count=0)

@app.route("/admin/orders/<int:oid>/status", methods=["POST"])
@login_required
@admin_required
def admin_update_status(oid):
    o=Order.query.get_or_404(oid); o.status=request.form.get("status",o.status)
    db.session.commit(); flash("Status updated.","success"); return redirect(url_for("admin_orders"))

@app.route("/admin/coupons")
@login_required
@admin_required
def admin_coupons():
    coupons=Coupon.query.order_by(Coupon.id.desc()).all()
    return render_template("admin/coupons.html", coupons=coupons, cart_count=0)

@app.route("/admin/coupons/add", methods=["POST"])
@login_required
@admin_required
def admin_add_coupon():
    code=request.form.get("code","").strip().upper(); pct=float(request.form.get("discount_pct",10))
    min_order=float(request.form.get("min_order",0)); max_uses=int(request.form.get("max_uses",100))
    if Coupon.query.filter_by(code=code).first(): flash("Code already exists.","error")
    else:
        db.session.add(Coupon(code=code, discount_pct=pct, min_order=min_order, max_uses=max_uses))
        db.session.commit(); flash(f"Coupon {code} created!","success")
    return redirect(url_for("admin_coupons"))

@app.route("/admin/coupons/toggle/<int:cid>")
@login_required
@admin_required
def admin_toggle_coupon(cid):
    c=Coupon.query.get_or_404(cid); c.active=not c.active; db.session.commit()
    flash(f"Coupon {'activated' if c.active else 'deactivated'}.","info")
    return redirect(url_for("admin_coupons"))

@app.errorhandler(403)
def forbidden(e): return render_template("403.html"), 403
@app.errorhandler(404)
def not_found(e): return render_template("404.html"), 404

if __name__ == "__main__":
    with app.app_context():
        db.create_all(); seed_db()
    app.run(debug=False)
