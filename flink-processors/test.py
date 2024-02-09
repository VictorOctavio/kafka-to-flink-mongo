import logging
import sys
import os
import json

from pyflink.common import Types, Configuration
from pyflink.datastream import StreamExecutionEnvironment, ProcessFunction
from pyflink.datastream.connectors.kafka import FlinkKafkaConsumer #, FlinkKafkaProducer
# from pyflink.datastream.formats.json import JsonRowSerializationSchema, JsonRowDeserializationSchema
from pyflink.common.serialization import SimpleStringSchema

# Handler state
from pyflink.datastream.state import ValueStateDescriptor
from pyflink.datastream.functions import MapFunction, KeyedProcessFunction, RuntimeContext

# mongodb

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
        
        if self.state.value() is None:
            print("state NONE")
            self.state.update(json.dumps({}))
    
    def process_element(self, value, ctx: 'KeyedProcessFunction.Context'):
        user_key = ctx.get_current_key()
        process_event(value, self.state, user_key)
        print(json.loads(self.state.value()))
        
def process_event(event_data, state, user_key):
    source_table = event_data['payload']['source']['table']
        
    if source_table == 'users' and event_data['payload']['op'] == 'c': # 'c' indicates an insertion operation
        user_data = event_data['payload']['after']
        current_state_value = json.loads(state.value())
        current_state_value[user_data['id']] = {
            'name': user_data['name'],
            'lastname': user_data['lastname'],
            'createdat': user_data['createdat']
        }
        
        state.update(json.dumps(current_state_value))

    # elif source_table == 'infouser' and event_data['payload']['op'] == 'c': # 'c' indicates an insertion operation
    #     user_infodata = event_data['payload']['after']
    #     user_id = user_infodata['user_id']
    #     current_state_value = json.loads(state.value())
    #     if user_id in current_state_value:
    #         print(user_id, current_state_value)
    #         current_state_value[user_id].update({
    #             'phone': user_infodata['phone'],
    #             'address': user_infodata['address'],
    #             'country': user_infodata['country'],
    #             'city': user_infodata['city']
    #         })
    #     else:
    #         print("Usuario no incluido...")
    #         print(user_id, current_state_value)
    #         # current_state_value[user_id] = {
    #         #     'phone': user_infodata['phone'],
    #         #     'address': user_infodata['address'],
    #         #     'country': user_infodata['country'],
    #         #     'city': user_infodata['city']
    #         # }
            
    #     state.update(json.dumps(current_state_value))
    
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

    config = Configuration()
    config.set_string('state.backend.type', 'hashmap')
    env = StreamExecutionEnvironment.get_execution_environment(config)
    env.add_jars("file:///home/byoct1/projects/flink/flink-sql-connector-kafka-3.0.2-1.18.jar")
    print("start reading data from kafka")
    read_from_kafka(env)
