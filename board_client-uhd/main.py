#!/usr/bin/env python3
"""
UnicornHD Wrangler (rPi/GPIO version) - Streaming Memory Debug
"""

import sys
import os
import gc
import time

print("Starting UnicornHD Wrangler...")

# Import compatibility layer first
import uhd

# Now we can import everything exactly as in the MicroPython version!
import uasyncio  # Works thanks to compatibility layer!
from uw.config import config as uw_config  # Original config class
from uw.logger import setup_logging, log
from uhd import graphics, gu, set_brightness, config, state, MQTTServicePi

print("Importing memory monitor...")
from uhd.memory_monitor import memory_monitor
from uhd.memory_debug import print_memory_summary, find_large_objects, debug_streaming_objects
print("Memory monitor imported")

# Import animation service - this should work mostly unchanged
from uw.animation_service import get_animation_list
from uw.transitions import melt_off, countdown

# Emergency memory threshold (MB)
EMERGENCY_MEMORY_THRESHOLD = 100  # Lower threshold for streaming

async def run_animation_with_timeout(animation_name, max_runtime_s):
    """Run animation with streaming-specific memory debugging"""
    import importlib
    
    print(f"[Animation] Starting: {animation_name} (max {max_runtime_s}s)")
    memory_before = memory_monitor.check_memory(force_gc=True)
    
    # Debug memory before animation
    if animation_name == "streaming":
        print(f"[Streaming] Memory before: {memory_before:.1f}MB")
        #print_memory_summary()
        #debug_streaming_objects()
    
    state.animation_active = True
    
    module_path = f"animations.{animation_name}"
    log(f"Loading animation: {animation_name}", "INFO")
    
    if state.mqtt_service and state.mqtt_service.connected:
        state.mqtt_service.publish_status({
            "animation": animation_name
        })
    
    mod = None
    animation_task = None
    timeout_task = None
    
    try:
        # Import and reload if necessary
        if module_path in sys.modules:
            importlib.reload(sys.modules[module_path])
        
        mod = importlib.import_module(module_path)
        anim_func = getattr(mod, "run")
        
        # Create animation task
        animation_task = uasyncio.create_task(
            anim_func(graphics, gu, state, state.interrupt_event)
        )
        
        # Create timeout task with shorter timeout for streaming
        #timeout_duration = 5 if animation_name == "streaming" else max_runtime_s
        timeout_duration = max_runtime_s
        
        async def timeout_handler():
            await uasyncio.sleep(timeout_duration)
            print(f"[Animation] {animation_name} timeout after {timeout_duration}s - forcing interrupt")
            state.interrupt_event.set()
            return "timeout"
        
        timeout_task = uasyncio.create_task(timeout_handler())
        
        # Wait for either animation completion or timeout
        done, pending = await uasyncio.wait(
            [animation_task, timeout_task],
            return_when=uasyncio.FIRST_COMPLETED
        )
        
        # Cancel any remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except uasyncio.CancelledError:
                pass
        
        # Check which task completed
        for task in done:
            if task == timeout_task:
                result = task.result()
                if result == "timeout":
                    print(f"[Animation] {animation_name} timed out")
                    # Force cancel the animation
                    if not animation_task.done():
                        animation_task.cancel()
                        try:
                            await animation_task
                        except uasyncio.CancelledError:
                            print(f"[Animation] {animation_name} cancelled due to timeout")
            elif task == animation_task:
                print(f"[Animation] {animation_name} completed normally")
        
    except Exception as e:
        log(f"Animation {animation_name} error: {e}", "ERROR")
        print(f"[Animation] Exception in {animation_name}: {e}")
    finally:
        state.animation_active = False
        
        # Cleanup any remaining tasks
        if animation_task and not animation_task.done():
            animation_task.cancel()
        if timeout_task and not timeout_task.done():
            timeout_task.cancel()
        
        # Comprehensive cleanup
        if mod is not None:
            del mod
        
        # Clear graphics buffer
        graphics.clear()
        graphics.set_pen((0, 0, 0))
        graphics.cleanup_text_cache()
        
        # Clear the display
        gu.clear_display()
        
        # Streaming-specific cleanup
        if animation_name == "streaming":
            print("[Streaming] Performing streaming-specific cleanup...")
            
            # Force cleanup of streaming state
            if hasattr(state, 'stream_frames_rendered'):
                state.stream_frames_rendered = 0
            if hasattr(state, 'stream_current_name'):
                state.stream_current_name = None
            if hasattr(state, 'stream_total_frames'):
                state.stream_total_frames = 0
            
            # Clear any cached frames or buffers
            if hasattr(state, '_cached_frames'):
                if state._cached_frames:
                    state._cached_frames.clear()
                    del state._cached_frames
                state._cached_frames = None
            
            # Aggressive garbage collection for streaming
            for i in range(10):
                collected = gc.collect()
                print(f"[Streaming] Cleanup GC pass {i+1}: {collected} objects")
                if collected == 0:
                    break
        
        # Force garbage collection
        memory_after = memory_monitor.check_memory(force_gc=True)
        
        memory_used = memory_after - memory_before
        print(f"[Animation] {animation_name} memory delta: {memory_used:+.1f}MB")
        
        # Debug memory after streaming
        if animation_name == "streaming":
            print(f"[Streaming] Memory after: {memory_after:.1f}MB")
            #debug_streaming_objects()
            #find_large_objects(0.5)  # Find objects > 0.5MB
        
        # Emergency cleanup if memory is too high
        if memory_after > EMERGENCY_MEMORY_THRESHOLD:
            print(f"[Animation] Memory over threshold ({memory_after:.1f}MB > {EMERGENCY_MEMORY_THRESHOLD}MB)")
            memory_monitor.emergency_cleanup()

