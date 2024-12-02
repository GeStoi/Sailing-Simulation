import numpy as np
import time
import libdaq
from ctypes import *
from device import *
# 全局变量用于保存初始化后的设备对象
device = None

def init_device():
    """初始化DAQ设备，只需执行一次"""
    global device

    if device is not None:
        print("Device already initialized.")
        return device  # 如果设备已初始化，则直接返回
    else:
        print("Initializing DAQ device...")
        libdaq.libdaq_init()  # 初始化 DAQ 系统
        device_count = libdaq.libdaq_device_get_count()

        if device_count <= 0:
            raise Exception("No device detected!")

        (errorcode, device_name) = libdaq.libdaq_device_get_name(0)
        print(f"Device: {device_name} detected")
        device = libdaq.DAQUSB401x(device_name)  # 创建设备对象

        # 配置和校准通道
        adc_config_channel(device)
        adc_calibrate_channel(device)

        print("Device initialized successfully.")
        return device  # 返回设备实例

def adc_sync_acquisition(sample_rate=10000):
    """从硬件设备同步采集数据，指定采样率，采样周期为1，并返回一维数组"""
    print("Acquiring hardware data with sample cycle = 1...")

    device = init_device()

    if device is None:
        raise Exception("Device not initialized. Please call init_device() first.")

    print(f"Acquiring data at {sample_rate} Hz...")

    # 设置采样参数（4个通道）
    channel_list = [0, 1, 2, 3]
    samplepara = adc_samplepara()
    samplepara.channel_list = channel_list
    samplepara.sample_mode = libdaq.ADC_SAMPLE_MODE_SYNC  # 同步采样模式
    samplepara.frequency = sample_rate  # 设置采样频率
    samplepara.cycles = 1  # 采样周期为1

    # 设置软件触发方式并应用采样参数
    device.adc.select_triggerSrc(libdaq.ADC_TRIG_SRC_SW)
    device.adc.set_sample_parameter(samplepara)

    # 清除缓冲区并启动采样任务
    device.adc.clear_buffer()
    device.adc.start_task()
    device.adc.send_trigger()  # 发送软件触发信号

    # 计算采样数据长度并读取数据
    data_len = len(channel_list)  # 每个通道采集一个周期的数据
    (errorcode, result) = device.adc.read_analog_sync(data_len, 5000)

    # 停止采样任务
    device.adc.stop_task()

    # 将所有通道的数据拼接为一个一维数组
    data = []
    for ch_index in range(len(channel_list)):
        ch_data = device.adc.extractChannelData(result, len(channel_list), ch_index)
        data.extend([round(value, 4) for value in ch_data])

    # 返回采集的数据
    return data

def adc_config_channel(device):
    """配置4个通道"""
    ch_range = libdaq.CHANNEL_RANGE_N10V_P10V
    ch_couplemode = libdaq.ADC_CHANNEL_DC_COUPLE
    ch_refground = libdaq.ADC_CHANNEL_REFGND_RSE

    for channel in range(4):
        device.adc.config_channel_ex(channel, ch_range, ch_couplemode, ch_refground)

def adc_calibrate_channel(device):
    """校准4个通道"""
    gain = 1.0
    offset = 0.0
    device.adc.calibrate_channel(0xFF, gain, offset)

if __name__ == "__main__":
    # 初始化设备
    init_device()

    # 采集数据
    data = adc_sync_acquisition(5000)  # 实际采样率为5 Hz
    for i, value in enumerate(data):
        print(f"Channel[{i}]: {value}")