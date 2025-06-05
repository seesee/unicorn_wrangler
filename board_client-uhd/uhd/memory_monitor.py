"""
Memory monitoring utility - Reduced Logging
"""

import gc
import time
import sys

try:
    import psutil
    import os
    PSUTIL_AVAILABLE = True
    # print("✓ psutil available for memory monitoring") # Quieter init
except ImportError:
    PSUTIL_AVAILABLE = False
    print("✗ WARNING: psutil not available - memory monitoring will be limited. Run: pip install psutil")

class MemoryMonitor:
    def __init__(self):
        # print("Initializing MemoryMonitor...") # Quieter init
        
        if PSUTIL_AVAILABLE:
            try:
                self.process = psutil.Process(os.getpid())
                # print(f"✓ psutil process monitoring enabled for PID {os.getpid()}")
            except Exception as e:
                print(f"✗ WARNING: psutil process creation failed: {e}")
                self.process = None # Ensure process is None if init fails
        else:
            self.process = None
        
        self.last_memory = 0
        self.check_counter = 0
        self.max_memory = 0
        self.start_time = time.time()
        self.memory_history = [] # Keep for potential future debugging if needed
        self.last_gc_time = time.time()
        
        # print(f"MemoryMonitor initialized. psutil_available={PSUTIL_AVAILABLE}")
        
        if self.process:
            try:
                initial_memory = self.process.memory_info().rss / 1024 / 1024
                # print(f"Initial memory usage: {initial_memory:.1f}MB") # Quieter init
                self.last_memory = initial_memory
                self.max_memory = initial_memory
            except Exception:
                # print("Could not get initial memory reading") # Quieter init
                pass
    
    def check_memory(self, force_gc=False, emergency_threshold_mb=150):
        """Check current memory usage and optionally force garbage collection"""
        self.check_counter += 1
        current_time = time.time()
        
        if force_gc or (current_time - self.last_gc_time) > 60:  # GC every 60 seconds or if forced
            # print(f"[Memory] Forcing garbage collection (check #{self.check_counter})") # Optional debug
            collected = gc.collect()
            # if collected > 0: # Optional debug
            #     print(f"[Memory] GC collected {collected} objects")
            self.last_gc_time = current_time
        
        if not PSUTIL_AVAILABLE or not self.process:
            # print(f"[Memory] Check #{self.check_counter} - psutil unavailable") # Optional debug
            return 0 # Return 0 or some indicator that monitoring is off
        
        try:
            mem_info = self.process.memory_info()
            current_memory = mem_info.rss / 1024 / 1024  # MB
            
            self.memory_history.append((current_time, current_memory))
            if len(self.memory_history) > 20: # Keep a smaller history
                self.memory_history.pop(0)
            
            if current_memory > self.max_memory:
                self.max_memory = current_memory
            
            growth = current_memory - self.last_memory if self.last_memory > 0 else 0
            
            # Log only if significant growth or high usage (less frequent)
            if self.check_counter % 60 == 0: # Log stats every ~minute (if called every second)
                growth_rate = self._calculate_growth_rate()
                uptime = current_time - self.start_time
                print(f"[Memory Stats] Current: {current_memory:.1f}MB, Max: {self.max_memory:.1f}MB, Growth Rate: {growth_rate:.2f}MB/min, Uptime: {uptime/60:.1f}min")

            # Update last_memory more frequently for accurate growth calculation
            if self.check_counter % 5 == 0:
                 self.last_memory = current_memory

            # Critical Warnings (keep these)
            if current_memory > emergency_threshold_mb: # Use passed threshold
                print(f"[Memory] WARNING: High memory usage: {current_memory:.1f}MB (Threshold: {emergency_threshold_mb}MB)")
                self.emergency_cleanup() # Trigger cleanup if above threshold
                # Re-check memory after cleanup
                current_memory = self.process.memory_info().rss / 1024 / 1024
                print(f"[Memory] Memory after emergency cleanup: {current_memory:.1f}MB")


            # More subtle growth warning
            # growth_rate = self._calculate_growth_rate() # Calculate only if needed
            # if growth_rate > 5.0: # Example: 5MB/min is high
            #     print(f"[Memory] WARNING: High growth rate detected: {growth_rate:.2f}MB/min")

            return current_memory
            
        except Exception as e:
            # print(f"[Memory] Error checking memory: {e}") # Optional debug
            return self.last_memory # Return last known value or 0
    
    def _calculate_growth_rate(self):
        """Calculate memory growth rate in MB/minute"""
        if len(self.memory_history) < 2:
            return 0.0
        
        # Use a shorter window for more responsive rate
        readings_to_check = min(len(self.memory_history), 10)
        if readings_to_check < 2:
            return 0.0

        relevant_readings = self.memory_history[-readings_to_check:]
        
        time_diff = relevant_readings[-1][0] - relevant_readings[0][0]
        memory_diff = relevant_readings[-1][1] - relevant_readings[0][1]
        
        if time_diff <= 0: # Avoid division by zero
            return 0.0
        
        return (memory_diff / time_diff) * 60 # MB per minute
    
    def emergency_cleanup(self):
        """Emergency memory cleanup"""
        print("[Memory] EMERGENCY CLEANUP INITIATED")
        total_collected = 0
        for i in range(5): # Fewer passes for quicker cleanup
            collected = gc.collect()
            total_collected += collected
            # print(f"[Memory] Emergency GC pass {i+1}: {collected} objects") # Optional debug
            if collected == 0 and i > 0: # Stop if no objects collected in a pass
                break
            time.sleep(0.05) 
        print(f"[Memory] Emergency cleanup complete: {total_collected} objects collected.")
    
    def get_stats(self):
        """Get memory statistics (can be called less frequently if needed)"""
        if not PSUTIL_AVAILABLE or not self.process:
            return {"error": "psutil not available or process not initialized"}
        
        try:
            current_memory = self.process.memory_info().rss / 1024 / 1024
            uptime = time.time() - self.start_time
            
            return {
                "current_mb": current_memory,
                "max_mb": self.max_memory,
                "uptime_minutes": uptime / 60,
                "checks": self.check_counter,
                "growth_rate_mb_per_min": self._calculate_growth_rate(),
                "history_count": len(self.memory_history)
            }
        except Exception as e:
            return {"error": str(e)}

# Global instance
memory_monitor = MemoryMonitor()
