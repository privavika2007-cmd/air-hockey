"""
Aerohockey - первый рабочий прототип Splash + Menu Overlay.
Реализация по спеке: aerohockey-frontend-design.md
Рендерит статичные состояния экрана 1 в PNG, чтобы проверить, что
слои (неон-glow, скруглённые карточки режимов, selected-состояние)
собираются и выглядят как в мокапах.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # headless render, без окна

import pygame

pygame.init()
pygame.font.init()

W, H = 1186, 670
screen = pygame.display.set_mode((W, H))

BLACK = (0, 0, 0)
TEAL = (60, 140, 124)
CYAN = (47, 208, 255)
OLIVE = (206, 194, 90)
GRAY = (107, 107, 107)
PANEL = (58, 58, 58)
TEXT = (230, 230, 230)

FONT = pygame.font.SysFont("arial", 18)


def draw_glow_circle(surf, center, radius, fill_color, glow_color, layers=10, max_extra=34):
    pad = max_extra
    glow = pygame.Surface((radius * 2 + pad * 2, radius * 2 + pad * 2), pygame.SRCALPHA)
    gc = (glow.get_width() // 2, glow.get_height() // 2)
    for i in range(layers, 0, -1):
        alpha = int(200 * (i / layers) ** 2)
        r = radius + int(pad * (i / layers))
        pygame.draw.circle(glow, (*glow_color, alpha), gc, r)
    surf.blit(glow, (center[0] - gc[0], center[1] - gc[1]))
    pygame.draw.circle(surf, fill_color, center, radius)
    pygame.draw.circle(surf, glow_color, center, radius, width=3)


def draw_triangle(surf, center, size, color):
    x, y = center
    pts = [(x - size * 0.45, y - size * 0.65), (x - size * 0.45, y + size * 0.65), (x + size * 0.75, y)]
    pygame.draw.polygon(surf, color, pts)


def draw_hamburger(surf, center, size, color):
    x, y = center
    for dy in (-size * 0.35, 0, size * 0.35):
        pygame.draw.rect(surf, color, (x - size * 0.5, y + dy - 3, size, 6), border_radius=3)


def draw_note(surf, center, size, color):
    x, y = center
    stem_x = x - size * 0.05
    pygame.draw.circle(surf, color, (int(x - size * 0.28), int(y + size * 0.32)), int(size * 0.16))
    pygame.draw.line(surf, color, (stem_x, y + size * 0.32), (stem_x, y - size * 0.5), 4)
    pygame.draw.line(surf, color, (stem_x, y - size * 0.5), (stem_x + size * 0.32, y - size * 0.62), 4)


PLAY_CENTER = (593, 515)
PLAY_R = 74
MENU_CENTER = (1052, 103)
SOUND_CENTER = (1052, 236)
SMALL_R = 44

MODES = ["Космос", "Цветочный", "Баскетбол", "Бутик", "Неон классика", "Пончик"]


def draw_splash(selected_mode=None, show_menu=False):
    screen.fill(BLACK)

    draw_glow_circle(screen, PLAY_CENTER, PLAY_R, TEAL, CYAN)
    draw_triangle(screen, PLAY_CENTER, 50, OLIVE)

    draw_glow_circle(screen, MENU_CENTER, SMALL_R, TEAL, CYAN)
    draw_hamburger(screen, MENU_CENTER, 40, OLIVE)

    draw_glow_circle(screen, SOUND_CENTER, SMALL_R, TEAL, CYAN)
    draw_note(screen, SOUND_CENTER, 40, OLIVE)

    if show_menu:
        panel = pygame.Surface((W - 40, H - 20), pygame.SRCALPHA)
        panel.fill((*PANEL, 235))
        screen.blit(panel, (18, 10))

        card_w, card_h, gap = 270, 40, 16
        x, y = 463, 50
        for i, name in enumerate(MODES):
            color = TEAL if i == selected_mode else GRAY
            card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
            pygame.draw.rect(card, (*color, 210), (0, 0, card_w, card_h), border_radius=14)
            screen.blit(card, (x, y))
            label = FONT.render(name, True, TEXT)
            screen.blit(label, (x + 14, y + card_h // 2 - label.get_height() // 2))
            y += card_h + gap


def save(name):
    pygame.image.save(screen, name)
    print(f"saved {name}")


# state 1: чистый Splash
draw_splash()
save("proto_1_splash.png")

# state 2: меню открыто, ничего не выбрано
draw_splash(show_menu=True)
save("proto_2_menu.png")

# state 3: меню открыто, выбран режим "Баскетбол" (index 2)
draw_splash(selected_mode=2, show_menu=True)
save("proto_3_menu_selected.png")

pygame.quit()
print("DONE")
