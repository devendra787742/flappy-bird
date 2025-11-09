import pygame
import random
import sys
import math
import os
from collections import deque

# ---------- Config ----------
WIDTH, HEIGHT = 480, 700
FPS = 60

BIRD_X = 100
GRAVITY = 0.45          # gravity acceleration
FLAP_POWER = -9.5       # instant velocity given on flap
TERMINAL_V = 12         # max falling speed

PIPE_SPEED = 3.3
PIPE_GAP = 200
PIPE_INTERVAL = 1700    # milliseconds between pipes
PIPE_WIDTH = 88

GROUND_HEIGHT = 100

PARTICLE_LIFETIME = 0.6  # seconds
# ----------------------------

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
font_big = pygame.font.SysFont("arial", 48, bold=True)
font_med = pygame.font.SysFont("arial", 28)
font_small = pygame.font.SysFont("arial", 18)

# Where high score will be stored
HIGH_FILE = "flappy_highscore.txt"

# ---------- Helpers ----------
def load_highscore():
    try:
        with open(HIGH_FILE, "r") as f:
            return int(f.read().strip() or 0)
    except:
        return 0

def save_highscore(v):
    try:
        with open(HIGH_FILE, "w") as f:
            f.write(str(int(v)))
    except:
        pass

def clamp(v, a, b): return max(a, min(b, v))

# ---------- Visuals: procedural assets ----------
def make_gradient_pipe(h, w, base=(32,160,32)):
    # Create a pipe surface with a simple vertical gradient and shadow edge
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        t = y / max(1, h-1)
        r = int(base[0] * (0.8 + 0.2 * (1 - t)))
        g = int(base[1] * (0.9 + 0.1 * (1 - t)))
        b = int(base[2] * (0.9 + 0.1 * (1 - t)))
        pygame.draw.line(surf, (r, g, b), (0, y), (w-1, y))
    # shadow on one side
    shadow = pygame.Surface((6, h), pygame.SRCALPHA)
    for i in range(6):
        alpha = int(120 * (1 - i/6))
        shadow.fill((0,0,0,alpha), (i,0,1,h))
    surf.blit(shadow, (w-6, 0))
    return surf

def draw_ground(y):
    # ground base
    pygame.draw.rect(screen, (222, 180, 120), (0, y, WIDTH, GROUND_HEIGHT))
    # subtle stripes
    for i in range(0, WIDTH, 40):
        pygame.draw.rect(screen, (210,170,110), (i, y+40, 20, 8))

# ---------- Bird ----------
class Bird:
    def __init__(self):
        self.x = BIRD_X
        self.y = HEIGHT//2
        self.vel = 0.0
        self.angle = 0.0
        self.wing_phase = 0.0
        self.radius = 18
        # pre-render body surface
        self.body = pygame.Surface((self.radius*2+6, self.radius*2+6), pygame.SRCALPHA)
        self._make_body()

    def _make_body(self):
        s = self.body
        r = self.radius
        s.fill((0,0,0,0))
        # body circle
        pygame.draw.circle(s, (255, 205, 60), (r+3, r+3), r)
        # beak
        pygame.draw.polygon(s, (255,120,20), [(r+3+r, r+3-6),(r+3+r+10,r+3),(r+3+r, r+3+6)])
        # eye
        pygame.draw.circle(s, (20,20,20), (r+3+6, r+3-6), 4)

    def flap(self):
        self.vel = FLAP_POWER
        # wing animation kick
        self.wing_phase = -0.6

    def update(self, dt):
        # physics
        self.vel += GRAVITY
        self.vel = clamp(self.vel, -999, TERMINAL_V)
        # smoother motion: apply velocity to position
        self.y += self.vel

        # angle based on vertical speed
        self.angle = clamp(-self.vel * 3.5, -30, 80)

        # wing oscillation (for idle)
        self.wing_phase += dt * 8.0

    def draw(self, surf):
        # draw with rotation around center
        image = self.body
        # create wing by simple ellipse drawn each frame
        wing_surf = pygame.Surface(image.get_size(), pygame.SRCALPHA)
        wp = 6 + int(math.sin(self.wing_phase) * 6)
        pygame.draw.ellipse(wing_surf, (255,180,40), (6, 10-wp, 26, 14))
        # composite
        comp = image.copy()
        comp.blit(wing_surf, (0,0))
        # rotate
        rotated = pygame.transform.rotate(comp, self.angle)
        rect = rotated.get_rect(center=(int(self.x), int(self.y)))
        surf.blit(rotated, rect.topleft)

    def get_rect(self):
        return pygame.Rect(self.x - self.radius, self.y - self.radius, self.radius*2, self.radius*2)

