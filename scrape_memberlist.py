import sqlite3
import requests
import bs4
import multiprocessing
import string
import queue
import time

def get_authors(soup):
    return [int(a['href'].split("=")[1]) for a in soup.findAll("a",{"class":"AuthorComponent__author__title___35k2X"})]

def scrape_memberlist_link(link):
    r = requests.get(link)
    r.raise_for_status()
    soup = bs4.BeautifulSoup(r.text, 'html5lib')
    authors = get_authors(soup)
    pages = soup.findAll("a",{"class":"Pagination__pagination__item___xxTpq"})
    if len(pages) == 0:
        return authors
    max_page = pages[-1].text
    max_page = int(max_page)
    for page in range(2, max_page+1):
        r = requests.get(link + f"&page={page}")
        r.raise_for_status()
        soup = bs4.BeautifulSoup(r.text, 'html5lib')
        authors.extend(get_authors(soup))
    return authors
    

def memberlist_process(search_queue, member_queue, done_queue):
    base_link = "https://search.literotica.com/?type=member&sort=date&query="
    while 1:
        try:
            combination = search_queue.get(timeout=20)
        except queue.Empty:
            break
        link = base_link + combination
        potential_members = scrape_memberlist_link(link)
        print(f"Scraped {combination}! Found {len(potential_members)} potentials!")
        for member in potential_members:
            member_queue.put(member)
    print("Process finished.")
    done_queue.put(1)

def scrape_all_members(scrape_processes = 10, filename="member_links"):
    # We can scrape through members through https://search.literotica.com/?type=member&query=aaa
    # Any three letter combination. Just run through every combination and collect the data
    search_terms = multiprocessing.Queue(26**3)
    member_list = multiprocessing.Queue()
    for l1 in string.ascii_lowercase:
        for l2 in string.ascii_lowercase:
            for l3 in string.ascii_lowercase:
                search_terms.put(''.join((l1,l2,l3)))
    done_queue = multiprocessing.Queue(scrape_processes)
    print("Queues created! Starting processes.")

    processes = []
    for i in range(scrape_processes):
        process = multiprocessing.Process(target=memberlist_process,\
                                          args=(search_terms,member_list, done_queue))
        process.start()
        processes.append(process)

    print("Started processes!")

    time.sleep(10)
    member_links = set()
    num_done = 0
    last_printed = 0
    while 1:
        try:
            member_link = member_list.get(block=False)
        except queue.Empty:
            while 1:
                try:
                    done_queue.get(block=False)
                    print("Additional scrape process has finished!")
                    num_done += 1
                except queue.Empty:
                    break
            if num_done == scrape_processes:
                print("All scrape processes completed!")
                break
            time.sleep(1)
        member_links.add(member_link)
        if len(member_links) % 1000 == 0 and len(member_links) != last_printed:
            last_printed = len(member_links)
            print(f"member_links now has {len(member_links)} members!")
            with open(filename, 'w') as file:
                file.write("\n".join(member_links))
                file.close()

    print("Writing {len(member_links)} member links to {filename}")
    with open(filename, 'w') as file:
        file.write("\n".join(member_links))

