"""
Advanced memory debugging tools
"""

import gc
import sys
from collections import defaultdict

def get_memory_summary():
    """Get a summary of objects in memory"""
    objects_by_type = defaultdict(int)
    total_objects = 0
    
    for obj in gc.get_objects():
        obj_type = type(obj).__name__
        objects_by_type[obj_type] += 1
        total_objects += 1
    
    return dict(objects_by_type), total_objects

def print_memory_summary():
    """Print a summary of memory usage"""
    objects_by_type, total = get_memory_summary()
    
    print(f"\n=== MEMORY SUMMARY ({total} total objects) ===")
    
    # Sort by count, show top 20
    sorted_types = sorted(objects_by_type.items(), key=lambda x: x[1], reverse=True)
    
    for obj_type, count in sorted_types[:20]:
        print(f"  {obj_type}: {count}")
    
    print("=" * 50)

def find_large_objects(min_size_mb=1):
    """Find objects larger than min_size_mb"""
    large_objects = []
    
    for obj in gc.get_objects():
        try:
            size = sys.getsizeof(obj)
            if size > min_size_mb * 1024 * 1024:  # Convert MB to bytes
                large_objects.append((type(obj).__name__, size / 1024 / 1024))
        except:
            pass  # Some objects don't support getsizeof
    
    if large_objects:
        print(f"\n=== LARGE OBJECTS (>{min_size_mb}MB) ===")
        for obj_type, size_mb in sorted(large_objects, key=lambda x: x[1], reverse=True):
            print(f"  {obj_type}: {size_mb:.2f}MB")
        print("=" * 40)
    
    return large_objects

def debug_streaming_objects():
    """Look for streaming-related objects"""
    streaming_objects = []
    
    for obj in gc.get_objects():
        obj_type = type(obj).__name__
        if any(keyword in obj_type.lower() for keyword in ['image', 'pil', 'frame', 'buffer', 'stream', 'gif']):
            try:
                size = sys.getsizeof(obj)
                streaming_objects.append((obj_type, size))
            except:
                streaming_objects.append((obj_type, 0))
    
    if streaming_objects:
        print(f"\n=== STREAMING-RELATED OBJECTS ===")
        type_counts = defaultdict(lambda: {'count': 0, 'total_size': 0})
        
        for obj_type, size in streaming_objects:
            type_counts[obj_type]['count'] += 1
            type_counts[obj_type]['total_size'] += size
        
        for obj_type, data in sorted(type_counts.items(), key=lambda x: x[1]['total_size'], reverse=True):
            total_mb = data['total_size'] / 1024 / 1024
            print(f"  {obj_type}: {data['count']} objects, {total_mb:.2f}MB total")
        print("=" * 40)
