from dotenv import load_dotenv
load_dotenv()

import pdb
import geopandas
import os
import urllib.parse
import pandas as pd
import json
import requests


DELTA_TABLES_DIR = os.environ.get('DELTA_TABLES_MOUNT_PATH')
API_SERVER = "https://portal.gss.stonybrook.edu/api"

def get_echo_data( sql, index_field=None, table_name=None ):
    '''
    This is the global function that can run an SQL query against
    the database and return the resulting Pandas DataFrame.

    Parameters
    ----------
    sql : str
        The SQL query to run
    index_field : str
        The field in the result set to set as the Dataframe's index

    Results
    -------
    Dataframe
        The results of the database query
    '''    
    url= 'https://portal.gss.stonybrook.edu/echoepa/?query=' #'http://apps.tlt.stonybrook.edu/echoepa/?query=' 
    data_location=url+urllib.parse.quote_plus(sql) + '&pg'
    # print( sql )
    # print( data_location )
    # pdb.set_trace()
    if ( index_field == "REGISTRY_ID" ):
        ds = pd.read_csv(data_location,encoding='iso-8859-1', 
                 dtype={"REGISTRY_ID": "Int64"})
    else:
        ds = pd.read_csv(data_location,encoding='iso-8859-1')
    if ( index_field is not None ):
        try:
            ds.set_index( index_field, inplace=True)
        except (KeyError, pd.errors.EmptyDataError):
            pass
    # print( "get_data() returning {} records.".format( len(ds) ))
    if (table_name is not None):
        try:
            lm_sql = 'select modified from "Last-Modified" where "name" = \'{}\''.format(table_name)
            lm_data_location=url+urllib.parse.quote_plus(lm_sql) + '&pg'
            lm_ds = pd.read_csv(lm_data_location,encoding='iso-8859-1')
            last_modified = lm_ds.modified[0]
            print("Data last updated: " + last_modified) # Print the last modified date for each file we get 
        except:
            print("Data last updated: Unknown")
    
    return ds

def spatial_selector(units):
    '''
    helper function for `get_spatial_data`
    helps parse out multiple inputs into a SQL format
    e.g. takes a list ["AL", "AK", "AR"] and returns the string ("AL", "AK", "AR")
    '''
    selection = '('
    if (type(units) == list):
      for place in units:
          selection += '\''+str(place)+'\', '
      selection = selection[:-2] # remove trailing comma
      selection += ')'
    else:
      selection = '(\''+str(units)+'\')'
    return selection

def get_huc8_by_states(state_codes, json_file="data/state_huc8_map.json"):
    """
    Returns a combined list of HUC8 codes for the given list of state codes from the JSON mapping file.
    
    Parameters:
        state_codes (list): A list of state abbreviations (e.g., ['NY', 'NJ']).
        json_file (str): The path to the JSON file containing the state-to-HUC8 mapping.
    
    Returns:
        list: A sorted list of unique HUC8 codes associated with the given state codes.
              Returns an empty list if none of the state codes are found.
    """
    try:
        with open(json_file, "r") as f:
            state_huc8_map = json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{json_file}' not found.")
        return []
    
    # Use a set to avoid duplicate HUC8 codes.
    combined_huc8 = set()
    for state in state_codes:
        # Retrieve HUC8 codes for this state, if present.
        codes = state_huc8_map.get(state, [])
        combined_huc8.update(codes)
    
    # Return a sorted list of HUC8 codes.
    return sorted(list(combined_huc8))

def state_abbr_to_fips(state_abbrs):
    data_dict = {
        "AL": "01","AK": "02","AZ": "04","AR": "05","CA": "06","CO": "08","CT": "09","DE": "10","DC": "11","FL": "12",
        "GA": "13","HI": "15","ID": "16","IL": "17","IN": "18","IA": "19","KS": "20","KY": "21","LA": "22","ME": "23",
        "MD": "24","MA": "25","MI": "26","MN": "27","MS": "28","MO": "29","MT": "30","NE": "31","NV": "32","NH": "33",
        "NJ": "34","NM": "35","NY": "36","NC": "37","ND": "38","OH": "39","OK": "40","OR": "41","PA": "42","RI": "44",
        "SC": "45","SD": "46","TN": "47","TX": "48","UT": "49","VT": "50","VA": "51","WA": "53","WV": "54","WI": "55",
        "WY": "56","AS": "60","GU": "66","MP": "69","PR": "72","VI": "78"
    }
    fips_codes = []
    for abbr in state_abbrs:
        # Check if the abbreviation is in the data dictionary's keys
        if abbr in data_dict:
            fips_codes.append(data_dict[abbr]) # Append the corresponding FIPS code
        else:
            return None  # State abbreviation not found
    return fips_codes

