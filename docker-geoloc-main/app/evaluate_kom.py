
import pandas as pd
import psycopg2
from pylab import*
from datetime import datetime

global dev_addr, qos, retain, device_name

#Postgres DB parameters
postgres_host= 'localhost'
postgres_port= '5432'
postgres_password= 'Admin1234'
DB_NAME= 'Geolocation_DB'

# to query data from new error table
def exec_sql_query(conn, sql_query):
    # sql_query_komro
    cur = conn.cursor()
    cur.execute(sql_query,)
    SQL_Query = cur.fetchall()
    df = pd.DataFrame(SQL_Query,
                        columns=['id', 'time', 'topic', 'device_address', 'device_name', 'num_of_gateways_used', 'num_of_ul_packets_used', 'latitude_tdoa', 'longitude_tdoa',
                                  'latitude_rssi', 'longitude_rssi', 'latitude_fused', 'longitude_fused', 'latitude_kf', 'longitude_kf', 'latitude_kfs', 'longitude_kfs',
                                 'latitude_true', 'longitude_true', 'error_tdoa', 'error_rssi', 'error_fused', 'error_kf', 'error_kfs',
                                 'hdop', 'mean_snr_db', 'mean_rssi_var_dbm', 'mean_toa_var_nsec', 'payloads'])
    return df
# filter out komro geolocation results [TDOA, RSSI, Fused, KF]
def query_errors():
    # query the main error of devices which reached atleast 3 gateways
    sql_query_overall = '''SELECT * from public.geoloc_results;'''
    conn = psycopg2.connect(user='postgres',
                            host=postgres_host,
                            port=postgres_port,
                            password=postgres_password,
                            database=DB_NAME)
    df_overall = exec_sql_query(conn, sql_query_overall)
    return df_overall

def search_coordinate(df_data: pd.DataFrame, search_set: set) -> list:
    nda_values = df_data.values
    tuple_index = np.where(np.isin(nda_values, [e for e in search_set]))
    return [(row, col, nda_values[row][col]) for row, col in zip(tuple_index[0], tuple_index[1])]

# query max error statistics of sp. device
def max_dev_error(dev_addr, df_0):
    # filter device address
    df_0 = df_0[df_0.device_address == dev_addr]
    # set datetime index
    #df_0['time'] = pd.to_datetime(df_0['time'])
    df_0 = df_0.set_index('time').copy()
    # sort geoloc frames based on time
    df_0 = df_0.sort_index().copy()
    max_toa_var_nsec = df_0.mean_toa_var_nsec.astype(float).max()
    max_snr_db = df_0.mean_snr_db.astype(float).max()
    max_rssi_var_dbm = df_0.mean_rssi_var_dbm.astype(float).max()
    max_error_tdoa = df_0.error_tdoa.astype(float).max()
    max_error_rssi = df_0.error_rssi.astype(float).max()
    max_error_fused = df_0.error_fused.astype(float).max()
    max_error_kf = df_0.error_kf.astype(float).max()
    max_error = np.max([min_error_kf, min_error_fused, min_error_rssi, min_error_tdoa])
    if bPrint_max:
        #print('max. toa uncertainty in nsec:', max_toa_u_nsec)
        #print('max. of snr in dBm:', max_snr_db)
        #print('max. variance of rssi in dBm', max_rssi_var_dbm)
        print('max. error in meters:', max_error)
    return max_toa_var_nsec, max_snr_db, max_rssi_var_dbm, max_error_tdoa, max_error_rssi, max_error_fused, max_error_kf, max_error
