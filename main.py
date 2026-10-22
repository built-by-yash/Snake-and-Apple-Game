import os
import random

import pygame
from pygame.locals import (
    KEYDOWN, QUIT,
    K_ESCAPE, K_RETURN, K_SPACE, K_p,
    K_LEFT, K_RIGHT, K_UP, K_DOWN,
)

# ---------------------------------------------------------------- settings
SIZE = 40                     
WIDTH, HEIGHT = 1000, 800
COLS, ROWS = WIDTH // SIZE, HEIGHT // SIZE
FPS = 60                      
START_DELAY = 200              
MIN_DELAY = 80                 
SPEEDUP_PER_APPLE = 5          
BACKGROUND_COLOR = (110, 110, 5)
WALL_COLOR = (120, 72, 52)      
WALL_DARK = (70, 40, 30)        
WALL_LIGHT = (160, 105, 80)     

# resources are found relative to this file, not the terminal's folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def res(name):
    return os.path.join(BASE_DIR, "resources", name)


# ---------------------------------------------------------------- asset helpers
def load_image(name, fallback_color, size=(SIZE, SIZE)):
    """Load an image once; use a plain colour block if the file is missing."""
    try:
        return pygame.image.load(res(name)).convert()
    except (pygame.error, FileNotFoundError):
        surf = pygame.Surface(size)
        surf.fill(fallback_color)
        return surf


def load_sound(name):
    try:
        return pygame.mixer.Sound(res(name))
    except (pygame.error, FileNotFoundError):
        return None


