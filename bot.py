# blitz_stats_ultimate.py
import requests
import json
import time
from datetime import datetime
import io
import sys
import signal
import sqlite3
from typing import Dict, List, Optional

BOT_TOKEN = "8575145131:AAERhzW7TTjf3NT1aFEGfkjuDGN_ftMuAvw"
WG_API_KEY = "3c2a90c4b97e6e4660b62117dc8bfe2e"
ADMIN_IDS = [7635015201]
CHANNEL_USERNAME = "@freeaccountanksblitz"

class BlitzBotUltimate:
    def __init__(self):
        self.bot_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
        self.wg_url = "https://api.wotblitz.eu/wotb"
        self.offset = 0
        self.user_data = {}
        self.running = True
        self.search_history = []  # История поиска
        
        # Инициализация базы данных
        self.init_database()
        
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def init_database(self):
        """Инициализация базы данных SQLite"""
        self.conn = sqlite3.connect('bot_data.db')
        self.cursor = self.conn.cursor()
        
        # Таблица заблокированных пользователей
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS blocked_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица обязательных каналов
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS required_channels (
                channel_id TEXT PRIMARY KEY,
                channel_name TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица истории поиска
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                nickname TEXT,
                searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица пользователей
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def signal_handler(self, signum, frame):
        print("\n🛑 Получен сигнал остановки...")
        self.running = False
        time.sleep(1)
        print("👋 Бот остановлен")
        sys.exit(0)
    
    def is_user_blocked(self, user_id):
        """Проверка блокировки пользователя"""
        self.cursor.execute('SELECT user_id FROM blocked_users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone() is not None
    
    def block_user(self, user_id, reason="Нарушение правил"):
        """Блокировка пользователя"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO blocked_users (user_id, reason) 
                VALUES (?, ?)
            ''', (user_id, reason))
            self.conn.commit()
            return True
        except:
            return False
    
    def unblock_user(self, user_id):
        """Разблокировка пользователя"""
        try:
            self.cursor.execute('DELETE FROM blocked_users WHERE user_id = ?', (user_id,))
            self.conn.commit()
            return True
        except:
            return False
    
    def get_blocked_users(self):
        """Получение списка заблокированных пользователей"""
        self.cursor.execute('SELECT user_id, reason, blocked_at FROM blocked_users ORDER BY blocked_at DESC')
        return self.cursor.fetchall()
    
    def add_required_channel(self, channel_id, channel_name):
        """Добавление обязательного канала"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO required_channels (channel_id, channel_name) 
                VALUES (?, ?)
            ''', (channel_id, channel_name))
            self.conn.commit()
            return True
        except:
            return False
    
    def remove_required_channel(self, channel_id):
        """Удаление обязательного канала"""
        try:
            self.cursor.execute('DELETE FROM required_channels WHERE channel_id = ?', (channel_id,))
            self.conn.commit()
            return True
        except:
            return False
    
    def get_required_channels(self):
        """Получение списка обязательных каналов"""
        self.cursor.execute('SELECT channel_id, channel_name FROM required_channels')
        return self.cursor.fetchall()
    
    def add_to_search_history(self, user_id, nickname):
        """Добавление в историю поиска"""
        try:
            self.cursor.execute('''
                INSERT INTO search_history (user_id, nickname) 
                VALUES (?, ?)
            ''', (user_id, nickname))
            self.conn.commit()
            
            # Обновляем активность пользователя
            self.update_user_activity(user_id)
        except:
            pass
    
    def get_search_history(self, limit=100):
        """Получение истории поиска"""
        self.cursor.execute('''
            SELECT sh.nickname, COUNT(*) as searches, 
                   GROUP_CONCAT(DISTINCT sh.user_id) as users,
                   MAX(sh.searched_at) as last_search
            FROM search_history sh
            GROUP BY sh.nickname
            ORDER BY searches DESC
            LIMIT ?
        ''', (limit,))
        return self.cursor.fetchall()
    
    def update_user_activity(self, user_id):
        """Обновление активности пользователя"""
        try:
            # Проверяем существует ли пользователь
            self.cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
            if not self.cursor.fetchone():
                # Добавляем нового пользователя
                # Здесь нужно получить данные пользователя из message
                # Пока добавим заглушку
                self.cursor.execute('''
                    INSERT OR IGNORE INTO users (user_id) 
                    VALUES (?)
                ''', (user_id,))
            else:
                # Обновляем время активности
                self.cursor.execute('''
                    UPDATE users 
                    SET last_activity = CURRENT_TIMESTAMP 
                    WHERE user_id = ?
                ''', (user_id,))
            self.conn.commit()
        except:
            pass
    
    def get_user_stats(self):
        """Статистика пользователей"""
        self.cursor.execute('SELECT COUNT(*) FROM users')
        total_users = self.cursor.fetchone()[0]
        
        self.cursor.execute('SELECT COUNT(*) FROM users WHERE last_activity > datetime("now", "-7 days")')
        active_users = self.cursor.fetchone()[0]
        
        self.cursor.execute('SELECT COUNT(*) FROM search_history')
        total_searches = self.cursor.fetchone()[0]
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'total_searches': total_searches
        }
    
    def check_subscription(self, user_id):
        """Проверка подписки на обязательные каналы"""
        channels = self.get_required_channels()
        
        for channel in channels:
            channel_id = channel[0]
            try:
                response = requests.post(
                    f"{self.bot_url}/getChatMember",
                    json={
                        'chat_id': channel_id,
                        'user_id': user_id
                    },
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('ok'):
                        status = data['result'].get('status')
                        if status not in ['member', 'administrator', 'creator']:
                            return False
                else:
                    return False
            except:
                return False
        
        return True if channels else True
    
    def make_request(self, url, params):
        try:
            response = requests.get(url, params=params, timeout=10, verify=False)
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None
    
    def get_updates(self):
        try:
            response = requests.get(
                f"{self.bot_url}/getUpdates",
                params={'offset': self.offset, 'timeout': 30},
                timeout=35
            )
            return response.json()
        except:
            return {'ok': False}
    
    def send_message(self, chat_id, text, keyboard=None, parse_mode='Markdown'):
        try:
            payload = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            if keyboard:
                payload['reply_markup'] = json.dumps(keyboard)
            
            requests.post(f"{self.bot_url}/sendMessage", json=payload, timeout=10)
        except:
            pass
    
    def send_document(self, chat_id, content, filename, caption=""):
        try:
            files = {'document': (filename, io.BytesIO(content.encode('utf-8')), 'text/plain')}
            data = {'chat_id': chat_id, 'caption': caption}
            requests.post(f"{self.bot_url}/sendDocument", files=files, data=data, timeout=30)
        except:
            pass
    
    def send_broadcast(self, message_text):
        """Рассылка сообщения всем пользователям"""
        try:
            self.cursor.execute('SELECT user_id FROM users')
            users = self.cursor.fetchall()
            
            success = 0
            failed = 0
            
            for user in users:
                user_id = user[0]
                try:
                    self.send_message(user_id, message_text)
                    success += 1
                    time.sleep(0.1)  # Задержка чтобы не превысить лимиты Telegram
                except:
                    failed += 1
            
            return success, failed
        except:
            return 0, 0
    
    def search_player(self, nickname):
        try:
            data = self.make_request(
                f"{self.wg_url}/account/list/",
                {'application_id': WG_API_KEY, 'search': nickname, 'limit': 1}
            )
            if data and data.get('data'):
                return data['data'][0]['account_id']
        except:
            pass
        return None
    
    def get_player_stats(self, account_id):
        try:
            data = self.make_request(
                f"{self.wg_url}/account/info/",
                {
                    'application_id': WG_API_KEY,
                    'account_id': account_id,
                    'fields': 'nickname,created_at,last_battle_time,statistics.all'
                }
            )
            
            if data and str(account_id) in data.get('data', {}):
                player = data['data'][str(account_id)]
                stats = player.get('statistics', {}).get('all', {})
                
                battles = stats.get('battles', 0)
                wins = stats.get('wins', 0)
                damage = stats.get('damage_dealt', 0)
                survived = stats.get('survived_battles', 0)
                hits = stats.get('hits', 0)
                shots = stats.get('shots', 0)
                frags = stats.get('frags', 0)
                max_xp = stats.get('max_xp', 0)
                
                winrate = (wins / battles * 100) if battles > 0 else 0
                avg_damage = (damage / battles) if battles > 0 else 0
                survival = (survived / battles * 100) if battles > 0 else 0
                accuracy = (hits / shots * 100) if shots > 0 else 0
                avg_frags = (frags / battles) if battles > 0 else 0
                
                return {
                    'nickname': player.get('nickname'),
                    'created_at': player.get('created_at'),
                    'last_battle': player.get('last_battle_time'),
                    'battles': battles,
                    'wins': wins,
                    'winrate': winrate,
                    'damage': avg_damage,
                    'survival': survival,
                    'accuracy': accuracy,
                    'frags': avg_frags,
                    'max_xp': max_xp
                }
        except:
            pass
        return None
    
    def get_player_tanks(self, account_id):
        """Получение списка танков в ангаре"""
        try:
            endpoints = [
                f"{self.wg_url}/account/tanks/",
                f"{self.wg_url}/tanks/stats/",
                f"{self.wg_url}/tanks/achievements/",
            ]
            
            for endpoint in endpoints:
                data = self.make_request(
                    endpoint,
                    {'application_id': WG_API_KEY, 'account_id': account_id}
                )
                
                if data and data.get('status') == 'ok' and 'data' in data:
                    if str(account_id) in data['data']:
                        tanks = data['data'][str(account_id)]
                        return tanks
            
            return []
        except Exception as e:
            return []
    
    def get_tank_names(self, tank_ids):
        """Получение названий танков"""
        if not tank_ids:
            return {}
        
        try:
            data = self.make_request(
                f"{self.wg_url}/encyclopedia/vehicles/",
                {'application_id': WG_API_KEY, 'tank_id': ','.join(map(str, tank_ids[:100]))}
            )
            
            if data and 'data' in data:
                return data['data']
            return {}
        except:
            return {}
    
    def format_main_message(self, stats):
        created = datetime.fromtimestamp(stats['created_at']).strftime('%d.%m.%Y %H:%M')
        last = datetime.fromtimestamp(stats['last_battle']).strftime('%d.%m.%Y %H:%M')
        
        message = f"👤 *{stats['nickname']}*\n"
        message += "➖➖➖➖➖➖➖➖➖➖\n"
        message += f"📅 Создан: `{created}`\n"
        message += f"🕒 Последний бой: `{last}`\n"
        message += "➖➖➖➖➖➖➖➖➖➖\n"
        message += f"⚔️ Боёв: `{stats['battles']}`\n"
        message += f"🏆 Побед: `{stats['wins']}` (`{stats['winrate']:.2f}%`)\n"
        message += f"💥 Ср. урон: `{int(stats['damage'])}`\n"
        message += f"🛡 Выживаемость: `{stats['survival']:.2f}%`\n"
        message += f"🎯 Точность: `{stats['accuracy']:.2f}%`\n"
        message += f"🎖 Фрагов за бой: `{stats['frags']:.2f}`\n"
        message += f"🌟 Макс. опыт: `{int(stats['max_xp'])}`\n"
        
        return message
    
    def format_tanks_message(self, nickname, tanks, tank_names):
        if not tanks:
            return "🚙 *Ангар игрока:*\n\nТанки не найдены"
        
        message = f"🚙 *Ангар игрока {nickname}:*\n"
        message += "➖➖➖➖➖➖➖➖➖➖\n\n"
        
        tank_list = []
        for tank in tanks:
            tank_id = tank['tank_id']
            tank_info = tank_names.get(str(tank_id), {})
            tank_name = tank_info.get('name', f'Танк {tank_id}')
            tier = tank_info.get('tier', '?')
            
            tank_list.append({
                'name': tank_name,
                'tier': tier,
                'id': tank_id
            })
        
        tank_list.sort(key=lambda x: x['tier'], reverse=True)
        
        for tank in tank_list:
            message += f"• [{tank['tier']}] {tank['name']}\n"
        
        message += f"\n📊 Всего танков: {len(tanks)}"
        return message
    
    def create_keyboard(self):
        return {
            "inline_keyboard": [
                [
                    {"text": "📊Общее", "callback_data": "main_stats"},
                    {"text": "🚙 Ангар", "callback_data": "hangar"}
                ],
                [
                    {"text": "📢 Стат. в файл", "callback_data": "stats_file"},
                    {"text": "📁 Ангар в файл", "callback_data": "hangar_file"}
                ]
            ]
        }
    
    def create_admin_keyboard(self):
        return {
            "inline_keyboard": [
                [
                    {"text": "📊 Статистика", "callback_data": "admin_stats"},
                    {"text": "👥 Пользователи", "callback_data": "admin_users"}
                ],
                [
                    {"text": "🚫 Блокировки", "callback_data": "admin_blocks"},
                    {"text": "📢 Каналы", "callback_data": "admin_channels"}
                ],
                [
                    {"text": "📨 Рассылка", "callback_data": "admin_broadcast"},
                    {"text": "📁 История", "callback_data": "admin_history"}
                ],
                [
                    {"text": "🔄 Перезапуск", "callback_data": "restart"},
                    {"text": "❌ Выход", "callback_data": "exit_admin"}
                ]
            ]
        }
    
    def generate_stats_file(self, nickname, stats, tanks, tank_names):
        created = datetime.fromtimestamp(stats['created_at']).strftime('%d.%m.%Y %H:%M')
        last = datetime.fromtimestamp(stats['last_battle']).strftime('%d.%m.%Y %H:%M')
        
        content = f"👤 {nickname}\n"
        content += "➖➖➖➖➖➖➖➖➖➖\n"
        content += f"📅 Создан: {created}\n"
        content += f"🕒 Последний бой: {last}\n"
        content += "➖➖➖➖➖➖➖➖➖➖\n"
        content += f"⚔️ Боёв: {stats['battles']}\n"
        content += f"🏆 Побед: {stats['wins']} ({stats['winrate']:.2f}%)\n"
        content += f"💥 Ср. урон: {int(stats['damage'])}\n"
        content += f"🛡 Выживаемость: {stats['survival']:.2f}%\n"
        content += f"🎯 Точность: {stats['accuracy']:.2f}%\n"
        content += f"🎖 Фрагов за бой: {stats['frags']:.2f}\n"
        content += f"🌟 Макс. опыт: {int(stats['max_xp'])}\n\n"
        
        if tanks:
            content += "🚙 ТАНКИ В АНГАРЕ:\n"
            content += "=" * 30 + "\n\n"
            
            tank_list = []
            for tank in tanks:
                tank_id = tank['tank_id']
                tank_info = tank_names.get(str(tank_id), {})
                tank_name = tank_info.get('name', f'Танк {tank_id}')
                tier = tank_info.get('tier', '?')
                type_ = tank_info.get('type', 'Танк')
                nation = tank_info.get('nation', 'Неизвестно')
                
                tank_list.append({
                    'name': tank_name,
                    'tier': tier,
                    'type': type_,
                    'nation': nation
                })
            
            tank_list.sort(key=lambda x: x['tier'], reverse=True)
            
            current_tier = None
            for tank in tank_list:
                if tank['tier'] != current_tier:
                    current_tier = tank['tier']
                    content += f"\n[Уровень {tank['tier']}]\n"
                    content += "-" * 20 + "\n"
                
                content += f"{tank['name']} ({tank['type']}, {tank['nation']})\n"
            
            content += f"\nВсего танков: {len(tanks)}"
        else:
            content += "🚙 ТАНКИ В АНГАРЕ:\n"
            content += "Танки не найдены\n"
        
        return content
    
    def generate_hangar_file(self, nickname, tanks, tank_names):
        content = f"🚙 АНГАР ИГРОКА: {nickname}\n"
        content += "=" * 40 + "\n\n"
        
        if not tanks:
            content += "Танки не найдены\n"
            return content
        
        tank_list = []
        for tank in tanks:
            tank_id = tank['tank_id']
            tank_info = tank_names.get(str(tank_id), {})
            tank_name = tank_info.get('name', f'Танк {tank_id}')
            tier = tank_info.get('tier', '?')
            type_ = tank_info.get('type', 'Танк')
            nation = tank_info.get('nation', 'Неизвестно')
            
            tank_list.append({
                'name': tank_name,
                'tier': tier,
                'type': type_,
                'nation': nation
            })
        
        tank_list.sort(key=lambda x: (x['tier'], x['name']), reverse=True)
        
        current_tier = None
        for tank in tank_list:
            if tank['tier'] != current_tier:
                current_tier = tank['tier']
                content += f"\n[Уровень {tank['tier']}]\n"
                content += "-" * 20 + "\n"
            
            content += f"{tank['name']} ({tank['type']}, {tank['nation']})\n"
        
        content += f"\nВсего танков: {len(tanks)}"
        return content
    
    def generate_search_history_file(self):
        """Генерация файла с историей поиска"""
        history = self.get_search_history(100)
        
        content = "📊 ИСТОРИЯ ПОИСКА АККАУНТОВ\n"
        content += "=" * 50 + "\n\n"
        
        if not history:
            content += "История поиска пуста\n"
            return content
        
        content += f"Всего уникальных поисков: {len(history)}\n\n"
        
        for i, item in enumerate(history, 1):
            nickname, searches, users, last_search = item
            user_list = users.split(',')
            
            content += f"{i}. {nickname}\n"
            content += f"   🔍 Количество поисков: {searches}\n"
            content += f"   👥 Пользователей искали: {len(user_list)}\n"
            content += f"   🕒 Последний поиск: {last_search}\n"
            content += "-" * 40 + "\n"
        
        return content
    
    def send_subscription_message(self, chat_id):
        channels = self.get_required_channels()
        
        if not channels:
            message = "📢 Подписка на канал обязательна!"
            keyboard = {
                "inline_keyboard": [
                    [{"text": "📢 Подписаться на канал", "url": f"https://t.me/{CHANNEL_USERNAME[1:]}"}],
                    [{"text": "✅ Я подписался", "callback_data": "check_subscription"}]
                ]
            }
        else:
            message = "📢 Для использования бота необходимо подписаться на следующие каналы:\n\n"
            keyboard_buttons = []
            
            for channel in channels:
                channel_id, channel_name = channel
                message += f"• {channel_name}\n"
                # Используем username если есть, иначе ID
                if channel_id.startswith('@'):
                    url = f"https://t.me/{channel_id[1:]}"
                else:
                    # Для ID каналов нужно другое форматирование
                    url = f"https://t.me/c/{channel_id[4:]}" if str(channel_id).startswith('-100') else f"https://t.me/{channel_id}"
                
                keyboard_buttons.append([{"text": f"📢 {channel_name}", "url": url}])
            
            keyboard_buttons.append([{"text": "✅ Я подписался", "callback_data": "check_subscription"}])
            
            keyboard = {"inline_keyboard": keyboard_buttons}
        
        self.send_message(chat_id, message, keyboard)
    
    def process_message(self, message):
        chat_id = message['chat']['id']
        user_id = message['from']['id']
        text = message.get('text', '').strip()
        
        # Проверка блокировки
        if self.is_user_blocked(user_id):
            self.send_message(chat_id, "❌ Вы заблокированы в этом боте.")
            return
        
        # Админ команды
        if text.startswith('/admin') and user_id in ADMIN_IDS:
            admin_keyboard = self.create_admin_keyboard()
            self.send_message(chat_id, "👑 *ПАНЕЛЬ АДМИНИСТРАТОРА*", admin_keyboard)
            return
        
        # Админ команды для управления
        if user_id in ADMIN_IDS:
            if text.startswith('/block '):
                try:
                    block_user_id = int(text.split()[1])
                    reason = ' '.join(text.split()[2:]) if len(text.split()) > 2 else "Нарушение правил"
                    if self.block_user(block_user_id, reason):
                        self.send_message(chat_id, f"✅ Пользователь {block_user_id} заблокирован.\nПричина: {reason}")
                    else:
                        self.send_message(chat_id, "❌ Ошибка блокировки пользователя")
                except:
                    self.send_message(chat_id, "❌ Использование: /block <user_id> [причина]")
                return
            
            elif text.startswith('/unblock '):
                try:
                    unblock_user_id = int(text.split()[1])
                    if self.unblock_user(unblock_user_id):
                        self.send_message(chat_id, f"✅ Пользователь {unblock_user_id} разблокирован")
                    else:
                        self.send_message(chat_id, "❌ Ошибка разблокировки пользователя")
                except:
                    self.send_message(chat_id, "❌ Использование: /unblock <user_id>")
                return
            
            elif text.startswith('/addchannel '):
                try:
                    parts = text.split()
                    if len(parts) >= 3:
                        channel_id = parts[1]
                        channel_name = ' '.join(parts[2:])
                        if self.add_required_channel(channel_id, channel_name):
                            self.send_message(chat_id, f"✅ Канал добавлен: {channel_name}")
                        else:
                            self.send_message(chat_id, "❌ Ошибка добавления канала")
                    else:
                        self.send_message(chat_id, "❌ Использование: /addchannel <channel_id> <channel_name>")
                except:
                    self.send_message(chat_id, "❌ Ошибка добавления канала")
                return
            
            elif text.startswith('/removechannel '):
                try:
                    channel_id = text.split()[1]
                    if self.remove_required_channel(channel_id):
                        self.send_message(chat_id, "✅ Канал удален")
                    else:
                        self.send_message(chat_id, "❌ Ошибка удаления канала")
                except:
                    self.send_message(chat_id, "❌ Использование: /removechannel <channel_id>")
                return
        
        if text == '/start':
            # Проверка подписки
            if not self.check_subscription(user_id):
                self.send_subscription_message(chat_id)
                return
            
            welcome = (
                "🎮 *STATS WoT Blitz*\n\n"
                "Привет, танкист!\n\n"
                "Я покажу статистику и ангар игрока WoT Blitz.\n"
                "Просто отправь мне никнейм игрока.\n\n"
                "*Пример:* `PRO_100_IGROK`\n\n"
                "by @freeaccountanksblitz"
            )
            self.send_message(chat_id, welcome)
            return
        
        if not text:
            return
        
        # Проверка подписки перед поиском
        if not self.check_subscription(user_id):
            self.send_subscription_message(chat_id)
            return
        
        self.send_message(chat_id, f"🔍 Ищу игрока `{text}`...")
        
        # Добавляем в историю поиска
        self.add_to_search_history(user_id, text)
        
        account_id = self.search_player(text)
        if not account_id:
            self.send_message(chat_id, f"❌ Игрок `{text}` не найден.")
            return
        
        stats = self.get_player_stats(account_id)
        if not stats:
            self.send_message(chat_id, "❌ Ошибка получения данных.")
            return
        
        # Получаем танки игрока
        tanks = self.get_player_tanks(account_id)
        tank_names = {}
        if tanks:
            tank_ids = [tank['tank_id'] for tank in tanks]
            tank_names = self.get_tank_names(tank_ids)
        
        self.user_data[f"{chat_id}_data"] = {
            'nickname': text,
            'stats': stats,
            'tanks': tanks,
            'tank_names': tank_names
        }
        
        main_message = self.format_main_message(stats)
        self.send_message(chat_id, main_message)
        
        keyboard = self.create_keyboard()
        self.send_message(chat_id, "📊 Выберите действие:", keyboard)
    
    def handle_callback(self, callback_query):
        chat_id = callback_query['message']['chat']['id']
        user_id = callback_query['from']['id']
        callback_id = callback_query['id']
        data = callback_query['data']
        
        try:
            requests.post(
                f"{self.bot_url}/answerCallbackQuery",
                json={'callback_query_id': callback_id}
            )
        except:
            pass
        
        # Проверка блокировки
        if self.is_user_blocked(user_id):
            return
        
        # Админ функции
        if user_id in ADMIN_IDS:
            if data == 'admin_stats':
                bot_stats = f"📊 *СТАТИСТИКА БОТА:*\n\n"
                bot_stats += f"👥 Пользователей в памяти: {len(self.user_data)}\n"
                bot_stats += f"🔄 Смещение updates: {self.offset}\n"
                bot_stats += f"🟢 Статус: {'Работает' if self.running else 'Останавливается'}\n\n"
                
                user_stats = self.get_user_stats()
                bot_stats += f"📈 *СТАТИСТИКА БАЗЫ ДАННЫХ:*\n"
                bot_stats += f"👤 Всего пользователей: {user_stats['total_users']}\n"
                bot_stats += f"🎯 Активных (7 дней): {user_stats['active_users']}\n"
                bot_stats += f"🔍 Всего поисков: {user_stats['total_searches']}\n"
                
                self.send_message(chat_id, bot_stats)
                return
                
            elif data == 'admin_users':
                self.cursor.execute('SELECT COUNT(*) FROM users')
                total = self.cursor.fetchone()[0]
                
                self.cursor.execute('SELECT user_id, username, joined_at FROM users ORDER BY joined_at DESC LIMIT 10')
                users = self.cursor.fetchall()
                
                message = f"👥 *ПОЛЬЗОВАТЕЛИ БОТА:*\n\n"
                message += f"Всего пользователей: {total}\n\n"
                message += "Последние 10 пользователей:\n"
                
                for user in users:
                    user_id, username, joined_at = user
                    message += f"• ID: {user_id}"
                    if username:
                        message += f" (@{username})"
                    message += f"\n  📅 Присоединился: {joined_at}\n"
                
                self.send_message(chat_id, message)
                return
                
            elif data == 'admin_blocks':
                blocked = self.get_blocked_users()
                
                if not blocked:
                    self.send_message(chat_id, "🚫 *ЗАБЛОКИРОВАННЫЕ ПОЛЬЗОВАТЕЛИ:*\n\nНет заблокированных пользователей")
                    return
                
                message = "🚫 *ЗАБЛОКИРОВАННЫЕ ПОЛЬЗОВАТЕЛИ:*\n\n"
                for block in blocked:
                    user_id, reason, blocked_at = block
                    message += f"• ID: {user_id}\n"
                    message += f"  Причина: {reason}\n"
                    message += f"  Дата: {blocked_at}\n\n"
                
                self.send_message(chat_id, message)
                return
                
            elif data == 'admin_channels':
                channels = self.get_required_channels()
                
                if not channels:
                    self.send_message(chat_id, "📢 *ОБЯЗАТЕЛЬНЫЕ КАНАЛЫ:*\n\nНет обязательных каналов")
                    return
                
                message = "📢 *ОБЯЗАТЕЛЬНЫЕ КАНАЛЫ:*\n\n"
                for channel in channels:
                    channel_id, channel_name = channel
                    message += f"• {channel_name}\n"
                    message += f"  ID: {channel_id}\n\n"
                
                self.send_message(chat_id, message)
                return
                
            elif data == 'admin_broadcast':
                self.user_data[f"{chat_id}_broadcast"] = True
                self.send_message(chat_id, "📨 *РАССЫЛКА СООБЩЕНИЙ:*\n\nОтправьте сообщение для рассылки всем пользователям бота.")
                return
                
            elif data == 'admin_history':
                history = self.get_search_history(20)
                
                if not history:
                    self.send_message(chat_id, "📊 *ИСТОРИЯ ПОИСКА:*\n\nИстория поиска пуста")
                    return
                
                message = "📊 *ТОП 20 ПОИСКОВЫХ ЗАПРОСОВ:*\n\n"
                for i, item in enumerate(history[:20], 1):
                    nickname, searches, users, last_search = item
                    user_list = users.split(',')
                    
                    message += f"{i}. *{nickname}*\n"
                    message += f"   🔍 Поисков: {searches}\n"
                    message += f"   👥 Пользователей: {len(user_list)}\n"
                    message += f"   🕒 Последний: {last_search}\n\n"
                
                # Кнопка для скачивания полной истории
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "📁 Скачать полную историю", "callback_data": "download_history"}]
                    ]
                }
                self.send_message(chat_id, message, keyboard)
                return
                
            elif data == 'download_history':
                history_content = self.generate_search_history_file()
                self.send_document(
                    chat_id,
                    history_content,
                    "search_history.txt",
                    "📊 История поиска аккаунтов"
                )
                return
                
            elif data == 'restart':
                self.send_message(chat_id, "🔄 Перезапуск бота...")
                time.sleep(2)
                self.running = False
                return
                
            elif data == 'exit_admin':
                self.send_message(chat_id, "👋 Выход из админ-панели")
                return
        
        # Проверка подписки для обычных пользователей
        if data not in ['check_subscription', 'admin_stats', 'admin_users', 'admin_blocks', 
                       'admin_channels', 'admin_broadcast', 'admin_history', 'download_history',
                       'restart', 'exit_admin']:
            if not self.check_subscription(user_id):
                self.send_subscription_message(chat_id)
                return
        
        if data == 'check_subscription':
            if self.check_subscription(user_id):
                self.send_message(chat_id, "✅ Отлично! Теперь можете использовать бота.\nОтправьте /start для начала работы.")
            else:
                self.send_subscription_message(chat_id)
            return
        
        # Обработка рассылки (админ ввел текст для рассылки)
        if self.user_data.get(f"{chat_id}_broadcast"):
            del self.user_data[f"{chat_id}_broadcast"]
            success, failed = self.send_broadcast(data)
            self.send_message(chat_id, f"📨 *РЕЗУЛЬТАТ РАССЫЛКИ:*\n\n✅ Отправлено: {success}\n❌ Не отправлено: {failed}")
            return
        
        user_data = self.user_data.get(f"{chat_id}_data")
        if not user_data:
            self.send_message(chat_id, "❌ Данные не найдены. Отправьте никнейм снова.")
            return
        
        if data == 'main_stats':
            main_message = self.format_main_message(user_data['stats'])
            self.send_message(chat_id, main_message)
        
        elif data == 'hangar':
            tanks_message = self.format_tanks_message(
                user_data['nickname'],
                user_data['tanks'],
                user_data['tank_names']
            )
            self.send_message(chat_id, tanks_message)
        
        elif data == 'stats_file':
            stats_content = self.generate_stats_file(
                user_data['nickname'],
                user_data['stats'],
                user_data['tanks'],
                user_data['tank_names']
            )
            self.send_document(
                chat_id,
                stats_content,
                f"{user_data['nickname']}_stats.txt",
                f"📊 Полная статистика игрока {user_data['nickname']}"
            )
        
        elif data == 'hangar_file':
            hangar_content = self.generate_hangar_file(
                user_data['nickname'],
                user_data['tanks'],
                user_data['tank_names']
            )
            self.send_document(
                chat_id,
                hangar_content,
                f"{user_data['nickname']}_hangar.txt",
                f"🚙 Ангар игрока {user_data['nickname']}"
            )
    
    def run(self):
        print("=" * 60)
        print("🤖 WoT BLITZ STATS BOT - PRO EDITION")
        print("=" * 60)
        print("✅ База данных SQLite")
        print("✅ Блокировка пользователей")
        print("✅ Обязательные каналы")
        print("✅ Рассылка сообщений")
        print("✅ История поиска аккаунтов")
        print("✅ Статистика пользователей")
        print("📊 Показывает статистику и ангар игрока")
        print("📁 Скачивание статистики и ангара в файлы")
        print("👑 Расширенная админ панель (/admin)")
        print("🛑 Остановка: Ctrl+C")
        print("=" * 60)
        print("\nБот запущен...")
        print(f"📁 База данных: bot_data.db")
        print(f"👑 Админы: {ADMIN_IDS}\n")
        
        while self.running:
            try:
                updates = self.get_updates()
                
                if updates.get('ok'):
                    for update in updates.get('result', []):
                        self.offset = update['update_id'] + 1
                        
                        if 'message' in update:
                            self.process_message(update['message'])
                        elif 'callback_query' in update:
                            self.handle_callback(update['callback_query'])
                
                time.sleep(0.3)
                
            except KeyboardInterrupt:
                print("\n🛑 Остановка бота...")
                self.running = False
                break
            except Exception as e:
                print(f"⚠️ Ошибка: {e}")
                time.sleep(1)
        
        # Закрываем соединение с базой данных
        self.conn.close()
        print("\n👋 Бот остановлен")
        sys.exit(0)

bat_content = '''@echo off
chcp 65001 > nul
cls
echo.
echo    WoT Blitz Stats Bot - Pro Edition
echo    =================================
echo.
echo 📁 База данных: bot_data.db
echo 👑 Расширенная админ-панель
echo 📊 История поиска аккаунтов
echo 🚫 Система блокировок
echo 📢 Рассылка сообщений
echo.
echo Запуск бота...
python blitz_stats_ultimate.py
pause
'''

with open('launch.bat', 'w', encoding='utf-8') as f:
    f.write(bat_content)

print("✅ Создан launch.bat для запуска")

if __name__ == '__main__':
    bot = BlitzBotUltimate()
    bot.run()