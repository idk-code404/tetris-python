import os
import sys
import time
import random
import threading
import queue

# ANSI escape codes
ANSI_CLEAR = "\033[2J\033[H"
ANSI_HIDE_CURSOR = "\033[?25l"
ANSI_SHOW_CURSOR = "\033[?25h"

# Use simple block that works everywhere
BLOCK = '██'

# Colors (Windows-compatible subset)
COLORS = {
    'I': '\033[96m',   # Bright Cyan
    'O': '\033[93m',   # Bright Yellow
    'T': '\033[95m',   # Bright Magenta
    'S': '\033[92m',   # Bright Green
    'Z': '\033[91m',   # Bright Red
    'J': '\033[94m',   # Bright Blue
    'L': '\033[33m',   # Yellow-Orange
    'BORDER': '\033[97m',  # White
    'TEXT': '\033[37m',    # Gray
    'RESET': '\033[0m'
}

# Fixed shape definitions (coordinates relative to top-left of 4x4 grid)
SHAPES = {
    'I': [
        [(1, 0), (1, 1), (1, 2), (1, 3)],  # Horizontal
        [(0, 2), (1, 2), (2, 2), (3, 2)]   # Vertical
    ],
    'O': [[(1, 1), (2, 1), (1, 2), (2, 2)]],
    'T': [
        [(1, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (1, 2)],
        [(1, 0), (0, 1), (1, 1), (1, 2)]
    ],
    'S': [
        [(1, 0), (2, 0), (0, 1), (1, 1)],
        [(1, 0), (1, 1), (2, 1), (2, 2)]
    ],
    'Z': [
        [(0, 0), (1, 0), (1, 1), (2, 1)],
        [(2, 0), (1, 1), (2, 1), (1, 2)]
    ],
    'J': [
        [(0, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 2)],
        [(1, 0), (0, 1), (1, 1), (1, 2)]
    ],
    'L': [
        [(2, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (0, 2)],
        [(1, 0), (0, 1), (1, 1), (1, 2)]
    ]
}

class Tetris:
    def __init__(self):
        self.width, self.height = 10, 20
        self.grid = [[None for _ in range(self.width)] for _ in range(self.height)]
        self.score = 0
        self.game_over = False
        self.paused = False
        self.drop_time = 0.5
        
        self.current_piece = None
        self.current_rotation = 0
        self.next_piece = random.choice(list(SHAPES.keys()))
        self.piece_x, self.piece_y = 0, 0
        
        self.key_queue = queue.Queue()
        self.setup_input()
        self.new_piece()
        
    def setup_input(self):
        """Reliable input handler"""
        def input_loop():
            try:
                if os.name == 'nt':
                    import msvcrt
                    while True:
                        if msvcrt.kbhit():
                            key = msvcrt.getch()
                            if key == b'\xe0':
                                key2 = msvcrt.getch()
                                if key2 == b'H': self.key_queue.put('up')
                                elif key2 == b'P': self.key_queue.put('down')
                                elif key2 == b'K': self.key_queue.put('left')
                                elif key2 == b'M': self.key_queue.put('right')
                            else:
                                if key == b' ': self.key_queue.put('space')
                                elif key in b'pP': self.key_queue.put('pause')
                                elif key in b'qQ\x03': self.key_queue.put('quit')
                        time.sleep(0.01)
                else:
                    import tty, termios
                    fd = sys.stdin.fileno()
                    old = termios.tcgetattr(fd)
                    try:
                        tty.setcbreak(fd)
                        while True:
                            ch = sys.stdin.read(1)
                            if ch == '\x1b':
                                ch2 = sys.stdin.read(1)
                                if ch2 == '[':
                                    ch3 = sys.stdin.read(1)
                                    if ch3 == 'A': self.key_queue.put('up')
                                    elif ch3 == 'B': self.key_queue.put('down')
                                    elif ch3 == 'C': self.key_queue.put('right')
                                    elif ch3 == 'D': self.key_queue.put('left')
                            elif ch == ' ': self.key_queue.put('space')
                            elif ch in 'pP': self.key_queue.put('pause')
                            elif ch in 'qQ\x03': self.key_queue.put('quit')
                            time.sleep(0.01)
                    finally:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except:
                pass
        
        threading.Thread(target=input_loop, daemon=True).start()
    
    def new_piece(self):
        self.current_piece = self.next_piece
        self.current_rotation = 0
        self.next_piece = random.choice(list(SHAPES.keys()))
        # Start piece at top-center (3 is (10-4)/2, aligning 4x4 grid center)
        self.piece_x, self.piece_y = 3, 0
        
        if not self.is_valid_position():
            self.game_over = True
    
    def get_shape(self):
        return SHAPES[self.current_piece][self.current_rotation]
    
    def is_valid_position(self, shape=None, x=None, y=None):
        if shape is None: shape = self.get_shape()
        if x is None: x = self.piece_x
        if y is None: y = self.piece_y
            
        for dx, dy in shape:
            # FIXED: Removed -2 offset bug
            px, py = x + dx, y + dy
            if px < 0 or px >= self.width or py >= self.height:
                return False
            if py >= 0 and self.grid[py][px] is not None:
                return False
        return True
    
    def rotate(self):
        if len(SHAPES[self.current_piece]) == 1:
            return
        new_rot = (self.current_rotation + 1) % len(SHAPES[self.current_piece])
        if self.is_valid_position(SHAPES[self.current_piece][new_rot]):
            self.current_rotation = new_rot
    
    def move(self, dx, dy):
        if self.is_valid_position(None, self.piece_x + dx, self.piece_y + dy):
            self.piece_x += dx
            self.piece_y += dy
            return True
        elif dy > 0:
            self.lock_piece()
            return False
        return True
    
    def hard_drop(self):
        while self.move(0, 1):
            self.draw()
            time.sleep(0.02)
    
    def lock_piece(self):
        # FIXED: Removed -2 offset bug
        for dx, dy in self.get_shape():
            x, y = self.piece_x + dx, self.piece_y + dy
            if y >= 0:
                self.grid[y][x] = self.current_piece
        
        lines_cleared = 0
        y = self.height - 1
        while y >= 0:
            if all(cell is not None for cell in self.grid[y]):
                del self.grid[y]
                self.grid.insert(0, [None for _ in range(self.width)])
                lines_cleared += 1
            else:
                y -= 1
        
        self.score += lines_cleared * 100
        if lines_cleared > 1:
            self.score += lines_cleared * 50
        
        self.new_piece()
    
    def handle_input(self):
        # FIXED: Process all keys instead of just the last one
        while not self.key_queue.empty():
            key = self.key_queue.get()
            if key == 'up': self.rotate()
            elif key == 'left': self.move(-1, 0)
            elif key == 'right': self.move(1, 0)
            elif key == 'down': self.move(0, 1)
            elif key == 'space': self.hard_drop()
            elif key == 'pause': self.paused = not self.paused
            elif key == 'quit': raise KeyboardInterrupt
    
    def draw(self):
        # FIXED: Use only ANSI clear for less flicker
        print(ANSI_CLEAR + ANSI_HIDE_CURSOR)
        
        # Create board state
        board = [[None for _ in range(self.width)] for _ in range(self.height)]
        for y in range(self.height):
            for x in range(self.width):
                board[y][x] = self.grid[y][x]
        
        # Add current piece
        if self.current_piece and not self.game_over:
            for dx, dy in self.get_shape():
                # FIXED: Removed -2 offset bug
                x, y = self.piece_x + dx, self.piece_y + dy
                if 0 <= x < self.width and 0 <= y < self.height:
                    board[y][x] = self.current_piece
        
        # Draw game board
        print(f"{COLORS['TEXT']}Score: {self.score}{COLORS['RESET']}\n")
        print(f"{COLORS['BORDER']}╔{'══'*self.width}╗{COLORS['RESET']}")
        
        for y in range(self.height):
            line = f"{COLORS['BORDER']}║{COLORS['RESET']}"
            for x in range(self.width):
                if board[y][x]:
                    line += f"{COLORS[board[y][x]]}{BLOCK}{COLORS['RESET']}"
                else:
                    line += '  '
            line += f"{COLORS['BORDER']}║{COLORS['RESET']}"
            print(line)
        
        print(f"{COLORS['BORDER']}╚{'══'*self.width}╝{COLORS['RESET']}\n")
        
        # FIXED: Proper next piece preview (4x4 grid)
        print(f"{COLORS['TEXT']}Next:{COLORS['RESET']}")
        preview = [['  ' for _ in range(4)] for _ in range(4)]
        next_shape = SHAPES[self.next_piece][0]
        # Center in 4x4 grid
        min_x = min(dx for dx, dy in next_shape)
        max_x = max(dx for dx, dy in next_shape)
        min_y = min(dy for dx, dy in next_shape)
        offset_x = (4 - (max_x - min_x + 1)) // 2 - min_x
        offset_y = (4 - (max_x - min_y + 1)) // 2 - min_y
        
        for dx, dy in next_shape:
            x, y = dx + offset_x, dy + offset_y
            if 0 <= x < 4 and 0 <= y < 4:
                preview[y][x] = f"{COLORS[self.next_piece]}{BLOCK}{COLORS['RESET']}"
        
        for row in preview:
            print(''.join(row))
        
        print(f"\n{COLORS['TEXT']}←→ Move | ↑ Rotate | ↓ Soft | Space Hard | P Pause | Q Quit{COLORS['RESET']}")
        
        if self.paused:
            print(f"\n{COLORS['TEXT']}PAUSED{COLORS['RESET']}")
        if self.game_over:
            # FIXED: Changed COLORS['Z'] to COLORS['TEXT']
            print(f"\n{COLORS['TEXT']}GAME OVER! Press Q to exit{COLORS['RESET']}")
    
    def run(self):
        try:
            last_time = time.time()
            while True:
                if not self.paused and not self.game_over:
                    if time.time() - last_time > self.drop_time:
                        self.move(0, 1)
                        last_time = time.time()
                
                self.handle_input()
                self.draw()
                time.sleep(0.05)
        except KeyboardInterrupt:
            pass
        finally:
            print(ANSI_SHOW_CURSOR)

if __name__ == '__main__':
    if os.name == 'nt':
        os.system('color')
    
    print("Starting Tetris in 1 second...")
    time.sleep(1)
    
    game = Tetris()
    game.run()