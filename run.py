import os
from datetime import datetime
import shutil
from flask import (
    Flask, flash, render_template, send_from_directory,
    redirect, request, session, url_for, Blueprint)
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
if os.path.exists("env.py"):
    import env

# App config
app = Flask(__name__)

profile_images = f'{app.root_path}/profile_images/'

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.config['UPLOAD_FOLDER'] = profile_images
app.secret_key = os.environ.get("SECRET_KEY")

# Database
mongo = PyMongo(app)

# Blueprints
main = Blueprint('main', __name__)

app.register_blueprint(main, url_prefix=('/main'))


# Routes
@app.route("/")
@app.route("/index", methods=["GET", "POST"])
def index():

    # Fetch topics collection from db
    topics = list(mongo.db.topics.find())

    # Create new topic, flash a message confirming the
    # insertion and reload page
    if request.method == "POST":

        # Redirects user to login if no session exists
        if session.get('user_id') is None:
            return redirect(url_for("login"))

        submit = {
            "author": session['user_id'],
            "author_name": session['display_name'],
            "title": request.form.get("title"),
            "description": request.form.get("description"),
            "posts": 0,
            "date": datetime.now()
        }
        mongo.db.topics.insert_one(submit)
        flash("Topic Successfully Updated")
        return redirect(url_for("index"))

    return render_template("index.html", topics=topics)


@app.route("/edit_topic/<topic>", methods=["GET", "POST"])
def edit_topic(topic):

    # Fetch topic info from db
    topic_info = mongo.db.topics.find_one({'_id': ObjectId(topic)})

    # Update topic and flash message confirming changes
    if request.method == "POST":
        submit = {
            "author": topic_info['author'],
            "author_name": topic_info['author_name'],
            "title": request.form.get("topic_title"),
            "description": request.form.get("topic_description"),
            "posts": topic_info['posts'],
            "date": topic_info['date']
        }
        mongo.db.topics.update({"_id": ObjectId(topic)}, submit)
        flash("Topic Successfully Updated")

    return redirect(url_for("discussion", topic=topic_info['_id']))


@app.route("/delete_topic/<topic>")
def delete_topic(topic):
    # Remove topic from db and flash message confirming deletion
    mongo.db.topics.remove({"_id": ObjectId(topic)})
    flash("Topic has been deleted.")
    return redirect(url_for("index"))


@app.route("/discussion/<topic>", methods=["GET", "POST"])
def discussion(topic):

    # Fetch topic info and posts within the topic from db
    topic_info = mongo.db.topics.find_one({'_id': ObjectId(topic)})
    posts = list(mongo.db.posts.find({'topic': topic}))

    # Insert new post into db
    if request.method == "POST":

        # Redirects user to login if no session exists
        if session.get('user_id') is None:
            return redirect(url_for("login"))

        submit = {
            "topic": topic,
            "author": session['user_id'],
            "date": datetime.now(),
            "post": request.form.get("post")
        }
        mongo.db.posts.insert_one(submit)
        # Increase post counts for the post and the user
        mongo.db.topics.update({"_id": ObjectId(topic)}, {
                               "$inc": {"posts": 1}})
        mongo.db.users.update({"_id": ObjectId(submit['author'])}, {
                              "$inc": {"posts": 1}})
        return redirect(url_for("discussion", topic=topic))

    return render_template(
        "discussion.html", topic_info=topic_info, posts=posts)


@app.route("/edit_post/<post>", methods=["GET", "POST"])
def edit_post(post):

    # Fetch post from db
    post_info = mongo.db.posts.find_one({'_id': ObjectId(post)})

    # Update post and flash message confirming changes
    if request.method == "POST":
        submit = {
            "topic": post_info['topic'],
            "author": post_info['author'],
            "date": post_info['date'],
            "post": request.form.get(f"post_edit_{post}")
        }
        mongo.db.posts.update({"_id": ObjectId(post)}, submit)
        flash("Post Successfully Updated")

    return redirect(url_for("discussion", topic=post_info['topic']))


