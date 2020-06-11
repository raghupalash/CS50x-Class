import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired

from helpers import apology, login_required


# Configure application
app = Flask(__name__)
 
# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configuring for sending emails
app.config.update (
    DEBUG = True,
    # Email Settings
    MAIL_SERVER = "smtp.gmail.com",
    MAIL_PORT = 465,
    MAIL_USE_SSL = True,
    MAIL_USERNAME = "raghupalash0@gmail.com",
    MAIL_PASSWORD = "bechariDUKARIYA"
)

mail = Mail(app)

s = URLSafeTimedSerializer("HarshBemtichodHai")


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///class.db")

@app.route("/index", methods=["GET", "POST"])
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "GET":
        # If user is not verified, don't let him enter
        if session["confirm"] == 'False':
            session.clear()
            return redirect("/login")
        
        # For flashing new notifications
        # Extrating friend requests
        friendR = db.execute("SELECT sender FROM requests WHERE reciever = :reciever", reciever=session["user_id"])
        if len(friendR) != 0: 
            flash(f"You have {len(friendR)} notification(s)!")

        # Extracting user's current week!
        week = db.execute("SELECT week FROM users WHERE id = :id", id=session["user_id"])
        return render_template("index.html", week=week[0]["week"])
    
    else:
        # Update week!
        db.execute("UPDATE users SET week = :week WHERE id = :id", week=request.form.get("week"), id=session["user_id"])
        return redirect("/")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("email"):
            return apology("must provide email", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE email = :email",
                            email=request.form.get("email"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid email and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["email"] = rows[0]["email"]
        session["confirm"] = rows[0]["confirm"]

        # If user is not verified, don't let him enter
        if session["confirm"] == 'False':
            session.clear()
            return redirect("/login")

        # Storing the languages the user speaks in "session"
        # Languages the the user speaks
        langs = db.execute("SELECT language FROM languages WHERE id IN (SELECT lang_id FROM language WHERE user_id = :user_id)", 
                user_id=session["user_id"])
        session["langcount"] = len(langs)
        for i in range(len(langs)):
            session[f"lang{i}"] = langs[i]["language"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    # Storing languages spoken by user in list for use in the function
    langs = []
    for i in range(session["langcount"]):
        langs.append(session[f"lang{i}"])

    if request.method == "GET":
        return render_template("search.html", langs=langs)
    else:
        # Dealing with 2 post request from search page
        if request.form.get("search-page") == "search":
            country = request.form.get("country")
            week = request.form.get("week")
            course = request.form.get("course")
            language = request.form.get("language")
            
            # Common part in all strings
            common = "SELECT email, name, surname, country, course, language, week FROM users JOIN country ON users.id = country.user_id JOIN countries ON country.country_id = countries.id JOIN language ON users.id = language.user_id JOIN languages ON language.lang_id = languages.id JOIN course ON users.id = course.user_id JOIN courses ON course.course_id = courses.id WHERE"

            # Adds only the fields which were selected and ignore the ones that were not selected
            s = ""
            if country:
                remaining = f" country = '{country}'"
                s += remaining
            if week:
                AND = ""
                if s != "":
                    AND = " AND"
                remaining = f" week = {week}"
                s += AND + remaining  
            if course:
                AND = ""
                if s != "":
                    AND = " AND"
                remaining = f" course = '{course}'"
                s += AND + remaining   
            if language:
                AND = ""
                if s != "":
                    AND = " AND"
                remaining = f" language = '{language}'"
                s += AND + remaining

            # If not input was given
            if s == "":
                flash("Must input atleast one category!", category="error")
                return render_template("search.html", langs=langs)
            query = common + s

            # s is query to be executed!
            session["search"] = db.execute(query)

            for i in range(len(session["search"])):
                id = db.execute("SELECT id FROM users WHERE email = :email", email=session["search"][i]["email"])
                session["search"][i]["id"] = id[0]["id"]

            # Removing the current user from this dictionary
            i = 0
            while i < len(session["search"]):
                if session["search"][i]["id"] == session["user_id"]:
                    session["search"].pop(i)   
                else: i += 1             

            # Removing the repeated people and shifting their language to previous occurence of that id
            NoRepeat(session["search"])
            return render_template("search.html", rows=session["search"], langs=langs)
        
        elif request.form.get("search-page") == "add-friend":
            friend_id = request.form.get("submit")
            # See if the user has already sent the friend request or is already a friend!
            # querying the request table
            requests = db.execute("SELECT * FROM requests WHERE sender = :sender AND reciever = :reciever", 
                sender=session["user_id"], reciever=friend_id)
            
            # querying the friends table (for loop because we have to check both possibilites (1, 2) or (2, 1))
            foundSmting = []
            x = session["user_id"]
            y = friend_id
            for i in range(2):
                friends = db.execute("SELECT * FROM friends WHERE friend1 = :x AND friend2 = :y", x=x, y=y)
                foundSmting.append(len(friends))
                x,y = y,x
            print(foundSmting)

            if len(requests) != 0:
                flash("You have already sent them a friend request, be patient!")
            elif 1 in foundSmting:
                flash("You are already friends with them, why you want to be friends again?")
            else:
                db.execute("INSERT INTO requests (sender, reciever) VALUES (:sender, :reciever)", 
                sender=session["user_id"], reciever=request.form.get("submit"))
                flash("Friend Request Sent!")

            return render_template("search.html", rows=session["search"], langs=langs)

@app.route("/notif", methods=["GET", "POST"])
@login_required
def notif():
    if request.method == "GET":
        friendR = db.execute("SELECT sender FROM requests WHERE reciever = :user", user=session["user_id"])
        # If no notifications
        if len(friendR) == 0:
            return apology("Notifications", "NO")
        # Storing this dictionary as a list to use in next sql query
        IDs = []
        for row in friendR:
            IDs.append(row["sender"])
        
        # To stay away from single element tupple problems
        if len(friendR) == 1:
            IDs = IDs[0]
            rel = "="
        else:
            IDs = tuple(IDs)
            rel = "IN"
        
        # Finding the sender's details
        rows = db.execute(f"SELECT users.id, email, name, surname, country, course, language, week FROM users JOIN country ON users.id = country.user_id JOIN countries ON country.country_id = countries.id JOIN language ON users.id = language.user_id JOIN languages ON language.lang_id = languages.id JOIN course ON users.id = course.user_id JOIN courses ON course.course_id = courses.id WHERE users.id {rel} {IDs}")
        
        # Removing the repeated people and shifting their language to previous occurence of that id
        NoRepeat(rows)
        return render_template("notifs.html", rows=rows)
    else:
        sender = request.form.get("person_id")
        # If the user accepthed the friend request
        if request.form.get("action") == "accepted":
            # Storing the friendship into the friends table
            db.execute("INSERT INTO friends (friend1, friend2) VALUES (:f1, :f2)",
                f1=session["user_id"], f2=sender)
            flash("You are friends now, contact them using their email!")
        
        # Deleting the values from the requests table (is applied weather the requset is accepted or deleted)
        db.execute("DELETE FROM requests WHERE sender = :sender AND reciever = :reciever",
            sender=sender, reciever=session["user_id"])
        db.execute("DELETE FROM requests WHERE sender= :sender AND reciever = :reciever",
            sender=session["user_id"], reciever=sender)

        return redirect("/notif")

@app.route("/friends")
@login_required
def friend():
    friendR = db.execute("SELECT friend1, friend2 FROM friends WHERE friend1 = :person1 OR friend2 = :person2", person1=session["user_id"], person2=session["user_id"])
    # If no friends!
    if len(friendR) == 0:
        return apology("Aww", "No friends")
    
    # Storing this dictionary as a list to use in next sql query
    IDs = []
    for row in friendR:
        if row["friend1"] == session["user_id"]:
            IDs.append(row["friend2"])
        elif row["friend2"] == session["user_id"]:
            IDs.append(row["friend1"])
    
    # To stay away from single element tupple problems
    if len(friendR) == 1:
        IDs = IDs[0]
        rel = "="
    else:
        IDs = tuple(IDs)
        rel = "IN"
    
    # Finding the sender's details
    rows = db.execute(f"SELECT users.id, email, name, surname, country, course, language, week FROM users JOIN country ON users.id = country.user_id JOIN countries ON country.country_id = countries.id JOIN language ON users.id = language.user_id JOIN languages ON language.lang_id = languages.id JOIN course ON users.id = course.user_id JOIN courses ON course.course_id = courses.id WHERE users.id {rel} {IDs}")
    
    # Removing the repeated people and shifting their language to previous occurence of that id
    NoRepeat(rows)
    return render_template("friends.html", rows=rows)


""" Function which removes the repeated people and shift their language to previous occurence of that id """
def NoRepeat(people):
    i = 0
    while i < len(people) - 1:
        if people[i]["id"] == people[i + 1]["id"]:
            people[i]["language"] = f'{people[i]["language"]}, {people[i + 1]["language"]}'
            people.pop(i + 1)
        else: i += 1

@app.route("/about")
def about():
    return render_template("about.html")
                                                                                                                                                                                                                                                                                                                           
@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")



@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "GET":
        """Register user"""
        name = request.args.get("name")
        # Ensure username field is not blank
        if not name:
            return apology("must provide a name", 400)
        
        surname = request.args.get("surname")
        # Ensure that if the surname field is blank, we put a None there
        if not surname:
            surname = None

        email = request.args.get("email")
        # Ensure email field is not blank
        if not email:
            return apology("must provide an email", 400)

        # Ensure email not already exists in the database
        rows = db.execute("SELECT id FROM users WHERE email = :email", email=email)
        if len(rows) != 0:
            return apology("Another user has an account on this email", 400)

        password = request.args.get("password")
        confirm = request.args.get("confirm")

        # Ensure password fields are not empty
        if not password:
            return apology("must provide a password", 400)
        elif not confirm:
            return apology("must confirm the password", 400)

        # Check if the passwords match
        if password != confirm:
            return apology("passwords does not match!", 400)

        if not request.args.get("country"):
            return apology("must provide your country", 400)
        
        # Inserting the data into the databases
        # Inserting in "users"
        user_id = db.execute("INSERT INTO users (name, surname, email, hash, week) VALUES (:name, :surname, :email, :hash, 1)", 
                        name=name, surname=surname, email=email, hash=generate_password_hash(password, method="pbkdf2:sha256", salt_length=8))

        # Saving the user in session dictionary
        session["user_id"] = user_id
        session["name"] = name
        # Inserting country into table if the value not already exists
        country_id_dict = db.execute("SELECT id FROM countries WHERE country = :value", value=request.args.get("country"))
        
        if len(country_id_dict) == 0:
            country_id = db.execute("INSERT INTO countries (country) VALUES (:value)", value=request.args.get("country"))
        else:
            country_id = country_id_dict[0]["id"] 

        # Relating country to the user
        db.execute("INSERT INTO country (user_id, country_id) VALUES (:value_user, :value_country)", 
            value_user=session["user_id"], value_country=country_id)

        # Relating the gender to the user ("genders" table already filled)
        db.execute("INSERT INTO gender (user_id, gender_id) VALUES (:user, :gender)", 
                    user=user_id, gender=request.args.get("gender"))

        # Towards the registration step 2!
        return render_template("registration.html")

    else:
        # Inserting course into table if the value not already exists
        course_id_dict = db.execute("SELECT id FROM courses WHERE course = :value", value=request.form.get("course"))
        
        if len(course_id_dict) == 0:
            course_id = db.execute("INSERT INTO courses (course) VALUES (:value)", value=request.form.get("course"))
        else:
            course_id = course_id_dict[0]["id"] 

        # Relating the course to the user
        db.execute("INSERT INTO course (user_id, course_id) VALUES (:value_user, :value_course)", 
            value_user=session["user_id"], value_course=course_id)

        # Inserting week in "users"
        db.execute("UPDATE users SET week = :week WHERE id = :user_id", week=request.form.get("week"), user_id=session["user_id"])

        # Inserting in "languages" and relating the language to the user
        language_id_dict = db.execute("SELECT id FROM languages WHERE language = :value", value=request.form.get("lang1"))
        if len(language_id_dict) == 0:
            language_id = db.execute("INSERT INTO languages (language) VALUES (:value)", value=request.form.get("lang1"))
        else:
            language_id = language_id_dict[0]["id"] 
        # Relating the language to the user
        db.execute("INSERT INTO language (user_id, lang_id) VALUES (:value_user, :value_language)", 
            value_user=session["user_id"], value_language=language_id)

        if request.form.get("lang2"):
            # Inserting in "languages" and relating the language to the user
            language_id_dict = db.execute("SELECT id FROM languages WHERE language = :value", value=request.form.get("lang2"))
            if len(language_id_dict) == 0:
                language_id = db.execute("INSERT INTO languages (language) VALUES (:value)", value=request.form.get("lang2"))
            else:
                language_id = language_id_dict[0]["id"] 
            # Relating the language to the user
            db.execute("INSERT INTO language (user_id, lang_id) VALUES (:value_user, :value_language)", 
                value_user=session["user_id"], value_language=language_id)

        if request.form.get("lang3"):
            # Inserting in "languages" and relating the language to the user
            language_id_dict = db.execute("SELECT id FROM languages WHERE language = :value", value=request.form.get("lang3"))
            if len(language_id_dict) == 0:
                language_id = db.execute("INSERT INTO languages (language) VALUES (:value)", value=request.form.get("lang3"))
            else:
                language_id = language_id_dict[0]["id"] 
            # Relating the language to the user
            db.execute("INSERT INTO language (user_id, lang_id) VALUES (:value_user, :value_language)", 
                value_user=session["user_id"], value_language=language_id)

        # Final user storage (for navbar purpose)
        session["email"] = request.args.get("email")

        return redirect("/verify")


@app.route("/verify", methods=["GET", "POST"])
def verify():
    if request.method == "GET":
        # User is not verified right now
        session["confirm"] = 'False'
        
        # Sending a verification email
        token = s.dumps(session["email"], salt="chumtiya")

        msg = Message("Class: Verification", sender="raghupalash0@gmail.com", recipients=[session["email"]])
        url = url_for("verified", token=token, _external=True)

        msg.body = "Verify your account by clicking on this <a href={}>link</a>. <p> this link will expire in 5 minutes </p>".format(url)
        mail.send(msg)

        return render_template("verification.html", email=session["email"])
    else:
        # Changing email
        db.execute("UPDATE users SET email = :email WHERE id = :id", email=request.form.get("email"), id=session["user_id"])
        session["email"] = request.form.get("email")

        return redirect("/verify")

@app.route("/verified/<token>")
def verified(token):
    # Verifying if the token is right
    try:
        email = s.loads(token, max_age=3000, return_timestamp=False, salt="chumtiya")
    except SignatureExpired:
        return "Signature Expired, hit resend on the verification page"
        if email != session["email"]:
            return "Access Denied"

    # Modifying the db as the user is verified
    db.execute("UPDATE users SET confirm = 'True' WHERE id = :id", id=session["user_id"])

    return render_template("verified.html", name=session["name"])
        

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
