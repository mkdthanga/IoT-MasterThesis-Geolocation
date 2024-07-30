# -*- coding: utf-8 -*-
"""
This script is used to calculate the A & n value given the RSSI & GWs position for an Uplink instance.
This is integrated into resolver script in order to calculate rssi for each device on each Uplink instance/ gelocation calculation!!

#Remember: In Pyproj Module
UTMx, UTMy = myProj(lon, lat)
lon, lat = myProj(UTMx, UTMy, inverse=True)
"""

import numpy as np
from pyproj import Proj
import pandas as pd
import psycopg2
import statistics
import json
import paho.mqtt.client as mqtt
import os
# required folder paths
rssi_A_n_dataset_path = 'RSSI_Experiment/'                           # destination folder to store the rssi_a_n datasets
# check if the dataset directories exists, if not create them
cwd = os.getcwd()
if not os.path.exists(rssi_A_n_dataset_path):
    os.mkdir(rssi_A_n_dataset_path)
# control flags
bSelected_devices = True
# utm co-ordinates
myProj = Proj("+proj=utm +zone=33 +north +ellps=WGS84")
# Postgres DB parameters
postgres_host= 'localhost'
postgres_port= '5432'
postgres_password= 'Admin1234'
DB_NAME= 'Geolocation_DB'
# MQTT parameters to publish the results
geoloc_host = '10.2.0.7'
mqtt_port= 1884
qos = 0
retain = False

# declare globals
global A, n

# mqtt connect function to establish a connection with mqtt broker!
def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
client = mqtt.Client()
client.on_connect = on_connect
client.connect(geoloc_host,mqtt_port, 60)
client.loop_start()
# read the true location.CSV file
df_trueloc = pd.read_csv('datasets/TrueLocations.csv', sep=';', encoding='latin-1')

# true_position in case of TOA calculation or error calculation
def true_position(df,dev_addr):
    if dev_addr in df['Device Address'].values:
        print('enters real true location')
        df = df[df['Device Address'] == dev_addr]
        dev_name = df['Device Name']
        dev_EUI = df['Device EUI']
        dev_address = df['Device Address']
        lat = df['Latitude']
        lon = df['Longitude']
        description = df['Description']
        # actual position
        tx_gps = np.array([lat.values[0],lon.values[0], 475])
        tx_utm = myProj(tx_gps[1], tx_gps[0])
        return tx_utm, tx_gps, dev_name
    else:
        print('enters dummy true location')
        # actual position
        dev_name = 'LoRa_device'
        tx_gps = np.array([47,12, 475])
        tx_utm = myProj(tx_gps[1], tx_gps[0])
        return tx_utm, tx_gps, dev_name

def query_geoloc_packets(address_entered):
    global device_addr
    sql_query = ''' SELECT * FROM public.geoloc_packets
                    WHERE device_address= %s                                                                                                                                                        
                '''
    device_addr = address_entered
    conn = psycopg2.connect(user='postgres',
                              host= postgres_host,
                              port= postgres_port,
                              password=postgres_password,
                              database=DB_NAME)
    cur = conn.cursor()
    cur.execute(sql_query, (device_addr,))
    SQL_Query = cur.fetchall()
    df = pd.DataFrame(SQL_Query,columns=['id', 'time', 'mote', 'frame_cnt', 'freq_hz', 'bandwidth', 'sf', 'antenna', 'toa_sec',
                                 'toa_nsec', 'rssi_dbm','snr_db', 'fo_hz', 'toa_u_nsec', 'fo_u_hz', 'gateway_latitude',
                                 'gateway_longitude','gateway_altitude', 'gateway_id', 'mic'])
    #print('latitude:',df['latitude'])
    #print('longitude:',df['longitude'])
    return df
# calculate A & n dynamically (online)
def calculate_n(GWs, rssi, tx_utm, df, dev_addr, A):
    # Variable initiation
    num_rows= len(rssi)
    print('No. of geoloc frames used:',num_rows)
    distances = np.array([((x[0]-tx_utm[0])**2+(x[1]-tx_utm[1])**2)**0.5for x in GWs])
    # A = abs(rssi/distances)
    # A = -33
    print('A:', A)
    n = (A-rssi)/(10*np.log10(distances))
    df.loc[:, 'A'] = A
    df.loc[:, 'n'] = n
    mean_A = A
    #mean_A = statistics.mean(A)
    mean_n = statistics.mean(n)
    # export df as csv data and store it in the above mentioned destination
    df.to_csv(str(rssi_A_n_dataset_path)+'RSSI_Experiment_'+str(dev_addr))
    print('A & n calculated & Exported as RSSI_Experiment/RSSI Experiment/'+str(dev_addr))
    return mean_A, mean_n
