import telebot, sqlite3, pandas as pd, logging
from datetime import datetime
from telebot.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup


logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# telegram bot TOKEN and connection
TOKEN = '7216940433:AAHvT6Ovg5iC0yp24N6VOpBgsg4sM06dyQ8'
bot = telebot.TeleBot(TOKEN)

# user related
user_states = {}


def create_table():
    connection = sqlite3.connect('f1.db')  # Using consistent database name
    with connection:
        connection.execute("""
        CREATE TABLE IF NOT EXISTS userStates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            state TEXT,
            date TEXT
        )
        """)
    connection.close()

create_table()

def insert_state(user_id, user_state, now_time):
    connection = sqlite3.connect('f1.db')
    with connection:
        connection.execute(
            "INSERT INTO userStates (user_id, state, date) VALUES (?, ?, ?)",
            (user_id, user_state, now_time)
        )
    connection.close()

def update_state(user_state, user_id):
    connection = sqlite3.connect('f1.db')
    with connection:
        connection.execute(
            "UPDATE userStates SET state = ?, date = ? WHERE user_id = ?",
            (user_state, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id)
        )
    connection.close()

def get_state(user_id):
    connection = sqlite3.connect('f1.db')
    state = ''
    try:
        cursor = connection.cursor()
        cursor.execute("""
        SELECT state 
        FROM userStates 
        WHERE user_id = ? 
        ORDER BY id DESC 
        LIMIT 1
        """, (user_id,))
        result = cursor.fetchone()
        if result:
            state = result[0]
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    finally:
        connection.close()
    return state


def user_state(message, user_state):
    user_id = message.from_user.id
    user_states[message.chat.id] = user_state

    current_state = get_state(user_id)
    now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not current_state:
        insert_state(user_id=user_id, user_state=user_states[message.chat.id], now_time=now_time)
    else:
        update_state(user_state=user_states[message.chat.id], user_id=user_id)


drivers_data = []
teams_data = []


# connection to Database
conn = sqlite3.connect('f1.db', check_same_thread=False)
cursor = conn.cursor()

# sql queries
def get_driver_info(driverID=None):
    if driverID is None:
        driver_query = "SELECT driverID, firstName, lastName FROM drivers"
    else:
        driver_query = f"SELECT * FROM drivers WHERE driverID = {driverID}"
    return driver_query

def get_team_info(teamID=None):
    if teamID is None:
        team_query = "SELECT teamID, teamName FROM teams"
    else:
        team_query = f"SELECT * FROM teams WHERE teamID = {teamID}"
    return team_query


"""
Section: with database and table
"""

def table_exists(table_name, connection):
    cur = connection.cursor()
    cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
    return cursor.fetchone() is not None


#function to import csv files as tables into f1.db
def import_csv_to_sqlite(csv_file, table_name, connection):
    if table_exists(table_name, connection):
        print(f"Table '{table_name}' already exists. Skipping import.")

    else:
        df = pd.read_csv(csv_file)
        df.to_sql(table_name, connection, if_exists='replace', index=False)
        print(f"Table '{table_name}' imported successfully from {csv_file}")


#importing csv files
import_csv_to_sqlite('Drivers.csv', 'drivers', conn)
import_csv_to_sqlite('Teams.csv', 'teams', conn)


"""
Section: with telegram bot commands
"""

def is_admin(user_id):
    return user_id == '1140808847'


# start page
@bot.message_handler(commands=['start'])
def start(message):
    user_state(message, "start_menu")

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    f1driver = KeyboardButton("F1 Drivers")
    f1team = KeyboardButton("F1 Teams")
    f1race = KeyboardButton("F1 Races")
    rating = KeyboardButton("Rate driver 🎖️")
    keyboard.row(f1driver, f1team)
    keyboard.row(f1race, rating)
    bot.send_message(message.chat.id, "Hello 👋!\nThis is a F1 🏎️ Wiki page bot. Currently it is in development 🚧 and this is the demo 🤞 version", reply_markup=keyboard)


