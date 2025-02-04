import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    current_user,
    logout_user,
    UserMixin,
)
from flask_bcrypt import Bcrypt
import openai
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

# Set the OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or "secret-key"
# Using SQLite for this example; the database file will be "app.db".
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions.
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    recipes = db.relationship("Recipe", backref="owner", lazy=True)

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    servings = db.Column(db.String(50))
    nutrition = db.Column(db.Text)
    cost_per_serving = db.Column(db.String(50))
    instructions = db.Column(db.Text)
    is_favorite = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route("/", methods=["GET", "POST"])
def index():
    meal_options = []
    debug_info = []
    if request.method == "POST":
        dietary_restrictions = request.form.get("dietaryRestrictions", "")
        ingredients = request.form.get("ingredients", "")
        region = request.form.get("region", "")
        diet_type = request.form.get("dietType", "")
        price = request.form.get("price", "")

        prompt = "Suggest 3 meal options that meet the following criteria:\n"
        if dietary_restrictions:
            prompt += f"Dietary restrictions: {dietary_restrictions}.\n"
        if ingredients:
            prompt += f"Include these ingredients: {ingredients}.\n"
        if region:
            prompt += f"Regional cuisine: {region}.\n"
        if diet_type:
            prompt += f"Diet type: {diet_type}.\n"
        if price:
            prompt += f"Price range: {price}.\n"
        prompt += """For each meal, please format the response exactly as follows (including the exact headers) [Do not include any special characters like ** or # or * or anything else, only $ for price]:

[Recipe Name]
Ingredients:
[List ingredients here]

Servings:
[Number of servings]

Nutrition Facts:
[Nutrition information]

Cost per Serving:
[Cost]

Instructions:
[Write detailed cooking instructions here. Do not skip this section.]


"""

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
            )
            raw_text = response.choices[0].message.content.strip()
            
            # Add debugging information and log it
            debug_info.append("ChatGPT prompt: " + prompt)
            debug_info.append("ChatGPT raw response: " + raw_text)
            app.logger.info("ChatGPT prompt: %s", prompt)
            app.logger.info("ChatGPT raw response: %s", raw_text)

            # Updated split regex to catch "Meal X:" or bracketed recipe names.
            meal_blocks = re.split(r'(?=Meal\s*\d+:)|(?=\[)', raw_text)
            meal_blocks = [block.strip() for block in meal_blocks if block.strip()]

            def parse_meal_block(block):
                fields = {"title": "N/A", "ingredients": "N/A", "servings": "N/A", "nutrition": "N/A", "cost": "N/A", "instructions": "N/A"}
                
                # Extract title from the beginning, either as [Title] or as "Meal <number>: Title"
                title_match = re.match(r'(?:\[(.*?)\]|Meal\s*\d+:\s*(.*?))\s*(?=Ingredients:)', block, re.DOTALL)
                if title_match:
                    fields['title'] = (title_match.group(1) or title_match.group(2)).strip()
                else:
                    # Fallback: use the first line of the block as the recipe title
                    fields['title'] = block.splitlines()[0].strip()

                # Extract sections using clear boundaries
                ingredients_match = re.search(r'Ingredients:\s*(.*?)(?=\n\s*Servings:)', block, re.DOTALL)
                if ingredients_match:
                    fields['ingredients'] = ingredients_match.group(1).strip()

                servings_match = re.search(r'Servings:\s*(.*?)(?=\n\s*Nutrition Facts:)', block, re.DOTALL)
                if servings_match:
                    fields['servings'] = servings_match.group(1).strip()

                nutrition_match = re.search(r'Nutrition Facts:\s*(.*?)(?=\n\s*Cost per Serving:)', block, re.DOTALL)
                if nutrition_match:
                    fields['nutrition'] = nutrition_match.group(1).strip()

                cost_match = re.search(r'Cost per Serving:\s*(.*?)(?=\n\s*Instructions:)', block, re.DOTALL)
                if cost_match:
                    fields['cost'] = cost_match.group(1).strip()

                instructions_match = re.search(r'Instructions:\s*(.*?)(?=\n\s*\[|$)', block, re.DOTALL)
                if instructions_match:
                    fields['instructions'] = instructions_match.group(1).strip()
                    if fields['instructions'] == 'N/A':
                        fields['instructions'] = 'Instructions not provided.'
                
                return fields
            
            # Process each block
            for block in meal_blocks:
                fields = parse_meal_block(block)
                meal_options.append(fields)
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            app.logger.error("Error during API call: %s", error_msg, exc_info=True)
            debug_info.append(error_msg)
            # Wrap the error in a dict so the template can render it
            meal_options = [{
                "title": error_msg,
                "ingredients": "",
                "servings": "",
                "nutrition": "",
                "cost": "",
                "instructions": ""
            }]

    return render_template("index.html", meal_options=meal_options, debug_info=debug_info)

@app.route("/save_recipe", methods=["POST"])
@login_required
def save_recipe():
    recipe_title = request.form.get("title")
    recipe_content = request.form.get("content")
    recipe_ingredients = request.form.get("ingredients")
    recipe_servings = request.form.get("servings")
    recipe_nutrition = request.form.get("nutrition")
    recipe_cost = request.form.get("cost")
    recipe_instructions = request.form.get("instructions")
    if recipe_title and recipe_content:
        recipe = Recipe(
            title=recipe_title,
            content=recipe_content,
            ingredients=recipe_ingredients,
            servings=recipe_servings,
            nutrition=recipe_nutrition,
            cost_per_serving=recipe_cost,
            instructions=recipe_instructions,
            user_id=current_user.id
        )
        db.session.add(recipe)
        db.session.commit()
        flash("Recipe saved successfully!", "success")
    else:
        flash("Invalid recipe data.", "danger")
    return redirect(url_for("index"))

@app.route("/saved_recipes")
@login_required
def saved_recipes():
    try:
        recipes = Recipe.query.filter_by(user_id=current_user.id).all()
    except Exception as e:
        flash("Error retrieving recipes: " + str(e), "danger")
        recipes = []
    favorites = [r for r in recipes if r.is_favorite]
    recent = [r for r in recipes if not r.is_favorite]
    return render_template("saved_recipes.html", favorites=favorites, recent=recent)

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        # Check if the email is already registered.
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return redirect(url_for("register"))
        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
        user = User(username=username, email=email, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash("Logged in successfully.", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid credentials.", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))

@app.route("/delete_recipe/<int:recipe_id>", methods=["POST"])
@login_required
def delete_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if recipe.user_id != current_user.id:
        flash("You do not have permission to delete this recipe.", "danger")
        return redirect(url_for("saved_recipes"))
    db.session.delete(recipe)
    db.session.commit()
    flash("Recipe deleted.", "success")
    return redirect(url_for("saved_recipes"))

@app.route("/toggle_favorite/<int:recipe_id>", methods=["POST"])
@login_required
def toggle_favorite(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if recipe.user_id != current_user.id:
        flash("You do not have permission to modify this recipe.", "danger")
        return redirect(url_for("saved_recipes"))
    # Toggle favorite status
    recipe.is_favorite = not recipe.is_favorite
    db.session.commit()
    flash("Recipe updated.", "success")
    return redirect(url_for("saved_recipes"))

# Create the database tables if they do not exist.
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
