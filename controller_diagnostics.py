"""Show whether macOS/SDL can see a USB game controller and its raw inputs.

Run: .venv/bin/python controller_diagnostics.py
Press Ctrl+C to quit.
"""

import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_JOYSTICK_HIDAPI", "1")
os.environ.setdefault("SDL_JOYSTICK_HIDAPI_SWITCH", "1")
os.environ.setdefault("SDL_JOYSTICK_MFI", "0")

import pygame

pygame.init()
pygame.joystick.init()
print("USB controller monitor — plug in the Pro Controller, then press buttons. Ctrl+C to quit.")
previous = None
try:
    while True:
        pygame.event.pump()
        if pygame.joystick.get_count() == 0:
            state = "No controller detected"
        else:
            joystick = pygame.joystick.Joystick(0)
            if not joystick.get_init():
                joystick.init()
            buttons = [i for i in range(joystick.get_numbuttons()) if joystick.get_button(i)]
            axes = [round(joystick.get_axis(i), 2) for i in range(joystick.get_numaxes())]
            state = f"{joystick.get_name()} | buttons={buttons} axes={axes}"
        if state != previous:
            print(state, flush=True)
            previous = state
        time.sleep(0.05)
except KeyboardInterrupt:
    print("\nStopped.")
