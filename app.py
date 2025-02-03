from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests
import json
import os
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Add a secret key for session management
app.secret_key = 'your-secret-key-here'  # Replace with a real secret key in production

# Get the absolute path to the instance folder
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, 'instance')

# Ensure the instance folder exists with proper permissions
if not os.path.exists(instance_path):
    os.makedirs(instance_path, mode=0o777)

# Configure SQLAlchemy with absolute path
db_path = os.path.join(instance_path, 'recipes.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Create the database file with proper permissions
if not os.path.exists(db_path):
    with open(db_path, 'w') as f:
        pass
    os.chmod(db_path, 0o666)

db = SQLAlchemy(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    recipes = db.relationship('SavedRecipe', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class SavedRecipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    cost = db.Column(db.String(50))
    diet_type = db.Column(db.String(50))
    region = db.Column(db.String(50))
    date_saved = db.Column(db.DateTime, default=datetime.now)
    dietary_restrictions = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'ingredients': self.ingredients,
            'cost': self.cost,
            'diet_type': self.diet_type,
            'region': self.region,
            'date_saved': self.date_saved.strftime('%Y-%m-%d %H:%M:%S')
        }

# Create the database tables
with app.app_context():
    try:
        db.drop_all()  # This will reset the database
        db.create_all()
        print("Database tables created successfully")
    except Exception as e:
        print(f"Error creating database tables: {e}")

OLLAMA_API_URL = "http://localhost:11434/api/generate"

DIET_TYPES = [
    "None",
    # Weight Management
    "Weight Loss - Extreme",
    "Weight Loss - Moderate",
    "Weight Loss - Light",
    "Weight Gain (Healthy)",
    "Weight Maintenance",
    
    # Protein-focused
    "High Protein",
    "Carnivore",
    
    # Plant-based
    "Vegan",
    "Vegetarian",
    "Plant Based",
    "Raw Vegan",
    "Pescatarian",
    
    # Specific Diets
    "Ketogenic",
    "Low-Carb",
    "Mediterranean Diet",
    "Paleo",
    "Whole30",
    "DASH Diet",
    "Anti-Inflammatory",
    
    # Health-specific
    "Diabetic-Friendly",
    "Heart-Healthy",
    "Low-Sodium",
    "Low-Fat",
    "Gluten-Free",
    
    # Fitness
    "Athletic Performance",
    "Bodybuilding",
    "Endurance Training",
    
    # Lifestyle
    "Clean Eating",
    "Intermittent Fasting",
    "Macro-Based",
    "Flexitarian"
]

REGIONS = [
    "None",
    "Mediterranean",
    "Mexican",
    "Chinese",
    "Indian",
    "Thai",
    "Italian",
    "Japanese",
    "Korean",
    "Vietnamese",
    "French",
    "Greek",
    "Middle Eastern",
    "Brazilian",
    "Spanish",
    "American",
    "Caribbean",
    "North African",
    "Ethiopian",
    "German",
    "Russian",
    "Turkish",
    "Lebanese",
    "Moroccan",
    "Persian"
]

PRICE_RANGES = [
    "Cheap",
    "Moderate",
    "Expensive"
]

@app.route('/')
def index():
    return render_template('index.html', 
                         is_main_page=True,
                         diet_types=DIET_TYPES,
                         regions=REGIONS,
                         price_ranges=PRICE_RANGES)

@app.route('/get_recommendations', methods=['POST'])
def get_recommendations():
    data = request.json
    
    # Construct the prompt for Ollama
    prompt = f"""
    You are a helpful AI nutritionist and chef. Please generate 5 meal recommendations with detailed ingrdient listsbased on the following criteria:
    - Dietary Restrictions: {data['restrictions']}
    - Requested Ingredients: {data['requests']}
    - Diet Type: {data['dietType']}
    - Region: {data['region']}
    - Price Range: {data['priceRange']}
    
    Please try to incorporate the requested ingredients where appropriate while respecting dietary restrictions.
    
    Format each recipe exactly like this, and ABSOLUTELY DO NOT include any asterisks (**) or other special characters:

    
    Description: [2-3 sentences describing the dish]
    Servings: [number of servings based on ingredients]
    Nutritional Facts (per serving):
    • Calories: [number] kcal
    • Protein: [number]g
    • Carbs: [number]g
    • Fat: [number]g
    Ingredients:
    • [ingredient 1]
    • [ingredient 2]
    • [etc...]
    Approximate Cost Per Serving: [cost]

    Recipe 2: [Recipe Name]
    [same format]

    Recipe 3: [Recipe Name]
    [same format]

    Recipe 4: [Recipe Name]
    [same format]

    Recipe 5: [Recipe Name]
    [same format]

    Please ensure each recipe is clearly separated and formatted consistently. Provide realistic nutritional estimates based on ingredients and portion sizes.
    
    Do not include any asterisks (*) or other special characters.
    """

    # Call Ollama API
    response = requests.post(OLLAMA_API_URL, 
                           json={
                               "model": "llama3.1:latest",
                               "prompt": prompt,
                               "stream": False
                           })
    
    if response.status_code == 200:
        result = response.json()
        return jsonify({"success": True, "recommendations": result['response']})
    else:
        error_msg = f"Failed to get recommendations. Status code: {response.status_code}"
        print(error_msg)
        return jsonify({"success": False, "error": error_msg})

# Add new route for saving recipes
@app.route('/save_recipe', methods=['POST'])
@login_required
def save_recipe():
    try:
        data = request.json
        recipe = SavedRecipe(
            name=data['name'],
            description=data['description'],
            ingredients=data['ingredients'],
            cost=data['cost'],
            diet_type=data['diet_type'],
            region=data['region'],
            date_saved=datetime.now(),
            dietary_restrictions=data.get('restrictions', ''),
            user_id=current_user.id
        )
        db.session.add(recipe)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# Add route to view saved recipes
@app.route('/saved_recipes')
def saved_recipes():
    recipes = SavedRecipe.query.filter_by(user_id=current_user.id).order_by(SavedRecipe.date_saved.desc()).all()
    return render_template('saved_recipes.html', recipes=recipes, is_main_page=False)

# Add delete route for recipes
@app.route('/delete_recipe/<int:recipe_id>', methods=['POST'])
def delete_recipe(recipe_id):
    try:
        recipe = SavedRecipe.query.filter_by(id=recipe_id, user_id=current_user.id).first()
        if recipe:
            db.session.delete(recipe)
            db.session.commit()
            return jsonify({"success": True, "message": "Recipe deleted successfully!"})
        else:
            return jsonify({"success": False, "error": "Recipe not found!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json
        username = data['username']
        email = data['email']
        password = data['password']
        
        if User.query.filter_by(username=username).first():
            return jsonify({"success": False, "error": "Username already exists"})
        
        if User.query.filter_by(email=email).first():
            return jsonify({"success": False, "error": "Email already registered"})
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        return jsonify({"success": True})
    
    return render_template('register.html', is_main_page=False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        username = data['username']
        password = data['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return jsonify({"success": True})
        
        return jsonify({"success": False, "error": "Invalid username or password"})
    
    return render_template('login.html', is_main_page=False)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True) 