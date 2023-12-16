import serial
from serial.tools import list_ports
import logging
from .CustomFormatter import CustomFormatter
from datetime import datetime
import time
import socket
import traceback
from threading import Thread


def _byte_hex_str(bytes_array):
    return "".join("{:02x} ".format(x) for x in bytes_array)


def current_milli_time():
    return round(time.time() * 1000)


class PertronicF100AMimic:
    def __init__(self, host: str, port: int):
        self._host_ip: str = host
        self._host_port: int = port
        self._timeout = 500

        self._setup_logging()

        # Used inside IO loop
        self._bytes_available = 0
        self._decodes = 0
        self._io_buffer = []

        self._lcd_led_names = [
            "normal",
            "fire",
            "defect",
            "evacuate",
            "silence_alarms",
            "device_isolated",
            "psu_defect",
            "sprinkler",
            "door_holder_isolate",
            "aux_isolate",
            "walk_test",
        ]

        self._led_callbacks = {
            "normal": [],
            "fire": [],
            "defect": [],
            "evacuate": [],
            "silence_alarms": [],
            "device_isolated": [],
            "psu_defect": [],
            "sprinkler": [],
            "door_holder_isolate": [],
            "aux_isolate": [],
            "walk_test": [],
        }
        self._lcd_callbacks = []

        self._run = False
        self._run_thread = None

        self.decoded_data = {
            "led": {
                "timestamp": 0,
                "normal": None,
                "fire": None,
                "defect": None,
                "evacuate": None,
                "silence_alarms": None,
                "addressable_leds": [None] * 257,
            },
            "lcd": {
                "line_1": {"timestamp": 0, "display_text": None},
                "line_2": {"timestamp": 0, "display_text": None},
                "leds": {
                    "timestamp": 0,
                    "normal": None,
                    "fire": None,
                    "defect": None,
                    "evacuate": None,
                    "silence_alarms": None,
                    "device_isolated": None,
                    "psu_defect": None,
                    "sprinkler": None,
                    "door_holder_isolate": None,
                    "aux_isolate": None,
                    "walk_test": None,
                },
            },
            "heartbeat": {"timestamp": 0, "status": None},
        }

        for i in range(257):
            self._led_callbacks[i] = []

    def start(self):
        if self.test_connection():
            self._run = True
            self._run_thread = Thread(target=self.__run, args=())
            self._run_thread.start()
            return True

        return False

    def stop(self):
        self._run = False
        self._run_thread.join()  # force the thread to exit

    def __run(self):
        self._io_loop()

    def _io_loop(self):
        io = socket.create_connection([self._host_ip, self._host_port])
        self.log.info("Starting IO loop")
        while self._run:
            self._io_buffer = []

            if not self._run:
                return

            try:
                io.settimeout(1)
                self._io_buffer = io.recv(500)
            except socket.timeout:
                self.log.warning("Socket timed out")
                io.close()
                time.sleep(10)
                try:
                    io = socket.create_connection([self._host_ip, self._host_port])
                except Exception as e:
                    self.log.error("Unable to reopen connection")
                    self.log.error(e)

            self._bytes_available = len(self._io_buffer)
            self._decodes = 0
            # print(_byte_hex_str(io_buffer))

            try:
                while self._bytes_available > 0:
                    last_decodes = self._decodes

                    if not self._run:
                        return

                    if len(self._io_buffer) < 2:
                        break

                    # LED Mimic Status update
                    # 0x19 0x24
                    if self._io_buffer[0] == 0x19 and self._io_buffer[1] == 0x24:
                        length = 38
                        pkt = self._get_io_bytes(length)
                        self.process_led_mimic_packet(pkt)
                        continue

                    # LCD Mimic Update line 1/2
                    # 0x20 0x17
                    if self._io_buffer[0] == 0x20 and self._io_buffer[1] == 0x17:
                        length = 46
                        pkt = self._get_io_bytes(length)
                        self.process_lcd_mimic_line(pkt)
                        continue

                    # LCD Mimic Update line 2/2
                    # 0x20 0x18
                    if self._io_buffer[0] == 0x20 and self._io_buffer[1] == 0x18:
                        length = 46
                        pkt = self._get_io_bytes(length)
                        self.process_lcd_mimic_line(pkt)
                        continue

                    # Unknown
                    # 0x20 0x19
                    if (
                        self._io_buffer[0] == 0x20
                        and self._io_buffer[1] == 0x19
                        and False
                    ):
                        length = 5
                        pkt = self._get_io_bytes(length)
                        self.process_lcd_mimic_line(pkt)
                        continue

                    # LCD Mimic Poll
                    # 0x80 0x90
                    if self._io_buffer[0] == 0x80 and self._io_buffer[1] == 0x90:
                        length = 10
                        # print("LCD Mimic Poll")

                        pkt = self._get_io_bytes(length)
                        continue

                    # Appears to be a heartbeat from the panel
                    # 0x80 0x22
                    if self._io_buffer[0] == 0x80 and self._io_buffer[1] == 0x22:
                        length = 2
                        # self.log.debug("Panel Heartbeat")
                        pkt = self._get_io_bytes(length)
                        self.decoded_data["heartbeat"]["status"] = True
                        self.decoded_data["heartbeat"]["timestamp"] = int(time.time())
                        continue

                    # Unknown
                    # 0x11 0x41
                    if self._io_buffer[0] == 0x11 and self._io_buffer[1] == 0x41:
                        length = 6
                        # print("Unknown 0x11 0x41")
                        pkt = self._get_io_bytes(length)
                        continue

                    # Unknown
                    # 0xA0 0x88
                    if self._io_buffer[0] == 0xA0 and self._io_buffer[1] == 0x88:
                        length = 14
                        # print("Unknown 0xA0 0x88")
                        pkt = self._get_io_bytes(length)
                        continue

                    # LCD Mimic 0 Response
                    # 0x40 0x40
                    if self._io_buffer[0] == 0x40 and self._io_buffer[1] == 0x40:
                        length = 10
                        # print("LCD Mimic 0 Response")
                        pkt = self._get_io_bytes(length)
                        continue

                    # Unknown
                    # 0x1c 0x22
                    if self._io_buffer[0] == 0x1C and self._io_buffer[1] == 0x22:
                        length = 36
                        # print("Unknown 0x1C 0x22")
                        pkt = self._get_io_bytes(length)
                        continue

                    # Unknown
                    # 0x47 0x31 0x97
                    if (
                        self._io_buffer[0] == 0x47
                        and self._io_buffer[1] == 0x31
                        and self._io_buffer[2] == 0x97
                    ):
                        length = 3
                        # print("Unknown 0x47 0x31 0x97")
                        pkt = self._get_io_bytes(length)
                        continue

                    # Unknown
                    # 0x83 0x31 0x97
                    if (
                        self._io_buffer[0] == 0x83
                        and self._io_buffer[1] == 0x31
                        and self._io_buffer[2] == 0x97
                    ):
                        length = 3
                        # print("Unknown 0x83 0x31 0x97")
                        pkt = self._get_io_bytes(length)
                        continue

                    if last_decodes == self._decodes:
                        # self.log.warning(
                        #    "No decoder for: {}".format(_byte_hex_str(self._io_buffer))
                        # )
                        break

            except Exception as e:
                self.log.error(
                    "Error processing bytes: {}".format(_byte_hex_str(self._io_buffer))
                )
                self.log.error(e)
                self.log.error(traceback.format_exc())

    def _get_io_bytes(self, length):
        # allow continued decoding of the packet
        self._bytes_available -= length
        self._decodes += 1
        output = self._io_buffer[:length]
        self.io_buffer = self._io_buffer[length:]
        return output

    def register_lcd_callback(self, function):
        self.log.debug("Adding LCD callback function {}".format(function.__name__))
        self._lcd_callbacks.append(function)
        return True

    def register_led_callback(self, led, function):
        self.log.debug(
            "Adding LED {} callback function {}".format(led, function.__name__)
        )
        if led <= 0 or led > 256:
            return False
        self._led_callbacks[led].append(function)
        return True

    def process_led_mimic_packet(self, pkt):
        if pkt[0] != 0x19 or pkt[1] != 0x24 or len(pkt) != 38:
            self.log.warning("Error: Invalid LED Mimic PKT")
            return

        self.decoded_data["led"]["timestamp"] = int(time.time())
        self.decoded_data["led"]["silence_alarms"] = bool(pkt[2] & 0x04)
        self.decoded_data["led"]["evacuate"] = bool(pkt[2] & 0x02)
        self.decoded_data["led"]["defect"] = bool(pkt[2] & 0x40)
        self.decoded_data["led"]["fire"] = bool(pkt[2] & 0x80)
        self.decoded_data["led"]["normal"] = bool(not (pkt[2] & 0x40 or pkt[2] & 0x80))

        """
        if pkt[2] & 0x04:
            self.log.debug("LED: Silence Alarms Active")

        if pkt[2] & 0x02:
            self.log.debug("LED: Evacuate Operated")

        if pkt[2] & 0x40:
            self.log.debug("LED Status: Defect")

        if pkt[2] & 0x80:
            self.log.debug("LED Status: FIRE")

        if not (pkt[2] & 0x40 or pkt[2] & 0x80):
            self.log.debug("LED Status: Normal")
        """

        led_offset = 4
        for i in range(32):
            byte = pkt[led_offset + i]

            for j in range(8):
                led_id = (i * 8) + j
                pos = 1 << j
                val = bool(byte & pos)
                self.decoded_data["led"]["addressable_leds"][led_id] = val
                if val:
                    self.log.debug("LED_{}".format(led_id + 1))

                callbacks = self._led_callbacks[led_id]
                for callback in callbacks:
                    try:
                        callback(bool(val))

                    except Exception as e:
                        self.log.error(
                            "Unable to process LED {} callback {}  - {}".format(
                                led_id, e
                            )
                        )
                        self.log.error(traceback.format_exc())

    def process_lcd_mimic_line(self, pkt):
        if not (
            pkt[0] == 0x20 and (pkt[1] == 0x17 or pkt[1] == 0x18) and len(pkt) == 46
        ):
            self.log.error("Invalid mimic line pkt: {}".format(_byte_hex_str(pkt)))
            return

        line = (pkt[1] == 0x18) + 1
        chars = pkt[2:42]
        line_string = chars.decode("utf8")
        line_string = line_string.lstrip(" ")  # Remove leading white space
        line_string = line_string.rstrip(" ")  # Remove trailing white space
        # self.log.debug("LCD Mimic Line {}: `{}`".format(line, line_string))
        self.decoded_data["lcd"]["line_{}".format(line)]["display_text"] = line_string
        self.decoded_data["lcd"]["line_{}".format(line)]["timestamp"] = int(time.time())

        lcd_led_pkt = pkt[42:]
        leds_dict = self.decoded_data["lcd"]["leds"]
        leds_dict["timestamp"] = int(time.time())

        leds_dict["normal"] = bool(
            not (lcd_led_pkt[3] & 0x02) and not (lcd_led_pkt[2] & 0x10)
        )
        leds_dict["defect"] = bool(lcd_led_pkt[2] & 0x10)
        leds_dict["fire"] = bool(lcd_led_pkt[3] & 0x02)

        leds_dict["silence_alarms"] = bool(lcd_led_pkt[3] & 0x10)
        leds_dict["evacuate"] = bool(lcd_led_pkt[3] & 0x04)

        leds_dict["device_isolated"] = bool(lcd_led_pkt[2] & 0x01)
        leds_dict["psu_defect"] = bool(lcd_led_pkt[2] & 0x02)
        leds_dict["sprinkler"] = None  # TODO: Not yet decoded
        leds_dict["door_holder_isolate"] = bool(lcd_led_pkt[2] & 0x80)
        leds_dict["aux_isolate"] = bool(lcd_led_pkt[2] & 0x08)
        leds_dict["walk_test"] = bool(lcd_led_pkt[2] & 0x20)

        # Global
        """
        if leds_dict["fire"]:
            self.log.debug("LCD: FIRE")

        if leds_dict["defect"]:
            self.log.debug("LCD: Defect")

        if leds_dict["normal"]:
            self.log.debug("LCD: Normal")

        # EVAC / Silence
        if leds_dict["silence_alarms"]:
            self.log.debug("LCD: Silence Alarms Active")

        if leds_dict["evacuate"]:
            self.log.debug("LCD: Evacuate operated")

        # LCD only
        if leds_dict["device_isolated"]:
            self.log.debug("LCD: Device Isolated")

        if leds_dict["psu_defect"]:
            self.log.debug("LCD: PSU Defect")

        if leds_dict["door_holder_isolate"]:
            self.log.debug("LCD: Door Holder Isolate")

        if leds_dict["aux_isolate"]:
            self.log.debug("LCD: Aux Isolate")

        if leds_dict["walk_test"]:
            self.log.debug("LCD: Walk Test")
        """

        for callback in self._lcd_callbacks:
            try:
                # self.log.debug("Triggering LCD callback {}".format(i))
                callback(self.get_lcd_text(1), self.get_lcd_text(2))
            except Exception as e:
                self.log.error("Unable to process LCD callback - {}".format(e))

        for led_name in self._lcd_led_names:
            callbacks = self._led_callbacks[led_name]
            for callback in callbacks:
                try:
                    # self.log.debug("Triggering LCD callback {}".format(led_name))
                    callback(self.decoded_data["lcd"]["leds"][led_name])
                except Exception as e:
                    self.log.error(
                        "Unable to process LCD callback {}  - {}".format(led_name, e)
                    )

    def test_connection(self, ip=None, port=None):
        if ip is None and port is None:
            ip = self._host_ip
            port = self._host_port

        self.log.info("Testing connection to TCP://{0}:{1}".format(ip, port))

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(self._timeout)
                s.connect((ip, port))
                s.close()
                self.log.info("Connection Successful")
                return True

        except Exception as e:
            self.log.error("Connection Test Failed")
            self.log.error(e)
        return False

    def get_lcd_text(self, line: int):
        if line < 1 or line > 2:
            return None
        return self.decoded_data["lcd"]["line_{}".format(line)]["display_text"]

    def get_led_state(self, led_id: int):
        if led_id < 0 or led_id > 256:
            return None
        return self.decoded_data["led"]["addressable_leds"][led_id]

    def get_special_led_state(self, led_type):
        if led_type not in self.decoded_data["lcd"]["leds"]:
            return None
        return self.decoded_data["lcd"]["leds"][led_type]

    def _setup_logging(self):
        # Setup logging
        self.log = logging.getLogger(self.__class__.__name__)
        self.log.setLevel(logging.DEBUG)

        # Create handlers
        c_handler = logging.StreamHandler()
        c_handler.setFormatter(CustomFormatter())

        # Create formatters and add it to handlers
        formatter_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

        # Add handlers to the logger
        self.log.addHandler(c_handler)
        self.log.info("Logging Setup!")

    def register_special_led_callback(self, led_type, function):
        if led_type not in self._led_callbacks:
            return False
        self._led_callbacks[led_type].append(function)
        return True
