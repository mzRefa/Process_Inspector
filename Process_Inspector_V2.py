import os
import time
import curses
from collections import deque, Counter

cpu_history = deque([0] * 50, maxlen=50)
last_cpu_data = None

def get_cpu_usage():
    """Calculates CPU usage percentage by comparing /proc/stat over time."""
    global last_cpu_data
    
    try:
        with open('/proc/stat', 'r') as f:
            # The first line 'cpu' is the aggregate of all cores
            line = f.readline()
    except FileNotFoundError:
        return 0.0

    # Parse the numbers from the line
    parts = list(map(float, line.split()[1:]))
    
    # parts[3] is idle, parts[4] is iowait. Both count as "not busy"
    idle = parts[3] + parts[4]
    total = sum(parts)
    
    # If this is the first run, save the state and return 0
    if last_cpu_data is None:
        last_cpu_data = (idle, total)
        return 0.0
        
    prev_idle, prev_total = last_cpu_data
    
    # Calculate how much total time and idle time has passed
    total_delta = total - prev_total
    idle_delta = idle - prev_idle
    
    # Update our global state for the next tick
    last_cpu_data = (idle, total)
    
    if total_delta == 0: 
        return 0.0
        
    # Usage is 100% minus the percentage of time spent idle
    usage = 100.0 * (1.0 - idle_delta / total_delta)
    return max(0.0, min(100.0, usage))

def get_ram_usage():
    """Reads /proc/meminfo to calculate RAM usage percentage."""
    meminfo = {}
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    # Store values in Kilobytes
                    meminfo[parts[0].strip()] = int(parts[1].split()[0])
    except FileNotFoundError:
        return 0.0, 0, 0
        
    total = meminfo.get('MemTotal', 1)
    # MemAvailable is the most accurate metric for modern Linux kernels
    available = meminfo.get('MemAvailable', meminfo.get('MemFree', 0))
    
    used = total - available
    pct = (used / total) * 100.0
    
    # Return percentage, and GBs (converted from KB)
    return pct, used / (1024**2), total / (1024**2)

def get_process_summary():
    """Gets a quick count of process states."""
    states = []
    for item in os.listdir('/proc'):
        if item.isdigit():
            try:
                with open(f'/proc/{item}/status', 'r') as f:
                    for line in f:
                        if line.startswith('State:'):
                            states.append(line.split(':', 1)[1].strip()[:1])
                            break
            except (FileNotFoundError, PermissionError):
                continue
    counts = Counter(states)
    return len(states), counts.get('R', 0), counts.get('S', 0)

def draw_dashboard(stdscr):
    curses.curs_set(0)
    # Refresh every 1000ms (1 second)
    stdscr.timeout(1000)
    
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_RED, -1)

    spark_chars = [' ', '▂', '▃', '▄', '▅', '▆', '▇', '█']

    while True:
        if stdscr.getch() in [ord('q'), ord('Q')]:
            break

        # Gather data
        cpu_pct = get_cpu_usage()
        cpu_history.append(cpu_pct)
        
        ram_pct, ram_used, ram_total = get_ram_usage()
        total_procs, running, sleeping = get_process_summary()
        
        stdscr.erase()
        
        try:
            # --- HEADER ---
            stdscr.addstr(1, 2, "=== SYSTEM INSPECTOR ===", curses.A_BOLD)
            stdscr.addstr(1, 40, "Press 'q' to quit", curses.A_DIM)

            # --- CPU GRAPH SECTION ---
            stdscr.addstr(3, 2, f"CPU Usage: {cpu_pct:>5.1f}%", curses.color_pair(1) | curses.A_BOLD)
            
            # Draw the graph history
            graph_x = 2
            for val in cpu_history:
                # Map 0-100% to an index of 0-7 for our sparkline characters
                char_idx = min(7, int((val / 100.0) * 8))
                
                # Color code based on intensity
                color = 2 # Green
                if val > 50: color = 3 # Yellow
                if val > 85: color = 4 # Red
                
                stdscr.addstr(4, graph_x, spark_chars[char_idx], curses.color_pair(color))
                graph_x += 1
                
            # Draw an axis line underneath
            stdscr.addstr(5, 2, "└" + "─" * 50, curses.A_DIM)

            # --- RAM BAR CHART SECTION ---
            stdscr.addstr(7, 2, f"RAM Usage: {ram_pct:>5.1f}% [{ram_used:.1f} GB / {ram_total:.1f} GB]", curses.color_pair(1) | curses.A_BOLD)
            
            bar_width = 50
            filled_len = int((ram_pct / 100.0) * bar_width)
            
            # Create the bar string (e.g., "██████░░░░")
            bar_str = "█" * filled_len + "░" * (bar_width - filled_len)
            
            # Color code the bar based on usage
            ram_color = 2
            if ram_pct > 60: ram_color = 3
            if ram_pct > 85: ram_color = 4
            
            stdscr.addstr(8, 2, f"[{bar_str}]", curses.color_pair(ram_color))

            # --- PROCESS SUMMARY SECTION ---
            stdscr.addstr(10, 2, "PROCESSES:", curses.A_BOLD)
            stdscr.addstr(11, 2, f"Total Tasks : {total_procs}")
            stdscr.addstr(12, 2, f"Running (R) : {running}", curses.color_pair(2))
            stdscr.addstr(13, 2, f"Sleeping (S): {sleeping}", curses.color_pair(3))

        except curses.error:
            stdscr.clear()
            stdscr.addstr(1, 1, "Terminal too small!", curses.color_pair(4))
            
        stdscr.refresh()

if __name__ == '__main__':
    curses.wrapper(draw_dashboard)
