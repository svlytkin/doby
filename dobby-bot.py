# -*- coding: utf-8 -*-
# [] перенести время напоминания
#   [] через реплай
#   [✓] через команду !
#   [✓] через поиск только даты в сообщении, и предыдущее отправил бот
#   [✓] сделать обновление в бд, а не дописывание
# [✓] ввод даты после отправки сообщения
# [✓] дописывать 0 в начале (или придумать другой вариант), если цифра одна 2 15 | ?215? 
# [✓] преобразовывать даты в даты, а время в время
# [✓] поменять время в пн, вт итд на 9 утра
# [✓] сделать даты 30го
# [] 1267 у меня возвращает 12часов 67минут, минуты должны быть между 0 и 59
# [] сделать относительные даты – завтра, вечером, днем, утром, через неделю, через мес, через Х часов/минут/?секунд?
# [] отменить последнее действие через клавиатуру и текст
# [] добавить поддержку таймзоны

# сервер
# [] сделать чтобы работал на сервере
# [] чтобы в телеграм приходили ошибки
 
# украшения
# [✓] вывести дату и время в норм формате в сообщении, что принял напоминание – не понятно как сделать вывод человеческого дня "четверг", "мая" и тд
# [✓] убрать дату из сообщения напоминания
# [] убрать слова напомни/напомнить из сообщения напоминания

# ошибки
# [] напоминание приходит раньше на несколько секунд http://take.ms/c1X5e

import app
import re
import sqlite3, os, sys
import locale
import telebot
import threading
from datetime import datetime
from datetime import timedelta
from dateutil import parser
from dateutil.relativedelta import relativedelta
from threading import Event, Thread
from collections import defaultdict

# подключаем бота
api_token = app.your_token
bot = telebot.TeleBot(api_token)

interval = 5 #интвервал проверки базы данных в секундах
tz_delta = app.tz_delta #временно делаю мск таймзону
default_time = 9 # время, во сколько ставится напоминание по умолчанию, если не задано время
default_time_str = '090000'
dic = defaultdict(list)
hours = ""
minutes = ""
seconds = ""

if sys.platform == 'win32':
    locale.setlocale(locale.LC_ALL, 'rus_rus')
else:
    locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')

cur_dir = os.getcwd() #получаем папку, где находится файл
DB = os.path.join(cur_dir, 'tg.db') # возвращаем адрес базы данных
try:
    con = sqlite3.connect(DB) # подсоединяемся к базе, стандартный метод
    cur = con.cursor() # ?? как-то подключаем бд, чтобы с ней чтобы делать
except sqlite3.Error as e:
    print(u'Ошибка при подключении к базе %s' % DB)
    sys.exit(1)

try:
    cur.execute("SELECT rowid from reminders limit 0,1") # выполняем запрос к базе данных – проверяем, есть такая база или нет
    con.close()
except sqlite3.Error as e :  
    sql = """CREATE TABLE "reminders" ("chat_id" ,"messages", "created_at" DATETIME, "remind_at" DATETIME)"""
    con.close()


# --- Функции ---
class RussianParserInfo(parser.parserinfo):
    WEEKDAYS = [("пн", "Понедельник"),
                ("вт", "Вторник"),
                ("ср", "Среда"),
                ("чт", "Четверг"),
                ("пт", "Пятница"),
                ("сб", "Суббота"),
                ("вс", "Воскресенье")]

    MONTHS = [('Jan', 'January', 'ян', 'янв', 'января', 'январь'), 
                ('Feb', 'February', 'фев', 'февраля', 'февраль'), 
                ('Mar', 'March', 'мар', 'марта', 'март'), 
                ('Apr', 'April', 'апр', 'апреля', 'апрель'), 
                ('May', 'мая', 'май'), 
                ('Jun', 'June', 'июня', 'июнь'), 
                ('Jul', 'July', 'июля', 'июль'), 
                ('Aug', 'August', 'авг', 'августа', 'август'),
                ('Sep', 'Sept', 'September', 'сент', 'сен', 'сентября', 'сентябрь'),
                ('Oct', 'October', 'окт', 'октября', 'октябрь'),
                ('Nov', 'November', 'ноя', 'ноября', 'ноябрь'),
                ('Dec', 'December', 'дек', 'декабря', 'декабрь')]
    HMS = [("h", "hour", "hours", "ч", "часов", "час"),
                ("m", "minute", "minutes", "мин", "минут", "минуту", "минута"),
                ("s", "second", "seconds", "с", "сек", "секунд", "секунду", "секунда")]
    JUMP = [" ", ".", ",", ";", "-", "/", "'",
            "at", "on", "and", "ad", "m", "t", "of",
            "st", "nd", "rd", "th", "в", 'во', "напомни"]
    AMPM = [("am", "a", "утра"),
            ("pm", "p", "вечера")]
    UTCZONE = ["UTC", "GMT", "Z"]
    PERTAIN = ["of"]  

