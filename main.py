import telebot, sqlite3, pandas as pd, logging
from datetime import datetime, timedelta
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
        driver_query = """
        SELECT d.driverID, d.firstName, d.lastName, d.dob, d.nationality, d.wins, d.podiums, d.totalRaces, t.teamName
        FROM drivers d
        LEFT JOIN teams t ON d.teamID = t.teamID
        WHERE d.isRetired = 0;
        """
    else:
        driver_query = f"SELECT * FROM drivers WHERE driverID = {driverID}"
    return driver_query

def get_team_info(teamID=None):
    if teamID is None:
        team_query = "SELECT teamID, teamName FROM teams"
    else:
        team_query = f"SELECT * FROM teams WHERE teamID = {teamID}"
    return team_query

def get_race_info(raceID=None):
    if raceID is None:
        race_query = "SELECT * FROM races"
    else:
        race_query = f"SELECT * FROM races WHERE raceID = {raceID}"
    return race_query


"""
Section: with database and table
"""

def table_exists(table_name, connection):
    cur = connection.cursor()
    cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
    return cur.fetchone()


#function to import csv files as tables into f1.db
def import_csv_to_sqlite(csv_file, table_name, connection):
    if not table_exists(table_name, connection):
        df = pd.read_csv(csv_file)
        df.to_sql(table_name, connection, if_exists='replace', index=False)
        print(f"Table '{table_name}' imported successfully from {csv_file}")


#importing csv files
import_csv_to_sqlite('Drivers.csv', 'drivers', conn)
import_csv_to_sqlite('Teams.csv', 'teams', conn)
import_csv_to_sqlite('Races.csv', 'races', conn)


"""
Section: with telegram bot commands
"""

def is_admin(user_id):
    admin_ids = [1140808847,]  # Replace with actual admin IDs
    return user_id in admin_ids


# start page
@bot.message_handler(commands=['start'])
def start(message):
    user_state(message, "start_menu")

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    f1driver = KeyboardButton("F1 Drivers")
    f1team = KeyboardButton("F1 Teams")
    f1race = KeyboardButton("F1 Races (2024)")
    rating = KeyboardButton("Rate a driver 🎖️")
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


@bot.callback_query_handler(func=lambda call: call.data.startswith("page_"))
def handle_page_navigation(call):
    try:

        callback_data_parts = call.data.split("_")

        page = int(callback_data_parts[1])
        context = callback_data_parts[2]

        if context == 'drivers' or context == 'rating':
            columns, rows = get_data_from_db(get_driver_info())
            data = rows
            items_per_page = 8
        elif context == 'teams':
            columns, rows = get_data_from_db(get_team_info())
            data = rows
            items_per_page = 5
        elif context == 'races':
            columns, rows = get_data_from_db(get_race_info())
            data = rows
            items_per_page = 9
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


def send_page(chat_id, page, data, columns, items_per_page, context, message_id=None):
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
        elif context == "races":
            for col_name, value in zip(columns, row):
                if col_name.lower() == "raceid":
                    race_id = value
                elif col_name.lower() == "name":
                    race_name = value
            formatted_row += f"<b>{race_id}. {race_name}</b>\n"
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



def format_results(columns, rows, context):
    result_message = ""
    for row in rows:
        team_name = base_location = None
        if context == "teams":
            for col_name, value in zip(columns, row):
                if col_name.lower() == "teamname":
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
            result_message += f"Base Location: <b>{base_location}</b>\n"
            result_message += f"Principal: <b>{principal}</b>\n"
            result_message += f"Founded Year: <b>{founded_year}</b>\n"
            result_message += f"Championships: <b>{championships}</b>\n"
            result_message += f"Engine Supplier: <b>{engine_supplier}</b>\n\n"
        elif context == "races":
            for col_name, value in zip(columns, row):
                if col_name.lower() == "season":
                    season = value
                elif col_name.lower() == "round":
                    round = value
                elif col_name.lower() == "name":
                    name = value
                elif col_name.lower() == "date":
                    date = value
            result_message += f"<b>{name}</b>\n\n"
            result_message += f"Season: <b>{season}</b>\n"
            result_message += f"Round: <b>{round}</b>\n"
            result_message += f"Date: <b>{date}</b>\n\n"
        else:
            for col_name, value in zip(columns, row):
                if col_name.lower() == "teamname":
                    team_name = value
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
                elif col_name.lower() == "teamname":  # handle teamName from the new query
                    team_name = value
            result_message += f"<b>{first_name} {last_name}</b>\n\n"
            result_message += f"Date of Birth: <b>{dob}</b>\n"
            result_message += f"Nationality: <b>{nationality}</b>\n"
            result_message += f"Team: <b>{team_name}</b>\n"
            result_message += f"Wins: <b>{wins}</b>\n"
            result_message += f"Podiums: <b>{podiums}</b>\n"
            result_message += f"Total Races: <b>{total_races}</b>\n\n"
    return result_message