def get_spatial_data(region_type, states, spatial_tables, fips=None, region_filter=None):
    '''
    Returns spatial data from the database utilizing an intersection query 

    Parameters
    ----------
    region_type : str
        The spatial unit to return e.g. "Congressional District" # from cell 3 region_type_widget
    states : list
        The extent across which to get the spatial data e.g. ["AL"]
    spatial_tables : dict
        Import from ECHO_modules/geographies.py
    fips : dict
        Optional - Import from ECHO_modules/geographies.py for Census Tracts
    region_filter : str
        Optional - specify whether to return a single unit (e.g. a specific county - "Erie"). region_filter should be based on the id_field specified in spatial_tables

    Returns
    -------
    regions_gdf
        GeoDataFrame of the spatial units
    states_gdf
        GeoDataFrame of the state(s) across which the units are selected
    
    '''
    '''

    spatial_tables is from ECHO_modules/geographies.py
    
    
    '''

    def get_tiger_geojson(query_string, geography_flag):
        """
        Retrieve GeoJSON data for counties in a given state using its FIPS code.
        
        Parameters:
            state_fips (str): The FIPS code for the state (e.g., "06" for California)
            geography (int): 0 for state, 1 for county 
        Returns:
            dict: GeoJSON data as a Python dictionary, or None if the request fails.
        """
        import requests
        # See the TIGERweb REST Services page: https://tigerweb.geo.census.gov/tigerwebmain/TIGERweb_restmapservice.html
        # base_url[0]: States (or statistically equivalent entities); 2020 Census - January 1, 2020 vintage; Generalized; 500K
        # base_url[1]: Counties (or statistically equivalent entities); 2020 Census - January 1, 2020 vintage; Generalized; 500K
        # base_url[1]: ZIP Code Tabulation Areas; 2020 Census - January 1, 2020 vintage; Generalized; 500K
        base_url = [
            "https://tigerweb.geo.census.gov/arcgis/rest/services/Generalized_TAB2020/State_County/MapServer/7/query",
            "https://tigerweb.geo.census.gov/arcgis/rest/services/Generalized_TAB2020/State_County/MapServer/11/query"
        ]
        params = {
            "where": f"{query_string}",  # Filter by state FIPS code
            "outFields": "*",                  # Retrieve all available fields
            "f": "geojson"                     # Return format as GeoJSON
        }
        # The timeout parameter may be necessary 
        response = requests.get(base_url[geography_flag], params=params, timeout=3)
        if response.status_code == 200:
            print("Success: retrieved the TIGER geojson!")
            return response.json()
        else:
            print("Error retrieving data. Status code:", response.status_code)
            return None

    def get_watershed_geojson(query_string):
        """
        Returns:
            dict: GeoJSON data as a Python dictionary, or None if the request fails.
        """
        import requests
        # See the USGS REST Services page: https://apps.nationalmap.gov/services/
        base_url = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/4/query"
        params = {
            "where": f"{query_string}",  # Filter by state FIPS code
            "outFields": "*",                  # Retrieve all available fields
            "geometryPrecision": "4",          # This parameter helps to retrieve less amount of data
            "f": "geojson"                     # Return format as GeoJSON
        }
        # somehow, the timeout parameter is necessary 
        response = requests.get(base_url, params=params)
        #print(response.url) # for debugging
        if response.status_code == 200:
            print("Success: retrieved the watershed geojson!")
            return response.json()
        else:
            print("Error retrieving data. Status code:", response.status_code)
            return None

    def get_zipcode_geojson(query_string):
        """
        Returns:
            dict: GeoJSON data as a Python dictionary, or None if the request fails.
        """
        import requests
        # Esri Living Atlas US Zip Code Boundaries: https://www.arcgis.com/home/item.html?id=5f31109b46d541da86119bd4cf213848
        base_url = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Boundaries_2023/FeatureServer/3/query"
        params = {
            "where": f"{query_string}",  # Filter by state FIPS code
            "outFields": "*",                  # Retrieve all available fields
            #"geometryPrecision": "4",          # This parameter helps to retrieve less amount of data
            "f": "geojson"                     # Return format as GeoJSON
        }
        # somehow, the timeout parameter is necessary 
        response = requests.get(base_url, params=params, timeout=3)
        if response.status_code == 200:
            print("Success: retrieved the US Zip Code geojson!")
            return response.json()
        else:
            print("Error retrieving data. Status code:", response.status_code)
            return None

    def retrieve(geojson_data):
        result = geopandas.GeoDataFrame.from_features(geojson_data['features'])
        # Set the CRS to EPSG:4326 (WGS 84) - a common standard for geographic coordinates
        result = result.set_crs("EPSG:4326") # Add this line to set the CRS
        return result

    #print("region_type ==>", region_type)
    #print("states ==>", states)
    #print("region_filter ==>", region_filter)

    state_fips = state_abbr_to_fips(states)
    states_tiger_str = spatial_selector(state_fips) # for the tigerweb rest api, e.g., ("36","39")
    states_str = spatial_selector(states) # for other rest api, e.g., ("NY","OH") 

    # Get the regions of interest (watersheds, zips, etc.) based on their intersection with the state(s)
    if (region_type == "Census Tract"):
      # Get all census tracts for this state
      # Which state is it? FIPS look up
      f = fips[states[0]] #assuming just one state for the time being
      #print(f) # Debugging
      # Get tracts
      import requests, zipfile, io
      url = "https://www2.census.gov/geo/tiger/TIGER2010/TRACT/2010/tl_2010_"+f+"_tract10.zip"
      r = requests.get(url)
      z = zipfile.ZipFile(io.BytesIO(r.content))
      z.extractall("/content")
      regions_gdf = geopandas.read_file("/content/tl_2010_"+f+"_tract10.shp")
      regions_gdf.columns = regions_gdf.columns.str.lower() #convert columns to lowercase for consistency

    elif (region_type == "County"):
      query_string = "STATE IN " + states_tiger_str 
      if region_filter:
        region_filter = spatial_selector(region_filter)
        query_string += " AND BASENAME IN " + region_filter

      #print("the query_string is:", query_string)
      geojson_data = get_tiger_geojson(query_string, 1)
      if geojson_data:
          print("Creating a geopandas dataframe ...")
          regions_gdf = retrieve(geojson_data)

    elif (region_type == "Watershed"):
      huc8_codes = get_huc8_by_states(states)
      huc8_filter = spatial_selector(huc8_codes)
      query_string = "huc8 IN " + huc8_filter 
      if region_filter:
        region_filter = spatial_selector(region_filter)
        query_string = "huc8 IN " + region_filter

      geojson_data = get_watershed_geojson(query_string)
      if geojson_data:
          print("Creating a geopandas dataframe ...")
          regions_gdf = retrieve(geojson_data)

    elif (region_type == "Zip Code"):
      query_string = "STATE IN " + states_str 
      if region_filter:
        region_filter = spatial_selector(region_filter)
        query_string += " AND ZIP_CODE IN " + region_filter

      geojson_data = get_zipcode_geojson(query_string)
      if geojson_data:
          print("Creating a geopandas dataframe ...")
          regions_gdf = retrieve(geojson_data)

    else: 
      print("ERROR: No spatial data was retrieved!") # Debugging
      regions_gdf = geopandas.GeoDataFrame(crs="EPSG:4326") # creating an empty GeoDataFrame 

    # Get the intersecting geo (i.e. states)
    if states == "":
        states_gdf = geopandas.GeoDataFrame(crs="EPSG:4326") # creating an empty GeoDataFrame 
    else:
        query_string = "STUSAB IN " + states_str
        geojson_data = get_tiger_geojson(query_string, 0)
        print("Creating a geopandas dataframe ...")
        states_gdf = retrieve(geojson_data) 

    return regions_gdf, states_gdf

