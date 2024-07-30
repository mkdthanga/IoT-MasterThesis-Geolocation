# -*- coding: utf-8 -*-
"""
Created on Sun Jun  7 21:13:12 2020

@author: mkdth

This script should run on the docker server for every minute/always in order to log the incoming geoloc packets
into the PostgreSQL DB

Points to Remember:
1. Check & Change the PostgreSQL params (host: 'db' & password: 'PW556655' )
2. Check the Broker params (host: 10.2.0.7:1884)
3. SQLAlchemy url Syntax: dialect+driver://username:password@host:port/database
"""
#!/usr/bin/python
import psycopg2
from psycopg2 import connect, Error, extensions, sql
import paho.mqtt.client as mqtt
import datetime
import time
import json
import pandas as pd
from sqlalchemy import create_engine

#postgres params
DB_NAME= 'Geolocation_DB'
postgres_host= 'db'
postgres_port= '5432'
postgres_password= 'PW556655'
#mqtt params
geoloc_host = '10.2.0.7'
mqtt_port = 1884
qos = 0
retain = False
# initialize sqlalchemy engine to write pandas DF into postgres
# continuosly even if error occured for one or few frames
engine_nf = create_engine('postgresql+psycopg2://postgres:' + postgres_password + '@'+ postgres_host +':'+postgres_port+'/'+ DB_NAME)
sql_execute = lambda sql: pd.io.sql.execute(sql, engine_nf)

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe([("gateway/geoloc/+",0), ("geolocation/#",0)])

