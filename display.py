from PiicoDev_SSD1306 import *
from PiicoDev_Unified import sleep_ms

class Display():
    
    _X_PIXELS = 64
    _Y_PIXELS = 128

    _ROWS = 6 
    _COLS = 13
    
    _display_present = True
    
    def __init__(self):
        self._next_row = 0
        self._display_dev = create_PiicoDev_SSD1306()
        self._display_present = True
        # test if the display is present.  if not set variable so that all display functions are by passed    
        self._display_dev.poweron()
        if self._display_dev.comms_err:
            print("PiicoDev SSD1306 Display not present")
            self._display_present = False
        else:   
            self._display_dev.fill(0)
            self._display_dev.show()


    def put(self, row, text):
        if self._display_present:
            self._display_dev.fill_rect(0, row, 128, (row + 9), 0)
            self._display_dev.text(text, 0, row, 1)
            self._next_row = row + 10
        return row


    def add(self, text):
        row  = self._next_row
        if self._display_present:
            self._next_row += 10
            self._display_dev.text(text, 0, row, 1)
        return row


    def clear(self):
        if self._display_present:
            self._next_row = 0
            self._display_dev.fill(0)


    def show(self):
        if self._display_present:
            self._display_dev.show()

