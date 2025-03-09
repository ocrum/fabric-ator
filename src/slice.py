import matplotlib
# matplotlib.use('Agg') # comment this out if you want the cool visualization
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
import math
from pathlib import Path
import ezdxf

# Print bed dimensions
PRINT_BED_X = 200
PRINT_BED_Y = 200


def combine_segments_to_polygon(segments, tol=1e-6):
    """
    Combines a list of line segments or polylines into a continuous polygon.

    Parameters:
      segments: List of segments or polylines, where each entry is a list of points.
      tol:      Tolerance for considering two points equal.

    Returns:
      A list of points [(x, y), (x, y), ...] that form the polygon.
      If the segments can't be completely connected, it returns as much as it could.
    """
    def points_equal(p1, p2):
        return abs(p1[0] - p2[0]) < tol and abs(p1[1] - p2[1]) < tol

    if not segments:
        return []

    segs = segments.copy()
    # Start with the first segment as the beginning of the polygon.
    polygon = segs.pop(0)

    # Continue connecting segments until no connecting segment is found.
    while segs:
        current_point = polygon[-1]  # End of current polyline
        found = False
        for i, seg in enumerate(segs):
            if points_equal(current_point, seg[0]):  # Connect at start
                polygon.extend(seg[1:])
                found = True
            elif points_equal(current_point, seg[-1]):  # Connect at end (reverse needed)
                polygon.extend(reversed(seg[:-1]))
                found = True
            elif points_equal(polygon[0], seg[0]):  # Connect start-to-start
                polygon = list(reversed(seg)) + polygon[1:]
                found = True
            elif points_equal(polygon[0], seg[-1]):  # Connect start-to-end
                polygon = seg[:-1] + polygon
                found = True

            if found:
                segs.pop(i)
                break

        if not found:
            # No segment connects to the current endpoints; break out.
            break

    return polygon

def combine_lines_to_polygon(lines):
    """
    Combines a list of line segments into a single continuous polygon path.

    Parameters:
      lines - List of line segments (each as [(x1, y1), (x2, y2)])

    Returns:
      A list of points representing the combined polygon path.
    """
    # Create a mapping of endpoints to segment pairs
    point_map = {}
    for start, end in lines:
        point_map.setdefault(start, []).append(end)
        point_map.setdefault(end, []).append(start)

    # Start from an arbitrary point and build the path
    start_point = lines[0][0]
    path = [start_point]

    current_point = start_point
    while True:
        next_points = point_map.get(current_point)
        if not next_points:
            break  # No valid connections
        next_point = next_points.pop()
        point_map[next_point].remove(current_point)  # Remove the reverse connection
        if next_point == start_point:
            path.append(next_point)  # Close the loop
            break
        path.append(next_point)
        current_point = next_point

    return path

def read_dxf_polygon(file_path):
    """
    Reads a DXF file and extracts the outer boundary polygon points.

    Parameters:
      file_path - Path to the DXF file.

    Returns:
      A list of points [(x, y), (x, y), ...] representing the polygon shape.
    """
    doc = ezdxf.readfile(file_path)
    msp = doc.modelspace()

    lines = []


    for entity in msp:
        print(entity.dxftype())
        if entity.dxftype() == 'LWPOLYLINE':
            points = [(point[0], point[1]) for point in entity.get_points()]
            if entity.is_closed:
                return points
        elif entity.dxftype() == 'POLYLINE':
            points = [(point[0], point[1]) for point in entity.points]
            if entity.is_closed:
                return points
        elif entity.dxftype() == 'LINE':
            points = [(entity.dxf.start.x, entity.dxf.start.y),
                      (entity.dxf.end.x, entity.dxf.end.y)]
            lines.append(points)
        elif entity.dxftype() in 'SPLINE':
            spline = ezdxf.math.BSpline(entity.control_points)
            points = list(spline.flattening(distance=0.1))
            lines.append([(point[0], point[1]) for point in points])
        elif entity.dxftype() in ['CIRCLE', 'ARC']:
            points = list(entity.flattening(sagitta=0.05))
            lines.append([(point[0], point[1]) for point in points])
        elif entity.dxftype() == 'ELLIPSE':
            points = list(entity.flattening(distance=0.1))
            lines.append([(point[0], point[1]) for point in points])

    if lines:
        return combine_segments_to_polygon(lines)

    raise ValueError("No valid polygon shapes found in DXF file.")

