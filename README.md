# Fish shop bot
<Бот магазина рыбы>  
[Telegram bot](https://t.me/fish_shop78_bot) - для старта послать боту сообщение `/start`
## Установка
[Установите Python](https://www.python.org/), если этого ещё не сделали. Требуется Python 3.8 и старше. Код может запуститься на других версиях питона от 3.1 и старше, но на них не тестировался.

Проверьте, что `python` установлен и корректно настроен. Запустите его в командной строке:
```sh
python --version
```
Возможно, вместо команды `python` здесь и в остальных инструкциях этого README придётся использовать `python3`. Зависит это от операционной системы и от того, установлен ли у вас Python старой второй версии.

Скачайте код:
```sh
git clone https://github.com/MelnikovEI/Fish-shop.git
```

Перейдите в каталог проекта:
```sh
cd Fish-shop
```

В каталоге проекта создайте виртуальное окружение:
```sh
python -m venv venv
```
Активируйте его. На разных операционных системах это делается разными командами:

- Windows: `.\venv\Scripts\activate`
- MacOS/Linux: `source venv/bin/activate`

Установите зависимости в виртуальное окружение:
```sh
pip install -r requirements.txt
```
### Настройка базы данных
[Создайте базу данных и запишите параметры доступа](https://redislabs.com/)

### Создайте магазин, наполните его продуктами, ценами и опубликуйте каталог 
[elasticpath](https://useast.cm.elasticpath.com/)

### Определите переменные окружения.
Создайте файл `.env` в каталоге `fish-shop/` и положите туда такой код:
```sh
TG_BOT_TOKEN=580108...eWQ
DATABASE_PASSWORD=WMod...qKtEFT
DATABASE_HOST=redis-13872.c55.eu...2.cloud.redislabs.com
DATABASE_PORT=13872
DATABASE_USERNAME=default
BASE_URL=https://useast.api.elasticpath.com
CMS_CLIENT_ID=3Wcy...w61bV
CMS_CLIENT_SECRET=9UE...wThh
```
Данные выше приведены для примера.
- `TG_BOT_TOKEN` замените на токен от чатбота в Telegram. Вот [туториал](https://spark.ru/startup/it-agenstvo-index/blog/47364/kak-poluchit-tokeni-dlya-sozdaniya-chat-bota-v-telegrame-vajbere-i-v-vkontakte), как это сделать.
- `DATABASE ...` параметры доступа к БД Redis
- `BASE_URL` [API Base URL](https://useast.cm.elasticpath.com/application-keys)
- `CMS_CLIENT_ID`, `CMS_CLIENT_SECRET` [Параметры доступа к CMS](https://useast.cm.elasticpath.com/application-keys)
## Запуск
Телеграм бот
```sh
python fish_shop_bot.py
```
Скрипт будет работать до тех пор, пока не будет закрыт.

### Цель проекта
Код написан в образовательных целях на онлайн-курсе для веб-разработчиков [dvmn.org](https://dvmn.org/).
### Authors
[Evgeny Melnikov](https://github.com/MelnikovEI)