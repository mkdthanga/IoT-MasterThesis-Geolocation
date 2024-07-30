# -*- coding: utf-8 -*-
"""
Created on Thu Jun  25 09:13:39 2020

@author: mkdth

# User inputs are:
postgres_host      -    hostname/IP of the postgres database server (zB. localhost/db)
postgres_password  -    password of the postgres database server (zB. postgres/PW556655)
DB_NAME            -    Database name at which the tables geoloc_packets, geoloc_results were created (zB. Geolocation_DB)
dev_addr           -    optional, device address assigned by network server (zB. [0167f446, 0167f447...])
                        otherwise should check & change everytime ín the resolver.py!
A                  - 	Absolute RSSI value for 1 meter (in dBm)
n                  -    RSSI Pathloss exponent or environment coefficient (no unit)
num_of_frames      -    number of latest UL frames to be queried from the table for a specific device
bCalculatedTOA     -    Just for simulation (hyperbola) Given the True location of a device,
                        calculate TOA instead of using the real-time geoloc frames(boolean zB. 0 or 1)
filter_mode        -    Essential parameter, it is used to choose one of the following data filter modes
split_date         -    If you choose filter mode 3, then one should pass this parameter for
                        splitting the dataframe from that particular date till the latest frame
# Control flags (part of user inputs):
bmultiframe       -    If you need to filter last three UL frame groups, then set it to '1', otherwise set to '0'

# Data Filter modes (of geoloc data frames)
# This program estimates the position in different filter four modes such as:
0- filter based on number of frames                 -> Num of UL Frames  should be specified
1- filter based on time delta (time interval)       -> no required parameters/args
2- filter based on framecount                       -> Should specify Random number as an Index for unique UL frame count group (i.e. Unique FCntUp)
3- filter based on constant date/time string
   (filter geoloc data after certain date/time)     -> Should specify a date/time  from which we need to construct a dataframe and estimate geolocation


Note:
Since it is a 'headless script' without GUI, there is no plotting here and it should run in the server
every one hour. (using sleep(3600))

In order to change the geoloc query parameter, go to the bottom of the script and change the params shown below:

if __name__ == '__main__':
    while True:
        # extract unique device_addresses from geoloc_packets table!
        device_addr_list = query_device_addr()
        for dev_addr in device_addr_list:
            print(dev_addr)
            try:
                A = 2
                n = -116
                filter_mode = 2
                bmultiframe = 1
                num_of_frames = 10
                bCalculatedTOA = 0
                # for filter mode 3, specify the date from which we need to estimate (not mandatory passed a arbitrary argument)
                split_date = datetime(2020, 5, 7)
                result = total_resolve(dev_addr, filter_mode, num_of_frames, bCalculatedTOA,
                                       A, n, split_date, bmultiframe)
                json_tdoa = json.dumps({'device_address': dev_addr, 'latitude':result[0][1], 'longitude':result[0][0]})
                client.publish("geolocation/tdoaposition_gps/" + str(dev_addr), json_tdoa, qos, retain)
                json_rssi = json.dumps({'device_address': dev_addr, 'latitude':result[1][1], 'longitude':result[1][0]})
                client.publish("geolocation/rssiposition_gps/" + str(dev_addr), json_rssi, qos, retain)
                json_fused = json.dumps({'device_address': dev_addr, 'latitude':result[2][1], 'longitude':result[2][0]})
                client.publish("geolocation/fusedposition_gps/" + str(dev_addr), json_fused, qos, retain)
                json_tdoa_error = json.dumps({'device_address': dev_addr, 'latitude_error':result[3][1], 'longitude_error':result[3][0]})
                client.publish("geolocation/error/tdoa/" + str(dev_addr), json_tdoa_error, qos, retain)
                json_rssi_error = json.dumps({'device_address': dev_addr, 'latitude_error':result[4][1], 'longitude_error':result[4][0]})
                client.publish("geolocation/error/rssi/" + str(dev_addr), json_rssi_error, qos, retain)
                json_fused_error = json.dumps({'device_address': dev_addr, 'latitude_error':result[5][1], 'longitude_error':result[5][0]})
                client.publish("geolocation/error/fused/" + str(dev_addr), json_fused_error, qos, retain)
                print('Resolved Positions Published')

# Points to Remember:
1. If we want to calculate the error, one should specify the true geolocation in the true_position() function,
    otherwise the calculated error is bogus (because in this case it uses dummy variable as true locations)
2. Change & Check the PostgreSQL params
3. Check the Broker params
4. Make sure the necessary the tables 'public.geoloc_packets' & 'public.geoloc_results'are created in
   PostgreSQL DB using the script 'subscriber_db.py'
5. If the specified device data is not sufficient in DB table, we will get the value errors exception however it
    does not stop the program execution, the error messages will be published to broker and stored in postgres DB:
    zB.
    Exception: ValueError
    Exception message: attempt to get argmin of an empty sequence
    #Also, runtime warning from RSSI localization section
    RuntimeWarning: divide by zero encountered in double_scalars
      W = [((l - 1) * S) / (S - w) for w in distances_to_station]

"""
import os
import numpy as np
import paho.mqtt.client as mqtt
import pandas as pd
import statistics
import json
import psycopg2
from scipy.optimize import least_squares
from scipy.optimize import minimize
from pyproj import Proj
from numpy import linalg
from datetime import datetime, timedelta
from time import sleep
from pykalman import KalmanFilter
import matplotlib.pyplot as plt
import math
#Postgres DB parameters
postgres_host= 'db'
postgres_password= 'PW556655'
DB_NAME= 'Geolocation_DB'
postgres_port= '5432'
# MQTT parameters to publish the results
geoloc_host = '10.2.0.7'
mqtt_port= 1884
qos = 0
retain = False
# UTM coordinates
myProj = Proj("+proj=utm +zone=33 +north +ellps=WGS84")
# Control Flags to use calculated TOA instead of real-time TOA data (to plot hyperbola under ideal scenario)
bCalculatedTOA = True       # calculate TOA given the ground truth locations of sp. devices
bCalculatedRSSI = True      # calculate RSSI given the ground truth locations of sp. devices
bPrint_debug = False         # enable print statements for debugging
bSelected_devices = True     # if only selected devices should be resolved
bDynamic_A_n = False          # to calculate A & n value for each device at every resolving instances (A&n)
bQuery_frame_cnt = False      # query geoloc packets based on frame counts
bCallPrevKFResults = False   # query previous KF results and append as KF measurements
bAssemble_tdoa_result = False    #assembly only tdoa results and append as KF measurements
# declare globals
global v, delta_d, max_d, df_0, tx_0, tx_temp, device_name, tx_utm, tx_gps
global tdoa_results, rssi_results, fusion_results, frame_counts, f, filepath
global loci, all_t_i, t_c, df_trueloc, kf
# Speed of transmission propogation
v = 3e8
#mqtt connect function to establish a connection with mqtt broker!
def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
client = mqtt.Client()
client.on_connect = on_connect
client.connect(geoloc_host,mqtt_port, 60)
client.loop_start()
# required folder paths
error_map_path = 'error_maps/'                              # destination folder to store the error_maps
true_location_file_path = 'datasets/TrueLocations.csv'  # destination of truelocation.csv
kf_map_path = 'kf_maps/'                                    # destination folder to store the kf_maps
# check if the error map directories exists, if not create them
cwd = os.getcwd()
if not os.path.exists(error_map_path):
    os.mkdir(error_map_path)
