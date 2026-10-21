"""Builds a ~195 MB, 1500-page course-pack PDF for the end-to-end upload test.

Each page has real text (so it can be searched and quizzed) plus a noise image, which is
incompressible and pushes the file size toward the 200 MB limit like scanned figures would.
A few pages carry distinctive facts at known page numbers to check retrieval end to end.
"""

import random
import sys

import pymupdf

PAGES = 1500
TARGET_BYTES = 195 * 1024 * 1024

TOPICS = [
    (
        "Process scheduling",
        "Round robin gives each process a fixed time quantum. Shortest job first minimises average waiting time but needs burst estimates. Priority scheduling can starve low-priority processes unless aging raises their priority over time.",
    ),
    (
        "Memory management",
        "Paging splits memory into fixed-size frames and avoids external fragmentation. A translation lookaside buffer caches recent page-table entries. Thrashing happens when the working sets of running processes exceed physical memory.",
    ),
    (
        "Synchronisation",
        "A semaphore is an integer accessed only through wait and signal. A mutex gives mutual exclusion to one thread at a time. Spinlocks busy-wait and suit short critical sections on multiprocessors.",
    ),
    (
        "File systems",
        "An inode stores a file's metadata and block pointers but not its name. Journaling file systems write intended changes to a log first so they can recover after a crash.",
    ),
    (
        "Normalisation",
        "First normal form requires atomic values. Second normal form removes partial dependencies on a composite key. Third normal form removes transitive dependencies between non-key attributes.",
    ),
    (
        "Transactions",
        "ACID stands for atomicity, consistency, isolation and durability. Strict two-phase locking holds exclusive locks until commit and prevents cascading rollbacks.",
    ),
]

FACTS = {
    417: (
        "Deadlock avoidance",
        "The Banker's algorithm avoids deadlock by granting a request only if the system stays in a safe state, meaning some order exists in which every process can finish with the resources available.",
    ),
    902: (
        "B+ tree indexes",
        "In a B+ tree every key lives in the leaf level, and the leaves are linked so range queries scan them in order without returning to the root.",
    ),
    1377: (
        "Virtual memory",
        "Belady's anomaly is when giving FIFO page replacement more frames causes more page faults; LRU and optimal replacement never show it.",
    ),
}


def main(out: str) -> None:
    rng = random.Random(7)  # noqa: S311  # reproducible test data, not security
    image_bytes = TARGET_BYTES // PAGES
    side = int((image_bytes / 3) ** 0.5)  # RGB noise barely compresses
    doc = pymupdf.open()
    for number in range(1, PAGES + 1):
        page = doc.new_page()
        heading, body = FACTS.get(number) or TOPICS[number % len(TOPICS)]
        text = f"Lecture {number // 10 + 1}: {heading}\n\n{body}\n\n{body}"
        page.insert_textbox(pymupdf.Rect(50, 50, 545, 330), text, fontsize=11)
        noise = rng.randbytes(side * side * 3)
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, side, side, noise, False)
        page.insert_image(pymupdf.Rect(50, 350, 545, 790), pixmap=pixmap)
        if number % 250 == 0:
            print(f"{number} pages", flush=True)
    doc.save(out, deflate=True)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1])