def scale_polygon(polygon, scale_factor):
    """
    Scales a polygon by a given factor.

    Parameters:
      polygon - List of (x, y) tuples representing the polygon points.
      scale_factor - The factor to scale the polygon by (e.g., 25.4 for mm to in).

    Returns:
      A new list of points representing the scaled polygon.
    """
    return [(x * scale_factor, y * scale_factor) for x, y in polygon]

def center_polygon(polygon, bed_width, bed_height):
    """
    Centers a closed polygon on the center of the given print bed dimensions.

    Parameters:
      polygon - List of (x, y) tuples representing the polygon points.
      bed_width - Width of the print bed.
      bed_height - Height of the print bed.

    Returns:
      A new list of points representing the centered polygon.
    """
    # Find polygon bounding box
    min_x = min(point[0] for point in polygon)
    max_x = max(point[0] for point in polygon)
    min_y = min(point[1] for point in polygon)
    max_y = max(point[1] for point in polygon)

    # Calculate polygon's current center
    poly_center_x = (min_x + max_x) / 2
    poly_center_y = (min_y + max_y) / 2

    # Calculate print bed center
    bed_center_x = bed_width / 2
    bed_center_y = bed_height / 2

    # Calculate translation values
    offset_x = bed_center_x - poly_center_x
    offset_y = bed_center_y - poly_center_y

    # Translate polygon points
    centered_polygon = [(x + offset_x, y + offset_y) for x, y in polygon]

    return centered_polygon

def generate_perimeter_path(polygon):
    """
    Converts a closed polygon into a command array representing its perimeter.

    Parameters:
      polygon - List of (x, y) tuples representing the polygon points.
                The polygon should already be closed (first and last points identical).

    Returns:
      A list of commands in the form (x, y, state)
      where state 0 means “move to” (no extrusion) and state 1 means “draw to” (extrude).
    """
    # Ensure the polygon is closed
    if polygon[0] != polygon[-1]:
        polygon.append(polygon[0])

    cmd_arr = [(polygon[0][0], polygon[0][1], 0)]  # Start at the first point without extruding

    # Iterate through the polygon points to build the path
    for point in polygon[1:]:
        cmd_arr.append((point[0], point[1], 1))  # Draw each segment

    return cmd_arr

def get_line_polygon_intersections(polygon, A, B, C, epsilon=1e-6):
    """
    Given a line in the form A*x + B*y + C = 0 and a polygon (list of (x, y) tuples),
    return a list of intersection points (x, y) between the line and the polygon’s edges.
    """
    intersections = []
    n = len(polygon)
    for i in range(n):
        p1 = polygon[i]
        p2 = polygon[(i + 1) % n]  # ensure closed polygon
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        denom = A * dx + B * dy
        if abs(denom) < epsilon:
            continue  # edge is parallel to the line
        t = -(A * p1[0] + B * p1[1] + C) / denom
        if 0 <= t <= 1:
            x_int = p1[0] + t * dx
            y_int = p1[1] + t * dy
            intersections.append((x_int, y_int))
    return intersections

