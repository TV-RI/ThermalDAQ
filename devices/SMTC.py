"""
    This module is specifically designed to interface with the Sequence Microsystems Thermocouple (SMTC) DAQ devices,
    connected via a Raspberry Pi. It allows for reading data from multiple thermocouple sensors.
    To run this module, ensure that the `smtc` command-line tool is installed and accessible in your system's PATH.
        https://github.com/SequentMicrosystems/smtc-rpi/tree/main
"""
from devices.Base import *
import time
import subprocess

# Sensor types:
# [0..7] -> [B, E, J, K, N, R, S, T]
_sensor_types = {
    'B': 0,
    'E': 1,
    'J': 2,
    'K': 3,
    'N': 4,
    'R': 5,
    'S': 6,
    'T': 7
}


class TCHAT(Device):
    def __init__(self, stack: int, sensors: dict, sampling_time: int = 2, name: str = None):
        """
        Thermocouples DAQ (type J, K, T, N, E, B, R and S)
        8 ports in each DAQ, stackable -> 8 DAQs
        - precheck: check the voltages (0: likely open circuit)
        - read: heat flux (coeff * mV) and temperatures (direct)
        """
        # no need on serial, connected to raspi by default
        # stack level: 0..7
        # input channel number: 1..8

        # check if command is available
        try:
            subprocess.run(['smtc', '-h'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except FileNotFoundError as e:
            print("SMTC command not found. Please ensure SMTC is installed and in your PATH.")
            exit(1)

        # check if the stack is valid
        assert stack >= 0 and stack <= 7, "stack must be between 0 and 7"
        stack_info = subprocess.run(['smtc', '-list'], stdout=subprocess.PIPE)
        stack_info = stack_info.stdout.decode('utf-8').rstrip('\n').split('\n')[1].split(' ')[1:]
        assert str(stack) in stack_info, f"stack {stack} is not available, available stacks: {stack_info}"
        
        name = name or f'TCHAT{stack}'
        super().__init__(name, sampling_time)
        
        # check if the sensor channels are valid
        num_sensors = len(sensors)
        assert num_sensors > 0, "The number of sensors must be greater than 0"
        sensor_ids = sorted([int(id) for id in sensors.keys()])
        # the sensor ids must be within range 1-8
        assert sensor_ids[0] >= 1 and sensor_ids[-1] <= 8, "Sensor IDs must be between 1 and 4"

        self.address = str(stack)
        self.num_sensors = num_sensors
        self.sensor_ids = sensor_ids
        self.sensors2read = {}
        self.header = []

        # configure sensors type
        for k, v in sensors.items():
            k = str(k)
            sensor_type = v.get('type', 'K')
            if sensor_type not in _sensor_types:
                raise ValueError(f"Invalid sensor type {sensor_type}, must be one of {_sensor_types.keys()}")
            # set sensor type
            subprocess.run(['smtc', self.address, 'stypewr', k, str(_sensor_types[sensor_type])], stdout=subprocess.PIPE)
            if v.get('q', False):
                if v['s_value'] is None or v['s_value'] <= 0:
                    raise ValueError(f"Sensor {k}: s_value must be greater than 0 for enabled sensors")
                coeff = 1000 / v['s_value']
                cmd = 'readmv'
                self.header.append(f'q{k}@TCHAT{self.address}')
            else:
                coeff = 1
                cmd = 'read'
                self.header.append(f'T{k}@TCHAT{self.address}')
            self.sensors2read[k] = {
                'cmd': cmd,
                'coeff': coeff
            }
        
        print('Run Precheck...')
        self.precheck()
        print(f"TCDAQ at {self.address} is successfully initialized \n")

    def precheck(self):
        # check the connection of the sensors
        # The initialization of devices is done in for loop
        # thue can be paused for manual inspection
        for channel in self.sensor_ids:
            q_mV = subprocess.run(['smtc', self.address, 'readmv', str(channel)], stdout=subprocess.PIPE)
            q_mV = q_mV.stdout.decode('utf-8').rstrip('\n')
            if float(q_mV) == 0:
                # ask manual inspection: enter-to-continue. ctrl-c to stop
                try: 
                    input(f"0 mV at sensor {channel}, press click enter to continue after your inspection or ctrl-c to stop")
                except KeyboardInterrupt:
                    print("Precheck interrupted by user")
                    exit(1)
            else:
                print(f"Sensor {channel} is connected, voltage: {q_mV} mV")
            time.sleep(0.5)
    
    def read_data(self):
        # read the data 
        output_data = []
        for channel in self.sensor_ids:
            channel = str(channel)
            cmd = self.sensors2read[channel]['cmd']
            coeff = self.sensors2read[channel]['coeff']
            output = subprocess.run(['smtc', self.address, cmd, channel], stdout=subprocess.PIPE)
            output = output.stdout.decode('utf-8').rstrip('\n')
            output_data.append(float(output) * coeff)
        time.sleep(self.sampling_time)
        return output_data
        

if __name__ == "__main__":
    
    # Example usage
    sensors = {
        '1': { 'q': True, 's_value': 18.97},
        '3': { 'q': True, 's_value': 18.32},
        '2': { 'q': False, 's_value': None},
        '4': { 'q': False, 's_value': None},
        '5': {},
        '6': {},
        '7': {},
        '8': {},
        # Add more sensors as needed
    }
    stack = 0
    tchat = TCHAT(stack, sensors)
    while True:
        data = TCHAT.read_data()
        print(data)