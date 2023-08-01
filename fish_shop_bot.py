import datetime
import logging
from enum import Enum
from pathlib import Path
import redis
import requests
from environs import Env
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InputMediaPhoto
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
CHOOSE, FILL_CART, HANDLE_CART = range(3)


class Buttons(Enum):
    START = 0
    ONE = 1
    FIVE = 5
    TEN = 10
    CART = -1


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
    products = []
    for product in products_data:
        products.append(
            {
                'name': product['attributes']['name'],
                'id': product['id'],
            }
        )
    return products


def get_product_details(product_id):
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
    product_details = [
        products_data['attributes']['name'],
        get_product_price(product_id),
        products_data.get('attributes').get('description', ''),
    ]
    return '\n'.join(product_details)


def get_product_price(product_id):
    price_book_id = env('PRICE_BOOK_ID')
    return '$1 per kg'


def get_product_image(product_id):
    header = {
        'Authorization': f'Bearer {get_cms_token()}',
        }
    url_path = f'/pcm/products/{product_id}/relationships/main_image'
    url = f'{BASE_URL}{url_path}'
    response = requests.get(url, headers=header)
    response.raise_for_status()
    image_file_id = response.json()['data'].get('id', '')

    file_path = Path.cwd() / 'images' / image_file_id

    if not file_path.exists():
        url_path = f'/v2/files/{image_file_id}'
        url = f'{BASE_URL}{url_path}'
        response = requests.get(url, headers=header)
        response.raise_for_status()
        image_url = response.json()['data']['link'].get('href', '')

        response = requests.get(image_url, headers=header)
        response.raise_for_status()
        Path(Path.cwd() / 'images').mkdir(parents=True, exist_ok=True)
        with open(file_path, 'wb') as file_to_save:
            file_to_save.write(response.content)
        print('Скачал')
    return file_path


def add_to_cart(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    quantity, product_id = query.data.split(maxsplit=1)

    header = {
        'Authorization': f'Bearer {get_cms_token()}',
        }
    url_path = f'/v2/carts/{update.effective_user.id}/items'
    url = f'{BASE_URL}{url_path}'
    data = {
        'data': {
            'id': product_id,
            'type': 'cart_item',
            'quantity': int(quantity),
        }
    }
    response = requests.post(url, headers=header, json=data)
    response.raise_for_status()
    return FILL_CART


def delete_from_cart(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    product_id = query.data

    header = {
        'Authorization': f'Bearer {get_cms_token()}',
        }
    url_path = f'/v2/carts/{update.effective_user.id}/items'
    url = f'{BASE_URL}{url_path}'
    data = {
        'data': {
            'id': product_id,
            'type': 'cart_item',
            'quantity': int(quantity),
        }
    }
    response = requests.post(url, headers=header, json=data)
    response.raise_for_status()
    return FILL_CART


def show_cart(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    header = {
        'Authorization': f'Bearer {get_cms_token()}',
        }
    url_path = f'/v2/carts/{update.effective_user.id}/items'
    url = f'{BASE_URL}{url_path}'
    response = requests.get(url, headers=header)
    response.raise_for_status()
    cart = response.json()
    products = []
    for product in cart['data']:
        products.extend((
            product['name'],
            f"{product['meta']['display_price']['with_tax']['unit']['formatted']} per kg",
            f"{product['quantity']} kg in cart for ${product['value']['amount'] / 100}",
            ''
        ))
    products.append(f"Total: {cart['meta']['display_price']['with_tax']['formatted']}")
    cart_content = 'Your cart:\n\n' + '\n'.join(products)
    
    
    keyboard = [
        [InlineKeyboardButton("-", callback_data=f'{str(Buttons.ONE.value)}'),],
        [InlineKeyboardButton("Back to main menu", callback_data=Buttons.START.value),]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    logo = Path.cwd() / 'images' / 'logo.png'
    with open(logo, 'rb') as photo:
        query.edit_message_media(media=InputMediaPhoto(media=photo, caption=cart_content), reply_markup=reply_markup)

    return HANDLE_CART


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
    buttons.append([InlineKeyboardButton('Cart', callback_data=str(Buttons.CART.value))])
    keyboard = buttons
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Send message with text and appended InlineKeyboard
    # update.message.reply_text('Please, choose:', reply_markup=reply_markup)
    logo = Path.cwd() / 'images' / 'logo.png'
    update.message.reply_photo(photo=open(logo, 'rb'), caption='Please, choose:', reply_markup=reply_markup)
    # Tell ConversationHandler that we're in state `FIRST` now
    return CHOOSE


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
    buttons.append([InlineKeyboardButton('Cart', callback_data=str(Buttons.CART.value))])
    keyboard = buttons
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Instead of sending a new message, edit the message that originated the CallbackQuery. This gives the feeling of an
    # interactive menu.
    # query.edit_message_text(text='Please, choose:', reply_markup=reply_markup)
    logo = Path.cwd() / 'images' / 'logo.png'
    with open(logo, 'rb') as photo:
        query.edit_message_media(media=InputMediaPhoto(media=photo, caption='Please, choose:'), reply_markup=reply_markup)

    return CHOOSE


def show_product(update: Update, context: CallbackContext) -> int:
    """Show new choice of buttons"""
    query = update.callback_query
    query.answer()
    product_id = query.data
    keyboard = [
        [
            InlineKeyboardButton("1 kg", callback_data=f'{str(Buttons.ONE.value)} {product_id}'),
            InlineKeyboardButton("5 kg", callback_data=f'{str(Buttons.FIVE.value)} {product_id}'),
            InlineKeyboardButton("10 kg", callback_data=f'{str(Buttons.TEN.value)} {product_id}'),
        ],
        [InlineKeyboardButton('Cart', callback_data=str(Buttons.CART.value))],
        [InlineKeyboardButton("Back to main menu", callback_data=Buttons.START.value)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    product_details = get_product_details(product_id)
    image = get_product_image(product_id)
    with open(image, 'rb') as photo:
        query.edit_message_media(media=InputMediaPhoto(media=photo, caption=product_details), reply_markup=reply_markup)
    return FILL_CART


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
            CHOOSE: [
                CallbackQueryHandler(start_over, pattern='^' + str(Buttons.START.value) + '$'),
                CallbackQueryHandler(show_cart, pattern='^' + str(Buttons.CART.value) + '$'),
                CallbackQueryHandler(show_product),
            ],
            FILL_CART: [
                CallbackQueryHandler(start_over, pattern='^' + str(Buttons.START.value) + '$'),
                CallbackQueryHandler(show_cart, pattern='^' + str(Buttons.CART.value) + '$'),
                CallbackQueryHandler(add_to_cart),
                # CallbackQueryHandler(end, pattern='^' + str('') + '$'),
            ],
            HANDLE_CART: [
                CallbackQueryHandler(start_over, pattern='^' + str(Buttons.START.value) + '$'),
                # CallbackQueryHandler(end, pattern='^' + str('') + '$'),
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