# query min error statistics of sp. device
def min_dev_error(dev_addr, df_0):
    # filter device address
    df_0 = df_0[df_0.device_address == dev_addr]
    # set datetime index
    #df_0['time'] = pd.to_datetime(df_0['time'])
    df_0 = df_0.set_index('time').copy()
    # sort geoloc frames based on time
    df_0 = df_0.sort_index().copy()
    min_toa_var_nsec = df_0.mean_toa_var_nsec.astype(float).min()
    min_snr_db = df_0.mean_snr_db.astype(float).min()
    min_rssi_var_dbm = df_0.mean_rssi_var_dbm.astype(float).min()
    min_error_tdoa = df_0.error_tdoa.astype(float).min()
    min_error_rssi = df_0.error_rssi.astype(float).min()
    min_error_fused = df_0.error_fused.astype(float).min()
    min_error_kf = df_0.error_kf.astype(float).min()
    min_error = np.min([min_error_kf, min_error_fused, min_error_rssi, min_error_tdoa])
    if bPrint_min:
        #print('min. toa uncertainty in nsec:', min_toa_u_nsec)
        #print('min. of snr in dBm:', min_snr_db)
        #print('min. variance of rssi in dBm', min_rssi_var_dbm)
        print('min. tdoa error in meters:', min_error_tdoa)
        print('min. rssi error in meters:', min_error_rssi)
        print('min. fused error in meters:', min_error_fused)
        print('min. kf error in meters:', min_error_kf)
        #print('method_used:', df_0.topic[df_0.mean_error==min_error].unique()[0])
        #print('num_of_gateways_used:', df_0.num_of_gateways_used[df_0.mean_error == min_error].unique()[0])
        # find the row, column & value in df, given a certain value
        min_error_index = search_coordinate(df_0, {min_error})
        #print('min_error_cindex:', min_error_index[0][1])
        # extract the row where the error is minimum
        timestamp = df_0.index[min_error_index[0][0]]
        print('timestamp:', timestamp)
        num_of_gateways_used = df_0.iloc[min_error_index[0][0],3]
        print('num_of_gateways_used:', num_of_gateways_used)
        # column name containing least minimum  error
        min_error_source = df_0.columns[min_error_index[0][1]]
        print('min_error_source:', min_error_source)
    return min_toa_var_nsec, min_snr_db, min_rssi_var_dbm, min_error_tdoa, min_error_rssi, min_error_fused, min_error_kf, min_error
# query mean error statistics of sp. device
def mean_dev_error(dev_addr, df_0):
    # filter device address
    df_0 = df_0[df_0.device_address == dev_addr]
    # set datetime index
    #df_0['time'] = pd.to_datetime(df_0['time'])
    df_0 = df_0.set_index('time').copy()
    # sort geoloc frames based on time
    df_0 = df_0.sort_index().copy()
    mean_toa_var_nsec = df_0.mean_toa_var_nsec.astype(float).mean()
    mean_snr_db = df_0.mean_snr_db.astype(float).mean()
    mean_rssi_var_dbm = df_0.mean_rssi_var_dbm.astype(float).mean()
    mean_error_tdoa = df_0.error_tdoa.astype(float).mean()
    mean_error_rssi = df_0.error_rssi.astype(float).mean()
    mean_error_fused = df_0.error_fused.astype(float).mean()
    mean_error_kf = df_0.error_kf.astype(float).mean()
    mean_error = np.mean([mean_error_tdoa, mean_error_rssi, mean_error_fused, mean_error_kf])
    if bPrint_mean:
        #print('mean toa uncertainty in nsec:', mean_toa_u_nsec)
        #print('mean of snr in dBm:', mean_snr_db)
        #print('mean variance of rssi in dBm', mean_rssi_var_dbm)
        print('mean_error in meters (RMS):', mean_error)
    return mean_toa_var_nsec, mean_snr_db, mean_rssi_var_dbm, mean_error_tdoa, mean_error_rssi, mean_error_fused, mean_error_kf, mean_error
# plot df
def plot_df(df, title, file_name ):
    error_map_path= 'errors_vs_samples/DF/'
    df = df.drop('id', 1)
    # set datetime index
    df['time'] = pd.to_datetime(df['time'])
    df = df.set_index('time').copy()
    ax = df.plot()
    ax.set(title= str(title))
    plt.savefig(error_map_path + file_name)
    print('DF plot stored in the destination folder ' + str(error_map_path) + str(file_name))
    #plt.show()
