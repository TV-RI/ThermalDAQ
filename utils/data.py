# Author: Paixun (prod.pxl@gmail.com)
from datetime import datetime
import time
from typing import Dict, List
import queue
import threading
import numpy as np
import os, copy, csv


def handle_empty_data():
    pass

def enqueue_data(queue: queue.Queue, data: List[float], 
                 timestamp:float=None) -> None:
    if timestamp: 
        queue.put([timestamp] + data)
    else:
        queue.put([time.time()] + data)

def dequeue_data(queue: queue.Queue, timestamp: float) -> List[float]:
    """
    Dequeue all data from queue that's before the timestamp
    and return the mean of the data
    """
    # take all data from queue that's before the timestamp
    data = []
    while not queue.empty():
        if queue.queue[0][0] < timestamp:
            data.append(queue.get()[1:])
        else:
            break
    if data:
        # if data is not empty, return the mean of the data
        return np.nanmean(data, axis=0)
    else:
        # if data is empty, return None
        return None

def read_device_data(device, queue: queue.Queue) -> None:
    """
    Continuously read data from device and put it in the queue
    Note: the sampling time of device is executed by the read_data function itself
    """
    # check device base class
    while True:
        timestamp = time.time()
        data = device.read_data()
        # print(device.name, timestamp, data) # NOTE: debug purpose
        if data:
            enqueue_data(queue, data, timestamp)
        else:
            handle_empty_data()

def device_read_thread(device, queue: queue.Queue) -> threading.Thread:
    thread = threading.Thread(target=read_device_data, 
                              args=(device, queue))
    thread.daemon = True
    return thread

def devices_read_threads(devices: List, 
                         queues: List[queue.Queue]) -> List[threading.Thread]:
    assert len(devices) == len(queues), "Number of devices and queues should be the same"
    threads = []
    for device, q in zip(devices, queues):
        thread = device_read_thread(device, q)
        threads.append(thread)
    return threads

def wait_until_time(timestamp: float) -> None:
    """
    Wait until the timestamp
    """
    while time.time() < timestamp:
        time.sleep(0.1)

class DataCollector:
    """
    Function of this class:
        - save hashmap and list for data with headers
        - save last valid data
        - controller can directly access the latest step data
    The data collection frequency is same as the writing frequency.
    (I don't see the need to write data asynchronously yet)
    """
    def __init__(self, queues: List[queue.Queue], headers: List[List[str]],
                 save=False, filepath=None, filename=None) -> None:
        assert len(queues) == len(headers), "Number of queues and headers should be the same"
        if not queues[0].empty():
            assert all([len(q) == len(h) for q, h in zip(queues, headers)]), "Number of data in each queue and header should be the same"

        self.queues = queues
        self.headers = headers
        self.header_row = []
        for header in headers:
            self.header_row.extend(header)
        self.array_start_idx = [0] + [len(header) for header in headers[:-1]]
        self.latest_queue_data = [None] * len(queues)
        self.latest_array_data = [None] * len(self.header_row)
        self.latest_dict_data = {head: None for head in self.header_row}

        # print(self.headers)
        # print(self.header_row)
        # print(self.array_start_idx)

        self.save = save
        self.writer = None
        if save:
            self.initiate_writer(filepath, filename)
    
    def initiate_writer(self, filepath: str, filename: str) -> None:
        if not filename:
            filename = f'data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        if not filepath:
            filepath = '.'
        else:
            if not os.path.exists(filepath):
                raise ValueError(f"Filepath {filepath} does not exist")
        if os.path.exists(os.path.join(filepath, filename)):
            try:
                input(f"File {filename} already exists in {os.path.abspath(filepath)}. Press Enter to overwrite or Ctrl+C to cancel.")
            except KeyboardInterrupt:
                raise ValueError("File already exists. User cancelled the operation.")
            try:
                os.remove(os.path.join(filepath, filename))
                print(f"File {filename} is overwritten")
            except OSError as e:
                raise ValueError(f"Error deleting file {filename} from {os.path.abspath(filepath)}: {e}")
            
        # csv writer
        self.writingfile = open(os.path.join(filepath, filename), 'w', newline='')
        self.writer = csv.writer(self.writingfile)
        self.writer.writerow(['time'] + self.header_row)
    
    def save_data(self, data: List[float], timestamp: float) -> None:
        if not self.writer:
            raise ValueError("Writer is not initialized")
        if not data:
            raise ValueError("Data is empty")
        if len(data) != len(self.header_row):
            raise ValueError(f"Data length {len(data)} does not match header length {len(self.header_row)}")
        # write data to csv file
        dt = datetime.fromtimestamp(timestamp)
        row = [dt.strftime('%Y-%m-%d %H:%M:%S')] + data
        self.writer.writerow(row)
        self.writingfile.flush()

    def close_writer(self) -> None:
        if self.writer:
            self.writer.close()
    
    def update_queue_data(self, queue_idx: int, data: List[float]) -> None:
        self.latest_queue_data[queue_idx] = data
    
    def update_array_data(self, queue_idx: int, data: List[float]) -> None:
        start_idx = self.array_start_idx[queue_idx]
        end_idx = start_idx + len(data)
        self.latest_array_data[start_idx:end_idx] = data
    
    def update_dict_data(self, queue_idx: int, data: List[float]) -> None:
        # for j, head in enumerate(self.headers[queue_idx]):
        #     self.latest_dict_data[head] = data[j]
        self.latest_dict_data.update(dict(zip(self.headers[queue_idx], data)))
        
    def update_data(self, queue_idx: int, data: List[float]) -> None:
        self.update_queue_data(queue_idx, data)
        self.update_array_data(queue_idx, data)
        self.update_dict_data(queue_idx, data)
    
    def get_latest_data(self) -> List[float]:
        return copy.deepcopy(self.latest_array_data)
    
    def get_latest_dict_data(self) -> Dict[str, float]:
        return copy.deepcopy(self.latest_dict_data)
    
    def collect_data(self, timestamp: float) -> None:
        """
        Collect data from all queues and update latest_queue_data, latest_array_data, latest_dict_data
        """
        # wait the time pass the timestamp
        wait_until_time(timestamp)
        # collect data from all queues
        for i, q in enumerate(self.queues):
            data = dequeue_data(q, timestamp)
            if data is None:
                # if data is None, use last_valid_data[i]
                data = self.latest_queue_data[i]
                print('use last valid data for ', self.headers[i])
            else:
                self.update_data(i, data)
        
        if self.save:
            self.save_data(self.latest_array_data, timestamp)