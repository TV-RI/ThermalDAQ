from devices.Base import *
import serial
import numpy as np
from typing import List, Dict
import threading
import time
import json

_error_codes = {
    0: "Invalid module",
    1: "Command executed properly",
    2: "Invalid parameter",
    3: "Command is forbidden",
    4: "Parameter out of range",
    5: "Unknown error",
    6: "Format error",
    7: "Verification error",
    8: "Save executed properly",
}

def extract_error_code(output_str: str) -> int:
    if output_str.startswith("CMD:"):
        # error code is single digit after '='
        error_code = int(output_str.split('=')[1][0])
        return error_code

class TCM(Device):
    def __init__(self, port: str, baudrate: int = 57600, num_devices: int = None,
                 read_keys: List[str] = [], name: str = None,
                 write=False, write_keys: List[str] = [], write_vals: List = [],
                 cmd_gap: int = 0.075, sampling_time: int = 2):
        """
            TCM class for reading data from and writing data to TCM devices.
            - The TCM devices are connected to the computer via a serial port.
            - Multiple TCM devices can be communicated but the address numbers must be unique,
              and specified in the read keys.
            - TCM read data by default; if write is True, it will provide writing functions.
            -- write_keys: list of keys to write to the devices, must be specified if write is True
            -- write_keys will be added to the header to be read
        """

        name = name or "TCM"
        super().__init__(name, sampling_time)
        
        self.serial_port = port
        self.baudrate = baudrate
        self.num_devices = num_devices
        self.ser = serial.Serial(self.serial_port, self.baudrate)
        self.write_mode = write
        self.lock = threading.Lock()

        # check keys and values
        self.read_keys = read_keys or [] 
        self.write_keys = write_keys or [] if write else []
        self.write_vals = write_vals or [] if write else []
        if isinstance(self.read_keys, str):
            self.read_keys = [self.read_keys]
        if isinstance(self.write_keys, str):
            self.write_keys = [self.write_keys]
        if isinstance(self.write_vals, float) or isinstance(self.write_vals, int):
            self.write_vals = [self.write_vals]
        if self.write_vals:
            assert len(self.write_keys) == len(self.write_vals), "Write values must match the write keys"
        if write and len(write_keys) == 0:
            raise ValueError("Write keys must be specified for writing data")
        
        # keys to header
        self.header = []
        self.headermap = {} # map the header to the index
        # read keys are headers by default; add in write keys
        for k in (self.read_keys + self.write_keys):
            if not isinstance(k, str) or '@' not in k:
                raise ValueError(f"Key {k} must be a string with '@' in it")
            if k not in self.headermap:
                self.header.append(k)
                self.headermap[k] = len(self.header) - 1
        
        # device number has to be specified in the read keys
        # split the read_keys into device number and attribute
        self.devices_lst = []
        self.attrs_lst = []
        for k in self.header:
            k_lst = k.split('@')
            if len(k_lst) != 2:
                raise ValueError("Invalid read key format")
            self.devices_lst.append(int(k_lst[1]))
            self.attrs_lst.append(k_lst[0])

        if write:
            self.write_attributes = [self.attrs_lst[self.headermap[k]] for k in self.write_keys]
            self.write_devices = [self.devices_lst[self.headermap[k]] for k in self.write_keys]

        # check if the devices are valid
        if self.num_devices:
            assert len(set(self.devices_lst)) == self.num_devices, "The number of devices does not match the number of read keys"
        else:
            self.num_devices = len(set(self.devices_lst))

        self.cmd_gap = cmd_gap

        # check if the devices are connected, and if the keys are valid
        self.precheck()

        # add variable for writing
        if write:
            self.tmp_write_keys = [k for k in self.write_keys]
            self.tmp_write_attrs = [self.attrs_lst[self.headermap[k]] for k in self.tmp_write_keys]
            self.tmp_write_devices = [self.devices_lst[self.headermap[k]] for k in self.tmp_write_keys]

        # check if the sampling time is appropriate
        self.header_size = len(self.header)
        self.read_time_buffer = self.cmd_gap * self.header_size + 0.005
        if self.sampling_time < self.read_time_buffer:
            raise ValueError(f"The sampling time must be greater than {self.read_time_buffer} seconds due to the number of keys to read")
        self.rest_time = self.sampling_time - self.read_time_buffer
     
        print("TCM at ", self.serial_port, " is successfully initialized \n")

    def precheck(self):
        # check if reading the header is successful
        precheck_data = self.precheck_read()
        time.sleep(0.1)
        if self.write_mode:
            write_vals = self.write_vals or [precheck_data[self.headermap[k]] for k in self.write_keys]
            self.precheck_write(write_vals)
    
    def precheck_read(self):
        data = []
        for addr, attr in zip(self.devices_lst, self.attrs_lst):
            self._read_cmd(attr, addr)
            bytes_waiting = self.ser.inWaiting()
            if bytes_waiting == 0:
                raise ValueError(f"Device {addr} is possibly not connected")
            output_str = (self.ser.readline(bytes_waiting)).decode()
            if output_str.startswith("CMD:"):
                error_code = extract_error_code(output_str)
                raise AttributeError(f"Error code {error_code} for attribute {attr} to \
                                       address {addr}: {self._errorcode_report(error_code)}")
            else:
                val = float(output_str.split('=')[1].replace(f'@{addr}', ''))
                print(f"Device {addr} is connected and attribute {attr} is valid, initial value: {val}")
                data.append(val)
        return data
    
    def precheck_write(self, init_vals: List):
        for addr, attr, val in zip(self.write_devices, self.write_attributes, init_vals):
            self._write_cmd(attr, addr, val)
            output_str = self.ser.read(self.ser.inWaiting()).decode()
            error_code = extract_error_code(output_str)
            if error_code != 1 and error_code != 8:
                raise AttributeError(
                    f"Error code {error_code} for attribute {attr} to "
                    f"address {addr}: {self._errorcode_report(error_code)}"
                )
            else:
                print(f"Device {addr} is connected and write in {attr} with value {val} is valid")
                # print(f"Write command {attr} to address {addr} with value {val} is successful")

    def issubset_write_keys(self, keys: List[str]):
        return set(keys).issubset(set(self.write_keys))
    
    def requires_write_mode(func):
        """
        Decorator to ensure that a function can only be called if `self.write` is True.
        """
        def wrapper(self, *args, **kwargs):
            if not getattr(self, 'write_mode', False):
                raise RuntimeError(f"The function '{func.__name__}' requires writing to be enabled. Set write=True to use this function.")
            return func(self, *args, **kwargs)
        return wrapper

    def read_data(self):
        # TODO: is flush neccesary?
        # TODO: check if collected data is correct/clean
        # send the read commands to the devices
        init_time = time.time()
        with self.lock:
            for addr, attr in zip(self.devices_lst, self.attrs_lst):
                self._read_cmd(attr, addr)
            # read the data
            output_str = (self.ser.readline(self.ser.inWaiting())).decode()   
            if len(output_str.split('\r')[:-1]) != self.header_size:
                return None
            output_lst = [float(ele.split('=')[1][:-len(f'@{self.devices_lst[i]}')]) 
                        for i, ele in enumerate(output_str.split('\r')[:-1])]
        # assert len(output_lst) == self.header_size, "The number of output keys does not match the number of read keys"
        time.sleep(max(0, self.sampling_time - (time.time() - init_time)))
        return output_lst
    
    def _errorcode_report(self, code: int):
        return _error_codes.get(code, "Unknown error code")
    
    def _read_cmd(self, attr: str, address: str):
        self.ser.write(f"{attr}?@{address}\r".encode())
        time.sleep(self.cmd_gap)
    
    @requires_write_mode
    def _write_cmd(self, attr: str, address: str, val):
        self.ser.write(f"{attr}={val}@{address}\r".encode())
        time.sleep(self.cmd_gap)
        # readout = self.ser.read(self.ser.inWaiting()).decode()
        # err_code = extract_error_code(readout)
        # return err_code
    
    @requires_write_mode
    def write_cmd(self, attr: str, address: str, val):
        """
        Write single command to the device
        """
        with self.lock:
            self._write_cmd(attr, address, val)
            readout = self.ser.read(self.ser.inWaiting()).decode()
            err_code = extract_error_code(readout)
            if err_code != 1 or err_code != 8:
                raise AttributeError(f"Error code {err_code} for attribute {attr} to \
                                    address {address}: {self._errorcode_report(err_code)}")
    
    @requires_write_mode
    def write_cmds(self, attributes: List[str], addresses: List[int], vals: List):
        """
        Write multiple commands to the devices
        """
        with self.lock:
            # alternative 1
            for attr, addr, val in zip(attributes, addresses, vals):
                self._write_cmd(attr, addr, val)
            readout = self.ser.read(self.ser.inWaiting()).decode()
            for line in readout.split('\r')[:-1]:
                error_code = extract_error_code(line)
                if error_code != 1 and error_code != 8:
                    raise AttributeError(
                        f"Error code {error_code} for attribute {attr} to"
                        f"address {addr}: {self._errorcode_report(error_code)}")
            # # alternative 2
            # # not used due to the concern of inefficiency of ser.read
            # for attr, addr, val in zip(attributes, addresses, vals):
            #     self.write_cmd(attr, addr, val)

    @requires_write_mode
    def write_data(self, data, keys=None):
        """
            Write data to the TCM devices.
            - data: a dictionary, list, numpy array, or even a single value
            - keys: user can specify the keys to write to the devices, but must be a subset 
                of the predefined write keys
        """
        if isinstance(data, dict):
            # input data is a dictionary
            keys = list(data.keys())
            vals = list(data.values())
        elif isinstance(data, list) or isinstance(data, np.ndarray):
            # input data is a list or numpy array
            keys = keys or self.write_keys
            vals = data
        elif isinstance(data, float) or isinstance(data, int):
            vals = [data]
            keys = keys or self.write_keys
            if not isinstance(keys, list):
                keys = [keys]
        else:
            raise ValueError("The input data must be a dictionary, list, numpy array, or a single value")
        assert len(keys) == len(vals), "The input data must match the keys"

        if keys == self.write_keys:
            self.write_cmds(self.write_attributes, self.write_devices, vals)
        elif keys == self.tmp_write_keys:
            self.write_cmds(self.tmp_write_attrs, self.tmp_write_devices, vals)
        else:
            # check if the keys are a subset of the write
            if not self.issubset_write_keys(keys):
                raise ValueError("The keys must be a subset of the write keys")
            attrs = [self.write_attributes[self.write_keys.index(k)] for k in keys]
            devices = [self.write_devices[self.write_keys.index(k)] for k in keys]
            self.tmp_write_keys = keys
            self.tmp_write_attrs = attrs
            self.tmp_write_devices = devices
            self.write_cmds(attrs, devices, vals)
    
