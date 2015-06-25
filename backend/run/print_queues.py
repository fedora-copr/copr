#!/usr/bin/python
# coding: utf-8

NUM_QUEUES = 2

import sys
sys.path.append("/usr/share/copr/")

from retask.task import Task
from retask.queue import Queue

for i in range(0, NUM_QUEUES):
    print("## Queue {}".format(i))
    q = Queue("copr-be-{}".format(i))
    q.connect()
    save_q = []
    while q.length != 0:
    	task = q.dequeue()
        print task.data
        save_q.append(task)
    for t in save_q:
        q.enqueue(t)