# Read stored data from a file rather than go to the database.
def read_file( base, type, state, region ):
    '''
    Read stored data from a  file in the CSVs directory, rather
    than the database.  (TBD: This should check the last_modified,
    perhaps against a timestamp on the file name, to verify that
    the file holds the latest data.)

    Parameters
    ----------
    base : str
        The base filename
    type : {'State','County','Congressional District','Zipcode'}
        The region type
    state : str
        The state two-letter abbreviation
    region : str or int
        The region

    Returns
    -------
    Dataframe or None
        The resulting data, if found
    '''

    if ( not os.path.exists( 'CSVs' )):
        return None
    filename = 'CSVs/' + base
    if ( type != 'Zip Code' ):
        filename += '-' + state
    filename += '-' + type
    if ( region is not None ):
        filename += '-' + str(region)
    filename += '.csv'
    program_data = None
    try:
        f = open( filename )
        f.close()
        program_data = pd.read_csv( filename )
    except FileNotFoundError:
        pass
    return program_data


from pyspark.sql import SparkSession
from delta import *

def get_echo_data_delta(sql, index_field=None, table_name=None, api=False, token=None):
    try:
        # Use the API if the api flag is set to True
        if api and token:
            return get_echo_data_delta_api(sql, index_field, table_name, token=token)
        elif api and not token:
            raise ValueError(
                "Authentication required\n"
                f"Run get token cell to get token"
            ) from None  # Cleaner traceback
        
        # Initialize Spark session
        builder = SparkSession.builder \
            .master("local[*]") \
            .appName("DeltaLakeQuery") \
            .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
            .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        
        spark = configure_spark_with_delta_pip(builder).getOrCreate()

        # Read the Delta table into a DataFrame
        if not table_name:
            table_name = "ECHO_EXPORTER"
            
        print(table_name)
        # the following loads the delta lake table in the local file system. 
        # We should replace it whith the environemnt variable (in the .env file).
        # Ideally, 
        df = spark.read.format("delta").load(os.path.join(DELTA_TABLES_DIR, table_name))
        df.createOrReplaceTempView(table_name)
        result_df = spark.sql(sql)

        # Convert spark dataframe to pandas dataframe
        pd_df = result_df.toPandas()
        
        if (index_field == "REGISTRY_ID"):
            # Set REGISTRY_ID as index
            pd_df = pd_df.set_index("REGISTRY_ID")

        if ( index_field is not None ):
            try:
                pd_df.set_index( index_field, inplace=True)
            except (KeyError, pd.errors.EmptyDataError):
                pass
        if (table_name is not None):
            try:
                print("table name:" ,table_name)
                # df = spark.read.format("delta").load(f'/opt/spark/epa-data/data-lake/files/{table_name}')
                # df.createOrReplaceTempView(table_name)
                # result_df = spark.sql(sql)

                # print("Data last updated: " + last_modified) # Print the last modified date for each file we get
                
            except:
                print("Data last updated: Unknown")

        # Print the updated Pandas DataFrame
        return pd_df
    except Exception as e:
        print(f"Error: {e}")
        return None