async def handle_text_interrupt():
    """Handle text messages with memory management"""
    if state.interrupt_event.is_set():
        state.interrupt_event.clear()
        if state.text_message:
            print(f"[Text] Displaying: {state.text_message}")
            memory_before = memory_monitor.check_memory()
            
            from animations.text_scroller import run as run_text_scroller
            
            # Run text with timeout too
            try:
                await uasyncio.wait_for(
                    run_text_scroller(
                        graphics, gu, state, state.interrupt_event,
                        state.text_message, state.text_repeat_count
                    ),
                    timeout=30  # 30 second timeout for text
                )
            except uasyncio.TimeoutError:
                print("[Text] Text scroller timed out")
                
            state.text_message = None
            
            # Cleanup after text scrolling
            graphics.cleanup_text_cache()
            gu.clear_display()
            memory_after = memory_monitor.check_memory(force_gc=True)
            
            memory_used = memory_after - memory_before
            print(f"[Text] Memory delta: {memory_used:+.1f}MB")
            
            return True
    return False

async def main():
    """Main loop with streaming memory management"""
    print("Setting up main loop...")
    
    # Setup
    setup_logging(config.get("general", "debug", False))
    set_brightness(config.get("general", "brightness", 0.5))
    
    # Check initial memory
    #initial_memory = memory_monitor.check_memory()
    #print(f"Initial memory after setup: {initial_memory:.1f}MB")
    #print_memory_summary()
    
    # MQTT setup
    if config.get("mqtt", "enable", False):
        mqtt_service = MQTTServicePi(config, state)
        state.mqtt_service = mqtt_service
        uasyncio.create_task(mqtt_service.loop())
    else:
        log("MQTT disabled.", "INFO")
    
    # Get animations
    animation_list = get_animation_list()
    sequence = list(config.get("general", "sequence", ["*"]))
    
    log(f"Starting main loop with {len(animation_list)} animations", "INFO")
    print(f"Animation list: {animation_list}")
    
    # Main loop
    loop_iteration = 0
    
    while True:
        loop_iteration += 1
        current_time = time.time()
        
        # Check memory every iteration
        current_memory = memory_monitor.check_memory()
        
        # Emergency memory check
        if current_memory > EMERGENCY_MEMORY_THRESHOLD:
            print(f"\n=== Loop Iteration {loop_iteration} ===")
            print(f"EMERGENCY: Memory usage {current_memory:.1f}MB exceeds threshold!")
            print_memory_summary()
            find_large_objects(1.0)
            memory_monitor.emergency_cleanup()
            
            # Check if cleanup helped
            post_cleanup_memory = memory_monitor.check_memory()
            if post_cleanup_memory > EMERGENCY_MEMORY_THRESHOLD * 0.9:  # Still too high
                print("CRITICAL: Memory cleanup insufficient.")
                print("FORCING RESTART to prevent OOM...")
                import os
                os._exit(1)  # Force restart

            # Post-animation cleanup
            final_memory = memory_monitor.check_memory(force_gc=True)
            print(f"=== End Loop {loop_iteration}: {final_memory:.1f}MB ===\n")

        if not state.display_on:
            await melt_off()
            while not state.display_on:
                await uasyncio.sleep(0.2)
            await countdown()
        
        if await handle_text_interrupt():
            continue
        
        # Run next in sequence
        job = sequence.pop(0)
        sequence.append(job)  # Rotate
        
        max_runtime = config.get("general", "max_runtime_s", 30)
        print(f"[Main] Next job: {job} (max runtime: {max_runtime}s)")
        
        if state.next_animation:
            animation = state.next_animation
            await run_animation_with_timeout(animation, max_runtime)
        elif job == "*":
            import random
            animation = random.choice(animation_list)
            print(f"[Main] Random animation selected: {animation}")
            await run_animation_with_timeout(animation, max_runtime)
        elif job in animation_list:
            print(f"[Main] Running specific animation: {job}")
            await run_animation_with_timeout(job, max_runtime)
        else:
            log(f"Unknown sequence job: {job}", "WARN")
            print(f"[Main] Unknown job: {job}, available: {animation_list}")
        
if __name__ == "__main__":
    try:
        print("Starting asyncio main loop...")
        uasyncio.run(main())
    except KeyboardInterrupt:
        log("Shutting down...")
        memory_monitor.emergency_cleanup()
        import unicornhathd
        unicornhathd.off()
        unicornhathd.clear()