def generate_cross_hatching_path(polygon, spacing):
    """
    Generate a cross-hatching pattern for a closed polygon.

    Parameters:
      polygon - a list of (x, y) tuples defining a closed path (the first and last point
                should be the same; if not, the function will close it automatically)
      spacing - the perpendicular distance between hatch lines.

    Returns:
      A list of commands in the form (x, y, state) where state 0 means “move to” (no extrusion)
      and state 1 means “draw to” (with extrusion).

    The function creates two sets of hatch lines:
      • For lines with slope -1 (diagonals running down/right), using the line equation:
          x + y = c
      • For lines with slope 1 (diagonals running up/right), using the equation:
          y - x = c

    For each hatch line the intersections with the polygon are computed and sorted, and pairs
    of intersections are used as start/end points for drawing.
    """
    # Ensure the polygon is closed.
    if polygon[0] != polygon[-1]:
        polygon = polygon + [polygon[0]]

    cmd_arr = []

    # --- Hatch set 1: lines of slope -1 (x + y = c) ---
    # Determine the range of c-values from the polygon vertices.
    c_values = [pt[0] + pt[1] for pt in polygon]
    c_min = min(c_values)
    c_max = max(c_values)
    # The perpendicular distance between lines y = -x + c is |delta_c|/√2.
    # To have a spacing of "spacing" we step by spacing*√2.
    step = spacing * math.sqrt(2)

    c = c_min
    while c <= c_max:
        # For the line x+y = c, we use A = 1, B = 1, C = -c.
        intersections = get_line_polygon_intersections(polygon, 1, 1, -c)
        if len(intersections) >= 2:
            # Sort intersections along the line (using x as a proxy).
            intersections.sort(key=lambda p: p[0])
            # For multiple intersections (in concave regions) pair them sequentially.
            for i in range(0, len(intersections) - 1, 2):
                start = intersections[i]
                end = intersections[i + 1]
                cmd_arr.append((start[0], start[1], 0))  # move without extruding
                cmd_arr.append((end[0], end[1], 1))      # draw (extrude)
        c += step

    # --- Hatch set 2: lines of slope 1 (y - x = c) ---
    c_values2 = [pt[1] - pt[0] for pt in polygon]
    c_min2 = min(c_values2)
    c_max2 = max(c_values2)

    c = c_min2
    while c <= c_max2:
        # For the line y - x = c, rewrite as -x + y = c; use A = -1, B = 1, C = -c.
        intersections = get_line_polygon_intersections(polygon, -1, 1, -c)
        if len(intersections) >= 2:
            intersections.sort(key=lambda p: p[0])
            for i in range(0, len(intersections) - 1, 2):
                start = intersections[i]
                end = intersections[i + 1]
                cmd_arr.append((start[0], start[1], 0))
                cmd_arr.append((end[0], end[1], 1))
        c += step

    return cmd_arr

def convert_to_gcode(coordinates):
    commands = []
    prev_x, prev_y, prev_e = coordinates[0]
    commands.append(f'G1 X{prev_x:.2f} Y{prev_y:.2f}')  # Initial travel move

    for x, y, e in coordinates[1:]:
        dist = math.sqrt((x - prev_x)**2 + (y - prev_y)**2)
        if e == 0:
            commands.append(f'G1 X{x:.2f} Y{y:.2f}')  # Travel move
        else:
            commands.append(f'G1 X{x:.2f} Y{y:.2f} E{dist / 10:.2f}')  # Extrusion move with E value
        prev_x, prev_y = x, y

    return commands