def calculate_a(GWs, rssi, tx_utm, df, dev_addr, n):
    # Variable initiation
    num_rows= len(rssi)
    print('No. of geoloc frames used:',num_rows)
    distances = np.array([((x[0]-tx_utm[0])**2+(x[1]-tx_utm[1])**2)**0.5for x in GWs])
    # A = -26
    # n = 2.4
    # n = (A-rssi)/(10*np.log10(distances))
    print('n:', n)
    A = n*(10*np.log10(distances))+rssi
    df.loc[:, 'A'] = A
    df.loc[:, 'n'] = n
    #mean_A = A
    mean_A = statistics.mean(A)
    #mean_n = statistics.mean(n)
    mean_n = n
    # export df as csv data and store it in the above mentioned destination
    df.to_csv(str(rssi_A_n_dataset_path)+'RSSI_Experiment_'+str(dev_addr))
    print('A & n calculated & Exported as RSSI_Experiment/RSSI Experiment/'+str(dev_addr))
    return mean_A, mean_n
# calculate RSSI given the distance, A & n (online)
def calculate_rssi(GWs, tx_utm, A, n):
    distances = np.array([((x[0]-tx_utm[0])**2+(x[1]-tx_utm[1])**2)**0.5for x in GWs])
    rssi = -(10*np.log10(abs(distances)))*n+abs(A)
    return rssi
#query unique device_addresses from geoloc_packets table
def query_device_addr():
    sql_query = '''select DISTINCT device_address FROM public.geoloc_packets where time BETWEEN NOW() - INTERVAL '24 HOURS' AND NOW()'''
    conn = psycopg2.connect(user='postgres',
                              host= postgres_host,
                              port= postgres_port,
                              password=postgres_password,
                              database=DB_NAME)
    cur = conn.cursor()
    cur.execute(sql_query)
    records = cur.fetchall()
    # convert sql return values into list format!!
    query_return = [x[0] for x in records]
    return query_return

# callbacks/parameters
# list variables for A & n
list_mean_A = []
list_mean_n = []
# topic to publish final mean A & n
topic_mean_A_n = "geolocation/rssi/mean_A_n/komro"
# device address for which A & n should be calculated
dev_addr = '1ec684c'  #'167f446'

# initiate A value
A = -36
if bSelected_devices:
    # calculate for selected device group only
    device_addr_list = ['1ec684c', '1d31e70', '14e57dc', '890dae', '11345b9', '16060fe', 'f56134', 'f2e68d',
                        '1a200f6', '2cb194', '11a5073', '5ec3d4', '1956641', '170a786', '1dbd8', 'b77e53',
                        '166457a', '167f446', '11757cf', '1eef69a','1a76fed', '1eb48f8']
    device_addr_list = df_trueloc['Device Address'].tolist()
else:
    # extract unique device_addresses from geoloc packets table! (unique address from last 24 hrs)
    device_addr_list = query_device_addr()
for dev_addr in device_addr_list:
    try:
        print('device_address:', dev_addr)
        # get the true location for error calculation
        tx_utm, tx_gps, device_name = true_position(df_trueloc, dev_addr)
        # query all the device records from public.geoloc_results table
        df = query_geoloc_packets(dev_addr)
        # geoloc packets-RSSI only interesting for now
        lat = df['gateway_latitude'].astype(float)
        lon = df['gateway_longitude'].astype(float)
        alt = df['gateway_altitude'].astype(float)
        rssi = df['rssi_dbm'].astype(float)
        # Variable initiation
        num_rows = len(rssi)
        GWs = np.zeros((num_rows, 2))
        # convert lat, lon to x,y
        for i in range(GWs.shape[0]):
            GWs[i][0], GWs[i][1] = myProj(lon[i], lat[i])
            # GWs[i][2]= alt[i]
        # callback function
        A_constant, n = calculate_n(GWs, rssi, tx_utm, df, dev_addr, A)
        A, n_constant = calculate_a(GWs, rssi, tx_utm, df, dev_addr, n)
        print('mean_A:', A)
        print('mean_n:', n)
        # append A & n in a list variable
        list_mean_A.append(A)
        list_mean_n.append(n)
    except:
        # exception handling in case of no data points of a device
        print('FOR LOOP passed due to no data points for the device '+str(device_name))
        pass
# calculate mean A & n from list of A & n
len_list_mean_A = len(list_mean_A)
len_list_mean_n = len(list_mean_n)
mean_A = statistics.mean(list_mean_A)
mean_n = statistics.mean(list_mean_n)
print('########### Mean of list of A & n ###########')
print('length_of_list_of_mean_A:', len_list_mean_A)
print('length_of_list_of_mean_n:', len_list_mean_n)
print('mean_A:', mean_A)
print('mean_n:', mean_n)
# publish mean A & n to geoloc broker
json_mean_A_n = json.dumps({'mean_A_dBm': mean_A, 'mean_n': mean_n, 'num_of_mean_A_used': len_list_mean_A,
                            'num_of_mean_n_used': len_list_mean_n})
client.publish(topic_mean_A_n, json_mean_A_n, qos, retain)
print('Mean A & n values published to geoloc broker successfully')
    


