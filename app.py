import os

from flask import Flask, session, render_template, redirect, flash, request, url_for, jsonify
from flask_session import Session
from sqlalchemy import *
from sqlalchemy.orm import scoped_session, sessionmaker
from functools import wraps
from wtforms import Form, TextField, PasswordField, BooleanField, validators
from passlib.hash import sha256_crypt
import requests
import gc

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["DATABASE_URL"] = 'postgres://zskmzakb:GCQ-GfroFibuP9a-XgBJoIhvjHvnrbo1@isilo.db.elephantsql.com:5432/zskmzakb'
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


def main():
	try:
		db.execute("CREATE TABLE users \
			(id SERIAL PRIMARY KEY, username VARCHAR NOT NULL, email VARCHAR NOT NULL, password VARCHAR NOT NULL);")
		db.execute("CREATE TABLE reviews \
			(id SERIAL PRIMARY KEY, rate INTEGER NOT NULL, r_text VARCHAR NOT NULL, book_id INTEGER REFERENCES books, \
			user_id INTEGER REFERENCES users);")
		db.commit()
	except Exception as e:
		raise e



@app.route("/")
def home():

	return render_template("homepage.html")

@app.route("/explore/", methods=["GET"])
def explore():
	l = db.execute("SELECT id, title, author FROM books LIMIT 51;").fetchall()
	book_info = []
	for list in l:
		book_info.append([list.id, list.title, list.author])
	return render_template("explore.html", details=book_info)


class RegistrationForm(Form):
	"""docstring for RegistrationForm"""
	username = TextField('Username', [validators.Length(min=4, max=20)])
	email = TextField('Email Address', [validators.Length(min=6, max=50)])
	password = PasswordField('Password', [validators.DataRequired(), validators.Length(min=5, max=25),
											validators.EqualTo('confirm', message="Passwords must match.")])
	confirm = PasswordField('Repeat Password')


@app.route("/sign-up/", methods=["GET", "POST"])
def signup_page():
	try:
		form = RegistrationForm(request.form)

		if request.method == "POST" and form.validate():
			username = form.username.data
			email = form.email.data
			password = sha256_crypt.hash((str(form.password.data)))

			x = db.execute("SELECT * FROM users WHERE username = :username",
							{"username": username}).fetchone()

			if x is None:
				db.execute("INSERT INTO users (username, email, password) VALUES (:username, :email, :password)",
							{"username": username, "email": email, "password": password})
				print('''

					ADDED USER!!!!
					''')
				db.commit()
				flash("Thanks for Registering!")	
				gc.collect()

				return redirect(url_for('login_page'))
			elif x[1] == form.username.data:
				flash("That username is already taken, please choose another")
				return render_template("signup-page.html", form=form)
			else:
				pass
		return render_template("signup-page.html", form=form)
	except Exception as e:
		raise e
	return render_template("signup-page.html")


@app.route("/log-in/", methods=["GET", "POST"])
def login_page():
	error = ''
	try:
		if request.method == "POST":
			data = db.execute("SELECT * FROM users WHERE username = :username",
								{"username": request.form.get("username")}).fetchone()
			data = data[3]
			
			if sha256_crypt.verify(request.form.get("password"), data):
				user_id = db.execute("SELECT id FROM users WHERE username = :username",
					{"username": request.form.get("username")}).fetchone()
				session['logged_in'] = True
				session['user_id'] = user_id.id
				flash("You are now logged in")
				return redirect(url_for('home'))
			else:
				error='Invalid Credentials, try again!'
				flash(error)
		gc.collect()
		return render_template("login-page.html", error=error)
	except Exception as e:
		error='Invalid Credentials, try again!'
		flash(error)
		return render_template("login-page.html")

def login_required(f):
	@wraps(f)
	def wrap(*args, **kwargs):
		if 'logged_in' in session:
			return f(*args, **kwargs)
		else:
			flash("You need to login first")
			redirect(url_for('login_page'))
	return wrap