def anayse_device_error(df, dev_addr):
    # analyse the toa, rssi, snr data of device
    dev_name = df.device_name[df.device_address == str(dev_addr)].unique()[0]
    '''    
    error = df.main_error[df.device_address == str(dev_addr)]
    #print('Statistics of '+str(dev_name)+' TDOA Error:', error.describe())
    #mean_toa_u_nsec = df.mean_toa_u_nsec[df.device_address == str(dev_addr)]
    #print('Statistics of '+str(dev_name)+' TDOA Uncertainty:', mean_toa_u_nsec.describe())
    #mean_rssi_var_dbm = df.mean_rssi_var_dbm[df.device_address == str(dev_addr)]
    #print('Statistics of '+str(dev_name)+' RSSI Variance:', mean_rssi_var_dbm.describe())
    #mean_snr_db = df.mean_snr_db[df.device_address == str(dev_addr)]
    #print('Statistics of '+str(dev_name)+' SNR:', mean_snr_db.describe())
    '''
    error = df[df.device_address == str(dev_addr)]
    print('Statistics of ' + str(dev_name) + ' TDOA Error:', error.describe())
# query error data
df_all = query_errors()

# control flags
bOld_error_table = False   # set this flags to false in order to query from new error table, this will be reset later
bPrint_min = True
bPrint_max = False
bPrint_mean = True
########################################### New Error table ############################################
#print('df_columns:',df_all.columns)
# data preprocessing
list_of_imp_columns= ['num_of_gateways_used', 'error_tdoa', 'error_rssi', 'error_fused', 'error_kf', 'mean_snr_db', 'mean_toa_var_nsec', 'hdop']
# convert the numerical data to floats apart from strings, so that it could be compared & filtered
df_all[list_of_imp_columns] = df_all[list_of_imp_columns].astype(float)
df_all[['topic', 'device_name','device_address']] = df_all[['topic', 'device_name', 'device_address']].astype(str)
# drop the unnecessary columns liks json, dict etc.
df_all = df_all.drop(['payloads', 'id'], 1)
df_all = df_all.dropna()
# remove geo-fence handled errors, 0 from main_error column
df_all[df_all[['error_tdoa', 'error_rssi', 'error_fused', 'error_kf']] != 0]
# filter datapoints in order to show the desired trends
#df_all = df_all.drop_duplicates()
# groupbyfcntup
#df_all = df_all.groupby(df_all.mean_snr_db).head(2).reset_index(drop=True)
#df_all = df_all.set_index('time').copy()
split_date = datetime(2021, 5, 4)
print('split_date:', split_date)
#df_all = df_all.loc[df_all.time >= split_date].copy()
# filter the errors less than a threshold
error_limit = 5000
#df_all = df_all[(df_all.error_tdoa <= error_limit) & (df_all.error_rssi <= error_limit) & (df_all.error_fused <= error_limit)& (df_all.error_kf <= error_limit)]
print('len of df_all after preprocessing:', len(df_all))

# assign tek, sem, kom data
df_kom = df_all[df_all.topic.str.contains('calculation')]
#df_kom = df_all
print('df_columns:', df_kom.columns)
'''
df_tek = df_all[df_all.topic.str.contains('tektelic')]
df_sem = df_all[df_all.topic.str.contains('semtech')]
df_tdoa = df_all[df_all.topic.str.contains('tdoa')]
df_rssi = df_all[df_all.topic.str.contains('rssi')]
df_fused = df_all[df_all.topic.str.contains('fused')]
df_kf = df_all[df_all.topic.str.contains('kf')]
'''

# evaluate error statistics numerically
mean_error_list = []
min_error_list = []
max_error_list = []

# filter the unique device_addresses in DB
dev_addr_list = df_kom.device_address.unique()
print('device_address:', df_kom.device_address)
print('################################### New Error Table ##########################################')
print('dev_addr_list:', dev_addr_list)