@bot.message_handler(func=lambda message: message.text == "F1 Drivers")
def list_drivers(message):
    user_state(message, "driver_menu")
    query = get_driver_info()
    columns, drivers_data = get_data_from_db(query)
    send_page(message.chat.id, page=1, data=drivers_data, columns=columns, items_per_page=8, context="drivers")


@bot.callback_query_handler(func=lambda call: call.data.startswith("drivers_"))
def view_driver(call):
    driver_id = call.data.split("_")[1]
    query = f"""
        SELECT d.driverID, d.firstName, d.lastName, d.dob, d.nationality, d.wins, d.podiums, d.totalRaces, t.teamName
        FROM drivers d
        LEFT JOIN teams t ON d.teamID = t.teamID
        WHERE d.isRetired = 0 AND driverID = {driver_id};
        """
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
    send_page(message.chat.id, page=1, data=teams_data, columns=columns, items_per_page=5, context="teams")


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


@bot.message_handler(func=lambda message: message.text == "F1 Races (2024)")
def list_races(message):
    user_state(message, "race_menu")
    query = get_race_info()
    columns, races_data = get_data_from_db(query)
    send_page(message.chat.id, page=1, data=races_data, columns=columns, items_per_page=9, context="races")


@bot.callback_query_handler(func=lambda call: call.data.startswith("races_"))
def view_race(call):
    race_id = call.data.split("_")[1]
    query = get_race_info(race_id)
    columns, race_data = get_data_from_db(query)

    full_race_info = format_results(columns, race_data, context="races")

    bot.send_message(
        chat_id=call.message.chat.id,
        text=f"<b>Race Info:</b>\n\n{full_race_info}",
        parse_mode="HTML"
    )


@bot.message_handler(func=lambda message: message.text == "Rate a driver 🎖️")
def rating_driver(message):
    user_state(message, "rate_menu")
    query = get_driver_info()
    columns, drivers_data = get_data_from_db(query)
    bot.send_message(message.chat.id, message.text)
    send_page(message.chat.id, page=1, data=drivers_data, columns=columns, items_per_page=8, context="rating")


@bot.callback_query_handler(func=lambda call: call.data.startswith("rating_"))
def handle_rating_driver(call):
    user_state(call.message, "handle_rate_menu")
    driver_id = call.data.split("_")[1]

    connection = sqlite3.connect('f1.db')
    cursor = connection.cursor()
    cursor.execute("SELECT firstname, lastname FROM drivers WHERE driverID = ?", (driver_id,))
    result = cursor.fetchone()
    connection.close()

    if result:
        driver_name = f"{result[0]} {result[1]}"
    else:
        driver_name = "Unknown Driver"

    keyboard = InlineKeyboardMarkup(row_width=5)
    buttons = [
        InlineKeyboardButton(
            text=str(i),
            callback_data=f"rated_{i}_{driver_id}"
        ) for i in range(1, 6)
    ]
    keyboard.add(*buttons)

    message_format = f"Rate a driver (Driver of the day):\n<b>{driver_name}</b>"

    bot.send_message(call.message.chat.id, message_format, reply_markup=keyboard, parse_mode="HTML")


def create_rating_table():
    with sqlite3.connect('f1.db') as connection:
        connection.execute("""
        CREATE TABLE IF NOT EXISTS ratingByUser (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            userID INTEGER,
            driverID INTEGER,
            rating INTEGER,
            date_time DATE
        )
        """)

create_rating_table()


@bot.callback_query_handler(func=lambda call: call.data.startswith("rated_"))
def rated_driver(call):
    user_state(call.message, "rated_page_menu")

    user_id = call.from_user.id

    data = call.data.split("_")
    rating = int(data[1])
    driver_id = data[2]

    date_formatted = datetime.now().strftime("%Y-%m-%d")
    day = datetime.now().strftime("%d")

    with sqlite3.connect('f1.db') as connection:
        cur = connection.cursor()
        check_query = "SELECT userID, driverID FROM ratingByUser WHERE userID = ? AND driverID = ? AND strftime('%d', date_time) = ?"
        cur.execute(check_query, (user_id, driver_id, day))

        existing_record = cur.fetchone()

        if existing_record is not None:
            update_query = "UPDATE ratingByUser SET rating = ? WHERE userID = ? AND driverID = ? AND strftime('%d', date_time) = ?"
            cur.execute(update_query, (rating, user_id, driver_id, str(day)))
            connection.commit()
        else:
            insert_query = "INSERT INTO ratingByUser (userID, driverID, rating, date_time) VALUES (?, ?, ?, ?)"
            cur.execute(insert_query,(user_id, driver_id, int(rating), date_formatted))
            connection.commit()

    bot.send_message(call.message.chat.id, f"You gave {rating} out of 5 ⭐s!")


