#!/bin/env python3

# ruff: noqa: ANN001, ANN201

import argparse
import heapq
import re
import shutil
import sys
import time

from collections import defaultdict
from queue import Empty, Queue
from select import select
from threading import Event, Semaphore, Thread

LOG_FORMATS = {
    'apache': r'^(\S+)',
    'vhosts': r'^\S+\s(\S+)',
}

def tail(fname, q, shutdown):
    try:
        with open(fname) as f:
            f.seek(0, 2)
            while not shutdown.is_set():
                if not (select([f], [], [], 0.01))[0]:
                    continue

                line = f.readline()
                if line:
                    q.put((fname, line.strip()))
    except FileNotFoundError:
        print(f'Filename {fname} not found', file=sys.stderr)
        shutdown.set()


def log_fetcher(q, shutdown):
    while not shutdown.is_set():
        try:
            log, line = q.get(False, 0.01)
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


def display(db, window, nolines, delay, dblock, shutdown):  # noqa: PLR0913
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
        for _ in range(delay):
            time.sleep(1)
            if shutdown.is_set():
                break


def main():
    log_formats = list(LOG_FORMATS.keys())

    cmdline = argparse.ArgumentParser(description='top for httpd access logs')
    cmdline.add_argument('--delay', '-d', type=int, default=1, help='Update delay')
    cmdline.add_argument('--nolines', '-n', type=int, default=10, help='Maximum number of IPs to show')
    cmdline.add_argument('--window', '-w', type=int, default=60, help='Time window over which to count the IPs')
    cmdline.add_argument('--logformat', '-l', choices=log_formats, default=log_formats[0], help='httpd log format')
    cmdline.add_argument('--logrx', '-r', type=str, help='Regular expression to extract the source IP from the log line')
    cmdline.add_argument('file', nargs='+', help='Log file')
    opts = cmdline.parse_args(sys.argv[1:])

    if opts.logrx:
        opts.logformat = 'custom'
        LOG_FORMATS[opts.logformat] = opts.logrx

    shutdown = Event()
    q = Queue()
    db = defaultdict(list)
    dblock = Semaphore()

    threads = [Thread(target=tail, args=(log, q, shutdown)) for log in opts.file]
    threads.append(Thread(target=display, args=(db, opts.window, opts.nolines, opts.delay, dblock, shutdown)))

    for t in threads:
        t.start()

    log_rx = re.compile(LOG_FORMATS[opts.logformat])
    try:
        for log, line in log_fetcher(q, shutdown):  # noqa: B007
            print('tick')
            if shutdown.is_set():
                break

            now = time.time()

            match = log_rx.search(line)
            ip = match.group(1) if match else 'PARSE ERROR'

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
