# Unicorn Wrangler Animations

A collection of animations for Pimoroni Unicorn displays (Galactic, Cosmic, Stellar). 

## Quick Start

Drop any `.py` file with a `run()` function into this directory and it will be automatically detected. See [GUIDE.md](GUIDE.md) for detailed development instructions.

## Animation Categories

### **Nature & Organic**
| Animation | Description | Performance | Best Display |
|-----------|-------------|-------------|--------------|
| **aurora.py** | Northern Lights style effect | Medium | Galactic, Cosmic |
| **fireflies.py** | Fireflies at dusk | Low | All displays |
| **jellyfish.py** | Underwater scene with swimming jellyfish | Medium | Cosmic, Stellar |
| **snowfall.py** | A winter snowfall effect | Low | All displays |
| **growing_vines.py** | Procedural organic vines | Medium | Galactic, Cosmic |
| **gravity_well.py** | Particles orbiting a heavy mass | High | Cosmic |
| **swarm.py** | Flocking behaviour simulation | Medium | All displays |

### **Fire & Energy**
| Animation | Description | Performance | Best Display |
|-----------|-------------|-------------|--------------|
| **fire.py** | Realistic flickering flame simulation (optimised from original unicorn demo)| Low | All displays |
| **lightning.py** | Thunderstorm with lightning bolts | Medium | Galactic, Cosmic |
| **plasma.py** | Colourful plasma patterns | High | All displays |
| **plasma_ball.py** | Simulation of a 1990s "Innovations" catalogue item | Medium | Cosmic, Stellar |
| **fireworks.py** | Fireworks display/Bonfire night | High | Galactic, Cosmic |

### **Space & Sci-Fi**
| Animation | Description | Performance | Best Display |
|-----------|-------------|-------------|--------------|
| **starfield.py** | Classic warp-speed starfield effect | Low | All displays |
| **meteor_shower.py** | Streaking meteors across night sky | Medium | Galactic, Cosmic |
| **trench_run.py** | Whomp rat eliminator | Medium | All displays |
| **tunnel.py** | Endless rotating tunnel | High | Cosmic, Stellar |
| **double_helix.py** | 3D rotating DNA strand | High | All displays |

### **Retro & Gaming**
| Animation | Description | Performance | Best Display |
|-----------|-------------|-------------|--------------|
| **boing_ball.py** | Classic Amiga bouncing checkered ball | Medium | All displays |
| **bouncing_pi.py** | Raspberry Pi logo bouncing with colour changes | Low | All displays |
| **rgbtrix.py** | Matrix-style digital rain effect | Medium | Galactic, Cosmic |
| **duelling_snakes.py** | Two-player Snake game | Low | Cosmic |
| **game_of_life.py** | Colourful Conway's cellular automaton | Medium | All displays |

### **Abstract & Geometric**
| Animation | Description | Performance | Best Display |
|-----------|-------------|-------------|--------------|
| **abstract_shapes.py** | The Third Place | High | All displays |
| **lissajous_dot.py** | Mathematical curve tracing | Low | All displays |
| **radial_rainbow.py** | Expanding rainbow bands | Medium | Cosmic, Stellar |
| **rotating_polygon.py** | Polygons. That rotate. | Medium | All displays |
| **morphing_polyhedra.py** | Attempt at solid 3d shape rotations | Very High | Cosmic |
| **wireframe_3d.py** | Various rotating 3D wireframe objects | Medium | All displays |

### **Utility & Functional**
| Animation | Description | Performance | Best Display |
|-----------|-------------|-------------|--------------|
| **clock.py** | Simple digital/analogue timepiece | Low | All displays |
| **qrclock.py** | QR code displaying current time (needs streaming server) | Low | Cosmic ONLY |
| **text_scroller.py** | MQTT message scroller | Low | All displays |
| **onair.py** | MQTT activated "On Air" sign | Low | All displays |
| **streaming.py** | Display streaming server content (needs streaming server) | Variable | All displays |
| **failsafe.py** | For friends of Mara | Low | All displays |

### **Colour & Pattern**
| Animation | Description | Performance | Best Display |
|-----------|-------------|-------------|--------------|
| **checker_wipe.py** | Checkerboard pattern transitions | Low | All displays |
| **checkerboard_pulse.py** | Rhythmic pulsing checkerboard | Medium | All displays |
| **sparkles.py** | Random twinkling colour sparkles | Low | All displays |
| **sparkles_plus.py** | Random twinkling colour sparkles, but plus | Low | All displays |
| **lava_lamp.py** | Retro lava lamp blob simulation | Medium | All displays |
| **slosh.py** | Liquid sloshing/wave sim | Medium | All displays |

### **Technical & Simulation**
| Animation | Description | Performance | Best Display |
|-----------|-------------|-------------|--------------|
| **oscilloscope.py** | Vintage oscilloscope waveforms | Medium | Galactic, Cosmic |
| **maze_generator.py** | Procedural maze creation and solving | Medium | Cosmic |

## Performance Guide

**Performance ratings:**
- **Low**: Minimal CPU usage, stable on all Pico W versions
- **Medium**: Moderate CPU usage, runs well on both Pico W v1 and v2
- **High**: CPU intensive, may struggle on Pico W v1, recommended for v2
- **Very High**: Maximum performance required, Pico W v2 recommended

## Display Compatibility

- **Stellar (16x16)**: Best for simpler animations but handles most surprisingly well
- **Cosmic (32x32)**: Best all-round as it's a large square with the most space
- **Galactic (53x11)**: Excellent for text, scrolling effects, and wide patterns
- **All displays**: Animation adapts to display dimensions automatically

## Memory Considerations

Each animation is lazy-loaded and automatically cleaned up after use. Memory-intensive animations (marked "High" or "Very High") may benefit from:
- Setting `max_iterations` limit in config.json
- Running on Pico W v2 for better memory management
- Avoiding concurrent high-memory animations

## Configuration

Animations can be controlled via `config.json`:

```json
{
  "general": {
    "sequence": ["jellyfish", "plasma", "starfield", "*"],
    "max_runtime_s": 300,
    "max_iterations": 20
  }
}
```

- `sequence`: Specific animation order, `"*"` = random
- `max_runtime_s`: Maximum seconds per animation
- `max_iterations`: Animation count before device restart (Pico W v1 stability)

## Development

See [GUIDE.md](GUIDE.md) for complete development documentation including:
- Animation API reference
- Performance optimisation tips
- Graphics primitives
- Utility functions
- Best practices

## Contributing

New animations are welcome! Ensure your animation:
1. Has a descriptive filename
2. Includes proper `async def run()` function
3. Handles `interrupt_event` to allow interceptions of events (like screen on/off mqtt messages)
4. Uses `animations.utils` for performance-critical operations
5. Works across different display sizes

Test in the simulator first: `cd board_client-sim && ./run.sh --animation your_animation`

## Animation Showcase

Visit the [online demo](https://seesee.github.io/apps/unicorn_wrangler/ "Note: TBD") to see all animations in action, or check out the included screenshots for visual previews of each effect.