def sql_fetchall(sql):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    con.close()
    return rows

def sql_commit(sql):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute(sql)
    con.commit()
    con.close()

def check_message_len(message_to_check):
    not_date_str = ''.join(message_to_check) 
    if len(not_date_str)>25:
        message_to_send = not_date_str[:25].rstrip()+'...'
    else:
        message_to_send = not_date_str[:25]
    return message_to_send

def search_date_pattern(string_to_search):
    rem_time = default_time_str
    rem_date = datetime.now()
    dic.clear()
    regex_wd = '(?:' + ('|'.join(['|'.join(day) for day in RussianParserInfo.WEEKDAYS])) + ')'
    re_patterns = {
                    'td_h_dm':['(?:^|\s+)([0-9]{1,2})\s+([0-9]{1,2}(?:/|-|–)[0-9]{1,2})(?:$|\s+)'],
                    'td_dm_h':['(?:^|\s+)([0-9]{1,2}(?:/|-|–)[0-9]{1,2})\s+([0-9]{1,2})(?:$|\s+)'],
                    'date_d/m':['(?:^|\s*)[0-9]{1,2}(?:/|-|–)[0-9]{1,2}(?:$|\s+)'],
                    'time_d2d2': ['(?:^|\s+)([0-9]{1,2}(?:\s+|\:)[0-9]{1,2})(?:$|\s+)'],
                    'time_d4': ['(?:^|\s+)[0-9]{4}(?:$|\s+)'],
                    'date_go': ['(?:^|\s+)[0-9]{2}(?:го|/)(?:$|\s+)'],
                    'time_d6': ['(?:^|\s+)[0-9]{6}(?:$|\s+)'],
                    'time_d2_day': ['([0-9]{1,2}) '+ regex_wd],
                    'time_in_d2': ['в [0-9]{1,2}'],
                    'time_end_d2': [' [0-9]{1,2}$'],
                    'time_begin_d2': ['^[0-9]{1,2}'],
                    'time_only': ['^\s+[0-9]{1,2}\s+$'],
                    'alone_d': ['[0-9]{1,2}']}
    clear_value = ""
    for key, value in re_patterns.items():
        print(key, value, string_to_search)
        re_v = re.findall(value[0],string_to_search)
        print(re_v, 're_v', type(re_v))
        re_v = [i for t in re_v for i in t] if all(isinstance(t, tuple) for t in re_v) else re_v
        print(re_v, 're_v', type(re_v))
        for item in re_v:
            print (item)
            # clear_value = re.findall('[0-9]{2}',value)
            if 'time' in key:
                clear_value = "".join(filter(str.isdigit, item))
                clear_value = ('0' + clear_value if len(clear_value)%2 == 1 else clear_value) 
                clear_value = "{:<06}".format(clear_value)
                rem_time = clear_value
            elif 'date' in key:
                clear_value = re.sub('[-–/(го)]', '/', item)
                print(item, 'item')
                days, months, years, *oth = clear_value.split('/') + ['']
                days = int(days)
                months = datetime.now().month if months == '' else int(months)
                months = 1 if months > 12 else months
                years = datetime.now().year if years == '' else int(years)
                rem_date = rem_date.replace(day = days, month = months, year = years)  
                rem_date = rem_date + relativedelta(months=1) if datetime.now() > rem_date else rem_date
                clear_value = rem_date
            elif 'td_' in key:
                print('td')
                if any(x in item for x in ['-', '–', '/', 'го']):
                    clear_value = re.sub('[-–/(го)]', '/', item)
                    print(item, 'item')
                    days, months, years, *oth = clear_value.split('/') + ['']
                    days = int(days)
                    months = datetime.now().month if months == '' else int(months)
                    years = datetime.now().year if years == '' else int(years)
                    rem_date = rem_date.replace(day = days, month = months, year = years)
                    rem_date = rem_date + timedelta(months=1) if datetime.now() > rem_date else rem_date
                    clear_value = rem_date
                else:
                    clear_value = "".join(filter(str.isdigit, item))
                    clear_value = ('0' + clear_value if len(clear_value)%2 == 1 else clear_value)
                    clear_value = "{:<06}".format(clear_value)
                    rem_time = clear_value
            else:
                clear_value = item
            dic[key].append(clear_value)
            dic['rem_time'].append(rem_time)
            dic['rem_date'].append(rem_date)
            string_to_search = (string_to_search.replace(item.strip(),'')).strip()
            print(clear_value, type(clear_value), 'clear_value')
            print(dic, 'dic')
            print(string_to_search, 'string_to_search')
    return string_to_search, dic

