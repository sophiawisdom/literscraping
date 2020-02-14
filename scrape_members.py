import sqlite3
import requests
import bs4
import multiprocessing
import string
import queue
import time

sql_attr_order = ["key","gender","age","weight","height","location","orientation",\
                   "interested in", "status", "smoke", "drink", "fetishes",\
                   "pets", "member since", "last modified", 'description']

def parse_member(link):
    r = requests.get(link)
    r.raise_for_status()
    soup = bs4.BeautifulSoup(r.text, 'html5lib')
    table = soup.find("table", {"style":"margin-top: 2px;", 'width':"100%", 'cellspacing':"0", 'cellpadding':"1", 'border':"0"})
    try:
        tbody = next(table.children)
    except AttributeError:
        return # This means there is no descriptor table - because they are banned
    descriptors = tbody.findAll("td", {"class":"nl"})
    attrs = {}
    for descriptor in descriptors:
        key = descriptor.text.strip(":").lower()
        value = descriptor.nextSibling.text.strip("\xa0").lower()
        attrs[key] = value

    paragraphs = soup.findAll("p",{"class":"pnew"})
    attrs['description'] = "\n".join([line.text for line in paragraphs])
    attrs['key'] = int(link.split("=")[1])
    if "age" not in attrs:
        attrs['age'] = 'None' # when age isn't given, isn't listed. Weird
    return attrs
    

def commit_sql(sql_queue, database = "liter.db"):
    connection = sqlite3.connect(database)
    cursor = connection.cursor()
    while 1:
        transaction = []
        while 1:
            try:
                transaction.append(sql_queue.get(timeout=1))
            except queue.Empty:
                break
        cursor.executemany("INSERT INTO members VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", transaction)
        connection.commit()
        print(f"Committed {len(transaction)} members into SQLite")
        if not sql_queue.qsize():
            time.sleep(10)

def member_scrape_process(members_queue, sqlite_queue):
    while 1:
        try:
            member_link = members_queue.get(timeout=1)
        except queue.Empty:
            print(f"members_queue failed. Queue size is {members_queue.qsize()}, exiting now")
            break
        attribute_dict = parse_member(member_link)
        if attribute_dict == None:
            continue
        sql_form = []
        for attribute in sql_attr_order:
            if attribute in attribute_dict:
                sql_form.append(attribute_dict[attribute])
            else:
                sql_form.append("None")
#        print(f"Appended sql_form of length {len(sql_form)}")
        sqlite_queue.put(sql_form)

    print("Process exiting!")

def scrape_members(members, scrape_processes = 10):
    members_queue = multiprocessing.Queue(len(members))
    for member in members:
        members_queue.put(member)
    sqlite_queue = multiprocessing.Queue()

    print(f"Set up queues. {members_queue.qsize()} items in members_queue")

    processes = []
    for p in range(scrape_processes):
        process = multiprocessing.Process(target=member_scrape_process,
                                          args = (members_queue, sqlite_queue))
        process.start()
        processes.append(process)

    sql_process = multiprocessing.Process(target=commit_sql, \
                                          args = (sqlite_queue,))
    sql_process.start()
    print("Started all processes")
    while 1:
        try:
            size = members_queue.qsize()
            print(f"Currently {size} members left to be scraped!")
        except NotImplementedError:
            pass
        time.sleep(20)
