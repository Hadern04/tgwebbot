import asyncio
import json
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from flask import Flask, request, jsonify, render_template, redirect, url_for
from threading import Thread
import jinja2

# Вставьте ваш токен
API_TOKEN = "8007919307:AAGkp0nCaIaAFxlS9t7XSLQNewX8vY0dKCU"

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Flask приложение
app = Flask(__name__)
menu_file = "menu.json"


# Загрузка и сохранение меню
def load_menu():
    try:
        with open(menu_file, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return []


def save_menu(new_menu):
    with open(menu_file, "w", encoding="utf-8") as file:
        json.dump(new_menu, file, ensure_ascii=False, indent=4)


menu = load_menu()


# Telegram бота
# Группы категорий
category_groups = {
    "Витрина": [0, 9, 10, 11],
    "Кухня": [1, 2, 3, 4, 5, 6, 12],
    "Бар": [7, 8],
}

# Главное меню
@dp.message(Command("start"))
async def show_main_groups(message: Message):
    builder = InlineKeyboardBuilder()
    for group_name in category_groups.keys():
        builder.row(InlineKeyboardButton(
            text=group_name,
            callback_data=f"group_{group_name}"
        ))
    await message.answer("Выберите раздел:", reply_markup=builder.as_markup())

# Меню категорий в группе
@dp.callback_query(lambda c: c.data.startswith("group_"))
async def show_categories_in_group(callback_query):
    group_name = callback_query.data.split("_", 1)[1]
    group_indices = category_groups.get(group_name)

    if not group_indices:
        await callback_query.answer("Раздел не найден", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for index in group_indices:
        category = menu[index]
        builder.row(InlineKeyboardButton(
            text=category["category"],
            callback_data=f"category_{index}"
        ))
    builder.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_groups"))

    await callback_query.message.edit_text(
        f"Раздел: {group_name}\n\nВыберите категорию:",
        reply_markup=builder.as_markup()
    )

# Возврат в главное меню с группами
@dp.callback_query(lambda c: c.data == "back_to_groups")
async def back_to_main_groups(callback_query):
    builder = InlineKeyboardBuilder()
    for group_name in category_groups.keys():
        builder.row(InlineKeyboardButton(
            text=group_name,
            callback_data=f"group_{group_name}"
        ))
    await callback_query.message.edit_text("Что вас сегодня интересует?:", reply_markup=builder.as_markup())

# Меню товаров в категории
@dp.callback_query(lambda c: c.data.startswith("category_"))
async def show_items_in_category(callback_query):
    category_index = int(callback_query.data.split("_")[1])
    category = menu[category_index]

    builder = InlineKeyboardBuilder()
    for idx, item in enumerate(category["items"]):
        builder.row(InlineKeyboardButton(
            text=item["title"],
            callback_data=f"item_{category_index}_{idx}"
        ))
    builder.row(InlineKeyboardButton(text="⬅ Назад", callback_data=f"group_{find_group_by_category(category_index)}"))
    try:
        await callback_query.message.edit_text(
            f"Категория: {category['category']}\n\nВыберите товар:",
            reply_markup=builder.as_markup()
        )
    except Exception:
        await callback_query.message.delete()
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=f"Категория: {category['category']}\n\nВыберите товар:",
            reply_markup=builder.as_markup()
        )

# Возвращение названия группы по индексу категории
def find_group_by_category(category_index):
    for group_name, indices in category_groups.items():
        if category_index in indices:
            return group_name
    return None

# Информация о товаре
@dp.callback_query(lambda c: c.data.startswith("item_"))
async def show_item_details(callback_query):
    category_index, item_index = map(int, callback_query.data.split("_")[1:3])
    category = menu[category_index]
    item = category["items"][item_index]

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅ Назад", callback_data=f"category_{category_index}"))
    await callback_query.message.edit_media(
        InputMediaPhoto(
            media=item["image"],
            caption=f"**{item['title']}**\n\n{item['description']}",
            parse_mode="Markdown"
        ),
        reply_markup=builder.as_markup()
    )


# Flask админка
@app.route("/")
def admin_panel():
    return render_template("admin.html", menu=menu)


@app.route("/add_category", methods=["POST"])
def add_category():
    new_category = request.form.get("category")
    if new_category:
        menu.append({"category": new_category, "items": []})
        save_menu(menu)
    return redirect(url_for("admin_panel"))


@app.route("/delete_category/<int:category_id>")
def delete_category(category_id):
    if 0 <= category_id < len(menu):
        menu.pop(category_id)
        save_menu(menu)
    return redirect(url_for("admin_panel"))


@app.route("/add_item/<int:category_id>", methods=["POST"])
def add_item(category_id):
    if 0 <= category_id < len(menu):
        new_item = {
            "title": request.form.get("title"),
            "image": request.form.get("image"),
            "description": request.form.get("description"),
        }
        menu[category_id]["items"].append(new_item)
        save_menu(menu)
    return redirect(url_for("admin_panel"))


@app.route("/delete_item/<int:category_id>/<int:item_id>")
def delete_item(category_id, item_id):
    if 0 <= category_id < len(menu) and 0 <= item_id < len(menu[category_id]["items"]):
        menu[category_id]["items"].pop(item_id)
        save_menu(menu)
    return redirect(url_for("admin_panel"))


# Запуск бота и Flask
def run_flask():
    app.run(port=5000)


def run_bot():
    asyncio.run(dp.start_polling(bot))


if __name__ == "__main__":
    Thread(target=run_flask).start()
    run_bot()
