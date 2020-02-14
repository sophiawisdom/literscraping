import requests
import multiprocessing
import bs4
import time
import sqlite3
import os
import random

from constants import * # e.g. category listing

category_queue = []
story_queue = set()
current_threads = 0
failed_categories = []
max_threads = 50
story_sqlite = []

def parse_story(soup):
    results = soup.findAll("div",{"class":"b-story-body-x x-r15"})
    text = results[0].div.p.text
    return text.split("\n\n")

def parse_last(soup):
    if soup.title.text == 'Literotica.com - error':
        return # sometimes there are shells. See: https://www.literotica.com/s/our-little-secret
    stats = soup.findAll("span", {"class":"b-story-stats"})
    stats = stats[0]
    stats = stats.text.split()
    num_comments = int(stats[0])
    num_views = int(stats[2])
    num_favorites = int(stats[4])
    title = soup.findAll("div",{"class":"b-story-header"})[0].h1.text
    author = soup.findAll("span",{"class":"b-story-user-y x-r22"})[0].a
    author_uid = int(author['href'].split("?")[1].split("&")[0].split("=")[1])
    author_name = author.text
    try:
        tags = soup.findAll("div",{"class":"b-s-story-tag-list"})[0].ul
    except IndexError: # some have no tags
        tags = []
    tags = [tag.a.text for tag in tags]
    category = soup.findAll("div",{"class":"b-breadcrumbs"})[0]
    category = category.findAll("a")[1].text
    return num_comments, num_views, num_favorites, title, author_uid, tags, category

def scrape_story(link, just_metadata = False):
    filename = link.split("/")[4] # they already did the cleaning, take advantage
    if link.startswith("//"):
        link = "http:" + link
    r = requests.get(link)
    if r.status_code == 410: # page removed -- not our fault
        return
    r.raise_for_status()

    soup = bs4.BeautifulSoup(r.text, 'html5lib')
    results = soup.findAll("select",{"name":"page"})
    if len(results) > 1:
        raise ValueError(f"more than one result returned for select.name=page. Should only 1 or 0")

    if len(results) == 0:
        text = parse_story(soup)
        num_comments, num_views, num_favorites, title, author_uid, tags, category = parse_last(soup)
        if just_metadata:
            return title, filename, author_uid, None, num_comments, num_favorites, num_views, None, category, None, "\t".join(tags)

    else:
        selector = results[0]
        if just_metadata:
            for child in selector:
                pass
            r = requests.get(link + f"?page={child.text}")
            r.raise_for_status()
            soup = bs4.BeautifulSoup(r.text, 'html5lib')
            num_comments, num_views, num_favorites, title, author_uid, tags, category = parse_last(soup)
            return title, filename, author_uid, None, num_comments, num_favorites, num_views, None, category, None, "\t".join(tags)
        text = parse_story(soup)
        for child in selector:
            if child.text == "1":
                continue
            r = requests.get(link + f"?page={child.text}")
            soup = bs4.BeautifulSoup(r.text, 'html5lib')
            text.extend(parse_story(soup))
        num_comments, num_views, num_favorites, title, author_uid, tags, category = parse_last(soup)

    if not just_metadata:
        with open(f"story_text/{filename}", 'w') as file:
            file.write("\n".join(text))

    return title, filename, author_uid, None, num_comments, num_favorites, num_views, None, category, None, "\t".join(tags)

def story_scrape_process(story_queue, sqlite_queue, just_metadata=False):
    while story_queue:
        story_link = story_queue.get()
        if not just_metadata and os.path.exists("story_text/" + story_link.split("/")[4]):
            continue
        sql_data = scrape_story(story_link, just_metadata)
        if not sql_data:
            continue
        if random.randint(0, 3000) == 0:            
            print(f"Appended sql_data {sql_data}")
        sqlite_queue.put(sql_data)

def run_sqlite(sqlite_queue, transaction_size = 1000):
    conn = sqlite3.connect("liter.db")
    cursor = conn.cursor()
    print("Loaded up SQLite connection")
    last_ran = time.time()
    s = 0
    try:
        while 1:
            local_queue = []
            for i in range(transaction_size): # guestimate - tradeoff is performance and potential data loss
                local_queue.append(sqlite_queue.get())
                s += 1
            cursor.executemany("INSERT INTO stories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", local_queue)
            conn.commit()
            print(f"Committed {transaction_size} items to SQLite, {s} total")
            last_run = time.time()
    except Exception as e:
        print(e)
        time.sleep(1)
    conn.close()

def scrape_stories(stories, process_count = 40, just_metadata=False):
    sqlite_queue = multiprocessing.Queue(5000) # no larger than 5000 to prevent fuckups
    story_queue = multiprocessing.Queue(len(stories))
    for story in stories:
        story_queue.put(story)
    sqlite_process = multiprocessing.Process(target=run_sqlite, args=(sqlite_queue,))
    sqlite_process.start()
    num_cpus = multiprocessing.cpu_count()
    scraping_processes = []
    for i in range(process_count): # however many running processes you want to have
        scraping_process = multiprocessing.Process(target=story_scrape_process,\
                                                   args = (story_queue, sqlite_queue, just_metadata))
        scraping_process.start()
        scraping_processes.append(scraping_process)
    print(f"Started {len(scraping_processes)} processes!")
    last_size = story_queue.qsize()
    while 1:
        time.sleep(10)
        curr_size = story_queue.qsize()
        diff = last_size - curr_size
        print(f"Story queue has {curr_size} items, {diff} less than before = {diff/10} per second.")
        last_size = curr_size

def refresh_queue():
    global story_queue
    file = open("story_queue")
    data = file.read()
    file.close()
    data = data.split("\n")
    story_queue = data
