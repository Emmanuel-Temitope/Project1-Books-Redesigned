from csv import reader
import os
from sqlalchemy import *
from sqlalchemy.orm import scoped_session, sessionmaker


engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

def main():
	try:
		db.execute("CREATE TABLE books(id SERIAL PRIMARY KEY, isbn VARCHAR NOT NULL, \
		 title VARCHAR NOT NULL, author VARCHAR NOT NULL, year VARCHAR NOT NULL, \
		 review_count INTEGER DEFAULT 0, average_count DECIMAL DEFAULT 0.0 );")
		book = open('books.csv')
		books = reader(book)
		for isbn, title, author, year in books:
			db.execute("INSERT INTO books (isbn,title,author,year) VALUES (:isbn, :title, :author, :year)",
						{"isbn":isbn, "title":title, "author":author, "year":year})
		db.commit()
	except Exception as e:
		raise e

if __name__ == "__main__":
	main()