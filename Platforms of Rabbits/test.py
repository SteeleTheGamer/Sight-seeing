import pygame
import random
import math
import sys
from melee import MeleeController, AttackSpec  # <-- uses your melee.py

# =========================
# Config / Defaults
# =========================
PROJ_SPEED = 5
PLAYER_SPEED = 5
WIDTH = 800
HEIGHT = 800
DIFFICULTY = 2
HEALTH = 58
BULLETS = 50

KNOCKBACK = 25
SPAWN_MS = 15000  # enemy wave timer
SHOOT_COOLDOWN_MS = 125

# Colors
BG = (5, 126, 255)
PLAYER_COLOR = (245, 245, 245)
PLAYER_AIM_COLOR = (240, 215, 80)
ENEMY_COLOR = (200, 60, 60)
ENEMY_TANK_COLOR = (150, 40, 40)
BULLET_COLOR = (30, 30, 30)
HUD_ACCENT = (255, 255, 255)
CLR_TEXT = (20, 20, 20)

pygame.init()
window = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Squares Only Edition (with melee.py)")
clock = pygame.time.Clock()
running = True

font_small = pygame.font.SysFont(None, 18)
font_hud = pygame.font.SysFont(None, 24)

# =========================
# Helpers
# =========================
def clamp_rect_to_surface(rect: pygame.Rect, surf: pygame.Surface):
    rect.clamp_ip(surf.get_rect())

def text(s, fnt, color=HUD_ACCENT):
    return fnt.render(str(s), True, color)

def dir_from_direction_name(direction: str, last: pygame.Vector2) -> pygame.Vector2:
    if direction == 'left':
        return pygame.Vector2(-1, 0)
    if direction == 'right':
        return pygame.Vector2(1, 0)
    if direction == 'up':
        return pygame.Vector2(0, -1)
    if direction == 'down':
        return pygame.Vector2(0, 1)
    return last

# =========================
# Sprites
# =========================
class Projectile(pygame.sprite.Sprite):
    def __init__(self, center, direction: str):
        super().__init__()
        self.image = pygame.Surface((10, 10))
        self.image.fill(BULLET_COLOR)
        self.rect = self.image.get_rect(center=center)
        self.vx = 0
        self.vy = 0
        if direction == 'left':
            self.vx = -PROJ_SPEED
        elif direction == 'right':
            self.vx = PROJ_SPEED
        elif direction == 'up':
            self.vy = -PROJ_SPEED
        elif direction == 'down':
            self.vy = PROJ_SPEED

    def update(self):
        self.rect.x += self.vx
        self.rect.y += self.vy
        if not window.get_rect().collidepoint(self.rect.center):
            self.kill()

class Enemy(pygame.sprite.Sprite):
    def __init__(self, hp, speed, dmg, size=32, color=ENEMY_COLOR):
        super().__init__()
        self.image = pygame.Surface((size, size))
        self.image.fill(color)
        self.rect = self.image.get_rect()
        self.vx = 0
        self.vy = 0
        self.hp = hp
        self.speed = speed
        self.dmg = dmg

        # spawn at edge
        spawnloc = random.randint(0, 3)
        if spawnloc == 0:
            self.rect.center = (0, random.randrange(0, HEIGHT))
        elif spawnloc == 1:
            self.rect.center = (WIDTH, random.randrange(0, HEIGHT))
        elif spawnloc == 2:
            self.rect.center = (random.randrange(0, WIDTH), 0)
        else:
            self.rect.center = (random.randrange(0, WIDTH), HEIGHT)

    def take_damage(self, dmg: int) -> None:
        self.hp = max(0, self.hp - dmg)

    def enemy_hit(self, bullet=None, knockout_on_death=True):
        global BULLETS
        self.hp -= 1
        if self.hp <= 0:
            if knockout_on_death:
                BULLETS += random.randint(0, 10)
                self.kill()
                return True
            else:
                # respawn elsewhere (used for touching the player)
                spawnloc = random.randint(0, 3)
                if spawnloc == 0:
                    self.rect.center = (0, random.randrange(0, HEIGHT))
                elif spawnloc == 1:
                    self.rect.center = (WIDTH, random.randrange(0, HEIGHT))
                elif spawnloc == 2:
                    self.rect.center = (random.randrange(0, WIDTH), 0)
                else:
                    self.rect.center = (random.randrange(0, WIDTH), HEIGHT)
                return True
        else:
            if bullet is not None:
                # knockback by bullet direction
                if bullet.vx < 0:
                    self.rect.x = max(0, self.rect.x - KNOCKBACK)
                elif bullet.vx > 0:
                    self.rect.x = min(WIDTH - self.rect.width, self.rect.x + KNOCKBACK)
                elif bullet.vy < 0:
                    self.rect.y = max(0, self.rect.y - KNOCKBACK)
                elif bullet.vy > 0:
                    self.rect.y = min(HEIGHT - self.rect.height, self.rect.y + KNOCKBACK)
        return False

    def update(self, player_center):
        dx, dy = (player_center[0] - self.rect.centerx, player_center[1] - self.rect.centery)
        dist = math.hypot(dx, dy) or 1
        self.rect.x += self.speed * dx / dist
        self.rect.y += self.speed * dy / dist
        clamp_rect_to_surface(self.rect, window)