if not os.path.exists(kf_map_path):
    os.mkdir(kf_map_path)
# read the true location.CSV file
df_trueloc = pd.read_csv(true_location_file_path, sep=';', encoding='latin-1', header= 'infer', engine='python')
# get true position for error calculation
def true_position(df,dev_addr):
    if dev_addr in df['Device Address'].values:
        print('gets real true location')
        df = df[df['Device Address'] == dev_addr].reset_index()
        dev_name = df['Device Name']
        dev_EUI = df['Device EUI']
        dev_address = df['Device Address']
        lat = df['Latitude']
        lon = df['Longitude']
        description = df['Description']
        # actual position
        tx_gps = np.array([lat.values[0],lon.values[0], 475])
        tx_utm = myProj(tx_gps[1], tx_gps[0])
        if bPrint_debug:
            print('df:', df)
            print('tx_gps:', tx_gps)
        return tx_utm, tx_gps, dev_name[0]
    else:
        print('gets dummy true location')
        # actual position
        dev_name = 'LoRa device'
        tx_gps = np.array([47,12, 475])
        tx_utm = myProj(tx_gps[1], tx_gps[0])
        return tx_utm, tx_gps, dev_name[0]

def search_coordinate(df_data: pd.DataFrame, search_set: set) -> list:
    nda_values = df_data.values
    tuple_index = np.where(np.isin(nda_values, [e for e in search_set]))
    return [(row, col, nda_values[row][col]) for row, col in zip(tuple_index[0], tuple_index[1])]

