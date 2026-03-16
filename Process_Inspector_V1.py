import os

def get_process_info(pid):
    """Fetches status and command line info for a given PID."""
    process_info = {
        'pid': pid,
        'state': 'Unknown',
        'cmd': 'Unknown'
    }
    
    try:
        # 1. Get the process state from /proc/[pid]/status
        with open(f'/proc/{pid}/status', 'r') as status_file:
            for line in status_file:
                if line.startswith('State:'):
                    # Example line: "State:  S (sleeping)"
                    process_info['state'] = line.split(':', 1)[1].strip()
                    break

        # 2. Get the command used to start the process
        with open(f'/proc/{pid}/cmdline', 'r') as cmd_file:
            # cmdline arguments are separated by null bytes (\x00)
            cmdline = cmd_file.read().replace('\x00', ' ').strip()
            
        # If cmdline is empty (often true for kernel threads), fall back to 'comm'
        if not cmdline:
            with open(f'/proc/{pid}/comm', 'r') as comm_file:
                # Wrap in brackets to denote it's a kernel thread/internal process
                process_info['cmd'] = f"[{comm_file.read().strip()}]"
        else:
            process_info['cmd'] = cmdline

    except (FileNotFoundError, PermissionError):
        return None
        
    return process_info

def get_all_processes():
    """Scans the /proc directory for all valid PIDs."""
    processes = []
    
    # Iterate through everything in the /proc directory
    for item in os.listdir('/proc'):
        if item.isdigit():
            info = get_process_info(item)
            if info:
                processes.append(info)
                
    return processes

def main():
    print(f"{'PID':<8} {'STATE':<20} {'COMMAND'}")
    print("-" * 80)
    
    processes = get_all_processes()
    
    # Sort processes by PID numerically before printing
    processes.sort(key=lambda x: int(x['pid']))
    
    for p in processes:
        # Truncate the command line to keep the output clean
        cmd_display = p['cmd'][:50] + '...' if len(p['cmd']) > 50 else p['cmd']
        print(f"{p['pid']:<8} {p['state']:<20} {cmd_display}")

if __name__ == '__main__':
    main()
