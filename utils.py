DEBUG_MODE = True  # Set to False to disable debug output

def debug_log(message, DEBUG_MODE=True):
    """Print debug message with timestamp if DEBUG_MODE is enabled"""
    if DEBUG_MODE:
        print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {message}")