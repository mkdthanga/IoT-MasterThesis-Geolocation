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

def create_db():
    """ Connect to the PostgreSQL database server """
    connection = None
    try:
        # declare a new PostgreSQL connection json_payload
        connection = connect(
            dbname="postgres",
            user="postgres",
            host=postgres_host,
            port=postgres_port,
            password=postgres_password
        )

        # json_payload type: psycopg2.extensions.connection
        print("\ntype(conn):", type(connection))
        # get the isolation level for autocommit
        autocommit = extensions.ISOLATION_LEVEL_AUTOCOMMIT
        print("ISOLATION_LEVEL_AUTOCOMMIT:", extensions.ISOLATION_LEVEL_AUTOCOMMIT)

        """
        ISOLATION LEVELS for psycopg2
        0 = READ UNCOMMITTED
        1 = READ COMMITTED
        2 = REPEATABLE READ
        3 = SERIALIZABLE
        4 = DEFAULT
        """

        # set the isolation level for the connection's cursors
        # will raise ActiveSqlTransaction exception otherwise
        connection.set_isolation_level(autocommit)

        # instantiate a cursor json_payload from the connection
        cursor = connection.cursor()

        # use the execute() method to make a SQL request
        # cursor.execute('CREATE DATABASE ' + str(DB_NAME))

        # use the sql module instead to avoid SQL injection attacks
        cursor.execute(sql.SQL(
            "CREATE DATABASE {}"
        ).format(sql.Identifier(DB_NAME)))
        print(str(DB_NAME)+' created successfully')
        # close the cursor to avoid memory leaks
        cursor.close()
        # close the connection to avoid memory leaks
        connection.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)

def create_table():
    """ create tables in the PostgreSQL database"""
    commands = (
        '''
        CREATE TABLE if not exists geoloc_packets(
                id SERIAL PRIMARY KEY,
                "time" timestamp ,
                device_address character varying ,
                frame_cnt character varying ,
                frequency_hz character varying ,
                bandwidth_hz character varying ,
                sf character varying ,
                antenna character varying ,
                toa_sec character varying ,
                toa_nsec character varying ,
                rssi_dbm character varying ,
                snr_db character varying ,
                fo_hz character varying ,
                toa_u_nsec character varying ,
                fo_u_hz character varying ,
                gateway_latitude character varying ,
                gateway_longitude character varying ,
                gateway_altitude character varying ,
                gateway_id character varying(255) ,
                mic character varying
            )
        ''',
        '''
        CREATE TABLE if not exists geoloc_results(
                id SERIAL PRIMARY KEY,
                "time" timestamp,
                topic character varying,
                device_address character varying,
                device_name character varying,
                num_Of_Gateways_Used numeric,
                num_Of_UL_Packets_Used numeric,
                latitude_tdoa numeric, 
                longitude_tdoa numeric,
                latitude_rssi numeric, 
                longitude_rssi numeric,
                latitude_fused numeric, 
                longitude_fused numeric,
                latitude_kf numeric, 
                longitude_kf numeric,
                latitude_kfs numeric, 
                longitude_kfs numeric,
                latitude_true numeric,
                longitude_true numeric,
                error_tdoa numeric, 
                error_rssi numeric, 
                error_fused numeric, 
                error_kf numeric, 
                error_kfs numeric,
                HDOP numeric,
                mean_snr_db numeric,
                mean_rssi_var_dbm numeric,
                mean_toa_var_nsec numeric,
                payloads json 
            )
        ''',
        '''
        CREATE TABLE if not exists miscellaneous(
                id SERIAL PRIMARY KEY,
                "time" timestamp,
                topic character varying,
                device_address character varying,
                payloads json 
            )
        '''
    )
    conn = None
    try:
        # connect to the PostgreSQL server
        conn = psycopg2.connect(user='postgres',
                              host=postgres_host,
                              port=postgres_port,
                              password=postgres_password,
                              database=DB_NAME)
        cur = conn.cursor()
        # create table one by one
        for command in commands:
            cur.execute(command)
        # close communication with the PostgreSQL database server
        cur.close()
        # commit the changes
        conn.commit()
        print('Above tables are created and commited in '+str(DB_NAME))
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)

# Set up a client for connecting to Postgresql DB
create_db()
create_table()
