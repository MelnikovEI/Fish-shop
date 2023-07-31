import datetime
import logging
import pprint

import redis
import requests
from environs import Env
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    CallbackContext,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

# Stages
FIRST, SECOND = range(2)
# Callback data
START, TWO, THREE, FOUR = range(4)

env = Env()
env.read_env()
BASE_URL = env('BASE_URL')

redis_db = redis.Redis(
    host=env('DATABASE_HOST'), port=env('DATABASE_PORT'), username=env('DATABASE_USERNAME'),
    password=env('DATABASE_PASSWORD'),
    decode_responses=True
)


def get_cms_token():
    expires = redis_db.get('expires')
    if expires and float(expires) > datetime.datetime.timestamp(datetime.datetime.now())+100:
        return redis_db.get('access_token')
    else:
        data = {
            'client_id': env('CMS_CLIENT_ID'),
            'client_secret': env('CMS_CLIENT_SECRET'),
            'grant_type': 'client_credentials',
        }
        url_path = '/oauth/access_token'
        url = f'{BASE_URL}{url_path}'
        response = requests.post(url, data=data)
        response.raise_for_status()
        token_data = response.json()
        redis_db.set('expires', token_data.get('expires'))
        redis_db.set('access_token', token_data.get('access_token'))
        print(token_data.get('expires'), token_data.get('access_token'))
        return token_data.get('access_token')


def get_all_products():
    header = {
        'Authorization': f'Bearer {get_cms_token()}',
        }
    url_path = '/pcm/products'
    url = f'{BASE_URL}{url_path}'
    response = requests.get(url, headers=header)
    response.raise_for_status()
    products_data = response.json()['data']
    # pprint.pprint(products_data)
    products = []
    for product in products_data:
        products.append(
            {
                'name': product['attributes']['name'],
                'id': product['id'],
            }
        )
    return products


def get_product_info(product_id):
    header = {
        'Authorization': f'Bearer {get_cms_token()}',
        }
    params = {
        'filter': f'in(id,{product_id})'
    }
    url_path = '/pcm/products'
    url = f'{BASE_URL}{url_path}'
    response = requests.get(url, headers=header, params=params)
    response.raise_for_status()
    products_data = response.json()['data'][0]
    product_info = [
        products_data['attributes']['name'],
        get_product_price(product_id),
        products_data.get('attributes').get('description', ''),
    ]
    pprint.pprint(products_data)
    return '\n'.join(product_info)


def get_product_price(product_id):
    price_book_id = env('PRICE_BOOK_ID')
    return '$1 per kg'


def start(update: Update, context: CallbackContext) -> int:
    """Send message on `/start`."""
    # Get user that sent /start and log his name
    user = update.message.from_user
    logger.info("User %s started the conversation.", user.first_name)
    # Build InlineKeyboard where each button has a displayed text a string as callback_data
    # The keyboard is a list of button rows, where each row is in turn a list (hence `[[...]]`).
    products = get_all_products()
    buttons = []
    for product in products:
        buttons.append(
            [
                InlineKeyboardButton(product['name'], callback_data=product['id'])
            ]
        )
    keyboard = buttons
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Send message with text and appended InlineKeyboard
    update.message.reply_text('Please, choose:', reply_markup=reply_markup)
    # Tell ConversationHandler that we're in state `FIRST` now
    return FIRST


def start_over(update: Update, context: CallbackContext) -> int:
    """Prompt same text & keyboard as `start` does but not as new message"""
    # Get CallbackQuery from Update
    query = update.callback_query
    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    query.answer()
    products = get_all_products()
    buttons = []
    for product in products:
        buttons.append(
            [
                InlineKeyboardButton(product['name'], callback_data=product['id'])
            ]
        )
    keyboard = buttons
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Instead of sending a new message, edit the message that
    # originated the CallbackQuery. This gives the feeling of an
    # interactive menu.
    query.edit_message_text(text='Please, choose:', reply_markup=reply_markup)
    return FIRST


def show_product_info(update: Update, context: CallbackContext) -> int:
    """Show new choice of buttons"""
    query = update.callback_query
    query.answer()
    keyboard = [
        [
            InlineKeyboardButton("Back to main menu", callback_data=str(START)),
            # InlineKeyboardButton("4", callback_data=str(FOUR)),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    product_id = query.data
    product_info = get_product_info(product_id)
    query.edit_message_text(text=product_info, reply_markup=reply_markup)
    return FIRST


def end(update: Update, context: CallbackContext) -> int:
    """Returns `ConversationHandler.END`, which tells the
    ConversationHandler that the conversation is over.
    """
    query = update.callback_query
    query.answer()
    query.edit_message_text(text="See you next time!")
    return ConversationHandler.END


def main() -> None:
    tg_bot_token = env('TG_BOT_TOKEN')
    updater = Updater(tg_bot_token)
    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher
    # Setup conversation handler with the states FIRST and SECOND
    # Use the pattern parameter to pass CallbackQueries with specific data pattern to the corresponding handlers.
    # ^ means "start of line/string" $ means "end of line/string" So ^ABC$ will only allow 'ABC'
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            FIRST: [
                CallbackQueryHandler(start_over, pattern='^' + str(START) + '$'),
                CallbackQueryHandler(show_product_info),
                # CallbackQueryHandler(two, pattern='^' + str(TWO) + '$'),
                # CallbackQueryHandler(three, pattern='^' + str(THREE) + '$'),
                # CallbackQueryHandler(four, pattern='^' + str(FOUR) + '$'),
            ],
            SECOND: [
                # CallbackQueryHandler(start_over, pattern='^' + str(ONE) + '$'),
                CallbackQueryHandler(end, pattern='^' + str(TWO) + '$'),
            ],
        },
        fallbacks=[CommandHandler('start', start)],
    )

    # Add ConversationHandler to dispatcher that will be used for handling updates
    dispatcher.add_handler(conv_handler)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
