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
    CallbackContext, MessageHandler, Filters,
)

logger = logging.getLogger(__name__)

env = Env()
env.read_env()
BASE_URL = env('BASE_URL')

CHOOSE, FILL_CART, HANDLE_CART, WAITING_EMAIL, END = range(5)  # Statuses


class Buttons(Enum):
    START = 0
    CART = -1
    PAY = -2
    LEAVE = -3
    ONE = 1
    FIVE = 5
    TEN = 10


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


def get_product_price(product_id):
    header = {
        'Authorization': f'Bearer {get_cms_token()}',
    }
    url_path = f'/catalog/products/{product_id}'
    url = f'{BASE_URL}{url_path}'
    response = requests.get(url, headers=header)
    response.raise_for_status()
    price_data = response.json()['data']
    product_price = int(price_data['attributes']['price']['USD']['amount'])/100
    return f'${product_price} per kg'


def get_product_details(product_id):
    header = {
        'Authorization': f'Bearer {get_cms_token()}',
        }
    params = {
        'filter': f'eq(id,{product_id})'
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
    redis_db.hset(update.effective_user.id, mapping={'status': FILL_CART})
    return FILL_CART


def delete_from_cart(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    cart_item_id = query.data

    header = {
        'Authorization': f'Bearer {get_cms_token()}',
        }
    url_path = f'/v2/carts/{update.effective_user.id}/items/{cart_item_id}'
    url = f'{BASE_URL}{url_path}'
    response = requests.delete(url, headers=header)
    response.raise_for_status()
    return show_cart(update, context)


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
    keyboard = []
    for product in cart['data']:
        products.extend((
            product['name'],
            f"{product['meta']['display_price']['with_tax']['unit']['formatted']} per kg",
            f"{product['quantity']} kg in cart for ${product['value']['amount'] / 100}",
            ''
        ))
        keyboard.append(
            [
                InlineKeyboardButton(f"Remove from cart {product['name']}", callback_data=f"{product['id']}")
            ]
        )
    products.append(f"Total: {cart['meta']['display_price']['with_tax']['formatted']}")
    cart_content = 'Your cart:\n\n' + '\n'.join(products)

    keyboard.append([InlineKeyboardButton("Pay", callback_data=Buttons.PAY.value)])
    keyboard.append([InlineKeyboardButton("Back to main menu", callback_data=Buttons.START.value)])

    reply_markup = InlineKeyboardMarkup(keyboard)
    logo = Path.cwd() / 'images' / 'logo.png'
    with open(logo, 'rb') as photo:
        query.edit_message_media(media=InputMediaPhoto(media=photo, caption=cart_content), reply_markup=reply_markup)

    redis_db.hset(update.effective_user.id, mapping={'status': HANDLE_CART})
    return HANDLE_CART


def start(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    logger.info("User %s started the conversation.", user.first_name)
    products = get_all_products()
    keyboard = []
    for product in products:
        keyboard.append([InlineKeyboardButton(product['name'], callback_data=product['id'])])
    keyboard.append([InlineKeyboardButton('Cart', callback_data=str(Buttons.CART.value))])
    keyboard.append([InlineKeyboardButton('Leave', callback_data=str(Buttons.LEAVE.value))])
    reply_markup = InlineKeyboardMarkup(keyboard)

    logo = Path.cwd() / 'images' / 'logo.png'
    with open(logo, 'rb') as photo:
        update.message.reply_photo(photo=photo, caption='Please, choose:', reply_markup=reply_markup)
    redis_db.hset(update.effective_user.id, mapping={'status': CHOOSE})
    return CHOOSE


def start_over(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    products = get_all_products()
    keyboard = []
    for product in products:
        keyboard.append(
            [
                InlineKeyboardButton(product['name'], callback_data=product['id'])
            ]
        )
    keyboard.append([InlineKeyboardButton('Cart', callback_data=str(Buttons.CART.value))])
    keyboard.append([InlineKeyboardButton('Leave', callback_data=str(Buttons.LEAVE.value))])
    reply_markup = InlineKeyboardMarkup(keyboard)

    logo = Path.cwd() / 'images' / 'logo.png'
    with open(logo, 'rb') as photo:
        query.edit_message_media(
            media=InputMediaPhoto(media=photo, caption='Please, choose:'),
            reply_markup=reply_markup
        )
    redis_db.hset(update.effective_user.id, mapping={'status': CHOOSE})
    return CHOOSE


def show_product(update: Update, context: CallbackContext) -> int:
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

    redis_db.hset(update.effective_user.id, mapping={'status': FILL_CART})
    return FILL_CART


def pay(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    logo = Path.cwd() / 'images' / 'logo.png'
    with open(logo, 'rb') as photo:
        query.edit_message_media(media=InputMediaPhoto(media=photo, caption='Enter your e-mail, please'))

    redis_db.hset(update.effective_user.id, mapping={'status': WAITING_EMAIL})
    return WAITING_EMAIL


def incorrect_email(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("We've got incorrect e-mail from you :(. Please try again.")

    redis_db.hset(update.effective_user.id, mapping={'status': WAITING_EMAIL})
    return WAITING_EMAIL


def add_customer(update: Update, context: CallbackContext) -> int:
    email = update.message.text
    header = {
        'Authorization': f'Bearer {get_cms_token()}',
    }
    params = {
        'filter': f'eq(email,{email})'
    }
    url_path = f'/v2/customers'
    url = f'{BASE_URL}{url_path}'
    response = requests.get(url, headers=header, params=params)
    response.raise_for_status()
    customer_from_cms = response.json()

    if not customer_from_cms['data']:
        header = {
            'Authorization': f'Bearer {get_cms_token()}',
            }
        data = {
            'data': {
                'type': 'customer',
                'name': update.effective_user.name,
                'email': email,
            }
        }
        url_path = f'/v2/customers'
        url = f'{BASE_URL}{url_path}'
        response = requests.post(url, headers=header, json=data)
        response.raise_for_status()

    return end(update, context)


def end(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    if query:
        query.answer()
        logo = Path.cwd() / 'images' / 'logo.png'
        with open(logo, 'rb') as photo:
            query.edit_message_media(media=InputMediaPhoto(media=photo, caption='Thank you! See you next time!'))
    else:
        update.message.reply_text('Thank you! See you next time!')
    redis_db.hset(update.effective_user.id, mapping={'status': END})
    return ConversationHandler.END


def main() -> None:
    tg_bot_token = env('TG_BOT_TOKEN')
    updater = Updater(tg_bot_token)
    dispatcher = updater.dispatcher
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSE: [
                CallbackQueryHandler(start_over, pattern='^' + str(Buttons.START.value) + '$'),
                CallbackQueryHandler(show_cart, pattern='^' + str(Buttons.CART.value) + '$'),
                CallbackQueryHandler(end, pattern='^' + str(Buttons.LEAVE.value) + '$'),
                CallbackQueryHandler(show_product),
            ],
            FILL_CART: [
                CallbackQueryHandler(start_over, pattern='^' + str(Buttons.START.value) + '$'),
                CallbackQueryHandler(show_cart, pattern='^' + str(Buttons.CART.value) + '$'),
                CallbackQueryHandler(add_to_cart),
            ],
            HANDLE_CART: [
                CallbackQueryHandler(start_over, pattern='^' + str(Buttons.START.value) + '$'),
                CallbackQueryHandler(pay, pattern='^' + str(Buttons.PAY.value) + '$'),
                CallbackQueryHandler(delete_from_cart),
            ],
            WAITING_EMAIL: [
                MessageHandler(Filters.entity('email'), add_customer),
                MessageHandler(Filters.all, incorrect_email)
            ],
        },
        fallbacks=[CommandHandler('start', start)],
    )

    dispatcher.add_handler(conv_handler)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    main()
