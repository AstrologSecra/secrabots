import telebot
from telebot import types
import sqlite3
import logging
import random
import string
import os
import threading

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ваши токены
TOKEN_SONGS = '7809873842:AAHD8XSChp9wJnkURj32v6I6ehRwjr0kwO4'
TOKEN_WALLETS = '7398848733:AAHvSzM68NHwB-P-sgkpdHEQ_LUkJICr-NM'

# Создание ботов
bot_songs = telebot.TeleBot(TOKEN_SONGS)
bot_wallets = telebot.TeleBot(TOKEN_WALLETS)

# Создание и подключение к базе данных SQLite
conn = sqlite3.connect('songs.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц для хранения пользователей и админов
cursor.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, role TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS wallets (user_id INTEGER PRIMARY KEY, wallet_id TEXT, balance INTEGER DEFAULT 0)''')

conn.commit()

# ID владельца бота
OWNER_ID = 6829778011  # Замените на свой ID

# Проверка прав пользователя
def is_admin(user_id):
    cursor.execute("SELECT * FROM admins WHERE user_id = ?", (user_id,))
    return cursor.fetchone() is not None

def is_owner(user_id):
    return user_id == OWNER_ID

# Генерация случайного кошелька
def generate_wallet_id():
    return ''.join(random.choices(string.ascii_letters, k=8))

# Приветственное сообщение и справка по командам
@bot_wallets.message_handler(commands=['start'])
def welcome(message):
    try:
        bot_wallets.reply_to(message, "Привет! Используйте команды или специальные фразы для управления ботом.\n/help - для получения списка команд.")
    except Exception as e:
        logging.error(f"Error in welcome: {e}")

@bot_wallets.message_handler(commands=['help'])
def help_message(message):
    try:
        help_text = (
            "/start - Приветственное сообщение\n"
            "/help - Список команд\n"
            "/create_wallet - Создать виртуальный кошелек\n"
            "/balance - Показать баланс кошелька\n"
            "/transfer - Перевести FSEC на другой кошелек\n"
            "/add_fsec - Добавить FSEC на кошелек (только для владельца)\n"
            "/add_fsec_to_all - Добавить FSEC всем пользователям (только для владельца)\n"
            "/reset_owner_balance - Обнулить баланс владельца\n"
        )
        bot_wallets.reply_to(message, help_text)
    except Exception as e:
        logging.error(f"Error in help_message: {e}")

# Хэндлер для создания виртуального кошелька
@bot_wallets.message_handler(commands=['create_wallet'])
def create_wallet(message):
    try:
        user_id = message.from_user.id
        existing_wallet = cursor.execute("SELECT * FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
        if existing_wallet:
            bot_wallets.reply_to(message, f"У вас уже есть кошелек: {existing_wallet[1]}")
        else:
            wallet_id = generate_wallet_id()
            cursor.execute("INSERT INTO wallets (user_id, wallet_id) VALUES (?, ?)", (user_id, wallet_id))
            conn.commit()
            bot_wallets.reply_to(message, f"Ваш новый кошелек создан: {wallet_id}")
    except Exception as e:
        logging.error(f"Error in create_wallet: {e}")

# Хэндлер для показа баланса кошелька
@bot_wallets.message_handler(commands=['balance'])
def show_balance(message):
    try:
        user_id = message.from_user.id
        wallet_info = cursor.execute("SELECT wallet_id, balance FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
        if wallet_info:
            bot_wallets.reply_to(message, f"Ваш кошелек: {wallet_info[0]}\nБаланс: {wallet_info[1]} FSEC")
        else:
            bot_wallets.reply_to(message, "У вас нет кошелька. Создайте его командой /create_wallet.")
    except Exception as e:
        logging.error(f"Error in show_balance: {e}")

# Хэндлер для перевода FSEC на другой кошелек
@bot_wallets.message_handler(commands=['transfer'])
def transfer_coins(message):
    try:
        user_id = message.from_user.id
        sender_wallet = cursor.execute("SELECT * FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
        if not sender_wallet:
            bot_wallets.reply_to(message, "У вас нет кошелька. Создайте его командой /create_wallet.")
            return
        bot_wallets.reply_to(message, "Введите ID кошелька получателя и количество FSEC для перевода (через пробел):")
        bot_wallets.register_next_step_handler(message, process_transfer)
    except Exception as e:
        logging.error(f"Error in transfer_coins: {e}")

def process_transfer(message):
    try:
        user_id = message.from_user.id
        parts = message.text.split()
        if len(parts) != 2:
            bot_wallets.reply_to(message, "Неверный формат команды. Используйте: /transfer [ID кошелька] [количество FSEC]")
            return
        receiver_wallet_id, amount = parts[0], int(parts[1])
        receiver_wallet = cursor.execute("SELECT * FROM wallets WHERE wallet_id = ?", (receiver_wallet_id,)).fetchone()
        if not receiver_wallet:
            bot_wallets.reply_to(message, "Кошелек получателя не найден.")
            return
        sender_balance = cursor.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,)).fetchone()[0]
        if sender_balance < amount:
            bot_wallets.reply_to(message, "Недостаточно FSEC на вашем счету.")
            return
        cursor.execute("UPDATE wallets SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
        cursor.execute("UPDATE wallets SET balance = balance + ? WHERE wallet_id = ?", (amount, receiver_wallet_id))
        conn.commit()
        bot_wallets.reply_to(message, f"Перевод выполнен. {amount} FSEC переведено на кошелек {receiver_wallet_id}.")
    except Exception as e:
        logging.error(f"Error in process_transfer: {e}")

# Хэндлер для добавления FSEC на кошелек (только для владельца)
@bot_wallets.message_handler(commands=['add_fsec'])
def add_fsec(message):
    try:
        if not is_owner(message.from_user.id):
            bot_wallets.reply_to(message, "У вас нет прав для выполнения этой команды.")
            return
        bot_wallets.reply_to(message, "Введите ID кошелька и количество FSEC для добавления (через пробел):")
        bot_wallets.register_next_step_handler(message, process_add_fsec)
    except Exception as e:
        logging.error(f"Error in add_fsec: {e}")

def process_add_fsec(message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot_wallets.reply_to(message, "Неверный формат команды. Используйте: /add_fsec [ID кошелька] [количество FSEC]")
            return
        wallet_id, amount = parts[0], int(parts[1])
        wallet = cursor.execute("SELECT * FROM wallets WHERE wallet_id = ?", (wallet_id,)).fetchone()
        if not wallet:
            bot_wallets.reply_to(message, "Кошелек не найден.")
            return
        cursor.execute("UPDATE wallets SET balance = balance + ? WHERE wallet_id = ?", (amount, wallet_id))
        conn.commit()
        bot_wallets.reply_to(message, f"{amount} FSEC добавлено на кошелек {wallet_id}.")
    except Exception as e:
        logging.error(f"Error in process_add_fsec: {e}")

# Хэндлер для добавления FSEC всем пользователям (только для владельца)
@bot_wallets.message_handler(commands=['add_fsec_to_all'])
def add_fsec_to_all(message):
    try:
        if not is_owner(message.from_user.id):
            bot_wallets.reply_to(message, "У вас нет прав для выполнения этой команды.")
            return
        bot_wallets.reply_to(message, "Введите количество FSEC для добавления всем пользователям:")
        bot_wallets.register_next_step_handler(message, process_add_fsec_to_all)
    except Exception as e:
        logging.error(f"Error in add_fsec_to_all: {e}")

def process_add_fsec_to_all(message):
    try:
        amount = int(message.text)
        cursor.execute("UPDATE wallets SET balance = balance + ?", (amount,))
        conn.commit()
        bot_wallets.reply_to(message, f"{amount} FSEC добавлено всем пользователям.")
    except ValueError:
        bot_wallets.reply_to(message, "Неверный формат команды. Используйте: /add_fsec_to_all [количество FSEC]")
    except Exception as e:
        logging.error(f"Error in process_add_fsec_to_all: {e}")

# Хэндлер для обнуления баланса владельца
@bot_wallets.message_handler(commands=['reset_owner_balance'])
def reset_owner_balance(message):
    try:
        if not is_owner(message.from_user.id):
            bot_wallets.reply_to(message, "У вас нет прав для выполнения этой команды.")
            return
        cursor.execute("UPDATE wallets SET balance = 0 WHERE user_id = ?", (OWNER_ID,))
        conn.commit()
        bot_wallets.reply_to(message, "Баланс владельца обнулен.")
    except Exception as e:
        logging.error(f"Error in reset_owner_balance: {e}")

# Директория для хранения песен
SONGS_DIR = 'songs'
if not os.path.exists(SONGS_DIR):
    os.makedirs(SONGS_DIR)

# Обработчик команды /start для бота песен
@bot_songs.message_handler(commands=['start'])
def send_welcome(message):
    try:
        bot_songs.reply_to(message, "Привет! Я бот для хранения песен. Используй /add для добавления песни и /list для просмотра списка песен.")
    except Exception as e:
        logging.error(f"Error in send_welcome: {e}")

# Обработчик команды /add для бота песен
@bot_songs.message_handler(commands=['add'])
def add_song(message):
    try:
        bot_songs.reply_to(message, "Отправьте мне .mp3 файл, и я сохраню его.")
    except Exception as e:
        logging.error(f"Error in add_song: {e}")

# Обработчик для получения .mp3 файла для бота песен
@bot_songs.message_handler(content_types=['audio'])
def handle_mp3(message):
    try:
        if message.audio and message.audio.mime_type == 'audio/mpeg':
            file_info = bot_songs.get_file(message.audio.file_id)
            downloaded_file = bot_songs.download_file(file_info.file_path)

            # Используем название файла в качестве названия песни
            title = os.path.splitext(message.audio.file_name)[0]
            file_path = os.path.join(SONGS_DIR, f"{title}.mp3")

            with open(file_path, 'wb') as new_file:
                new_file.write(downloaded_file)

            bot_songs.reply_to(message, f"Песня '{title}' успешно добавлена!")
        else:
            bot_songs.reply_to(message, "Пожалуйста, отправьте .mp3 файл.")
    except Exception as e:
        logging.error(f"Error in handle_mp3: {e}")

# Обработчик команды /list для бота песен
@bot_songs.message_handler(commands=['list'])
def list_songs(message):
    try:
        songs = [f for f in os.listdir(SONGS_DIR) if f.endswith('.mp3')]
        if not songs:
            bot_songs.reply_to(message, "Список песен пуст.")
            return

        markup = types.InlineKeyboardMarkup()
        for song in songs:
            title = os.path.splitext(song)[0]
            callback_data = f"send_song_{song}"
            markup.add(types.InlineKeyboardButton(title, callback_data=callback_data))

        bot_songs.send_message(message.chat.id, "Выберите песню:", reply_markup=markup)
    except Exception as e:
        logging.error(f"Error in list_songs: {e}")

# Обработчик нажатия на инлайн-кнопку для бота песен
@bot_songs.callback_query_handler(func=lambda call: call.data.startswith('send_song_'))
def send_song_callback(call):
    try:
        song_filename = call.data.replace('send_song_', '')
        file_path = os.path.join(SONGS_DIR, song_filename)

        if os.path.exists(file_path):
            with open(file_path, 'rb') as audio_file:
                bot_songs.send_audio(call.message.chat.id, audio_file)
        else:
            bot_songs.answer_callback_query(call.id, "Файл не найден.")
    except Exception as e:
        logging.error(f"Error in send_song_callback: {e}")

# Функция для запуска бота в отдельном потоке
def run_bot(bot):
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        logging.error(f"Error in run_bot: {e}")

# Запуск ботов в отдельных потоках
if __name__ == '__main__':
    thread_songs = threading.Thread(target=run_bot, args=(bot_songs,))
    thread_wallets = threading.Thread(target=run_bot, args=(bot_wallets,))

    thread_songs.start()
    thread_wallets.start()

    thread_songs.join()
    thread_wallets.join()

# Закрытие соединения с базой данных при завершении работы
conn.close()