def extract_date(chat_message):
    remind_at = ''
    chat_message, dic = search_date_pattern(chat_message)
    not_date_list = chat_message

    print(dic, 'dic ex')
    try:
        hours = int(dic["rem_time"][-1][:2])
        minutes = int(dic["rem_time"][-1][2:4])
        seconds = int(dic["rem_time"][-1][4:6])
        remind_at = dic["rem_date"][-1].replace(hour = hours, minute = minutes, second = seconds, microsecond=0)
        remind_at = remind_at + timedelta(days=1) if datetime.now() > remind_at else remind_at
        # [] если дата больше сегодня то + месяц       
        # + не переносить время, типа если уже больще 9 утра       
        print(remind_at, 'ext_date')
        try:
            remind_at, not_date_list = parser.parse(chat_message, default=datetime.now().replace(hourdefault_time, minute = 0, second = 0, microsecond = 0), parserinfo=RussianParserInfo(), fuzzy_with_tokens=True) # ищем дату в сообщении
            remind_at = remind_at.replace(hour = hours, minute = minutes, second = seconds, microsecond=0)
            case = 'dateutil + custom date'
        except:
            case = 'custom date'
    except:
        try:
            remind_at, not_date_list = parser.parse(chat_message, default=datetime.now().replace(hour = default_time, minute = 0, second = 0, microsecond = 0), parserinfo=RussianParserInfo(), fuzzy_with_tokens=True) # ищем дату в сообщении
            case = 'dateutil date'
        except:
            remind_at = datetime.now().replace(hour=default_time, minute=0, second=0,  microsecond=0)
            if datetime.now() > remind_at:
                remind_at = remind_at + timedelta(days=1)
            case = 'no date'
    return remind_at, not_date_list, case, chat_message 

def only_date_in_mes(message):
    if extract_date(message.text)[3] is not '':
        try:
            date, list2 = parser.parse(message.text, default=datetime.now().replace(hour = default_time, minute = 0, second = 0, microsecond = 0), parserinfo=RussianParserInfo(), fuzzy_with_tokens=True) #list2 - список слов без даты
            list2 = ' '.join(list2).split()
            list3 = [x for x in list2 if x not in RussianParserInfo.JUMP] # может можно убрать not здесь и в строке ниже?
            return not list3
        except:
            return False
    else:
        return True

# / --- Функции ---

@bot.message_handler(func=only_date_in_mes)
@bot.message_handler(regexp="^!.+")
def upd_reminder(message):
    print(message.text)
    # upd_remind_at, not_date_list = parser.parse(message.text, parserinfo=RussianParserInfo(), fuzzy_with_tokens=True)
    upd_remind_at = extract_date(message.text)[0]
    last_message = sql_fetchall('select rowid, * from reminders where (user_id = "{}") and (chat_id = "{}") order by created_at desc limit 1'.format(message.from_user.id, message.chat.id))
    last_message = list(last_message[-1])
    print(last_message[-1], type(last_message[-1]))
    last_reminder = sql_fetchall('select * from last_reminders where (user_id = "{}") and (chat_id = "{}") order by reminder_sent_at desc limit 1'.format(message.from_user.id, message.chat.id))
    last_reminder = list(last_reminder[-1])
    if last_message[-1] < last_reminder[-1]: #[] -1  – это таймстэмп, когда создан, лучше сюда переменную всатавить, чтобы не потерялся, если случайно перенесу столбец с таймстэмпом
        sql_commit('insert into reminders (user_id, chat_id, messages, remind_at, message_id, created_at) values ("{}", "{}", "{}", "{}", "{}", "{}")'.format(last_reminder[0], last_reminder[1], last_reminder[2], upd_remind_at, message.message_id, int(datetime.today().timestamp())))
        bot.send_message(last_reminder[1], 'перенёс на {}  ·  {}'.format(datetime.strftime(upd_remind_at, "%-H:%M, %a %-d %B"), check_message_len(last_reminder[2])))
    else:
        sql_commit('update reminders set remind_at = "{}" where (user_id = "{}") and (chat_id = "{}") and (rowid = "{}")'.format(upd_remind_at,last_message[1], last_message[2], last_message[0]))
        mes_cut_date = extract_date(last_message[3])[1]
        bot.send_message(message.chat.id, 'перенёс на {}  ·  {}'.format(datetime.strftime(upd_remind_at,  "%-H:%M, %a %-d %B"), check_message_len(mes_cut_date)))