for dev_addr in dev_addr_list:
    try:
        device_name = df_kom[df_kom.device_address == dev_addr].device_name.unique()[0]
        print('device_name:', str(device_name))
        mean_toa_var_nsec, mean_snr_db, mean_rssi_var_dbm,  mean_error_tdoa, mean_error_rssi, mean_error_fused, mean_error_kf, mean_error = mean_dev_error(dev_addr, df_kom)
        min_toa_var_nsec, min_snr_db, min_rssi_var_dbm, min_error_tdoa, min_error_rssi, min_error_fused, min_error_kf, min_error = min_dev_error(dev_addr, df_kom)
        max_toa_var_nsec, max_snr_db, max_rssi_var_dbm, max_error_tdoa, max_error_rssi, max_error_fused, max_error_kf, max_error = max_dev_error(dev_addr, df_kom)
        min_error_list.append(min_error)
        max_error_list.append(max_error)
        mean_error_list.append(mean_error)
    except Exception as exception:
        print('exception:',exception)

print('min_error_list:', min_error_list)
print('max_error_list:', max_error_list)
print('mean_error_list:', mean_error_list)

# overall mean_new error
print('######################### Overall Statistics: New error dataset #########################')
print('min_of_min_error_list:', np.min(min_error_list))
print('max_of_max_error_list:', np.max(max_error_list))
print('mean_of_min_error_list:', np.mean(min_error_list))
print('mean_of_max_error_list:', np.mean(max_error_list))
print('mean_of_mean_error_list:', np.mean(mean_error_list))
print('var_of_mean_error_list:', np.var(mean_error_list))

########################## Statistics of Komro Methods ##########################
pd.options.display.width = 0

'''
print('Statistics of TDOA Method:', df_tdoa.describe())

print('Statistics of RSSI Method:', df_rssi.describe())

print('Statistics of Fused Method:', df_fused.describe())

print('Statistics of KF Method:', df_kf.describe())
'''
print('Statistics of Komro GRS:', df_kom.describe())

best_error_limit= 100
# to check the best geolocating devices in rosenheim (kom)
best_device_list_kom = df_kom[(df_kom.error_tdoa<best_error_limit)|(df_kom.error_rssi<best_error_limit)|(df_kom.error_fused<best_error_limit)|(df_kom.error_kf<best_error_limit)].device_name.unique()
print('kom_best_device_list (<'+str(best_error_limit)+'m):', best_device_list_kom)

print('Total no. of devices:', len(dev_addr_list))
print('No. of best devices:', len(best_device_list_kom))

'''
# to check the best geolocating devices in rosenheim (sem)
best_device_list_sem = df_sem[df_sem.mean_error<best_error_limit].device_name.unique()
print('sem_best_device_list (<'+str(best_error_limit)+'m):', best_device_list_sem)

# to check the best geolocating devices in rosenheim (tek)
best_device_list_tek = df_tek[df_tek.mean_error<best_error_limit].device_name.unique()
print('tek_best_device_list (<'+str(best_error_limit)+'m):', best_device_list_tek)
'''


# analyse device uncertainty statistics
# drop the unnecessary columns liks json, dict etc.
#df_tdoa = df_tdoa.drop(['num_of_gateways_used', 'mean_rssi_var_dbm', 'hdop'], 1)
# df_tdoa = df_tdoa.drop(['mean_rssi_var_dbm', 'mean_snr_db', 'mean_toa_var_nsec', 'mean_error'], 1)
df_kom = df_kom.drop(['mean_rssi_var_dbm'], 1)

# read the true location.CSV file
true_location_file_path = 'datasets/TrueLocations.csv'      # destination of truelocation.csv
df_trueloc = pd.read_csv(true_location_file_path, sep=';', encoding='latin-1', header= 'infer', engine='python')
device_addr_list = df_trueloc['Device Address'].tolist()
anayse_device_error(df_kom, dev_addr)

'''
########################### plot TDOA DF #########################
title= 'TDOA Error Dataframe'
file_name= 'TDOA_DF'
plot_df(df_tdoa, title, file_name)

########################### plot RSSI DF #########################
title= 'RSSI Error Dataframe'
file_name= 'RSSI_DF'
plot_df(df_rssi, title, file_name)

########################### plot Fused DF #########################
title= 'Fused Error Dataframe'
file_name= 'Fused_DF'
plot_df(df_fused, title, file_name)

########################### plot KF DF #########################
title= 'KF Error Dataframe'
file_name= 'KF_DF'
plot_df(df_kf, title, file_name)
'''
