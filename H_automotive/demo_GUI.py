# -*- coding: utf-8 -*-
"""
Created on Mon Jun 23 14:40:18 2025

@author: skj
"""

import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports  # 추가
import threading
import queue
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import random  # 테스트용 시뮬레이션 데이터
import tkinter.font as tkFont
import time


class ADC_GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ADC GUI")
        self.root.geometry("1300x850")  # 창 크기 설정

        # ✅ 기본 폰트 크기 조정
        default_font = tkFont.nametofont("TkDefaultFont")
        default_font.configure(size=16)  # 원하는 크기로 변경 (예: 12~14)

        self.uart_rx_queue = queue.Queue()
        self.adc_data = {1: [], 2: [], 3: []}  # ADC1,2,3 각각 데이터 리스트

        self.serial_port = None
        self.create_widgets()

    def create_widgets(self):
        ################### first line
        # UART 채널, Baudrate
        tk.Label(self.root, text="UART 채널").grid(row=0, column=0, padx=5, pady=20)

        self.uart_ports = self.get_serial_ports()
        self.uart_combo = ttk.Combobox(
            self.root, values=self.uart_ports, state="readonly", width=15
        )
        self.uart_combo.grid(row=0, column=1)
        if self.uart_ports:
            self.uart_combo.current(0)  # 기본 선택

        self.refresh_uart_ports()  # 초기화 시 포트 리스트 로드

        # Refresh 버튼
        ttk.Button(self.root, text="Refresh", command=self.refresh_uart_ports).grid(
            row=0, column=2, padx=5
        )

        # Baudrate 입력
        tk.Label(self.root, text="Baudrate").grid(row=0, column=3, padx=5, pady=5)
        self.baud_entry = ttk.Entry(self.root, width=13,font=("Arial",14))
        self.baud_entry.insert(0, "115200")
        self.baud_entry.grid(row=0, column=4)

        # 연결/해제 버튼
        ttk.Button(self.root, text="  UART Connect  ", command=self.connect_uart).grid(
            row=0, columnspan=2, column=5, padx=10
        )
        ttk.Button(
            self.root, text="UART Disconnect", command=self.disconnect_uart
        ).grid(row=0, column=7, padx=10)
        ################### first line

        ################### second line
        # Reg 입력 필드
        self.reg_entries = []
        default_values = ["80", "0c", "43", "01", "05", "04", "c2", "00"]
        for i in range(8):
            row, col = 1 + i // 4, (i % 4) * 2
            tk.Label(self.root, text=f"Reg {i+1:02}").grid(row=row, column=col)
            entry = ttk.Entry(self.root, width=13, font=("Arial", 12))
            entry.grid(row=row, column=col + 1, padx=5, pady=5)
            entry.insert(0, default_values[i])
            self.reg_entries.append(entry)

        # ADC 채널 드롭다운
        self.adc_channel_combo = ttk.Combobox(
            self.root,
            values=["ADC ch. 1", "ADC ch. 2", "ADC ch. 3"],
            state="readonly",
            width=10,
            font=("Arial",13),
        )
        self.adc_channel_combo.grid(row=3, column=0, padx=5)
        self.adc_channel_combo.current(0)  # 기본값 설정

        # ADC Setting 버튼
        ttk.Button(self.root, text="Reg setting", command=self.set_adc_channel).grid(
            row=3, column=1, pady=5
        )

        # Fault detection 및 모드 전환
        tk.Label(self.root, text="ADC fault detection mode setting",font=("Arial",14)).grid(
            row=3, column=2, columnspan=2, pady=5
        )
        self.mode_combo = ttk.Combobox(
            self.root, values=["Mode 1", "Mode 2", "Mode 3"], state="readonly", width=10, font=("Arial",14)
        )
        self.mode_combo.grid(row=3, column=4)
        self.mode_combo.current(0)  # 기본값 설정

        ttk.Button(self.root, text="Mode setting", command=self.send_mode).grid(
            row=3, column=5, padx=5
        )
        ttk.Button(
            self.root, text="ADC Start", command=self.send_adc_start, width=20
        ).grid(
            row=3,
            column=6,            
            columnspan=2,
            padx=5,
        )
        # ttk.Button(self.root, text="ADC Stop", command=self.send_adc_stop).grid(
        #    row=3, column=8, padx=5, pady=15
        # )
        
        tk.Label(self.root, text="").grid(row=4, column=0, columnspan=6, pady=5) # empty row
        # Plot 설명
        
        tk.Label(self.root, text="Red : ADC1   Blue : ADC2   Green : ADC3").grid(
            row=5, column=0, columnspan=6, pady=1
        )

        # Plot 영역 생성
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().grid(row=6, column=0, columnspan=6)

        # ADC 상태 표시
        tk.Label(self.root, text="ADC status").grid(row=5, column=6, columnspan=2)
        self.status_label = tk.Label(
            self.root, text="Normal", bg="lime green", width=25, height=15
        )
        self.status_label.grid(row=6, column=6, columnspan=2, padx=20, pady=20)

        self.plot_update_loop()
        
        ######################################################################################  
        # self.root.grid_columnconfigure(0,weight=1)
        # self.root.grid_columnconfigure(1,weight=1)        
        
        style = ttk.Style()
        style.configure("TButton", font=("Arial",14),padding=10)
        style.configure("TEntry", font=("Arial",14),padding=10)
        style.configure("TCombobox", font=("Arial",14),padding=10)       
        
        self.default_font = tkFont.Font(family="Arial", size=14)
        self.root.option_add("*Font", self.default_font)
        ######################################################################################  

    def uart_read_loop(self):
        while True:
            if self.serial_port and self.serial_port.is_open:
                try:
                    header = self.serial_port.read(1)
                    if not header:
                        continue
                    # print(f"[DEBUG] 수신 헤더: {header.hex().upper()}")
                    head_val = header[0]

                    if head_val in [0x01, 0x02, 0x03]:  # ADC 데이터
                        payload = self.serial_port.read(3)
                        if len(payload) == 3:
                            adc_raw = (
                                (payload[0] << 16) | (payload[1] << 8) | payload[2]
                            )
                            self.uart_rx_queue.put((head_val, adc_raw))

                    elif head_val == 0x11:  # Fault detection status
                        status = self.serial_port.read(1)
                        if status:
                            self.uart_rx_queue.put(("status", status[0]))

                except Exception as e:
                    print(f"UART read error: {e}")
            else:
                break

    def adc_to_voltage(self, adc_val):
        return (adc_val / (2**14 - 1)) * 3.3  # 16383 기준

    def plot_update_loop(self):
        if not self.root.winfo_exists():  # 창이 닫힌 경우 종료
            return
        # 큐에서 데이터 꺼내 누적
        while not self.uart_rx_queue.empty():
            item = self.uart_rx_queue.get()

            if isinstance(item[0], int):  # ADC 데이터
                head, value = item
                adc_idx = head
                self.adc_data[adc_idx].append(value)
                if len(self.adc_data[adc_idx]) > 100:
                    self.adc_data[adc_idx] = self.adc_data[adc_idx][-100:]

            elif item[0] == "status":  # Fault status 처리
                status_val = item[1]
                if status_val == 0x01:
                    self.status_label.config(text="Error", bg="red")
                elif status_val == 0x00:
                    self.status_label.config(text="Normal", bg="cornflower blue")

        # Plot
        self.ax.clear()
        if self.adc_data[1]:
            v1 = [self.adc_to_voltage(val) for val in self.adc_data[1]]
            self.ax.plot(v1, "r-", label="ADC1")
        if self.adc_data[2]:
            v2 = [self.adc_to_voltage(val) for val in self.adc_data[2]]
            self.ax.plot(v2, "b-", label="ADC2")
        if self.adc_data[3]:
            v3 = [self.adc_to_voltage(val) for val in self.adc_data[3]]
            self.ax.plot(v3, "g-", label="ADC3")
        
        self.ax.set_xlabel("Sample (n)")
        self.ax.set_ylabel("Voltage (V)")
        self.ax.set_ylim(0.2, 3.2)
        self.ax.legend(loc="upper right")
        self.canvas.draw()

        # self.root.after(300, self.plot_update_loop)
        self.after_id = self.root.after(200, self.plot_update_loop)

    def send_adc_stop(self):
        if not self.serial_port or not self.serial_port.is_open:
            print("UART not connected.")
            return

        tx_data = bytes([0x06])
        print(f"ADC Stop 전송: {tx_data.hex(' ').upper()}")

        try:
            self.serial_port.write(tx_data)
        except Exception as e:
            print(f"UART 전송 실패: {e}")

    def send_adc_start(self):
        if not self.serial_port or not self.serial_port.is_open:
            print("UART not connected.")
            return

        tx_data = bytes([0x05])
        print(f"ADC Start 전송: {tx_data.hex(' ').upper()}")

        try:
            self.serial_port.write(tx_data)
        except Exception as e:
            print(f"UART 전송 실패: {e}")

    def send_mode(self):
        if not self.serial_port or not self.serial_port.is_open:
            print("UART not connected.")
            return

        mode_map = {"Mode 1": 0x01, "Mode 2": 0x02, "Mode 3": 0x03}
        selected_mode = self.mode_combo.get()
        mode_val = mode_map.get(selected_mode)

        if mode_val is None:
            print(f"잘못된 모드 선택: {selected_mode}")
            return

        tx_data = bytes([0x04, mode_val])
        print(f"Mode 설정 전송: {tx_data.hex(' ').upper()}")

        try:
            self.serial_port.write(tx_data)
        except Exception as e:
            print(f"UART 전송 실패: {e}")

    def set_adc_channel(self):
        if not self.serial_port or not self.serial_port.is_open:
            print("UART not connected.")
            return

        # 1. ADC 채널 헤더 바이트 설정
        adc_ch_map = {"ADC ch. 1": 0x01, "ADC ch. 2": 0x02, "ADC ch. 3": 0x03}
        selected_ch = self.adc_channel_combo.get()
        head_byte = adc_ch_map.get(selected_ch, 0x01)

        # 2. 레지스터 값 읽기 및 바이트 리스트로 변환
        try:
            reg_bytes = []
            for entry in self.reg_entries:
                val_str = entry.get().strip()
                byte_val = int(val_str, 16)  # 16진수 문자열을 int로 변환
                if not 0 <= byte_val <= 255:
                    raise ValueError(f"Out of range: {val_str}")
                reg_bytes.append(byte_val)
        except ValueError as e:
            print(f"잘못된 입력값: {e}")
            return

        # 3. 바이트 단위로 전송
        tx_sequence = [head_byte] + reg_bytes
        print("TX (1바이트씩):", " ".join(f"{b:02X}" for b in tx_sequence))

        try:
            for byte in tx_sequence:
                self.serial_port.write(bytes([byte]))
                time.sleep(0.005)
        except Exception as e:
            print(f"UART 전송 실패: {e}")

    def get_serial_ports(self):
        """현재 PC에 연결된 시리얼 포트 목록 가져오기"""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def refresh_uart_ports(self):
        """현재 연결 가능한 포트를 다시 불러와 드롭다운 갱신"""
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        self.uart_combo["values"] = port_list
        if port_list:
            self.uart_combo.current(0)
        else:
            self.uart_combo.set("")  # 선택 해제

    def connect_uart(self):
        port = self.uart_combo.get()
        baud = self.baud_entry.get()
        try:
            self.serial_port = serial.Serial(port, int(baud), timeout=1)
            print(f"{port} 연결됨 (baud: {baud})")
            print(f"serial_port.is_open: {self.serial_port.is_open}")

            self.uart_rx_thread = threading.Thread(
                target=self.uart_read_loop, daemon=True
            )
            self.uart_rx_thread.start()

        except Exception as e:
            print(f"연결 실패: {e}")

    def disconnect_uart(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            print("UART 연결 해제됨.")

    def on_close(self):
        if hasattr(self, "after_id"):
            self.root.after_cancel(self.after_id)
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ADC_GUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)  # X버튼 누르면 안전하게 종료
    root.mainloop()
