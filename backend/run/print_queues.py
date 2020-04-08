#!/usr/bin/python3
# coding: utf-8

NUM_QUEUES = 2

import sys

from retask.task import Task
from retask.queue import Queue
from copr_backend.helpers import BackendConfigReader

opts = BackendConfigReader().read()
redis_config = {
    'host': opts['redis_host'],
    'port': opts['redis_port'],
    'db': opts['redis_db'],
}

for i in range(0, NUM_QUEUES):
    print("## Queue {}".format(i))
    q = Queue("copr-be-{}".format(i), config=redis_config)
    q.connect()
    save_q = []
    while q.length != 0:
        task = q.dequeue()
        print(task.data)
        save_q.append(task)
    for t in save_q:
        q.enqueue(t)