class Bad(Enemy):
    def __init__(self):
        super().__init__(hp=5, speed=2, dmg=0, size=28, color=ENEMY_COLOR)

class Sandbag(Enemy):
    def __init__(self):
        super().__init__(hp=5, speed=0, dmg=0, size=36, color=ENEMY_TANK_COLOR)

class Player(pygame.sprite.Sprite):
    def __init__(self, enemies, attack_group):
        super().__init__()
        self.size = 34
        self.image = pygame.Surface((self.size, self.size))
        self.image.fill(PLAYER_COLOR)
        self.rect = self.image.get_rect(center=(WIDTH // 2, HEIGHT // 2))

        self.base_health = HEALTH
        self.health = self.base_health
        self.direction = 'none'
        self.mode = 'move'
        self.facing = pygame.Vector2(1, 0)

        self.latest_shot = 0
        self.cooldown = SHOOT_COOLDOWN_MS

        self.enemies = enemies
        self.attack_group = attack_group

        # === Wire up melee.py just like your original ===
        def get_facing() -> pygame.Vector2:
            # Return a unit-like vector with components -1/0/1 as in your original
            fx = 1 if self.facing.x > 0 else (-1 if self.facing.x < 0 else 0)
            fy = 1 if self.facing.y > 0 else (-1 if self.facing.y < 0 else 0)
            return pygame.Vector2(fx, fy)

        def on_hit(attacker: pygame.sprite.Sprite, target: pygame.sprite.Sprite, spec: AttackSpec) -> None:
            if hasattr(target, "take_damage"):
                target.take_damage(spec.damage)

        spec = AttackSpec(
            windup_ms=120,
            active_ms=180,
            recovery_ms=200,
            damage=1,
        )
        self.melee = MeleeController(self, enemies, attack_group, spec, on_hit, get_facing)

    def firearm_ready(self, now):
        return BULLETS > 0 and (now >= self.latest_shot + self.cooldown)

    def try_shoot(self, keys, now):
        global BULLETS
        aim = keys[pygame.K_f]
        if not aim or not self.firearm_ready(now):
            return None

        left = keys[pygame.K_LEFT] or keys[pygame.K_j]
        down = keys[pygame.K_DOWN] or keys[pygame.K_k]
        up = keys[pygame.K_UP] or keys[pygame.K_l]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_SEMICOLON]

        if not (left or right or up or down):
            return None

        self.latest_shot = now
        BULLETS -= 1

        if up:
            return Projectile(self.rect.center, 'up')
        if left:
            return Projectile(self.rect.center, 'left')
        if down:
            return Projectile(self.rect.center, 'down')
        if right:
            return Projectile(self.rect.center, 'right')
        return None

    def update_move(self, keys):
        dx = dy = 0
        left = keys[pygame.K_LEFT] or keys[pygame.K_j]
        down = keys[pygame.K_DOWN] or keys[pygame.K_k]
        up = keys[pygame.K_UP] or keys[pygame.K_l]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_SEMICOLON]
        aim = keys[pygame.K_f]

        if aim:
            self.mode = 'aim'
            self.image.fill(PLAYER_AIM_COLOR)
        else:
            self.mode = 'move'
            self.image.fill(PLAYER_COLOR)

        if left:
            dx = -PLAYER_SPEED
            self.direction = 'left'
        if right:
            dx = PLAYER_SPEED
            self.direction = 'right'
        if up:
            dy = -PLAYER_SPEED
            self.direction = 'up'
        if down:
            dy = PLAYER_SPEED
            self.direction = 'down'

        if dx == 0 and dy == 0:
            self.direction = 'none'
        else:
            self.facing = dir_from_direction_name(self.direction, self.facing)

        self.rect.move_ip(dx, dy)
        clamp_rect_to_surface(self.rect, window)

    def knockback(self, enemy):
        # push player away from enemy and take damage
        if abs(enemy.rect.x - self.rect.x) > abs(enemy.rect.y - self.rect.y):
            if enemy.rect.x < self.rect.x:
                self.rect.x += KNOCKBACK // 5
            else:
                self.rect.x -= KNOCKBACK // 5
        else:
            if enemy.rect.y < self.rect.y:
                self.rect.y += KNOCKBACK // 5
            else:
                self.rect.y -= KNOCKBACK // 5
        self.health -= 5
        clamp_rect_to_surface(self.rect, window)

