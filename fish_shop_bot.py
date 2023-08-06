import logging
from enum import Enum
from pathlib import Path
from environs import Env
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InputMediaPhoto
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    CallbackContext, MessageHandler, Filters,
)
from cms_api import (
    add_product_to_cart, delete_product_from_cart, get_cart_products, get_all_products,
    get_product_details, get_product_image, add_customer_to_cms,
)

logger = logging.getLogger(__name__)
CHOOSE, FILL_CART, HANDLE_CART, WAITING_EMAIL, END = range(5)  # Statuses


class Buttons(Enum):
    START = 0
    CART = -1
    PAY = -2
    LEAVE = -3
    ONE = 1
    FIVE = 5
    TEN = 10


def add_to_cart(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    quantity, product_id = query.data.split(maxsplit=1)
    add_product_to_cart(update.effective_user.id, quantity, product_id)
    return FILL_CART


def delete_from_cart(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    product_id = query.data
    user = update.effective_user.id
    delete_product_from_cart(user, product_id)
    return show_cart(update, context)


def show_cart(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    cart = get_cart_products(update.effective_user.id)
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

    return HANDLE_CART


def start(update: Update, context: CallbackContext) -> int:
    message = update.message
    if message:
        logger.info("User %s started the conversation.", message.from_user.first_name)

    products = get_all_products()
    keyboard = []
    for product in products:
        keyboard.append([InlineKeyboardButton(product['name'], callback_data=product['id'])])
    keyboard.append([InlineKeyboardButton('Cart', callback_data=str(Buttons.CART.value))])
    keyboard.append([InlineKeyboardButton('Leave', callback_data=str(Buttons.LEAVE.value))])
    reply_markup = InlineKeyboardMarkup(keyboard)

    query = update.callback_query
    logo = Path.cwd() / 'images' / 'logo.png'
    with open(logo, 'rb') as photo:
        if query:
            query.answer()
            query.edit_message_media(
                media=InputMediaPhoto(media=photo, caption='Please, choose:'),
                reply_markup=reply_markup
            )
        else:
            update.message.reply_photo(photo=photo, caption='Please, choose:', reply_markup=reply_markup)

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

    return FILL_CART


def pay(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    logo = Path.cwd() / 'images' / 'logo.png'
    with open(logo, 'rb') as photo:
        query.edit_message_media(media=InputMediaPhoto(media=photo, caption='Enter your e-mail, please'))

    return WAITING_EMAIL


def incorrect_email(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("We've got incorrect e-mail from you :(. Please try again.")

    return WAITING_EMAIL


def add_customer(update: Update, context: CallbackContext) -> int:
    user_name = update.effective_user.name
    email = update.message.text
    add_customer_to_cms(user_name, email)
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
    return ConversationHandler.END


def main() -> None:
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    env = Env()
    env.read_env()
    tg_bot_token = env('TG_BOT_TOKEN')
    updater = Updater(tg_bot_token)
    dispatcher = updater.dispatcher
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSE: [
                CallbackQueryHandler(start, pattern=f'^{Buttons.START.value}$'),
                CallbackQueryHandler(show_cart, pattern=f'^{Buttons.CART.value}$'),
                CallbackQueryHandler(end, pattern=f'^{Buttons.LEAVE.value}$'),
                CallbackQueryHandler(show_product),
            ],
            FILL_CART: [
                CallbackQueryHandler(start, pattern=f'^{Buttons.START.value}$'),
                CallbackQueryHandler(show_cart, pattern=f'^{Buttons.CART.value}$'),
                CallbackQueryHandler(add_to_cart),
            ],
            HANDLE_CART: [
                CallbackQueryHandler(start, pattern=f'^{Buttons.START.value}$'),
                CallbackQueryHandler(pay, pattern=f'^{Buttons.PAY.value}$'),
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
    main()
