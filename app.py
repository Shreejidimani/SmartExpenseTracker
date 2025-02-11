from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required, current_user, logout_user, login_user
from extensions import db  # Import db from extensions.py
from models import User, Expense, Budget, Income  # Import models after db
from forms import BudgetForm
from flask_bcrypt import Bcrypt
import csv
from datetime import datetime
from flask import send_file
from sqlalchemy import func
from flask_migrate import Migrate


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expense_tracker.db'
app.config['SECRET_KEY'] = 'your_secret_key'

# Dummy user data (Replace with actual database logic)
users = {"test@example.com": {"password": "password123", "username": "John Doe"}}
migrate = Migrate(app, db)
db.init_app(app)  # Initialize database
bcrypt = Bcrypt(app)

# Flask-Login setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Homepage Route
@app.route('/')
def home():
    return render_template('home.html')

# Routes for Authentication
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered. Please log in.', 'danger')
            return redirect(url_for('login'))

        new_user = User(username=username, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)  # ✅ Correctly logs in the user
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')

    return render_template('login.html')



@app.route('/logout')
@login_required
def logout():
    logout_user()  # ✅ Logs out the user properly
    flash('Logged out successfully!', 'success')
    return redirect(url_for('home'))


@app.route('/dashboard')
@login_required
def dashboard():
    user_expenses = Expense.query.filter_by(user_id=current_user.id).all()
    user_incomes = Income.query.filter_by(user_id=current_user.id).all()  # ✅ Fetch incomes

    total_expenses = sum(expense.amount for expense in user_expenses)
    total_income = sum(income.amount for income in user_incomes)  # ✅ Calculate total income

    budget = Budget.query.filter_by(user_id=current_user.id).first()
    budget_amount = budget.amount if budget else 0
    savings = max(total_income - total_expenses, 0)  # ✅ Corrected savings calculation

    # Expense by category for visualization
    categories = {}
    for expense in user_expenses:
        categories[expense.category] = categories.get(expense.category, 0) + expense.amount

    category_labels = list(categories.keys())
    category_amounts = list(categories.values())

    # Monthly Spending Trend
    monthly_spending = {}
    for expense in user_expenses:
        month = expense.date.strftime("%b %Y")  # Example: "Jan 2025"
        monthly_spending[month] = monthly_spending.get(month, 0) + expense.amount

    month_labels = list(monthly_spending.keys())
    month_amounts = list(monthly_spending.values())

    # ✅ Get recent incomes
    recent_incomes = Income.query.filter_by(user_id=current_user.id).order_by(Income.date.desc()).limit(5).all()

    return render_template('dashboard.html', 
                           expenses=user_expenses, 
                           total_expenses=total_expenses, 
                           total_income=total_income,  # ✅ Pass total income
                           budget_amount=budget_amount, 
                           savings=savings,
                           category_labels=category_labels, 
                           category_amounts=category_amounts,
                           month_labels=month_labels, 
                           month_amounts=month_amounts,
                           recent_incomes=recent_incomes)  # ✅ Pass recent incomes