def make_walls():
    """Pre-draw the boundary wall (outer ring of cells) on a transparent surface."""
    walls = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for c in range(COLS):
        for r in range(ROWS):
            if c in (0, COLS - 1) or r in (0, ROWS - 1):
                x, y = c * SIZE, r * SIZE
                pygame.draw.rect(walls, WALL_COLOR, (x, y, SIZE, SIZE))
                pygame.draw.line(walls, WALL_LIGHT, (x + 2, y + 2), (x + SIZE - 3, y + 2), 2)
                # brick mortar lines
                pygame.draw.line(walls, WALL_DARK, (x, y + SIZE // 2), (x + SIZE, y + SIZE // 2), 2)
                pygame.draw.line(walls, WALL_DARK, (x + SIZE // 2, y), (x + SIZE // 2, y + SIZE // 2), 2)
                pygame.draw.rect(walls, WALL_DARK, (x, y, SIZE, SIZE), 2)
    return walls


# ---------------------------------------------------------------- game objects
class Apple:
    def __init__(self, image):
        self.image = image
        self.x, self.y = 3 * SIZE, 3 * SIZE

    def move(self, occupied):
        """Place the apple on a random cell that the snake is not covering."""
        free = [
            (c * SIZE, r * SIZE)
            for c in range(1, COLS - 1)
            for r in range(1, ROWS - 1)
            if (c * SIZE, r * SIZE) not in occupied
        ]
        if not free:
            return False           
        self.x, self.y = random.choice(free)
        return True

    def draw(self, surface):
        surface.blit(self.image, (self.x, self.y))


class Snake:
    DELTAS = {
        'left': (-SIZE, 0), 'right': (SIZE, 0),
        'up': (0, -SIZE), 'down': (0, SIZE),
    }
    OPPOSITE = {'left': 'right', 'right': 'left', 'up': 'down', 'down': 'up'}

    def __init__(self, image):
        self.image = image
        self.direction = 'down'
        self.pending = []          
        self.body = [(SIZE, SIZE)] 
        self.growing = 0

    @property
    def head(self):
        return self.body[0]

    def turn(self, new_dir):
        """Buffer a turn. Ignores reversing and duplicate presses."""
        last = self.pending[-1] if self.pending else self.direction
        if new_dir != last and new_dir != self.OPPOSITE[last] and len(self.pending) < 2:
            self.pending.append(new_dir)

    def grow(self):
        self.growing += 1

    def step(self):
        if self.pending:
            self.direction = self.pending.pop(0)
        dx, dy = self.DELTAS[self.direction]
        hx, hy = self.head
        self.body.insert(0, (hx + dx, hy + dy))
        if self.growing:
            self.growing -= 1
        else:
            self.body.pop()

    def hit_wall(self):
        x, y = self.head
        return x < SIZE or y < SIZE or x >= WIDTH - SIZE or y >= HEIGHT - SIZE

    def hit_itself(self):
        return self.head in self.body[1:]

    def draw(self, surface):
        for pos in self.body:
            surface.blit(self.image, pos)


# ---------------------------------------------------------------- game
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Snake And Apple Game")
        self.surface = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()

        # audio (game still runs if the sound device or files are missing)
        self.audio_ok = True
        try:
            pygame.mixer.init()
        except pygame.error:
            self.audio_ok = False
        self.ding = load_sound("ding.mp3") if self.audio_ok else None
        self.crash = load_sound("crash.mp3") if self.audio_ok else None
        self.play_background_music()

        # load everything once, not every frame
        bg = load_image("background.jpg", BACKGROUND_COLOR, (WIDTH, HEIGHT))
        self.background = pygame.transform.scale(bg, (WIDTH, HEIGHT))
        self.walls = make_walls()
        self.snake_img = load_image("block.jpg", (30, 160, 30))
        self.apple_img = load_image("apple.jpg", (200, 30, 30))

        self.font = pygame.font.SysFont('arial', 30)
        self.big_font = pygame.font.SysFont('arial', 50, bold=True)

        self.high_score = 0
        self.reset()

    # ---- audio
    def play_background_music(self):
        if not self.audio_ok:
            return
        try:
            pygame.mixer.music.load(res("bg_music_1.mp3"))
            pygame.mixer.music.play(-1)
        except (pygame.error, FileNotFoundError):
            pass

    def play_sound(self, sound):
        if sound:
            sound.play()

    # ---- state
    def reset(self):
        self.snake = Snake(self.snake_img)
        self.apple = Apple(self.apple_img)
        self.apple.move(set(self.snake.body))
        self.delay = START_DELAY
        self.timer = 0
        self.paused = False
        self.game_over = False
        if self.audio_ok:
            pygame.mixer.music.unpause()

    @property
    def score(self):
        return len(self.snake.body)

    def end_game(self):
        self.game_over = True
        self.high_score = max(self.high_score, self.score)
        self.play_sound(self.crash)
        if self.audio_ok:
            pygame.mixer.music.pause()

    # ---- one snake step
    def update(self):
        self.snake.step()

        if self.snake.hit_wall() or self.snake.hit_itself():
            self.end_game()
            return

        if self.snake.head == (self.apple.x, self.apple.y):
            self.play_sound(self.ding)
            self.snake.grow()
            self.delay = max(MIN_DELAY, self.delay - SPEEDUP_PER_APPLE)
            if not self.apple.move(set(self.snake.body)):
                self.end_game()    # snake filled the whole board

    # ---- drawing (one flip per frame)
    def draw_text(self, font, text, y, color=(255, 255, 255)):
        img = font.render(text, True, color)
        self.surface.blit(img, img.get_rect(center=(WIDTH // 2, y)))

    def draw(self):
        self.surface.blit(self.background, (0, 0))
        self.surface.blit(self.walls, (0, 0))
        self.apple.draw(self.surface)
        self.snake.draw(self.surface)

        score = self.font.render(f"Score: {self.score}", True, (200, 200, 200))
        self.surface.blit(score, (WIDTH - score.get_width() - 20, 10))
        best = self.font.render(f"Best: {self.high_score}", True, (200, 200, 200))
        self.surface.blit(best, (20, 10))

        if self.game_over:
            self.draw_text(self.big_font, "Game Over", 300)
            self.draw_text(self.font, f"Your score is {self.score}", 370)
            self.draw_text(self.font, "Press Enter to play again, Escape to exit", 420)
        elif self.paused:
            self.draw_text(self.big_font, "Paused", 350)
            self.draw_text(self.font, "Press P or Space to resume", 410)

        pygame.display.flip()

    # ---- main loop
    def run(self):
        keys = {
            K_LEFT: 'left', K_RIGHT: 'right', K_UP: 'up', K_DOWN: 'down',
        }
        running = True

        while running:
            dt = self.clock.tick(FPS)       # ms since last frame

            for event in pygame.event.get():
                if event.type == QUIT:
                    running = False
                elif event.type == KEYDOWN:
                    if event.key == K_ESCAPE:
                        running = False
                    elif self.game_over:
                        if event.key == K_RETURN:
                            self.reset()
                    elif event.key in (K_p, K_SPACE):
                        self.paused = not self.paused
                    elif event.key in keys and not self.paused:
                        self.snake.turn(keys[event.key])

            # move the snake only when enough time has passed
            if not self.game_over and not self.paused:
                self.timer += dt
                while self.timer >= self.delay and not self.game_over:
                    self.timer -= self.delay
                    self.update()

            self.draw()

        pygame.quit()


if __name__ == '__main__':
    Game().run()
