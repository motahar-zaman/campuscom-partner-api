from mongoengine import get_db
from .amqp_connector import AMQPConnection

def generic_task_enqueue(routing_key, doc_id=None):
    if doc_id:
        payload = {
            'routing_key': routing_key,
            'doc_id': doc_id
        }
        connection = AMQPConnection()

        print('trying to connect to amqp')
        connection.basic_publish(routing_key, payload)
        print('completed')
