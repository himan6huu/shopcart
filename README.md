# 🛒 ShopCart v3 — Full-Featured Flask E-commerce

## What's New in v3
- ✅ **User Login & Registration** — secure auth with Flask-Login
- ✅ **Admin Panel** — manage products & update order statuses
- ✅ **Advanced Filters** — search by price range, rating, category, sort
- ✅ **Order History** — logged-in users can track all past orders
- ✅ **Cart Quantity Controls** — +/− buttons with live update
- ✅ **35+ Products** across 5 categories (Electronics, Gaming, Office, Audio, Accessories)
- ✅ **INR Currency** — proper Indian number formatting
- ✅ **Related Products** on product detail page
- ✅ **Free Shipping Bar** — visual progress toward ₹2,000 threshold

## Quick Start
```bash
pip install -r requirements.txt
python app.py
# → http://127.0.0.1:5000
```

## Admin Access
- URL: http://127.0.0.1:5000/admin
- Email: admin@shopcart.com
- Password: admin123

## Test Payment
- Card: 1234 5678 9012 3456
- Expiry: 12/27  CVV: 123

## Project Structure
```
shop/
├── app.py
├── requirements.txt
├── templates/
│   ├── base.html
│   ├── index.html       # Shop with sidebar filters
│   ├── product.html     # Detail + related products
│   ├── cart.html        # Cart with quantity controls
│   ├── checkout.html
│   ├── success.html
│   ├── login.html
│   ├── register.html
│   ├── account.html     # Order history
│   ├── 403.html / 404.html
│   └── admin/
│       ├── dashboard.html
│       ├── products.html
│       ├── add_product.html
│       ├── edit_product.html
│       └── orders.html
└── static/
    ├── css/style.css
    └── js/main.js, checkout.js
```
