from devices.helpers import initialize_devices
from utils import read_config, hold_time
from utils.data import DataCollector
from utils.data import devices_read_threads
from tqdm import tqdm
import time
import queue
import traceback


def run():
    # load config
    config = read_config()
    assert 'devices' in config, 'devices not found in config'
    config_devices = config['devices']
    assert isinstance(config_devices, dict), "value of 'devices' must be a dictionary"

    # initialize devices
    print('Program starts... \n')
    devices, device_info = initialize_devices(config_devices)
    device_headers = device_info['headers']
    device_sampling_times = device_info['sampling_times']
    print(f"Devices initialized: {device_info['names']}")
    print(f"Device headers: {device_headers}")
    print(f"Device sampling times: {device_sampling_times}")

    # data queues and threads
    queues = [queue.Queue() for _ in range(len(devices))]
    threads = devices_read_threads(devices, queues)

    # initilate data collector
    save = config.get('save', False)
    filepath = config.get('filepath', None)
    filename = config.get('filename', None)
    collector = DataCollector(queues, device_headers, save=save, filepath=filepath, filename=filename)
    writing_time = config['writing_time']

    # holding time before starting the data collection
    holding_duration = config.get('holding_time', 0)
    hold_time(holding_duration)

    # collection duration
    collection_duration = config.get('collection_duration', 24*7*3600)  # max 7 days
    if collection_duration <= 0:
        raise ValueError("Collection duration must be greater than 0 seconds.")

    # start threads
    timestamp = time.time()
    print("\nStarting data collection threads...")
    for thread in threads:
        thread.start()
    
    # wait for threads to start
    time.sleep(max(device_sampling_times)*2)
    start_time = time.time()

    # run data collection loop
    print("\nData collection started. Press Ctrl-C to stop.")
    while time.time() - start_time < collection_duration:
        # check if all threads are alive
        if not all([thread.is_alive() for thread in threads]):
            print("One or more threads are not alive. Exiting...")
            for thread in threads:
                thread.join(timeout=1)
            break
        # collect data
        try:
            collector.collect_data(timestamp+writing_time)
            data_dict = collector.get_latest_dict_data()
            print([f"{value:.2f}" for value in data_dict.values()])
        except KeyboardInterrupt:
            print("KeyboardInterrupt received. Exiting...")
            for thread in threads:
                thread.join(timeout=1)
            break
        except Exception as e:
            traceback.print_exc()
            for thread in threads:
                thread.join(timeout=1)
            break
        # update timestamp
        timestamp = timestamp + writing_time
    print("Data collection stopped.")

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
    finally:
        print("Program terminated.")