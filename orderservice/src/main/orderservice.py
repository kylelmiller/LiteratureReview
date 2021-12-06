import json
import os
import random
import requests
import sys
import time
from multiprocessing import Process
import logging

import pandas as pd
import redis
from confluent_kafka import DeserializingConsumer, KafkaException, KafkaError
from sklearn.decomposition.pca import PCA
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model.logistic import LogisticRegression

TWENTY_MINUTES_IN_SECONDS = 20 * 60
logger = logging.getLogger()
logger.addHandler(logging.StreamHandler())
conf = {
    "bootstrap.servers": os.environ.get("KAFKA_BROKERS"),
    "group.id": "literature-review2",
    "auto.offset.reset": "earliest",
    "key.deserializer": lambda key, ctx: key.decode("utf-8"),
    "value.deserializer": lambda value, ctx: json.loads(value.decode("utf-8")),
}

API_HOSTNAME = os.environ.get("API_HOSTNAME", "literature-review")
API_PORT = os.environ.get("API_PORT", 8000)
API_USERNAME = os.environ.get("API_USERNAME", "admin")
API_PASSWORD = os.environ.get("API_PASSWORD", "admin")

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)

REORDER_INTERVAL = os.environ.get("REORDER_INTERVAL", 20)

consumer = DeserializingConsumer(conf)
# consumer = Consumer({
#     'bootstrap.servers': os.environ.get("KAFKA_BROKERS"),
#     'group.id': "literature-review3",
#     'auto.offset.reset': 'beginning'
# })
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
running = True


def msg_process(msg):
    key = msg.key()
    value = msg.value()
    if (value["positive_labels"] + value["negative_labels"]) % REORDER_INTERVAL:
        return

    print("ordering documents")
    unique_string = str(os.getpid()) + str(int(time.time())) + str(random.randint(0, 1_000_000))
    redis_name = f"project_order_lock:{key}"
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

        df = pd.DataFrame(response.json())

        # create the features
        df["text"] = df["title"] + " " + df["description"].fillna("")
        text_tfidf = TfidfVectorizer(stop_words="english", max_df=0.8, min_df=0.005).fit_transform(df["text"])
        text_features = PCA(n_components=40).fit_transform(text_tfidf.toarray())
        # text_features = text_tfidf
        labeled_document_count = len(df[df["label"].notnull()])

        # train the model
        clf = LogisticRegression(solver="lbfgs").fit(
            text_features[:labeled_document_count], df[df["label"].notnull()]["label"]
        )

        # order the documents
        df["predicted"] = clf.predict_proba(text_features)[:, 1]
        order_value = 0
        document_order = []
        for index, row in df.sort_values("predicted", ascending=False).iterrows():
            document_order.append({"id": row["id"], "order": order_value})
            order_value += 1

        # update the order
        requests.post(
            f"http://{API_HOSTNAME}:{API_PORT}/api/projects/{key}/documentsorder",
            data=json.dumps(document_order),
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
