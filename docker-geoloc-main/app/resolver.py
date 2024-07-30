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
6. *TDOA-Method:*
Pseudo range distance between multiple gateways and device has been used
Apart from gateway locations, we need TOA (timestamp) data to estimate geolocation of end-device

7. *RSSI-Method:*
Absoulte (true range) distance between multiple gateways and device has been used
Apart from gateway locations, we need three more parameters to estimate geolocation such as RSSI (dBm),
A (dBm), n (eeta) values
Where A is absolute rssi value for 1 meter
n is path loss exponent or environmental exponent (mostly ranges between 2-3)

8. *Fused Method:*
Mean & Variance of TDOA & RSSI has been determined and it is passed to gaussian fusion function,
to estimate the possible position of device!

9. *KF Method:*
The above three methods has been calculated and the results are passed into KF function to determine
the most likely position of the device considering the observation noises or uncertainty of
toa timestamps and rssi variances, when the flag 'bCallPrevKFResults' is set to 'True', then
the previous kf results  are queried from DB and it is also passed along with currently calculated results!

"""
import os
import sys
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
postgres_password= 'Admin1234'
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
        tx_gps = np.array([47.85544376919304, 12.132042241083115, 475])
        tx_utm = myProj(tx_gps[1], tx_gps[0])
        return tx_utm, tx_gps, dev_name[0]

# calculate the distance of the end-device using RSS, A & n values
def distance_rssi(RSS, A, n):
    result = (A - RSS / 10 * n)
    dis = 10 ** (result)
    dis = np.array(dis)
    #dis = dis.transpose()
    return dis
# resolve the tdoa position given the toa & gateway locations
def resolve_tdoa(TOA, GWs):
    # guess= GWs.mean(axis=0)
    c = np.argmin(TOA)
    guess = GWs[c]
    # Call get_loci function
    # loci = get_loci(TOA, GWs, v, delta_d, max_d)
    p_c = np.expand_dims(GWs[c], axis=0)
    t_c = TOA[c]
    # Remove the c GW to allow for vectorization.
    all_p_i = np.delete(GWs, c, axis=0)
    all_t_i = np.delete(TOA, c, axis=0)
    # Position Calculation of Sensor
    def eval_solution(x):
        return (np.linalg.norm(x - p_c, axis=1) - np.linalg.norm(x - all_p_i, axis=1) + v * (all_t_i - t_c))
    res = least_squares(eval_solution, guess)
    return res
# trilaterate the position of devices by passing the absolute distances to the gateways using below function
def resolve_rssi(distances_to_station, stations_coordinates):
    def error(x, c, r):
        return sum([(np.linalg.norm(x - c[i]) - r[i]) ** 2 for i in range(len(c))])
    l = len(stations_coordinates)
    S = sum(distances_to_station)
    # compute weight vector for initial guess
    W = [((l - 1) * S) / (S - w) for w in distances_to_station]
    # get initial guess of point location
    x0 = sum([W[i] * stations_coordinates[i] for i in range(l)])
    # optimize distance_rssi from signal origin to border of spheres
    return minimize(error, x0, args=(stations_coordinates, distances_to_station), method='Nelder-Mead').x
# fuse tdoa & rssi positions with means of their variance using below function
def fuse_tdoa_rssi(mean1, var1, mean2, var2):
    sum = var1 + var2
    pr_s = mean1 * var2 + mean2 * var1
    new_mean = 1 / (sum) * pr_s
    product = var1 * var2
    new_var = product / sum
    return [new_mean, new_var]
# calculate A & n values acc. device_address
def calculate_a_n(GWs, rssi, tx_utm, *argv):
    # Variable initiation
    num_rows= len(rssi)
    print('No. of geoloc frames used for calculating A & n :',num_rows)
    distances = np.array([((x[0]-tx_utm[0])**2+(x[1]-tx_utm[1])**2)**0.5for x in GWs])
    #A= rssi/distances
    A= abs(rssi)/abs(distances)
    #n= rssi+A/-(10*np.log10(distances))
    n= abs(rssi)+abs(A)/-(10*np.log10(abs(distances)))
    #df.loc[:,'A']=A
    #df.loc[:,'n']=n
    mean_A = statistics.mean(A)
    mean_n = statistics.mean(n)
    if bPrint_debug:
        #df.to_csv('RSSI_Experiment/'+'RSSI_Experiment_'+str(dev_addr))
        print('A & n calculated & Exported as RSSI_Experiment/RSSI Experiment/'+str(dev_addr))
    return mean_A, mean_n
# HDOP
def DOP(GWs,**kwargs):
    global LOS_Matrix
    a = np.ones(GWs.shape[0])
    LOS_Matrix = np.column_stack([GWs,a])
    for key, value in kwargs.items():
        #print("%s == %s" % (key, value))
        if key == 'tx':
            #print('enters **kwargs')
            LOS_Matrix_2 = np.asarray([value[0], value[1], 1.0])
            LOS_Matrix = np.vstack((LOS_Matrix, LOS_Matrix_2))
    LOS_Matrix_t = LOS_Matrix.transpose()
    try:
        cov_matrix = np.linalg.inv(np.dot(LOS_Matrix_t, LOS_Matrix))
    except np.linalg.LinAlgError as err:
        if 'Singular matrix' in str(err):
            print("Oops! LOS_Matrix was Singular Matrix, which means Determinant equals zero, so performing pseudo-inverse")
            cov_matrix = np.linalg.pinv(np.dot(LOS_Matrix_t, LOS_Matrix))
    #print('shape of cov_matrix:', np.shape(cov_matrix))
    try:
        HDOP = np.sqrt(abs(cov_matrix[0,0]) + abs(cov_matrix[1,1]))
        return HDOP
    except (RuntimeError, TypeError, NameError):
        print("Oops! Negative value in Sqrt function")
        pass
# calculate difference between generated & calculated TOA (only if bTOACalculated is set to 'True')
def diff_gen_cal_toa(gen_toa, cal_toa):
    diff_gen_toa = np.zeros(len(gen_toa)-1)
    diff_cal_toa = np.zeros(len(cal_toa)-1)
    for i in range(1, len(gen_toa)):
        diff_gen_toa[i-1] = gen_toa[i]-gen_toa[i-1]
    for i in range(1, len(cal_toa)):
        diff_cal_toa[i-1] = cal_toa[i]-cal_toa[i-1]
    diff_toa = diff_gen_toa-diff_cal_toa
    diff_tdoa_rmse = np.sqrt((np.sum(diff_toa)**2/len(diff_gen_toa)))
    if bPrint_debug:
        print('toa_generated:', gen_toa)
        print('toa_calculated:', cal_toa)
        print('len(gen_toa):',len(gen_toa))
        print('len(cal_toa):', len(cal_toa))
        print('diff_gen_toa:',diff_gen_toa)
        print('diff_cal_toa:',diff_cal_toa)
        print('diff_toa:',diff_toa)
        print('diff_tdoa_rmse:', diff_tdoa_rmse)
    return diff_toa, diff_tdoa_rmse
# plot map for true location vs calculated location
def plot_map(ground_truth, tdoa, rssi, fused, kf, kf_smoother, dev_name, time_index, **kwargs):
    #all the arguments should be converted to UTM coordinates in order to plot the nodes in metres unit
    ground_truth = myProj(ground_truth[1], ground_truth[0])
    tdoa = myProj(tdoa[0], tdoa[1])
    rssi = myProj(rssi[0], rssi[1])
    fused = myProj(fused[0], fused[1])
    kf = myProj(kf[0], kf[1])
    smoother = myProj(kf_smoother[0], kf_smoother[1])
    # filename for each error map acc. to device name
    file_name = dev_name + '_utm_tdoa_rssi_fused_kf_error_map'
    fig, ax = plt.subplots(1, 1)
    ax.scatter(tdoa[0], tdoa[1], c='b', label='tdoa')
    ax.scatter(rssi[0], rssi[1], c='g', label='rssi')
    ax.scatter(fused[0], fused[1], c='c', label='fused')
    ax.scatter(kf[0], kf[1], c='m', label='kf')
    ax.scatter(smoother[0], smoother[1], marker = "*", c='m', label='kf_smoothed')
    ax.scatter(ground_truth[0], ground_truth[1], c='r', label='ground truth')
    plt.legend()
    plt.xlabel('UTMx (longitude in meters)')
    plt.ylabel('UTMy (latitude in meters)')
    plt.title(str(dev_name)+' on '+str(time_index.min()), fontweight = 'bold')
    plt.savefig(error_map_path + file_name)
    if bPrint_debug:
        print('ground_truth:', ground_truth)
        print('tdoa:', tdoa)
        print('rssi:', rssi)
        print('fused:', fused)
        print('kf_filter:', kf)
    print('Error Map plotted & stored in the destination folder: '+str(error_map_path) + str(file_name)+' successfully')
    #plt.show()
def plot_main_error(dev_addr, error_map_path, main_error, time_index, print_str):
    # draw main errors
    file_name = 'main_error_'+str(print_str)+'_'+dev_addr
    plt.figure()
    points_main_errors = plt.plot(main_error, color='b', label = 'main_error')
    plt.legend()
    #pl.xlim(0, 10)
    plt.ylim(0, 300)
    plt.xlabel('samples(row_id)')
    plt.ylabel('error in meters')
    plt.title('Main error for '+str(print_str)+' '+str(dev_addr) + ' on ' + str(time_index.min()), fontweight='bold')
    plt.savefig(error_map_path + file_name)
    print('Error Map plotted & stored in the destination folder '+str(error_map_path) + str(file_name)+' successfully')
# calculate RSSI given the distance, A & n
def calculate_rssi(dis_rssi, A, n):
    #cal_rssi = (np.log10(A*dis_rssi))
    cal_rssi= (abs(A)*abs(dis_rssi))
    #temp= (10*np.log10(abs(distances)))
    return cal_rssi
# calculate noises associated with Uplinks/Tx
def cal_UL_noise_info(df):
    global mean_snr_db, mean_toa_u_nsec, mean_rssi_var_dbm
    mean_toa_u_nsec = df.toa_u_nsec.astype(float).mean()
    mean_snr_db = df.snr_db.astype(float).mean()
    # calculate rssi variance per each gateway_id, bcz b/w a gateway & device the rssi should be normally distributed
    grouped_df_temp = df.groupby(df.gateway_id)
    unique_gw_id = df.gateway_id.unique()
    temp_rssi_var = []
    for i in range(len(unique_gw_id)):
        grouped_df = grouped_df_temp.get_group(unique_gw_id[i])
        var_of_each_gw_id = grouped_df.rssi_dbm.astype(float).var()
        temp_rssi_var.append(var_of_each_gw_id)
    temp_rssi_var = np.array(temp_rssi_var)   # convert list into np.array in order to cal. variance
    temp_rssi_var_per_gw = temp_rssi_var[~np.isnan(temp_rssi_var)]  # remove na values from np.array
    print('temp_rssi_var_per_gw:', temp_rssi_var_per_gw)
    mean_rssi_var_dbm = temp_rssi_var_per_gw.mean()
    print('max. toa uncertainty in nsec:', df.toa_u_nsec.astype(float).max())
    print('min. toa uncertainty in nsec:', df.toa_u_nsec.astype(float).min())
    print('mean toa uncertainty in nsec:', mean_toa_u_nsec)
    print('mean of snr in dBm:', mean_snr_db)
    print('variance of rssi in dBm:', mean_rssi_var_dbm)
    return mean_toa_u_nsec, mean_rssi_var_dbm, mean_snr_db
# resolve tdoa, rssi, fused positions using below function
def komro_resolve(df, A, n, tx_utm, dev_addr, *argv):
    global index, tdoa_results, rssi_results, fusion_results, toa_var, rssi_var, time_index, TOA, toa_sec, total_unique_fcnts
    global Position_TDOA, Position_RSSI, Position_FUSED, error_tdoa, error_rssi, error_fused, total_unique_gw_id, GWs, rssi, dis_rssi
    # extract the subset/ individual components of dataframe being grouped
    time_index = df.index
    column = df.columns
    values = df.values
    # device frame on 27.04 @ 11:35
    toa = np.asarray(pd.to_numeric(df['toa'])).astype(float)
    rssi = np.asarray(pd.to_numeric(df['rssi_dbm'])).astype(float)
    toa_sec = np.asarray(pd.to_numeric(df['toa_sec'])).astype(float)
    toa_n_sec = np.asarray(pd.to_numeric(df['toa_nsec'])).astype(float)
    toa_u = np.asarray(pd.to_numeric(df['toa_u_nsec'])).astype(float)
    foa_u = np.asarray(pd.to_numeric(df['fo_u_hz'])).astype(float)
    fo = np.asarray(pd.to_numeric(df['fo_hz'], errors='coerce'))
    lat = np.array(pd.to_numeric(df['gateway_latitude'])).astype(float)
    lon = np.array(pd.to_numeric(df['gateway_longitude'])).astype(float)
    alt = np.asarray(pd.to_numeric(df['gateway_altitude'])).astype(float)
    # properties of filtered DF
    total_unique_fcnts = len(df.frame_cnt.unique())
    total_unique_gw_id = len(df.gateway_id.unique())
    no_of_occurences = df.frame_cnt.value_counts()
    if len(df) > 2:
        toa_n_sec_mean = statistics.mean(toa_n_sec)
        toa_u = statistics.mean(toa_u)
        rssi_u = statistics.variance(rssi)
        fo = statistics.mean(fo)
        foa_u = statistics.mean(foa_u)
        # assign mean var. of per gateway rssi as rssi uncertainty!
        if ~ np.isnan(mean_rssi_var_dbm):
            rssi_u = mean_rssi_var_dbm
        else:
            rssi_u = rssi_u
        num_TOAs = len(toa)
        GWs = np.zeros((num_TOAs, 2))
        # convert lat, lon to x,y
        for i in range(GWs.shape[0]):
            GWs[i][0], GWs[i][1] = myProj(lon[i], lat[i])
        # assign toa (extracted df) to TOA (df used by program for calculations)
        TOA = toa
        # TDOA: call the function resolve_tdoa
        Position_tdoa = resolve_tdoa(TOA, GWs)
        Position_TDOA = myProj(Position_tdoa.x[0], Position_tdoa.x[1], inverse=True)
        Position_TDOA = np.array(Position_TDOA)
        error_tdoa = Position_tdoa.x - tx_utm
        # RSSI: call the function calculate_a_n, distance_rssi & resolve_rssi
        # calculate A & n value for RSSI based geolocation (dynamic)
        if bDynamic_A_n:
            A, n = calculate_a_n(GWs, rssi, tx_utm, dev_addr)
        # if bPrint_debug:
        print('A:', A)
        print('n:', n)
        dis_rssi = distance_rssi(rssi, A, n)
        # initialize a list to store measured distances
        dis_list = []
        for i in range(num_TOAs):
            distance_i = dis_rssi[i]
            dis_list.append(distance_i)
        Position_rssi = resolve_rssi(dis_list, GWs)
        Position_RSSI = myProj(Position_rssi[0], Position_rssi[1], inverse=True)
        Position_RSSI = np.array(Position_RSSI)
        error_rssi = Position_rssi - tx_utm
        # Fused: call the function fuse_tdoa_rssi
        # extract noise information based on toa_u & rssi variance
        toa_u = toa_u / 3
        toa_u = 0.5 * toa_u
        toa_var = np.array([toa_u, toa_u]).astype(float)
        rssi_u = abs(rssi_u) / A
        rssi_u = 0.5 * rssi_u
        rssi_var = np.array([rssi_u, rssi_u]).astype(float)
        Position_fused = fuse_tdoa_rssi(Position_rssi, rssi_var, Position_tdoa.x, toa_var)
        error_fusion = Position_fused[0] - tx_utm
        Position_FUSED = myProj(Position_fused[0][0], Position_fused[0][1], inverse=True)
        # DOP calculation for checking the quality of gateway placements
        HDOP = DOP(GWs, tx=tx_utm)
        # HDOP = DOP(GWs)
        print('HDOP_calculated:', HDOP)
        # percentage error [in meters]
        percentage_tdoa_error = (Position_tdoa.x - tx_utm) / tx_utm * 100
        percentage_rssi_error = (Position_rssi - tx_utm) / tx_utm * 100
        percentage_fused_error = (Position_fused[0] - tx_utm) / tx_utm * 100
        percentage_tdoa_error = abs(np.sum(percentage_tdoa_error))
        percentage_rssi_error = abs(np.sum(percentage_rssi_error))
        percentage_fused_error = abs(np.sum(percentage_fused_error))
        # print('percentage_tdoa_error:', percentage_tdoa_error)
        # print('percentage_rssi_error:', percentage_rssi_error)
        # print('percentage_fused_error:', percentage_fused_error)
    else:
        toa_n_sec_mean = 1
        toa_u = 1
        rssi_u = 1
        fo = 1
        foa_u = 1
    return Position_TDOA, Position_RSSI, Position_FUSED, error_tdoa, error_rssi, error_fusion, HDOP
#for mobile device filtering last/recent (also best) Fcntup instance
def filter_last_fcntup(df):
    global f_index, frame_count, grouped_df, total_unique_gw_id
    f_index = -1
    frame_counts = df.frame_cnt
    unique_frame_counts = frame_counts.unique()
    total_unique_fcnts = len(unique_frame_counts)
    total_unique_gw_id = len(df.gateway_id.unique())
    no_of_occurences= df['frame_cnt'].value_counts()
    recent_total_frames= no_of_occurences[unique_frame_counts[f_index]]
    #print('recent_total_frames:',recent_total_frames)
    #groupbyfcntup
    grouped = df.groupby(df.frame_cnt)
    skipped_frames = 0
    total_filtered_frames = 0
    total_unique_gw_id = 0
    if (total_unique_fcnts > 1 or recent_total_frames < 3):
        #print('enters last framecntup > IF Statement')
        while (skipped_frames < total_unique_fcnts and total_unique_gw_id < 3):
            f_index = f_index-1
            grouped_df = grouped.get_group(unique_frame_counts[f_index])
            total_unique_gw_id = len(grouped_df.gateway_id.unique())
            total_filtered_frames = len(grouped_df)
            skipped_frames = skipped_frames + 1
    else:
        #print('enters last framecntup > ELSE Statement')
        grouped_df = grouped.get_group(unique_frame_counts[f_index])
        total_filtered_frames = len(grouped_df)
    if bPrint_debug:
        total_unique_gw_id = len(df.gateway_id.unique())
        print('no. of unique gw_ids:', total_unique_gw_id)
        print('no. of unique frame counts:', total_unique_fcnts)
        print('unique_frame_counts:', unique_frame_counts)
        print('no_of_occurences:', no_of_occurences)
        print('recent_total_frames:', recent_total_frames)
        print('grouped_df:', grouped_df)
        print('frame_cnt_used:',grouped_df.frame_cnt.unique())
        frame_count = grouped_df.frame_cnt.unique()
    print('frame_cnt_used:', grouped_df.frame_cnt.unique()[0])
    return grouped_df
#for stationary device filtering/grouping last two or more Fcntup instances
def filter_multi_fcntup(df, set_fcnt):
    frame_counts = df.frame_cnt
    unique_frame_counts = frame_counts.unique()
    total_unique_fcnts= len(unique_frame_counts)
    total_unique_gw_id = len(df.gateway_id.unique())
    no_of_occurences = df.frame_cnt.value_counts()
    # groupbyfcntup & print the size
    grouped = df.groupby(df.frame_cnt)
    unique_frame_counts = grouped.frame_cnt.unique()
    print('len_of_unique_frame_counts_b4_grouping_best_fcnts:', len(unique_frame_counts))
    # filter grouped dataframes acc. to 'set_fcnt'
    if set_fcnt < 2 or total_unique_fcnts < 2:
        print('no grouping with one unique frame group, so just returning the entire df')
        grouped_df = df
        #grouped_df = grouped_df[len(grouped_df['gateway_id'].unique())>2]
        unique_frame_counts = grouped_df.frame_cnt.unique()
    elif set_fcnt == 2 or total_unique_fcnts == 2:
        grouped_df= pd.concat([group for (name, group) in grouped if
                               name in [unique_frame_counts[-1], unique_frame_counts[-2]]])
        #grouped_df = grouped_df[len(grouped_df['gateway_id'].unique())>2]
        unique_frame_counts = grouped_df.frame_cnt.unique()
    elif set_fcnt == 3 or total_unique_fcnts == 3:
        grouped_df = pd.concat([group for (name, group) in grouped if
                                name in [unique_frame_counts[-1], unique_frame_counts[-2], unique_frame_counts[-3]]])
        #grouped_df = grouped_df[len(grouped_df['gateway_id'].unique())>2]
        unique_frame_counts = grouped_df.frame_cnt.unique()
    else:
        # assemble all the unique frame counts (ULs) present in df
        print('set_fcnt is more than 3, so all ULs frames are grouped & filtered')
        grouped_df = grouped.filter(lambda x: len(x['gateway_id'].unique())>2)
        unique_frame_counts = grouped_df.frame_cnt.unique()
    if bPrint_debug:
        print('no. of unique gateway IDs:', total_unique_gw_id)
        print('no. of unique frame counts:', total_unique_fcnts)
        print('unique_frame_counts:',unique_frame_counts)
        print('no_of_occurences:',no_of_occurences)
        print('grouped:', grouped_df)
    print('len_of_unique_frame_counts_after_grouping_best_fcnts:', len(unique_frame_counts))
    return grouped_df
# numpy json encoder for dealing with datatype errors
class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(NpEncoder, self).default(obj)
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
# reformat acc. to requirements of subscriber_db.py
def reformat_error_msg(payload, dev_addr):
    payload = {'device_address': dev_addr,'payload': payload}
    json_formatted = json.dumps(payload)
    print('formatted_error_payload:', json_formatted)
    return json_formatted

# covariance of kf object
cov = 1 * np.array([[1, 0], [0, 1]])
# tuning params [transition_covariance, observation_covariance]
kf = KalmanFilter(n_dim_state=2,
                  n_dim_obs=2,
                  transition_matrices=[[1, 0], [0, 1]],
                  observation_matrices=[[1, 0], [0, 1]],
                  transition_covariance=[[1, 0], [0, 1]],
                  initial_state_covariance=cov)
# kalman filter to estimate from tdoa, rssi & fused results [as measurements]
def kf_estimate(kf, measurements, ground_truth, dev_addr, time_index):
    # kf function, pass some geolocation estimates from previous cycle & current cycle (gaussian mixer model)
    file_name = dev_addr
    for i in range(measurements.shape[0]):
        measurements[i] = myProj(measurements[i][1], measurements[i][0])
    ground_truth = myProj(ground_truth[1], ground_truth[0])
    kf.initial_state_mean = measurements[0]
    kf = kf.em(measurements, n_iter=10)
    (filtered_state_means, filtered_state_covariances) = kf.filter(measurements)
    (smoothed_state_means, smoothed_state_covariances) = kf.smooth(measurements)
    kf_filter_error_lat = np.sqrt((filtered_state_means[0][1] - ground_truth[1]) ** 2)
    kf_filter_error_lon = np.sqrt((filtered_state_means[0][0] - ground_truth[0]) ** 2)
    kf_smoother_error_lat = np.sqrt((smoothed_state_means[0][1] - ground_truth[1]) ** 2)
    kf_smoother_error_lon = np.sqrt((smoothed_state_means[0][0] - ground_truth[0]) ** 2)
    #kf_error_lat = np.sqrt((kf_filter_error_lat + kf_smoother_error_lat)**2)
    #kf_error_lon = np.sqrt((kf_filter_error_lon + kf_smoother_error_lon)**2)
    kf_error_lat = kf_filter_error_lat
    kf_error_lon = kf_filter_error_lon
    kf_smoothed_error_lat = kf_smoother_error_lat
    kf_smoothed_error_lon = kf_smoother_error_lon
    if bPrint_debug:
        print('ground_truth:', ground_truth)
        print('measurements:', measurements)
        print('kf_error_lat:', kf_error_lat)
        print('kf_error_lon:', kf_error_lon)
        print('kf_smoothed_error_lat:', kf_smoothed_error_lat)
        print('kf_smoothed_error_lon:', kf_smoothed_error_lon)
        fig, ax = plt.subplots(1, 1)
        ax.scatter(measurements[:, 0], measurements[:, 1], label='meas')
        ax.scatter(filtered_state_means[:, 0], filtered_state_means[:, 1], c='b', label='filter')
        ax.scatter(smoothed_state_means[:, 0], smoothed_state_means[:, 1], c='g', label='smooth')
        ax.scatter(ground_truth[0], ground_truth[1], c='r', label='ground truth')
        plt.legend()
        plt.xlabel('UTMx (longitude in meters)')
        plt.ylabel('UTMy (latitude in meters)')
        plt.title('kf for '+str(dev_addr) + ' on ' + str(time_index.min()), fontweight='bold')
        plt.savefig(kf_map_path + file_name)
        #plt.show()
    filtered_state_means = myProj(filtered_state_means[0][0], filtered_state_means[0][1], inverse=True)
    smoothed_state_means = myProj(smoothed_state_means[0][0], smoothed_state_means[0][1], inverse=True)
    return filtered_state_means, smoothed_state_means, kf_error_lat, kf_error_lon, kf_smoothed_error_lat, kf_smoothed_error_lon
# filter out komro kf geolocation results [KF]
def query_kf_results(dev_addr):
    global time_index, tx_gps, device_name, tx_utm
    # get the true location for error calculation
    #tx_utm, tx_gps, device_name = true_position(df_trueloc, dev_addr)
    # query the last three rows of kalman-filtered estimations
    #%%/estimation/kf/komro/%% #%%tdoa%%
    desc_limit= 5
    sql_query = '''SELECT * from public.geoloc_results
                   WHERE (device_address = %s AND topic LIKE '%%calculation%%' AND num_of_gateways_used>2)
                   ORDER BY time DESC LIMIT %s;'''
    conn = psycopg2.connect(user='postgres',
                            host=postgres_host,
                            port=postgres_port,
                            password=postgres_password,
                            database=DB_NAME)
    cur = conn.cursor()
    cur.execute(sql_query, (dev_addr,desc_limit))
    SQL_Query = cur.fetchall()
    df_0 = pd.DataFrame(SQL_Query,
                        columns=['id', 'time', 'topic', 'device_address', 'device_name', 'num_of_gateways_used', 'num_of_ul_packets_used', 'latitude_tdoa', 'longitude_tdoa',
                                  'latitude_rssi', 'longitude_rssi', 'latitude_fused', 'longitude_fused', 'latitude_kf', 'longitude_kf', 'latitude_kfs', 'longitude_kfs',
                                 'latitude_true', 'longitude_true', 'error_tdoa', 'error_rssi', 'error_fused', 'error_kf', 'error_kfs',
                                 'hdop', 'mean_snr_db', 'mean_rssi_var_dbm', 'mean_toa_var_nsec', 'payloads'])
    df_0['time'] = pd.to_datetime(df_0['time'])
    df_0 = df_0.set_index('time').copy()
    # extract the subset/ individual components of dataframe being grouped
    time_index = df_0.index
    # sort geoloc frames based on time
    df_0 = df_0.sort_index().copy()
    return df_0
# filter out more uncertain values
def query_less_noisy_toa(dev_addr, low, high):
    # df_0 is original dataframe whereas df is filtered dataframe
    sql_query = '''SELECT * from public.geoloc_packets 
                   WHERE (device_address = %s AND CAST(toa_u_nsec AS decimal(18, 2)) BETWEEN %s AND %s);'''
    conn = psycopg2.connect(user='postgres',
                            host=postgres_host,
                            port=postgres_port,
                            password=postgres_password,
                            database=DB_NAME)
    cur = conn.cursor()
    cur.execute(sql_query, (dev_addr,low, high,))
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
    # print UL noises (no useful here, since these frames are further filtered acc. to filter modes)
    # mean_toa_u_nsec, mean_rssi_var_dbm, mean_snr_db= cal_UL_noise_info(df_0)
    return df_0

def extract_geoloc_frames(dev_addr, filter_mode, num_of_frames, split_date, bmultiframe, *argv):
    # df_0 is original less noisy dataframe whereas df is filtered dataframe acc. to filter modes
    df_0 = query_less_noisy_toa(dev_addr, low_limit, high_limit)
    # filter modes to filter the geoloc data
    if filter_mode == 0:
        # group/filter based on number of rows
        df = df_0.copy()
        len_b4_filter = len(df)
        df = df.tail(n=num_of_frames).copy()
        len_after_filter = len(df)
    elif filter_mode == 1:
        # group/filter geoloc rows for last one hour
        df = df_0.copy()
        len_b4_filter = len(df)
        delta = pd.Timestamp.now() - pd.Timedelta(hours=1)
        df = df[df.index > delta].copy()
        len_after_filter = len(df)
    elif filter_mode == 2:
        # group/filter based on UL frame counts
        df = df_0.copy()
        len_b4_filter = len(df)
        if bmultiframe:
            # if only multiframe HTTP request enabled
            filtered_multiframe = filter_multi_fcntup(df, set_fcnt)
            df = filtered_multiframe
        else:
            print('extracts only last but best UL frame ')
            filtered_singleframe = filter_last_fcntup(df)
            df = filtered_singleframe
        len_after_filter = len(df)
    elif filter_mode == 3:
        # group/filter based on specific date. Ex: frames/rows after certain date.
        df = df_0.copy()
        len_b4_filter = len(df)
        df = df.loc[df.index > split_date].copy()
        len_after_filter = len(df)
        if bPrint_debug:
            print('split_date_1:', split_date)
            print('type split_date_1:', type(split_date))
            print('len_df:', len(df))
        if len(df)<4:
            split_date = datetime.now() - timedelta(days=5)
            split_date = split_date.replace(hour=0, minute=0, second=0, microsecond=0)
            #split_date= split_date.strftime("%y-%m-%d %H:%M:%S")
            df = df_0.copy()
            df = df.loc[df.index > split_date].copy()
            if bPrint_debug:
                print('type of split_date_2:', type(split_date))
                print('split_date_2:', split_date)
                print('df:', df)
    # length of dataframe before & after geoloc filter modes
    #if bPrint_debug:
    print('length of dataframe before geoloc filter:', len_b4_filter)
    print('length of dataframe after geoloc filter:',len_after_filter)
    # print UL noises
    mean_toa_u_nsec, mean_rssi_var_dbm, mean_snr_db = cal_UL_noise_info(df)
    return df

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
    mean_toa_u_nsec, mean_rssi_var_dbm, mean_snr_db= cal_UL_noise_info(df_0)
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

if __name__ == '__main__':
    global ground_truth, tdoa, rssi, fused, kf_filter, sem_s, sem_m, tek_est, diff_rssi_rmse, diff_tdoa_rmse
    while True:
        #execute every one hour
        print('Resolver timer starts 3600s.....')
        for remaining in range(3600, 0, -1):
            sys.stdout.write("\r")
            sys.stdout.write("{:2d} seconds remaining.".format(remaining))
            sys.stdout.flush()
            sleep(1)
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
            #device_addr_list = ['354b3a'] #713694,1ae331a,1e0ea9d,3b4016,708c6a
        else:
            device_addr_list = query_device_addr()
        for dev_addr in device_addr_list:
            print('device address:', dev_addr)
            # get the true location for error calculation
            tx_utm, tx_gps, device_name = true_position(df_trueloc, dev_addr)
            print('device_name:', device_name)
            #MQTT Topics
            topic_calculation = "geolocation/calculation/komro/" + str(dev_addr)
            topic_true = "geolocation/calculation/groundtruth/" + str(dev_addr)
            topic_error_exception = "geolocation/error/exception/komro/" + str(dev_addr)
            try:
                A = -28.64
                n = 2.74
                filter_mode = 2           # 0 or 2 only for http request!!
                bmultiframe = 0        # if set to 1, multiple ULs will be passed to resolver function!(boolean)
                num_of_frames = 20
                bCalculatedTOA = False
                # for filter mode 3, specify the date from which we need to estimate (not mandatory passed a arbitrary argument)
                split_date = datetime(2021, 5, 4)
                set_fcnt = 1  # how many UL frame groups should be extracted (for multiframe resolve/request)
                low_limit = -500  # lower toa_uncertainty limit
                high_limit = 500  # higher toa_uncertainty limit
                # filter geoloc packets as dataframe (df)
                if bQuery_frame_cnt and dev_addr == '183838':
                    # query geoloc packets acc. to frame_cnt & device_address (especially for evaluating sp. frame counts)
                    print('Entered bQuery_frame_cnt statement')
                    # frame count to be queried
                    frame_cnt = '1722'   #'3315'
                    df = query_frame_cnt(dev_addr, frame_cnt)
                else:
                    # query geoloc packets acc. to filter modes
                    df = extract_geoloc_frames(dev_addr, filter_mode, num_of_frames, split_date, bmultiframe, set_fcnt, low_limit, high_limit)
                # publish the groundtruth
                #json_true = json.dumps({'device_address': dev_addr, 'device_name': device_name, 'latitude': str(tx_gps[0]),'longitude': str(tx_gps[1])})
                #client.publish(topic_true, json_true, qos, retain)
                # properties of filtered DF
                total_unique_fcnts = len(df.frame_cnt.unique())
                total_unique_gw_id = len(df.gateway_id.unique())
                no_of_occurences = df.frame_cnt.value_counts()
                frame_cnt_resolved = df.frame_cnt.unique()[0]
                print('frame_cnt_resolved:', frame_cnt_resolved)
                print('no. of unique frame counts:', total_unique_fcnts)
                print('no. of unique gateway IDs:', total_unique_gw_id)
                print('no_of_occurences:', no_of_occurences)
                # get the true location for error calculation
                #tx_utm, tx_gps, device_name = true_position(df_trueloc, dev_addr)
                #print('device_name:', device_name)
                # resolve_utm only for gateways more than 2
                if total_unique_gw_id >= 1:
                    result = komro_resolve(df, A, n, tx_utm, dev_addr, bCalculatedTOA)
                    print('result:', result)
                    print('Position Resolved for device ' + str(dev_addr) + ' successfully by Komro Resolver')
                    tdoa = np.zeros(2)
                    rssi = np.zeros(2)
                    fused = np.zeros(2)
                    tdoa_error = np.zeros(2)
                    rssi_error = np.zeros(2)
                    fused_error = np.zeros(2)
                    tdoa[0] = result[0][1]
                    tdoa[1] = result[0][0]
                    rssi[0] = result[1][1]
                    rssi[1] = result[1][0]
                    fused[0] = result[2][1]
                    fused[1] = result[2][0]
                    tdoa_error[0] = result[3][1]
                    tdoa_error[1] = result[3][0]
                    main_tdoa_error = np.sqrt((tdoa_error[0])**2 + (tdoa_error[1])**2)
                    rssi_error[0] = result[4][1]
                    rssi_error[1] = result[4][0]
                    main_rssi_error = np.sqrt((rssi_error[0])**2 + (rssi_error[1])**2)
                    fused_error[0] = result[5][1]
                    fused_error[1] = result[5][0]
                    main_fused_error = np.sqrt((fused_error[0])**2 + (fused_error[1])**2)
                    hdop = result[6]
                    # exception handling in case of infinity values in results
                    # geo-fence for each methods
                    lat_lim = [46, 48]
                    lon_lim = [11, 13]
                    geo_fence_tdoa_ok = (((lat_lim[0] < tdoa[0]) & (tdoa[0] < lat_lim[1])) & (
                                (lon_lim[0] < tdoa[1]) & (tdoa[1] < lon_lim[1]))).all()
                    geo_fence_rssi_ok = (((lat_lim[0] < rssi[0]) & (rssi[0] < lat_lim[1])) & (
                                (lon_lim[0] < rssi[1]) & (rssi[1] < lon_lim[1]))).all()
                    geo_fence_fused_ok = (((lat_lim[0] < fused[0]) & (fused[0] < lat_lim[1])) & (
                                (lon_lim[0] < fused[1]) & (fused[1] < lon_lim[1]))).all()
                    print('geo_fence_tdoa_ok:', geo_fence_tdoa_ok)
                    print('geo_fence_fused_ok:', geo_fence_fused_ok)
                    if ~np.isfinite(tdoa).any() or np.isnan(tdoa).any() or ~geo_fence_tdoa_ok:
                        tdoa = [0, 0]
                    if ~np.isfinite(rssi).any() or np.isnan(rssi).any() or ~geo_fence_rssi_ok:
                        rssi = [0, 0]
                    if ~np.isfinite(fused).any() or np.isnan(fused).any() or ~geo_fence_fused_ok:
                        fused = [0, 0]
                    if ~np.isfinite(tdoa_error).any() or np.isnan(tdoa_error).any() or ~geo_fence_tdoa_ok:
                        tdoa_error = [0, 0]
                        main_tdoa_error = 0
                    if ~np.isfinite(rssi_error).any() or np.isnan(rssi_error).any() or ~geo_fence_rssi_ok:
                        rssi_error = [0, 0]
                        main_rssi_error = 0
                    if ~np.isfinite(fused_error).any() or np.isnan(fused_error).any() or ~geo_fence_fused_ok:
                        fused_error = [0, 0]
                        main_fused_error = 0
                    if ~np.isfinite(hdop).any() or np.isnan(hdop):
                        hdop = 0
                    if np.isnan(mean_rssi_var_dbm).any():
                        mean_rssi_var_dbm = 0
                    # write the above updated (valid) values to original_meas which will be passed to kf function
                    original_meas = np.asarray([tdoa, rssi, fused])
                    #diff_tdoa_rmse = 0
                    if bCalculatedTOA:
                        t_0 = toa_sec
                        distances = np.array([((x[0] - tx_utm[0]) ** 2 + (x[1] - tx_utm[1]) ** 2) ** 0.5 for x in GWs])
                        calculated_toa = distances / v + t_0
                        # TOA += np.random.normal(loc=0, scale=rec_time_noise_stdd,size=num_TOAs)
                        diff_toa_array, diff_tdoa_rmse_temp = diff_gen_cal_toa(TOA, calculated_toa)
                        diff_tdoa_rmse.append(diff_tdoa_rmse_temp)
                        if bPrint_debug:
                            print('enters bCalculatedTOA')
                            print('toa_generated:', TOA)
                            print('toa_calculated:', calculated_toa)
                            print('diff_toa:', diff_toa_array)
                            print('diff_tdoa_rmse:', diff_tdoa_rmse)
                    # kf portion
                    pos = []
                    i = 0
                    if bAssemble_tdoa_result:
                        pos.append([original_meas[0][0], original_meas[0][1]])
                        pos.append([original_meas[0][0], original_meas[0][1]])
                    else:
                        # assemble current geoloc results
                        for i in range(len(original_meas)):
                            pos.append([original_meas[i][0], original_meas[i][1]])
                    # concatenate previous kf geoloc results
                    kf_results_df = query_kf_results(dev_addr)
                    if len(kf_results_df) == 0 or not(bCallPrevKFResults):
                        #if the kf dataframe is empty, then pass the loop
                        print('not calling previous KF results')
                        pass
                    else:
                        latitude = np.array(kf_results_df.latitude.astype(float))
                        longitude = np.array(kf_results_df.longitude.astype(float))
                        num_of_ul_packets_used = round(np.mean(kf_results_df.num_of_ul_packets_used.astype(float)))
                        num_of_gateways_used = round(np.mean(kf_results_df.num_of_gateways_used.astype(float)))
                        HDOP = np.mean(kf_results_df.hdop.astype(float))
                        for i in range(len(latitude)):
                            pos.append([latitude[i], longitude[i]])
                    #print('pos:', pos)
                    measurements = np.array(pos)      #all results
                    # geo-fence to eliminate invalid geo-coordinates (46-48 & 11-13)
                    measurements = measurements[((measurements[:, 0] > 46) & (measurements[:, 0] < 48))]
                    measurements = measurements[((measurements[:, 1] > 11) & (measurements[:, 1] < 13))]
                    # print ground truth for comparison
                    print('ground truth:', tx_gps)
                    print('measurements to kf function:', measurements)
                    # ground_truth = [47.855329,12.132985]
                    ground_truth = np.array([tx_gps[0], tx_gps[1]])
                    # concatenate variance of kf measurements [R]
                    mean_rssi_var_m = abs(mean_rssi_var_dbm/2)
                    mean_toa_u_m = abs(mean_toa_u_nsec/3)
                    mean_R = np.mean([mean_rssi_var_m, mean_toa_u_m])
                    print('Mean R in meters:', mean_R)
                    kf.observation_covariance = mean_R* np.array([[1, 0], [0, 1]])
                    kf_filter, kf_smoother, kf_error_lat, kf_error_lon, kf_smoothed_error_lat, kf_smoothed_error_lon = kf_estimate(
                        kf, measurements, ground_truth, dev_addr, time_index)
                    main_kf_error = np.sqrt((kf_error_lat) ** 2 + (kf_error_lon) ** 2)
                    main_kf_smoothed_error = np.sqrt((kf_smoothed_error_lat) ** 2 + (kf_smoothed_error_lon) ** 2)
                    json_result = json.dumps({'device_address': dev_addr, 'device_name': device_name, 'numOfGatewaysUsed': total_unique_gw_id, 'HDOP': hdop, 'numOfULPacketsUsed': total_unique_fcnts,
                                            'latitude_tdoa': tdoa[0], 'longitude_tdoa': tdoa[1],
                                            'latitude_rssi': rssi[0], 'longitude_rssi': rssi[1],
                                            'latitude_fused': fused[0], 'longitude_fused': fused[1],
                                            'latitude_kf': kf_filter[1], 'longitude_kf': kf_filter[0],
                                            'latitude_kfs': kf_smoother[1], 'longitude_kfs': kf_smoother[0],
                                            'latitude_true': str(tx_gps[0]), 'longitude_true': str(tx_gps[1]),
                                            'error_tdoa': main_tdoa_error, 'error_rssi': main_rssi_error, 'error_fused': main_fused_error, 'error_kf': main_kf_error, 'error_kfs': main_kf_smoothed_error,
                                            'mean_snr': mean_snr_db, 'mean_toa_u': mean_toa_u_nsec, 'mean_rssi_var': mean_rssi_var_dbm})
                    client.publish(topic_calculation, json_result, qos, retain)
                    print('main_tdoa_error:',main_tdoa_error)
                    print('main_rssi_error:', main_rssi_error)
                    print('main_fused_error:', main_fused_error)
                    print('main_kf_error:', main_kf_error)
                    print('main_kf_smoothed_error:', main_kf_smoothed_error)
                    print("Komro Resolved Positions published to topics: "+topic_calculation+" successfully for "+str(device_name))
                    print('Kalman Filter applied & published for TDOA, RSSI & Fused Results successfully')
                    if bPrint_debug:
                        print('tdoa:', tdoa)
                        print('rssi:', rssi)
                        print('fused:', fused)
                        print('kf_filter:', kf_filter)
                        print('ground_truth:', ground_truth)
                        # to plot calculated errors in a map & store them
                        plot_map(ground_truth, tdoa, rssi, fused, kf_filter, kf_smoother, device_name, time_index)
                    #print('Error Map plotted for ' + str(dev_addr) + ' successfully')
                else:
                    print('Due to less than three gateways, the resolver FOR LOOP passed for '+str(device_name))
                    pass
            except IndexError as index_error:
                print("Exception: {}".format(type(index_error).__name__))
                print('num. of gateways reached per uplink by ' + str(dev_addr) + ':', total_unique_gw_id)
            except Exception as exception:
                print("Exception: {}".format(type(exception).__name__))
                print("Exception message: {}".format(exception))
                error_msg_temp = json.dumps(['Cant resolve for ' + str(dev_addr) + ', ' + str(exception)])
                error_msg = reformat_error_msg(error_msg_temp, dev_addr)
                client.publish(topic_error_exception, error_msg, qos, retain)
        # differential toa root mean square error [RMSE]
        json_diff_tdoa_rmse = json.dumps({'device_address_list': device_addr_list, 'diff_tdoa_rmse': diff_tdoa_rmse})
        client.publish(topic_diff_tdoa_rmse, json_diff_tdoa_rmse, qos, retain)
        # publish unique device_address_list
        json_device_list = json.dumps({'device_address_list': device_addr_list})
        client.publish(topic_device_list, json_device_list, qos, 1)
        print('device_address_lists are published on topic '+str(topic_device_list))