if __name__ == "__main__":
    config = 'config_TCM_test.json'
    with open(config, 'r') as f:
        config = json.load(f)

    device_config = config['devices']['TCM']
    tcm = TCM(**device_config)

    print(tcm.write_keys)
    print(tcm.headermap)
    
    t = 0
    while t < 10:
        data = tcm.read_data()
        print(data)
        if t == 3:
            try:
                tcm.write_data(15, keys='TC1:TCTEMP@3')
            except Exception as e:
                print(f"Error writing data: {e}")
            try:
                tcm.write_data(50, keys='TC1:TCADJUSTTEMP@3')
            except Exception as e:
                print(f"Error writing data: {e}")
        if t == 6:
            try:
                tcm.write_data([20, 0], keys=['TC1:TCADJUSTTEMP@3'])
            except Exception as e:
                print(f"Error writing data: {e}")
            try:
                tcm.write_data([20, 1])
            except Exception as e:
                print(f"Error writing data: {e}")
        if t == 8:
            tcm.write_mode = False
            try:
                tcm.write_data(15, keys='TC1:TCADJUSTTEMP@3')
            except Exception as e:
                print(f"Error writing data: {e}")
            tcm.write_mode = True
            try:
                tcm.write_data(25, keys='TC1:TCADJUSTTEMP@3')
            except Exception as e:
                print(f"Error writing data: {e}")
            print(tcm.tmp_write_keys)
        t += 1
        time.sleep(0.25)