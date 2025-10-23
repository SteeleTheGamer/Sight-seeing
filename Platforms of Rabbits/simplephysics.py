import pygame
import sys

# Game settings
FPS = 60
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
SPEED = 10

# Visual and collision dimensions
IMAGE_HEIGHT = 100
HITBOX_HEIGHT = 68
JUMP_POWER = 15
GRAVITY = 1

# Colors
PLATFORM_COLOR = (0, 0, 0)
BG_COLOR = (200, 220, 255)
PLAYER_COLOR = (0, 100, 255)
SPRING_COLOR = (152, 255, 152)  # Mint green
PORTAL_COLOR = (200, 100, 255)

# Platform layout
LEVEL1 = [pygame.Rect(0, 500, 800, 40), pygame.Rect(500, 400, 200, 20), pygame.Rect(700, 320, 100, 20)]
LEVEL2 = [pygame.Rect(100, 220, 100, 20), pygame.Rect(120, 120, 700, 20), pygame.Rect(-100, 320, 200, 20)]
LEVEL3 = [pygame.Rect(0, 500, 325, 40), pygame.Rect(500, 250, 700, 20)]
LEVEL4 = [pygame.Rect(0, 500, 150, 40)]
LEVELS = [LEVEL1, LEVEL2, LEVEL3, LEVEL4]

class Springs:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 75, 20)  # Spring size

    def draw(self, surface):
        pygame.draw.rect(surface, SPRING_COLOR, self.rect)

class Portals:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 74, 55)  # Portal size

    def draw(self, surface):
        pygame.draw.rect(surface, PORTAL_COLOR, self.rect)

class Player:
    def __init__(self, x, y):
        width = 50
        self.image_height = IMAGE_HEIGHT
        self.hitbox_height = HITBOX_HEIGHT

        self.image_offset_y = -(self.image_height - self.hitbox_height)
        self.rect = pygame.Rect(x, y, width, self.hitbox_height)

        self.vel_y = 0
        self.vel_x = 0
        self.on_ground = False

    def handle_input(self, keys):
        self.vel_x = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.vel_x = -SPEED
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.vel_x = SPEED
        if keys[pygame.K_SPACE] and self.on_ground:
            self.vel_y = -JUMP_POWER
            self.on_ground = False

    def apply_physics(self):
        self.vel_y += GRAVITY
        self.rect.y += self.vel_y

        self.rect.x += int(self.vel_x)
        self.vel_x *= 0.8
        if abs(self.vel_x) < 0.5:
            self.vel_x = 0

    def check_collisions(self, platforms):
        self.on_ground = False
        for plat in platforms:
            if self.rect.colliderect(plat):
                if self.vel_y > 0 and self.rect.bottom - self.vel_y <= plat.top:
                    self.rect.bottom = plat.top
                    self.vel_y = 0
                    self.on_ground = True
                elif self.vel_y < 0 and self.rect.top - self.vel_y >= plat.bottom:
                    self.rect.top = plat.bottom
                    self.vel_y = 0
                else:
                    if self.rect.centerx < plat.centerx:
                        self.rect.right = plat.left
                    else:
                        self.rect.left = plat.right

    def spring_collisions(self, springs):
        for spring in springs:
            if self.rect.colliderect(spring.rect):
                if self.vel_y > 0 and self.rect.bottom <= spring.rect.top + self.vel_y:
                    self.vel_y = -JUMP_POWER * 1.5

    def update(self, platforms, springs):
        self.apply_physics()
        self.check_collisions(platforms)
        self.spring_collisions(springs)

    def draw(self, surface):
        draw_x = self.rect.x
        draw_y = self.rect.y + -self.image_offset_y - 32
        draw_rect = pygame.Rect(draw_x, draw_y, self.rect.width, self.image_height)
        pygame.draw.rect(surface, PLAYER_COLOR, draw_rect)

def leveldata(levelindex):
    SLEVEL3 = [Springs(250, 450)]
    SLEVEL4 = [Springs(100, 430), Springs(350, 220)]

    if levelindex == 0:
        platforms = LEVEL4
        portal = Portals(730, 260)
        springs = SLEVEL4
    elif levelindex == 1:
        platforms = LEVEL2
        portal = Portals(730, 50)
        springs = []
    elif levelindex == 2:
        platforms = LEVEL3
        portal = Portals(730, 200)
        springs = SLEVEL3
    elif levelindex == 3:
        platforms = LEVEL4
        portal = Portals(730, 260)
        springs = SLEVEL4
    else:
        platforms = LEVEL1
        portal = None
        springs = []
    return platforms, portal, springs

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Forgiving Platformer Hitbox")
    clock = pygame.time.Clock()

    indexlevel = 0
    platforms, portal, springs = leveldata(indexlevel)
    player = Player(100, platforms[0].top - HITBOX_HEIGHT)

    running = True
    while running:
        clock.tick(FPS)
        keys = pygame.key.get_pressed()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        player.handle_input(keys)
        player.update(platforms, springs)

        if portal and player.rect.colliderect(portal.rect):
            indexlevel += 1
            platforms, portal, springs = leveldata(indexlevel)
            player.vel_y = 0
            player.vel_x = 0
            player.rect.x = -100
            player.rect.y = 200

        screen.fill(BG_COLOR)
        for plat in platforms:
            pygame.draw.rect(screen, PLATFORM_COLOR, plat)
        for spring in springs:
            spring.draw(screen)
        if portal:
            portal.draw(screen)
        player.draw(screen)

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
