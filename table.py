from flask import Flask, render_template, request, send_file, url_for, jsonify
import os
from io import BytesIO
import re
import qrcode
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__, static_folder='static')
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Функция для создания QR кода из ссылки
def create_qr_code(url):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # Создаем QR-код с белым фоном
    img = qr.make_image(fill_color="black", back_color="white")

    # Преобразуем QR-код в формат RGBA
    img = img.convert("RGBA")
    datas = img.getdata()

    newData = []
    for item in datas:
        # Заменяем белый цвет (255, 255, 255) на прозрачный (255, 255, 255, 0)
        if item[0] == 255 and item[1] == 255 and item[2] == 255:
            newData.append((255, 255, 255, 0))
        else:
            newData.append(item)

    img.putdata(newData)
    return img

def create_base_layout(logo_file, icon_filenames, text_fields):
    # Создание изображения с прозрачным фоном
    table_image = Image.new("RGBA", (2258, 2258), (255, 255, 255, 0))

    # Загрузка и изменение размера логотипа
    logo = Image.open(logo_file.stream)
    logo = logo.convert("RGBA")  # Преобразование логотипа в формат RGBA
    original_width, original_height = logo.size
    new_height = 200
    new_width = int(original_width * (new_height / original_height))
    logo = logo.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Расчет координат для наложения логотипа (выравнивание по центру)
    x = (table_image.width - logo.width) // 2
    y = 250  # Отступ сверху
    table_image.paste(logo, (x, y), logo)

    # Координаты для размещения иконок
    icon_coords = [(650, 600), (650, 1630), (650, 1860)]

    for icon_filename, (x, y) in zip(icon_filenames, icon_coords):
        icon_path = os.path.join(app.static_folder, 'icons', icon_filename)
        icon = Image.open(icon_path).convert("RGBA")
        # Можно добавить изменение размера иконки, если это необходимо
        table_image.paste(icon, (x - icon.width // 2, y), icon)

    # Добавление текста
    draw = ImageDraw.Draw(table_image)
    try:
        # Попытка использовать шрифт Times New Roman, если он установлен
        font = ImageFont.truetype("times.ttf", 150)
    except IOError:
        # Использование стандартного шрифта, если Times New Roman недоступен
        font = ImageFont.load_default()

    text_coords = [(820, 600), (820, 1630), (820, 1860)]
    for text, (x, y) in zip(text_fields, text_coords):
        draw.text((x, y), text, fill="black", font=font)

    return table_image

@app.route('/icons')
def get_icons():
    icons_dir = os.path.join(app.static_folder, 'icons')
    icons = [f for f in os.listdir(icons_dir) if os.path.isfile(os.path.join(icons_dir, f))]
    return jsonify(icons)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_table():
    # Получение данных из формы
    logo = request.files['logo']
    icon_filenames = [
        request.form['icon1'],
        request.form['icon2'],
        request.form['icon3']
    ]
    text_fields = [request.form['text1'], request.form['text2'], request.form['text3']]
    addresses = [addr.strip() for addr in request.form['addresses'].split('\n') if addr.strip()]

    # Создание общего макета таблички (без QR-кода)
    base_image = create_base_layout(logo, icon_filenames, text_fields)

    # Для каждого адреса создаем уникальный QR-код и накладываем его на макет
    for address in addresses:
        table_image = base_image.copy()
        qr_image = create_qr_code(address)
        qr_image = qr_image.resize((600, 600), Image.Resampling.LANCZOS)

        # Выравнивание QR-кода по центру и 950 пикселей от верха
        x = (table_image.width - qr_image.width) // 2
        y = 950
        table_image.paste(qr_image, (x, y), qr_image)

        # Сохранение изображения с QR-кодом
        image_filename = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '', address) + ".png"
        png_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
        table_image.save(png_path, format="PNG", dpi=(300, 300))

    return "Таблички успешно созданы!"

if __name__ == '__main__':
    app.run(debug=True)