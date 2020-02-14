import sqlite3

file = open("liter.db",'w')
file.close()
conn = sqlite3.connect("liter.db")
c = conn.cursor()
c.execute("""CREATE TABLE members(
member_id INTEGER PRIMARY KEY,
gender TEXT,
age TEXT,
weight TEXT, -- 0 for no answer
height TEXT, -- 0 
location TEXT,
orientation TEXT,
interested_in TEXT,
status TEXT,
smoke TEXT,
drink TEXT,
fetishes TEXT,
pets TEXT,
member_since TEXT,
last_modified TEXT,
personal_description DESC,
name TEXT
);""")
c.execute("""CREATE TABLE stories(
title TEXT,
filename TEXT,
author_id INTEGER,
rating INTEGER,
num_comments INTEGER,
num_favorites INTEGER,
num_views INTEGER,
date_posted TEXT,
category TEXT,
series_id INTEGER,
tags TEXT,
blurb TEXT,
FOREIGN KEY (author_id) REFERENCES members(member_id),
FOREIGN KEY (series_id) REFERENCES series(series_id)
);""")
c.execute("""CREATE TABLE favorites(
member_id INTEGER,
story_id INTEGER,
FOREIGN KEY (member_id) REFERENCES members(member_id),
FOREIGN KEY (story_id) REFERENCES stories(rowid)
);""")
c.execute("""CREATE TABLE tags(
story_id INTEGER PRIMARY KEY,
tag1 TEXT,
tag2 TEXT,
tag3 TEXT,
tag4 TEXT,
tag5 TEXT,
tag6 TEXT,
tag7 TEXT,
tag8 TEXT,
tag9 TEXT,
tag10 INTEGER,
FOREIGN KEY (story_id) REFERENCES stories(rowid)
);""")
c.execute("""CREATE TABLE comments(
comment_id INTEGER PRIMARY KEY,
poster_id INTEGER, -- 0 if poster is anonymous
story_id INTEGER,
date_posted TEXT,
comment_text TEXT
member_id INTEGER,
FOREIGN KEY (story_id) REFERENCES stories(rowid)
FOREIGN KEY (poster_id) REFERENCES members(story_id)
);""")
c.execute("""CREATE TABLE series(
series_id INTEGER PRIMARY KEY,
name TEXT,
member_id INTEGER,
FOREIGN KEY (member_id) REFERENCES members(member_id)
);""")
conn.commit()
conn.close()
