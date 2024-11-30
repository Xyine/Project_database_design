import telebot
from telebot.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
import sqlite3

TOKEN = '7216940433:AAHvT6Ovg5iC0yp24N6VOpBgsg4sM06dyQ8'
bot = telebot.TeleBot(TOKEN)

# user related
user_ids = []
user_states = {}


def connect_db():
    connection = sqlite3.connect('f1.db')
    cursor = connection.cursor()
    cursor.close()
    connection.close()


def is_admin(user_id):
    return user_id == '1140808847'

@bot.message_handler(commands=['start'])
def start(message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    button1 = KeyboardButton("F1 Drivers")
    button2 = KeyboardButton("F1 Teams")
    keyboard.row(button1, button2)
    bot.send_message(message.chat.id, "Hello!\n This is a F1 Wikipage bot. Currently it is in development and this is the demo version", reply_markup=keyboard)


if __name__ == '__main__':
    bot.infinity_polling()