# help page
@bot.message_handler(commands=['help'])
def help_page(message):
    user_state(message, "help_menu")
    bot.send_message(message.chat.id, "Overall bot structure:\n\n <b>F1 Drivers </b>\n\n- Driver's full name\n- Date of birth\n"
                                      "- Nationality\n- Driver's Team Name\n- Number of wins\n- Number of podiums\n- Number of races driver attended\n\n"
                                      "<b>F1 Teams</b>\n\n- Team name\n- Headquarter location\n- Principal Name\n- Founded Year\n"
                                      "- Constructor championship wins\n- Engine supplier"
                     , parse_mode="HTML")


def get_data_from_db(query, params=()):
    connection = sqlite3.connect('f1.db')
    cursor = connection.cursor()
    cursor.execute(query, params)
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()
    return columns, rows


def send_page(chat_id, page, data, columns, items_per_page, context, callback_prefix=None, message_id=None):
    start = (page - 1) * items_per_page
    end = start + items_per_page
    page_data = data[start:end]

    keyboard = InlineKeyboardMarkup(row_width=3)
    buttons = [
        InlineKeyboardButton(
            text=str(item[0]),
            callback_data=f"{context}_{item[0]}"
        ) for item in page_data
    ]
    for i in range(0, len(buttons), 3):
        keyboard.add(*buttons[i:i + 3])

    navigation_buttons = []
    if page > 1:
        navigation_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page_{page - 1}_{context}"))
    if end < len(data):
        navigation_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page + 1}_{context}"))
    if navigation_buttons:
        keyboard.add(*navigation_buttons)

    result_message = format_data(columns=columns, rows=page_data, context=context)

    if message_id:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"Page {page} of {((len(data) - 1) // items_per_page) + 1}\n\n{result_message}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except telebot.apihelper.ApiTelegramException:
            bot.send_message(
                chat_id,
                text=f"Page {page} of {((len(data) - 1) // items_per_page) + 1}\n\n{result_message}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    else:
        bot.send_message(
            chat_id,
            text=f"Page {page} of {((len(data) - 1) // items_per_page) + 1}\n\n{result_message}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )


def format_data(columns, rows, context):
    result_message = ""
    for row in rows:
        formatted_row = ""
        if context == "teams":
            for col_name, value in zip(columns, row):
                if col_name.lower() == "teamname":
                    team_name = value
                elif col_name.lower() == "teamid":
                    team_id = value
            formatted_row += f"<b>{team_id}. {team_name}</b>\n"
        else:
            for col_name, value in zip(columns, row):
                if col_name.lower() == "firstname":
                    first_name = value
                elif col_name.lower() == "lastname":
                    last_name = value
                elif col_name.lower() == "driverid":  # assuming 'driverid' is the driver ID column
                    driver_id = value
            formatted_row += f"<b>{driver_id}. {first_name} {last_name}</b>\n"
        result_message += formatted_row
    return result_message


@bot.callback_query_handler(func=lambda call: call.data.startswith("page_"))
def handle_page_navigation(call):
    try:

        callback_data_parts = call.data.split("_")

        page = int(callback_data_parts[1])
        context = callback_data_parts[2]

        if context == 'drivers':
            columns, rows = get_data_from_db(get_driver_info())
            data = rows
            items_per_page = 7
        elif context == 'teams':
            columns, rows = get_data_from_db(get_team_info())
            data = rows
            items_per_page = 5
        else:
            logger.error(f"Unknown context: {context}")
            return

        total_pages = (len(data) - 1) // items_per_page + 1
        if page < 1 or page > total_pages:
            logger.error(f"Page number out of bounds: {page} (total pages: {total_pages})")
            return

        send_page(call.message.chat.id, page=page, data=data, columns=columns, items_per_page=items_per_page, message_id=call.message.message_id, context=context)

    except Exception as e:
        logger.error(f"Error handling page navigation: {e}")
        bot.answer_callback_query(call.id, text="There was an error. Please try again.")


def format_results(columns, rows, context):
    result_message = ""
    for row in rows:
        if context == "teams":
            for col_name, value in zip(columns, row):
                if col_name.lower() == "teamid":
                    team_id = value
                elif col_name.lower() == "teamname":
                    team_name = value
                elif col_name.lower() == "baselocation":
                    base_location = value
                elif col_name.lower() == "principal":
                    principal = value
                elif col_name.lower() == "foundedyear":
                    founded_year = value
                elif col_name.lower() == "championships":
                    championships = value
                elif col_name.lower() == "enginesupplier":
                    engine_supplier = value
            result_message += f"<b>{team_name}</b>\n\n"
            result_message += f"Base Location: {base_location}\n"
            result_message += f"Principal: {principal}\n"
            result_message += f"Founded Year: {founded_year}\n"
            result_message += f"Championships: {championships}\n"
            result_message += f"Engine Supplier: {engine_supplier}\n\n"
        else:
            for col_name, value in zip(columns, row):
                if col_name.lower() == "firstname":
                    first_name = value
                elif col_name.lower() == "lastname":
                    last_name = value
                elif col_name.lower() == "dob":
                    dob = value
                elif col_name.lower() == "nationality":
                    nationality = value
                elif col_name.lower() == "wins":
                    wins = value
                elif col_name.lower() == "podiums":
                    podiums = value
                elif col_name.lower() == "totalraces":
                    total_races = value
            result_message += f"<b>{first_name} {last_name}</b>\n\n"
            result_message += f"Date of Birth: {dob}\n"
            result_message += f"Nationality: {nationality}\n"
            result_message += f"Wins: {wins}\n"
            result_message += f"Podiums: {podiums}\n"
            result_message += f"Total Races: {total_races}\n\n"
    return result_message


@bot.message_handler(func=lambda message: message.text == "F1 Drivers")
def list_drivers(message):
    user_state(message, "driver_menu")
    query = get_driver_info()
    columns, drivers_data = get_data_from_db(query)
    send_page(message.chat.id, page=1, data=drivers_data, columns=columns, items_per_page=7, callback_prefix="drivers", context="drivers")


@bot.callback_query_handler(func=lambda call: call.data.startswith("drivers_"))
def view_driver(call):
    driver_id = call.data.split("_")[1]
    query = f"SELECT * FROM drivers WHERE driverID = {driver_id}"
    columns, driver_data = get_data_from_db(query)

    full_driver_info = format_results(columns, driver_data, context="drivers")

    bot.send_message(
        chat_id=call.message.chat.id,
        text=f"<b>Driver Info:</b>\n\n{full_driver_info}",
        parse_mode="HTML"
    )


@bot.message_handler(func=lambda message: message.text == "F1 Teams")
def list_teams(message):
    user_state(message, "team_menu")
    query = get_team_info()
    columns, teams_data = get_data_from_db(query)
    send_page(message.chat.id, page=1, data=teams_data, columns=columns, items_per_page=5, callback_prefix="teams", context="teams")


@bot.callback_query_handler(func=lambda call: call.data.startswith("teams_"))
def view_team(call):
    team_id = call.data.split("_")[1]
    query = f"SELECT * FROM teams WHERE teamID = {team_id}"
    columns, team_data = get_data_from_db(query)

    full_team_info = format_results(columns, team_data, context="teams")

    bot.send_message(
        chat_id=call.message.chat.id,
        text=f"<b>Team Info:</b>\n\n{full_team_info}",
        parse_mode="HTML"
    )


@bot.message_handler(func=lambda message: message.text == "Rate driver 🎖️")
def rate_driver(message):
    user_state(message, "rate_menu")
    query = get_team_info()
    columns, teams_data = get_data_from_db(query)
    bot.send_message(message.chat.id, message.text)
    send_page(message.chat.id, page=1, data=drivers_data, columns=columns, items_per_page=7, callback_prefix="rate", context="rating")


@bot.callback_query_handler(func=lambda call: call.data.startswith("rate_"))
def handle_rate_driver(call):
    driver_id = call.data.split("_")[1]
    bot.send_message(
        chat_id=call.message.chat.id,
        text=f"You selected driver ID {driver_id} to rate. Please provide your rating."
    )


conn.close()


if __name__ == '__main__':
    bot.infinity_polling()
