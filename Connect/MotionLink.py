import sys
import numpy as np
import pandas as pd
import time
import socket
import struct
import matplotlib.pyplot as plt
from datetime import datetime
from PyQt5 import QtCore
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QWidget, QGridLayout, QSpinBox, QComboBox, QLineEdit, QFileDialog
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont, QResizeEvent, QPalette, QColor

import pyqtgraph as pg
from pyqtgraph import ArrowItem  # 在顶部导入 ArrowItem

# from DAQ.Zishu_DAQ.USB_4010.DAQUSB401x_4_CN_HW_sample import init_device
from DAQUSB401x_4_CN_SW_sample import adc_sync_acquisition_virtual
from DAQUSB401x_4_CN_HW_sample import adc_sync_acquisition, init_device


class Real_Time_Simulation(QMainWindow):
    def __init__(self):
        super().__init__()

        self.channel_data = {i: [] for i in range(4)}
        self.cg_data = []
        self.timestamp_data = []
        self.sample_times = []
        self.sampling_rate = 10
        self.elapsed_time = 0
        self.mode = "Software Mode"  # 默认模式
        self.timer_duration = None
        self.is_running = False

        self.width = 2.0
        self.height = 2.0

        self.data_labels = {}
        self.avg_labels = {}
        self.Force_sum_label = None
        self.pid_output_label = None
        self.attitude_5_label = None

        self.y_discrete = [0]
        self.v_discrete = [0]
        self.a_discrete = [0]
        self.e = [0]
        self.integral_e = [0]
        self.u_discrete = [0]

        self.m = 10
        self.k = 1000
        self.damping = 40
        self.dt_discrete = 0.01  # 离散解的采样时间为10ms

        self.Kp = 0
        self.Ki = 0
        self.Kd = 0

        self.Initial_Force_Sum = None
        self.platform_mass = None

        self.initUI()

        # 初始化设备（只执行一次）
        self.device = init_device()

    def initUI(self):
        self.setWindowTitle('DAQ Real-time Data Visualization')
        self.setGeometry(100, 100, 1800, 900)

        font = QFont('Helvetica', 16)
        self.setFont(font)

        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        control_layout = QGridLayout()
        control_layout.setSpacing(10)

        # 模式选择
        self.mode_selector = QComboBox(self)
        self.mode_selector.addItems(["Software Mode", "Hardware Mode"])
        self.mode_selector.currentIndexChanged.connect(self.change_mode)
        control_layout.addWidget(QLabel('Select Mode:', self), 0, 0)
        control_layout.addWidget(self.mode_selector, 0, 1)

        # 信号类型选择
        self.signal_type_selector = QComboBox(self)
        self.signal_type_selector.addItems(["sine", "square", "sawtooth", "triangle", "random"])
        control_layout.addWidget(QLabel('Signal Type:', self), 1, 0)
        control_layout.addWidget(self.signal_type_selector, 1, 1)

        # 采样频率
        self.freq_input = QSpinBox(self)
        self.freq_input.setRange(10, 200000)  # 每通道采样率10Sa/s~200KSa/s
        self.freq_input.setValue(self.sampling_rate)
        control_layout.addWidget(QLabel('Sampling Frequency (Hz):', self), 2, 0)
        control_layout.addWidget(self.freq_input, 2, 1)

        # 采样持续时间
        self.duration_input = QSpinBox(self)
        self.duration_input.setRange(0, 3600)
        self.duration_input.setValue(0)
        control_layout.addWidget(QLabel('Sampling Duration (seconds):', self), 3, 0)
        control_layout.addWidget(self.duration_input, 3, 1)

        # 前向平均时间输入
        self.forward_avg_input = QSpinBox(self)
        self.forward_avg_input.setRange(1, 20)
        self.forward_avg_input.setValue(5)  # 默认5秒
        control_layout.addWidget(QLabel('Forward Avg Time (s):', self), 4, 0)
        control_layout.addWidget(self.forward_avg_input, 4, 1)

        # 设置宽度输入框，并绑定 textChanged 信号
        self.width_input = QLineEdit(self)
        self.width_input.setText(str(self.width))
        self.width_input.textChanged.connect(self.update_cg_range)  # 监听宽度更改
        control_layout.addWidget(QLabel('Rectangle Width (m):', self), 5, 0)
        control_layout.addWidget(self.width_input, 5, 1)

        # 设置高度输入框，并绑定 textChanged 信号
        self.height_input = QLineEdit(self)
        self.height_input.setText(str(self.height))
        self.height_input.textChanged.connect(self.update_cg_range)  # 监听高度更改
        control_layout.addWidget(QLabel('Rectangle Height (m):', self), 6, 0)
        control_layout.addWidget(self.height_input, 6, 1)

        left_layout.addLayout(control_layout)

        # 状态显示（带颜色）
        self.status_label = QLabel('Status: Stopped', self)
        self.update_status_color('red')
        self.status_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.status_label)

        # Channel Data 标签布局
        channel_data_layout = QGridLayout()
        for i in range(4):
            label = QLabel(f"Channel {i} Data: --", self)
            # label.setAlignment(Qt.AlignCenter)
            label.setFont(QFont('Helvetica', 16))  # 设置字体为 Helvetica, 大小为 16
            channel_data_layout.addWidget(label, i // 2, i % 2)
            self.data_labels[i] = label
        left_layout.addLayout(channel_data_layout)

        # 四个通道的前向平均值标签布局
        avg_label_layout = QGridLayout()
        for j in range(4):
            label = QLabel(f"Channel {j} Avg: --", self)
            label.setFont(font)
            # label.setAlignment(Qt.AlignCenter)
            avg_label_layout.addWidget(label, j // 2, j % 2)
            self.avg_labels[j] = label
        left_layout.addLayout(avg_label_layout)

        # Force_Sum 标签布局
        self.Force_sum_label = QLabel("Force Sum: -- N", self)
        self.Force_sum_label.setFont(font)
        left_layout.addWidget(self.Force_sum_label)

        # pid_output 标签布局
        self.pid_output_label = QLabel("PID Output: --m", self)
        self.pid_output_label.setFont(font)
        left_layout.addWidget(self.pid_output_label)

        # attitudes[5] 标签布局
        self.attitude_5_label = QLabel("Attitude[5]: --m", self)
        self.attitude_5_label.setFont(font)
        left_layout.addWidget(self.attitude_5_label)

        # CG 坐标标签的两列布局
        cg_label_layout = QHBoxLayout()
        self.cg_x_label = QLabel("CG X: -- m", self)
        self.cg_y_label = QLabel("CG Y: -- m", self)
        # self.cg_x_label.setAlignment(Qt.AlignCenter)
        # self.cg_y_label.setAlignment(Qt.AlignCenter)

        # 设置字体和对齐方式
        font = QFont('Helvetica', 16)
        self.cg_x_label.setFont(font)
        self.cg_y_label.setFont(font)

        # 添加到水平布局
        cg_label_layout.addWidget(self.cg_x_label)
        cg_label_layout.addWidget(self.cg_y_label)

        left_layout.addLayout(cg_label_layout)
        # 控制按钮
        button_layout = QHBoxLayout()
        for text, func in [
            ("Start", self.start_acquisition),
            ("Stop", self.stop_acquisition),
            ("Clear", self.clear_data),
            ("Export", self.export_data)
        ]:
            button = QPushButton(text, self)
            button.setMinimumHeight(40)
            button.clicked.connect(func)
            button_layout.addWidget(button)
        left_layout.addLayout(button_layout)

        # 数据曲线图
        self.data_plot = pg.PlotWidget()
        self.data_plot.setTitle("Channel Data Over Time")
        self.data_plot.setBackground('k')
        self.data_plot.showGrid(x=True, y=True)
        self.data_plot.addLegend()

        # 设置 X 和 Y 轴的标签和字体
        self.data_plot.setLabel('left', 'Amplitude', **self.get_font_style())
        self.data_plot.setLabel('bottom', 'Time (s)', **self.get_font_style())

        self.data_curves = {
            i: self.data_plot.plot(name=f"Channel {i}", pen=(i, 4)) for i in range(4)
        }
        left_layout.addWidget(self.data_plot)

        # 重心位置图
        self.cg_plot = pg.PlotWidget()
        self.cg_plot.setBackground('k')
        self.cg_plot.setTitle("Center of Gravity")
        self.cg_plot.showGrid(x=True, y=True)
        self.cg_plot.setAspectLocked(True)
        self.cg_plot.setLabel('left', 'Y Position (m)', **self.get_font_style())
        self.cg_plot.setLabel('bottom', 'X Position (m)', **self.get_font_style())

        # 初始化箭头（颜色设为黄色）
        self.arrow = ArrowItem(
            angle=0, tipAngle=30, baseAngle=20, headLen=20, tailLen=None,
            brush=pg.mkBrush('w'), pen=pg.mkPen('w', width=2)
        )
        self.arrow.setPos(0, 0)  # 初始位置
        self.cg_plot.addItem(self.arrow)  # 将箭头添加到重心图

        # 添加中心标记
        self.center_marker = pg.ScatterPlotItem(symbol='o', size=20, brush=pg.mkBrush('y'))
        self.cg_plot.addItem(self.center_marker)

        # 用于存储上一次的位置
        self.previous_position = np.array([0.0, 0.0])  # 上一次位置

        main_layout.addLayout(left_layout, 2)
        main_layout.addWidget(self.cg_plot, 1)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.update_cg_range()
        # 在显示窗口后模拟轻微调整窗口
        QTimer.singleShot(0, self.simulate_resize)

    def get_font_style(self):
        """返回统一的字体样式"""
        return {'font': QFont('Helvetica', 16)}

    def update_status_color(self, color):
        palette = self.status_label.palette()
        palette.setColor(QPalette.WindowText, QColor(color))
        self.status_label.setPalette(palette)

    def change_mode(self):
        mode = self.mode_selector.currentText()
        self.mode = mode
        self.status_label.setText(f"Mode: {mode}")

        # 禁用或启用信号类型选择
        if mode == "Hardware Mode":
            self.signal_type_selector.setEnabled(False)
        else:
            self.signal_type_selector.setEnabled(True)

    def update_cg_range(self):
        """根据宽度和高度调整CG窗口的比例和坐标范围"""
        try:
            width = float(self.width_input.text())
            height = float(self.height_input.text())
        except ValueError:
            return  # 输入无效时不更新

        self.width = width
        self.height = height

        # 1.01倍放大比例
        expanded_width = width * 1.01
        expanded_height = height * 1.01

        # 根据宽高比计算窗口的固定宽度
        aspect_ratio = expanded_width / expanded_height
        plot_height = self.cg_plot.height()  # 获取CG窗口的高度
        new_width = int(plot_height * aspect_ratio)

        # 设置窗口的固定宽度
        self.cg_plot.setFixedWidth(new_width)

        # 设置坐标范围，确保范围稍微超出
        self.cg_plot.setXRange(-expanded_width / 2, expanded_width / 2, padding=0)
        self.cg_plot.setYRange(-expanded_height / 2, expanded_height / 2, padding=0)

        # 强制刷新窗口布局
        self.cg_plot.update()

    def resizeEvent(self, event: QResizeEvent):
        """重写窗口大小调整事件，确保CG窗口的比例正确"""
        super().resizeEvent(event)
        # QApplication.processEvents()  # 强制更新布局
        self.update_cg_range()  # 在窗口大小改变时更新CG窗口

    def simulate_resize(self):
        """模拟轻微调整窗口大小以确保CG窗口布局正确"""
        current_size = self.frameGeometry()
        current_width = current_size.width()
        current_height = current_size.height()

        # 模拟用户拖动窗口：增加 10 像素，然后恢复原始尺寸
        self.resize(current_width + 10, current_height + 10)
        QApplication.processEvents()  # 确保界面刷新
        self.resize(current_width, current_height)
        QApplication.processEvents()  # 确保布局更新

        # 恢复为原尺寸
        self.resize(current_width, current_height)

        # 再次处理事件，确保布局更新
        QApplication.processEvents()

    def start_acquisition(self):
        if not self.is_running:
            # 获取采样率和持续时间
            self.sampling_rate = self.freq_input.value()
            self.timer_duration = self.duration_input.value() or 3600  # 默认为 1 小时

            # 清空数据
            self.is_running = True
            self.update_status_color('green')
            self.status_label.setText(f'Status: Running ({self.mode})')

            # 根据采样率设置定时器
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_data)
            interval = int(1000 / self.sampling_rate)  # 采样间隔（毫秒）
            self.timer.start(interval)

            # 如果 duration 为 0，表示无限采样
            if self.timer_duration > 0:
                # 在指定时长后自动停止采样
                QTimer.singleShot(self.timer_duration * 1000, self.stop_acquisition)

            # 立即更新一次数据，确保开始时有数据
            self.update_data()

    def stop_acquisition(self):
        self.update_status_color('red')
        self.status_label.setText('Status: Stopped')
        self.timer.stop()
        self.is_running = False

    def clear_data(self):
        self.channel_data = {i: [] for i in range(4)}
        self.sample_times.clear()
        self.elapsed_time = 0
        for curve in self.data_curves.values():
            curve.clear()
        self.center_marker.setData([], [])

    def map_to_pixel_distance(self, p1, p2):
        """将物理距离转换为像素距离"""
        # 获取当前 CG 绘图窗口的大小（像素）
        plot_size = self.cg_plot.size()
        width_px, height_px = plot_size.width(), plot_size.height()

        # 获取绘图的 X 和 Y 轴范围（物理单位，米）
        x_range = self.cg_plot.viewRange()[0]  # (x_min, x_max)
        y_range = self.cg_plot.viewRange()[1]  # (y_min, y_max)

        # 计算物理范围的宽度和高度
        width_m = x_range[1] - x_range[0]
        height_m = y_range[1] - y_range[0]

        # 计算物理距离的比例到像素距离
        delta = np.array(p2) - np.array(p1)  # 两点之间的物理距离
        delta_px = np.array([
            (delta[0] / width_m) * width_px,  # X 方向的像素距离
            (delta[1] / height_m) * height_px  # Y 方向的像素距离
        ])

        # 返回像素距离的 L2 范数（总距离）
        return np.linalg.norm(delta_px)

    def update_data(self):
        """根据所选模式更新数据，并计算重心位置"""
        # 从用户输入的控件中获取采样时长和频率
        sampling_rate = self.freq_input.value()
        duration = self.duration_input.value() or 3600  # 默认为1小时
        forward_avg_time = self.forward_avg_input.value()  # 获取前向平均时间

        # 根据所选模式更新数据
        if self.mode == "Hardware Mode":
            # 从硬件采集最新数据
            data = adc_sync_acquisition(sampling_rate)
        else:
            # 从虚拟采集函数获取当前时间点的最新数据
            data = adc_sync_acquisition_virtual(1, self.signal_type_selector.currentText(), sampling_rate)

        sampling_rate = self.freq_input.value()  # 获取采样率
        sampling_interval = 1.0 / sampling_rate  # 每次采样的时间间隔 (秒)

        # 更新时间戳并记录时间序列（x轴为时间）
        self.elapsed_time += sampling_interval
        self.sample_times.append(self.elapsed_time)

        map = [195.7555170, 198.2143588, 196.2374373, 192.8436289]
        Force_Sum = sum(d * m for d, m in zip(data, map))

        # 新增逻辑，初始化Initial_Force_Sum
        if self.Initial_Force_Sum is None:
            self.Initial_Force_Sum = Force_Sum
        self.platform_mass = abs(self.initial_F_discrete / 9.81)
        # 更新每个通道的数据和曲线
        for i in range(4):
            value = data[i] * map[i]  # 获取最新数据点的值
            self.channel_data[i].append(value)  # 将新值加入通道数据

            # 更新数据标签和曲线
            self.data_labels[i].setText(f"Channel {i} Data: {value:.12f}")
            self.data_curves[i].setData(self.sample_times, self.channel_data[i])

            # 计算前向平均值
            forward_avg_time = self.forward_avg_input.value()  # 前向平均时间
            samples_to_avg = int(forward_avg_time * sampling_rate)
            samples_to_avg = min(samples_to_avg, len(self.channel_data[i]))  # 避免数组越界

            avg_value = np.mean(self.channel_data[i][-samples_to_avg:])  # 计算平均值
            self.avg_labels[i].setText(f"Channel {i} Avg: {avg_value:.12f}")

        # 定义每个通道的物理位置
        positions = np.array([
            [-self.width / 2, -self.height / 2],  # 通道0的位置（左下）
            [self.width / 2, -self.height / 2],  # 通道1的位置（右下）
            [-self.width / 2, self.height / 2],  # 通道2的位置（左上）
            [self.width / 2, self.height / 2]  # 通道3的位置（右上）
        ])

        # 使用通道数据计算加权重心
        sensor_values = np.array(data)  # 假设data是 [value1, value2, value3, value4]
        cg = np.average(positions, axis=0, weights=sensor_values)

        # 计算上次重心位置与当前重心位置的物理距离
        delta = cg - self.previous_position
        print(f"Delta: {delta}")

        # 将物理距离转换为像素距离
        distance_px = self.map_to_pixel_distance(self.previous_position, cg)

        # 计算箭头旋转角度
        if np.linalg.norm(delta) > 0:
            angle = np.degrees(np.arctan2(delta[1], delta[0]))
        else:
            angle = 0

        # 更新箭头的方向、长度和位置
        self.arrow.setStyle(tailLen=distance_px, headLen=10)  # 使用像素距离
        self.arrow.setRotation(angle)  # 设置箭头的旋转角度
        self.arrow.setPos(cg[0], cg[1])  # 起点为上次位置
        # 打印箭头起点坐标
        print(f"Arrow Start: {self.previous_position}")
        print(f"CG: {cg}, Distance: {distance_px:.2f} px")

        # 更新小白点的位置为当前重心位置
        self.center_marker.setData([cg[0]], [cg[1]])

        # 更新重心标签
        self.cg_x_label.setText(f"CG X: {cg[0]:.12f} m")
        self.cg_y_label.setText(f"CG Y: {cg[1]:.12f} m")

        # 将当前重心位置保存为上次位置
        self.previous_position = cg

        attitudes = self.receive_status()
        a_heave = self.calculate_heave_acceleration(attitudes)
        print(f"a_heave at {self.elapsed_time:.3f}s: {a_heave}")
        self.a_heave_data.append(a_heave)

        virtual_force = self.calculate_virtual_force(a_heave)

        F_change = Force_Sum - self.Initial_Force_Sum + virtual_force
        spring_output = self.Spring(F_change)
        pid_output = self.pid_control(spring_output)
        self.follow_mode(0, 0, 0, 0, 0, 0.5 * pid_output)

        # 更新 Force_Sum 标签
        Force_Sum = sum(d * m for d, m in zip(data, map))
        self.Force_sum_label.setText(f"Force Sum: {Force_Sum:.12f} N")

        # 更新 pid_output 标签
        pid_output = self.pid_control(spring_output)
        self.pid_output_label.setText(f"PID Output: {pid_output:.12f}")

        # 更新 attitudes[5] 标签
        attitudes = self.receive_status()
        if attitudes is not None:
            self.attitude_5_label.setText(f"Attitude[5]: {attitudes[5]:.12f}")

    def calculate_virtual_force(self, a_heave):
        """
        计算虚拟力 F = m * a
        """
        if self.platform_mass is not None:
            return self.platform_mass * a_heave
        return 0.0

    def calculate_heave_acceleration(self, attitudes):
        """
        根据姿态数据计算heave方向的加速度
        使用三次相邻时刻的姿态值求解加速度
        """
        if not hasattr(self, 'last_attitudes'):
            self.last_attitudes = [attitudes, attitudes, attitudes]  # 初始化为当前姿态的三份副本
            return 0.0  # 初始时刻没有加速度数据
        else:
            # 更新姿态值队列
            self.last_attitudes.pop(0)  # 移除最早的一个姿态值
            self.last_attitudes.append(attitudes)  # 添加最新的姿态值

            # 调试信息
            print(f"last_attitudes: {self.last_attitudes}")

            # 计算加速度
            delta_attitude_1 = [self.last_attitudes[1][5] - self.last_attitudes[0][5]]
            delta_attitude_2 = [self.last_attitudes[2][5] - self.last_attitudes[1][5]]
            a_heave = (delta_attitude_2[0] - delta_attitude_1[0]) / (2 * self.dt_discrete ** 2)

            if a_heave > 5 or a_heave < -5:
                print("a_heave out of range")
                a_heave = 0
            return a_heave

    def Spring(self, F_discrete):
        """
        仿真一维弹簧系统，计算下一时刻的位移。

        参数:
        F_discrete -- 瞬时力

        返回值:
        output -- 下一时刻的位移
        """
        # 定义系统参数
        m = self.m  # 物块质量
        k = self.k  # 弹簧弹力系数
        damping = self.damping  # 阻尼
        dt_discrete = self.dt_discrete  # 离散时间间隔

        # 初始状态
        if not hasattr(self, 'position'):
            self.position = 0  # 初始位置
        if not hasattr(self, 'velocity'):
            self.velocity = 0  # 初始速度
        if not hasattr(self, 'acceleration'):
            self.acceleration = 0  # 初始加速度

        # 根据牛顿第二定律计算加速度
        self.acceleration = (F_discrete - k * self.position - damping * self.velocity) / m

        # 更新速度和位置
        self.velocity += self.acceleration * dt_discrete
        self.position += self.velocity * dt_discrete
        y_discrete_new = self.position
        if y_discrete_new > 0.24:
            y_discrete_new = 0.24
            print(f"output exceeded upper bound, set to 0.24")
        elif y_discrete_new < -0.24:
            y_discrete_new = -0.24
            print(f"output exceeded lower bound, set to -0.24")
        # 返回下一时刻的位移
        return y_discrete_new

    def pid_control(self, F_discrete):
        e_new = 0 - self.y_discrete[-1]  # 目标值为0
        integral_e_new = self.integral_e[-1] + e_new * self.dt_discrete
        derivative_e = (e_new - self.e[-1]) / self.dt_discrete
        u_discrete_new = self.Kp * e_new + self.Ki * integral_e_new + self.Kd * derivative_e
        a_discrete_pid_new = (F_discrete - self.k * self.y_discrete[-1] - self.damping * self.v_discrete[
            -1] + u_discrete_new) / self.m
        v_discrete_pid_new = self.v_discrete[-1] + a_discrete_pid_new * self.dt_discrete
        y_discrete_pid_new = self.y_discrete[-1] + v_discrete_pid_new * self.dt_discrete

        # 限制pid_output范围在 -0.24到0.24之间，并打印越界提示
        if y_discrete_pid_new > 0.24:
            y_discrete_pid_new = 0.24
            print(f"PID output exceeded upper bound, set to 0.24")
        elif y_discrete_pid_new < -0.24:
            y_discrete_pid_new = -0.24
            print(f"PID output exceeded lower bound, set to -0.24")

        self.y_discrete.append(y_discrete_pid_new)
        self.v_discrete.append(v_discrete_pid_new)
        self.a_discrete.append(a_discrete_pid_new)
        self.e.append(e_new)
        self.integral_e.append(integral_e_new)
        self.u_discrete.append(u_discrete_new)

        return y_discrete_pid_new

# UDP通信配置
USER_IP = "192.168.0.131"
USER_PORT = 10000
CONTROLLER_IP = "192.168.0.125"
CONTROLLER_PORT = 5000
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((USER_IP, USER_PORT))


def send_command(command):
    try:
        sock.sendto(bytes.fromhex(command), (CONTROLLER_IP, CONTROLLER_PORT))
    except socket.error as e:
        print(f"Error sending command: {e}")


def receive_status():
    try:
        data, addr = sock.recvfrom(408)
        id_, status, di, rev1, *rest, version, timestamp = struct.unpack('<BBBB 6f 6f 6f 6f II', data)
        attitudes = rest[:6]
        error_codes = rest[6:12]
        motor_codes = rest[12:18]
        torques = rest[18:24]

        # 确保 attitudes, error_codes, motor_codes, torques 都是包含 6 个浮点数的数组
        attitudes = attitudes[:6]
        error_codes = error_codes[:6]
        motor_codes = motor_codes[:6]
        torques = torques[:6]

        print("接收到状态信息:")
        print("标识位:", id_)
        print("当前状态:", status)
        print("数字输入:", di)
        print("保留位:", rev1)
        print("实际姿态:", attitudes)
        print("错误代码:", error_codes)
        print("电机码值:", motor_codes)
        print("电机力矩:", torques)
        print("固件版本:", version)
        print("时间戳:", timestamp)
        return attitudes  # 返回姿态数组
    except (socket.error) as e:
        print(f"Error receiving status: {e}")
        return None

def to_bottom():
    send_command("37 07 02 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00")


def to_middle():
    send_command("37 06 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00")


def float2hex(f):
    hex_str = struct.pack('>f', f).hex()
    return ' '.join([hex_str[i:i + 2] for i in range(0, 8, 2)])


def follow_mode(roll=0.0, pitch=0.0, yaw=0.0, surge=0.0, sway=0.0, heave=0.0):
    surge_hex = float2hex(surge)
    sway_hex = float2hex(sway)
    heave_hex = float2hex(heave)
    roll_hex = float2hex(roll)
    pitch_hex = float2hex(pitch)
    yaw_hex = float2hex(yaw)
    command_head = "37 09 00 00 00 00 00 00 "
    command_main = f"{roll_hex} {pitch_hex} {yaw_hex} {surge_hex} {sway_hex} {heave_hex}"
    command_last = " 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"
    send_command(command_head + command_main + command_last)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Real_Time_Simulation()
    ex.show()
    sys.exit(app.exec_())
    sock.close()