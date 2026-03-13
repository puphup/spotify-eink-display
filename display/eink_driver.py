"""
E-Ink driver for Waveshare 7.3" ACeP 7-Color display (epd7in3f).

Physical resolution: 800 × 480 (landscape)
We design in portrait (480 × 800) and rotate 90° before sending to hardware.

Set EINK_MOCK=true in .env to save PNG instead of writing to hardware.
"""

import os
from PIL import Image

MOCK_MODE = os.getenv("EINK_MOCK", "false").lower() == "true"
MOCK_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", ".cache", "last_display.png")


class EinkDisplay:
    def __init__(self):
        self._epd = None
        if not MOCK_MODE:
            self._init_hardware()

    def _init_hardware(self):
        try:
            # Waveshare 7.3" ACeP 7-color
            from waveshare_epd import epd7in3f
            self._epd = epd7in3f.EPD()
            self._epd.init()
            print("[eink] Hardware display initialized (7.3\" ACeP).")
        except ImportError:
            print("[eink] WARNING: waveshare_epd not found. Falling back to mock mode.")
            global MOCK_MODE
            MOCK_MODE = True
        except Exception as e:
            print(f"[eink] ERROR initializing display: {e}. Falling back to mock mode.")
            MOCK_MODE = True

    def display(self, image: Image.Image):
        """
        Push a portrait RGB image (480×800) to the display.
        Rotates 90° CW to fit the physical 800×480 landscape panel.
        """
        # Rotate portrait → landscape for the physical hardware
        landscape = image.rotate(90, expand=True)

        if MOCK_MODE:
            self._mock_display(image)  # save portrait for easy preview
            return

        try:
            buf = self._epd.getbuffer(landscape.convert("RGB"))
            self._epd.display(buf)
            print("[eink] Display updated.")
        except Exception as e:
            print(f"[eink] ERROR during display update: {e}")

    def clear(self):
        if MOCK_MODE:
            print("[eink] Mock clear.")
            return
        try:
            self._epd.Clear()
        except Exception as e:
            print(f"[eink] ERROR during clear: {e}")

    def sleep(self):
        if MOCK_MODE:
            return
        try:
            self._epd.sleep()
        except Exception as e:
            print(f"[eink] ERROR during sleep: {e}")

    def _mock_display(self, image: Image.Image):
        os.makedirs(os.path.dirname(MOCK_OUTPUT_PATH), exist_ok=True)
        image.save(MOCK_OUTPUT_PATH)
        print(f"[eink] Mock display — image saved to {MOCK_OUTPUT_PATH}")