@bot.message_handler(commands=['standings'])
def rating_standings(message):
    user_state(message, "standings_menu")

    get_rating_query = f"""SELECT AVG(r.rating) AS 'rating', d.firstName || ' ' || d.lastName AS 'name', COUNT(r.userID) count_voters, t.teamName
                    FROM ratingByUser r LEFT JOIN drivers d ON r.driverID = d.driverID
                    LEFT JOIN teams t on d.teamID = t.teamID
                    WHERE r.date_time = DATE('now')
                    GROUP BY d.driverID
                    ORDER BY AVG(r.rating) DESC;"""

    winner_driver = f"""SELECT AVG(r.rating) AS 'rating', d.driverID, d.firstName || ' ' || d.lastName AS 'name', COUNT(r.userID) count_voters, t.teamName
                    FROM ratingByUser r LEFT JOIN drivers d ON r.driverID = d.driverID
                    LEFT JOIN teams t on d.teamID = t.teamID
                    WHERE r.date_time = DATE('now', '-1 day')
                    GROUP BY d.driverID
                    ORDER BY AVG(r.rating) DESC
                    LIMIT 1;"""

    with sqlite3.connect('f1.db') as connection:
        cur = connection.cursor()
        cur.execute(winner_driver)

    columns_yes = [description[0] for description in cur.description]
    rows_yes = cur.fetchall()

    with sqlite3.connect('f1.db') as connection:
        cur = connection.cursor()
        cur.execute(get_rating_query)

    today_date = datetime.now().strftime("%Y-%m-%d")
    yesterday_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    result_message = f"<b>Winner ({yesterday_date}):\n</b>"
    for row_yes in rows_yes:
        full_name = row_yes[columns_yes.index("name")]
        team_name = row_yes[columns_yes.index("teamName")]
        result_message += f"<b>{full_name} ({team_name})</b>\n\n"

    columns = [description[0] for description in cur.description]
    rows = cur.fetchall()

    result_message += f"Driver of the day\nDate: <b>{today_date}</b>\n\n"

    i = 1
    for row in rows:
        rating_value = row[columns.index("rating")]
        full_name = row[columns.index("name")]
        count_voters = row[columns.index("count_voters")]
        team_name = row[columns.index("teamName")]
        result_message += f"{i}. <b>{full_name} ({team_name})</b>\n"
        result_message += f"Score: <b>{rating_value:.2f}⭐️ (📢{count_voters} voters)</b>\n\n"
        i += 1

    bot.send_message(message.chat.id, result_message, parse_mode="HTML")


@bot.message_handler(commands=['update'])
def update_driver(message):
    if is_admin(message.from_user.id):
        user_state(message, "update_driver")
        msg = bot.send_message(
            message.chat.id,
            "Send Driver ID and Team ID in the format: <i>(e.g., 5, 5)</i>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, process_update)
    else:
        bot.send_message(message.chat.id, "Only <b>admin</b> is allowed to update the information", parse_mode="HTML")


def process_update(message):
    if get_state(message.from_user.id) == "update_driver":
        try:
            driver_id, team_id = map(int, message.text.split(","))

            with sqlite3.connect('f1.db') as connection:
                cur = connection.cursor()

                update_query = """UPDATE drivers SET teamID = ? WHERE driverID = ?"""
                cur.execute(update_query, (team_id, driver_id))

                select_query = """SELECT d.lastName || ' ' ||  d.firstName as fullname, t.teamName FROM drivers d 
                                    JOIN teams t ON d.teamID = t.teamID
                                    WHERE driverID = ?;"""
                cur.execute(select_query, (driver_id,))
                result = cur.fetchall()

            if result:
                for row in result:
                    fullname, team_name = row
                    bot.send_message(
                        message.chat.id,
                        f"<i>Driver</i>: <b>{fullname}</b> has been assigned to <i>team</i>: <b>{team_name}</b>.",
                        parse_mode="HTML"
                    )
            else:
                bot.send_message(message.chat.id, "No data found.\n\nPlease make sure you have correct DriverID and TeamID.\n\nCommand: /update")
        except ValueError:
            bot.send_message(
                message.chat.id,
                "Invalid format. Please send the data as: <i>Driver ID, Team ID</i> (e.g., 5, 5).",
                parse_mode="HTML"
            )
            process_update(message)


cursor.close()
conn.close()


if __name__ == '__main__':
    bot.infinity_polling()
