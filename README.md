# E-commerce Fashion Store 🛍️

An E-commerce Fashion Store built with Django and Python, offering a platform for users to browse, search, and purchase fashion products easily.

## ✨ Features

- 🛒 User Authentication (Admin, Customer, Brand)
- 👗 Product Management (Add, Edit, Delete)
- 🔎 Search and Filter Products
- 📷 Image Upload for Products
- 🧠 AI-Based Image Search (find similar products using an image)
- 💰 Discount Pricing System
- ❤️ Wishlist Management
- 🛍️ Orders and Review System
- 📋 "My Account" Page for Order and Profile Management

## 🚀 Tech Stack

- **Frontend**: HTML5, CSS3, JavaScript
- **Backend**: Python, Django
- **Database**: SQLite (for development)
- **AI Model**: MobileNetV2 for image feature extraction
- **Other Tools**: Tesseract OCR (optional for text recognition), Django Admin Panel

## 📂 Project Structure


## 🛠️ Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone https://github.com/san7eeth/E-commerce-Fashion-Store.git
   cd E-commerce-Fashion-Store

2. python -m venv env
source env/bin/activate  # On Windows use: env\Scripts\activate

3.pip install -r requirements.txt

4.python manage.py makemigrations
python manage.py migrate

5.python manage.py runserver

