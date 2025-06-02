"""
    Basic class for thermal data acquisition devices.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from tqdm import tqdm


class Device(ABC):
    def __init__(self, name, sampling_time):
        self.name = name
        self.sampling_time = sampling_time
        self.header = []
        self.write_mode = False
        self.write_keys = []
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

    def issubset_header(self, keys: List[str]) -> bool:
        return set(keys).issubset(set(self.header))
    
    def issubset_write_keys(self, keys: List[str]) -> bool:
        return set(keys).issubset(set(self.write_keys))
    
    def get_info(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'sampling_time': self.sampling_time,
            'header': self.header
        }

    @staticmethod
    def requires_write_mode(func):
        """
        Decorator to ensure that a function can only be called if 'self.write_mode' is True.
        """
        def wrapper(self, *args, **kwargs):
            if not self.write_mode:
                raise RuntimeError(f"The function '{func.__name__}' requires writing to be enabled. Set write=True to use this function.")
            return func(self, *args, **kwargs)
        return wrapper
        