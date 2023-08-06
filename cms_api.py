import datetime
from pathlib import Path
import redis
import requests
from environs import Env

env = Env()


class RedisDB:
    redis_db = None

    @classmethod
    def get_redis_db(cls):
        if not cls.redis_db:
            cls.redis_db = redis.Redis(
                host=env('DATABASE_HOST'), port=env('DATABASE_PORT'), username=env('DATABASE_USERNAME'),
                password=env('DATABASE_PASSWORD'),
                decode_responses=True
            )
        return cls.redis_db


def get_cms_token():
    redis_db = RedisDB.get_redis_db()
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
        url = f'{env("BASE_URL")}{url_path}'
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
    url = f'{env("BASE_URL")}{url_path}'
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
    url = f'{env("BASE_URL")}{url_path}'
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
    url = f'{env("BASE_URL")}{url_path}'
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
    url = f'{env("BASE_URL")}{url_path}'
    response = requests.get(url, headers=header)
    response.raise_for_status()
    image_file_id = response.json()['data'].get('id', '')

    file_path = Path.cwd() / 'images' / image_file_id

    if not file_path.exists():
        url_path = f'/v2/files/{image_file_id}'
        url = f'{env("BASE_URL")}{url_path}'
        response = requests.get(url, headers=header)
        response.raise_for_status()
        image_url = response.json()['data']['link'].get('href', '')

        response = requests.get(image_url, headers=header)
        response.raise_for_status()
        Path(Path.cwd() / 'images').mkdir(parents=True, exist_ok=True)
        with open(file_path, 'wb') as file_to_save:
            file_to_save.write(response.content)
    return file_path


def delete_product_from_cart(user, product_id):
    header = {
        'Authorization': f'Bearer {get_cms_token()}',
        }
    url_path = f'/v2/carts/{user}/items/{product_id}'
    url = f'{env("BASE_URL")}{url_path}'
    response = requests.delete(url, headers=header)
    response.raise_for_status()


def get_cart_products(user):
    header = {
        'Authorization': f'Bearer {get_cms_token()}',
        }
    url_path = f'/v2/carts/{user}/items'
    url = f'{env("BASE_URL")}{url_path}'
    response = requests.get(url, headers=header)
    response.raise_for_status()
    return response.json()


def add_customer_to_cms(user_name, email):
    header = {
        'Authorization': f'Bearer {get_cms_token()}',
    }
    params = {
        'filter': f'eq(email,{email})'
    }
    url_path = f'/v2/customers'
    url = f'{env("BASE_URL")}{url_path}'
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
                'name': user_name,
                'email': email,
            }
        }
        url_path = f'/v2/customers'
        url = f'{env("BASE_URL")}{url_path}'
        response = requests.post(url, headers=header, json=data)
        response.raise_for_status()


def add_product_to_cart(user, quantity, product_id):
    header = {
        'Authorization': f'Bearer {get_cms_token()}',
        }
    url_path = f'/v2/carts/{user}/items'
    url = f'{env("BASE_URL")}{url_path}'
    data = {
        'data': {
            'id': product_id,
            'type': 'cart_item',
            'quantity': int(quantity),
        }
    }
    response = requests.post(url, headers=header, json=data)
    response.raise_for_status()
