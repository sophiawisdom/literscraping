import requests
import bs4
import threading
import time
from constants import *
import sqlite3
import os
import multiprocessing
import queue
import json

category_queue = []
story_queue = set()
current_threads = 0
failed_categories = []
max_threads = 50
story_sqlite = []

def update_metadata(link):
    r = requests.get(link)
    r.raise_for_status()
    soup = bs4.BeautifulSoup(r.text, 'html5lib')
    stories = soup.findAll("div",{"class":"b-sl-item-r w-34t"})
    metadata = []

    for story in stories:
        filename = story.a['href'].split("/")[4]
        description = story.span.text[3:] # starts with \xa0-\xa0
        date = story.find("span",{"class":"b-sli-date"}).text
        try:
            rating = story.find("span", {"class":"b-sli-rating"}).text
        except Exception:
            rating = None
        metadata.append((filename, description, date, rating))

    return metadata

def metadata_process(c_queue, metadata_queue):
    while 1:
        try:
            link = c_queue.get(timeout=1)
        except queue.Empty:
            print("Queue is empty! Exiting now")
            break
        metadata = update_metadata(link)
        for story in metadata:
            metadata_queue.put(story)
        print(f"Added {len(metadata)} stories to metadata_queue!")
    print("Exiting!")

def update_all_metadata(scrape_processes = 10):
    global category_queue
    category_queue = []
    for cat in categories:
        scrape_category(cat)

    c_queue = multiprocessing.Queue(len(category_queue))
    for i in category_queue:
        c_queue.put(i)

    metadata_queue = multiprocessing.Queue()
    all_metadata = []

    processes = []

    for i in range(scrape_processes):
        p = multiprocessing.Process(target=metadata_process, args=(c_queue, metadata_queue))
        p.start()
        processes.append(p)

    while 1:
        try:
            all_metadata.append(metadata_queue.get(timeout=1))
        except queue.Empty:
            if not c_queue.qsize():
                print("c_queue is empty, exiting loop!")
                break

    while 1:
        try:
            all_metadata.append(metadata_queue.get(timeout=10))
        except queue.Empty:
            break

    print(f"Writing results to file!")
    file = open("metadata", 'w')
    file.write(json.dumps(all_metadata))
    file.close()
    print("Wrote results to file metadata!")

def scrape_category_page(link):
    global failed_categories
    try:
        r = requests.get(link)
        r.raise_for_status()
    except BaseException:
        failed_categories.append(link)
        return
    soup = bs4.BeautifulSoup(r.text, 'html5lib')
    stories = soup.findAll("a",attrs={"class":"r-34i"})
    print(f"Just scraped {link}. Found {len(stories)} stories!")
    for story in stories:
        story_queue.add(story['href'])

def scrape_category(category):
    global category_queue
    global current_threads
    current_threads += 1
    url = f"{category_urls[category]}/" + "{0}-page" # different formatting systems
    r = requests.get(url.format(1))
    r.raise_for_status()
    soup = bs4.BeautifulSoup(r.text, 'html5lib')
    page_listing = soup.findAll(attrs={"name":"page"})
    if len(page_listing) != 1:
        raise ValueError(f"name=page returned {['less','more'][len(page_listing) > 1]} than 1 result when scraping {category} ({len(page_listing)})")
    pages = [child.text for child in page_listing[0]]
    print(f"There are {len(pages)} pages to be scraped for category {category}")
    for page in pages:
        category_queue.append(url.format(page))
    current_threads -= 1

def scrape_categories():
    global category_queue
    global story_queue
    global current_threads
    for category in categories:
        print(f"Scraping {category}")
        scrape_category(category)
    print(f"Finished getting lists for categories. {len(category_queue)} stories in category queue")
    while category_queue:
        while current_threads > max_threads:
            time.sleep(.1)
            if time.time() % 30 < .5:
                print(f"There are {len(category_queue)} stories left in the queue")
        for a in range(max_threads-current_threads):
            try:
                cat_link = category_queue.pop()
            except IndexError: # list is empty
                print("Category queue is empty! Writing back!")
                break
            threading.Thread(target=scrape_category_page, args=(cat_link,)).start()
    print("Just finished scraping!")
    start = time.time()
    while threading.active_count() > 3:
        if time.time() - start > 30:
            print("It's been 30 seconds, writing now.")
            break
        time.sleep(1)
        print(f"There are {current_threads} current threads")
    file = open("story_queue",'w')
    file.write("\n".join(story_queue))
    file.close()
    print(f"Finished writing {len(story_queue)} stories to file")
