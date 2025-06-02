from devices.Base import Device
from devices.FluxDAQ import FluxDAQ
from devices.SMTC import TCHAT
import importlib


def initialize_device(cls: str, config: dict) -> Device:
    # use cls name to choose the device class
    if cls in globals():
        device_class = globals()[cls]
    else:
        # Try to dynamically import the module
        try:
            # Assume the module is in the devices package with the same name as the class
            module_name = f"devices.{cls}"
            module = importlib.import_module(module_name)
            device_class = getattr(module, cls)
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Device class {cls} could not be loaded: {e}")
    device = device_class(**config)
    return device

def initialize_devices(config_devices: dict):
    devices = []
    for cls, config in config_devices.items():
        try:
            if isinstance(config, list):
                for cfg in config:
                    device = initialize_device(cls, cfg)
                    devices.append(device)
            elif isinstance(config, dict):
                device = initialize_device(cls, config)
                devices.append(device)
            else:
                raise ValueError(f"Invalid config for device {cls}: {config}")
        except Exception as e:
            print(f"Error initializing {cls}: {e}")
            continue

    if not devices:
        raise RuntimeError("No devices loaded. Exiting...")
    elif len(devices) < len(config_devices):
        print(f"Only {len(devices)} out of {len(config_devices)} devices loaded.")
        try:
            input("Press Enter to continue, or terminated by Ctrl-C")
        except KeyboardInterrupt:
            print("Terminating program due to incomplete device initialization.")
            raise RuntimeError("Device initialization interrupted by user.")
    return devices

def get_devices_info(devices: list[Device]):
    devices_info = {
        'names': [device.name for device in devices],
        'headers': [device.header for device in devices],
        'sampling_times': [device.sampling_time for device in devices]
    }
    return devices_info

def get_device_info(device: Device):
    return device.get_info()