from telethon.sync import TelegramClient
from telethon import functions, types

with TelegramClient("namess:", "29400566", "8fd30dc496aea7c14cf675f59b74ec6f") as client:
    result = client(functions.account.CheckUsernameRequest(
        username='agens'
    ))
    print(result)