import requests
from tqdm import tqdm

def get_echo_data_delta_api(sql, index_field=None, table_name=None, token=None, backoff_factor=2, retries=5):
    
    # Read the Delta table into a DataFrame
    if not table_name:
        table_name = "ECHO_EXPORTER"
        
    print(table_name)
   
    params = {
    "sql": sql
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
    }
    
    output_file = f"{table_name.lower()}_data.json"

    attempt = 0
    while attempt < retries:
        try:
            response = requests.get(f"{API_SERVER}/echo/{table_name}", params=params, headers=headers, stream=True)
            content_disposition = response.headers.get('Content-Disposition')
            
            # Set filename from Content-Disposition header if available
            if content_disposition:
                parts = content_disposition.split(';')
                for part in parts:
                    if "filename=" in part:
                        output_file = part.split('=')[1].strip().strip('"')
            if response.status_code == 200:
                print("200 OK: Data retrieved successfully.")
                
                chunk_size = 8192
                total_size = int(response.headers.get('content-length', 0))

                with open(output_file, 'wb') as f, tqdm(
                    desc=output_file,
                    total=total_size,
                    unit='iB',
                    unit_scale=True,
                    unit_divisor=1024,
                ) as bar:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        f.write(chunk)
                        bar.update(len(chunk))
    
                print(f"✅ Downloaded to: {os.path.abspath(output_file)}")
                break
            elif response.status_code == 403:
                print("403 Forbidden: You can only use SELECT statements.")
                return pd.DataFrame()  # Return empty DataFrame on failure
            elif response.status_code == 429:
                wait_time = backoff_factor ** attempt
                print(f"429 Too Many Requests: Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                attempt += 1
                continue
            else:
                response.raise_for_status()

        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return pd.DataFrame()  # Return empty DataFrame on failure
    else:
        print("Max retries exceeded.")
        return pd.DataFrame()
    
    print("Reading data...")
    
    # Load json string to JSON and convert it to pandas dataframe
    try:
        json_data = json.load(open(output_file))
    except json.JSONDecodeError as e:
        print(f"JSON decoding failed: {e}")
        return pd.DataFrame()
    
    pd_df = pd.DataFrame(json_data)
     
    if (index_field == "REGISTRY_ID"):
        # Set REGISTRY_ID as index
        pd_df = pd_df.set_index("REGISTRY_ID")

    if ( index_field is not None ):
        try:
            pd_df.set_index( index_field, inplace=True)
        except (KeyError, pd.errors.EmptyDataError):
            pass
    # if (table_name is not None):
    #     try:
    #         print("table name:" ,table_name)
    #         # df = spark.read.format("delta").load(f'/opt/spark/epa-data/data-lake/files/{table_name}')
    #         # df.createOrReplaceTempView(table_name)
    #         # result_df = spark.sql(sql)

    #         # print("Data last updated: " + last_modified) # Print the last modified date for each file we get
             
    #     except:
    #         print("Data last updated: Unknown")

    # Print the updated Pandas DataFrame
    return pd_df

def get_echo_api_access_token():
    from IPython.display import display, HTML
    
    display(HTML(f'<a href="{API_SERVER}/github-auth">Get Token</a>'))

    # Manually paste token
    token = input("Paste your token: ")

    # Use token
    response = requests.get(
        f"{API_SERVER}",
        headers={"Authorization": f"Bearer {token}"}
    )
    print(response.json())
    if response.status_code != 200:
        print("Failed to authenticate. Please check your token.")
        return None
    return token


def try_test():
    print('hellooo')