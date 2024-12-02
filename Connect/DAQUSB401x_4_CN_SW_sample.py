import numpy as np
import math

# 初始化全局变量，用于跟踪每个通道的采样时间点
current_time_points = [0.0, 0.0, 0.0, 0.0]  # 4 个通道的时间点


def generate_signal_value(signal_type, t, amplitude=10.0, offset=0.0):
    """
    根据当前时间 t 生成指定类型的信号值。
    """
    phase = 2 * np.pi * t  # 计算相位

    if signal_type == 'sine':
        return amplitude * np.sin(phase) + offset
    elif signal_type == 'square':
        return amplitude * np.sign(np.sin(phase)) + offset
    elif signal_type == 'sawtooth':
        return amplitude * (2 * (t % 1) - 1) + offset
    elif signal_type == 'triangle':
        return amplitude * (2 * np.abs(2 * (t % 1) - 1) - 1) + offset
    elif signal_type == 'random':
        return np.random.uniform(-amplitude, amplitude) + offset
    else:
        raise ValueError(f"Unsupported signal type: {signal_type}")


def adc_sync_acquisition_virtual(duration, signal_type, frequency):
    """
    模拟采集：逐次返回每个通道当前时间点的最新信号值。
    """
    global current_time_points  # 使用全局变量跟踪每个通道的时间点

    # 每个通道的最新采样值
    new_values = []

    # 为每个通道生成最新的信号值
    for i in range(4):
        # 获取当前时间点的信号值
        value = generate_signal_value(signal_type, current_time_points[i])

        # 更新时间点（推进一个采样间隔）
        current_time_points[i] += 1 / frequency

        # 为每个通道的信号添加随机缩放（模拟噪声）
        scaling_factor = np.random.normal(1.0, 0.1)  # 正态分布N(1.0, 0.1)
        scaled_value = value * scaling_factor

        # 将缩放后的值加入到新采样值列表中
        new_values.append(scaled_value)

    return new_values


if __name__ == "__main__":
    # 测试逐次采样，每秒 10 个采样点
    print("Starting SW mode sampling...")
    for _ in range(10):  # 采样 10 次
        data = adc_sync_acquisition_virtual(1, 'sine', 10)
        print(f"Sampled data: {data}")
