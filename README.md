# Всё переписать!!!




# Отправляем уведомления о проверке работ
Телеграм бот уведомляет о результатах проверки работ на [dvmn.org](https://dvmn.org/)

## Как установить
Для запуска у вас уже должен быть установлен Python 3.
- Скачайте код
- Установите зависимости командой
```sh
pip install -r requirements.txt
```
### Docker running locally.
Follow the instructions to [download and install Docker](https://docs.docker.com/desktop/)

### Создайте бота
В телеграм с помощью https://t.me/BotFather.
Создайте файл с переменными окружения в папке проекта: "your_project_folder\\.env":
- DEVMAN_ACCESS_TOKEN= <- токен Вашего доступа к [API Devman](https://dvmn.org/api/docs/)  
- TG_BOT_TOKEN= <- токен бота можно узнать в https://t.me/BotFather

## Как использовать
Запустить бот:
```sh
python dvmn_notification_bot.py 123456789
```
где "123456789" - id Вашей учетной записи в телеграм можно узнать https://telegram.me/userinfobot

Как только работа будет проверена, бот пришлёт Вам оповещение, например:

`Преподаватель проверил работу "Отправляем уведомления о проверке работ".
https://dvmn.org/modules/chat-bots/lesson/devman-bot/
К сожалению, в работе нашлись ошибки :(`

Такое же оповещение придёт, если Вы отзовете отправленную работу с проверки.

### Цель проекта
Код написан в образовательных целях на онлайн-курсе для веб-разработчиков [dvmn.org](https://dvmn.org/).

### Authors
[Evgeny Melnikov](https://github.com/MelnikovEI)