# Add Expense Route
@app.route('/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        amount = request.form['amount']
        category = request.form['category']
        description = request.form['description']
        date = datetime.strptime(request.form['date'], '%Y-%m-%d')

        new_expense = Expense(
            amount=amount,
            category=category,
            description=description,
            date=date,
            user_id=current_user.id
        )
        db.session.add(new_expense)
        db.session.commit()

        flash('Expense added successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_expense.html')
  
@app.route('/save_expense')
def save_expense():
    # Get the expense details from the query parameters
    amount = request.args.get('amount')
    category = request.args.get('category')
    description = request.args.get('description')
    date = request.args.get('date')

    expense = {
        'amount': amount,
        'category': category,
        'description': description,
        'date': date
    }
    return render_template('save_expense.html', expense=expense)

@app.route('/view_expenses')
@login_required
def view_expenses():
    user_expenses = Expense.query.filter_by(user_id=current_user.id).all()
    return render_template('view_expenses.html', expenses=user_expenses)

  # Visualize Expenses Route
@app.route('/visualize')
@login_required
def visualize_expenses():
    user_expenses = Expense.query.filter_by(user_id=current_user.id).all()
    categories = {}
    for expense in user_expenses:
        categories[expense.category] = categories.get(expense.category, 0) + expense.amount

    # Convert data for Chart.js
    category_labels = list(categories.keys())
    category_amounts = list(categories.values())

    return render_template('visualize.html', categories=category_labels, amounts=category_amounts)

@app.route('/set_budget', methods=['GET', 'POST'])
@login_required
def set_budget():
    form = BudgetForm()
    budget = Budget.query.filter_by(user_id=current_user.id).first()

    if form.validate_on_submit():
        if budget:
            budget.amount = form.amount.data
        else:
            budget = Budget(user_id=current_user.id, amount=form.amount.data)
            db.session.add(budget)

        db.session.commit()
        flash("Budget goal updated!", "success")
        return redirect(url_for('dashboard'))

    return render_template('set_budget.html', form=form, budget=budget)

@app.route('/edit_expense/<int:expense_id>', methods=['GET', 'POST'])
@login_required
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)

    if request.method == 'POST':
        expense.amount = request.form['amount']
        expense.category = request.form['category']
        expense.description = request.form['description']
        expense.date = datetime.strptime(request.form['date'], '%Y-%m-%d')

        db.session.commit()
        flash('Expense updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('edit_expense.html', expense=expense)

@app.route('/add_income', methods=['GET', 'POST'])
@login_required
def add_income():
    if request.method == 'POST':
        amount = request.form['amount']
        source = request.form['source']
        date = datetime.strptime(request.form['date'], '%Y-%m-%d')

        new_income = Income(amount=amount, source=source, date=date, user_id=current_user.id)
        db.session.add(new_income)
        db.session.commit()

        flash('Income added successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_income.html')

@app.route('/delete_income/<int:income_id>', methods=['POST'])
@login_required
def delete_income(income_id):
    income = Income.query.get_or_404(income_id)
    
    # Ensure the user can only delete their own income
    if income.user_id != current_user.id:
        flash("Unauthorized action!", "danger")
        return redirect(url_for('dashboard'))

    db.session.delete(income)
    db.session.commit()
    flash("Income record deleted successfully!", "success")
    return redirect(url_for('dashboard'))

@app.route('/edit_income/<int:income_id>', methods=['GET', 'POST'])
@login_required
def edit_income(income_id):
    income = Income.query.get_or_404(income_id)

    # Ensure only the owner can edit
    if income.user_id != current_user.id:
        flash("Unauthorized action!", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        income.amount = request.form['amount']
        income.source = request.form['source']
        income.date = datetime.strptime(request.form['date'], '%Y-%m-%d')

        db.session.commit()
        flash("Income record updated successfully!", "success")
        return redirect(url_for('dashboard'))

    return render_template('edit_income.html', income=income)

@app.route('/delete_expense/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)

    db.session.delete(expense)
    db.session.commit()
    flash('Expense deleted successfully!', 'success')

    return redirect(url_for('dashboard'))

@app.route('/export_expenses')
def export_expenses():
    expenses = Expense.query.all()
    total_income = db.session.query(func.sum(Income.amount)).scalar() or 0
    total_expenses = db.session.query(func.sum(Expense.amount)).scalar() or 0
    savings = total_income - total_expenses

    with open('expenses.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Date', 'Description', 'Amount'])

        for expense in expenses:
            formatted_date = expense.date.strftime('%Y-%m-%d') if expense.date else "N/A"  # ✅ Fix: Ensure proper formatting
            writer.writerow([formatted_date, expense.description, expense.amount])

        writer.writerow([])
        writer.writerow(['Total Income', total_income])
        writer.writerow(['Total Expenses', total_expenses])
        writer.writerow(['Savings', savings])


    return send_file('expenses.csv', as_attachment=True) 


# Initialize Database
def create_tables():
    with app.app_context():
        db.create_all()
        print("Tables created.")

# ✅ Now `if __name__ == '__main__'` comes LAST
if __name__ == '__main__':
    create_tables()  
    app.run(debug=True)
    


