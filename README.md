
##
This code is designed for thermal data collection from devices:
- FLUXDAQ: COMPAQ, FluxDAQ+
- SM Thermocouple DAQ 

## 
Before running, execute the following command to install the required packages:
```
pip install -r requirements.txt
```

## 
In **config.json**, each device can define its own configuration, following the specific format. For example, each device can define its own sampling time individually.

The writing time is separated from the reading time. The writing time is the time that the program takes to write the data to the data file. It's recommended to set the writing time bigger than the maximum of sampling time of all devices. The mechanism of the program is to read the data from all devices at the same time, and then write the average of the data in the memory to the data file. If there's no data from a device in the memory, the program will write the last data of that device to the data file.