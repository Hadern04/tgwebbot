import asyncio
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from threading import Thread
from models import db, Category, Item
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio
import json
import jinja2

def import_json_to_db():
    with open("menu.json", "r", encoding="utf-8") as file:
        menu_data = json.load(file)

    for category_data in menu_data:
        category = Category(name=category_data["category"])
        print(category)
        db.session.add(category)
        db.session.commit()

        for item_data in category_data["items"]:
            item = Item(
                title=item_data["title"],
                image=item_data["image"],
                description=item_data["description"],
                category_id=category.id
            )
            db.session.add(item)
        db.session.commit()

# --- ИНИЦИАЛИЗАЦИЯ ---
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///menu.db"
app.config["SECRET_KEY"] = "supersecretkey"
db.init_app(app)

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)

# --- БОТ ТЕЛЕГРАМ ---
bot = Bot(token="8007919307:AAGkp0nCaIaAFxlS9t7XSLQNewX8vY0dKCU")
dp = Dispatcher()
# Загрузка и сохранение меню
def load_menu():
    try:
        with open("menu.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return []


def save_menu(new_menu):
    with open("menu.json", "w", encoding="utf-8") as file:
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


# --- МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ ---
class User(UserMixin):
    id = 1
    username = "admin"
    password = bcrypt.generate_password_hash("admin").decode("utf-8")

@login_manager.user_loader
def load_user(user_id):
    return User()

# --- АДМИН-ПАНЕЛЬ ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        print(f"Введён логин: {username}, пароль: {password}")  # Отладочный вывод
        if username == "admin" and bcrypt.check_password_hash(User().password, password):
            login_user(User())
            print("Вход выполнен успешно!")
            return redirect(url_for("admin_panel"))
        else:
            print("Ошибка авторизации!")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def admin_panel():
    categories = Category.query.all()
    return render_template("admin.html", categories=categories)

@app.route("/add_category", methods=["POST"])
@login_required
def add_category():
    name = request.form.get("name")
    if name:
        db.session.add(Category(name=name))
        db.session.commit()
    return redirect(url_for("admin_panel"))

@app.route("/delete_category/<int:category_id>")
@login_required
def delete_category(category_id):
    Category.query.filter_by(id=category_id).delete()
    db.session.commit()
    return redirect(url_for("admin_panel"))

@app.route("/update_item/<int:item_id>", methods=["POST"])
@login_required
def update_item(item_id):
    item = Item.query.get(item_id)
    if item:
        item.title = request.form.get("title", item.title)
        item.image = request.form.get("image", item.image)
        item.description = request.form.get("description", item.description)
        db.session.commit()
    return redirect(url_for("admin_panel"))

# --- БОТ ---
@dp.message(Command("start"))
async def show_main_groups(message: Message):
    builder = InlineKeyboardBuilder()
    for category in Category.query.all():
        builder.row(InlineKeyboardButton(text=category.name, callback_data=f"category_{category.id}"))
    await message.answer("Выберите категорию:", reply_markup=builder.as_markup())

@dp.callback_query(lambda c: c.data.startswith("category_"))
async def show_items(callback_query):
    category_id = int(callback_query.data.split("_")[1])
    category = Category.query.get(category_id)
    builder = InlineKeyboardBuilder()
    for item in category.items:
        builder.row(InlineKeyboardButton(text=item.title, callback_data=f"item_{item.id}"))
    await callback_query.message.edit_text(f"Категория: {category.name}", reply_markup=builder.as_markup())

@dp.callback_query(lambda c: c.data.startswith("item_"))
async def show_item(callback_query):
    item_id = int(callback_query.data.split("_")[1])
    item = Item.query.get(item_id)
    await callback_query.message.edit_media(
        InputMediaPhoto(media=item.image, caption=f"{item.title}\n\n{item.description}")
    )

# --- ЗАПУСК ---
def run_flask():
    with app.app_context():
        db.create_all()
        import_json_to_db()
        print("Данные успешно импортированы!")
    app.run(port=5000)

def run_bot():
    asyncio.run(dp.start_polling(bot))

if __name__ == "__main__":
    Thread(target=run_flask).start()
    run_bot()
