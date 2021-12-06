import json
import pika
from decouple import config


class AMQPConnection(object):
    def __init__(self):
        amqp_user = config('AMQP_USER')
        amqp_pass = config('AMQP_PASS')
        amqp_host = config('AMQP_HOST')
        amqp_port = config('AMQP_PORT')
        self.amqp_url = f'amqps://{amqp_user}:{amqp_pass}@{amqp_host}:{amqp_port}?connection_attempts=2&retry_delay=1'

    def basic_publish(self, routing_key, data):
        connection = pika.BlockingConnection(pika.URLParameters(self.amqp_url))
        channel = connection.channel()

        exchange_name = 'campusmq'
        channel.exchange_declare(exchange=exchange_name, exchange_type='topic')
        channel.basic_publish(exchange=exchange_name, routing_key=routing_key, body=json.dumps(data))
        print('Published data to MQ, closing connection')
        connection.close()
        print('Done')
