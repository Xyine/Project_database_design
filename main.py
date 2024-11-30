import telebot, sqlite3, pandas as pd, logging
from telebot.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup


logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# telegram bot TOKEN and connection
TOKEN = '7216940433:AAHvT6Ovg5iC0yp24N6VOpBgsg4sM06dyQ8'
bot = telebot.TeleBot(TOKEN)

# user related
user_ids = []
user_states = {}


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
import_csv_to_sqlite('Races.csv', 'races', conn)
import_csv_to_sqlite('Teams.csv', 'teams', conn)


"""
Section: with telegram bot commands
"""

def is_admin(user_id):
    return user_id == '1140808847'


# start page
@bot.message_handler(commands=['start'])
def start(message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    f1driver = KeyboardButton("F1 Drivers")
    f1team = KeyboardButton("F1 Teams")
    f1race = KeyboardButton("F1 Races")
    keyboard.row(f1driver, f1team)
    bot.send_message(message.chat.id, "Hello 👋!\nThis is a F1 🏎️ Wiki page bot. Currently it is in development 🚧 and this is the demo 🤞 version", reply_markup=keyboard)


# help page
@bot.message_handler(commands=['help'])
def help_page(message):
    bot.send_message(message.chat.id, "Overall bot structure:\n\n <b>F1 Drivers </b>\n\n- Driver's full name\n- Date of birth\n"
                                      "- Nationality\n- Driver's Team Name\n- Number of wins\n- Number of podiums\n- Number of races driver attended\n\n"
                                      "<b>F1 Teams</b>\n\n- Team name\n- Headquarter location\n- Principal Name\n- Founded Year\n"
                                      "- Constructor championship wins\n- Engine supplier"
                     , parse_mode="HTML")


def formatting(columns, rows):
    result_message = ""
    for row in rows:
        formatted_row = ""
        firstname = ""
        lastname = ""
        driverID = ""
        for col_name, value in zip(columns, row):
            if col_name.lower() == "firstname":
                firstname = value
            elif col_name.lower() == "lastname":
                lastname = value
            else:
                driverID = value
        if firstname and lastname and driverID:
            full_value = f"{driverID}. {firstname} {lastname}"
            formatted_row += f"<b>{full_value}</b>\n"
        result_message += formatted_row
    return result_message


@bot.message_handler(func=lambda message: message.text == "F1 Drivers")
def list_drivers(message):
    global drivers_data
    cursor.execute(get_driver_info())
    drivers_data = cursor.fetchall()
    send_driver_page(message.chat.id, page=1)


def send_driver_page(chat_id, page=1, message_id=None):
    global drivers_data
    cursor.execute(get_driver_info())
    drivers = cursor.fetchall()
    columns = [description[0] for description in cursor.description]

    items_per_page = 7
    start = (page - 1) * items_per_page
    end = start + items_per_page
    page_drivers = drivers_data[start:end]

    keyboard = InlineKeyboardMarkup(row_width=3)
    buttons = [
        InlineKeyboardButton(
            text=str(driver[0]),  # Assuming the first column is driver ID
            callback_data=f"driver_{driver[0]}"
        ) for driver in page_drivers
    ]
    for i in range(0, len(buttons), 3):
        keyboard.add(*buttons[i:i + 3])
    navigation_buttons = []
    if page > 1:
        navigation_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page_{page - 1}"))
    if end < len(drivers_data):
        navigation_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page + 1}"))
    if navigation_buttons:
        keyboard.add(*navigation_buttons)

    result_message = formatting(columns, drivers[start:end])
    if message_id:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"Page {page} of {((len(drivers_data) - 1) // items_per_page) + 1}\n\nChoose a driver: \n\n{result_message}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except telebot.apihelper.ApiTelegramException:
            bot.send_message(
                chat_id,
                text=f"Page {page} of {((len(drivers_data) - 1) // items_per_page) + 1}\n\nChoose a driver: \n\n{result_message}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    else:
        bot.send_message(
            chat_id,
            text=f"Page {page} of {((len(drivers_data) - 1) // items_per_page) + 1}\n\nChoose a driver: \n\n{result_message}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )


# Callback query handler for navigation
@bot.callback_query_handler(func=lambda call: call.data.startswith("page_"))
def handle_page_navigation(call):
    page = int(call.data.split("_")[1])
    send_driver_page(call.message.chat.id, page, message_id=call.message.message_id)


#format the structure of the query result
def format_results(columns, rows):
    result_message = ""
    for row in rows:
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

        # Concatenate all the relevant details into the message
        result_message += f"<b>{first_name} {last_name}</b>\n\n"
        result_message += f"Date of Birth: {dob}\n"
        result_message += f"Nationality: {nationality}\n"
        result_message += f"Wins: {wins}\n"
        result_message += f"Podiums: {podiums}\n"
        result_message += f"Total Races: {total_races}\n\n"
    return result_message


@bot.callback_query_handler(func=lambda call: call.data.startswith("driver_"))
def f1_driver(call):
    driver_id = call.data.split("_")[1]
    cursor.execute(get_driver_info(driver_id))
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()
    result_message = format_results(columns, rows)
    bot.send_message(
        chat_id=call.message.chat.id,
        text=result_message,
        parse_mode="HTML"
    )


@bot.message_handler(func=lambda message: message.text == "F1 Teams")
def list_teams(message):
    global teams_data
    cursor.execute(get_team_info())
    teams_data = cursor.fetchall()
    send_team_page(message.chat.id, page=1)


def formatting_team(columns, rows):
    result_message = ""
    for row in rows:
        formatted_row = ""
        teamName = ""
        teamID = ""
        for col_name, value in zip(columns, row):
            if col_name.lower() == "teamname":
                teamName = value
            else:
                teamID = value
        if teamName and teamID:
            full_value = f"{teamID}. {teamName}"
            formatted_row += f"<b>{full_value}</b>\n"
        result_message += formatted_row
    return result_message


def send_team_page(chat_id, page=1, message_id=None):
    global teams_data
    cursor.execute(get_team_info())
    teams = cursor.fetchall()
    columns = [description[0] for description in cursor.description]

    items_per_page = 5
    start = (page - 1) * items_per_page
    end = start + items_per_page
    page_teams = teams_data[start:end]

    keyboard = InlineKeyboardMarkup(row_width=3)
    buttons = [
        InlineKeyboardButton(
            text=str(team[0]),
            callback_data=f"team_{team[0]}"
        ) for team in page_teams
    ]
    for i in range(0, len(buttons), 3):
        keyboard.add(*buttons[i:i + 3])

    navigation_buttons = []
    if page > 1:
        navigation_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"teampage_{page - 1}"))
    if end < len(teams_data):
        navigation_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"teampage_{page + 1}"))
    if navigation_buttons:
        keyboard.add(*navigation_buttons)

    result_message = formatting_team(columns, teams[start:end])
    if message_id:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"Page {page} of {((len(teams_data) - 1) // items_per_page) + 1}\n\nChoose a team: \n\n{result_message}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            print(e)
    else:
        bot.send_message(
            chat_id,
            text=f"Page {page} of {((len(teams_data) - 1) // items_per_page) + 1}\n\nChoose a team: \n\n{result_message}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("teampage_"))
def handle_page_navigation(call):
    page = int(call.data.split("_")[1])
    send_team_page(call.message.chat.id, page, message_id=call.message.message_id)


def format_team_results(columns, rows):
    result_message = ""
    for row in rows:
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

        # Concatenate all the relevant details into the message
        result_message += f"<b>{team_name}</b>\n\n"
        result_message += f"Base Location: {base_location}\n"
        result_message += f"Principal: {principal}\n"
        result_message += f"Founded Year: {founded_year}\n"
        result_message += f"Championships: {championships}\n"
        result_message += f"Engine Supplier: {engine_supplier}\n\n"
    return result_message



@bot.callback_query_handler(func=lambda call: call.data.startswith("team_"))
def f1_driver(call):
    team_id = call.data.split("_")[1]
    cursor.execute(get_team_info(team_id))
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()
    result_message = format_team_results(columns, rows)
    bot.send_message(
        chat_id=call.message.chat.id,
        text=result_message,
        parse_mode="HTML"
    )


cursor.close()
conn.close()


if __name__ == '__main__':
    bot.infinity_polling()
