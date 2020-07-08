import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")



@app.route("/")
@login_required
def index():
    #getting the user's current shares
    info = db.execute("SELECT * FROM current WHERE user_id=:id", id=session["user_id"])

    #getting the user's information
    user = db.execute("SELECT * FROM users WHERE id=:id", id=session["user_id"])
    sum = user[0]["cash"]

    names = []
    symbols = []
    numbers = []
    prices = []
    values = []

    #extracting all required data and storing it in arrays
    for row in info:
        if int(row["shares"]) == 0:
            continue;

        data = lookup(row["symbol"])
        names.append(data["name"])
        symbols.append(data["symbol"])
        numbers.append(row["shares"])
        prices.append(usd(data["price"]))
        values.append(usd(float(row["shares"]) * data["price"]))
        sum += float(row["shares"]) * data["price"]

    return render_template("index.html", leng = len(names), names=names, symbols=symbols, numbers=numbers, prices=prices, values=values, cash = usd(float("{:.3f}".format(user[0]["cash"]))), sum = usd(float("{:.3f}".format(sum))))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

         # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)

        # Ensure number of shares was submitted
        if not request.form.get("shares"):
            return apology("must provide number of shares", 403)

        #call lookup()
        info = lookup(request.form.get("symbol"))

        #ensure symbol is valid
        if info == None:
            return apology("Symbol is invalid", 403)

        #ensure number of shares is valid
        if int(request.form.get("shares")) < 0:
            return apology("Number of shares must be a positive integer", 403)

        #calculating the total cost of the shares
        cost = info["price"] * int(request.form.get("shares"))

        user = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])

        #checking whether the user has enough money
        if cost > float(user[0]["cash"]):
            return apology("Not enough cash", 403)

        #buy the stock for the user
        user[0]["cash"] = user[0]["cash"] - cost

        db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=user[0]["cash"], id=session["user_id"])

        #log purchase in the "buy" table
        db.execute("INSERT INTO buy(user_id, symbol, shares, price) VALUES(?,?,?,?)",
        session["user_id"], request.form.get("symbol"), request.form.get("shares"), info["price"])

        #log purchase in the "current" table
        check = db.execute("SELECT shares FROM (SELECT shares FROM current WHERE user_id = :id AND symbol = :sym UNION ALL SELECT 0) A ORDER BY shares DESC LIMIT 1", id=session["user_id"], sym=request.form.get("symbol"))

        if check[0]["shares"] == 0:
            db.execute("INSERT INTO current(user_id, symbol, shares) VALUES(?,?,?)",
            session["user_id"], request.form.get("symbol"), request.form.get("shares"))
        else:
            value = int(check[0]["shares"]) + int(request.form.get("shares"))
            db.execute("UPDATE current set shares = :share WHERE user_id = :id AND symbol = :sym", share = value, id = session["user_id"], sym=request.form.get("symbol"))

        return render_template("bought.html", name = info["name"], number = request.form.get("shares"), price = usd(info["price"]))


    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    info = db.execute("SELECT * FROM buy WHERE user_id = :id", id = session["user_id"])
    for row in info:
        row["price"] = usd(row["price"])
    return render_template("history.html", info = info)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)

        #call lookup()
        info = lookup(request.form.get("symbol"))

        #ensure symbol is valid
        if info == None:
            return apology("Symbol is invalid", 403)

        return render_template("quoted.html", name = info["name"], symbol = info["symbol"], price = usd(info["price"]))

    else:
        return render_template("quote.html")

symbol1 = ""

@app.route("/bgraph", methods=["GET", "POST"])
@login_required
def bgraph():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)

        #call lookup()
        info = lookup(request.form.get("symbol"))

        #ensure symbol is valid
        if info == None:
            return apology("Symbol is invalid", 403)

        global symbol1
        symbol1 = request.form.get("symbol")

        return render_template("graph.html", symbol = info["name"]);

    else:
        return render_template("bgraph.html")

@app.route("/graph")
@login_required
def graph():
    """Get stock quote."""
    info = lookup(symbol1)
    test = 5
    return jsonify(info["price"])


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure password was submitted
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username does not already exist
        if len(rows) == 1:
            return apology("username already exists", 403)

        #insert the user into the database
        db.execute("INSERT INTO users(username, hash) VALUES(?,?)", request.form.get("username"), generate_password_hash(request.form.get("password")) )

        rows = db.execute("SELECT * FROM users WHERE username = :username",
        username=request.form.get("username"))

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

         # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)

        # Ensure number of shares was submitted
        if not request.form.get("shares"):
            return apology("must provide number of shares", 403)

        #call lookup()
        info = lookup(request.form.get("symbol"))

        #ensure symbol is valid
        if info == None:
            return apology("Symbol is invalid", 403)

        #ensure number of shares is valid
        if int(request.form.get("shares")) < 0:
            return apology("Number of shares must be a positive integer", 403)

        #calculating the total cost of the shares
        cost = info["price"] * int(request.form.get("shares"))

        user = db.execute("SELECT * FROM current WHERE user_id = :id AND symbol = :sym", id=session["user_id"], sym = request.form.get("symbol"))
        this = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])

        #checking whether the user owns enough shares
        if int(request.form.get("shares")) > int(user[0]["shares"]):
            return apology("Not enough shares", 403)

        #sell the stock for the user
        this[0]["cash"] = this[0]["cash"] + cost

        db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=this[0]["cash"], id=session["user_id"])

        #log purchase in the "buy" table
        bs = str(int(request.form.get("shares")) * -1)

        db.execute("INSERT INTO buy(user_id, symbol, shares, price) VALUES(?,?,?,?)",
        session["user_id"], request.form.get("symbol"),bs, info["price"])

        #log purchase in the "current" table
        check = db.execute("SELECT shares FROM (SELECT shares FROM current WHERE user_id = :id AND symbol = :sym UNION ALL SELECT 0) A ORDER BY shares DESC LIMIT 1", id=session["user_id"], sym=request.form.get("symbol"))

        if check == 0:
            db.execute("INSERT INTO current(user_id, symbol, shares) VALUES(?,?,?)",
            session["user_id"], request.form.get("symbol"), request.form.get("shares"))
        else:
            value = int(check[0]["shares"]) - int(request.form.get("shares"))
            db.execute("UPDATE current set shares = :share WHERE user_id = :id AND symbol = :sym", share = value, id = session["user_id"], sym=request.form.get("symbol"))


        return render_template("sold.html", name = info["name"], number = request.form.get("shares"), price = usd(info["price"]))


    else:
        symbols = db.execute("SELECT symbol FROM current WHERE user_id = :id", id = session["user_id"])
        sym = []
        for row in symbols:
            sym.append(row["symbol"])
        return render_template("sell.html", symbols = sym)



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
