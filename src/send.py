import serial
import time
import re
import math

# Configuration
SERIAL_PORT = '/dev/tty.usbmodem1101'  # Replace with your Arduino's port
BAUD_RATE = 115200  # Must match the baud rate in your Arduino code
GCODE_FILE = "temp/ugly.gcode"

# Extract X, Y, Z coordinates from G-code lines
def extract_coordinates(line):
    match_x = re.search(r'X([-+]?[0-9]*\.?[0-9]+)', line)
    match_y = re.search(r'Y([-+]?[0-9]*\.?[0-9]+)', line)
    match_z = re.search(r'Z([-+]?[0-9]*\.?[0-9]+)', line)

    x = float(match_x.group(1)) if match_x else None
    y = float(match_y.group(1)) if match_y else None
    z = float(match_z.group(1)) if match_z else None
    return x, y, z

# Calculate Euclidean distance
def calculate_distance(p1, p2):
    x1, y1, z1 = p1
    x2, y2, z2 = p2
    dx = (x2 - x1) if x1 is not None and x2 is not None else 0
    dy = (y2 - y1) if y1 is not None and y2 is not None else 0
    dz = (z2 - z1) if z1 is not None and z2 is not None else 0
    return math.sqrt(dx**2 + dy**2 + dz**2)

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)  # Wait for connection to establish
    print(f"Connected to {SERIAL_PORT}")

    # Read G-code file
    with open(GCODE_FILE, 'r') as file:
        gcode_lines = [line.strip() for line in file if line.strip() and not line.startswith(';')]

    # Track the previous point
    prev_point = (0, 0, 0)

    # Send each G-code line with proportional delay
    for gcode_line in gcode_lines:
        ser.write((gcode_line + '\n').encode('utf-8'))
        print(f"Sent: {gcode_line}")

        # Calculate delay based on movement distance
        current_point = extract_coordinates(gcode_line)
        if any(coord is not None for coord in current_point):
            distance = calculate_distance(prev_point, current_point)
            delay = max(1, distance / 12)  # Scale delay; adjust divisor to tune speed
            print(f"Distance: {distance:.2f}, Delay: {delay:.2f}s")
            time.sleep(delay)
            prev_point = current_point  # Update previous point

    print("G-code file transmission complete.")
    ser.close()

except serial.SerialException as e:
    print(f"Error: {e}")
except FileNotFoundError:
    print(f"Error: File '{GCODE_FILE}' not found.")
except KeyboardInterrupt:
    print("\nExiting...")
