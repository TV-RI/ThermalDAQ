from devices.Base import *
import serial
import time
import json


class FluxDAQ(Device):
    def __init__(self, port: str, DAQ_type: str, sensors: dict, baudrate: int = 9600,
                 sampling_time: int = 2, precheck_steps: int = 5, name: str = None):
        """
            By default, the keys are: q1, T1, q2, T2, ...
        """
        if DAQ_type not in ['COMPAQ', 'FluxDAQ+']:
            raise ValueError("Invalid DAQ type, must be 'COMPAQ' or 'FluxDAQ+'")
        
        name = name or DAQ_type
        super().__init__(name, sampling_time)

        # sensors = sorted(sensors, key=lambda x: int(x['id']))
        # sensor_ids = [int(sensor['id']) for sensor in sensors]
        num_sensors = len(sensors)
        assert num_sensors > 0, "The number of sensors must be greater than 0"
        sensor_ids = sorted([int(id) for id in sensors.keys()])
        # the sensor ids must be within range 1-4
        assert sensor_ids[0] >= 1 and sensor_ids[-1] <= 4, "Sensor IDs must be between 1 and 4"
        report_num_sensors = sensor_ids[-1]

        self.serial_port = port
        self.DAQ_type = DAQ_type
        self.num_sensors = num_sensors
        self.sensor_ids = sensor_ids
        self.report_num_sensors = report_num_sensors
        self.baudrate = baudrate

        self.active_ports = [False] * 2 * report_num_sensors
        self.s_list = [float('inf')] * report_num_sensors
        self.header = []

        for id in range(1, report_num_sensors+1):
            if id in sensor_ids:
                sensor = sensors[str(id)]
                if not sensor: raise ValueError(f"Missing infomation at sensor {id}; if {id} is not used, remove it from 'sensors' in config file")
                if sensor['q']:
                    if sensor['s_value'] is None or sensor['s_value'] <= 0:
                        raise ValueError(f"Sensor {sensor['id']}: s_value must be greater than 0 for enabled sensors")
                    self.s_list[id-1] = sensor['s_value']
                    self.header.append(f'q{id}')
                    self.active_ports[2 * (id - 1)] = True 
                self.header.append(f'T{id}')
                self.active_ports[2 * (id - 1) + 1] = True

        # initialize the serial port
        if self.DAQ_type == 'FluxDAQ+':
            self.ser = serial.Serial(self.serial_port, self.baudrate, timeout=0.01, rtscts=True)
            time.sleep(1)
            self.ser.write(b'1')
        elif self.DAQ_type == 'COMPAQ':
            # It seems that COMPAQ doesn't support rts/cts
            self.ser = serial.Serial(self.serial_port, self.baudrate, timeout=0.01)
        time.sleep(2)
        
        print(f"Write in number of sensors: {self.report_num_sensors}")
        if num_sensors < self.report_num_sensors:
            print(f"though only {num_sensors} of ports are active, id: {sensor_ids}")
        self.ser.write(f'{self.report_num_sensors}'.encode())
        # print(f'{self.report_num_sensors}'.encode())
        time.sleep(2)

        print(f"Write in s values (1-{report_num_sensors}): {self.s_list}")

        for s in self.s_list:
            self.ser.write(f'{s}'.encode())
            # s_bytes = bytes(map(ord,str(s))) # alternative
            # self.ser.write(s_bytes)
            time.sleep(1)
        
        time.sleep(1)
        print('Run Precheck...')
        self.precheck(precheck_steps)
        print("FluxDAQ at ", self.serial_port, " is successfully initialized \n")

    def precheck(self, precheck_steps: int):
        # criteria: 80% of steps have data received
        received_data = 0
        data_lst = []
        for step in tqdm(range(precheck_steps)):
            if self.ser.inWaiting() > 0:
                try:
                    output_str = self.ser.readline().decode()
                    # print(output_str)
                    if len(output_str.split(',')) == self.report_num_sensors*2:
                        output_data = [float(val) for i, val in enumerate(output_str.split(',')) if self.active_ports[i]]
                        received_data += 1
                        data_lst.append(output_data)
                except:
                    continue
            time.sleep(self.sampling_time)
        
        if received_data / precheck_steps < 0.8:
            raise ValueError(f"FluxDAQ @ {self.serial_port} is not responding properly ({received_data}/{precheck_steps})")
        else:
            print(f"FluxDAQ is responding properly ({received_data}/{precheck_steps}), output data: ")
            header_str = "   |   ".join(self.header)
            print("|   " + header_str + "   |")
            print("|   " + "-" * len(header_str) + "   |") 
            for row in data_lst:
                formatted_row = " | ".join([f"{float(val):6.2f}" for i, val in enumerate(row)])
                print("| " + formatted_row + " |")
            
    def read_data(self):
        # TODO: check if collected data is correct/clean
        output_str = self.ser.readline().decode()
        if len(output_str.split(',')) != self.report_num_sensors*2:
            return None
        output_data = []
        for i, val in enumerate(output_str.split(',')):
            if not self.active_ports[i]:
                continue
            try:
                output_data.append(float(val))
            except ValueError:
                output_data.append(float('nan'))
        time.sleep(self.sampling_time)
        return output_data

if __name__ == "__main__":
    config = 'config_FLUX_test.json'
    with open(config, 'r') as f:
        config = json.load(f)
    
    device_config = config['devices'][0]
    fluxdaq = FluxDAQ(device_config['port'], device_config['DAQ_type'], device_config['sensors'], device_config['baudrate'],
                      device_config['sampling_time'], device_config['precheck_steps'])
    
    while True:
        data = fluxdaq.read_data()
        print(data)