def on_message(client, userdata, msg):
    print("Received a message on topic: " + msg.topic)
    Date = datetime.datetime.utcnow()
    payload = str(msg.payload.decode("utf-8", "ignore"))
    topicstring = str(msg.topic)
    dev_address = topicstring[-8:]
    topic_error = 'subscriber/error/'+str(dev_address)
    topic_stored = 'subscriber/stored/'+str(dev_address)
    topickindstatus = topicstring[:3]
    payload_type = topicstring[12:17]
    #print('payload_type:', payload_type)
    #print('rms?:', topicstring[18:21])
    #print('topicstring[0:23]:', topicstring[0:23])
    #print('topicstring[0:25]:', topicstring[0:25])
    #insert into geoloc_packets table
    if topickindstatus == "gat":
        try:
            # print the JSON payload with Data and Topic
            print(str(Date) + ": " + msg.topic + " " + str(payload))
            # convert JSON into json_payloads
            json_payload = json.loads(payload)[0]
            insert = '''
            INSERT INTO geoloc_packets(time, device_address, frame_cnt, frequency_hz, bandwidth_hz, sf, antenna, toa_sec, toa_nsec, rssi_dbm, snr_db, fo_hz, toa_u_nsec, fo_u_hz, gateway_latitude, gateway_longitude, gateway_altitude, gateway_id, mic)
            VALUES ('%s','%s','%s','%s','%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s','%s','%s','%s','%s', '%s', '%s')
            ''' % (Date, json_payload['mote'],json_payload['frame_cnt'],json_payload['freq_hz'],json_payload['bandwidth'],json_payload['sf'],json_payload['antenna'], json_payload['toa_sec'], json_payload['toa_nsec'],json_payload['rssi_dbm'],json_payload['snr_db'],
                    json_payload['fo_hz'],json_payload['toa_u_nsec'],json_payload['fo_u_hz'], json_payload['lat'], json_payload['lon'], json_payload['alt'], json_payload['gateway_id'], json_payload['mic'] )
            sql_execute(insert)
            stored_str = "Finished writing to PostgreSQL table geoloc_packets"
            #client.publish(topic_stored, stored_str, qos, retain)
            print(stored_str)
        except (Exception, Error) as err:
            print("\npsycopg2 connect error:", err)
            error_str = "Could not insert " + payload + " into table geoloc_results, therefore inserted into miscellaneous"
            # print the JSON payload with Data and Topic
            print(str(Date) + ": " + msg.topic + " " + str(payload))
            topic = msg.topic
            # convert JSON into json_payloads
            json_payload = json.loads(payload)
            dev_address = json_payload['device_address']
            insert = '''
                    INSERT INTO miscellaneous(time, topic, device_address, payloads)
                                VALUES ('%s','%s','%s','%s')
                    ''' % (Date, topic, dev_address, payload)
            sql_execute(insert)
            client.publish(topic_error, error_str, qos, retain)
            print(error_str)
    #insert into miscellaneous table
    elif topicstring[0:23] == "geolocation/device_list":
        try:
            #print('topicstring[0:23]:', topicstring[0:23])
            # print the JSON payload with Data and Topic
            print(str(Date) + ": " + msg.topic + " " + str(payload))
            topic = msg.topic
            # convert JSON into json_payloads
            json_payload = json.loads(payload)
            #dev_address = json_payload['device_address']
            insert = '''
                INSERT INTO miscellaneous(time, topic, payloads)
                            VALUES ('%s','%s','%s')
                ''' % (Date, topic, payload)
            sql_execute(insert)
            stored_str = "Finished writing to PostgreSQL table miscellaneous"
            #client.publish(topic_stored, stored_str, qos, retain)
            print(stored_str)
        except (Exception, Error) as err:
            print("\npsycopg2 connect error:", err)
            error_str = "Could not insert " + payload + " into table miscellaneous"
            client.publish(topic_error, error_str, qos, retain)
            print(error_str)
    #insert into geoloc_results table
    elif topickindstatus == "geo":
        try:
            # print the JSON payload with Data and Topic
            print(str(Date) + ": " + msg.topic + " " + str(payload))
            topic = msg.topic
            # convert JSON into json_payloads
            json_payload = json.loads(payload)
            dev_address = json_payload['device_address']
            dev_name = json_payload['device_name']
            HDOP = json_payload['HDOP']
            if "http" in topic:
                mean_snr = 0
                mean_rssi_var = 0
                mean_toa_u = 0
            elif "estimation" in topic:
                mean_snr = json_payload['mean_snr']
                mean_rssi_var = json_payload['mean_rssi_var']
                mean_toa_u = json_payload['mean_toa_u']
                latitude_tdoa = 'NAN'
                longitude_tdoa= 'NAN'
                latitude_rssi= 'NAN'
                longitude_rssi= 'NAN'
                latitude_fused= 'NAN'
                longitude_fused= 'NAN'
                latitude_kf= json_payload['latitude_kf']
                longitude_kf= json_payload['longitude_kf']
                latitude_kfs= "NAN"
                longitude_kfs= "NAN"
                latitude_true= 'NAN'
                longitude_true= 'NAN'
                error_tdoa = 'NAN'
                error_rssi = 'NAN'
                error_fused = 'NAN'
                error_kf = json_payload['error_kf']
                error_kfs = "NAN"
            else:
                mean_snr = json_payload['mean_snr']
                mean_rssi_var = json_payload['mean_rssi_var']
                mean_toa_u = json_payload['mean_toa_u']
                latitude_tdoa = json_payload['latitude_tdoa']
                longitude_tdoa= json_payload['longitude_tdoa']
                latitude_rssi= json_payload['latitude_rssi']
                longitude_rssi= json_payload['longitude_rssi']
                latitude_fused= json_payload['latitude_fused']
                longitude_fused= json_payload['longitude_fused']
                latitude_kf= json_payload['latitude_kf']
                longitude_kf= json_payload['longitude_kf']
                latitude_kfs= json_payload['latitude_kfs']
                longitude_kfs= json_payload['longitude_kfs']
                latitude_true= json_payload['latitude_true']
                longitude_true= json_payload['longitude_true']
                error_tdoa = json_payload['error_tdoa']
                error_rssi = json_payload['error_rssi']
                error_fused = json_payload['error_fused']
                error_kf = json_payload['error_kf']
                error_kfs = json_payload['error_kfs']
            insert = '''
                INSERT INTO geoloc_results(time, topic, device_address, device_name, num_Of_Gateways_Used, num_Of_UL_Packets_Used, HDOP, mean_snr_db, mean_rssi_var_dbm, mean_toa_var_nsec, latitude_tdoa, longitude_tdoa, 
                latitude_rssi, longitude_rssi, latitude_fused, longitude_fused, latitude_kf, longitude_kf,latitude_kfs, longitude_kfs, latitude_true, longitude_true, error_tdoa, error_rssi, error_fused, error_kf, error_kfs, payloads)
                VALUES ('%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s', '%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s', '%s', '%s', '%s')
                ''' % (Date, topic, dev_address, dev_name, json_payload['numOfGatewaysUsed'], json_payload['numOfULPacketsUsed'], HDOP, mean_snr, mean_rssi_var, mean_toa_u, latitude_tdoa, longitude_tdoa,
                       latitude_rssi, longitude_rssi, latitude_fused, longitude_fused, latitude_kf, longitude_kf, latitude_kfs, longitude_kfs, latitude_true, longitude_true, error_tdoa, error_rssi, error_fused, error_kf, error_kfs,  payload)
            sql_execute(insert)
            stored_str = "Finished writing to PostgreSQL table geoloc_results"
            #client.publish(topic_stored, stored_str, qos, retain)
            print(stored_str)
        except (Exception, Error) as err:
            print("\npsycopg2 connect error:", err)
            error_str = "Could not insert " + payload + " into table geoloc_results, therefore inserted into miscellaneous"
            # print the JSON payload with Data and Topic
            print(str(Date) + ": " + msg.topic + " " + str(payload))
            topic = msg.topic
            # convert JSON into json_payloads
            json_payload = json.loads(payload)
            dev_address = json_payload['device_address']
            insert = '''
                    INSERT INTO miscellaneous(time, topic, device_address, payloads)
                                VALUES ('%s','%s','%s','%s')
                    ''' % (Date, topic, dev_address, payload)
            sql_execute(insert)
            client.publish(topic_error, error_str, qos, retain)
            print(error_str)

# Initialize the MQTT client that should connect to the Mosquitto server
client = mqtt.Client()

#set last will message
client.will_set('subscriber_db/lastwill','Last will message', 1, True)

client.on_connect = on_connect
client.on_message = on_message

connOK=False
while(connOK == False):
    try:
        client.connect(geoloc_host, mqtt_port, 60)
        connOK = True
    except:
        connOK = False
    time.sleep(2)

# Blocking loop to the Mosquitto server
client.loop_forever()