# =========================
# HUD / Drawing
# =========================
def label_enemy_health(surface, rect, health):
    txt = text(health, font_small, HUD_ACCENT)
    surface.blit(txt, (rect.centerx - txt.get_width() // 2, rect.top - 18))

def draw_hud(surface, hp, maxhp, enemycount, wavecount, bullets_left):
    if hp < 0:
        sys.exit()
    percent = round((hp / maxhp) * 100) if maxhp else 0

    # Player HP %
    surface.blit(text("HP:", font_hud, HUD_ACCENT), (8, 8))
    surface.blit(text(f"{percent}%", font_hud, HUD_ACCENT), (48, 8))

    # Enemies
    enemies_label = text("ENEMIES:", font_hud, HUD_ACCENT)
    n_enemies = text(str(enemycount), font_hud, HUD_ACCENT)
    ex = WIDTH - enemies_label.get_width() - n_enemies.get_width() - 16
    surface.blit(enemies_label, (ex, HEIGHT - 30))
    surface.blit(n_enemies, (ex + enemies_label.get_width() + 6, HEIGHT - 30))

    # Wave
    surface.blit(text("WAVE:", font_hud, HUD_ACCENT), (8, HEIGHT - 30))
    surface.blit(text(str(wavecount), font_hud, HUD_ACCENT), (70, HEIGHT - 30))

    # Bullets
    bullets_label = text("AMMO:", font_hud, HUD_ACCENT)
    n_bul = text(str(bullets_left), font_hud, HUD_ACCENT)
    bx = WIDTH - bullets_label.get_width() - n_bul.get_width() - 16
    surface.blit(bullets_label, (bx, 8))
    surface.blit(n_bul, (bx + bullets_label.get_width() + 6, 8))

def draw_debug_hud(screen, player, enemies_group, font):
    # Uses player.melee.phase and player.melee.phase_time (from melee.py)
    phase = getattr(player.melee, "phase", "unknown")
    phase_time = int(getattr(player.melee, "phase_time", 0))
    hud = [
        f"phase={phase}",
        f"t={phase_time}ms",
        f"facing=({int(player.facing.x)},{int(player.facing.y)})",
        f"enemy_hp={[e.hp for e in enemies_group]}",
        "Controls: arrows/J/K/L/; move, F+dir shoot, D melee, ESC quit",
    ]
    for i, line in enumerate(hud):
        screen.blit(font.render(line, True, CLR_TEXT), (8, 40 + i * 18))

# =========================
# Groups & Game State
# =========================
all_sprites = pygame.sprite.Group()
bullets = pygame.sprite.Group()
enemies = pygame.sprite.Group()
attack = pygame.sprite.Group()  # passed to MeleeController; it will manage its own hitboxes

spawn_event = pygame.USEREVENT + 1
pygame.time.set_timer(spawn_event, SPAWN_MS)
wavecount = 0
wavesize = 4
killcount = 0

player = Player(enemies, attack)
all_sprites.add(player)

# =========================
# Main Loop
# =========================
while running:
    dt = clock.tick(240)  # dt in ms-ish per tick (pygame returns ms per frame with tick FPS cap)
    now = pygame.time.get_ticks()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_d:
                # Start melee via melee.py controller
                player.melee.try_start()
        elif event.type == spawn_event:
            bulletbonus = random.randint(0, 60)
            if bulletbonus - 40 > 0:
                BULLETS += bulletbonus - 40
            wavecount += 1
            for _ in range(wavesize):
                if random.random() < 0.25:
                    e = Sandbag()
                else:
                    e = Bad()
                enemies.add(e)
                all_sprites.add(e)
            wavesize += DIFFICULTY

    keys = pygame.key.get_pressed()

    # Actions
    player.update_move(keys)

    maybe_proj = player.try_shoot(keys, now)
    if maybe_proj:
        bullets.add(maybe_proj)
        all_sprites.add(maybe_proj)

    # Update bullets
    bullets.update()

    # Update melee system (melee.py drives phases & hitboxes in 'attack' group)
    player.melee.update(dt)

    # Enemy logic & touches
    for enemy in list(enemies):
        enemy.update(player.rect.center)

    touches = pygame.sprite.spritecollide(player, enemies, dokill=False)
    for enemy in touches:
        # On touch: respawn enemy and knock the player (like your original branch)
        enemy.enemy_hit(bullet=None, knockout_on_death=False)
        for _ in range(5):
            player.knockback(enemy)

    # Bullet collisions with enemies
    if len(bullets) > 0:
        for bullet in list(bullets):
            hitlist = pygame.sprite.spritecollide(bullet, enemies, dokill=False)
            for enemy in hitlist:
                died = enemy.enemy_hit(bullet=bullet, knockout_on_death=True)
                if died:
                    killcount += 1
                    player.health = min(player.base_health, player.health + wavecount + DIFFICULTY)
                bullet.kill()

    # Draw
    window.fill(BG)
    all_sprites.draw(window)

    # enemy health labels
    for enemy in enemies:
        label_enemy_health(window, enemy.rect, enemy.hp)

    draw_hud(window, player.health, player.base_health, len(enemies), wavecount, BULLETS)
    draw_debug_hud(window, player, enemies, font_small)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
