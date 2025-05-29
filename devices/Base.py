"""
    Basic class for thermal data acquisition devices.
"""
from abc import ABC, abstractmethod
from typing import List, Dict
from tqdm import tqdm


class Device(ABC):
    def __init__(self, name, sampling_time):
        self.name = name
        self.sampling_time = sampling_time
        self.header = []
        assert isinstance(sampling_time, (int, float)), "Sampling time must be a number"
        assert sampling_time > 0, "Sampling time must be greater than 0"
        assert isinstance(name, str), "Device name must be a string"
                 
    @abstractmethod
    def precheck(self):
        """
        Abstract method to check the connection of the sensors.
        """
        pass
    
    @abstractmethod
    def read_data(self):
        """
        Abstract method to read data from the sensors.
        
        :return: List of sensor readings.
        """
        pass