# ---------- Particles ----------
class Particle:
    def __init__(self, x, y):
        self.x = x + random.uniform(-6,6)
        self.y = y + random.uniform(-6,6)
        self.velx = random.uniform(-1.8, 1.8)
        self.vely = random.uniform(-3.0, -0.5)
        self.life = PARTICLE_LIFETIME
        self.size = random.randint(2,5)
        self.color = (255, 220, 90)

    def update(self, dt):
        self.life -= dt
        self.x += self.velx
        self.y += self.vely
        self.vely += GRAVITY*0.6

    def draw(self, surf):
        if self.life <= 0: return
        a = clamp(int(255 * (self.life / PARTICLE_LIFETIME)), 0, 255)
        col = (*self.color[:3], a)
        s = pygame.Surface((self.size*2, self.size*2), pygame.SRCALPHA)
        pygame.draw.circle(s, col, (self.size, self.size), self.size)
        surf.blit(s, (self.x - self.size, self.y - self.size))

# ---------- Pipes ----------
class Pipe:
    def __init__(self, x):
        self.x = x
        self.w = PIPE_WIDTH
        total_h = HEIGHT - GROUND_HEIGHT
        self.h_top = random.randint(80, total_h - PIPE_GAP - 80)
        self.h_bottom = total_h - self.h_top - PIPE_GAP
        # create surfaces
        self.top_surf = make_gradient_pipe(self.h_top, self.w)
        self.bottom_surf = make_gradient_pipe(self.h_bottom, self.w)
        # top surface is flipped vertically
        self.top_surf = pygame.transform.flip(self.top_surf, False, True)
        self.passed = False

    def update(self, dt):
        self.x -= PIPE_SPEED

    def draw(self, surf):
        # top pipe (y negative so it aligns)
        surf.blit(self.top_surf, (self.x, 0 + self.h_top - self.top_surf.get_height()))
        # bottom pipe
        bottom_y = self.h_top + PIPE_GAP
        surf.blit(self.bottom_surf, (self.x, bottom_y))

    def get_top_rect(self):
        return pygame.Rect(self.x, 0, self.w, self.h_top)

    def get_bottom_rect(self):
        bottom_y = self.h_top + PIPE_GAP
        return pygame.Rect(self.x, bottom_y, self.w, self.h_bottom)

# ---------- Parallax Clouds ----------
class Cloud:
    def __init__(self):
        self.x = random.randint(0, WIDTH)
        self.y = random.randint(40, 200)
        self.speed = random.uniform(0.3, 1.1)
        self.scale = random.uniform(0.8, 1.6)

    def update(self, dt):
        self.x -= self.speed
        if self.x < -120:
            self.x = WIDTH + 60
            self.y = random.randint(40, 200)
            self.speed = random.uniform(0.3, 1.1)

    def draw(self, surf):
        # simple cloud with three ellipses
        s = pygame.Surface((160, 80), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (255,255,255,200), (0,20,80*self.scale,40*self.scale))
        pygame.draw.ellipse(s, (255,255,255,200), (40,0,90*self.scale,50*self.scale))
        pygame.draw.ellipse(s, (255,255,255,200), (80,20,80*self.scale,40*self.scale))
        surf.blit(s, (int(self.x - 60*self.scale), int(self.y - 20*self.scale)))

