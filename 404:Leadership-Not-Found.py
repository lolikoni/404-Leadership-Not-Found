import pygame
import random
import json
from datetime import datetime
import os

# Инициализация Pygame
pygame.init()
os.environ['SDL_VIDEO_CENTERED'] = '1'

# Константы
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 720
CELL_COLOR = (249, 209, 183)
BUTTON_COLOR = (255, 255, 255)
BUTTON_BORDER_COLOR = (0, 0, 0)
TEXT_COLOR = (0, 0, 0)
FPS = 60
CELL_WIDTH = 100
CELL_HEIGHT = 40
PLAYER_SIZE = (30, 50)
FIELD_LENGTH = 61
CAMERA_SPEED = 0.1
MUSIC_VOLUME = 0.3
SFX_VOLUME = 0.6

# Типы клеток
CELL_TYPES = {
    5: {"name": "boost", "effect": 3},
    15: {"name": "trap", "effect": -2},
    30: {"name": "portal", "effect": 10}
}

# Звуковые файлы
BG_MUSIC = "bg_music.mp3"
DICE_SOUND = "dice_roll.wav"
WIN_SOUND = "victory.wav"
BUTTON_CLICK = "click.wav"

# Позиции
FIELD_Y = SCREEN_HEIGHT - (SCREEN_HEIGHT // 3)
CELL_Y = FIELD_Y - CELL_HEIGHT // 2
PLAYER_Y = CELL_Y - PLAYER_SIZE[1] - 15

class Player:
    def __init__(self, color, order, name=""):
        self.color = color
        self.position = 0
        self.screen_x = 0
        self.order = order
        self.name = name
        self.completed_quests = 0

class GameState:
    def __init__(self):
        self.players = []
        self.players_selected = False    
        self.players_count = 0          
        self.dice_result = 0            
        self.is_quest_active = False    
        self.active_quest = ""          
        self.leader = 0                 
        self.is_moving = False          
        self.steps_remaining = 0        
        self.winner = None
        self.field_offset = 0
        self.should_move_camera = False
        self.sound_on = True
        self.stats = {"best_time": 0, "quests_completed": 0}

    def save_game(self):
        data = {
            "players": [{
                "color": p.color,
                "position": p.position,
                "name": p.name
            } for p in self.players],
            "leader": self.leader,
            "stats": self.stats
        }
        with open("save.json", "w") as f:
            json.dump(data, f)

    def load_game(self):
        try:
            with open("save.json") as f:
                data = json.load(f)
                self.players = [
                    Player(tuple(p["color"]), i, p["name"]) 
                    for i, p in enumerate(data["players"])
                ]
                self.leader = data["leader"]
                self.stats = data["stats"]
                return True
        except:
            return False

def draw_button(font, text, x, y, padding=20):
    text_render = font.render(text, True, TEXT_COLOR)
    width = text_render.get_width() + padding * 2
    height = text_render.get_height() + padding
    button_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    text_rect = text_render.get_rect(center=(width//2, height//2))
    pygame.draw.rect(button_surface, BUTTON_COLOR, (0, 0, width, height), border_radius=5)
    pygame.draw.rect(button_surface, BUTTON_BORDER_COLOR, (0, 0, width, height), 2, border_radius=5)
    button_surface.blit(text_render, text_rect)
    return button_surface, (x, y)

def draw_cells(screen, font, offset):
    start_cell = max(0, int(offset // CELL_WIDTH) - 2)
    end_cell = min(FIELD_LENGTH, int((offset + SCREEN_WIDTH) // CELL_WIDTH) + 2)
    
    for i in range(start_cell, end_cell):
        x = i * CELL_WIDTH - offset
        if x > SCREEN_WIDTH + CELL_WIDTH:
            break
        
        if i in CELL_TYPES:
            color = (255, 200, 0) if CELL_TYPES[i]["name"] == "boost" else (
                255, 0, 0) if CELL_TYPES[i]["name"] == "trap" else (0, 150, 255)
        else:
            color = (76, 175, 80) if i == 60 else (249, 209, 30)
        
        pygame.draw.ellipse(screen, color, (x, CELL_Y - CELL_HEIGHT//2, CELL_WIDTH, CELL_HEIGHT))
        pygame.draw.ellipse(screen, BUTTON_BORDER_COLOR, (x, CELL_Y - CELL_HEIGHT//2, CELL_WIDTH, CELL_HEIGHT), 2)
        
        text = font.render("ФИНИШ" if i == 60 else str(i), True, TEXT_COLOR)
        text_rect = text.get_rect(center=(x + CELL_WIDTH//2, CELL_Y))
        screen.blit(text, text_rect)

def calculate_player_positions(players, field_offset):
    position_groups = {}
    for player in players:
        position = player.position
        if position not in position_groups:
            position_groups[position] = []
        position_groups[position].append(player)

    for position, group in position_groups.items():
        if position >= FIELD_LENGTH:
            continue
            
        cell_left = position * CELL_WIDTH - field_offset
        cell_right = cell_left + CELL_WIDTH

        if position == 60:
            for player in group:
                player.screen_x = cell_left + (CELL_WIDTH - PLAYER_SIZE[0]) // 2
            continue

        num_players = len(group)
        if num_players == 1:
            group[0].screen_x = cell_left + (CELL_WIDTH - PLAYER_SIZE[0]) // 2
        else:
            total_width = num_players * PLAYER_SIZE[0]
            spacing = (CELL_WIDTH - total_width) / (num_players + 1)
            start_x = cell_left + spacing
            
            for i, player in enumerate(group):
                player.screen_x = start_x + i * (PLAYER_SIZE[0] + spacing)
                player.screen_x = min(player.screen_x, cell_right - PLAYER_SIZE[0] - spacing)

        for player in group:
            player.screen_x = int(player.screen_x)

def load_sound(file):
    try:
        sound = pygame.mixer.Sound(file)
        sound.set_volume(SFX_VOLUME)
        return sound
    except pygame.error as e:
        print(f"Ошибка загрузки звука: {e}")
        return None

class DiceAnimation:
    def __init__(self):
        self.frames = [pygame.Surface((50, 50)) for _ in range(6)]
        for i in range(6):
            self.frames[i].fill((255, 255, 255))
            text = pygame.font.Font(None, 40).render(str(i+1), True, (0, 0, 0))
            self.frames[i].blit(text, (15, 10))
        self.current_frame = 0
        self.is_animating = False
        self.last_result = 1
        self.show_result = False

    def animate(self, screen, pos):
        if self.is_animating:
            self.current_frame = (self.current_frame + 1) % 6
            if self.current_frame == 0:
                self.is_animating = False
                self.show_result = True
                self.last_result = random.randint(1,6)
        
        # Всегда показываем последний результат
        if self.show_result:
            screen.blit(self.frames[self.last_result-1], pos)
        elif self.is_animating:
            screen.blit(self.frames[self.current_frame], pos)

def main():
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.DOUBLEBUF)
    pygame.display.set_caption("404: Leadership Not Found")
    clock = pygame.time.Clock()
    
    # Шрифты
    font = pygame.font.Font(None, 36)
    quest_font = pygame.font.Font(None, 28)
    cell_font = pygame.font.Font(None, 22)
    
    # Звуки
    pygame.mixer.init()
    sounds = {
        'dice': load_sound(DICE_SOUND),
        'win': load_sound(WIN_SOUND),
        'click': load_sound(BUTTON_CLICK)
    }
    
    # Музыка
    try:
        pygame.mixer.music.load(BG_MUSIC)
        pygame.mixer.music.set_volume(MUSIC_VOLUME)
        pygame.mixer.music.play(-1)
    except pygame.error as e:
        print(f"Ошибка загрузки музыки: {e}")

    # Игровые данные
    quests = [
        "Спорт: Повторите 5 упражнений!",
        "Пантомима: Угадайте слово!",
        "Слова: Назовите 5 предметов!",
        "Рисование: Угадайте рисунок!",
        "Математика: Решите пример!",
        "Актёрское мастерство: Изобразите эмоцию!"
    ]
    
    game_state = GameState()
    dice_anim = DiceAnimation()
    running = True
    start_time = datetime.now()

    # Основной игровой цикл
    while running:
        screen.fill(CELL_COLOR)
        
        # Обработка событий
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
                
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if game_state.sound_on and sounds['click']:
                    sounds['click'].play()
                
                mouse_x, mouse_y = pygame.mouse.get_pos()
                
                # Кнопка звука
                if 700 <= mouse_x <= 750 and 20 <= mouse_y <= 70:
                    game_state.sound_on = not game_state.sound_on
                    pygame.mixer.music.set_volume(MUSIC_VOLUME if game_state.sound_on else 0)
                    for s in sounds.values():
                        if s: s.set_volume(SFX_VOLUME if game_state.sound_on else 0)
                
                # Выбор игроков
                if not game_state.players_selected:
                    if 150 <= mouse_x <= 300 and 480 <= mouse_y <= 530:
                        game_state.players_count = 2
                    elif 350 <= mouse_x <= 500 and 480 <= mouse_y <= 530:
                        game_state.players_count = 3
                    elif 550 <= mouse_x <= 700 and 480 <= mouse_y <= 530:
                        game_state.players_count = 4
                    else:
                        continue
                    
                    game_state.players = [
                        Player(
                            (random.randint(50, 255), 
                            random.randint(50, 255), 
                            random.randint(50, 255)), 
                            i
                        ) for i in range(game_state.players_count)
                    ]
                    game_state.players_selected = True
                    game_state.should_move_camera = True

                # Кнопка "Бросить кубик"
                elif game_state.players_selected and not game_state.winner:
                    dice_btn_rect = pygame.Rect(150, 150, 200, 50)
                    if dice_btn_rect.collidepoint(mouse_x, mouse_y):
                        if not game_state.is_quest_active and not dice_anim.show_result:
                            dice_anim.is_animating = True
                            game_state.active_quest = random.choice(quests)
                            game_state.is_quest_active = True
                            if game_state.sound_on and sounds['dice']:
                                sounds['dice'].play()

                    # Кнопка "Задание выполнено"
                    complete_btn_rect = pygame.Rect(150, 50, 200, 50)
                    if complete_btn_rect.collidepoint(mouse_x, mouse_y):
                        if game_state.is_quest_active and dice_anim.show_result:
                            game_state.steps_remaining = dice_anim.last_result
                            game_state.is_quest_active = False
                            game_state.is_moving = True
                            game_state.should_move_camera = True
                            dice_anim.is_animating = False
                            dice_anim.show_result = False

        # Логика движения камеры
        if game_state.should_move_camera:
            target_pos = game_state.players[game_state.leader].position
            target_offset = target_pos * CELL_WIDTH - SCREEN_WIDTH//2 + CELL_WIDTH//2
            game_state.field_offset += (target_offset - game_state.field_offset) * CAMERA_SPEED
            
            if abs(game_state.field_offset - target_offset) < 1:
                game_state.should_move_camera = False

        # Логика движения игрока
        if game_state.is_moving and game_state.steps_remaining > 0:
            current_player = game_state.players[game_state.leader]
            current_player.position += 1
            game_state.steps_remaining -= 1

            # Применение эффектов клеток
            if current_player.position in CELL_TYPES:
                effect = CELL_TYPES[current_player.position]["effect"]
                game_state.steps_remaining += effect
                if game_state.steps_remaining < 0:
                    game_state.steps_remaining = 0

            # Ограничение позиции
            if current_player.position > 60:
                current_player.position = 60

            # Обновление камеры
            game_state.should_move_camera = True

            # Завершение движения
            if game_state.steps_remaining <= 0:
                game_state.is_moving = False
                if current_player.position >= 60:
                    game_state.winner = game_state.leader
                    if game_state.sound_on and sounds['win']:
                        sounds['win'].play()
                else:
                    game_state.leader = (game_state.leader + 1) % game_state.players_count
                    game_state.should_move_camera = True

        # Отрисовка интерфейса
        if not game_state.players_selected:
            # Меню выбора игроков
            title_text = font.render("Выберите количество игроков:", True, TEXT_COLOR)
            screen.blit(title_text, (200, SCREEN_HEIGHT//2 - 50))
            
            buttons = [
                draw_button(font, "2 игрока", 150, 480),
                draw_button(font, "3 игрока", 350, 480),
                draw_button(font, "4 игрока", 550, 480)
            ]
            for btn, pos in buttons:
                screen.blit(btn, pos)
        else:
            # Игровое поле
            draw_cells(screen, cell_font, int(game_state.field_offset))
            calculate_player_positions(game_state.players, int(game_state.field_offset))
            
            # Отрисовка игроков
            for idx, player in enumerate(game_state.players):
                if -CELL_WIDTH < player.screen_x < SCREEN_WIDTH:
                    # Тень
                    pygame.draw.ellipse(screen, (0, 0, 0, 100), 
                                     (player.screen_x+3, PLAYER_Y+5, *PLAYER_SIZE))
                    # Фигура
                    pygame.draw.ellipse(screen, player.color, 
                                     (player.screen_x, PLAYER_Y, *PLAYER_SIZE))
                    pygame.draw.ellipse(screen, BUTTON_BORDER_COLOR, 
                                     (player.screen_x, PLAYER_Y, *PLAYER_SIZE), 2)
                    
                    # Номер игрока
                    number_text = font.render(str(idx+1), True, TEXT_COLOR)
                    screen.blit(number_text, (player.screen_x + 10, PLAYER_Y - 20))

            # Кнопки интерфейса
            sound_btn, sound_pos = draw_button(font, "🔊" if game_state.sound_on else "🔇", 700, 20, 50)
            screen.blit(sound_btn, sound_pos)
            
            if game_state.is_quest_active:
                # Всегда показываем кубик после броска
                dice_anim.animate(screen, (400, 200))
                
                # Отображение задания и результата
                quest_text = quest_font.render(game_state.active_quest, True, TEXT_COLOR)
                screen.blit(quest_text, (150, 300))
                complete_btn, complete_pos = draw_button(font, "Задание выполнено!", 150, 50)
                screen.blit(complete_btn, complete_pos)
                
                # Отображение результата
                if dice_anim.show_result:
                    result_text = quest_font.render(f"Результат: {dice_anim.last_result}", True, (0, 0, 0))
                    screen.blit(result_text, (400, 260))
            else:
                if not game_state.winner:
                    dice_btn, dice_pos = draw_button(font, "Бросить кубик", 150, 150)
                    screen.blit(dice_btn, dice_pos)

            # Статистика
            stats_text = font.render(f"Рекорд: {game_state.stats['best_time']} сек", True, TEXT_COLOR)
            screen.blit(stats_text, (600, 100))

            if game_state.winner is not None:
                win_text = font.render(f"Победил {game_state.players[game_state.winner].name}!", True, (255, 0, 0))
                screen.blit(win_text, (250, SCREEN_HEIGHT//2))

        pygame.display.flip()
        clock.tick(FPS)

    # Завершение работы
    game_state.save_game()
    with open("stats.json", "w") as f:
        json.dump(game_state.stats, f)
    pygame.mixer.music.stop()
    pygame.quit()

if __name__ == "__main__":
    main()
