import logging
import sys
import os
import json

from pyflink.common import Types
from pyflink.datastream import StreamExecutionEnvironment, ProcessFunction
from pyflink.datastream.connectors.kafka import FlinkKafkaConsumer #, FlinkKafkaProducer
# from pyflink.datastream.formats.json import JsonRowSerializationSchema, JsonRowDeserializationSchema
from pyflink.common.serialization import SimpleStringSchema

# Handler state
from pyflink.datastream.state import ValueStateDescriptor
from pyflink.datastream.functions import MapFunction, KeyedProcessFunction, RuntimeContext

os.environ['JAVA_HOME'] = '/usr'

class EventToJson(MapFunction):
    def map(self, value):
        return json.loads(value) # Convertir el valor de cadena a un objeto JSON

class UserStateProcessFunction(KeyedProcessFunction):
    def __init__(self):
        self.state = None
         
    def open(self, runtime_context: RuntimeContext):
        self.state = runtime_context.get_state(ValueStateDescriptor(
            "user_states",  # the state name
            Types.STRING()  # type information
        ))

    def process_element(self, value, ctx: 'KeyedProcessFunction.Context'):
        process_event(value, self.state, ctx)
        
def process_event(event_data, state, key):
    key = ctx.get_current_key()
    source_table = event_data['payload']['source']['table']
    if source_table == 'users' and event_data['payload']['op'] == 'c': # 'c' indicates an insertion operation
        print("new message user insert: :)")
        # Store the user data in the state
        user_data = event_data['payload']['after']
        state.update(json.dumps({
            'name': user_data['name'],
            'lastname': user_data['lastname'],
            'createdAt': user_data['createdat']
        }))

    if source_table == 'infouser' and event_data['payload']['op'] == 'c': # 'c' indicates an insertion operation
        print("new message user info insert: :)")
        # Update the user data in the state
        user_infodata = event_data['payload']['after']
        user_id = user_infodata['user_id']
        current_user_data = json.loads(state.value())
        if user_id in current_user_data:
            current_user_data[user_id] = {
                **current_user_data[user_id],
                'phone': user_infodata['phone'],
                'address': user_infodata['address'],
                'country': user_infodata['country'],
                'city': user_infodata['city']
            }
            state.update(json.dumps(current_user_data))

    # Check if it's an account creation event
    elif source_table == 'accounts' and event_data['payload']['op'] == 'c':
        print("new message account insert: :)")
        # Retrieve the user data from the state
        account_data = event_data['payload']['after']
        user_id = account_data['user_id']
        current_user_data = json.loads(state.value())
        if user_id in current_user_data:
            # Combine user data with account data
            combined_data = {
                **current_user_data[user_id],
                'amount': account_data['amount']
            }
            print("Combined data: ", combined_data)
            # Clear the state for this user since we have processed their account
            state.clear()

def read_from_kafka(env):
    kafka_consumer = FlinkKafkaConsumer(
        topics=['dbserver1.bank.users', 'dbserver1.bank.accounts', 'dbserver1.bank.infouser'],
        deserialization_schema=SimpleStringSchema(),
        properties={'bootstrap.servers': 'localhost:9092', 'group.id': 'thisgroup'}
    )
    # kafka_consumer.set_start_from_earliest()
    json_stream = env.add_source(kafka_consumer).map(EventToJson())
    
    json_stream.key_by(lambda event: event['payload']['after']['id']).process(UserStateProcessFunction())
    env.execute()

if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")

    env = StreamExecutionEnvironment.get_execution_environment()
    env.add_jars("file:///home/byoct1/projects/flink/flink-sql-connector-kafka-3.0.2-1.18.jar")
    print("start reading data from kafka")
    read_from_kafka(env)