@app.route("/delete_post/<post>")
def delete_post(post):
    post_info = mongo.db.posts.find_one({'_id': ObjectId(post)})
    print(post)
    # Decrease post counts for the post and the user
    mongo.db.topics.update_one({"_id": ObjectId(post_info['topic'])}, {
                               "$inc": {"posts": -1}})
    mongo.db.users.update_one({"_id": ObjectId(post_info['author'])}, {
                              "$inc": {"posts": -1}})
    # Delete post from db and flash message confirming deletion
    mongo.db.posts.delete_one({"_id": ObjectId(post)})
    flash("Post has been deleted.")
    return redirect(url_for("discussion", topic=post_info['topic']))


# Helper route to load images stored in profile_images
@app.route("/send_file/<filename>")
def send_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/profile/<user_id>")
def profile(user_id):
    # Fetch user from db
    user = mongo.db.users.find_one(
        {"_id": ObjectId(user_id)})

    return render_template("profile.html", user=user)


@app.route("/edit_profile/<user_id>", methods=["GET", "POST"])
def edit_profile(user_id):

    # Fetch user from db
    user = mongo.db.users.find_one(
        {"_id": ObjectId(user_id)})

    # Update user and flash message confirming changes, then redirects
    # to updated profile page
    if request.method == "POST":
        # Saves image in upload folder and grabs filename to save in db
        profile_image = request.files['profile_picture']
        filename = session['user_id']
        profile_image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        submit = {
            "rank": "user",
            "display_name": request.form.get("display_name"),
            "email": user['email'],
            "password": user['password'],
            "posts": user['posts'],
            "password_status": "set"
        }
        mongo.db.users.update({"_id": ObjectId(user_id)}, submit)
        session['display_name'] = submit['display_name']
        flash("Profile Successfully Updated")
        return redirect(url_for("profile", user_id=user_id))

    # Allows user to edit own profile only if logged in, otherwise
    # redirect to main page
    if user_id == session['user_id']:
        return render_template("edit_profile.html", user=user)

    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        # Check if username already exists in db
        existing_user = mongo.db.users.find_one(
            {"email": request.form.get("email").lower()})

        # Shows message to user confirming that account already
        # exists and redirects to register
        if existing_user:
            flash("Account already exists")
            return redirect(url_for("register"))

        # Inserts new user into db
        register = {
            "rank": "user",
            "display_name": request.form.get("display_name"),
            "email": request.form.get("email").lower(),
            "password": generate_password_hash(request.form.get("password")),
            "posts": 0,
            "password_status": "set",
        }
        mongo.db.users.insert_one(register)
        user_id = str(mongo.db.users.find_one(
            {"email": register["email"]})["_id"])

        # Create a copy of default.png and save it in profile_images
        shutil.copyfile(f'{app.config["UPLOAD_FOLDER"]}default.png',
                        f'{app.config["UPLOAD_FOLDER"]}{user_id}')

        # Put the new user's name and _id into 'session' cookie, shows
        # message confirming registration and redirects to profile
        session['display_name'] = register['display_name']
        session['user_id'] = user_id
        flash("Registration Successful!")

        return redirect(url_for(
            "profile",
            user_id=user_id))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        # Check if usernarme exists in db
        existing_user = mongo.db.users.find_one(
            {"email": request.form.get("email").lower()})

        if existing_user:
            # Ensures hashed password matches user input, sets cookies,
            # shows message welcoming user and redirects to profile
            if check_password_hash(
                    existing_user["password"],
                    request.form.get("password")):
                session["display_name"] = existing_user["display_name"]
                session["user_id"] = str(existing_user["_id"])
                flash("Welcome, {}".format(existing_user["display_name"]))
                return redirect(url_for(
                    "profile",
                    user_id=session["user_id"]))
            else:
                # Invalid passwords match
                flash("Incorrect Email and/or Password")
                return redirect(url_for("login"))

        else:
            # Username doesn't exist
            flash("Incorrect Email and/or Password")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    # Logs user out, shows message confirming changes and
    # deletes cookies
    flash("You have been logged out.")
    session.pop("display_name")
    session.pop("user_id")
    return redirect(url_for("login"))


@app.route("/search", methods=["GET", "POST"])
def search():
    # Queries the topics collection according to the value entered
    # in the search field and loads page with the results
    query = request.form.get("search")
    topics = list(mongo.db.topics.find({"$text": {"$search": query}}))
    return render_template("index.html", topics=topics)


if __name__ == "__main__":
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)