# filter out komro kf geolocation results [KF]
def query_best_results(dev_addr):
    global time_index, tx_gps, device_name, tx_utm, min_error_source, latitude_best, longitude_best, error_best
    # get the true location for error calculation
    #tx_utm, tx_gps, device_name = true_position(df_trueloc, dev_addr)
    # query the last three rows of kalman-filtered estimations
    #%%/estimation/kf/komro/%% #%%tdoa%% #device_address = %s AND mean_error!=0 AND mean_error<100 AND mean_toa_var_nsec<500 AND mean_snr_db >0
    desc_limit = 1
    sql_query = '''SELECT * from public.geoloc_results
                   WHERE (device_address = %s AND topic not like '%%http%%' AND topic not like '%%best%%')
                   ORDER BY time DESC;'''
    conn = psycopg2.connect(user='postgres',
                            host=postgres_host,
                            port=postgres_port,
                            password=postgres_password,
                            database=DB_NAME)
    cur = conn.cursor()
    cur.execute(sql_query, (dev_addr,))
    SQL_Query = cur.fetchall()
    df_0 = pd.DataFrame(SQL_Query, columns=['id', 'time', 'topic', 'device_address', 'device_name', 'num_of_gateways_used', 'num_of_ul_packets_used', 'latitude_tdoa', 'longitude_tdoa',
                'latitude_rssi', 'longitude_rssi', 'latitude_fused', 'longitude_fused', 'latitude_kf', 'longitude_kf', 'latitude_kfs', 'longitude_kfs', 'latitude_true', 'longitude_true',
                'error_tdoa', 'error_rssi', 'error_fused', 'error_kf', 'error_kfs', 'hdop', 'mean_snr_db', 'mean_rssi_var_dbm', 'mean_toa_var_nsec', 'payloads'])
    df_0[['error_tdoa', 'error_rssi', 'error_fused', 'error_kf']] = df_0[['error_tdoa', 'error_rssi', 'error_fused', 'error_kf']].astype(float)
    df_0 = df_0.dropna(how='all')
    df_0 = df_0.loc[(df_0 != 0).all(axis=1)]
    df_error = df_0[['error_tdoa', 'error_rssi', 'error_fused', 'error_kf']].copy()
    print('df_error_all:', df_error)
    # find the least error value in a df
    min_error = df_0[['error_tdoa', 'error_rssi', 'error_fused', 'error_kf']].min().min()
    # find the row, column & value in df, given a certain value
    min_error_index = search_coordinate(df_0, {min_error})
    print('min_error_cindex:', min_error_index[0][1])
    # column name containing least minimum  error
    min_error_source = df_0.columns[min_error_index[0][1]]
    print('min_error_source:', min_error_source)
    # extract the entire row where the least error is located
    df_error_best = df_0.iloc[[min_error_index[0][0]]]
    df_error_best = df_error_best.drop(['payloads'], 1)
    print('df_error_best:', df_error_best)
    # copy the respective lat, long values according to min_error_source
    if min_error_source == 'error_tdoa':
        #print('df_error_best_error:', df_error_best['error_tdoa'].values[0])
        latitude_best = df_error_best['latitude_tdoa'].values[0]
        longitude_best = df_error_best['longitude_tdoa'].values[0]
    elif min_error_source == 'error_rssi':
        #print('df_error_best_error:', df_error_best['error_rssi'].values[0])
        latitude_best = df_error_best['latitude_rssi'].values[0]
        longitude_best = df_error_best['longitude_rssi'].values[0]
    elif min_error_source == 'error_fused':
        #print('df_error_best_error:', df_error_best['error_fused'].values[0])
        latitude_best = df_error_best['latitude_fused'].values[0]
        longitude_best = df_error_best['longitude_fused'].values[0]
    elif min_error_source == 'error_kf':
        #print('df_error_best_error:', df_error_best['error_kf'].values[0])
        latitude_best = df_error_best['latitude_kf'].values[0]
        longitude_best = df_error_best['longitude_kf'].values[0]
    error_best = min_error
    print('latitude_best:', latitude_best)
    print('longitude_best:', longitude_best)
    print('error_best:', error_best)
    return df_error_best

