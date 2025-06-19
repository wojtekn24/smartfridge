# app.py

import os
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'smartfridge.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "tajny_klucz"

db = SQLAlchemy(app)

# MODELE
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Fridge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    purchase_date = db.Column(db.Date, nullable=False)
    expiration_date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='aktywny')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    fridge_id = db.Column(db.Integer, db.ForeignKey('fridge.id'), nullable=False)
    user = db.relationship('User', backref='products')
    fridge = db.relationship('Fridge', backref='products')

class IssueReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    issue_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    fridge_id = db.Column(db.Integer, db.ForeignKey('fridge.id'), nullable=False)
    user = db.relationship('User', backref='issues')
    fridge = db.relationship('Fridge', backref='issues')

# INICJALIZACJA BAZY
with app.app_context():
    db.create_all()
    if Fridge.query.first() is None:
        db.session.add(Fridge(name="Domyślna Lodówka"))
        db.session.commit()

# REJESTRACJA
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash("Użytkownik już istnieje")
            return redirect(url_for('register'))
        hashed = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed)
        if User.query.first() is None:
            new_user.is_admin = True
        db.session.add(new_user)
        db.session.commit()
        flash("Zarejestrowano! Zaloguj się")
        return redirect(url_for('login'))
    return render_template('register.html')

# LOGOWANIE
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Błędne dane logowania")
            return redirect(url_for('login'))
        session['user_id'] = user.id
        session['username'] = user.username
        flash("Zalogowano")
        return redirect(url_for('list_products'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Wylogowano")
    return redirect(url_for('login'))

# DODAWANIE PRODUKTU
@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['name']
        purchase = datetime.strptime(request.form['purchase_date'], "%Y-%m-%d").date()
        expiration = datetime.strptime(request.form['expiration_date'], "%Y-%m-%d").date()
        category = request.form['category']
        quantity = int(request.form['quantity'])
        notes = request.form['notes']
        status = request.form['status']
        fridge = Fridge.query.first()
        new_product = Product(name=name, purchase_date=purchase, expiration_date=expiration,
                              category=category, quantity=quantity, notes=notes, status=status,
                              user_id=session['user_id'], fridge_id=fridge.id)
        db.session.add(new_product)
        db.session.commit()
        flash("Dodano produkt")
        return redirect(url_for('list_products'))
    return render_template('add_product.html')

# LISTA PRODUKTÓW
@app.route('/products')
def list_products():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    category = request.args.get('category')
    query = Product.query.filter_by(user_id=session['user_id'])
    if category:
        query = query.filter_by(category=category)
    products = query.order_by(Product.expiration_date).all()
    return render_template('products.html', products=products, today=date.today(), category=category)

# ZGŁOSZENIE PROBLEMU
@app.route('/report_issue', methods=['GET', 'POST'])
def report_issue():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        issue_type = request.form['type']
        description = request.form['description']
        fridge = Fridge.query.first()
        issue = IssueReport(issue_type=issue_type, description=description,
                             user_id=session['user_id'], fridge_id=fridge.id)
        db.session.add(issue)
        db.session.commit()
        flash("Zgłoszono problem")
        return redirect(url_for('list_products'))
    return render_template('report_issue.html')

# LISTA ZGŁOSZEŃ (ADMIN)
@app.route('/issues')
def list_issues():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        flash("Brak dostępu")
        return redirect(url_for('list_products'))
    issues = IssueReport.query.order_by(IssueReport.timestamp.desc()).all()
    return render_template('issues.html', issues=issues)

# PRZEKAZYWANIE PRODUKTU
@app.route('/transfer/<int:product_id>', methods=['GET', 'POST'])
def transfer_product(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    product = Product.query.get_or_404(product_id)
    if product.user_id != session['user_id']:
        flash("Brak uprawnień")
        return redirect(url_for('list_products'))
    if request.method == 'POST':
        username = request.form['username']
        target_user = User.query.filter_by(username=username).first()
        if not target_user or target_user.id == session['user_id']:
            flash("Niepoprawny użytkownik")
            return redirect(url_for('transfer_product', product_id=product.id))
        product.user_id = target_user.id
        product.status = 'oddany'
        db.session.commit()
        flash("Produkt przekazany")
        return redirect(url_for('list_products'))
    return render_template('transfer.html', product=product)
    
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('list_products'))
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
