import os
import curses
import signal
from collections import deque

cpu_history = deque([0] * 50, maxlen=50)
ram_history = deque([0] * 50, maxlen=50)
swap_history = deque([0] * 50, maxlen=50)

last_cpu_data = None
PAGE_SIZE = os.sysconf('SC_PAGE_SIZE') 

def get_cpu_usage():
    global last_cpu_data
    try:
        with open('/proc/stat', 'r') as f:
            line = f.readline()
    except FileNotFoundError:
        return 0.0
    parts = list(map(float, line.split()[1:]))
    idle = parts[3] + parts[4]
    total = sum(parts)
    if last_cpu_data is None:
        last_cpu_data = (idle, total)
        return 0.0
    prev_idle, prev_total = last_cpu_data
    total_delta = total - prev_total
    idle_delta = idle - prev_idle
    last_cpu_data = (idle, total)
    if total_delta == 0: return 0.0
    return max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / total_delta)))

def get_mem_usage():
    meminfo = {}
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                parts = line.split(':')
                if len(parts) == 2: meminfo[parts[0].strip()] = int(parts[1].split()[0])
    except FileNotFoundError:
        return (0.0, 0, 0), (0.0, 0, 0)
    mem_total = meminfo.get('MemTotal', 1)
    mem_avail = meminfo.get('MemAvailable', meminfo.get('MemFree', 0))
    ram_used = mem_total - mem_avail
    ram_pct = (ram_used / mem_total) * 100.0
    swap_total = meminfo.get('SwapTotal', 1) 
    swap_free = meminfo.get('SwapFree', swap_total)
    swap_used = swap_total - swap_free
    swap_pct = 0.0 if swap_total <= 1 else (swap_used / swap_total) * 100.0
    return (ram_pct, ram_used, mem_total), (swap_pct, swap_used, swap_total)

def get_disk_usage(path='/'):
    try:
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize 
        used = total - free
        pct = (used / total) * 100.0 if total > 0 else 0.0
        return pct, used, total
    except Exception:
        return 0.0, 0, 0

def get_top_processes():
    processes = []
    for pid in os.listdir('/proc'):
        if pid.isdigit():
            try:
                with open(f'/proc/{pid}/statm', 'r') as f:
                    rss_pages = int(f.readline().split()[1])
                    rss_mb = (rss_pages * PAGE_SIZE) / (1024 * 1024)
                with open(f'/proc/{pid}/comm', 'r') as f:
                    cmd = f.readline().strip()
                processes.append({'pid': pid, 'cmd': cmd, 'ram_mb': rss_mb})
            except (FileNotFoundError, PermissionError, IndexError):
                continue
    processes.sort(key=lambda x: x['ram_mb'], reverse=True)
    return processes[:5]

def draw_sparkline(stdscr, y, x, label, pct, history):
    stdscr.addstr(y, x, f"{label:<4} [{pct:>5.1f}%]", curses.color_pair(1) | curses.A_BOLD)
    graph_x = x + 15
    spark_chars = [' ', '▂', '▃', '▄', '▅', '▆', '▇', '█']
    for val in history:
        char_idx = min(7, int((val / 100.0) * 8))
        color = 2 
        if val > 60: color = 3 
        if val > 85: color = 4 
        stdscr.addstr(y, graph_x, spark_chars[char_idx], curses.color_pair(color))
        graph_x += 1

def draw_capacity_bar(stdscr, y, x, label, pct, details_str=""):
    title = f"{label:<4} Usage: {pct:>5.1f}%"
    if details_str: title += f" [{details_str}]"
    stdscr.addstr(y, x, title, curses.color_pair(1) | curses.A_BOLD)
    bar_width = 50
    filled_len = int((pct / 100.0) * bar_width)
    bar_str = "█" * filled_len + "░" * (bar_width - filled_len)
    color = 2
    if pct > 60: color = 3
    if pct > 85: color = 4
    stdscr.addstr(y + 1, x, f"[{bar_str}]", curses.color_pair(color))