# ---------- Main Game ----------
def run_game():
    bird = Bird()
    particles = []
    clouds = [Cloud() for _ in range(6)]
    pipes = deque()

    last_pipe_time = pygame.time.get_ticks() - PIPE_INTERVAL//2
    score = 0
    high = load_highscore()
    running = True
    started = False
    game_over = False

    while running:
        dt = clock.tick(FPS) / 1000.0  # seconds
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                    break
                if event.key == pygame.K_SPACE:
                    if not started:
                        started = True
                        bird = Bird()  # reset nicely for first start
                    if not game_over:
                        bird.flap()
                        # spawn particles at bird
                        for _ in range(12):
                            particles.append(Particle(bird.x - 6, bird.y))
                    else:
                        # on game over, space -> restart
                        pipes.clear()
                        last_pipe_time = pygame.time.get_ticks()
                        score = 0
                        bird = Bird()
                        particles.clear()
                        started = True
                        game_over = False
                if event.key == pygame.K_r and game_over:
                    pipes.clear()
                    last_pipe_time = pygame.time.get_ticks()
                    score = 0
                    bird = Bird()
                    particles.clear()
                    started = True
                    game_over = False

        # update background clouds
        for c in clouds:
            c.update(dt)

        # spawn pipes
        now = pygame.time.get_ticks()
        if started and not game_over and now - last_pipe_time > PIPE_INTERVAL:
            last_pipe_time = now
            pipes.append(Pipe(WIDTH + 20))

        # update pipes
        for p in list(pipes):
            p.update(dt)
            if p.x + p.w < -60:
                pipes.popleft()
            # scoring
            if not p.passed and p.x + p.w < bird.x:
                p.passed = True
                score += 1
                high = max(high, score)
                save_highscore(high)

        # update bird
        if started and not game_over:
            bird.update(dt)
        else:
            # slight bobbing before start
            bird.wing_phase += dt * 4.0

        # update particles
        for part in list(particles):
            part.update(dt)
            if part.life <= 0:
                particles.remove(part)

        # collision detection
        if started and not game_over:
            brect = bird.get_rect()
            # ground collision
            if bird.y + bird.radius > HEIGHT - GROUND_HEIGHT:
                game_over = True
            # pipes collision
            for p in pipes:
                if brect.colliderect(p.get_top_rect()) or brect.colliderect(p.get_bottom_rect()):
                    game_over = True
                    break

        # ---------- Drawing ----------
        # sky gradient
        for i in range(HEIGHT):
            t = i / HEIGHT
            r = int(120 + 135 * (1 - t))
            g = int(190 + 40 * (1 - t))
            b = int(255 - 100 * t)
            pygame.draw.line(screen, (r, g, b), (0, i), (WIDTH, i))

        # distant hills (parallax)
        pygame.draw.ellipse(screen, (60, 140, 70), (-200, HEIGHT - 220, 700, 300))
        pygame.draw.ellipse(screen, (70, 150, 80), (120, HEIGHT - 240, 600, 320))

        # clouds
        for c in clouds:
            c.draw(screen)

        # pipes
        for p in pipes:
            p.draw(screen)

        # ground
        draw_ground(HEIGHT - GROUND_HEIGHT)

        # particles behind bird
        for part in particles:
            part.draw(screen)

        # bird
        bird.draw(screen)

        # HUD: score
        score_surf = font_big.render(str(score), True, (255,255,255))
        # shadow
        screen.blit(font_big.render(str(score), True, (0,0,0)), (WIDTH//2 - score_surf.get_width()//2 + 2, 30 + 2))
        screen.blit(score_surf, (WIDTH//2 - score_surf.get_width()//2, 30))

        # top-right highscore
        hs = font_small.render(f"Best: {high}", True, (255,255,255))
        screen.blit(hs, (WIDTH - hs.get_width() - 12, 12))

        if not started and not game_over:
            s1 = font_med.render("Press SPACE to start", True, (255,255,255))
            screen.blit(s1, (WIDTH//2 - s1.get_width()//2, HEIGHT//2 - 20))

        if game_over:
            # overlay
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0,0,0,120))
            screen.blit(overlay, (0,0))

            go = font_big.render("GAME OVER", True, (255, 200, 200))
            scr = font_med.render(f"Score: {score}", True, (255,255,255))
            rr = font_small.render("Press R or SPACE to try again", True, (220,220,220))
            screen.blit(go, (WIDTH//2 - go.get_width()//2, HEIGHT//2 - 80))
            screen.blit(scr, (WIDTH//2 - scr.get_width()//2, HEIGHT//2 - 20))
            screen.blit(rr, (WIDTH//2 - rr.get_width()//2, HEIGHT//2 + 30))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    run_game()
# use this in cmd to run it 
#cd C:\Users\singh\Downloads> python flappy_bird.py
#python flappy_bird.py