# query geoloc packets based on device adress & UL frame count
def query_frame_cnt(dev_addr, frame_cnt):
    global time_index, tx_gps, device_name, tx_utm
    # query the geoloc packets based on 'frame_cnt'
    sql_query = ''' SELECT * from public.geoloc_packets 
                    WHERE (device_address = %s AND frame_cnt = %s
                    AND CAST(toa_u_nsec AS decimal(18, 2)) BETWEEN -500 AND 500); '''
    conn = psycopg2.connect(user='postgres',
                            host=postgres_host,
                            port=postgres_port,
                            password=postgres_password,
                            database=DB_NAME)
    cur = conn.cursor()
    cur.execute(sql_query, (dev_addr, frame_cnt,))
    SQL_Query = cur.fetchall()
    df_0 = pd.DataFrame(SQL_Query,
                        columns=['id', 'time', 'mote', 'frame_cnt', 'freq_hz', 'bandwidth', 'sf', 'antenna', 'toa_sec',
                                 'toa_nsec', 'rssi_dbm', 'snr_db', 'fo_hz', 'toa_u_nsec', 'fo_u_hz', 'gateway_latitude',
                                 'gateway_longitude', 'gateway_altitude', 'gateway_id', 'mic'])
    toa_column = df_0['toa_sec'].astype(str).str.cat(df_0['toa_nsec'].astype(str), sep='.').copy()
    df_0['toa'] = toa_column.copy()
    # set datetime index
    df_0['time'] = pd.to_datetime(df_0['time'])
    df_0 = df_0.set_index('time').copy()
    # sort geoloc frames based on time
    df_0 = df_0.sort_index().copy()
    # print UL noises
    mean_toa_var_nsec, mean_rssi_var_dbm, mean_snr_db
    return df_0

# query geoloc packets based on device adress & UL frame count
def query_unique_frames(dev_addr, frame_cnt):
    global time_index, tx_gps, device_name, tx_utm
    # query the geoloc packets based on 'frame_cnt'
    sql_query = ''' SELECT * from public.geoloc_packets 
                    WHERE (device_address = %s 
                    AND CAST(toa_u_nsec AS decimal(18, 2)) BETWEEN -500 AND 500); '''
    conn = psycopg2.connect(user='postgres',
                            host=postgres_host,
                            port=postgres_port,
                            password=postgres_password,
                            database=DB_NAME)
    cur = conn.cursor()
    cur.execute(sql_query, (dev_addr, frame_cnt,))
    SQL_Query = cur.fetchall()
    df_0 = pd.DataFrame(SQL_Query,
                        columns=['id', 'time', 'mote', 'frame_cnt', 'freq_hz', 'bandwidth', 'sf', 'antenna', 'toa_sec',
                                 'toa_nsec', 'rssi_dbm', 'snr_db', 'fo_hz', 'toa_u_nsec', 'fo_u_hz', 'gateway_latitude',
                                 'gateway_longitude', 'gateway_altitude', 'gateway_id', 'mic'])
    toa_column = df_0['toa_sec'].astype(str).str.cat(df_0['toa_nsec'].astype(str), sep='.').copy()
    df_0['toa'] = toa_column.copy()
    # set datetime index
    df_0['time'] = pd.to_datetime(df_0['time'])
    df_0 = df_0.set_index('time').copy()
    # sort geoloc frames based on time
    df_0 = df_0.sort_index().copy()
    # print UL noises
    mean_toa_u_nsec, mean_rssi_var_dbm, mean_snr_db= cal_UL_noise_info(df_0)
    return df_0
#query unique device_addresses from geoloc_packets table
def query_device_addr():
    sql_query = '''select DISTINCT device_address FROM public.geoloc_packets where time BETWEEN NOW() - INTERVAL '24 HOURS' AND NOW()'''
    conn = psycopg2.connect(user='postgres',
                              host=postgres_host,
                              port=postgres_port,
                              password=postgres_password,
                              database=DB_NAME)
    cur = conn.cursor()
    cur.execute(sql_query)
    records = cur.fetchall()
    # convert sql return values into list format!!
    query_return = [x[0] for x in records]
    return query_return