@bot.message_handler()
def add_message(message): # Название функции не играет никакой роли, в принципе
    # записываем сообщение, дату создания и дату напоминания в базу
    # remind_at, not_date_list = parser.parse(message.text, parserinfo=RussianParserInfo(), fuzzy_with_tokens=True) # ищем дату в сообщении
    remind_at, not_date_list, case = extract_date(message.text)[0:3]
    print (not_date_list, 'not_date_list')
    if case == 'no date':
        print('no date case')
        sql_commit('insert into reminders (user_id, chat_id, messages, remind_at, message_id, created_at) values ("{}", "{}", "{}", "{}", "{}", "{}")'.format(message.from_user.id, message.chat.id, message.text, remind_at, message.message_id, int(datetime.today().timestamp())))
        bot.send_message(message.chat.id, 'хорошо, напомню завтра в {} утра, или введите дату — перенесу'.format(default_time))
    else:
        print('case', case)
        con = sqlite3.connect(DB)
        cur = con.cursor()
        sql_commit('insert into reminders (user_id, chat_id, messages, remind_at, message_id, created_at) values ("{}", "{}", "{}", "{}", "{}", "{}")'.format(message.from_user.id, message.chat.id, message.text, remind_at, message.message_id, int(datetime.today().timestamp())))
        # bot.reply_to(message, 'ок, напомню в {}'.format(datetime.strftime(remind_at,  "%H:%M, %a %d %B"))) 
        bot.send_message(message.chat.id, 'напомню в {}  ·  {}'.format(datetime.strftime(remind_at,  "%-H:%M, %a %-d %B"), check_message_len(not_date_list))) 

def send_reminder():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    reminders = sql_fetchall('select user_id, chat_id, messages, message_id, created_at from reminders where (remind_at >= "{}") and (remind_at < "{}")'.format(datetime.strftime(datetime.now()+timedelta(hours=tz_delta), "%Y-%m-%d %H:%M:%S"), datetime.strftime(datetime.now()+timedelta(seconds=interval)+timedelta(hours=tz_delta), "%Y-%m-%d %H:%M:%S")))
    print('select user_id, chat_id, messages, message_id, created_at from reminders where (remind_at >= "{}") and (remind_at < "{}")'.format(datetime.strftime(datetime.now()+timedelta(hours=tz_delta), "%Y-%m-%d %H:%M:%S"), datetime.strftime(datetime.now()+timedelta(seconds=interval)+timedelta(hours=tz_delta), "%Y-%m-%d %H:%M:%S")))
    for reminder in reminders:
        # [] вырезать слова напомни / напомнить, в, через, след
        try:
            cur.executescript('update last_reminders set user_id = "{uid}", chat_id = "{ch_id}", last_reminder_text = "{m_text}", reminder_message_id = "{mes_id}", reminder_sent_at = "{s_at}" where (user_id = "{uid}") and (chat_id = "{ch_id}");insert into last_reminders (user_id, chat_id, last_reminder_text, reminder_message_id, reminder_sent_at) select "{uid}", "{ch_id}", "{m_text}", "{mes_id}", "{s_at}" where (select Changes() = 0)'.format(uid=reminder[0], ch_id=reminder[1], m_text=reminder[2], mes_id=reminder[3], s_at=int(datetime.today().timestamp())))
            con.commit()
            con.close()
            bot.send_message(reminder[1], f"⏰ {reminder[2]}")
        except ValueError as e:
            pass

def call_repeatedly(interval, func):
    stopped = Event()
    def loop():
        while not stopped.wait(interval):
            func()
    Thread(target=loop).start()    
    return stopped.set
    
cancel_future_calls = call_repeatedly(interval, send_reminder)  

bot.polling(none_stop=True)