@app.route("/log-out/")
# @login_required
def logout():
	session.clear()
	flash("You have been logged out.")
	gc.collect()
	return redirect(url_for('home'))


@app.route("/search-page/", methods=["POST"])
def search():
	word = request.form.get("search")
	print(word)
	try:
		results = db.execute("SELECT * FROM books WHERE title LIKE :word OR author LIKE :word OR year LIKE :word OR isbn LIKE :word",
															{"word":'%{}%'.format(word.capitalize())}).fetchall()
	except Exception as e:
		return render_template("error.html", message='e')

	return render_template("search.html", word=word, results=results)


@app.route("/book/<int:book_id>/", methods=["POST"])
def book_details(book_id):
	u_id = session['user_id']
	try:
		result = db.execute("SELECT * FROM books WHERE id = :book_id",
					{"book_id": book_id}).fetchone()
		check = db.execute("SELECT * FROM reviews WHERE user_id = :user_id AND book_id = :book_id",
					{"user_id": u_id, "book_id":book_id}).fetchone()
		res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "0t0Vd7DsYxtHbEtpYG1LyQ", "isbns": result.isbn})
		data = res.json()
		wrc = data['books'][0]['work_ratings_count']
		ar = data['books'][0]['average_rating']
		infos = []
		for info in result:
			infos.append(info)
		print(book_id, result.isbn)
	    
		reviews = []
		l = db.execute("SELECT r_text, rate, username, book_id FROM reviews JOIN users ON users.id = reviews.user_id WHERE book_id = \
						:book_id", {"book_id": book_id}).fetchall()
		for le in l:
			print(le)
			reviews.append(le)

	except Exception as e:
		return render_template("error.html", message='Oops network error, Try Again later!')
	return render_template("book-info.html", info=infos, check=check, reviews=reviews, wrc=wrc, ar=ar)


@app.route("/book/review/<int:book_id>/", methods=["POST"])
def review_add(book_id):
	rate = request.form.get('review-s')
	r_text = request.form.get('review-t')

	if r_text.strip(' ') == '':
		return render_template('error.html', message='Leave a valid message there')



	book_avg = db.execute("SELECT AVG(review_count) FROM books WHERE id = :book_id",
				{"book_id": book_id}).fetchone()

	db.execute("INSERT INTO reviews (book_id, user_id, rate, r_text) VALUES (:book_id, :user_id, :rate, :r_text)",
				{"book_id":book_id, "user_id": session["user_id"], "rate":rate, "r_text":r_text}) 

	db.execute("UPDATE books SET review_count = review_count + 1 WHERE id = :book_id",
				{"book_id": book_id})
	db.execute("UPDATE books SET average_count = :ac WHERE id = :book_id",
				{"book_id": book_id, "ac": book_avg[0]})

	db.commit()


	flash("Review added Successfully!")
	return render_template("review.html")

@app.route("/api/<isbn>/", methods=['GET'])
def api_pass(isbn):
	book = db.execute("SELECT * FROM books WHERE isbn = :isbn",
				{"isbn": isbn}).fetchone()
	# Make sure book exists
	if book is None:
		return jsonify({"error": "Invalid book isbn"}), 422
	# Get all Book details
	a_s = float(book.average_count)
	return jsonify({
		"title" : book.title,
		"author" : book.author,
		"year" : book.year,
		"isbn" : book.isbn,
		"review_count" : book.review_count,
		"average_score" : a_s
		})

@app.errorhandler(404)
def page(message):
    return render_template("404.html")

@app.errorhandler(405)
def page(message):
    return render_template("405.html")

@app.errorhandler(500)
def page(message):
    return render_template("error.html", message='500 error. Please return to the homepage and try again.')


if __name__ == "__main__":
	main()

# key: 0t0Vd7DsYxtHbEtpYG1LyQ
# secret: zjXnh03raO4ltraH37WnSQ4mGuyf8T3lByaY0HMc