import os
from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pymongo import MongoClient
from bson.objectid import ObjectId

from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = "your_secret_key"

# MongoDB connection
client = MongoClient("mongodb+srv://samuelashishn:s123@recipehub.fodgz74.mongodb.net/?retryWrites=true&w=majority&appName=Recipehub")
db = client["recipe_db"]
users_collection = db["users"]
recipes_collection = db["recipes"]

# Flask extensions
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# User Class
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@login_manager.user_loader
def load_user(user_id):
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    return User(user_data) if user_data else None

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')

        if users_collection.find_one({"username": username}):
            return redirect(url_for('register', message="Username already exists"))


        users_collection.insert_one({"username": username, "password": password, "favorites": []})
        return redirect(url_for('login', message="Registration successful, please log in."))

        

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        user = users_collection.find_one({"username": username})

        if user and bcrypt.check_password_hash(user['password'], request.form['password']):
            login_user(User(user))
            return redirect(url_for('home', message="Login successful!"))

        else:
            return redirect(url_for('login', error="Invalid credentials"))


    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def home():
    return render_template('home.html')


@app.route('/category/<category_name>')
@login_required
def category(category_name):
    recipes = list(recipes_collection.find({"category": category_name.lower()}))
    return render_template('category.html', category=category_name, recipes=recipes)


@app.route('/add-recipe', methods=['GET', 'POST'])
@login_required
def add_recipe():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        ingredients = request.form['ingredients'].split('\n')
        steps = request.form['steps'].split('\n')
        category = request.form['category'].lower()
        image_file = request.files.get('image')

        image_filename = ""
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
            image_filename = filename

        recipe = {
            "title": title,
            "description": description,
            "ingredients": ingredients,
            "steps": steps,
            "category": category,
            "user_id": current_user.id,
            "image": image_filename
        }

        recipes_collection.insert_one(recipe)
        flash("Recipe added successfully!")
        return redirect(url_for('home'))

    return render_template('add_recipe.html')





@app.route('/recipe/<recipe_id>')
@login_required
def view_recipe(recipe_id):
    recipe = recipes_collection.find_one({"_id": ObjectId(recipe_id)})
    if not recipe:
        flash("Recipe not found.")
        return redirect(url_for('home'))

    # Convert ObjectId to string for HTML use
    recipe['_id'] = str(recipe['_id'])

    is_favorite = False
    user = users_collection.find_one({"_id": ObjectId(current_user.id)})
    if recipe_id in user.get("favorites", []):
        is_favorite = True

    return render_template('recipe_detail.html', recipe=recipe, is_favorite=is_favorite)


@app.route('/favorite/<recipe_id>', methods=['POST'])
@login_required
def add_favorite(recipe_id):
    users_collection.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$addToSet": {"favorites": recipe_id}}
    )
    return redirect(url_for('view_recipe', recipe_id=recipe_id))


@app.route('/unfavorite/<recipe_id>', methods=['POST'])
@login_required
def remove_favorite(recipe_id):
    users_collection.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$pull": {"favorites": recipe_id}}
    )
    return redirect(url_for('view_recipe', recipe_id=recipe_id))

@app.route('/favorites')
@login_required
def favorites():
    user = users_collection.find_one({"_id": ObjectId(current_user.id)})
    favorite_ids = user.get("favorites", [])

    # Convert string IDs to ObjectId and fetch matching recipes
    favorite_recipes = list(recipes_collection.find({"_id": {"$in": [ObjectId(rid) for rid in favorite_ids]}}))

    return render_template('favorites.html', recipes=favorite_recipes)


@app.route('/my-recipes')
@login_required
def my_recipes():
    user_recipes = list(recipes_collection.find({"user_id": current_user.id}))
    return render_template('my_recipes.html', recipes=user_recipes)


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('admin_password')
        if password == "admin123":  # You can change this to a secure one
            return redirect(url_for('admin_page'))
        else:
            flash("Invalid admin password")
            return redirect(url_for('admin_login'))
    return render_template('admin_login.html')


@app.route('/admin-page')
def admin_page():
    all_recipes = list(recipes_collection.find({}))
    enriched_recipes = []

    for recipe in all_recipes:
        user = users_collection.find_one({'_id': ObjectId(recipe['user_id'])})
        enriched_recipes.append({
            "title": recipe["title"],
            "category": recipe["category"],
            "description": recipe["description"],
            "username": user["username"] if user else "Unknown"
        })

    return render_template('admin_page.html', recipes=enriched_recipes)


if __name__ == '__main__':
    app.run(debug=True)
