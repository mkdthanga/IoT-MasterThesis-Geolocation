Instructions for Docker:
1. Clone the geolocation docker files from the Gitlab
2. Go to the directory: cd <cloned folder>
3. Build the docker image: docker build -t komrogrs .
4. Start the docker image just built in previous step as container: docker-compose up 

The subscriber_db.py, resolver.py and resolver_ecef.py are ready for geolocation estimation. 

Now, the resolver gives three results:
A. TDOA based Geolocation estimate
B. RSSI based Geolocation estimate
C. Fusion of both the TDOA & RSSI results (50% of both)
However, these algorithms could be improved over time based on experience and learnings. 
Even the Tektelic geolocation resolver is not so accurate. 
Needs GW placement tuning or LoRa Parameter tuning!!
For each ULs, it estimates different position eventhough the device was stationary.

1. subscriber_db.py will subscribe geoloca frames from geoloc host and store them on local postgresql DB
under 'geoloc_packets' table. Additionally, it creates another table called 'geoloc_results'for storing 
the resolved geolocations from resolver.py

2. gui_resolver.py is GUI resolver, plots graph for every geo-estimation, 
therefore needs to matplotlib.py & multilaterate.py libraries!

3. resolver.py is headless resolver, which estimate geolocation and publishes the results on various topics 
according to device address & localization method used.

4. resolver_ecef.py is similar to resolver.py but includes altitude estimation & dilution of precision (DOP) 
calculation using different co-ordinate system called ECEF.

5. gui_resolver_ecef.py is similar to gui_resolver.py but includes altitude estimation & dilution of precision 
(DOP) calculation using different co-ordinate system called ECEF.

6. test_dop_ecef.py is a sample/test script which calculates DOP for 5 gateways & a sensor!!

7. multilaterate.py is a library used for plotting hyperbola!
###########################################################################################################

# Topics on which the geolocation results are published

Device_address: geolocation/device_list

TDOA_geolocation: geolocation/tdoaposition_gps/$(device_addr)

RSSI_geolocation: geolocation/rssiposition_gps/$(device_addr) 

FUSED_geolocation: geolocation/fusedposition_gps/$(device_addr)

TDOA_geolocation_error: geolocation/error/tdoa/$(device_addr)

RSSI_geolocation_error: geolocation/error/rssi/$(device_addr)

FUSED_geolocation_error: geolocation/error/fused/$(device_addr)

###########################################################################################################

8. Before building the docker image or executing headless script one should check/ enter the 
updated 'A' & 'n' values along with other user inputs such as device_address, filter modes, 
framegroup_index(which is randome seed), num_of_frames, bcalculatedTOA, split_date

###########################################################################################################

# User Inputs:
Device Address     -    device address assigned by network server (zB. 0167f446)
Num of UL Frames   -    no. of frames to be passed for geolocation estimation (zB. 4...10)
Filter Multi-frame?-    If you need to filter last three UL frame groups, then set it to '1', otherwise set to '0'
Calculate TOA      -    Just for simulation (hyperbola) Given the True location of a device,
                        calculate TOA instead of using the real-time geoloc frames(boolean zB. 0 or 1)
Filter Mode        -    Essential parameter, it is used to choose one of the following data filter modes
Plot Hyperbola     -    Just for checking whether the TOA uncertainties are large using known true 
			location(boolena zB. 0 or 1)
split_date         -    If you choose filter mode 3, then one should pass this parameter for
                        splitting the dataframe from that particular date till the latest frame
A                  - 	Absolute RSSI value for 1 meter (in dBm)
n                  -    RSSI Pathloss exponent or environment coefficient


# Data Filter modes (of geoloc data frames)
# This program estimates the position in different filter four modes such as:
0- filter based on number of frames                 -> Num of UL Frames  should be specified
1- filter based on time delta (time interval)       -> no required parameters/args
2- filter based on framecount                       -> Should specify Random number(seed) as an Index for unique UL frame count group (i.e. Unique FCntUp)
3- filter based on constant date/time string
   (filter geoloc data after certain date/time)     -> Should specify a date/time  from which we need to construct a dataframe and estimate geolocation

# User Input Example:
#automatic device_address extraction
device_addr_list = query_device_addr()
or
#manual
device_addr_list = ['b18577', 'd57530', '1f3f60', '12fd3ac', 'e648ab', '1d5d7f4',
			        '16df31a', 'bafd16','15cbbbf', '72cd7f','1105324', 'd181d2']
A = 2
n = -116
filter_mode = 0
bmulti_frame = 1        # if set to 1, multiple ULs will be passed to resolver function!(boolean)
num_of_frames = 10
bcalculatedTOA = 0
split_date = datetime(2020, 5, 7)

###########################################################################################################



