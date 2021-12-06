import json
import os
import random
import requests
import sys
import time
from multiprocessing import Process

import numpy as np
import redis
from confluent_kafka import DeserializingConsumer, KafkaException, KafkaError
from scipy.optimize import curve_fit

TWENTY_MINUTES_IN_SECONDS = 20 * 60
MEAN_WINDOW = 10
MIN_TAIL_VALUE = 0.005
MIN_LABELED_LIMIT = 200
MIN_LABELED_PERCENTAGE_THRESHOLD = 0.3

conf = {
    "bootstrap.servers": os.environ.get("KAFKA_BROKERS"),
    "group.id": "literature-review",
    "auto.offset.reset": "smallest",
    "key.deserializer": lambda key, ctx: key.decode("utf-8"),
    "value.deserializer": lambda value, ctx: json.loads(value.decode("utf-8")),
}

API_HOSTNAME = os.environ.get("API_HOSTNAME", "literature-review")
API_PORT = os.environ.get("API_PORT", 8000)
API_USERNAME = os.environ.get("API_USERNAME", "admin")
API_PASSWORD = os.environ.get("API_PASSWORD", "admin")

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)

ESTIMATE_INTERVAL = os.environ.get("ESTIMATE_INTERVAL", 10)
consumer = DeserializingConsumer(conf)
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
running = True


def msg_process(msg):
    key = msg.key()
    value = msg.value()
    total_labeled_documents = value["positive_labels"] + value["negative_labels"]
    if (
        total_labeled_documents < MIN_LABELED_LIMIT
        or total_labeled_documents < value["total_documents"] * MIN_LABELED_PERCENTAGE_THRESHOLD
        or (total_labeled_documents) % ESTIMATE_INTERVAL
    ):
        return

    unique_string = str(os.getpid()) + str(int(time.time())) + str(random.randint(0, 1_000_000))
    redis_name = f"project_estimator_lock:{key}"
    if not redis_client.set(redis_name, unique_string, nx=True, ex=TWENTY_MINUTES_IN_SECONDS):
        # We didn't get the lock
        return
    try:
        # get the list of documents
        response = requests.get(
            f"http://{API_HOSTNAME}:{API_PORT}/api/projects/{key}/documents", auth=(API_USERNAME, API_PASSWORD)
        )
        if not response.ok:
            raise Exception(response.content)

        def objective(x, a, b, c):
            return a * x + b * x ** 2 + c

        labels = [document["label"] for document in response.json() if document["label"] is not None]

        mean_values = [np.mean(labels[i : i + MEAN_WINDOW]) for i in range(len(labels) - MEAN_WINDOW)]
        max_index = mean_values.index(max(mean_values))
        mean_values = mean_values[max_index:]
        coefficients, _ = curve_fit(objective, np.array(range(len(mean_values))), mean_values)
        fit_values = objective(np.array(range(len(labels) - max_index)), *coefficients)

        predicted_prob = [max(min(v, min(mean_values[-10:])), MIN_TAIL_VALUE) for v in fit_values[len(mean_values) :]]
        predicted_prob[-1] = predicted_prob[-1] * MEAN_WINDOW
        # update the order
        requests.post(
            f"http://{API_HOSTNAME}:{API_PORT}/api/projects/{key}",
            data=json.dumps({"estimated_positive": sum(predicted_prob)}),
            headers={"Content-Type": "application/json; charset=utf-8"},
            auth=(API_USERNAME, API_PASSWORD),
        )
    finally:
        # We are done, remove the lock
        redis_client.delete(redis_name)


def basic_consume_loop(consumer, topics):
    try:
        consumer.subscribe(topics)

        while running:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    # End of partition event
                    sys.stderr.write(
                        "%% %s [%d] reached end at offset %d\n" % (msg.topic(), msg.partition(), msg.offset())
                    )
                elif msg.error():
                    raise KafkaException(msg.error())
            else:
                # spin off a new process to handle the message
                Process(target=msg_process, args=(msg,)).start()
    finally:
        # Close down consumer to commit final offsets.
        consumer.close()


def shutdown():
    running = False


basic_consume_loop(consumer, ["project"])