def visualize_interactive(cmds):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_aspect('equal', adjustable='box')

    # Draw print bed outline
    ax.plot([0, PRINT_BED_X, PRINT_BED_X, 0, 0],
            [0, 0, PRINT_BED_Y, PRINT_BED_Y, 0], 'k-', lw=2)

    extrusion_lines, = ax.plot([], [], 'b-', lw=2)
    travel_lines, = ax.plot([], [], 'g--', linewidth=1)
    extruder_dot, = ax.plot([], [], 'ro')  # Red dot for extruder head

    frame = len(cmds) - 1  # Start at the end of the operation

    def update(frame):
        extrusion_x, extrusion_y = [], []
        travel_x, travel_y = [], []

        curr_cmds = cmds[:frame + 1]

        prev_x, prev_y, prev_e = curr_cmds[0]
        curr_x, curr_y, curr_e = curr_cmds[-1]
        prev_type = 0 # 0 for travel, 1 for extrude

        for x, y, e in curr_cmds:
            if e == 0:
                if prev_type == 1: # if was previously extrude
                    extrusion_x.append(None)
                    extrusion_y.append(None)
                    travel_x.append(prev_x)
                    travel_y.append(prev_y)
                travel_x.append(x)
                travel_y.append(y)
                prev_type = 0
            else:
                if prev_type == 0:
                    travel_x.append(None)
                    travel_y.append(None)
                    extrusion_x.append(prev_x)
                    extrusion_y.append(prev_y)
                extrusion_x.append(x)
                extrusion_y.append(y)
                prev_type = 1

            prev_x, prev_y = x, y

        extrusion_lines.set_data(extrusion_x, extrusion_y)
        travel_lines.set_data(travel_x, travel_y)
        extruder_dot.set_data([curr_x], [curr_y])

        print(f"G1 X{curr_x} Y{curr_y} E{curr_e}")

    def on_key(event):
        nonlocal frame
        if event.key == 'right' and frame < len(cmds) - 1:
            frame += 1
        elif event.key == 'left' and frame > 0:
            frame -= 1
        slider.set_val(frame)  # Sync slider position with arrow key movement

    fig.canvas.mpl_connect('key_press_event', on_key)

    # Slider for interactive control
    ax_slider = plt.axes([0.25, 0.01, 0.5, 0.03], facecolor='lightgray')
    slider = Slider(ax_slider, 'Step', 0, len(cmds) - 1, valinit=len(cmds) - 1, valstep=1)

    def slider_update(val):
        nonlocal frame
        frame = int(slider.val)
        update(frame)
        fig.canvas.draw_idle()

    slider.on_changed(slider_update)

    ax.set_xlim(0, PRINT_BED_X)
    ax.set_ylim(0, PRINT_BED_Y)
    plt.title("Diagonal Cross-Hatching Animation")
    plt.show()

def export_visualization(cmds, output_image_path):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_aspect('equal', adjustable='box')

    extrusion_lines, = ax.plot([], [], 'b-', lw=2)
    travel_lines, = ax.plot([], [], 'g--', linewidth=1)
    extruder_dot, = ax.plot([], [], 'ro')  # Red dot for extruder head

    extrusion_x, extrusion_y = [], []
    travel_x, travel_y = [], []

    prev_x, prev_y, prev_e = cmds[0]
    curr_x, curr_y, curr_e = cmds[-1]
    prev_type = 0 # 0 for travel, 1 for extrude

    for x, y, e in cmds:
        if e == 0:
            if prev_type == 1: # if was previously extrude
                extrusion_x.append(None)
                extrusion_y.append(None)
                travel_x.append(prev_x)
                travel_y.append(prev_y)
            travel_x.append(x)
            travel_y.append(y)
            prev_type = 0
        else:
            if prev_type == 0:
                travel_x.append(None)
                travel_y.append(None)
                extrusion_x.append(prev_x)
                extrusion_y.append(prev_y)
            extrusion_x.append(x)
            extrusion_y.append(y)
            prev_type = 1

        prev_x, prev_y = x, y

    extrusion_lines.set_data(extrusion_x, extrusion_y)
    travel_lines.set_data(travel_x, travel_y)
    extruder_dot.set_data([curr_x], [curr_y])

    ax.set_xlim(0, PRINT_BED_X)
    ax.set_ylim(0, PRINT_BED_Y)
    plt.savefig(output_image_path)
    plt.close()

def slice_dxf(file_path, spacing=10, output_image_path='visualization.png', debug=False):
    path = (Path(__file__).parent / file_path).resolve()
    if not path.exists() or path.suffix.lower() != '.dxf':
        raise FileNotFoundError(f"Invalid DXF file: {path}")


    polygon = read_dxf_polygon(path)
    shape = center_polygon(polygon, PRINT_BED_X, PRINT_BED_Y)
    cmd_arr = generate_perimeter_path(shape)
    cmd_arr.extend(generate_cross_hatching_path(shape, spacing))

    gcode = convert_to_gcode(cmd_arr)

    if debug:
        visualize_interactive(cmd_arr)
    else:
        export_visualization(cmd_arr, output_image_path)

    return "\n".join(gcode)

if __name__ == '__main__':
    filename = '../data/square.dxf'
    output = slice_dxf(filename, debug=True)
    print(output)
