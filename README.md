# ECHO Modules Delta

This folder contains a modified version of the ECHO Modules, updated to work with data fetched from Delta Lake using PySpark. 

## How to Use
### Running with Docker
This is for when you have Delta Lake set up on your local machine and you want to use them without using API services. 

1. Copy the example environment file:
    ```bash
    cp .env.example .env
    ```

2. Set up your `.env` file. If you are using the local tables, you need to set the `DELTA_TABLES_HOST_PATH` to the location of the Delta Tables on your machine. 

3. Build the Docker container:
   ```bash
   docker compose build
   ```
4. Start the container:
    ```bash
    docker compose up
    ```

This will start the services defined in the **echo-delta-compose.yaml** file which is the ECHO Modules app and any dependencies (e.g., Spark, Delta Lake, etc.). A bash script `startup.sh` runs on start of container which sets up the Spakr Session for use. A Jupyter Notebook server will also be launched, allowing you to run notebooks that utilize the ECHO_modules.

5. (Optional) To enter the container's shell:
    ```bash
    docker exec -it echo-modules bash
    ```

## Environment Variables
Add the following variables to a `.env` file for the application to run:

Variable | Description | Example
---------|-------------|--------
DELTA_TABLES_HOST_PATH | Path to the Delta tables on the host machine | /home/user/epa-data/delta-tables
DELTA_TABLES_MOUNT_PATH | Mount path inside the container for Delta tables | /opt/echo/epa-data/data-lake/files
WORK_DIR_HOST_PATH | Path to your working directory on the host machine | /home/user/ECHO_Modules_delta


## Notes
- Ensure that the paths defined in your .env file is accessible and correctly mounted within the container.