def draw_dashboard(stdscr):
    curses.curs_set(0)
    stdscr.timeout(1000) 
    
    stdscr.keypad(True) 
    
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_RED, -1)

    selected_index = 0 
    message = ""       

    while True:
        
        key = stdscr.getch()
        
        
        top_procs = get_top_processes()
        
        if key in [ord('q'), ord('Q')]:
            break
        elif key == curses.KEY_UP:
            selected_index = max(0, selected_index - 1)
            message = "" 
        elif key == curses.KEY_DOWN:
            selected_index = min(len(top_procs) - 1, selected_index + 1)
            message = ""
        elif key in [ord('k'), ord('K')] and top_procs:
            
            target_pid = int(top_procs[selected_index]['pid'])
            target_name = top_procs[selected_index]['cmd']
            try:
                os.kill(target_pid, signal.SIGTERM) 
                message = f"Sent termination signal to {target_name} (PID: {target_pid})"
            except PermissionError:
                message = f"Permission denied to kill {target_name}. Try running with sudo."
            except ProcessLookupError:
                message = f"Process {target_name} already ended."

        
        cpu_pct = get_cpu_usage()
        ram_data, swap_data = get_mem_usage()
        disk_pct, disk_used, disk_total = get_disk_usage()
        
        ram_pct, ram_used, ram_total = ram_data
        swap_pct, swap_used, swap_total = swap_data
        
        cpu_history.append(cpu_pct)
        ram_history.append(ram_pct)
        swap_history.append(swap_pct)
        
        stdscr.erase()
        
        try:
            
            stdscr.addstr(1, 2, "=== SYSTEM MASTER DASHBOARD ===", curses.A_BOLD)
            stdscr.addstr(1, 40, "Arrows: Select | 'k': Kill | 'q': Quit", curses.A_DIM)

            
            draw_sparkline(stdscr, 3, 2, "CPU", cpu_pct, cpu_history)
            draw_sparkline(stdscr, 4, 2, "RAM", ram_pct, ram_history)
            draw_sparkline(stdscr, 5, 2, "SWAP", swap_pct, swap_history)
            stdscr.addstr(6, 17, "└" + "─" * 50, curses.A_DIM)

            
            draw_capacity_bar(stdscr, 8, 2, "CPU", cpu_pct)
            ram_str = f"{ram_used/(1024**2):.1f} GB / {ram_total/(1024**2):.1f} GB"
            draw_capacity_bar(stdscr, 10, 2, "RAM", ram_pct, ram_str)
            disk_str = f"{disk_used/(1024**3):.1f} GB / {disk_total/(1024**3):.1f} GB"
            draw_capacity_bar(stdscr, 12, 2, "MAIN", disk_pct, disk_str)

            stdscr.addstr(15, 2, "TOP 5 PROCESSES (By Memory):", curses.color_pair(1) | curses.A_BOLD)
            stdscr.addstr(16, 2, f"{'PID':<8} {'RAM (MB)':<10} {'COMMAND':<30}", curses.A_UNDERLINE)
            
            row = 17
            for i, p in enumerate(top_procs):
                cmd = p['cmd'][:30] + "..." if len(p['cmd']) > 30 else p['cmd']
                row_text = f"{p['pid']:<8} {p['ram_mb']:<10.1f} {cmd:<30}"
                
                if i == selected_index:
                    stdscr.addstr(row, 2, row_text, curses.A_REVERSE)
                else:
                    stdscr.addstr(row, 2, row_text)
                row += 1

            if message:
                msg_color = curses.color_pair(4) if "Permission" in message else curses.color_pair(3)
                stdscr.addstr(23, 2, message, msg_color)

        except curses.error:
            stdscr.clear()
            stdscr.addstr(1, 1, "Terminal too small to draw everything! Please resize.", curses.color_pair(4))
            
        stdscr.refresh()

if __name__ == '__main__':
    curses.wrapper(draw_dashboard)