if __name__ == '__main__':
    global ground_truth, tdoa, rssi, fused, kf_filter, sem_s, sem_m, tek_est, diff_rssi_rmse, diff_tdoa_rmse
    while True:
        diff_tdoa_rmse = []
        diff_rssi_rmse = []
        topic_device_list = "geolocation/device_list"
        topic_diff_tdoa_rmse = "geolocation/diff_tdoa_rmse"
        # extract unique device_addresses from geoloc_packets table!
        if bSelected_devices:
            # resolve for selected device group only
            device_addr_list = ['1ec684c', '1d31e70', '14e57dc', '890dae', '11345b9', '16060fe', 'f56134', 'f2e68d', '1a200f6', '2cb194',
                                '11a5073', '1a76fed', '1eb48f8', '5ec3d4', '1956641', '180a928', '1dbd8', 'b77e53', '166457a', '167f446', '11757cf', '1eef69a']
            device_addr_list = df_trueloc['Device Address'].tolist()
            #device_addr_list = ['157170f'] #713694,1ae331a,1e0ea9d
        else:
            device_addr_list = query_device_addr()
        for dev_addr in device_addr_list:
            print('device address:', dev_addr)
            # get the true location for error calculation
            tx_utm, tx_gps, device_name = true_position(df_trueloc, dev_addr)
            print('device_name:', device_name)
            #MQTT Topics
            topic_best_result = "geolocation/estimation/best/komro/" + str(dev_addr)
            topic_true = "geolocation/calculation/groundtruth/" + str(dev_addr)
            topic_error_exception = "geolocation/error/exception/komro/" + str(dev_addr)
            try:
                A = -20.34
                n = 2
                filter_mode = 2           # 0 or 2 only for http request!!
                bmultiframe = 0           # if set to 1, multiple ULs will be passed to resolver function!(boolean)
                num_of_frames = 20
                bCalculatedTOA = False
                # for filter mode 3, specify the date from which we need to estimate (not mandatory passed a arbitrary argument)
                split_date = datetime(2021, 5, 4)
                best_result_df= query_best_results(dev_addr)
                if len(best_result_df) == 0:
                    # if the kf dataframe is empty, then pass the loop
                    print('no best results for: '+str(device_name))
                    pass
                else:
                    latitude_best = float(latitude_best)
                    longitude_best = float(longitude_best)
                    num_of_ul_packets_used = round(np.mean(best_result_df.num_of_ul_packets_used.astype(float)))
                    num_of_gateways_used = round(np.mean(best_result_df.num_of_gateways_used.astype(float)))
                    HDOP = np.mean(best_result_df.hdop.astype(float))
                    mean_snr_db = np.array(best_result_df.mean_snr_db.astype(float))[0]
                    mean_rssi_var_dbm = np.array(best_result_df.mean_rssi_var_dbm.astype(float))[0]
                    mean_toa_var_nsec = np.array(best_result_df.mean_toa_var_nsec.astype(float))[0]
                    error_best = float(error_best)
                    if min_error_source=='error_tdoa':
                        best_source= 'tdoa'
                    if min_error_source=='error_rssi':
                        best_source= 'rssi'
                    if min_error_source=='error_fused':
                        best_source= 'fused'
                    if min_error_source=='error_kf':
                        best_source= 'kf'
                    print('best_source:', best_source)
                    if bPrint_debug:
                        #print('best_result_df_columns:', best_result_df.columns)
                        print('device_address:', dev_addr)
                        print('device_name:', device_name)
                        print('num_of_ul_packets_used:', num_of_ul_packets_used)
                        print('num_of_gateways_used:', num_of_gateways_used)
                        print('HDOP', HDOP)
                        print('mean_rssi_var_dbm:', mean_rssi_var_dbm)
                        print('mean_toa_u_nsec:', mean_toa_var_nsec)
                        print('mean_snr_db:', mean_snr_db)
                        #print('mean_error:', mean_error)
                    json_best_result = json.dumps({'device_address': dev_addr, 'device_name': device_name, 'source': best_source, 'numOfGatewaysUsed': num_of_gateways_used,
                                                   'numOfULPacketsUsed': num_of_ul_packets_used, 'HDOP': HDOP, 'latitude_kf': latitude_best, 'longitude_kf': longitude_best,
                                                   'error_kf': error_best, 'mean_snr': mean_snr_db, 'mean_toa_u': mean_toa_var_nsec, 'mean_rssi_var': mean_rssi_var_dbm})
                    print('json_best_result:', json_best_result)
                    client.publish(topic_best_result, json_best_result, qos, retain)
                    print('Best results queried and published successfully')
            except IndexError as index_error:
                print("Exception: {}".format(type(index_error).__name__))
                #print('num. of gateways reached per uplink by ' + str(dev_addr) + ':', total_unique_gw_id)
            except Exception as exception:
                print("Exception: {}".format(type(exception).__name__))
                print("Exception message: {}".format(exception))
        # publish unique device_address_list
        json_device_list = json.dumps({'device_address_list': device_addr_list})
        client.publish(topic_device_list, json_device_list, qos, 1)
        print('device_address_lists are published on topic '+str(topic_device_list))
        #execute every one hour
        sleep(3600)



