#!/bin/env python3

import argparse
import heapq
import os
import shutil
import sys
import threading
import time

from collections import defaultdict
from queue import Queue, Empty
from select import select

def tail(fname, queue, shutdown):
    with open(fname) as f:
        f.seek(0, 2)
        while not shutdown.is_set():
            sel = None
            if not (sel := select([f], [], [], 0.01))[0]:
                continue

            line = f.readline()
            if line:
                queue.put((fname, line.strip()))


def log_fetcher(q):
    while True:
        try:
            log, line = q.get()
        except Empty:
            continue

        yield (log, line)


def gc(db, window):
    now = time.time()
    killed = []
    for ip, agelist in db.items():
        while agelist and now - agelist[0] > window:
            agelist.pop(0)
        if not agelist:
            killed.append(ip)
    for ip in killed:
        del(db[ip])


def display(db, window, nolines, delay, dblock, shutdown):
    while not shutdown.is_set():
        width = shutil.get_terminal_size(fallback=(80, 25))[0]
        # see format string below
        bar_max = width - 24

        timestamp = time.strftime('%F %T', time.localtime())

        print(f'\033c{timestamp:>{width}}')
        print(f'delay: {delay}s  entries: {nolines}  collect window: {window}s', end='\n\n') 
        print(f'{"IP":>15}  {"Hits":>6}')

        heap = []
        dblock.acquire()
        for ip, hitlist in db.items():
            heapq.heappush(heap, (len(hitlist), ip))
        dblock.release()

        for hits, ip in heapq.nlargest(nolines, heap):
            bar = '#' * min(bar_max, int(hits))
            print(f'{ip:>15}: {hits:>6d} {bar}')

        dblock.acquire()
        gc(db, window)
        dblock.release()

        # A long time.sleep would block the shutdown...
        for i in range(delay):
            time.sleep(1)
            if shutdown.is_set():
                break


def main():
    cmdline = argparse.ArgumentParser(description='top for httpd access logs')
    cmdline.add_argument('--window', '-w', type=int, default=60, help='Time window over which to count the IPs')
    cmdline.add_argument('--delay', '-d', type=int, default=1, help='Update delay')
    cmdline.add_argument('--nolines', '-n', type=int, default=10, help='Maximum number of IPs to show')
    cmdline.add_argument('file', nargs='+', help='Log file')
    opts = cmdline.parse_args(sys.argv[1:])

    shutdown = threading.Event()
    q = Queue()
    db = defaultdict(list)
    dblock = threading.Semaphore()

    threads = [threading.Thread(target=tail, args=(log, q, shutdown)) for log in opts.file]
    threads.append(threading.Thread(target=display, args=(db, opts.window, opts.nolines, opts.delay, dblock, shutdown)))

    for t in threads:
        t.start()

    try:
        for log, line in log_fetcher(q):
            now = time.time()

            ip = line[:line.find(' ')]

            dblock.acquire()
            db[ip].append(now)
            dblock.release()
    except KeyboardInterrupt:
        pass

    shutdown.set()
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
