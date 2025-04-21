# ECHO Modules Delta

This folder contains a modified version of the ECHO Modules, updated to work with data fetched from Delta Lake using PySpark. 

## How to Use
You can use ECHO modules Delta in a Notebook setting like Jupyter Notebook.
Usage differs depending on if you want to access data through an api server or locally.

1. Set up the virtual environment

2. Activate the virtual environment

3. Run the command to install libraries used.
    ```bash
   pip install -r requirements.txt
   ```

4. Start the Jupyter Notebook Server to access the notebooks.
    ```bash
   jupyter lab
   ```

5. You can now use ECHO modules in the notebook.

### Accessing Data through API Server
1. You need to get an access token to access the API server. To get a token, connect your github account to the server as authentication. After authenticating, the server will return an access token that you will use for all function that require getting data. 

2. Set `api` parameter to **True** to indicate using server and `token` parameter to the value you received from server in all functions that access the delta tables.


Note: If you will be querying large datasets, we recommend that you set up the delta lake locally as the api server will not respond to queries that result in dataset size over the limit(~100mb).

### Accessing Data Locally
1. Set the **DELTA_LAKE_DIR_PATH** to the location of your delta tables on your machine in the `.env` file.

2. Simply use the functions to access data without setting `api` and `token` parameters. 

Note: You will need to install Apache Spark and Delta Lake on your machine for this option. Refer to the following articles for installation and set up:
- (https://phoenixnap.com/kb/install-spark-on-ubuntu)
- (https://docs.delta.io/latest/delta-intro.html)