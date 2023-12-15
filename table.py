from flask import Flask, render_template, request, send_file, url_for, jsonify, after_this_request, Response, stream_with_context
import os
from io import BytesIO
import re
import qrcode
from PIL import Image, ImageDraw, ImageFont
from werkzeug.datastructures import FileStorage
import shutil
import tempfile
import uuid
import zipfile
import io

app = Flask(__name__, static_folder='static')
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Функция для создания QR кода из ссылки
def create_qr_code(url):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=0,
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
    # Проверка типа логотипа и его загрузка
    if isinstance(logo_file, FileStorage):  # Flask-загруженный файл
        logo = Image.open(logo_file.stream)
    else:  # Стандартный файловый объект Python
        logo = Image.open(logo_file)
    logo = logo.convert("RGBA")  # Преобразование логотипа в формат RGBA
    original_width, original_height = logo.size
    new_height = 250
    new_width = int(original_width * (new_height / original_height))
    logo = logo.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Расчет координат для наложения логотипа (выравнивание по центру)
    x = (table_image.width - logo.width) // 2
    y = 250  # Отступ сверху
    table_image.paste(logo, (x, y), logo)

    # Координаты для размещения иконок
    icon_coords = [(650, 600), (650, 1630), (650, 1860)]

    for icon_filename, (x, y) in zip(icon_filenames, icon_coords):
        if "default/" in icon_filename:
            icon_path = os.path.join(app.static_folder, icon_filename)
        else:
            icon_path = os.path.join(app.static_folder, 'icons', icon_filename)
        icon = Image.open(icon_path).convert("RGBA")

        # Изменение размера иконки
        original_width, original_height = icon.size
        new_width = 200
        new_height = int(original_height * (new_width / original_width))
        icon = icon.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Наложение иконки с учетом новых размеров
        x = x - new_width // 2  # Центрирование иконки по горизонтали
        table_image.paste(icon, (x, y), icon)

    # Добавление текста
    draw = ImageDraw.Draw(table_image)
    try:
        # Попытка использовать шрифт Times New Roman, если он установлен
        font = ImageFont.truetype("times.ttf", 120)
    except IOError:
        # Использование стандартного шрифта, если Times New Roman недоступен
        font = ImageFont.load_default()

    text_coords = [(820, 600), (820, 1630), (820, 1860)]
    for text, (x, y) in zip(text_fields, text_coords):
        draw.text((x, y), text, fill="black", font=font)

    return table_image

def get_form_data(request):
    # Значения по умолчанию

    default_logo_path = 'static/default/logo.png'
    default_icon_paths = ['default/wifi.png', 'default/msg.png', 'default/call.png']

    # Получение логотипа или использование логотипа по умолчанию
    logo = request.files.get('logo') or default_logo_path

    # Получение иконок или использование иконок по умолчанию
    icon_filenames = [
        request.form.get('icon1') or default_icon_paths[0],
        request.form.get('icon2') or default_icon_paths[1],
        request.form.get('icon3') or default_icon_paths[2]
    ]
    text_fields = [
        request.form.get('text1') or "Текст 1",
        request.form.get('text2') or "Текст 2",
        request.form.get('text3') or "Текст 3"
    ]
    addresses = request.form.get('addresses', '').splitlines()
    return logo, icon_filenames, text_fields, [address.strip() for address in addresses if address.strip()]

@app.route('/preview-update', methods=['POST'])
def preview_update():
    # Извлечение данных из запроса
    logo, icon_filenames, text_fields, _ = get_form_data(request)

    # Генерация предпросмотра макета
    preview_image = create_base_layout(logo, icon_filenames, text_fields)

    # Загрузка QR-кода по умолчанию
    qr_default_path = os.path.join(app.static_folder, 'default', 'qr.png')
    qr_image = Image.open(qr_default_path).convert("RGBA")

    # Выравнивание QR-кода по центру и 850 пикселей от верха
    x = (preview_image.width - qr_image.width) // 2
    y = 850
    preview_image.paste(qr_image, (x, y), qr_image)

    # Конвертация изображения в байты и отправка клиенту
    byte_io = BytesIO()
    preview_image.save(byte_io, 'PNG')
    byte_io.seek(0)
    return send_file(byte_io, mimetype='image/png')

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
    logo, icon_filenames, text_fields, addresses = get_form_data(request)
    base_url = request.form.get('base_url')  # Получение основного URL из формы

    # Создаем основное изображение
    base_image = create_base_layout(logo, icon_filenames, text_fields)

    # Создаем BytesIO объект для хранения ZIP-файла
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        # Для каждого адреса создаем QR код и добавляем в ZIP
        for address in addresses:
            full_url = f"{base_url}{address}"  # Формирование полного URL
            table_image = base_image.copy()
            qr_image = create_qr_code(full_url)  # Создание QR-кода для полного URL
            qr_image = qr_image.resize((600, 600), Image.Resampling.LANCZOS)

            # Выравнивание QR-кода по центру и 850 пикселей от верха
            x = (table_image.width - qr_image.width) // 2
            y = 850
            table_image.paste(qr_image, (x, y), qr_image)

            # Сохраняем изображение в BytesIO объект
            img_byte_arr = BytesIO()
            table_image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            zf.writestr(f'{address}.png', img_byte_arr.getvalue())

    memory_file.seek(0)

    def generate():
        with memory_file:
            yield memory_file.getvalue()

    return Response(
        stream_with_context(generate()),
        mimetype='application/zip',
        headers={
            'Content-Disposition': 'attachment; filename=table_images.zip'
        }
    )


if __name__ == '__main__':
    app.run(debug=True)